"""SHOP-10 isolated review-save equivalence, expiry and origin regressions."""

import time
import uuid
from copy import deepcopy

import pytest
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_listing_check import review_value
from test_lot_calculator import workspace as workspace
from test_migration import snapshot as snapshot
from test_shopping import shop as shop

from pokemon_hunter.beta import collection, collection_catalog, discovery, listing_check, lot_calculator


def test_bounded_review_catalog_equals_full_supported_catalog(workspace):
    who = workspace["actor"]
    full = lot_calculator.catalog(who, include_goals=True, include_current=True)
    ids = {p["id"] for p in full[:3]}
    subset = lot_calculator.catalog(who, include_goals=True, include_current=True, printing_ids=ids)
    assert subset == [p for p in full if p["id"] in ids]
    assert lot_calculator.catalog(who, include_goals=True, printing_ids=set()) == []
    assert collection_catalog.catalog_entries(printing_ids={"' OR 1=1 --"}) == []


def test_bounded_catalog_keeps_current_publication_filter(b4):
    who = b4["actor"]
    p = collection.catalog(who)[0]
    ids = {p["id"]}
    assert collection_catalog.catalog_entries(printing_ids=ids)
    collection.execute("UPDATE printings SET publication_state='archived' WHERE id=%s", [p["id"]])
    assert collection_catalog.catalog_entries(printing_ids=ids) == []
    assert lot_calculator.catalog(who, include_goals=True, include_current=True, printing_ids=ids) == []


def test_ordinary_review_ids_avoid_goal_progress_but_goal_only_entries_keep_policy(workspace, monkeypatch):
    who = workspace["actor"]
    p = deepcopy(lot_calculator.catalog(who)[0])
    monkeypatch.setattr(collection, "catalog_entries", lambda *a, **k: [p])
    monkeypatch.setattr(collection, "goals", lambda *a, **k: pytest.fail("Unrelated goal progress"))
    assert lot_calculator.catalog(who, include_goals=True, include_current=True, printing_ids={p["id"]}) == [
        p
    ]
    p["set_name"] = "Engineering later expansion"
    p["attributes"]["supertype"] = "Trainer"
    calls = []

    def goals(actor, **kwargs):
        assert actor == who and kwargs == {"include_updates": False}
        calls.append(True)
        return [{"definition": {"items": [{"printing_ids": [p["id"]]}]}}]

    monkeypatch.setattr(collection, "goals", goals)
    assert lot_calculator.catalog(who, include_goals=True, include_current=True, printing_ids={p["id"]}) == [
        p
    ]
    assert calls == [True]
    monkeypatch.setattr(collection, "goals", lambda *a, **k: [])
    assert lot_calculator.catalog(who, include_goals=True, include_current=True, printing_ids={p["id"]}) == []


def test_structural_errors_are_rejected_before_catalog_work(workspace, monkeypatch):
    p = workspace["catalog"][0]
    monkeypatch.setattr(
        lot_calculator, "catalog", lambda *a, **k: pytest.fail("Malformed input needs no catalog")
    )
    value = review_value(p)
    value["cards"][0]["printing_id"] = ["invalid"]
    with pytest.raises(ValueError, match="supported printing"):
        listing_check.validate_review(workspace["actor"], value)
    value = review_value(p)
    value["cards"][0]["quantity"] = -1
    with pytest.raises(ValueError, match="whole card"):
        listing_check.validate_review(workspace["actor"], value)


def test_save_revalidates_origin_once_and_each_read_revalidates_again(workspace, monkeypatch):
    who = workspace["actor"]
    listing_check._reviews.clear()
    calls, available = [], [True]
    origin = dict(run_id=str(uuid.uuid4()), result_id="a" * 24)
    created = time.monotonic() - 30

    def source(*args, **kwargs):
        calls.append(True)
        if not available[0]:
            raise ValueError("Origin unavailable")
        return dict(created=created, choices={"intent": "deals"}, scope=None)

    monkeypatch.setattr(discovery, "review_candidate", source)
    opened = listing_check.review(who, "session")
    value = review_value(workspace["catalog"][0], discovery_origin=origin)
    result = listing_check.review(who, "session", value, opened["lease"])
    assert calls == [True]
    assert result["context"]["choices"] == {"intent": "deals"}
    assert result["review"] == value and result["lease"] == opened["lease"]
    listing_check.review(who, "session")
    assert len(calls) == 2
    available[0] = False
    with pytest.raises(ValueError, match="expired or was stopped"):
        listing_check.review(who, "session")
    assert listing_check.review(who, "session")["review"] is None


def test_expiry_during_validation_cannot_commit_a_new_revision(workspace, monkeypatch):
    who = workspace["actor"]
    listing_check._reviews.clear()
    opened = listing_check.review(who, "session")
    before = listing_check._reviews[discovery._owner(who, "session")]
    original = listing_check.validate_review

    def elapsed(actor, value):
        original(actor, value)
        monkeypatch.setattr(listing_check.time, "monotonic", lambda: before[0] + discovery.EPHEMERAL_SECONDS)

    monkeypatch.setattr(listing_check, "validate_review", elapsed)
    with pytest.raises(ValueError, match="expired"):
        listing_check.review(who, "session", review_value(workspace["catalog"][0]), opened["lease"])
    assert listing_check._reviews[discovery._owner(who, "session")] == before
