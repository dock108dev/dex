"""Legacy batching preserves reconciliation evidence and fresh identity guards."""

import json

import pytest
from django.db import connection
from test_b4 import b2 as b2
from test_b4 import b3 as b3
from test_b4 import b4 as b4
from test_b4 import env as env
from test_b5_followup import snapshot as snapshot

from pokemon_hunter.beta import catalog_imports as cat
from pokemon_hunter.beta import catalog_reconcile as legacy
from pokemon_hunter.beta import collection as inv
from pokemon_hunter.beta import store


def package():
    return cat.validate(json.loads((legacy.PACKAGES / "base_set.json").read_text()))


def test_legacy_batch_retains_scalar_identity_and_prior_nullable_fields(b4):
    p = package()
    sid = legacy.set_id(p)
    expected = [legacy.printing(p, c, sid) for c in p["cards"]]
    _, rows = cat.rows_for(p)
    assert [r["id"] for r in rows] == [pid for pid, _ in expected]
    for row, (_, prior) in zip(rows, expected, strict=True):
        assert prior is not None
        assert all(row[k] == prior[k] for k in ("edition", "finish", "variant", "unresolved_fields"))


def test_legacy_queries_scale_by_batch_without_suppressing_cards(b4):
    p = package()
    c = p["cards"][0]
    p["cards"] = [
        dict(c, external_id=f"m8-{n}", legacy_id=f"m8-{n}", number=str(10000 + n)) for n in range(1001)
    ]
    queries = []

    def record(execute, sql, params, many, context):
        queries.append(sql)
        return execute(sql, params, many, context)

    with connection.execute_wrapper(record):
        _, rows = cat.rows_for(p)
    assert len(rows) == len({r["id"] for r in rows}) == 1001
    assert len(queries) <= 16


@pytest.mark.parametrize("fault", ["missing", "other-set", "wrong-legacy", "ambiguous"])
def test_changed_legacy_evidence_is_rechecked_and_conflicts_rejected(b4, fault):
    p = package()
    before = cat.rows_for(p)
    card = p["cards"][0]
    pid = before[1][0]["id"]
    if fault == "missing":
        inv.execute(
            "UPDATE external_mappings SET internal_id='m8-missing' WHERE provider='legacy' AND external_id IN (%s,%s)",
            [card["legacy_id"] + ":unresolved", card["legacy_id"] + ":first_edition"],
        )
    elif fault == "other-set":
        other = next(r["id"] for r in store.rows("SELECT id FROM catalog_sets") if r["id"] != before[0]["id"])
        inv.execute("UPDATE printings SET set_id=%s WHERE id=%s", [other, pid])
    elif fault == "wrong-legacy":
        inv.execute("UPDATE printings SET provenance='{}' WHERE id=%s", [pid])
    else:
        row = store.rows("SELECT * FROM printings WHERE id=%s", [pid])[0]
        cat.write("printings", dict(row, id="m8-ambiguous", edition="different"))
    with pytest.raises(ValueError, match="Ambiguous|Legacy identity"):
        cat.rows_for(p)
