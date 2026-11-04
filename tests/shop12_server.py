"""Ordinary engineering CLI server with a pre-received, non-acquired run."""

import json
import runpy
import sys
from pathlib import Path

from pokemon_hunter.beta import asgi

original = asgi.get_asgi_application


def application():
    app = original()
    from pokemon_hunter.beta import discovery, store

    data = json.loads((root / "engineering-shopping.json").read_text())
    if data.get("exercise_expiry"):
        from datetime import datetime, timedelta

        from pokemon_hunter.beta import listing_check

        class ReviewClock(datetime):
            @classmethod
            def now(cls, tz=None):
                elapsed = 31 if (root / "engineering-next-month").exists() else 0
                return super().now(tz) + timedelta(days=elapsed)

        listing_check.datetime = ReviewClock
    if "lease_seconds" in data:
        discovery.EPHEMERAL_SECONDS = data["lease_seconds"]
    if data.get("measure_compare"):
        from pokemon_hunter.beta import read_diagnostics

        original_emit = read_diagnostics.emit

        def emit(record):
            original_emit(record)
            if record.get("route") == data.get("measure_route", "api/shopping/listing/compare/"):
                with (root / "engineering-compare.jsonl").open("a") as out:
                    print(json.dumps(record), file=out)

        read_diagnostics.emit = emit
    actor = store.principal(data["subject"])
    run = discovery.Run(
        data["run_id"],
        discovery._owner(actor, data["binding"]),
        discovery.Choices(**data.get("choices", dict(query="Venusaur", product_type="mixed_lots"))),
        discovery.goal_hunts.snapshot(actor, data.get("choices", {}).get("goal_id")),
        ["Venusaur"],
        state="complete",
        raws=[data["raw"]],
    )
    discovery._runs[run.id] = run

    def no_transport(*args, **kwargs):
        raise AssertionError("Engineering browser must never acquire provider content")

    discovery.Transport = no_transport
    return app


root = Path(sys.argv[1])
asgi.get_asgi_application = application
runpy.run_path(str(Path(__file__).with_name("ops_server.py")), run_name="__main__")
