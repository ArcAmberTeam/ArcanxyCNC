"""CAM homing/workflow contracts through the public Controller only."""

import tempfile
import unittest
import uuid
from pathlib import Path

from test_controller import FakeClock, FakeLinuxCNC
from test_received_jobs import received

from bettercnc_controller import Controller


class CamHomingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir="/tmp", prefix="cam-home-")
        self.addCleanup(self.temp.cleanup)
        self.inbox = Path(self.temp.name) / "inbox"
        self.transfer = received(self.inbox)
        self.vendor = FakeLinuxCNC()
        self.clock = FakeClock()
        self.controller = Controller(
            ini_path="/machine/machine.ini",
            module=self.vendor,
            clock=self.clock,
            cam_inbox=self.inbox,
        )
        self.addCleanup(self.controller.close)

    def workflow(self, **options):
        return self.controller.start_received(
            self.transfer,
            home_first=True,
            clearance_confirmed=True,
            machining_confirmed=True,
            **options,
        )

    def reach(self, command):
        for _ in range(12):
            if self.vendor.calls and self.vendor.calls[-1][0] == command:
                return
            self.vendor.confirm()
            self.controller.poll()
        self.fail(f"did not reach {command}: {self.vendor.calls}")

    def test_desktop_start_checks_file_before_power_and_runs_after_homing(self):
        path = "/machine/part.ngc"
        self.vendor.status.task_state = self.vendor.STATE_OFF
        self.vendor.status.enabled = False
        self.vendor.status.file = ""
        self.assertFalse(self.controller.dispatch("program.home-and-run", {"file": path}))
        self.assertEqual(self.vendor.calls, [])
        self.vendor.status.file = path
        self.assertTrue(self.controller.dispatch("program.home-and-run", {"file": path}))
        self.assertEqual(self.vendor.calls, [("state", (self.vendor.STATE_ON,))])
        self.controller.poll()
        self.assertEqual(len(self.vendor.calls), 1)
        self.reach("home")
        self.vendor.confirm(apply=False)
        self.vendor.status.joint[0]["homing"] = True
        self.controller.poll()
        self.assertEqual(self.vendor.calls[-1][0], "home")
        self.vendor.status.joint[0]["homing"] = False
        self.reach("auto")
        self.assertEqual(self.vendor.calls[-1], ("auto", (self.vendor.AUTO_RUN, 0)))

    def test_desktop_start_rejects_estop_and_cancels_if_selected_file_changes(self):
        path = "/machine/part.ngc"
        self.vendor.status.file = path
        self.vendor.status.estop = True
        self.assertFalse(self.controller.dispatch("program.home-and-run", {"file": path}))
        self.assertEqual(self.vendor.calls, [])
        self.vendor.status.estop = False
        self.assertTrue(self.controller.dispatch("program.home-and-run", {"file": path}))
        self.reach("home")
        self.vendor.status.file = "/machine/other.ngc"
        self.vendor.confirm()
        self.assertEqual(self.controller.poll()["commandState"], "error")
        self.assertNotIn("auto", [name for name, _ in self.vendor.calls])

    def test_standalone_home_never_loads_and_same_id_never_rehomes(self):
        operation = str(uuid.uuid4())
        self.assertEqual(
            self.controller.start_homing(operation, clearance_confirmed=True)["state"], "homing"
        )
        self.reach("home")
        self.vendor.confirm()
        self.controller.poll()
        self.assertEqual(self.controller.homing_status(operation)["state"], "completed")
        before = list(self.vendor.calls)
        self.controller.start_homing(operation, clearance_confirmed=True)
        self.assertEqual(before, self.vendor.calls)
        self.assertFalse(any(name in ("auto", "program_open") for name, _ in before))

    def test_workflow_waits_for_all_homed_and_motion_completion_from_auto_mode(self):
        self.vendor.status.task_mode = self.vendor.MODE_AUTO
        self.workflow()
        self.reach("home")
        self.assertFalse(any(self.vendor.status.homed))
        self.vendor.confirm(apply=False)
        self.vendor.status.joint[0]["homing"] = True
        self.clock.now += 15
        self.controller.poll()
        self.assertEqual(self.controller.received_status(self.transfer)["state"], "homing")
        self.assertFalse(any(name == "program_open" for name, _ in self.vendor.calls))
        self.vendor.confirm()
        self.vendor.status.joint[0]["homing"] = False
        self.vendor.status.inpos = False
        self.controller.poll()
        # The home acknowledgement alone does not authorize loading while moving.
        self.assertFalse(any(name == "program_open" for name, _ in self.vendor.calls))
        self.vendor.status.inpos = True
        self.reach("auto")

    def test_successful_workflow_orders_home_load_auto_and_completes_after_motion(self):
        self.vendor.status.homed = [0, 0, 0]
        self.vendor.status.task_mode = self.vendor.MODE_AUTO
        self.workflow()
        self.reach("auto")
        names = [name for name, _ in self.vendor.calls]
        self.assertLess(names.index("unhome"), names.index("home"))
        self.assertLess(names.index("home"), names.index("program_open"))
        self.assertLess(names.index("program_open"), names.index("auto"))
        self.assertEqual(self.vendor.status.task_mode, self.vendor.MODE_AUTO)
        self.vendor.confirm(state=self.vendor.RCS_EXEC)
        self.controller.poll()
        self.assertEqual(self.controller.received_status(self.transfer)["state"], "running")
        self.vendor.status.interp_state = self.vendor.INTERP_IDLE
        self.vendor.status.state = self.vendor.RCS_DONE
        self.controller.poll()
        self.assertEqual(self.controller.received_status(self.transfer)["state"], "completed")

    def test_homing_failure_cancel_power_loss_foreign_writer_and_timeout_never_start(self):
        for failure in ("error", "cancel", "power", "foreign", "disconnect", "timeout"):
            with self.subTest(failure=failure):
                vendor = FakeLinuxCNC()
                clock = FakeClock()
                controller = Controller(
                    ini_path="/machine/machine.ini",
                    module=vendor,
                    clock=clock,
                    cam_inbox=self.inbox,
                )
                transfer = received(self.inbox)
                controller.start_received(
                    transfer, home_first=True, clearance_confirmed=True, machining_confirmed=True
                )
                for _ in range(10):
                    if vendor.calls[-1][0] == "home":
                        break
                    vendor.confirm()
                    controller.poll()
                self.assertEqual(vendor.calls[-1][0], "home")
                if failure == "error":
                    vendor.errors.append((vendor.NML_ERROR, "home switch error"))
                elif failure == "cancel":
                    controller.cancel_cam(transfer)
                elif failure == "power":
                    vendor.status.enabled = False
                elif failure == "foreign":
                    vendor.status.echo_serial_number = vendor.commands.serial + 10
                elif failure == "disconnect":
                    vendor.available = False
                else:
                    vendor.confirm(apply=False)
                    vendor.status.joint[0]["homing"] = True
                    clock.now += 301
                controller.poll()
                self.assertIn(controller.received_status(transfer)["state"], ("error", "unknown"))
                self.assertFalse(any(name in ("auto", "program_open") for name, _ in vendor.calls))
                controller.close()

    def test_restart_returns_unknown_and_never_replays_home_or_workflow(self):
        operation = str(uuid.uuid4())
        self.controller.start_homing(operation, clearance_confirmed=True)
        other_vendor = FakeLinuxCNC()
        other = Controller(
            ini_path="/machine/machine.ini", module=other_vendor, cam_inbox=self.inbox
        )
        self.addCleanup(other.close)
        self.assertEqual(
            other.start_homing(operation, clearance_confirmed=True)["state"], "unknown"
        )
        self.assertEqual(other_vendor.calls, [])

    def test_missing_clearance_or_setup_and_unsafe_machine_do_not_move(self):
        for failure in ("clearance", "setup", "estop", "power", "override", "spindle"):
            with self.subTest(failure=failure):
                vendor = FakeLinuxCNC()
                if failure == "estop":
                    vendor.status.estop = True
                if failure == "power":
                    vendor.status.enabled = False
                if failure == "override":
                    vendor.status.joint[0]["override_limits"] = True
                if failure == "spindle":
                    vendor.status.spindle[0]["direction"] = 1
                controller = Controller(
                    ini_path="/machine/machine.ini", module=vendor, cam_inbox=self.inbox
                )
                result = controller.start_received(
                    received(self.inbox),
                    home_first=True,
                    clearance_confirmed=failure != "clearance",
                    machining_confirmed=failure != "setup",
                )
                self.assertEqual(result["state"], "error")
                self.assertEqual(vendor.calls, [])
                controller.close()

    def test_transfer_intent_cannot_change_from_home_run_to_run_only(self):
        self.workflow()
        with self.assertRaises(ValueError):
            self.controller.start_received(self.transfer)

    def test_opt_in_clears_block_delete_after_home_and_waits_before_loading(self):
        self.vendor.status.block_delete = True
        self.workflow(disable_block_delete=True)
        self.reach("set_block_delete")
        self.assertEqual(self.vendor.calls[-1], ("set_block_delete", (0,)))
        self.assertTrue(all(self.vendor.status.homed))
        self.vendor.confirm(apply=False)
        self.controller.poll()
        self.assertFalse(any(name == "program_open" for name, _ in self.vendor.calls))
        self.vendor.confirm()
        self.reach("auto")
        self.assertFalse(self.vendor.status.block_delete)
        before = list(self.vendor.calls)
        self.workflow(disable_block_delete=True)
        self.assertEqual(before, self.vendor.calls)
        with self.assertRaises(ValueError):
            self.workflow(disable_block_delete=False)

    def test_block_delete_is_never_changed_without_opt_in(self):
        self.vendor.status.block_delete = True
        self.workflow()
        self.reach("home")
        self.vendor.confirm()
        self.controller.poll()
        self.assertEqual(self.controller.received_status(self.transfer)["state"], "error")
        self.assertFalse(
            any(
                name in ("set_block_delete", "program_open", "auto")
                for name, _ in self.vendor.calls
            )
        )

    def test_failed_setting_acknowledgement_never_loads_or_runs(self):
        self.vendor.status.block_delete = True
        self.workflow(disable_block_delete=True)
        self.reach("set_block_delete")
        self.vendor.confirm(apply=False)
        self.clock.now += 11
        self.controller.poll()
        self.assertEqual(self.controller.received_status(self.transfer)["state"], "unknown")
        self.assertFalse(any(name in ("program_open", "auto") for name, _ in self.vendor.calls))


if __name__ == "__main__":
    unittest.main()
