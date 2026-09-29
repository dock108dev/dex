"""Durable worker with cooperative SIGTERM/SIGINT and redacted health diagnostics."""

import signal
import threading
import time

from django.conf import settings
from django.db import close_old_connections

from . import scans
from .diagnostics import failure


def run(stop=None):
    stop = stop or threading.Event()
    if threading.current_thread() is threading.main_thread():
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: stop.set())
    while not stop.is_set():
        try:
            close_old_connections()
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
        except Exception as exc:
            # Retry the iteration, never a claimed provider call. Log in both profiles.
            failure("worker_iteration_failed", exc)
            worked = False
        stop.wait(0.2 if worked else 2)
    close_old_connections()
