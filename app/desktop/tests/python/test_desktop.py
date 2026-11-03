"""Public QObject behavior over a real Unix socket, with no controller process."""

import copy
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from bettercnc.desktop import DesktopBackend
from PySide6.QtCore import QCoreApplication, QObject, QSettings, Qt, QUrl
from PySide6.QtGui import QGuiApplication, QWindow
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtTest import QTest
from test_session import Peer

APP = QGuiApplication.instance() or QGuiApplication([])


class DesktopTests(unittest.TestCase):
    def test_operator_notices_are_not_presented_as_failures(self):
        errors, notices = [], []
        self.backend.errorOccurred.connect(errors.append)
        self.backend.noticeOccurred.connect(notices.append)
        self.state["errors"] = [{"message": "Operator information", "error": False}]
        self.wait(lambda: notices == ["Operator information"])
        self.assertEqual(errors, [])
        self.state["errors"].append({"message": "joint 1 on limit switch error", "error": True})
        self.wait(lambda: errors == ["joint 1 on limit switch error"])
        QTest.qWait(200)
        self.assertEqual(notices, ["Operator information"])
        self.assertEqual(errors, ["joint 1 on limit switch error"])

    def test_mesa_pending_request_rechecks_the_latest_root_status(self):
        for phase in ("verifying_identity", "writing", "programmed_pending_power_cycle"):
            self.backend.close()
            calls = Path(self.temporary.name) / (phase + "-calls.jsonl")
            script = Path(self.temporary.name) / (phase + "-flash.py")
            script.write_text(
                "import json, sys, time\nfrom pathlib import Path\n"
                f"with Path({str(calls)!r}).open('a') as f:\n"
                "    f.write(json.dumps(sys.argv[1:]) + '\\n')\n"
                "time.sleep(.15)\n"
                "record = dict(schema_version=1, component='mesa-flash', message='')\n"
                f"record['phase'] = {phase!r}\n"
                "print(json.dumps(record))\n",
                encoding="utf-8",
            )
            self.backend = DesktopBackend(
                socket_path=self.peer.path,
                mesa_flash_command=[sys.executable, str(script)],
            )
            self.addCleanup(self.backend.close)
            flash = self.backend.mesaFlash
            self.wait(lambda calls=calls: calls.exists())
            flash.request()
            self.wait(lambda flash=flash, phase=phase: flash.state["phase"] == phase)
            QTest.qWait(100)
            self.assertEqual(
                [json.loads(line) for line in calls.read_text().splitlines()], [["status"]]
            )
            self.assertNotEqual(flash.state["phase"], "error")

    def test_mesa_flash_request_uses_a_separate_fixed_cli_without_hardware_arguments(self):
        self.backend.close()
        calls = Path(self.temporary.name) / "flash-calls.jsonl"
        script = Path(self.temporary.name) / "flash-service.py"
        script.write_text(
            "import json, sys\nfrom pathlib import Path\n"
            f"with Path({str(calls)!r}).open('a') as f:\n"
            "    f.write(json.dumps(sys.argv[1:]) + '\\n')\n"
            "phase = 'host_restarted_board_unconfirmed'\n"
            "if sys.argv[1] == 'request': phase = 'scheduled'\n"
            "record = dict(schema_version=1, component='mesa-flash', phase=phase, message='')\n"
            "print(json.dumps(record))\n",
            encoding="utf-8",
        )
        self.backend = DesktopBackend(
            socket_path=self.peer.path,
            mesa_flash_command=[sys.executable, str(script)],
        )
        self.addCleanup(self.backend.close)
        flash = self.backend.mesaFlash
        self.wait(lambda: flash.state["phase"] == "host_restarted_board_unconfirmed")
        flash.request()
        flash.request()
        self.wait(lambda: flash.state["phase"] == "scheduled" and calls.exists())
        QTest.qWait(100)
        commands = [json.loads(line) for line in calls.read_text().splitlines()]
        self.assertEqual(commands.count(["request"]), 1)
        self.assertTrue(all(command in (["status"], ["request"]) for command in commands))
        self.assertFalse(any(item["method"] == "command.execute" for item in self.peer.requests))

    def mesa_peer(self, response):
        self.backend.close()
        calls = Path(self.temporary.name) / "mesa-calls.jsonl"
        script = Path(self.temporary.name) / "mesa-service.py"
        script.write_text(
            "import json, sys, time\nfrom pathlib import Path\n"
            f"with Path({str(calls)!r}).open('a') as f: f.write(json.dumps(sys.argv[1:]) + '\\n')\n"
            "time.sleep(.05)\n"
            f"print(json.dumps({response!r}), flush=True)\n",
            encoding="utf-8",
        )
        self.backend = DesktopBackend(
            socket_path=self.peer.path,
            mesa_update_command=[sys.executable, str(script)],
        )
        self.addCleanup(self.backend.close)
        return self.backend.mesaUpdate, calls

    def test_mesa_source_release_is_presented_without_machine_commands(self):
        updater, calls = self.mesa_peer(
            dict(
                schema_version=1,
                component="mesa-update",
                phase="source_only",
                message="Source release only",
                available_version="26.10.26.1",
            )
        )
        updater.check()
        updater.check()
        self.wait(lambda: updater.state["phase"] == "source_only")
        QTest.qWait(150)
        commands = [json.loads(line) for line in calls.read_text().splitlines()]
        self.assertEqual(commands.count(["check"]), 1)
        self.assertTrue(all(command in (["status"], ["check"]) for command in commands))
        self.assertEqual(updater.state["available_version"], "26.10.26.1")
        self.assertIn("没有经过验证", updater.state["message"])
        self.assertFalse(any(item["method"] == "command.execute" for item in self.peer.requests))

    def test_mesa_adapter_rejects_wrong_component_and_invalid_version(self):
        for response in (
            dict(schema_version=1, component="mesa-flash", phase="source_only", message=""),
            dict(
                schema_version=1,
                component="mesa-update",
                phase="source_only",
                message="",
                available_version={"unexpected": "object"},
            ),
        ):
            updater, _calls = self.mesa_peer(response)
            updater.check()
            self.wait(lambda updater=updater: updater.state["phase"] == "error")
            self.assertIn("无效状态", updater.state["message"])

    def update_peer(self, script):
        self.backend.close()
        path = Path(self.temporary.name) / "updater.py"
        path.write_text(script, encoding="utf-8")
        settings = QSettings(
            str(Path(self.temporary.name) / "updater.ini"), QSettings.Format.IniFormat
        )
        self.backend = DesktopBackend(
            socket_path=self.peer.path,
            settings=settings,
            updater_command=[sys.executable, str(path)],
        )
        self.addCleanup(self.backend.close)
        return self.backend.firmwareUpdater

    def test_firmware_download_progress_single_flight_and_independent_install(self):
        calls = Path(self.temporary.name) / "calls.jsonl"
        updater = self.update_peer(f"""
import json, sys, time
from pathlib import Path
with Path({str(calls)!r}).open("a") as f:
    f.write(json.dumps(sys.argv[1:]) + "\\n")
def emit(phase, progress=0):
    record = dict(phase=phase, progress=progress, message=phase, version="0.3.0")
    print(json.dumps(record), flush=True)
if sys.argv[1] == "status":
    time.sleep(.05)
    emit("idle")
elif sys.argv[1] == "fetch":
    emit("downloading", 42)
    time.sleep(.1)
    emit("ready", 100)
elif sys.argv[1] == "install":
    emit("scheduled", 100)
""")
        events = []
        updater.changed.connect(lambda: events.append(dict(updater.state)))
        updater.fetch()
        updater.fetch()
        self.wait(lambda: updater.state["phase"] == "ready")
        self.assertTrue(
            any(item["phase"] == "downloading" and item["progress"] == 42 for item in events)
        )
        updater.install()
        self.wait(lambda: updater.state["phase"] == "scheduled")
        commands = [json.loads(line) for line in calls.read_text().splitlines()]
        self.assertEqual(sum(command[0] == "fetch" for command in commands), 1)
        self.assertIn(["install"], commands)
        self.assertFalse(any("--socket" in command for command in commands))
        self.assertFalse(any(item["method"] == "command.execute" for item in self.peer.requests))

    def test_firmware_service_errors_never_enable_installation(self):
        updater = self.update_peer("""
import json, sys
if sys.argv[1] == "status":
    print(json.dumps(dict(phase="idle", message="", progress=0)))
else:
    print(json.dumps(dict(phase="ready", message="bad", progress=101)))
    print(json.dumps(dict(phase="ready", message="cannot recover a broken protocol", progress=100)))
""")
        updater.fetch()
        self.wait(lambda: updater.state["phase"] == "error")
        self.assertIn("无效状态", updater.state["message"])
        state = dict(updater.state)
        updater.install()
        QTest.qWait(40)
        self.assertEqual(updater.state, state)

    def test_firmware_no_release_and_failed_process_are_explicit(self):
        updater = self.update_peer("""
import json, sys
if sys.argv[1] == "status":
    print(json.dumps(dict(phase="idle", message="", progress=0)))
else:
    print(json.dumps(dict(phase="no_release", message="当前仓库尚未发布正式 Release", progress=0)))
""")
        updater.fetch()
        self.wait(lambda: updater.state["phase"] == "no_release")
        self.assertIn("尚未发布", updater.state["message"])
        updater = self.update_peer("import sys; sys.exit(1)")
        self.wait(lambda: updater.state["phase"] == "error")
        self.assertIn("退出", updater.state["message"])

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="cnc-document-", dir="/tmp")
        self.addCleanup(self.temporary.cleanup)
        self.state = {
            "connected": True,
            "powered": True,
            "estop": False,
            "mode": "manual",
            "axes": ["X", "Y", "Z"],
            "actualPosition": [0.0] * 9,
            "commandedPosition": [0.0] * 9,
            "linearUnits": 1,
            "busy": False,
            "file": "",
            "errors": [],
            "capabilities": {},
            "commandState": "idle",
        }
        self.peer = Peer(self.reply)
        self.addCleanup(self.peer.close)
        settings = QSettings(str(Path(self.temporary.name) / "ui.ini"), QSettings.Format.IniFormat)
        self.program_roots = [
            Path(self.temporary.name).resolve() / name for name in ("programs", "inbox")
        ]
        for root in self.program_roots:
            root.mkdir()
        self.backend = DesktopBackend(
            socket_path=self.peer.path,
            settings=settings,
            managed=self._testMethodName.startswith("test_managed_"),
            kiosk=self._testMethodName.startswith("test_kiosk_"),
            program_roots=self.program_roots,
        )
        self.addCleanup(self.backend.close)
        self.wait(lambda: self.backend.snapshot.get("serviceConnected"))

    def reply(self, request):
        method, params = request["method"], request["params"]
        if method == "session.attach":
            return {}
        if method == "session.status":
            return copy.deepcopy(self.state)
        if method == "command.execute":
            if params["action"] == "file.open":
                self.state["file"] = params["payload"]["path"]
            return {"accepted": True, "snapshot": copy.deepcopy(self.state)}
        if method == "preview.start":
            return {"job_id": "fixture"}
        if method == "preview.read":
            return {
                "done": True,
                "busy": False,
                "units": "mm",
                "next_offset": 1,
                "segments": [{"type": "feed", "start": [0, 0, 0], "end": [1, 2, 0], "line": 2}],
                "bounds": {"min": [0, 0, 0], "max": [1, 2, 0]},
            }
        return {}

    def wait(self, predicate, timeout=3):
        deadline = time.monotonic() + timeout
        while not predicate() and time.monotonic() < deadline:
            QTest.qWait(20)
        self.assertTrue(predicate())

    def actions(self):
        return [
            r["params"]["action"] for r in self.peer.requests if r["method"] == "command.execute"
        ]

    def test_state_is_only_updated_from_service(self):
        self.backend.dispatch("machine.power", {})
        self.wait(lambda: "machine.power" in self.actions())
        self.assertTrue(self.backend.snapshot["powered"])
        self.state["powered"] = False
        self.wait(lambda: not self.backend.snapshot["powered"])

    def test_qml_whole_number_debug_value_uses_protocol_integer(self):
        self.assertTrue(self.backend.dispatch("machine.debug", {"value": 42.0}))
        self.wait(lambda: "machine.debug" in self.actions())
        request = next(r for r in self.peer.requests if r["method"] == "command.execute")
        self.assertIs(type(request["params"]["payload"]["value"]), int)
        self.assertEqual(request["params"]["payload"]["value"], 42)
        self.assertFalse(self.backend.dispatch("machine.debug", {"value": 1.5}))

    def test_existing_tool_table_accepts_linuxcnc_case_and_decimal_syntax(self):
        table = Path(self.temporary.name) / "tool.tbl"
        table.write_text("t1 p1 z2. d6. ; existing tool\n")
        self.state["toolTablePath"] = str(table)
        self.wait(lambda: len(self.backend.toolTable) == 1)
        self.assertEqual(self.backend.toolTable[0]["Z"], 2)
        self.assertEqual(self.backend.toolTableText, table.read_text())

    def test_real_document_and_remote_geometry_are_bound_to_public_properties(self):
        program = (Path(self.temporary.name) / "part.ngc").resolve()
        program.write_text("G21\nG1 X1 Y2 F100\nM2\n")
        self.assertTrue(self.backend.openProgram(str(program)))
        self.wait(lambda: not self.backend.program.previewBusy)
        self.assertEqual(self.backend.program.lines[1], "G1 X1 Y2 F100")
        self.assertEqual(self.backend.program.segments[0]["end"], [1, 2, 0])
        self.assertEqual(self.backend.program.previewError, "")
        self.wait(lambda: self.backend.snapshot.get("file") == str(program))

    def test_ui_freeze_stops_jog_instead_of_renewing_it_in_worker(self):
        QTest.qWait(180)
        self.backend.dispatch("jog.start", {"axis": "X", "direction": 1, "velocity": 1})
        self.wait(lambda: "jog.start" in self.actions())
        self.wait(lambda: any(r["params"].get("jog_lease") for r in self.peer.requests))
        # Deliberately stop the GUI event loop while the socket worker continues.
        time.sleep(0.65)
        self.assertIn("jog.stop", self.actions())

    def test_busy_program_cannot_be_overwritten(self):
        program = Path(self.temporary.name) / "busy.ngc"
        program.write_text("M2\n")
        self.state["busy"] = True
        self.wait(lambda: self.backend.snapshot.get("busy"))
        self.assertFalse(self.backend.saveProgram(str(program), "G0 X100\n"))
        self.assertEqual(program.read_text(), "M2\n")

    def test_service_reachable_does_not_mean_machine_connected(self):
        self.state["connected"] = False
        self.state["powered"] = False
        self.state["axes"] = []
        self.state["actualPosition"] = None
        self.wait(lambda: not self.backend.snapshot["connected"])
        self.assertTrue(self.backend.snapshot["serviceConnected"])
        self.assertIsNone(self.backend.snapshot["actualPosition"])

    def test_edit_is_sent_to_service_without_locally_overwriting_the_program(self):
        program = (Path(self.temporary.name) / "service-owned.ngc").resolve()
        program.write_text("M2\n")
        original = self.peer.responder

        def reject_edit(request):
            if request["method"] == "command.execute":
                return {"accepted": False, "snapshot": copy.deepcopy(self.state)}
            return original(request)

        self.peer.responder = reject_edit
        self.assertTrue(self.backend.saveProgram(str(program), "G0 X100\n"))
        self.wait(lambda: "file.save" in self.actions())
        self.assertEqual(program.read_text(), "M2\n")
        self.assertNotIn("file.open", self.actions())

    def test_offline_editor_cannot_replace_a_machine_file(self):
        program = Path(self.temporary.name) / "offline.ngc"
        program.write_text("M2\n")
        self.state["connected"] = False
        self.wait(lambda: not self.backend.snapshot["connected"])
        self.assertFalse(self.backend.saveProgram(str(program), "G0 X100\n"))
        self.assertEqual(program.read_text(), "M2\n")

    def test_history_clipboard_paste_never_executes_commands(self):
        APP.clipboard().setText("G0 X10\nM3 S1000")
        self.backend.dispatch("mdi.paste", {})
        QTest.qWait(200)
        self.assertEqual(self.backend.history, ["G0 X10", "M3 S1000"])
        self.assertNotIn("mdi.execute", self.actions())

    def test_real_qobject_notifications_update_the_qml_geometry(self):
        qml = Path(__file__).resolve().parents[2] / "qml"
        engine = QQmlApplicationEngine()
        warnings = []
        engine.warnings.connect(
            lambda items: warnings.extend(str(item.toString()) for item in items)
        )
        engine.addImportPath(str(qml))
        engine.setInitialProperties({"backend": self.backend})
        engine.load(QUrl.fromLocalFile(str(qml / "Main.qml")))
        try:
            self.assertTrue(engine.rootObjects())
            window = engine.rootObjects()[0]
            canvas = window.findChild(QObject, "toolpathCanvas")
            self.assertIsNotNone(canvas)
            program = (Path(self.temporary.name) / "qobject.ngc").resolve()
            program.write_text("G21\nG1 X1 Y2 F100\nM2\n")
            self.assertTrue(self.backend.openProgram(str(program)))
            self.wait(lambda: not self.backend.program.previewBusy)

            def geometry():
                value = canvas.property("geometry")
                return value.toVariant() if hasattr(value, "toVariant") else value

            self.wait(lambda: len(geometry()) == 1)
            self.assertEqual(geometry()[0]["end"], [1, 2, 0])
            problems = [
                w
                for w in warnings
                if any(
                    text in w
                    for text in ("ReferenceError", "TypeError", "Unable to assign", "Binding loop")
                )
            ]
            self.assertEqual(problems, [])
        finally:
            for window in engine.rootObjects():
                window.setProperty("visible", False)
            engine.deleteLater()
            QCoreApplication.sendPostedEvents()

    def test_managed_close_rejects_busy_pending_job_offline_and_stale_state(self):
        self.assertTrue(self.backend.requestClose())
        for update in (
            {"busy": True},
            {"busy": False, "commandState": "sent"},
            {"commandState": "idle", "camJob": {"state": "starting"}},
            {"commandState": "idle", "camJob": {"state": "homing"}},
            {"camJob": None, "connected": False},
        ):
            self.state.update(update)
            self.wait(
                lambda update=update: all(
                    self.backend.snapshot.get(key) == value for key, value in update.items()
                )
            )
            self.assertFalse(self.backend.requestClose())
        self.state["connected"] = True
        self.wait(lambda: self.backend.snapshot.get("connected"))
        self.assertTrue(self.backend.requestClose())
        time.sleep(1.1)
        self.assertFalse(self.backend.requestClose())
        self.assertEqual(self.actions(), [])

    def test_managed_window_rejects_close_during_program_and_accepts_when_idle(self):
        qml = Path(__file__).resolve().parents[2] / "qml"
        engine = QQmlApplicationEngine()
        engine.addImportPath(str(qml))
        engine.setInitialProperties({"backend": self.backend})
        engine.load(QUrl.fromLocalFile(str(qml / "Main.qml")))
        try:
            self.assertTrue(engine.rootObjects())
            window = engine.rootObjects()[0]
            self.state["busy"] = True
            self.wait(lambda: self.backend.snapshot.get("busy"))
            self.assertFalse(window.close())
            self.assertTrue(window.isVisible())
            QTest.qWait(100)
            capture = os.environ.get("BETTERCNC_CLOSE_CAPTURE")
            if capture:
                self.assertTrue(window.grabWindow().save(capture))
            self.state["busy"] = False
            self.wait(lambda: not self.backend.snapshot.get("busy"))
            self.assertTrue(window.close())
            self.assertFalse(window.isVisible())
        finally:
            for window in engine.rootObjects():
                window.setProperty("visible", False)
            engine.deleteLater()
            QCoreApplication.sendPostedEvents()

    def test_kiosk_window_stays_fullscreen_and_rejects_operator_exit(self):
        qml = Path(__file__).resolve().parents[2] / "qml"
        engine = QQmlApplicationEngine()
        engine.addImportPath(str(qml))
        engine.setInitialProperties({"backend": self.backend, "kioskMode": True})
        engine.load(QUrl.fromLocalFile(str(qml / "Main.qml")))
        try:
            self.assertTrue(engine.rootObjects())
            window = engine.rootObjects()[0]
            self.wait(lambda: window.visibility() == QWindow.Visibility.FullScreen)
            self.assertFalse(window.close())
            self.assertTrue(window.isVisible())
            quit_item = window.findChild(QObject, "menu-file.quit")
            self.assertIsNotNone(quit_item)
            self.assertFalse(quit_item.property("enabled"))
            window.requestActivate()
            QTest.keyClick(window, Qt.Key.Key_F4, Qt.KeyboardModifier.AltModifier)
            QTest.keyClick(window, Qt.Key.Key_Q, Qt.KeyboardModifier.ControlModifier)
            self.assertTrue(window.isVisible())
            window.showNormal()
            self.wait(lambda: window.visibility() == QWindow.Visibility.FullScreen)
            window.showMinimized()
            self.wait(lambda: window.visibility() == QWindow.Visibility.FullScreen)
            self.assertEqual(self.actions(), [])
        finally:
            for window in engine.rootObjects():
                window.setProperty("kioskMode", False)
                window.setProperty("visible", False)
            engine.deleteLater()
            QCoreApplication.sendPostedEvents()

    def test_kiosk_program_browser_and_commands_reject_path_and_symlink_escape(self):
        program = self.program_roots[0] / "part.ngc"
        program.write_text("G21\nM2\n")
        outside = Path(self.temporary.name).resolve() / "outside.ngc"
        outside.write_text("M2\n")
        (self.program_roots[0] / "escape.ngc").symlink_to(outside)
        (self.program_roots[0] / "escape-dir").symlink_to(outside.parent, target_is_directory=True)
        browser = self.backend.programFiles
        browser.refresh()
        self.assertEqual([item["name"] for item in browser.entries], ["part.ngc"])
        self.assertFalse(browser.browse(str(outside.parent)))
        self.assertEqual(browser.destination("../outside.ngc"), "")
        for rejected in (
            outside,
            self.program_roots[0] / "escape.ngc",
            self.program_roots[0] / "escape-dir/new.ngc",
        ):
            self.assertFalse(self.backend.openProgram(str(rejected)))
            self.assertFalse(self.backend.saveProgram(str(rejected), "G0 X100\n"))
            self.assertFalse(
                self.backend.dispatch("file.save", {"path": str(rejected), "text": "M2\n"})
            )
        self.assertEqual(self.actions(), [])
        self.assertEqual(outside.read_text(), "M2\n")
        self.assertTrue(self.backend.openProgram(str(program)))
        self.wait(lambda: "file.open" in self.actions())
        self.assertTrue(self.backend.saveProgram(str(self.program_roots[1] / "saved.ngc"), "M2\n"))
        self.wait(lambda: "file.save" in self.actions())

    def test_kiosk_rejects_external_tools_and_direct_exit_dispatch(self):
        errors = []
        self.backend.errorOccurred.connect(errors.append)
        for tool in (
            "machine.ladder",
            "machine.calibration",
            "machine.hal-config",
            "machine.hal-meter",
            "machine.hal-scope",
            "show.pyvcp",
        ):
            self.assertFalse(self.backend.dispatch(tool, {}))
            self.assertIn("专用操作界面", errors[-1])
        self.assertFalse(self.backend.dispatch("file.quit", {}))
        self.assertFalse(self.backend.requestClose())
        self.assertEqual(self.actions(), [])


class DesktopCliTests(unittest.TestCase):
    def test_kiosk_status_cli_reads_only_launcher_files_without_loading_backend(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = root / "20261026-120000-123"
            run.mkdir()
            for phase in ("starting", "recovering", "retained"):
                with self.subTest(phase=phase):
                    (run / "state.json").write_text(json.dumps({"phase": phase}))
                    script = f"""
import json, os, sys
from bettercnc.desktop import main
original_open = os.open
def opened(path, flags, *args, **kwargs):
    if path == '/var/log/betterlinuxcnc/launcher':
        path = {str(root)!r}
    return original_open(path, flags, *args, **kwargs)
os.open = opened
def audit(event, args):
    if event in ('socket.connect', 'subprocess.Popen'):
        raise AssertionError('status page attempted process or socket access')
sys.addaudithook(audit)
code = main(['--kiosk-status', '--smoke-test'])
assert 'bettercnc.desktop._backend' not in sys.modules
assert 'bettercnc.session' not in sys.modules
raise SystemExit(code)
"""
                    result = subprocess.run(
                        [sys.executable, "-c", script],
                        env=dict(
                            os.environ,
                            QT_QPA_PLATFORM="offscreen",
                            QT_QUICK_BACKEND="software",
                        ),
                        capture_output=True,
                        text=True,
                        timeout=15,
                    )
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    records = [json.loads(line) for line in result.stdout.splitlines()]
                    self.assertIn({"kioskStatus": "visible", "phase": phase}, records)
                    self.assertNotIn("QQmlApplicationEngine failed", result.stderr)
                    self.assertNotIn("ReferenceError", result.stderr)

    def test_public_kiosk_cli_and_environment_start_without_native_dialogs(self):
        for arguments, kiosk_environment in ((["--kiosk"], "0"), ([], "1")):
            with self.subTest(arguments=arguments):
                result = subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        "from bettercnc.desktop import main; raise SystemExit(main())",
                        *arguments,
                        "--smoke-test",
                        "--socket",
                        "/tmp/no-kiosk-test-controller.sock",
                    ],
                    env=dict(
                        os.environ,
                        BETTERCNC_KIOSK=kiosk_environment,
                        QT_QPA_PLATFORM="offscreen",
                        QT_QUICK_BACKEND="software",
                    ),
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertNotIn("QQmlApplicationEngine failed", result.stderr)
                self.assertNotIn("ReferenceError", result.stderr)


if __name__ == "__main__":
    unittest.main()
