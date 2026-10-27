"""Offline comparison explanations and literal matching regressions.

All cases are fabricated engineering inputs. They do not reconstruct the erased
seller corpus or establish actual reference coverage, freshness or a bargain.
"""

from copy import deepcopy

import pytest
from test_hunter_catalog import OBSERVED, listing, printing, reference
from test_hunter_catalog import local as local
from test_hunter_ranking import row as ranking_row

from pokemon_hunter.beta import (
    collection,
    discovery_comparison,
    hunter_catalog,
    hunter_coverage,
    hunter_lots,
    hunter_ranking,
    lot_calculator,
)


def project(actor, monkeypatch, cards, raws, *, records_status="active_snapshot", reason=None):
    monkeypatch.setattr(collection, "catalog", lambda *a, **kw: cards)
    monkeypatch.setattr(
        lot_calculator,
        "retained_records",
        lambda: lot_calculator.SnapshotRecords([], records_status),
    )
    monkeypatch.setattr(
        discovery_comparison.lot_guides,
        "cell_details",
        lambda p, *a: ({}, {"raw": reason}) if reason else ({"raw": reference(p)}, {}),
    )
    return hunter_catalog.compare(actor, raws, now=OBSERVED)


def codes(row):
    return set(row["comparison_diagnostics"]["codes"])


def test_literal_collection_set_name_is_a_single_without_masking_a_real_lot(local, monkeypatch):
    p = printing("legendary", "Pikachu", set_name="Legendary Collection", number="86/110")
    raws = [listing(p), listing(p, itemId="lot", title=listing(p)["title"] + " lot 3 cards")]
    by_id = {row["item_id"]: row for row in project(local, monkeypatch, [p], raws)}
    single = by_id["offer-legendary"]
    assert single["discovery_kind"] == "single"
    assert single["reference"] is not None and single["hunt_status"] == "priced"
    lot = by_id["lot"]
    assert lot["discovery_kind"] == "mixed_lot" and lot["reference"] is None
    assert codes(lot) == {"lot_contents_review"}


@pytest.mark.parametrize("extra", ["sealed booster", "mystery", "choose your card"])
def test_literal_collection_set_never_hides_excluded_product_claims(local, monkeypatch, extra):
    p = printing("legendary", "Pikachu", set_name="Legendary Collection", number="86/110", attributes={})
    row = project(local, monkeypatch, [p], [listing(p, title=listing(p)["title"] + " " + extra)])[0]
    assert row["discovery_kind"] == "unsupported" and row["reference"] is None
    assert codes(row) == {"unsupported_product"}


def test_conflicting_literal_sets_cannot_admit_the_only_named_card_reference(local, monkeypatch):
    p = printing("modern")
    unrelated = printing("base", "Pikachu", set_name="Base Set", number="58/102")
    raw = listing(p, title=listing(p)["title"] + " Base Set")
    row = project(local, monkeypatch, [p, unrelated], [raw])[0]
    assert row["proposed_identity"]["printing_id"] == p["id"]
    assert row["identity_status"] == "conflicting"
    assert row["reference"] is None and row["opportunity"]["rank"] is None
    assert "literal_set_conflict" in codes(row)


def test_shared_and_contained_set_aliases_alone_are_not_conflicting_sets(local, monkeypatch):
    p = printing("modern", set_aliases=["Paradox"])
    other = printing("other", "Other card", set_name="Other Set", set_aliases=["Paradox Rift"])
    row = project(local, monkeypatch, [p, other], [listing(p)])[0]
    assert row["identity_status"] == "matched" and row["reference"]
    assert "literal_set_conflict" not in codes(row)


def test_card_name_equal_to_a_known_set_is_not_a_second_set_claim(local, monkeypatch):
    p = printing("arceus", "Arceus", set_name="Platinum", number="1/99")
    other = printing("other", "Other card", set_name="Arceus", number="2/99")
    row = project(local, monkeypatch, [p, other], [listing(p)])[0]
    assert row["identity_status"] == "matched" and row["reference"]


def test_primary_outcomes_and_overlapping_reasons_have_explicit_denominators(local, monkeypatch):
    p = printing("modern")
    sibling = printing("sibling", finish="holo")
    raws = [
        listing(p),
        listing(p, itemId="shipping", shippingOptions=[]),
        listing(p, itemId="lot", title="Pokemon lot 20 cards"),
        listing(p, itemId="sealed", title="Pokemon sealed booster"),
        listing(p, itemId="missing", title="No known local card"),
        listing(p, itemId="ambiguous", title="Paradox Rift Gholdengo ex 252/182 English"),
    ]
    rows = project(local, monkeypatch, [p, sibling], raws)
    rows.append(dict(hunt_status="rejected", reason="listing_ended", reference=None))
    report = hunter_coverage.summarize(rows, fetched=20, retained=7)
    assert report["denominators"] == dict(
        fetched=20,
        retained=7,
        eligible_singles=4,
        lots=1,
        excluded_products=1,
        matched_identities=2,
        admitted_references=2,
        complete_comparisons=0,
        conditional_opportunities=2,
    )
    assert sum(report["primary_outcomes"].values()) == 7
    assert report["reason_counts"]["unknown_tax"] == 4
    assert report["reason_counts"]["unknown_shipping"] == 1
    assert report["reason_counts"]["lot_contents_review"] == 1
    assert report["reason_counts"]["unsupported_product"] == 1
    assert report["reason_counts"]["locally_rejected"] == 1
    assert report["reasons_overlap"] is True and report["reason_denominator"] == "retained"
    # Aggregate reports contain only code-owned labels/counts, not listing/source content.
    assert "Gholdengo" not in str(report) and "example.test" not in str(report)


@pytest.mark.parametrize(
    "title,expected",
    [
        ("Gholdengo ex English Unlimited Non Holo", "missing_set_claim"),
        ("Paradox Rift Gholdengo ex English Unlimited Non Holo", "missing_number_claim"),
        ("Paradox Rift Gholdengo ex #252/198 English Unlimited Non Holo", "literal_number_conflict"),
        ("Paradox Rift Gholdengo ex #252/182 English Japanese", "language_conflict"),
        ("Paradox Rift Gholdengo ex #252/182 Unlimited First Edition", "edition_conflict"),
        ("Paradox Rift Gholdengo ex #252/182 Non Holo Reverse Holo", "finish_conflict"),
        ("Paradox Rift Gholdengo ex #252/182 NM LP", "condition_conflict"),
        ("Paradox Rift Gholdengo ex #252/182 CGC 8.5", "grading_conflict"),
    ],
)
def test_identity_gaps_and_adversarial_claims_explain_their_local_reason(local, monkeypatch, title, expected):
    p = printing("modern")
    row = project(local, monkeypatch, [p], [listing(p, title=title)])[0]
    assert row["reference"] is None
    assert expected in codes(row)


@pytest.mark.parametrize(
    "reason,status,expected",
    [
        ("Missing observation for this exact printing and grade", "active_snapshot", "missing_reference"),
        ("Reference date is older than 30 days", "active_snapshot", "stale_reference"),
        (
            "Reference date missing; capture date cannot establish freshness",
            "active_snapshot",
            "missing_reference_date",
        ),
        ("Reference date is in the future", "active_snapshot", "future_reference_date"),
        ("Withdrawn source", "withdrawn_snapshot", "withdrawn_reference"),
        ("Expired source", "expired_snapshot", "expired_reference"),
        ("No available source", "sources_unavailable", "unavailable_reference_source"),
        ("Private snapshot is invalid or unreviewed", "invalid_snapshot", "invalid_reference_source"),
        (
            "Claimed condition conflicts with the admitted reference",
            "active_snapshot",
            "inapplicable_reference",
        ),
    ],
)
def test_unavailable_reference_causes_are_separate_without_admitting_one(
    local, monkeypatch, reason, status, expected
):
    p = printing("modern")
    row = project(local, monkeypatch, [p], [listing(p)], records_status=status, reason=reason)[0]
    assert row["reference"] is None and row["opportunity"]["rank"] is None
    assert expected in codes(row)
    assert not row["comparison_diagnostics"]["admitted_reference"]


def test_priced_legacy_status_is_not_counted_as_complete_with_unknown_costs(local, monkeypatch):
    p = printing("modern")
    row = project(local, monkeypatch, [p], [listing(p)])[0]
    assert row["hunt_status"] == "priced"  # Preserved historical reference-disposition contract.
    assert row["comparison_diagnostics"]["admitted_reference"] is True
    assert row["comparison_diagnostics"]["complete_delivered_comparison"] is False
    assert {"unknown_tax", "unknown_other_costs", "incomplete_delivered_cost"} <= codes(row)


def test_complete_comparison_needs_exact_reference_and_explicit_costs_and_bin():
    original = ranking_row("offer")
    row = hunter_ranking.project([original], now=OBSERVED, costs={"offer": {"tax": "0", "other_costs": "0"}})[
        0
    ]
    diagnostic = hunter_coverage.diagnose(row)
    assert diagnostic["complete_delivered_comparison"] is True
    assert diagnostic["conditional_opportunity"] is False
    for changed in (
        dict(original, reference_eligibility="conditional"),
        dict(original, reference=dict(original["reference"], match_status="conditional")),
        dict(original, buying_options=["AUCTION"], current_bid="1.00", buy_now_available=False),
    ):
        result = hunter_ranking.project(
            [changed], now=OBSERVED, costs={"offer": {"tax": "0", "other_costs": "0"}}
        )[0]
        assert hunter_coverage.diagnose(result)["complete_delivered_comparison"] is False
    assert original == ranking_row("offer")


def test_lot_diagnostics_preserve_unknown_contents_and_costs_instead_of_zero():
    values = dict(
        reconciled=False,
        unknown_contents=None,
        unpriced_units=2,
        costs=dict(price="3", shipping="1", tax="", other_costs=""),
        reference_count=1,
    )
    before = deepcopy(values)
    diagnosis = hunter_coverage.lot_diagnostics(**values)
    assert set(diagnosis["codes"]) == {
        "unreconciled_lot_contents",
        "unpriced_lot_contents",
        "unknown_tax",
        "unknown_other_costs",
        "incomplete_delivered_cost",
    }
    assert values == before
    complete = hunter_coverage.lot_diagnostics(
        reconciled=True,
        unknown_contents=0,
        unpriced_units=0,
        costs=dict(price="3", shipping="1", tax="0", other_costs="0"),
        reference_count=1,
    )
    assert complete == dict(codes=[], reasons=[])


def test_legendary_collection_lot_parser_keeps_literal_set_and_quantities():
    p = printing("legendary", "Pikachu", set_name="Legendary Collection", number="86/110", attributes={})
    raw = listing(
        p,
        title="Pokemon lot 2 cards",
        shortDescription="2x Pikachu Legendary Collection 86/110 English Unlimited Non Holo",
    )
    parsed = hunter_lots.parse(raw, [p])
    assert parsed["proposals"][0]["printing_id"] == p["id"]
    assert parsed["proposals"][0]["included_quantity"] == 2


def test_unknown_counts_remain_null_and_bad_denominators_are_rejected():
    report = hunter_coverage.summarize([])
    assert report["denominators"]["fetched"] is None
    assert report["denominators"]["complete_comparisons"] == 0
    with pytest.raises(ValueError, match="match"):
        hunter_coverage.summarize([], retained=1)
    with pytest.raises(ValueError, match="nonnegative"):
        hunter_coverage.summarize([], fetched=True)
    with pytest.raises(ValueError, match="800"):
        hunter_coverage.summarize([{}] * 801)
