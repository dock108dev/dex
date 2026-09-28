"""Durable worker with cooperative SIGTERM/SIGINT and redacted health diagnostics."""

import signal
import threading
import time

from django.conf import settings
from django.db import close_old_connections

from . import scans


def run(stop=None):
    stop = stop or threading.Event()
    if threading.current_thread() is threading.main_thread():
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: stop.set())
    while not stop.is_set():
        close_old_connections()
        try:
            if getattr(settings, "STAGING", False):
                from .collection import execute
                from .support import cleanup

                cleanup()
                execute(
                    "INSERT INTO beta_operations VALUES('worker_heartbeat',%s) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    [str(time.time())],
                )
            else:
                scans.cleanup()
            worked = scans.process_one(stop)
        except Exception:
            # Fixed event name only; never log exception text or request content.
            if getattr(settings, "STAGING", False):
                print("worker_iteration_failed", flush=True)
            worked = False
        stop.wait(0.2 if worked else 2)
    close_old_connections()
