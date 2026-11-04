"""Read admitted, privately retained versioned releases at both catalog sizes."""

import json
import math
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from price_snapshot_helpers import package, stage
from test_catalog_read_performance import seed
from test_perf04_interactions import candidate
from test_shop17_journey import b2 as b2
from test_shop17_journey import b3 as b3
from test_shop17_journey import b4 as b4
from test_shop17_journey import cx as cx
from test_shop17_journey import e1 as e1
from test_shop17_journey import env as env
from test_shop17_journey import snapshot as snapshot

from pokemon_hunter.beta import collection, price_snapshot_contract, price_snapshots


@pytest.mark.no_cover
@pytest.mark.parametrize("printings,observations", [(33083, 7653), (66166, 15306)])
def test_private_snapshot_read_cost(cx, printings, observations):
    (cx["root"] / "SYNTHETIC_ONLY").touch()
    collection.execute("UPDATE printings SET edition='standard',finish='normal',variant='normal'")
    seed(cx, printings)
    eligible = iter(
        p
        for p in price_snapshots.entries().values()
        if all(p.get(k) for k in ("language", "edition", "finish", "variant"))
    )
    now = datetime.now(UTC)
    version = str(uuid4())
    contracts, records = {}, []
    while len(records) < observations:
        p = next(eligible)
        source = package({"entries": {p["id"]: p}}, permanent=False)
        idx = len(records) // 8000
        key = f"engineering-{idx}"
        if key not in contracts:
            policy = source["contract"]
            policy.update(review_id=key, mappings={})
            contracts[key] = dict(contract=policy, expires_at=(now + timedelta(days=1)).isoformat())
        for row in source["records"][: observations - len(records)]:
            row.update(contract_id=key, captured_at=now.isoformat(), as_of=str(now.date()))
            contracts[key]["contract"]["mappings"][p["id"]] = {
                k: row[k] for k in ("identity", "provider_identity", "source_url", "source_version")
            }
            records.append(row)
    value = dict(
        schema="dex-price-snapshot-v2",
        version=version,
        release_month=now.strftime("%Y-%m"),
        contracts=contracts,
        records=records,
    )
    size = price_snapshot_contract.serialized_bytes(value)
    price_snapshots.activate(stage(value), None, now=now)
    digest = candidate()
    times = []
    for _ in range(20):
        # The seller return executes this read before it can publish a decision.
        start = time.perf_counter()
        with price_snapshots.read_only():
            rows, status = price_snapshots.display_current()
        times.append(round((time.perf_counter() - start) * 1000, 3))
        assert status == "active_snapshot" and len(rows) == observations
    assert digest == candidate()
    result = dict(
        source_sha256=digest,
        printings=printings,
        records=observations,
        contracts=len(contracts),
        package_bytes=size,
        ms=times,
        p95=sorted(times)[math.ceil(len(times) * 0.95) - 1],
        worst=max(times),
    )
    path = Path(f"reports/shop-17-prepared/snapshot-volume-{printings}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2))
    # The snapshot substep alone cannot consume more than the entire local API budget.
    assert result["p95"] <= 180, result
