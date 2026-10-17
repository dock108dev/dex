"""Offline opportunity meanings, equivalent costs and admission lifecycle."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from itertools import permutations

import pytest
from price_snapshot_helpers import NOW, package, stage
from price_snapshot_helpers import b2 as b2
from price_snapshot_helpers import env as env
from price_snapshot_helpers import setup as setup
from price_snapshot_helpers import shop as shop
from price_snapshot_helpers import snapshot as snapshot

from pokemon_hunter.beta import hunter_catalog, hunter_ranking, lot_calculator, price_snapshots

OBSERVED = datetime(2026, 10, 16, 12, tzinfo=UTC)


def row(key, *, price="10.00", shipping="2.00", reference="50.00", **changes):
    ref = (
        dict(
            amount=reference,
            currency="USD",
            as_of="2026-10-15",
            match_status="exact",
            source_version="fixture",
        )
        if reference is not None
        else None
    )
    result = dict(
        item_id=key,
        discovery_kind="single",
        identity_status="matched",
        reference_eligibility="eligible",
        reference=ref,
        buying_options=["FIXED_PRICE"],
        buy_now_available=True,
        buy_now_price=price,
        current_bid=None,
        minimum_next_bid=None,
        shipping=shipping,
        tax=None,
        other_costs=None,
        reason="Admitted fixture; physical card unverified",
        identity_uncertainties=[],
    )
    return dict(result, **changes)


def scenarios(result):
    return {scenario["kind"]: scenario for scenario in result["opportunity"]["scenarios"]}


def project(*rows, **options):
    return hunter_ranking.project(list(rows), now=OBSERVED, **options)


def test_known_shipping_changes_ranking_and_gaps_use_the_reference_denominator():
    expensive_shipping = row("shipping-high", price="1.00", shipping="40.00")
    cheaper_delivered = row("shipping-low", price="10.00", shipping="0.00")
    result = project(expensive_shipping, cheaper_delivered)
    assert [r["item_id"] for r in result] == ["shipping-low", "shipping-high"]
    first, second = [scenarios(r)["buy_it_now"] for r in result]
    assert [r["opportunity"]["rank"] for r in result] == [1, 2]
    assert first["cost_basis"] == "listing_and_shipping_subtotal"
    assert first["gap"]["amount"] == "40.00" and first["gap"]["percent"] == "80.00"
    assert second["gaps"]["listing_amount"]["amount"] == "49.00"
    assert second["gap"]["amount"] == "9.00" and second["gap"]["percent"] == "18.00"
    assert first["gap"]["percent_denominator"] == "reference_amount"
    assert first["complete_delivered_cost"] is None
    assert first["unknown_cost_components"] == ["tax", "other_costs"]
    assert "not_resale_ev" in first["meaning"]


def test_unknown_shipping_and_conditional_identity_have_separate_rank_groups():
    results = project(
        row("known"),
        row("unknown", shipping=None, reference_eligibility="conditional"),
        row(
            "conditional", reference_eligibility="conditional", identity_uncertainties=["Finish needs review"]
        ),
    )
    values = {r["item_id"]: scenarios(r)["buy_it_now"] for r in results}
    assert len({s["rank_group"] for s in values.values()}) == 3
    assert all(s["rank"] == 1 for s in values.values())
    unknown = values["unknown"]
    assert unknown["cost_basis"] == "listing_amount"
    assert unknown["listing_and_shipping_subtotal"] is None
    assert unknown["gap"]["amount"] == "40.00"
    assert unknown["unknown_cost_components"] == ["shipping", "tax", "other_costs"]
    conditional = next(r for r in results if r["item_id"] == "conditional")
    assert conditional["opportunity"]["identity_uncertainties"] == ["Finish needs review"]


def test_complete_delivered_cost_requires_explicit_known_zero_and_all_costs_affect_gap():
    original = row("offer")
    complete = scenarios(project(original, costs={"offer": {"tax": "3.00", "other_costs": "0"}})[0])[
        "buy_it_now"
    ]
    assert complete["complete_delivered_cost"] == "15.00"
    assert complete["delivered_cost_complete"] is True
    assert complete["gap"]["amount"] == "35.00" and complete["gap"]["percent"] == "70.00"
    assert complete["gaps"]["listing_and_shipping_subtotal"]["amount"] == "38.00"
    assert complete["cost_basis"] == "complete_delivered_cost"
    assert complete["unknown_cost_components"] == []
    partial = scenarios(project(original, costs={"offer": {"tax": "3.00"}})[0])["buy_it_now"]
    assert partial["complete_delivered_cost"] is None
    assert partial["cost_basis"] == "known_cost_subtotal"
    assert partial["known_cost_subtotal"] == "15.00" and partial["gap"]["amount"] == "35.00"
    assert original["tax"] is None and original["other_costs"] is None


def test_mixed_offer_bin_auction_minimum_and_manual_bid_are_separate_scenarios():
    source = row(
        "mixed",
        price="60.00",
        buying_options=["AUCTION", "FIXED_PRICE"],
        current_bid="5.00",
        minimum_next_bid="5.50",
    )
    result = project(source, planned_bids={"mixed": "12.00"})[0]
    values = scenarios(result)
    assert list(values) == list(hunter_ranking.SCENARIOS)
    assert values["buy_it_now"]["gap"]["amount"] == "-12.00"
    assert values["buy_it_now"]["rank"] is None
    assert values["buy_it_now"]["offer_meaning"] == "currently_available_buy_it_now"
    assert values["current_bid"]["gap"]["amount"] == "43.00"
    assert values["minimum_next_bid"]["gap"]["amount"] == "42.50"
    assert values["planned_manual_bid"]["gap"]["amount"] == "36.00"
    assert all(values[k]["offer_meaning"] == "auction_scenario" for k in list(values)[1:])
    assert len({v["rank_group"] for v in values.values()}) == 4
    assert result["opportunity"]["primary_scenario"] == "buy_it_now"
    assert result["opportunity"]["rank"] is None
    assert result["planned_manual_bid"] == "12.00" and result["final_purchase_price"] is None
    assert all(v["final_purchase_price"] is None for v in values.values())
    assert not any("recommended" in key or "bid_limit" in key for v in values.values() for key in v)


@pytest.mark.parametrize("kind", ["ambiguous", "conflicting", "unavailable", "unmatched"])
def test_identity_conflicts_and_ambiguity_never_rank_even_if_reference_is_present(kind):
    result = project(row("offer", identity_status=kind))[0]
    scenario = scenarios(result)["buy_it_now"]
    assert result["opportunity"]["rank"] is None
    assert result["opportunity"]["unranked_reason"] == "no_applicable_reference"
    assert scenario["gap"]["amount"] is None and scenario["reference_amount"] is None


@pytest.mark.parametrize("kind", ["mixed_lot", "unsupported"])
def test_lot_and_unsupported_rows_remain_visible_without_single_reference_rank(kind):
    result = project(row("offer", discovery_kind=kind))[0]
    assert result["item_id"] == "offer"
    assert result["opportunity"]["rank"] is None
    assert scenarios(result)["buy_it_now"]["reference_amount"] is None


@pytest.mark.parametrize("reference", [None, "0.00"])
def test_missing_and_zero_reference_percentage_is_unknown(reference):
    result = scenarios(project(row("offer", reference=reference))[0])["buy_it_now"]
    assert result["gap"]["percent"] is None
    assert result["gap"]["percent_status"] == (
        "missing_reference" if reference is None else "nonpositive_reference"
    )
    assert result["rank"] is None


def test_missing_listing_amount_never_ranks_known_shipping_as_a_purchase_cost():
    result = scenarios(project(row("offer", price=None))[0])["buy_it_now"]
    assert result["known_cost_subtotal"] is None and result["comparison_cost"] is None
    assert result["gap"]["amount"] is None and result["gap"]["percent_status"] == "missing_cost"
    assert result["rank"] is None


def test_deterministic_ties_preserve_exact_variation_identity_and_every_unpriced_row():
    source = [row("v1|123|2"), row("v1|123|1"), row("ambiguous", reference=None)]
    expected = project(*source)
    for permutation in permutations(source):
        assert project(*permutation) == expected
    assert {r["item_id"] for r in expected} == {r["item_id"] for r in source}
    assert [r["opportunity"]["rank"] for r in expected] == [1, 2, None]


def test_read_projection_discards_previous_ranks_after_reference_loss_staleness_or_expiry():
    prior = project(row("offer"))[0]
    assert prior["opportunity"]["rank"] == 1
    for reference in (
        None,
        dict(prior["reference"], as_of="2026-08-01"),
        dict(prior["reference"], expires_at=OBSERVED.isoformat()),
    ):
        changed = dict(prior, reference=reference)
        current = project(changed)[0]
        assert current["opportunity"]["rank"] is None
        scenario = scenarios(current)["buy_it_now"]
        assert scenario["reference_amount"] is None and scenario["reference_as_of"] is None
        assert scenario["gap"]["amount"] is None and scenario["gap"]["percent"] is None


def test_reference_age_uses_the_same_local_date_as_shopping_at_utc_midnight():
    source = row("offer")
    source["reference"]["as_of"] = "2026-09-16"
    result = hunter_ranking.project([source], now=datetime(2026, 10, 17, 1, tzinfo=UTC))[0]
    assert result["opportunity"]["rank"] == 1


def test_chunk_merge_reranks_without_reading_catalog_or_references():
    first = project(*[row(str(i), price="20.00") for i in range(400)])
    second = project(row("better", price="10.00"))
    merged = hunter_ranking.order(first + second)
    assert len(merged) == 401 and merged[0]["item_id"] == "better"
    assert [r["opportunity"]["rank"] for r in merged] == list(range(1, 402))


@pytest.mark.parametrize("value", ["-1", "NaN", "1e2", "1000000000001", "1.0000001", 5, True])
def test_manual_money_inputs_reuse_shopping_admission(value):
    with pytest.raises(ValueError):
        project(row("offer"), costs={"offer": {"tax": value}})


def test_subcent_manual_costs_use_shopping_exact_arithmetic_before_rounding():
    result = scenarios(project(row("offer", price="0.005", shipping="0.005", reference="0.01"))[0])[
        "buy_it_now"
    ]
    assert result["listing_and_shipping_subtotal"] == "0.01"
    assert result["gap"]["amount"] == "0.00"
    assert result["gaps"]["listing_amount"]["amount"] == "0.00"


def test_limits_and_no_implicit_manual_bid_or_unknown_override_keys():
    with pytest.raises(ValueError, match="400"):
        project(*[row(str(i)) for i in range(401)])
    with pytest.raises(ValueError, match="aware"):
        hunter_ranking.project([], now=datetime(2026, 10, 16))
    with pytest.raises(ValueError, match="shipping"):
        project(row("offer"), costs={"offer": {"guessed_tax": "0"}})
    with pytest.raises(ValueError, match="item-keyed"):
        project(row("offer"), planned_bids=[])
    with pytest.raises(ValueError, match="item-keyed"):
        project(row("offer"), costs=[])
    result = project(row("offer"), planned_bids={"offer": "3"})[0]
    assert result["planned_manual_bid"] is None
    assert list(scenarios(result)) == ["buy_it_now"]


@pytest.mark.parametrize("withdrawn", [False, True])
def test_catalog_integration_clears_derived_rank_on_real_snapshot_lifecycle(setup, monkeypatch, withdrawn):
    value = package(setup, permanent=False)
    price_snapshots.activate(stage(value), None, now=NOW)
    printing = setup["entries"][value["records"][0]["printing_id"]]
    raw = dict(
        itemId="fixture-offer",
        title=f"{printing['set_name']} {printing['name']} {printing['collector_number']} English Unlimited Non Holo",
        condition="Near Mint",
        buyingOptions=["FIXED_PRICE"],
        price=dict(value="1", currency="USD"),
        shippingOptions=[dict(shippingCostType="FIXED", shippingCost=dict(value="0", currency="USD"))],
    )
    before = hunter_catalog.compare(setup["actor"], [deepcopy(raw)], now=NOW)[0]
    assert before["opportunity"]["rank"] == 1
    assert before["opportunity"]["source_reason"] == before["reason"]
    assert scenarios(before)["buy_it_now"]["reference_as_of"] == "2026-10-09"
    monkeypatch.setattr(lot_calculator, "legacy_records", lambda: [])
    if withdrawn:
        price_snapshots.remove(value["version"])
    else:
        price_snapshots.purge_expired(now=NOW + timedelta(days=2))
    after = hunter_catalog.compare(setup["actor"], [raw], now=NOW)[0]
    assert after["reference"] is None and after["opportunity"]["rank"] is None
    assert scenarios(after)["buy_it_now"]["reference_amount"] is None
