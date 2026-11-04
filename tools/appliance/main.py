"""Root-only account provisioning and explicit machine/policy administration."""

import argparse
import configparser
import functools
import json
import os
import pwd
import subprocess
import sys
from pathlib import Path

# -I rejects caller-controlled Python paths; only installed sibling modules load.
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, "/usr/lib/betterlinuxcnc/python")
import _accounts
import _axis_upgrade
import _backup
import _homing
import _machine
import _policy
import axis_profiles
from bettercnc_error_records import report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    profiles = commands.add_parser(
        "axis-profile",
        help="Automatically write the installed machine axis configuration",
    )
    operations = profiles.add_subparsers(dest="operation", required=True)
    operations.add_parser("status")
    for operation in ("request", "switch-system", "prepare-system", "apply-system"):
        command = operations.add_parser(operation)
        command.add_argument("axes", type=int, choices=(3, 4, 5))
        if operation == "apply-system":
            command.add_argument("revision")
    commands.add_parser(
        "plan", help="Show fixed paths and account policy without changing the host"
    )
    commands.add_parser(
        "provision",
        help="Idempotently create dedicated accounts and system data directories",
    )
    commands.add_parser(
        "backup", help="Create a verified root-private configuration snapshot"
    )
    commands.add_parser(
        "migrate-machine",
        help="Apply the fixed commissioned XYZ correction while stopped",
    )
    stage = commands.add_parser(
        "stage", help="Preview a machine import in a new staging directory"
    )
    stage.add_argument("--source-config", required=True, type=Path)
    stage.add_argument("--destination", required=True, type=Path)
    prepare = commands.add_parser(
        "prepare", help="Create accounts and copy an existing machine profile"
    )
    prepare.add_argument("--source-config", required=True, type=Path)
    for command in (stage, prepare):
        homing = command.add_mutually_exclusive_group()
        homing.add_argument(
            "--zhulong-inputs-only",
            action="store_true",
            help="Connect verified XYZ switches and inhibit homing without measured travel",
        )
        homing.add_argument(
            "--zhulong-homing-travel-mm",
            nargs=3,
            type=float,
            metavar=("X", "Y", "Z"),
            help="Enable the reviewed Zhulong HOMEMOD using measured XYZ total travel in mm",
        )
        command.add_argument(
            "--zhulong-xyz-only",
            action="store_true",
            help="Remove the reviewed unused ABC configuration; requires measured homing travel",
        )
    commands.add_parser(
        "set-maintenance-password", help="Read one initial password from stdin"
    )
    commands.add_parser(
        "activate", help="Install fixed login policies; does not restart the display"
    )
    args = parser.parse_args()
    if args.action == "axis-profile":
        result = axis_profiles.run(
            args.operation, getattr(args, "axes", None), getattr(args, "revision", None)
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0
    configure_profile = None
    if args.action in ("stage", "prepare"):
        travel = _homing.measured_travel(args.zhulong_homing_travel_mm)
        if args.zhulong_xyz_only and travel is None:
            raise ValueError(
                "--zhulong-xyz-only requires --zhulong-homing-travel-mm X Y Z"
            )
        if args.zhulong_inputs_only or travel is not None:
            configure_profile = functools.partial(
                _homing.prepare,
                travel=travel,
                installation_verified=args.action == "prepare" and travel is not None,
                xyz_only=args.zhulong_xyz_only,
            )
    if args.action == "plan":
        print(
            json.dumps(
                {
                    "operator": _accounts.OPERATOR,
                    "maintenance": _accounts.MAINTENANCE,
                    "operatorHome": str(_accounts.HOME),
                    "config": str(_machine.CONFIG),
                    "data": str(_machine.DATA),
                    "policyFiles": list(_policy.POLICIES),
                    "passwordInPackage": False,
                    "automaticActivation": False,
                    "automaticAccountProvisioning": True,
                    "snapshots": _backup.SNAPSHOTS,
                },
                indent=2,
            )
        )
        return 0
    if args.action == "stage":
        root = _machine.stage(args.source_config, args.destination, configure_profile)
        print(f"Migration staged without changing host policy: {root}")
        if args.zhulong_homing_travel_mm is not None:
            print(
                "HOMEMOD installation and LinuxCNC version will be verified by prepare"
            )
        return 0
    if sys.platform != "linux" or os.geteuid() != 0:
        raise ValueError("Host provisioning requires a Linux root maintenance session")
    if args.action == "provision":
        _accounts.provision()
        axis_profiles.install_integration()
        account_manager = Path(
            "/usr/lib/betterlinuxcnc/account-management/cnc-maint/cnc-maint-account"
        )
        if account_manager.is_file():
            _accounts.run(str(account_manager), "provision")
        print("Maintenance policy: " + _policy.upgrade_maintenance())
        error_records = Path(
            "/usr/lib/betterlinuxcnc/error-records/betterlinuxcnc-error-records"
        )
        if error_records.is_file():
            _accounts.run(str(error_records), "provision")
        print("Machine axis migration: " + _axis_upgrade.upgrade())
        if Path("/run/systemd/system").is_dir():
            _accounts.run("/usr/bin/systemctl", "daemon-reload")
        print("Provisioned dedicated accounts and system data directories")
    elif args.action == "migrate-machine":
        print("Machine axis migration: " + _axis_upgrade.upgrade())
    elif args.action == "backup":
        print(json.dumps(_backup.backup()))
    elif args.action == "prepare":
        if args.zhulong_homing_travel_mm is not None:
            _homing.validate_installed()
        _accounts.prepare()
        account = pwd.getpwnam(_accounts.OPERATOR)
        _policy.write(
            "/etc/betterlinuxcnc/updater.json",
            json.dumps(
                {"user": "linuxcnc", "config": "/etc/betterlinuxcnc/launcher.json"}
            )
            + "\n",
        )
        _machine.migrate(
            args.source_config,
            owner=(account.pw_uid, account.pw_gid),
            configure_profile=configure_profile,
        )
        print("Prepared fixed appliance paths; original machine files are preserved")
    elif args.action == "set-maintenance-password":
        _accounts.password(sys.stdin.readline(258).rstrip("\n"))
        print("Maintenance password configured; future updates do not reset it")
    elif args.action == "activate":
        for name in ("linuxcnc", "cnc-maint"):
            pwd.getpwnam(name)
        if not Path("/etc/betterlinuxcnc/launcher.json").is_file():
            raise ValueError("Prepare and verify the machine configuration first")
        if not Path("/usr/share/xsessions/betterlinuxcnc-kiosk.desktop").is_file():
            raise ValueError(
                "The installed package does not provide the dedicated session"
            )
        recovery = _policy.install()
        if Path("/run/systemd/system").is_dir():
            _accounts.run(
                "/usr/bin/systemctl",
                "enable",
                "--now",
                "betterlinuxcnc-mesa-update.timer",
            )
        print(f"Login policy installed; recovery manifest: {recovery}/policies.json")
        print(
            "Validate a new maintenance SSH connection before retiring the current session"
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        ValueError,
        KeyError,
        TypeError,
        OSError,
        configparser.Error,
        subprocess.SubprocessError,
    ) as error:
        report("configuration", "appliance_error", str(error))
        print(f"Appliance provisioning refused: {error}", file=sys.stderr)
        raise SystemExit(1) from None
