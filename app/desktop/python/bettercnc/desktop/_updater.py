"""Async QObject adapter for the public Rust release-updater CLI."""

import json
import shutil
import sys

from PySide6.QtCore import Property, QCoreApplication, QObject, QProcess, QTimer, Signal, Slot

from bettercnc import __version__


class FirmwareUpdater(QObject):
    changed = Signal()
    _phases = {
        "idle",
        "checking",
        "downloading",
        "verifying",
        "ready",
        "current",
        "no_release",
        "scheduled",
        "installing",
        "complete",
        "error",
    }

    def __init__(self, parent=None, *, command=None):
        super().__init__(parent)
        self._command = command or [shutil.which("betterlinuxcnc-updater") or ""]
        self._available = bool(self._command[0]) and (
            sys.platform == "linux" or command is not None
        )
        message = (
            ""
            if self._available
            else (
                "更新服务尚未安装" if sys.platform == "linux" else "固件更新仅支持 Debian 安装版本"
            )
        )
        self._state = {"phase": "idle", "message": message, "progress": 0, "version": ""}
        self._self_compiled = False
        self._process = QProcess(self)
        self._process.readyReadStandardOutput.connect(self._read)
        self._process.finished.connect(self._finished)
        self._process.errorOccurred.connect(self._failed)
        self._buffer = b""
        self._operation = ""
        self._pending_operation = None
        self._seen = False
        self._protocol_failed = False
        self._timer = QTimer(self)
        self._timer.setInterval(1500)
        self._timer.timeout.connect(lambda: self._start("status"))
        if self._available:
            QTimer.singleShot(0, lambda: self._start("status"))

    state = Property("QVariantMap", lambda self: self._state, notify=changed)
    selfCompiled = Property(bool, lambda self: self._self_compiled, notify=changed)
    available = Property(bool, lambda self: self._available, constant=True)

    def _error(self, message):
        self._timer.stop()
        self._state = {"phase": "error", "message": message, "progress": 0, "version": ""}
        self.changed.emit()

    def _start(self, operation):
        if not self._available or self._process.state() != QProcess.ProcessState.NotRunning:
            return
        self._buffer = b""
        self._seen = False
        self._protocol_failed = False
        self._operation = operation
        arguments = list(self._command[1:]) + [operation]
        if operation == "fetch":
            arguments += ["--current-version", QCoreApplication.applicationVersion() or __version__]
        self._process.start(self._command[0], arguments)

    def _read(self):
        self._buffer += bytes(self._process.readAllStandardOutput())
        if self._protocol_failed:
            self._buffer = b""
            return
        if len(self._buffer) > 65536:
            self._protocol_failed = True
            self._error("更新服务响应过大")
            self._process.kill()
            return
        while b"\n" in self._buffer:
            line, self._buffer = self._buffer.split(b"\n", 1)
            try:
                record = json.loads(line)
                if (
                    not isinstance(record, dict)
                    or record.get("phase") not in self._phases
                    or not isinstance(record.get("message"), str)
                    or not isinstance(record.get("version", ""), str)
                    or type(record.get("self_compiled", False)) is not bool
                    or type(record.get("progress", 0)) is not int
                    or not 0 <= record.get("progress", 0) <= 100
                ):
                    raise ValueError("invalid update status")
            except (ValueError, UnicodeError):
                self._protocol_failed = True
                self._buffer = b""
                self._error("更新服务返回了无效状态")
                self._process.kill()
                return
            self._self_compiled = record.get("self_compiled", False)
            self._state = record
            self._seen = True
            self.changed.emit()

    def _finished(self, code, _status):
        self._read()
        if code != 0 and self._state["phase"] != "error":
            detail = bytes(self._process.readAllStandardError()).decode("utf-8", errors="replace")
            self._error(detail.strip()[:1000] or "更新服务意外退出，请重试")
        elif code == 0 and not self._seen and self._state["phase"] != "error":
            self._error("更新服务未返回结果")
        if self._state["phase"] in ("scheduled", "installing"):
            self._timer.start()
        else:
            self._timer.stop()
        pending, self._pending_operation = self._pending_operation, None
        if pending:
            QTimer.singleShot(0, self.fetch if pending == "fetch" else self.install)

    def _failed(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self._error("无法启动 Rust 更新服务，请检查安装是否完整")

    @Slot()
    def fetch(self):
        if self._state["phase"] in ("scheduled", "installing"):
            return
        if self._process.state() != QProcess.ProcessState.NotRunning:
            if self._operation == "status" or self._state["phase"] in (
                "ready",
                "current",
                "no_release",
                "complete",
                "error",
            ):
                self._pending_operation = "fetch"
            return
        if self._process.state() == QProcess.ProcessState.NotRunning and self._available:
            self._state = {
                "phase": "checking",
                "message": "正在检查最新 Release…",
                "progress": 0,
                "version": "",
            }
            self.changed.emit()
            self._start("fetch")

    @Slot()
    def install(self):
        if self._state["phase"] == "ready":
            if self._process.state() != QProcess.ProcessState.NotRunning:
                self._pending_operation = "install"
                return
            self._start("install")

    def close(self):
        self._timer.stop()
        # Installation belongs to its independent systemd unit and survives GUI exit.
        if self._process.state() != QProcess.ProcessState.NotRunning:
            self._process.kill()
            self._process.waitForFinished(1500)
