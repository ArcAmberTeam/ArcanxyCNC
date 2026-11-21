"""Explicit homing migration through the public CLI, without loading LinuxCNC."""

import configparser
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
VENDOR = MODULE.parents[1] / "vendor/cnc-mesa/linuxcnc/vendor-reference"
TRAVEL = ["--zhulong-homing-travel-mm", "420", "275", "90"]
HEADERS = (
    "motion.h",
    "homing.h",
    "emcmotcfg.h",
    "emcpos.h",
    "posemath.h",
    "simple_tp.h",
)

# The public prepare CLI must verify the installed ABI before reaching account
# provisioning. A group lookup is an intentional stop at that OS boundary. All
# file opens are rooted in the fixture and no administrative process is executed.
PREPARE = r"""
import grp, json, os, runpy, subprocess, sys
from pathlib import Path
from types import SimpleNamespace
script, root, version, euid = sys.argv[1:]
root = Path(root)
real_open, real_fstat = os.open, os.fstat
def opened(path, flags, *args, **kwargs):
    if path == '/':
        path = root
    elif os.path.isabs(path):
        raise AssertionError('unexpected absolute open: ' + str(path))
    assert not flags & (os.O_CREAT | os.O_WRONLY | os.O_RDWR)
    return real_open(path, flags, *args, **kwargs)
def info(descriptor):
    values = list(real_fstat(descriptor))
    values[4:6] = [0, 0]
    return os.stat_result(values)
def run(arguments, **kwargs):
    assert arguments[:3] == ['/usr/bin/dpkg-query', '-W', '-f=${Version}']
    assert arguments[3] in ('linuxcnc-uspace', 'linuxcnc-uspace-dev', 'betterlinuxcnc')
    return SimpleNamespace(stdout='26.10.26.1' if arguments[3] == 'betterlinuxcnc' else version)
def stop_accounts(_name):
    raise ValueError('ABI verified; account boundary reached')
os.open, os.fstat, os.geteuid = opened, info, lambda: int(euid)
grp.getgrnam = stop_accounts
subprocess.run = run
sys.platform = 'linux'
sys.argv = [script, 'prepare', '--source-config', '/never-read.json',
    '--zhulong-homing-travel-mm', '420', '275', '90']
runpy.run_path(script, run_name='__main__')
"""


def parsed(path):
    config = configparser.ConfigParser(strict=False, interpolation=None)
    config.read(path)
    return config


class HomingMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="appliance-homing-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.source = self.base / "source"
        self.profile = self.source / "machine"
        shutil.copytree(VENDOR, self.profile)
        (self.source / "programs").mkdir()
        (self.source / "programs/keep.ngc").write_text("G21\nM2\n")
        self.ini = self.profile / "烛龙V2.ini"
        self.ini.write_text(
            self.ini.read_text()
            .replace("DISPLAY = gmoccapy", "DISPLAY = betterlinuxcnc")
            .replace("/home/lite/linuxcnc/nc_files", "../programs")
            .replace("gmoccapy_postgui.hal", "qt_postgui.hal")
        )
        (self.profile / "qt_postgui.hal").write_text(
            "loadusr -W hal_manualtoolchange\n"
            "net tool-change-request => hal_manualtoolchange.change\n"
            "net tool-change-confirmed <= hal_manualtoolchange.changed\n"
            "net tool-number => hal_manualtoolchange.number\n"
        )
        self.original = self.ini.read_text()
        self.hal = self.profile / "烛龙V2.hal"
        self.config = self.source / "launcher.json"
        self.config.write_text(json.dumps({"ini": "machine/烛龙V2.ini"}))
        self.destination = self.base / "staged"

    def stage(self, *options):
        return subprocess.run(
            [
                sys.executable,
                "-I",
                str(MODULE / "main.py"),
                "stage",
                "--source-config",
                str(self.config),
                "--destination",
                str(self.destination),
                *options,
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )

    def output(self):
        return self.destination / "etc/betterlinuxcnc/machine"

    def test_measured_profile_preserves_tuning_and_wires_only_verified_inputs(self):
        original_hal = self.hal.read_text()
        result = self.stage(*TRAVEL)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.ini.read_text(), self.original)
        self.assertEqual(self.hal.read_text(), original_hal)
        before, after = parsed(self.ini), parsed(self.output() / self.ini.name)
        self.assertEqual(after["EMCMOT"]["HOMEMOD"], "zhulong_homing")
        for joint, axis, minimum, maximum, offset in (
            (0, "X", 0, 410, -5),
            (1, "Y", -265, 0, 5),
            (2, "Z", 0, 80, -5),
        ):
            for section in ("AXIS_" + axis, f"JOINT_{joint}"):
                self.assertEqual(after.getfloat(section, "MIN_LIMIT"), minimum)
                self.assertEqual(after.getfloat(section, "MAX_LIMIT"), maximum)
            section = f"JOINT_{joint}"
            self.assertEqual(after.getfloat(section, "HOME_OFFSET"), offset)
            self.assertEqual(after.getfloat(section, "HOME_SEARCH_VEL"), offset * 0.4)
            self.assertEqual(after.getfloat(section, "HOME_LATCH_VEL"), offset * 0.1)
            self.assertEqual(after.getint(section, "HOME_SEQUENCE"), joint + 1)
            self.assertEqual(after.getfloat(section, "HOME_FINAL_VEL"), 2)
            self.assertEqual(after[section]["HOME_IGNORE_LIMITS"], "YES")
            self.assertEqual(after[section]["HOME_USE_INDEX"], "NO")
        for joint in range(6):
            for key in ("P", "STEP_SCALE", "FERROR", "MAX_ACCELERATION", "DIRSETUP"):
                self.assertEqual(
                    before[f"JOINT_{joint}"][key], after[f"JOINT_{joint}"][key]
                )
        for joint in range(3, 6):
            self.assertEqual(after.getint(f"JOINT_{joint}", "HOME_SEQUENCE"), 101)
            self.assertEqual(
                before[f"AXIS_{'ABC'[joint - 3]}"], after[f"AXIS_{'ABC'[joint - 3]}"]
            )
        self.assertEqual(before["SPINDLE_0"], after["SPINDLE_0"])
        hal = (self.output() / self.hal.name).read_text()
        self.assertEqual(hal.count("loadrt debounce cfg=3"), 1)
        self.assertIn("setp debounce.0.delay 5", hal)
        self.assertIn("setp motion.homing-inhibit false", hal)
        self.assertNotIn("loadrt zhulong_homing", hal)
        self.assertLess(hal.index("addf hm2_7i92.0.read"), hal.index("addf debounce.0"))
        self.assertLess(
            hal.index("addf debounce.0"), hal.index("addf motion-command-handler")
        )
        for joint, axis, gpio, side in (
            (0, "x", 20, "neg"),
            (1, "y", 21, "pos"),
            (2, "z", 22, "neg"),
        ):
            self.assertIn(f"hm2_7i92.0.gpio.{gpio:03}.in => debounce.0.{joint}.in", hal)
            self.assertIn(
                f"net {axis}-home-sw debounce.0.{joint}.out => joint.{joint}.{side}-lim-sw-in",
                hal,
            )
        manifest = json.loads(
            (self.output() / "betterlinuxcnc-homing.json").read_text()
        )
        self.assertEqual(manifest["travelMm"], {"X": 420, "Y": 275, "Z": 90})
        self.assertEqual(manifest["installationCheck"], "required-at-prepare")
        self.assertFalse(manifest["installedModuleVerified"])
        for name, digest in manifest["halFiles"].items():
            self.assertEqual(
                hashlib.sha256((self.output() / name).read_bytes()).hexdigest(), digest
            )

    def test_inputs_only_preserves_all_homing_parameters_and_opposite_limits(self):
        self.hal.write_text(
            self.hal.read_text() + "net x-pos-limit hm2_7i92.0.gpio.023.in\n"
        )
        result = self.stage("--zhulong-inputs-only")
        self.assertEqual(result.returncode, 0, result.stderr)
        before, after = parsed(self.ini), parsed(self.output() / self.ini.name)
        self.assertNotIn("HOMEMOD", after["EMCMOT"])
        for joint in range(6):
            self.assertEqual(before[f"JOINT_{joint}"], after[f"JOINT_{joint}"])
        for axis in "XYZABC":
            self.assertEqual(before[f"AXIS_{axis}"], after[f"AXIS_{axis}"])
        hal = (self.output() / self.hal.name).read_text()
        self.assertIn("net x-pos-limit hm2_7i92.0.gpio.023.in", hal)
        self.assertIn("setp motion.homing-inhibit true", hal)
        self.assertNotIn("TRAVEL_X_MM", after["BETTERCNC_HOMING"])

    def test_no_option_keeps_homing_unchanged(self):
        result = self.stage()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            (self.output() / self.hal.name).read_text(), self.hal.read_text()
        )
        self.assertNotIn("BETTERCNC_HOMING", parsed(self.output() / self.ini.name))

    def test_invalid_travel_never_publishes_configuration(self):
        for values in (
            ("nan", "275", "90"),
            ("420", "inf", "90"),
            ("5", "275", "90"),
            ("420", "275", "-90"),
        ):
            with self.subTest(values=values):
                result = self.stage("--zhulong-homing-travel-mm", *values)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.destination.exists())

    def test_every_loaded_hal_file_is_checked_for_conflicts_and_dynamic_commands(self):
        conflicts = (
            "net x-home-sw hm2_7i92.0.gpio.023.in\n",
            "net alias joint.0.neg-lim-sw-in\n",
            "sets x-home-sw true\n",
            "setp joint.0.home-sw-in true\n",
            "net input hm2_7i92.0.gpio.020.in_not\n",
            "setp ini.3.home_sequence 1\n",
            "setp [CUSTOM]PIN 1\n",
            "loadrt debounce cfg=3\n",
            "source another.hal\n",
            "loadusr arbitrary-script\n",
            "setp motion.homing-inhibit false\n",
        )
        for name in ("custom.hal", "custom_postgui.hal", "shutdown.hal"):
            path = self.profile / name
            original = path.read_text()
            for conflict in conflicts:
                with self.subTest(name=name, conflict=conflict):
                    path.write_text(original + conflict)
                    result = self.stage(*TRAVEL)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse(self.destination.exists())
            path.write_text(original)
        self.assertEqual(self.ini.read_text(), self.original)

    def test_modified_managed_block_or_reordered_motion_is_rejected(self):
        original = self.hal.read_text()
        self.hal.write_text(
            original.replace("addf hm2_7i92.0.read", "addf changed.read")
        )
        self.assertNotEqual(self.stage(*TRAVEL).returncode, 0)
        self.assertFalse(self.destination.exists())
        self.hal.write_text(original + "# BEGIN BetterLinuxCNC Zhulong inputs v1\n")
        self.assertNotEqual(self.stage(*TRAVEL).returncode, 0)
        self.assertFalse(self.destination.exists())

    def test_duplicate_homing_value_and_external_hal_are_rejected(self):
        for replacement in (
            "[JOINT_0]\nHOME_OFFSET = 99\n",
            "[JOINT_0]\nHOME_SEQUENCE = -1\n",
        ):
            self.ini.write_text(self.original.replace("[JOINT_0]\n", replacement))
            self.assertNotEqual(self.stage(*TRAVEL).returncode, 0)
            self.assertFalse(self.destination.exists())
        self.ini.write_text(
            self.original.replace("HALFILE = custom.hal", "HALFILE = ../outside.hal")
        )
        self.assertNotEqual(self.stage(*TRAVEL).returncode, 0)
        self.assertFalse(self.destination.exists())

    def test_owned_input_block_can_be_regenerated_without_duplicate_pins(self):
        result = self.stage("--zhulong-inputs-only")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.hal.write_text((self.output() / self.hal.name).read_text())
        shutil.rmtree(self.destination)
        result = self.stage(*TRAVEL)
        self.assertEqual(result.returncode, 0, result.stderr)
        hal = (self.output() / self.hal.name).read_text()
        self.assertEqual(hal.count("loadrt debounce cfg=3"), 1)
        self.assertEqual(hal.count("setp motion.homing-inhibit false"), 1)

    def test_explicit_xyz_only_removes_known_inactive_channels_and_keeps_spindle(self):
        result = self.stage(*TRAVEL, "--zhulong-xyz-only")
        self.assertEqual(result.returncode, 0, result.stderr)
        before, after = parsed(self.ini), parsed(self.output() / self.ini.name)
        self.assertEqual(after.getint("KINS", "JOINTS"), 3)
        self.assertEqual(after["KINS"]["KINEMATICS"], "trivkins coordinates=XYZ")
        self.assertEqual(after["TRAJ"]["COORDINATES"], "XYZ")
        self.assertEqual(after["DISPLAY"]["GEOMETRY"], "XYZ")
        for axis, joint in (("A", 3), ("B", 4), ("C", 5)):
            self.assertNotIn("AXIS_" + axis, after)
            self.assertNotIn(f"JOINT_{joint}", after)
        self.assertEqual(before["SPINDLE_0"], after["SPINDLE_0"])
        hal = (self.output() / self.hal.name).read_text()
        commands = "\n".join(
            line
            for line in hal.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
        for token in (
            "pid.a",
            "pid.b",
            "pid.c",
            "joint.3",
            "joint.4",
            "joint.5",
            "stepgen.03",
            "stepgen.04",
            "stepgen.05",
            "halui.axis.a",
        ):
            self.assertNotIn(token, commands)
        self.assertIn("loadrt pid names=pid.x,pid.y,pid.z,pid.s", commands)
        self.assertIn("num_stepgens=6", commands)
        for line in self.hal.read_text().splitlines():
            if any(
                part in line
                for part in ("spindle", "pid.s.", "pwmgen", "coolant", "estop")
            ):
                self.assertIn(line, hal)
        self.assertEqual(
            (self.output() / "linuxcnc.var").read_bytes(),
            (self.profile / "linuxcnc.var").read_bytes(),
        )
        self.assertEqual(
            (self.output() / "tool.tbl").read_bytes(),
            (self.profile / "tool.tbl").read_bytes(),
        )
        manifest = json.loads(
            (self.output() / "betterlinuxcnc-homing.json").read_text()
        )
        self.assertEqual(manifest["activeAxes"], "XYZ")
        self.assertFalse(manifest["motorMappingVerified"])
        self.assertFalse(manifest["motorDirectionsVerified"])
        self.assertEqual(after["BETTERCNC_HOMING"]["MOTOR_MAPPING_VERIFIED"], "NO")
        self.assertEqual(after["BETTERCNC_HOMING"]["MOTOR_DIRECTIONS_VERIFIED"], "NO")

    def test_xyz_only_rejects_missing_or_additional_abc_wiring_without_publication(
        self,
    ):
        original = self.hal.read_text()
        for changed in (
            original + "net a-enable spindle.0.on\n",
            original + "net unexpected joint.3.amp-enable-out\n",
            original.replace("net a-home-sw", "# net a-home-sw"),
            original.replace("setp   pid.a.maxerror 0.012700", "setp pid.a.maxerror 1"),
        ):
            with self.subTest(changed=changed[-80:]):
                self.hal.write_text(changed)
                self.assertNotEqual(
                    self.stage(*TRAVEL, "--zhulong-xyz-only").returncode, 0
                )
                self.assertFalse(self.destination.exists())
        self.hal.write_text(original)
        self.ini.write_text(self.original.replace("[AXIS_A]", "[AXIS_A]\nUNREVIEWED=1"))
        self.assertNotEqual(self.stage(*TRAVEL, "--zhulong-xyz-only").returncode, 0)
        self.assertFalse(self.destination.exists())

    def test_xyz_only_without_measured_travel_is_refused(self):
        self.assertNotEqual(self.stage("--zhulong-xyz-only").returncode, 0)
        self.assertFalse(self.destination.exists())


class InstalledHomingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="appliance-homing-abi-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        headers = self.root / "usr/include/linuxcnc"
        headers.mkdir(parents=True)
        for name in HEADERS:
            (headers / name).write_text("/* isolated public ABI fixture */\n")
        self.module = self.root / "usr/lib/linuxcnc/modules/zhulong_homing.so"
        self.module.parent.mkdir(parents=True)
        self.module.write_bytes(b"\x7fELF\x02\x01" + bytes(12) + b"\x3e\x00")
        self.provenance = self.root / "usr/share/betterlinuxcnc/homing/provenance.json"
        self.provenance.parent.mkdir(parents=True)
        self.provenance.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "module": "zhulong_homing.so",
                    "architecture": "amd64",
                    "application_version": "26.10.26.1",
                    "sha256": hashlib.sha256(self.module.read_bytes()).hexdigest(),
                    "linuxcnc": {
                        "version": "2.9.10",
                        "build_system": "uspace",
                        "source_commit": "a" * 40,
                        "headers": {
                            name: hashlib.sha256(
                                (headers / name).read_bytes()
                            ).hexdigest()
                            for name in HEADERS
                        },
                    },
                    "vendor": {
                        "commit": json.loads(
                            (
                                MODULE.parents[1] / "vendor/cnc-mesa/SOURCE.json"
                            ).read_text()
                        )["commit"]
                    },
                }
            )
        )

    def prepare(self, version="1:2.9.10+git20261025.5a9f7b7", euid=0):
        return subprocess.run(
            [
                sys.executable,
                "-I",
                "-c",
                PREPARE,
                str(MODULE / "main.py"),
                str(self.root),
                version,
                str(euid),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )

    def test_matching_artifacts_reach_account_boundary_only_after_validation(self):
        result = self.prepare()
        self.assertEqual(result.returncode, 1)
        self.assertIn("ABI verified; account boundary reached", result.stderr)

    def test_wrong_core_header_and_module_refuse_before_account_changes(self):
        for version in ("2.9.4", "2.9.10~pre1", "2.10.0"):
            result = self.prepare(version)
            self.assertEqual(result.returncode, 1)
            self.assertNotIn("account boundary reached", result.stderr)
        header = self.root / "usr/include/linuxcnc/motion.h"
        original = header.read_bytes()
        header.write_bytes(b"wrong ABI")
        self.assertIn("headers do not match", self.prepare().stderr)
        header.write_bytes(original)
        self.module.write_bytes(b"not the published module")
        self.assertIn("does not match", self.prepare().stderr)

    def test_links_and_writable_parents_are_refused(self):
        parent = self.root / "usr/include/linuxcnc"
        parent.chmod(0o777)
        self.assertIn("untrusted parent", self.prepare().stderr)
        parent.chmod(0o755)
        header = parent / "motion.h"
        saved = parent / "saved.h"
        header.rename(saved)
        header.symlink_to(saved)
        result = self.prepare()
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("account boundary reached", result.stderr)

    def test_regular_operator_cannot_prepare(self):
        result = self.prepare(euid=1000)
        self.assertEqual(result.returncode, 1)
        self.assertIn("root maintenance session", result.stderr)


if __name__ == "__main__":
    unittest.main()
