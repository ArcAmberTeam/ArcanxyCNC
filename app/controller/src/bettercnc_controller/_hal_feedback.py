"""Read spindle and rotary-table feedback from the machine's existing HAL wiring."""

import importlib
import math
import os


class HalFeedback:
    def __init__(self, clock):
        self._clock = clock
        self._hal = None
        self._component = None
        self._retry_at = 0

    def read(self, model):
        if self._component is None:
            if self._clock() < self._retry_at:
                return None, {}
            self._retry_at = self._clock() + 5
            try:
                self._hal = importlib.import_module("hal")
                component = self._hal.component(f"bettercnc-manual-status-{os.getpid()}")
                component.ready()
                self._component = component
            except Exception:
                # Optional HAL telemetry must never take the NML controller offline.
                return None, {}
        rpm = self._value("spindle.0.speed-in", require_writer=True)
        rpm = None if rpm is None else abs(rpm) * 60
        geometry = {}
        if model in ("xyzac-trt-kins", "xyzbc-trt-kins"):
            offsets = "YZ" if model == "xyzac-trt-kins" else "XZ"
            groups = (("XYZ", "rot-point", "center"), (offsets, "offset", "offset"))
            for axes, suffix, prefix in groups:
                for axis in axes:
                    value = self._value(f"{model}.{axis.lower()}-{suffix}")
                    if value is not None:
                        geometry[prefix + axis] = value
            length = self._value(model + ".tool-offset")
            if length is not None:
                geometry["toolLength"] = length
        return rpm if rpm is not None and math.isfinite(rpm) else None, geometry

    def _value(self, pin, require_writer=False):
        try:
            if require_writer and not self._hal.pin_has_writer(pin):
                return None
            value = self._hal.get_value(pin)
            return value if math.isfinite(value) else None
        except (NameError, TypeError, RuntimeError, self._hal.error):
            return None

    def close(self):
        if self._component is not None:
            self._component.exit()
            self._component = None
