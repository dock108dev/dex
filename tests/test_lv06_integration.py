"""LV-06 payload and return integration through the bounded worker, authored inputs."""

import pytest
from test_hunter_lots import entries as entries
from test_hunter_policy import everyday as everyday
from test_lv03_hunt import env as env
from test_lv04_integration import configure
from test_lv05_integration import prices as prices

from pokemon_hunter.beta import discovery_catalog, listing_check, lot_hunt


def test_automatic_evidence_remains_in_original_lease_and_no_read_acquires(env, entries, prices, monkeypatch):
    configure(env, entries, monkeypatch)
    run, result = env.execute()
    before_calls = list(env.calls)
    assert len(before_calls) == 5
    for row in result["results"]:
        value = row["lot_value"]
        assert value["assessment_version"] == "dex-lot-value-v3"
        assert row["value_order"]["schema"] == "dex-lot-order-v1"
        assert value["source_fields"]
        assert all(card["name"] for card in value["cards"])
        assert row["evidence_kind"] == "seller_details"
        assert row["observed_at"] and row["expires_at"]
    preview = listing_check.candidate(env.actor, "session", run.id, result["results"][0]["id"])
    assert "proposals" not in preview["listing"]["seller_contents"]
    assert sum(p["quantity"] for p in preview["listing"]["proposals"]) == 3
    assert {p["id"] for line in preview["listing"]["contents"] for p in line["candidates"]} == {
        p["id"] for p in entries
    }
    reread = lot_hunt.status(env.actor, "session", run.id)
    assert reread["expires_in_seconds"] <= result["expires_in_seconds"]
    assert env.calls == before_calls
    prices.clear()
    withdrawn = lot_hunt.status(env.actor, "session", run.id)
    assert all(r["lot_value"]["total"] is None for r in withdrawn["results"])
    assert all(r["lot_value"]["source_fields"] for r in withdrawn["results"])
    assert all(r["value_order"]["combined"]["group"] == "unpriced" for r in withdrawn["results"])
    assert env.calls == before_calls


@pytest.mark.parametrize("basis", ["all", "guide", "sold_estimate", "mixed", "native"])
def test_local_basis_filter_is_supported_return_state(basis):
    discovery_catalog.validate_page(dict(value_basis=basis, buying_mode="buy_now", time_window="72"))


def test_unrecognized_basis_is_not_a_provider_or_return_parameter():
    with pytest.raises(ValueError):
        discovery_catalog.validate_page(dict(value_basis="acquire_more"))
