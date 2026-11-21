"""Repackage the verified application for updaters that only recognize the former name."""

import hashlib
from pathlib import Path
import re
import subprocess
import sys
import tempfile


def build(package):
    old = "betterlinuxcnc-qt"
    new = "betterlinuxcnc"
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary) / "package"
        subprocess.run(["dpkg-deb", "--raw-extract", package, root], check=True)
        control = root / "DEBIAN/control"
        fields = control.read_text()
        if not re.search(r"^Package: betterlinuxcnc$", fields, re.M):
            raise ValueError("Expected the canonical application package")
        fields = fields.replace(f"Package: {new}\n", f"Package: {old}\n")
        for field in ("Conflicts", "Replaces", "Provides"):
            fields, count = re.subn(rf"^{field}: {old}(?: \(= [^)]+\))?\n", "", fields, flags=re.M)
            if count != 1:
                raise ValueError(f"Unexpected {field} relationship")
        control.write_text(fields)
        for relative in ("usr/share/doc/betterlinuxcnc", "usr/share/applications/betterlinuxcnc.desktop"):
            path = root / relative
            path.rename(path.with_name(path.name.replace(new, old)))
        (root / "usr/share/betterlinuxcnc/package-rename").write_text(old + "\n")
        sums = root / "DEBIAN/md5sums"
        with sums.open("w") as output:
            for path in sorted(root.rglob("*")):
                relative = path.relative_to(root)
                if relative.parts[0] != "DEBIAN" and path.is_file():
                    with path.open("rb") as stream:
                        digest = hashlib.file_digest(stream, "md5").hexdigest()
                    print(f"{digest}  {relative}", file=output)
        target = package.with_name(package.name.replace(new + "_", old + "_", 1))
        subprocess.run(["dpkg-deb", "--root-owner-group", "--build", root, target], check=True)


if __name__ == "__main__":
    build(Path(sys.argv[1]))
