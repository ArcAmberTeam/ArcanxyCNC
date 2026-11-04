"""Explicit CLI. Defaults belong to the running project, never the home config."""

import argparse
import json
import os
import subprocess
from pathlib import Path

from bettercnc_error_records import install_exception_hooks, report

from ._autostart import run_kiosk_session, start_session
from ._config import load
from ._configuration_lease import configuration_lease
from ._supervisor import RecoveryBlocked, Runtime


def main(argv=None):
    install_exception_hooks("launcher")
    parser = argparse.ArgumentParser(description="BetterLinuxCNC 标准库启动编排")
    parser.add_argument("--config", type=Path, help="项目启动配置，默认 ./launcher.json")
    parser.add_argument("--ini", help="覆盖本次启动的 INI 路径")
    parser.add_argument("--check", action="store_true", help="只校验配置和依赖，不启动进程")
    parser.add_argument("--once", action="store_true", help="单次运行，不自动拉起退出的模块")
    session = parser.add_mutually_exclusive_group()
    session.add_argument("--session-start", action="store_true", help=argparse.SUPPRESS)
    session.add_argument("--kiosk-session", action="store_true", help="保持专用 X11 CNC 会话")
    args = parser.parse_args(argv)
    try:
        if args.kiosk_session:
            return run_kiosk_session()
        if args.session_start:
            return start_session()
        if args.config is not None and not args.config.expanduser().is_file():
            raise ValueError(f"启动配置不存在：{args.config}")
        config_path = (args.config or Path.cwd() / "launcher.json").expanduser().resolve()
        with configuration_lease(config_path, args.ini):
            config = load(config_path, args.ini)
            if args.check:
                print(json.dumps(config.plan(), ensure_ascii=False, indent=2))
                return 0
            with configuration_lease(config_path, str(config.ini)):
                # Resolve again under the final INI lease for external launcher files.
                config = load(config_path, args.ini)
                os.umask(0o077)
                return Runtime(config, keep_alive=not args.once).run()
    except RecoveryBlocked as error:
        report("launcher", "startup_blocked", str(error))
        print(f"无法启动：{error}")
        return 78
    except (subprocess.SubprocessError, OSError, ValueError) as error:
        report("launcher", "startup_error", str(error))
        parser.exit(1, f"无法启动：{error}\n")
