"""Check the board IDROM and NC input path against unmodified Mesa HDL."""

from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if not shutil.which("ghdl"):
    raise SystemExit("GHDL is required (Debian: apt-get install ghdl).")
sources = [
    "hostmot2/upstream/IDROMConst.vhd",
    "hostmot2/upstream/i92_x9card.vhd",
    "hostmot2/upstream/wordpr.vhd",
    "hostmot2/upstream/wordrb.vhd",
    "firmware/zhulong-v2/PIN_ZHULONG_V2_34.vhd",
    "tests/hdl/board_profile_tb.vhd",
    "tests/hdl/nc_inputs_tb.vhd",
]
with tempfile.TemporaryDirectory(prefix="cnc-mesa-ghdl-") as work:
    for source in sources:
        subprocess.run(["ghdl", "-a", "--std=08", "-fsynopsys", str(ROOT / source)], cwd=work, check=True)
    for testbench in ("board_profile_tb", "nc_inputs_tb"):
        subprocess.run(["ghdl", "-r", "--std=08", "-fsynopsys", testbench, "--assert-level=error"], cwd=work, check=True, timeout=30)
