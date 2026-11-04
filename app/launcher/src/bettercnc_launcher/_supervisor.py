"""Own child processes; supervise services without replaying machine commands."""

import contextlib
import fcntl
import json
import os
import signal
import stat
import subprocess
import time
from pathlib import Path

from bettercnc_error_records import report

from ._ipc import quiescent, status


class RecoveryBlocked(RuntimeError):
    pass


class StopFlag:
    """Signal handlers must not take the lock used by threading.Event.wait()."""

    def __init__(self):
        self.requested = False

    def set(self):
        self.requested = True

    def is_set(self):
        return self.requested

    def wait(self, seconds):
        deadline = time.monotonic() + seconds
        while not self.requested:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(remaining, 0.05))
        return self.requested


def _private_directory(path):
    path.mkdir(parents=True, mode=0o700, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError(f"目录必须属于当前用户且权限为 0700：{path}")


def _log_directory(path, shared):
    if not shared:
        _private_directory(path)
        return
    try:
        path.mkdir(parents=True, mode=0o2750)
    except FileExistsError:
        pass
    else:
        # Override the runtime's private umask only for traversable log folders.
        # setgid preserves the maintenance group provisioned on the log root.
        path.chmod(0o2750)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o027:
        raise ValueError(f"日志目录必须属于当前用户，且组不可写、其他用户不可访问：{path}")


class Child:
    def __init__(self, name, command, logs, env, generation):
        self.name = name
        self.log = logs / f"{name}-{generation}.log"
        self._terminal = None
        terminal_input = None
        with self.log.open("xb") as output:
            if env.get("BETTERCNC_SHARE_LOGS") == "1":
                os.fchmod(output.fileno(), 0o640)
            if name == "linuxcnc" and env.get("BETTERCNC_KIOSK") == "1":
                # Upstream selects terminal-only error reporting with `tty -s`.
                # Keep the master alive without writing input or exposing a shell.
                master, slave = os.openpty()
                self._terminal = os.fdopen(master, "rb", buffering=0)
                terminal_input = os.fdopen(slave, "rb", buffering=0)
            try:
                self.process = subprocess.Popen(
                    command,
                    stdin=terminal_input if terminal_input is not None else subprocess.DEVNULL,
                    stdout=output,
                    stderr=subprocess.STDOUT,
                    env=env,
                    start_new_session=True,
                )
            except BaseException:
                if self._terminal is not None:
                    self._terminal.close()
                raise
            finally:
                if terminal_input is not None:
                    terminal_input.close()
        print(f"已启动 {name}，PID {self.process.pid}，日志 {self.log}", flush=True)

    def stop(self, timeout, *, force=True):
        if self.process.poll() is not None:
            if self._terminal is not None:
                self._terminal.close()
            return True
        with contextlib.suppress(ProcessLookupError):
            os.killpg(self.process.pid, signal.SIGTERM)
        try:
            self.process.wait(timeout=timeout)
            if self._terminal is not None:
                self._terminal.close()
            return True
        except subprocess.TimeoutExpired:
            if not force:
                return False
            with contextlib.suppress(ProcessLookupError):
                os.killpg(self.process.pid, signal.SIGKILL)
            self.process.wait()
            if self._terminal is not None:
                self._terminal.close()
            return True


class Runtime:
    def __init__(self, config, *, keep_alive=True):
        self.config = config
        self.keep_alive = keep_alive
        self.service = self.native = self.cam = None
        self.stop = StopFlag()
        self.logs = self.env = self.socket_identity = None
        self.generation = 0
        self._last_state = None

    def _spawn(self, name, command):
        self.generation += 1
        return Child(name, command, self.logs, self.env, self.generation)

    def _publish(self, phase):
        record = {"phase": phase, "pid": os.getpid(), "ini": str(self.config.ini)}
        record["processes"] = {
            child.name: child.process.pid
            for child in (self.service, self.native, self.cam)
            if child is not None and child.process.poll() is None
        }
        if record == self._last_state:
            return
        pending = self.logs / "state.tmp"
        pending.write_text(json.dumps(record, ensure_ascii=False))
        pending.replace(self.logs / "state.json")
        self._last_state = record

    def _check_children(self):
        for child in (self.service, self.native, self.cam):
            if child is not None and child.process.poll() is not None:
                raise RuntimeError(
                    f"{child.name} 已退出（{child.process.returncode}），日志 {child.log}"
                )

    def _wait(self, description, ready):
        deadline = time.monotonic() + self.config.startup_timeout
        last = ""
        while not self.stop.is_set():
            self._check_children()
            try:
                if ready():
                    print(f"{description}就绪", flush=True)
                    return
            except (OSError, ValueError) as error:
                last = str(error)
            if time.monotonic() >= deadline:
                raise RuntimeError(f"等待{description}超时：{last}")
            self.stop.wait(0.1)
        raise InterruptedError("启动被停止信号取消")

    def _cam_ready(self):
        # The public CLI announces JSON after TCP and optional UDP are ready.
        if self.cam.log.stat().st_size > 1024 * 1024:
            raise RuntimeError("CAM 启动日志超过 1 MiB")
        for line in self.cam.log.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                record = json.loads(line)
            except ValueError:
                continue
            host, port, inbox = self.config.cam_endpoint
            if (
                isinstance(record, dict)
                and record.get("host") == host
                and record.get("port") == port
                and record.get("inbox") == inbox
            ):
                return True
        return False

    def _release_socket(self):
        if self.config.socket.exists() or self.config.socket.is_symlink():
            info = self.config.socket.lstat()
            # Only a terminated child and its exact recorded socket can be cleaned.
            if self.socket_identity != (info.st_dev, info.st_ino) or not stat.S_ISSOCK(
                info.st_mode
            ):
                raise RecoveryBlocked("控制端点已被替换；保活不会接管其他服务")
            self.config.socket.unlink()
        self.socket_identity = None

    def _start_service(self):
        if self.service is not None:
            self.service.stop(self.config.shutdown_timeout)
            self.service = None
            self._release_socket()
        self.service = self._spawn("controller", self.config.service)
        self._wait("控制服务", lambda: bool(status(self.config.socket)))
        info = self.config.socket.lstat()
        self.socket_identity = (info.st_dev, info.st_ino)

    def _start_cam(self):
        if self.config.cam is not None:
            self.cam = self._spawn("cam-link", self.config.cam)
            self._wait("CAM 联动", self._cam_ready)

    def _stop_cam(self):
        if self.cam is not None:
            self.cam.stop(self.config.shutdown_timeout)
            self.cam = None

    def _start_stack(self):
        native_lock = Path("/tmp/linuxcnc.lock")
        if native_lock.exists() or native_lock.is_symlink():
            raise RecoveryBlocked("/tmp/linuxcnc.lock 已存在；不会清理或接管其他核心")
        self._start_service()
        if status(self.config.socket)["connected"]:
            raise RecoveryBlocked("发现已运行的 LinuxCNC，不会启动第二个核心")
        if native_lock.exists() or native_lock.is_symlink():
            raise RecoveryBlocked("LinuxCNC 锁在启动期间出现，不会接管其他会话")
        self.native = self._spawn("linuxcnc", self.config.native)
        self._wait("LinuxCNC", lambda: status(self.config.socket)["connected"])
        self._start_cam()
        self._publish("ready")
        print("启动编排完成；未发送上电、回零或加工命令。", flush=True)

    def _repair(self):
        if self.native is None or self.native.process.poll() is not None:
            self._stop_cam()
            if self.native is not None:
                try:
                    os.killpg(self.native.process.pid, 0)
                except ProcessLookupError:
                    pass
                else:
                    raise RuntimeError("原 LinuxCNC 子进程组仍在运行，等待原生清理")
            self.native = None
            self._start_stack()
        elif self.service is None or self.service.process.poll() is not None:
            self._stop_cam()
            self._start_service()
            self._wait("LinuxCNC 状态", lambda: status(self.config.socket)["connected"])
            self._start_cam()
        else:
            if not status(self.config.socket)["connected"]:
                self._stop_cam()
                raise RuntimeError("LinuxCNC 状态连接丢失，等待恢复后再开放 CAM")
            if self.cam is not None and self.cam.process.poll() is not None:
                self._stop_cam()
                self._start_cam()
            elif self.cam is None:
                self._start_cam()
        self._publish("ready")

    def _supervise(self):
        backoff = 1
        while not self.stop.wait(0.25):
            if not self.keep_alive:
                if self.native.process.poll() is not None:
                    return 0 if self.native.process.returncode == 0 else 1
                self._check_children()
                if not status(self.config.socket)["connected"]:
                    raise RuntimeError("LinuxCNC 状态连接丢失")
                continue
            try:
                self._repair()
                backoff = 1
            except (OSError, ValueError, RuntimeError) as error:
                report("launcher", "process_error", str(error))
                self._stop_cam()
                self._publish("recovering")
                print(f"保活等待 {backoff} 秒：{error}", flush=True)
                self.stop.wait(backoff)
                backoff = min(30, backoff * 2)
        return 0

    def _cleanup(self, requested):
        self._stop_cam()
        if self.native is not None and self.native.process.poll() is None:
            safe = False
            if requested:
                try:
                    safe = quiescent(status(self.config.socket))
                except (OSError, ValueError):
                    pass
            if not safe or not self.native.stop(self.config.shutdown_timeout, force=False):
                print(
                    "保留 LinuxCNC 和控制服务：机床忙、状态未知或原生清理尚未结束。"
                    "请在本地界面处理并退出。",
                    flush=True,
                )
                self._publish("retained")
                return False
        if self.service is not None:
            # An unexpectedly exited native shell may leave a live core behind.
            if self.native is not None and self.native.process.returncode != 0:
                try:
                    if status(self.config.socket)["connected"]:
                        self._publish("retained")
                        return False
                except (OSError, ValueError):
                    self._publish("retained")
                    return False
            self.service.stop(self.config.shutdown_timeout)
            self._release_socket()
        self._publish("stopped")
        return True

    def run(self):
        config = self.config
        _private_directory(config.socket.parent)
        descriptor = os.open(
            config.socket.parent / "launcher.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600
        )
        with os.fdopen(descriptor, "r+") as lock:
            info = os.fstat(lock.fileno())
            if info.st_uid != os.getuid() or not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
                raise ValueError("启动锁必须是当前用户的私有普通文件")
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RecoveryBlocked("启动器已在运行，不会重复启动") from None
            if config.socket.exists() or config.socket.is_symlink():
                raise RecoveryBlocked(f"控制端点已存在，不会接管或删除：{config.socket}")
            if Path("/tmp/linuxcnc.lock").exists() or Path("/tmp/linuxcnc.lock").is_symlink():
                raise RecoveryBlocked("/tmp/linuxcnc.lock 已存在，请先处理原 LinuxCNC 会话")
            shared_logs = os.environ.get("BETTERCNC_SHARE_LOGS") == "1"
            _log_directory(config.state, shared_logs)
            self.logs = config.state / f"{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}"
            _log_directory(self.logs, shared_logs)
            lock.seek(0)
            lock.truncate()
            lock.write(
                json.dumps({"pid": os.getpid(), "ini": str(config.ini), "logs": str(self.logs)})
            )
            lock.flush()
            self.env = dict(os.environ, BETTERCNC_SOCKET=str(config.socket), BETTERCNC_MANAGED="1")
            previous = {
                sig: signal.signal(sig, lambda *_: self.stop.set())
                for sig in (signal.SIGINT, signal.SIGTERM)
            }
            result = 0
            try:
                self._publish("starting")
                try:
                    self._start_stack()
                except RecoveryBlocked:
                    raise
                except (OSError, ValueError, RuntimeError) as error:
                    report("launcher", "process_error", str(error))
                    if not self.keep_alive:
                        raise
                    self._stop_cam()
                    self._publish("recovering")
                    print(f"启动尚未完成，保活等待恢复：{error}", flush=True)
                result = self._supervise()
            except InterruptedError as error:
                print(str(error), flush=True)
            except (OSError, ValueError, RuntimeError) as error:
                report("launcher", "process_error", str(error))
                print(f"启动编排失败：{error}", flush=True)
                result = 78
            finally:
                try:
                    if not self._cleanup(self.stop.is_set()):
                        result = 78
                finally:
                    for sig, handler in previous.items():
                        signal.signal(sig, handler)
            return result
