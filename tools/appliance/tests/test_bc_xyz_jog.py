"""Public preparation CLI coverage without starting a controller or hardware."""

import configparser
import fcntl
import json
import shutil
import subprocess
import sys
import unittest

import test_axis_upgrade as installation

BOOTSTRAP = r"""
import json, os, pwd, runpy, subprocess, sys
from pathlib import Path
from types import SimpleNamespace
script, directory, fault, action = sys.argv[1:]
root = Path(directory)
real_open, real_fstat, real_fsync = os.open, os.fstat, os.fsync
def opened(path, flags, *args, **kwargs):
    if path == '/':
        path = directory
    elif os.path.isabs(path):
        raise AssertionError('Unexpected absolute path: ' + str(path))
    return real_open(path, flags, *args, **kwargs)
def info(fd):
    values = list(real_fstat(fd))
    values[4:6] = [0, 0]
    return os.stat_result(values)
def account(name):
    assert name == 'linuxcnc'
    return SimpleNamespace(pw_uid=1001)
def run(args, **kwargs):
    with (root / 'calls.jsonl').open('a') as stream:
        stream.write(json.dumps(args) + '\n')
    if args == ['/usr/sbin/betterlinuxcnc-appliance', 'backup']:
        if fault == 'backup':
            raise subprocess.CalledProcessError(1, args)
        if fault == 'changed':
            path = root / 'etc/betterlinuxcnc/launcher.json'
            path.write_text(path.read_text() + ' ')
        return SimpleNamespace(returncode=0)
    if args[:2] == ['/usr/lib/betterlinuxcnc/manage-ini/pa-config', 'stage-axis']:
        if fault == 'helper':
            raise subprocess.CalledProcessError(1, args)
        with (Path(kwargs['cwd']) / args[2]).open('xb') as stream:
            stream.write(kwargs['input'])
        return SimpleNamespace(returncode=0)
    assert args[:3] == ['/usr/bin/dpkg-query', '-W', '-f=${Version}']
    assert args[3] in ('linuxcnc-uspace', 'linuxcnc-uspace-dev', 'betterlinuxcnc')
    return SimpleNamespace(stdout='26.10.26.5' if args[3] == 'betterlinuxcnc' else '2.9.10')
def sync(fd):
    if fault == 'write':
        raise OSError('Injected storage failure before atomic publication')
    real_fsync(fd)
os.open, os.fstat, os.geteuid, os.fsync = opened, info, lambda: 0, sync
pwd.getpwnam, subprocess.run = account, run
sys.argv = [script, *json.loads(action)]
runpy.run_path(script, run_name='__main__')
"""


# --------#
# BEGIN: BcXyzJogTests
@unittest.skipUnless(sys.platform == "linux", "Linux atomic publication contract")
class BcXyzJogTests(unittest.TestCase):
    def setUp(self):
        # Reuse the installed ABI/provenance fixture, not the old motor mapping.
        installation.AxisUpgradeTests.setUp(self)
        shutil.rmtree(self.machine)
        installation.write_fixture(
            self.machine, installation.FIXTURE.with_name("bc-inputs-installed.json")
        )
        (self.machine / "tool.tbl").write_text("; retained machine data\n")
        (self.machine / "linuxcnc.var").write_text("5220 1\n")
        (self.config / "launcher.json").write_text(
            json.dumps({"ini": "/etc/betterlinuxcnc/machine/axis-5.ini"})
        )
        self.locks = [
            self.root / "var/cache/betterlinuxcnc/update/update.lock",
            self.root / "var/lib/betterlinuxcnc/configuration.lock",
        ]
        for path in self.locks:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch(mode=0o600)

    def invoke(self, fault="", action=None):
        return subprocess.run(
            [
                sys.executable,
                "-I",
                "-c",
                BOOTSTRAP,
                str(installation.MODULE / "main.py"),
                str(self.root),
                fault,
                json.dumps(action or ["prepare-bc-xyz-jog"]),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def contents(self):
        return {p.name: p.read_bytes() for p in self.machine.iterdir()}

    def test_prepares_only_xyz_and_preserves_other_profiles_and_launcher(self):
        before = self.contents()
        launcher = (self.config / "launcher.json").read_bytes()
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("prepared", result.stdout)
        after = self.contents()
        self.assertEqual(set(after), {*before, "bc-xyz-jog.hal"})
        for name, content in before.items():
            if name != "axis-3.ini":
                self.assertEqual(after[name], content)
        self.assertEqual((self.config / "launcher.json").read_bytes(), launcher)
        ini = configparser.ConfigParser(interpolation=None)
        ini.read_string(after["axis-3.ini"].decode())
        self.assertEqual(ini["KINS"]["JOINTS"], "3")
        self.assertEqual(ini["TRAJ"]["COORDINATES"], "XYZ")
        self.assertEqual(ini["HAL"]["HALFILE"], "bc-xyz-jog.hal")
        self.assertNotIn("JOINT_3", ini)
        self.assertNotIn("AXIS_B", ini)
        self.assertEqual(ini["BETTERCNC_HOMING"]["MOTOR_MAPPING_VERIFIED"], "NO")
        self.assertEqual(ini["BETTERCNC_HOMING"]["MOTOR_DIRECTIONS_VERIFIED"], "NO")
        hal = after["bc-xyz-jog.hal"].decode()
        self.assertIn("num_stepgens=3 num_pwmgens=0", hal)
        self.assertIn("setp motion.homing-inhibit true", hal)
        self.assertIn("iocontrol.0.user-enable-out => iocontrol.0.emc-enable-in", hal)
        for joint, axis, limits in (
            (0, "X", (0, 580)),
            (1, "Y", (0, 380)),
            (2, "Z", (-50, 0)),
        ):
            section = ini[f"JOINT_{joint}"]
            self.assertEqual(
                section.getfloat("STEP_SCALE"), -320 if axis == "Z" else 320
            )
            self.assertEqual(section.getfloat("MAX_VELOCITY"), 15)
            self.assertEqual(section.getfloat("MAX_ACCELERATION"), 50)
            self.assertEqual(section.getfloat("STEPGEN_MAXVEL"), 18.75)
            self.assertEqual(section.getfloat("STEPGEN_MAXACCEL"), 62.5)
            self.assertEqual(section.getint("HOME_SEQUENCE"), 1000)
            self.assertEqual(
                (section.getfloat("MIN_LIMIT"), section.getfloat("MAX_LIMIT")), limits
            )
            self.assertEqual(ini[f"AXIS_{axis}"].getfloat("MAX_VELOCITY"), 15)
            stepgen = (1, 0, 2)[joint]
            self.assertIn(
                f"joint.{joint}.amp-enable-out => hm2_7i92.0.stepgen.{stepgen:02}.enable",
                hal,
            )
            self.assertIn(
                f"joint.{joint}.motor-pos-cmd => hm2_7i92.0.stepgen.{stepgen:02}.position-cmd",
                hal,
            )
            self.assertIn(
                f"hm2_7i92.0.stepgen.{stepgen:02}.position-fb => joint.{joint}.motor-pos-fb",
                hal,
            )
            self.assertIn(
                f"hm2_7i92.0.stepgen.{stepgen:02}.position-scale [JOINT_{joint}]STEP_SCALE",
                hal,
            )
            self.assertIn(
                f"hm2_7i92.0.gpio.{20 + joint:03}.in => debounce.0.{joint}.in", hal
            )
            self.assertIn(
                f"debounce.0.{joint}.out => joint.{joint}.neg-lim-sw-in joint.{joint}.home-sw-in",
                hal,
            )
        calls = [
            json.loads(line)
            for line in (self.root / "calls.jsonl").read_text().splitlines()
        ]
        backup = calls.index(["/usr/sbin/betterlinuxcnc-appliance", "backup"])
        writes = [
            (i, command) for i, command in enumerate(calls) if "stage-axis" in command
        ]
        self.assertEqual(
            {command[-1] for _, command in writes},
            {"axis-3.ini", "axis-4.ini", "axis-5.ini"},
        )
        self.assertTrue(all(i > backup for i, _ in writes))
        again = self.invoke()
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertIn("already-current", again.stdout)
        self.assertEqual(self.contents(), after)

    def installed_jog(self):
        fixture = installation.FIXTURE.with_name("bc-xyz-jog-installed.json")
        for name, lines in json.loads(fixture.read_text()).items():
            (self.machine / name).write_text("".join(lines))
        (self.config / "launcher.json").write_text(
            json.dumps({"ini": "/etc/betterlinuxcnc/machine/axis-3.ini"})
        )

    def test_corrects_jog_outputs_preserving_inputs_and_other_profiles(self):
        self.installed_jog()
        before = self.contents()
        launcher = (self.config / "launcher.json").read_bytes()
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        after = self.contents()
        self.assertEqual(set(after), set(before))
        for name, content in before.items():
            if name not in ("bc-xyz-jog.hal", "axis-3.ini"):
                self.assertEqual(after[name], content)
        ini = configparser.ConfigParser(interpolation=None)
        ini.read_string(after["axis-3.ini"].decode())
        self.assertEqual(ini["JOINT_2"].getfloat("STEP_SCALE"), -320)
        self.assertEqual(ini["JOINT_2"].getfloat("MAX_VELOCITY"), 15)
        self.assertEqual(ini["AXIS_Z"].getfloat("MIN_LIMIT"), -50)
        self.assertEqual(ini["AXIS_Z"].getfloat("MAX_LIMIT"), 0)
        self.assertEqual(ini["BETTERCNC_HOMING"]["MOTOR_DIRECTIONS_VERIFIED"], "NO")
        self.assertEqual((self.config / "launcher.json").read_bytes(), launcher)
        hal = after["bc-xyz-jog.hal"].decode()
        for joint, axis, stepgen in ((0, "x", 1), (1, "y", 0), (2, "z", 2)):
            self.assertIn(
                f"net {axis}-command joint.{joint}.motor-pos-cmd => hm2_7i92.0.stepgen.{stepgen:02}.position-cmd",
                hal,
            )
        self.assertEqual(
            [line for line in hal.splitlines() if "stepgen" not in line][1:],
            [
                line
                for line in before["bc-xyz-jog.hal"].decode().splitlines()
                if "stepgen" not in line
            ][1:],
        )
        again = self.invoke()
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertIn("already-current", again.stdout)
        self.assertEqual(self.contents(), after)

    def test_updates_the_captured_xy_corrected_profile(self):
        self.installed_jog()
        (self.machine / "bc-xyz-jog.hal").write_bytes(
            (installation.MODULE / "templates/bc-xyz-jog.hal").read_bytes()
        )
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        ini = configparser.ConfigParser(interpolation=None)
        ini.read(self.machine / "axis-3.ini")
        self.assertEqual(ini["JOINT_2"].getfloat("STEP_SCALE"), -320)

    def test_homing_requires_explicit_acceptance_of_the_corrected_profile(self):
        self.installed_jog()
        action = [
            "commission-bc-xyz-homing",
            "--directions-confirmed",
            "--travel-confirmed",
        ]
        before = self.contents()
        self.assertNotEqual(self.invoke(action=action).returncode, 0)
        self.assertEqual(self.contents(), before)
        prepared = self.invoke()
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        before = self.contents()
        for arguments in (action[:1], action[:2], [action[0], action[2]]):
            self.assertNotEqual(self.invoke(action=arguments).returncode, 0)
            self.assertEqual(self.contents(), before)
        result = self.invoke(action=action)
        self.assertEqual(result.returncode, 0, result.stderr)
        after = self.contents()
        for name, content in before.items():
            if name not in ("axis-3.ini", "bc-xyz-jog.hal"):
                self.assertEqual(after[name], content)
        ini = configparser.ConfigParser(interpolation=None)
        ini.read_string(after["axis-3.ini"].decode())
        self.assertEqual(ini["BETTERCNC_HOMING"]["MOTOR_DIRECTIONS_VERIFIED"], "YES")
        for joint, axis, sequence, maximum in (
            (0, "X", 2, 580),
            (1, "Y", 3, 380),
            (2, "Z", 1, 50),
        ):
            section = ini[f"JOINT_{joint}"]
            self.assertEqual(section.getint("HOME_SEQUENCE"), sequence)
            self.assertEqual(section.getfloat("HOME"), 0)
            self.assertEqual(section.getfloat("HOME_OFFSET"), -5)
            self.assertEqual(section.getfloat("HOME_SEARCH_VEL"), -2)
            self.assertEqual(section.getfloat("HOME_LATCH_VEL"), -0.5)
            self.assertEqual(section.getfloat("HOME_BACKOFF_VEL"), 1)
            for section in (ini[f"JOINT_{joint}"], ini[f"AXIS_{axis}"]):
                self.assertEqual(section.getfloat("MIN_LIMIT"), -0.1)
                self.assertEqual(section.getfloat("MAX_LIMIT"), maximum)
        self.assertIn(b"setp motion.homing-inhibit false", after["bc-xyz-jog.hal"])
        again = self.invoke(action=action)
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertIn("already-current", again.stdout)
        self.assertEqual(self.contents(), after)
        self.assertNotEqual(self.invoke().returncode, 0)
        self.assertEqual(self.contents(), after)

    def test_mapping_correction_rejects_onsite_edits_and_backup_failure(self):
        self.installed_jog()
        for name in ("axis-3.ini", "bc-xyz-jog.hal"):
            path = self.machine / name
            original = path.read_bytes()
            path.write_bytes(original + b"\n# local adjustment\n")
            before = self.contents()
            result = self.invoke()
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertEqual(self.contents(), before)
            path.write_bytes(original)
        before = self.contents()
        result = self.invoke("backup")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.contents(), before)

    def test_rejects_changed_profiles_without_overwriting_tuning(self):
        for name in ("axis-3.ini", "axis-5.ini", "bc-inputs.hal", "bc-xyz-limits.hal"):
            path = self.machine / name
            original = path.read_bytes()
            path.write_bytes(original + b"\n# local adjustment\n")
            before = self.contents()
            result = self.invoke()
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertEqual(self.contents(), before)
            path.write_bytes(original)

    def test_stopped_stack_backup_helper_and_atomic_write_fail_closed(self):
        for problem in ("core", "socket", "backup", "changed", "helper", "write"):
            with self.subTest(problem=problem):
                path = None
                if problem in ("core", "socket"):
                    path = self.root / (
                        "tmp/linuxcnc.lock"
                        if problem == "core"
                        else "run/user/1001/betterlinuxcnc/control.sock"
                    )
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.touch()
                before = self.contents()
                result = self.invoke(problem)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertEqual(self.contents(), before)
                self.assertEqual(list(self.config.glob(".axis-upgrade-*")), [])
                if path:
                    path.unlink()

    def test_maintenance_and_launcher_leases_prevent_publication(self):
        for path in self.locks:
            with path.open("rb") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                before = self.contents()
                result = self.invoke()
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertEqual(self.contents(), before)

    def test_unknown_files_and_existing_jogging_hal_are_preserved(self):
        for name in ("extra.ini", "bc-xyz-jog.hal"):
            path = self.machine / name
            path.write_text("# existing site configuration\n")
            before = self.contents()
            result = self.invoke()
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertEqual(self.contents(), before)
            path.unlink()


# END: BcXyzJogTests
# --------#
