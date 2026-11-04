"""Exercise the fixed public migration CLI against the captured installed profile."""

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
FIXTURE = Path(__file__).parent / "fixtures/zhulong-installed-v1.json"
BOOTSTRAP = r"""
import os, pwd, runpy, subprocess, sys
from pathlib import Path
from types import SimpleNamespace
script, root, fault = sys.argv[1:]
real_open, real_fstat, real_fsync = os.open, os.fstat, os.fsync
def opened(path, flags, *args, **kwargs):
    if path == '/':
        path = root
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
    assert args[:3] == ['/usr/bin/dpkg-query', '-W', '-f=${Version}']
    assert args[3] in ('linuxcnc-uspace', 'linuxcnc-uspace-dev', 'betterlinuxcnc-qt')
    return SimpleNamespace(stdout='26.10.26.5' if args[3] == 'betterlinuxcnc-qt' else '2.9.10')
def sync(fd):
    if fault == 'write':
        raise OSError('Injected storage failure before atomic publication')
    real_fsync(fd)
os.open, os.fstat, os.geteuid, os.fsync = opened, info, lambda: 0, sync
pwd.getpwnam, subprocess.run = account, run
sys.argv = [script, 'migrate-machine']
runpy.run_path(script, run_name='__main__')
"""


def fixture_bytes(name):
    return "".join(json.loads(FIXTURE.read_text())[name]).encode()


def write_fixture(target, fixture=FIXTURE):
    target.mkdir(parents=True)
    for name, lines in json.loads(fixture.read_text()).items():
        (target / name).write_text("".join(lines))


@unittest.skipUnless(
    sys.platform == "linux",
    "Atomic directory exchange is a Linux installation contract",
)
class AxisUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.config = self.root / "etc/betterlinuxcnc"
        self.machine = self.config / "machine"
        write_fixture(self.machine)
        (self.config / "launcher.json").write_text(
            json.dumps({"ini": "/etc/betterlinuxcnc/machine/烛龙V2.ini"})
        )
        module = b"\x7fELF\x02\x01" + bytes(12) + b"\x3e\x00"
        path = self.root / "usr/lib/linuxcnc/modules/zhulong_homing.so"
        path.parent.mkdir(parents=True)
        path.write_bytes(module)
        headers = {}
        for name in (
            "motion.h",
            "homing.h",
            "emcmotcfg.h",
            "emcpos.h",
            "posemath.h",
            "simple_tp.h",
        ):
            path = self.root / "usr/include/linuxcnc" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"ABI fixture\n")
            headers[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        source = json.loads(
            (MODULE.parents[1] / "vendor/cnc-mesa/SOURCE.json").read_text()
        )
        metadata = {
            "schema_version": 1,
            "module": "zhulong_homing.so",
            "application_version": "26.10.26.5",
            "architecture": "amd64",
            "sha256": hashlib.sha256(module).hexdigest(),
            "linuxcnc": {
                "version": "2.9.10",
                "build_system": "uspace",
                "source_commit": "a" * 40,
                "headers": headers,
            },
            "vendor": {"commit": source["commit"]},
            "commissioning_profile": "zhulong-xyz-v5-20261026",
        }
        self.metadata = self.root / "usr/share/betterlinuxcnc/homing/provenance.json"
        self.metadata.parent.mkdir(parents=True)
        self.metadata.write_text(json.dumps(metadata))

    def invoke(self, fault=""):
        return subprocess.run(
            [
                sys.executable,
                "-I",
                "-c",
                BOOTSTRAP,
                str(MODULE / "main.py"),
                str(self.root),
                fault,
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def contents(self):
        return {p.name: p.read_bytes() for p in self.machine.iterdir() if p.is_file()}

    def test_migrates_command_feedback_enable_scale_and_home_switches_together(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        ini = configparser.ConfigParser(strict=False, interpolation=None)
        ini.read(self.machine / "烛龙V2.ini")
        hal = (self.machine / "烛龙V2.hal").read_text()
        for joint, axis, channel, travel in (
            (0, "X", "01", 420),
            (1, "Y", "00", 275),
            (2, "Z", "02", 90),
        ):
            name = axis.lower()
            for signal, endpoint in (
                ("output", "velocity-cmd"),
                ("pos-fb", "position-fb"),
                ("enable", "enable"),
            ):
                lines = [
                    line.split()
                    for line in hal.splitlines()
                    if line.startswith(f"net {name}-{signal}")
                ]
                self.assertTrue(
                    any(
                        f"hm2_7i92.0.stepgen.{channel}.{endpoint}" in line
                        for line in lines
                    )
                )
            self.assertIn(
                f"net bettercnc-{name}-home-raw hm2_7i92.0.gpio.{20 + joint:03}.in => debounce.0.{joint}.in",
                hal,
            )
            self.assertIn(
                f"net {name}-home-sw debounce.0.{joint}.out => joint.{joint}.neg-lim-sw-in",
                hal,
            )
            self.assertEqual(
                ini.getfloat(f"JOINT_{joint}", "HOME_SEARCH_VEL"),
                -5 if axis == "Z" else -15,
            )
            self.assertEqual(ini.getfloat(f"JOINT_{joint}", "HOME_BACKOFF_VEL"), 2)
            self.assertEqual(ini.getfloat(f"JOINT_{joint}", "HOME_SEQUENCE"), 1)
            self.assertEqual(
                ini.getfloat(f"JOINT_{joint}", "HOME_FINAL_VEL"),
                2 if axis == "Z" else 5,
            )
            self.assertEqual(ini.getfloat(f"JOINT_{joint}", "HOME_LATCH_VEL"), -1)
            self.assertEqual(ini.getfloat(f"JOINT_{joint}", "HOME_OFFSET"), -5)
            self.assertIn(
                f"setp joint.{joint}.home-backoff-vel [JOINT_{joint}]HOME_BACKOFF_VEL",
                hal,
            )
            self.assertEqual(ini.getfloat(f"AXIS_{axis}", "MAX_LIMIT"), travel - 10)
            self.assertEqual(ini.getfloat(f"AXIS_{axis}", "MIN_LIMIT"), -0.1)
        self.assertEqual(
            [ini.getfloat(f"JOINT_{j}", "STEP_SCALE") for j in range(3)],
            [200, 200, -200],
        )
        self.assertEqual(ini["BETTERCNC_HOMING"]["MOTOR_MAPPING_VERIFIED"], "YES")
        self.assertEqual(ini["BETTERCNC_HOMING"]["MOTOR_DIRECTIONS_VERIFIED"], "YES")
        self.assertEqual(
            ini["RS274NGC"]["PARAMETER_FILE"],
            "/var/lib/betterlinuxcnc/machine/linuxcnc.var",
        )
        self.assertEqual(
            ini["EMCIO"]["TOOL_TABLE"], "/var/lib/betterlinuxcnc/machine/tool.tbl"
        )
        manifest = json.loads((self.machine / "betterlinuxcnc-homing.json").read_text())
        self.assertEqual(
            manifest["motionAcceptance"], "pending-empty-table-parallel-test"
        )
        self.assertEqual(manifest["stepgenByAxis"], {"X": 1, "Y": 0, "Z": 2})
        self.assertEqual(
            manifest["sourceCommit"],
            json.loads(self.metadata.read_text())["vendor"]["commit"],
        )
        for name in (
            "custom.hal",
            "custom_postgui.hal",
            "qt_postgui.hal",
            "shutdown.hal",
        ):
            self.assertEqual((self.machine / name).read_bytes(), fixture_bytes(name))
        current = self.contents()
        again = self.invoke()
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertIn("already-current", again.stdout)
        self.assertEqual(self.contents(), current)
        self.assertEqual(list(self.config.glob(".axis-upgrade-*")), [])

    def test_v4_upgrade_keeps_confirmed_axis_mapping_and_origin(self):
        shutil.rmtree(self.machine)
        write_fixture(self.machine, FIXTURE.with_name("zhulong-installed-v4.json"))
        # The same public assertions must hold for both v1 and v4 inputs;
        # in particular a v4 upgrade must not swap the motors a second time.
        self.test_migrates_command_feedback_enable_scale_and_home_switches_together()
        ini = configparser.ConfigParser(strict=False, interpolation=None)
        ini.read(self.machine / "烛龙V2.ini")
        for joint, axis in enumerate("XYZ"):
            self.assertEqual(ini.getfloat(f"JOINT_{joint}", "HOME"), 0)
            minimum = ini.getfloat(f"JOINT_{joint}", "MIN_LIMIT")
            self.assertLess(minimum, -7.629394360719743e-08)
            self.assertGreater(minimum, ini.getfloat(f"JOINT_{joint}", "HOME_OFFSET"))
            self.assertEqual(ini.getfloat(f"AXIS_{axis}", "MIN_LIMIT"), minimum)

    def test_preserves_generated_axis_profiles_and_rejects_changed_evidence(self):
        self.assertEqual(self.invoke().returncode, 0)
        original = self.contents()
        base = original["烛龙V2.ini"].decode()
        script = """
import json, sys
sys.path.insert(0, sys.argv[1])
from axis_configuration import generate, hal_files
data = json.load(sys.stdin)
base = data['烛龙V2.ini']
names = hal_files(base)
ini, hal = generate(base, {name: data[name] for name in names}, int(sys.argv[2]))
print(json.dumps({'ini': ini, 'hal': hal, 'names': names}))
"""
        for count in (3, 4, 5):
            with self.subTest(count=count):
                generated = json.loads(
                    subprocess.check_output(
                        [sys.executable, "-I", "-c", script, str(MODULE), str(count)],
                        input=json.dumps({k: v.decode() for k, v in original.items()}),
                        text=True,
                    )
                )
                files = dict(original)
                files["烛龙V2.ini"] = generated["ini"].encode()
                files.update({k: v.encode() for k, v in generated["hal"].items()})
                files[".axis-settings-source.json"] = json.dumps(
                    {
                        "schema_version": 1,
                        "ini": "烛龙V2.ini",
                        "base_ini": base,
                        "accepted_ini_hashes": [
                            hashlib.sha256(files["烛龙V2.ini"]).hexdigest()
                        ],
                        "hal_hashes": {
                            name: hashlib.sha256(original[name]).hexdigest()
                            for name in generated["names"]
                        },
                    }
                ).encode()
                for path in self.machine.iterdir():
                    path.unlink()
                for name, data in files.items():
                    (self.machine / name).write_bytes(data)
                result = self.invoke()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("already-current", result.stdout)
                self.assertEqual(self.contents(), files)
                for name in ("烛龙V2.ini", "custom.hal", *generated["hal"]):
                    (self.machine / name).write_bytes(files[name] + b"\n# changed\n")
                    self.assertNotEqual(self.invoke().returncode, 0)
                    (self.machine / name).write_bytes(files[name])

    def test_refuses_live_core_unknown_files_and_modified_source_without_partial_changes(
        self,
    ):
        for problem in ("core", "socket", "changed", "extra", "module", "write"):
            with self.subTest(problem=problem):
                shutil.rmtree(self.machine)
                write_fixture(self.machine)
                path = None
                if problem in ("core", "socket"):
                    path = self.root / (
                        "tmp/linuxcnc.lock"
                        if problem == "core"
                        else "run/user/1001/betterlinuxcnc/control.sock"
                    )
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.touch()
                if problem == "changed":
                    (self.machine / "custom.hal").write_text("# unreviewed change\n")
                if problem == "extra":
                    (self.machine / "extra.hal").write_text("# unreviewed include\n")
                metadata = self.metadata.read_bytes()
                if problem == "module":
                    self.metadata.unlink()
                before = self.contents()
                result = self.invoke("write" if problem == "write" else "")
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertEqual(before, self.contents())
                self.assertEqual(list(self.config.glob(".axis-upgrade-*")), [])
                self.metadata.write_bytes(metadata)
                if path:
                    path.unlink()

    def test_rejects_symlink_and_modified_migrated_profile(self):
        target = self.machine / "custom.hal"
        target.unlink()
        outside = self.root / "outside.hal"
        outside.write_bytes(fixture_bytes("custom.hal"))
        target.symlink_to(outside)
        self.assertNotEqual(self.invoke().returncode, 0)
        target.unlink()
        target.write_bytes(fixture_bytes("custom.hal"))
        self.assertEqual(self.invoke().returncode, 0)
        target.write_text("# changed after migration\n")
        self.assertNotEqual(self.invoke().returncode, 0)


if __name__ == "__main__":
    unittest.main()
