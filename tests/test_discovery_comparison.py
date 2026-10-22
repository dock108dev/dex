"""Synthetic offline discovery comparisons over the real lifecycle services."""

import copy
import json
from datetime import timedelta

import pytest
from django.conf import settings
from price_snapshot_helpers import NOW, multi_package, package, stage
from price_snapshot_helpers import b2 as b2
from price_snapshot_helpers import env as env
from price_snapshot_helpers import setup as setup
from price_snapshot_helpers import shop as shop
from price_snapshot_helpers import snapshot as snapshot

from pokemon_hunter.beta import collection, lot_calculator, price_snapshot_contract, price_snapshots, shopping
from pokemon_hunter.beta import discovery as service
from pokemon_hunter.beta import discovery_comparison as discovery


def listing(p, **changes):
    raw = dict(
        itemId="fixture-item-1",
        title=f"{p['set_name']} {p['name']} {p['collector_number']} English Unlimited Non Holo",
        condition="Near Mint",
        buyingOptions=["FIXED_PRICE"],
        price=dict(value="1.00", currency="USD"),
        shippingOptions=[dict(shippingCostType="FIXED", shippingCost=dict(value="0.50", currency="USD"))],
        itemWebUrl="https://www.ebay.com/itm/123",
    )
    raw.update(changes)
    return raw


def active(setup, *, permanent=True):
    value = package(setup, permanent=permanent)
    price_snapshots.activate(stage(value), None, now=NOW)
    return value, setup["entries"][value["records"][0]["printing_id"]]


def compare(setup, raw, *, now=NOW):
    return discovery.compare(setup["actor"], [raw], list(setup["entries"].values()), now=now)[0]


def test_owned_cards_are_candidates_no_goal_or_inventory_mutation(setup):
    value, p = active(setup)
    before = collection.export_data(setup["actor"])
    candidates = [dict(p, owned=True, current_copy_owned=True)]
    row = discovery.compare(setup["actor"], [listing(p)], candidates, now=NOW)[0]
    assert row["proposed_identity"]["printing_id"] == p["id"]
    assert row["proposed_identity"]["verified"] is False
    assert row["reference"]["amount"] == value["records"][0]["value"]
    assert row["delivered_total"] == "1.50"
    assert row["comparison"]["reference_minus_delivered_total"] == "1.05"
    assert row["comparison"]["below_reference"] is True
    assert row["classification"] == "conditional"  # Generic raw condition remains conditional.
    assert collection.export_data(setup["actor"]) == before


def test_unknown_shipping_is_retained_without_a_delivered_discount(setup):
    _, p = active(setup)
    row = compare(setup, listing(p, shippingOptions=[]))
    assert row["classification"] == "conditional"
    assert row["shipping"] is None and row["delivered_total"] is None
    assert row["comparison"]["reference_minus_delivered_total"] is None
    assert row["comparison"]["below_reference"] is None
    assert row["comparison"]["reference_minus_listing_price"] == "1.55"
    assert "shipping is unknown" in row["reason"]


@pytest.mark.parametrize(
    "claim", ["Japanese", "1st Edition", "Holo", "PSA 8 CGC 9", "Reverse Holo", "Not 1st Edition"]
)
def test_conflicting_or_special_identity_never_receives_reference(setup, claim):
    _, p = active(setup)
    raw = listing(p)
    raw["title"] += " " + claim
    row = compare(setup, raw)
    assert row["classification"] == "unpriced"
    assert row["reference"] is None
    assert row["comparison"]["below_reference"] is None


def test_generic_grade_scenario_and_literal_grader_match_are_distinct(setup, monkeypatch):
    _, p = active(setup)
    raw = listing(p)
    raw["title"] += " PSA 8"
    generic = compare(setup, raw)
    assert generic["classification"] == "conditional"
    assert generic["reference"]["grade"] == "8"
    assert "Generic grade scenario" in generic["reason"]
    original = discovery.lot_guides.cell_details

    def literal(printing, records, today):
        cells, reasons = original(printing, records, today)
        cells["8"] = dict(cells["8"], grader="PSA", estimated=False)
        return cells, reasons

    monkeypatch.setattr(discovery.lot_guides, "cell_details", literal)
    literal_row = compare(setup, raw)
    assert literal_row["classification"] == "comparable"
    assert "Literal grader and grade match" in literal_row["basis"]
    assert literal_row["proposed_identity"]["verified"] is False


def test_restricted_comparisons_remain_ephemeral_and_leave_history_intact(setup):
    value, p = active(setup, permanent=False)
    before = shopping.listing(setup["actor"])
    row = compare(setup, listing(p))
    assert row["reference"] and row["reference"]["save_allowed"] is False
    assert row["save_allowed"] is False and "saving is unavailable" in row["save_reason"]
    assert row["reference"]["snapshot_version"] == value["version"]
    assert row["reference"]["source_contract"] == price_snapshot_contract.digest(value["contract"])
    assert "raw_record" not in json.dumps(row) and "_contract_sha256" not in json.dumps(row)
    assert shopping.listing(setup["actor"]) == before


def test_conflicting_sources_expose_only_noncontent_lifecycle_keys(setup):
    value = multi_package(setup, competing=True)
    price_snapshots.activate(stage(value), None, now=NOW)
    p = setup["entries"][value["records"][0]["printing_id"]]
    before = shopping.listing(setup["actor"])
    row = compare(setup, listing(p))
    reference = row["reference"]
    assert reference["snapshot_version"] == value["version"]
    contracts = {price_snapshot_contract.digest(part["contract"]) for part in value["contracts"].values()}
    assert {
        reference["source_contract"],
        *(c["source_contract"] for c in reference["conflicts"]),
    } == contracts
    assert reference["conflicts"] and all("source_review" not in c for c in reference["conflicts"])
    assert "raw_record" not in json.dumps(row) and "_contract_sha256" not in json.dumps(row)
    assert row["save_allowed"] is False and reference["save_allowed"] is False
    assert shopping.listing(setup["actor"]) == before


@pytest.mark.parametrize("withdrawn", [True, False])
def test_expired_or_withdrawn_references_do_not_survive_reopening(setup, monkeypatch, withdrawn):
    value, p = active(setup, permanent=False)
    assert compare(setup, listing(p))["reference"]
    monkeypatch.setattr(lot_calculator, "legacy_records", lambda: [])
    if withdrawn:
        price_snapshots.remove(value["version"])
    else:
        price_snapshots.purge_expired(now=NOW + timedelta(days=2))
    row = compare(setup, listing(p))
    assert row["classification"] == "unpriced" and row["reference"] is None


def test_provider_valuation_date_remains_unknown_for_approved_build_reference(setup):
    value = package(setup)
    row = value["records"][0]
    policy = value["contract"]
    policy["provider"] = "TCGCSV"
    policy["fields"]["price-raw"].update(
        date_basis="publisher_build", valuation_date_field=None, reference_date_field="last-updated.txt"
    )
    row.update(as_of=None, reference_as_of="2026-10-09", publisher_built_at="2026-10-09T00:00:00+00:00")
    price_snapshots.atomic(
        settings.ROOT / "price-contracts.json", {"fixture": price_snapshot_contract.digest(policy)}
    )
    price_snapshots.activate(stage(value), None, now=NOW)
    p = setup["entries"][row["printing_id"]]
    reference = compare(setup, listing(p))["reference"]
    assert reference["valuation_as_of"] is None
    assert reference["as_of"] == "2026-10-09"
    assert reference["date_basis"] == "publisher_build"
    assert reference["captured_at"] == NOW.isoformat()


def test_duplicates_ambiguous_singles_and_unsupported_prices_are_readable(setup):
    _, p = active(setup)
    raw = listing(p)
    rows = discovery.compare(setup["actor"], [raw, copy.deepcopy(raw)], [p], now=NOW)
    assert len(rows) == 1
    unmatched = compare(setup, listing(p, title="Pokemon card no exact set or card number"))
    assert unmatched["classification"] == "unpriced" and unmatched["proposed_identity"] is None
    currency = compare(setup, listing(p, price=dict(value="1", currency="EUR")))
    assert currency["listing_price"] is None and currency["delivered_total"] is None
    auction = compare(
        setup, listing(p, buyingOptions=["AUCTION"], currentBidPrice=dict(value="0.50", currency="USD"))
    )
    assert auction["classification"] == "conditional" and auction["reference"]
    assert auction["comparison"]["below_reference"] is None
    assert "current bid" in auction["reason"]


def test_catalog_tampering_is_rejected_and_no_raw_legacy_value_path(setup, monkeypatch):
    _, p = active(setup)
    forged = dict(p, edition="first_edition")
    with pytest.raises(ValueError, match="authorized metadata"):
        discovery.compare(setup["actor"], [listing(p)], [forged], now=NOW)
    monkeypatch.setattr(shopping, "sources", lambda: pytest.fail("No old raw-value comparison path"))
    monkeypatch.setattr(lot_calculator, "legacy_records", lambda: [])
    assert compare(setup, listing(p))["reference"]


def test_condition_conflicts_unknown_condition_and_literal_grader_are_not_equivalent(setup, monkeypatch):
    _, p = active(setup)
    original = discovery.lot_guides.cell_details

    def condition(printing, records, today):
        cells, reasons = original(printing, records, today)
        cells["raw"] = dict(cells["raw"], raw_record=dict(cells["raw"]["raw_record"], condition="LP"))
        cells["8"] = dict(cells["8"], grader="CGC")
        return cells, reasons

    monkeypatch.setattr(discovery.lot_guides, "cell_details", condition)
    conflict = compare(setup, listing(p))
    assert conflict["classification"] == "unpriced" and "condition conflicts" in conflict["reason"]
    unknown = compare(setup, listing(p, condition="Ungraded"))
    assert unknown["classification"] == "conditional"
    matching = compare(setup, listing(p, condition="Lightly Played (Excellent)"))
    assert matching["classification"] == "comparable"
    grader = compare(setup, listing(p, title=listing(p)["title"] + " PSA 8"))
    assert grader["classification"] == "unpriced" and "grader conflicts" in grader["reason"]


def test_rank_uses_admitted_comparison_class_and_delivered_difference(setup, monkeypatch):
    _, p = active(setup)
    original = discovery.lot_guides.cell_details

    def condition(printing, records, today):
        cells, reasons = original(printing, records, today)
        cells["raw"] = dict(cells["raw"], raw_record=dict(cells["raw"]["raw_record"], condition="NM"))
        return cells, reasons

    monkeypatch.setattr(discovery.lot_guides, "cell_details", condition)
    raws = [
        listing(p, itemId="unpriced", title="Unknown Pokemon card"),
        listing(p, itemId="conditional-over", price=dict(value="4", currency="USD"), condition="Ungraded"),
        listing(p, itemId="over", price=dict(value="3", currency="USD")),
        listing(p, itemId="conditional-below", condition="Ungraded"),
        listing(p, itemId="below-small-b"),
        listing(p, itemId="below-small-a"),
        listing(p, itemId="below-large", price=dict(value="0.50", currency="USD")),
    ]
    rows = discovery.compare(setup["actor"], raws, [p], now=NOW)
    assert [r["item_id"] for r in rows] == [
        "below-large",
        "below-small-a",
        "below-small-b",
        "conditional-below",
        "over",
        "conditional-over",
        "unpriced",
    ]
    assert [r["classification"] for r in rows] == [
        "comparable",
        "comparable",
        "comparable",
        "conditional",
        "comparable",
        "conditional",
        "unpriced",
    ]


def test_service_candidate_projection_preserves_authoritative_catalog_identity(setup):
    _, p = active(setup)
    candidates = service._candidate_data(setup["actor"], service.Choices(), None)
    assert candidates
    rows = discovery.compare(setup["actor"], [listing(p)], candidates, now=NOW)
    assert len(rows) == 1


@pytest.mark.parametrize("claim", ["2 cards", "x4", "4x"])
def test_multiples_and_selectable_offers_never_use_single_reference(setup, claim):
    _, p = active(setup)
    row = compare(setup, listing(p, title=listing(p)["title"] + " " + claim))
    assert row["classification"] == "unpriced" and row["reference"] is None


@pytest.mark.parametrize(
    "claim", ["Choose your card", "Complete Set", "Sealed Booster", "Mystery", "Curated", "Random", "Repack"]
)
def test_unsupported_products_are_excluded_from_discovery(setup, claim):
    _, p = active(setup)
    assert (
        discovery.compare(setup["actor"], [listing(p, title=listing(p)["title"] + " " + claim)], [p], now=NOW)
        == []
    )


def test_loose_lot_and_imperfect_title_are_useful_without_single_reference(setup):
    _, p = active(setup)
    row = compare(setup, listing(p, title=f"{p['name']} vintage loose mixed lot 10 cards"))
    assert row["discovery_kind"] == "mixed_lot"
    assert row["discovery_eligibility"] == "candidate"
    assert row["proposed_identity"] is None and row["reference"] is None
    assert p["id"] in {c["printing_id"] for c in row["identity_candidates"]}
    assert all(c["verified"] is False for c in row["identity_candidates"])
    assert "approximate name match" in row["reason"]


def test_mixed_auction_buy_now_and_bid_remain_separate(setup):
    _, p = active(setup)
    row = compare(
        setup,
        listing(
            p,
            buyingOptions=["AUCTION", "FIXED_PRICE"],
            currentBidPrice=dict(value="0.50", currency="USD"),
            price=dict(value="20.00", currency="USD"),
        ),
    )
    assert row["current_bid"] == row["listing_price"] == "0.50"
    assert row["buy_now_price"] == "20.00" and row["price_kind"] == "current_bid"
    assert row["reference"] and row["comparison"]["below_reference"] is None
    assert row["comparison"]["reference_minus_delivered_total"] is None
    assert "not the final purchase price" in row["reason"]


def test_auction_without_bid_does_not_substitute_buy_now(setup):
    _, p = active(setup)
    row = compare(setup, listing(p, buyingOptions=["AUCTION", "FIXED_PRICE"], currentBidPrice=None))
    assert row["listing_price"] is None and row["current_bid"] is None
    assert row["buy_now_price"] == "1.00" and row["delivered_total"] is None


def test_base_set_two_cannot_match_base_set_even_with_uuid_catalog_set_id(setup):
    _, p = active(setup)
    raw = listing(p)
    raw["title"] = raw["title"].replace("Base Set", "Base Set 2")
    row = compare(setup, raw)
    assert row["proposed_identity"] is None and row["reference"] is None


def test_mixed_category_never_values_whole_lot_as_one_named_card(setup):
    _, p = active(setup)
    raw = listing(
        p,
        _discovery_category="183455",
        image={"imageUrl": "https://i.ebayimg.com/images/g/Engineering/s-l500.jpg"},
    )
    row = compare(setup, raw)
    assert row["discovery_kind"] == "mixed_lot" and row["reference"] is None
    assert row["identity_candidates"] and row["proposed_identity"] is None
    assert row["seller_image"].startswith("https://i.ebayimg.com/")
    assert row["item_url"] == raw["itemWebUrl"]
    assert "whole lot" in row["reason"]
