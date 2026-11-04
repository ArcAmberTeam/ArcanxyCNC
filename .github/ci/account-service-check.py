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
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=30, **kwargs)


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
    helper = Path("/usr/lib/betterlinuxcnc/account-management/cnc-maint/cnc-maint-account")
    helper.parent.mkdir(parents=True)
    shutil.copyfile(sys.argv[1], helper)
    helper.chmod(0o755)
    run(str(helper), "provision")
    run("systemctl", "is-active", "--quiet", "betterlinuxcnc-cnc-maint.socket")
    def request(operation, password=""):
        result = run("runuser", "-u", "linuxcnc", "--", str(helper), "request", operation, input=password)
        if password and password in result.stdout + result.stderr:
            raise RuntimeError("Credential leaked")
        return json.loads(result.stdout)["enabled"]
    try:
        assert request("status") is False
        assert request("enable", secrets.token_urlsafe(32)) is True
        assert request("enable", secrets.token_urlsafe(32)) is True
        run(str(helper), "provision")
        assert request("status") is True
        assert request("disable") is False
        assert request("status") is False
        assert Path("/usr/lib/systemd/system/betterlinuxcnc-cnc-maint@.service").read_text().find("NoNewPrivileges=yes") >= 0
        print("Real systemd socket authentication, password mutation, revocation and repeat provisioning passed")
    finally:
        run(str(helper), "disable")
        run("systemctl", "stop", "betterlinuxcnc-cnc-maint.socket")


if __name__ == "__main__":
    main()
