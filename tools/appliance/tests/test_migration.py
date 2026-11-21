"""Migration filesystem regressions; all input and output live in temporary roots."""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "appliance_migration", MODULE / "_machine.py"
)
MACHINE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MACHINE)


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="appliance-migration-")
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.source = self.base / "source"
        self.profile = self.source / "machine"
        self.profile.mkdir(parents=True)
        (self.source / "programs").mkdir()
        (self.source / "programs/demo.ngc").write_text("G21\nM2\n")
        self.original = (
            "[DISPLAY]\nDISPLAY=betterlinuxcnc\nPROGRAM_PREFIX=../programs\n"
            "[HAL]\nHALFILE=first.hal\nHALFILE=second.hal\n"
            "[RS274NGC]\nPARAMETER_FILE=state.var\n"
        )
        (self.profile / "machine.ini").write_text(self.original)
        (self.profile / "state.var").write_text("5220 1\n")
        self.config = self.source / "launcher.json"
        self.config.write_text(json.dumps({"ini": "machine/machine.ini"}))

    def root(self):
        root = self.base / "host"
        (root / "etc/betterlinuxcnc").mkdir(parents=True)
        for name in ("programs", "machine", "inbox"):
            (root / "var/lib/betterlinuxcnc" / name).mkdir(parents=True)
        return root

    def cli(self, destination):
        return subprocess.run(
            [
                sys.executable,
                "-I",
                str(MODULE / "main.py"),
                "stage",
                "--source-config",
                str(self.config),
                "--destination",
                str(destination),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )

    def assert_unpublished(self, root):
        self.assertFalse((root / "etc/betterlinuxcnc/machine").exists())
        self.assertFalse((root / "etc/betterlinuxcnc/launcher.json").exists())
        self.assertFalse((root / "etc/betterlinuxcnc/.migration").exists())
        self.assertFalse((root / "var/lib/betterlinuxcnc/.migration").exists())
        self.assertEqual((self.profile / "machine.ini").read_text(), self.original)

    def test_stage_local_ini_without_source_launcher_or_program_prefix(self):
        self.config.unlink()
        ini = self.profile / "machine.ini"
        original = self.original.replace("PROGRAM_PREFIX=../programs\n", "")
        ini.write_text(original)
        for name in ("first.hal", "second.hal"):
            (self.profile / name).write_text("# Local HAL\n")
        destination = self.base / "staged"
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                str(MODULE / "main.py"),
                "stage",
                "--source-ini",
                str(ini),
                "--destination",
                str(destination),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        installed = destination / "etc/betterlinuxcnc"
        self.assertEqual(
            json.loads((installed / "launcher.json").read_text()),
            {"ini": "/etc/betterlinuxcnc/machine/machine.ini"},
        )
        self.assertIn(
            "PROGRAM_PREFIX = /var/lib/betterlinuxcnc/programs",
            (installed / "machine/machine.ini").read_text(),
        )
        self.assertEqual(ini.read_text(), original)
        self.assertFalse(self.config.exists())

    def test_dangling_destination_link_cannot_create_a_file_outside_data(self):
        root = self.root()
        outside = self.base / "must-not-be-created"
        link = root / "var/lib/betterlinuxcnc/machine/state.var"
        link.symlink_to(outside)
        with self.assertRaises((OSError, ValueError)):
            MACHINE.migrate(self.config, root)
        self.assertFalse(outside.exists())
        self.assertTrue(link.is_symlink())
        self.assert_unpublished(root)
        link.unlink()
        MACHINE.migrate(self.config, root)
        self.assertEqual(link.read_text(), "5220 1\n")
        self.assertFalse(outside.exists())

    def test_nonempty_destinations_are_preserved_before_any_publication(self):
        root = self.root()
        existing = root / "var/lib/betterlinuxcnc/programs/keep.ngc"
        existing.write_text("M2\n")
        with self.assertRaises(ValueError):
            MACHINE.migrate(self.config, root)
        self.assertEqual(existing.read_text(), "M2\n")
        self.assert_unpublished(root)
        existing.unlink()
        MACHINE.migrate(self.config, root)
        self.assertTrue((existing.parent / "demo.ngc").is_file())

    def test_untrusted_or_linked_parent_is_rejected(self):
        root = self.root()
        parent = root / "var/lib/betterlinuxcnc"
        parent.chmod(0o777)
        with self.assertRaises(ValueError):
            MACHINE.migrate(self.config, root)
        self.assert_unpublished(root)
        parent.chmod(0o755)
        saved = parent.with_name("original-data")
        parent.rename(saved)
        parent.symlink_to(saved, target_is_directory=True)
        with self.assertRaises(OSError):
            MACHINE.migrate(self.config, root)
        self.assertEqual(list((saved / "machine").iterdir()), [])
        self.assertFalse((root / "etc/betterlinuxcnc/machine").exists())

    def test_cli_failure_removes_preview_and_retry_succeeds(self):
        destination = self.base / "preview"
        forbidden = self.profile / "linked.hal"
        forbidden.symlink_to(self.base / "missing")
        failed = self.cli(destination)
        self.assertNotEqual(failed.returncode, 0)
        self.assertFalse(destination.exists())
        self.assertEqual(list(self.base.glob(".bettercnc-stage-*")), [])
        self.assertTrue(forbidden.is_symlink())
        forbidden.unlink()
        result = self.cli(destination)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.profile / "machine.ini").read_text(), self.original)
        migrated = (destination / "etc/betterlinuxcnc/machine/machine.ini").read_text()
        self.assertIn("HALFILE=first.hal\nHALFILE=second.hal", migrated)

    def test_cli_existing_or_dangling_destination_is_never_followed(self):
        destination = self.base / "preview"
        outside = self.base / "outside"
        destination.symlink_to(outside, target_is_directory=True)
        result = self.cli(destination)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(destination.is_symlink())
        self.assertFalse(outside.exists())

    def test_duplicate_mutable_names_fail_privately_and_can_be_retried(self):
        (self.profile / "other").mkdir()
        (self.profile / "other/state.var").write_text("different state\n")
        ini = self.profile / "machine.ini"
        ini.write_text(self.original + "[TRAJ]\nPOSITION_FILE=other/state.var\n")
        destination = self.base / "preview"
        self.assertNotEqual(self.cli(destination).returncode, 0)
        self.assertFalse(destination.exists())
        self.assertEqual(
            (self.profile / "other/state.var").read_text(), "different state\n"
        )
        ini.write_text(self.original)
        result = self.cli(destination)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_publication_error_restores_old_directories_and_preserves_late_writes(self):
        root = self.root()
        data = root / "var/lib/betterlinuxcnc"
        original_inodes = {
            name: (data / name).stat().st_ino
            for name in ("programs", "machine", "inbox")
        }
        rename = MACHINE._rename
        injected = False

        def fail_once(source, destination):
            nonlocal injected
            if destination == root / "etc/betterlinuxcnc/machine" and not injected:
                injected = True
                # Simulates a writer that obtained access to a published tree.
                (data / "programs/late.ngc").write_text("G0 X1\n")
                raise OSError("injected publication failure")
            return rename(source, destination)

        with (
            patch.object(MACHINE, "_rename", side_effect=fail_once),
            self.assertRaisesRegex(OSError, "publication failure"),
        ):
            MACHINE.migrate(self.config, root)
        self.assert_unpublished(root)
        for name, inode in original_inodes.items():
            self.assertEqual((data / name).stat().st_ino, inode)
        recovered = list(data.glob("migration-recovery-*/new/programs/late.ngc"))
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0].read_text(), "G0 X1\n")
        MACHINE.migrate(self.config, root)
        self.assertTrue((root / "etc/betterlinuxcnc/launcher.json").is_file())

    def test_process_interruption_is_recovered_before_the_next_import(self):
        root = self.root()
        script = """
import importlib.util, os, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location('migration', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
rename = module._rename
root = Path(sys.argv[3])
def interrupted(source, destination):
    rename(source, destination)
    if destination == root / 'var/lib/betterlinuxcnc/programs':
        os._exit(86)
module._rename = interrupted
module.migrate(Path(sys.argv[2]), root)
"""
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-c",
                script,
                str(MODULE / "_machine.py"),
                str(self.config),
                str(root),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(result.returncode, 86, result.stderr)
        self.assertFalse((root / "etc/betterlinuxcnc/launcher.json").exists())
        MACHINE.migrate(self.config, root)
        self.assertTrue((root / "etc/betterlinuxcnc/launcher.json").is_file())
        self.assertEqual((self.profile / "machine.ini").read_text(), self.original)
        self.assertFalse((root / "var/lib/betterlinuxcnc/.migration").exists())


if __name__ == "__main__":
    unittest.main()
