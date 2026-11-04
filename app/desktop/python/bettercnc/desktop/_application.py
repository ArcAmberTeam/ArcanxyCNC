"""PySide6 owns the QML engine and injects the public QObject backend."""

import argparse
import json
import os
import sys
from pathlib import Path

from bettercnc_error_records import install_exception_hooks
from PySide6.QtCore import QCoreApplication, Qt, QTimer, QUrl
from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from bettercnc import __version__


def main(argv=None):
    install_exception_hooks("desktop")
    parser = argparse.ArgumentParser(description="BetterLinuxCNC QML desktop")
    parser.add_argument("-ini", "--ini", dest="ini", help="Require the service to use this INI")
    parser.add_argument(
        "--socket",
        default=os.environ.get("BETTERCNC_SOCKET"),
        help="Private Unix socket of betterlinuxcnc-service",
    )
    parser.add_argument("--program", help="Open a local G-code program")
    parser.add_argument(
        "--fullscreen", action="store_true", default=os.environ.get("BETTERCNC_FULLSCREEN") == "1"
    )
    parser.add_argument(
        "--kiosk",
        action="store_true",
        default=os.environ.get("BETTERCNC_KIOSK") == "1",
        help="Run a fullscreen operator interface without desktop exit controls",
    )
    parser.add_argument(
        "--kiosk-status",
        action="store_true",
        help="Display read-only session startup status without a controller connection",
    )
    parser.add_argument(
        "--check-connection",
        action="store_true",
        help="Read machine.status without opening a window or taking control (exit 0/1/2)",
    )
    parser.add_argument("--qml", help=argparse.SUPPRESS)
    parser.add_argument("--smoke-test", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.kiosk_status and (args.ini or args.program or args.check_connection):
        parser.error("--kiosk-status 只显示启动状态，不能同时指定机床或程序操作")
    if args.check_connection:
        from bettercnc.session import read_machine_status

        if args.ini or args.program:
            parser.error("--check-connection 仅观察机床状态，不能同时指定 --ini 或 --program")
        try:
            state = read_machine_status(args.socket)
        except (OSError, RuntimeError, ValueError) as error:
            print(
                json.dumps({"serviceConnected": False, "message": str(error)}, ensure_ascii=False)
            )
            return 1
        print(json.dumps({"serviceConnected": True, "snapshot": state}, ensure_ascii=False))
        return 0 if state["connected"] else 2
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeMenuBar)
    if args.kiosk:
        QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs)
    app = QGuiApplication([sys.argv[0]])
    app.setApplicationName("BetterLinuxCNC")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("Xamber-Software")
    QQuickStyle.setStyle("Basic")
    families = QFontDatabase.families()
    for family in ("Inter", "Noto Sans CJK SC", "PingFang SC", "Microsoft YaHei"):
        if family in families:
            font = QFont(family)
            font.setPixelSize(13)
            app.setFont(font)
            break
    source_qml = Path(__file__).resolve().parents[3] / "qml"
    qml = (
        Path(args.qml or os.environ.get("BETTERCNC_QML_DIR", ""))
        if (args.qml or os.environ.get("BETTERCNC_QML_DIR"))
        else source_qml
    )
    if not qml.is_dir():
        qml = Path(sys.prefix) / "share/betterlinuxcnc/qml"
    entry = "KioskStatus.qml" if args.kiosk_status else "Main.qml"
    if not (qml / entry).is_file():
        print(f"QML installation is incomplete: {qml}", file=sys.stderr)
        return 1
    if args.kiosk_status:
        from ._kiosk_status import KioskStatus

        backend = KioskStatus(app)
        properties = {"statusModel": backend}
    else:
        from ._backend import DesktopBackend

        backend = DesktopBackend(
            socket_path=args.socket,
            ini_path=args.ini,
            managed=os.environ.get("BETTERCNC_MANAGED") == "1",
            kiosk=args.kiosk,
        )
        app.installEventFilter(backend)
        properties = {
            "backend": backend,
            "kioskMode": args.kiosk,
            "startFullscreen": args.fullscreen,
        }
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(qml))
    engine.setInitialProperties(properties)
    engine.load(QUrl.fromLocalFile(str(qml / entry)))
    if not engine.rootObjects():
        backend.close()
        return 1
    if args.kiosk_status:
        backend.watch_window(engine.rootObjects()[0])
    app.aboutToQuit.connect(backend.close)
    if args.program:
        QTimer.singleShot(500, lambda: backend.openProgram(args.program))
    if args.smoke_test:
        QTimer.singleShot(800, lambda: app.exit(0))
    code = app.exec()
    backend.close()
    del engine
    return code
