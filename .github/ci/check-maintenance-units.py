"""Check the packaged privilege-drop sandbox on a GitHub-hosted systemd runner."""

import configparser
import os
import pwd
import subprocess
from pathlib import Path


# --------#
# BEGIN: AxisRuntimeSandboxCheck
def check_axis_runtime(sandbox):
    """Exercise runtime visibility and socket access without starting CNC or a user session."""
    account = pwd.getpwnam("nobody")
    directory = Path(f"/run/user/{account.pw_uid}")
    if directory.exists() or directory.is_symlink():
        raise RuntimeError("Refuse to replace an existing runtime directory")
    subprocess.run(
        [
            "sudo",
            "install",
            "-d",
            "-m",
            "0700",
            "-o",
            str(account.pw_uid),
            "-g",
            str(account.pw_gid),
            str(directory),
        ],
        check=True,
    )
    server_code = r"""
import contextlib, os, socket, struct, sys
path, uid, gid = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
with contextlib.ExitStack() as stack:
    servers = []
    for name, expected_uid in [('control.sock', 0), ('bus', uid)]:
        server = stack.enter_context(socket.socket(socket.AF_UNIX))
        server.settimeout(90)
        server.bind(path + '/' + name)
        os.chown(path + '/' + name, uid, gid)
        os.chmod(path + '/' + name, 0o600)
        server.listen(1)
        servers.append((server, expected_uid))
    print('ready', flush=True)
    for server, expected_uid in servers:
        connection, _ = server.accept()
        with connection:
            connection.settimeout(5)
            _, actual_uid, _ = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            assert actual_uid == expected_uid
            assert connection.recv(64) == b'axis-runtime-check'
            connection.sendall(b'confirmed')
"""
    client_code = r"""
import errno, os, socket, sys
path, uid, name = sys.argv[1], int(sys.argv[2]), sys.argv[3]
assert os.getuid() == os.geteuid() == uid
with socket.socket(socket.AF_UNIX) as client:
    client.settimeout(5)
    client.connect(path + '/' + name)
    client.sendall(b'axis-runtime-check')
    assert client.recv(64) == b'confirmed'
try:
    with open(path + '/unexpected-write', 'x'):
        pass
except OSError as error:
    assert error.errno == errno.EROFS, error
else:
    raise AssertionError('Runtime directory is writable inside the sandbox')
print('runtime socket verified')
"""
    probe_code = r"""
import os, stat, subprocess, sys
path, uid, client = sys.argv[1], int(sys.argv[2]), sys.argv[3]
try:
    directory = os.stat(path)
    bus = os.stat(path + '/bus')
except FileNotFoundError:
    print('operator runtime hidden', file=sys.stderr)
    raise SystemExit(3)
assert stat.S_ISDIR(directory.st_mode) and directory.st_uid == uid
assert stat.S_IMODE(directory.st_mode) == 0o700
assert stat.S_ISSOCK(bus.st_mode) and bus.st_uid == uid
control = os.stat(path + '/control.sock')
assert stat.S_ISSOCK(control.st_mode) and control.st_uid == uid
assert stat.S_IMODE(control.st_mode) == 0o600
# The Rust updater observes machine.status as root, before stopping control.
subprocess.run(['/usr/bin/python3', '-c', client, path, '0', 'control.sock'], check=True)
subprocess.run(['/usr/sbin/runuser', '-u', 'nobody', '--', '/usr/bin/python3', '-c', client, path, str(uid), 'bus'], check=True)
"""
    server = None
    try:
        server = subprocess.Popen(
            [
                "sudo",
                "/usr/bin/python3",
                "-c",
                server_code,
                str(directory),
                str(account.pw_uid),
                str(account.pw_gid),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if server.stdout.readline().strip() != "ready":
            raise RuntimeError("Runtime socket fixture did not start")
        probe = [
            "/usr/bin/python3",
            "-c",
            probe_code,
            str(directory),
            str(account.pw_uid),
            client_code,
        ]
        broken = [
            "--property=ProtectHome=yes"
            if item.startswith("--property=ProtectHome=")
            else item
            for item in sandbox
        ]
        failed = subprocess.run(
            broken + probe, capture_output=True, text=True, timeout=30
        )
        if failed.returncode == 0 or "operator runtime hidden" not in failed.stderr:
            raise RuntimeError(
                "Legacy sandbox did not reproduce the missing runtime error: "
                + failed.stderr[-2000:]
            )
        missing_socket_access = [
            item.replace(" CAP_DAC_OVERRIDE", "")
            if item.startswith(
                ("--property=CapabilityBoundingSet=", "--property=AmbientCapabilities=")
            )
            else item
            for item in sandbox
        ]
        denied = subprocess.run(
            missing_socket_access + probe, capture_output=True, text=True, timeout=30
        )
        if denied.returncode == 0 or "PermissionError: [Errno 13]" not in denied.stderr:
            raise RuntimeError(
                "Missing socket capability did not reproduce permission denial: "
                + denied.stderr[-2000:]
            )
        result = subprocess.run(
            sandbox + probe, capture_output=True, text=True, timeout=30
        )
        if result.returncode or "runtime socket verified" not in result.stdout:
            raise RuntimeError("Axis runtime sandbox failed: " + result.stderr[-2000:])
        _, errors = server.communicate(timeout=10)
        if server.returncode:
            raise RuntimeError("Runtime peer verification failed: " + errors[-2000:])
        print(
            "Verified root control socket and unprivileged bus peers with read-only runtime; hidden runtime and missing socket capability rejected"
        )
    finally:
        if server is not None:
            server.communicate(timeout=95)
        subprocess.run(
            [
                "sudo",
                "rm",
                "-f",
                str(directory / "bus"),
                str(directory / "control.sock"),
                str(directory / "unexpected-write"),
            ],
            check=True,
        )
        subprocess.run(["sudo", "rmdir", str(directory)], check=True)


# END: AxisRuntimeSandboxCheck
# --------#


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
        sandbox = command.copy()
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
        if relative.endswith("betterlinuxcnc-axis-profile@.service.in"):
            check_axis_runtime(sandbox)


if __name__ == "__main__":
    main()
