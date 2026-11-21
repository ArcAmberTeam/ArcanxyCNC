"""Exercise the fixed backup CLI against an isolated filesystem and dpkg adapter."""

import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]
SNAPSHOTS = "var/lib/betterlinuxcnc/recovery/snapshots"
BOOTSTRAP = r"""
import datetime, json, os, runpy, subprocess, sys
from pathlib import Path
from types import SimpleNamespace
script, directory, encoded = sys.argv[1:]
root, options = Path(directory), json.loads(encoded)
real_open, real_fstat = os.open, os.fstat
real_fsync, real_rename = os.fsync, os.rename
commands, corrupt = [], set()
os.geteuid = lambda: options.get('euid', 0)

def opened(path, flags, *args, **kwargs):
    if path == '/':
        path = str(root)
    elif os.path.isabs(path):
        raise AssertionError('unexpected absolute open')
    if options.get('race') == path and not flags & os.O_CREAT:
        options.pop('race')
        parent = kwargs['dir_fd']
        os.rename(path, path + '.original', src_dir_fd=parent, dst_dir_fd=parent)
        os.symlink(str(root.parent / 'outside'), path, dir_fd=parent)
    descriptor = real_open(path, flags, *args, **kwargs)
    if options.get('corrupt') and path == 'machine.var' and flags & os.O_WRONLY:
        corrupt.add(descriptor)
    return descriptor

def info(descriptor):
    original = real_fstat(descriptor)
    values = {name: getattr(original, name) for name in dir(original) if name.startswith('st_')}
    values['st_uid'] = values['st_gid'] = 0
    if options.get('unsafe_parent') and original.st_ino == (root / 'var/lib').stat().st_ino:
        values['st_uid'] = 1000
    return SimpleNamespace(**values)

def sync(descriptor):
    if descriptor in corrupt:
        corrupt.remove(descriptor)
        os.lseek(descriptor, 0, os.SEEK_SET)
        os.write(descriptor, b'X')
    return real_fsync(descriptor)

def rename(source, destination, **kwargs):
    if options.get('publish_failure') and str(source).startswith('.snapshot-'):
        raise OSError(5, 'confidential filename or content must never reach stderr')
    return real_rename(source, destination, **kwargs)

def command(args, **kwargs):
    assert args == ['/usr/bin/dpkg-query', '-W', '-f=${Version}', 'betterlinuxcnc']
    assert kwargs['env'] == {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C'}
    commands.append(args)
    return SimpleNamespace(stdout=options.get('version', '26.10.26.1'), returncode=0)

os.open, os.fstat, os.fsync, os.rename = opened, info, sync, rename
subprocess.run = command
if options.get('no_space'):
    os.fstatvfs = lambda descriptor: SimpleNamespace(f_bavail=0, f_frsize=4096)
if 'time' in options:
    original_datetime = datetime.datetime
    class Clock(original_datetime):
        @classmethod
        def now(cls, tz=None):
            return cls.fromisoformat(options['time']).replace(tzinfo=tz)
    datetime.datetime = Clock
sys.argv = [script, 'backup'] + options.get('arguments', [])
runpy.run_path(script, run_name='__main__')
"""


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve() / "host"
        self.root.mkdir(mode=0o755)
        self.files = {
            "etc/betterlinuxcnc/launcher.json": b'{"machine":"fixed"}\n',
            "etc/betterlinuxcnc/updater.json": b'{"user":"linuxcnc"}\n',
            "etc/betterlinuxcnc/machine/controller.ini": b"[EMC]\nMACHINE = retained\n",
            "var/lib/betterlinuxcnc/machine/machine.var": b"5210 1.25\n",
            "var/lib/betterlinuxcnc/machine/tool.tbl": b"T1 P1 Z2.5\n",
            "etc/ssh/sshd_config": b"AllowUsers cnc-maint\n",
            "etc/sudoers": b"root ALL=(ALL:ALL) ALL\n",
        }
        for path, contents in self.files.items():
            self.write(path, contents)
        (self.root / "var/lib/betterlinuxcnc/machine/empty").mkdir()
        self.snapshots = self.root / SNAPSHOTS

    def write(self, relative, contents):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)
        return path

    def backup(self, *, success=True, **options):
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-c",
                BOOTSTRAP,
                str(MODULE / "main.py"),
                str(self.root),
                json.dumps(options),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(result.stderr, "")
            self.assertEqual(len(result.stdout.splitlines()), 1)
            return json.loads(result.stdout)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertNotIn("Traceback", result.stderr)
        return result

    def snapshot(self, result):
        return self.root / result["snapshot"].lstrip("/")

    def assert_no_staging(self):
        if self.snapshots.exists():
            self.assertFalse(list(self.snapshots.glob(".snapshot-*")))

    def test_fixed_sources_hashes_empty_directories_and_private_permissions(self):
        for excluded in (
            "etc/shadow",
            "etc/ssh/ssh_host_ed25519_key",
            "var/lib/betterlinuxcnc/programs/part.ngc",
            "var/lib/betterlinuxcnc/inbox/job.ngc",
            "var/cache/betterlinuxcnc/user/cache",
        ):
            self.write(excluded, b"excluded secret data\n")
        result = self.backup()
        snapshot = self.snapshot(result)
        manifest = json.loads((snapshot / "manifest.json").read_text())
        self.assertEqual(manifest["sourceVersion"], "26.10.26.1")
        self.assertEqual(manifest["format"], "betterlinuxcnc-snapshot-v1")
        self.assertEqual(manifest["package"], "betterlinuxcnc")
        self.assertEqual(snapshot.name, manifest["createdUtc"] + "-26.10.26.1")
        self.assertEqual(result["files"], len(self.files))
        self.assertEqual(
            {entry["path"] for entry in manifest["files"]},
            {"/" + path for path in self.files},
        )
        for entry in manifest["files"]:
            content = self.files[entry["path"].lstrip("/")]
            self.assertEqual(entry["size"], len(content))
            self.assertEqual(entry["sha256"], hashlib.sha256(content).hexdigest())
            self.assertEqual(
                (snapshot / "files" / entry["path"].lstrip("/")).read_bytes(), content
            )
        self.assertTrue(
            (snapshot / "files/var/lib/betterlinuxcnc/machine/empty").is_dir()
        )
        for directory in (self.snapshots.parent, self.snapshots, snapshot):
            self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)
        for path in snapshot.rglob("*"):
            self.assertEqual(
                stat.S_IMODE(path.stat().st_mode), 0o700 if path.is_dir() else 0o600
            )
        self.assert_no_staging()

    def test_retention_keeps_new_and_latest_two_old_but_preserves_foreign_backups(self):
        recovery = self.snapshots.parent
        legacy = recovery / "legacy-before-demo"
        legacy.mkdir(parents=True, mode=0o700)
        (legacy / "keep").write_bytes(b"old machine data")
        foreign = self.snapshots / "20200101T000000000000Z-1.0"
        foreign.mkdir(parents=True, mode=0o700)
        (foreign / "manifest.json").write_text('{"format":"different-tool"}')
        results = [self.backup(time=f"2026-10-26T01:00:0{index}") for index in range(4)]
        self.assertFalse(self.snapshot(results[0]).exists())
        for result in results[1:]:
            self.assertTrue(self.snapshot(result).exists())
        rewind = self.backup(time="2025-01-01T00:00:00")
        self.assertTrue(self.snapshot(rewind).exists())
        self.assertFalse(self.snapshot(results[1]).exists())
        self.assertTrue(self.snapshot(results[2]).exists())
        self.assertTrue(self.snapshot(results[3]).exists())
        self.assertEqual((legacy / "keep").read_bytes(), b"old machine data")
        self.assertTrue(foreign.exists())

    def test_failure_never_prunes_valid_old_snapshots_or_prints_contents(self):
        old = [self.backup(time=f"2026-10-26T02:00:0{index}") for index in range(3)]
        for options in (
            {"no_space": True},
            {"corrupt": True},
            {"publish_failure": True},
            {"version": "secret/version"},
        ):
            with self.subTest(options=options):
                result = self.backup(success=False, **options)
                self.assertNotIn("confidential", result.stderr)
                self.assertNotIn("secret/version", result.stderr)
                for previous in old:
                    self.assertTrue(self.snapshot(previous).exists())
                self.assert_no_staging()

    def test_symlink_hardlink_and_fifo_sources_are_refused(self):
        outside = self.root.parent / "outside"
        outside.write_bytes(b"private outside content")
        suspect = self.root / "var/lib/betterlinuxcnc/machine/suspect"
        for kind in ("symlink", "hardlink", "fifo"):
            with self.subTest(kind=kind):
                if kind == "symlink":
                    suspect.symlink_to(outside)
                elif kind == "hardlink":
                    os.link(outside, suspect)
                else:
                    os.mkfifo(suspect)
                try:
                    result = self.backup(success=False)
                    self.assertNotIn("private outside content", result.stderr)
                    self.assert_no_staging()
                finally:
                    suspect.unlink()

    def test_parent_symlink_and_open_time_replacement_cannot_escape(self):
        outside = self.root.parent / "outside"
        outside.mkdir()
        (outside / "secret").write_bytes(b"never read")
        self.backup(success=False, race="machine")
        self.assertEqual((outside / "secret").read_bytes(), b"never read")
        self.assertEqual(list(outside.iterdir()), [outside / "secret"])
        self.assert_no_staging()

    def test_file_replacement_between_stat_and_open_is_refused(self):
        outside = self.root.parent / "outside"
        outside.write_bytes(b"never read")
        result = self.backup(success=False, race="machine.var")
        self.assertNotIn("never read", result.stderr)
        self.assert_no_staging()

    def test_untrusted_destination_parent_is_refused(self):
        self.backup(success=False, unsafe_parent=True)
        self.assertFalse(self.snapshots.exists())

    def test_oversize_source_and_missing_required_source_preserve_previous(self):
        old = self.backup()
        oversized = self.root / "var/lib/betterlinuxcnc/machine/oversized"
        with oversized.open("wb") as output:
            output.truncate(64 * 1024 * 1024 + 1)
        self.backup(success=False)
        oversized.unlink()
        (self.root / "var/lib/betterlinuxcnc/machine").rename(
            self.root / "saved-machine"
        )
        self.backup(success=False)
        self.assertTrue(self.snapshot(old).exists())
        self.assert_no_staging()

    def test_root_gate_and_no_arbitrary_path_arguments(self):
        self.backup(success=False, euid=1000)
        self.assertFalse(self.snapshots.exists())
        self.backup(success=False, arguments=["--destination", "/tmp/arbitrary"])
        self.assertFalse(self.snapshots.exists())


if __name__ == "__main__":
    unittest.main()
