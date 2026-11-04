"""Apply the operator-confirmed XYZ correction to the exact installed v1/v4 profiles.

Only the package provision entry point calls this migration. No machine commands
are issued; the updater must have stopped and masked the control stack first.
"""

import contextlib
import ctypes
import fcntl
import hashlib
import json
import os
import pwd
import re
import stat
import uuid

import _homing
from axis_profiles import migration_base

V4_REVISION = "zhulong-xyz-20261026"
REVISION = "zhulong-xyz-v5-20261026"
INI = "烛龙V2.ini"
HAL = "烛龙V2.hal"
MANIFEST = "betterlinuxcnc-homing.json"
ORIGINAL = {
    INI: "74d9033720ee87a53582ff254b24d4f0fcaeae09f65ae24d3713326096cec08c",
    HAL: "4a857a23fbcedf5142b0917949575f41cfb2e88bc7e566ec6516a9c1776af040",
    "custom.hal": "34581418aef7f3453986cdbcd760df6083a94fe03edec4f2bc7d85b951dd5eb8",
    "custom_postgui.hal": "ee3543526da49290358cc34bca83db25e8442291961f1a9a981152cb22b9c6f4",
    "qt_postgui.hal": "9731a1fefc86d6c3494fb24fa62fdf3eeab9905aa15d1048ad8b3b8df9a36236",
    "shutdown.hal": "aaffa097850005d60367e58949926f0c54806607264d759bd828801b9f1a999f",
    MANIFEST: "678058cb2ea8c6aece78a04b9b5e367c66a5e1635469f7f513f79d2825fa4019",
}
ORIGINAL_V4 = {
    **ORIGINAL,
    INI: "35a53a2172ae98a9d8c310513858f64565b811918425b5a1e892aec2b97f9c6b",
    HAL: "ef89bfae3d683beb6a9cad4d26194c31262892959445960c6e76c14e76fb0344",
    MANIFEST: "c31ae5ca17b9d5f57bab318ebad775bd8a480e362bca566bdf0e05e2baa664fb",
}
DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def _digest(content):
    return hashlib.sha256(content).hexdigest()


def _trusted(info):
    if info.st_uid != 0 or info.st_gid != 0 or info.st_mode & 0o6022:
        raise ValueError("Axis migration requires protected root-owned configuration")


@contextlib.contextmanager
def _directory(parent, name):
    descriptor = os.open(name, DIRECTORY, dir_fd=parent)
    try:
        _trusted(os.fstat(descriptor))
        yield descriptor
    finally:
        os.close(descriptor)


def _read(parent, name):
    descriptor = os.open(
        name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent
    )
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        _trusted(info)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("Axis migration refuses links and non-regular files")
        content = stream.read(1024 * 1024 + 1)
        if len(content) > 1024 * 1024:
            raise ValueError("Machine configuration file exceeds migration size limit")
        return content


def _stopped(root):
    uid = pwd.getpwnam("linuxcnc").pw_uid
    for name in ("tmp/linuxcnc.lock", f"run/user/{uid}/betterlinuxcnc/control.sock"):
        try:
            os.stat(name, dir_fd=root, follow_symlinks=False)
        except FileNotFoundError:
            continue
        raise ValueError(
            "Stop the CNC launcher through the updater before axis migration"
        )


def _correct(files):
    """Measured outputs: 00=Y/right, 01=X/front, 02=Z/down for positive scale."""
    result = dict(files)
    text = files[HAL].decode()
    text = re.sub(
        r"hm2_7i92\.0\.stepgen\.(00|01)(?=\.)",
        lambda match: "hm2_7i92.0.stepgen." + {"00": "01", "01": "00"}[match[1]],
        text,
    )
    text = (
        text.replace(
            "net y-home-sw debounce.0.1.out => joint.1.pos-lim-sw-in",
            "net y-home-sw debounce.0.1.out => joint.1.neg-lim-sw-in",
        )
        .replace(
            "net y-neg-limit     =>  joint.1.neg-lim-sw-in\n",
            "# BetterLinuxCNC merged limit: net y-neg-limit     =>  joint.1.neg-lim-sw-in\n",
        )
        .replace(
            "# BetterLinuxCNC merged limit: net y-pos-limit     =>  joint.1.pos-lim-sw-in",
            "net y-pos-limit     =>  joint.1.pos-lim-sw-in",
        )
    )
    result[HAL] = text.encode()
    changes = {
        ("JOINT_2", "STEP_SCALE"): "-200.0",
        ("BETTERCNC_HOMING", "CONFIGURATION_REVISION"): V4_REVISION,
        ("BETTERCNC_HOMING", "MOTOR_MAPPING_VERIFIED"): "YES",
        ("BETTERCNC_HOMING", "MOTOR_DIRECTIONS_VERIFIED"): "YES",
    }
    # X+ is forward, Y+ right, Z+ up. All three home toward negative coordinates.
    for joint, axis, travel in ((0, "X", 420), (1, "Y", 275), (2, "Z", 90)):
        for section in (f"JOINT_{joint}", "AXIS_" + axis):
            changes[(section, "MIN_LIMIT")] = "0"
            changes[(section, "MAX_LIMIT")] = str(travel - 10)
        for key, value in {
            "HOME": "0",
            "HOME_OFFSET": "-5",
            "HOME_SEARCH_VEL": "-2",
            "HOME_LATCH_VEL": "-0.5",
            "HOME_FINAL_VEL": "2",
            "HOME_SEQUENCE": str(joint + 1),
            "HOME_IGNORE_LIMITS": "YES",
            "HOME_USE_INDEX": "NO",
        }.items():
            changes[(f"JOINT_{joint}", key)] = value
    result[INI] = _homing._patch_ini(files[INI].decode(), changes).encode()
    manifest = json.loads(files[MANIFEST])
    manifest.update(
        configurationRevision=V4_REVISION,
        motorMappingVerified=True,
        motorDirectionsVerified=True,
        motorObservation="Operator confirmed outputs and positive directions on 2026-10-26",
        motionAcceptance="pending-after-update",
        stepgenByAxis={"X": 1, "Y": 0, "Z": 2},
        positiveDirectionByAxis={"X": "front", "Y": "right", "Z": "up"},
        halFiles={
            name: _digest(data)
            for name, data in result.items()
            if name.endswith(".hal")
        },
        configurationFiles={
            name: _digest(data) for name, data in result.items() if name != MANIFEST
        },
    )
    result[MANIFEST] = (
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    ).encode()
    return result


def _fast_profile(files):
    """Keep the origin and motor mapping; place HOME inside the soft envelope."""
    result = dict(files)
    changes = {
        ("BETTERCNC_HOMING", "CONFIGURATION_REVISION"): REVISION,
        ("BETTERCNC_HOMING", "PARALLEL_TEST_CONDITION"): "EMPTY_TABLE_NO_TOOL",
        ("BETTERCNC_HOMING", "SWITCH_OVERRUN_MM"): "1",
    }
    for joint, axis in enumerate("XYZ"):
        # HOME stays at zero, 5 mm clear of the switch. The -0.1 mm soft
        # boundary remains 4.9 mm clear, but tolerates feedback quantization.
        for section in (f"JOINT_{joint}", "AXIS_" + axis):
            changes[(section, "MIN_LIMIT")] = "-0.1"
        for key, value in {
            "HOME_SEARCH_VEL": "-5" if axis == "Z" else "-15",
            "HOME_BACKOFF_VEL": "2",
            "HOME_LATCH_VEL": "-1",
            "HOME_FINAL_VEL": "2" if axis == "Z" else "5",
            "HOME_SEQUENCE": "1",
        }.items():
            changes[(f"JOINT_{joint}", key)] = value
    result[INI] = _homing._patch_ini(files[INI].decode(), changes).encode()
    result[HAL] = (
        files[HAL]
        + (
            "\n# Fixed v5 HOMEMOD: independent slow retreat, sampled at HOME_START.\n"
            + "".join(
                f"setp joint.{joint}.home-backoff-vel [JOINT_{joint}]HOME_BACKOFF_VEL\n"
                for joint in range(3)
            )
        ).encode()
    )
    manifest = json.loads(files[MANIFEST])
    manifest.update(
        sourceCommit=_homing.VENDOR_COMMIT,
        configurationRevision=REVISION,
        motionAcceptance="pending-empty-table-parallel-test",
        homingSchedule="parallel-xyz",
        switchOverrunMinimumMm=1,
        parallelTestCondition="Operator agreed to remove tools and clear the full travel envelope",
        softLimitMarginMm=0.1,
        halFiles={
            name: _digest(data)
            for name, data in result.items()
            if name.endswith(".hal")
        },
        configurationFiles={
            name: _digest(data) for name, data in result.items() if name != MANIFEST
        },
    )
    result[MANIFEST] = (
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    ).encode()
    return result


def _exchange(parent, first, second):
    # Linux renameat2 provides a single atomic commit for the entire profile.
    rename = ctypes.CDLL(None, use_errno=True).renameat2
    rename.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    rename.restype = ctypes.c_int
    if rename(parent, os.fsencode(first), parent, os.fsencode(second), 2) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))


def _upgrade(root, config):
    with contextlib.ExitStack() as stack:
        try:
            machine = stack.enter_context(_directory(config, "machine"))
        except FileNotFoundError:
            return "not-applicable"
        try:
            content = _read(machine, INI)
        except FileNotFoundError:
            return "not-applicable"
        if b"PROFILE = zhulong-v2" not in content:
            return "not-applicable"
        files = {name: _read(machine, name) for name in os.listdir(machine)}
        manifest = json.loads(files[MANIFEST])
        if manifest.get("configurationRevision") == REVISION:
            files = migration_base(files, INI)
        if set(files) != set(ORIGINAL):
            raise ValueError(
                "Machine file set differs from the reviewed v1/v4 profiles"
            )
    manifest = json.loads(files[MANIFEST])
    if manifest.get("configurationRevision") == REVISION:
        expected = manifest.get("configurationFiles")
        actual = {
            name: _digest(data) for name, data in files.items() if name != MANIFEST
        }
        if actual != expected:
            raise ValueError(
                "Migrated machine configuration changed; review before updating"
            )
        return "already-current"
    hashes = {name: _digest(data) for name, data in files.items()}
    if hashes not in (ORIGINAL, ORIGINAL_V4):
        raise ValueError(
            "Machine configuration differs from the commissioned v1/v4 input"
        )
    launcher = json.loads(_read(config, "launcher.json"))
    if launcher.get("ini") != "/etc/betterlinuxcnc/machine/" + INI:
        raise ValueError("Launcher does not select the reviewed machine configuration")
    _stopped(root)
    _homing.validate_installed()
    provenance = json.loads(
        _homing._installed_file(
            "/usr/share/betterlinuxcnc/homing/provenance.json", 256 * 1024
        )
    )
    if provenance.get("commissioning_profile") != REVISION:
        raise ValueError(
            "Install the corrected signed-profile HOMEMOD before migrating axes"
        )
    updated = _fast_profile(_correct(files) if hashes == ORIGINAL else files)
    stage = ".axis-upgrade-" + uuid.uuid4().hex
    os.mkdir(stage, 0o700, dir_fd=config)
    try:
        with _directory(config, stage) as staged:
            for name, data in updated.items():
                descriptor = os.open(
                    name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o644,
                    dir_fd=staged,
                )
                with os.fdopen(descriptor, "wb") as stream:
                    os.fchmod(stream.fileno(), 0o644)
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
            os.fchmod(staged, 0o755)
            os.fsync(staged)
        _stopped(root)
        with _directory(config, "machine") as machine:
            if {name: _read(machine, name) for name in ORIGINAL} != files:
                raise ValueError("Machine configuration changed during migration")
        _exchange(config, stage, "machine")
        os.fsync(config)
    finally:
        # Before commit this is the new copy; after commit it is the old copy.
        with _directory(config, stage) as staged:
            for name in os.listdir(staged):
                os.unlink(name, dir_fd=staged)
        os.rmdir(stage, dir_fd=config)
    return "migrated"


def upgrade():
    """Fixed root-only migration, also reached by the unchanged package postinst."""
    with _directory(None, "/") as root, contextlib.ExitStack() as stack:
        try:
            etc = stack.enter_context(_directory(root, "etc"))
            config = stack.enter_context(_directory(etc, "betterlinuxcnc"))
        except FileNotFoundError:
            return "not-applicable"
        lock = os.open(
            ".axis-upgrade.lock",
            os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW,
            0o600,
            dir_fd=config,
        )
        try:
            info = os.fstat(lock)
            _trusted(info)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError("Invalid axis migration lock")
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return _upgrade(root, config)
        finally:
            os.close(lock)
