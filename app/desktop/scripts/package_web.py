"""Build the locked Electron application in a private CMake build tree."""

import shutil
import subprocess
import sys
from pathlib import Path


def package(web, stage, npm):
    desktop = stage / "app/desktop"
    staged_web = desktop / "web"
    staged_web.mkdir(parents=True, exist_ok=True)
    for directory in ("src", "electron", "scripts", "public"):
        target = staged_web / directory
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(web / directory, target)
    for pattern in ("*.json", "*.ts", "*.html", "SHADCN-LICENSE"):
        for source in web.glob(pattern):
            shutil.copyfile(source, staged_web / source.name)
    shutil.copyfile(web.parent / "LICENSE", desktop / "LICENSE")
    versions = stage / "versions"
    versions.mkdir(exist_ok=True)
    shutil.copyfile(web.parents[2] / "versions/version.json", versions / "version.json")
    for arguments in (["ci", "--no-audit", "--no-fund"], ["run", "build"], ["run", "package"]):
        subprocess.run([npm, *arguments], cwd=staged_web, check=True)
    bundle = staged_web / "release/linux-unpacked"
    for relative in ("betterlinuxcnc-desktop", "chrome_crashpad_handler", "resources/app.asar"):
        if not (bundle / relative).is_file():
            raise RuntimeError(f"Missing packaged desktop component: {relative}")


if __name__ == "__main__":
    package(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3])
