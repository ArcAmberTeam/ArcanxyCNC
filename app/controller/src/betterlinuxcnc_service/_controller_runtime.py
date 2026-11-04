"""Single-writer session ownership, serialized controller work and jog leases."""

import asyncio
import math
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

from bettercnc_error_records import report

from bettercnc_controller import Controller, StatusReader

from ._preview_jobs import PreviewJobs
from ._protocol import ProtocolError
from ._wire_snapshot import wire_snapshot

JOG_LEASE_SECONDS = 0.6


# --------#
# BEGIN: ControllerRuntime
class ControllerRuntime:
    def __init__(
        self,
        ini_path=None,
        controller_factory=None,
        process_factory=None,
        status_reader_factory=None,
        cam_inbox=None,
    ):
        self._factory = controller_factory or Controller
        self._status_factory = status_reader_factory or StatusReader
        self._status_reader = None
        self._ini = ini_path
        self._cam_inbox = cam_inbox
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="linuxcnc-owner")
        self._controller = None
        self._owner = None
        self._releasing = False
        self._generation = 0
        self._snapshot = None
        self._lease_deadline = None
        self._jog_expired = False
        self._cam_jog_owner = None
        self._cam_jog_id = None
        self._cam_jog_deadline = None
        self._cam_jog_used = {}
        self._jobs = PreviewJobs(process_factory)
        self._poll_task = asyncio.create_task(self._poll_loop())

    async def _work(self, function, *args):
        return await asyncio.get_running_loop().run_in_executor(self._executor, function, *args)

    def _expired(self):
        return self._lease_deadline is not None and time.monotonic() >= self._lease_deadline

    def _clear_cam_jog(self):
        self._cam_jog_owner = self._cam_jog_id = self._cam_jog_deadline = None

    def _stop_cam_jog(self):
        if self._controller is not None:
            self._controller.stop_jog()

    async def _cancel_cam_jog(self, owner):
        if self._cam_jog_owner is owner:
            self._clear_cam_jog()
            await self._work(self._stop_cam_jog)

    def _start_cam_jog(self, owner, params):
        if self._cam_jog_owner is not owner or self._releasing:
            raise ProtocolError("jog_expired", "本次点动已结束")
        if self._controller is None:
            self._new_controller(self._generation)
        snapshot = self._controller.poll()
        units = snapshot.get("linearUnits")
        if (
            not snapshot.get("connected")
            or snapshot.get("motionMode") != "world"
            or type(units) not in (int, float)
            or not math.isfinite(units)
            or units <= 0
        ):
            raise ProtocolError("jog_unavailable", "XYZ 点动需要已连接且已回零的世界坐标模式")
        # EOF/stop/expiry invalidates a start queued behind another worker call.
        if (
            self._cam_jog_owner is not owner
            or self._cam_jog_id != params["jogId"]
            or self._cam_jog_deadline is None
            or time.monotonic() >= self._cam_jog_deadline
            or self._releasing
        ):
            raise ProtocolError("jog_expired", "本次点动已结束")
        if self._lease_deadline is not None:
            raise ProtocolError("control_in_use", "本地界面正在点动")
        accepted = self._controller.dispatch(
            "jog.start",
            {
                "axis": params["axis"],
                "mode": "world",
                "direction": params["direction"],
                "velocity": params["feedRate"] / 60 * units,
                "increment": 0,
            },
        )
        self._snapshot = self._controller.snapshot
        if not accepted:
            raise ProtocolError(
                "jog_rejected", self._snapshot.get("commandMessage") or "点动被拒绝"
            )
        return {"jogId": params["jogId"], "accepted": True}

    def _poll(self, generation):
        if self._releasing or generation != self._generation or self._controller is None:
            return
        if self._cam_jog_deadline is not None and time.monotonic() >= self._cam_jog_deadline:
            self._clear_cam_jog()
            self._controller.stop_jog()
        if self._expired() or self._jog_expired:
            self._jog_expired = False
            self._lease_deadline = None
            self._controller.stop_jog()
        self._snapshot = self._controller.poll()

    async def _poll_loop(self):
        while True:
            if self._controller is not None and not self._releasing:
                try:
                    await self._work(self._poll, self._generation)
                except Exception as error:
                    report("service", "poll_error", str(error))
                    # A vendor adapter exception must not make a stale online
                    # snapshot available to command/preview callers.
                    self._snapshot = None
            await asyncio.sleep(0.1)

    def _new_controller(self, generation):
        if generation != self._generation:
            return None
        if self._controller is None:
            options = {"cam_inbox": self._cam_inbox} if self._cam_inbox is not None else {}
            self._controller = self._factory(ini_path=self._ini, **options)
        self._snapshot = self._controller.poll()
        return self._snapshot

    def _close_controller(self):
        if self._controller is not None:
            try:
                # close cancels unsent operations and stops owned jogs only;
                # never abort a machining program when a desktop disconnects.
                self._controller.close()
            finally:
                self._controller = None
        self._snapshot = None

    def _release_desktop(self):
        # An accepted CAM job belongs to the service, not the upload/desktop socket.
        job = (self._snapshot or {}).get("camJob") or {}
        if job.get("state") in ("accepted", "homing", "loading", "starting", "running"):
            self._controller.stop_jog()
        else:
            self._close_controller()

    async def release(self, owner):
        await self._cancel_cam_jog(owner)
        if self._owner is not owner:
            return
        self._clear_cam_jog()
        self._releasing = True
        self._generation += 1  # invalidate queued work before awaiting anything
        self._lease_deadline = None
        self._jog_expired = True
        try:
            await self._work(self._release_desktop)
        finally:
            await self._jobs.clear(owner)
            if self._owner is owner:
                self._owner = None
                self._releasing = False

    async def close(self):
        self._poll_task.cancel()
        await asyncio.gather(self._poll_task, return_exceptions=True)
        self._clear_cam_jog()
        if self._owner is not None:
            await self.release(self._owner)
        await self._work(self._close_controller)
        await self._work(self._close_status_reader)
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _close_status_reader(self):
        if self._status_reader is not None:
            self._status_reader.close()
            self._status_reader = None

    def _read_status(self):
        if self._status_reader is None:
            self._status_reader = self._status_factory(ini_path=self._ini)
        result = self._status_reader.poll()
        # A queued/unknown GUI command can precede fresh NML execution feedback.
        command = (self._snapshot or {}).get("commandState")
        if command in ("accepted", "pending", "sent", "unknown"):
            result["commandState"] = command
        job = (self._snapshot or {}).get("camJob")
        if job:
            result["job"] = deepcopy(job)
            if job.get("transferId") and result.get("file") == job.get("path"):
                result["transferId"] = job["transferId"]
        return result

    def _params(self, params, required=(), optional=()):
        if not set(required).issubset(params) or not set(params).issubset(
            set(required) | set(optional)
        ):
            raise ProtocolError("invalid_params", "parameters do not match this method")

    def _observed(self):
        if self._snapshot is None:
            raise ProtocolError("status_unavailable", "controller status is unavailable")
        return wire_snapshot(self._snapshot)

    def _execute(self, owner, generation, action, payload):
        if (
            self._releasing
            or owner is not self._owner
            or generation != self._generation
            or self._controller is None
        ):
            raise ProtocolError("session_expired", "control session expired before command send")
        if self._cam_jog_owner is not None:
            if action not in ("jog.stop", "program.stop", "machine.estop", "machine.power"):
                raise ProtocolError("control_in_use", "CAM 正在点动，请先松开")
            self._clear_cam_jog()
            self._controller.stop_jog()
        if action in ("jog.start", "machine.jog-plus", "machine.jog-minus") and self._expired():
            self._controller.stop_jog()
            self._lease_deadline = None
            raise ProtocolError("jog_lease_expired", "jog lease expired before command send")
        accepted = self._controller.dispatch(action, payload)
        if accepted and action in ("jog.stop", "program.stop", "machine.estop", "machine.power"):
            self._lease_deadline = None
        if not accepted and action in ("jog.start", "machine.jog-plus", "machine.jog-minus"):
            self._controller.stop_jog()
            self._lease_deadline = None
        if self._expired():
            self._controller.stop_jog()
            self._lease_deadline = None
        self._snapshot = self._controller.snapshot
        return {"accepted": bool(accepted), "snapshot": wire_snapshot(self._snapshot)}

    def _cam_request(self, method, params):
        if method.endswith(".start") and (
            self._cam_jog_owner is not None or self._lease_deadline is not None
        ):
            raise ProtocolError("control_in_use", "正在点动，请先松开")
        if self._controller is None:
            self._new_controller(self._generation)
        controller = self._controller
        if method == "cam.home.start":
            result = controller.start_homing(
                params["operationId"], clearance_confirmed=params["clearanceConfirmed"]
            )
        elif method == "cam.home.status":
            result = controller.homing_status(params["operationId"])
        elif method == "cam.home.cancel":
            result = controller.cancel_cam(params["operationId"], homing=True)
        elif method == "cam.workflow.start":
            result = controller.start_received(
                params["transferId"],
                home_first=True,
                clearance_confirmed=params["clearanceConfirmed"],
                machining_confirmed=params["machiningConfirmed"],
                disable_block_delete=params.get("disableBlockDelete", False),
            )
        elif method == "cam.job.start":
            result = controller.start_received(params["transferId"])
        elif method == "cam.job.cancel":
            result = controller.cancel_cam(params["transferId"])
        else:
            result = controller.received_status(params["transferId"])
        self._snapshot = controller.snapshot
        return {"job": result}

    async def handle(self, owner, method, params):
        if method in ("cam.jog.start", "cam.jog.keepalive", "cam.jog.stop"):
            self._params(
                params,
                required=("jogId", "axis", "direction", "feedRate")
                if method == "cam.jog.start"
                else ("jogId",),
            )
            jog_id = params["jogId"]
            try:
                valid_id = isinstance(jog_id, str) and str(uuid.UUID(jog_id)) == jog_id
            except ValueError:
                valid_id = False
            if not valid_id:
                raise ProtocolError("invalid_params", "jogId 必须是规范 UUID")
            if method == "cam.jog.start":
                feed = params["feedRate"]
                if (
                    params["axis"] not in ("X", "Y", "Z")
                    or type(params["direction"]) is not int
                    or params["direction"] not in (-1, 1)
                    or type(feed) not in (int, float)
                    or not math.isfinite(feed)
                    or not 0 < feed <= 3000
                ):
                    raise ProtocolError("invalid_params", "点动轴、方向或速度无效")
                if (
                    self._releasing
                    or self._cam_jog_owner is not None
                    or self._lease_deadline is not None
                ):
                    raise ProtocolError("control_in_use", "已有点动操作")
                now = time.monotonic()
                self._cam_jog_used = {k: v for k, v in self._cam_jog_used.items() if now - v < 300}
                if jog_id in self._cam_jog_used or len(self._cam_jog_used) >= 4096:
                    raise ProtocolError("jog_expired", "点动编号已使用或请求过于频繁")
                self._cam_jog_used[jog_id] = now
                self._cam_jog_owner, self._cam_jog_id = owner, jog_id
                self._cam_jog_deadline = now + JOG_LEASE_SECONDS
                try:
                    return await self._work(self._start_cam_jog, owner, params)
                except BaseException:
                    await self._cancel_cam_jog(owner)
                    raise
            if self._cam_jog_owner is not owner or self._cam_jog_id != jog_id:
                raise ProtocolError("jog_expired", "点动已结束")
            deadline = self._cam_jog_deadline
            if deadline is None:
                raise ProtocolError("jog_expired", "点动已结束")
            if method == "cam.jog.stop" or time.monotonic() >= deadline:
                self._clear_cam_jog()
                await self._work(self._stop_cam_jog)
                if method != "cam.jog.stop":
                    raise ProtocolError("jog_expired", "点动租约已过期")
            else:
                self._cam_jog_deadline = time.monotonic() + JOG_LEASE_SECONDS
            return {"jogId": jog_id, "accepted": True}
        if method in (
            "cam.job.start",
            "cam.job.status",
            "cam.job.cancel",
            "cam.workflow.start",
            "cam.home.start",
            "cam.home.status",
            "cam.home.cancel",
        ):
            keys = ("operationId",) if method.startswith("cam.home.") else ("transferId",)
            if method in ("cam.home.start", "cam.workflow.start"):
                keys += ("clearanceConfirmed",)
            if method == "cam.workflow.start":
                keys += ("machiningConfirmed",)
            optional = ("disableBlockDelete",) if method == "cam.workflow.start" else ()
            self._params(params, required=keys, optional=optional)
            for key in ("clearanceConfirmed", "machiningConfirmed", "disableBlockDelete"):
                if key in params and params[key] is not True:
                    raise ProtocolError("invalid_params", key + " must be true")
            if self._cam_inbox is None:
                raise ProtocolError(
                    "auto_run_disabled", "controller CAM execution is not configured"
                )
            if self._releasing:
                raise ProtocolError("session_busy", "controller session is releasing")
            return await self._work(self._cam_request, method, params)
        if method == "machine.status":
            self._params(params)
            return await self._work(self._read_status)
        if method == "session.attach":
            self._params(params, optional=("ini_path",))
            requested_ini = params.get("ini_path")
            if requested_ini is not None and (
                not isinstance(requested_ini, str) or not os.path.isabs(requested_ini)
            ):
                raise ProtocolError("invalid_params", "ini_path must be an absolute path")
            if (
                requested_ini
                and self._ini
                and os.path.realpath(requested_ini) != os.path.realpath(self._ini)
            ):
                raise ProtocolError(
                    "ini_mismatch", "desktop INI differs from the service configuration"
                )
            if self._owner is not None and self._owner is not owner:
                raise ProtocolError("control_in_use", "another desktop owns machine control")
            if self._owner is None:
                self._owner = owner
                self._generation += 1
                self._lease_deadline = None
                self._jog_expired = False
                try:
                    await self._work(self._new_controller, self._generation)
                except Exception:
                    await self.release(owner)
                    raise
            observed = self._observed()
            actual_ini = observed.get("iniPath") or self._ini
            if requested_ini and (
                not actual_ini or os.path.realpath(requested_ini) != os.path.realpath(actual_ini)
            ):
                await self.release(owner)
                raise ProtocolError(
                    "ini_mismatch", "desktop INI cannot be matched to the running controller"
                )
            return observed
        if self._owner is not owner:
            raise ProtocolError("not_attached", "attach this connection before using v2 methods")
        if method == "session.status":
            self._params(params, optional=("jog_lease",))
            renewal = params.get("jog_lease", False)
            if type(renewal) is not bool:
                raise ProtocolError("invalid_params", "jog_lease must be boolean")
            if self._expired():
                self._jog_expired = True
            elif renewal and self._lease_deadline is not None:
                self._lease_deadline = time.monotonic() + JOG_LEASE_SECONDS
            return self._observed()
        if method == "command.execute":
            self._params(params, required=("action", "payload"))
            action, payload = params["action"], params["payload"]
            if not isinstance(action, str) or not action or not isinstance(payload, dict):
                raise ProtocolError(
                    "invalid_params", "action must be a string and payload an object"
                )
            if action in ("jog.start", "machine.jog-plus", "machine.jog-minus"):
                if self._cam_jog_owner is not None:
                    raise ProtocolError("control_in_use", "CAM 正在点动，请先松开")
                self._lease_deadline = time.monotonic() + JOG_LEASE_SECONDS
                self._jog_expired = False
            return await self._work(self._execute, owner, self._generation, action, payload)
        if method == "preview.start":
            self._params(params, required=("path",))
            context = deepcopy(self._snapshot or {})
            if not context.get("connected"):
                raise ProtocolError(
                    "status_unavailable", "preview needs an observed machine configuration"
                )
            keys = (
                "g5xIndex",
                "axisMask",
                "blockDelete",
                "actualPosition",
                "g5xOffset",
                "g92Offset",
                "toolOffset",
                "rotationXY",
                "linearUnits",
                "angularUnits",
                "randomToolChanger",
                "iniPath",
                "parameterFile",
                "toolTablePath",
                "toolTable",
            )
            context = {key: context[key] for key in keys if context.get(key) is not None}
            return await self._jobs.start(owner, params["path"], context)
        if method == "preview.read":
            self._params(params, required=("job_id", "offset"))
            return self._jobs.read(owner, params["job_id"], params["offset"])
        if method == "preview.cancel":
            self._params(params, required=("job_id",))
            return await self._jobs.cancel(owner, params["job_id"])
        raise ProtocolError("unsupported_method", "unsupported v2 method")


# END: ControllerRuntime
# --------#
