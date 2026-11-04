"""Private Unix transport; controller policy belongs to bettercnc_controller."""

import argparse
import asyncio
import contextlib
import os
import signal
import socket
import stat
import struct
import tempfile
from pathlib import Path

from bettercnc_error_records import install_exception_hooks, report

from ._controller_runtime import ControllerRuntime
from ._protocol import MAX_FRAME_BYTES, ProtocolError, decode, encode, health

IO_TIMEOUT = 2.0
MAX_CLIENTS = 8


def default_socket() -> Path:
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir())
    return runtime / "betterlinuxcnc" / "control.sock"


async def serve(
    path: Path,
    *,
    ini_path=None,
    controller_factory=None,
    process_factory=None,
    status_reader_factory=None,
    stop_event=None,
    cam_inbox=None,
) -> None:
    """Embed the service with explicit controller/process seams and shutdown.

    Factory injection is a host API, never a socket parameter. The command
    channel is created only after an owner attaches; no machine is auto-started.
    """
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory = path.parent.lstat()
    if (
        not stat.S_ISDIR(directory.st_mode)
        or directory.st_uid != os.getuid()
        or stat.S_IMODE(directory.st_mode) & 0o077
    ):
        raise ValueError("socket directory must be owned by this user with mode 0700")

    clients: set[asyncio.Task] = set()
    runtime = None

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.current_task()
        assert task is not None
        if len(clients) >= MAX_CLIENTS:
            writer.close()
            await writer.wait_closed()
            return
        clients.add(task)
        owner = object()
        ids = set()

        async def watch_disconnect():
            # StreamReader learns EOF even while an executor command is pending.
            # Cancellation invalidates queued work in release(), before close.
            while True:
                if reader.at_eof():
                    task.cancel()
                    return
                await asyncio.sleep(0.05)

        watcher = asyncio.create_task(watch_disconnect())
        try:
            while True:
                async with asyncio.timeout(IO_TIMEOUT):
                    header = await reader.readexactly(4)
                    size = struct.unpack("!I", header)[0]
                    if not 0 < size <= MAX_FRAME_BYTES:
                        return
                    payload = await reader.readexactly(size)
                request = None
                try:
                    request = decode(payload)
                    if request.version == 1:
                        result = health(request)
                    else:
                        if request.request_id in ids:
                            raise ProtocolError(
                                "duplicate_request", "a request_id cannot be replayed"
                            )
                        if len(ids) >= 100000:
                            raise ProtocolError(
                                "session_limit", "reconnect to open a fresh session"
                            )
                        ids.add(request.request_id)
                        result = await runtime.handle(owner, request.method, request.params)
                    reply = encode(request.version, request.request_id, result=result)
                except ProtocolError as error:
                    report("service", "protocol_error", str(error))
                    reply = encode(
                        request.version if request else error.version,
                        request.request_id if request else error.request_id,
                        error=error,
                    )
                except (ValueError, OSError, RuntimeError) as error:
                    report("service", "request_error", str(error))
                    reply = encode(
                        request.version if request else 2,
                        request.request_id if request else "",
                        error=ProtocolError("service_error", str(error)),
                    )
                async with asyncio.timeout(IO_TIMEOUT):
                    writer.write(struct.pack("!I", len(reply)) + reply)
                    await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError, TimeoutError):
            pass
        finally:
            watcher.cancel()
            await asyncio.gather(watcher, return_exceptions=True)
            await runtime.release(owner)
            clients.discard(task)
            writer.close()
            with contextlib.suppress(ConnectionError):
                await writer.wait_closed()

    stopped = stop_event or asyncio.Event()
    loop = asyncio.get_running_loop()
    signals = (signal.SIGINT, signal.SIGTERM) if stop_event is None else ()
    for sig in signals:
        loop.add_signal_handler(sig, stopped.set)

    # Bind ourselves: never unlink another service's endpoint on startup.
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    identity = None
    try:
        listener.bind(str(path))
        identity = path.lstat()
        path.chmod(0o600)
        listener.setblocking(False)
        runtime = ControllerRuntime(
            ini_path, controller_factory, process_factory, status_reader_factory, cam_inbox
        )
        server = await asyncio.start_unix_server(handle, sock=listener, limit=MAX_FRAME_BYTES)
        async with server:
            print(f"Local controller service ready: {path}", flush=True)
            await stopped.wait()
    finally:
        listener.close()
        pending = list(clients)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        if runtime is not None:
            await runtime.close()
        if identity is not None:
            with contextlib.suppress(FileNotFoundError):
                current = path.lstat()
                if (current.st_dev, current.st_ino) == (identity.st_dev, identity.st_ino):
                    path.unlink()
        for sig in signals:
            loop.remove_signal_handler(sig)


def main() -> None:
    install_exception_hooks("service")
    parser = argparse.ArgumentParser(description="BetterLinuxCNC local controller service")
    parser.add_argument("--socket", type=Path, default=default_socket())
    parser.add_argument("--ini", type=Path)
    parser.add_argument(
        "--cam-inbox", type=Path, help="allow explicit CAM jobs from this private inbox"
    )
    args = parser.parse_args()
    try:
        asyncio.run(
            serve(
                args.socket.absolute(),
                ini_path=str(args.ini.absolute()) if args.ini else None,
                cam_inbox=args.cam_inbox.absolute() if args.cam_inbox else None,
            )
        )
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Cannot start local service: {exc}\n")
