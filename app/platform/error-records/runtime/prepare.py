"""Install a checksum-pinned Oracle MySQL runtime into the application's build tree."""

import hashlib
import json
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

root = Path(sys.argv[1])
record = json.loads(Path(__file__).with_name("mysql.json").read_text())
root.mkdir(parents=True, exist_ok=True)
archive = root / "mysql.deb"
if (
    not archive.exists()
    or hashlib.sha256(archive.read_bytes()).hexdigest() != record["sha256"]
):
    with urllib.request.urlopen(record["url"], timeout=60) as response:
        content = response.read(record["size"] + 1)
    if (
        len(content) != record["size"]
        or hashlib.sha256(content).hexdigest() != record["sha256"]
    ):
        raise ValueError("MySQL runtime checksum mismatch")
    archive.write_bytes(content)
with subprocess.Popen(
    ["dpkg-deb", "--fsys-tarfile", str(archive)], stdout=subprocess.PIPE
) as process:
    with tarfile.open(fileobj=process.stdout, mode="r|") as package:
        for member in package:
            name = member.name.removeprefix("./")
            keep = (
                name == "usr/sbin/mysqld"
                or name.startswith(("usr/lib/mysql/", "usr/share/mysql/"))
                or name == "usr/share/doc/mysql-community-server-core/copyright"
            )
            if not keep or not member.isfile():
                continue
            if (
                ".." in Path(name).parts
                or name.startswith("/")
                or member.size > 200 * 1024**2
            ):
                raise ValueError("Unsafe MySQL runtime archive")
            target = root / "mysql" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(package.extractfile(member).read())
            target.chmod(0o755 if member.mode & 0o111 else 0o644)
    if process.wait() != 0:
        raise ValueError("Cannot read MySQL runtime package")
(root / "ready").write_text(record["sha256"] + "\n")
