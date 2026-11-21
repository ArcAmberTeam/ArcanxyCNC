"""Build the pinned HOMEMOD using this checkout's native headers in GitHub CI."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import tomllib

from commissioned_profile import REVISION, prepare_profile


PUBLIC_API = (
    "homeMotFunctions", "homing_init", "do_homing", "get_allhomed", "get_homed",
    "get_home_is_idle", "get_home_is_synchronized", "get_home_needs_unlock_first",
    "get_home_sequence", "get_homing", "get_homing_at_index_search_wait",
    "get_homing_is_active", "get_index_enable", "read_homing_in_pins",
    "do_home_joint", "do_cancel_homing", "set_unhomed", "set_joint_homing_params",
    "update_joint_homing_params", "write_homing_out_pins",
)
SCENARIOS = (
    "normal", "initially-active", "missing", "stuck", "final-stuck", "cancel",
    "cancel-retreat", "limit", "wrong-direction",
)


def run(*arguments, cwd=None, capture=False):
    return subprocess.run(
        [str(argument) for argument in arguments], cwd=cwd, check=True, text=True,
        stdout=subprocess.PIPE if capture else None,
    )


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_vendor(root):
    vendor = root / "vendor/cnc-mesa"
    source = json.loads((vendor / "SOURCE.json").read_text())
    if source["repository"] != "https://github.com/ArcAmberTeam/CNC-Mesa":
        raise ValueError("Unexpected vendor repository")
    if not re.fullmatch(r"[0-9a-f]{40}", source["commit"]):
        raise ValueError("Vendor source commit must be fixed")
    expected = source["files"]
    actual = {str(path.relative_to(vendor)) for path in vendor.rglob("*") if path.is_file()}
    if actual != set(expected) | {"SOURCE.json"}:
        raise ValueError("Vendor snapshot file set changed")
    for name, expected_digest in expected.items():
        path = vendor / name
        if path.is_symlink() or not path.resolve().is_relative_to(vendor.resolve()):
            raise ValueError("Vendor source must be an ordinary file inside its snapshot")
        if digest(path) != expected_digest:
            raise ValueError(f"Vendor snapshot checksum changed: {name}")
    return vendor, source


def copy_checkout(root, destination):
    files = subprocess.check_output([
        "/usr/bin/python3", str(root / ".github/ci/native-source-files.py"), str(root),
    ]).split(b"\0")
    for raw in filter(None, files):
        name = Path(os.fsdecode(raw))
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / name, target, follow_symlinks=False)


def verify_module(module):
    header = module.read_bytes()[:20]
    if header[:6] != b"\x7fELF\x02\x01" or int.from_bytes(header[18:20], "little") != 62:
        raise ValueError("Expected an ELF64 little-endian amd64 homing module")
    exported = {
        line.split()[-1] for line in run("nm", "-D", "--defined-only", module, capture=True).stdout.splitlines()
        if line.split()
    }
    required = set(PUBLIC_API) | {"rtapi_app_main", "rtapi_app_exit"}
    if not required <= exported:
        raise ValueError(f"Missing HOMEMOD exports: {sorted(required - exported)}")


def build(root, output, integration_tests):
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise ValueError("Homing builds are restricted to GitHub CI")
    vendor, source = verify_vendor(root)
    core_version = (root / "VERSION").read_text().strip()
    if core_version != "2.9.10":
        raise ValueError("Review the HOMEMOD ABI before changing the native core version")
    app_version = tomllib.loads((root / "app/desktop/pyproject.toml").read_text())["project"]["version"]
    commit = run("git", "-c", f"safe.directory={root}", "-C", root, "rev-parse", "HEAD", capture=True).stdout.strip()
    with tempfile.TemporaryDirectory(prefix="mesa-homing-") as temporary:
        work = Path(temporary)
        native = work / "native"
        copy_checkout(root, native)
        run("./autogen.sh", cwd=native / "src")
        run(
            "./configure", "--with-realtime=uspace", "--disable-check-runtime-deps",
            "--disable-build-documentation", "--disable-gtk", "--disable-gtk2",
            cwd=native / "src",
        )
        run("make", "-j2", "headers", "../bin/halcompile", cwd=native / "src")
        modinc = (native / "src/Makefile.modinc").read_text()
        if "RUN_IN_PLACE=yes" not in modinc or f"EMC2_HOME={native}" not in modinc:
            raise ValueError("halcompile must use this disposable native source tree")
        headers = native / "include"
        staged_vendor = native / "vendor/cnc-mesa"
        run("/usr/bin/python3", staged_vendor / "homing/prepare.py")
        module_work = staged_vendor / ".build/homing"
        prepare_profile(module_work, staged_vendor)
        run(native / "bin/halcompile", "--compile", "zhulong_homing.comp", cwd=module_work)
        module = module_work / "zhulong_homing.so"
        verify_module(module)
        harness = work / "test_homing"
        for name in ("test_homing", "test_parallel"):
            run(
                "cc", "-std=gnu11", "-DULAPI", "-DEXPORT_SYMBOL(x)=", "-Wall", "-Wextra",
                f"-I{headers}", f"-I{staged_vendor / 'homing/upstream'}",
                staged_vendor / f"tests/homing/{name}.c", module_work / "homing.c",
                staged_vendor / "homing/upstream/simple_tp.c", "-lm", "-o", harness,
            )
            scenarios = SCENARIOS if name == "test_homing" else (
                "normal", "initially-active", "missing", "stuck", "final-stuck", "cancel",
                "cancel-retreat", "limit", "invalid-backoff",
            )
            profiles = ((), ("negative-xyz",)) if name == "test_homing" else ((),)
            for profile in profiles:
                for axis in range(3):
                    for scenario in scenarios:
                        subprocess.run([str(harness), scenario, str(axis), *profile], check=True, timeout=15)
        if integration_tests:
            run("/usr/bin/python3", "-m", "unittest", "discover", "-s", "tests", "-p", "test_linuxcnc_config.py", "-v", cwd=staged_vendor)
            fpga = native / "vendor/cnc-mesa-fpga"
            run("/usr/bin/python3", fpga / "firmware/prepare.py", cwd=fpga)
            run("/usr/bin/python3", fpga / "tools/test_hdl.py", cwd=fpga)
        provenance = {
            "schema_version": 1, "module": "zhulong_homing.so", "sha256": digest(module),
            "architecture": "amd64", "application_version": app_version,
            "linuxcnc": {
                "version": core_version, "source_commit": commit, "build_system": "uspace",
                "headers": {path.name: digest(path) for path in sorted(headers.glob("*.h"))},
            },
            "vendor": source,
            "public_api": list(PUBLIC_API),
            "commissioning_profile": REVISION,
            "profile_adapter_sha256": digest(root / "tools/mesa-homing/commissioned_profile.py"),
            "validation": {"public_api_scenarios": 81, "hardware_verified": False},
        }
        output.mkdir(parents=True, exist_ok=True)
        shutil.copy2(module, output / module.name)
        (output / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print("PASS pinned HOMEMOD build, ELF exports and 81 public API scenarios; no hardware started")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--integration-tests", action="store_true")
    args = parser.parse_args()
    build(args.source.resolve(), args.output.resolve(), args.integration_tests)
