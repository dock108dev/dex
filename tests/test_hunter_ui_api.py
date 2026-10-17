"""Offline Hunter UI authority, image binding and correction provenance."""

import uuid
from copy import deepcopy

import pytest
from test_b1 import env as env
from test_b2 import b2 as b2
from test_hunter_lots import entries as entries
from test_hunter_lots import local as local
from test_lot_calculator import workspace as workspace
from test_migration import snapshot as snapshot
from test_shopping import shop as shop

from pokemon_hunter.beta import (
    collection,
    discovery,
    ebay_hunts,
    hunter,
    hunter_budget,
    hunter_lots,
    hunter_query,
    image_bindings,
)


def forbidden(*args, **kwargs):
    pytest.fail("A local Hunter UI read must not enter provider configuration or dispatch")


def test_disabled_metadata_is_explicit_and_does_not_probe_configuration(workspace, monkeypatch):
    monkeypatch.setattr(ebay_hunts, "configuration", forbidden)
    monkeypatch.setattr(hunter_budget, "TRAVERSAL_ALLOWANCE", None)
    response = workspace["a"].get("/api/shopping/hunter/")
    assert response.status_code == 200
    value = response.json()
    assert value["acquisition_available"] is False
    assert "No marketplace search has run" in value["acquisition_unavailable_reason"]
    assert "all years and generations" in value["scope_label"]
    assert value["traversal_remaining"] == dict.fromkeys(hunter_budget.TRAVERSAL_LIMIT_KEYS, 0)
    assert "no-store" in response.headers["Cache-Control"]


def test_home_uses_safe_json_bound_authority_and_has_no_acquisition(workspace, monkeypatch):
    monkeypatch.setattr(ebay_hunts, "configuration", forbidden)
    monkeypatch.setattr(hunter, "start", forbidden)
    monkeypatch.setattr(hunter, "metadata", lambda *args: {"acquisition_unavailable_reason": "</script>"})
    assert workspace["client"]().get("/shopping/hunter/").status_code == 302
    response = workspace["a"].get("/shopping/hunter/")
    assert response.status_code == 200
    assert "no-store" in response.headers["Cache-Control"]
    page = response.content.decode()
    assert 'id="hunter-initial"' in page and "\\u003C/script\\u003E" in page
    assert workspace["actor"].user_id in page
    assert "csrfmiddlewaretoken" in page
    assert response.headers["Content-Security-Policy"].count("assets.tcgdex.net") == 1
    assert (
        workspace["a"].get("/shopping/hunter/", {"provider_url": "https://example.test"}).status_code == 400
    )


def test_result_images_use_checked_existing_adapter_and_account_authority(workspace, monkeypatch):
    printing = collection.catalog(workspace["actor"], include_archived=True)[0]
    marker = dict(role="card_reference", availability="reference", image_url="https://assets.tcgdex.net/test")
    calls = []

    def artwork(actor, entries):
        assert actor.user_id == workspace["actor"].user_id
        assert entries == [printing]
        calls.append("authorized_image_adapter")
        return {printing["id"]: marker}

    monkeypatch.setattr(image_bindings, "catalog_images", artwork)
    monkeypatch.setattr(ebay_hunts, "configuration", forbidden)
    monkeypatch.setattr(
        hunter,
        "status",
        lambda *args, **kwargs: dict(
            results=[
                dict(id="opaque", proposed_identity=dict(printing_id=printing["id"]), identity_candidates=[])
            ],
            result_cursor="local-only",
            result_page=dict(offset=0, returned=1, total=1),
        ),
    )
    response = workspace["a"].get("/api/shopping/hunter/", {"run_id": str(uuid.uuid4())})
    assert response.status_code == 200
    value = response.json()
    assert value["results"][0]["proposed_identity"]["artwork"] == marker
    assert value["result_cursor"] == "local-only"
    assert value["authority"]["account_id"] == workspace["actor"].user_id
    assert calls == ["authorized_image_adapter"]


def test_invalid_result_cursor_has_private_recovery_code_without_acquisition(workspace, monkeypatch):
    def invalid(*args, **kwargs):
        assert kwargs["cursor"] == "previous-projection"
        raise hunter.InvalidResultCursor

    monkeypatch.setattr(hunter, "status", invalid)
    monkeypatch.setattr(hunter, "continue_run", forbidden)
    response = workspace["a"].get(
        "/api/shopping/hunter/", {"run_id": str(uuid.uuid4()), "cursor": "previous-projection"}
    )
    assert response.status_code == 400
    value = response.json()
    assert value["code"] == "invalid_result_cursor"
    assert "first local page" in value["error"]
    assert value["authority"]["account_id"] == workspace["actor"].user_id
    assert "no-store" in response.headers["Cache-Control"]


def test_optional_image_descriptors_do_not_breach_response_bound(workspace, monkeypatch):
    printing = collection.catalog(workspace["actor"], include_archived=True)[0]
    monkeypatch.setattr(
        image_bindings,
        "catalog_images",
        lambda *args: {printing["id"]: dict(image_url="https://assets.tcgdex.net/" + "X" * 10000)},
    )
    monkeypatch.setattr(
        hunter,
        "status",
        lambda *args, **kwargs: dict(
            padding="X" * (hunter_query.RESPONSE_BYTE_LIMIT - 5000),
            results=[dict(proposed_identity=dict(printing_id=printing["id"]))],
        ),
    )
    response = workspace["a"].get("/api/shopping/hunter/", {"run_id": str(uuid.uuid4())})
    assert response.status_code == 200
    assert len(response.content) < hunter_query.RESPONSE_BYTE_LIMIT
    value = response.json()
    assert "artwork" not in value["results"][0]["proposed_identity"]
    assert "bounded response" in value["image_binding_status"]


def test_local_catalog_all_era_corrections_have_images_without_prices(workspace, monkeypatch):
    original = collection.catalog(workspace["actor"], include_archived=True)[0]
    modern = dict(original, id="modern-trainer", name="Professor Turo's Scenario", set_name="Paradox Rift")
    energy = dict(original, id="modern-energy", name="Basic Lightning Energy", set_name="Scarlet & Violet")
    archived = dict(modern, id="archived", publication_state="archived")
    monkeypatch.setattr(hunter_lots, "_catalog", lambda *args: [modern, energy, archived])
    monkeypatch.setattr(image_bindings, "catalog_images", lambda *args: {})
    monkeypatch.setattr(ebay_hunts, "configuration", forbidden)
    for term, expected in (
        ("", {modern["id"], energy["id"]}),
        ("Turo", {modern["id"]}),
        ("Energy", {energy["id"]}),
    ):
        response = workspace["a"].get("/api/shopping/hunter/catalog/", {"q": term})
        assert response.status_code == 200
        value = response.json()
        assert {row["id"] for row in value["cards"]} == expected
        assert value["total"] == len(expected)
        assert all("artwork" in row and "reference" not in row for row in value["cards"])
        assert "no-store" in response.headers["Cache-Control"]
    for params in ({"q": "x" * 161}, {"q": "bad\x00text"}, {"q": "", "scope": "vintage"}):
        assert workspace["a"].get("/api/shopping/hunter/catalog/", params).status_code == 400


def test_image_resolution_rechecks_generation_before_private_publication(workspace, monkeypatch):
    printing = collection.catalog(workspace["actor"], include_archived=True)[0]
    state = dict(generation=1)
    monkeypatch.setattr(collection, "generation", lambda *args: state["generation"])
    monkeypatch.setattr(
        hunter,
        "status",
        lambda *args, **kwargs: dict(results=[dict(proposed_identity=dict(printing_id=printing["id"]))]),
    )

    def changed(*args):
        state["generation"] = 2
        return {printing["id"]: dict(image_url="https://assets.tcgdex.net/test")}

    monkeypatch.setattr(image_bindings, "catalog_images", changed)
    response = workspace["a"].get("/api/shopping/hunter/", {"run_id": str(uuid.uuid4())})
    assert response.status_code == 409
    assert b"assets.tcgdex" not in response.content


def test_correction_contract_distinguishes_inherited_and_explicit_traits(local):
    actor, _ = local
    initial = hunter_lots.analyze(actor, "session", "run", "result")
    assert initial["review"]["cards"][0]["language"] == "en"
    assert initial["correction_contract"]["explicit_card_attributes"] == {}
    cards = [
        dict(printing_id=card["printing_id"], quantity=card["quantity"])
        for card in initial["review"]["cards"]
    ]
    quantity_only = hunter_lots.correct(
        actor, "session", initial["review_id"], dict(revision=1, cards=cards, unknown_contents=0)
    )
    assert quantity_only["correction_contract"]["explicit_card_attributes"] == {
        card["printing_id"]: [] for card in cards
    }
    cards[0]["condition"] = "LP"
    corrected = hunter_lots.correct(
        actor, "session", initial["review_id"], dict(revision=2, cards=cards, unknown_contents=None)
    )
    assert corrected["correction_contract"]["explicit_card_attributes"][cards[0]["printing_id"]] == [
        "condition"
    ]
    assert corrected["review"]["unknown_contents"] is None


def test_detail_intent_reads_captured_capacity_without_dispatch_or_renewal(local, monkeypatch, tmp_path):
    actor, state = local
    captured = hunter_budget.TraversalAllowance("hunt-04-ui-intent-test", oauth=1, detail=1, total=2, lots=1)
    monkeypatch.setattr(discovery, "_owner", lambda *args: (str(tmp_path), actor.user_id, "session"))
    monkeypatch.setattr(
        hunter,
        "summary_lease",
        lambda *args, **kwargs: dict(
            raw=deepcopy(state["raw"]), created=state["created"], expires_in_seconds=1700, _allowance=captured
        ),
    )
    monkeypatch.setattr(ebay_hunts, "configuration", forbidden)
    monkeypatch.setattr(hunter_budget, "consume_traversal", forbidden)
    target = hunter_budget.traversal_path(tmp_path, captured)
    result = hunter_lots.detail_intent(actor, "session", "run", ["result"])
    assert result["enabled"] and result["dispatch_allowed"]
    assert result["ledger_identity"] == captured.id
    assert result["remaining_capacity"]["detail"] == 1
    assert not result["intent_grants_capacity"] and not result["lease_renews"]
    assert result["original_lease_remaining_seconds"] == 1700
    assert not target.exists()


def test_navigation_and_image_reads_leave_customer_records_unchanged(workspace, monkeypatch):
    before = collection.export_data(workspace["actor"])
    monkeypatch.setattr(ebay_hunts, "configuration", forbidden)
    assert workspace["a"].get("/shopping/hunter/").status_code == 200
    assert workspace["a"].get("/api/shopping/hunter/").status_code == 200
    assert workspace["a"].get("/api/shopping/hunter/catalog/", {"q": ""}).status_code == 200
    assert collection.export_data(workspace["actor"]) == before
