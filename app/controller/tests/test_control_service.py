"""V2 behavior through the public embedded service and real Unix framing."""

import asyncio
import copy
import json
import os
import stat
import struct
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from betterlinuxcnc_service import serve


class FakeController:
    def __init__(self, ini_path=None):
        self.ini_path = ini_path
        self.calls = []
        self.threads = []
        self.started = threading.Event()
        self.unblock = threading.Event()
        self.closed = False
        self.state = {
            "connected": True,
            "powered": True,
            "actualPosition": [0.0] * 9,
            "g5xOffset": [0.0] * 9,
            "g92Offset": [0.0] * 9,
            "toolOffset": [0.0] * 9,
            "linearUnits": 1.0,
            "rotationXY": 0.0,
            "g5xIndex": 1,
            "axisMask": 7,
            "blockDelete": False,
            "toolTable": [],
            "commandState": "idle",
        }

    def _record(self, method, *args):
        self.threads.append(threading.get_ident())
        self.calls.append((method, *args))

    @property
    def snapshot(self):
        return copy.deepcopy(self.state)

    def poll(self):
        self._record("poll")
        return self.snapshot

    def dispatch(self, action, payload=None):
        self._record("dispatch", action, payload)
        if action == "blocked.command":
            self.started.set()
            self.unblock.wait(3)
        self.state["commandState"] = "sent"
        return action != "reject.command"

    def stop_jog(self):
        self._record("stop_jog")

    def close(self):
        self.stop_jog()
        self._record("close")
        self.closed = True


class FakeProcess:
    def __init__(self, result, output, blocked):
        self.returncode = None if blocked else 0
        self.terminate_delay = 0.0
        self.terminating = False
        self.finished = asyncio.Event()
        if not blocked:
            Path(output).write_text(json.dumps(result), encoding="utf-8")
            self.finished.set()

    async def wait(self):
        await self.finished.wait()
        return self.returncode

    def terminate(self):
        self.terminating = True

        def finish():
            self.returncode = -15
            self.finished.set()

        if self.terminate_delay:
            asyncio.get_running_loop().call_later(self.terminate_delay, finish)
        else:
            finish()

    def kill(self):
        self.terminate()


class ControlServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(dir="/tmp", prefix="cnc-v2-")
        self.path = Path(self.temp.name) / "private" / "control.sock"
        self.stop = asyncio.Event()
        self.controllers = []
        self.writers = []
        self.ids = 0
        self.preview_processes = []
        self.preview_requests = []
        self.preview_blocked = False
        self.preview_terminate_delay = 0.0
        self.preview_exitcode = None
        self.real_preview = False
        self.seed_snapshot = {}
        self.status_readers = []
        test = self

        class Reader:
            def __init__(self, ini_path=None):
                self.ini_path = ini_path
                self.closed = False
                self.threads = []
                test.status_readers.append(self)

            def poll(self):
                self.threads.append(threading.get_ident())
                return {"connected": True, "programState": "running", "currentLine": 12}

            def close(self):
                self.closed = True

        self.preview_result = {
            "units": "mm",
            "segments": [],
            "bounds": {"min": [0, 0, 0], "max": [1, 2, 3]},
            "warnings": [],
            "truncated": False,
        }

        def factory(ini_path=None):
            controller = FakeController(ini_path)
            controller.state.update(self.seed_snapshot)
            self.controllers.append(controller)
            return controller

        async def process_factory(*args, **kwargs):
            self.assertEqual(args[1:3], ("-m", "bettercnc_preview"))
            request = args[args.index("--request") + 1]
            output = args[args.index("--output") + 1]
            self.preview_requests.append(json.loads(Path(request).read_text()))
            if self.real_preview:
                root = Path(kwargs["env"]["PYTHONPATH"].split(os.pathsep)[0])
                self.assertTrue((root / "bettercnc_preview" / "__main__.py").is_file())
                self.assertEqual(kwargs["env"]["BETTERCNC_TEST_PREVIEW_ENV"], "preserved")
                return await asyncio.create_subprocess_exec(*args, **kwargs)
            process = FakeProcess(
                self.preview_result,
                output,
                self.preview_blocked or self.preview_exitcode is not None,
            )
            process.terminate_delay = self.preview_terminate_delay
            if self.preview_exitcode is not None:
                process.returncode = self.preview_exitcode
                process.finished.set()
            self.preview_processes.append(process)
            return process

        self.server = asyncio.create_task(
            serve(
                self.path,
                ini_path="/example/machine.ini",
                controller_factory=factory,
                process_factory=process_factory,
                status_reader_factory=Reader,
                stop_event=self.stop,
            )
        )
        for _ in range(100):
            if self.path.exists():
                break
            if self.server.done():
                await self.server
            await asyncio.sleep(0.01)
        self.assertTrue(self.path.exists())

    async def asyncTearDown(self):
        for controller in self.controllers:
            controller.unblock.set()
        for writer in self.writers:
            writer.close()
        self.stop.set()
        await asyncio.wait_for(self.server, 5)
        self.temp.cleanup()

    async def connect(self):
        reader, writer = await asyncio.open_unix_connection(str(self.path))
        self.writers.append(writer)
        return reader, writer

    def request(self, method, params=None, request_id=None):
        self.ids += 1
        return {
            "version": 2,
            "request_id": request_id or str(self.ids),
            "method": method,
            "params": {} if params is None else params,
        }

    async def send(self, connection, request):
        body = json.dumps(request).encode()
        connection[1].write(struct.pack("!I", len(body)) + body)
        await connection[1].drain()

    async def read(self, connection):
        async with asyncio.timeout(4):
            length = struct.unpack("!I", await connection[0].readexactly(4))[0]
            self.assertLessEqual(length, 65536)
            return json.loads(await connection[0].readexactly(length))

    async def rpc(self, connection, method, params=None, request_id=None):
        await self.send(connection, self.request(method, params, request_id))
        return await self.read(connection)

    async def attached(self):
        connection = await self.connect()
        result = await self.rpc(connection, "session.attach")
        self.assertTrue(result["result"]["connected"])
        return connection

    async def wait_for(self, predicate, seconds=2):
        end = time.monotonic() + seconds
        while not predicate():
            if time.monotonic() >= end:
                self.fail("condition did not become true")
            await asyncio.sleep(0.01)

    async def test_v1_health_stays_diagnostic_and_does_not_open_controller(self):
        connection = await self.connect()
        await self.send(connection, {"version": 1, "request_id": "old", "method": "health"})
        reply = await self.read(connection)
        self.assertEqual(reply["version"], 1)
        self.assertFalse(reply["result"]["machine_connected"])
        self.assertEqual(self.controllers, [])

    async def test_machine_feedback_does_not_acquire_control_or_renew_jog_lease(self):
        observer = await self.connect()
        reply = await self.rpc(observer, "machine.status")
        self.assertEqual(reply["result"]["currentLine"], 12)
        self.assertEqual(self.controllers, [])
        self.assertEqual(self.status_readers[0].ini_path, "/example/machine.ini")
        self.assertNotIn(threading.get_ident(), self.status_readers[0].threads)
        self.assertEqual(
            (await self.rpc(observer, "machine.status", {"jog_lease": True}))["error"]["code"],
            "invalid_params",
        )
        owner = await self.attached()
        await self.rpc(owner, "command.execute", {"action": "jog.start", "payload": {"axis": "X"}})
        for _ in range(6):
            await self.rpc(observer, "machine.status")
            await self.rpc(owner, "session.status")
            await asyncio.sleep(0.15)
        self.assertIn(("stop_jog",), self.controllers[0].calls)
        self.assertEqual(
            (await self.rpc(observer, "command.execute", {"action": "program.run", "payload": {}}))[
                "error"
            ]["code"],
            "not_attached",
        )
        observer[1].close()
        await observer[1].wait_closed()
        self.assertTrue((await self.rpc(owner, "session.status"))["result"]["connected"])
        self.assertFalse(self.controllers[0].closed)
        self.stop.set()
        await self.server
        self.assertTrue(self.status_readers[0].closed)

    async def test_attach_has_exclusive_ownership_and_requires_exact_params(self):
        first = await self.attached()
        second = await self.connect()
        self.assertEqual(
            (await self.rpc(second, "session.attach"))["error"]["code"], "control_in_use"
        )
        self.assertEqual(
            (await self.rpc(second, "command.execute", {"action": "program.run", "payload": {}}))[
                "error"
            ]["code"],
            "not_attached",
        )
        self.assertEqual(
            (await self.rpc(first, "session.status", {"jog_lease": 1}))["error"]["code"],
            "invalid_params",
        )
        self.assertEqual(
            (await self.rpc(first, "session.status", {"extra": False}))["error"]["code"],
            "invalid_params",
        )
        self.assertEqual(self.controllers[0].ini_path, "/example/machine.ini")

    async def test_attach_checks_requested_ini_without_changing_service_configuration(self):
        connection = await self.connect()
        mismatch = await self.rpc(connection, "session.attach", {"ini_path": "/other/machine.ini"})
        self.assertEqual(mismatch["error"]["code"], "ini_mismatch")
        self.assertEqual(self.controllers, [])
        valid = await self.rpc(connection, "session.attach", {"ini_path": "/example/machine.ini"})
        self.assertTrue(valid["result"]["connected"])
        self.assertEqual(self.controllers[0].ini_path, "/example/machine.ini")

    async def test_command_is_serialized_off_event_loop_and_reports_acceptance(self):
        connection = await self.attached()
        reply = await self.rpc(
            connection, "command.execute", {"action": "program.run", "payload": {"line": 12}}
        )
        self.assertTrue(reply["result"]["accepted"])
        self.assertEqual(reply["result"]["snapshot"]["commandState"], "sent")
        controller = self.controllers[0]
        self.assertIn(("dispatch", "program.run", {"line": 12}), controller.calls)
        self.assertEqual(len(set(controller.threads)), 1)
        self.assertNotIn(threading.get_ident(), controller.threads)
        reply = await self.rpc(
            connection, "command.execute", {"action": "reject.command", "payload": {}}
        )
        self.assertFalse(reply["result"]["accepted"])

    async def test_duplicate_request_id_does_not_repeat_commands(self):
        connection = await self.attached()
        params = {"action": "program.run", "payload": {}}
        await self.rpc(connection, "command.execute", params, "only-once")
        result = await self.rpc(connection, "command.execute", params, "only-once")
        self.assertEqual(result["error"]["code"], "duplicate_request")
        self.assertEqual(sum(call[0] == "dispatch" for call in self.controllers[0].calls), 1)

    async def test_jog_lease_expires_even_when_status_reads_continue(self):
        connection = await self.attached()
        await self.rpc(
            connection, "command.execute", {"action": "jog.start", "payload": {"axis": "X"}}
        )
        for _ in range(6):
            await asyncio.sleep(0.15)
            await self.rpc(connection, "session.status", {"jog_lease": False})
        controller = self.controllers[0]
        self.assertIn(("stop_jog",), controller.calls)
        count = sum(call[0] == "dispatch" for call in controller.calls)
        await self.rpc(connection, "session.status", {"jog_lease": True})
        self.assertEqual(sum(call[0] == "dispatch" for call in controller.calls), count)

    async def test_explicit_lease_renewal_keeps_jog_alive_until_it_stops(self):
        connection = await self.attached()
        await self.rpc(
            connection, "command.execute", {"action": "jog.start", "payload": {"axis": "X"}}
        )
        for _ in range(5):
            await asyncio.sleep(0.2)
            await self.rpc(connection, "session.status", {"jog_lease": True})
        self.assertNotIn(("stop_jog",), self.controllers[0].calls)
        await self.rpc(connection, "command.execute", {"action": "jog.stop", "payload": {}})
        self.assertIn(("dispatch", "jog.stop", {}), self.controllers[0].calls)

    async def test_disconnect_closes_owner_without_aborting_or_replaying_program(self):
        first = await self.attached()
        await self.rpc(first, "command.execute", {"action": "program.run", "payload": {}})
        first[1].close()
        await first[1].wait_closed()
        controller = self.controllers[0]
        await self.wait_for(lambda: controller.closed)
        self.assertIn(("stop_jog",), controller.calls)
        self.assertFalse(any(call[:2] == ("dispatch", "program.stop") for call in controller.calls))
        second = await self.attached()
        await self.rpc(second, "session.status")
        self.assertEqual(len(self.controllers), 2)
        self.assertFalse(any(call[0] == "dispatch" for call in self.controllers[1].calls))

    async def test_blocked_vendor_command_does_not_block_other_socket_and_disconnect_is_seen(self):
        owner = await self.attached()
        await self.send(
            owner, self.request("command.execute", {"action": "blocked.command", "payload": {}})
        )
        controller = self.controllers[0]
        await self.wait_for(controller.started.is_set)
        observer = await self.connect()
        await self.send(observer, {"version": 1, "request_id": "health", "method": "health"})
        reply = await asyncio.wait_for(self.read(observer), 0.3)
        self.assertIn("result", reply)
        owner[1].close()
        await owner[1].wait_closed()
        await asyncio.sleep(0.12)
        controller.unblock.set()
        await self.wait_for(lambda: controller.closed)
        index = next(
            i
            for i, call in enumerate(controller.calls)
            if call[:2] == ("dispatch", "blocked.command")
        )
        self.assertEqual(controller.calls[index + 1 :], [("stop_jog",), ("close",)])

    async def test_idle_owner_timeout_releases_control(self):
        connection = await self.attached()
        await asyncio.sleep(2.15)
        self.assertEqual(await connection[0].read(1), b"")
        self.assertTrue(self.controllers[0].closed)
        await self.attached()

    async def test_private_permissions_and_clean_shutdown(self):
        self.assertEqual(stat.S_IMODE(self.path.parent.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        connection = await self.attached()
        self.stop.set()
        await asyncio.wait_for(self.server, 1)
        self.assertEqual(await connection[0].read(1), b"")
        self.assertFalse(self.path.exists())
        self.assertTrue(self.controllers[0].closed)

    async def test_v2_shape_duplicate_fields_and_nonfinite_numbers_are_rejected(self):
        connection = await self.connect()
        for message in (
            {"version": 2, "request_id": "missing", "method": "session.attach"},
            {
                "version": 2,
                "request_id": "extra",
                "method": "session.attach",
                "params": {},
                "extra": 1,
            },
            {"version": 2, "request_id": "bad", "method": "session.attach", "params": []},
        ):
            await self.send(connection, message)
            self.assertEqual((await self.read(connection))["error"]["code"], "invalid_request")
        raw = b'{"version":2,"request_id":"x","method":"session.attach","params":{"a":NaN}}'
        connection[1].write(struct.pack("!I", len(raw)) + raw)
        await connection[1].drain()
        self.assertEqual((await self.read(connection))["error"]["code"], "invalid_request")

    async def test_preview_is_separate_process_uses_observed_context_and_pages(self):
        connection = await self.attached()
        program = Path(self.temp.name) / "test.ngc"
        program.write_text("G0 X0\nM2\n")
        self.preview_result["segments"] = [
            {"start": [0.0, 0.0, 0.0], "end": [1.0, 2.0, 3.0], "line": i, "kind": "feed"}
            for i in range(600)
        ]
        result = await self.rpc(connection, "preview.start", {"path": str(program)})
        job_id = result["result"]["job_id"]
        for _ in range(100):
            reply = (await self.rpc(connection, "preview.read", {"job_id": job_id, "offset": 0}))[
                "result"
            ]
            if not reply["busy"]:
                break
            await asyncio.sleep(0.01)
        self.assertEqual(len(reply["segments"]), 256)
        self.assertEqual(reply["next_offset"], 256)
        self.assertFalse(reply["done"])
        tail = (await self.rpc(connection, "preview.read", {"job_id": job_id, "offset": 512}))[
            "result"
        ]
        self.assertEqual(len(tail["segments"]), 88)
        self.assertTrue(tail["done"])
        self.assertEqual(self.preview_requests[0]["context"]["actualPosition"], [0.0] * 9)
        self.assertFalse(any(call[0] == "dispatch" for call in self.controllers[0].calls))

    async def test_preview_cancel_and_owner_disconnect_terminate_children(self):
        connection = await self.attached()
        program = Path(self.temp.name) / "test.ngc"
        program.write_text("M2\n")
        self.preview_blocked = True
        first = (await self.rpc(connection, "preview.start", {"path": str(program)}))["result"][
            "job_id"
        ]
        self.assertTrue(
            (await self.rpc(connection, "preview.cancel", {"job_id": first}))["result"]["cancelled"]
        )
        self.assertEqual(self.preview_processes[0].returncode, -15)
        self.assertEqual(
            (await self.rpc(connection, "preview.read", {"job_id": first, "offset": 0}))["error"][
                "code"
            ],
            "unknown_job",
        )
        await self.rpc(connection, "preview.start", {"path": str(program)})
        connection[1].close()
        await self.wait_for(lambda: self.preview_processes[-1].returncode is not None)
        await self.wait_for(lambda: self.controllers[0].closed)
        new = await self.attached()
        self.assertEqual(
            (await self.rpc(new, "preview.cancel", {"job_id": first}))["error"]["code"],
            "unknown_job",
        )

    async def test_large_tool_table_and_error_history_have_bounded_wire_status(self):
        table = [[float(i) / 7 + j for j in range(14)] for i in range(1001)]
        self.seed_snapshot.update(
            toolTable=table,
            errors=[{"message": "错误" * 5000, "kind": 1, "error": True} for _ in range(100)],
        )
        connection = await self.attached()
        result = (await self.rpc(connection, "session.status"))["result"]
        self.assertNotIn("toolTable", result)
        self.assertEqual(len(result["toolTableRevision"]), 64)
        self.assertEqual(len(result["errors"]), 20)
        self.assertEqual(result["errorHistoryCount"], 100)
        self.assertTrue(result["errorsTruncated"])
        self.assertTrue(all(len(error["message"].encode()) <= 1024 for error in result["errors"]))
        self.assertLess(len(json.dumps(result).encode()), 65536)
        first_revision = result["toolTableRevision"]
        self.assertEqual(
            (await self.rpc(connection, "session.status"))["result"]["toolTableRevision"],
            first_revision,
        )
        program = Path(self.temp.name) / "large-table.ngc"
        program.write_text("M2\n")
        await self.rpc(connection, "preview.start", {"path": str(program)})
        self.assertEqual(self.preview_requests[0]["context"]["toolTable"], table)

    async def test_crashed_preview_process_returns_structured_signal_error(self):
        connection = await self.attached()
        program = Path(self.temp.name) / "crash.ngc"
        program.write_text("M2\n")
        self.preview_exitcode = -11
        job = (await self.rpc(connection, "preview.start", {"path": str(program)}))["result"][
            "job_id"
        ]
        for _ in range(100):
            result = (await self.rpc(connection, "preview.read", {"job_id": job, "offset": 0}))[
                "result"
            ]
            if not result["busy"]:
                break
            await asyncio.sleep(0.01)
        self.assertIn("signal 11", result["error"]["message"])
        self.assertEqual(result["segments"], [])
        self.assertTrue(result["done"])

    async def test_real_preview_child_imports_private_package_without_inherited_pythonpath(self):
        # A missing parameter file guarantees a structured error before any
        # vendor status is opened, even on hosts where gcode is installed.
        self.seed_snapshot["parameterFile"] = str(Path(self.temp.name) / "missing.var")
        connection = await self.attached()
        program = Path(self.temp.name) / "real-child.ngc"
        program.write_text("M2\n")
        self.real_preview = True
        with patch.dict(os.environ, {"BETTERCNC_TEST_PREVIEW_ENV": "preserved"}):
            os.environ.pop("PYTHONPATH", None)
            job = (await self.rpc(connection, "preview.start", {"path": str(program)}))["result"][
                "job_id"
            ]
        for _ in range(200):
            result = (await self.rpc(connection, "preview.read", {"job_id": job, "offset": 0}))[
                "result"
            ]
            if not result["busy"]:
                break
            await asyncio.sleep(0.01)
        self.assertTrue(result["done"])
        self.assertIsInstance(result["error"], dict)
        self.assertNotIn("异常退出", result["error"]["message"])
        self.assertNotIn("No module named 'bettercnc_preview'", result["error"]["message"])
        self.assertEqual(result["segments"], [])

    async def test_release_never_polls_pending_controller_during_slow_preview_cleanup(self):
        connection = await self.attached()
        program = Path(self.temp.name) / "slow-cleanup.ngc"
        program.write_text("M2\n")
        self.preview_blocked = True
        self.preview_terminate_delay = 0.4
        await self.rpc(connection, "preview.start", {"path": str(program)})
        controller = self.controllers[0]
        connection[1].close()
        await self.wait_for(lambda: self.preview_processes[0].terminating)
        self.assertTrue(controller.closed)
        controller.state["commandState"] = "pending"
        count = len(controller.calls)
        observer = await self.connect()
        self.assertEqual(
            (await self.rpc(observer, "session.attach"))["error"]["code"], "control_in_use"
        )
        await asyncio.sleep(0.25)
        self.assertEqual(len(controller.calls), count)
        await self.wait_for(lambda: self.preview_processes[0].returncode is not None)

    async def test_preview_pages_remain_inside_frame_budget_with_large_segments(self):
        connection = await self.attached()
        program = Path(self.temp.name) / "test.ngc"
        program.write_text("M2\n")
        self.preview_result["segments"] = [{"line": i, "large": "x" * 1000} for i in range(256)]
        job = (await self.rpc(connection, "preview.start", {"path": str(program)}))["result"][
            "job_id"
        ]
        for _ in range(100):
            reply = (await self.rpc(connection, "preview.read", {"job_id": job, "offset": 0}))[
                "result"
            ]
            if not reply["busy"]:
                break
            await asyncio.sleep(0.01)
        self.assertGreater(len(reply["segments"]), 0)
        self.assertLess(len(reply["segments"]), 256)
        self.assertFalse(reply["done"])


if __name__ == "__main__":
    unittest.main()
