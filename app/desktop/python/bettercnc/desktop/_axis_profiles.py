"""Presentation adapter for the fixed machine-profile maintenance CLI."""

import json
import math
import sys
import time

from PySide6.QtCore import Property, QObject, QProcess, QTimer, Signal, Slot


# --------#
# BEGIN: AxisProfiles
class AxisProfiles(QObject):
    changed = Signal()

    def __init__(self, parent=None, *, command=None):
        super().__init__(parent)
        self._command = command or ["/usr/sbin/betterlinuxcnc-appliance", "axis-profile"]
        self._available = sys.platform == "linux" or command is not None
        self._state = {"profiles": [], "configured_axis_count": None, "operation": None}
        self._message = (
            "正在读取机床配置…" if self._available else "本机预览环境未安装机床配置切换服务"
        )
        self._busy = False
        self._closed = False
        self._buffer = b""
        self._operation = ""
        self._requested = None
        self._pending = None
        self._pending_deadline = 0
        self._process = QProcess(self)
        self._process.readyReadStandardOutput.connect(self._read)
        self._process.finished.connect(self._finished)
        self._process.errorOccurred.connect(self._failed)
        self._deadline = QTimer(self)
        self._deadline.setSingleShot(True)
        self._deadline.setInterval(15000)
        self._deadline.timeout.connect(self._timed_out)
        self._timer = QTimer(self)
        self._timer.setInterval(5000)
        self._timer.timeout.connect(self.refresh)
        if self._available:
            self._timer.start()
            QTimer.singleShot(0, self.refresh)

    state = Property("QVariantMap", lambda self: self._state, notify=changed)
    message = Property(str, lambda self: self._message, notify=changed)
    busy = Property(bool, lambda self: self._busy, notify=changed)
    available = Property(bool, lambda self: self._available, constant=True)

    def _start(self, operation, count=None):
        if self._closed or not self._available or self._busy:
            return False
        self._buffer = b""
        self._operation = operation
        self._requested = count
        self._busy = True
        self.changed.emit()
        arguments = [*self._command[1:], operation]
        if count is not None:
            arguments.append(str(count))
        self._process.start(self._command[0], arguments)
        self._deadline.start()
        return True

    @Slot()
    def refresh(self):
        self._start("status")

    @Slot(int, result=bool)
    def request(self, count):
        if type(count) is not int or count not in (3, 4, 5):
            return False
        operation = self._state.get("operation") or {}
        if operation.get("phase") in ("scheduled", "switching"):
            return False
        if not any(
            profile["axis_count"] == count and profile["available"]
            for profile in self._state["profiles"]
        ):
            self._message = "转轴参数尚未完整，暂未改写当前 INI"
            self.changed.emit()
            return False
        if not self._start("request", count):
            return False
        self._pending = {"phase": "scheduled", "axis_count": count, "started_at": time.time()}
        self._pending_deadline = time.monotonic() + 30
        self._state = {**self._state, "operation": self._pending}
        self.changed.emit()
        return True

    def _read(self):
        self._buffer += bytes(self._process.readAllStandardOutput())
        if len(self._buffer) > 65536:
            self._message = "机床配置服务返回内容过大"
            self._process.kill()

    def _finished(self, code, _status):
        self._deadline.stop()
        self._read()
        self._busy = False
        try:
            if code != 0 or len(self._buffer) > 65536:
                raise ValueError("service failed")
            record = json.loads(self._buffer)
            if self._operation == "request":
                if (
                    record.get("phase") != "scheduled"
                    or record.get("axis_count") != self._requested
                ):
                    raise ValueError("invalid request acknowledgement")
                self._state = {**self._state, "operation": self._pending}
                self._message = "已提交轴数设置，正在备份并自动写入 INI / HAL"
            else:
                if (
                    record.get("schema_version") != 1
                    or record.get("component") != "axis-profile"
                    or not isinstance(record.get("profiles"), list)
                    or len(record["profiles"]) != 3
                    or [p.get("axis_count") for p in record["profiles"]] != [3, 4, 5]
                    or any(
                        type(p.get("available")) is not bool
                        or not isinstance(p.get("reason"), str)
                        or p.get("axes") != {3: "XYZ", 4: "XYZC", 5: "XYZAC"}[p["axis_count"]]
                        for p in record["profiles"]
                    )
                    or record.get("configured_axis_count") not in (None, 3, 4, 5)
                ):
                    raise ValueError("invalid profile status")
                operation = record.get("operation")
                if operation is not None and (
                    not isinstance(operation, dict)
                    or operation.get("phase")
                    not in ("scheduled", "switching", "configured", "error")
                    or operation.get("axis_count") not in (3, 4, 5)
                    or not isinstance(operation.get("message", ""), str)
                    or len(operation.get("message", "")) > 8192
                    or type(operation.get("started_at")) not in (int, float)
                    or not math.isfinite(operation["started_at"])
                ):
                    raise ValueError("invalid operation status")
                if self._pending:
                    if operation and operation["started_at"] >= self._pending["started_at"]:
                        self._pending = None
                    elif time.monotonic() < self._pending_deadline:
                        record["operation"] = operation = self._pending
                    else:
                        record["operation"] = operation = {**self._pending, "phase": "error"}
                        self._pending = None
                self._state = record
                self._message = {
                    "scheduled": "已提交切换请求",
                    "switching": "正在自动写入 INI / HAL，控制界面将重新打开",
                    "configured": "INI / HAL 已写入；以连接后的实际轴数确认是否生效",
                    "error": "切换未完成，请查看配置切换服务日志；未确认成功前不要加工",
                }.get((operation or {}).get("phase"), "")
                if operation and operation["phase"] == "error" and operation.get("message"):
                    self._message = "切换未完成：\n" + operation["message"]
        except (ValueError, TypeError, AttributeError, KeyError):
            # A lost acknowledgement does not cancel an independently started job.
            self._state = {
                "profiles": [],
                "configured_axis_count": None,
                "operation": self._pending,
            }
            self._message = "无法读取或应用机床配置，请检查配置完整性、服务安装和维护权限"
        self.changed.emit()

    def _failed(self, error):
        if error == QProcess.FailedToStart:
            self._deadline.stop()
            self._busy = False
            self._state = {"profiles": [], "configured_axis_count": None, "operation": None}
            self._message = "机床配置切换服务尚未安装"
            self.changed.emit()

    def _timed_out(self):
        # Stop only the CLI observer. A system maintenance job has its own lifetime.
        self._process.kill()

    def close(self):
        self._closed = True
        self._timer.stop()
        self._deadline.stop()
        if self._process.state() != QProcess.NotRunning:
            self._process.kill()
            self._process.waitForFinished(1500)


# END: AxisProfiles
# --------#
