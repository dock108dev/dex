"""Offline Hunter batches reuse the admitted Shopping identity/value authorities."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from price_snapshot_helpers import NOW, package, stage
from price_snapshot_helpers import b2 as b2
from price_snapshot_helpers import env as env
from price_snapshot_helpers import setup as setup
from price_snapshot_helpers import shop as shop
from price_snapshot_helpers import snapshot as snapshot

from pokemon_hunter.beta import (
    collection,
    discovery_comparison,
    hunter_catalog,
    lot_calculator,
    price_snapshots,
)

OBSERVED = datetime(2026, 10, 16, 12, tzinfo=UTC)


def printing(key, name="Gholdengo ex", *, set_name="Paradox Rift", number="252/182", **changes):
    result = dict(
        id=key,
        name=name,
        set_id="set-" + set_name,
        set_name=set_name,
        collector_number=number,
        language="en",
        edition="standard",
        finish="normal",
        variant="normal",
        game_id="pokemon",
        pokemon_dex=1000,
        provenance='{"legacy_id":"' + key + '"}',
        owned=True,
    )
    return dict(result, **changes)


def listing(p, **changes):
    result = dict(
        itemId="offer-" + p["id"],
        title=f"{p['set_name']} {p['name']} {p['collector_number']} English Unlimited Non Holo",
        condition="Near Mint",
        buyingOptions=["FIXED_PRICE"],
        price=dict(value="1.00", currency="USD"),
        shippingOptions=[dict(shippingCostType="FIXED", shippingCost=dict(value="0.50", currency="USD"))],
        itemWebUrl="https://www.ebay.com/itm/123",
    )
    return dict(result, **changes)


def reference(p):
    return dict(
        amount="2.55",
        currency="USD",
        as_of="2026-10-15",
        grade="raw",
        grader="PSA",
        raw_record=dict(condition="NM", language="en", edition="standard", finish="normal"),
        match_status="exact",
        source_url="https://example.test/fixture",
    )


@pytest.fixture
def local(monkeypatch):
    from pokemon_hunter.beta import store

    actor = SimpleNamespace(user_id="hunter")
    monkeypatch.setattr(store, "verified", lambda value: value)
    monkeypatch.setattr(store, "rows", lambda *a, **k: [dict(id="pokemon")])
    monkeypatch.setattr(collection, "generation", lambda actor: 1)
    return actor


def test_owned_modern_trainer_energy_are_indexed_in_one_read(local, monkeypatch):
    cards = [
        printing("modern"),
        printing("trainer", "Professor Turo's Scenario", number="171/182", pokemon_dex=None),
        printing(
            "energy", "Basic Lightning Energy", set_name="Scarlet & Violet", number="004", pokemon_dex=None
        ),
        printing("other-game", "Gholdengo ex", game_id="other"),
    ]
    called = dict(catalog=0, references=0, guides=0)

    def catalog(*args, **kw):
        assert kw == {"include_archived": True}
        called["catalog"] += 1
        return cards

    def records():
        called["references"] += 1
        return []

    def guides(p, records, today):
        called["guides"] += 1
        return {"raw": reference(p)}, {}

    monkeypatch.setattr(collection, "catalog", catalog)
    monkeypatch.setattr(lot_calculator, "retained_records", records)
    monkeypatch.setattr(discovery_comparison.lot_guides, "cell_details", guides)
    monkeypatch.setattr(
        discovery_comparison.image_bindings,
        "catalog_images",
        lambda *a: pytest.fail("Hunter backend must not reread the catalog to bind artwork"),
    )
    raws = [listing(cards[i % 3], itemId=str(i)) for i in range(400)]
    rows = hunter_catalog.compare(local, raws, now=OBSERVED)
    assert len(rows) == 400
    assert called == dict(catalog=1, references=1, guides=3)
    assert hunter_catalog.counts(rows)["priced"] == 400
    assert {row["proposed_identity"]["printing_id"] for row in rows} == {"modern", "trainer", "energy"}
    assert all(row["proposed_identity"]["catalog_identity"]["variant"] == "normal" for row in rows)
    assert all(row["delivered_cost_complete"] is False and row["tax"] is None for row in rows)
    assert all(row["listing_and_shipping_complete"] is True for row in rows)
    assert all(
        row["listing_and_shipping_subtotal"] == "1.50" and row["delivered_total"] is None for row in rows
    )
    assert all(row["comparison"]["reference_minus_delivered_total"] is None for row in rows)
    assert all(row["comparison"]["reference_minus_listing_and_shipping_subtotal"] == "1.05" for row in rows)
    assert all(row["comparison"]["below_reference"] is True for row in rows)


def test_reconciled_dispositions_keep_ambiguity_gaps_and_lots(local, monkeypatch):
    cards = [printing("priced"), printing("unpriced", "Iron Hands ex", number="248/182")]
    siblings = [
        printing("sibling-a", "Pikachu", number="27"),
        printing("sibling-b", "Pikachu", number="27", finish="holo"),
    ]
    monkeypatch.setattr(collection, "catalog", lambda *a, **k: cards + siblings)
    monkeypatch.setattr(lot_calculator, "retained_records", lambda: [])
    monkeypatch.setattr(
        discovery_comparison.lot_guides,
        "cell_details",
        lambda p, r, t: ({"raw": reference(p)} if p["id"] == "priced" else {}, {"raw": "Missing reference"}),
    )
    raws = [
        listing(cards[0]),
        listing(cards[0], itemId="conditional", shippingOptions=[]),
        listing(siblings[0], title="Paradox Rift Pikachu 27 English"),
        listing(cards[0], itemId="unmatched", title="Unindexed modern Pokemon card"),
        listing(cards[1]),
        listing(cards[0], itemId="sealed", title="Gholdengo ex sealed booster"),
        listing(cards[0], itemId="lot", title=listing(cards[0])["title"] + " lot 3 cards"),
    ]
    rows = hunter_catalog.compare(local, raws, now=OBSERVED)
    assert hunter_catalog.counts(rows) == dict(
        priced=1, conditional=1, ambiguous=1, unmatched=1, unpriced=1, unsupported=2
    )
    by_id = {row["item_id"]: row for row in rows}
    assert by_id["offer-sibling-a"]["identity_candidates_total"] == 2
    assert by_id["offer-sibling-a"]["reference"] is None
    assert by_id["lot"]["contents_review_required"] is True
    assert by_id["lot"]["reference"] is None and by_id["lot"]["proposed_identity"] is None
    assert by_id["conditional"]["shipping"] is None and by_id["conditional"]["delivered_total"] is None
    assert sum(hunter_catalog.counts(rows).values()) == len(raws)


def test_index_narrows_before_exact_match_and_reference_buckets_preserve_status(local, monkeypatch):
    cards = [printing("modern")] + [printing(str(i), "IndexedSpecies" + str(i)) for i in range(20000)]
    monkeypatch.setattr(collection, "catalog", lambda *a, **k: cards)
    records = lot_calculator.SnapshotRecords(
        [dict(card_id="modern", grade="raw"), dict(card_id="unrelated", grade="raw")], "missing_snapshot"
    )
    monkeypatch.setattr(lot_calculator, "retained_records", lambda: records)
    original = discovery_comparison._matches
    sizes = []

    def matches(candidates, clues):
        sizes.append(len(candidates))
        return original(candidates, clues)

    def guides(p, records, today):
        assert list(records) == [dict(card_id="modern", grade="raw")]
        assert records.status == "missing_snapshot"
        return {}, {"raw": "No active private snapshot"}

    monkeypatch.setattr(discovery_comparison, "_matches", matches)
    monkeypatch.setattr(discovery_comparison.lot_guides, "cell_details", guides)
    rows = hunter_catalog.compare(local, [listing(cards[0], itemId=str(i)) for i in range(400)], now=OBSERVED)
    assert sizes == [1] * 400
    assert len(rows) == 400 and all(row["hunt_status"] == "unpriced" for row in rows)


def test_conflicts_and_separate_auction_bin_observations(local, monkeypatch):
    p = printing("modern")
    monkeypatch.setattr(collection, "catalog", lambda *a, **k: [p])
    monkeypatch.setattr(lot_calculator, "retained_records", lambda: [])
    monkeypatch.setattr(
        discovery_comparison.lot_guides, "cell_details", lambda *a: ({"raw": reference(p)}, {})
    )
    raw = listing(
        p,
        buyingOptions=["AUCTION", "FIXED_PRICE"],
        currentBidPrice=dict(value="0.20", currency="USD"),
        minimumPriceToBid=dict(value="0.25", currency="USD"),
        price=dict(value="4.00", currency="USD"),
    )
    row = hunter_catalog.compare(local, [raw], now=OBSERVED)[0]
    assert row["current_bid"] == "0.20" and row["buy_now_price"] == "4.00"
    assert row["minimum_next_bid"] == "0.25" and row["buy_now_available"] is True
    assert row["final_purchase_price"] is None and row["planned_manual_bid"] is None
    assert row["comparison"]["below_reference"] is None and row["hunt_status"] == "conditional"
    raw["title"] += " Japanese"
    conflict = hunter_catalog.compare(local, [raw], now=OBSERVED)[0]
    assert conflict["reference"] is None and conflict["hunt_status"] == "unpriced"


def test_limits_and_catalog_change_suppress_projection(local, monkeypatch):
    with pytest.raises(ValueError, match="400"):
        hunter_catalog.compare(local, [{}] * 401)
    with pytest.raises(ValueError, match="aware"):
        hunter_catalog.compare(local, [], now=datetime(2026, 10, 16))
    p = printing("modern")
    monkeypatch.setattr(collection, "catalog", lambda *a, **k: [p])
    monkeypatch.setattr(lot_calculator, "retained_records", lambda: [])
    generation = iter([1, 2])
    monkeypatch.setattr(collection, "generation", lambda actor: next(generation))
    with pytest.raises(collection.Conflict, match="Catalog changed"):
        hunter_catalog.compare(local, [listing(p)], now=OBSERVED)


@pytest.mark.parametrize("withdrawn", [False, True])
def test_real_admission_expiry_withdrawal_and_original_dates(setup, monkeypatch, withdrawn):
    value = package(setup, permanent=False)
    price_snapshots.activate(stage(value), None, now=NOW)
    p = setup["entries"][value["records"][0]["printing_id"]]
    raw = listing(p)
    row = hunter_catalog.compare(setup["actor"], [raw], now=NOW)[0]
    assert row["hunt_status"] == "conditional" and row["reference"]
    assert row["reference"]["as_of"] == "2026-10-09"
    assert row["reference"]["captured_at"] == NOW.isoformat()
    assert row["observed_at"] == NOW.astimezone(UTC).isoformat()
    monkeypatch.setattr(lot_calculator, "legacy_records", lambda: [])
    if withdrawn:
        price_snapshots.remove(value["version"])
    else:
        price_snapshots.purge_expired(now=NOW + timedelta(days=2))
    unavailable = hunter_catalog.compare(setup["actor"], [raw], now=NOW)[0]
    assert unavailable["hunt_status"] == "unpriced" and unavailable["reference"] is None


def test_literal_variant_and_raw_grade_claims_never_collapse_siblings(local, monkeypatch):
    normal = printing("normal")
    stamped = printing("stamped", variant="stamped")
    monkeypatch.setattr(collection, "catalog", lambda *a, **k: [normal, stamped])
    monkeypatch.setattr(lot_calculator, "retained_records", lambda: [])
    row = hunter_catalog.compare(local, [listing(normal)], now=OBSERVED)[0]
    assert row["hunt_status"] == "ambiguous" and row["reference"] is None
    assert {i["catalog_identity"]["variant"] for i in row["identity_candidates"]} == {"normal", "stamped"}
    monkeypatch.setattr(collection, "catalog", lambda *a, **k: [normal])
    monkeypatch.setattr(
        discovery_comparison.lot_guides, "cell_details", lambda *a: ({"raw": reference(normal)}, {})
    )
    raw = listing(
        normal, title=listing(normal)["title"] + " Reverse Holo CGC 8.5", condition="Lightly Played"
    )
    conflicted = hunter_catalog.compare(local, [raw], now=OBSERVED)[0]
    assert conflicted["hunt_status"] == "unpriced" and conflicted["reference"] is None
    assert conflicted["raw_condition_basis"] == "Lightly Played"
    assert conflicted["proposed_identity"]["grader"] == "CGC"
    assert conflicted["proposed_identity"]["grade"] == "8.5"


def test_stale_reference_and_unknown_shipping_never_claim_complete_comparison(local, monkeypatch):
    p = printing("modern")
    monkeypatch.setattr(collection, "catalog", lambda *a, **k: [p])
    monkeypatch.setattr(lot_calculator, "retained_records", lambda: [])
    stale = dict(reference(p), as_of="2026-08-01")
    monkeypatch.setattr(discovery_comparison.lot_guides, "cell_details", lambda *a: ({"raw": stale}, {}))
    row = hunter_catalog.compare(local, [listing(p, shippingOptions=[])], now=OBSERVED)[0]
    assert row["hunt_status"] == "unpriced" and row["reference"] is None
    assert row["shipping"] is None and row["listing_and_shipping_subtotal"] is None
    assert row["delivered_total"] is None and row["delivered_cost_complete"] is False
    assert row["comparison"]["below_reference"] is None
