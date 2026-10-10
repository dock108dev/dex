"""Policy projections and additive erasure, on at most twelve fixture printings."""

import csv
import io
from pathlib import Path

from test_b1 import env as env
from test_b2 import apply
from test_b2 import b2 as b2
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_broad_goals import special
from test_collection_goals import create, seed
from test_migration import snapshot as snapshot
from test_sealed_catalog import e1 as e1
from test_shopping import NOW, inputs

from pokemon_hunter.beta import collection, deployment, shopping, store


def test_declaration_resolved_copy_exact_and_duplicate_quantities(e1, monkeypatch):
    monkeypatch.setattr(shopping, "sources", lambda: ([], {}))
    special(e1)
    entries = collection.catalog(e1["actor"])
    assert len(store.rows("SELECT id FROM printings")) <= 12
    p = next(p for p in entries if p["attributes"].get("pokemon_dex") == 1)
    source = list(
        csv.reader(io.StringIO((Path(__file__).parent / "fixtures/synthetic-collection.csv").read_text()))
    )
    row = next(r for r in source[1:] if r[0] == "1")
    row[2], row[3] = "Owned", "✓ Bulbasaur #13 (Rare)"
    output = io.StringIO(newline="")
    csv.writer(output).writerows(source)
    _, src = seed(e1, output.getvalue())
    declaration = create(e1, src)
    raw = inputs(dict(catalog=[p]))
    raw["value_references"] = raw["value_references"][:1]
    raw["selected_cards"][0].update(quantity=3, completion_confirmed=True)
    raw.update(goal_id=declaration["id"], goal_version=declaration["version"])
    declared = shopping.prepare(e1["actor"], raw, now=NOW)
    assert declared["result"]["full_selected_total"] == "42.00"
    assert declared["result"]["goal"]["full_distinct_gain"] == 0
    assert declared["result"]["goal"]["full_useful_total"] == "0.00"
    assert not collection.copies(e1["actor"]) or all(
        c["printing_id"] != p["id"] for c in collection.copies(e1["actor"])
    )
    # Deliberately resolved synthetic metadata for copy-policy qualification.
    collection.execute("UPDATE printings SET unresolved_fields='[]' WHERE id=%s", [p["id"]])
    apply(e1, "goal", dict(name="Resolved-copy synthetic goal", goal_kind="original151"))
    resolved = next(g for g in collection.goals(e1["actor"]) if g["kind"] == "original151")
    raw.update(goal_id=resolved["id"], goal_version=resolved["version"])
    result = shopping.prepare(e1["actor"], raw, now=NOW)["result"]
    assert result["goal"]["full_distinct_gain"] == 1
    assert result["goal"]["full_useful_total"] == "14.00"
    assert result["goal"]["useful_quantities"] == {"0": 1}
    apply(
        e1,
        "goal",
        dict(name="Exact synthetic goal", goal_kind="custom", policy="exact", printing_ids=[p["id"]]),
    )
    exact = next(g for g in collection.goals(e1["actor"]) if g["name"] == "Exact synthetic goal")
    raw.update(goal_id=exact["id"], goal_version=exact["version"])
    assert shopping.prepare(e1["actor"], raw, now=NOW)["result"]["goal"]["full_distinct_gain"] == 1
    for _ in range(2):
        apply(e1, "add", dict(printing_id=p["id"], duplicate_policy="allow"))
    result = shopping.prepare(e1["actor"], raw, now=NOW)["result"]
    assert result["goal"]["full_distinct_gain"] == 0 and result["full_selected_total"] == "42.00"
    assert len(collection.copies(e1["actor"])) >= 2


def test_additive_saved_shopping_obeys_existing_erasure(b4):
    from pokemon_hunter.beta import support

    deployment.initialize()
    shopping.initialize()
    protected = collection.export_data(b4["actor"])
    # Use the supported service to create valid history before testing account erasure.
    raw = inputs(dict(catalog=[]))
    raw["value_references"] = []
    shopping.save(b4["member"], raw, "Synthetic private research", now=NOW)
    assert shopping.listing(b4["member"])
    support.delete_account(b4["member"])
    assert not store.rows("SELECT * FROM saved_shopping_comparisons WHERE user_id=%s", [b4["member"].user_id])
    assert collection.export_data(b4["actor"]) == protected
