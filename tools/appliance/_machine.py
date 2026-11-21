"""Copy machine profiles privately, then publish fixed paths as a transaction."""

import configparser
import contextlib
import fcntl
import json
import os
import re
import shutil
import stat
import tempfile
import uuid
from pathlib import Path

CONFIG = Path("/etc/betterlinuxcnc")
DATA = Path("/var/lib/betterlinuxcnc")
_DIRECTORY = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
_NAMES = ("programs", "machine", "inbox")


@contextlib.contextmanager
def _directory(path):
    """Pin every path component; a later rename cannot redirect an open parent."""
    path = Path(os.path.abspath(path))
    descriptor = os.open("/", _DIRECTORY)
    try:
        for part in path.parts[1:]:
            child = os.open(part, _DIRECTORY, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        yield descriptor
    finally:
        os.close(descriptor)


@contextlib.contextmanager
def _file(path):
    path = Path(os.path.abspath(path))
    with _directory(path.parent) as parent:
        descriptor = os.open(
            path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent
        )
    with os.fdopen(descriptor, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError(f"Migration requires a regular file: {path}")
        yield stream


def _copy_file(source, destination):
    with _file(source) as stream:
        _copy_stream(stream, destination)


def _copy_stream(stream, destination):
    # The destination is always inside our private staging directory.
    with destination.open("xb") as output:
        shutil.copyfileobj(stream, output)
        output.flush()
        os.fsync(output.fileno())
        mode = os.fstat(stream.fileno()).st_mode
        os.fchmod(output.fileno(), 0o755 if mode & 0o111 else 0o644)


def _copy_directory(source, destination, programs_only=False):
    with _directory(source) as descriptor:
        _copy_children(descriptor, destination, programs_only)


def _copy_children(descriptor, destination, programs_only):
    for name in os.listdir(descriptor):
        info = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
        target = destination / name
        if stat.S_ISDIR(info.st_mode):
            child = os.open(name, _DIRECTORY, dir_fd=descriptor)
            try:
                target.mkdir(mode=0o700)
                _copy_children(child, target, programs_only)
            finally:
                os.close(child)
        elif programs_only and Path(name).suffix.lower() not in (
            ".ngc",
            ".nc",
            ".tap",
            ".gcode",
        ):
            continue
        else:
            handle = os.open(
                name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptor
            )
            with os.fdopen(handle, "rb") as stream:
                if not stat.S_ISREG(os.fstat(handle).st_mode):
                    raise ValueError(
                        f"Migration refuses links or special files: {name}"
                    )
                _copy_stream(stream, target)


def resolve(value, base):
    if "$" in value or "~" in value:
        raise ValueError(f"Resolve environment-dependent machine paths first: {value}")
    result = Path(value)
    return Path(os.path.abspath(result if result.is_absolute() else base / result))


def _build(
    source, config_dir, data_dir, configure_profile=None, *, source_is_ini=False
):
    source = Path(os.path.abspath(source))
    if source_is_ini:
        config = {}
        ini = source
    else:
        with _file(source) as stream:
            config = json.load(stream)
        ini = resolve(config["ini"], source.parent)
    with _file(ini) as stream:
        text = stream.read().decode("utf-8")
    parser = configparser.ConfigParser(strict=False, interpolation=None)
    parser.read_string(text)
    if "#INCLUDE" in text.upper():
        raise ValueError("Included INI files require an explicitly reviewed migration")
    profile = parser.get("DISPLAY", "DISPLAY", fallback="")
    if profile.split()[:1] != ["betterlinuxcnc"]:
        raise ValueError("Machine must already use the BetterLinuxCNC display")
    if source_is_ini and not parser.get("HAL", "HALFILE", fallback="").strip():
        raise ValueError("The selected machine INI must reference a HAL file")
    program_prefix = (
        parser.get("DISPLAY", "PROGRAM_PREFIX", fallback=None)
        if source_is_ini
        else parser.get("DISPLAY", "PROGRAM_PREFIX")
    )
    program_source = (
        resolve(program_prefix, ini.parent) if program_prefix is not None else None
    )
    if any(config.get("cam", {}).get(key) for key in ("token_file", "cert", "key")):
        raise ValueError("CAM credentials require a separately reviewed migration")
    target = config_dir / "machine"
    target.mkdir(mode=0o700)
    _copy_directory(ini.parent, target)
    if source_is_ini:
        from axis_configuration import hal_files

        for name in hal_files(text):
            if not (target / name).is_file():
                raise ValueError(f"Missing local machine HAL file: {name}")
    for name in _NAMES:
        (data_dir / name).mkdir(mode=0o700)
    if program_source is not None and _identity(program_source) is not None:
        _copy_directory(program_source, data_dir / "programs", programs_only=True)
    replacements = {
        ("DISPLAY", "PROGRAM_PREFIX"): str(DATA / "programs"),
        ("DISPLAY", "INTRO_TIME"): "0",
        ("DISPLAY", "INTRO_GRAPHIC"): "",
        ("DISPLAY", "EDITOR"): "",
    }
    for section, key in (
        ("RS274NGC", "PARAMETER_FILE"),
        ("EMCIO", "TOOL_TABLE"),
        ("TRAJ", "POSITION_FILE"),
    ):
        value = parser.get(section, key, fallback="")
        if value:
            old = resolve(value, ini.parent)
            _copy_file(old, data_dir / "machine" / old.name)
            replacements[(section, key)] = str(DATA / "machine" / old.name)
    section, output = "", []
    for line in text.splitlines(keepends=True):
        header = re.match(r"\s*\[([^]]+)\]", line)
        if header:
            section = header.group(1).upper()
            if section == "DISPLAY" and program_prefix is None:
                output.append(line.rstrip("\r\n") + "\n")
                output.append(f"PROGRAM_PREFIX = {DATA / 'programs'}\n")
                continue
        setting = re.match(r"\s*([A-Za-z_0-9]+)\s*=", line)
        key = (section, setting.group(1).upper()) if setting else None
        if section == "FILTER" and setting:
            output.append("# Disabled in dedicated CNC mode: " + line)
        elif key in replacements:
            output.append(f"{key[1]} = {replacements[key]}\n")
        else:
            output.append(line)
    (target / ini.name).write_text("".join(output))
    if configure_profile is not None:
        configure_profile(target / ini.name)
    config["ini"] = str(CONFIG / "machine" / ini.name)
    if config.get("cam"):
        inbox = resolve(config["cam"]["inbox"], source.parent)
        if _identity(inbox) is not None:
            _copy_directory(inbox, data_dir / "inbox")
        config["cam"]["inbox"] = str(DATA / "inbox")
    (config_dir / "launcher.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n"
    )


def _identity(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    return [info.st_dev, info.st_ino]


def _trusted(path):
    with _directory(path) as descriptor:
        info = os.fstat(descriptor)
        if info.st_uid != os.geteuid() or info.st_mode & 0o022:
            raise ValueError(f"Migration parent must be owned and protected: {path}")


def _parents(root):
    # The administrative roots must be protected before any staging or recovery.
    for relative in (CONFIG, DATA):
        path = root
        _trusted(path)
        for part in relative.parts[1:]:
            path /= part
            _trusted(path)


def _empty(path):
    if _identity(path) is None:
        return
    with _directory(path) as descriptor:
        if os.listdir(descriptor):
            raise ValueError(
                f"Existing machine data is preserved; directory is not empty: {path}"
            )


def _protect_staged(config_dir, data_dir, owner):
    for path in [config_dir, *config_dir.rglob("*")]:
        path.chmod(0o755 if path.is_dir() or path.stat().st_mode & 0o111 else 0o644)
    for name in _NAMES:
        directory = data_dir / name
        for path in [directory, *directory.rglob("*")]:
            path.chmod(0o700 if path.is_dir() else 0o600)
            if owner is not None:
                os.chown(path, *owner)
    for root in (config_dir, data_dir):
        for path in reversed([root, *root.rglob("*")]):
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)


def _journal(path, records):
    temporary = path.with_suffix(".new")
    with temporary.open("w") as stream:
        json.dump(records, stream)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    with _directory(path.parent) as descriptor:
        os.fsync(descriptor)


def _rename(source, destination):
    os.rename(source, destination)
    for parent in {source.parent, destination.parent}:
        with _directory(parent) as descriptor:
            os.fsync(descriptor)


def _recover(config_dir, data_dir):
    stages = {"config": config_dir / ".migration", "data": data_dir / ".migration"}
    for stage in stages.values():
        if _identity(stage) is not None:
            _trusted(stage)
    journal = stages["config"] / "transaction.json"
    records = json.loads(journal.read_text()) if journal.exists() else []
    allowed = [("data", name) for name in _NAMES] + [
        ("config", "machine"),
        ("config", "launcher.json"),
    ]
    if records and [(r["area"], r["name"]) for r in records] != allowed:
        raise ValueError(
            "Unrecognized migration recovery record; preserve it for review"
        )
    committed = (
        bool(records) and _identity(config_dir / "launcher.json") == records[-1]["new"]
    )
    exposed = committed or any(record.get("publishing") for record in records)
    if not committed:
        for record in reversed(records):
            area, name = record["area"], record["name"]
            parent = config_dir if area == "config" else data_dir
            final, saved = parent / name, stages[area] / "old" / name
            current = _identity(final)
            if current == record["new"]:
                _rename(final, stages[area] / "new" / name)
                current = None
            if current is not None and current != record["old"]:
                raise ValueError(
                    f"Migration destination changed; preserving recovery: {final}"
                )
            if _identity(saved) is not None:
                if current is not None or _identity(saved) != record["old"]:
                    raise ValueError(
                        f"Migration backup changed; preserving recovery: {saved}"
                    )
                _rename(saved, final)
    # Published data may have been opened by the operator. Keep its directory,
    # including late writes through old file descriptors, for manual recovery.
    data_stage = stages["data"]
    if _identity(data_stage) is not None:
        if exposed and (not committed or any(r["old"] is not None for r in records)):
            recovery = data_dir / ("migration-recovery-" + uuid.uuid4().hex)
            _rename(data_stage, recovery)
        else:
            shutil.rmtree(data_stage)
    if _identity(stages["config"]) is not None:
        shutil.rmtree(stages["config"])


@contextlib.contextmanager
def migration_lock(config_dir):
    _trusted(config_dir)
    lock = os.open(
        config_dir / ".migration.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600
    )
    with os.fdopen(lock, "r+") as stream:
        info = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or info.st_uid != os.geteuid()
            or info.st_mode & 0o077
        ):
            raise ValueError("Untrusted migration lock")
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def migrate(
    source, root=Path("/"), owner=None, configure_profile=None, *, source_is_ini=False
):
    """Publish copies; launcher.json is the final, durable commit marker."""
    root = Path(os.path.abspath(root))
    _parents(root)
    config_dir = root / CONFIG.relative_to("/")
    data_dir = root / DATA.relative_to("/")
    with migration_lock(config_dir):
        _recover(config_dir, data_dir)
        for name in ("machine", "launcher.json"):
            if _identity(config_dir / name) is not None:
                raise ValueError(
                    f"Existing appliance configuration is preserved: {config_dir / name}"
                )
        for name in _NAMES:
            _empty(data_dir / name)
        stages = {"config": config_dir / ".migration", "data": data_dir / ".migration"}
        try:
            for stage in stages.values():
                stage.mkdir(mode=0o700)
                (stage / "new").mkdir(mode=0o700)
                (stage / "old").mkdir(mode=0o700)
            _build(
                source,
                stages["config"] / "new",
                stages["data"] / "new",
                configure_profile,
                source_is_ini=source_is_ini,
            )
            _protect_staged(stages["config"] / "new", stages["data"] / "new", owner)
            records = []
            for area, names in (
                ("data", _NAMES),
                ("config", ("machine", "launcher.json")),
            ):
                parent = data_dir if area == "data" else config_dir
                for name in names:
                    records.append(
                        {
                            "area": area,
                            "name": name,
                            "old": _identity(parent / name),
                            "new": _identity(stages[area] / "new" / name),
                            "publishing": False,
                        }
                    )
            journal = stages["config"] / "transaction.json"
            _journal(journal, records)
            for record in records:
                area, name = record["area"], record["name"]
                parent = data_dir if area == "data" else config_dir
                final = parent / name
                if _identity(final) != record["old"]:
                    raise ValueError(f"Destination changed during migration: {final}")
                if record["old"] is not None:
                    _rename(final, stages[area] / "old" / name)
                    _empty(stages[area] / "old" / name)
                record["publishing"] = True
                _journal(journal, records)
                _rename(stages[area] / "new" / name, final)
        except BaseException:
            _recover(config_dir, data_dir)
            raise
        _recover(config_dir, data_dir)
    return config_dir / "machine"


def stage(source, destination, configure_profile=None, *, source_is_ini=False):
    """Expose a complete preview, or remove only the empty reservation we made."""
    destination = Path(os.path.abspath(destination))
    parent = destination.parent
    for path in reversed([parent, *parent.parents]):
        with _directory(path) as descriptor:
            info = os.fstat(descriptor)
            shared_temporary = info.st_uid == 0 and info.st_mode & stat.S_ISVTX
            if info.st_uid not in (0, os.geteuid()) or (
                info.st_mode & 0o022 and not shared_temporary
            ):
                raise ValueError(f"Untrusted staging parent: {path}")
    destination.mkdir(mode=0o700)
    reservation = _identity(destination)
    temporary = None
    try:
        temporary = Path(tempfile.mkdtemp(prefix=".bettercnc-stage-", dir=parent))
        (temporary / CONFIG.relative_to("/")).mkdir(parents=True)
        (temporary / DATA.relative_to("/")).mkdir(parents=True)
        migrate(
            source,
            temporary,
            configure_profile=configure_profile,
            source_is_ini=source_is_ini,
        )
        if _identity(destination) != reservation:
            raise ValueError("Staging destination changed; refusing to replace it")
        _rename(temporary, destination)
        temporary = None
    finally:
        if temporary is not None:
            shutil.rmtree(temporary)
        if _identity(destination) == reservation:
            destination.rmdir()
    return destination
