"""Automatically write installed INI axis settings through guarded maintenance."""

import configparser
import contextlib
import fcntl
import hashlib
import json
import os
import pwd
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path, PurePosixPath

from axis_configuration import AXES, axis_count, generate, hal_files

CONFIG = Path("/etc/betterlinuxcnc")
LEASE = Path("/var/lib/betterlinuxcnc/configuration.lock")
UPDATE_LOCK = Path("/var/cache/betterlinuxcnc/update/update.lock")
PUBLIC = Path("/var/lib/betterlinuxcnc/axis-profile")
ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8"}


def trusted_read(path):
    """Read a bounded root-owned regular file through protected ancestors."""
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("Invalid managed path")
    for parent in path.parents:
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError("Untrusted configuration parent")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != 0
            or info.st_nlink != 1
            or info.st_mode & 0o022
            or info.st_size > 262144
        ):
            raise ValueError("Untrusted configuration file")
        data = stream.read(262145)
        if len(data) > 262144:
            raise ValueError("Configuration file exceeds limit")
        return data


def relative_file(name):
    if not isinstance(name, str):
        raise TypeError("Profile filenames must be strings")
    path = PurePosixPath(name)
    if (
        len(path.parts) != 1
        or path.is_absolute()
        or ".." in path.parts
        or str(path) != name
    ):
        raise ValueError("Profile files must use literal filenames in one directory")
    return path


# --------#
# BEGIN: AxisProfileStore
class AxisProfileStore:
    def current(self):
        launcher_bytes = trusted_read(CONFIG / "launcher.json")
        launcher = json.loads(launcher_bytes)
        if not isinstance(launcher, dict) or not isinstance(launcher.get("ini"), str):
            raise TypeError("Invalid installed launcher configuration")
        path = Path(launcher["ini"])
        if not path.is_absolute():
            path = CONFIG / path
        if not path.is_relative_to(CONFIG / "machine") or ".." in path.parts:
            raise ValueError("Current INI must be in the managed machine directory")
        content = trusted_read(path)
        if len(content) > 65536:
            raise ValueError("Current INI exceeds the automatic editing size limit")
        return path, content, launcher_bytes

    def prepare(self, count):
        path, current, launcher = self.current()
        current_hash = hashlib.sha256(current).hexdigest()
        base = current.decode("utf-8")
        saved_bytes = b""
        saved_path = path.with_name(".axis-settings-source.json")
        if axis_count(base) != 3:
            saved_bytes = trusted_read(saved_path)
            saved = json.loads(saved_bytes)
            if (
                not isinstance(saved, dict)
                or saved.get("schema_version") != 1
                or saved.get("ini") != path.name
                or current_hash not in saved.get("accepted_ini_hashes", [])
                or not isinstance(saved.get("base_ini"), str)
            ):
                raise ValueError(
                    "Active INI changed outside axis settings; preserve and review those edits first"
                )
            base = saved["base_ini"]
        names = hal_files(base)
        files = {
            name: trusted_read(path.parent / relative_file(name)) for name in names
        }
        active_generated = {}
        for name in hal_files(current.decode("utf-8")):
            if name.startswith(".axis-settings-"):
                data = trusted_read(path.parent / relative_file(name))
                if (
                    name
                    != ".axis-settings-" + hashlib.sha256(data).hexdigest() + ".hal"
                ):
                    raise ValueError(
                        "Active generated HAL was edited; changes were not overwritten"
                    )
                active_generated[name] = data
        if saved_bytes:
            expected = saved.get("hal_hashes")
            if expected != {
                name: hashlib.sha256(data).hexdigest() for name, data in files.items()
            }:
                raise ValueError(
                    "Base HAL changed after switching; no changes were overwritten"
                )
        generated_ini, generated_hal = generate(
            base, {name: data.decode("utf-8") for name, data in files.items()}, count
        )
        if len(generated_ini.encode()) > 65536 or any(
            len(text.encode()) > 262144 for text in generated_hal.values()
        ):
            raise ValueError(
                "Generated INI/HAL exceeds the automatic editing size limit"
            )
        fingerprint = hashlib.sha256(
            str(count).encode()
            + b"\0"
            + launcher
            + b"\0"
            + current
            + b"\0"
            + saved_bytes
        )
        for name, data in sorted({**files, **active_generated}.items()):
            fingerprint.update(name.encode() + b"\0" + data + b"\0")
        # Preserve the base automatically; users never supply alternate INI/HAL files.
        # Both hashes allow recovery if writing the final INI is interrupted.
        snapshot = {
            "schema_version": 1,
            "ini": path.name,
            "base_ini": base,
            "accepted_ini_hashes": [
                current_hash,
                hashlib.sha256(generated_ini.encode()).hexdigest(),
            ],
            "hal_hashes": {
                name: hashlib.sha256(data).hexdigest() for name, data in files.items()
            },
        }
        return {
            "revision": fingerprint.hexdigest(),
            "axis_count": count,
            "path": path,
            "ini": generated_ini.encode(),
            "hal": generated_hal,
            "snapshot": snapshot,
        }

    def status(self):
        profiles = []
        for count, axes in AXES.items():
            try:
                self.prepare(count)
                profiles.append(
                    {"axis_count": count, "axes": axes, "available": True, "reason": ""}
                )
            except (
                OSError,
                ValueError,
                KeyError,
                TypeError,
                configparser.Error,
            ) as error:
                profiles.append(
                    {
                        "axis_count": count,
                        "axes": axes,
                        "available": False,
                        "reason": str(error),
                    }
                )
        try:
            _, current, _ = self.current()
            configured = axis_count(current.decode("utf-8"))
        except (OSError, ValueError, KeyError, TypeError, configparser.Error):
            configured = None
        return {
            "schema_version": 1,
            "component": "axis-profile",
            "profiles": profiles,
            "configured_axis_count": configured,
        }

    def apply(self, count, expected_revision):
        # FD4 is the maintenance guard's live update lock; keep it open until exit.
        info = os.fstat(4)
        target = UPDATE_LOCK.lstat()
        if (info.st_dev, info.st_ino) != (target.st_dev, target.st_ino):
            raise ValueError("Missing inherited maintenance lock")
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != 0
            or info.st_nlink != 1
            or info.st_mode & 0o077
        ):
            raise ValueError("Untrusted maintenance lock")
        fcntl.flock(4, fcntl.LOCK_EX | fcntl.LOCK_NB)
        trusted_read(LEASE)
        with LEASE.open("rb") as lease:
            fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.require_stopped()
            prepared = self.prepare(count)
            if prepared["revision"] != expected_revision:
                raise ValueError("Profile or launcher changed; select again")
            subprocess.run(
                ["/usr/sbin/betterlinuxcnc-appliance", "backup"],
                env=ENV,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                check=True,
                timeout=300,
            )
            self.require_stopped()
            if self.prepare(count)["revision"] != expected_revision:
                raise ValueError("Profile changed during backup")
            path = prepared["path"]
            # New HAL files are content-addressed. The current INI is the single
            # atomic commit point and never references partially written content.
            for name, content in prepared["hal"].items():
                target = path.parent / relative_file(name)
                try:
                    existing = trusted_read(target)
                except FileNotFoundError:
                    atomic_bytes(target, content.encode())
                else:
                    if existing != content.encode():
                        raise ValueError("Generated HAL content changed unexpectedly")
            atomic_json(
                path.with_name(".axis-settings-source.json"), prepared["snapshot"]
            )
            atomic_bytes(path, prepared["ini"])

    @staticmethod
    def require_stopped():
        uid = pwd.getpwnam("linuxcnc").pw_uid
        for path in (
            Path("/tmp/linuxcnc.lock"),
            Path(f"/run/user/{uid}/betterlinuxcnc/control.sock"),
        ):
            try:
                path.lstat()
            except FileNotFoundError:
                continue
            raise ValueError("Control endpoints remain; configuration was not changed")


# END: AxisProfileStore
# --------#


def atomic_json(path, value):
    atomic_bytes(
        path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()
    )


def atomic_bytes(path, content):
    # All callers use fixed protected paths; never replace links or special files.
    try:
        trusted_read(path)
        original = path.lstat()
        mode, uid, gid = (
            stat.S_IMODE(original.st_mode),
            original.st_uid,
            original.st_gid,
        )
    except FileNotFoundError:
        mode, uid, gid = 0o644, 0, 0
    temporary = path.with_name(f".{path.name}-{os.getpid()}")
    descriptor = os.open(
        temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fchown(stream.fileno(), uid, gid)
            os.fchmod(stream.fileno(), mode)
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        with contextlib.suppress(FileNotFoundError):
            temporary.unlink()


def install_integration():
    """Register fixed maintenance files without starting units or activating login.

    Deliver these sources inside the existing application package tree so older
    updater allowlists can install this release through their normal entry point.
    """
    sources = Path(__file__).resolve().parent
    destinations = {
        "betterlinuxcnc-axis-profile@.service": Path("/usr/lib/systemd/system"),
        "00-betterlinuxcnc-axis-settings.rules": Path("/usr/share/polkit-1/rules.d"),
    }
    if not any((sources / name).exists() for name in destinations):
        return
    if os.geteuid() != 0:
        raise ValueError("Maintenance registration requires root")
    ledger = Path("/var/lib/betterlinuxcnc/axis-integration.json")
    try:
        previous = json.loads(trusted_read(ledger))
    except FileNotFoundError:
        previous = {}
    if not isinstance(previous, dict):
        raise TypeError("Invalid maintenance registration record")
    contents = {name: trusted_read(sources / name) for name in destinations}
    for name, directory in destinations.items():
        try:
            existing = trusted_read(directory / name)
        except FileNotFoundError:
            continue
        if existing != contents[name] and hashlib.sha256(
            existing
        ).hexdigest() != previous.get(name):
            raise ValueError("Maintenance integration has local edits: " + name)
    for name, directory in destinations.items():
        atomic_bytes(directory / name, contents[name])
    atomic_json(
        ledger,
        {
            name: hashlib.sha256(content).hexdigest()
            for name, content in contents.items()
        },
    )


def run(operation, count=None, revision=None):
    if operation != "status" and sys.platform != "linux":
        raise ValueError("Profile switching requires the Linux appliance")
    if operation not in ("status", "request") and (
        os.getuid() != 0 or os.geteuid() != 0
    ):
        raise ValueError("Profile maintenance requires the root service")
    store = AxisProfileStore()
    if operation == "status":
        result = store.status()
        try:
            result["operation"] = json.loads(trusted_read(PUBLIC / "status.json"))
        except FileNotFoundError:
            result["operation"] = None
        operation_status = result["operation"]
        if operation_status is not None and not isinstance(operation_status, dict):
            raise ValueError("Invalid profile operation record")
        if operation_status and operation_status.get("phase") == "switching":
            count = operation_status.get("axis_count")
            if count not in AXES:
                raise ValueError("Invalid profile operation record")
            unit = subprocess.run(
                [
                    "/usr/bin/systemctl",
                    "--system",
                    "show",
                    "--property=ActiveState",
                    "--value",
                    f"betterlinuxcnc-axis-profile@{count}.service",
                ],
                env=ENV,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
            if unit.stdout.strip() not in ("active", "activating", "reloading"):
                result["operation"] = {**operation_status, "phase": "error"}
        return result
    if count not in AXES:
        raise ValueError("Only 3, 4 or 5 axes may be selected")
    if operation == "request":
        uid = pwd.getpwnam("linuxcnc").pw_uid
        if uid == 0 or os.getuid() != uid or os.geteuid() != uid:
            raise ValueError("Only the operator may request a profile switch")
        store.prepare(count)
        requested_at = time.time()
        subprocess.run(
            [
                "/usr/bin/systemctl",
                "--system",
                "--no-ask-password",
                "--no-block",
                "start",
                f"betterlinuxcnc-axis-profile@{count}.service",
            ],
            env=ENV,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=True,
            timeout=10,
        )
        return {"phase": "scheduled", "axis_count": count, "started_at": requested_at}
    if operation == "prepare-system":
        return {"revision": store.prepare(count)["revision"]}
    if operation == "apply-system":
        store.apply(count, revision)
        return {"phase": "configured", "axis_count": count}
    if operation != "switch-system":
        raise ValueError("Unknown axis-profile operation")
    PUBLIC.mkdir(mode=0o755, exist_ok=True)
    # Reject an untrusted status directory before writing a root result.
    probe = PUBLIC.lstat()
    if not stat.S_ISDIR(probe.st_mode) or probe.st_uid != 0 or probe.st_mode & 0o022:
        raise ValueError("Untrusted profile status directory")
    # The unit's private umask must not hide its read-only result from operators.
    PUBLIC.chmod(0o755)
    descriptor = os.open(
        PUBLIC / "operation.lock",
        os.O_RDONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
        0o600,
    )
    with os.fdopen(descriptor, "rb") as lock:
        info = os.fstat(lock.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != 0
            or info.st_nlink != 1
            or info.st_mode & 0o077
        ):
            raise ValueError("Untrusted profile operation lock")
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = {
            "phase": "switching",
            "axis_count": count,
            "message": "",
            "started_at": time.time(),
        }
        atomic_json(PUBLIC / "status.json", result)
        with tempfile.TemporaryFile() as errors:
            try:
                subprocess.run(
                    ["/usr/bin/betterlinuxcnc-updater", "axis-maintenance", str(count)],
                    env=ENV,
                    stdin=subprocess.DEVNULL,
                    stderr=errors,
                    check=True,
                )
                result["phase"] = "configured"
            except (OSError, subprocess.SubprocessError) as error:
                errors.seek(0, os.SEEK_END)
                errors.seek(max(0, errors.tell() - 8192))
                detail = errors.read().decode("utf-8", "replace").strip()
                result.update(phase="error", message=detail or str(error))
                atomic_json(PUBLIC / "status.json", result)
                if detail:
                    print(detail, file=sys.stderr)
                raise
        atomic_json(PUBLIC / "status.json", result)
        return result
