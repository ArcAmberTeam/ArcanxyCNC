"""Read configuration through the LinuxCNC INI API, including #INCLUDE support."""

import math
import os
import re

AXES = "XYZABCUVW"
SYSTEMS = ("G54", "G55", "G56", "G57", "G58", "G59", "G59.1", "G59.2", "G59.3")


class Configuration:
    def __init__(self, module, path):
        self.path = os.path.realpath(os.path.expanduser(path)) if path else None
        self.ini = module.ini(self.path) if self.path else None
        self.no_force_homing = self.get("TRAJ", "NO_FORCE_HOMING") == "1"
        self.joints = int(self.number("KINS", "JOINTS", 0))
        self.joint_map = {}
        kinematics = self.get("KINS", "KINEMATICS") or ""
        self.kinematics_model = next(iter(kinematics.split()), None)
        # Only trivkins defines a known Cartesian-to-joint mapping. A Cartesian
        # axis name is never used as a guessed joint index for other kinematics.
        if kinematics.split()[:1] == ["trivkins"]:
            match = re.search(r"(?:^|\s)coordinates=([XYZABCUVWxyzabcuvw]+)(?:\s|$)", kinematics)
            # This is trivkins' documented default, not TRAJ COORDINATES order.
            coordinates = match.group(1).upper() if match else AXES
            if 0 < self.joints <= len(coordinates):
                for joint, axis in enumerate(coordinates[: self.joints]):
                    self.joint_map.setdefault(axis, []).append(joint)
        self.max_velocity = self.number("TRAJ", "MAX_LINEAR_VELOCITY")
        self.jog_max_velocity = self.number("DISPLAY", "MAX_LINEAR_VELOCITY", self.max_velocity)
        self.feed_max = self.number("DISPLAY", "MAX_FEED_OVERRIDE", 1.0)
        self.spindle_override_min = self.number("DISPLAY", "MIN_SPINDLE_OVERRIDE", 0.0)
        self.spindle_override_max = self.number("DISPLAY", "MAX_SPINDLE_OVERRIDE", 1.0)
        self.spindle_min = self.number("SPINDLE_0", "MIN_FORWARD_VELOCITY", 0.0)
        self.spindle_max = self.number("SPINDLE_0", "MAX_FORWARD_VELOCITY")
        self.spindle_min = self.number(
            "DISPLAY",
            "MIN_SPINDLE_SPEED",
            self.number("DISPLAY", "MIN_SPINDLE_0_SPEED", self.spindle_min),
        )
        self.spindle_max = self.number(
            "DISPLAY",
            "MAX_SPINDLE_SPEED",
            self.number("DISPLAY", "MAX_SPINDLE_0_SPEED", self.spindle_max),
        )
        self.default_spindle = self.number(
            "DISPLAY", "DEFAULT_SPINDLE_SPEED", self.number("DISPLAY", "DEFAULT_SPINDLE_0_SPEED")
        )
        self.axis_limits = {}
        self.joint_limits = {}
        self.home_sequences = {}
        for axis in AXES:
            section = "AXIS_" + axis
            self.axis_limits[axis] = {
                "min": self.number(section, "MIN_LIMIT"),
                "max": self.number(section, "MAX_LIMIT"),
                "maxVelocity": self.number(section, "MAX_VELOCITY"),
            }
        for joint in range(self.joints):
            section = "JOINT_" + str(joint)
            self.joint_limits[joint] = self.number(section, "MAX_VELOCITY")
            sequence = self.number(section, "HOME_SEQUENCE")
            if sequence is not None and not sequence.is_integer():
                raise ValueError(f"INI [{section}] HOME_SEQUENCE must be an integer")
            self.home_sequences[joint] = int(sequence) if sequence is not None else None
        # Native homing omits unspecified sequences (default 1000) and positive
        # values above 100. Negative values select synchronized groups; do not
        # silently reinterpret an invalid negative sequence as an excluded joint.
        self.home_all_joints = [
            joint
            for joint, sequence in self.home_sequences.items()
            if sequence is not None and sequence <= 100
        ]
        sequences = sorted({abs(self.home_sequences[joint]) for joint in self.home_all_joints})
        self.home_all_valid = (
            bool(sequences)
            and sequences[0] in (0, 1)
            and sequences == list(range(sequences[0], sequences[0] + len(sequences)))
        )
        self.dedicated_homing = (
            os.environ.get("BETTERCNC_KIOSK") == "1"
            or self.get("EMCMOT", "HOMEMOD") == "zhulong_homing"
            or self.get("BETTERCNC_HOMING", "PROFILE") == "zhulong-v2"
        )
        self.homing_message = self._homing_policy() if self.dedicated_homing else ""

    def _homing_policy(self):
        """Validate the effective, package-prepared INI; never infer measured travel."""
        section = "BETTERCNC_HOMING"
        if (
            self.get(section, "PROFILE") != "zhulong-v2"
            or self.get("EMCMOT", "HOMEMOD") != "zhulong_homing"
        ):
            return "回零未配置：尚未启用已验证的烛龙 XYZ 回零配置"
        if self.no_force_homing:
            return "回零未配置：专用机禁止 NO_FORCE_HOMING 绕过回零"
        if (self.get("TRAJ", "LINEAR_UNITS") or "").lower() != "mm":
            return "回零未配置：烛龙回零配置要求毫米机床单位"
        if (self.get(section, "SWITCH_INPUTS_VERIFIED") or "").upper() != "YES":
            return "回零未配置：必须确认三轴开关输入与极性"
        if (self.get(section, "MOTOR_MAPPING_VERIFIED") or "").upper() != "YES":
            return "回零未配置：XYZ 电机通道与实机轴尚未核验；开关验证不能代替电机验证"
        if (self.get(section, "MOTOR_DIRECTIONS_VERIFIED") or "").upper() != "YES":
            return "回零未配置：电机方向尚未核验；实机应为 X 向后、Y 向左、Z 向下"
        if self.home_all_joints != [0, 1, 2] or any(
            self.joint_map.get(axis) != [joint] for joint, axis in enumerate("XYZ")
        ):
            return "回零未配置：XYZ joint 映射或 HOME ALL 集合不匹配"
        revision = self.get(section, "CONFIGURATION_REVISION")
        parallel = revision == "zhulong-xyz-v5-20261026"
        commissioned = parallel or revision == "zhulong-xyz-20261026"
        if parallel and (
            self.get(section, "PARALLEL_TEST_CONDITION") != "EMPTY_TABLE_NO_TOOL"
            or self.number(section, "SWITCH_OVERRUN_MM") != 1
        ):
            return "回零未配置：并行回零缺少空台测试条件或开关余量记录"
        for joint, axis, direction in (
            (0, "X", -1),
            (1, "Y", -1 if commissioned else 1),
            (2, "Z", -1),
        ):
            travel = self.number(section, f"TRAVEL_{axis}_MM")
            if travel is None or travel <= 15:
                return f"回零未配置：{axis} 轴缺少大于 15 mm 的实测可用总行程"
            joint_section = "JOINT_" + str(joint)
            search = self.number(joint_section, "HOME_SEARCH_VEL")
            latch = self.number(joint_section, "HOME_LATCH_VEL")
            final = self.number(joint_section, "HOME_FINAL_VEL")
            if (
                search is None
                or latch is None
                or final is None
                or not 0
                < direction * latch
                < direction * search
                <= (15 if parallel and axis != "Z" else 5)
                or not 0 < final <= 5
                or self.number(joint_section, "HOME") != 0
                or self.number(joint_section, "HOME_OFFSET") != direction * 5
                or self.home_sequences[joint] != (1 if parallel else joint + 1)
                or (self.get(joint_section, "HOME_IGNORE_LIMITS") or "").upper() != "YES"
                or (self.get(joint_section, "HOME_USE_INDEX") or "").upper() != "NO"
            ):
                return f"回零未配置：{axis} 轴搜索、定位或退开参数不符合已验证配置"
            if parallel:
                acceleration = self.number(joint_section, "MAX_ACCELERATION")
                backoff = self.number(joint_section, "HOME_BACKOFF_VEL")
                # Reserve half the reported 1 mm overrun. This is a configured
                # braking budget (including 10 ms detection/control allowance),
                # not proof of the actual motor deceleration or machine latency.
                if (
                    acceleration is None
                    or acceleration <= 0
                    or backoff is None
                    or not 0 < backoff <= 2
                    or abs(latch) > 1
                    or (axis == "Z" and final > 2)
                    or search * search / (2 * acceleration) + abs(search) * 0.010 > 0.5
                ):
                    return f"回零未配置：{axis} 轴速度、减速预算或慢退速度不符合开关余量"
            lower, upper = (-travel + 10, 0) if direction > 0 else (0, travel - 10)
            if parallel:
                lower = -0.1
            for limits in ("AXIS_" + axis, joint_section):
                minimum = self.number(limits, "MIN_LIMIT")
                maximum = self.number(limits, "MAX_LIMIT")
                if (
                    minimum is None
                    or maximum is None
                    or not lower <= minimum <= 0 <= maximum <= upper
                    or minimum >= maximum
                    or (parallel and minimum != -0.1)
                ):
                    return f"回零未配置：{axis} 轴软限位未落在实测行程内"
        return ""

    def can_home(self, joints):
        if not joints:
            return False
        if self.dedicated_homing:
            return not self.homing_message and all(joint in (0, 1, 2) for joint in joints)
        return True

    def can_home_all(self):
        return self.home_all_valid and self.can_home(self.home_all_joints)

    def get(self, section, key):
        return self.ini.find(section, key) if self.ini else None

    def number(self, section, key, default=None):
        value = self.get(section, key)
        if value is None:
            return default
        result = float(value)
        if not math.isfinite(result):
            raise ValueError(f"INI [{section}] {key} must be finite")
        return result

    def file(self, section, key):
        value = self.get(section, key)
        if not value:
            return None
        value = os.path.expanduser(os.path.expandvars(value))
        if not os.path.isabs(value):
            value = os.path.join(os.path.dirname(self.path), value)
        return os.path.realpath(value)

    def snapshot(self):
        return {
            "iniPath": self.path,
            "kinematicsModel": self.kinematics_model,
            "parameterFile": self.file("RS274NGC", "PARAMETER_FILE"),
            "toolTablePath": self.file("EMCIO", "TOOL_TABLE"),
            "programPrefix": self.file("DISPLAY", "PROGRAM_PREFIX"),
            "pyvcpPath": self.file("DISPLAY", "PYVCP"),
            "defaultSpindleSpeed": self.default_spindle,
            "spindleMin": self.spindle_min,
            "spindleMax": self.spindle_max,
            "maxVelocityLimit": self.max_velocity,
            "jogMaxVelocity": self.jog_max_velocity,
            "jointMap": self.joint_map,
            "axisLimits": self.axis_limits,
            "noForceHoming": self.no_force_homing,
            "homeAllJoints": list(self.home_all_joints),
            "homingConfigured": self.can_home_all(),
            "homingMessage": self.homing_message,
            "randomToolChanger": self.get("EMCIO", "RANDOM_TOOLCHANGER") == "1",
            "feedOverrideMax": self.feed_max,
            "spindleOverrideMin": self.spindle_override_min,
            "spindleOverrideMax": self.spindle_override_max,
        }
