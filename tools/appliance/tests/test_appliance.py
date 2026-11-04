"""Public provisioning and forced-command contracts; no host administration."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]


class ApplianceTests(unittest.TestCase):
    def cli(self, *args):
        return subprocess.run(
            [sys.executable, "-I", str(MODULE / "main.py"), *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )

    def test_plan_has_system_paths_and_no_embedded_password(self):
        result = self.cli("plan")
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.assertEqual(plan["operator"], "linuxcnc")
        self.assertEqual(plan["config"], "/etc/betterlinuxcnc")
        self.assertFalse(plan["passwordInPackage"])
        self.assertFalse(plan["automaticActivation"])

    def test_ssh_accepts_only_exact_read_only_vocabulary(self):
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / "executed"
            requests = (
                f"logs; touch {marker}",
                "sh",
                "pa manage sudo open extra",
                "internal-sftp",
                "scp -t /tmp/file",
                "logs /etc/shadow",
                "version && id",
            )
            for request in requests:
                result = subprocess.run(
                    [sys.executable, "-I", str(MODULE / "maintenance.py")],
                    env=dict(os.environ, SSH_ORIGINAL_COMMAND=request),
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                self.assertEqual(result.returncode, 64, result.stdout + result.stderr)
                self.assertIn("error", json.loads(result.stdout))
            self.assertFalse(marker.exists())

    def test_stage_preserves_source_and_moves_only_runtime_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            machine = source / "machine"
            machine.mkdir(parents=True)
            (source / "programs").mkdir()
            (source / "programs/demo.ngc").write_text("G21\nM2\n")
            (source / "programs/unsafe.py").write_text(
                "raise RuntimeError('not G-code')"
            )
            (source / "programs/external.py").symlink_to("/etc/passwd")
            (machine / "tool.tbl").write_text("T1 P1 Z0\n")
            (machine / "linuxcnc.var").write_text("5220 1\n")
            original = (
                "[DISPLAY]\nDISPLAY=betterlinuxcnc\nPROGRAM_PREFIX=../programs\n"
                "EDITOR=gedit\nINTRO_TIME=5\n[FILTER]\npy=python\n"
                "[HAL]\nHALFILE=first.hal\nHALFILE=second.hal\n"
                "[AXIS_X]\nMAX_VELOCITY=25\n"
                "[RS274NGC]\nPARAMETER_FILE=linuxcnc.var\n"
                "[EMCIO]\nTOOL_TABLE=tool.tbl\n"
            )
            (machine / "machine.ini").write_text(original)
            config = source / "launcher.json"
            config.write_text(json.dumps({"ini": "machine/machine.ini"}))
            destination = root / "staged"
            result = self.cli(
                "stage",
                "--source-config",
                str(config),
                "--destination",
                str(destination),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((machine / "machine.ini").read_text(), original)
            migrated = (
                destination / "etc/betterlinuxcnc/machine/machine.ini"
            ).read_text()
            self.assertIn("HALFILE=first.hal\nHALFILE=second.hal", migrated)
            self.assertIn("MAX_VELOCITY=25", migrated)
            self.assertIn(
                "TOOL_TABLE = /var/lib/betterlinuxcnc/machine/tool.tbl", migrated
            )
            self.assertIn("# Disabled in dedicated CNC mode: py=python", migrated)
            programs = destination / "var/lib/betterlinuxcnc/programs"
            self.assertEqual([p.name for p in programs.iterdir()], ["demo.ngc"])
            again = self.cli(
                "stage",
                "--source-config",
                str(config),
                "--destination",
                str(destination),
            )
            self.assertNotEqual(again.returncode, 0)


if __name__ == "__main__":
    unittest.main()
