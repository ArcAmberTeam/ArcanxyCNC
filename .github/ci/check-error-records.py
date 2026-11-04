"""Installed MySQL and error-client acceptance in an isolated CI container only."""

import json
import ctypes
import errno
import os
import pwd
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

BASE = Path("/usr/lib/betterlinuxcnc/error-records")
BINARY = BASE / "betterlinuxcnc-error-records"
STATE = Path("/var/lib/betterlinuxcnc/error-records")
RUNTIME = Path("/run/betterlinuxcnc-error-records")
EXPORT = Path("/var/log/betterlinuxcnc/errors")


def restrict_special_mode_bits():
    """Apply the updater's chmod SGID/SUID restriction to the child only."""
    class Argument(ctypes.Structure):
        _fields_ = [
            ("arg", ctypes.c_uint),
            ("op", ctypes.c_int),
            ("mask", ctypes.c_uint64),
            ("value", ctypes.c_uint64),
        ]

    library = ctypes.CDLL("libseccomp.so.2")
    library.seccomp_init.argtypes = [ctypes.c_uint32]
    library.seccomp_init.restype = ctypes.c_void_p
    library.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    library.seccomp_rule_add_array.argtypes = [
        ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint,
        ctypes.POINTER(Argument),
    ]
    library.seccomp_load.argtypes = [ctypes.c_void_p]
    library.seccomp_release.argtypes = [ctypes.c_void_p]
    context = library.seccomp_init(0x7FFF0000)
    if not context:
        raise RuntimeError("Cannot initialize the installation sandbox")
    try:
        for name, argument in ((b"chmod", 1), (b"fchmod", 1), (b"fchmodat", 2), (b"fchmodat2", 2)):
            syscall = library.seccomp_syscall_resolve_name(name)
            if syscall < 0:
                if name == b"fchmodat2":
                    continue
                raise RuntimeError("Missing chmod syscall")
            for bit in (0o2000, 0o4000):
                comparison = Argument(argument, 7, bit, bit)
                result = library.seccomp_rule_add_array(
                    context, 0x00050000 | errno.EPERM, syscall, 1,
                    ctypes.byref(comparison),
                )
                if result != 0:
                    raise RuntimeError("Cannot install chmod restriction")
        if library.seccomp_load(context) != 0:
            raise RuntimeError("Cannot activate the installation sandbox")
    finally:
        library.seccomp_release(context)


def run(*args, **kwargs):
    return subprocess.run(
        args, text=True, capture_output=True, check=True, timeout=20, **kwargs
    )


def query(filter=""):
    command = "errors" + (" " + filter if filter else "")
    output = run(
        "runuser",
        "-u",
        "cnc-maint",
        "--",
        "env",
        f"SSH_ORIGINAL_COMMAND={command}",
        "python3",
        "-I",
        "/usr/lib/betterlinuxcnc/appliance/maintenance.py",
    )
    return json.loads(output.stdout)


def wait(predicate, description):
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            result = predicate()
            if result:
                return result
        except (subprocess.SubprocessError, ValueError, OSError, KeyError):
            pass
        time.sleep(0.5)
    raise AssertionError(description)


def emit(message):
    script = (
        "import sys; sys.path.insert(0, '/usr/lib/betterlinuxcnc/python'); "
        "from bettercnc_error_records import report; "
        f"report('controller','invalid_params',{message!r},"
        "{'joint':4,'velocity':61,'mode':'joint','password':'must-not-persist'})"
    )
    run("runuser", "-u", "linuxcnc", "--", "python3", "-I", "-c", script)


def main():
    if (
        os.environ.get("GITHUB_ACTIONS") != "true"
        or os.geteuid() != 0
        or Path("/run/systemd/system").exists()
    ):
        raise SystemExit("Only an isolated GitHub installation container is supported")
    import grp

    account = pwd.getpwnam("cnc-errors")
    group = grp.getgrnam("cnc-logs").gr_gid
    # Real installed provisioning must work under the update service's filter.
    # Verify the restriction itself, so an ineffective fixture cannot pass.
    with tempfile.TemporaryDirectory() as scratch:
        denied = subprocess.run(
            ["chmod", "2750", scratch], capture_output=True,
            preexec_fn=restrict_special_mode_bits,
        )
        assert denied.returncode != 0, "SGID restriction was not applied"
    run(str(BINARY), "provision", preexec_fn=restrict_special_mode_bits)
    assert EXPORT.stat().st_mode & 0o7777 == 0o750
    RUNTIME.mkdir(exist_ok=True)
    os.chown(RUNTIME, account.pw_uid, group)
    RUNTIME.chmod(0o755)
    run(
        "runuser",
        "-u",
        "cnc-errors",
        "--",
        "test",
        "-x",
        str(BASE / "mysql/usr/sbin/mysqld"),
    )
    assert (BASE / "mysql/usr/share/mysql-8.4/english/errmsg.sys").is_file()
    with tempfile.TemporaryFile(mode="w+") as output:
        service = subprocess.Popen(
            [
                "runuser",
                "-u",
                "cnc-errors",
                "-g",
                "cnc-logs",
                "--",
                str(BINARY),
                "serve",
            ],
            start_new_session=True,
            stdout=output,
            stderr=output,
        )
        try:
            wait(
                lambda: query("status")["database"] == "ready",
                "MySQL did not become ready",
            )
            assert (BASE / "mysql/usr/sbin/mysqld").read_bytes()[:4] == b"\x7fELF"
            password = (STATE / "mysql-password").read_bytes()
            assert len(password) == 64
            run(str(BINARY), "provision")
            assert (STATE / "mysql-password").read_bytes() == password
            emit(
                "invalid parameter: rotary speed exceeds limit password=private-test-token"
            )
            records = wait(
                lambda: query("parameters")["events"], "Missing parameter event"
            )
            record = next(
                event for event in records if "rotary speed" in event["message"]
            )
            assert record["uid"] == pwd.getpwnam("linuxcnc").pw_uid
            assert record["context"] == {"joint": 4, "velocity": 61, "mode": "joint"}
            assert "private-test-token" not in json.dumps(record)
            assert query(record["event_id"])["events"] == [record]
            assert query()["server_version"].startswith("8.4.")
            exported = list(EXPORT.glob("parameters/*/events-*.jsonl"))
            assert any(record["event_id"] in path.read_text() for path in exported)
            run("runuser", "-u", "cnc-maint", "--", "test", "-r", str(exported[0]))

            # Exercise the installed public Controller against a test-only vendor seam.
            script = """
import sys
sys.path.insert(0, '/usr/lib/betterlinuxcnc/python')
sys.path.insert(0, sys.argv[1])
from test_controller import FakeLinuxCNC
from bettercnc_controller import Controller
vendor = FakeLinuxCNC()
controller = Controller(module=vendor)
controller.poll()
assert not controller.dispatch('jog.start', {'axis':'X','velocity':31,'direction':1})
assert not vendor.calls
"""
            run(
                "python3",
                "-I",
                "-c",
                script,
                str(Path(sys.argv[1]) / "app/controller/tests"),
            )
            wait(
                lambda: any(
                    e["context"].get("velocity") == 31
                    and e["context"].get("limit") == 30
                    for e in query("parameters")["events"]
                ),
                "Raw Controller rejection was not captured",
            )

            for name in (STATE / "mysql-password", RUNTIME / "mysql/mysql.sock"):
                denied = subprocess.run(
                    ["runuser", "-u", "cnc-maint", "--", "test", "-r", str(name)]
                )
                assert denied.returncode != 0, (
                    "Maintenance account can access private database"
                )
            for filter in ("../../etc/passwd", "SELECT * FROM events"):
                denied = subprocess.run(
                    [str(BINARY), "query", filter], capture_output=True
                )
                assert denied.returncode != 0
            denied = subprocess.run(
                ["runuser", "-u", "nobody", "--", str(BINARY), "query"],
                capture_output=True,
            )
            assert denied.returncode != 0

            # Pause only the test database; control clients remain nonblocking and exports persist.
            mysql_pid = int((RUNTIME / "mysql/mysql.pid").read_text())
            os.kill(mysql_pid, signal.SIGSTOP)
            try:
                before = time.monotonic()
                emit("invalid parameter: database-outage-acceptance")
                assert time.monotonic() - before < 2
                wait(
                    lambda: query("status")["pending"] > 0,
                    "Outage event was not queued",
                )
                wait(
                    lambda: any(
                        "database-outage-acceptance" in p.read_text()
                        for p in EXPORT.glob("parameters/*/*.jsonl")
                    ),
                    "Outage event was not exported",
                )
            finally:
                os.kill(mysql_pid, signal.SIGCONT)
            wait(
                lambda: any(
                    "database-outage-acceptance" in e["message"]
                    for e in query("parameters")["events"]
                ),
                "Queued event was not replayed",
            )
            wait(lambda: query("status")["pending"] == 0, "Replay did not clear queue")
            assert (
                len(
                    [
                        e
                        for e in query()["events"]
                        if "database-outage-acceptance" in e["message"]
                    ]
                )
                == 1
            )
            print(
                "Real MySQL persistence, Controller errors, exports, credential boundaries and outage replay passed"
            )
        except Exception:
            diagnostics = subprocess.run(
                [str(BINARY), "query", "status"],
                text=True,
                capture_output=True,
                timeout=15,
            )
            print(diagnostics.stdout + diagnostics.stderr, file=sys.stderr)
            for path in (
                STATE,
                Path("/var/lib/mysql"),
                Path("/var/lib/mysql/betterlinuxcnc-errors"),
                BASE / "mysql/usr/sbin/mysqld",
            ):
                print(
                    str(path),
                    path.stat() if path.exists() else "missing",
                    file=sys.stderr,
                )
            output.seek(0)
            print(output.read()[-12000:], file=sys.stderr)
            raise
        finally:
            os.killpg(service.pid, signal.SIGTERM)
            service.wait(timeout=65)


if __name__ == "__main__":
    main()
