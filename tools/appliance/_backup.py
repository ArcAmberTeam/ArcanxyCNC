"""Bounded, root-private snapshots of the fixed appliance configuration."""

import datetime
import errno
import fcntl
import hashlib
import json
import os
import re
import stat
import subprocess
import uuid
from contextlib import ExitStack, contextmanager
from pathlib import PurePosixPath

from _package_identity import PACKAGE
from _policy import POLICIES

SNAPSHOTS = "/var/lib/betterlinuxcnc/recovery/snapshots"
SOURCES = ("/etc/betterlinuxcnc", "/var/lib/betterlinuxcnc/machine")
FORMAT = "betterlinuxcnc-snapshot-v1"
MAX_BYTES = 64 * 1024 * 1024
MAX_ENTRIES = 4096
MAX_DEPTH = 32
MAX_MANIFEST = 4 * 1024 * 1024
DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
VERSION = re.compile(r"[0-9][A-Za-z0-9.+:~_-]{0,127}\Z")
STAMP = re.compile(r"[0-9]{8}T[0-9]{12}Z\Z")


class BackupError(ValueError):
    """Safe diagnostic containing no source names, contents or credentials."""


def _identity(info):
    return info.st_dev, info.st_ino


def _unchanged(before, after):
    return (
        _identity(before) == _identity(after)
        and before.st_mode == after.st_mode
        and before.st_nlink == after.st_nlink
        and before.st_size == after.st_size
        and before.st_mtime_ns == after.st_mtime_ns
        and before.st_ctime_ns == after.st_ctime_ns
    )


def _private(info, mode):
    if info.st_uid != 0 or stat.S_IMODE(info.st_mode) != mode:
        raise BackupError("Snapshot ownership or permissions are unsafe")


def _trusted(info):
    if info.st_uid != 0 or info.st_mode & 0o022:
        raise BackupError(
            "A fixed system directory has unsafe ownership or permissions"
        )


@contextmanager
def _directory(path, *, create=False, source=False):
    """Anchor every component to an open root descriptor; never resolve symlinks."""
    descriptor = os.open("/", DIRECTORY_FLAGS)
    try:
        _trusted(os.fstat(descriptor))
        components = PurePosixPath(path).parts[1:]
        for index, part in enumerate(components):
            if create:
                try:
                    os.mkdir(part, 0o700, dir_fd=descriptor)
                    os.fsync(descriptor)
                except FileExistsError:
                    pass
            child = os.open(part, DIRECTORY_FLAGS, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
            if not source or index < len(components) - 1:
                _trusted(os.fstat(descriptor))
            if create and index >= len(components) - 2:
                os.fchmod(descriptor, 0o700)
                os.fsync(descriptor)
        yield descriptor
    finally:
        os.close(descriptor)


def _names(descriptor):
    scan = os.open(".", DIRECTORY_FLAGS, dir_fd=descriptor)
    try:
        with os.scandir(scan) as entries:
            names = []
            for entry in entries:
                if len(names) >= MAX_ENTRIES:
                    raise BackupError("Snapshot entry limit exceeded")
                names.append(entry.name)
    finally:
        os.close(scan)
    return sorted(names)


@contextmanager
def _child(parent, name, directory=False):
    before = os.stat(name, dir_fd=parent, follow_symlinks=False)
    expected = stat.S_ISDIR if directory else stat.S_ISREG
    if not expected(before.st_mode) or (not directory and before.st_nlink != 1):
        raise BackupError(
            "Snapshot sources must contain only directories and regular files without hard links"
        )
    descriptor = os.open(
        name, DIRECTORY_FLAGS if directory else FILE_FLAGS, dir_fd=parent
    )
    try:
        current = os.fstat(descriptor)
        if not expected(current.st_mode) or _identity(current) != _identity(before):
            raise BackupError("A snapshot source changed while opening it")
        if not directory and current.st_nlink != 1:
            raise BackupError("Hard-linked snapshot files are forbidden")
        yield descriptor
    finally:
        os.close(descriptor)


@contextmanager
def _destination(parent, parts):
    descriptor = os.dup(parent)
    try:
        for name in parts:
            try:
                os.mkdir(name, 0o700, dir_fd=descriptor)
            except FileExistsError:
                pass
            child = os.open(name, DIRECTORY_FLAGS, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
            _private(os.fstat(descriptor), 0o700)
        yield descriptor
    finally:
        os.close(descriptor)


def _metadata(path, info):
    return {
        "path": path,
        "mode": stat.S_IMODE(info.st_mode),
        "uid": info.st_uid,
        "gid": info.st_gid,
    }


def _write(descriptor, data):
    remaining = memoryview(data)
    while remaining:
        count = os.write(descriptor, remaining)
        if count <= 0:
            raise BackupError("Could not persist the snapshot")
        remaining = remaining[count:]


def _copy_file(source, destination, path, manifest, budget):
    before = os.fstat(source)
    if before.st_size > MAX_BYTES - budget[0]:
        raise BackupError("Snapshot exceeds the 64 MiB limit")
    parts = PurePosixPath(path).parts[1:]
    with _destination(destination, ("files", *parts[:-1])) as parent:
        output = os.open(
            parts[-1],
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent,
        )
        digest = hashlib.sha256()
        size = 0
        try:
            while data := os.read(source, 65536):
                size += len(data)
                budget[0] += len(data)
                if budget[0] > MAX_BYTES:
                    raise BackupError("Snapshot exceeds the 64 MiB limit")
                digest.update(data)
                _write(output, data)
            os.fsync(output)
        finally:
            os.close(output)
    if size != before.st_size or not _unchanged(before, os.fstat(source)):
        raise BackupError("A snapshot source changed while reading it")
    manifest["files"].append(
        dict(_metadata(path, before), size=size, sha256=digest.hexdigest())
    )


def _copy_tree(source, destination, path, manifest, budget, depth=0):
    if depth > MAX_DEPTH:
        raise BackupError("Snapshot directory depth limit exceeded")
    before = os.fstat(source)
    budget[1] += 1
    if budget[1] > MAX_ENTRIES:
        raise BackupError("Snapshot entry limit exceeded")
    manifest["directories"].append(_metadata(path, before))
    with _destination(destination, ("files", *PurePosixPath(path).parts[1:])):
        pass
    for name in _names(source):
        info = os.stat(name, dir_fd=source, follow_symlinks=False)
        directory = stat.S_ISDIR(info.st_mode)
        with _child(source, name, directory) as child:
            if directory:
                _copy_tree(
                    child, destination, path + "/" + name, manifest, budget, depth + 1
                )
            else:
                budget[1] += 1
                if budget[1] > MAX_ENTRIES:
                    raise BackupError("Snapshot entry limit exceeded")
                _copy_file(child, destination, path + "/" + name, manifest, budget)
    if not _unchanged(before, os.fstat(source)):
        raise BackupError("A snapshot source directory changed while reading it")


def _installed_version():
    try:
        result = subprocess.run(
            ["/usr/bin/dpkg-query", "-W", "-f=${Version}", PACKAGE],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
            env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"},
        )
    except (OSError, subprocess.SubprocessError, UnicodeError):
        raise BackupError(
            "Could not determine the installed application version"
        ) from None
    version = result.stdout.strip()
    if not VERSION.fullmatch(version):
        raise BackupError("Installed application version is invalid")
    return version


def _allowed(path, directory=False):
    if not isinstance(path, str) or str(PurePosixPath(path)) != path:
        return False
    if ".." in PurePosixPath(path).parts or not path.startswith("/"):
        return False
    return any(path == root or path.startswith(root + "/") for root in SOURCES) or (
        not directory and path in POLICIES
    )


def _expected(manifest, name):
    if not isinstance(manifest, dict) or set(manifest) != {
        "format",
        "package",
        "sourceVersion",
        "createdUtc",
        "files",
        "directories",
    }:
        raise BackupError("Snapshot manifest is invalid")
    version, stamp = manifest["sourceVersion"], manifest["createdUtc"]
    if (
        manifest["format"] != FORMAT
        or manifest["package"] not in ("betterlinuxcnc", "betterlinuxcnc-qt")
        or not isinstance(version, str)
        or not VERSION.fullmatch(version)
        or not isinstance(stamp, str)
        or not STAMP.fullmatch(stamp)
        or name != stamp + "-" + version
    ):
        raise BackupError("Snapshot identity is invalid")
    expected = {"manifest.json": None, "files": None}
    entries = set()
    total = 0
    for key in ("directories", "files"):
        collection = manifest[key]
        if not isinstance(collection, list) or len(collection) > MAX_ENTRIES:
            raise BackupError("Snapshot manifest entries are invalid")
        for entry in collection:
            fields = {"path", "mode", "uid", "gid"}
            if key == "files":
                fields |= {"size", "sha256"}
            if not isinstance(entry, dict) or set(entry) != fields:
                raise BackupError("Snapshot manifest entry is invalid")
            path = entry["path"]
            if not _allowed(path, key == "directories") or path in entries:
                raise BackupError("Snapshot manifest path is invalid")
            if any(
                type(entry[field]) is not int or entry[field] < 0
                for field in ("mode", "uid", "gid")
            ):
                raise BackupError("Snapshot source metadata is invalid")
            if entry["mode"] > 0o7777:
                raise BackupError("Snapshot source mode is invalid")
            entries.add(path)
            relative = "files" + path
            if len(PurePosixPath(relative).parts) > MAX_DEPTH + 8:
                raise BackupError("Snapshot directory depth limit exceeded")
            for parent in PurePosixPath(relative).parents:
                if str(parent) != ".":
                    if expected.get(str(parent)) is not None:
                        raise BackupError("Snapshot has conflicting entries")
                    expected[str(parent)] = None
            if key == "files":
                if type(entry["size"]) is not int or entry["size"] < 0:
                    raise BackupError("Snapshot file size is invalid")
                if not isinstance(entry["sha256"], str) or not re.fullmatch(
                    r"[0-9a-f]{64}", entry["sha256"]
                ):
                    raise BackupError("Snapshot digest is invalid")
                total += entry["size"]
                expected[relative] = entry
            else:
                expected[relative] = None
    directory_sources = {entry["path"] for entry in manifest["directories"]}
    if (
        total > MAX_BYTES
        or len(entries) > MAX_ENTRIES
        or not set(SOURCES).issubset(directory_sources)
    ):
        raise BackupError("Snapshot source set or size is invalid")
    return expected


def _verify(descriptor, name):
    _private(os.fstat(descriptor), 0o700)
    with _child(descriptor, "manifest.json") as source:
        before = os.fstat(source)
        _private(before, 0o600)
        if before.st_size > MAX_MANIFEST:
            raise BackupError("Snapshot manifest is too large")
        data = bytearray()
        while chunk := os.read(source, min(65536, MAX_MANIFEST + 1 - len(data))):
            data.extend(chunk)
            if len(data) > MAX_MANIFEST:
                raise BackupError("Snapshot manifest is too large")
        if len(data) != before.st_size or not _unchanged(before, os.fstat(source)):
            raise BackupError("Snapshot manifest changed while reading it")
    try:
        manifest = json.loads(data)
    except (ValueError, UnicodeError, RecursionError):
        raise BackupError("Snapshot manifest is unreadable") from None
    expected = _expected(manifest, name)
    found = set()

    def walk(parent, prefix=""):
        for entry in _names(parent):
            relative = prefix + entry
            if relative not in expected:
                raise BackupError("Snapshot contains an unexpected entry")
            found.add(relative)
            item = expected[relative]
            directory = item is None and relative != "manifest.json"
            with _child(parent, entry, directory) as child:
                _private(os.fstat(child), 0o700 if directory else 0o600)
                if directory:
                    walk(child, relative + "/")
                elif item is not None:
                    digest = hashlib.sha256()
                    size = 0
                    while data := os.read(child, 65536):
                        size += len(data)
                        if size > item["size"]:
                            raise BackupError(
                                "Snapshot file size does not match its manifest"
                            )
                        digest.update(data)
                    if size != item["size"] or digest.hexdigest() != item["sha256"]:
                        raise BackupError("Snapshot file verification failed")
        os.fsync(parent)

    walk(descriptor)
    if found != set(expected):
        raise BackupError("Snapshot is incomplete")
    return manifest


def _remove(parent, name):
    with _child(parent, name, True) as child:
        for entry in _names(child):
            info = os.stat(entry, dir_fd=child, follow_symlinks=False)
            if stat.S_ISDIR(info.st_mode):
                _remove(child, entry)
            else:
                os.unlink(entry, dir_fd=child)
    os.rmdir(name, dir_fd=parent)


def _prune(parent, current):
    valid = []
    for name in _names(parent):
        if name.startswith("."):
            continue
        try:
            with _child(parent, name, True) as child:
                _verify(child, name)
            valid.append(name)
        except (OSError, ValueError):
            # Foreign, legacy or damaged backups are never retention candidates.
            continue
    if current not in valid:
        raise BackupError("Published snapshot could not be verified")
    older = sorted((name for name in valid if name != current), reverse=True)
    for name in older[2:]:
        _remove(parent, name)
    os.fsync(parent)


def _snapshot(parent):
    space = os.fstatvfs(parent)
    if space.f_bavail * space.f_frsize < MAX_BYTES + MAX_MANIFEST + 1024 * 1024:
        raise BackupError(
            "Insufficient free space for a complete configuration snapshot"
        )
    version = _installed_version()
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    name = stamp + "-" + version
    temporary = ".snapshot-" + uuid.uuid4().hex
    os.mkdir(temporary, 0o700, dir_fd=parent)
    published = False
    try:
        with _child(parent, temporary, True) as destination:
            manifest = {
                "format": FORMAT,
                "package": PACKAGE,
                "sourceVersion": version,
                "createdUtc": stamp,
                "files": [],
                "directories": [],
            }
            budget = [0, 0]
            for path in SOURCES:
                with _directory(path, source=True) as source:
                    _copy_tree(source, destination, path, manifest, budget)
            for path in POLICIES:
                policy = PurePosixPath(path)
                with ExitStack() as stack:
                    try:
                        source = stack.enter_context(_directory(str(policy.parent)))
                        file = stack.enter_context(_child(source, policy.name))
                    except FileNotFoundError:
                        continue
                    budget[1] += 1
                    if budget[1] > MAX_ENTRIES:
                        raise BackupError("Snapshot entry limit exceeded")
                    _copy_file(file, destination, path, manifest, budget)
            data = (
                json.dumps(manifest, ensure_ascii=True, sort_keys=True) + "\n"
            ).encode()
            if len(data) > MAX_MANIFEST:
                raise BackupError("Snapshot manifest is too large")
            output = os.open(
                "manifest.json",
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=destination,
            )
            try:
                _write(output, data)
                os.fsync(output)
            finally:
                os.close(output)
            _verify(destination, name)
        # No replacement: a timestamp collision must preserve the existing snapshot.
        try:
            os.stat(name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise BackupError("Snapshot identity already exists")
        os.rename(temporary, name, src_dir_fd=parent, dst_dir_fd=parent)
        published = True
        os.fsync(parent)
        _prune(parent, name)
        return {
            "snapshot": SNAPSHOTS + "/" + name,
            "sourceVersion": version,
            "files": len(manifest["files"]),
        }
    finally:
        if not published:
            _remove(parent, temporary)
            os.fsync(parent)


def backup():
    """Create and verify one snapshot; accept no caller-controlled paths or commands."""
    if os.geteuid() != 0:
        raise BackupError("Configuration snapshots require root")
    try:
        with _directory(SNAPSHOTS, create=True) as parent:
            descriptor = os.open(
                ".lock",
                os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
                0o600,
                dir_fd=parent,
            )
            try:
                info = os.fstat(descriptor)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise BackupError("Snapshot lock is unsafe")
                _private(info, 0o600)
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise BackupError(
                        "Another configuration snapshot is in progress"
                    ) from None
                return _snapshot(parent)
            finally:
                os.close(descriptor)
    except OSError as error:
        reasons = {
            errno.ENOSPC: "Insufficient space while writing the snapshot",
            errno.ENOENT: "A required configuration source is missing or changed",
            errno.ELOOP: "A symbolic link is forbidden in a fixed snapshot path",
            errno.ENOTDIR: "A snapshot directory is unsafe or changed",
            errno.EACCES: "Configuration snapshot access was denied",
        }
        raise BackupError(
            reasons.get(
                error.errno, "Configuration snapshot filesystem operation failed"
            )
        ) from None
