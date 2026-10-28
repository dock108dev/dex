"""Deterministic full-size/2x SQLite qualification; no customer files or network."""

import json
import math
import os
import platform
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_effective_collection import cx as cx
from test_migration import snapshot as snapshot
from test_ownership_declarations import migrate as declarations_migrate
from test_sealed_catalog import e1 as e1

from pokemon_hunter.beta import catalog_read_build as builds
from pokemon_hunter.beta import catalog_read_queries as reads
from pokemon_hunter.beta import store
from pokemon_hunter.beta.catalog_read_schema import migrate


def seed(cx, count):
    base = store.rows("SELECT * FROM printings WHERE id=%s", [cx["by_legacy"]["a"]["id"]])[0]
    template = store.rows("SELECT * FROM catalog_sets WHERE id=%s", [base["set_id"]])[0]
    with transaction.atomic(), connection.cursor() as c:
        sets = []
        for n in range(187):
            entry = dict(template, id=f"perf-set-{n}", name=f"Engineering Set {n}")
            sets.append(tuple(entry.values()))
        c.executemany(
            "INSERT INTO catalog_sets ("
            + ",".join(template)
            + ") VALUES ("
            + ",".join(["%s"] * len(template))
            + ")",
            sets,
        )
    rows = []
    group_count = round(count * 19011 / 33083)
    for i in range(count - 3):
        group = i % group_count
        row = dict(base)
        row.update(
            id=f"perf-{i}",
            set_id=f"perf-set-{group % 187}",
            collector_number=str(group // 187),
            attributes=json.dumps(
                dict(
                    name=("Flabébé" if group % 17 == 0 else "Pikachu") + f" {group % 251}",
                    pokemon_dex=group % 251 + 1,
                    supertype="Pokémon",
                )
            ),
            provenance="{}",
            edition="first_edition" if i >= group_count else None,
            finish="holo" if i >= group_count else None,
            unresolved_fields="[]",
        )
        if i == 0:
            row["publication_state"] = "archived"
        elif i == 1:
            row["attributes"] = json.dumps(dict(name="Unresolved engineering card", supertype="Pokémon"))
        elif i == 2:
            row["provenance"] = base["provenance"]
        rows.append(tuple(row.values()))
    with transaction.atomic(), connection.cursor() as c:
        c.executemany(
            "INSERT INTO printings (" + ",".join(base) + ") VALUES (" + ",".join(["%s"] * len(base)) + ")",
            rows,
        )


# Measure product work, not branch-coverage tracing. Functional coverage remains
# in test_catalog_reads.py; this test still runs and enforces every budget in CI.
@pytest.mark.no_cover
@pytest.mark.parametrize("count", [33083, 66166])
def test_scale(cx, count):
    declarations_migrate(cx)
    seed(cx, count)
    migrate()
    started = time.perf_counter()
    timings = {}
    build = builds.prepare(timings=timings)
    builds.activate(build)
    preparation_ms = (time.perf_counter() - started) * 1000
    assert reads.unresolved_printings()["total"] > 0
    assert reads.evidence()["total"] > 0
    assert (
        store.rows("SELECT COUNT(*) AS n FROM cr_printings WHERE build=%s AND published=0", [build])[0]["n"]
        > 0
    )
    key = reads.groups()["groups"][0]["id"]
    routes = {
        "empty": "card-groups/",
        "one_character": "card-groups/?q=a",
        "unicode": "card-groups/?q=bé",
        "punctuation": "card-groups/?q=%25",
        "search": "card-groups/?q=pikachu",
        "deep": "card-groups/?sort=number&page=400",
        "max_page": "card-groups/?page_size=100",
        "variant": "card-groups/?finish=holo&edition=first_edition",
        "search_variant": "card-groups/?q=pikachu&finish=holo&edition=first_edition",
        "filters": "card-group-filters/",
        "detail": f"card-groups/{key}/",
        "species": "species/25/card-groups/",
        "pokedex": "pokedex-species/",
        "picker": "catalog/?q=pikachu",
        "picker_empty": "catalog/",
        "search_name": "card-groups/?q=pikachu&sort=name",
        "picker_number": "catalog/?q=pikachu&sort=number",
        "variants": f"card-groups/{key}/variants/",
        "evidence": "evidence/",
        "unresolved": "catalog-unresolved/",
    }
    report = dict(
        printings=count,
        preparation_ms=preparation_ms,
        preparation_phases=timings,
        environment=dict(
            platform=platform.platform(),
            python=platform.python_version(),
            sqlite=connection.Database.sqlite_version,
            load_average=os.getloadavg() if hasattr(os, "getloadavg") else None,
        ),
        catalog_groups=reads.groups()["total"],
        manifest=store.rows("SELECT policy,builder,counts FROM catalog_read_builds WHERE id=%s", [build])[0],
        scenarios={},
    )
    print("prepared", count, preparation_ms, flush=True)
    scenarios = [(name, route, fresh) for fresh in (False, True) for name, route in routes.items()]
    out = Path("reports/perf02")
    out.mkdir(parents=True, exist_ok=True)
    original = store.rows
    failures = []
    client = cx["client"]()
    for name, route, fresh in scenarios:
        name = ("fresh_" if fresh else "warm_") + name
        print("measuring", count, name, flush=True)
        samples, sql_times, query_counts, fetched_counts, sizes, plans, decoded_counts = (
            [],
            [],
            [],
            [],
            [],
            [],
            [],
        )
        for sample in range(20):
            if fresh:
                connection.close()
            connection.queries_log.clear()
            sql_elapsed = 0
            fetched = 0
            decoded = 0
            original_payload = reads.payload

            def measured_payload(*args, **kwargs):
                nonlocal decoded
                decoded += 1
                return original_payload(*args, **kwargs)

            def measured(sql, params=()):
                nonlocal sql_elapsed, fetched
                start = time.perf_counter()
                before = sql_elapsed
                result = original(sql, params)
                sql_elapsed += max(0, (time.perf_counter() - start) * 1000 - (sql_elapsed - before))
                fetched += len(result)
                if sample == 0 and "cr_" in sql:
                    plans.append(original("EXPLAIN QUERY PLAN " + sql, params))
                return result

            def measured_execute(execute, sql, params, many, context):
                nonlocal sql_elapsed
                if sql.startswith("EXPLAIN"):
                    return execute(sql, params, many, context)
                start = time.perf_counter()
                try:
                    return execute(sql, params, many, context)
                finally:
                    sql_elapsed += (time.perf_counter() - start) * 1000

            start = time.perf_counter()
            with (
                connection.execute_wrapper(measured_execute),
                CaptureQueriesContext(connection) as captured,
                patch.object(store, "rows", side_effect=measured),
                patch.object(reads, "payload", side_effect=measured_payload),
            ):
                response = client.get("/api/v2/public/" + route)
                elapsed = (time.perf_counter() - start) * 1000
            assert response.status_code == 200, response.content
            samples.append(elapsed)
            sql_times.append(sql_elapsed)
            query_counts.append(len([q for q in captured if not q["sql"].startswith("EXPLAIN")]))
            fetched_counts.append(fetched)
            decoded_counts.append(decoded)
            sizes.append(len(response.content))

        def p95(values):
            return sorted(values)[math.ceil(len(values) * 0.95) - 1]

        report["scenarios"][name] = dict(
            samples_ms=samples,
            p95_ms=p95(samples),
            worst_ms=max(samples),
            sql_p95_ms=p95(sql_times),
            sql_worst_ms=max(sql_times),
            queries=max(query_counts),
            fetched=max(fetched_counts),
            decoded=max(decoded_counts),
            payload=max(sizes),
            plans=plans,
            connection="fresh" if fresh else "reused",
            sql_samples_ms=sql_times,
            query_samples=query_counts,
            fetched_samples=fetched_counts,
            decoded_samples=decoded_counts,
        )
        (out / f"scale-{count}.json").write_text(json.dumps(report, indent=2))
        budget = 32768 if name.endswith("_filters") else 131072
        if (
            p95(samples) > 180
            or p95(sql_times) > 40
            or max(query_counts) > 20
            or max(sizes) > budget
            or max(decoded_counts) > 100
        ):
            failures.append(name)
    (out / f"scale-{count}.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != "scenarios"}), failures)
    assert preparation_ms <= 30000
    assert not failures
