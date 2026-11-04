"""Public provision CLI with isolated OS adapters; never change host identities."""

import json
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1]

# Exercise the public CLI against real temporary directories. Account databases,
# ownership changes and administrative processes are replaced at the OS boundary.
# Opening '/' is anchored to the temporary root before any provisioning code runs.
BOOTSTRAP = r"""
import grp, json, os, pwd, runpy, stat, subprocess, sys
from pathlib import Path
from types import SimpleNamespace
script, root, options = sys.argv[1:]
root = Path(root).resolve()
options = json.loads(options)
sys.platform = 'linux'
commands = []
users = {'root': {'uid': 0, 'gid': 0, 'home': '/root', 'shell': '/bin/sh', 'password': 'root-fixture'}}
users.update(options.get('users', {}))
groups = {
    'root': {'gid': 0, 'members': []},
    'video': {'gid': 44, 'members': []},
    'render': {'gid': 109, 'members': []},
    'audio': {'gid': 29, 'members': []},
    'realtime': {'gid': 106, 'members': []},
}
groups.update(options.get('groups', {}))
memberships = options.get('memberships', {})
owners = {}
real_open, real_fstat = os.open, os.fstat
real_is_dir = Path.is_dir
real_lstat = Path.lstat
def policy_lstat(path, *args, **kwargs):
    if str(path) in ('/etc/ssh/sshd_config', '/etc/sudoers', '/etc/ssh', '/etc'):
        path = root / str(path).lstrip('/')
    return real_lstat(path, *args, **kwargs)
Path.lstat = policy_lstat
for relative, owner in options.get('owners', {}).items():
    info = (root / relative).stat()
    owners[(info.st_dev, info.st_ino)] = owner

def account(name):
    entry = users[name]
    return SimpleNamespace(pw_name=name, pw_uid=entry['uid'], pw_gid=entry['gid'],
        pw_dir=entry['home'], pw_shell=entry['shell'], pw_passwd=entry['password'])
def group(name):
    entry = groups[name]
    return SimpleNamespace(gr_name=name, gr_gid=entry['gid'], gr_mem=entry['members'])
pwd.getpwnam = account
pwd.getpwall = lambda: [account(name) for name in users]
grp.getgrnam = group
grp.getgrall = lambda: [group(name) for name in groups]
os.geteuid = lambda: options.get('euid', 0)
os.getgrouplist = lambda name, primary: [primary] + [groups[g]['gid'] for g in memberships.get(name, [])]

def opened(path, flags, *args, **kwargs):
    if path == '/':
        path = str(root)
    elif os.path.isabs(path):
        raise AssertionError('unexpected absolute open: ' + str(path))
    return real_open(path, flags, *args, **kwargs)
def info(descriptor):
    original = real_fstat(descriptor)
    values = list(original)
    values[4:6] = owners.get((original.st_dev, original.st_ino), (0, 0))
    return os.stat_result(values)
def chown(descriptor, uid, gid):
    original = real_fstat(descriptor)
    owners[(original.st_dev, original.st_ino)] = (uid, gid)
os.open, os.fstat, os.fchown = opened, info, chown
Path.is_dir = lambda path: options.get('systemd', False) if str(path) == '/run/systemd/system' else real_is_dir(path)

def run(args, **kwargs):
    args = list(args)
    commands.append(args)
    if args[:2] == ['/usr/sbin/groupadd', '--system']:
        assert args[-1] == 'cnc-logs'
        groups['cnc-logs'] = {'gid': 986, 'members': []}
    elif args[0] == '/usr/sbin/useradd':
        name = args[-1]
        assert name in ('linuxcnc', 'cnc-maint') and name not in users
        assert '--no-create-home' in args and '--password' not in args
        uid = 1100 if name == 'linuxcnc' else 1101
        users[name] = {'uid': uid, 'gid': uid, 'home': args[args.index('--home-dir') + 1],
            'shell': args[args.index('--shell') + 1], 'password': '!'}
        groups[name] = {'gid': uid, 'members': []}
    elif args[:2] == ['/usr/sbin/usermod', '--groups']:
        name = args[-1]
        memberships[name] = args[2].split(',')
        for value in groups.values():
            value['members'] = [member for member in value['members'] if member != name]
        for group_name in memberships[name]:
            groups[group_name]['members'].append(name)
    elif args == ['/usr/bin/systemctl', 'daemon-reload']:
        assert options.get('systemd', False)
    else:
        raise AssertionError('unexpected administrative command: ' + repr(args))
    return SimpleNamespace(returncode=0, stdout='', stderr='')
subprocess.run = run
statuses = []
for attempt in range(options.get('repeats', 1)):
    sys.argv = [script, 'provision']
    try:
        runpy.run_path(script, run_name='__main__')
    except SystemExit as error:
        statuses.append(error.code)
    else:
        statuses.append(0)
directories = {}
for path in root.rglob('*'):
    if path.is_symlink() or not real_is_dir(path):
        continue
    original = path.stat()
    uid, gid = owners.get((original.st_dev, original.st_ino), (0, 0))
    directories[str(path.relative_to(root))] = [uid, gid, stat.S_IMODE(original.st_mode)]
print(json.dumps({'statuses': statuses, 'commands': commands, 'users': users,
    'memberships': memberships, 'directories': directories}))
"""


class ProvisionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve() / "host"
        self.root.mkdir()

    def provision(self, **options):
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
            timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout.splitlines()[-1])

    def existing_users(self):
        return {
            "linuxcnc": {
                "uid": 1100,
                "gid": 1100,
                "home": "/var/lib/betterlinuxcnc/home",
                "shell": "/bin/sh",
                "password": "preserved-operator-password",
            },
            "cnc-maint": {
                "uid": 1101,
                "gid": 1101,
                "home": "/var/lib/betterlinuxcnc/maintenance",
                "shell": "/bin/sh",
                "password": "preserved-maintenance-password",
            },
        }

    def existing_groups(self):
        return {
            "linuxcnc": {"gid": 1100, "members": []},
            "cnc-maint": {"gid": 1101, "members": []},
            "cnc-logs": {"gid": 986, "members": []},
        }

    def test_new_install_creates_fixed_accounts_and_minimal_data_permissions(self):
        result = self.provision()
        self.assertEqual(result["statuses"], [0])
        expected = {
            "etc/betterlinuxcnc": [0, 0, 0o755],
            "var/lib/betterlinuxcnc": [0, 0, 0o755],
            "var/lib/betterlinuxcnc/home": [1100, 1100, 0o700],
            "var/lib/betterlinuxcnc/maintenance": [0, 1101, 0o750],
            "var/lib/betterlinuxcnc/programs": [1100, 1100, 0o700],
            "var/lib/betterlinuxcnc/inbox": [1100, 1100, 0o700],
            "var/lib/betterlinuxcnc/machine": [1100, 1100, 0o700],
            "var/cache/betterlinuxcnc/user": [1100, 1100, 0o700],
            "var/cache/betterlinuxcnc/update": [0, 0, 0o700],
            "var/lib/betterlinuxcnc/update": [0, 0, 0o755],
            "var/log/betterlinuxcnc/launcher": [1100, 986, 0o2750],
        }
        for path, permissions in expected.items():
            self.assertEqual(result["directories"][path], permissions, path)
        self.assertEqual(result["memberships"]["cnc-maint"], ["cnc-logs"])
        self.assertEqual(result["users"]["linuxcnc"]["password"], "!")
        self.assertEqual(result["users"]["cnc-maint"]["password"], "!")
        self.assertFalse(
            any(command[0].endswith("systemctl") for command in result["commands"])
        )

    def test_configuration_lease_is_root_owned_and_symlink_is_rejected(self):
        result = self.provision(repeats=2)
        self.assertEqual(result["statuses"], [0, 0])
        lease = self.root / "var/lib/betterlinuxcnc/configuration.lock"
        self.assertEqual(stat.S_IMODE(lease.stat().st_mode), 0o644)
        original = self.root / "untouched"
        original.write_text("original")
        lease.unlink()
        lease.symlink_to(original)
        result = self.provision()
        self.assertNotEqual(result["statuses"], [0])
        self.assertEqual(original.read_text(), "original")

    def test_repeat_install_preserves_configuration_programs_and_passwords(self):
        preserved = {
            "etc/betterlinuxcnc/launcher.json": b'{"operator":"existing"}\n',
            "etc/betterlinuxcnc/machine/machine.ini": b"[DISPLAY]\n",
            "var/lib/betterlinuxcnc/programs/part.ngc": b"M2\n",
        }
        for relative, data in preserved.items():
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        users = self.existing_users()
        result = self.provision(
            users=users, groups=self.existing_groups(), repeats=2, systemd=True
        )
        self.assertEqual(result["statuses"], [0, 0])
        self.assertEqual(result["users"]["linuxcnc"], users["linuxcnc"])
        self.assertEqual(result["users"]["cnc-maint"], users["cnc-maint"])
        self.assertEqual(
            result["commands"].count(["/usr/bin/systemctl", "daemon-reload"]), 2
        )
        self.assertEqual(
            sum(command[0].endswith("usermod") for command in result["commands"]), 2
        )
        for relative, data in preserved.items():
            self.assertEqual((self.root / relative).read_bytes(), data)
        self.assertFalse((self.root / "etc/ssh").exists())
        self.assertFalse((self.root / "etc/lightdm").exists())

    def test_legacy_package_directory_modes_are_repaired_without_touching_contents(
        self,
    ):
        names = (
            "usr/lib/betterlinuxcnc",
            "usr/share/betterlinuxcnc",
            "usr/share/doc/betterlinuxcnc-qt",
        )
        for name in names:
            path = self.root / name
            path.mkdir(parents=True)
            path.chmod(0o775)
            (path / "retained").write_bytes(b"existing package data")
        result = self.provision(repeats=2)
        self.assertEqual(result["statuses"], [0, 0])
        for name in names:
            self.assertEqual(result["directories"][name], [0, 0, 0o755])
            self.assertEqual(
                (self.root / name / "retained").read_bytes(), b"existing package data"
            )

    def test_non_root_is_rejected_before_any_mutation(self):
        result = self.provision(euid=1000)
        self.assertEqual(result["statuses"], [1])
        self.assertEqual(result["commands"], [])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_existing_privileged_supplementary_groups_are_rejected(self):
        for name in ("sudo", "docker", "disk", "systemd-journal"):
            with self.subTest(group=name):
                groups = self.existing_groups()
                groups[name] = {"gid": 2000, "members": ["linuxcnc"]}
                result = self.provision(
                    users=self.existing_users(),
                    groups=groups,
                    memberships={"linuxcnc": [name]},
                )
                self.assertEqual(result["statuses"], [1])
                self.assertEqual(result["commands"], [])

    def test_existing_account_identity_or_primary_group_cannot_be_repurposed(self):
        for field, value in (
            ("uid", 0),
            ("gid", 0),
            ("home", "/home/existing"),
            ("shell", "/home/existing/shell"),
        ):
            with self.subTest(field=field):
                users = self.existing_users()
                users["linuxcnc"][field] = value
                result = self.provision(users=users, groups=self.existing_groups())
                self.assertEqual(result["statuses"], [1])
                self.assertEqual(result["commands"], [])

    def test_private_identities_and_log_group_cannot_be_shared_with_other_users(self):
        for shared in ("uid", "gid", "log-reader"):
            with self.subTest(shared=shared):
                users = self.existing_users()
                users["unrelated"] = {
                    "uid": 2200,
                    "gid": 2200,
                    "home": "/home/unrelated",
                    "shell": "/bin/sh",
                    "password": "untouched",
                }
                groups = self.existing_groups()
                if shared == "log-reader":
                    groups["cnc-logs"]["members"].append("unrelated")
                else:
                    users["unrelated"][shared] = users["cnc-maint"][shared]
                result = self.provision(users=users, groups=groups)
                self.assertEqual(result["statuses"], [1])
                self.assertEqual(result["commands"], [])

    def test_parent_and_leaf_symlinks_never_redirect_privileged_changes(self):
        outside = self.root.parent / "outside"
        outside.mkdir()
        sentinel = outside / "preserved"
        sentinel.write_text("unchanged")
        outside.chmod(0o750)
        for relative in (
            "var",
            "var/lib",
            "var/lib/betterlinuxcnc",
            "var/lib/betterlinuxcnc/home",
        ):
            with self.subTest(path=relative):
                target = self.root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.symlink_to(outside, target_is_directory=True)
                try:
                    result = self.provision()
                    self.assertEqual(result["statuses"], [1])
                    self.assertEqual(sentinel.read_text(), "unchanged")
                    self.assertEqual(stat.S_IMODE(outside.stat().st_mode), 0o750)
                    self.assertEqual([p.name for p in outside.iterdir()], ["preserved"])
                finally:
                    target.unlink()

    def test_untrusted_parent_or_unrelated_leaf_owner_is_rejected(self):
        for relative in ("var", "var/lib/betterlinuxcnc/home"):
            with self.subTest(path=relative):
                path = self.root / relative
                path.mkdir(parents=True, exist_ok=True)
                result = self.provision(owners={relative: [2000, 2000]})
                self.assertEqual(result["statuses"], [1])

    def test_postinst_only_provisions_on_configure(self):
        postinst = MODULE / "packaging/postinst"
        source = postinst.read_text()
        self.assertIn("exec /usr/sbin/betterlinuxcnc-appliance provision", source)
        for action in ("abort-upgrade", "abort-remove", "abort-deconfigure"):
            result = subprocess.run(
                ["/bin/sh", str(postinst), action], check=False, timeout=5
            )
            self.assertEqual(result.returncode, 0)
        result = subprocess.run(
            ["/bin/sh", str(postinst), "unsupported"], check=False, timeout=5
        )
        self.assertEqual(result.returncode, 1)


if __name__ == "__main__":
    unittest.main()
