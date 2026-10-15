"""Scoped completion and real boundary serialization on isolated engineering state."""

import json
from unittest.mock import patch
from urllib.parse import urlencode

import pytest
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_collection_goals import create
from test_effective_collection import cx as cx
from test_effective_collection import select
from test_migration import snapshot as snapshot
from test_sealed_catalog import e1 as e1

from pokemon_hunter.beta import collection, species_projection, species_scope


def criteria(**kw):
    return {**species_projection.filters({}), **kw}


def release(start, end=None):
    return dict(start=start, end=end or start)


@pytest.mark.parametrize(
    ("evidence", "selected", "expected"),
    [
        (release("1999-12-31"), {"released": "pre-2000"}, True),
        (release("2000-01-01"), {"released": "pre-2000"}, False),
        (release("2000-01-01"), {"released": "2000-onward"}, True),
        (release("1999-12-01", "2000-01-01"), {"released": "pre-2000"}, None),
        (release("1999-01-01", "2000-12-31"), {"released": '["pre-2000","2000-onward"]'}, True),
        (release("2000-01-01", "2000-12-31"), {"year": "2000"}, True),
        (release("2000-01-01", "2000-12-31"), {"date_from": "2000-02-01"}, None),
        (release("2000-02-01"), {"date_from": "2000-02-01", "date_to": "2000-02-01"}, True),
        (None, {"released": "pre-2000", "gaps": "true"}, None),
        (None, {"released": "Unknown"}, True),
        (None, {"released": "Unknown", "date_to": "1999-12-31"}, None),
        (None, {}, True),
    ],
)
def test_date_precision_boundaries_unknown_and_unrestricted(evidence, selected, expected):
    assert species_scope.date_match(evidence, selected) is expected


def test_intervals_do_not_invent_exact_dates():
    assert species_scope.interval("2000") == ("2000-01-01", "2000-12-31")
    assert species_scope.interval("2000-02") == ("2000-02-01", "2000-02-29")
    assert species_scope.interval("2000-02-30") is None


@pytest.mark.parametrize(
    "raw",
    [
        {"set": '["a", 2]'},
        {"set": "["},
        {"set": '["a"]' * 1000},
        {"set": json.dumps(list(map(str, range(9))))},
        {"set": '["a\\n"]'},
        {"released": "Jurassic"},
        {"year": "1995"},
        {"date_from": "2000-02-30"},
        {"date_from": "2001-01-01", "date_to": "2000-01-01"},
        {"finish": ["normal"]},
        {"not_supported": "x"},
    ],
)
def test_invalid_scope_is_rejected(raw):
    with pytest.raises((ValueError, TypeError)):
        species_projection.filters(raw)


def test_multivalue_and_navigation_contract(cx):
    from pokemon_hunter.beta.card_group_views import return_context

    raw = {
        "set": '["Jungle","Base Set","Jungle"]',
        "finish": "normal",
        "released": "pre-2000",
        "region": "kanto",
    }
    parsed = species_projection.filters(raw)
    assert parsed["set"] == '["Base Set","Jungle"]'
    destination = "/pokedex/?" + urlencode({**raw, "scroll": "91", "focus": "2"})
    detail = "/pokedex/2/?" + urlencode({"return": destination})
    card = "/card-groups/dg1-" + "a" * 64 + "/?" + urlencode({"return": detail, "child": "exact-child"})
    assert return_context(destination) == destination
    assert return_context(detail) == detail
    assert return_context(card) == card
    assert cx["a"].get("/pokedex/?" + urlencode(raw)).status_code == 200
    answer = cx["a"].get("/api/pokedex-species/?" + urlencode(raw))
    assert answer.status_code == 200 and answer.json()["filters"]["set"] == parsed["set"]
    assert cx["a"].get("/api/pokedex-species/?set=a&set=b").status_code == 400
    assert cx["a"].get("/pokedex/2/?set=a").status_code == 400
    assert cx["a"].get("/api/pokedex-species/?released=Jurassic").status_code == 400
    assert cx["client"]().get("/pokedex/?set=%5B%22one%22%2C%22two%22%5D").status_code == 400


def test_same_owned_card_conjunction_and_or_sets():
    a = dict(set="base", finish="normal", release=release("1999-12-31"), card="Charizard 4")
    b = dict(set="modern", finish="holo", release=release("2020-01-01"), card="Charizard 9")
    selected = criteria(set='["base","jungle"]', finish="holo")
    assert species_scope.classify([a, b], selected) == "outside"
    assert species_scope.classify([{**a, "finish": "holo"}, b], selected) == "collected"
    assert species_scope.classify([{**a, "set": "jungle", "finish": "holo"}], selected) == "collected"


def test_broad_evidence_and_unknown_quantity_do_not_infer_variant():
    owned = dict(
        name="Charizard",
        number="4",
        set_name="Base Set",
        printing_ids=["a", "b"],
        exact_printing_owned_ids=[],
        established_total_quantity=None,
    )
    indexed = {
        k: dict(
            set="base",
            type="Pokémon",
            rarity="Rare",
            era="base",
            release=release("1999-01-09"),
            finish=f,
            card="Charizard 4",
        )
        for k, f in [("a", "normal"), ("b", "holo")]
    }
    rows = species_scope.owned_evidence(owned, indexed)
    assert species_scope.classify(rows, criteria(set="base", released="pre-2000")) == "collected"
    assert species_scope.classify(rows, criteria(finish="holo")) == "unresolved"
    assert species_scope.classify(rows, criteria(finish="Unknown")) == "unresolved"
    assert (
        species_scope.classify(
            species_scope.owned_evidence({**owned, "owned_variant": "normal"}, indexed),
            criteria(finish="holo"),
        )
        == "outside"
    )
    assert (
        species_scope.classify(
            species_scope.owned_evidence({**owned, "exact_printing_owned_ids": ["b"]}, indexed),
            criteria(finish="holo", set="base"),
        )
        == "collected"
    )


def test_modern_only_owned_vs_vintage_unowned_stable_targets_and_saved_goal(cx):
    # The fixture has authentic engineering declaration evidence, no owner-state access.
    _, source = select(cx, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}})
    goal = create(cx, source)
    goal_before = collection.one(cx["actor"], "goal", goal["id"])
    sid = cx["by_legacy"]["a"]["set_id"]
    with patch.object(species_scope, "release_dates", return_value={sid: release("2000-02-24")}):
        pre = species_projection.project(cx["actor"], {"region": "kanto", "released": "pre-2000"})
        modern = species_projection.project(cx["actor"], {"region": "kanto", "released": "2000-onward"})
        assert pre["scoped_progress"] == dict(satisfied=0, total=151, units="species")
        assert modern["scoped_progress"] == dict(satisfied=1, total=151, units="species")
        assert len(pre["species"]) == len(modern["species"]) == 151
        row = next(r for r in pre["species"] if r["dex"] == 2)
        assert row["current_present"] and not row["scoped_present"]
        assert not next(r for r in modern["species"] if r["dex"] == 3)["scoped_present"]
        for display in [{"q": "Ivysaur"}, {"owned": "missing"}, {"owned": "owned"}]:
            result = species_projection.project(
                cx["actor"], {"region": "kanto", "released": "2000-onward", **display}
            )
            assert result["scoped_progress"] == modern["scoped_progress"]
        saved = species_projection.project(cx["actor"], {"goal": goal["id"], "released": "pre-2000"})
        assert saved["progress"]["satisfied"] == 1 and saved["scoped_progress"]["satisfied"] == 0
        assert saved["scoped_progress"]["total"] == 151
        assert collection.one(cx["actor"], "goal", goal["id"]) == goal_before


def test_species_only_unresolved_and_duplicates_count_once(cx):
    select(
        cx, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon); Ivysaur #44 (Uncommon)"}, 3: {"Base Set 2": "✓"}}
    )
    sid = cx["by_legacy"]["a"]["set_id"]
    with patch.object(species_scope, "release_dates", return_value={sid: release("2000-02-24")}):
        result = species_projection.project(cx["actor"], {"released": "2000-onward"})
        assert result["scoped_progress"]["satisfied"] == 1
        assert next(r for r in result["species"] if r["dex"] == 3)["scope_status"] == "unresolved"
        assert result["current_progress"]["satisfied"] == 2


def test_unindexed_literal_card_uses_only_unique_expansion_facts():
    row = dict(
        name="Ivysaur",
        number="999",
        set_name="Base Set",
        pokemon_dex=2,
        printing_ids=[],
        exact_printing_owned_ids=[],
    )
    facts = {"Base Set": dict(set="base", era="base", release=release("1999-01-09"))}
    evidence = species_scope.owned_evidence(row, {}, facts)
    assert species_scope.classify(evidence, criteria(set="base", released="pre-2000")) == "collected"
    assert species_scope.classify(evidence, criteria(finish="holo")) == "unresolved"
    assert species_scope.classify(evidence, criteria(rarity="Rare")) == "unresolved"


def test_unowned_eligible_printing_of_same_species_does_not_complete(cx):
    from test_cx03_review import clone

    select(cx, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}})
    modern_set = cx["by_legacy"]["a"]["set_id"]
    from pokemon_hunter.beta import store

    vintage_set = "ux03-vintage"
    original = store.rows("SELECT * FROM catalog_sets WHERE id=%s", [modern_set])[0]
    original.update(id=vintage_set, name="Vintage expansion")
    columns = list(original)
    collection.execute(
        "INSERT INTO catalog_sets ("
        + ",".join(columns)
        + ") VALUES ("
        + ",".join(["%s"] * len(columns))
        + ")",
        list(original.values()),
    )
    vintage = clone(cx, collector_number="99")
    collection.execute("UPDATE printings SET set_id=%s WHERE id=%s", [vintage_set, vintage])
    with patch.object(
        species_scope,
        "release_dates",
        return_value={modern_set: release("2020-01-01"), vintage_set: release("1999-01-09")},
    ):
        result = species_projection.project(
            cx["actor"], {"q": "Ivysaur", "region": "kanto", "released": "pre-2000"}
        )
        row = result["species"][0]
        assert row["eligible_indexed_printings"] > 0
        assert row["current_present"] and not row["scoped_present"]
        assert row["scope_status"] == "missing"
        assert result["scoped_progress"]["total"] == 151


def test_scope_bounds_reserve_room_for_focus_and_scroll(cx):
    from pokemon_hunter.beta.card_group_views import return_context

    raw = dict(set=json.dumps([str(i) + "a" * 150 for i in range(8)]))
    species_projection.filters(raw)
    destination = "/pokedex/?" + urlencode({**raw, "scroll": "10000000", "focus": "251", "selecting": "1"})
    assert return_context(destination) == destination
    nested = "/pokedex/251/?" + urlencode({"return": destination, "scroll": "10000000"})
    assert len(nested) < 4096 and return_context(nested) == nested
    with pytest.raises(ValueError):
        species_projection.filters({**raw, "q": "é" * 100})


def test_detail_scope_joins_canonical_tiles_without_internal_assertion_ids(cx):
    from pokemon_hunter.beta import card_groups

    select(cx, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}})
    sid = cx["by_legacy"]["a"]["set_id"]
    with patch.object(species_scope, "release_dates", return_value={sid: release("2000-02-24")}):
        outside = species_projection.project(cx["actor"], {"region": "kanto", "released": "pre-2000"})
        inside = species_projection.project(cx["actor"], {"region": "kanto", "released": "2000-onward"})
        tiles = card_groups.species(cx["actor"], 2)["owned"]["groups"]
        assert tiles and all("assertion_id" not in tile for tile in tiles)
        assert all(outside["scope_groups"][tile["id"]] == "outside" for tile in tiles)
        assert all(inside["scope_groups"][tile["id"]] == "collected" for tile in tiles)
