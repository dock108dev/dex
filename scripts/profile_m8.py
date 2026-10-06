"""Exactly one private profile per initial-data route on a copied boundary."""

import argparse
import cProfile
import hashlib
import json
import os
import time
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from backup_m6 import dbhashes, filemap


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert "m8-resume-20261006" in str(args.root.resolve())
    os.umask(0o077)
    args.output.mkdir(parents=True, exist_ok=False)
    from pokemon_hunter.beta.cli import setup

    setup(args.root)
    from django.contrib.auth import get_user_model
    from django.db import connection
    from django.test import RequestFactory
    from django.urls import resolve

    before = dict(tables=dbhashes(args.root / "inventory.db"), files=filemap(args.root))
    user = get_user_model().objects.get(pk=1)
    ledger = []

    def blocked(*_args, **_kwargs):
        raise RuntimeError("External acquisition disabled")

    with (
        patch("httpx.Client.send", blocked),
        patch("httpx.AsyncClient.send", blocked),
        patch("urllib.request.urlopen", blocked),
        patch("pokemon_hunter.beta.ebay_hunts.search", blocked),
    ):
        for name in ["collection", "parity"]:
            path = f"/api/{name}/"
            entry = dict(path=path, state="charged", profiled=True)
            ledger.append(entry)
            (args.output / "ledger.json").write_text(json.dumps(ledger, indent=2))
            counts = Counter()

            def query(execute, sql, params, many, context):
                counts[sql] += 1
                return execute(sql, params, many, context)

            request = RequestFactory().get(path)
            request.user = user
            profile = cProfile.Profile()
            start = time.perf_counter()
            with connection.execute_wrapper(query), profile:
                response = resolve(path).func(request)
            body = response.content
            profile.dump_stats(args.output / f"{name}.prof")
            (args.output / f"{name}-response.json").write_bytes(body)
            entry.update(
                state="complete",
                status=response.status_code,
                seconds=time.perf_counter() - start,
                queries=sum(counts.values()),
                bytes=len(body),
                sha256=hashlib.sha256(body).hexdigest(),
            )
            (args.output / f"{name}-queries.json").write_text(json.dumps(dict(counts), indent=2))
            (args.output / "ledger.json").write_text(json.dumps(ledger, indent=2))
            print(name, entry["seconds"], entry["queries"], flush=True)
    after = dict(tables=dbhashes(args.root / "inventory.db"), files=filemap(args.root))
    assert before == after
    (args.output / "preservation.json").write_text(json.dumps(dict(identical=True, **after), indent=2))


if __name__ == "__main__":
    main()
