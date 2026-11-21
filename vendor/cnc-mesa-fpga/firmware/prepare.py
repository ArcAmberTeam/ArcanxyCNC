"""Compose an offline ISE workspace. Never program a device."""

import json
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
NS = "{http://www.xilinx.com/XMLSchema}"


def prepare(destination: Path) -> Path:
    profile = json.loads((ROOT / "mesa/board/zhulong-v2.json").read_text())
    upstream = ROOT / "hostmot2/upstream"
    tree = ET.parse(upstream / profile["ise_project"])
    properties = {p.attrib[NS + "name"]: p.attrib[NS + "value"] for p in tree.findall(f"{NS}properties/{NS}property")}
    for key, setting in (("Device", "fpga"), ("Package", "package"), ("Speed Grade", "speed_grade")):
        if properties[key] != profile[setting]:
            raise ValueError(f"Board {setting} disagrees with the selected ISE project")
    files = tree.getroot().find(NS + "files")
    constraints = [f.attrib[NS + "name"] for f in files if f.attrib[NS + "type"] == "FILE_UCF"]
    if constraints != [profile["constraints"]]:
        raise ValueError("Selected ISE project has different physical constraints")
    destination.mkdir(parents=True, exist_ok=True)
    # The upstream project includes many alternative boards. Select only the
    # required board/PIN while retaining its IP dependency and property list.
    for node in list(files):
        name = node.attrib[NS + "name"]
        if name.startswith("PIN_") or name.lower().endswith("card.vhd"):
            files.remove(node)
            continue
        source = upstream / name
        if not source.is_file():
            raise ValueError(f"Missing upstream project dependency: {name}")
        shutil.copyfile(source, destination / name)
    for name, source in (
        (profile["board_package"] + ".vhd", upstream / (profile["board_package"] + ".vhd")),
        (profile["pin_package"] + ".vhd", ROOT / "firmware/zhulong-v2" / (profile["pin_package"] + ".vhd")),
    ):
        shutil.copyfile(source, destination / name)
        node = ET.SubElement(files, NS + "file", {NS + "name": name, NS + "type": "FILE_VHDL"})
        ET.SubElement(node, NS + "association", {NS + "name": "Implementation", NS + "seqID": "0"})
    top_path = destination / profile["top_source"]
    top = top_path.read_text()
    top, count = re.subn(r"(?im)^use work\.\w*card\.all;[^\n]*", f'use work.{profile["board_package"]}.all;', top)
    if count != 1:
        raise ValueError("Expected exactly one active upstream board selection")
    top, count = re.subn(r"(?im)^use work\.PIN_\w+\.all;[^\n]*", f'use work.{profile["pin_package"]}.all;', top)
    if count != 1:
        raise ValueError("Expected exactly one active upstream pin selection")
    top_path.write_text(top)
    project = destination / "zhulong-v2.xise"
    ET.register_namespace("", NS[1:-1])
    ET.register_namespace("xil_pn", NS[1:-1])
    tree.write(project, encoding="utf-8", xml_declaration=True)
    (destination / "BOARD-VERIFICATION.txt").write_text(
        "Reconstructed logical pin map, Mesa 7i92 physical constraints.\n"
        "Verify Zhulong V2 FPGA pads, clock, Ethernet and flash wiring before programming.\n"
        "No claim of byte-for-byte equivalence to the original firmware.\n"
    )
    return project


if __name__ == "__main__":
    print(prepare(ROOT / ".build/firmware"))
