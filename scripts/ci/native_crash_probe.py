"""Disposable native-crash diagnostic; never an acceptance or performance gate.

Accelerates only this synthetic process's watchdog. The real suite retains its
90-second diagnostic timer. Run under GDB to capture a fault, not a memory dump.
"""

import argparse
import faulthandler
import gc
import json
import os
import sqlite3
import time

from greenlet import getcurrent, greenlet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("sqlite", "greenlet", "primed-sqlite"))
    parser.add_argument("--timer", action="store_true")
    args = parser.parse_args()
    root = getcurrent()
    connection = sqlite3.connect(":memory:")

    def nested(depth, switch):
        if depth:
            return nested(depth - 1, switch)
        if switch:
            root.switch()
        connection.execute(
            "WITH RECURSIVE x(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM x WHERE n<300) SELECT sum(n) FROM x"
        ).fetchall()
        if switch:
            root.switch()
        return None

    def switched():
        task = greenlet(lambda: nested(20, True))
        while not task.dead:
            task.switch()

    if args.mode == "primed-sqlite":
        for _ in range(1000):
            switched()
        gc.collect()
    count = 0
    end = time.monotonic() + 5
    with open(os.devnull, "w") as trace:
        if args.timer:
            faulthandler.dump_traceback_later(0.0001, repeat=True, file=trace)
        try:
            while time.monotonic() < end:
                if args.mode == "greenlet":
                    switched()
                else:
                    nested(20, False)
                count += 1
                if count % 100 == 0:
                    gc.collect()
        finally:
            if args.timer:
                faulthandler.cancel_dump_traceback_later()
            connection.close()
    print(json.dumps({"diagnostic_only": True, "mode": args.mode, "timer": args.timer, "iterations": count}))


if __name__ == "__main__":
    main()
