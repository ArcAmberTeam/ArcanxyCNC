"""Generate axis-count changes from installed INI settings, without machine I/O."""

import configparser
import hashlib
import math
import re
import shlex

AXES = {3: "XYZ", 4: "XYZC", 5: "XYZAC"}
HAL_KEYS = ("HALFILE", "POSTGUI_HALFILE", "SHUTDOWN")


# --------#
# BEGIN: AutomaticAxisConfiguration
def parse_ini(text):
    if re.search(r"^\s*#INCLUDE", text, re.MULTILINE):
        raise ValueError("Automatic axis changes require a self-contained INI")
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    section, seen = "", set()
    for line in text.splitlines():
        value = line.strip()
        if not value or value.startswith(("#", ";")):
            continue
        if value.startswith("[") and value.endswith("]"):
            section = value[1:-1]
        elif "=" in value:
            key = value.split("=", 1)[0].strip()
            if (section, key) in seen and not (section == "HAL" and key in HAL_KEYS):
                raise ValueError("Ambiguous repeated INI setting: " + key)
            seen.add((section, key))
    parser.read_string(text)
    return parser


def axis_count(text):
    ini = parse_ini(text)
    coordinates = "".join(ini.get("TRAJ", "COORDINATES").split()).upper()
    count = next((count for count, axes in AXES.items() if axes == coordinates), None)
    if count is None or ini.getint("KINS", "JOINTS") != count:
        raise ValueError("Current axes must be XYZ, XYZC or XYZAC")
    return count


def hal_files(text):
    section, names = "", []
    for line in text.splitlines():
        value = line.strip()
        if value.startswith("["):
            section = value
        elif section == "[HAL]" and "=" in value and not value.startswith(("#", ";")):
            key, value = value.split("=", 1)
            if key.strip() in HAL_KEYS:
                words = shlex.split(value, comments=True)
                if len(words) != 1 or not re.fullmatch(r"[^/\\\s]+\.hal", words[0]):
                    raise ValueError(
                        "Automatic switching requires local literal HAL filenames"
                    )
                names.append(words[0])
    if not names or len(names) > 32 or len(names) != len(set(names)):
        raise ValueError("Missing or excessive HAL files")
    return names


def patch_ini(text, settings, replacements, rotary_sections):
    """Retain unrelated lines and settings, including all XYZ calibration."""
    section, output, applied = "", [], set()
    removed = {"AXIS_A", "AXIS_C", "JOINT_3", "JOINT_4"}
    for line in text.splitlines(keepends=True):
        header = re.match(r"\s*\[([^]]+)\]", line)
        if header:
            section = header[1]
        if section in removed:
            continue
        match = re.match(r"\s*([A-Z_0-9]+)\s*=", line)
        key = (section, match[1]) if match else None
        if key in settings:
            output.append(f"{key[1]} = {settings[key]}\n")
            applied.add(key)
        elif key and section == "HAL" and key[1] in HAL_KEYS:
            name = shlex.split(line.split("=", 1)[1], comments=True)[0]
            output.append(f"{key[1]} = {replacements.get(name, name)}\n")
        else:
            output.append(line)
    required = {("KINS", "JOINTS"), ("KINS", "KINEMATICS"), ("TRAJ", "COORDINATES")}
    if not required <= applied:
        raise ValueError("Current INI is missing axis topology settings")
    output.append("\n# BEGIN: AutomaticallyGeneratedRotaryAxes\n")
    for name, values in rotary_sections:
        output.append(f"[{name}]\n")
        output.extend(f"{key} = {value}\n" for key, value in values.items())
        output.append("\n")
    output.append("# END: AutomaticallyGeneratedRotaryAxes\n")
    return "".join(output)


def rotary_parameters(ini, axis):
    # Reuse stored calibration; XYZ pulse/mm values are never rotary pulse/degree values.
    joint_section = "JOINT_" + axis
    if not ini.has_section(joint_section):
        joint_section = "JOINT_3" if axis == "A" else "JOINT_4"
    joint = dict(ini.items(joint_section)) if ini.has_section(joint_section) else {}
    axis_section = "AXIS_" + axis
    limits = dict(ini.items(axis_section)) if ini.has_section(axis_section) else {}
    if axis == "A":
        limits.update(MIN_LIMIT="-90", MAX_LIMIT="90")
        joint.update(MIN_LIMIT="-90", MAX_LIMIT="90")
    joint["TYPE"] = "ANGULAR"
    missing = []
    for name, values, keys in (
        (
            "axis",
            limits,
            ("MAX_VELOCITY", "MAX_ACCELERATION", "MIN_LIMIT", "MAX_LIMIT"),
        ),
        (
            "joint",
            joint,
            (
                "STEP_SCALE",
                "MAX_VELOCITY",
                "MAX_ACCELERATION",
                "STEPGEN_MAXVEL",
                "STEPGEN_MAXACCEL",
                "FERROR",
                "MIN_FERROR",
                "DIRSETUP",
                "DIRHOLD",
                "STEPLEN",
                "STEPSPACE",
                "MIN_LIMIT",
                "MAX_LIMIT",
                "HOME",
                "HOME_OFFSET",
                "HOME_SEARCH_VEL",
                "HOME_LATCH_VEL",
                "HOME_SEQUENCE",
                "HOME_USE_INDEX",
            ),
        ),
    ):
        missing.extend(f"{axis}.{name}.{key}" for key in keys if key not in values)
    if missing:
        raise ValueError("缺少转轴参数：" + ", ".join(missing))
    for values in (limits, joint):
        for key in (
            "MAX_VELOCITY",
            "MAX_ACCELERATION",
            "STEPGEN_MAXVEL",
            "STEPGEN_MAXACCEL",
            "FERROR",
            "MIN_FERROR",
            "DIRSETUP",
            "DIRHOLD",
            "STEPLEN",
            "STEPSPACE",
        ):
            if key in values and (
                not math.isfinite(float(values[key])) or float(values[key]) <= 0
            ):
                raise ValueError(f"{axis}.{key} must be a positive calibrated value")
        for key in (
            "MIN_LIMIT",
            "MAX_LIMIT",
            "HOME",
            "HOME_OFFSET",
            "HOME_SEARCH_VEL",
            "HOME_LATCH_VEL",
        ):
            if key in values and not math.isfinite(float(values[key])):
                raise ValueError(f"{axis}.{key} must be finite")
        if float(values["MIN_LIMIT"]) >= float(values["MAX_LIMIT"]):
            raise ValueError(f"{axis} limits are reversed")
    if not math.isfinite(float(joint["STEP_SCALE"])) or float(joint["STEP_SCALE"]) == 0:
        raise ValueError(f"{axis}.STEP_SCALE must be calibrated in pulses per degree")
    if (
        abs(int(joint["HOME_SEQUENCE"])) > 100
        or joint["HOME_USE_INDEX"].upper() != "NO"
    ):
        raise ValueError(f"{axis} requires a configured non-index homing sequence")
    if float(joint["HOME_SEARCH_VEL"]) or float(joint["HOME_LATCH_VEL"]):
        raise ValueError(
            f"{axis} switch homing requires commissioned input wiring; not inferred"
        )
    if (
        not float(joint["MIN_LIMIT"])
        <= float(joint["HOME"])
        <= float(joint["MAX_LIMIT"])
    ):
        raise ValueError(f"{axis}.HOME lies outside the joint limits")
    return limits, joint


def generate(text, files, count):
    """Transform a three-axis base; the root adapter records it automatically."""
    if count not in AXES or axis_count(text) != 3:
        raise ValueError("Automatic generation needs the installed XYZ base")
    ini = parse_ini(text)
    kinematics = shlex.split(ini.get("KINS", "KINEMATICS"))
    if (
        not kinematics
        or kinematics[0] != "trivkins"
        or "coordinates=XYZ" not in kinematics
    ):
        raise ValueError("Automatic axis-count changes require XYZ trivkins")
    if count == 3:
        return text, {}
    if ini.get("TRAJ", "ANGULAR_UNITS", fallback="degree") not in ("degree", "deg"):
        raise ValueError("Rotary settings must use degrees")
    rotary = []
    wiring = ["\n# BEGIN: AutomaticallyGeneratedRotaryWiring\n"]
    for axis in AXES[count][3:]:
        limits, tuning = rotary_parameters(ini, axis)
        joint = AXES[count].index(axis)
        channel = 4 if axis == "A" else 3
        rotary.extend((("AXIS_" + axis, limits), (f"JOINT_{joint}", tuning)))
        stepgen = f"hm2_7i92.0.stepgen.{channel:02}"
        for pin, key in (
            ("position-scale", "STEP_SCALE"),
            ("maxvel", "STEPGEN_MAXVEL"),
            ("maxaccel", "STEPGEN_MAXACCEL"),
            ("dirsetup", "DIRSETUP"),
            ("dirhold", "DIRHOLD"),
            ("steplen", "STEPLEN"),
            ("stepspace", "STEPSPACE"),
        ):
            wiring.append(f"setp {stepgen}.{pin} [JOINT_{joint}]{key}\n")
        wiring.extend(
            (
                f"setp {stepgen}.step_type 0\n",
                f"setp {stepgen}.control-type 0\n",
                f"net axis-settings-{axis}-command joint.{joint}.motor-pos-cmd => {stepgen}.position-cmd\n",
                f"net axis-settings-{axis}-feedback {stepgen}.position-fb => joint.{joint}.motor-pos-fb\n",
                f"net axis-settings-{axis}-enable joint.{joint}.amp-enable-out => {stepgen}.enable\n",
            )
        )
    wiring.append("# END: AutomaticallyGeneratedRotaryWiring\n")
    drivers, generated, replacements = 0, {}, {}
    commands = [
        shlex.split(line, comments=True)
        for text in files.values()
        for line in text.splitlines()
    ]
    if ["loadrt", "[KINS]KINEMATICS"] not in commands or not any(
        words[:2] == ["loadrt", "[EMCMOT]EMCMOT"] and "num_joints=[KINS]JOINTS" in words
        for words in commands
    ):
        raise ValueError(
            "HAL must load the configured kinematics and joint count from INI"
        )
    for function in ("read", "write"):
        if ["addf", f"hm2_7i92.0.{function}", "servo-thread"] not in commands:
            raise ValueError(
                "Current HAL must schedule the configured Mesa read/write functions"
            )
    for name, original in files.items():
        output = []
        contains_driver = False
        for line in original.splitlines(keepends=True):
            words = shlex.split(line, comments=True)
            if words and words[0] == "source":
                raise ValueError(
                    "Automatic switching requires HAL without nested source commands"
                )
            if any(
                re.search(r"(?:joint\.[3-9]\.|stepgen\.0[34]\.|pid\.[ac]\.)", word)
                for word in words
            ):
                raise ValueError(
                    "Rotary hardware channels are already wired; no existing wiring was replaced"
                )
            if words[:2] == ["loadrt", "hm2_eth"]:
                drivers += 1
                contains_driver = True
                if len(re.findall(r"num_stepgens=\d+", line)) != 1:
                    raise ValueError("Mesa step-generator count is not explicit")
                line = re.sub(
                    r"num_stepgens=(\d+)",
                    lambda match: (
                        f"num_stepgens={max(int(match[1]), 5 if count == 5 else 4)}"
                    ),
                    line,
                )
            output.append(line)
        if contains_driver:
            output.extend(wiring)
            content = "".join(output)
            generated_name = (
                ".axis-settings-"
                + hashlib.sha256(content.encode()).hexdigest()
                + ".hal"
            )
            generated[generated_name] = content
            replacements[name] = generated_name
    if drivers != 1:
        raise ValueError(
            "Automatic switching requires exactly one Mesa Ethernet driver"
        )
    # The generated HAL replaces only the existing driver file reference. Other
    # HAL files, spindle, I/O, XYZ tuning and the launcher path remain unchanged.
    kinematics = [
        f"coordinates={AXES[count]}" if word == "coordinates=XYZ" else word
        for word in kinematics
    ]
    settings = {
        ("KINS", "JOINTS"): str(count),
        ("KINS", "KINEMATICS"): " ".join(kinematics),
        ("TRAJ", "COORDINATES"): AXES[count],
        ("DISPLAY", "GEOMETRY"): AXES[count],
        ("BETTERCNC_HOMING", "MOTOR_MAPPING_VERIFIED"): "NO",
        ("BETTERCNC_HOMING", "MOTOR_DIRECTIONS_VERIFIED"): "NO",
    }
    return patch_ini(text, settings, replacements, rotary), generated


# END: AutomaticAxisConfiguration
# --------#
