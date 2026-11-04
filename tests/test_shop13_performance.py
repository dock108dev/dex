"""Full/2x Shopping profiles; no installation, provider transport or private data.

Required fixed-budget failures remain failures; all samples are retained first.
"""

import hashlib
import json
import math
import platform
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

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
from test_sealed_catalog import e1 as e1

from pokemon_hunter.beta import discovery, discovery_listing, read_diagnostics


@pytest.mark.no_cover
@pytest.mark.parametrize("count,copies", [(33083, 5000), (66166, 10000)])
def test_collection_intent_scale(cx, monkeypatch, count, copies):
    from pokemon_hunter.beta import collection, navigation

    seed(cx, count)
    ownership(cx, copies)
    from test_b2 import apply

    from pokemon_hunter.beta import goal_hunts

    goal = apply(
        cx, "goal", dict(name="Engineering frozen species", goal_kind="original151"), client=cx["b"]
    )["changes"][0]["after"]
    prepare_reads(cx)
    client = cx["b"]
    # Local readiness only, with no configuration file or provider request.
    monkeypatch.setattr(discovery.ebay_hunts, "status", lambda: {"enabled": False, "configured": False})
    request = SimpleNamespace(user=cx["second"], session=client.session)
    binding = navigation.binding(request)["navigation_binding"]
    run = discovery.Run(
        str(uuid.uuid4()),
        discovery._owner(cx["member"], binding),
        discovery.Choices(
            query="Venusaur",
            product_type="mixed_lots",
            collection_intent=True,
            intent="missing",
            species=3,
            generation=collection.generation(cx["member"]),
            budget="87.25",
            prefer_vintage=True,
        ),
        None,
        ["Venusaur"],
        state="complete",
        acquired_at=time.monotonic(),
        raws=[
            {
                "itemId": "v1|123456789012|0",
                "title": "Two card lot Base Set 2 Venusaur 18",
                "buyingOptions": ["FIXED_PRICE"],
                "price": {"value": "10", "currency": "USD"},
            }
        ],
    )
    discovery._runs[run.id] = run
    run.raws.append(
        dict(
            itemId="v1|123456789013|0",
            title="Pikachu 18 two card lot",
            buyingOptions=["FIXED_PRICE"],
            price={"value": "10", "currency": "USD"},
        )
    )
    handle = discovery_listing.result_handle(run.id, "v1|123456789012|0")
    frozen = discovery.Run(
        str(uuid.uuid4()),
        run.owner,
        run.choices.model_copy(update=dict(goal_id=goal["id"], goal_version=goal["version"])),
        goal_hunts.snapshot(cx["member"], goal["id"]),
        ["Venusaur"],
        state="complete",
        raws=list(run.raws),
    )
    discovery._runs[frozen.id] = frozen
    frozen_handle = discovery_listing.result_handle(frozen.id, "v1|123456789012|0")
    from pokemon_hunter.beta import listing_check

    opened = listing_check.review(cx["member"], binding)
    listing_check.review(
        cx["member"],
        binding,
        dict(
            currency="USD",
            unknown_contents=None,
            cards=[],
            discovery_origin=dict(run_id=run.id, result_id=handle),
        ),
        opened["lease"],
    )
    routes = {
        "review_restore": "/api/shopping/listing/review/",
        "review_restore_frozen": "/api/shopping/listing/review/",
        "targets_current": "/api/shopping/discovery/targets/?scope=all",
        "targets_kanto": "/api/shopping/discovery/targets/?scope=kanto",
        "targets_frozen": f"/api/shopping/discovery/targets/?goal={goal['id']}&version={goal['version']}",
        "status": f"/api/shopping/discovery/?run_id={run.id}&view=received",
        "status_frozen": f"/api/shopping/discovery/?run_id={frozen.id}&view=received",
        "candidate": f"/api/shopping/listing/candidate/?discovery_run={run.id}&item_id={handle}",
        "candidate_frozen": f"/api/shopping/listing/candidate/?discovery_run={frozen.id}&item_id={frozen_handle}",
        "back_shell": f"/shopping/?run_id={run.id}&q=Venusaur&species=3&intent=missing&budget=87.25&prefer_vintage=1",
        "back_frozen": f"/shopping/?run_id={frozen.id}&species=3&goal={goal['id']}&version={goal['version']}&intent=missing&budget=87.25",
    }

    from pokemon_hunter.beta import collection

    generation = str(collection.generation(cx["member"]))
    member_binding = navigation.binding(SimpleNamespace(user=cx["second"], session=cx["b"].session))[
        "navigation_binding"
    ]
    member_generation = str(collection.generation(cx["member"]))
    source_sha = hashlib.sha256(
        b"".join(
            p.read_bytes()
            for p in sorted(Path("src/pokemon_hunter/beta").rglob("*"))
            if p.is_file() and p.suffix in {".py", ".js", ".css", ".html"}
        )
    ).hexdigest()
    report = dict(
        source_sha256=source_sha,
        printings=count,
        copies=copies,
        python=platform.python_version(),
        scenarios={},
        failures=[],
        provider_requests=0,
        browser_parse_paint=None,
        admission_ms=None,
        note="In-process HTTP; no browser or transport timings inferred.",
    )
    out = Path("reports/shop-13")
    out.mkdir(parents=True, exist_ok=True)
    try:
        for name, route in routes.items():
            if name.startswith("review_restore"):
                origin = frozen if name.endswith("frozen") else run
                result_id = frozen_handle if name.endswith("frozen") else handle
                listing_check.review(
                    cx["member"],
                    binding,
                    dict(
                        currency="USD",
                        unknown_contents=None,
                        cards=[dict(printing_id=cx["by_legacy"]["c"]["id"], quantity=2)],
                        discovery_origin=dict(run_id=origin.id, result_id=result_id),
                    ),
                    opened["lease"],
                )
            samples = []
            for _ in range(20):
                other_account = name == "explorer_missing_available"
                response = (cx["b"] if other_account else client).get(
                    route,
                    HTTP_X_DEX_SHOPPING_BINDING=member_binding if other_account else binding,
                    HTTP_X_DEX_SHOPPING_GENERATION=member_generation if other_account else generation,
                )
                diagnostic = dict(read_diagnostics.recent[-1])
                diagnostic.pop("id", None)
                diagnostic.pop("route", None)
                samples.append(diagnostic)
                (out / f"progress-{count}.json").write_text(
                    json.dumps(
                        dict(scenario=name, samples=len(samples), last_elapsed_ms=diagnostic["elapsed_ms"])
                    )
                )
                if name == "explorer_missing_available" and response.status_code == 200:
                    assert response.json()["results"], "Nonempty missing-card page required"
                if response.status_code != 200:
                    report["failures"].append(f"{name}: HTTP {response.status_code}")
            metrics = {}
            for field in (
                "elapsed_ms",
                "sql_execute_ms",
                "sql_fetch_ms",
                "query_count",
                "fetched_rows",
                "decoded_rows",
                "composition_ms",
                "serialization_ms",
                "payload_bytes",
            ):
                values = [s[field] for s in samples if s.get(field) is not None]
                metrics[field] = (
                    dict(p95=sorted(values)[math.ceil(0.95 * len(values)) - 1], worst=max(values))
                    if values
                    else None
                )
            other = sorted(
                max(
                    0,
                    s["elapsed_ms"]
                    - s["sql_execute_ms"]
                    - s["sql_fetch_ms"]
                    - (s.get("composition_ms") or 0)
                    - (s.get("serialization_ms") or 0),
                )
                for s in samples
            )
            metrics["other_server_ms"] = dict(p95=other[18], worst=max(other))
            sql = sorted(s["sql_execute_ms"] + s["sql_fetch_ms"] for s in samples)
            metrics["sql_combined_ms"] = dict(p95=sql[18], worst=max(sql))
            report["scenarios"][name] = dict(metrics=metrics, samples=samples)
            limits = {
                "elapsed_ms": 180,
                "composition_ms": 80,
                "serialization_ms": 60,
                "other_server_ms": 60,
                "sql_combined_ms": 40,
                "query_count": 20,
                "payload_bytes": 32768 if name == "options" or name.startswith("targets_") else 131072,
            }
            for field, limit in limits.items():
                if metrics[field] is not None and metrics[field]["p95"] > limit:
                    report["failures"].append(f"{name}: {field} exceeds {limit}")
            if metrics["decoded_rows"]["worst"] >= count:
                report["failures"].append(f"{name}: full printing decode")
            (out / f"shopping-{count}.json").write_text(json.dumps(report, indent=2))
    finally:
        discovery._runs.pop(run.id, None)
        final_sha = hashlib.sha256(
            b"".join(
                p.read_bytes()
                for p in sorted(Path("src/pokemon_hunter/beta").rglob("*"))
                if p.is_file() and p.suffix in {".py", ".js", ".css", ".html"}
            )
        ).hexdigest()
        assert final_sha == source_sha, "Source changed during Shopping scale measurement"
    assert not report["failures"], report["failures"]
