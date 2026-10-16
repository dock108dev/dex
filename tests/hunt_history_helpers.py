"""Offline fixture insertion for retained authenticated hunt read regressions.

This test support has no provider adapter. Non-demo history requires explicitly
supplied retained rows; ordinary product requests cannot create these fixtures.
"""

import json
import uuid
from datetime import UTC, datetime

from django.conf import settings

from pokemon_hunter.beta import collection, goal_hunts, parity, store, transactions
from pokemon_hunter.hunt import query_plan
from pokemon_hunter.migration import encode


def demo_rows():
    return json.loads((settings.ROOT / "parity-evidence/demo_hunts.json").read_text())


def seed_historical_hunt(actor, raw, *, rows=None, coverage=None):
    store.verified(actor)
    body = parity.hunt_settings(raw)
    if rows is None:
        if not body.demo:
            raise ValueError("Non-demo history needs explicitly supplied retained fixture rows")
        rows = demo_rows()
    config = parity.evidence("hunt.json", None)
    scope = goal_hunts.snapshot(actor, body.goal_id)
    data = parity.hunt_projection(actor, scope, body)
    plan = [body.query] if body.query else query_plan(data, config, body.pool, body.focus)
    captured = dict(queries_run=0, queries_total=len(plan), offset=body.offset, next_offset=None)
    captured.update(coverage or {})
    captured.update(goal_scope=scope, query_plan=plan)
    batch = str(uuid.uuid4())
    saved = dict(
        created=datetime.now(UTC).isoformat(),
        demo=int(body.demo),
        request=body.model_dump_json(),
        raw=encode(rows),
        coverage=encode(captured),
    )
    result = parity.hunt_response(actor, saved, batch, 1)
    with transactions.atomic():
        collection.execute(
            "INSERT INTO import_batches VALUES(%s,%s,%s,%s,%s)",
            [batch, actor.user_id, batch, "b2-parity-hunt", "saved"],
        )
        collection.execute(
            "INSERT INTO saved_hunts VALUES(%s,%s,1,%s,%s,%s,%s,%s)",
            [
                batch,
                actor.user_id,
                saved["created"],
                saved["demo"],
                saved["request"],
                saved["raw"],
                saved["coverage"],
            ],
        )
    return result


def seed_history(client, raw, **kwargs):
    return seed_historical_hunt(store.principal(int(client.session["_auth_user_id"])), raw, **kwargs)
