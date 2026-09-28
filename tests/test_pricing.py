from decimal import Decimal

import pytest

from pokemon_hunter.normalize import evaluate


def assess(raw, settings, catalog, now):
    return evaluate(raw, settings, catalog, (18 / 151, 0.8), now)


def test_exact_landed(raw, settings, catalog, now):
    raw["title"] = "80 Pokemon cards Neo Genesis lot"
    raw["price"]["value"] = "54.99"
    raw["shippingOptions"][0]["shippingCost"]["value"] = "6"
    settings.maximum_purchase.fixed_price = None
    x = assess(raw, settings, catalog, now)
    assert x.landed_price == Decimal("60.99")
    assert x.cost_per_card == Decimal("60.99") / 80
    assert x.qualifying


def test_auction_uses_current_bid(raw, settings, catalog, now):
    raw.update(
        buyingOptions=["AUCTION", "FIXED_PRICE"],
        currentBidPrice={"value": "38", "currency": "USD"},
        itemEndDate="2026-09-25T06:00:00Z",
        title="120 Pokemon cards Neo Genesis lot",
    )
    raw["price"]["value"] = "99"
    raw["shippingOptions"][0]["shippingCost"]["value"] = "7"
    x = assess(raw, settings, catalog, now)
    assert x.cost_per_card == Decimal(".375")
    assert x.max_bid == Decimal("53")
    assert x.listing_type == "auction"
    assert x.qualifying


def test_auction_cap(raw, settings, catalog, now):
    raw.update(
        buyingOptions=["AUCTION"],
        currentBidPrice={"value": "34", "currency": "USD"},
        itemEndDate="2026-09-25T06:00:00Z",
        title="200 Pokemon cards Neo Genesis lot",
    )
    raw["shippingOptions"][0]["shippingCost"]["value"] = "12"
    assert assess(raw, settings, catalog, now).max_bid == Decimal("63")


@pytest.mark.parametrize("value,passes", [("50.00", True), ("50.01", False)])
def test_inclusive_threshold(raw, settings, catalog, now, value, passes):
    raw["title"] = "50 Pokemon cards Jungle lot"
    raw["price"]["value"] = value
    raw["shippingOptions"][0]["shippingCost"]["value"] = "0"
    assert assess(raw, settings, catalog, now).qualifying is passes


@pytest.mark.parametrize("change", ["shipping", "currency", "count", "expired", "bid", "cap", "url"])
def test_reject_unknown_and_over_budget(raw, settings, catalog, now, change):
    if change == "shipping":
        raw.pop("shippingOptions")
    elif change == "currency":
        raw["price"]["currency"] = "GBP"
    elif change == "count":
        raw["title"] = "6 Pokemon cards Neo lot"
    elif change == "expired":
        raw["itemEndDate"] = "2026-01-01T00:00:00Z"
    elif change == "bid":
        raw.update(buyingOptions=["AUCTION"], itemEndDate="2026-10-01T00:00:00Z")
    elif change == "cap":
        raw["price"]["value"] = "60"
    else:
        raw["itemWebUrl"] = "https://ebay.com.evil.invalid/item"
    assert not assess(raw, settings, catalog, now).qualifying


def test_neo_ranks_above_kanto(raw, settings, catalog, now):
    neo = assess(raw, settings, catalog, now)
    raw["title"] = raw["title"].replace("Neo Genesis", "Base Jungle Fossil")
    kanto = assess(raw, settings, catalog, now)
    assert neo.pokedex_score > kanto.pokedex_score


def test_unsearched_is_not_evidence(raw, settings, catalog, now):
    before = assess(raw, settings, catalog, now)
    raw["title"] += " unsearched"
    assert assess(raw, settings, catalog, now).pokedex_score == before.pokedex_score
