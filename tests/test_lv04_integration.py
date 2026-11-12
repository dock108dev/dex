"""LV-03 worker → automatic assessment → optional review, using controlled I/O."""

from copy import deepcopy
from types import SimpleNamespace

import pytest
from django.http import Http404
from test_hunter_lots import entries as entries
from test_hunter_policy import everyday as everyday
from test_listing_check import review_value
from test_lv03_hunt import env as env
from test_lv03_hunt import offer

from pokemon_hunter.beta import (
    collection,
    effective_collection,
    image_bindings,
    listing_check,
    shopping_index,
)
from pokemon_hunter.beta import discovery as discovery
from pokemon_hunter.beta import lot_calculator as calculator
from pokemon_hunter.beta import lot_hunt as hunt

TEXT = (
    "All cards are ungraded Base Set English Unlimited Non Holo. Two Charizard 4/102 and one Blastoise 2/102"
)


def configure(env, entries, monkeypatch):
    for row in env.bin + env.auction:
        env.details[row["itemId"]] = dict(row, description=TEXT)
    monkeypatch.setattr(calculator, "catalog", lambda *a, **kw: deepcopy(entries))
    # This controlled worker has no Django database; supply collection-fit inputs
    # while exercising the real projection consumer and review lease.
    monkeypatch.setattr(effective_collection, "project", lambda actor: {"species": {"6": {"present": False}}})
    monkeypatch.setattr(
        collection,
        "catalog_entries",
        lambda *a, printing_ids=(), **kw: [
            {**p, "attributes": {"pokemon_dex": 6 if p["id"] == "charizard" else 9, "supertype": "Pokémon"}}
            for p in deepcopy(entries)
            if p["id"] in printing_ids
        ],
    )
    monkeypatch.setattr(image_bindings, "catalog_images", lambda *a: {})
    listing_check._reviews.clear()


def test_automatic_contents_unpriced_and_manual_correction_same_lease(env, entries, monkeypatch):
    configure(env, entries, monkeypatch)
    run, result = env.execute(env.start(query="Charizard"))
    row = result["results"][0]
    value = hunt.evidence(env.actor, "session", run.id, row["id"], row["content_revision"])["lot_value"]
    assert value["contents_state"] == "resolved"
    assert value["identified_quantity"] == value["identified_unpriced_quantity"] == 3
    assert value["priced_quantity"] == value["unidentified_quantity"] == 0
    assert {c["printing_id"] for c in value["cards"]} == {p["id"] for p in entries}
    assert all(c["reference_subtotal"] is None for c in value["cards"])
    origin = dict(run_id=run.id, result_id=result["results"][0]["id"])
    preview = listing_check.candidate(env.actor, "session", **origin)
    projected = preview["listing"]
    assert sum(p["quantity"] for p in projected["proposals"]) == 3
    assert projected["seller_contents"]["detail_used"]
    assert projected["unknown_contents"] == 0
    assert len(env.calls) == 5
    opened = listing_check.review(env.actor, "session")
    correction = review_value(entries[0], discovery_origin=origin)
    correction["cards"][0]["quantity"] = 1
    saved = listing_check.review(env.actor, "session", correction, opened["lease"])
    assert saved["review"]["cards"][0]["quantity"] == 1
    assert saved["expires_in_seconds"] <= preview["expires_in_seconds"]
    assert len(env.calls) == 5
    with pytest.raises(ValueError):
        listing_check.review(env.actor, "session", correction, "stale-lease")
    with pytest.raises(Http404):
        listing_check.candidate(env.actor, "wrong-session", **origin)
    with pytest.raises(Http404):
        listing_check.candidate(SimpleNamespace(user_id="other", role="owner"), "session", **origin)
    hunt.stop(env.actor, "session", run.id)
    with pytest.raises(ValueError, match="expired or was stopped"):
        listing_check.review(env.actor, "session")
    assert len(env.calls) == 5


def test_summary_assessment_remains_distinct_from_full_seller_details(env):
    env.bin.append(offer(3))
    env.details[env.bin[0]["itemId"]] = dict(env.bin[0], description="All cards from Base Set; see photos")
    _, result = env.execute()
    enriched = next(
        r
        for r in result["results"]
        if r["evidence_kind"] == "seller_details" and r["lot_value"]["identified_quantity"] == 0
    )
    assert enriched["lot_value"]["contents_state"] == "unresolved"
    unprocessed = next(r for r in result["results"] if r["assessment_state"] == "unprocessed")
    assert unprocessed["evidence_kind"] == "seller_summary"
    assert unprocessed["lot_value"]["identified_quantity"] == 0
    assert unprocessed["lot_value"]["total"] is None
    assert unprocessed["lot_value"]["references"] == []
    assert result["progress"]["unprocessed"] == 1 and len(env.calls) == 5


def test_revision_during_manual_projection_fails_without_replay(env, entries, monkeypatch):
    configure(env, entries, monkeypatch)
    run, result = env.execute()
    original = listing_check.catalog

    def catalog(*a, **kw):
        value = original(*a, **kw)
        run.content_revision += 1
        return value

    monkeypatch.setattr(listing_check, "catalog", catalog)
    with pytest.raises(ValueError, match="changed"):
        listing_check.candidate(env.actor, "session", run.id, result["results"][0]["id"])
    assert len(env.calls) == 5


def test_indexed_catalog_narrowing_includes_aspects_and_all_cards(env, entries, monkeypatch):
    from pokemon_hunter.beta import discovery_listing, discovery_lot_values

    source = offer()
    detail = dict(
        source,
        description="",
        localizedAspects=[
            dict(
                name="Contents",
                value="2x Charizard Base Set 4/102 English Unlimited Non Holo; 1x Blastoise Base Set 2/102 English Unlimited Non Holo",
            )
        ],
    )
    seen = []
    selections = []
    retained = calculator.retained_records

    def selected_records():
        selections.append(calculator.price_snapshots._selection.get()[0])
        return retained()

    monkeypatch.setattr(calculator, "retained_records", selected_records)

    def proposals(text):
        seen.append(text)
        return entries if "Blastoise" in text else []

    monkeypatch.setattr(
        shopping_index,
        "current",
        lambda *a: SimpleNamespace(
            proposals=proposals,
            publication_checks=[],
            release_dates=discovery_lot_values.species_scope.release_dates,
        ),
    )
    rows = discovery_listing.received_rows([source])
    discovery_lot_values.project(env.actor, [source], rows, details={source["itemId"]: detail})
    assert rows[0]["lot_value"]["identified_quantity"] == 3
    assert seen and "Blastoise" in seen[0] and env.calls == []
    assert selections[0] == {p["id"] for p in entries}


def test_saved_correction_reuses_detail_and_rejects_content_revision_race(env, entries, monkeypatch):
    configure(env, entries, monkeypatch)
    run, result = env.execute()
    origin = dict(run_id=run.id, result_id=result["results"][0]["id"])
    opened = listing_check.review(env.actor, "session")
    saved = listing_check.review(
        env.actor,
        "session",
        review_value(entries[0], discovery_origin=origin, price_kind="current_asking_price"),
        opened["lease"],
    )

    def compare(actor, value, *, offers, _checks=None):
        assert offers[0]["_contents_kind"] == "official_detail"
        assert offers[0]["_contents_source"]["description"] == TEXT
        run.content_revision += 1
        return dict(assessment=dict(evidence=[], maximum=None))

    monkeypatch.setattr(listing_check, "compare", compare)
    with pytest.raises(ValueError, match="Offer changed"):
        listing_check.saved_comparison(env.actor, "session", saved["revision"], opened["lease"])
    assert len(env.calls) == 5
