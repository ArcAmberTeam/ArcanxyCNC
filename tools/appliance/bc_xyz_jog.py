"""Prepare bounded XYZ jogging from the captured BC input-only installation."""

import hashlib
import io
from pathlib import Path

from axis_configuration import parse_ini
from axis_profiles import PROFILE_HEADER

HAL = "bc-xyz-jog.hal"
ORIGINAL = {
    "axis-3.ini": "0e250427b87ab5863360d56cd85f124f36103f1cd93e7dd7325907f3f1445b43",
    "axis-5.ini": "29b56912ef71023d2ca5e66b9b9b779e73e1a74939ca4c541c589c1923d84d1f",
    "bc-inputs.hal": "ce1e5756a3362f4732b88e20261929253691bb19298093f3fafa1fc0d46c905f",
    "bc-xyz-limits.hal": "4b0f519b5dfb7c9e3408ec6b2164fa98e4ceee89ca22ca693fcfb2e2db067470",
}
PREVIOUS_JOG = {
    "axis-3.ini": "282a07dafa472ac87f9237b22b3994c3184fb77fd8e79a3c64485771d43171e1",
    HAL: "9d35e7ba7b7731e76b02eb07fec797a04d54bfc94e17b44d2dd75f21f3d66b99",
}
CORRECTED_XY_HAL = "48283146c5c3cdb3bd7c92412ead8401fe452a52ef04aa3de5c027161becaad5"
HOMING_REVISION = "bc-xyz-homing-20261124"


# --------#
# BEGIN: BcXyzJogProfile
def prepare(files):
    """Return a separate preset, without selecting it or accepting motor direction."""
    allowed = {*ORIGINAL, "axis-4.ini", "tool.tbl", "linuxcnc.var", HAL}
    if set(files) - allowed:
        raise ValueError("Machine file set differs from the captured BC installation")
    if any(
        hashlib.sha256(files.get(name, b"")).hexdigest() != digest
        for name, digest in ORIGINAL.items()
        if name != "axis-3.ini"
    ):
        raise ValueError(
            "BC input configuration changed; no machine files were replaced"
        )
    ini = parse_ini(files["axis-5.ini"].decode())
    for section in ("AXIS_B", "AXIS_C", "JOINT_3", "JOINT_4"):
        ini.remove_section(section)
    settings = {
        "EMC": {"MACHINE": "Zhulong V2 XYZ - direction commissioning"},
        "KINS": {"JOINTS": "3", "KINEMATICS": "trivkins coordinates=XYZ"},
        "TRAJ": {
            "COORDINATES": "XYZ",
            "MAX_LINEAR_VELOCITY": "15",
            "DEFAULT_LINEAR_VELOCITY": "15",
            "MAX_LINEAR_ACCELERATION": "50",
            "NO_FORCE_HOMING": "0",
        },
        "DISPLAY": {
            "GEOMETRY": "XYZ",
            "MAX_LINEAR_VELOCITY": "15",
            "DEFAULT_LINEAR_VELOCITY": "15",
            "MIN_LINEAR_VELOCITY": "0.01",
            "MAX_FEED_OVERRIDE": "1",
        },
        "SPINDLE_0": {"MAX_FORWARD_VELOCITY": "0"},
        "BETTERCNC_HOMING": {
            "PROFILE": "zhulong-v2",
            "CONFIGURATION_REVISION": "bc-xyz-jog-20261124",
            "SWITCH_INPUTS_VERIFIED": "YES",
            "MOTOR_MAPPING_VERIFIED": "NO",
            "MOTOR_DIRECTIONS_VERIFIED": "NO",
        },
    }
    for joint, axis in enumerate("XYZ"):
        settings[f"AXIS_{axis}"] = {"MAX_VELOCITY": "15", "MAX_ACCELERATION": "50"}
        settings[f"JOINT_{joint}"] = {
            "MAX_VELOCITY": "15",
            "MAX_ACCELERATION": "50",
            # Confirmed 1600 pulses per motor turn and 5 mm screw lead.
            # The operator observed Z+ approaching the negative home switch.
            "STEP_SCALE": "-320" if axis == "Z" else "320",
            "STEPGEN_MAXVEL": "18.75",
            "STEPGEN_MAXACCEL": "62.5",
            "DIRSETUP": "10000",
            "DIRHOLD": "10000",
            "STEPLEN": "5000",
            "STEPSPACE": "5000",
            "FERROR": "0.5",
            "MIN_FERROR": "0.05",
            # Exclude every joint from HOME ALL; HAL also inhibits homing.
            "HOME_SEQUENCE": "1000",
            "HOME_USE_INDEX": "NO",
        }
    for section, values in settings.items():
        for key, value in values.items():
            ini.set(section, key, value)
    ini.remove_section("HAL")
    ini["HAL"] = {"HALFILE": HAL}
    output = io.StringIO()
    output.write(PROFILE_HEADER + "axis-5.ini\n")
    output.write(
        "; XYZ direction commissioning only; homing and machining remain blocked.\n"
    )
    ini.write(output)
    prepared = dict(files)
    prepared["axis-3.ini"] = output.getvalue().encode()
    prepared[HAL] = (Path(__file__).parent / "templates" / HAL).read_bytes()
    return prepared


def validate_destination(files, prepared):
    if (
        files.get("axis-3.ini") == prepared["axis-3.ini"]
        and files.get(HAL) == prepared[HAL]
    ):
        return "already-current"
    if (
        hashlib.sha256(files.get("axis-3.ini", b"")).hexdigest()
        == PREVIOUS_JOG["axis-3.ini"]
        and hashlib.sha256(files.get(HAL, b"")).hexdigest()
        in (PREVIOUS_JOG[HAL], CORRECTED_XY_HAL)
    ):
        return "correct-jog"
    if (
        hashlib.sha256(files.get("axis-3.ini", b"")).hexdigest()
        != ORIGINAL["axis-3.ini"]
        or HAL in files
    ):
        raise ValueError("Existing three-axis tuning or jogging HAL is preserved")
    return "prepare"


def commission_homing(files):
    """Accept onsite motor/envelope confirmation only through the explicit CLI."""
    jogging = prepare(files)
    ini = parse_ini(jogging["axis-3.ini"].decode())
    ini["BETTERCNC_HOMING"].update(
        {
            "CONFIGURATION_REVISION": HOMING_REVISION,
            "MOTOR_MAPPING_VERIFIED": "YES",
            "MOTOR_DIRECTIONS_VERIFIED": "YES",
            "TRAVEL_SOURCE": "OPERATOR_CONFIRMED_ENVELOPE",
            "TRAVEL_X_MM": "600",
            "TRAVEL_Y_MM": "400",
            "TRAVEL_Z_MM": "90",
        }
    )
    for joint, axis, maximum, sequence in (
        (0, "X", 580, 2),
        (1, "Y", 380, 3),
        (2, "Z", 50, 1),
    ):
        for section in (f"AXIS_{axis}", f"JOINT_{joint}"):
            # HOME lies inside the limit despite floating-point readback noise.
            ini[section].update({"MIN_LIMIT": "-0.1", "MAX_LIMIT": str(maximum)})
        ini[f"JOINT_{joint}"].update(
            {
                "HOME": "0",
                "HOME_OFFSET": "-5",
                "HOME_SEARCH_VEL": "-2",
                "HOME_LATCH_VEL": "-0.5",
                "HOME_BACKOFF_VEL": "1",
                "HOME_FINAL_VEL": "2",
                "HOME_SEQUENCE": str(sequence),
                "HOME_IGNORE_LIMITS": "YES",
            }
        )
    output = io.StringIO()
    output.write(PROFILE_HEADER + "axis-5.ini\n")
    output.write("; Explicitly commissioned XYZ negative-switch homing.\n")
    ini.write(output)
    updated = dict(jogging)
    updated["axis-3.ini"] = output.getvalue().encode()
    updated[HAL] = jogging[HAL].replace(
        b"setp motion.homing-inhibit true\n", b"setp motion.homing-inhibit false\n"
    ) + "".join(
        f"setp joint.{joint}.home-backoff-vel [JOINT_{joint}]HOME_BACKOFF_VEL\n"
        for joint in range(3)
    ).encode()
    names = ("axis-3.ini", HAL)
    if all(files.get(name) == updated[name] for name in names):
        return updated, "already-current"
    if not all(files.get(name) == jogging[name] for name in names):
        raise ValueError("First prepare and verify the corrected XYZ jogging profile")
    return updated, "commission-homing"


# END: BcXyzJogProfile
# --------#
