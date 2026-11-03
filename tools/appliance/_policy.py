"""Fixed host policy, deliberately separate from routine package installation."""

import datetime
import json
import os
import subprocess
import tempfile
from pathlib import Path

POLICIES = {
    "/etc/lightdm/lightdm.conf.d/90-betterlinuxcnc.conf": """[Seat:*]
autologin-user=linuxcnc
autologin-user-timeout=0
autologin-session=betterlinuxcnc-kiosk
user-session=betterlinuxcnc-kiosk
allow-guest=false
allow-user-switching=false
greeter-hide-users=true
greeter-show-manual-login=false
# Fail closed instead of exposing a general-purpose greeter on session failure.
greeter-session=betterlinuxcnc-disabled
xserver-command=X -nolisten tcp
""",
    "/etc/X11/xorg.conf.d/90-betterlinuxcnc.conf": """Section "ServerFlags"
    Option "DontVTSwitch" "true"
    Option "DontZap" "true"
    Option "DontZoom" "true"
EndSection
""",
    "/etc/systemd/logind.conf.d/90-betterlinuxcnc.conf": """[Login]
NAutoVTs=0
ReserveVT=0
""",
    "/etc/ssh/sshd_config": """# Managed dedicated CNC SSH policy. Original saved in the recovery manifest.
# No Include or Match blocks: local overrides cannot reopen shell access.
Port 22
UsePAM yes
StrictModes yes
MaxAuthTries 3
PermitRootLogin no
PermitEmptyPasswords no
PasswordAuthentication yes
PubkeyAuthentication no
AuthenticationMethods password
KbdInteractiveAuthentication no
PermitUserEnvironment no
PermitUserRC no
PermitTTY yes
PermitTunnel no
DisableForwarding yes
X11Forwarding no
AllowUsers cnc-maint
DenyUsers root linuxcnc teto
ForceCommand /usr/bin/python3 -I /usr/lib/betterlinuxcnc/appliance/maintenance.py
""",
    "/etc/default/ssh": 'SSHD_OPTS=""\n',
    "/etc/systemd/system/ssh.service.d/90-betterlinuxcnc.conf": """[Service]
ExecStart=
ExecStart=/usr/sbin/sshd -D -f /etc/ssh/sshd_config
""",
    "/etc/sudoers": """# Managed CNC appliance: ordinary accounts have no sudo grants.
# Original rules and includes are preserved in the root-only recovery manifest.
Defaults env_reset
Defaults use_pty
Defaults secure_path="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
root ALL=(ALL:ALL) ALL
Defaults!/usr/lib/betterlinuxcnc/manage-ini/pa-config !use_pty
cnc-maint ALL=(root) NOPASSWD: /usr/lib/betterlinuxcnc/manage-ini/pa-config ""
""",
    "/etc/sysctl.d/90-betterlinuxcnc.conf": "kernel.sysrq = 0\n",
    "/etc/polkit-1/rules.d/00-betterlinuxcnc-isolation.rules": """polkit.addRule(function(action, subject) {
    if (subject.user !== "linuxcnc" && subject.user !== "cnc-maint" && subject.user !== "teto") return;
    if (subject.user === "linuxcnc" && action.id === "org.freedesktop.systemd1.manage-units"
        && (action.lookup("unit") === "betterlinuxcnc-system-update.service"
            || action.lookup("unit") === "betterlinuxcnc-mesa-flash.service"
            || action.lookup("unit") === "betterlinuxcnc-axis-profile@3.service"
            || action.lookup("unit") === "betterlinuxcnc-axis-profile@4.service"
            || action.lookup("unit") === "betterlinuxcnc-axis-profile@5.service")
        && action.lookup("verb") === "start") return polkit.Result.YES;
    return polkit.Result.NO;
});
""",
}

SSH_EXPECTED = {
    "permitrootlogin": "no",
    "permitemptypasswords": "no",
    "passwordauthentication": "yes",
    "pubkeyauthentication": "no",
    "authenticationmethods": "password",
    "kbdinteractiveauthentication": "no",
    "permituserenvironment": "no",
    "permituserrc": "no",
    "permittty": "yes",
    "permittunnel": "no",
    "disableforwarding": "yes",
    "x11forwarding": "no",
    "allowusers": "cnc-maint",
    "denyusers": "root linuxcnc teto",
    "forcecommand": "/usr/bin/python3 -I /usr/lib/betterlinuxcnc/appliance/maintenance.py",
}


def validate_ssh(config=Path("/etc/ssh/sshd_config")):
    """Check effective restrictions, rather than accepting syntax alone."""
    for user in ("cnc-maint", "linuxcnc", "teto", "root"):
        result = subprocess.run(
            [
                "/usr/sbin/sshd",
                "-T",
                "-f",
                str(config),
                "-C",
                f"user={user},host=localhost,addr=127.0.0.1,laddr=127.0.0.1,lport=22",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        effective = {}
        for line in result.stdout.splitlines():
            key, separator, value = line.partition(" ")
            if separator and key in SSH_EXPECTED:
                effective.setdefault(key, []).append(value.strip())
        for key, value in SSH_EXPECTED.items():
            actual = effective.get(key, [])
            expected = [value]
            if key in ("allowusers", "denyusers"):
                actual = [user for item in actual for user in item.split()]
                expected = value.split()
            if actual != expected:
                raise ValueError(f"Effective SSH policy mismatch for {user}: {key}")


def write(path, text, mode=0o644):
    path = Path(path)
    if path.is_symlink():
        raise ValueError(f"Refusing to replace a symbolic link: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".bettercnc-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
            os.fchmod(stream.fileno(), mode)
        os.replace(temporary, path)
        parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def install(root=Path("/")):
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    recovery = root / "var/lib/betterlinuxcnc/recovery" / stamp
    recovery.mkdir(parents=True, mode=0o700)
    recovery.parent.chmod(0o700)
    previous = []
    for name in POLICIES:
        path = root / name.lstrip("/")
        if path.is_symlink():
            raise ValueError(f"Existing policy is a symlink: {path}")
        previous.append(
            {
                "path": name,
                "content": path.read_text() if path.exists() else None,
                "mode": path.stat().st_mode & 0o777 if path.exists() else 0o644,
            }
        )
    # Complete and persist recovery data before touching any login policy.
    write(recovery / "policies.json", json.dumps(previous, indent=2) + "\n", 0o600)
    for directory in (recovery.parent, recovery.parent.parent):
        descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    try:
        for name, text in POLICIES.items():
            path = root / name.lstrip("/")
            write(path, text, 0o440 if name == "/etc/sudoers" else 0o644)
        if root == Path("/"):
            for command in (["/usr/sbin/sshd", "-t"], ["/usr/sbin/visudo", "-c"]):
                subprocess.run(command, check=True, capture_output=True, text=True)
            validate_ssh()
    except Exception:
        restore(previous, root)
        raise
    return recovery


def restore(previous, root=Path("/")):
    for item in reversed(previous):
        path = root / item["path"].lstrip("/")
        if item["content"] is None:
            path.unlink(missing_ok=True)
        else:
            write(path, item["content"], item["mode"])
