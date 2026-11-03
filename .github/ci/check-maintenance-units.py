"""Check the packaged privilege-drop sandbox on a GitHub-hosted systemd runner."""

import configparser
import os
import pwd
import subprocess
from pathlib import Path


def main():
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise SystemExit("This check is restricted to GitHub CI.")
    source = Path(__file__).resolve().parents[2]
    expected = str(pwd.getpwnam("nobody").pw_uid)
    for relative in (
        "app/platform/updater/packaging/betterlinuxcnc-system-update.service.in",
        "app/platform/mesa-update/packaging/betterlinuxcnc-mesa-flash.service.in",
        "tools/appliance/packaging/betterlinuxcnc-axis-profile@.service.in",
    ):
        parser = configparser.ConfigParser(interpolation=None, strict=False)
        parser.optionxform = str
        parser.read(source / relative)
        service = parser["Service"]
        required = {"CAP_SETUID", "CAP_SETGID"}
        if not required <= set(service.get("AmbientCapabilities", "").split()):
            raise RuntimeError(f"Missing fixed-account capabilities: {relative}")
        command = ["sudo", "systemd-run", "--quiet", "--pipe", "--wait", "--collect"]
        for key, value in service.items():
            if key in {"ExecStart", "Type", "Environment", "TimeoutStartSec"}:
                continue
            if key == "ReadWritePaths":
                # Optional application directories are absent on the hosted runner.
                value = " ".join("-" + path for path in value.split())
            command.append(f"--property={key}={value}")
        # No app, machine, graphical session, network service or flash command runs.
        command.extend(["/usr/sbin/runuser", "-u", "nobody", "--", "/usr/bin/id", "-u"])
        result = subprocess.run(command, capture_output=True, text=True, timeout=30)
        if result.returncode:
            raise RuntimeError(
                f"Sandbox check failed for {relative}: {result.stderr[-2000:]}"
            )
        if result.stdout.strip() != expected:
            raise RuntimeError(
                f"Privilege drop did not reach the unprivileged account: {relative}"
            )
        print(f"Verified fixed-user privilege drop: {relative}")


if __name__ == "__main__":
    main()
