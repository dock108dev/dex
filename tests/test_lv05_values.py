"""Authored independent LV-05 arithmetic, ordering and integration expectations.

No provider calls or customer data. Sample prices are not real source coverage.
"""

from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
from test_hunter_lots import entries as entries
from test_hunter_lots import local as local
from test_hunter_lots import raw
from test_lv02_native_consumers import REFERENCE_CELLS, native_rows

from pokemon_hunter.beta import discovery_comparison as dc
from pokemon_hunter.beta import (
    discovery_listing,
    discovery_lot_values,
    hunter_lots,
    listing_prices,
    lot_assessment,
    lot_calculator,
    shopping_math,
    sold_estimates,
)
from pokemon_hunter.beta import valuation_evidence as evidence


@pytest.fixture
def priced(local, entries, monkeypatch):
    for p in entries:
        p["catalog_version"] = "authored-v1"
    records = native_rows(entries)
    for i, row in enumerate(records):
        row.pop("_native_context")
        row.update(
            value="10" if i == 0 else "5",
            condition=None,
            as_of=datetime.now(lot_calculator.shopping.TZ).date().isoformat(),
        )
        row["evidence"] = dict(
            schema=evidence.SCHEMA,
            basis="guide",
            condition=None,
            amount_basis="item_excluding_shipping_tax",
            sales=[],
            estimate=None,
        )
    monkeypatch.setattr(dc, "_reference_cells", REFERENCE_CELLS)
    monkeypatch.setattr(lot_calculator, "retained_records", lambda: records)
    return local[0], records


def project(actor, sources):
    rows = discovery_listing.received_rows(sources)
    discovery_lot_values.project(actor, sources, rows)
    return rows


def sold_row(guide):
    row = deepcopy(guide)
    now = datetime.now(UTC)
    sales = [
        dict(
            origin="authored",
            sale_id=str(i),
            identity=row["identity"],
            grade="raw",
            condition=None,
            sold_at=(now - timedelta(days=1)).isoformat(),
            captured_at=now.isoformat(),
            amount="12",
            shipping="999",
            currency="USD",
            quantity=1,
            amount_basis="item_excluding_shipping_tax",
            price_semantics="transaction_amount",
            accepted_offer=False,
            accepted_amount_known=False,
            source_url="https://example.test/sale",
        )
        for i in range(12)
    ]
    estimate = sold_estimates.estimate(sales, row["identity"], now=now)
    row.update(
        observation_id="authored-sold",
        value=estimate["value"],
        estimate_kind="dex_sold_estimate",
        as_of=(now - timedelta(days=1)).date().isoformat(),
        captured_at=now.isoformat(),
    )
    row["evidence"].update(basis="sold_estimate", sales=sales, estimate=estimate)
    return row


def test_sold_first_mixed_provenance_and_guide_fallback(priced):
    actor, records = priced
    records.append(sold_row(records[0]))
    value = project(actor, [raw()])[0]["lot_value"]
    # 2 * 12 + 1 * 5; neither twelve postage quotes nor guide + sales are added.
    assert value["total"] == "29.00" and value["buy_now_difference"] == "25.00"
    assert value["basis_label"] == "Mixed"
    sold = next(r for r in value["references"] if r["basis"] == "sold_estimate")
    assert sold["printing_id"] == "charizard" and sold["method"]["method"] == "median"
    assert sold["sample"]["unique_sales"] == 12 and sold["sample"]["excluded"] == {}
    assert sold["sample"]["sold_from"] == sold["sample"]["sold_through"]
    assert "range" not in value and "spread" not in value
    records[-1]["valuation_qualification"] = "engineering_only"
    value = project(actor, [raw()])[0]["lot_value"]
    assert value["total"] == "25.00" and value["basis_label"] == "Guide"
    records[-1]["valuation_qualification"] = "reviewed"
    records[-1]["condition"] = "LP"
    value = project(actor, [raw()])[0]["lot_value"]
    assert value["total"] == "25.00" and value["basis_label"] == "Guide"


@pytest.mark.parametrize("shipping,expected", [("0", "23.00"), ("2.25", "20.75"), (None, None)])
def test_free_unknown_shipping_negative_dual_and_missing_bid(priced, shipping, expected):
    actor, _ = priced
    source = raw(
        buyingOptions=["AUCTION", "FIXED_PRICE"],
        currentBidPrice={"value": "2", "currency": "USD"},
        itemEndDate=(datetime.now(UTC) + timedelta(hours=12)).isoformat(),
        price={"value": "40", "currency": "USD"},
        shippingOptions=[]
        if shipping is None
        else [{"shippingCost": {"value": shipping, "currency": "USD"}}],
    )
    value = project(actor, [source])[0]["lot_value"]
    assert value["bid_difference"] == expected
    assert value["buy_now_difference"] == {"0": "-15.00", "2.25": "-17.25", None: None}[shipping]
    assert value["benchmark_costs"]["auction"]["tax"] == "unknown"
    source.pop("currentBidPrice")
    value = project(actor, [source])[0]["lot_value"]
    assert value["bid_difference"] is None
    assert value["buy_now_difference"] == {"0": "-15.00", "2.25": "-17.25", None: None}[shipping]


@pytest.mark.parametrize("field", ["price", "shipping"])
def test_incompatible_money_blocks_only_cost_comparison(priced, field):
    actor, _ = priced
    source = raw()
    (source["price"] if field == "price" else source["shippingOptions"][0]["shippingCost"])["currency"] = (
        "EUR"
    )
    value = project(actor, [source])[0]["lot_value"]
    assert value["total"] == "25.00"
    assert value["buy_now_difference"] is None


def test_decimal_rounds_after_sum_and_rejects_above_cap():
    source = raw(
        price={"value": "0.005", "currency": "USD"},
        shippingOptions=[{"shippingCost": {"value": "0.005", "currency": "USD"}}],
    )
    result = listing_prices.benchmark_costs(source, total="1.00")["buy_it_now"]
    assert result["delivered_before_tax"] == "0.01" and result["difference"] == "0.99"
    source["price"]["value"] = str(shopping_math.CAP)
    source["shippingOptions"][0]["shippingCost"]["value"] = "1"
    result = listing_prices.benchmark_costs(source, total="1.00")["buy_it_now"]
    assert result["delivered_before_tax"] is None and result["difference"] is None
    assert result["issues"]["total"] == "cost_total_above_cap"


def test_partial_unknown_and_incompatible_reference_preserve_contents(priced):
    actor, records = priced
    records[1]["currency"] = "EUR"
    value = project(actor, [raw(title="Pokemon lot of 37 cards")])[0]["lot_value"]
    assert value["subtotal"] == "20.00" and value["total"] is None
    assert value["benchmark_costs"]["buy_it_now"]["subtotal_difference"] == "16.00"
    assert value["buy_now_difference"] is None
    assert (
        value["identified_quantity"],
        value["priced_quantity"],
        value["identified_unpriced_quantity"],
        value["unidentified_quantity"],
    ) == (3, 2, 1, 34)
    assert len(value["cards"]) == 2
    records.clear()
    row = project(actor, [raw()])[0]
    assert row["lot_value"]["identified_quantity"] == 3 and row["lot_value"]["subtotal"] is None
    assert row["value_order"]["lanes"]["buy_it_now"]["group"] == "unpriced"


def test_condition_specific_reference_requires_matching_condition(priced):
    actor, records = priced
    for record in records:
        record["condition"] = "LP"
    assert project(actor, [raw()])[0]["lot_value"]["subtotal"] is None
    assert project(actor, [raw(condition="")])[0]["lot_value"]["subtotal"] is None
    assert project(actor, [raw(condition="Lightly Played")])[0]["lot_value"]["total"] == "25.00"


def test_independent_lane_order_and_partial_group(priced):
    actor, _ = priced
    now = datetime.now(UTC)

    def offer(n, bid, bin_price, **changes):
        return raw(
            itemId=f"v1|{123456789010 + n}|0",
            buyingOptions=["AUCTION", "FIXED_PRICE"],
            currentBidPrice={"value": bid, "currency": "USD"},
            price={"value": bin_price, "currency": "USD"},
            itemEndDate=(now + timedelta(hours=12)).isoformat(),
            **changes,
        )

    sources = [
        offer(1, "1", "40"),
        offer(2, "8", "10"),
        offer(3, "50", "50"),
        offer(4, "0", "0", title="37-card lot"),
        offer(5, "1", "1", shippingOptions=[]),
    ]
    rows = project(actor, sources)

    def order(lane):
        return [row["item_id"] for row in sorted(rows, key=lambda r: r["value_order"]["lanes"][lane]["rank"])]

    assert order("auction") == [sources[i]["itemId"] for i in [0, 1, 2, 3, 4]]
    assert order("buy_it_now") == [sources[i]["itemId"] for i in [1, 0, 2, 3, 4]]
    partial = rows[3]["value_order"]["lanes"]["buy_it_now"]
    assert partial["score"] == "24.00" and partial["group"] == "partial"
    assert partial["meaning"] == "identified_subtotal_difference_not_whole_lot_score"
    assert rows[2]["value_order"]["lanes"]["buy_it_now"]["score"] == "-26.00"
    reversed_rows = project(actor, list(reversed(sources)))
    assert {r["item_id"]: r["value_order"] for r in rows} == {
        r["item_id"]: r["value_order"] for r in reversed_rows
    }


@pytest.mark.parametrize(
    "end,lanes",
    [
        (72, {"auction", "buy_it_now"}),
        (72.0001, {"buy_it_now"}),
        (0, set()),
        (-1, set()),
        ("bad", set()),
        (None, {"buy_it_now"}),
    ],
)
def test_exact_lane_boundaries_invalid_and_ended(priced, end, lanes):
    actor, _ = priced
    now = datetime.now(UTC)
    source = raw(buyingOptions=["AUCTION", "FIXED_PRICE"], currentBidPrice={"value": "2", "currency": "USD"})
    if end is not None:
        source["itemEndDate"] = (
            (now + timedelta(hours=end)).isoformat() if isinstance(end, (int, float)) else end
        )
    rows = project(actor, [source])
    discovery_lot_values.rank(rows, [source], now=now)
    assert set(rows[0]["value_order"]["lanes"]) == lanes


def test_manual_correction_quantities_reuses_shared_benchmark(priced, local, entries):
    actor, _ = priced
    initial = hunter_lots.analyze(actor, "session", "run", "result")
    corrected = hunter_lots.correct(
        actor,
        "session",
        initial["review_id"],
        dict(
            revision=initial["revision"],
            cards=[dict(printing_id="charizard", quantity=3)],
            unknown_contents=0,
        ),
    )
    assert corrected["comparison"]["result"]["full_lot_total"] == "30.00"
    assert corrected["comparison"]["benchmark_costs"]["buy_it_now"]["difference"] == "26.00"
    assert corrected["review"]["costs"]["tax"] == ""
    assert corrected["expires_in_seconds"] == initial["expires_in_seconds"]
    assert corrected["comparison"]["complete_delivered_comparison"] is False
    # The benchmark does not loosen the strict ceiling selector.
    sold = sold_row(priced[1][0])
    ref, reason = lot_assessment.applicable(
        entries[0], dict(grade="raw", condition="NM"), [sold], datetime.now(UTC).date()
    )
    assert ref is None and reason


def test_native_and_normalized_cohorts_never_pool(priced, entries):
    actor, records = priced
    records[:] = native_rows(entries)
    records[1]["_native_context"] = dict(records[1]["_native_context"], provider="other-authored")
    value = project(actor, [raw()])[0]["lot_value"]
    assert value["total"] is value["subtotal"] is value["buy_now_difference"] is None
    assert value["native_priced_quantity"] == 3 and value["normalized_priced_quantity"] == 0
    assert len(value["native_guides"]) == 2 and all(g["total"] is None for g in value["native_guides"])
    assert sorted(g["subtotal"] for g in value["native_guides"]) == ["10.00", "20.00"]


def test_source_specific_withdrawal_fallback_and_publication_race(priced, monkeypatch):
    actor, records = priced
    sale = sold_row(records[0])
    records.append(sale)
    source = raw()
    assert project(actor, [source])[0]["lot_value"]["total"] == "29.00"
    records.remove(sale)
    assert project(actor, [source])[0]["lot_value"]["total"] == "25.00"
    records.pop(0)
    value = project(actor, [source])[0]["lot_value"]
    assert value["subtotal"] == "5.00" and value["identified_quantity"] == 3
    checks = []
    rows = discovery_listing.received_rows([source])
    discovery_lot_values.project(actor, [source], rows, _checks=checks)
    records.clear()
    with pytest.raises(ValueError, match="Contributing reference changed"):
        for check in checks:
            check()


def test_alternatives_never_select_by_price(priced, entries):
    actor, _ = priced
    source = raw(shortDescription="2x Charizard Base Set 4/102; 1x Blastoise Base Set 2/102")
    value = project(actor, [source])[0]["lot_value"]
    assert value["identified_quantity"] == 0 and value["priced_quantity"] == 0
    assert value["total"] is value["subtotal"] is None
    assert "range" not in value
    assert len(value["contents"]) == 2


def test_fractional_reference_difference_rounds_once(priced):
    actor, records = priced
    records[0]["value"] = "0.005"
    records[1]["value"] = "0.005"
    source = raw(
        price={"value": "0.005", "currency": "USD"},
        shippingOptions=[{"shippingCost": {"value": "0", "currency": "USD"}}],
    )
    value = project(actor, [source])[0]["lot_value"]
    assert value["total"] == "0.02"  # display of 0.015
    assert value["buy_now_difference"] == "0.01"  # exact 0.015 - 0.005


def test_manual_quantity_mismatch_cannot_promote_to_full(priced):
    actor, _ = priced
    initial = hunter_lots.analyze(actor, "session", "run", "result")
    value = hunter_lots.correct(
        actor,
        "session",
        initial["review_id"],
        dict(
            revision=initial["revision"],
            cards=[dict(printing_id="charizard", quantity=4)],
            unknown_contents=0,
        ),
    )
    assert value["comparison"]["result"]["known_selected_subtotal"] == "40.00"
    assert value["comparison"]["result"]["full_lot_total"] is None
    assert not value["comparison"]["quantities_reconciled"]
    assert value["comparison"]["benchmark_costs"]["buy_it_now"]["difference"] is None


def test_order_ties_use_coverage_oldest_date_end_and_stable_identity():
    now = datetime(2026, 11, 4, 12, tzinfo=UTC)
    specs = [
        ("identity-z", 2, "2026-11-02", 12),
        ("identity-a", 2, "2026-11-02", 12),
        ("older", 2, "2026-11-01", 1),
        ("earlier", 2, "2026-11-02", 2),
        ("more-covered", 3, "2026-10-20", 24),
    ]
    sources, rows = [], []
    for identity, count, oldest, end in specs:
        source = raw(
            itemId=identity,
            buyingOptions=["AUCTION", "FIXED_PRICE"],
            itemEndDate=(now + timedelta(hours=end)).isoformat(),
        )
        sources.append(source)
        row = discovery_listing.received_rows([source])[0]
        row["lot_value"] = dict(
            total="20",
            subtotal="20",
            priced_quantity=count,
            references=[dict(as_of="2026-11-04"), dict(as_of=oldest)],
            benchmark_costs={
                lane: dict(difference="10", subtotal_difference=None, delivered_before_tax="10")
                for lane in ("auction", "buy_it_now")
            },
        )
        rows.append(row)
    discovery_lot_values.rank(rows, sources, now=now)
    assert [
        r["item_id"] for r in sorted(rows, key=lambda r: r["value_order"]["lanes"]["auction"]["rank"])
    ] == ["more-covered", "earlier", "identity-a", "identity-z", "older"]
    assert [
        r["item_id"] for r in sorted(rows, key=lambda r: r["value_order"]["lanes"]["buy_it_now"]["rank"])
    ] == ["more-covered", "earlier", "identity-a", "identity-z", "older"]
    # BIN tie has no auction countdown in its audit key.
    assert all(r["value_order"]["lanes"]["buy_it_now"]["end_time"] is None for r in rows)


def test_native_cohort_order_is_separate_and_partial_never_wins(priced, entries):
    actor, records = priced
    records[:] = native_rows(entries)
    sources = [
        raw(itemId="a", title="37-card lot"),
        raw(itemId="b"),
        raw(
            itemId="c",
            title="1-card lot",
            shortDescription="1x Charizard Base Set 4/102 English Unlimited Non Holo",
        ),
    ]
    rows = project(actor, sources)
    order = sorted(rows, key=lambda r: r["value_order"]["native"][0]["rank"])
    assert [r["item_id"] for r in order] == ["b", "c", "a"]
    assert all(r["value_order"]["lanes"]["buy_it_now"]["score"] is None for r in rows)
    assert all(r["lot_value"]["benchmark_costs"]["buy_it_now"]["difference"] is None for r in rows)


@pytest.mark.parametrize("bad", [None, [], {}, 1])
def test_malformed_shipping_currency_is_unknown(bad):
    source = raw(shippingOptions=[dict(shippingCost=dict(value="1", currency=bad))])
    cost = listing_prices.benchmark_costs(source, total="25")["buy_it_now"]
    assert cost["delivered_before_tax"] is cost["difference"] is None


def test_invalid_availability_cannot_publish_comparison(priced):
    actor, _ = priced
    source = raw(estimatedAvailabilities=[dict(estimatedAvailabilityStatus={})])
    row = project(actor, [source])[0]
    assert row["value_order"]["lanes"] == {}
    assert row["lot_value"]["buy_now_difference"] is None
