"""Inspect a dpkg tar stream without extracting or executing package contents."""
import os
import posixpath
import stat
import sys
import tarfile
from pathlib import PurePosixPath

# This is a versioned installation contract, not a template. Keep these bytes
# stable so an already installed updater can admit subsequent release packages.
APPROVED_POSTINST = b'''#!/bin/sh
set -eu
case "${1:-}" in
    configure)
        exec /usr/sbin/betterlinuxcnc-appliance provision
        ;;
    abort-upgrade|abort-remove|abort-deconfigure)
        exit 0
        ;;
    *)
        exit 1
        ;;
esac
'''

TREES = (
    "usr/lib/betterlinuxcnc",
    "usr/share/betterlinuxcnc",
    "usr/share/doc/betterlinuxcnc",
)
FILES = {
    "usr/bin/pa",
    "usr/bin/betterlinuxcnc",
    "usr/bin/betterlinuxcnc-service",
    "usr/bin/betterlinuxcnc-launch",
    "usr/bin/betterlinuxcnc-cam-link",
    "usr/bin/betterlinuxcnc-updater",
    "usr/bin/betterlinuxcnc-mesa-update",
    "usr/bin/betterlinuxcnc-mesa-flash",
    "usr/sbin/betterlinuxcnc-appliance",
    "usr/lib/linuxcnc/modules/zhulong_homing.so",
    "usr/lib/systemd/user/betterlinuxcnc-launcher.service",
    "usr/lib/systemd/system/betterlinuxcnc-system-update.service",
    "usr/lib/systemd/system/betterlinuxcnc-mesa-update.service",
    "usr/lib/systemd/system/betterlinuxcnc-mesa-update.timer",
    "usr/lib/systemd/system/betterlinuxcnc-mesa-flash.service",
    "usr/share/polkit-1/rules.d/49-betterlinuxcnc-update.rules",
    "usr/share/applications/betterlinuxcnc.desktop",
    "usr/share/xsessions/betterlinuxcnc-kiosk.desktop",
    "etc/xdg/autostart/betterlinuxcnc-autostart.desktop",
    "etc/betterlinuxcnc/updater.json",
}
PARENTS = {"."}
for path in (*TREES, *FILES):
    PARENTS.update(str(parent) for parent in PurePosixPath(path).parents)


def destination(path):
    current = "/"
    for part in PurePosixPath(path).parts:
        current = posixpath.join(current, part)
        try:
            info = os.lstat(current)
        except FileNotFoundError:
            break
        if stat.S_ISLNK(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError("existing installation path is not a trusted root-owned path")
        if current != "/" + path and not stat.S_ISDIR(info.st_mode):
            raise ValueError("installation parent is not a directory")


def inspect(stream, kind):
    seen = set()
    total = 0
    with tarfile.open(fileobj=stream, mode="r|") as archive:
        for member in archive:
            raw = member.name
            if raw.startswith("/") or ".." in raw.split("/") or "\\" in raw or "\x00" in raw:
                raise ValueError("invalid archive path")
            path = posixpath.normpath(raw)
            if path in seen:
                raise ValueError("duplicate archive path")
            seen.add(path)
            total += member.size
            if len(seen) > 100000 or total > 2 * 1024**3 or member.size < 0:
                raise ValueError("package expansion exceeds limit")
            if member.type not in (tarfile.REGTYPE, tarfile.AREGTYPE, tarfile.DIRTYPE) or member.sparse:
                raise ValueError("links and special archive entries are forbidden")
            if member.uid != 0 or member.gid != 0 or member.mode & 0o6022:
                raise ValueError("package ownership or permissions are unsafe")
            if kind == "data":
                allowed = path in FILES or any(path == root or path.startswith(root + "/") for root in TREES)
                if member.isdir():
                    allowed = path in PARENTS or any(path == root or path.startswith(root + "/") for root in TREES)
                if not allowed:
                    raise ValueError("package writes outside application installation boundary: " + path)
                destination(path)
            elif kind == "control":
                if member.isdir():
                    if path != ".":
                        raise ValueError("unknown control directory")
                elif path not in {"control", "md5sums", "conffiles", "postinst"}:
                    raise ValueError("unapproved maintainer scripts and control files are forbidden")
                elif member.size > 16 * 1024**2:
                    raise ValueError("control record too large")
                elif path == "postinst":
                    if member.mode != 0o755 or member.size != len(APPROVED_POSTINST):
                        raise ValueError("postinst must match the fixed provisioning contract")
                    if archive.extractfile(member).read() != APPROVED_POSTINST:
                        raise ValueError("postinst must match the fixed provisioning contract")
                elif path == "conffiles":
                    text = archive.extractfile(member).read().decode("utf-8")
                    if any(line.strip() != "/etc/betterlinuxcnc/updater.json" for line in text.splitlines() if line.strip()):
                        raise ValueError("unapproved conffile")
            else:
                raise ValueError("unknown package archive")
    if not seen:
        raise ValueError("empty package archive")


if __name__ == "__main__":
    try:
        inspect(sys.stdin.buffer, sys.argv[1])
    except (ValueError, OSError, tarfile.TarError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
