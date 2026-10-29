"""Ordinary CLI, actual workers, disposable engineering full-size datasets."""

import concurrent.futures
import json
import platform
import select
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from perf04_helpers import prepare_reads
from test_account_read_performance import ownership
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_catalog_read_performance import seed
from test_effective_collection import cx as cx
from test_migration import snapshot as snapshot
from test_perf04_interactions import candidate
from test_sealed_catalog import e1 as e1

pytestmark = [pytest.mark.no_cover, pytest.mark.allow_hosts(["127.0.0.1"])]


@pytest.mark.parametrize("scale,copies", [(33083, 5000), (66166, 10000)])
def test_ordinary_runtime(cx, scale, copies):
    from django.conf import settings
    from django.db import connection

    from pokemon_hunter.beta import collection, store

    seed(cx, scale)
    ownership(cx, copies)
    before = time.perf_counter()
    prepare_reads(cx)
    prep_ms = (time.perf_counter() - before) * 1000
    for marker in ("B2_ISOLATED", "B3_ISOLATED", "B4_ISOLATED"):
        (cx["root"] / marker).write_text("Engineering only\n")
    (cx["root"] / "secret.key").write_text(settings.SECRET_KEY)
    digest = candidate()
    authority = store.rows("SELECT SUM(revision) AS revisions,COUNT(*) AS n FROM owned_copies")
    report = dict(
        candidate=digest,
        platform=platform.platform(),
        python=platform.python_version(),
        sqlite=connection.Database.sqlite_version,
        scale=scale,
        copies=copies,
        combined_preparation_ms=prep_ms,
        startup=[],
        requests=[],
        customer_data=False,
        cache="warm OS cache from preparation; request connections close normally",
        failures=[],
    )
    out = Path("reports/ops-readiness")
    out.mkdir(parents=True, exist_ok=True)
    process = None

    def start():
        nonlocal process
        begun = time.perf_counter()
        process = subprocess.Popen(
            [sys.executable, "tests/ops_server.py", str(cx["root"]), "0"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert select.select([process.stdout], [], [], 10)[0], "Startup did not report a listener"
        line = process.stdout.readline().strip()
        assert line.isdigit(), "Runtime failed before listening"
        base = "http://127.0.0.1:" + line
        with httpx.Client(base_url=base, timeout=2) as client:
            live = client.get("/livez/")
            ready = client.get("/readyz/")
            elapsed = (time.perf_counter() - begun) * 1000
            report["startup"].append(
                dict(ms=elapsed, status=ready.status_code, category=ready.json()["category"])
            )
            assert live.status_code == 200
        return base

    def stop():
        process.terminate()
        process.wait(timeout=12)
        assert process.returncode in (0, -15)  # uvicorn re-raises SIGTERM after orderly shutdown
        profile = cx["root"] / "engineering-query-timings.json"
        if profile.exists():
            report.setdefault("query_profiles", []).append(json.loads(profile.read_text()))
        records = [
            json.loads(line) for line in (cx["root"] / "diagnostics/reads.jsonl").read_text().splitlines()
        ]
        assert any(r.get("event") == "shutdown" and r.get("ready") for r in records)
        errors = process.stderr.read()
        assert not errors, "Runtime emitted unexpected errors (not included for privacy)"

    try:
        for _ in range(3):
            base = start()
            assert report["startup"][-1]["status"] == 200
            if report["startup"][-1]["ms"] > 2000:
                report["failures"].append("startup >2000ms")
            if len(report["startup"]) == 1:
                cookies = {k: v.value for k, v in cx["a"].cookies.items()}

                def read(n):
                    with httpx.Client(base_url=base, cookies=cookies, timeout=5) as client:
                        started = time.perf_counter()
                        response = client.get("/api/v2/my-card-groups/?q=pikachu")
                        return dict(
                            ms=(time.perf_counter() - started) * 1000,
                            status=response.status_code,
                            timing=response.headers.get("server-timing"),
                            diagnostic=response.headers.get("x-dex-diagnostic-id"),
                        )

                for concurrency in (1, 4):
                    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
                        observations = list(pool.map(read, range(20)))
                    p95 = sorted(r["ms"] for r in observations)[18]
                    report["requests"].append(dict(concurrency=concurrency, samples=observations, p95_ms=p95))
                    if p95 > 180:
                        report["failures"].append(f"concurrency {concurrency} API p95 >180ms")
                    assert all(r["status"] == 200 for r in observations)
                    records = {
                        r["id"]: r
                        for r in (
                            json.loads(line)
                            for line in (cx["root"] / "diagnostics/reads.jsonl").read_text().splitlines()
                        )
                        if "id" in r
                    }
                    phases = [records[r["diagnostic"]] for r in observations]
                    sql_p95 = sorted(r["sql_execute_ms"] + r["sql_fetch_ms"] for r in phases)[18]
                    report["requests"][-1].update(phases=phases, sql_p95_ms=sql_p95)
                    if sql_p95 > 40 or max(r["query_count"] for r in phases) > 20:
                        report["failures"].append(f"concurrency {concurrency} SQL budget")

                rss = subprocess.check_output(["ps", "-o", "rss=", "-p", str(process.pid)], text=True)
                report["rss_kib_after_reads"] = int(rss.strip())
            stop()
        collection.execute("UPDATE catalog_read_builds SET status='preparing'")
        start()
        assert report["startup"][-1]["category"] == "preparation_interrupted"
        assert report["startup"][-1]["ms"] <= 2000
        stop()
        assert store.rows("SELECT SUM(revision) AS revisions,COUNT(*) AS n FROM owned_copies") == authority
        assert candidate() == digest
        assert not report["failures"], report["failures"]
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait(timeout=12)
        (out / f"runtime-{scale}.json").write_text(json.dumps(report, indent=2))
