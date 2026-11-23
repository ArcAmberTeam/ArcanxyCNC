"""Exercise the installed service's public CLI and socket protocol."""

import json
import os
import socket
import stat
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


def frame(message):
    body = json.dumps(message).encode()
    return struct.pack("!I", len(body)) + body


def read_reply(connection):
    def exact(count):
        data = b""
        while len(data) < count:
            part = connection.recv(count - len(data))
            if not part:
                raise EOFError
            data += part
        return data

    size = struct.unpack("!I", exact(4))[0]
    return json.loads(exact(size))


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir="/tmp", prefix="cnc-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "private" / "control.sock"
        self.command = [sys.executable, "-m", "betterlinuxcnc_service", "--socket", str(self.path)]
        self.start_service()
        self.addCleanup(self.stop)

    def start_service(self, env=None):
        self.process = subprocess.Popen(
            self.command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, env=env
        )
        deadline = time.monotonic() + 5
        # Binding creates the socket path before the service starts listening.
        while True:
            if self.process.poll() is not None:
                self.fail(self.process.stderr.read().decode())
            try:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
                    probe.settimeout(1)
                    probe.connect(str(self.path))
            except (FileNotFoundError, ConnectionRefusedError):
                pass
            else:
                break
            if time.monotonic() > deadline:
                self.fail("service did not start listening on its socket")
            time.sleep(0.01)

    def stop(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.process.stderr.close()

    def connect(self):
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connection.settimeout(4)
        connection.connect(str(self.path))
        self.addCleanup(connection.close)
        return connection

    def test_fragmented_and_multiple_requests_preserve_boundaries(self):
        connection = self.connect()
        data = frame({"version": 1, "request_id": "first", "method": "health"})
        for byte in data:
            connection.sendall(bytes([byte]))
        first = read_reply(connection)
        self.assertEqual(first["request_id"], "first")
        self.assertEqual(first["result"]["mode"], "diagnostics-only")
        self.assertIs(first["result"]["machine_connected"], False)
        connection.sendall(frame({"version": 1, "request_id": "second", "method": "health"}))
        self.assertEqual(read_reply(connection)["request_id"], "second")

    def test_rejects_machine_commands_and_invalid_versions(self):
        for version, method, code in [
            (1, "machine.home-all", "unsupported_method"),
            (3, "health", "unsupported_version"),
            (True, "health", "unsupported_version"),
        ]:
            with self.subTest(version=version, method=method):
                connection = self.connect()
                connection.sendall(
                    frame({"version": version, "request_id": "test", "method": method})
                )
                reply = read_reply(connection)
                self.assertEqual(reply["error"]["code"], code)
                self.assertNotIn("result", reply)

    def test_oversized_frame_is_closed_without_reading_body(self):
        connection = self.connect()
        connection.sendall(struct.pack("!I", 65537))
        self.assertEqual(connection.recv(1), b"")

    def test_partial_frame_times_out(self):
        connection = self.connect()
        connection.sendall(b"\x00")
        self.assertEqual(connection.recv(1), b"")

    def test_invalid_json_and_extra_fields_are_rejected(self):
        connection = self.connect()
        connection.sendall(struct.pack("!I", 1) + b"{")
        self.assertEqual(read_reply(connection)["error"]["code"], "invalid_request")
        connection.sendall(frame({"version": 1, "request_id": "x", "method": "health", "extra": 1}))
        self.assertEqual(read_reply(connection)["error"]["code"], "invalid_request")

    def test_duplicate_keys_and_nonfinite_numbers_are_rejected(self):
        for payload in [
            b'{"version":1,"request_id":"x","method":"move","method":"health"}',
            b'{"version":NaN,"request_id":"x","method":"health"}',
            b"[" * 3000 + b"]" * 3000,
        ]:
            connection = self.connect()
            connection.sendall(struct.pack("!I", len(payload)) + payload)
            self.assertEqual(read_reply(connection)["error"]["code"], "invalid_request")

    def test_second_start_does_not_replace_active_socket(self):
        inode = self.path.stat().st_ino
        second = subprocess.run(self.command, capture_output=True, timeout=5)
        self.assertNotEqual(second.returncode, 0)
        self.assertEqual(self.path.stat().st_ino, inode)
        connection = self.connect()
        connection.sendall(frame({"version": 1, "request_id": "alive", "method": "health"}))
        self.assertIn("result", read_reply(connection))

    def test_private_permissions_and_clean_shutdown(self):
        self.assertEqual(stat.S_IMODE(self.path.parent.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        self.process.terminate()
        self.assertEqual(self.process.wait(timeout=5), 0)
        self.assertFalse(self.path.exists())

    def test_managed_service_survives_a_native_binding_that_latches_early_failure(self):
        self.stop()
        root = Path(self.temp.name)
        ready = root / "native-ready"
        (root / "linuxcnc.py").write_text(
            "from pathlib import Path\n"
            "from test_controller import FakeLinuxCNC\n"
            "vendor = FakeLinuxCNC()\n"
            f"vendor.available = Path({str(ready)!r}).exists()\n"
            "__getattr__ = lambda name: getattr(vendor, name)\n"
        )
        self.start_service(
            dict(
                os.environ,
                BETTERCNC_MANAGED="1",
                PYTHONPATH=os.pathsep.join((str(root), str(Path(__file__).resolve().parent))),
                PATH=str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"],
            )
        )
        with self.connect() as connection:

            def status(request_id):
                connection.sendall(
                    frame(
                        {
                            "version": 2,
                            "request_id": str(request_id),
                            "method": "machine.status",
                            "params": {},
                        }
                    )
                )
                return read_reply(connection)["result"]["connected"]

            self.assertFalse(status(0))
            ready.touch()
            for attempt in range(1, 31):
                if status(attempt):
                    break
                time.sleep(0.1)
            else:
                self.fail("observer stayed disconnected after native startup")

    def test_refuses_insecure_directory(self):
        unsafe = Path(self.temp.name) / "unsafe"
        unsafe.mkdir(mode=0o755)
        os.chmod(unsafe, 0o755)
        result = subprocess.run(
            self.command[:-1] + [str(unsafe / "control.sock")], capture_output=True, timeout=5
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((unsafe / "control.sock").exists())


if __name__ == "__main__":
    unittest.main()
