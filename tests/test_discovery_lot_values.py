"""Offline lot-result arithmetic and uncertainty; no provider or customer data."""

from datetime import UTC, datetime, timedelta

import pytest
from test_hunter_lots import entries as entries
from test_hunter_lots import local as local
from test_hunter_lots import raw

from pokemon_hunter.beta import discovery_listing, discovery_lot_values


def project(local, **changes):
    actor, _ = local
    source = raw(**changes)
    rows = discovery_listing.received_rows([source])
    discovery_lot_values.project(actor, [source], rows)
    return rows[0]


def test_bid_and_buy_now_have_independent_delivered_comparisons(local):
    row = project(
        local,
        buyingOptions=["AUCTION", "FIXED_PRICE"],
        currentBidPrice=dict(value="2.00", currency="USD"),
        itemEndDate=(datetime.now(UTC) + timedelta(hours=12)).isoformat(),
        price=dict(value="20.00", currency="USD"),
    )
    assert row["delivered_total"] == "3.00"
    assert row["buy_now_delivered_total"] == "21.00"
    value = row["lot_value"]
    assert value["total"] == value["subtotal"] == "25.00"
    assert value["priced_quantity"] == value["stated_quantity"] == 3
    assert value["bid_difference"] == "22.00"
    assert value["buy_now_difference"] == "4.00"
    assert len(value["cards"]) == 2


@pytest.mark.parametrize(
    "changes",
    [dict(shippingOptions=[]), dict(shippingOptions=[dict(shippingCost=dict(value="1.00", currency="EUR"))])],
)
def test_unknown_or_foreign_shipping_never_becomes_a_discount(local, changes):
    row = project(local, **changes)
    assert row["lot_value"]["total"] == "25.00"
    assert row["delivered_total"] is row["buy_now_delivered_total"] is None
    assert row["lot_value"]["bid_difference"] is row["lot_value"]["buy_now_difference"] is None


def test_incomplete_lot_shows_subtotal_without_value_ranking(local):
    value = project(local, title="Pokemon lot of 37 cards")["lot_value"]
    assert value["subtotal"] == "25.00"
    assert value["total"] is value["bid_difference"] is value["buy_now_difference"] is None
    assert value["stated_quantity"] == 37


def test_title_mention_never_invents_quantity_or_whole_lot_value(local):
    value = project(
        local, title="Charizard Base Set 4/102 English Unlimited Non Holo lot", shortDescription=""
    )["lot_value"]
    assert value["subtotal"] is value["total"] is None
    assert value["priced_quantity"] == 0


def test_missing_bid_does_not_substitute_buy_now(local):
    row = project(local, buyingOptions=["AUCTION", "FIXED_PRICE"])
    assert row["current_bid"] is row["delivered_total"] is None
    assert row["buy_now_delivered_total"] == "4.00"
    assert row["lot_value"]["bid_difference"] is None
    assert row["lot_value"]["buy_now_difference"] == "21.00"


def test_withdrawn_references_remove_values_and_differences(local):
    assert project(local)["lot_value"]["total"] == "25.00"
    local[1]["references"] = False
    value = project(local)["lot_value"]
    assert value["total"] is value["subtotal"] is None
    assert value["references"] == []
    assert value["bid_difference"] is value["buy_now_difference"] is None


def test_local_value_display_contract():
    import shutil
    import subprocess
    from pathlib import Path

    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required for shipped result presentation")
    root = Path(__file__).resolve().parents[1]
    subprocess.run(
        [
            node,
            str(root / "tests/discovery_values_ui.cjs"),
            str(root / "src/pokemon_hunter/beta/static/discovery-values.js"),
        ],
        check=True,
        timeout=30,
        capture_output=True,
        text=True,
    )


def test_complete_pre2000_contents_survive_in_recommendation(local, monkeypatch):
    from pokemon_hunter.beta import lot_recommendations, species_scope

    monkeypatch.setattr(species_scope, "release_dates", lambda: {"base": {"end": "1999-12-31"}})
    row = project(local)
    assert row["lot_value"]["all_pre_2000"]
    lot_recommendations.rank([row])
    assert row["buying_order"]["combined"]["all_pre_2000"]
    assert not project(local, title="Pokemon lot of 37 cards")["lot_value"]["all_pre_2000"]
