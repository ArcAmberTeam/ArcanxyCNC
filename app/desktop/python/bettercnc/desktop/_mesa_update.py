"""Desktop adapter for the separate, unprivileged Mesa release service."""

import json
import shutil
import sys

from bettercnc_error_records import report
from PySide6.QtCore import Property, QObject, QProcess, QTimer, Signal, Slot


class _MesaProcess(QObject):
    changed = Signal()

    def __init__(self, parent=None, *, command=None):
        super().__init__(parent)
        self._command = command or [shutil.which("betterlinuxcnc-" + self._component) or ""]
        self._available = bool(self._command[0]) and (
            sys.platform == "linux" or command is not None
        )
        self._state = {
            "phase": "not_checked",
            "message": self._messages["not_checked"]
            if self._available
            else "Mesa 更新服务尚未安装",
        }
        self._process = QProcess(self)
        self._process.readyReadStandardOutput.connect(self._read)
        self._process.finished.connect(self._finished)
        self._process.errorOccurred.connect(self._failed)
        self._buffer = b""
        self._seen = False
        self._invalid = False
        self._pending = None
        self._closed = False
        self._operation = ""
        self._timer = QTimer(self)
        self._timer.setInterval(60000)
        self._timer.timeout.connect(lambda: self._start("status"))
        if self._available:
            self._timer.start()
            QTimer.singleShot(0, lambda: self._start("status"))

    state = Property("QVariantMap", lambda self: self._state, notify=changed)
    available = Property(bool, lambda self: self._available, constant=True)

    def _error(self, message):
        report("mesa-update", "adapter_error", message)
        self._state = {"phase": "error", "message": message}
        self.changed.emit()

    def _start(self, operation):
        if self._closed or not self._available or self._process.state() != QProcess.NotRunning:
            return
        self._operation = operation
        self._buffer = b""
        self._seen = self._invalid = False
        self._process.start(self._command[0], [*self._command[1:], operation])

    def _read(self):
        self._buffer += bytes(self._process.readAllStandardOutput())
        if self._invalid:
            self._buffer = b""
            return
        try:
            if len(self._buffer) > 65536:
                raise ValueError("Oversized Mesa response")
            while b"\n" in self._buffer:
                line, self._buffer = self._buffer.split(b"\n", 1)
                record = json.loads(line)
                if (
                    not isinstance(record, dict)
                    or type(record.get("schema_version")) is not int
                    or record["schema_version"] != 1
                    or record.get("component") != self._component
                    or record.get("phase") not in self._messages
                    or not isinstance(record.get("message"), str)
                    or any(
                        record.get(key) is not None and not isinstance(record[key], str)
                        for key in (
                            "installed_app_version",
                            "available_version",
                            "mesa_latest_version",
                        )
                    )
                ):
                    raise ValueError("Invalid Mesa status")
                # The service owns validation and eligibility; the GUI only presents results.
                record["message"] = self._messages[record["phase"]]
                self._state = record
                self._seen = True
                self.changed.emit()
        except (ValueError, UnicodeError, TypeError):
            self._invalid = True
            self._error("Mesa 服务返回了无效状态")
            self._process.kill()

    def _finished(self, code, _status):
        self._read()
        if not self._invalid and (code != 0 or not self._seen or self._buffer):
            self._error("Mesa 更新服务未正常完成，请查看维护日志")
        active = self._state["phase"] in (
            "scheduled",
            "verified",
            "verifying_identity",
            "writing",
            "verifying",
        )
        active = active or (self._component == "mesa-flash" and self._state["phase"] == "checking")
        self._timer.setInterval(1500 if active else 60000)
        pending, self._pending = self._pending, None
        if pending and not self._closed:
            # Re-enter the public action so the newly read state can veto it.
            QTimer.singleShot(0, self.check if pending[0] == "check" else self.request)

    def _failed(self, error):
        if error == QProcess.FailedToStart:
            self._error("无法启动 Mesa 更新服务，请检查安装是否完整")

    def _request(self, operation, phase):
        if self._process.state() != QProcess.NotRunning:
            if self._operation == "status":
                self._pending = (operation, phase)
            return
        if not self._available or self._closed:
            return
        self._state = {"phase": phase, "message": self._messages[phase]}
        self.changed.emit()
        self._start(operation)

    def close(self):
        self._closed = True
        self._timer.stop()
        if self._process.state() != QProcess.NotRunning:
            self._process.kill()
            self._process.waitForFinished(1500)


class MesaUpdate(_MesaProcess):
    _component = "mesa-update"
    _messages = {
        "not_checked": "尚未检查 Mesa 配套更新",
        "checking": "正在检查 Mesa 配套更新…",
        "version_mismatch": "应用与 Mesa 最新版本尚未配对，请稍后重试",
        "source_only": "配套源码已发布；本版本没有经过验证的可烧录固件",
        "release_available": "发现经过验证的配套固件，请先安装对应应用版本",
        "downloaded": "固件已下载并校验，控制板尚未烧录",
        "firmware_unavailable": "当前应用版本没有经过验证的可烧录固件",
        "error": "Mesa 更新检查失败，请重试或查看维护日志",
    }

    @Slot()
    def check(self):
        self._request("check", "checking")


class MesaFlash(_MesaProcess):
    _component = "mesa-flash"
    _messages = {
        "not_checked": "",
        "scheduled": "烧录维护请求已提交，正在等待安全检查",
        "checking": "正在独立校验官方固件和机床状态",
        "verified": "固件验证通过，准备停止控制并备份",
        "verifying_identity": "正在核对控制板身份，请勿断电",
        "writing": "正在写入控制板，请勿断电",
        "verifying": "正在回读验证，请勿断电",
        "programmed_pending_power_cycle": "回读验证成功，控制已停止。请现场断电重启并验收",
        "host_restarted_board_unconfirmed": "主机已重启，尚未确认控制板运行新固件",
        "blocked": "烧录条件不满足，详情请查看维护日志",
        "error": "烧录维护未完成，请查看维护日志并现场排查",
    }

    @Slot()
    def request(self):
        if self._state["phase"] in (
            "scheduled",
            "checking",
            "verified",
            "verifying_identity",
            "writing",
            "verifying",
            "programmed_pending_power_cycle",
        ):
            return
        self._request("request", "scheduled")
