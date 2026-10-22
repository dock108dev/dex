"""Cross-consumer listing policy regressions; supplied engineering bodies only."""

from datetime import UTC, datetime

import pytest

from pokemon_hunter.beta import discovery_comparison, hunter_catalog, hunter_lots, listing_details

REST = "v1|123456789012|0"


def offer(**changes):
    return dict(
        itemId=REST,
        title="Pokemon mixed card lot",
        buyingOptions=["FIXED_PRICE"],
        price={"value": "3.50", "currency": "USD"},
        **changes,
    )


def summary(monkeypatch, raw):
    monkeypatch.setattr(discovery_comparison.store, "verified", lambda actor: actor)
    return discovery_comparison._project(
        object(), [raw], [], [], artwork={}, now=datetime(2026, 10, 20, tzinfo=UTC)
    )[0]


@pytest.mark.parametrize("value", ["1e2", "+1", " 1", "01", 1, True, "1.0000001", "NaN", "-1"])
def test_summary_and_details_use_shopping_decimal_input_contract(monkeypatch, value):
    raw = offer()
    raw["price"]["value"] = value
    assert listing_details.details(REST, raw)["price"]["amount"] is None
    assert summary(monkeypatch, raw)["listing_price"] is None


def test_invalid_shipping_does_not_erase_an_independently_valid_listing_price(monkeypatch):
    raw = offer(shippingOptions=[{"shippingCost": {"value": "9999999999999", "currency": "USD"}}])
    row = summary(monkeypatch, raw)
    details = listing_details.details(REST, raw)
    assert row["listing_price"] == details["price"]["amount"] == "3.50"
    assert row["buy_now_price"] == "3.50"
    assert row["shipping"] is details["shipping"]["amount"] is None
    assert row["delivered_total"] is None


@pytest.mark.parametrize("end", ["", False, 0, 123, "2099-01-01T00:00:00", "9999-12-31T23:59:59-23:00"])
def test_invalid_supplied_end_time_has_one_explicit_failure(end):
    with pytest.raises(ValueError, match="availability could not be resolved"):
        listing_details.details(REST, offer(itemEndDate=end))


@pytest.mark.parametrize(
    "value,expected",
    [("0", "0.00"), ("1.005", "1.00"), ("1.015", "1.02"), ("1000000000000", "1000000000000.00")],
)
def test_supported_amounts_share_rounding_and_limits(monkeypatch, value, expected):
    raw = offer()
    raw["price"]["value"] = value
    assert summary(monkeypatch, raw)["listing_price"] == expected
    assert listing_details.details(REST, raw)["price"]["amount"] == expected
    assert hunter_lots._cost_inputs(raw)["price"] == expected


@pytest.mark.parametrize("value", [None, "1e2", "1000000000001", "1.0000001", "0.25"])
def test_hunter_minimum_bid_and_lot_review_share_admission(monkeypatch, value):
    monkeypatch.setattr(hunter_catalog.collection, "catalog", lambda *a, **kw: [])
    monkeypatch.setattr(hunter_catalog.collection, "generation", lambda actor: 1)
    monkeypatch.setattr(hunter_catalog.store, "verified", lambda actor: actor)
    monkeypatch.setattr(hunter_catalog.store, "rows", lambda *a: [])
    monkeypatch.setattr(hunter_catalog.lot_calculator, "retained_records", lambda: [])
    raw = offer(minimumPriceToBid={"value": value, "currency": "USD"})
    raw["buyingOptions"] = ["AUCTION", "FIXED_PRICE"]
    row = hunter_catalog.compare(object(), [raw], now=datetime(2026, 10, 20, tzinfo=UTC))[0]
    expected = "0.25" if value == "0.25" else None
    assert row["minimum_next_bid"] == hunter_lots._cost_inputs(raw)["minimum_next_bid"] == expected
    assert row["listing_price"] is None  # Buy-now never supplies a missing bid.
    assert row["buy_now_price"] == "3.50"


def test_summary_and_detail_shipping_retain_their_distinct_selection_contracts(monkeypatch):
    raw = offer(
        shippingOptions=[
            {"shippingCost": {"value": "10", "currency": "USD"}},
            {"shippingCost": {"value": "2", "currency": "USD"}},
        ]
    )
    assert summary(monkeypatch, raw)["shipping"] == "2.00"
    assert listing_details.details(REST, raw)["shipping"]["amount"] is None
    assert hunter_lots._cost_inputs(raw)["shipping"] == ""
    raw["shippingOptions"][1]["shippingCost"]["value"] = "10.00"
    assert listing_details.details(REST, raw)["shipping"]["amount"] == "10.00"
    assert hunter_lots._cost_inputs(raw)["shipping"] == "10.00"


@pytest.mark.parametrize("options", [None, [], "unknown", [None, {}]])
def test_unresolved_shipping_never_becomes_free(monkeypatch, options):
    raw = offer(shippingOptions=options)
    assert summary(monkeypatch, raw)["shipping"] is None
    assert listing_details.details(REST, raw)["shipping"]["amount"] is None
    assert hunter_lots._cost_inputs(raw)["shipping"] == ""


def test_foreign_prices_remain_display_only(monkeypatch):
    raw = offer(shippingOptions=[{"shippingCost": {"value": "0", "currency": "GBP"}}])
    raw["price"]["currency"] = "GBP"
    row = summary(monkeypatch, raw)
    assert row["listing_price"] is row["shipping"] is row["delivered_total"] is None
    details = listing_details.details(REST, raw)
    assert details["price"] == {"amount": "3.50", "currency": "GBP"}
    assert details["shipping"] == {"amount": "0.00", "currency": "GBP"}


def test_removed_policy_implementations_and_inert_query_option_stay_absent():
    import inspect

    from pokemon_hunter.beta import discovery, discovery_search, listing_prices

    assert not hasattr(listing_details, "_money")
    assert not hasattr(listing_details, "prices")
    assert not hasattr(hunter_catalog, "_money")
    for module in (listing_details, discovery_comparison, hunter_catalog, hunter_lots):
        assert module.listing_prices is listing_prices
    for function in (discovery.query_plan, discovery_search.submitted_query):
        assert "product_type" not in inspect.signature(function).parameters
