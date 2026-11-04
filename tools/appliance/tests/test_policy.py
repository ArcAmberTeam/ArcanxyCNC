"""Effective SSH restrictions and rollback, without changing host policy."""

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("appliance_policy", MODULE / "_policy.py")
policy = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(policy)

# OpenSSH emits array settings on separate lines. Do not derive this fixture
# from the expected policy: that would hide parser mistakes in the real output.
EFFECTIVE = """hostkey /etc/ssh/ssh_host_rsa_key
hostkey /etc/ssh/ssh_host_ed25519_key
listenaddress [::]:22
listenaddress 0.0.0.0:22
permitrootlogin no
permitemptypasswords no
passwordauthentication yes
pubkeyauthentication no
authenticationmethods password
kbdinteractiveauthentication no
permituserenvironment no
permituserrc no
permittty yes
permittunnel no
disableforwarding yes
x11forwarding no
allowusers cnc-maint
denyusers root
denyusers linuxcnc
denyusers teto
forcecommand /usr/bin/python3 -I /usr/lib/betterlinuxcnc/appliance/maintenance.py
"""


class PolicyTests(unittest.TestCase):
    def result(self, changes=None):
        changes = changes or {}
        lines = [
            line for line in EFFECTIVE.splitlines() if line.split()[0] not in changes
        ]
        lines.extend(f"{key} {value}" for key, value in changes.items())
        output = "\n".join(lines)
        return subprocess.CompletedProcess([], 0, output, "")

    def test_effective_policy_checks_maintenance_and_denied_identities(self):
        with patch.object(policy.subprocess, "run", return_value=self.result()) as run:
            policy.validate_ssh(Path("/test/sshd_config"))
        self.assertEqual(run.call_count, 4)
        for call in run.call_args_list:
            command = call.args[0]
            self.assertIn("-T", command)
            self.assertIn("/test/sshd_config", command)
        contexts = [call.args[0][-1] for call in run.call_args_list]
        self.assertEqual(
            {context.split(",")[0] for context in contexts},
            {"user=cnc-maint", "user=linuxcnc", "user=teto", "user=root"},
        )

    def test_syntax_success_cannot_hide_unrestricted_ssh(self):
        for changes in (
            {"forcecommand": "none"},
            {"allowusers": "cnc-maint teto"},
            {"denyusers": "root linuxcnc"},
            {"disableforwarding": "no"},
            {"permittty": "no"},
            {"permitrootlogin": "yes"},
            {"authenticationmethods": "any"},
        ):
            with (
                self.subTest(changes=changes),
                patch.object(
                    policy.subprocess, "run", return_value=self.result(changes)
                ),
                self.assertRaisesRegex(ValueError, "Effective SSH policy mismatch"),
            ):
                policy.validate_ssh()

    def test_upgrade_recognizes_legacy_pair_preserves_custom_policy_and_is_repeatable(
        self,
    ):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            self.assertEqual(
                policy.upgrade_maintenance(root), "unrecognized policy preserved"
            )
            policy.install(root)
            ssh = root / "etc/ssh/sshd_config"
            sudo = root / "etc/sudoers"
            current_ssh, current_sudo = ssh.read_text(), sudo.read_text()
            legacy_ssh = current_ssh.replace("PermitTTY yes", "PermitTTY no")
            legacy_sudo = "\n".join(
                line for line in current_sudo.split("\n") if "pa-config" not in line
            )
            ssh.write_text(legacy_ssh)
            sudo.write_text(legacy_sudo + "# onsite customization\n")
            self.assertEqual(
                policy.upgrade_maintenance(root), "unrecognized policy preserved"
            )
            self.assertEqual(ssh.read_text(), legacy_ssh)
            sudo.write_text(legacy_sudo)
            self.assertEqual(policy.upgrade_maintenance(root), "upgraded")
            self.assertEqual(ssh.read_text(), current_ssh)
            self.assertEqual(sudo.read_text(), current_sudo)
            self.assertEqual(policy.upgrade_maintenance(root), "current")
            backups = list(
                (root / "var/lib/betterlinuxcnc/recovery").glob(
                    "*-pa-policy/policies.json"
                )
            )
            self.assertEqual(len(backups), 1)
            import json

            saved = {
                item["path"]: item["content"]
                for item in json.loads(backups[0].read_text())
            }
            self.assertEqual(saved["/etc/ssh/sshd_config"], legacy_ssh)
            self.assertEqual(saved["/etc/sudoers"], legacy_sudo)

    def test_fixed_policy_removes_override_sources_and_preserves_original(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ssh = root / "etc/ssh/sshd_config"
            ssh.parent.mkdir(parents=True)
            original = "Include /etc/ssh/custom.conf\nMatch User teto\n PermitTTY yes\n"
            ssh.write_text(original)
            recovery = policy.install(root)
            self.assertTrue((recovery / "policies.json").is_file())
            directives = [
                line.split()[0].lower()
                for line in ssh.read_text().splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            ]
            self.assertNotIn("include", directives)
            self.assertNotIn("match", directives)
            self.assertEqual((root / "etc/sudoers").stat().st_mode & 0o777, 0o440)
            self.assertNotIn("@includedir", (root / "etc/sudoers").read_text())
            import json

            policy.restore(json.loads((recovery / "policies.json").read_text()), root)
            self.assertEqual(ssh.read_text(), original)
            self.assertFalse((root / "etc/sudoers").exists())


if __name__ == "__main__":
    unittest.main()
