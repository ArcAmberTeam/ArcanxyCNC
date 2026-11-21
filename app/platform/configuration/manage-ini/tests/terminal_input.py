"""Exercise the public preview process through a real macOS/Linux pseudoterminal."""

import fcntl
import os
import pty
import re
import select
import struct
import subprocess
import termios
import time
import unicodedata
import unittest


class TerminalInputTests(unittest.TestCase):
    def setUp(self):
        self.master, self.slave = pty.openpty()
        fcntl.ioctl(self.slave, termios.TIOCSWINSZ, struct.pack("HHHH", 30, 100, 0, 0))
        self.original = termios.tcgetattr(self.slave)
        self.process = subprocess.Popen(
            [os.environ["PA_PREVIEW_BINARY"]],
            stdin=self.slave,
            stdout=self.slave,
            stderr=self.slave,
        )
        self.addCleanup(self.close)
        self.wait_for(b"PA Configuration Utility")

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
        self.process.wait(timeout=3)
        os.close(self.master)
        os.close(self.slave)

    def wait_for(self, expected):
        output = b""
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if select.select([self.master], [], [], 0.05)[0]:
                output += os.read(self.master, 65536)
                if expected in output:
                    return output
            self.assertIsNone(self.process.poll(), output[-1000:])
        self.fail(f"Missing terminal output: {expected!r}; tail={output[-1000:]!r}")

    def send(self, sequence):
        while select.select([self.master], [], [], 0)[0]:
            os.read(self.master, 65536)
        os.write(self.master, sequence)

    def test_csi_and_ss3_arrows_navigate_without_exiting(self):
        for prefix in (b"\x1b[", b"\x1bO"):
            self.send(prefix + b"B")
            self.wait_for(b"\x1b[10;3H\x1b[97;44m")
            self.send(prefix + b"A")
            self.wait_for(b"\x1b[8;3H\x1b[97;44m")
            self.send(prefix + b"C")
            self.wait_for(b"\x1b[4;15H\x1b[37;44m  Motion")
            self.send(prefix + b"D")
            self.wait_for(b"\x1b[4;3H\x1b[37;44m  General")
        self.assertIsNone(self.process.poll())

    def test_fragmented_modified_and_batched_keys_are_not_lost(self):
        for byte in b"\x1b[C":
            self.send(bytes([byte]))
            time.sleep(0.08)
        self.wait_for(b"\x1b[4;15H\x1b[37;44m  Motion")
        self.send(b"\x1b[1;2D")
        self.wait_for(b"\x1b[4;3H\x1b[37;44m  General")
        self.send(b"\x1b[C\x1b[B")
        self.wait_for(b"\x1b[14;3H\x1b[97;44m Working volume")
        self.assertIsNone(self.process.poll())

    def test_incomplete_sequence_does_not_become_exit(self):
        self.send(b"\x1b[")
        time.sleep(0.25)
        self.assertIsNone(self.process.poll())
        self.send(b"\x1bOP")
        self.wait_for(b"Left/Right or Tab:")

    def test_language_selection_translates_and_switches_back(self):
        self.send(b"\x1b[D\x1b[B\r")
        self.wait_for("PA 設定管理工具".encode())
        self.wait_for("[使用中]".encode())
        self.send(b"\x1b[C\x1b[C\x1b[B")
        self.wait_for("加工平台尺寸".encode())
        self.wait_for(b"[-0.100]")
        self.send(b"\x1bOP")
        self.wait_for("左/右或 Tab".encode())
        self.send(b"\x1b[D\x1b[D\r")
        self.wait_for(b"PA Configuration Utility")
        self.wait_for(b"[Current]")
        self.send(b"\t")
        self.wait_for(b"Management target")
        self.assertIsNone(self.process.poll())

    def test_chinese_frames_fit_minimum_terminal(self):
        fcntl.ioctl(self.slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0))
        self.send(b"\x1b[D\x1b[B\r")
        self.wait_for("PA 設定管理工具".encode())
        footer = "  PA 平台管理"
        footer_width = sum(
            2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in footer
        )
        end = (footer + " " * (80 - footer_width)).encode()
        for _ in range(7):
            self.send(b"\t")
            output = self.wait_for(end).decode()
            frame = output[output.rfind("\x1b[2J") :]
            runs = re.findall(r"\x1b\[(\d+);(\d+)H\x1b\[[0-9;]+m([^\x1b]*)", frame)
            self.assertTrue(runs)
            for row, column, text in runs:
                cells = sum(
                    2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text
                )
                self.assertLessEqual(int(row), 24)
                self.assertLessEqual(int(column) - 1 + cells, 80, text)
            self.assertIn("項目說明", frame)
        self.send(b"\x1b")
        self.assertEqual(self.process.wait(timeout=3), 0)

    def test_inline_travel_edits_save_and_cancel_without_new_page(self):
        self.send(b"\t")
        self.wait_for(b"Axis travel")
        self.wait_for(b"\x1b[9;3H\x1b[90;47m")
        self.send(b"\r\x1b[C420\r")
        self.wait_for(b"[420] mm")
        self.wait_for(b"Saved to this session only")
        self.send(b"\r\x1b[C999")
        self.wait_for(b"<999>")
        self.send(b"\x1b")
        self.wait_for(b"Edit cancelled")
        self.wait_for(b"[420] mm")
        self.send(b"\r999\r")
        self.wait_for(b"Invalid value")
        self.assertIsNone(self.process.poll())

    def test_table_and_subpage_editing_then_escape_returns_to_parent(self):
        self.send(b"\t\x1b[B\r450\r")
        self.wait_for(b"[450] mm")
        self.send(b"\x1b[B\r")
        self.wait_for(b"Motion / Velocity / acceleration")
        self.send(b"\r30\r")
        self.wait_for(b"[30] mm/s")
        self.send(b"\x1b")
        self.wait_for(b"Motion / Motion parameters")
        self.send(b"\x1b[B\r")
        self.wait_for(b"Motion / Homing")
        self.wait_for(b"J0 Homing sequence")
        self.send(b"\x1b")
        self.wait_for(b"Motion / Motion parameters")
        self.assertIsNone(self.process.poll())

    def test_expert_editor_loads_shared_ini_and_preserves_unsaved_choice(self):
        self.send(b"\t\r\x1b[C430\r")
        self.wait_for(b"[430] mm")
        self.send(b"\t\x1b[B\x1b[B\x1b[B\r")
        self.wait_for(b"Preview INI (session only)")
        self.wait_for(b"Ctrl+S Save")
        self.send("# 繁體註解\r".encode())
        self.wait_for("繁體註解".encode())
        self.send(b"\x1b")
        self.wait_for(b"Unsaved edits")
        self.send(b"\x1b")
        self.wait_for(b"Ctrl+S Save")
        self.send(b"\x13")
        self.wait_for(b"Saved to this session only")
        self.send(b"\x1b")
        self.wait_for(b"Expert INI")
        self.send(b"\r")
        self.wait_for("繁體註解".encode())
        self.assertIsNone(self.process.poll())

    def test_cam_size_source_is_saved_in_the_same_ini(self):
        self.send(b"\t\t\t\r\x1b[B\r")
        self.wait_for(b"Saved to this session only")
        self.wait_for(b"Working volume")
        self.send(b"\x1b[B\r12.5\r")
        self.wait_for(b"[12.5] mm")
        self.send(b"\x1b[D\x1b[B\x1b[B\x1b[B\r")
        self.wait_for(b"DIMENSION_SOURCE = working_volume")
        self.wait_for(b"ORIGIN_X_MM = 12.5")

    def test_standalone_escape_exits_and_restores_terminal(self):
        self.send(b"\x1b")
        self.assertEqual(self.process.wait(timeout=3), 0)
        restored = termios.tcgetattr(self.slave)
        # macOS may set the transient pending-input flag when restoring modes.
        pending = getattr(termios, "PENDIN", 0)
        restored[3] &= ~pending
        self.original[3] &= ~pending
        self.assertEqual(restored, self.original)


if __name__ == "__main__":
    unittest.main()
