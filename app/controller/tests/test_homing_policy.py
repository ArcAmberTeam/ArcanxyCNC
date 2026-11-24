"""HOME ALL completion and dedicated-machine interlocks via the public API."""

import os
import unittest
from unittest.mock import patch

from test_controller import FakeClock, FakeLinuxCNC

from bettercnc_controller import Controller


def six_joint_vendor():
    vendor = FakeLinuxCNC()
    vendor.ini_values[("KINS", "JOINTS")] = "6"
    vendor.ini_values[("KINS", "KINEMATICS")] = "trivkins coordinates=XYZABC"
    vendor.status.joints = 6
    vendor.status.axis_mask = 63
    vendor.status.homed = [0] * 6
    vendor.status.joint = [dict(vendor.status.joint[0]) for _ in range(6)]
    for joint in range(3):
        vendor.ini_values[(f"JOINT_{joint}", "HOME_SEQUENCE")] = str(joint + 1)
    for joint in range(3, 6):
        vendor.ini_values[(f"JOINT_{joint}", "HOME_SEQUENCE")] = "101"
    return vendor


def verified_profile(vendor):
    """Only a test fixture: these distances are never production commissioning data."""
    vendor.ini_values[("EMCMOT", "HOMEMOD")] = "zhulong_homing"
    vendor.ini_values[("TRAJ", "LINEAR_UNITS")] = "mm"
    vendor.ini_values[("BETTERCNC_HOMING", "PROFILE")] = "zhulong-v2"
    vendor.ini_values[("BETTERCNC_HOMING", "SWITCH_INPUTS_VERIFIED")] = "YES"
    vendor.ini_values[("BETTERCNC_HOMING", "MOTOR_MAPPING_VERIFIED")] = "YES"
    vendor.ini_values[("BETTERCNC_HOMING", "MOTOR_DIRECTIONS_VERIFIED")] = "YES"
    for joint, axis, direction in ((0, "X", -1), (1, "Y", 1), (2, "Z", -1)):
        vendor.ini_values[("BETTERCNC_HOMING", f"TRAVEL_{axis}_MM")] = "100"
        values = {
            "HOME": "0",
            "HOME_OFFSET": str(direction * 5),
            "HOME_SEARCH_VEL": str(direction * 2),
            "HOME_LATCH_VEL": str(direction * 0.5),
            "HOME_FINAL_VEL": "2",
            "HOME_IGNORE_LIMITS": "YES",
            "HOME_USE_INDEX": "NO",
        }
        for key, value in values.items():
            vendor.ini_values[(f"JOINT_{joint}", key)] = value
        for section in ("AXIS_" + axis, f"JOINT_{joint}"):
            vendor.ini_values[(section, "MIN_LIMIT")] = "-90" if direction > 0 else "0"
            vendor.ini_values[(section, "MAX_LIMIT")] = "0" if direction > 0 else "90"


def parallel_profile():
    vendor = FakeLinuxCNC()
    verified_profile(vendor)
    vendor.status.homed = [0, 0, 0]
    vendor.ini_values.update(
        {
            ("KINS", "KINEMATICS"): "trivkins coordinates=XYZ",
            ("BETTERCNC_HOMING", "CONFIGURATION_REVISION"): "zhulong-xyz-v5-20261026",
            ("BETTERCNC_HOMING", "PARALLEL_TEST_CONDITION"): "EMPTY_TABLE_NO_TOOL",
            ("BETTERCNC_HOMING", "SWITCH_OVERRUN_MM"): "1",
        }
    )
    for joint, axis, travel in ((0, "X", 420), (1, "Y", 275), (2, "Z", 90)):
        vendor.ini_values[("BETTERCNC_HOMING", f"TRAVEL_{axis}_MM")] = str(travel)
        for key, value in {
            "HOME_OFFSET": "-5",
            "HOME_SEARCH_VEL": "-5" if axis == "Z" else "-15",
            "HOME_BACKOFF_VEL": "2",
            "HOME_LATCH_VEL": "-1",
            "HOME_FINAL_VEL": "2" if axis == "Z" else "5",
            "HOME_SEQUENCE": "1",
            "MAX_ACCELERATION": "750",
        }.items():
            vendor.ini_values[(f"JOINT_{joint}", key)] = value
        for section in (f"JOINT_{joint}", f"AXIS_{axis}"):
            vendor.ini_values[(section, "MIN_LIMIT")] = "-0.1"
            vendor.ini_values[(section, "MAX_LIMIT")] = str(travel - 10)
    return vendor


def bc_profile():
    vendor = parallel_profile()
    vendor.ini_values.update(
        {
            ("BETTERCNC_HOMING", "CONFIGURATION_REVISION"): "bc-xyz-parallel-homing-20261124",
            ("BETTERCNC_HOMING", "TRAVEL_SOURCE"): "OPERATOR_CONFIRMED_ENVELOPE",
        }
    )
    for joint, axis, travel, maximum in (
        (0, "X", 600, 580),
        (1, "Y", 400, 380),
        (2, "Z", 90, 50),
    ):
        vendor.ini_values[("BETTERCNC_HOMING", f"TRAVEL_{axis}_MM")] = str(travel)
        for key, value in {
            "STEP_SCALE": "-320" if axis == "Z" else "320",
            "HOME_SEARCH_VEL": "-2",
            "HOME_LATCH_VEL": "-0.5",
            "HOME_BACKOFF_VEL": "1",
            "HOME_FINAL_VEL": "2",
            "HOME_SEQUENCE": "1",
            "MAX_ACCELERATION": "50",
        }.items():
            vendor.ini_values[(f"JOINT_{joint}", key)] = value
        for section in (f"JOINT_{joint}", f"AXIS_{axis}"):
            vendor.ini_values[(section, "MAX_LIMIT")] = str(maximum)
    return vendor


class HomingPolicyTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {"BETTERCNC_KIOSK": "0"})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_confirmed_manual_home_waits_for_power_and_only_homes_configured_joints(self):
        vendor = six_joint_vendor()
        vendor.status.enabled = False
        vendor.status.task_state = vendor.STATE_OFF
        vendor.status.file = ""
        controller = Controller(module=vendor)
        action = "machine.power-and-home"
        self.assertTrue(controller.poll()["capabilities"][action])
        for clearance in (None, False, 1, "true"):
            self.assertFalse(controller.dispatch(action, {"clearanceConfirmed": clearance}))
        self.assertEqual(vendor.calls, [])
        self.assertTrue(controller.dispatch(action, {"clearanceConfirmed": True}))
        self.assertFalse(controller.poll()["capabilities"][action])
        self.assertEqual(vendor.calls, [("state", (vendor.STATE_ON,))])
        vendor.confirm(apply=False)
        controller.poll()
        self.assertEqual(len(vendor.calls), 1)
        for method in ("mode", "teleop_enable", "home"):
            vendor.confirm()
            controller.poll()
            self.assertEqual(vendor.calls[-1][0], method)
        self.assertEqual(vendor.calls[-1][1], (-1,))
        vendor.confirm(apply=False)
        vendor.status.homed[:3] = [1, 1, 1]
        self.assertEqual(controller.poll()["commandState"], "completed")
        self.assertEqual(len(vendor.calls), 4)

    def test_manual_home_obeys_estop_before_and_after_enabling(self):
        vendor = FakeLinuxCNC()
        vendor.status.enabled = False
        vendor.status.task_state = vendor.STATE_OFF
        vendor.status.estop = True
        controller = Controller(module=vendor)
        action = "machine.power-and-home"
        confirmed = {"clearanceConfirmed": True}
        self.assertFalse(controller.poll()["capabilities"][action])
        self.assertFalse(controller.dispatch(action, confirmed))
        self.assertEqual(vendor.calls, [])
        vendor.status.estop = False
        self.assertTrue(controller.dispatch(action, confirmed))
        vendor.confirm()
        vendor.status.estop = True
        self.assertEqual(controller.poll()["commandState"], "error")
        self.assertEqual(vendor.calls, [("state", (vendor.STATE_ON,))])

    def test_confirmed_manual_home_waits_for_estop_reset_before_power_and_home(self):
        vendor = bc_profile()
        vendor.status.estop = True
        vendor.status.enabled = False
        vendor.status.task_state = vendor.STATE_ESTOP
        controller = Controller(module=vendor)
        action = "machine.power-and-home"
        self.assertTrue(controller.poll()["capabilities"][action])
        self.assertFalse(controller.poll()["capabilities"]["program.home-and-run"])
        self.assertFalse(controller.dispatch(action, {"clearanceConfirmed": False}))
        self.assertEqual(vendor.calls, [])
        self.assertTrue(controller.dispatch(action, {"clearanceConfirmed": True}))
        self.assertEqual(vendor.calls, [("state", (vendor.STATE_ESTOP_RESET,))])
        vendor.confirm(apply=False)
        controller.poll()
        self.assertEqual(len(vendor.calls), 1)
        vendor.confirm()
        controller.poll()
        self.assertEqual(vendor.calls[-1], ("state", (vendor.STATE_ON,)))
        for method in ("mode", "teleop_enable", "home"):
            vendor.confirm()
            controller.poll()
            self.assertEqual(vendor.calls[-1][0], method)
        self.assertEqual(vendor.calls[-1], ("home", (-1,)))
        vendor.confirm()
        self.assertEqual(controller.poll()["commandState"], "completed")

    def test_unreleased_estop_cannot_advance_to_enable_or_home(self):
        vendor = bc_profile()
        vendor.status.estop = True
        vendor.status.enabled = False
        vendor.status.task_state = vendor.STATE_ESTOP
        clock = FakeClock()
        controller = Controller(module=vendor, clock=clock)
        self.assertTrue(controller.dispatch("machine.power-and-home", {"clearanceConfirmed": True}))
        vendor.confirm(apply=False)
        clock.now = 11
        self.assertEqual(controller.poll()["commandState"], "unknown")
        self.assertEqual(vendor.calls, [("state", (vendor.STATE_ESTOP_RESET,))])

    def test_bc_homing_preserves_acceptance_direction_sequence_and_braking_checks(self):
        controller = Controller(module=bc_profile())
        self.assertTrue(controller.poll()["capabilities"]["machine.home-all"])
        for key, value in (
            (("BETTERCNC_HOMING", "MOTOR_DIRECTIONS_VERIFIED"), "NO"),
            (("BETTERCNC_HOMING", "MOTOR_MAPPING_VERIFIED"), "NO"),
            (("BETTERCNC_HOMING", "TRAVEL_SOURCE"), "UNCONFIRMED"),
            (("BETTERCNC_HOMING", "TRAVEL_Z_MM"), "20"),
            (("JOINT_2", "STEP_SCALE"), "320"),
            (("JOINT_1", "HOME_SEARCH_VEL"), "2"),
            (("JOINT_2", "HOME_SEQUENCE"), "2"),
            (("JOINT_2", "HOME_OFFSET"), "5"),
            (("JOINT_2", "HOME_BACKOFF_VEL"), "0"),
            (("JOINT_0", "MAX_ACCELERATION"), "1"),
        ):
            with self.subTest(key=key, value=value):
                vendor = bc_profile()
                vendor.ini_values[key] = value
                controller = Controller(module=vendor)
                self.assertFalse(controller.poll()["capabilities"]["machine.home-all"])
                self.assertFalse(controller.dispatch("machine.home-all"))
                self.assertEqual(vendor.calls, [])

    def test_parallel_bc_homing_has_a_bounded_longer_completion_window(self):
        for action in ("machine.home-all", "machine.power-and-home"):
            with self.subTest(action=action):
                vendor = bc_profile()
                clock = FakeClock()
                controller = Controller(module=vendor, clock=clock)
                self.assertTrue(controller.dispatch(action, {"clearanceConfirmed": True}))
                vendor.confirm(apply=False)
                vendor.status.joint[2]["homing"] = True
                vendor.status.inpos = False
                clock.now = 600
                self.assertEqual(controller.poll()["commandState"], "sent")
                clock.now = 901
                self.assertEqual(controller.poll()["commandState"], "unknown")
                self.assertEqual(vendor.calls, [("home", (-1,))])

    def test_home_all_finishes_when_only_configured_xyz_finish(self):
        vendor = six_joint_vendor()
        controller = Controller(module=vendor)
        self.assertTrue(controller.dispatch("machine.home-all"))
        self.assertEqual(vendor.calls, [("home", (-1,))])
        vendor.confirm(apply=False)
        vendor.status.homed = [1, 1, 0, 0, 0, 0]
        self.assertEqual(controller.poll()["commandState"], "sent")
        vendor.status.homed[2] = 1
        vendor.status.joint[2]["homing"] = True
        self.assertEqual(controller.poll()["commandState"], "sent")
        vendor.status.joint[2]["homing"] = False
        snapshot = controller.poll()
        self.assertEqual(snapshot["commandState"], "completed")
        self.assertEqual(snapshot["homeAllJoints"], [0, 1, 2])
        self.assertTrue(snapshot["homeAllHomed"])
        self.assertEqual(snapshot["homed"], [True, True, True, False, False, False])

    def test_omitted_sequences_and_synchronized_groups_match_native_home_all(self):
        vendor = six_joint_vendor()
        for joint in range(3, 6):
            del vendor.ini_values[(f"JOINT_{joint}", "HOME_SEQUENCE")]
        vendor.ini_values[("JOINT_0", "HOME_SEQUENCE")] = "-1"
        vendor.ini_values[("JOINT_1", "HOME_SEQUENCE")] = "1"
        vendor.ini_values[("JOINT_2", "HOME_SEQUENCE")] = "2"
        controller = Controller(module=vendor)
        self.assertFalse(controller.dispatch("machine.home-X"))
        self.assertTrue(controller.dispatch("machine.home-all"))
        vendor.confirm(apply=False)
        vendor.status.homed[:3] = [1, 1, 1]
        self.assertEqual(controller.poll()["commandState"], "completed")

    def test_empty_or_gapped_home_all_is_rejected_before_native_commands(self):
        for sequences in ((101, 101, 101), (1, 3, 4), (-101, 1, 2)):
            with self.subTest(sequences=sequences):
                vendor = FakeLinuxCNC()
                for joint, sequence in enumerate(sequences):
                    vendor.ini_values[(f"JOINT_{joint}", "HOME_SEQUENCE")] = str(sequence)
                controller = Controller(module=vendor)
                self.assertFalse(controller.dispatch("machine.home-all"))
                self.assertFalse(controller.snapshot["capabilities"]["machine.home-all"])
                self.assertEqual(vendor.calls, [])

    def test_xyz_completion_does_not_authorize_any_coordinated_motion(self):
        vendor = six_joint_vendor()
        verified_profile(vendor)
        vendor.status.homed = [1, 1, 1, 0, 0, 0]
        controller = Controller(module=vendor)
        for action, payload in (
            ("mdi.execute", {"text": "G0 A1"}),
            ("mdi.execute", {"text": "G0 X1"}),
            ("machine.mode", {"mode": "mdi"}),
            ("program.run", {}),
            ("mode.world", {}),
        ):
            with self.subTest(action=action):
                self.assertFalse(controller.dispatch(action, payload))
        vendor.status.motion_mode = vendor.TRAJ_MODE_TELEOP
        self.assertFalse(
            controller.dispatch(
                "jog.start", {"axis": "X", "mode": "world", "direction": 1, "velocity": 1}
            )
        )
        snapshot = controller.poll()
        self.assertTrue(snapshot["homeAllHomed"])
        for name in ("mdi.execute", "program.run", "mode.world", "jog.start"):
            self.assertFalse(snapshot["capabilities"][name])
        self.assertEqual(vendor.calls, [])

    def test_dedicated_home_requires_verified_measurements_and_effective_parameters(self):
        cases = (
            (("BETTERCNC_HOMING", "TRAVEL_X_MM"), None),
            (("BETTERCNC_HOMING", "TRAVEL_Y_MM"), "5"),
            (("BETTERCNC_HOMING", "TRAVEL_Z_MM"), "15"),
            (("BETTERCNC_HOMING", "SWITCH_INPUTS_VERIFIED"), "NO"),
            (("BETTERCNC_HOMING", "MOTOR_MAPPING_VERIFIED"), None),
            (("BETTERCNC_HOMING", "MOTOR_MAPPING_VERIFIED"), "NO"),
            (("BETTERCNC_HOMING", "MOTOR_DIRECTIONS_VERIFIED"), None),
            (("BETTERCNC_HOMING", "MOTOR_DIRECTIONS_VERIFIED"), "NO"),
            (("EMCMOT", "HOMEMOD"), "homemod"),
            (("TRAJ", "LINEAR_UNITS"), "inch"),
            (("JOINT_0", "HOME_OFFSET"), "0"),
            (("JOINT_1", "HOME_SEARCH_VEL"), "-2"),
            (("JOINT_2", "HOME_LATCH_VEL"), "0"),
            (("JOINT_0", "MAX_LIMIT"), "100"),
            (("JOINT_3", "HOME_SEQUENCE"), "4"),
        )
        for setting, value in cases:
            with self.subTest(setting=setting, value=value):
                vendor = six_joint_vendor()
                verified_profile(vendor)
                if value is None:
                    del vendor.ini_values[setting]
                else:
                    vendor.ini_values[setting] = value
                controller = Controller(module=vendor)
                self.assertFalse(controller.dispatch("machine.home-all"))
                self.assertFalse(controller.dispatch("machine.home-X"))
                self.assertFalse(controller.dispatch("home", {"joint": 0}))
                self.assertIn("回零未配置", controller.snapshot["commandMessage"])
                self.assertFalse(controller.snapshot["capabilities"]["machine.home-all"])
                self.assertEqual(vendor.calls, [])

    def test_verified_dedicated_profile_homes_xyz_but_never_immediate_homes_abc(self):
        vendor = six_joint_vendor()
        verified_profile(vendor)
        controller = Controller(module=vendor)
        self.assertFalse(controller.dispatch("machine.home-A"))
        self.assertFalse(controller.dispatch("home", {"joint": 4}))
        self.assertEqual(vendor.calls, [])
        self.assertTrue(controller.dispatch("machine.home-X"))
        self.assertEqual(vendor.calls, [("home", (0,))])
        self.assertFalse(controller.snapshot["capabilities"]["machine.home-A"])

    def test_commissioned_profile_enables_home_all_with_negative_xyz_search(self):
        vendor = FakeLinuxCNC()
        vendor.status.homed = [0, 0, 0]
        verified_profile(vendor)
        vendor.ini_values[("BETTERCNC_HOMING", "CONFIGURATION_REVISION")] = "zhulong-xyz-20261026"
        for joint in range(3):
            vendor.ini_values[(f"JOINT_{joint}", "HOME_SEQUENCE")] = str(joint + 1)
        for key, value in (
            ("HOME_SEARCH_VEL", "-2"),
            ("HOME_LATCH_VEL", "-0.5"),
            ("HOME_OFFSET", "-5"),
        ):
            vendor.ini_values[("JOINT_1", key)] = value
        for section in ("AXIS_Y", "JOINT_1"):
            vendor.ini_values[(section, "MIN_LIMIT")] = "0"
            vendor.ini_values[(section, "MAX_LIMIT")] = "90"
        controller = Controller(module=vendor)
        self.assertTrue(controller.poll()["capabilities"]["machine.home-all"])
        self.assertFalse(controller.dispatch("program.run"))
        self.assertTrue(controller.dispatch("machine.home-all"))
        self.assertEqual(vendor.calls, [("home", (-1,))])

    def test_parallel_home_waits_for_all_axes_then_allows_coordinated_motion(self):
        for profile in (parallel_profile, bc_profile):
            with self.subTest(profile=profile.__name__):
                vendor = profile()
                controller = Controller(module=vendor)
                self.assertTrue(controller.poll()["capabilities"]["machine.home-all"])
                self.assertFalse(controller.dispatch("program.run"))
                self.assertTrue(controller.dispatch("machine.home-all"))
                self.assertEqual(vendor.calls, [("home", (-1,))])
                vendor.confirm(apply=False)
                vendor.status.homed = [1, 1, 0]
                self.assertEqual(controller.poll()["commandState"], "sent")
                vendor.status.homed[2] = 1
                vendor.status.joint[2]["homing"] = True
                self.assertEqual(controller.poll()["commandState"], "sent")
                vendor.status.joint[2]["homing"] = False
                snapshot = controller.poll()
                self.assertEqual(snapshot["commandState"], "completed")
                for name in ("mode.world", "mdi.execute", "program.run"):
                    self.assertTrue(snapshot["capabilities"][name], name)

    def test_parallel_home_rejects_unreviewed_speed_clearance_and_braking_budget(self):
        for setting, value in (
            (("BETTERCNC_HOMING", "PARALLEL_TEST_CONDITION"), "UNKNOWN"),
            (("BETTERCNC_HOMING", "SWITCH_OVERRUN_MM"), "0.5"),
            (("JOINT_0", "HOME_SEARCH_VEL"), "-16"),
            (("JOINT_2", "HOME_SEARCH_VEL"), "-15"),
            (("JOINT_0", "HOME_BACKOFF_VEL"), "15"),
            (("JOINT_0", "HOME_LATCH_VEL"), "-10"),
            (("JOINT_2", "HOME_FINAL_VEL"), "5"),
            (("JOINT_1", "HOME_BACKOFF_VEL"), "0"),
            (("JOINT_0", "MAX_ACCELERATION"), "100"),
            (("JOINT_1", "HOME_SEQUENCE"), "2"),
            (("JOINT_0", "MIN_LIMIT"), "0"),
            (("AXIS_Z", "MIN_LIMIT"), "-5"),
        ):
            with self.subTest(setting=setting, value=value):
                vendor = parallel_profile()
                vendor.ini_values[setting] = value
                controller = Controller(module=vendor)
                self.assertFalse(controller.dispatch("machine.home-all"))
                self.assertFalse(controller.poll()["capabilities"]["machine.home-all"])
                self.assertEqual(vendor.calls, [])

    def test_unverified_motor_mapping_blocks_homing_and_coordinated_motion(self):
        vendor = FakeLinuxCNC()
        verified_profile(vendor)
        del vendor.ini_values[("BETTERCNC_HOMING", "MOTOR_MAPPING_VERIFIED")]
        controller = Controller(module=vendor)
        for action, payload in (
            ("machine.home-all", {}),
            ("home", {"joint": 0}),
            ("mdi.execute", {"text": "G0 X1"}),
            ("program.run", {}),
        ):
            self.assertFalse(controller.dispatch(action, payload))
        self.assertIn("电机通道", controller.snapshot["homeAllUnavailableReason"])
        self.assertEqual(vendor.calls, [])

    def test_home_all_reason_tracks_estop_power_and_pending_commands(self):
        vendor = FakeLinuxCNC()
        controller = Controller(module=vendor)
        self.assertEqual(controller.poll()["homeAllUnavailableReason"], "")
        vendor.status.estop = True
        self.assertIn("急停", controller.poll()["homeAllUnavailableReason"])
        vendor.status.estop = False
        vendor.status.enabled = False
        self.assertIn("未使能", controller.poll()["homeAllUnavailableReason"])
        vendor.status.enabled = True
        self.assertTrue(controller.dispatch("machine.home-all"))
        self.assertIn("等待命令", controller.snapshot["homeAllUnavailableReason"])
        self.assertEqual(vendor.calls, [("home", (-1,))])

    def test_actual_three_axis_profile_authorizes_motion_only_after_xyz_are_homed(self):
        vendor = FakeLinuxCNC()
        verified_profile(vendor)
        vendor.ini_values[("KINS", "KINEMATICS")] = "trivkins coordinates=XYZ"
        for joint in range(3):
            vendor.ini_values[(f"JOINT_{joint}", "HOME_SEQUENCE")] = str(joint + 1)
        vendor.status.homed = [0, 0, 0]
        controller = Controller(module=vendor)
        self.assertTrue(controller.dispatch("machine.home-all"))
        vendor.confirm(apply=False)
        vendor.status.homed = [1, 1, 1]
        snapshot = controller.poll()
        self.assertEqual(snapshot["commandState"], "completed")
        self.assertTrue(snapshot["capabilities"]["mdi.execute"])
        self.assertTrue(snapshot["capabilities"]["program.run"])
        self.assertTrue(snapshot["capabilities"]["mode.world"])
        self.assertEqual(snapshot["homed"], [True, True, True])

    def test_kiosk_legacy_instant_homing_and_no_force_bypass_are_blocked(self):
        with patch.dict(os.environ, {"BETTERCNC_KIOSK": "1"}):
            vendor = FakeLinuxCNC()
            vendor.ini_values[("TRAJ", "NO_FORCE_HOMING")] = "1"
            vendor.status.homed = [0, 0, 0]
            controller = Controller(module=vendor)
            self.assertFalse(controller.dispatch("machine.home-all"))
            self.assertFalse(controller.dispatch("mdi.execute", {"text": "G0 X1"}))
            self.assertEqual(vendor.calls, [])
        vendor = FakeLinuxCNC()
        controller = Controller(module=vendor)
        self.assertTrue(controller.dispatch("machine.home-all"))
        self.assertEqual(vendor.calls, [("home", (-1,))])

    def test_unhome_all_still_waits_for_every_joint(self):
        vendor = six_joint_vendor()
        verified_profile(vendor)
        vendor.status.homed = [1] * 6
        controller = Controller(module=vendor)
        self.assertTrue(controller.dispatch("machine.unhome-all"))
        vendor.confirm(apply=False)
        vendor.status.homed[:3] = [0, 0, 0]
        self.assertEqual(controller.poll()["commandState"], "sent")
        vendor.status.homed[3:] = [0, 0, 0]
        self.assertEqual(controller.poll()["commandState"], "completed")


if __name__ == "__main__":
    unittest.main()
