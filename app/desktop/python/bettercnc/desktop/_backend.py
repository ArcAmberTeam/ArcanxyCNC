"""QObject API for desktop composition; machine policy belongs to Controller."""

import copy
import json
import math
import os
import re
import shlex
import shutil
import time
from pathlib import Path

from PySide6.QtCore import (
    Property,
    QEvent,
    QObject,
    QProcess,
    QSettings,
    Qt,
    QThread,
    QTimer,
    QUrl,
    Signal,
    Slot,
)
from PySide6.QtGui import QGuiApplication

from ._mesa_update import MesaFlash, MesaUpdate
from ._program import ProgramModel
from ._program_files import ProgramFiles
from ._updater import FirmwareUpdater
from ._worker import ControllerWorker


def local_path(value):
    url = QUrl(str(value))
    if url.scheme() and not url.isLocalFile():
        raise ValueError("只能打开本机文件")
    try:
        return Path(url.toLocalFile() if url.isLocalFile() else str(value)).expanduser().resolve()
    except RuntimeError as error:
        raise ValueError("文件路径包含循环链接") from error


class DesktopBackend(QObject):
    snapshotChanged = Signal()
    historyChanged = Signal()
    recentFilesChanged = Signal()
    toolTableChanged = Signal()
    errorOccurred = Signal(str)
    noticeOccurred = Signal(str)
    commandRequested = Signal(str, dict)
    stopRequested = Signal()
    shutdownRequested = Signal()
    heartbeatRequested = Signal(float)

    def __init__(
        self,
        socket_path=None,
        ini_path=None,
        parent=None,
        worker_factory=ControllerWorker,
        settings=None,
        managed=False,
        updater_command=None,
        kiosk=False,
        program_roots=None,
        mesa_update_command=None,
        mesa_flash_command=None,
    ):
        super().__init__(parent)
        self._snapshot = {
            "connected": False,
            "connecting": True,
            "message": "正在连接本地服务…",
            "axes": [],
            "powered": False,
            "estop": True,
            "busy": False,
            "capabilities": {},
            "actualPosition": None,
            "commandedPosition": None,
            "errors": [],
        }
        self._program = ProgramModel(self)
        self._program_files = ProgramFiles(self, roots=program_roots)
        self._firmware_updater = FirmwareUpdater(self, command=updater_command)
        self._mesa_update = MesaUpdate(self, command=mesa_update_command)
        self._mesa_flash = MesaFlash(self, command=mesa_flash_command)
        self._settings = settings if settings is not None else QSettings()
        self._history = self._settings.value("mdi/history", [], type=list) or []
        self._recent = self._settings.value("program/recent", [], type=list) or []
        self._tool_text = ""
        self._tool_rows = []
        self._tool_path = ""
        self._last_errors = []
        self._last_command_error = ""
        self._preview_signature = None
        self._requested_file = ""
        self._closed = False
        self._managed = managed
        self._kiosk = kiosk
        self._last_status_time = 0
        self._thread = QThread(self)
        self._thread.setObjectName("Local controller socket")
        self._worker = worker_factory(socket_path=socket_path, ini_path=ini_path)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.start)
        self._worker.snapshotReady.connect(self._publish)
        self._worker.rejected.connect(self.errorOccurred)
        self._worker.accepted.connect(self._command_accepted)
        self.commandRequested.connect(self._worker.dispatch)
        self.stopRequested.connect(self._worker.stopJog)
        self.shutdownRequested.connect(self._worker.shutdown)
        self.heartbeatRequested.connect(self._worker.heartbeat)
        self._program.previewRequested.connect(self._worker.startPreview)
        self._program.cancelRequested.connect(self._worker.cancelPreview)
        self._worker.previewReady.connect(self._program.acceptPreview)
        self._worker.stopped.connect(self._thread.quit, Qt.ConnectionType.DirectConnection)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.start()
        self._heartbeat = QTimer(self)
        self._heartbeat.setInterval(100)
        self._heartbeat.timeout.connect(lambda: self.heartbeatRequested.emit(time.monotonic()))
        self._heartbeat.start()

    snapshot = Property("QVariantMap", lambda self: self._snapshot, notify=snapshotChanged)
    program = Property(QObject, lambda self: self._program, constant=True)
    programFiles = Property(QObject, lambda self: self._program_files, constant=True)
    firmwareUpdater = Property(QObject, lambda self: self._firmware_updater, constant=True)
    mesaUpdate = Property(QObject, lambda self: self._mesa_update, constant=True)
    mesaFlash = Property(QObject, lambda self: self._mesa_flash, constant=True)
    history = Property("QStringList", lambda self: self._history, notify=historyChanged)
    recentFiles = Property("QStringList", lambda self: self._recent, notify=recentFilesChanged)
    toolTable = Property("QVariantList", lambda self: self._tool_rows, notify=toolTableChanged)
    toolTableText = Property(str, lambda self: self._tool_text, notify=toolTableChanged)

    @Slot(result=bool)
    def requestClose(self):
        """A managed DISPLAY exiting also tears down LinuxCNC's native core."""
        if self._kiosk:
            return False
        state = self._snapshot
        if self._managed and (
            not state.get("connected")
            or time.monotonic() - self._last_status_time > 1
            or state.get("busy", True)
            or state.get("paused", False)
            or state.get("commandState") in ("accepted", "pending", "sent", "unknown")
            or (state.get("camJob") or {}).get("state")
            in ("accepted", "homing", "loading", "starting", "running", "unknown")
        ):
            self.errorOccurred.emit(
                "加工、命令尚未结束或状态未知，不能退出机床界面；请先在本地停止并确认空闲。"
            )
            return False
        return True

    def _context(self):
        names = (
            "iniPath",
            "parameterFile",
            "toolTablePath",
            "toolTable",
            "toolTableRevision",
            "actualPosition",
            "commandedPosition",
            "g5xOffset",
            "g92Offset",
            "toolOffset",
            "rotationXY",
            "g5xIndex",
            "linearUnits",
            "angularUnits",
            "axisMask",
            "blockDelete",
            "tool",
            "programUnits",
        )
        context = {name: self._snapshot[name] for name in names if name in self._snapshot}
        context.update(self._snapshot.get("previewContext", {}))
        return context

    @Slot(dict)
    def _publish(self, snapshot):
        if self._closed:
            return
        previous = self._snapshot
        self._last_status_time = time.monotonic()
        self._snapshot = copy.deepcopy(snapshot)
        if previous != self._snapshot:
            self.snapshotChanged.emit()
        if previous.get("connected") and not snapshot.get("connected"):
            self.stopRequested.emit()
        errors = snapshot.get("errors", [])
        if errors and errors != self._last_errors:
            latest = errors[-1]
            signal = (
                self.noticeOccurred
                if isinstance(latest, dict) and latest.get("error") is False
                else self.errorOccurred
            )
            signal.emit(str(latest.get("message", latest) if isinstance(latest, dict) else latest))
        self._last_errors = copy.deepcopy(errors)
        state = snapshot.get("commandState")
        detail = snapshot.get("commandMessage", "")
        if state in ("error", "unknown") and detail and detail != self._last_command_error:
            self.errorOccurred.emit(detail)
        self._last_command_error = detail if state in ("error", "unknown") else ""
        current_file = snapshot.get("file", "")
        if current_file == self._requested_file or state in ("error", "unknown", "disconnected"):
            self._requested_file = ""
        if current_file and current_file != self._program.filePath and not self._requested_file:
            try:
                self._program.load(self._program_path(current_file), self._context())
                self._remember(current_file)
            except (ValueError, OSError) as error:
                # Avoid retrying unreadable external files on every status tick.
                if current_file != getattr(self, "_failed_file", ""):
                    self.errorOccurred.emit(f"无法读取控制器程序：{error}")
                    self._failed_file = current_file
        tool_path = snapshot.get("toolTablePath", "")
        if tool_path and (
            tool_path != self._tool_path
            or snapshot.get("toolTableRevision") != previous.get("toolTableRevision")
        ):
            self._tool_path = tool_path
            self._read_tool_table()
        context = self._context()
        signature = json.dumps(
            {
                key: value
                for key, value in context.items()
                if key not in ("actualPosition", "commandedPosition")
            },
            sort_keys=True,
        )
        if self._preview_signature is not None and signature != self._preview_signature:
            self._program.preview(context)
        self._preview_signature = signature

    @Slot(str, "QVariantMap", result=bool)
    def dispatch(self, action, payload):
        if self._closed:
            return False
        payload = dict(payload or {})
        if action == "machine.debug":
            # QML Number(text) crosses QVariantMap as a double, even for a whole
            # number. Preserve the protocol's explicit integer representation.
            value = payload.get("value")
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value != int(value)
            ):
                self.errorOccurred.emit("调试标志必须为整数")
                return False
            payload = {"value": int(value)}
        if action == "file.open" and payload.get("path"):
            return self.openProgram(payload["path"])
        if self._kiosk and action == "file.save":
            return self.saveProgram(payload.get("path", ""), payload.get("text", ""))
        if action == "file.reload":
            return self.reloadProgram()
        if action == "file.clear-recents":
            self._recent = []
            self._settings.setValue("program/recent", [])
            self.recentFilesChanged.emit()
            return True
        if action == "file.quit":
            self.stopJog()
            if self._kiosk:
                return False
            QGuiApplication.quit()
            return True
        if action.startswith("mdi.") and action in ("mdi.clear", "mdi.copy", "mdi.paste"):
            return self._history_action(action)
        if action in ("mdi.execute", "mdi.go"):
            text = str(payload.get("text", payload.get("command", ""))).strip()
            if not text or "\n" in text or "\r" in text:
                self.errorOccurred.emit("请输入一行有效的 MDI 指令")
                return False
            payload = {"text": text}
            action = "mdi.execute"
            # Record submitted text as history, never as a machine completion.
            if self._snapshot.get("connected"):
                self.addHistory(text)
        if action in ("program.run", "program.run-line", "program.step"):
            loaded = self._snapshot.get("file")
            if not loaded or os.path.realpath(loaded) != self._program.filePath:
                self.errorOccurred.emit("当前显示的程序尚未由控制器加载")
                return False
            if action == "program.run-line":
                payload["line"] = self._program.selectedLine
        if action == "tool.edit":
            self._read_tool_table()
            return bool(self._tool_path)
        if action == "tool.reload":
            self._read_tool_table()
        if action == "machine.status":
            self.noticeOccurred.emit(json.dumps(self._snapshot, ensure_ascii=False, indent=2))
            return True
        if action in (
            "machine.ladder",
            "machine.calibration",
            "machine.hal-config",
            "machine.hal-meter",
            "machine.hal-scope",
            "show.pyvcp",
        ):
            return self._launch_tool(action)
        self.commandRequested.emit(action, payload)
        return True

    @Slot()
    def stopJog(self):
        if not self._closed:
            self.stopRequested.emit()

    def _can_edit(self):
        if self._snapshot.get("busy") or self._snapshot.get("commandState") in ("pending", "sent"):
            self.errorOccurred.emit("请先停止程序并等待当前命令结束")
            return False
        return True

    @Slot(str, result=bool)
    def openProgram(self, value):
        if not self._can_edit():
            return False
        try:
            path = self._program_path(value)
            self._program.load(path, self._context())
            self._remember(str(path))
            if self._snapshot.get("connected"):
                self._requested_file = str(path)
                self.commandRequested.emit("file.open", {"path": str(path)})
            return True
        except (OSError, ValueError) as error:
            self.errorOccurred.emit(str(error))
            return False

    @Slot(result=bool)
    def reloadProgram(self):
        if not self._program.filePath:
            self.errorOccurred.emit("尚未打开加工程序")
            return False
        return self.openProgram(self._program.filePath)

    @Slot(str, str, result=bool)
    def saveProgram(self, value, text):
        if not self._can_edit() or not self._snapshot.get("connected"):
            self.errorOccurred.emit("需要连接控制器并停止程序后才能保存程序")
            return False
        try:
            path = self._program_path(value)
            if not path.name or "\0" in text:
                raise ValueError("程序文件或内容无效")
            self.commandRequested.emit("file.save", {"path": str(path), "text": text})
            return True
        except (OSError, ValueError) as error:
            self.errorOccurred.emit(str(error))
            return False

    def _program_path(self, value):
        path = local_path(value)
        return self._program_files.resolve(path) if self._kiosk else path

    @Slot(str, dict)
    def _command_accepted(self, action, payload):
        if self._closed:
            return
        if action == "file.save":
            try:
                path = str(self._program_path(payload["path"]))
                self._program.load(path, self._context())
                self._requested_file = path
                self._remember(path)
                self.noticeOccurred.emit("程序文件已保存；控制器加载状态以反馈为准")
            except (OSError, ValueError, KeyError) as error:
                self.errorOccurred.emit(str(error))
        elif action == "tooltable.save":
            self._read_tool_table()
            self.noticeOccurred.emit("刀具表已保存；重载状态以控制器反馈为准")

    def _remember(self, path):
        self._recent = [path] + [entry for entry in self._recent if entry != path][:11]
        self._settings.setValue("program/recent", self._recent)
        self.recentFilesChanged.emit()

    @Slot(str)
    def addHistory(self, text):
        self._history = [*self._history, text][-100:]
        self._settings.setValue("mdi/history", self._history)
        self.historyChanged.emit()

    @Slot()
    def clearHistory(self):
        self._history = []
        self._settings.setValue("mdi/history", [])
        self.historyChanged.emit()

    def _history_action(self, action):
        if action == "mdi.clear":
            self.clearHistory()
        elif action == "mdi.copy":
            QGuiApplication.clipboard().setText("\n".join(self._history))
        else:
            # Pasting only edits the history; it never executes clipboard text.
            entries = QGuiApplication.clipboard().text().splitlines()
            for entry in entries[-100:]:
                if entry.strip():
                    self.addHistory(entry.strip()[:256])
        return True

    def _read_tool_table(self):
        if not self._tool_path:
            return
        try:
            self._tool_text = Path(self._tool_path).read_text(encoding="utf-8")
            self._tool_rows = self._parse_tool_table(self._tool_text)
            self.toolTableChanged.emit()
        except (OSError, ValueError) as error:
            self.errorOccurred.emit(f"无法读取刀具表：{error}")

    @staticmethod
    def _parse_tool_table(text):
        rows = []
        tools = set()
        for number, line in enumerate(text.splitlines(), 1):
            values, _, comment = line.partition(";")
            if not values.strip():
                continue
            row = {"comment": comment.strip()}
            for token in values.split():
                match = re.fullmatch(
                    r"([TPXYZABCUVWDIJQ])([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)",
                    token,
                    re.I,
                )
                if not match:
                    raise ValueError(f"刀具表第 {number} 行格式错误：{token}")
                key, value = match.groups()
                key = key.upper()
                value = float(value)
                if not math.isfinite(value) or key in row:
                    raise ValueError(f"刀具表第 {number} 行参数无效")
                if key in "TPQ" and (value != int(value) or value < 0):
                    raise ValueError(f"刀具表第 {number} 行 {key} 必须是非负整数")
                row[key] = value
            if "T" not in row or "P" not in row or row["T"] in tools:
                raise ValueError(f"刀具表第 {number} 行需有唯一刀号 T 和刀位 P")
            if row.get("Q", 0) > 9 or row.get("D", 0) < 0:
                raise ValueError(f"刀具表第 {number} 行方向或直径无效")
            tools.add(row["T"])
            rows.append(row)
        return rows

    @Slot(str, result=bool)
    def saveToolTableText(self, text):
        if not self._can_edit() or not self._tool_path or not self._snapshot.get("connected"):
            self.errorOccurred.emit("需要连接控制器并停止程序后才能保存刀具表")
            return False
        try:
            self._parse_tool_table(text)
            self.commandRequested.emit("tooltable.save", {"text": text})
            return True
        except (OSError, ValueError) as error:
            self.errorOccurred.emit(str(error))
            return False

    @Slot("QVariantList", result=bool)
    def saveToolTable(self, rows):
        try:
            text = (
                "\n".join(
                    " ".join(f"{key}{float(row[key]):g}" for key in "TPXYZABCUVWDIJQ" if key in row)
                    + ";"
                    + str(row.get("comment", "")).replace("\n", " ")
                    for row in rows
                )
                + "\n"
            )
            return self.saveToolTableText(text)
        except (TypeError, ValueError, KeyError) as error:
            self.errorOccurred.emit(str(error))
            return False

    @Slot()
    def reloadToolTable(self):
        self.dispatch("tool.reload", {})

    def _launch_tool(self, action):
        if self._kiosk:
            self.errorOccurred.emit("专用操作界面不提供外部调试工具；请联系维护人员。")
            return False
        if not self._snapshot.get("connected"):
            self.errorOccurred.emit("请先连接 LinuxCNC")
            return False
        commands = {
            "machine.hal-config": ["halshow"],
            "machine.hal-meter": ["halmeter"],
            "machine.hal-scope": ["halscope"],
            "machine.calibration": ["emccalib"],
            "machine.ladder": ["classicladder", "--modmaster"],
        }
        command = commands.get(action)
        if action == "show.pyvcp":
            panel = self._snapshot.get("pyvcpPath", "")
            if panel and Path(panel).is_file():
                command = ["pyvcp", panel]
        if not command or not shutil.which(command[0]):
            self.errorOccurred.emit("当前配置未提供此面板，或对应 LinuxCNC 工具尚未安装")
            return False
        ini = self._snapshot.get("iniPath", "")
        if action == "machine.calibration" and ini:
            command.extend(["-ini", ini])
        started, _pid = QProcess.startDetached(command[0], command[1:])
        if not started:
            self.errorOccurred.emit(f"无法启动 {shlex.join(command)}")
        return started

    def eventFilter(self, watched, event):
        if event.type() in (QEvent.Type.ApplicationDeactivate, QEvent.Type.WindowDeactivate):
            self.stopJog()
        return False

    @Slot()
    def close(self):
        if self._closed:
            return
        self.stopJog()
        self._closed = True
        self._firmware_updater.close()
        self._mesa_update.close()
        self._mesa_flash.close()
        self._heartbeat.stop()
        self._program.cancel()
        self.shutdownRequested.emit()
        # The LinuxCNC extension may wait for a command acknowledgement. Keep
        # the worker alive through that bounded call and its final jog stop.
        self._thread.wait(30_000)
        self._settings.sync()
