"""Presentation-only client of the fixed Rust maintenance account CLI."""

import json
import sys

from bettercnc_error_records import report
from PySide6.QtCore import Property, QObject, QProcess, QTimer, Signal, Slot


# --------#
# BEGIN: MaintenanceAccount
class MaintenanceAccount(QObject):
    changed = Signal()

    def __init__(self, parent=None, *, command=None):
        super().__init__(parent)
        self._command = command or [
            "/usr/lib/betterlinuxcnc/account-management/cnc-maint/cnc-maint-account"
        ]
        self._available = sys.platform == "linux" or command is not None
        self._closed = False
        self._enabled = False
        self._known = False
        self._busy = False
        self._message = "正在读取维护账户状态…" if self._available else "本机未安装账户管理服务"
        self._process = QProcess(self)
        self._process.finished.connect(self._finished)
        self._process.errorOccurred.connect(self._failed)
        self._deadline = QTimer(self)
        self._deadline.setSingleShot(True)
        self._deadline.setInterval(20000)
        self._deadline.timeout.connect(self._process.kill)
        self._timer = QTimer(self)
        self._timer.setInterval(10000)
        self._timer.timeout.connect(self.refresh)
        if self._available:
            self._timer.start()
            QTimer.singleShot(0, self.refresh)

    enabled = Property(bool, lambda self: self._enabled, notify=changed)
    known = Property(bool, lambda self: self._known, notify=changed)
    busy = Property(bool, lambda self: self._busy, notify=changed)
    available = Property(bool, lambda self: self._available, constant=True)
    message = Property(str, lambda self: self._message, notify=changed)

    def _request(self, operation, password=""):
        if self._closed or not self._available or self._busy:
            return False
        self._busy = True
        self._message = "正在读取…" if operation == "status" else "正在保存…"
        self.changed.emit()
        self._process.start(self._command[0], [*self._command[1:], "request", operation])
        if password:
            self._process.write(password.encode("utf-8"))
        self._process.closeWriteChannel()
        self._deadline.start()
        return True

    @Slot()
    def refresh(self):
        self._request("status")

    @Slot(str, result=bool)
    def setPassword(self, password):
        if not 8 <= len(password.encode("utf-8")) <= 256 or any(
            ord(char) < 32 or ord(char) == 127 or char == ":" for char in password
        ):
            self._message = "密码须为 8–256 字节，不能包含控制字符或冒号"
            self.changed.emit()
            return False
        return self._request("enable", password)

    @Slot(result=bool)
    def disable(self):
        return self._request("disable")

    def _finished(self, code, _status):
        self._deadline.stop()
        self._busy = False
        raw = bytes(self._process.readAllStandardOutput())
        self._process.readAllStandardError()
        try:
            if code != 0 or len(raw) > 1024:
                raise ValueError("Account operation failed")
            record = json.loads(raw)
            if record.get("ok") is not True or type(record.get("enabled")) is not bool:
                raise ValueError("Invalid account response")
            self._enabled = record["enabled"]
            self._known = True
            self._message = "维护登录已开启" if self._enabled else "维护登录已关闭，旧密码已清除"
        except (ValueError, TypeError, AttributeError) as error:
            report("account", "adapter_error", str(error))
            self._known = False
            self._message = "未能确认账户状态，请刷新重试；不要将请求视为已生效"
        self.changed.emit()

    def _failed(self, error):
        if error == QProcess.FailedToStart:
            report("account", "service_unavailable", self._process.errorString())
            self._deadline.stop()
            self._busy = False
            self._known = False
            self._message = "账户管理服务不可用"
            self.changed.emit()

    def close(self):
        self._closed = True
        self._timer.stop()
        self._deadline.stop()
        self._process.kill()
        self._process.waitForFinished(1000)


# END: MaintenanceAccount
# --------#
