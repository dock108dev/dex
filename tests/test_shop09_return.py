"""SHOP-09 disposable equivalence and authority checks; no customer/provider use."""

from copy import deepcopy

import pytest
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_lot_calculator import workspace as workspace
from test_migration import snapshot as snapshot
from test_shopping import shop as shop

from pokemon_hunter.beta import collection, discovery, discovery_catalog, image_bindings


def denied(*args, **kwargs):
    raise AssertionError("Unrelated ownership/group projection must not run")


def test_deals_catalog_candidates_equal_full_projection_without_loading_ownership(workspace, monkeypatch):
    who = workspace["actor"]
    choices = [
        discovery.Choices(**fields)
        for fields in (
            {},
            {"focus": "kanto"},
            {"focus": "rares"},
            {"focus": "bulk"},
            {"set_id": "Base Set"},
            {"species": 2},
        )
    ]
    expected = [[p["id"] for p in discovery._candidate_data(who, c, None)] for c in choices]
    monkeypatch.setattr(discovery.parity, "projection", denied)
    assert [
        [p["id"] for p in discovery._candidate_data(who, c, None, ownership=False)] for c in choices
    ] == expected


def test_lean_deals_recheck_generation_and_publication(b4):
    who = b4["actor"]
    choices = discovery.Choices(generation=collection.generation(who))
    before = discovery._candidate_data(who, choices, None, ownership=False)
    assert before
    collection.execute("UPDATE printings SET publication_state='archived' WHERE id=%s", [before[0]["id"]])
    assert before[0]["id"] not in {
        p["id"] for p in discovery._candidate_data(who, choices, None, ownership=False)
    }
    collection.bump(who)
    with pytest.raises(collection.Conflict):
        discovery._candidate_data(who, choices, None, ownership=False)


def test_missing_still_uses_current_ownership_projection(workspace, monkeypatch):
    monkeypatch.setattr(discovery.parity, "projection", denied)
    with pytest.raises(AssertionError, match="ownership"):
        discovery._candidate_data(
            workspace["actor"], discovery.Choices(intent="missing"), None, ownership=False
        )


def test_image_subset_equals_full_binding_and_preserves_conflicting_siblings(workspace, monkeypatch):
    who = workspace["actor"]
    catalog = collection.catalog(who, include_archived=True)
    chosen = catalog[0]
    full = image_bindings.catalog_images(who, catalog)
    calls = []
    from pokemon_hunter.beta import image_mappings

    original = image_mappings.card_group_reference

    def counted(group, children, **kwargs):
        calls.append(group["id"])
        return original(group, children, **kwargs)

    monkeypatch.setattr(image_mappings, "card_group_reference", counted)
    subset = image_bindings.catalog_images(who, [chosen])
    assert subset == {chosen["id"]: full[chosen["id"]]}
    assert len(calls) == 1
    contradictory = deepcopy(chosen)
    contradictory.update(id="engineering-collision", name="Conflicting literal name")
    monkeypatch.setattr(collection, "catalog", lambda *args, **kwargs: [chosen, contradictory])
    assert image_bindings.catalog_images(who, [chosen]) == {}
    with pytest.raises(ValueError, match="authorized"):
        image_bindings.catalog_images(who, [dict(chosen, name="Forged")])


def test_no_inherited_set_needs_no_group_projection(workspace, monkeypatch):
    from pokemon_hunter.beta import card_groups

    monkeypatch.setattr(card_groups, "project", denied)
    monkeypatch.setattr(collection, "catalog", denied)
    assert discovery_catalog.entry_refinements(workspace["actor"], {"q": "Hypno"}, {"return_url": ""}) == (
        {"q": "Hypno"},
        "",
    )
