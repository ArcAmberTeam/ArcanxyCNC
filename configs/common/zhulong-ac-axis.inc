# Rotary-axis fragment for a future XYZAC configuration, not a launchable INI.
# Joint order: X=0, Y=1, Z=2, A=3, C=4. Hardware Axis numbers are separate.
# A uses hardware Axis4 / stepgen.04; C uses hardware Axis3 / stepgen.03.
# The active XYZ configuration does not include this file.
# Integration requires five joints, matching kinematics and calibrated rotary
# scale, direction, velocity, acceleration, following error and homing settings.
# C travel/wrapping and rotary pivot geometry remain unspecified.
# No commissioning or motor-direction verification is implied by this fragment.

#--------#
# BEGIN: ZhulongRotaryAxisLimits
[AXIS_A]
MIN_LIMIT = -90.0
MAX_LIMIT = 90.0

[JOINT_3]
TYPE = ANGULAR
MIN_LIMIT = -90.0
MAX_LIMIT = 90.0

[JOINT_4]
TYPE = ANGULAR
# END: ZhulongRotaryAxisLimits
#--------#
