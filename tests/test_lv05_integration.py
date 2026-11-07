"""LV-05 through the actual finite worker and temporary review, authored streams only."""

from datetime import datetime

import pytest
from test_hunter_lots import entries as entries
from test_hunter_policy import everyday as everyday
from test_listing_check import review_value
from test_lv02_native_consumers import REFERENCE_CELLS, native_rows
from test_lv03_hunt import env as env
from test_lv04_integration import configure
from test_lv05_values import sold_row

from pokemon_hunter.beta import discovery_comparison as dc
from pokemon_hunter.beta import listing_check, lot_calculator
from pokemon_hunter.beta import lot_hunt as hunt
from pokemon_hunter.beta import valuation_evidence as evidence


@pytest.fixture
def prices(env, entries, monkeypatch):
    for offer in env.bin + env.auction:
        offer["shippingOptions"][0]["shippingCostType"] = "FIXED"
    for p in entries:
        p["catalog_version"] = "authored-v1"
    records = native_rows(entries)
    for i, r in enumerate(records):
        r.pop("_native_context")
        r.update(
            value="10" if i == 0 else "5", as_of=datetime.now(lot_calculator.shopping.TZ).date().isoformat()
        )
        r["evidence"] = dict(
            schema=evidence.SCHEMA,
            basis="guide",
            condition=None,
            amount_basis="item_excluding_shipping_tax",
            sales=[],
            estimate=None,
        )
    records.append(sold_row(records[0]))
    monkeypatch.setattr(dc, "_reference_cells", REFERENCE_CELLS)
    monkeypatch.setattr(lot_calculator, "retained_records", lambda: records)
    return records


def test_automatic_sold_assessment_source_withdrawal_and_correction(env, prices, entries, monkeypatch):
    configure(env, entries, monkeypatch)
    run, result = env.execute()
    assert len(env.calls) == 5 and result["progress"]["ready"] == 2
    assert all(r["lot_value"]["total"] == "29.00" for r in result["results"])
    assert all(r["lot_value"]["basis_label"] == "Mixed" for r in result["results"])
    auction = next(r for r in result["results"] if "auction" in r["value_order"]["lanes"])
    assert auction["lot_value"]["bid_difference"] == "26.00"
    prices.pop()  # only the sold source disappears; valid guides still work
    result = hunt.status(env.actor, "session", run.id)
    assert all(r["lot_value"]["total"] == "25.00" for r in result["results"])
    origin = dict(run_id=run.id, result_id=result["results"][0]["id"])
    preview = listing_check.candidate(env.actor, "session", **origin)
    review = listing_check.review(env.actor, "session")
    correction = review_value(
        entries[0], discovery_origin=origin, unknown_contents=0, price_kind="current_asking_price"
    )
    correction["cards"][0]["quantity"] = 3
    saved = listing_check.review(env.actor, "session", correction, review["lease"])
    changed = listing_check.saved_comparison(env.actor, "session", saved["revision"], saved["lease"])
    assert changed["benchmark"]["result"]["full_lot_total"] == "30.00"
    assert changed["benchmark"]["benchmark_costs"]["buy_it_now"]["difference"] == "26.00"
    assert changed["assessment"]["maximum"] is None
    assert saved["expires_in_seconds"] <= preview["expires_in_seconds"]
    assert len(env.calls) == 5
    prices.clear()
    result = hunt.status(env.actor, "session", run.id)
    assert result["progress"]["ready"] == 0
    assert all(r["lot_value"]["identified_quantity"] == 3 for r in result["results"])
    assert all(r["value_order"]["combined"]["score"] is None for r in result["results"])
    assert len(env.calls) == 5


def test_reference_change_during_final_authority_check_rejects_publication(env, prices, monkeypatch):
    run, _ = env.execute()
    original = hunt._guard
    calls = 0

    def guard(*args, **kwargs):
        nonlocal calls
        original(*args, **kwargs)
        if kwargs.get("acquiring") is False:
            calls += 1
            if calls == 2:
                prices.clear()

    monkeypatch.setattr(hunt, "_guard", guard)
    with pytest.raises(ValueError, match="Contributing reference changed"):
        hunt.status(env.actor, "session", run.id)
    assert len(env.calls) == 5


def test_sold_evidence_mutation_without_amount_change_rejects_publication(env, prices):
    run, _ = env.execute()
    assessment = hunt._assess(env.actor, run, run.raws)
    prices[-1]["evidence"]["sales"][0]["sale_id"] = "changed-contributor"
    with pytest.raises(ValueError, match="Contributing reference changed"):
        for check in assessment["reference_checks"]:
            check()


def test_stop_after_priced_assessment_clears_scores(env, prices, monkeypatch):
    run, _ = env.execute()
    original = hunt._assess

    def assess(*args):
        result = original(*args)
        hunt.stop(env.actor, "session", run.id)
        return result

    monkeypatch.setattr(hunt, "_assess", assess)
    result = hunt.status(env.actor, "session", run.id)
    assert result["state"] == "stopped" and result["results"] == []
    assert len(env.calls) == 5


def test_stop_during_reference_revalidation_cannot_publish(env, prices, monkeypatch):
    run, _ = env.execute()
    original = hunt._assess

    def assess(*args):
        result = original(*args)
        result["reference_checks"].append(lambda: hunt.stop(env.actor, "session", run.id))
        return result

    monkeypatch.setattr(hunt, "_assess", assess)
    result = hunt.status(env.actor, "session", run.id)
    assert result["state"] == "stopped" and result["results"] == []
