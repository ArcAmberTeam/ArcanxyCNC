"""Package the FPGA and LinuxCNC integration trees from the DEB's Git commit."""

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tarfile


def package(output):
    root = Path(__file__).resolve().parents[2]
    commit = (output / "SOURCE_COMMIT").read_text().strip()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    if commit != head or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("DEB and Mesa sources must identify the same checkout")
    version = json.loads((root / "versions/version.json").read_text())["version"].split("-")[0]
    if not re.fullmatch(r"\d{2}\.\d{2}\.\d{2}\.\d+", version):
        raise ValueError("Invalid package version")
    fpga = root / "vendor/cnc-mesa-fpga"
    integration = root / "vendor/cnc-mesa"
    upstream = fpga / "hostmot2/upstream"
    files = json.loads((fpga / "hostmot2/manifest.json").read_text())["files"]
    actual = {p.relative_to(upstream).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in upstream.rglob("*") if p.is_file()}
    if actual != files:
        raise ValueError("FPGA source tree differs from its upstream checksums")
    pinned = json.loads((integration / "SOURCE.json").read_text())
    for name, digest in pinned["files"].items():
        shared = fpga / name
        if shared.is_file() and hashlib.sha256(shared.read_bytes()).hexdigest() != digest:
            raise ValueError(f"Inconsistent FPGA and integration source: {name}")
    board = json.loads((fpga / "mesa/board/zhulong-v2.json").read_text())
    timestamp = subprocess.check_output(["git", "show", "-s", "--format=%cI", commit], cwd=root, text=True).strip()
    archives = {}
    for kind, tree, entry in (("source", fpga, "firmware/prepare.py"),
                              ("integration", integration, "homing/prepare.py")):
        path = output / f"cnc-mesa-{kind}-{version}.tar.gz"
        subprocess.run(["git", "archive", "--format=tar.gz", f"--mtime={timestamp}", "-o", path,
                        f"{commit}:{tree.relative_to(root).as_posix()}"],
                       cwd=root, check=True)
        with tarfile.open(path) as archive:
            archive.getmember(entry)
        archives[kind] = {"asset": path.name, "size_bytes": path.stat().st_size,
                          "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    manifest = {
        "schema_version": 1, "version": version, "tag_name": f"v{version}",
        "compatible_app_version": version, "source_commit": commit,
        "board": board["name"], "variant": board["pin_package"],
        "fpga": board["fpga"], "package": board["package"],
        "physical_constraints_verified": board["physical_constraints_verified"],
        "firmware": {
            "available": False, "asset": None, "sha256": None, "size": None,
            "origin": "unavailable",
            "verification": {"implementation": False, "timing": False, "board_approved": False},
            "reason": "No implemented and board-verified bitstream is available for this release.",
        },
        "artifacts": archives,
    }
    (output / "mesa-release.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    package(Path(sys.argv[1]).resolve())
