"""Exercise the real socket-activated account service on an isolated hosted runner."""
import json
import os
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
    for name in ("linuxcnc", "cnc-maint"):
        try:
            pwd.getpwnam(name)
        except KeyError:
            pass
        else:
            raise RuntimeError("Refuse to replace an existing test account")
    run("useradd", "--user-group", "--no-create-home", "--shell", "/bin/sh", "linuxcnc")
    run("useradd", "--user-group", "--no-create-home", "--shell", "/bin/sh",
        "--home-dir", "/var/lib/betterlinuxcnc/maintenance", "cnc-maint")
    root = Path("/var/lib/betterlinuxcnc")
    root.mkdir(mode=0o755)
    Path("/etc/betterlinuxcnc").mkdir(mode=0o755)
    helper = Path("/usr/lib/betterlinuxcnc/account-management/cnc-maint/cnc-maint-account")
    helper.parent.mkdir(parents=True)
    shutil.copyfile(sys.argv[1], helper)
    helper.chmod(0o755)
    run(str(helper), "provision")
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
    installer.write_text("#!/usr/bin/python3\nimport os, sys\nassert os.getuid() == 0\nassert sys.argv[1:] == ['maintenance-install']\nassert sys.stdin.buffer.read() == b'local-package-fixture'\n")
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


def verify_sudo_access(helper, password):
    """Exercise real PAM, sudo expiry and systemd cleanup through the public CLI."""
    fixture = Path("/etc/sudoers.d/cnc-maint-ci")
    if fixture.exists():
        raise RuntimeError("Refuse to replace an existing sudo fixture")
    fixture.write_text(
        "@include /etc/betterlinuxcnc/cnc-maint-sudo\n"
        f"Defaults!{helper} timestamp_timeout=0, !rootpw, !targetpw, !runaspw\n"
        f"cnc-maint ALL=(root) PASSWD: {helper} sudo-open\n"
    )
    fixture.chmod(0o440)
    policy = Path("/etc/betterlinuxcnc/cnc-maint-sudo")
    timer = "betterlinuxcnc-cnc-maint-sudo-expire.timer"

    def sudo(*args, secret="", ok=True):
        result = subprocess.run(
            ["runuser", "-u", "cnc-maint", "--", "sudo", *args],
            input=secret, capture_output=True, text=True, timeout=30,
        )
        assert (result.returncode == 0) == ok, result.stderr
        assert password not in result.stdout + result.stderr
        return result

    try:
        run("visudo", "-c")
        sudo("-n", "/usr/bin/id", "-u", ok=False)
        sudo("-S", "-k", str(helper), "sudo-open", secret="incorrect-ci-password\n", ok=False)
        assert "NOPASSWD: ALL" not in policy.read_text()
        sudo("-S", "-k", str(helper), "sudo-open", secret=password + "\n")
        assert sudo("-n", "/usr/bin/id", "-u").stdout.strip() == "0"
        run("systemctl", "is-active", "--quiet", timer)
        configured = run("systemctl", "show", timer, "-p", "TimersMonotonic", "--value").stdout
        assert "OnActiveUSec=15min" in configured, configured
        # A wildcard grant must never make opening/renewal passwordless.
        sudo("-n", "-k", str(helper), "sudo-open", ok=False)
        sudo("-S", "-k", str(helper), "sudo-open", secret="incorrect-ci-password\n", ok=False)
        run("systemctl", "start", "betterlinuxcnc-cnc-maint-sudo-expire.service")
        sudo("-n", "/usr/bin/id", "-u", ok=False)
        # Native sudo refuses the deadline independently of the cleanup service.
        policy.write_text("cnc-maint ALL=(ALL:ALL) NOTAFTER=20000101000000Z NOPASSWD: ALL\n")
        sudo("-n", "/usr/bin/id", "-u", ok=False)
        sudo("-S", "-k", str(helper), "sudo-open", secret=password + "\n")
        run("systemctl", "start", "betterlinuxcnc-cnc-maint-sudo-reset.service")
        sudo("-n", "/usr/bin/id", "-u", ok=False)
        sudo("-S", "-k", str(helper), "sudo-open", secret=password + "\n")
        run(str(helper), "provision")
        sudo("-n", "/usr/bin/id", "-u", ok=False)
        # A failed timer startup must leave the grant closed.
        run("systemctl", "stop", timer)
        run("systemctl", "mask", "--runtime", timer)
        sudo("-S", "-k", str(helper), "sudo-open", secret=password + "\n", ok=False)
        sudo("-n", "/usr/bin/id", "-u", ok=False)
        print("Fresh PAM authentication, 900-second timer, native sudo expiry, reset and fail-closed activation passed")
    finally:
        run(str(helper), "sudo-close")
        run("systemctl", "unmask", "--runtime", timer)
        run("systemctl", "stop", timer)
        fixture.unlink()


if __name__ == "__main__":
    main()
