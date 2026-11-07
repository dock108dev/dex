"""Controlled provider at the transport boundary of a disposable ordinary CLI."""

import json
import runpy
import sys
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from pokemon_hunter.beta import asgi

root = Path(sys.argv[1])
assert (root / "SYNTHETIC_ONLY").is_file()
original = asgi.get_asgi_application


def application():
    app = original()
    from pokemon_hunter.beta import discovery, lot_hunt, price_snapshot_sources, read_diagnostics

    class SnapshotClock(datetime):
        @classmethod
        def now(cls, tz=None):
            offset = 2 if (root / "advance-snapshot-clock").exists() else 0
            return super().now(tz) + timedelta(days=offset)

    price_snapshot_sources.datetime = SnapshotClock

    raw = json.loads((root / "engineering-offer.json").read_text())

    class Controlled:
        async def request(self, stage, **kwargs):
            with (root / "controlled-calls").open("a") as log:
                print(stage, file=log)
            if stage == "oauth":
                value = {"access_token": "engineering", "expires_in": 1800, "token_type": "Bearer"}
            elif stage == "detail":
                value = raw
            else:
                assert stage == "browse"
                page = kwargs["search_options"]["lot_hunt"]
                rows = [raw] if page.lane == "auction" else []
                value = {"itemSummaries": rows, "total": len(rows)}
            if kwargs.get("byte_budget") is not None:
                kwargs["byte_budget"].take(len(json.dumps(value).encode()))
            return value

        async def close(self):
            pass

    discovery.Transport = Controlled
    lot_hunt.Transport = Controlled
    guard = lot_hunt._guard

    def observed_guard(*args, **kwargs):
        try:
            return guard(*args, **kwargs)
        except Exception as error:
            frames = [
                dict(file=Path(frame.filename).name, line=frame.lineno, function=frame.name)
                for frame in traceback.extract_tb(error.__traceback__)
            ]
            with (root / "guard-failures.jsonl").open("a") as log:
                print(json.dumps(dict(type=type(error).__name__, frames=frames)), file=log)
            raise

    lot_hunt._guard = observed_guard
    discovery.ebay_hunts.configuration = lambda: (
        SimpleNamespace(environment="production"),
        dict(EBAY_CLIENT_ID="engineering", EBAY_CLIENT_SECRET="engineering"),
    )
    admission = discovery.review_candidate

    def counted(*args, **kwargs):
        record = read_diagnostics.current.get()
        if record is not None:
            with (root / "assessment-admissions.jsonl").open("a") as log:
                print(json.dumps(dict(id=record["id"])), file=log)
        return admission(*args, **kwargs)

    discovery.review_candidate = counted
    emit = read_diagnostics.emit

    def record(row):
        emit(row)
        if row.get("event") == "request":
            with (root / "journey-requests.jsonl").open("a") as log:
                print(json.dumps(row), file=log)

    read_diagnostics.emit = record
    return app


asgi.get_asgi_application = application
runpy.run_path(str(Path(__file__).with_name("ops_server.py")), run_name="__main__")
