"""Public installed session CLI with a controlled systemd command boundary."""

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


class KioskSessionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="kiosk-session-", dir="/tmp")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.config = self.root / "launcher.json"
        self.config.write_text("{}")
        self.records = self.root / "requests.jsonl"
        self.status_records = self.root / "status.jsonl"
        self.display_records = self.root / "display.jsonl"
        display = self.root / "xset"
        display.write_text(
            f"#!{sys.executable}\n"
            "import json, sys\n"
            f"with open({str(self.display_records)!r}, 'a') as output:\n"
            "    output.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        )
        display.chmod(0o700)
        status_executable = self.root / "betterlinuxcnc"
        status_executable.write_text(
            f"#!{sys.executable}\n"
            "import json, os, signal, sys\n"
            "def record(event):\n"
            f"    with open({str(self.status_records)!r}, 'a') as output:\n"
            "        output.write(json.dumps({'event': event, 'args': sys.argv[1:]}) + '\\n')\n"
            "def stop(*_): raise SystemExit(0)\n"
            "signal.signal(signal.SIGTERM, stop)\n"
            "record('started')\n"
            "try:\n"
            "    if os.environ.get('STATUS_EXIT'): sys.exit(12)\n"
            "    print(json.dumps({'kioskStatus': 'visible'}), flush=True)\n"
            "    while True: signal.pause()\n"
            "finally:\n"
            "    record('stopped')\n"
        )
        status_executable.chmod(0o700)
        executable = self.root / "systemctl"
        executable.write_text(
            f"#!{sys.executable}\n"
            "import json, os, sys\n"
            f"with open({str(self.records)!r}, 'a') as output:\n"
            "    output.write(json.dumps({'args': sys.argv[1:], 'kiosk': "
            "os.environ.get('BETTERCNC_KIOSK'), 'fullscreen': "
            "os.environ.get('BETTERCNC_FULLSCREEN'), 'status_started': "
            f"os.path.exists({str(self.status_records)!r})"
            "}) + '\\n')\n"
            "if 'start' in sys.argv: sys.exit(int(os.environ.get('START_EXIT', '0')))\n"
        )
        executable.chmod(0o700)
        self.environment = dict(
            os.environ, PATH=str(self.root), DISPLAY=":77", XDG_SESSION_TYPE="x11"
        )
        self.environment.pop("PYTHONPATH", None)

    def launch(self, mode, **environment):
        process = subprocess.Popen(
            [sys.executable, "-m", "bettercnc_launcher", mode, "--config", str(self.config)],
            env=dict(self.environment, **environment),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        def cleanup():
            if process.poll() is None:
                process.terminate()
            process.communicate(timeout=5)

        self.addCleanup(cleanup)
        return process

    def wait_for_start(self):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if self.records.exists():
                records = [json.loads(line) for line in self.records.read_text().splitlines()]
                if len(records) == 3:
                    return records
            time.sleep(0.02)
        self.fail("session did not start its user service")

    @unittest.skipIf(os.getuid() == 0, "the operator session deliberately rejects root")
    def test_kiosk_keeps_x_session_alive_after_service_success_or_failure(self):
        for status in (0, 78):
            with self.subTest(status=status):
                self.records.unlink(missing_ok=True)
                self.status_records.unlink(missing_ok=True)
                self.display_records.unlink(missing_ok=True)
                process = self.launch("--kiosk-session", START_EXIT=str(status))
                records = self.wait_for_start()
                self.assertEqual(
                    [json.loads(line) for line in self.display_records.read_text().splitlines()],
                    [["s", "off"], ["s", "noblank"], ["-dpms"]],
                )
                self.assertEqual(records[1]["args"][:2], ["--user", "import-environment"])
                self.assertEqual(records[1]["kiosk"], "1")
                self.assertEqual(records[1]["fullscreen"], "1")
                self.assertTrue(all(record["status_started"] for record in records))
                self.assertEqual(
                    records[2]["args"], ["--user", "start", "betterlinuxcnc-launcher.service"]
                )
                process.send_signal(signal.SIGINT)
                time.sleep(0.15)
                self.assertIsNone(process.poll())
                self.assertEqual(len(self.records.read_text().splitlines()), 3)
                process.terminate()
                process.communicate(timeout=5)
                events = [json.loads(line) for line in self.status_records.read_text().splitlines()]
                self.assertEqual([event["event"] for event in events], ["started", "stopped"])
                self.assertEqual(events[0]["args"], ["--kiosk-status"])

    def test_regular_session_clears_kiosk_environment(self):
        process = self.launch("--session-start", BETTERCNC_KIOSK="1", BETTERCNC_FULLSCREEN="1")
        output = process.communicate(timeout=5)[0]
        self.assertEqual(process.returncode, 0, output)
        records = self.wait_for_start()
        self.assertEqual(records[1]["kiosk"], "0")
        self.assertEqual(records[1]["fullscreen"], "0")
        self.assertFalse(self.status_records.exists())
        self.assertFalse(self.display_records.exists())

    @unittest.skipIf(os.getuid() == 0, "the operator session deliberately rejects root")
    def test_new_machine_opens_fullscreen_without_starting_the_machine_service(self):
        self.config.unlink()
        process = self.launch("--kiosk-session")
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if self.status_records.exists() and self.status_records.stat().st_size:
                break
            time.sleep(0.02)
        self.assertTrue(self.status_records.is_file())
        process.terminate()
        output = process.communicate(timeout=5)[0]
        self.assertEqual(process.returncode, 0, output)
        events = [json.loads(line) for line in self.status_records.read_text().splitlines()]
        self.assertEqual([event["event"] for event in events], ["started", "stopped"])
        self.assertEqual(events[0]["args"], ["--kiosk", "--fullscreen"])
        self.assertFalse(self.records.exists())

    @unittest.skipIf(os.getuid() == 0, "the operator session deliberately rejects root")
    def test_status_page_failure_does_not_restart_it_over_the_machine_ui(self):
        process = self.launch("--kiosk-session", STATUS_EXIT="1")
        self.wait_for_start()
        time.sleep(0.2)
        self.assertIsNone(process.poll())
        events = [json.loads(line) for line in self.status_records.read_text().splitlines()]
        self.assertEqual([event["event"] for event in events], ["started", "stopped"])
        process.send_signal(signal.SIGHUP)
        process.communicate(timeout=5)
        self.assertEqual(process.returncode, 0)

    def test_kiosk_rejects_missing_x11_before_service_actions(self):
        process = self.launch("--kiosk-session", DISPLAY="", XDG_SESSION_TYPE="wayland")
        output = process.communicate(timeout=5)[0]
        self.assertNotEqual(process.returncode, 0, output)
        self.assertFalse(self.records.exists())


if __name__ == "__main__":
    unittest.main()
