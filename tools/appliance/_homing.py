"""Selectively merge the verified Zhulong switch profile into a private copy."""

import hashlib
import json
import math
import os
import re
import shlex
import stat
import subprocess
from pathlib import Path

PROFILE = "zhulong-v2"
VENDOR_COMMIT = "eae9e6d6238fadab5b8b043f568952a0a90e6eed"
AXES = (("X", 0, 20, "neg", -1), ("Y", 1, 21, "pos", 1), ("Z", 2, 22, "neg", -1))
BEGIN = "# BEGIN BetterLinuxCNC Zhulong inputs v1\n"
END = "# END BetterLinuxCNC Zhulong inputs v1\n"
SCHEDULE = "# BetterLinuxCNC Zhulong input schedule v1\naddf debounce.0 servo-thread\n"
MOVED = "# BetterLinuxCNC merged limit: "
MANIFEST = "betterlinuxcnc-homing.json"
HEADERS = (
    "motion.h",
    "homing.h",
    "emcmotcfg.h",
    "emcpos.h",
    "posemath.h",
    "simple_tp.h",
)


def measured_travel(values):
    if values is None:
        return None
    if len(values) != 3 or any(
        isinstance(value, bool) or not math.isfinite(float(value)) or float(value) <= 15
        for value in values
    ):
        raise ValueError(
            "Provide three measured usable XYZ travel distances greater than 15 mm"
        )
    return tuple(float(value) for value in values)


def _installed_file(path, maximum):
    descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in Path(path).parts[1:-1]:
            child = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor
            )
            os.close(descriptor)
            descriptor = child
            info = os.fstat(descriptor)
            if info.st_uid != 0 or info.st_mode & 0o022:
                raise ValueError(
                    "Homing installation has an untrusted parent directory"
                )
        file = os.open(
            Path(path).name,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
            dir_fd=descriptor,
        )
        with os.fdopen(file, "rb") as stream:
            info = os.fstat(file)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
                or info.st_uid != 0
                or info.st_gid != 0
                or info.st_mode & 0o6022
            ):
                raise ValueError(
                    "Homing installation requires protected root-owned regular files"
                )
            content = stream.read(maximum + 1)
            if len(content) > maximum:
                raise ValueError(
                    "Installed homing metadata or module exceeds its size limit"
                )
            return content
    finally:
        os.close(descriptor)


def _package_version(package):
    result = subprocess.run(
        ["/usr/bin/dpkg-query", "-W", "-f=${Version}", package],
        check=True,
        capture_output=True,
        text=True,
        timeout=15,
        env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"},
    )
    return result.stdout.strip()


def validate_installed():
    """Validate fixed installed artifacts without loading a realtime module."""
    try:
        core = _package_version("linuxcnc-uspace")
        development = _package_version("linuxcnc-uspace-dev")
        app = _package_version("betterlinuxcnc-qt")
        metadata = json.loads(
            _installed_file(
                "/usr/share/betterlinuxcnc/homing/provenance.json", 256 * 1024
            )
        )
        module = _installed_file(
            "/usr/lib/linuxcnc/modules/zhulong_homing.so", 16 * 1024 * 1024
        )
        native = metadata["linuxcnc"]
        if (
            not re.fullmatch(r"(?:[0-9]+:)?2\.9\.10(?:[+-][A-Za-z0-9.+:~_-]+)?", core)
            or development != core
            or metadata["schema_version"] != 1
            or metadata["module"] != "zhulong_homing.so"
            or metadata["application_version"] != app
            or metadata["architecture"] != "amd64"
            or native["version"] != "2.9.10"
            or native["build_system"] != "uspace"
            or not re.fullmatch(r"[0-9a-f]{40}", native["source_commit"])
            or any(
                not re.fullmatch(r"[0-9a-f]{64}", native["headers"][name])
                for name in HEADERS
            )
            or metadata["vendor"]["commit"] != VENDOR_COMMIT
            or metadata["sha256"] != hashlib.sha256(module).hexdigest()
            or module[:6] != b"\x7fELF\x02\x01"
            or len(module) < 20
            or int.from_bytes(module[18:20], "little") != 62
        ):
            raise ValueError(
                "Installed LinuxCNC or HOMEMOD provenance does not match the reviewed profile"
            )
        for name in HEADERS:
            try:
                content = _installed_file("/usr/include/linuxcnc/" + name, 1024 * 1024)
            except FileNotFoundError as error:
                raise ValueError(
                    "Installed LinuxCNC development headers are required to verify the HOMEMOD ABI"
                ) from error
            if hashlib.sha256(content).hexdigest() != native["headers"][name]:
                raise ValueError(
                    "Installed LinuxCNC headers do not match the HOMEMOD ABI: " + name
                )
    except (KeyError, TypeError, UnicodeError, subprocess.SubprocessError) as error:
        raise ValueError(
            "Could not verify the installed LinuxCNC and homing module"
        ) from error


def _ini(text):
    values, section = {}, ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("#INCLUDE"):
            raise ValueError("Included INI files require a separate homing review")
        header = re.fullmatch(r"\[([^]]+)\]\s*(?:[#;].*)?", stripped)
        if header:
            section = header[1].upper()
        elif stripped and not stripped.startswith(("#", ";")):
            match = re.match(r"([A-Za-z_0-9]+)\s*=\s*(.*)", stripped)
            if match:
                values.setdefault((section, match[1].upper()), []).append(
                    match[2].strip()
                )
    return values


def _one(values, section, key, default=None):
    found = values.get((section, key), [])
    if len(found) > 1:
        raise ValueError(f"Duplicate homing-related INI value [{section}] {key}")
    return found[0] if found else default


def _commands(text):
    for index, line in enumerate(text.splitlines(keepends=True)):
        content = line.split("#", 1)[0]
        if any(char in content for char in ("\\", ";", "`", "$")):
            raise ValueError(
                "Dynamic or multiline HAL commands require a separate review"
            )
        words = shlex.split(line, comments=True)
        if words:
            yield index, words


def _block(enabled):
    lines = [
        BEGIN,
        "loadrt debounce cfg=3\n",
        "setp debounce.0.delay 5\n",
        f"setp motion.homing-inhibit {'false' if enabled else 'true'}\n",
    ]
    for axis, joint, gpio, side, _direction in AXES:
        name = axis.lower()
        lines += [
            f"net bettercnc-{name}-home-raw hm2_7i92.0.gpio.{gpio:03}.in => debounce.0.{joint}.in\n",
            f"net {name}-home-sw debounce.0.{joint}.out => joint.{joint}.{side}-lim-sw-in\n",
        ]
    return "".join([*lines, END])


def _restore_managed(files):
    block_count = schedule_count = moved_count = 0
    restored = {}
    for path, text in files.items():
        for enabled in (False, True):
            block = _block(enabled)
            block_count += text.count(block)
            text = text.replace(block, "")
        schedule_count += text.count(SCHEDULE)
        text = text.replace(SCHEDULE, "")
        if "BetterLinuxCNC Zhulong" in text:
            raise ValueError(
                "The managed homing block was changed; preserve it for review"
            )
        lines = []
        for line in text.splitlines(keepends=True):
            if line.startswith(MOVED):
                moved_count += 1
                line = line[len(MOVED) :]
            lines.append(line)
        restored[path] = "".join(lines)
    if (block_count, schedule_count, moved_count) not in ((0, 0, 0), (1, 1, 3)):
        raise ValueError("Incomplete or repeated managed homing migration")
    return restored


def _audit(files, ordered, startup):
    nets, locations, functions = {}, {}, {}
    targets = {
        f"{axis.lower()}-{kind}": pin
        for axis, joint, _gpio, side, _direction in AXES
        for kind, pin in (
            ("home-sw", f"joint.{joint}.home-sw-in"),
            (f"{side}-limit", f"joint.{joint}.{side}-lim-sw-in"),
        )
    }
    protected_pins = set(targets.values())
    allowed_modules = {
        "[KINS]KINEMATICS",
        "[EMCMOT]EMCMOT",
        "hostmot2",
        "hm2_eth",
        "pid",
    }
    order = 0
    for path in ordered:
        for line, words in _commands(files[path]):
            command = words[0]
            if command not in ("loadrt", "loadusr", "addf", "setp", "sets", "net"):
                raise ValueError(
                    "Unsupported HAL command in homing migration: " + command
                )
            if any(
                "home_sequence" in word.lower()
                or word.lower().startswith("ini.")
                or word == "motion.homing-inhibit"
                or word.startswith(("debounce.", "bettercnc-"))
                or re.search(r"\.gpio\.0*(20|21|22)\.", word)
                for word in words
            ):
                raise ValueError(
                    "Existing GPIO, debounce, homing inhibit or dynamic INI wiring conflicts"
                )
            if command == "loadrt" and (
                len(words) < 2 or words[1] not in allowed_modules
            ):
                raise ValueError(
                    "Unreviewed realtime module conflicts with selective homing migration"
                )
            if command == "loadusr" and words != [
                "loadusr",
                "-W",
                "hal_manualtoolchange",
            ]:
                raise ValueError(
                    "Unreviewed userspace HAL program could alter homing wiring"
                )
            if command in ("setp", "sets", "addf") and (
                len(words) < 3 or not re.fullmatch(r"[A-Za-z0-9_.:\-]+", words[1])
            ):
                raise ValueError(
                    "Dynamic HAL pin, parameter or function requires a separate review"
                )
            if command == "net":
                if len(words) < 3 or any(
                    not re.fullmatch(r"[A-Za-z0-9_.:\-]+|<?=>?|<=", word)
                    for word in words[1:]
                ):
                    raise ValueError(
                        "Dynamic or malformed HAL net requires a separate review"
                    )
                signal = words[1]
                pins = [word for word in words[2:] if word not in ("=>", "<=", "<=>")]
                if any(
                    pin in protected_pins and targets.get(signal) != pin for pin in pins
                ):
                    raise ValueError(
                        "Home or selected limit pin is already connected to another signal"
                    )
                nets.setdefault(signal, []).extend(pins)
                locations.setdefault(signal, []).append((path, line))
            elif any(word in targets or word in protected_pins for word in words):
                raise ValueError(
                    "Home or selected limit has another writer or assignment"
                )
            if command == "addf" and len(words) >= 2:
                functions.setdefault(words[1], []).append((path, line, order, words))
            order += 1
    for signal, pin in targets.items():
        if nets.get(signal) != [pin] or len(locations[signal]) != 1:
            raise ValueError(
                "Existing home/limit signal must contain exactly its unwired joint input"
            )
    schedule = []
    for function in ("hm2_7i92.0.read", "motion-command-handler", "motion-controller"):
        found = functions.get(function, [])
        if (
            len(found) != 1
            or found[0][3] != ["addf", function, "servo-thread"]
            or found[0][0] not in startup
        ):
            raise ValueError(
                "Expected one unpositioned servo-thread read and motion function"
            )
        schedule.append(found[0])
    if not schedule[0][2] < schedule[1][2] < schedule[2][2]:
        raise ValueError(
            "HostMot2 read must precede motion command handling and control"
        )
    return locations, schedule[0][:2]


def _patch_ini(text, changes):
    values = _ini(text)
    for section, key in changes:
        _one(values, section, key)
    remaining = dict(changes)
    output, section = [], ""

    def append_missing():
        if output and not output[-1].endswith("\n"):
            output.append("\n")
        for field in [field for field in remaining if field[0] == section]:
            output.append(f"{field[1]} = {remaining.pop(field)}\n")

    for line in text.splitlines(keepends=True):
        header = re.match(r"\s*\[([^]]+)\]", line)
        if header:
            append_missing()
            section = header[1].upper()
        match = re.match(r"\s*([A-Za-z_0-9]+)\s*=", line)
        field = (section, match[1].upper()) if match else None
        if field in remaining:
            output.append(f"{field[1]} = {remaining.pop(field)}\n")
        else:
            output.append(line)
    append_missing()
    for name in dict.fromkeys(field[0] for field in remaining):
        output.append(f"\n[{name}]\n")
        section = name
        append_missing()
    return "".join(output)


def _abc_commands():
    """Exact token signatures of the inactive PNCconf wiring read on the machine."""
    commands = set()
    for axis, joint in (("a", 3), ("b", 4), ("c", 5)):
        pid = "pid." + axis
        step = f"hm2_7i92.0.stepgen.{joint:02}"
        native = f"joint.{joint}"
        for parameter, field in (
            ("Pgain", "P"),
            ("Igain", "I"),
            ("Dgain", "D"),
            ("bias", "BIAS"),
            ("FF0", "FF0"),
            ("FF1", "FF1"),
            ("FF2", "FF2"),
            ("deadband", "DEADBAND"),
            ("maxoutput", "MAX_OUTPUT"),
        ):
            commands.add(("setp", f"{pid}.{parameter}", f"[JOINT_{joint}]{field}"))
        commands.add(("setp", pid + ".error-previous-target", "true"))
        commands.add(("setp", pid + ".maxerror", "0.012700"))
        commands.add(("addf", pid + ".do-pid-calcs", "servo-thread"))
        # The reviewed legacy C step generator references JOINT_4 parameters.
        # It is removed as-is; accepting a different relationship needs review.
        step_joint = 4 if joint == 5 else joint
        for parameter, field in (
            ("dirsetup", "DIRSETUP"),
            ("dirhold", "DIRHOLD"),
            ("steplen", "STEPLEN"),
            ("stepspace", "STEPSPACE"),
            ("position-scale", "STEP_SCALE"),
            ("maxaccel", "STEPGEN_MAXACCEL"),
            ("maxvel", "STEPGEN_MAXVEL"),
        ):
            commands.add(
                ("setp", f"{step}.{parameter}", f"[JOINT_{step_joint}]{field}")
            )
        commands.add(("setp", step + ".step_type", "0"))
        commands.add(("setp", step + ".control-type", "1"))
        for signal, direction, pin in (
            ("index-enable", "=>", pid + ".index-enable"),
            ("enable", "=>", pid + ".enable"),
            ("pos-cmd", "=>", pid + ".command"),
            ("pos-fb", "=>", pid + ".feedback"),
            ("output", "<=", pid + ".output"),
            ("pos-cmd", "<=", native + ".motor-pos-cmd"),
            ("vel-cmd", "<=", native + ".vel-cmd"),
            ("output", "=>", step + ".velocity-cmd"),
            ("pos-fb", "<=", step + ".position-fb"),
            ("pos-fb", "=>", native + ".motor-pos-fb"),
            ("enable", "<=", native + ".amp-enable-out"),
            ("enable", "=>", step + ".enable"),
            ("home-sw", "=>", native + ".home-sw-in"),
            ("neg-limit", "=>", native + ".neg-lim-sw-in"),
            ("pos-limit", "=>", native + ".pos-lim-sw-in"),
        ):
            commands.add(("net", f"{axis}-{signal}", direction, pin))
    commands.update(
        {
            ("net", "axis-select-a", "halui.axis.a.select"),
            ("net", "jog-a-pos", "halui.axis.a.plus"),
            ("net", "jog-a-neg", "halui.axis.a.minus"),
            ("net", "jog-a-analog", "halui.axis.a.analog"),
            ("net", "a-is-homed", "halui.joint.3.is-homed"),
        }
    )
    return commands


def _xyz_only(text, files):
    values = _ini(text)
    axis_fields = {"MAX_VELOCITY", "MAX_ACCELERATION", "MIN_LIMIT", "MAX_LIMIT"}
    joint_fields = axis_fields | {
        "TYPE",
        "HOME",
        "FERROR",
        "MIN_FERROR",
        "STEPGEN_MAXVEL",
        "STEPGEN_MAXACCEL",
        "P",
        "I",
        "D",
        "FF0",
        "FF1",
        "FF2",
        "BIAS",
        "DEADBAND",
        "MAX_OUTPUT",
        "DIRSETUP",
        "DIRHOLD",
        "STEPLEN",
        "STEPSPACE",
        "STEP_SCALE",
        "HOME_OFFSET",
        "HOME_SEQUENCE",
    }
    removed = {"AXIS_A", "AXIS_B", "AXIS_C", "JOINT_3", "JOINT_4", "JOINT_5"}
    for section in removed:
        expected = joint_fields if section.startswith("JOINT_") else axis_fields
        actual = {key for name, key in values if name == section}
        if actual != expected:
            raise ValueError(
                "Unused ABC sections differ from the reviewed PNCconf profile"
            )
        for key in expected:
            value = _one(values, section, key)
            if key == "TYPE":
                if value != "ANGULAR":
                    raise ValueError(
                        "Unused ABC joint type is not the reviewed angular configuration"
                    )
            elif not math.isfinite(float(value)):
                raise ValueError(
                    "Unused ABC configuration contains invalid numeric parameters"
                )
    for section, key in (("TRAJ", "COORDINATES"), ("DISPLAY", "GEOMETRY")):
        if _one(values, section, key) != "XYZABC":
            raise ValueError(
                "XYZ-only conversion requires the reviewed XYZABC geometry"
            )
    output, section = [], ""
    for line in text.splitlines(keepends=True):
        header = re.match(r"\s*\[([^]]+)\]", line)
        if header:
            section = header[1].upper()
        if section not in removed:
            if re.search(r"\[(?:JOINT_[345]|AXIS_[ABC])\]", line.split("#", 1)[0]):
                raise ValueError(
                    "A retained INI parameter references an unused ABC section"
                )
            output.append(line)
    expected, found, rewritten = _abc_commands(), set(), {}
    pid_command = ("loadrt", "pid", "names=pid.x,pid.y,pid.z,pid.a,pid.b,pid.c,pid.s")
    pid_count = 0
    references = re.compile(
        r"(?:pid\.[abc]\.|(?:^|\.)joint\.[345]\.|stepgen\.0[345]\.|"
        r"axis\.[abc]\.|\[(?:JOINT_[345]|AXIS_[ABC])\]|^[abc]-|^jog-[abc]-|^axis-select-[abc]$)"
    )
    for path, content in files.items():
        changes = {}
        for line, words in _commands(content):
            signature = tuple(words)
            if signature == pid_command:
                pid_count += 1
                changes[line] = "loadrt pid names=pid.x,pid.y,pid.z,pid.s\n"
            elif signature in expected:
                if signature in found:
                    raise ValueError("Repeated ABC command cannot be safely removed")
                found.add(signature)
                changes[line] = ""
            elif any(references.search(word) for word in words):
                raise ValueError(
                    "Unknown ABC wiring must be reviewed before three-axis conversion"
                )
        rewritten[path] = "".join(
            changes.get(index, line)
            for index, line in enumerate(content.splitlines(keepends=True))
        )
    if found != expected or pid_count != 1:
        raise ValueError(
            "Three-axis conversion requires the complete reviewed unused ABC wiring"
        )
    return "".join(output), rewritten


def prepare(ini, travel=None, installation_verified=False, xyz_only=False):
    """Modify only the caller's private staging tree; never import vendor reference files."""
    travel = measured_travel(travel)
    if xyz_only and travel is None:
        raise ValueError("XYZ-only conversion requires measured homing travel")
    ini = Path(ini)
    text = ini.read_text()
    values = _ini(text)
    if (
        _one(values, "KINS", "JOINTS") != "6"
        or _one(values, "KINS", "KINEMATICS") != "trivkins coordinates=XYZABC"
        or _one(values, "HMOT", "CARD0") != "hm2_7i92.0"
        or _one(values, "EMCMOT", "EMCMOT") != "motmod"
        or _one(values, "TRAJ", "LINEAR_UNITS") != "mm"
        or _one(values, "TRAJ", "NO_FORCE_HOMING", "0") != "0"
    ):
        raise ValueError(
            "Selective homing migration requires the reviewed six-joint Zhulong profile"
        )
    for section in ("AXIS_X", "AXIS_Y", "AXIS_Z", *(f"JOINT_{i}" for i in range(6))):
        if not any(field[0] == section for field in values):
            raise ValueError(
                "The existing machine profile lacks required axis or joint parameters"
            )
    for joint in range(6):
        sequence = _one(values, f"JOINT_{joint}", "HOME_SEQUENCE")
        if sequence is not None and not re.fullmatch(r"[+-]?[0-9]+", sequence):
            raise ValueError("HOME_SEQUENCE must be one explicit integer per joint")
    existing_module = _one(values, "EMCMOT", "HOMEMOD", "homemod")
    if existing_module not in ("homemod", "zhulong_homing") or (
        travel is None and existing_module != "homemod"
    ):
        raise ValueError("Existing HOMEMOD cannot be silently replaced or disabled")
    ordered, files, startup = [], {}, set()
    for (section, key), entries in values.items():
        if section != "HAL":
            continue
        if key == "HALUI" and entries == ["halui"]:
            continue
        if key not in ("HALFILE", "POSTGUI_HALFILE", "SHUTDOWN"):
            raise ValueError("Unreviewed HAL configuration directive: " + key)
        for value in entries:
            parts = shlex.split(value, comments=True)
            relative = Path(parts[0]) if len(parts) == 1 else None
            if (
                relative is None
                or relative.is_absolute()
                or ".." in relative.parts
                or relative.suffix != ".hal"
                or any(char in value for char in "$~\\")
            ):
                raise ValueError(
                    "HAL files must be explicit relative .hal files inside the machine profile"
                )
            path = ini.parent / relative
            if path in files or path.is_symlink() or not path.is_file():
                raise ValueError(
                    "Duplicate, missing or linked HAL file in the machine profile"
                )
            content = path.read_text()
            if len(content.encode()) > 1024 * 1024:
                raise ValueError("HAL file exceeds the reviewed profile size limit")
            files[path] = content
            ordered.append(path)
            if key == "HALFILE":
                startup.add(path)
    if not ordered:
        raise ValueError("The machine profile does not declare any HAL files")
    files = _restore_managed(files)
    if xyz_only:
        text, files = _xyz_only(text, files)
    # LinuxCNC loads every HALFILE before the post-GUI and shutdown scripts.
    ordered = [path for path in ordered if path in startup] + [
        path for path in ordered if path not in startup
    ]
    locations, (schedule_path, schedule_line) = _audit(files, ordered, startup)
    moves = {
        locations[f"{axis.lower()}-{side}-limit"][0] for axis, _, _, side, _ in AXES
    }
    for path, content in files.items():
        output = []
        for line, original in enumerate(content.splitlines(keepends=True)):
            if (path, line) in moves:
                output.append(MOVED + original)
            else:
                if path == schedule_path and line == schedule_line:
                    output.append(_block(travel is not None))
                output.append(original)
                if path == schedule_path and line == schedule_line:
                    if not original.endswith("\n"):
                        output.append("\n")
                    output.append(SCHEDULE)
        files[path] = "".join(output)
    changes = {
        ("BETTERCNC_HOMING", "PROFILE"): PROFILE,
        ("BETTERCNC_HOMING", "SWITCH_INPUTS_VERIFIED"): "YES",
        # Preparing software and switch inputs is not physical motor commissioning.
        ("BETTERCNC_HOMING", "MOTOR_MAPPING_VERIFIED"): "NO",
        ("BETTERCNC_HOMING", "MOTOR_DIRECTIONS_VERIFIED"): "NO",
    }
    if xyz_only:
        changes.update(
            {
                ("KINS", "JOINTS"): "3",
                ("KINS", "KINEMATICS"): "trivkins coordinates=XYZ",
                ("TRAJ", "COORDINATES"): "XYZ",
                ("DISPLAY", "GEOMETRY"): "XYZ",
            }
        )
    if travel is not None:
        changes[("EMCMOT", "HOMEMOD")] = "zhulong_homing"
        for (axis, joint, _gpio, _side, direction), length in zip(
            AXES, travel, strict=True
        ):
            changes[("BETTERCNC_HOMING", f"TRAVEL_{axis}_MM")] = f"{length:.17g}"
            for section in ("AXIS_" + axis, f"JOINT_{joint}"):
                changes[(section, "MIN_LIMIT")] = (
                    f"{-length + 10 if direction > 0 else 0:.17g}"
                )
                changes[(section, "MAX_LIMIT")] = (
                    f"{0 if direction > 0 else length - 10:.17g}"
                )
            for key, value in {
                "HOME": "0",
                "HOME_OFFSET": str(direction * 5),
                "HOME_SEARCH_VEL": str(direction * 2),
                "HOME_LATCH_VEL": str(direction * 0.5),
                "HOME_FINAL_VEL": "2",
                "HOME_SEQUENCE": str(joint + 1),
                "HOME_IGNORE_LIMITS": "YES",
                "HOME_USE_INDEX": "NO",
            }.items():
                changes[(f"JOINT_{joint}", key)] = value
        for joint in () if xyz_only else range(3, 6):
            changes[(f"JOINT_{joint}", "HOME_SEQUENCE")] = "101"
    rewritten = _patch_ini(text, changes)
    for path, content in files.items():
        path.write_text(content)
    ini.write_text(rewritten)
    (ini.parent / MANIFEST).write_text(
        json.dumps(
            {
                "format": "betterlinuxcnc-zhulong-homing-v1",
                "sourceCommit": VENDOR_COMMIT,
                "mode": "homing" if travel else "inputs-only",
                "activeAxes": "XYZ" if xyz_only else "XYZABC",
                "switchInputsVerified": True,
                "motorMappingVerified": False,
                "motorDirectionsVerified": False,
                "travelMm": dict(zip("XYZ", travel, strict=True)) if travel else None,
                "installedModuleVerified": installation_verified if travel else False,
                "installationCheck": (
                    "verified" if installation_verified else "required-at-prepare"
                )
                if travel
                else "not-required",
                "halFiles": {
                    str(path.relative_to(ini.parent)): hashlib.sha256(
                        content.encode()
                    ).hexdigest()
                    for path, content in files.items()
                },
            },
            indent=2,
        )
        + "\n"
    )
