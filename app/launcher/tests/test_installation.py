"""Stage the real CMake install without writing to the host installation."""

import configparser
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path


class InstallationTests(unittest.TestCase):
    def test_installed_launcher_uses_only_the_stdlib_diagnostic_client(self):
        self.assertEqual(
            importlib.metadata.requires("betterlinuxcnc-launcher"),
            ["betterlinuxcnc-error-records==0.1.0"],
        )
        self.assertFalse(importlib.metadata.requires("betterlinuxcnc-error-records"))

    def test_standalone_desktop_installs_only_its_own_application(self):
        source = Path(__file__).resolve().parents[3] / "app/desktop"
        with tempfile.TemporaryDirectory(prefix="desktop-install-") as temporary:
            root = Path(temporary)
            build = root / "build"
            stage = root / "stage"
            result = subprocess.run(
                [
                    "cmake",
                    "-S",
                    str(source),
                    "-B",
                    str(build),
                    "-DBUILD_TESTING=OFF",
                    f"-DPython3_EXECUTABLE={sys.executable}",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Building the desktop only", result.stdout)
            result = subprocess.run(
                ["cmake", "--install", str(build)],
                env=dict(os.environ, DESTDIR=str(stage)),
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(
                {path.name for path in (stage / "usr/bin").iterdir()},
                {"betterlinuxcnc"},
            )
            self.assertEqual(
                {path.name for path in (stage / "usr/lib/betterlinuxcnc/python").iterdir()},
                {"bettercnc"},
            )
            self.assertTrue((stage / "usr/share/betterlinuxcnc/qml/Main.qml").is_file())
            self.assertFalse((stage / "usr/lib/systemd").exists())
            self.assertFalse((stage / "etc").exists())

    def assert_debian_release_package(self, source, build, stage, output):
        result = subprocess.run(
            ["cpack", "--config", str(build / "CPackConfig.cmake"), "-G", "DEB", "-B", str(output)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        packages = list(output.glob("*.deb"))
        self.assertEqual(len(packages), 1)
        package = packages[0]
        unpacked = output / "unpacked"
        result = subprocess.run(
            ["dpkg-deb", "--extract", str(package), str(unpacked)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        for command in (
            "pa",
            "betterlinuxcnc-cam-link",
            "betterlinuxcnc-updater",
            "betterlinuxcnc-mesa-update",
            "betterlinuxcnc-mesa-flash",
        ):
            with self.subTest(packaged_command=command):
                self.assertEqual(
                    (unpacked / "usr/bin" / command).read_bytes(),
                    (stage / "usr/bin" / command).read_bytes(),
                )
        self.assertFalse((unpacked / "etc/betterlinuxcnc/launcher.json").exists())
        self.assertTrue((unpacked / "etc/betterlinuxcnc/updater.json").is_file())
        self.assertFalse((unpacked / "etc/lightdm").exists())
        self.assertFalse((unpacked / "etc/ssh").exists())
        control = output / "control"
        result = subprocess.run(
            ["dpkg-deb", "--control", str(package), str(control)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            "/etc/betterlinuxcnc/updater.json", (control / "conffiles").read_text().splitlines()
        )
        self.assertLessEqual(
            {path.name for path in control.iterdir()},
            {"control", "md5sums", "conffiles", "postinst"},
        )
        self.assertEqual(
            (control / "postinst").read_bytes(),
            (source / "tools/appliance/packaging/postinst").read_bytes(),
        )
        self.assertEqual((control / "postinst").stat().st_mode & 0o7777, 0o755)
        fields = {}
        for field in ("Package", "Version", "Architecture", "Depends"):
            result = subprocess.run(
                ["dpkg-deb", "--field", str(package), field],
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            fields[field] = result.stdout.strip()
        with (source / "app/desktop/pyproject.toml").open("rb") as metadata:
            application_version = tomllib.load(metadata)["project"]["version"]
        architecture = subprocess.check_output(["dpkg", "--print-architecture"], text=True).strip()
        self.assertEqual(fields["Package"], "betterlinuxcnc-qt")
        self.assertEqual(fields["Version"], application_version)
        installed_version = subprocess.check_output(
            [sys.executable, "-c", "from bettercnc import __version__; print(__version__)"],
            env=dict(os.environ, PYTHONPATH=str(unpacked / "usr/lib/betterlinuxcnc/python")),
            text=True,
            timeout=10,
        ).strip()
        self.assertEqual(installed_version, fields["Version"])
        self.assertEqual(fields["Architecture"], architecture)
        self.assertEqual(
            package.name,
            f"betterlinuxcnc-qt_{fields['Version']}_{fields['Architecture']}.deb",
        )
        dependencies = {entry.strip().split()[0] for entry in fields["Depends"].split(",")}
        self.assertNotIn("pkexec", dependencies)
        self.assertTrue(
            {
                "polkitd",
                "systemd",
                "util-linux",
                "ca-certificates",
                "apt",
                "dpkg",
                "dbus-user-session",
                "lightdm",
                "xserver-xorg",
                "x11-xserver-utils",
                "openssh-server",
                "sudo",
                "passwd",
                "procps",
            }
            <= dependencies,
            dependencies,
        )

    def test_staged_install_includes_autostart_unit_and_preserves_project_config(self):
        source = Path(__file__).resolve().parents[3]
        with tempfile.TemporaryDirectory(prefix="launcher-install-") as temporary:
            root = Path(temporary)
            stage = root / "stage"
            config = stage / "etc/betterlinuxcnc/launcher.json"
            config.parent.mkdir(parents=True)
            config.write_text('{"ini":"keep-existing.ini"}')
            updater_config = config.parent / "updater.json"
            updater_config.write_text('{"account":"preserve-local-policy"}')
            retired_cam = stage / "usr/lib/betterlinuxcnc/python/bettercnc_cam_link"
            retired_cam.mkdir(parents=True)
            (retired_cam / "__init__.py").write_text("# obsolete Python CAM service\n")
            build = root / "build"
            # CI can reuse explicitly built target binaries when splitting verification.
            # The complete package job leaves these unset and builds the checkout.
            prebuilt_services = [
                f"-D{name}={os.environ[name]}"
                for name in (
                    "BETTERCNC_CAM_LINK_BINARY",
                    "BETTERCNC_UPDATER_BINARY",
                    "BETTERCNC_MESA_UPDATE_BINARY",
                    "BETTERCNC_MESA_FLASH_BINARY",
                )
                if os.environ.get(name)
            ]
            result = subprocess.run(
                [
                    "cmake",
                    "-S",
                    str(source),
                    "-B",
                    str(build),
                    "-DBUILD_TESTING=OFF",
                    f"-DPython3_EXECUTABLE={sys.executable}",
                    *prebuilt_services,
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run(
                ["cmake", "--build", str(build), "--parallel"],
                capture_output=True,
                text=True,
                timeout=600,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run(
                ["cmake", "--install", str(build)],
                env=dict(os.environ, DESTDIR=str(stage)),
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            cam_binary = stage / "usr/bin/betterlinuxcnc-cam-link"
            self.assertFalse(cam_binary.read_bytes().startswith(b"#!"))
            result = subprocess.run(
                [str(cam_binary), "--help"], capture_output=True, text=True, timeout=10
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Rust CAM Link", result.stdout)
            updater_binary = stage / "usr/bin/betterlinuxcnc-updater"
            self.assertFalse(updater_binary.read_bytes().startswith(b"#!"))
            result = subprocess.run(
                [str(updater_binary), "--help"], capture_output=True, text=True, timeout=10
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("betterlinuxcnc-updater", result.stdout)
            for command in ("betterlinuxcnc-mesa-update", "betterlinuxcnc-mesa-flash"):
                binary = stage / "usr/bin" / command
                self.assertFalse(binary.read_bytes().startswith(b"#!"))
                result = subprocess.run(
                    [str(binary), "--help"], capture_output=True, text=True, timeout=10
                )
                self.assertEqual(result.returncode, 0, result.stderr)
            python_root = stage / "usr/lib/betterlinuxcnc/python"
            for package in (
                "bettercnc",
                "betterlinuxcnc_service",
                "bettercnc_controller",
                "bettercnc_preview",
                "bettercnc_launcher",
            ):
                with self.subTest(package=package):
                    self.assertTrue((python_root / package / "__init__.py").is_file())
            self.assertFalse((python_root / "bettercnc_cam_link").exists())
            self.assertEqual(config.read_text(), '{"ini":"keep-existing.ini"}')
            self.assertEqual(updater_config.read_text(), '{"account":"preserve-local-policy"}')
            self.assertFalse((config.parent / "launcher.example.json").exists())
            self.assertTrue(
                (stage / "usr/share/doc/betterlinuxcnc-qt/examples/launcher.example.json").is_file()
            )
            self.assertTrue((stage / "usr/sbin/betterlinuxcnc-appliance").is_file())
            self.assertTrue((stage / "usr/lib/betterlinuxcnc/appliance/maintenance.py").is_file())
            self.assertTrue((stage / "usr/lib/betterlinuxcnc/appliance/axis_profiles.py").is_file())
            result = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    str(stage / "usr/lib/betterlinuxcnc/appliance/main.py"),
                    "plan",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            appliance_plan = json.loads(result.stdout)
            self.assertEqual(appliance_plan["operatorHome"], "/var/lib/betterlinuxcnc/home")
            self.assertFalse(appliance_plan["automaticActivation"])
            self.assertTrue(
                (stage / "usr/lib/systemd/system/betterlinuxcnc-system-update.service").is_file()
            )
            for unit in (
                "betterlinuxcnc-mesa-update.service",
                "betterlinuxcnc-mesa-update.timer",
                "betterlinuxcnc-mesa-flash.service",
            ):
                self.assertTrue((stage / "usr/lib/systemd/system" / unit).is_file())
            for name in (
                "betterlinuxcnc-axis-profile@.service",
                "00-betterlinuxcnc-axis-settings.rules",
            ):
                self.assertTrue((stage / "usr/lib/betterlinuxcnc/appliance" / name).is_file())
            self.assertTrue(
                (stage / "usr/share/polkit-1/rules.d/49-betterlinuxcnc-update.rules").is_file()
            )
            self.assertFalse((stage / "etc/lightdm").exists())
            self.assertFalse((stage / "etc/ssh").exists())
            unit = stage / "usr/lib/systemd/user/betterlinuxcnc-launcher.service"
            parser = configparser.ConfigParser(interpolation=None)
            parser.read(unit)
            self.assertEqual(parser["Service"]["Restart"], "on-failure")
            self.assertIn("SIGKILL", parser["Service"]["RestartPreventExitStatus"])
            self.assertIn("78", parser["Service"]["RestartPreventExitStatus"])
            self.assertEqual(parser["Service"]["KillMode"], "process")
            self.assertIn("/etc/betterlinuxcnc/launcher.json", parser["Service"]["ExecStart"])
            self.assertIn(
                "BETTERCNC_LOG_ROOT=/var/log/betterlinuxcnc/launcher",
                parser["Service"]["Environment"],
            )
            self.assertIn(
                "XDG_CACHE_HOME=/var/cache/betterlinuxcnc/user", parser["Service"]["Environment"]
            )
            self.assertIn("BETTERCNC_SHARE_LOGS=1", parser["Service"]["Environment"])
            session = configparser.ConfigParser(interpolation=None)
            session.read(stage / "usr/share/xsessions/betterlinuxcnc-kiosk.desktop")
            self.assertEqual(
                session["Desktop Entry"]["Exec"],
                "/usr/bin/betterlinuxcnc-launch --kiosk-session",
            )
            self.assertEqual(session["Desktop Entry"]["TryExec"], "/usr/bin/betterlinuxcnc-launch")
            parser.read(stage / "etc/xdg/autostart/betterlinuxcnc-autostart.desktop")
            self.assertIn("--session-start", parser["Desktop Entry"]["Exec"])
            self.assertNotEqual(parser["Desktop Entry"].get("Hidden"), "true")
            parser.read(stage / "usr/share/applications/betterlinuxcnc-qt.desktop")
            self.assertEqual(
                parser["Desktop Entry"]["Exec"], "betterlinuxcnc-launch --session-start"
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(stage / "usr/bin/betterlinuxcnc-launch"),
                    "--help",
                ],
                env=dict(os.environ, PYTHONPATH=str(stage / "usr/lib/betterlinuxcnc/python")),
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("--config", result.stdout)
            if sys.platform.startswith("linux"):
                self.assert_debian_release_package(source, build, stage, root / "packages")
            # Verify the generated unit using the host's offline parser where
            # available; substitute only the not-yet-installed executable path.
            analyzer = shutil.which("systemd-analyze")
            if analyzer:
                runtime = root / "runtime"
                runtime.mkdir(mode=0o700)
                for installed_unit, command, options in (
                    (unit, "betterlinuxcnc-launch", ["--user"]),
                    (
                        stage / "usr/lib/systemd/system/betterlinuxcnc-system-update.service",
                        "betterlinuxcnc-updater",
                        [],
                    ),
                ):
                    with self.subTest(systemd_unit=installed_unit.name):
                        checked = root / installed_unit.name
                        checked.write_text(
                            installed_unit.read_text().replace(f"/usr/bin/{command}", "/bin/true")
                        )
                        result = subprocess.run(
                            [analyzer, *options, "verify", str(checked)],
                            env=dict(os.environ, XDG_RUNTIME_DIR=str(runtime)),
                            capture_output=True,
                            text=True,
                            timeout=20,
                        )
                        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
