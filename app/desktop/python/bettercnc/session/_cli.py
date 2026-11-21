"""Read-only status CLI, independent of a graphical runtime."""

import argparse
import json
import os

from ._client import read_machine_status


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-connection", action="store_true", required=True)
    parser.add_argument("--socket", default=os.environ.get("BETTERCNC_SOCKET"))
    args = parser.parse_args(argv)
    try:
        state = read_machine_status(args.socket)
    except (OSError, RuntimeError, ValueError) as error:
        print(json.dumps({"serviceConnected": False, "message": str(error)}, ensure_ascii=False))
        return 1
    print(json.dumps({"serviceConnected": True, "snapshot": state}, ensure_ascii=False))
    return 0 if state["connected"] else 2
