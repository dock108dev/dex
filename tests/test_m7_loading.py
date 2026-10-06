"""Batched identity reads retain conflicts and observe changed catalog state."""

import copy

import pytest
from django.db import connection
from test_b4 import b2 as b2
from test_b4 import b3 as b3
from test_b4 import b4 as b4
from test_b4 import env as env
from test_b4 import package, publish
from test_b4 import snapshot as snapshot

from pokemon_hunter.beta import catalog_imports as cat
from pokemon_hunter.beta import collection as inv
from pokemon_hunter.beta import store


def test_identity_queries_scale_by_batch_and_return_every_card(b4):
    p = cat.validate(package())
    card = p["cards"][0]
    p["cards"] = [dict(card, external_id=f"large-{n}", number=str(n)) for n in range(1001)]
    queries = []

    def record(execute, sql, params, many, context):
        queries.append(sql)
        return execute(sql, params, many, context)

    with connection.execute_wrapper(record):
        _, cards = cat.rows_for(p)
    assert len(cards) == 1001
    assert len({c["id"] for c in cards}) == 1001
    # One game read, one set read and two bounded reads for each of three batches.
    assert len(queries) == 8
    assert all(c["edition"] == card["edition"] for c in cards)


def test_changed_mapping_is_rechecked_on_next_projection(b4):
    p = cat.validate(package())
    original = cat.rows_for(p)
    c = p["cards"][0]
    inv.execute(
        "INSERT INTO external_mappings VALUES(%s,%s,%s,%s)",
        [p["provider"] + ":" + p["language"], "printing", c["external_id"], "conflicting-id"],
    )
    with pytest.raises(ValueError, match="already mapped"):
        cat.rows_for(p)
    inv.execute("DELETE FROM external_mappings WHERE internal_id=%s", ["conflicting-id"])
    assert cat.rows_for(p) == original


def test_null_identity_and_global_id_guards_remain_distinct(b4):
    publish(b4)
    p = cat.validate(package())
    _, before = cat.rows_for(p)
    other = copy.deepcopy(p)
    other["provider"] = "second-provider"
    other["cards"] = [dict(other["cards"][0], edition="distinct-reviewed-edition")]
    cat.rows_for(other)
    other["cards"][0]["edition"] = p["cards"][0]["edition"]
    with pytest.raises(ValueError, match="different source mapping"):
        cat.rows_for(other)
    target = next(
        r["id"] for r in store.rows("SELECT id FROM catalog_sets") if r["id"] != before[0]["set_id"]
    )
    inv.execute("UPDATE printings SET set_id=%s WHERE id=%s", [target, before[0]["id"]])
    with pytest.raises(ValueError, match="cannot be repurposed"):
        cat.rows_for(p)
