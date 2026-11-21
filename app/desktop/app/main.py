#!/usr/bin/env python3
"""Launch the packaged source-tree desktop or query controller status."""

import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "python"))

if "--check-connection" in sys.argv[1:]:
    from bettercnc.session import main

    raise SystemExit(main())

desktop = root / "web/release/linux-unpacked/betterlinuxcnc-desktop"
os.execv(desktop, [str(desktop), *sys.argv[1:]])
