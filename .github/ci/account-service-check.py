"""Exercise the real socket-activated account service on an isolated hosted runner."""
import json
import os
import pty
import re
from pathlib import Path
import pwd
import secrets
import shutil
import subprocess
import sys


def run(*args, **kwargs):
    result = subprocess.run(args, check=False, capture_output=True, text=True, timeout=30, **kwargs)
    if result.returncode:
        raise RuntimeError(f"{args[0]} failed: {result.stderr}")
    return result


def main():
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.geteuid() != 0:
        raise RuntimeError("Only run in the isolated GitHub hosted job")
    for name in ("linuxcnc", "cnc-maint", "cnc_admin"):
        try:
            pwd.getpwnam(name)
        except KeyError:
            pass
        else:
            raise RuntimeError("Refuse to replace an existing test account")
    run("useradd", "--user-group", "--no-create-home", "--shell", "/bin/sh", "linuxcnc")
    run("useradd", "--user-group", "--no-create-home", "--shell", "/bin/sh",
        "--home-dir", "/var/lib/betterlinuxcnc/maintenance", "cnc-maint")
    run("useradd", "--user-group", "--no-create-home", "--shell", "/bin/sh",
        "--home-dir", "/var/lib/betterlinuxcnc/admin", "cnc_admin")
    root = Path("/var/lib/betterlinuxcnc")
    root.mkdir(mode=0o755)
    Path("/etc/betterlinuxcnc").mkdir(mode=0o755)
    helper = Path("/usr/lib/betterlinuxcnc/account-management/cnc-maint/cnc-maint-account")
    helper.parent.mkdir(parents=True)
    shutil.copyfile(sys.argv[1], helper)
    helper.chmod(0o755)
    previous_sudo = Path("/etc/betterlinuxcnc/cnc-maint-sudo")
    previous_sudo.write_text("cnc-maint ALL=(ALL:ALL) NOTAFTER=20990101000000Z NOPASSWD: ALL\n")
    previous_sudo.chmod(0o440)
    run(str(helper), "provision")
    assert "NOPASSWD: ALL" not in previous_sudo.read_text()
    build_unit = Path("/usr/lib/systemd/system/betterlinuxcnc-cnc-maint-build@.service")
    expected_unit = build_unit.read_text()
    build_unit.write_text(expected_unit.replace("AmbientCapabilities=CAP_SETUID CAP_SETGID\n", ""))
    run(str(helper), "provision")
    assert build_unit.read_text() == expected_unit
    run("systemctl", "is-active", "--quiet", "betterlinuxcnc-cnc-maint.socket")
    build_socket = "/run/betterlinuxcnc-cnc-maint-build.sock"
    probe = """
import socket, sys
with socket.socket(socket.AF_UNIX) as connection:
    connection.settimeout(10)
    connection.connect(sys.argv[1])
    connection.sendall(b'local-package-fixture')
    connection.shutdown(socket.SHUT_WR)
    reply = bytearray()
    try:
        while chunk := connection.recv(4096):
            reply.extend(chunk)
    except ConnectionResetError:
        pass
    assert (b'LOCAL-INSTALL-COMPLETE' in reply) == (sys.argv[2] == 'allowed')
"""
    installer = Path("/usr/bin/betterlinuxcnc-updater")
    if installer.exists():
        raise RuntimeError("Refuse to replace an existing updater")
    installer.write_text("#!/usr/bin/python3\nimport os, sys, subprocess\nassert os.getuid() == 0\nassert sys.argv[1:] == ['maintenance-install']\nassert subprocess.check_output(['/usr/sbin/runuser', '-u', 'linuxcnc', '--', '/usr/bin/id', '-un'], text=True).strip() == 'linuxcnc'\nassert sys.stdin.buffer.read() == b'local-package-fixture'\n")
    installer.chmod(0o755)
    def upload(expected):
        run("runuser", "-u", "cnc-maint", "--", "/usr/bin/python3", "-c", probe, build_socket, expected)
    def request(operation, password=""):

        result = run("runuser", "-u", "linuxcnc", "--", str(helper), "request", operation, input=password)
        if password and password in result.stdout + result.stderr:
            raise RuntimeError("Credential leaked")
        return json.loads(result.stdout)["enabled"]
    try:
        assert request("status") is False
        upload("denied")
        assert request("enable", secrets.token_urlsafe(32)) is True
        password = secrets.token_urlsafe(32)
        assert request("enable", password) is True
        run(str(helper), "provision")
        assert request("status") is True
        upload("allowed")
        denied = subprocess.run(["runuser", "-u", "linuxcnc", "--", "/usr/bin/python3", "-c", probe, build_socket, "denied"], capture_output=True)
        assert denied.returncode != 0
        verify_sudo_access(helper, password)
        assert request("disable") is False
        upload("denied")
        assert request("status") is False
        assert Path("/usr/lib/systemd/system/betterlinuxcnc-cnc-maint@.service").read_text().find("NoNewPrivileges=yes") >= 0
        print("Real systemd socket authentication, password mutation, revocation and repeat provisioning passed")
    finally:
        run(str(helper), "disable")
        run("systemctl", "stop", "betterlinuxcnc-cnc-maint.socket", "betterlinuxcnc-cnc-maint-build.socket")
        installer.unlink()


def verify_sudo_access(helper, maintenance_password):
    """Check the same local CLI, socket, PAM and sudo policy used by the desktop."""
    sudoers = Path("/etc/sudoers")
    original = sudoers.read_bytes()
    policy = Path("/etc/betterlinuxcnc/cnc-admin-sudo")
    admin_password = secrets.token_urlsafe(32)

    def issue(allowed=True):
        master, terminal = pty.openpty()
        try:
            result = subprocess.run([str(helper), "issue-admin-code"], stdout=terminal,
                                    stderr=subprocess.DEVNULL, timeout=10)
            assert (result.returncode == 0) == allowed
            if allowed:
                code = os.read(master, 128).decode().strip()
                assert re.fullmatch(r"[0-9A-F]{4}(?:-[0-9A-F]{4}){7}", code)
                return code
        finally:
            os.close(master)
            os.close(terminal)

    def setup_required():
        reply = run("runuser", "-u", "linuxcnc", "--", str(helper), "request", "admin-setup-required")
        return json.loads(reply.stdout)["setupRequired"]

    def switch(op, password="", allowed=True, caller="linuxcnc"):
        result = subprocess.run(
            ["runuser", "-u", caller, "--", str(helper), "request", f"admin-sudo-{op}"],
            input=password, capture_output=True, text=True, timeout=30,
        )
        assert (result.returncode == 0) == allowed
        assert all(secret not in result.stdout + result.stderr for secret in password.splitlines() if secret)
        return json.loads(result.stdout)["enabled"] if allowed else None

    def elevate(allowed):
        result = subprocess.run(
            ["runuser", "-u", "cnc_admin", "--", "sudo", "-S", "-k", "/usr/bin/id", "-u"],
            input=admin_password + "\n", capture_output=True, text=True, timeout=30,
        )
        assert (result.returncode == 0 and result.stdout.strip() == "0") == allowed

    try:
        previous_code = issue()
        code = issue()
        assert code != previous_code
        switch("enable", admin_password, allowed=False)  # Host policy not activated yet.
        with sudoers.open("ab") as stream:
            stream.write(f"\n@include {policy}\n".encode())
        run("visudo", "-c", "-f", str(sudoers))
        assert switch("status") is False
        assert setup_required() is True
        switch("enroll", f"{previous_code}\n{admin_password}", allowed=False)
        switch("enroll", f"{code}\n{admin_password}", allowed=False, caller="nobody")
        run(str(helper), "provision")  # An update must preserve an unused code.
        switch("enable", maintenance_password, allowed=False)
        switch("enable", admin_password, caller="nobody", allowed=False)
        elevate(False)
        assert switch("enroll", f"{code}\n{admin_password}") is True
        assert setup_required() is False
        issue(allowed=False)
        elevate(True)
        run(str(helper), "disable")
        assert switch("status") is True
        run(str(helper), "provision")
        assert switch("status") is True
        switch("disable", maintenance_password, allowed=False)
        assert switch("status") is True
        assert switch("disable", admin_password) is False
        switch("enroll", f"{code}\n{secrets.token_urlsafe(32)}", allowed=False)
        assert switch("enable", admin_password) is True
        assert switch("disable", admin_password) is False
        elevate(False)
        assert switch("status") is False
        # Upgrade an existing password-based installation without an enrollment record.
        Path("/var/lib/betterlinuxcnc/cnc-admin-enrollment").unlink()
        run(str(helper), "provision")
        assert setup_required() is False
        issue(allowed=False)
        assert switch("enable", admin_password) is True
        assert switch("disable", admin_password) is False
        print("Persistent admin sudo, independent PAM authentication and immediate revocation passed")
    finally:
        sudoers.write_bytes(original)


if __name__ == "__main__":
    main()
