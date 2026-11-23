"""Keep early tool-mapping failures out of the long-lived native bindings."""

import json
import subprocess
import time


class StartupProbe:
    def __init__(self, ini):
        self.command = ["betterlinuxcnc-service", "--probe-native"]
        if ini:
            self.command.extend(("--ini", ini))
        self.snapshot = None
        self.retry_at = 0

    def poll(self):
        if time.monotonic() >= self.retry_at:
            # Pre-core LinuxCNC bindings can permanently cache a failed tool mmap.
            # Only the disposable observer touches those bindings until it succeeds.
            try:
                result = subprocess.run(
                    self.command,
                    check=True,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    timeout=2,
                )
            except subprocess.SubprocessError as error:
                raise RuntimeError("本机控制状态探测失败") from error
            self.snapshot = json.loads(result.stdout)
            self.retry_at = time.monotonic() + 1
        return self.snapshot
