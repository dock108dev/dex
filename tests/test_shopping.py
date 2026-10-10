"""Fresh three-printing, two-account integration; no owner root or network."""

import copy
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from django.db import connection
from django.http import Http404
from test_b1 import env as env
from test_b2 import apply
from test_b2 import b2 as b2
from test_migration import snapshot as snapshot

from pokemon_hunter.beta import collection, lot_calculator, shopping

NOW = datetime(2026, 10, 9, 12, tzinfo=ZoneInfo("America/New_York"))


@pytest.fixture
def shop(b2, monkeypatch):
    guides = [
        dict(
            card_id="b",
            value="2.55",
            currency="USD",
            as_of="2026-09-27",
            edition="standard",
            grade="raw",
            grader="Guide",
            variant_verified=True,
            source_url="https://example.test/guide",
            basis="Retained synthetic guide",
        )
    ]
    monkeypatch.setattr(shopping, "sources", lambda: (guides, {}))
    monkeypatch.setattr(lot_calculator, "retained_records", lambda: shopping.sources()[0])
    hashes = {shopping.digest(r) for r in guides}
    monkeypatch.setattr(lot_calculator, "admitted_hashes", lambda: hashes)
    shopping.initialize()
    shopping.initialize()
    b2["guides"] = guides
    return b2


def inputs(shop):
    cards = shop["catalog"][:2]
    return dict(
        selected_cards=[
            dict(
                selection_id=str(i),
                printing_id=p["id"],
                quantity=1,
                assumptions="Synthetic identified raw standard card",
                edition="standard",
                condition="LP",
                grade="",
                grader="",
                completion_confirmed=False,
                chosen_value_reference=f"manual-{i}",
            )
            for i, p in enumerate(cards)
        ],
        value_references=[
            dict(
                reference_id=f"manual-{i}",
                kind="manual",
                amount="14",
                currency="USD",
                as_of="2026-10-09",
                assumptions="Synthetic identified raw standard card",
                value_scope="per_card",
            )
            for i in range(2)
        ],
        unknown_contents=dict(quantity=None),
        goal_id="",
        goal_version="",
        listing_observation=dict(
            amount="12",
            currency="USD",
            status="known",
            date="2026-10-09",
            price_kind="current_bid",
            source_url="https://www.ebay.com/itm/synthetic",
        ),
        planned_bid=dict(
            amount="20", currency="USD", status="known", date="2026-10-09", price_kind="personal_planned_bid"
        ),
        delivery_cost_inputs={
            b: {
                c: dict(
                    amount=None, currency="USD", status="unknown", date="2026-10-09", notes="Not supplied"
                )
                for c in ("shipping", "tax", "other_costs")
            }
            for b in ("listing_observation", "planned_bid")
        },
    )


def post(shop, data):
    shop["a"].get("/shopping/")
    return shop["a"].post(
        "/api/shopping/compare/",
        json.dumps(data),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=shop["a"].cookies["dex_b1_csrf"].value,
    )


def test_all_card_owned_research_search_sort_and_private_filters(shop):
    before = collection.export_data(shop["actor"])
    result = shopping.browse(shop["actor"], today=NOW.date())
    assert len(result["cards"]) == 3
    owned = next(c for c in result["cards"] if c["copy_count"])
    assert shopping.browse(shop["actor"], dict(q=owned["collector_number"]), NOW.date())["cards"]
    assert (
        len(shopping.browse(shop["actor"], dict(missing="printing"), NOW.date())["cards"]) == 3
    )  # associated unresolved copies are not exact
    assert len(shopping.browse(shop["actor"], dict(value="available"), NOW.date())["cards"]) == 1
    assert len(shopping.browse(shop["actor"], dict(value="unavailable"), NOW.date())["cards"]) == 2
    sorted_ = shopping.browse(shop["actor"], dict(sort="value_desc"), NOW.date())["cards"]
    assert sorted_[0]["value"] == "2.55"
    assert collection.export_data(shop["actor"]) == before
    with pytest.raises(ValueError, match="policy"):
        shopping.browse(shop["actor"], dict(missing="species"))
    assert shop["client"]().get("/shopping/").status_code == 302


def test_private_save_reopen_separate_current_and_preservation(shop):
    before = collection.export_data(shop["actor"])
    generation = collection.generation(shop["actor"])
    raw = inputs(shop)
    key = shopping.save(shop["actor"], raw, "<Synthetic lot>", now=NOW)
    saved = shopping.reopen(shop["actor"], key)
    assert saved["result"]["full_selected_total"] == "28.00"
    assert saved["result"]["comparisons"]["planned_bid"]["full_selected_reference_minus_base_price"] == "8.00"
    assert (
        collection.export_data(shop["actor"]) == before and collection.generation(shop["actor"]) == generation
    )
    assert not shopping.listing(shop["member"])
    with pytest.raises(Http404):
        shopping.reopen(shop["member"], key)
    assert shop["b"].get(f"/shopping/saved/{key}/").status_code == 404
    original = shopping.one(shop["actor"], key)["snapshot"]
    raw["selected_cards"][0]["quantity"] = 4
    connection.close()
    assert shopping.reopen(shop["actor"], key)["context"]["selected_cards"][0]["quantity"] == 1
    current = shopping.reevaluate(shop["actor"], key)
    later = shopping.reopen(shop["actor"], current)
    assert later["saved"]["parent_id"] == key
    assert later["context"]["context_id"] != saved["context"]["context_id"]
    assert (
        later["context"]["listing_observation"]["observation_id"]
        == saved["context"]["listing_observation"]["observation_id"]
    )
    assert shopping.one(shop["actor"], key)["snapshot"] == original
    assert collection.export_data(shop["actor"]) == before
    page = shop["a"].get(f"/shopping/saved/{key}/")
    assert page.status_code == 200 and b"&lt;Synthetic lot&gt;" in page.content
    assert shop["a"].post(f"/shopping/saved/{key}/current/").status_code == 403
    assert shop["a"].get(f"/shopping/saved/{key}/current/").status_code == 405


def test_csrf_tampering_security_and_recovery(shop):
    raw = inputs(shop)
    assert (
        shop["a"]
        .post("/api/shopping/compare/", json.dumps(dict(inputs=raw)), content_type="application/json")
        .status_code
        == 403
    )
    assert post(shop, dict(inputs=raw)).status_code == 200
    for mutation in ("float", "negative", "quantity", "account", "url", "missing_ref", "assumptions"):
        invalid = copy.deepcopy(raw)
        if mutation == "float":
            invalid["planned_bid"]["amount"] = 20.0
        elif mutation == "negative":
            invalid["value_references"][0]["amount"] = "-1"
        elif mutation == "quantity":
            invalid["selected_cards"][0]["quantity"] = True
        elif mutation == "account":
            invalid["account_id"] = shop["member"].user_id
        elif mutation == "url":
            invalid["listing_observation"]["source_url"] = "https://www.ebay.com@evil.test/itm/x"
        elif mutation == "missing_ref":
            invalid["selected_cards"][0]["chosen_value_reference"] = "forged"
        else:
            invalid["value_references"][0]["assumptions"] = ""
        assert post(shop, dict(inputs=invalid)).status_code == 400, mutation
    assert post(shop, dict(inputs=raw)).status_code == 200
    key = shopping.save(shop["actor"], raw, "integrity", now=NOW)
    original = shopping.one(shop["actor"], key)["snapshot"]
    collection.execute("UPDATE saved_shopping_comparisons SET snapshot=%s WHERE id=%s", [original + " ", key])
    with pytest.raises(ValueError, match="integrity"):
        shopping.reopen(shop["actor"], key)
    collection.execute("UPDATE saved_shopping_comparisons SET snapshot='{}' WHERE id=%s", [key])
    with pytest.raises(ValueError, match="integrity"):
        shopping.reopen(shop["actor"], key)


def test_guide_original_precision_provenance_date_and_missing_reference(shop):
    raw = inputs(shop)
    p = next(c for c in shopping.browse(shop["actor"], today=NOW.date())["cards"] if c["guide"])
    first = raw["selected_cards"][0]
    first["printing_id"] = p["id"]
    first["chosen_value_reference"] = "chosen-guide"
    raw["value_references"][0] = dict(
        reference_id="chosen-guide",
        kind="guide",
        observation_id=p["guide"]["observation_id"],
        printing_id=p["id"],
    )
    saved = shopping.prepare(shop["actor"], raw, now=NOW)
    assert saved["result"]["full_selected_total"] == "16.55"
    assert saved["context"]["value_references"][0]["raw_record"] == shop["guides"][0]
    assert saved["result"]["reference_terms"][0]["as_of"] == "2026-09-27"
    key = shopping.save(shop["actor"], raw, "mixed", now=NOW)
    tampered = copy.deepcopy(raw)
    tampered["value_references"][0]["observation_id"] = "tampered"
    with pytest.raises(ValueError, match="reference"):
        shopping.prepare(shop["actor"], tampered, now=NOW)
    shop["guides"].clear()
    with pytest.raises(ValueError, match="reference"):
        shopping.prepare(shop["actor"], raw, now=NOW)
    current = shopping.reevaluate(shop["actor"], key)
    assert shopping.reopen(shop["actor"], current)["result"]["full_selected_total"] is None
    assert shopping.reopen(shop["actor"], key)["result"]["full_selected_total"] == "16.55"


def test_group_once_changed_quantity_detach_and_known_zero(shop):
    raw = inputs(shop)
    raw["value_references"] = [
        dict(
            reference_id="group",
            kind="manual",
            amount="14",
            currency="USD",
            as_of="2026-10-09",
            assumptions="Both raw standard cards, synthetic",
            value_scope="selection_group_total",
            applies_to_quantities={"0": 1, "1": 1},
        )
    ]
    for s in raw["selected_cards"]:
        s["chosen_value_reference"] = "group"
    result = shopping.prepare(shop["actor"], raw, now=NOW)["result"]
    assert result["full_selected_total"] == "14.00"
    assert result["comparisons"]["listing_observation"]["full_selected_reference_minus_base_price"] == "2.00"
    assert result["comparisons"]["planned_bid"]["full_selected_reference_minus_base_price"] == "-6.00"
    raw["selected_cards"][0]["quantity"] = 2
    assert shopping.prepare(shop["actor"], raw, now=NOW)["result"]["full_selected_total"] is None
    raw["selected_cards"][0]["quantity"] = 1
    raw["selected_cards"][1]["chosen_value_reference"] = None
    assert shopping.prepare(shop["actor"], raw, now=NOW)["result"]["known_selected_subtotal"] is None
    raw["selected_cards"][1]["chosen_value_reference"] = "group"
    raw["value_references"][0]["amount"] = "0"
    assert shopping.prepare(shop["actor"], raw, now=NOW)["result"]["full_selected_total"] == "0.00"


def test_frozen_policy_account_and_version_missing_printing(shop):
    apply(
        shop,
        "goal",
        dict(
            name="Synthetic set catalog",
            goal_kind="set",
            set_id=shop["catalog"][0]["set_id"],
            policy="catalog",
        ),
    )
    g = next(g for g in collection.goals(shop["actor"]) if g["name"] == "Synthetic set catalog")
    raw = inputs(shop)
    raw.update(goal_id=g["id"], goal_version=g["version"])
    for s in raw["selected_cards"]:
        s["completion_confirmed"] = True
    payload = shopping.prepare(shop["actor"], raw, now=NOW)
    assert payload["context"]["frozen_goal"]["owned_item_ids"]
    assert payload["result"]["goal"]["policy"] == "catalog"
    with pytest.raises(Http404):
        shopping.prepare(shop["member"], raw, now=NOW)
    bad = copy.deepcopy(raw)
    bad["goal_version"] = "tampered"
    with pytest.raises(ValueError, match="version"):
        shopping.prepare(shop["actor"], bad, now=NOW)
    collection.execute("UPDATE collection_goals SET version='forged' WHERE id=%s", [g["id"]])
    with pytest.raises(ValueError, match="version"):
        shopping.prepare(shop["actor"], raw, now=NOW)
