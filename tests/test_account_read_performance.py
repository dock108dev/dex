"""Full-size and 2x private reads with nontrivial synthetic copies and history."""

import hashlib
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
from test_catalog_read_performance import seed
from test_effective_collection import cx as cx
from test_migration import snapshot as snapshot
from test_ownership_declarations import migrate as declarations_migrate
from test_sealed_catalog import e1 as e1

from pokemon_hunter.beta import account_read_build as accounts
from pokemon_hunter.beta import account_read_schema as schema
from pokemon_hunter.beta import catalog_read_build as catalogs
from pokemon_hunter.beta import store
from pokemon_hunter.beta.catalog_read_schema import migrate


def ownership(cx, count):
    actor = cx["actor"]
    base = store.rows("SELECT * FROM owned_copies WHERE user_id=%s LIMIT 1", [actor.user_id])[0]
    rows = []
    ops = []
    for n in range(count):
        row = dict(
            base,
            id=f"scale-copy-{n}",
            printing_id=f"perf-{n}",
            notes="Engineering-only copy",
            legacy_id=None,
            revision=0,
        )
        rows.append(row)
        # Historical metadata edits, no invented quantity or physical-copy admission.
        for j in range(2):
            ops.append(
                (
                    f"scale-op-{n}-{j}",
                    actor.user_id,
                    "edit",
                    "{}",
                    json.dumps(dict(creates=[], updates=[], deletes=[])),
                    "confirmed",
                    json.dumps([dict(kind="copy", before=row, after=row)]),
                    2 * n + j,
                )
            )
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.executemany(
            "INSERT INTO owned_copies (" + ",".join(base) + ") VALUES (" + ",".join(["%s"] * len(base)) + ")",
            [tuple(r.values()) for r in rows],
        )
        cursor.executemany(
            "INSERT INTO collection_operations(id,user_id,kind,request,plan,state,changes,generation) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
            ops,
        )
        cursor.execute(
            "INSERT OR REPLACE INTO collection_generations VALUES(%s,%s)", [actor.user_id, count * 2]
        )


def p95(values):
    return sorted(values)[math.ceil(len(values) * 0.95) - 1]


@pytest.mark.no_cover
@pytest.mark.parametrize("count,copies", [(33083, 5000), (66166, 10000)])
def test_scale(cx, count, copies):
    declarations_migrate(cx)
    seed(cx, count)
    ownership(cx, copies)
    migrate()
    catalogs.activate(catalogs.prepare())
    schema.migrate()
    started = time.perf_counter()
    accounts.prepare(cx["actor"])
    prep = (time.perf_counter() - started) * 1000
    client = cx["a"]
    key = client.get("/api/v2/my-card-groups/").json()["groups"][0]["id"]
    routes = dict(
        owned="my-card-groups/",
        owned_search="my-card-groups/?q=pikachu",
        owned_short="my-card-groups/?q=a",
        max_owned="my-card-groups/?page_size=100",
        catalog="card-groups/",
        max_page="card-groups/?page_size=100",
        unicode="card-groups/?q=bé",
        search="card-groups/?q=pikachu",
        short="card-groups/?q=a",
        deep="card-groups/?sort=number&page=400",
        variants="card-groups/?finish=holo&edition=first_edition",
        options="card-group-filters/",
        owned_options="card-group-filters/?scope=owned",
        detail=f"card-groups/{key}/",
        copies=f"card-groups/{key}/copies/",
        history=f"card-groups/{key}/history/",
        children=f"card-groups/{key}/variants/",
        artwork=f"card-groups/{key}/artwork/",
        species="pokedex-species/",
        scoped_species="pokedex-species/?finish=holo&year=2000&page_size=100",
        species_options="species-filter-options/",
        scoped_set="pokedex-species/?set=Engineering%20Set%200&finish=holo&year=2000&page_size=100",
        species_finish_options="species-filter-options/?field=finish",
        context="collection-context/",
        duplicates="duplicate-counts/?ids=perf-0,perf-1",
        picker="catalog/",
        picker_search="catalog/?q=pikachu",
        evidence="evidence/",
    )
    report = dict(
        environment=dict(
            platform=platform.platform(),
            python=platform.python_version(),
            sqlite=connection.Database.sqlite_version,
            load_average=os.getloadavg(),
        ),
        printings=count,
        copies=copies,
        history=copies * 2,
        whole_account_preparation_ms=prep,
        scenarios={},
        failures=[],
    )
    h = hashlib.sha256()
    for path in sorted(Path("src/pokemon_hunter/beta").rglob("*.py")):
        h.update(str(path.relative_to("src")).encode())
        h.update(path.read_bytes())
    report["candidate_sha256"] = h.hexdigest()
    from account_read_measurements import incremental

    report["incremental_preparation"] = incremental(cx)
    report["incremental_preparation"]["p95_ms"] = p95(report["incremental_preparation"]["samples_ms"])
    if report["incremental_preparation"]["p95_ms"] > 200:
        report["failures"].append("incremental_preparation")
    out = Path("reports/perf03")
    out.mkdir(parents=True, exist_ok=True)
    original = store.rows
    for fresh in (False, True):
        for name, route in routes.items():
            samples = []
            sql_samples = []
            queries = []
            fetched = []
            sizes = []
            plans = []
            decoded_samples = []
            composition_samples = []
            for sample in range(20):
                if fresh:
                    connection.close()
                connection.queries_log.clear()
                sql_ms = 0
                row_count = 0
                decoded = 0
                composition_ms = 0
                from pokemon_hunter.beta import account_read_queries as reads

                original_payload = reads.payload

                def measured_payload(*args, **kwargs):
                    nonlocal decoded, composition_ms
                    before = time.perf_counter()
                    try:
                        decoded += 1
                        return original_payload(*args, **kwargs)
                    finally:
                        composition_ms += (time.perf_counter() - before) * 1000

                def measured_execute(execute, sql, params, many, context):
                    nonlocal sql_ms
                    if sql.startswith("EXPLAIN"):
                        return execute(sql, params, many, context)
                    before = time.perf_counter()
                    try:
                        return execute(sql, params, many, context)
                    finally:
                        sql_ms += (time.perf_counter() - before) * 1000

                def measured(sql, params=()):
                    nonlocal sql_ms, row_count
                    start = time.perf_counter()
                    before_sql = sql_ms
                    result = original(sql, params)
                    sql_ms += max(0, (time.perf_counter() - start) * 1000 - (sql_ms - before_sql))
                    row_count += len(result)
                    if sample == 0 and ("ar_" in sql or "cr_" in sql):
                        plans.append(original("EXPLAIN QUERY PLAN " + sql, params))
                    return result

                start = time.perf_counter()
                with (
                    connection.execute_wrapper(measured_execute),
                    CaptureQueriesContext(connection) as captured,
                    patch.object(reads, "payload", side_effect=measured_payload),
                    patch.object(store, "rows", side_effect=measured),
                ):
                    response = client.get("/api/v2/" + route)
                samples.append((time.perf_counter() - start) * 1000)
                assert response.status_code == 200, (route, response.content)
                sql_samples.append(sql_ms)
                queries.append(len([q for q in captured if not q["sql"].startswith("EXPLAIN")]))
                fetched.append(row_count)
                sizes.append(len(response.content))
                decoded_samples.append(decoded)
                composition_samples.append(composition_ms)
            scenario = ("fresh_" if fresh else "warm_") + name
            report["scenarios"][scenario] = dict(
                samples_ms=samples,
                p95_ms=p95(samples),
                worst_ms=max(samples),
                sql_samples_ms=sql_samples,
                sql_p95_ms=p95(sql_samples),
                queries=max(queries),
                fetched=max(fetched),
                payload=max(sizes),
                plans=plans,
                decoded_samples=decoded_samples,
                composition_samples_ms=composition_samples,
                composition_p95_ms=p95(composition_samples),
            )
            if (
                p95(samples) > 180
                or p95(sql_samples) > 40
                or max(queries) > 20
                or p95(composition_samples) > 80
                or max(decoded_samples) > 100
                or max(sizes)
                > (
                    32768
                    if name
                    in {"options", "owned_options", "species_options", "species_finish_options", "context"}
                    else 131072
                )
            ):
                report["failures"].append(scenario)
            (out / f"scale-{count}.json").write_text(json.dumps(report, indent=2))
            print(count, scenario, round(p95(samples), 2), max(queries), max(fetched), max(sizes), flush=True)
    assert not report["failures"], report["failures"]
