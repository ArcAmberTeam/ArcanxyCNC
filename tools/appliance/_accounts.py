"""Dedicated non-administrative identities and ownership, only used by root."""

import grp
import os
import pwd
import stat
import subprocess
from pathlib import Path

OPERATOR = "linuxcnc"
MAINTENANCE = "cnc-maint"
HOME = Path("/var/lib/betterlinuxcnc/home")
MAINTENANCE_HOME = Path("/var/lib/betterlinuxcnc/maintenance")
DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
HARDWARE_GROUPS = ("video", "render", "audio", "realtime")


def run(*args, **kwargs):
    return subprocess.run(
        args,
        check=True,
        text=True,
        capture_output=True,
        env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8"},
        **kwargs,
    )


def directory(path, owner="root", group="root", mode=0o755):
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts or len(path.parts) < 2:
        raise ValueError("Account directories require a fixed absolute path")
    uid = 0 if owner == "root" else pwd.getpwnam(owner).pw_uid
    gid = 0 if group == "root" else grp.getgrnam(group).gr_gid
    descriptor = os.open("/", DIRECTORY_FLAGS)
    try:
        for component in path.parts[1:]:
            parent = os.fstat(descriptor)
            if parent.st_uid != 0 or parent.st_mode & 0o022:
                raise ValueError(
                    f"Account directory parent is not root-controlled: {path}"
                )
            try:
                os.mkdir(component, 0o755, dir_fd=descriptor)
            except FileExistsError:
                pass
            child = os.open(component, DIRECTORY_FLAGS, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        info = os.fstat(descriptor)
        if info.st_uid not in {0, uid}:
            raise ValueError(f"Account directory belongs to an unrelated user: {path}")
        if (info.st_uid, info.st_gid) != (uid, gid):
            os.fchown(descriptor, uid, gid)
        if stat.S_IMODE(os.fstat(descriptor).st_mode) != mode:
            os.fchmod(descriptor, mode)
    finally:
        os.close(descriptor)


def trusted_group(name):
    group = grp.getgrnam(name)
    if (
        group.gr_name != name
        or group.gr_gid == 0
        or any(
            entry.gr_gid == group.gr_gid and entry.gr_name != name
            for entry in grp.getgrall()
        )
    ):
        raise ValueError(f"Group {name} aliases another or privileged identity")
    return group


def validate_user(name, home, allowed_groups):
    account = pwd.getpwnam(name)
    private_group = trusted_group(name)
    if (
        account.pw_name != name
        or account.pw_uid < 1000
        or account.pw_uid == 65534
        or account.pw_dir != str(home)
        or account.pw_shell != "/bin/sh"
        or account.pw_gid != private_group.gr_gid
        or private_group.gr_gid < 1000
        or any(member != name for member in private_group.gr_mem)
        or any(
            (entry.pw_uid == account.pw_uid or entry.pw_gid == private_group.gr_gid)
            and entry.pw_name != name
            for entry in pwd.getpwall()
        )
    ):
        raise ValueError(f"Existing {name} is not the expected dedicated account")
    allowed = {private_group.gr_gid}
    for group_name in allowed_groups:
        try:
            allowed.add(trusted_group(group_name).gr_gid)
        except KeyError:
            pass
    if not set(os.getgrouplist(name, account.pw_gid)).issubset(allowed):
        raise ValueError(f"Existing {name} has groups outside the dedicated allowlist")
    return account


def create_user(name, home, allowed_groups):
    try:
        pwd.getpwnam(name)
    except KeyError:
        run(
            "/usr/sbin/useradd",
            "--user-group",
            "--no-create-home",
            "--home-dir",
            str(home),
            "--shell",
            "/bin/sh",
            name,
        )
    return validate_user(name, home, allowed_groups)


def provision():
    if os.geteuid() != 0:
        raise ValueError("Account provisioning requires root")
    operator_groups = ["cnc-logs"]
    for name in HARDWARE_GROUPS:
        try:
            trusted_group(name)
        except KeyError:
            continue
        operator_groups.append(name)
    identities = (
        (OPERATOR, HOME, operator_groups),
        (MAINTENANCE, MAINTENANCE_HOME, ["cnc-logs"]),
    )
    # Reject unexpected existing identities before creating or changing accounts.
    for name, home, groups in identities:
        try:
            pwd.getpwnam(name)
        except KeyError:
            continue
        validate_user(name, home, groups)
    try:
        logs = trusted_group("cnc-logs")
    except KeyError:
        run("/usr/sbin/groupadd", "--system", "cnc-logs")
        logs = trusted_group("cnc-logs")
    if set(logs.gr_mem) - {OPERATOR, MAINTENANCE} or any(
        entry.pw_gid == logs.gr_gid for entry in pwd.getpwall()
    ):
        raise ValueError("cnc-logs must be dedicated to appliance log readers")
    for name, home, groups in identities:
        account = create_user(name, home, groups)
        desired = {trusted_group(group).gr_gid for group in groups}
        current = set(os.getgrouplist(name, account.pw_gid)) - {account.pw_gid}
        if current != desired:
            run("/usr/sbin/usermod", "--groups", ",".join(groups), name)
        validate_user(name, home, groups)
    for root in (
        "/usr/lib/betterlinuxcnc",
        "/usr/share/betterlinuxcnc",
        "/usr/share/doc/betterlinuxcnc-qt",
        "/var/lib/betterlinuxcnc",
        "/var/cache/betterlinuxcnc",
        "/var/log/betterlinuxcnc",
        "/etc/betterlinuxcnc",
    ):
        directory(root)
    directory(HOME, OPERATOR, OPERATOR, 0o700)
    directory(MAINTENANCE_HOME, "root", MAINTENANCE, 0o750)
    for child in ("programs", "inbox", "machine"):
        directory(f"/var/lib/betterlinuxcnc/{child}", OPERATOR, OPERATOR, 0o700)
    directory("/var/cache/betterlinuxcnc/user", OPERATOR, OPERATOR, 0o700)
    directory("/var/log/betterlinuxcnc/launcher", OPERATOR, "cnc-logs", 0o2750)
    directory("/var/cache/betterlinuxcnc/update", mode=0o700)
    directory("/var/lib/betterlinuxcnc/update")
    parent = os.open("/", DIRECTORY_FLAGS)
    try:
        for component in ("var", "lib", "betterlinuxcnc"):
            info = os.fstat(parent)
            if info.st_uid != 0 or info.st_mode & 0o022:
                raise ValueError("Untrusted configuration lease parent")
            child = os.open(component, DIRECTORY_FLAGS, dir_fd=parent)
            os.close(parent)
            parent = child
        info = os.fstat(parent)
        if info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError("Untrusted configuration lease parent")
        descriptor = os.open(
            "configuration.lock",
            os.O_CREAT | os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o644,
            dir_fd=parent,
        )
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1:
                raise ValueError("Unsafe configuration lease")
            os.fchmod(descriptor, 0o644)
        finally:
            os.close(descriptor)
    finally:
        os.close(parent)


def prepare():
    provision()


def password(value):
    # Compatibility entry only; Rust owns validation and all password mutations.
    run(
        "/usr/lib/betterlinuxcnc/account-management/cnc-maint/cnc-maint-account",
        "enable",
        input=value,
    )
