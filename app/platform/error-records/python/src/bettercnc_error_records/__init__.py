"""Public nonblocking error client; MySQL, classification and export live in Rust."""

import json
import math
import socket
import sys
import threading

__all__ = ["report", "install_exception_hooks"]
_SOCKET = "/run/betterlinuxcnc-error-records/events.sock"


def report(source, code, message, context=None):
    """Send bounded diagnostics without waiting for a database or collector reply."""
    try:
        bounded_context = {}
        for key, value in (context or {}).items():
            if isinstance(value, float) and not math.isfinite(value):
                value = str(value)
            if isinstance(value, str):
                value = value[:128]
            if value is None or isinstance(value, (str, int, float, bool)):
                bounded_context[str(key)[:64]] = value
        data = json.dumps(
            {
                "schema_version": 1,
                "source": str(source)[:64],
                "code": str(code)[:96],
                "message": str(message)[:4096],
                "context": bounded_context,
            },
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
        if len(data) <= 16384:
            with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as channel:
                channel.setblocking(False)
                channel.sendto(data, _SOCKET)
    except (OSError, TypeError, ValueError):
        # Diagnostics must never suppress the original error or delay motion control.
        pass


def install_exception_hooks(source):
    """Retain Python's normal traceback while recording uncaught process/thread errors."""
    previous = sys.excepthook
    previous_thread = threading.excepthook

    def process_error(kind, value, trace):
        report(source, "uncaught_exception", f"{kind.__name__}: {value}")
        previous(kind, value, trace)

    def thread_error(args):
        report(
            source,
            "uncaught_thread_exception",
            f"{args.exc_type.__name__}: {args.exc_value}",
        )
        previous_thread(args)

    sys.excepthook = process_error
    threading.excepthook = thread_error
