"""Current species and retained goal choices on disposable engineering accounts."""

from unittest.mock import patch

import pytest
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_collection_goals import create
from test_effective_collection import cx as cx
from test_effective_collection import select
from test_lot_calculator import post, request
from test_migration import snapshot as snapshot
from test_sealed_catalog import e1 as e1
from test_shopping import NOW

from pokemon_hunter.beta import collection, effective_collection, shopping, species_projection
from pokemon_hunter.beta import lot_calculator as lot


def test_missing_controls_and_current_scope_work_without_saved_goals(cx):
    assert collection.goals(cx["actor"], include_updates=False) == []
    before = collection.export_data(cx["actor"])
    page = cx["a"].get("/shopping/calculator/")
    assert page.status_code == 200
    html = page.content.decode()
    assert 'id="show-missing"' in html and 'id="show-all"' in html
    assert '<option value="">Current collection · Original 151</option>' in html
    assert cx["a"].get("/api/shopping/lot-catalog/", {"missing": "species"}).status_code == 200
    assert collection.export_data(cx["actor"]) == before


def test_current_missing_matches_pokedex_and_preserves_explicit_frozen_goal(cx):
    _, source = select(cx, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}})
    goal = create(cx, source)
    select(cx, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}, 3: {"Base Set 2": "✓"}})
    before = collection.export_data(cx["actor"])
    frozen = collection.one(cx["actor"], "goal", goal["id"])
    with patch("requests.sessions.Session.request", side_effect=AssertionError("No provider calls")):
        response = cx["a"].get("/api/shopping/lot-catalog/", {"missing": "species"})
        expected = species_projection.project(cx["actor"], {"region": "kanto", "owned": "missing"})
        retained = cx["a"].get("/api/shopping/lot-catalog/", {"goal": goal["id"]}).json()
    assert response.status_code == 200, response.content
    result = response.json()
    assert result["context"]["kind"] == "missing"
    assert result["context"]["label"] == "Current collection · Original 151"
    assert result["context"]["goal_version"] is None
    assert {item["id"] for item in result["missing_items"]} == {
        f"#{row['dex']:03} {row['name']}" for row in expected["species"]
    }
    assert "#003 Venusaur" not in {item["id"] for item in result["missing_items"]}
    assert "#003 Venusaur" in {item["id"] for item in retained["missing_items"]}
    assert any(item["available"] == 0 for item in result["missing_items"])
    assert collection.one(cx["actor"], "goal", goal["id"]) == frozen
    assert collection.export_data(cx["actor"]) == before


def test_current_missing_modern_choice_locks_restores_and_compares_without_widening_all(cx, monkeypatch):
    select(cx)
    collection.execute("UPDATE catalog_sets SET name='Modern engineering set'")
    monkeypatch.setattr(lot, "retained_records", lambda: [])
    shopping.initialize()
    before = collection.export_data(cx["actor"])
    assert lot.browse(cx["actor"]) == []
    result = (
        cx["a"]
        .get("/api/shopping/lot-catalog/", {"missing": "species", "missing_item": "#003 Venusaur"})
        .json()
    )
    assert [p["id"] for p in result["cards"]] == [cx["by_legacy"]["c"]["id"]]
    first = cx["a"].get("/api/shopping/lot-catalog/", {"missing": "species", "pick_first": "1"}).json()
    assert first["selected_missing_item"] == "#001 Bulbasaur" and first["total"] == 1
    printing = result["cards"][0]
    assert (
        post(
            cx, "/api/shopping/wants/", {"wants": [{"printing_id": printing["id"], "quantity": 1}]}
        ).status_code
        == 200
    )
    restored = cx["a"].get("/api/shopping/lot-catalog/", {"restore": printing["id"]}).json()
    wanted = cx["a"].get("/api/shopping/lot-catalog/", {"wanted": "1"}).json()
    assert [p["id"] for p in restored["cards"]] == [printing["id"]]
    assert [p["id"] for p in wanted["cards"]] == [printing["id"]]
    raw = request(cx)
    raw["cards"] = [
        {"printing_id": printing["id"], "quantity": 1, "values": {g: {"mode": "none"} for g in lot.COLUMNS}}
    ]
    assert all(
        scenario["result"]["coverage"]["priced_units"] == 0
        for scenario in lot.prepare(cx["actor"], raw, NOW)["scenarios"].values()
    )
    assert collection.export_data(cx["actor"]) == before


@pytest.mark.parametrize(
    "extra",
    [
        {"missing": "exact"},
        {"goal": "foreign"},
        {"version": "0" * 64},
        {"species": "3"},
        {"group": "dg1-" + "0" * 64},
        {"child": "foreign"},
        {"missing_item": "#999 Invented"},
        {"account_id": "foreign"},
    ],
)
def test_current_missing_rejects_ambiguous_or_forged_scope_without_changes(cx, extra):
    before = collection.export_data(cx["actor"])
    response = cx["a"].get("/api/shopping/lot-catalog/", {"missing": "species", **extra})
    assert response.status_code == 400, response.content
    assert collection.export_data(cx["actor"]) == before


def test_current_missing_is_account_scoped_and_rejects_stale_collection(cx):
    select(cx, {3: {"Base Set 2": "✓"}})
    before = collection.export_data(cx["actor"])
    owner = cx["a"].get("/api/shopping/lot-catalog/", {"missing": "species"}).json()
    other = cx["b"].get("/api/shopping/lot-catalog/", {"missing": "species"}).json()
    assert "#003 Venusaur" not in {item["id"] for item in owner["missing_items"]}
    assert "#003 Venusaur" in {item["id"] for item in other["missing_items"]}
    assert other["context"]["account_id"] == cx["member"].user_id
    stale = collection.generation(cx["actor"]) - 1
    assert (
        cx["a"]
        .get("/api/shopping/lot-catalog/", {"missing": "species", "generation": str(stale)})
        .status_code
        == 409
    )
    assert (
        cx["a"]
        .get("/api/shopping/lot-catalog/", {"missing": "species", "missing_item": "#003 Venusaur"})
        .status_code
        == 400
    )
    assert cx["client"]().get("/api/shopping/lot-catalog/", {"missing": "species"}).status_code in {302, 403}
    assert collection.export_data(cx["actor"]) == before


@pytest.mark.parametrize("field,value", [("user_id", "foreign"), ("generation", -1)])
def test_current_missing_rejects_mismatched_authoritative_projection(cx, field, value):
    projected = effective_collection.project(cx["actor"])
    with patch.object(effective_collection, "project", return_value={**projected, field: value}):
        with pytest.raises(collection.Conflict):
            lot.current_missing_choices(cx["actor"])
