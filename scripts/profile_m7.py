"""Bounded private owner-copy response profiling with a common evidence clock."""

import argparse
import cProfile
import hashlib
import json
import os
import re
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from backup_m6 import dbhashes, filemap

CLOCK = datetime(2026, 10, 6, 18, 10, tzinfo=UTC)


class RetainedClock(datetime):
    @classmethod
    def now(cls, tz=None):
        return CLOCK.astimezone(tz) if tz else CLOCK.replace(tzinfo=None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--attempts", type=int, choices=[1, 2, 3], default=2)
    args = ap.parse_args()
    os.umask(0o077)
    args.output.mkdir(parents=True, exist_ok=False)
    from pokemon_hunter.beta.cli import setup

    setup(args.root)
    from django.contrib.auth import get_user_model
    from django.db import connection
    from django.test import RequestFactory
    from django.urls import resolve

    from pokemon_hunter.beta import lookup, offer_filters, packs, store

    actor = store.principal(1)
    user = get_user_model().objects.get(pk=1)
    before = dict(tables=dbhashes(args.root / "inventory.db"), files=filemap(args.root))
    ledger = []
    scenarios = {
        "pokedex": ["/pokedex/", "/api/collection/", "/api/parity/"],
        "coverage": ["/catalog-coverage/", "/api/catalog-coverage/"],
        **{f"scalar-{n}": n for n in (123, 134, 196, 197)},
        "combined": ["/lookup/?targets=123,134,196,197&scope=all"],
    }

    def blocked(*_a, **_kw):
        raise RuntimeError("External acquisition disabled during M7")

    with (
        patch.object(packs, "datetime", RetainedClock),
        patch.object(offer_filters, "datetime", RetainedClock),
        patch("httpx.Client.send", blocked),
        patch("httpx.AsyncClient.send", blocked),
        patch("urllib.request.urlopen", blocked),
        patch("pokemon_hunter.beta.ebay_hunts.search", blocked),
    ):
        for name, routes in scenarios.items():
            for attempt in range(1, args.attempts + 1):
                entry = dict(scenario=name, attempt=attempt, clock=CLOCK.isoformat(), state="charged")
                ledger.append(entry)
                (args.output / "ledger.json").write_text(json.dumps(ledger, indent=2))
                counts = Counter()

                def query(execute, sql, params, many, context):
                    signature = re.sub(r"\s+", " ", sql).strip()
                    counts[signature] += 1
                    return execute(sql, params, many, context)

                profile = cProfile.Profile()
                outputs = []
                start = time.perf_counter()
                with connection.execute_wrapper(query):
                    if attempt == 2:
                        profile.enable()
                    if isinstance(routes, int):
                        outputs.append(
                            json.dumps(
                                lookup.project(actor, {"targets": str(routes)}), sort_keys=True, default=str
                            )
                        )
                    else:
                        for url in routes:
                            request = RequestFactory().get(url)
                            request.user = user
                            response = resolve(request.path).func(request, **resolve(request.path).kwargs)
                            assert response.status_code == 200, (name, response.status_code)
                            body = response.content.decode()
                            if response.get("Content-Type", "").startswith("application/json"):
                                body = json.dumps(json.loads(body), sort_keys=True)
                            else:
                                body = re.sub(
                                    r'(name="csrfmiddlewaretoken" value=")[^"]+', r"\1REDACTED", body
                                )
                            outputs.append(body)
                    if attempt == 2:
                        profile.disable()
                elapsed = time.perf_counter() - start
                raw = json.dumps(outputs, ensure_ascii=False).encode()
                (args.output / f"{name}-{attempt}.json").write_bytes(raw)
                if attempt == 2:
                    profile.dump_stats(args.output / f"{name}.prof")
                entry.update(
                    state="complete",
                    seconds=elapsed,
                    queries=sum(counts.values()),
                    response_sha256=hashlib.sha256(raw).hexdigest(),
                    response_bytes=len(raw),
                    profiled=attempt == 2,
                )
                (args.output / f"{name}-{attempt}-queries.json").write_text(
                    json.dumps(dict(counts), indent=2)
                )
                (args.output / "ledger.json").write_text(json.dumps(ledger, indent=2))
                print(name, attempt, round(elapsed, 3), "seconds", entry["queries"], "queries", flush=True)
    after = dict(tables=dbhashes(args.root / "inventory.db"), files=filemap(args.root))
    assert before == after, "Profiling changed copied owner state"
    (args.output / "preservation.json").write_text(
        json.dumps(dict(before=before, after=after, identical=True), indent=2)
    )


if __name__ == "__main__":
    main()
