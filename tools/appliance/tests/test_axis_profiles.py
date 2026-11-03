"""Public profile CLI contracts on isolated files, with no host or motion commands."""

import configparser
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
BOOTSTRAP = r"""
import os, pwd, runpy, subprocess, sys
from pathlib import Path
from types import SimpleNamespace
module, directory, fault, *arguments = sys.argv[1:]
root = Path(directory)
sys.path.insert(0, module)
import axis_profiles
axis_profiles.CONFIG = root / 'etc'
axis_profiles.LEASE = root / 'configuration.lock'
axis_profiles.UPDATE_LOCK = root / 'update.lock'
axis_profiles.PUBLIC = root / 'status'
original_lstat, original_fstat = Path.lstat, os.fstat
def root_info(info, parent=False):
    values = list(info)
    values[4] = 0
    if parent:
        values[0] &= ~0o022
    return os.stat_result(values)
def lstat(path, *args, **kwargs):
    if str(path) in ('/tmp/linuxcnc.lock', '/run/user/65432/betterlinuxcnc/control.sock'):
        if fault == 'running':
            return root_info(original_lstat(root / 'update.lock'))
        raise FileNotFoundError(str(path))
    return root_info(original_lstat(path, *args, **kwargs), not path.is_relative_to(root))
Path.lstat = lstat
os.fstat = lambda descriptor: root_info(original_fstat(descriptor))
os.fchown = lambda descriptor, uid, gid: None
os.getuid = os.geteuid = lambda: 65432 if arguments[0] == 'request' else 0
pwd.getpwnam = lambda name: SimpleNamespace(pw_uid=65432)
def run(command, **kwargs):
    with (root / 'calls.jsonl').open('a') as stream:
        import json
        stream.write(json.dumps(command) + '\n')
    if command == ['/usr/sbin/betterlinuxcnc-appliance', 'backup']:
        if fault == 'backup':
            raise subprocess.CalledProcessError(1, command)
        if fault == 'changed':
            path = root / 'etc/launcher.json'
            path.write_text(path.read_text() + ' ')
        return SimpleNamespace(returncode=0)
    if command[:2] == ['/usr/bin/systemctl', '--system']:
        return SimpleNamespace(returncode=0, stdout='inactive\n')
    raise AssertionError('Unexpected process: ' + repr(command))
subprocess.run = run
if fault == 'commit':
    original_replace = os.replace
    def replace(source, destination):
        if Path(destination) == root / 'etc/machine/machine.ini':
            raise OSError('Injected failure before the atomic INI commit')
        return original_replace(source, destination)
    os.replace = replace
if arguments[0] == 'apply-system' and fault != 'missing-lock':
    descriptor = os.open(axis_profiles.UPDATE_LOCK, os.O_RDONLY)
    if descriptor != 4:
        os.dup2(descriptor, 4)
        os.close(descriptor)
elif fault == 'missing-lock':
    try:
        os.close(4)
    except OSError:
        pass
sys.argv = [str(Path(module) / 'main.py'), 'axis-profile', *arguments]
runpy.run_path(sys.argv[0], run_name='__main__')
"""


def fixture():
    """Synthetic saved rotary tuning; never used as production defaults."""
    ini = (
        "[KINS]\nJOINTS = 3\nKINEMATICS = trivkins coordinates=XYZ\n"
        "[TRAJ]\nCOORDINATES = XYZ\nANGULAR_UNITS = degree\n"
        "[DISPLAY]\nDISPLAY = betterlinuxcnc\nGEOMETRY = XYZ\n"
        "[HAL]\nHALFILE = machine.hal\nHALFILE = custom.hal\n"
        "[AXIS_X]\nMAX_VELOCITY = 17\nMIN_LIMIT = -0.1\nMAX_LIMIT = 410\n"
        "[JOINT_0]\nTYPE = LINEAR\nSTEP_SCALE = 200\nHOME_OFFSET = -5\n"
    )
    for joint, axis in ((3, "A"), (4, "C")):
        ini += (
            f"[AXIS_{axis}]\nMIN_LIMIT = -180\nMAX_LIMIT = 180\n"
            "MAX_VELOCITY = 1\nMAX_ACCELERATION = 1\n"
            f"[JOINT_{joint}]\nTYPE = ANGULAR\nMIN_LIMIT = -180\nMAX_LIMIT = 180\n"
            f"STEP_SCALE = {100 if axis == 'A' else 200}\n"
            "MAX_VELOCITY = 1\nMAX_ACCELERATION = 1\n"
            "STEPGEN_MAXVEL = 2\nSTEPGEN_MAXACCEL = 2\nFERROR = 1\nMIN_FERROR = 0.5\n"
            "DIRSETUP = 10000\nDIRHOLD = 10000\nSTEPLEN = 5000\nSTEPSPACE = 5000\n"
            "HOME = 0\nHOME_OFFSET = 0\nHOME_SEARCH_VEL = 0\nHOME_LATCH_VEL = 0\n"
            "HOME_USE_INDEX = NO\nHOME_SEQUENCE = 3\n"
        )
    hal = (
        "# Isolated fixture: do not load into HAL.\n"
        "loadrt [KINS]KINEMATICS\n"
        "loadrt [EMCMOT]EMCMOT num_joints=[KINS]JOINTS\n"
        'loadrt hm2_eth board_ip="10.10.10.10" config="num_stepgens=3"\n'
        "addf hm2_7i92.0.read servo-thread\n"
        "addf hm2_7i92.0.write servo-thread\n"
        "net x-feedback hm2_7i92.0.stepgen.01.position-fb => joint.0.motor-pos-fb\n"
    )
    return ini, hal


# --------#
# BEGIN: AxisProfileCliTests
@unittest.skipUnless(sys.platform == "linux", "Linux appliance contract")
class AxisProfileCliTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.config = self.root / "etc"
        self.machine = self.config / "machine"
        self.machine.mkdir(parents=True)
        self.launcher = self.config / "launcher.json"
        self.ini = self.machine / "machine.ini"
        self.original, self.original_hal = fixture()
        self.ini.write_text(self.original)
        (self.machine / "machine.hal").write_text(self.original_hal)
        (self.machine / "custom.hal").write_text("# Preserve user I/O settings\n")
        self.launcher_content = json.dumps(
            {"ini": str(self.ini), "cam": {"port": 1234}}
        )
        self.launcher.write_text(self.launcher_content)
        for name in ("update.lock", "configuration.lock"):
            (self.root / name).touch(mode=0o600)

    def invoke(self, *arguments, fault=""):
        return subprocess.run(
            [
                sys.executable,
                "-I",
                "-c",
                BOOTSTRAP,
                str(MODULE),
                str(self.root),
                fault,
                *arguments,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )

    def revision(self, count=5):
        result = self.invoke("prepare-system", str(count))
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)["revision"]

    def apply(self, count, fault=""):
        result = self.invoke(
            "apply-system", str(count), self.revision(count), fault=fault
        )
        return result

    def test_current_ini_generates_all_counts_without_external_profile_files(self):
        result = self.invoke("status")
        self.assertEqual(result.returncode, 0, result.stderr)
        record = json.loads(result.stdout)
        self.assertEqual(record["configured_axis_count"], 3)
        self.assertTrue(all(item["available"] for item in record["profiles"]))
        result = self.invoke("request", "5")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["phase"], "scheduled")
        calls = [
            json.loads(line)
            for line in (self.root / "calls.jsonl").read_text().splitlines()
        ]
        self.assertEqual(
            calls,
            [
                [
                    "/usr/bin/systemctl",
                    "--system",
                    "--no-ask-password",
                    "--no-block",
                    "start",
                    "betterlinuxcnc-axis-profile@5.service",
                ]
            ],
        )
        self.assertEqual(self.ini.read_text(), self.original)
        self.assertNotEqual(self.invoke("request", "6").returncode, 0)

    def test_round_trip_writes_same_ini_correct_channels_and_preserves_xyz(self):
        for count, axes in ((5, "XYZAC"), (4, "XYZC"), (3, "XYZ")):
            result = self.apply(count)
            self.assertEqual(result.returncode, 0, result.stderr)
            text = self.ini.read_text()
            self.assertIn(f"JOINTS = {count}", text)
            self.assertIn(f"COORDINATES = {axes}", text)
            self.assertIn("STEP_SCALE = 200\nHOME_OFFSET = -5", text)
            self.assertEqual(self.launcher.read_text(), self.launcher_content)
            self.assertEqual(
                (self.machine / "machine.hal").read_text(), self.original_hal
            )
            if count > 3:
                parser = configparser.ConfigParser(strict=False)
                parser.read_string(text)
                primary = next(
                    line.split("=", 1)[1].strip()
                    for line in text.splitlines()
                    if line.startswith("HALFILE")
                )
                hal = (self.machine / primary).read_text()
                c_joint = 4 if count == 5 else 3
                self.assertIn(
                    f"joint.{c_joint}.motor-pos-cmd => hm2_7i92.0.stepgen.03.position-cmd",
                    hal,
                )
                self.assertIn(
                    f"stepgen.03.position-scale [JOINT_{c_joint}]STEP_SCALE", hal
                )
                self.assertIn(f"num_stepgens={count}", hal)
                if count == 5:
                    self.assertIn(
                        "joint.3.motor-pos-cmd => hm2_7i92.0.stepgen.04.position-cmd",
                        hal,
                    )
                    self.assertEqual(parser.getfloat("AXIS_A", "MIN_LIMIT"), -90)
                    self.assertEqual(parser.getfloat("JOINT_3", "MAX_LIMIT"), 90)
                else:
                    self.assertNotIn("stepgen.04", hal)
                    self.assertEqual(parser.getfloat("JOINT_3", "STEP_SCALE"), 200)
        self.assertEqual(self.ini.read_text(), self.original)

    def test_missing_rotary_parameters_are_named_without_copying_linear_scale(self):
        self.ini.write_text(self.original[: self.original.index("[AXIS_A]")])
        result = self.invoke("status")
        self.assertEqual(result.returncode, 0, result.stderr)
        profiles = json.loads(result.stdout)["profiles"]
        self.assertTrue(profiles[0]["available"])
        self.assertFalse(profiles[1]["available"])
        self.assertIn("C.joint.STEP_SCALE", profiles[1]["reason"])
        self.assertIn("A.joint.STEP_SCALE", profiles[2]["reason"])
        before = self.ini.read_bytes()
        self.assertNotEqual(self.invoke("request", "5").returncode, 0)
        self.assertEqual(self.ini.read_bytes(), before)

    def test_identical_duplicate_ini_values_are_preserved_but_conflicts_rejected(self):
        repeated = self.original.replace(
            "GEOMETRY = XYZ", "GEOMETRY = XYZ\nGEOMETRY = XYZ"
        )
        self.ini.write_text(repeated)
        self.assertEqual(self.apply(5).returncode, 0)
        self.assertEqual(self.apply(3).returncode, 0)
        self.assertEqual(self.ini.read_text(), repeated)
        conflicting = repeated.replace("GEOMETRY = XYZ\n", "GEOMETRY = XZY\n", 1)
        self.ini.write_text(conflicting)
        self.assertNotEqual(self.invoke("request", "5").returncode, 0)
        self.assertEqual(self.ini.read_text(), conflicting)

    def test_captured_zhulong_first_use_generates_confirmed_rotary_transmission(self):
        captured = json.loads(
            (Path(__file__).parent / "fixtures/zhulong-installed-v4.json").read_text()
        )
        for name, lines in captured.items():
            (self.machine / name).write_text("".join(lines))
        original = "".join(captured["烛龙V2.ini"])
        self.ini.write_text(original)
        before = configparser.ConfigParser(strict=False)
        before.read_string(original)
        for count in (4, 5, 3):
            result = self.apply(count)
            self.assertEqual(result.returncode, 0, result.stderr)
            parser = configparser.ConfigParser(strict=False)
            parser.read_string(self.ini.read_text())
            for section in (
                "AXIS_X",
                "AXIS_Y",
                "AXIS_Z",
                "JOINT_0",
                "JOINT_1",
                "JOINT_2",
            ):
                self.assertEqual(dict(parser[section]), dict(before[section]))
            if count == 3:
                self.assertEqual(self.ini.read_text(), original)
                continue
            for joint in range(3, count):
                name = f"JOINT_{joint}"
                self.assertAlmostEqual(
                    parser.getfloat(name, "STEP_SCALE"), 160000 / 360
                )
                self.assertEqual(parser.getfloat(name, "MAX_VELOCITY"), 1)
                self.assertEqual(parser.getfloat(name, "HOME_SEARCH_VEL"), 0)
                self.assertEqual(parser.getfloat(name, "HOME_LATCH_VEL"), 0)
                self.assertEqual(parser.getint(name, "HOME_SEQUENCE"), 1000)
            self.assertEqual(parser.getfloat("AXIS_C", "MIN_LIMIT"), -1e99)
            self.assertEqual(parser.getfloat("AXIS_C", "MAX_LIMIT"), 1e99)
            if count == 5:
                self.assertEqual(parser.getfloat("AXIS_A", "MIN_LIMIT"), -90)
                self.assertEqual(parser.getfloat("JOINT_3", "MAX_LIMIT"), 90)
            for key in ("MOTOR_MAPPING_VERIFIED", "MOTOR_DIRECTIONS_VERIFIED"):
                self.assertEqual(parser.get("BETTERCNC_HOMING", key), "NO")
        self.ini.write_text(original + "\n[AXIS_C]\nMAX_VELOCITY = 7\n")
        self.assertNotEqual(self.invoke("request", "4").returncode, 0)
        self.ini.write_text(original.replace("MACHINE = 烛龙V2", "MACHINE = Other"))
        self.assertNotEqual(self.invoke("request", "5").returncode, 0)

    def test_apply_requires_lock_stopped_stack_revision_and_successful_backup(self):
        revision = self.revision()
        for fault in ("missing-lock", "running", "backup"):
            with self.subTest(fault=fault):
                result = self.invoke("apply-system", "5", revision, fault=fault)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.ini.read_text(), self.original)
        self.assertNotEqual(self.invoke("apply-system", "5", "0" * 64).returncode, 0)
        self.assertEqual(self.ini.read_text(), self.original)

    def test_rechecks_revision_after_backup(self):
        result = self.apply(5, fault="changed")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.ini.read_text(), self.original)
        self.assertEqual(self.launcher.read_text(), self.launcher_content + " ")

    def test_failed_ini_commit_keeps_previous_configuration_and_allows_retry(self):
        self.assertEqual(self.apply(4).returncode, 0)
        before = self.ini.read_bytes()
        result = self.apply(5, fault="commit")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.ini.read_bytes(), before)
        result = self.apply(5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("COORDINATES = XYZAC", self.ini.read_text())

    def test_external_edits_are_not_discarded_when_switching_back(self):
        self.assertEqual(self.apply(5).returncode, 0)
        self.ini.write_text(
            self.ini.read_text().replace("HOME_OFFSET = -5", "HOME_OFFSET = -6")
        )
        before = self.ini.read_bytes()
        self.assertNotEqual(self.invoke("prepare-system", "3").returncode, 0)
        self.assertEqual(self.ini.read_bytes(), before)

    def test_rejects_occupied_rotary_channel_and_unsafe_source(self):
        hal = self.machine / "machine.hal"
        for extra in (
            "net other => hm2_7i92.0.stepgen.03.enable\n",
            "source outside.hal\n",
        ):
            hal.write_text(self.original_hal + extra)
            self.assertNotEqual(self.invoke("prepare-system", "5").returncode, 0)
        hal.write_text(self.original_hal)
        hal.chmod(0o666)
        self.assertNotEqual(self.invoke("prepare-system", "5").returncode, 0)

    def test_dead_service_does_not_leave_permanent_switching_status(self):
        directory = self.root / "status"
        directory.mkdir()
        (directory / "status.json").write_text(
            json.dumps({"phase": "switching", "axis_count": 5, "started_at": 1})
        )
        result = self.invoke("status")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["operation"]["phase"], "error")

    def test_missing_launcher_never_implies_a_selected_three_axis_profile(self):
        self.launcher.unlink()
        result = self.invoke("status")
        self.assertEqual(result.returncode, 0, result.stderr)
        record = json.loads(result.stdout)
        self.assertIsNone(record["configured_axis_count"])
        self.assertFalse(any(profile["available"] for profile in record["profiles"]))


# END: AxisProfileCliTests
# --------#
