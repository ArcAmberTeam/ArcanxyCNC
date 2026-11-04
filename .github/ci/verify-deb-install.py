"""Exercise an actual DEB in the disposable GitHub CI container, never a machine."""

import configparser
import datetime
import fcntl
import grp
import hashlib
import json
import os
import pwd
import re
import secrets
import socket
import threading
import stat
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path


def run(*arguments, **kwargs):
    try:
        return subprocess.run(arguments, check=True, text=True, capture_output=True, **kwargs)
    except subprocess.CalledProcessError as error:
        lines = ((error.stdout or "") + "\n" + (error.stderr or "")).splitlines()
        print(f"{arguments[0]} failed with exit {error.returncode}; final diagnostics:", file=sys.stderr)
        print("\n".join(lines[-50:])[-8000:], file=sys.stderr)
        raise


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def validate_deb_paths(package, source):
    """Apply the root broker's exact archive contract before APT or postinst."""
    validator = source / "app/platform/updater/src/updater/package_members.py"
    for kind, option in (("data", "--fsys-tarfile"), ("control", "--ctrl-tarfile")):
        with tempfile.TemporaryFile() as errors:
            process = subprocess.Popen(
                ["/usr/bin/dpkg-deb", option, str(package)],
                stdout=subprocess.PIPE, stderr=errors,
            )
            try:
                result = subprocess.run(
                    ["/usr/bin/python3", "-I", "-S", str(validator), kind],
                    stdin=process.stdout, capture_output=True, text=True, timeout=60,
                )
                process.stdout.close()
                require(
                    result.returncode == 0,
                    f"DEB {kind} archive rejected by root broker: {result.stderr[-8000:].strip()}",
                )
                require(process.wait(timeout=30) == 0, "dpkg-deb could not read the package archive")
            except BaseException:
                if process.poll() is None:
                    process.kill()
                process.wait()
                raise
            finally:
                process.stdout.close()


def ownership(path, user, group, mode, directory=True):
    value = Path(path).lstat()
    require((stat.S_ISDIR if directory else stat.S_ISREG)(value.st_mode), f"Unexpected file type: {path}")
    require(value.st_uid == pwd.getpwnam(user).pw_uid, f"Unexpected owner: {path}")
    require(value.st_gid == grp.getgrnam(group).gr_gid, f"Unexpected group: {path}")
    require(stat.S_IMODE(value.st_mode) == mode, f"Unexpected permissions: {path}")


def accounts_and_paths():
    operator = pwd.getpwnam("linuxcnc")
    maintenance = pwd.getpwnam("cnc-maint")
    require(operator.pw_uid >= 1000 and maintenance.pw_uid >= 1000, "Invalid account UID")
    require(operator.pw_dir == "/var/lib/betterlinuxcnc/home", "Invalid operator HOME")
    require(maintenance.pw_dir == "/var/lib/betterlinuxcnc/maintenance", "Invalid maintenance HOME")
    for account in (operator, maintenance):
        names = {grp.getgrgid(gid).gr_name for gid in os.getgrouplist(account.pw_name, account.pw_gid)}
        require(not names & {"sudo", "adm", "disk", "root"}, "Privileged account group")
        require("cnc-logs" in names, "Missing read-only log group")
    for path in ("/etc/betterlinuxcnc", "/var/lib/betterlinuxcnc", "/var/cache/betterlinuxcnc", "/var/log/betterlinuxcnc"):
        ownership(path, "root", "root", 0o755)
    for child in ("home", "programs", "inbox", "machine"):
        ownership(f"/var/lib/betterlinuxcnc/{child}", "linuxcnc", "linuxcnc", 0o700)
    ownership("/var/cache/betterlinuxcnc/user", "linuxcnc", "linuxcnc", 0o700)
    ownership("/var/cache/betterlinuxcnc/update", "root", "root", 0o700)
    ownership("/var/lib/betterlinuxcnc/update", "root", "root", 0o755)
    ownership("/var/lib/betterlinuxcnc/maintenance", "root", "cnc-maint", 0o750)
    ownership("/var/log/betterlinuxcnc/launcher", "linuxcnc", "cnc-logs", 0o2750)
    return operator.pw_uid, maintenance.pw_uid


def password_digest():
    # Compare without exposing either a credential or its digest in CI output.
    value = next(line for line in Path("/etc/shadow").read_bytes().splitlines() if line.startswith(b"cnc-maint:"))
    return hashlib.sha256(value).digest()


def verify_maintenance_account():
    """Exercise installed Rust with actual account tools and authenticated sockets."""
    helper = "/usr/lib/betterlinuxcnc/account-management/cnc-maint/cnc-maint-account"
    ledger = Path("/var/lib/betterlinuxcnc/cnc-maint-policy-v1")
    ownership(helper, "root", "root", 0o755, directory=False)
    require(json.loads(run(helper, "status").stdout)["enabled"] is False, "New maintenance account is enabled")
    # Reproduce a pre-migration installation with a real existing password.
    run("/usr/sbin/betterlinuxcnc-appliance", "set-maintenance-password", input=secrets.token_urlsafe(32))
    ledger.unlink()
    run(helper, "provision")
    fields = next(line.split(":") for line in Path("/etc/shadow").read_text().splitlines() if line.startswith("cnc-maint:"))
    require(fields[1] == "!" and fields[7] == "1", "Migration retained an unlockable old password")
    listener = socket.socket(socket.AF_UNIX)
    endpoint = Path("/run/betterlinuxcnc-cnc-maint.sock")
    listener.bind(str(endpoint))
    listener.listen(1)
    listener.settimeout(15)
    operator = pwd.getpwnam("linuxcnc")
    os.chown(endpoint, operator.pw_uid, operator.pw_gid)
    endpoint.chmod(0o600)
    def request(operation, password="", success=True):
        failures = []
        def serve():
            try:
                connection, _ = listener.accept()
                with connection:
                    result = subprocess.run([helper, "serve"], stdin=connection,
                                            capture_output=True, timeout=15)
                    require(result.returncode == 0, "Account server failed")
            except BaseException as error:
                failures.append(error)
        worker = threading.Thread(target=serve)
        worker.start()
        result = subprocess.run(["/usr/sbin/runuser", "-u", "linuxcnc", "--", helper, "request", operation],
                                input=password, capture_output=True, text=True, timeout=20)
        worker.join(20)
        require(not worker.is_alive() and not failures, "Account socket exchange failed")
        require((result.returncode == 0) == success, "Unexpected account client outcome")
        require(not password or password not in result.stdout + result.stderr, "Credential leaked in output")
        return json.loads(result.stdout) if success else None
    try:
        require(request("status")["enabled"] is False, "Disabled account status lost")
        require(request("enable", secrets.token_urlsafe(32))["enabled"] is True, "Enabling failed")
        before = password_digest()
        require(request("enable", secrets.token_urlsafe(32))["enabled"] is True, "Changing password failed")
        require(password_digest() != before, "Password did not change")
        before = password_digest()
        run(helper, "provision")
        require(password_digest() == before, "Repeat provisioning revoked the new password")
        require(request("disable")["enabled"] is False, "Disabling failed")
        fields = next(line.split(":") for line in Path("/etc/shadow").read_text().splitlines() if line.startswith("cnc-maint:"))
        require(fields[1] == "!" and fields[7] == "1", "Disable kept credentials or account validity")
        for account in ("cnc-maint", "nobody"):
            result = subprocess.run(["/usr/sbin/runuser", "-u", account, "--", helper, "request", "status"],
                                    capture_output=True, timeout=10)
            require(result.returncode != 0, "Unauthorized account reached account management")
    finally:
        listener.close()
        endpoint.unlink(missing_ok=True)


def verify_xsession_entry():
    """Let Debian's real argument parser resolve the installed LightDM entry."""
    session = configparser.ConfigParser(interpolation=None)
    session.read("/usr/share/xsessions/betterlinuxcnc-kiosk.desktop")
    command = session["Desktop Entry"]["Exec"]
    # Source only the distribution's argument parser, never Xsession itself.
    # Neither Xorg, a desktop nor the CNC launcher is started in the CI container.
    script = r'''
message() { printf '%s\n' "$*" >&2; exit 41; }
errormsg() { message "$@"; }
has_option() { return 1; }
STARTUP=
. /etc/X11/Xsession.d/20x11-common_process-args
test "$STARTUP" = "$1"
printf '%s\n' "$STARTUP"
'''
    result = run("/bin/sh", "-eu", "-c", script, "xsession-entry", command)
    require(
        result.stdout.strip() == "/usr/bin/betterlinuxcnc-launch --kiosk-session",
        "Debian Xsession did not select the dedicated installed launcher",
    )


def verify_snapshot(path, version, expected_files, expected_directories):
    snapshots = Path("/var/lib/betterlinuxcnc/recovery/snapshots")
    require(path.parent == snapshots, "Backup returned a non-fixed destination")
    ownership(path, "root", "root", 0o700)
    manifest = json.loads((path / "manifest.json").read_text())
    require(
        set(manifest) == {
            "format", "package", "sourceVersion", "createdUtc", "files", "directories"
        },
        "Unexpected snapshot manifest schema",
    )
    require(manifest["format"] == "betterlinuxcnc-snapshot-v1", "Snapshot format mismatch")
    require(manifest["package"] == "betterlinuxcnc-qt", "Snapshot package mismatch")
    require(manifest["sourceVersion"] == version, "Snapshot installed version mismatch")
    stamp = manifest["createdUtc"]
    datetime.datetime.strptime(stamp, "%Y%m%dT%H%M%S%fZ")
    require(path.name == f"{stamp}-{version}", "Snapshot identity mismatch")
    files = {item["path"]: item for item in manifest["files"]}
    require(len(files) == len(manifest["files"]), "Duplicate snapshot source file")
    require(set(files) == set(expected_files), "Snapshot omitted or added source files")
    for source, item in files.items():
        require(
            set(item) == {"path", "mode", "uid", "gid", "size", "sha256"},
            "Unexpected snapshot file metadata",
        )
        content, metadata = expected_files[source]
        copied = path / "files" / source.lstrip("/")
        require(copied.read_bytes() == content, "Snapshot content mismatch")
        require(item["size"] == len(content), "Snapshot size mismatch")
        require(item["sha256"] == hashlib.sha256(content).hexdigest(), "Snapshot hash mismatch")
        require(
            (item["mode"], item["uid"], item["gid"]) == metadata,
            "Snapshot source ownership metadata mismatch",
        )
    directories = {item["path"]: item for item in manifest["directories"]}
    require(len(directories) == len(manifest["directories"]), "Duplicate source directory")
    require(set(directories) == expected_directories, "Snapshot source directories mismatch")
    for source, item in directories.items():
        require(set(item) == {"path", "mode", "uid", "gid"}, "Invalid directory metadata")
        require((path / "files" / source.lstrip("/")).is_dir(), "Missing snapshot directory")
        info = Path(source).stat()
        require(
            (item["mode"], item["uid"], item["gid"])
            == (stat.S_IMODE(info.st_mode), info.st_uid, info.st_gid),
            "Snapshot source directory metadata mismatch",
        )
    copied_files = set()
    for entry in path.rglob("*"):
        info = entry.lstat()
        require(info.st_uid == 0 and info.st_gid == 0, "Snapshot entry is not root-owned")
        if stat.S_ISDIR(info.st_mode):
            require(stat.S_IMODE(info.st_mode) == 0o700, "Snapshot directory is not private")
        else:
            require(stat.S_ISREG(info.st_mode), "Snapshot contains a link or special file")
            require(stat.S_IMODE(info.st_mode) == 0o600, "Snapshot file is not private")
            copied_files.add(entry.relative_to(path).as_posix())
    require(
        copied_files == {"manifest.json"} | {"files" + name for name in expected_files},
        "Snapshot contains unexpected files",
    )


def verify_installed_backup(version, policies):
    snapshots = Path("/var/lib/betterlinuxcnc/recovery/snapshots")
    require(not snapshots.exists(), "Expected a fresh CI snapshot store")
    sources = [Path("/etc/betterlinuxcnc"), Path("/var/lib/betterlinuxcnc/machine")]
    expected_directories = {str(source) for source in sources}
    expected_directories.update(
        str(entry) for source in sources for entry in source.rglob("*") if entry.is_dir()
    )
    source_files = [entry for source in sources for entry in source.rglob("*") if entry.is_file()]
    source_files.extend(Path(name) for name in policies if Path(name).is_file())
    expected = {}
    for path in source_files:
        info = path.stat()
        expected[str(path)] = (
            path.read_bytes(), (stat.S_IMODE(info.st_mode), info.st_uid, info.st_gid)
        )
    password = password_digest()
    created = []
    legacy = {}
    for attempt in range(4):
        result = json.loads(run("/usr/sbin/betterlinuxcnc-appliance", "backup", timeout=30).stdout)
        require(set(result) == {"snapshot", "sourceVersion", "files"}, "Invalid backup result")
        require(result["sourceVersion"] == version, "Backup result version mismatch")
        require(result["files"] == len(expected), "Backup result file count mismatch")
        current = Path(result["snapshot"])
        require(current not in created, "Backup replaced an earlier snapshot")
        created.append(current)
        ownership(snapshots.parent, "root", "root", 0o700)
        ownership(snapshots, "root", "root", 0o700)
        verify_snapshot(current, version, expected, expected_directories)
        if attempt == 0:
            # Preserve both historical recovery data and an unrelated retention entry.
            for parent in (snapshots.parent, snapshots):
                directory = parent / "legacy-before-demo"
                directory.mkdir(mode=0o700)
                marker = directory / "retain.txt"
                marker.write_bytes(b"Unrelated legacy backup must remain unchanged.\n")
                marker.chmod(0o600)
                legacy[marker] = marker.read_bytes()
        present = {
            path for path in snapshots.iterdir()
            if path.name not in {".lock", "legacy-before-demo"}
        }
        require(present == set(created[-3:]), "Backup retention did not keep exactly the latest three")
        for path in present:
            verify_snapshot(path, version, expected, expected_directories)
        for marker, content in legacy.items():
            require(marker.read_bytes() == content, "Backup retention changed legacy data")
    require(not created[0].exists(), "Fourth backup did not rotate the oldest snapshot")
    for source, (content, _) in expected.items():
        require(Path(source).read_bytes() == content, "Backup changed a source file")
    require(password_digest() == password, "Backup changed maintenance credentials")
    for account in ("linuxcnc", "cnc-maint"):
        result = subprocess.run(
            ["/usr/sbin/runuser", "-u", account, "--", "/usr/bin/test", "-r",
             str(created[-1] / "manifest.json")],
            capture_output=True, text=True,
        )
        require(result.returncode == 1, "Non-root account can read a configuration snapshot")


def verify_installed_homing(source, version):
    module = Path("/usr/lib/linuxcnc/modules/zhulong_homing.so")
    content = module.read_bytes()
    require(
        content[:6] == b"\x7fELF\x02\x01" and int.from_bytes(content[18:20], "little") == 62,
        "Expected a real ELF64 amd64 homing module",
    )
    info = module.lstat()
    require(
        stat.S_ISREG(info.st_mode) and info.st_uid == info.st_gid == 0
        and not info.st_mode & 0o6022,
        "Unsafe installed homing module ownership or mode",
    )
    metadata = json.loads(Path("/usr/share/betterlinuxcnc/homing/provenance.json").read_text())
    require(metadata["schema_version"] == 1, "Invalid homing provenance schema")
    require(metadata["application_version"] == version, "Homing application version mismatch")
    require(metadata["sha256"] == hashlib.sha256(content).hexdigest(), "Homing binary digest mismatch")
    require(metadata["architecture"] == "amd64", "Homing architecture mismatch")
    require(metadata["linuxcnc"]["version"] == (source / "VERSION").read_text().strip(), "Native core version mismatch")
    require(metadata["linuxcnc"]["source_commit"] == os.environ["BUILD_SHA"], "Homing build revision mismatch")
    for name in ("homing.h", "motion.h", "emcmotcfg.h", "simple_tp.h"):
        expected = hashlib.sha256((source / "src/emc/motion" / name).read_bytes()).hexdigest()
        require(metadata["linuxcnc"]["headers"][name] == expected, "Homing used unrelated native headers")
    require(metadata["vendor"] == json.loads((source / "vendor/cnc-mesa/SOURCE.json").read_text()), "Vendor provenance changed")
    api = set(re.findall(r"EXPORT_SYMBOL\((\w+)\);", (source / "vendor/cnc-mesa/homing/src/homing.c").read_text()))
    require(len(api) == 20 and set(metadata["public_api"]) == api, "HOMEMOD public API contract changed")
    symbols = {line.split()[-1] for line in run("nm", "-D", "--defined-only", str(module)).stdout.splitlines() if line.split()}
    require(api <= symbols, "Installed homing module omitted public API symbols")
    require(metadata["validation"] == {"public_api_scenarios": 81, "hardware_verified": False}, "Unexpected homing validation claim")
    require(metadata["commissioning_profile"] == "zhulong-xyz-v5-20261026", "Missing commissioned direction profile")
    require(metadata["profile_adapter_sha256"] == hashlib.sha256((source / "tools/mesa-homing/commissioned_profile.py").read_bytes()).hexdigest(), "Profile adapter provenance mismatch")
    # The distribution core is installed for package lifecycle checks only.
    # Never dlopen this module or infer ABI compatibility from successful installation.
    print("PASS installed HOMEMOD ELF, 20 public exports and fixed source/header provenance")


def verify_pa_configuration():
    """Exercise the installed fixed helper through the actual maintenance sudo grant."""
    helper = "/usr/lib/betterlinuxcnc/manage-ini/pa-config"
    ownership(helper, "root", "root", 0o755, directory=False)
    require(Path(helper).read_bytes().startswith(b"\x7fELF"), "Missing PA configuration ELF")
    launcher = Path("/etc/betterlinuxcnc/launcher.json")
    previous_launcher = launcher.read_bytes()
    require(json.loads(previous_launcher) == {"ciFixture": True}, "PA fixture must only replace the known CI retention fixture")
    machine = Path("/etc/betterlinuxcnc/machine")
    machine.mkdir(exist_ok=True)
    ini = machine / "pa-ci.ini"
    require(not ini.exists(), "PA fixture must not replace an existing INI")
    initial = "[EMC]\nMACHINE = CI file-only fixture\n[AXIS_X]\nMIN_LIMIT = 0\nMAX_LIMIT = 400\n"
    ini.write_text(initial)
    ini.chmod(0o644)
    launcher.write_text(json.dumps({"ini": str(ini)}))
    launcher.chmod(0o644)

    def request(value, ok=True, account="cnc-maint", extra=()):
        result = subprocess.run(
            ["/usr/sbin/runuser", "-u", account, "--", "/usr/bin/sudo", "-n", "--", helper, *extra],
            input=json.dumps(value), text=True, capture_output=True, timeout=45,
        )
        require((result.returncode == 0) == ok, f"Unexpected PA helper result: {result.stdout} {result.stderr}")
        return json.loads(result.stdout) if result.stdout else {}

    try:
        loaded = request({"operation": "read", "target": "ini"})["document"]
        require(loaded["content"] == initial, "PA did not load current INI")
        request({"operation": "read", "target": "/etc/shadow"}, ok=False)
        request({"operation": "read", "target": "ini"}, ok=False, account="linuxcnc")
        request({"operation": "read", "target": "ini"}, ok=False, extra=("--path", "/etc/shadow"))
        updated = initial + "[PA_CAM]\nDIMENSION_SOURCE = working_volume\nTABLE_X_MM = 300\nTABLE_Y_MM = 200\nTABLE_Z_MM = 80\n"
        save = {"operation": "save", "target": "ini", "revision": loaded["revision"], "content": updated}
        with Path("/var/lib/betterlinuxcnc/configuration.lock").open() as lease:
            fcntl.flock(lease, fcntl.LOCK_SH | fcntl.LOCK_NB)
            request(save, ok=False)
        lock = Path("/tmp/linuxcnc.lock")
        with lock.open("x"):
            try:
                request(save, ok=False)
            finally:
                lock.unlink()
        request({**save, "content": "[invalid"}, ok=False)
        with Path("/var/lib/betterlinuxcnc/recovery/snapshots/.lock").open() as snapshot_lock:
            fcntl.flock(snapshot_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            response = request(save, ok=False)
            require("Backup failed" in response["error"], "PA did not fail closed on backup failure")
        require(ini.read_text() == initial, "Rejected PA save changed the INI")
        saved = request(save)["document"]
        require(ini.read_text() == updated, "PA save did not reach the installed INI")
        require(saved["revision"] != loaded["revision"], "PA revision did not change")
        require(ini.stat().st_uid == 0 and stat.S_IMODE(ini.stat().st_mode) == 0o644, "PA changed INI ownership")
        request(save, ok=False)
        current_launcher = request({"operation": "read", "target": "launcher.json"})["document"]
        request({"operation": "save", "target": "launcher.json", "revision": current_launcher["revision"],
                 "content": json.dumps({"ini": str(ini), "startup_timeout": 60})})
        require(json.loads(launcher.read_text())["startup_timeout"] == 60, "Launcher save was lost")
        ini.unlink()
        ini.symlink_to("/etc/passwd")
        request({"operation": "read", "target": "ini"}, ok=False)
    finally:
        ini.unlink(missing_ok=True)
        launcher.write_bytes(previous_launcher)


def verify_maintenance_workspace(package, source, version):
    """Build through the installed non-root CLI; inspect artifacts without running CNC."""
    helper = "/usr/lib/betterlinuxcnc/account-management/cnc-maint/cnc-maint-account"
    workspace = Path("/var/lib/betterlinuxcnc/build")
    ownership(str(workspace), "root", "root", 0o755)
    for child in ("src", "work", "packages", "home"):
        ownership(str(workspace / child), "cnc-maint", "cnc-maint", 0o700)
    result = run("runuser", "-u", "cnc-maint", "--", helper, "workspace", "build-status")
    require(str(workspace) in result.stdout, "Maintenance workspace is unavailable")
    for account in ("root", "linuxcnc", "nobody"):
        result = subprocess.run(["runuser", "-u", account, "--", helper, "workspace", "build-status"], capture_output=True)
        require(result.returncode != 0, "Workspace accepted an unauthorized OS account")
    for args in (("git", "clone", "file:///etc"), ("git", "-c", "alias.x=!id", "x"), ("install-deb", "../outside.deb")):
        result = subprocess.run(["runuser", "-u", "cnc-maint", "--", helper, "workspace", *args], capture_output=True)
        require(result.returncode != 0, "Workspace accepted an unsupported command")
    # The checkout is a CI fixture; production Git remains HTTPS-only.
    import shutil
    checkout = workspace / "src/ArcanxyCNC"
    shutil.copytree(source, checkout, symlinks=True, ignore=shutil.ignore_patterns(".git", "__pycache__", "target"))
    run("chown", "-hR", "cnc-maint:cnc-maint", str(checkout))
    # A newer source version must not silently change the installed base version.
    cmake = checkout / "CMakeLists.txt"
    cmake.write_text(cmake.read_text().replace("VERSION " + version, "VERSION 99.1.1.1", 1))
    metadata = checkout / "app/desktop/python/bettercnc/__init__.py"
    metadata.write_text(metadata.read_text().replace(version, "99.1.1.1"))
    subprocess.run(["runuser", "-u", "cnc-maint", "--", helper, "workspace", "build-deb"], check=True, timeout=1500)
    built = list((workspace / "packages").glob("*.deb"))
    require(len(built) == 1, "Local build did not produce one package")
    require(run("dpkg-deb", "-f", str(built[0]), "Version").stdout.strip() == version, "Local build changed the Debian version")
    validate_deb_paths(built[0], source)
    for path in ("usr/lib/linuxcnc/modules/zhulong_homing.so", "usr/share/betterlinuxcnc/homing/provenance.json"):
        with tempfile.TemporaryDirectory() as temporary:
            run("dpkg-deb", "-x", str(built[0]), temporary)
            require((Path(temporary) / path).read_bytes() == (Path("/") / path).read_bytes(), "Local build replaced the commissioned homing payload")
            metadata = Path(temporary) / "usr/lib/betterlinuxcnc/python/bettercnc/__init__.py"
            require('__version__ = "' + version + '"' in metadata.read_text(), "Local desktop version differs from its DEB")
    # Exercise origin presentation with a real root-owned record, no machine operation.
    origin = Path("/var/lib/betterlinuxcnc/build-origin.json")
    origin.write_text(json.dumps({"schema_version": 1, "version": version, "sha256": hashlib.sha256(built[0].read_bytes()).hexdigest()}))
    origin.chmod(0o644)
    try:
        state = json.loads(run("betterlinuxcnc-updater", "status", env={"PATH":"/usr/bin:/bin", "HOME":"/root"}).stdout)
        require(state["self_compiled"] is True, "Self-compiled origin is not visible")
    finally:
        origin.unlink()
    state = json.loads(run("betterlinuxcnc-updater", "status", env={"PATH":"/usr/bin:/bin", "HOME":"/root"}).stdout)
    require(state["self_compiled"] is False, "Official origin did not clear")
    # Missing machine context must refuse the explicit upload before installation.
    before = run("dpkg-query", "-W", "-f=${Version}", "betterlinuxcnc-qt").stdout
    result = subprocess.run(["betterlinuxcnc-updater", "maintenance-install"], stdin=built[0].open("rb"), capture_output=True)
    require(result.returncode != 0, "Local installation ran without a managed controller context")
    require(run("dpkg-query", "-W", "-f=${Version}", "betterlinuxcnc-qt").stdout == before, "Rejected installation changed package state")
    print("Installed maintenance CLI built a same-version DEB as cnc-maint; archive, retained HOMEMOD, origin and preflight refusal verified")


def main():
    require(os.environ.get("GITHUB_ACTIONS") == "true" and os.geteuid() == 0, "GitHub CI container required")
    package, source = map(Path, sys.argv[1:])
    version = tomllib.loads((source / "app/desktop/pyproject.toml").read_text())["project"]["version"]
    fields = {field: run("dpkg-deb", "--field", str(package), field).stdout.strip() for field in ("Package", "Version", "Architecture")}
    require(fields == {"Package": "betterlinuxcnc-qt", "Version": version, "Architecture": "amd64"}, "Incorrect package metadata")
    require(package.name == f"betterlinuxcnc-qt_{version}_amd64.deb", "Incorrect package filename")
    validate_deb_paths(package, source)
    with tempfile.TemporaryDirectory() as temporary:
        control = Path(temporary)
        run("dpkg-deb", "--control", str(package), str(control))
        require({item.name for item in control.iterdir()} <= {"control", "md5sums", "conffiles", "postinst"}, "Unexpected control file")
        require((control / "postinst").read_bytes() == (source / "tools/appliance/packaging/postinst").read_bytes(), "Unexpected postinst bytes")
        require(stat.S_IMODE((control / "postinst").stat().st_mode) == 0o755, "postinst must be executable")
    # dpkg preserves directory modes during upgrades. Older manual installations
    # used group-writable application roots; provisioning must protect them.
    for name in ("/usr/lib/betterlinuxcnc", "/usr/share/betterlinuxcnc", "/usr/share/doc/betterlinuxcnc-qt"):
        path = Path(name)
        path.mkdir(parents=True, exist_ok=True)
        path.chmod(0o775)
    run("apt-get", "install", "-y", "--no-install-recommends", str(package))
    for name in ("/usr/lib/betterlinuxcnc", "/usr/share/betterlinuxcnc", "/usr/share/doc/betterlinuxcnc-qt"):
        ownership(name, "root", "root", 0o755)
    verify_xsession_entry()
    for name, directory in (
        ("betterlinuxcnc-axis-profile@.service", "/usr/lib/systemd/system"),
        ("00-betterlinuxcnc-axis-settings.rules", "/usr/share/polkit-1/rules.d"),
    ):
        installed = Path(directory) / name
        ownership(str(installed), "root", "root", 0o644, directory=False)
        require(installed.read_bytes() == (Path("/usr/lib/betterlinuxcnc/appliance") / name).read_bytes(), "Axis maintenance integration was not registered")
    require(
        run("dpkg-query", "-S", "/usr/bin/mesaflash").stdout.strip() == "mesaflash: /usr/bin/mesaflash",
        "The fixed mesaflash command must come from the distribution package",
    )
    require(Path("/usr/bin/mesaflash").read_bytes().startswith(b"\x7fELF"), "Missing real mesaflash dependency")
    identities = accounts_and_paths()
    verify_maintenance_account()
    require(not Path("/etc/betterlinuxcnc/launcher.json").exists(), "Package imported a machine configuration")
    require(not Path("/etc/lightdm/lightdm.conf.d/90-betterlinuxcnc.conf").exists(), "Package activated display policy")
    require("ForceCommand /usr/bin/python3 -I /usr/lib/betterlinuxcnc" not in Path("/etc/ssh/sshd_config").read_text(), "Package activated SSH policy")
    for executable in (
        "betterlinuxcnc-cam-link", "betterlinuxcnc-updater",
        "betterlinuxcnc-mesa-update", "betterlinuxcnc-mesa-flash",
    ):
        require(Path("/usr/bin", executable).read_bytes().startswith(b"\x7fELF"), "Expected a real Linux Rust binary")
        run(f"/usr/bin/{executable}", "--help")
    installed_version = run("/usr/bin/python3", "-c", "import sys; sys.path.insert(0, '/usr/lib/betterlinuxcnc/python'); from bettercnc import __version__; print(__version__)").stdout.strip()
    require(installed_version == version, "Installed application version mismatch")
    verify_installed_homing(source, version)
    run("/usr/bin/python3", str(source / ".github/ci/check-error-records.py"), str(source))
    verify_maintenance_workspace(package, source, version)

    # PA is installed in PATH without aliases, shell profiles, or elevated mode.
    ownership("/usr/bin/pa", "root", "root", 0o755, directory=False)
    require(Path("/usr/bin/pa").read_bytes().startswith(b"\x7fELF"), "Missing real PA binary")
    for target in ("ini", "launcher.json"):
        result = run("/usr/sbin/runuser", "-u", "cnc-maint", "--", "/usr/bin/pa", "manage", target, input="help\nexit\n")
        require("interactive terminal" in result.stdout, "PA non-TTY mode must explain how to open the editor")
        result = run("/usr/sbin/runuser", "-u", "cnc-maint", "--", "/usr/bin/env", f"SSH_ORIGINAL_COMMAND=pa manage {target}", "/usr/bin/python3", "-I", "/usr/lib/betterlinuxcnc/appliance/maintenance.py", input="exit\n")
        require("PA /" in result.stdout, "SSH fixed-command routing did not reach PA")
    for account in ("root", "linuxcnc"):
        result = subprocess.run(
            ["/usr/sbin/runuser", "-u", account, "--", "/usr/bin/env", "USER=cnc-maint", "LOGNAME=cnc-maint", "/usr/bin/pa", "manage", "ini"],
            capture_output=True, text=True, timeout=10,
        )
        require(result.returncode == 77, "PA accepted an unauthorized OS account")

    # Exercise upgrade preservation with private, synthetic data, never machine commands.
    fixtures = {
        "/etc/betterlinuxcnc/launcher.json": b'{"ciFixture":true}\n',
        "/var/lib/betterlinuxcnc/programs/retain.ngc": b"; retained CI program\n",
        "/var/lib/betterlinuxcnc/inbox/retain.ngc": b"; retained CI inbox\n",
        "/var/lib/betterlinuxcnc/machine/tool.tbl": b"; retained CI tool data\n",
        "/var/log/betterlinuxcnc/launcher/retain.log": b"retained CI log\n",
    }
    for name, content in fixtures.items():
        Path(name).write_bytes(content)
    updater = Path("/etc/betterlinuxcnc/updater.json")
    fixtures[str(updater)] = updater.read_bytes() + b"\n"
    updater.write_bytes(fixtures[str(updater)])
    run("/usr/sbin/betterlinuxcnc-appliance", "set-maintenance-password", input=secrets.token_urlsafe(32) + "\n")
    password = password_digest()
    policies = json.loads(run("/usr/sbin/betterlinuxcnc-appliance", "plan").stdout)["policyFiles"]
    previous = {name: Path(name).read_bytes() if Path(name).is_file() else None for name in policies}
    run("dpkg", "--force-confold", "--install", str(package))
    require(accounts_and_paths() == identities, "Repeated install changed account identities")
    require(password_digest() == password, "Repeated install changed maintenance credentials")
    for name, content in fixtures.items():
        require(Path(name).read_bytes() == content, f"Repeated install changed persistent data: {name}")
    for name, content in previous.items():
        require((Path(name).read_bytes() if Path(name).is_file() else None) == content, f"Repeated install changed login policy: {name}")

    # Explicit activation is tested only here, in a container with no init or machine.
    run("ssh-keygen", "-A")
    Path("/run/sshd").mkdir(exist_ok=True)
    run("/usr/sbin/betterlinuxcnc-appliance", "activate")
    # Reproduce an activated pre-PA appliance, then upgrade through real postinst.
    ssh_policy = Path("/etc/ssh/sshd_config")
    sudo_policy = Path("/etc/sudoers")
    ssh_policy.write_text(ssh_policy.read_text().replace("PermitTTY yes", "PermitTTY no"))
    sudo_policy.write_text("\n".join(line for line in sudo_policy.read_text().split("\n") if "pa-config" not in line and "cnc-maint-sudo" not in line and "cnc-maint-account" not in line))
    run("dpkg", "--force-confold", "--install", str(package))
    require(password_digest() == password, "Maintenance policy migration changed credentials")
    require(list(Path("/var/lib/betterlinuxcnc/recovery").glob("*-pa-policy/policies.json")), "Missing pre-PA policy recovery")
    run("/usr/sbin/sshd", "-t")
    run("/usr/sbin/visudo", "-c")
    effective = run("/usr/sbin/sshd", "-T", "-C", "user=cnc-maint,host=localhost,addr=127.0.0.1").stdout
    for setting in ("allowusers cnc-maint", "permitrootlogin no", "permittty yes", "disableforwarding yes", "forcecommand /usr/bin/python3 -I /usr/lib/betterlinuxcnc/appliance/maintenance.py"):
        require(setting in effective.splitlines(), f"Missing effective SSH restriction: {setting}")
    sudo_rules = [
        line.strip() for line in Path("/etc/sudoers").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith(("#", "Defaults"))
    ]
    require(sudo_rules == [
        "root ALL=(ALL:ALL) ALL",
        'cnc-maint ALL=(root) NOPASSWD: /usr/lib/betterlinuxcnc/manage-ini/pa-config ""',
        '@include /etc/betterlinuxcnc/cnc-maint-sudo',
        'cnc-maint ALL=(root) PASSWD: /usr/lib/betterlinuxcnc/account-management/cnc-maint/cnc-maint-account sudo-open',
    ], "Unexpected ordinary-user sudo rule or include")
    require("#include" not in Path("/etc/sudoers").read_text(), "Unexpected sudoers include")
    for account in ("linuxcnc", "cnc-maint"):
        # Listing as root can succeed while reporting that the selected user has no grants.
        # Exercise actual denial from each unprivileged identity using a read-only command.
        result = subprocess.run(
            ["/usr/sbin/runuser", "-u", account, "--", "/usr/bin/sudo", "-n", "-k",
             "/usr/bin/id", "-u"],
            capture_output=True, text=True,
        )
        require(
            result.returncode != 0 and result.stdout.strip() != "0",
            f"Unexpected sudo execution by {account}: {result.stdout} {result.stderr}",
        )
    verify_installed_backup(version, policies)
    verify_pa_configuration()
    ownership("/etc/betterlinuxcnc/cnc-maint-sudo", "root", "root", 0o440, directory=False)
    require("NOPASSWD: ALL" not in Path("/etc/betterlinuxcnc/cnc-maint-sudo").read_text(), "Package opened sudo authorization")
    denied = subprocess.run(["runuser", "-u", "cnc-maint", "--", "sudo", "-n", "-k", "/usr/lib/betterlinuxcnc/account-management/cnc-maint/cnc-maint-account", "sudo-open"], capture_output=True, text=True)
    require(denied.returncode != 0 and "password" in denied.stderr.lower(), "Sudo activation did not require fresh authentication")
    print("DEB metadata, Rust binaries, provisioning, data retention, PA configuration, SSH/sudo and private backup rotation passed")


if __name__ == "__main__":
    main()
