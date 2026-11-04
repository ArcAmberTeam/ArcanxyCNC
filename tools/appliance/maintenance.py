"""Fixed SSH command routing. Never evaluate SSH_ORIGINAL_COMMAND as a shell."""

import json
import os
import re
import shlex
import stat
import subprocess
import sys
from pathlib import Path

LOG_ROOT = Path("/var/log/betterlinuxcnc/launcher")
ALLOWED = ("help", "version", "status", "logs", "diagnostics", "axis-status")
PA_COMMANDS = (("pa", "manage", "ini"), ("pa", "manage", "launcher.json"))
RUN_NAME = re.compile(r"[0-9]{8}-[0-9]{6}-[1-9][0-9]*")
LOG_NAME = re.compile(r"(?:controller|linuxcnc|cam-link)-[1-9][0-9]*\.log")
DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
MAX_ENTRIES = 4096
MAX_LOG_FILES = 12
MAX_TAIL_BYTES = 65536
MAX_TOTAL_BYTES = 262144


def command(args):
    result = subprocess.run(
        args,
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
        env={
            "PATH": "/usr/bin:/bin",
            "LANG": "C.UTF-8",
            "SYSTEMD_PAGER": "cat",
            "SYSTEMD_COLORS": "0",
        },
    )
    return {
        "exit": result.returncode,
        "stdout": result.stdout[:65536],
        "stderr": result.stderr[:4096],
    }


def _log_root():
    # Open every component from the filesystem root. A path-based check followed
    # by open() would allow replacement of any parent with a symlink in between.
    descriptor = os.open("/", DIRECTORY_FLAGS)
    try:
        for component in LOG_ROOT.parts[1:]:
            child = os.open(component, DIRECTORY_FLAGS, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _entries(descriptor, pattern, expected_type):
    candidates = []
    with os.scandir(descriptor) as entries:
        for index, entry in enumerate(entries):
            if index >= MAX_ENTRIES:
                break
            if not pattern.fullmatch(entry.name):
                continue
            try:
                info = entry.stat(follow_symlinks=False)
            except OSError:
                continue
            if expected_type(info.st_mode):
                candidates.append((info.st_mtime_ns, entry.name, info))
    return sorted(candidates, key=lambda item: item[:2], reverse=True)


def _same_file(before, after):
    return (before.st_dev, before.st_ino) == (after.st_dev, after.st_ino)


def logs():
    result = []
    remaining = MAX_TOTAL_BYTES
    try:
        root = _log_root()
    except OSError:
        return result
    try:
        for _, directory, expected in _entries(root, RUN_NAME, stat.S_ISDIR)[:3]:
            try:
                run = os.open(directory, DIRECTORY_FLAGS, dir_fd=root)
                try:
                    if not _same_file(expected, os.fstat(run)):
                        continue
                    for _, name, expected_log in _entries(run, LOG_NAME, stat.S_ISREG):
                        if len(result) >= MAX_LOG_FILES or remaining <= 0:
                            return result
                        try:
                            descriptor = os.open(name, FILE_FLAGS, dir_fd=run)
                            with os.fdopen(descriptor, "rb") as stream:
                                info = os.fstat(stream.fileno())
                                if (
                                    not stat.S_ISREG(info.st_mode)
                                    or info.st_nlink != 1
                                    or not _same_file(expected_log, info)
                                ):
                                    continue
                                count = min(MAX_TAIL_BYTES, remaining)
                                stream.seek(max(0, info.st_size - count))
                                tail = stream.read(count)
                                remaining -= len(tail)
                                result.append(
                                    {
                                        "file": f"{directory}/{name}",
                                        "tail": tail.decode("utf-8", "replace"),
                                    }
                                )
                        except OSError:
                            continue
                finally:
                    os.close(run)
            except OSError:
                continue
    finally:
        os.close(root)
    return result


def main():
    if len(sys.argv) != 1:
        print(json.dumps({"error": "Arguments are not accepted"}))
        return 64
    try:
        words = shlex.split(os.environ.get("SSH_ORIGINAL_COMMAND", ""))
    except ValueError:
        words = []
    if not words:
        words = ["help"]
    if words[0] in ("git", "build-deb", "install-deb", "build-status"):
        os.execve(
            "/usr/lib/betterlinuxcnc/account-management/cnc-maint/cnc-maint-account",
            ["cnc-maint-account", "workspace", *words],
            {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
        )
    if tuple(words) in PA_COMMANDS:
        # PA verifies the actual OS account again. Inherit the SSH streams for
        # its session; never buffer it through the one-shot diagnostics runner.
        os.execve(
            "/usr/bin/pa",
            words,
            {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
        )
    if len(words) != 1 or words[0] not in ALLOWED:
        print(
            json.dumps(
                {
                    "error": "Only fixed maintenance commands are permitted",
                    "allowed": ALLOWED,
                }
            )
        )
        return 64
    name = words[0]
    if name == "help":
        payload = {
            "commands": ALLOWED,
            "managementCommands": [" ".join(words) for words in PA_COMMANDS],
            "buildCommands": ["git clone", "git pull", "build-deb", "build-status", "install-deb FILE"],
            "buildDirectory": "/var/lib/betterlinuxcnc/build",
            "shell": False,
            "upload": False,
            "forwarding": False,
            "privilegeEscalation": False,
        }
    elif name == "logs":
        payload = {
            "logs": logs(),
            "axisProfiles": command(
                ["/usr/sbin/betterlinuxcnc-appliance", "axis-profile", "status"]
            ),
        }
    elif name == "axis-status":
        payload = command(
            ["/usr/sbin/betterlinuxcnc-appliance", "axis-profile", "status"]
        )
    elif name == "version":
        payload = command(
            [
                "/usr/bin/dpkg-query",
                "-W",
                "-f=${Package} ${Version}\n",
                "betterlinuxcnc-qt",
                "linuxcnc-uspace",
            ]
        )
    elif name == "status":
        payload = command(
            [
                "/usr/bin/systemctl",
                "show",
                "lightdm.service",
                "betterlinuxcnc-system-update.service",
                "--no-pager",
                "-p",
                "Id",
                "-p",
                "ActiveState",
                "-p",
                "SubState",
                "-p",
                "Result",
            ]
        )
    else:
        payload = {
            "kernel": command(["/usr/bin/uname", "-srmo"]),
            "storage": command(["/usr/bin/df", "-h", "/var/lib/betterlinuxcnc"]),
            "processes": command(
                ["/usr/bin/ps", "-u", "linuxcnc", "-o", "pid,ppid,stat,comm"]
            ),
        }
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, subprocess.SubprocessError) as error:
        print(json.dumps({"error": str(error)}))
        raise SystemExit(1) from None
