"""The diagnostic client cannot import control or private platform capabilities."""

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class ErrorBoundaries(unittest.TestCase):
    def test_client_reverse_dependency_is_rejected(self):
        probe = (
            ROOT
            / "app/platform/error-records/python/src/bettercnc_error_records/_ci_probe.py"
        )
        checker = ROOT / "app/desktop/scripts/check_boundaries.py"
        self.assertFalse(probe.exists())
        try:
            probe.write_text("from bettercnc_controller import Controller\n")
            result = subprocess.run(
                [sys.executable, str(checker)], capture_output=True, text=True
            )
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("bettercnc_controller", result.stdout + result.stderr)
        finally:
            probe.unlink(missing_ok=True)
        subprocess.run([sys.executable, str(checker)], check=True)
