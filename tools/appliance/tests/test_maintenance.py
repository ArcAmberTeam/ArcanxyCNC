"""Bounded SSH log access over real temporary files; never administer the host."""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "maintenance.py"
SPEC = importlib.util.spec_from_file_location("appliance_maintenance", SCRIPT)
maintenance = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(maintenance)


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.root = self.base / "var/log/betterlinuxcnc/launcher"
        self.root.mkdir(parents=True)
        self.run = self.root / "20261026-120000-123"
        self.run.mkdir()
        self.log = self.run / "controller-1.log"
        self.log.write_text("allowed log\n")
        self.outside = self.base / "private"
        self.outside.mkdir()
        (self.outside / self.log.name).write_text("PRIVATE CONTENT\n")
        root_patch = patch.object(maintenance, "LOG_ROOT", self.root)
        root_patch.start()
        self.addCleanup(root_patch.stop)

    def assert_no_private_content(self, result):
        self.assertNotIn("PRIVATE CONTENT", json.dumps(result))

    def test_logs_contain_only_named_regular_logs_and_bounded_tails(self):
        (self.run / "state.json").write_text("PRIVATE CONTENT")
        (self.run / "controller-secret.log").write_text("PRIVATE CONTENT")
        (self.run / "controller-2.log").symlink_to(self.outside / self.log.name)
        os.link(self.outside / self.log.name, self.run / "controller-3.log")
        os.mkfifo(self.run / "linuxcnc-4.log")
        result = maintenance.logs()
        self.assertEqual(
            result,
            [{"file": f"{self.run.name}/{self.log.name}", "tail": "allowed log\n"}],
        )
        for generation in range(5, 25):
            (self.run / f"linuxcnc-{generation}.log").write_bytes(b"x" * 70000)
        result = maintenance.logs()
        self.assertLessEqual(len(result), 12)
        self.assertLessEqual(sum(len(item["tail"]) for item in result), 262144)
        self.assertTrue(all(len(item["tail"]) <= 65536 for item in result))
        self.assert_no_private_content(result)

    def test_only_three_latest_run_directories_are_read(self):
        for number in range(5):
            run = self.root / f"20261026-120000-{200 + number}"
            run.mkdir()
            (run / "linuxcnc-1.log").write_text(str(number))
            os.utime(run, ns=(number + 1, number + 1))
        os.utime(self.run, ns=(0, 0))
        self.assertEqual(
            {entry["file"].split("/")[0] for entry in maintenance.logs()},
            {f"20261026-120000-{number}" for number in (202, 203, 204)},
        )

    def test_symlink_at_each_log_root_component_is_rejected(self):
        relative = self.root.relative_to(self.base)
        for index in range(1, len(relative.parts) + 1):
            with self.subTest(component=index):
                path = self.base.joinpath(*relative.parts[:index])
                moved = path.with_name(path.name + "-original")
                path.rename(moved)
                try:
                    path.symlink_to(moved, target_is_directory=True)
                    self.assertEqual(maintenance.logs(), [])
                finally:
                    path.unlink()
                    moved.rename(path)

    def test_symlink_run_directory_is_rejected(self):
        (self.root / "20261026-130000-999").symlink_to(
            self.outside, target_is_directory=True
        )
        self.assert_no_private_content(maintenance.logs())

    def test_parent_replacement_after_open_stays_on_original_descriptor(self):
        original_open = os.open
        original_root = self.root.with_name("launcher-original")
        replaced = False

        def replacing_open(path, flags, *args, **kwargs):
            nonlocal replaced
            descriptor = original_open(path, flags, *args, **kwargs)
            if path == "launcher" and kwargs.get("dir_fd") is not None and not replaced:
                replaced = True
                self.root.rename(original_root)
                self.root.symlink_to(self.outside, target_is_directory=True)
            return descriptor

        with patch.object(maintenance.os, "open", side_effect=replacing_open):
            result = maintenance.logs()
        self.assertTrue(replaced)
        self.assertEqual(result[0]["tail"], "allowed log\n")
        self.assert_no_private_content(result)

    def test_run_replaced_with_symlink_between_listing_and_open_is_rejected(self):
        original_open = os.open
        replaced = False

        def replacing_open(path, flags, *args, **kwargs):
            nonlocal replaced
            if (
                path == self.run.name
                and kwargs.get("dir_fd") is not None
                and not replaced
            ):
                replaced = True
                self.run.rename(self.run.with_name("old-run"))
                self.run.symlink_to(self.outside, target_is_directory=True)
            return original_open(path, flags, *args, **kwargs)

        with patch.object(maintenance.os, "open", side_effect=replacing_open):
            self.assertEqual(maintenance.logs(), [])
        self.assertTrue(replaced)

    def test_open_run_replacement_does_not_redirect_its_log_open(self):
        original_open = os.open
        replaced = False

        def replacing_open(path, flags, *args, **kwargs):
            nonlocal replaced
            descriptor = original_open(path, flags, *args, **kwargs)
            if (
                path == self.run.name
                and kwargs.get("dir_fd") is not None
                and not replaced
            ):
                replaced = True
                self.run.rename(self.run.with_name("old-run"))
                self.run.symlink_to(self.outside, target_is_directory=True)
            return descriptor

        with patch.object(maintenance.os, "open", side_effect=replacing_open):
            result = maintenance.logs()
        self.assertTrue(replaced)
        self.assertEqual(result[0]["tail"], "allowed log\n")
        self.assert_no_private_content(result)

    def test_log_replaced_with_symlink_or_regular_file_is_rejected(self):
        original_open = os.open
        for symlink in (True, False):
            with self.subTest(symlink=symlink):
                replaced = False

                def replacing_open(path, flags, *args, symlink=symlink, **kwargs):
                    nonlocal replaced
                    if (
                        path == self.log.name
                        and kwargs.get("dir_fd") is not None
                        and not replaced
                    ):
                        replaced = True
                        self.log.rename(self.log.with_name("original.txt"))
                        if symlink:
                            self.log.symlink_to(self.outside / self.log.name)
                        else:
                            self.log.write_text("PRIVATE CONTENT\n")
                    return original_open(path, flags, *args, **kwargs)

                try:
                    with patch.object(
                        maintenance.os, "open", side_effect=replacing_open
                    ):
                        self.assertEqual(maintenance.logs(), [])
                    self.assertTrue(replaced)
                finally:
                    self.log.unlink()
                    self.log.with_name("original.txt").rename(self.log)

    def test_public_cli_rejects_path_arguments_and_shell_commands(self):
        for request in (
            "pa manage /etc/shadow",
            "pa manage ../ini",
            "pa manage ini extra",
            "pa manage ini; id",
            "pa manage $(id)",
            "pa execute ini",
            "logs /etc/shadow",
            "logs; id",
            "cat /etc/shadow",
            "$(id)",
            "sudo logs",
        ):
            result = subprocess.run(
                [sys.executable, "-I", str(SCRIPT)],
                env=dict(os.environ, SSH_ORIGINAL_COMMAND=request),
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            self.assertEqual(result.returncode, 64, result.stdout + result.stderr)
            self.assertIn("error", json.loads(result.stdout))

    def test_axis_status_and_logs_use_only_the_fixed_read_only_cli(self):
        for requested in ("axis-status", "logs"):
            with (
                patch.object(sys, "argv", [str(SCRIPT)]),
                patch.dict(os.environ, {"SSH_ORIGINAL_COMMAND": requested}),
                patch.object(
                    maintenance, "command", return_value={"exit": 0}
                ) as command,
                patch("builtins.print"),
            ):
                self.assertEqual(maintenance.main(), 0)
            command.assert_called_once_with(
                ["/usr/sbin/betterlinuxcnc-appliance", "axis-profile", "status"]
            )

    def test_management_routes_exact_targets_without_a_shell_or_environment_inheritance(
        self,
    ):
        for target in ("ini", "launcher.json"):
            with self.subTest(target=target):
                with (
                    patch.object(sys, "argv", [str(SCRIPT)]),
                    patch.dict(
                        os.environ, {"SSH_ORIGINAL_COMMAND": f"pa manage {target}"}
                    ),
                    patch.object(
                        maintenance.os, "execve", side_effect=SystemExit(0)
                    ) as execute,
                    self.assertRaises(SystemExit),
                ):
                    maintenance.main()
                execute.assert_called_once_with(
                    "/usr/bin/pa",
                    ["pa", "manage", target],
                    {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
                )


if __name__ == "__main__":
    unittest.main()
