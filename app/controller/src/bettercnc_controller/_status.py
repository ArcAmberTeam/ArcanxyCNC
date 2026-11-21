"""Normalize observed NML status without manufacturing machine coordinates."""

import math

from ._config import AXES

COORDINATES = {
    "actualPosition": "actual_position",
    "commandedPosition": "position",
    "g5xOffset": "g5x_offset",
    "g92Offset": "g92_offset",
    "toolOffset": "tool_offset",
    "dtg": "dtg",
}


def offline(message):
    return {
        "connected": False,
        "message": message,
        "taskState": "unknown",
        "debug": None,
        "powered": False,
        "estop": True,
        "mode": "unknown",
        "busy": False,
        "motionMode": "unknown",
        "axes": [],
        "axisMask": 0,
        "homed": [],
        "homeAllJoints": [],
        "homeAllHomed": False,
        "homingConfigured": False,
        "homingMessage": "LinuxCNC 未连接",
        "jointCount": 0,
        "joints": [],
        **{name: None for name in COORDINATES},
        "rotationXY": None,
        "linearUnits": None,
        "angularUnits": None,
        "velocity": None,
        "maxVelocity": None,
        "feedOverride": None,
        "rapidOverride": None,
        "spindleOverride": None,
        "spindleSpeed": None,
        "spindleFeedbackRpm": None,
        "rtcpGeometry": {},
        "spindleDirection": None,
        "spindleBrake": None,
        "flood": None,
        "mist": None,
        "optionalStop": None,
        "blockDelete": None,
        "limitOverride": None,
        "file": "",
        "currentLine": 0,
        "tool": None,
        "activeCodes": [],
        "g5xIndex": None,
        "toolTable": [],
        "paused": False,
        "commandState": "idle",
        "commandMessage": "",
        "capabilities": {},
        "errors": [],
        "iniPath": None,
        "parameterFile": None,
        "toolTablePath": None,
        "programPrefix": None,
        "pyvcpPath": None,
        "jointMap": {},
        "axisLimits": {},
        "jogMaxVelocity": None,
        "maxVelocityLimit": None,
        "defaultSpindleSpeed": None,
        "spindleMin": None,
        "spindleMax": None,
    }


def vector(value):
    result = [float(x) for x in value]
    if len(result) != 9 or not all(math.isfinite(x) for x in result):
        raise ValueError("LinuxCNC returned an invalid nine-axis coordinate")
    return result


def observe(stat, module, config):
    modes = {module.MODE_MANUAL: "manual", module.MODE_MDI: "mdi", module.MODE_AUTO: "auto"}
    states = {
        module.STATE_ESTOP: "estop",
        module.STATE_ESTOP_RESET: "estop-reset",
        module.STATE_OFF: "off",
        module.STATE_ON: "on",
    }
    if stat.task_state not in states or stat.task_mode not in modes:
        raise ValueError("LinuxCNC task status is not initialized")
    if stat.joints <= 0 or stat.axis_mask <= 0 or stat.linear_units <= 0:
        raise ValueError("LinuxCNC trajectory status is not initialized")
    joints = list(stat.joint[: stat.joints])
    if len(joints) != stat.joints or len(stat.homed) < stat.joints:
        raise ValueError("LinuxCNC joint status is incomplete")
    spindle = stat.spindle[0]
    motion_mode = (
        "joint"
        if stat.motion_mode == module.TRAJ_MODE_FREE
        else "world"
        if stat.motion_mode in (module.TRAJ_MODE_TELEOP, module.TRAJ_MODE_COORD)
        else "unknown"
    )
    busy = (
        stat.interp_state != module.INTERP_IDLE
        or not stat.inpos
        or stat.exec_state != module.EXEC_DONE
        or stat.queue > 0
        or stat.active_queue > 0
        or any(joint.get("homing", False) for joint in joints)
    )
    codes = [f"G{code / 10:g}" for code in stat.gcodes[1:] if code >= 0]
    codes += [f"M{code}" for code in stat.mcodes[1:] if code >= 0]
    return {
        "connected": True,
        "message": "已连接 LinuxCNC",
        "taskState": states[stat.task_state],
        "debug": int(stat.debug),
        "powered": stat.task_state == module.STATE_ON and bool(stat.enabled),
        "estop": bool(stat.estop) or stat.task_state == module.STATE_ESTOP,
        "mode": modes[stat.task_mode],
        "motionMode": motion_mode,
        "busy": busy,
        "axes": [axis for i, axis in enumerate(AXES) if stat.axis_mask & (1 << i)],
        "axisMask": int(stat.axis_mask),
        "jointCount": int(stat.joints),
        "joints": list(range(stat.joints)),
        "homed": [bool(x) for x in stat.homed[: stat.joints]],
        "homeAllHomed": bool(config.home_all_joints)
        and all(joint < stat.joints and stat.homed[joint] for joint in config.home_all_joints),
        **{name: vector(getattr(stat, native)) for name, native in COORDINATES.items()},
        "rotationXY": float(stat.rotation_xy),
        "linearUnits": float(stat.linear_units),
        "angularUnits": float(stat.angular_units),
        "velocity": float(stat.current_vel),
        "maxVelocity": float(stat.max_velocity),
        "feedOverride": float(stat.feedrate),
        "rapidOverride": float(stat.rapidrate),
        "spindleOverride": float(spindle["override"]),
        "spindleSpeed": float(spindle["speed"]),
        "spindleDirection": int(spindle["direction"]),
        "spindleBrake": bool(spindle["brake"]),
        "flood": bool(stat.flood),
        "mist": bool(stat.mist),
        "optionalStop": bool(stat.optional_stop),
        "blockDelete": bool(stat.block_delete),
        "limitOverride": any(joint.get("override_limits", False) for joint in joints),
        "file": str(stat.file),
        "currentLine": int(stat.motion_line or stat.current_line),
        "tool": int(stat.tool_in_spindle),
        "activeCodes": codes,
        "g5xIndex": int(stat.g5x_index),
        "toolTable": [list(tool) for tool in stat.tool_table],
        "paused": bool(stat.paused),
        **config.snapshot(),
    }
