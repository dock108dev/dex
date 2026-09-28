"""Local background worker; durable claims survive web refresh and worker restarts."""

import time

from django.db import close_old_connections

from . import scans


def run():
    while True:
        close_old_connections()
        try:
            scans.cleanup()
            worked = scans.process_one()
        except Exception:
            # Never log private images, credentials or provider response bodies.
            worked = False
        time.sleep(0.2 if worked else 2)
