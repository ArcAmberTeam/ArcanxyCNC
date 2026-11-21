"""Exercise the public controller against the external LinuxCNC API contract."""

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from bettercnc_controller import Controller, StatusReader


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class FakeLinuxCNC:
    """Only the vendor seam is replaced; no controller internals are accessed."""

    MODE_MANUAL, MODE_MDI, MODE_AUTO = 1, 2, 3
    STATE_ESTOP, STATE_ESTOP_RESET, STATE_OFF, STATE_ON = 1, 2, 3, 4
    TRAJ_MODE_FREE, TRAJ_MODE_COORD, TRAJ_MODE_TELEOP = 1, 2, 3
    INTERP_IDLE, INTERP_READING, INTERP_PAUSED = 1, 2, 3
    EXEC_DONE = 1
    RCS_DONE, RCS_EXEC, RCS_ERROR = 1, 2, 3
    NML_ERROR, OPERATOR_ERROR, OPERATOR_TEXT = 1, 2, 3
    JOG_STOP, JOG_CONTINUOUS, JOG_INCREMENT = 0, 1, 2
    AUTO_RUN, AUTO_STEP, AUTO_PAUSE, AUTO_RESUME = 0, 1, 2, 3
    SPINDLE_FORWARD, SPINDLE_REVERSE, SPINDLE_OFF = 1, -1, 0
    SPINDLE_INCREASE, SPINDLE_DECREASE = 10, 11
    BRAKE_ENGAGE, BRAKE_RELEASE = 1, 0
    FLOOD_ON, FLOOD_OFF, MIST_ON, MIST_OFF = 1, 0, 1, 0

    def __init__(self):
        self.available = True
        self.errors = []
        self.calls = []
        self.polls = 0
        self.ini_values = {
            ("KINS", "JOINTS"): "3",
            ("KINS", "KINEMATICS"): "trivkins coordinates=XYZ",
            ("TRAJ", "MAX_LINEAR_VELOCITY"): "40",
            ("DISPLAY", "MAX_LINEAR_VELOCITY"): "20",
            ("DISPLAY", "MAX_FEED_OVERRIDE"): "1.5",
            ("DISPLAY", "MIN_SPINDLE_OVERRIDE"): ".5",
            ("DISPLAY", "MAX_SPINDLE_OVERRIDE"): "1.2",
            ("DISPLAY", "DEFAULT_SPINDLE_SPEED"): "500",
            ("DISPLAY", "MAX_SPINDLE_SPEED"): "2000",
            ("DISPLAY", "MIN_SPINDLE_SPEED"): "100",
            ("RS274NGC", "PARAMETER_FILE"): "machine.var",
            ("EMCIO", "TOOL_TABLE"): "tool.tbl",
            ("DISPLAY", "PROGRAM_PREFIX"): "programs",
            ("DISPLAY", "PYVCP"): "panel.xml",
        }
        for i, axis in enumerate("XYZ"):
            self.ini_values[("JOINT_" + str(i), "MAX_VELOCITY")] = "30"
            self.ini_values[("AXIS_" + axis, "MAX_VELOCITY")] = "25"
            self.ini_values[("JOINT_" + str(i), "HOME_SEQUENCE")] = str(i)
        self.status = SimpleNamespace(
            task_state=self.STATE_ON,
            debug=0,
            task_mode=self.MODE_MANUAL,
            enabled=True,
            estop=False,
            joints=3,
            axis_mask=7,
            homed=[1, 1, 1],
            joint=[
                {
                    "homing": False,
                    "override_limits": False,
                    "min_hard_limit": False,
                    "max_hard_limit": False,
                }
                for _ in range(3)
            ],
            motion_mode=self.TRAJ_MODE_FREE,
            interp_state=self.INTERP_IDLE,
            exec_state=self.EXEC_DONE,
            inpos=True,
            queue=0,
            active_queue=0,
            echo_serial_number=0,
            state=self.RCS_DONE,
            actual_position=[1.0, 2.0, 3.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            position=[1.0, 2.0, 3.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            g5x_offset=[0.0] * 9,
            g92_offset=[0.0] * 9,
            tool_offset=[0.0] * 9,
            dtg=[0.0] * 9,
            rotation_xy=0.0,
            linear_units=1.0,
            angular_units=1.0,
            current_vel=0.0,
            max_velocity=35.0,
            feedrate=1.0,
            rapidrate=1.0,
            spindle=[{"override": 1.0, "speed": 0.0, "direction": 0, "brake": False}],
            flood=False,
            mist=False,
            optional_stop=False,
            block_delete=False,
            file="/machine/demo.ngc",
            motion_line=0,
            current_line=0,
            tool_in_spindle=1,
            gcodes=[0, 0, 210, 540, -1],
            mcodes=[0, 5, 9, -1],
            g5x_index=1,
            tool_table=[(1, 0.0, 0.0, 4.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 6.0, 0.0, 0.0, 0)],
            paused=False,
            ini_filename="/machine/machine.ini",
        )
        self.status.poll = self._poll
        self.commands = FakeCommands(self)

    def _poll(self):
        self.polls += 1
        if not self.available:
            raise RuntimeError("NML status channel invalid")

    def stat(self):
        return self.status

    def command(self):
        return self.commands

    def error_channel(self):
        return SimpleNamespace(poll=lambda: self.errors.pop(0) if self.errors else None)

    def ini(self, path):
        if path != "/machine/machine.ini":
            raise ValueError("unexpected INI")
        return SimpleNamespace(find=lambda section, key: self.ini_values.get((section, key)))

    def confirm(self, apply=True, state=None):
        """Advance the independently observed status after a captured command."""
        self.status.echo_serial_number = self.commands.serial
        self.status.state = self.RCS_DONE if state is None else state
        if not apply or not self.calls:
            return
        method, args = self.calls[-1]
        s = self.status
        if method == "mode":
            s.task_mode = args[0]
        elif method == "state":
            s.task_state = args[0]
            s.enabled = args[0] == self.STATE_ON
            s.estop = args[0] == self.STATE_ESTOP
        elif method == "teleop_enable":
            s.motion_mode = self.TRAJ_MODE_TELEOP if args[0] else self.TRAJ_MODE_FREE
        elif method in ("home", "unhome"):
            indices = range(s.joints) if args[0] == -1 else [args[0]]
            for index in indices:
                s.homed[index] = int(method == "home")
        elif method == "auto":
            if args[0] == self.AUTO_RUN:
                s.interp_state = self.INTERP_READING
            elif args[0] == self.AUTO_PAUSE:
                s.paused = True
            elif args[0] == self.AUTO_RESUME:
                s.paused = False
        elif method == "abort":
            s.interp_state = self.INTERP_IDLE
            s.inpos = True
        elif method == "program_open":
            s.file = args[0]
        elif method == "set_optional_stop":
            s.optional_stop = bool(args[0])
        elif method == "set_block_delete":
            s.block_delete = bool(args[0])
        elif method == "debug":
            s.debug = args[0]
        elif method in ("flood", "mist"):
            setattr(s, method, bool(args[0]))
        elif method in ("feedrate", "rapidrate"):
            setattr(s, method, args[0])
        elif method == "maxvel":
            s.max_velocity = args[0]
        elif method == "spindleoverride":
            s.spindle[0]["override"] = args[0]
        elif method == "spindle":
            if args[0] in (-1, 0, 1):
                s.spindle[0]["direction"] = args[0]
                s.spindle[0]["speed"] = args[1] * args[0]


class FakeCommands:
    METHODS = {
        "mode",
        "state",
        "teleop_enable",
        "home",
        "unhome",
        "auto",
        "abort",
        "program_open",
        "set_optional_stop",
        "set_block_delete",
        "debug",
        "flood",
        "mist",
        "feedrate",
        "rapidrate",
        "maxvel",
        "spindleoverride",
        "spindle",
        "brake",
        "jog",
        "mdi",
        "override_limits",
        "load_tool_table",
    }

    def __init__(self, module):
        self.module = module
        self.serial = 0
        self.fail = None

    def __getattr__(self, method):
        if method not in self.METHODS:
            raise AssertionError("Unexpected external command API: " + method)

        def send(*args):
            if self.fail:
                raise self.fail
            self.serial += 1
            self.module.calls.append((method, args))

        return send


class StatusReaderTests(unittest.TestCase):
    def test_feedback_opens_only_status_and_keeps_motion_and_task_lines_separate(self):
        module = FakeLinuxCNC()

        def forbidden():
            self.fail("read-only feedback opened a writable or consumptive channel")

        module.command = module.error_channel = forbidden
        module.status.task_mode = module.MODE_AUTO
        module.status.interp_state = module.INTERP_READING
        module.status.motion_line = 12
        module.status.current_line = 90
        reader = StatusReader(module=module, ini_path="/machine/machine.ini")
        status = reader.poll()
        self.assertTrue(status["connected"])
        self.assertEqual(status["programState"], "running")
        self.assertTrue(status["busy"])
        self.assertEqual(status["velocity"], 0.0)
        self.assertEqual(status["nativeCommandState"], "done")
        self.assertEqual(status["currentLine"], 12)
        self.assertEqual(status["taskLine"], 90)
        self.assertIsNone(status["progressPercent"])
        module.status.paused = True
        self.assertEqual(reader.poll()["programState"], "paused")
        module.status.paused = False
        module.status.interp_state = module.INTERP_IDLE
        self.assertEqual(reader.poll()["programState"], "idle")
        self.assertEqual(module.calls, [])

    def test_update_observer_preserves_unknown_velocity_and_native_pending_state(self):
        module = FakeLinuxCNC()
        module.status.state = module.RCS_EXEC
        module.status.current_vel = float("nan")
        status = StatusReader(module=module).poll()
        self.assertEqual(status["nativeCommandState"], "executing")
        self.assertIsNone(status["velocity"])
        self.assertEqual(module.calls, [])

    def test_disconnect_clears_feedback_and_reconnect_does_not_replay(self):
        module = FakeLinuxCNC()
        reader = StatusReader(module=module)
        self.assertTrue(reader.poll()["connected"])
        module.available = False
        offline = reader.poll()
        self.assertFalse(offline["connected"])
        self.assertIsNone(offline["currentLine"])
        self.assertEqual(offline["programState"], "unknown")
        module.available = True
        self.assertTrue(reader.poll()["connected"])
        reader.close()
        self.assertEqual(module.calls, [])

    def test_configuration_mismatch_is_not_reported_as_a_connected_machine(self):
        reader = StatusReader(module=FakeLinuxCNC(), ini_path="/other/machine.ini")
        self.assertFalse(reader.poll()["connected"])


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.vendor = FakeLinuxCNC()
        self.clock = FakeClock()
        self.controller = Controller(module=self.vendor, clock=self.clock)
        self.controller.poll()

    def confirm(self, **options):
        self.vendor.confirm(**options)
        return self.controller.poll()

    def test_snapshot_observes_machine_and_configuration_without_writing(self):
        s = self.controller.snapshot
        self.assertTrue(s["connected"])
        self.assertEqual(s["axes"], ["X", "Y", "Z"])
        self.assertEqual(s["actualPosition"][:3], [1, 2, 3])
        self.assertEqual(s["jointMap"], {"X": [0], "Y": [1], "Z": [2]})
        self.assertEqual(s["parameterFile"], "/machine/machine.var")
        self.assertEqual(s["toolTablePath"], "/machine/tool.tbl")
        self.assertEqual(s["programPrefix"], "/machine/programs")
        self.assertEqual(s["pyvcpPath"], "/machine/panel.xml")
        self.assertEqual(s["toolTable"][0][3], 4)
        self.assertEqual(s["activeCodes"], ["G0", "G21", "G54", "M5", "M9"])
        self.assertEqual(s["maxVelocityLimit"], 40)
        self.assertEqual(s["jogMaxVelocity"], 20)
        self.assertEqual(self.vendor.calls, [])

    def test_spindle_feedback_requires_a_writer_and_converts_revolutions_per_second(self):
        hal = Mock(error=RuntimeError)
        self.vendor.status.spindle[0]["speed"] = 1200
        with patch.dict(sys.modules, {"linuxcnc": self.vendor, "hal": hal}):
            controller = Controller(clock=self.clock)
            try:
                hal.pin_has_writer.return_value = False
                self.assertIsNone(controller.poll()["spindleFeedbackRpm"])
                hal.get_value.assert_not_called()
                hal.pin_has_writer.return_value = True
                for rps, rpm in ((-10.5, 630.0), (0.0, 0.0), (float("nan"), None)):
                    hal.get_value.return_value = rps
                    observed = controller.poll()
                    self.assertEqual(observed["spindleFeedbackRpm"], rpm)
                    self.assertEqual(observed["spindleSpeed"], 1200)
                hal.get_value.assert_called_with("spindle.0.speed-in")
                self.vendor.available = False
                self.assertIsNone(controller.poll()["spindleFeedbackRpm"])
                hal.component.return_value.exit.assert_called_once()
            finally:
                controller.close()

    def test_table_offsets_use_the_loaded_model_and_its_live_tool_pin(self):
        model = "xyzbc-trt-kins"
        self.vendor.ini_values[("KINS", "KINEMATICS")] = model
        hal = Mock(error=RuntimeError)
        hal.pin_has_writer.return_value = False
        pins = {model + ".x-offset": -3.5, model + ".tool-offset": 42.0}

        def read_pin(pin):
            if pin not in pins:
                raise NameError(pin)
            return pins[pin]

        hal.get_value.side_effect = read_pin
        with patch.dict(sys.modules, {"linuxcnc": self.vendor, "hal": hal}):
            controller = Controller(clock=self.clock)
            try:
                snapshot = controller.poll()
                self.assertEqual(snapshot["rtcpGeometry"], {"offsetX": -3.5, "toolLength": 42.0})
                self.assertIsNone(snapshot["spindleFeedbackRpm"])
            finally:
                controller.close()

    def test_snapshots_do_not_expose_mutable_internal_state(self):
        s = self.controller.snapshot
        s["actualPosition"][0] = 999
        s["jointMap"]["X"].append(99)
        self.assertEqual(self.controller.snapshot["actualPosition"][0], 1)
        self.assertEqual(self.controller.snapshot["jointMap"]["X"], [0])

    def test_offline_has_no_fabricated_coordinates_and_rejects_motion(self):
        self.vendor.available = False
        s = self.controller.poll()
        self.assertFalse(s["connected"])
        self.assertIsNone(s["actualPosition"])
        self.assertEqual(s["axes"], [])
        self.assertFalse(self.controller.dispatch("program.run"))
        self.assertEqual(self.vendor.calls, [])

    def test_invalid_raw_state_is_not_a_connection(self):
        self.vendor.status.axis_mask = 0
        self.assertFalse(self.controller.poll()["connected"])
        self.assertFalse(
            self.controller.dispatch("jog.start", {"axis": "X", "direction": 1, "velocity": 1})
        )

    def test_selected_ini_must_match_running_machine(self):
        controller = Controller("/other/machine.ini", module=self.vendor)
        self.assertFalse(controller.poll()["connected"])
        self.assertIn("INI", controller.snapshot["message"])

    def test_mdi_waits_for_confirmed_mode_and_never_updates_machine_optimistically(self):
        self.assertTrue(self.controller.dispatch("mdi.execute", {"text": "G0 X1"}))
        self.assertEqual(self.vendor.calls, [("mode", (self.vendor.MODE_MDI,))])
        self.assertEqual(self.controller.snapshot["mode"], "manual")
        self.assertEqual(self.controller.snapshot["commandState"], "pending")
        self.controller.poll()
        self.assertEqual(len(self.vendor.calls), 1)
        self.confirm(apply=False)
        self.assertEqual(len(self.vendor.calls), 1)
        self.vendor.status.task_mode = self.vendor.MODE_MDI
        self.controller.poll()
        self.assertEqual(self.vendor.calls[-1], ("mdi", ("G0 X1",)))
        self.assertEqual(self.controller.snapshot["commandState"], "sent")
        self.assertEqual(self.confirm()["commandState"], "completed")

    def test_power_estop_and_homing_are_enforced(self):
        for field, value in (("enabled", False), ("estop", True), ("homed", [1, 0, 1])):
            original = getattr(self.vendor.status, field)
            setattr(self.vendor.status, field, value)
            self.assertFalse(self.controller.dispatch("mdi.execute", {"text": "G0 X1"}))
            self.assertFalse(self.controller.dispatch("program.run"))
            setattr(self.vendor.status, field, original)
        self.assertEqual(self.vendor.calls, [])

    def test_no_force_homing_is_respected_from_ini(self):
        self.vendor.ini_values[("TRAJ", "NO_FORCE_HOMING")] = "1"
        self.vendor.status.homed = [0, 0, 0]
        controller = Controller(module=self.vendor)
        self.assertTrue(controller.dispatch("mdi.execute", {"text": "G0 X1"}))

    def test_busy_machine_rejects_mdi_and_home(self):
        self.vendor.status.interp_state = self.vendor.INTERP_READING
        self.assertFalse(self.controller.dispatch("mdi.execute", {"text": "G0 X1"}))
        self.assertFalse(self.controller.dispatch("machine.home-all"))
        self.assertFalse(self.controller.dispatch("file.open", {"path": "/tmp/a.ngc"}))

    def test_lost_power_after_mode_request_prevents_followup_mdi(self):
        self.controller.dispatch("mdi.execute", {"text": "G0 X1"})
        self.vendor.status.enabled = False
        self.assertEqual(self.confirm()["commandState"], "error")
        self.assertEqual(len(self.vendor.calls), 1)

    def test_disconnect_discards_pending_movement_and_does_not_replay(self):
        self.controller.dispatch("mdi.execute", {"text": "G0 X1"})
        self.vendor.available = False
        self.assertEqual(self.controller.poll()["commandState"], "unknown")
        self.vendor.available = True
        self.vendor.confirm()
        self.assertTrue(self.controller.poll()["connected"])
        self.assertEqual(len(self.vendor.calls), 1)
        self.assertEqual(self.controller.snapshot["commandState"], "unknown")

    def test_external_command_serial_cancels_the_sequence(self):
        self.controller.dispatch("mdi.execute", {"text": "G0 X1"})
        self.vendor.status.echo_serial_number = self.vendor.commands.serial + 1
        self.assertEqual(self.controller.poll()["commandState"], "unknown")
        self.assertEqual(len(self.vendor.calls), 1)

    def test_unconfirmed_command_times_out_without_retry(self):
        self.controller.dispatch("machine.mode", {"mode": "mdi"})
        self.clock.now += 11
        self.assertEqual(self.controller.poll()["commandState"], "unknown")
        self.controller.poll()
        self.assertEqual(len(self.vendor.calls), 1)

    def test_command_error_and_error_channel_cancel_pending_sequence(self):
        self.controller.dispatch("mdi.execute", {"text": "G0 X1"})
        self.assertEqual(self.confirm(state=self.vendor.RCS_ERROR)["commandState"], "error")
        self.assertEqual(len(self.vendor.calls), 1)
        self.controller.dispatch("mdi.execute", {"text": "G0 X2"})
        self.vendor.errors.append((self.vendor.OPERATOR_ERROR, "machine fault"))
        s = self.controller.poll()
        self.assertEqual(s["commandState"], "error")
        self.assertEqual(s["errors"][-1]["message"], "machine fault")

    def test_send_exception_is_unknown_not_success(self):
        self.vendor.commands.fail = RuntimeError("lost NML receipt")
        self.assertFalse(self.controller.dispatch("machine.power", {"enabled": False}))
        self.assertEqual(self.controller.snapshot["commandState"], "unknown")
        self.assertTrue(self.controller.snapshot["powered"])

    def test_rejected_concurrent_command_does_not_discard_original(self):
        self.controller.dispatch("mdi.execute", {"text": "G0 X1"})
        self.assertFalse(self.controller.dispatch("machine.home-all"))
        self.assertEqual(self.controller.snapshot["commandState"], "pending")
        self.confirm()
        self.assertEqual(self.vendor.calls[-1], ("mdi", ("G0 X1",)))

    def test_program_stop_preempts_pending_mode_and_never_sends_mdi(self):
        self.controller.dispatch("mdi.execute", {"text": "G0 X1"})
        self.assertTrue(self.controller.dispatch("program.stop"))
        self.assertEqual(self.vendor.calls[-1], ("abort", ()))
        self.confirm()
        self.assertFalse(any(call[0] == "mdi" for call in self.vendor.calls))

    def test_program_run_switches_to_auto_and_tracks_actual_program_state(self):
        self.assertTrue(self.controller.dispatch("program.run-line", {"line": 12}))
        self.assertEqual(self.vendor.calls[-1], ("mode", (self.vendor.MODE_AUTO,)))
        self.confirm()
        self.assertEqual(self.vendor.calls[-1], ("auto", (self.vendor.AUTO_RUN, 12)))
        self.assertFalse(self.controller.snapshot["busy"])
        s = self.confirm(state=self.vendor.RCS_EXEC)
        self.assertTrue(s["busy"])
        self.assertEqual(s["commandState"], "completed")
        self.assertTrue(self.controller.dispatch("program.pause"))
        self.assertTrue(self.confirm()["paused"])
        self.assertTrue(self.controller.dispatch("program.resume"))
        self.assertFalse(self.confirm()["paused"])

    def test_run_requires_program_and_explicit_valid_start_line(self):
        self.assertFalse(self.controller.dispatch("program.run-line"))
        self.assertFalse(self.controller.dispatch("program.run-line", {"line": 1.5}))
        self.vendor.status.file = ""
        self.assertFalse(self.controller.dispatch("program.run"))

    def test_homing_changes_task_and_motion_mode_before_joint_command(self):
        self.vendor.status.task_mode = self.vendor.MODE_MDI
        self.vendor.status.motion_mode = self.vendor.TRAJ_MODE_TELEOP
        self.vendor.status.homed = [0, 0, 0]
        self.assertTrue(self.controller.dispatch("machine.home-all"))
        self.assertEqual(self.vendor.calls[-1], ("mode", (self.vendor.MODE_MANUAL,)))
        self.confirm()
        self.assertEqual(self.vendor.calls[-1], ("teleop_enable", (0,)))
        self.confirm()
        self.assertEqual(self.vendor.calls[-1], ("home", (-1,)))
        self.assertEqual(self.confirm()["homed"], [True] * 3)

    def test_known_kinematic_coordinates_define_joint_mapping_not_axis_index(self):
        self.vendor.ini_values[("KINS", "KINEMATICS")] = "trivkins coordinates=ZXY kinstype=BOTH"
        controller = Controller(module=self.vendor)
        self.assertTrue(controller.dispatch("machine.home-X"))
        self.assertEqual(self.vendor.calls[-1], ("home", (1,)))

    def test_unknown_kinematics_and_duplicate_axes_are_not_guessed(self):
        for kinematics in ("pumakins", "trivkins coordinates=XXZ"):
            self.vendor.ini_values[("KINS", "KINEMATICS")] = kinematics
            controller = Controller(module=self.vendor)
            self.assertFalse(
                controller.dispatch("jog.start", {"axis": "X", "direction": 1, "velocity": 1})
            )
        self.vendor.ini_values[("KINS", "KINEMATICS")] = "pumakins"
        controller = Controller(module=self.vendor)
        self.assertFalse(controller.dispatch("machine.home-X"))
        self.assertEqual(self.vendor.calls, [])

    def test_synchronized_homing_group_requires_home_all(self):
        self.vendor.ini_values[("JOINT_0", "HOME_SEQUENCE")] = "-1"
        controller = Controller(module=self.vendor)
        self.assertFalse(controller.dispatch("machine.home-X"))
        self.assertTrue(controller.dispatch("machine.home-all"))

    def test_joint_jog_allows_unhomed_and_sends_native_units_per_second(self):
        self.vendor.status.homed = [0, 0, 0]
        self.assertTrue(
            self.controller.dispatch("jog.start", {"axis": "Y", "direction": -1, "velocity": 2.5})
        )
        self.assertEqual(self.vendor.calls[-1], ("jog", (self.vendor.JOG_CONTINUOUS, 1, 1, -2.5)))
        self.controller.stop_jog()
        self.assertEqual(self.vendor.calls[-1], ("jog", (self.vendor.JOG_STOP, 1, 1)))

    def test_world_jog_uses_canonical_axis_index_and_requires_homing(self):
        self.vendor.status.motion_mode = self.vendor.TRAJ_MODE_TELEOP
        self.vendor.status.homed = [0, 0, 0]
        self.assertFalse(
            self.controller.dispatch("jog.start", {"axis": "Z", "direction": 1, "velocity": 2})
        )
        self.vendor.status.homed = [1, 1, 1]
        self.assertTrue(
            self.controller.dispatch(
                "jog.start", {"axis": "Z", "direction": 1, "velocity": 2, "increment": 0.1}
            )
        )
        self.assertEqual(
            self.vendor.calls[-1], ("jog", (self.vendor.JOG_INCREMENT, 0, 2, 2.0, 0.1))
        )

    def test_release_before_mode_confirmation_cancels_unsent_jog(self):
        self.vendor.status.task_mode = self.vendor.MODE_MDI
        self.controller.dispatch("jog.start", {"axis": "X", "direction": 1, "velocity": 2})
        self.controller.stop_jog()
        self.confirm()
        self.assertFalse(any(call[0] == "jog" for call in self.vendor.calls))

    def test_close_stops_owned_jog_and_disables_future_commands(self):
        self.controller.dispatch("jog.start", {"axis": "X", "direction": 1, "velocity": 2})
        self.controller.close()
        self.assertEqual(self.vendor.calls[-1], ("jog", (self.vendor.JOG_STOP, 1, 0)))
        self.assertFalse(self.controller.poll()["connected"])
        self.assertFalse(self.controller.dispatch("program.run"))
        self.controller.close()
        self.assertEqual(len(self.vendor.calls), 2)

    def test_invalid_jog_values_never_reach_linuxcnc(self):
        base = {"axis": "X", "direction": 1, "velocity": 1}
        for update in (
            {"axis": "A"},
            {"direction": 0},
            {"direction": True},
            {"velocity": 0},
            {"velocity": float("nan")},
            {"velocity": 31},
            {"increment": -1},
        ):
            self.assertFalse(self.controller.dispatch("jog.start", {**base, **update}))
        self.assertEqual(self.vendor.calls, [])

    def test_overrides_are_ratios_and_config_limits_are_enforced(self):
        for action, value, method in (
            ("override.feed", 1.25, "feedrate"),
            ("override.rapid", 0.5, "rapidrate"),
            ("override.spindle", 1.1, "spindleoverride"),
            ("velocity.max", 12.0, "maxvel"),
        ):
            self.assertTrue(self.controller.dispatch(action, {"value": value}))
            self.assertEqual(self.vendor.calls[-1], (method, (value,)))
            self.assertEqual(self.confirm()["commandState"], "completed")
        for action, value in (
            ("override.feed", 150),
            ("override.rapid", 1.1),
            ("override.spindle", 0.4),
            ("velocity.max", 41),
        ):
            self.assertFalse(self.controller.dispatch(action, {"value": value}))

    def test_touchoff_converts_native_units_to_current_gcode_units(self):
        self.vendor.status.task_mode = self.vendor.MODE_MDI
        self.vendor.status.gcodes = [0, 200, 540]
        self.assertTrue(
            self.controller.dispatch(
                "machine.touch-off", {"axis": "X", "value": 25.4, "system": "G54"}
            )
        )
        self.assertEqual(self.vendor.calls[-1], ("mdi", ("G10 L20 P1 X1",)))
        self.confirm()
        self.vendor.status.linear_units = 1 / 25.4
        self.vendor.status.gcodes = [0, 210, 540]
        self.assertTrue(
            self.controller.dispatch(
                "machine.touch-off", {"axis": "Z", "value": 1, "system": "G55"}
            )
        )
        self.assertEqual(self.vendor.calls[-1], ("mdi", ("G10 L20 P2 Z25.4",)))

    def test_offsets_require_explicit_axis_value_system_and_do_not_move(self):
        for payload in (
            {"axis": "X", "value": 0},
            {"axis": "X", "system": "G54"},
            {"value": 0, "system": "G54"},
            {"axis": "X", "value": 0, "system": "G999"},
        ):
            self.assertFalse(self.controller.dispatch("machine.touch-off", payload))
        self.vendor.status.task_mode = self.vendor.MODE_MDI
        self.assertTrue(self.controller.dispatch("machine.zero-G92"))
        self.assertEqual(self.vendor.calls[-1], ("mdi", ("G92.1",)))

    def test_tool_touch_off_uses_explicit_tool_and_coordinate_system(self):
        self.vendor.status.task_mode = self.vendor.MODE_MDI
        self.assertTrue(
            self.controller.dispatch("tool.touch-off", {"axis": "Z", "value": 0, "system": "G59.3"})
        )
        self.assertEqual(self.vendor.calls[-1], ("mdi", ("G10 L11 P1 Z0",)))

    def test_mdi_rejects_multiline_nul_empty_and_byte_overflow(self):
        for text in ("", " ", "G0 X0\nM3", "G0\x00M3", "中" * 100):
            self.assertFalse(self.controller.dispatch("mdi.execute", {"text": text}))
        self.assertEqual(self.vendor.calls, [])

    def test_spindle_aliases_use_configured_rpm_and_real_status(self):
        self.assertTrue(self.controller.dispatch("spindle.cw"))
        self.assertEqual(
            self.vendor.calls[-1], ("spindle", (self.vendor.SPINDLE_FORWARD, 500.0, 0))
        )
        self.assertEqual(self.controller.snapshot["spindleSpeed"], 0)
        self.assertEqual(self.confirm()["spindleSpeed"], 500)
        self.assertFalse(self.controller.dispatch("spindle.reverse", {"speed": 2500}))
        self.assertTrue(self.controller.dispatch("spindle.stop"))
        self.assertEqual(self.confirm()["spindleDirection"], 0)

    def test_switches_are_confirmed_from_status(self):
        for action, key in (
            ("coolant.flood", "flood"),
            ("coolant.mist", "mist"),
            ("program.optional", "optionalStop"),
            ("program.block-delete", "blockDelete"),
        ):
            self.assertTrue(self.controller.dispatch(action))
            self.assertFalse(self.controller.snapshot[key])
            self.assertTrue(self.confirm()[key])

    def test_override_limits_requires_actual_hard_limit(self):
        self.assertFalse(self.controller.dispatch("machine.override-limits"))
        self.vendor.status.joint[0]["min_hard_limit"] = True
        self.assertTrue(self.controller.dispatch("machine.override-limits"))
        self.assertEqual(self.vendor.calls[-1], ("override_limits", ()))

    def test_program_open_and_tool_reload_use_real_vendor_api(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "test.ngc"
            path.write_text("G0 X0\nM2\n", encoding="utf-8")
            self.assertTrue(self.controller.dispatch("file.open", {"path": str(path)}))
            self.assertEqual(self.vendor.calls[-1], ("program_open", (str(path),)))
            self.assertEqual(self.confirm()["file"], str(path))
        self.assertTrue(self.controller.dispatch("tool.reload"))
        self.assertEqual(self.vendor.calls[-1], ("load_tool_table", ()))

    def test_error_drain_is_bounded_and_errors_are_separate_from_state(self):
        self.vendor.errors = [(self.vendor.OPERATOR_TEXT, f"message {i}") for i in range(200)]
        self.assertEqual(len(self.controller.poll()["errors"]), 32)
        for _ in range(10):
            self.controller.poll()
        self.assertEqual(len(self.controller.snapshot["errors"]), 100)
        self.assertTrue(self.controller.snapshot["connected"])

    def test_explicit_joint_index_handles_unknown_kinematics_without_guessing(self):
        self.vendor.ini_values[("KINS", "KINEMATICS")] = "pumakins"
        controller = Controller(module=self.vendor)
        self.assertEqual(controller.poll()["joints"], [0, 1, 2])
        self.assertTrue(
            controller.dispatch(
                "jog.start", {"axis": 2, "mode": "joint", "direction": 1, "velocity": 1}
            )
        )
        self.assertEqual(self.vendor.calls[-1], ("jog", (self.vendor.JOG_CONTINUOUS, 1, 2, 1.0)))
        controller.stop_jog()
        self.vendor.confirm()
        controller.poll()
        self.assertTrue(controller.dispatch("home", {"joint": 2}))
        self.assertEqual(self.vendor.calls[-1], ("home", (2,)))

    def test_requested_jog_mode_must_match_observed_mode(self):
        self.assertFalse(
            self.controller.dispatch(
                "jog.start", {"axis": "X", "mode": "world", "direction": 1, "velocity": 1}
            )
        )
        self.assertEqual(self.vendor.calls, [])

    def test_program_save_is_atomic_and_rejects_fresh_busy_or_offline_state(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "saved.ngc"
            path.write_text("OLD")
            self.vendor.status.interp_state = self.vendor.INTERP_READING
            self.assertFalse(
                self.controller.dispatch("file.save", {"path": str(path), "text": "M2\n"})
            )
            self.assertEqual(path.read_text(), "OLD")
            self.vendor.status.interp_state = self.vendor.INTERP_IDLE
            self.vendor.available = False
            self.assertFalse(
                self.controller.dispatch("file.save", {"path": str(path), "text": "M2\n"})
            )
            self.assertEqual(path.read_text(), "OLD")
            self.vendor.available = True
            self.assertTrue(
                self.controller.dispatch("file.save", {"path": str(path), "text": "M2\n"})
            )
            self.assertEqual(path.read_text(), "M2\n")
            self.assertEqual(self.vendor.calls[-1], ("program_open", (str(path),)))
            self.assertEqual(list(Path(directory).glob(".bettercnc-*")), [])

    def test_tool_table_save_validates_fields_before_touching_file(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "tool.tbl"
            path.write_text("OLD")
            self.vendor.ini_values[("EMCIO", "TOOL_TABLE")] = str(path)
            controller = Controller(module=self.vendor)
            invalid = (
                "T1 P1 D-1",
                "T1e2 P1",
                "T1.0 P1",
                "T2147483648 P1",
                "T1.5 P1",
                "T1 P1.2",
                "T1 P1 Q1.2",
                "T1 P1 Q10",
                "T1 P1 Dnan",
                "T1 P1 X1e999",
                "T1 P1 BAD",
                "T1 P1\nT1 P2",
                "T1 D3",
            )
            for text in invalid:
                self.assertFalse(controller.dispatch("tooltable.save", {"text": text}), text)
                self.assertEqual(path.read_text(), "OLD")
            valid = "T1 P1 Z3.25 D6 Q0 ; endmill\nT2 P2 X1e-2 D4\n"
            self.assertTrue(controller.dispatch("tooltable.save", {"text": valid}))
            self.assertEqual(path.read_text(), valid)
            self.assertEqual(self.vendor.calls[-1], ("load_tool_table", ()))

    def test_tool_touch_off_refreshes_only_previously_active_g43_after_confirmation(self):
        self.vendor.status.task_mode = self.vendor.MODE_MDI
        self.vendor.status.gcodes.append(430)
        self.assertTrue(
            self.controller.dispatch("tool.touch-off", {"axis": "Z", "value": 0, "system": "G54"})
        )
        self.assertEqual(self.vendor.calls[-1], ("mdi", ("G10 L10 P1 Z0",)))
        self.confirm()
        self.assertEqual(self.vendor.calls[-1], ("mdi", ("G43 H1",)))

    def test_failed_stop_retains_owned_jog_for_explicit_stop_retry(self):
        self.controller.dispatch("jog.start", {"axis": "X", "direction": 1, "velocity": 1})
        self.vendor.commands.fail = RuntimeError("NML send failed")
        self.controller.stop_jog()
        self.assertEqual(self.controller.snapshot["commandState"], "unknown")
        self.vendor.commands.fail = None
        self.controller.stop_jog()
        self.assertEqual(self.vendor.calls[-1], ("jog", (self.vendor.JOG_STOP, 1, 0)))
        self.confirm()
        self.assertTrue(self.controller.dispatch("machine.home-all"))

    def test_failed_abort_retains_jog_until_explicit_close_stop(self):
        self.controller.dispatch("jog.start", {"axis": "X", "direction": 1, "velocity": 1})
        self.vendor.commands.fail = RuntimeError("abort receipt missing")
        self.assertFalse(self.controller.dispatch("program.stop"))
        self.vendor.commands.fail = None
        self.controller.close()
        self.assertEqual(self.vendor.calls[-1], ("jog", (self.vendor.JOG_STOP, 1, 0)))

    def test_debug_flags_are_not_updated_until_observed_confirmation(self):
        self.assertTrue(self.controller.snapshot["capabilities"]["machine.debug"])
        self.assertTrue(self.controller.dispatch("machine.debug", {"value": 0x101}))
        self.assertEqual(self.vendor.calls[-1], ("debug", (0x101,)))
        self.assertEqual(self.controller.snapshot["debug"], 0)
        self.assertFalse(self.controller.snapshot["capabilities"]["machine.debug"])
        self.assertEqual(self.confirm(apply=False)["commandState"], "sent")
        observed = self.confirm()
        self.assertEqual(observed["debug"], 0x101)
        self.assertEqual(observed["commandState"], "completed")
        self.assertTrue(observed["capabilities"]["machine.debug"])

    def test_debug_flags_reject_invalid_values_and_busy_or_offline_status(self):
        for value in (None, True, -1, 2147483648, 1.5, 1.0, "3", float("nan")):
            self.assertFalse(self.controller.dispatch("machine.debug", {"value": value}))
        self.vendor.status.interp_state = self.vendor.INTERP_READING
        self.assertFalse(self.controller.dispatch("machine.debug", {"value": 0}))
        self.assertFalse(self.controller.snapshot["capabilities"]["machine.debug"])
        self.vendor.available = False
        self.assertFalse(self.controller.dispatch("machine.debug", {"value": 0}))
        self.assertIsNone(self.controller.snapshot["debug"])
        self.assertEqual(self.vendor.calls, [])

    def test_debug_flags_allow_idle_power_off_without_enabling_machine(self):
        self.vendor.status.task_state = self.vendor.STATE_OFF
        self.vendor.status.enabled = False
        self.assertTrue(self.controller.dispatch("machine.debug", {"value": 2147483647}))
        self.assertEqual(self.vendor.calls, [("debug", (2147483647,))])
        self.assertFalse(self.confirm()["powered"])

    def test_unknown_ui_actions_do_not_become_machine_commands(self):
        for action in ("file.quit", "machine.hal-config", "mdi.clear", "program.launch-unsafe"):
            self.assertFalse(self.controller.dispatch(action))
        self.assertEqual(self.vendor.calls, [])


if __name__ == "__main__":
    unittest.main()
