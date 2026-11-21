"""Debian package owning this installation."""

from pathlib import Path

PACKAGE = (
    "betterlinuxcnc-qt"
    if Path("/usr/share/betterlinuxcnc/package-rename").is_file()
    else "betterlinuxcnc"
)
