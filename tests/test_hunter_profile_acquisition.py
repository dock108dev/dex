"""Exact finite execution profile joined to Hunter/lot services with fake I/O."""

import asyncio
from copy import deepcopy
from dataclasses import replace

import pytest
from test_hunter import hunt as hunt
from test_hunter_h07_integration import integrated as integrated
from test_hunter_profile import b2 as b2
from test_hunter_profile import env as env
from test_hunter_profile import post
from test_hunter_profile import restricted as restricted
from test_hunter_profile import snapshot as snapshot

from pokemon_hunter.beta import (
    discovery,
    hunter,
    hunter_budget,
    hunter_lot_details,
    hunter_lots,
    hunter_profile,
    store,
)

_STORE_ROWS = store.rows


@pytest.mark.parametrize("plan_id", [hunter_profile.PLAN_ID, hunter_profile.COMPLETION_PLAN_ID])
def test_selected_profile_complete_both_plan_and_selected_details_consume_exact_shared_limits(
    integrated,
    monkeypatch,
    plan_id,
):
    selected = hunter_profile.ExecutionProfile(
        integrated.env.actor.user_id,
        integrated.env.root,
        authorization_check=lambda: None,
        plan_id=plan_id,
    )
    monkeypatch.setattr(hunter_profile, "_configured", selected)
    # Startup/settings integration is qualified separately against a schema-
    # compatible root. This joined service fixture has no Django application.
    monkeypatch.setattr(hunter_profile, "require_current", lambda: selected)
    allowance = hunter_budget.TraversalAllowance(plan_id, **hunter_profile.PLAN_LIMITS)
    monkeypatch.setattr(hunter_budget, "TRAVERSAL_ALLOWANCE", allowance)
    actor = integrated.env.actor
    # Every captured partition returns observations, so the empty-partition
    # optimization does not skip planned pages in this exact-limit exercise.
    integrated.pages[0] = deepcopy(integrated.pages[1])
    first = hunter.start(actor, "binding", {"scope": "both"})
    parent = hunter._runs[first["run_id"]]
    while True:
        asyncio.run(hunter._acquire_traversal(parent, ("fixture-client", "CANARY_SECRET"), actor))
        if parent.next_index == len(parent.traversal.requests):
            break
        hunter.continue_run(
            actor, "binding", parent.id, {"cursor": parent.traversal.cursor(parent.next_index)}
        )
    assert parent.next_index == 12
    current = hunter.status(actor, "binding", parent.id)
    result_ids = [row["id"] for row in current["results"]]
    assert len(result_ids) == 2
    action = hunter_lot_details.start(actor, "binding", parent.id, result_ids)
    detail = hunter_lot_details._runs[action["detail_action_id"]]
    asyncio.run(hunter_lot_details._acquire(detail, actor, "binding", ("fixture-client", "CANARY_SECRET")))
    result = hunter_lot_details.status(actor, "binding", detail.id)
    assert len(result["reviews"]) == 2
    assert [stage for stage, _ in integrated.calls].count("oauth") == 1
    assert [stage for stage, _ in integrated.calls].count("browse") == 12
    assert [stage for stage, _ in integrated.calls].count("detail") == 2
    assert hunter_budget.remaining_traversal(integrated.env.root, allowance) == dict.fromkeys(
        hunter_budget.TRAVERSAL_LIMIT_KEYS,
        0,
    )
    assert not hunter_budget.path(integrated.env.root).exists()
    ledger = hunter_budget.traversal_path(integrated.env.root, allowance).read_text()
    assert len(ledger.splitlines()) == 15
    for private in ("CANARY", "Charizard", "Blastoise", "description", "access_token"):
        assert private not in ledger
    hunter_profile.shutdown()
    assert parent.cancel.is_set() and detail.cancel.is_set()
    assert not parent.raws and not detail.raws
    assert not hunter._runs and not hunter_lot_details._runs


@pytest.mark.parametrize("plan_id", [hunter_profile.PLAN_ID, hunter_profile.COMPLETION_PLAN_ID])
def test_selected_profile_http_hunt_continue_and_detail_join_real_services_with_fake_transport(
    restricted,
    integrated,
    monkeypatch,
    plan_id,
):
    from django.conf import settings

    from pokemon_hunter.beta import hunter_views

    monkeypatch.setattr(hunter_profile, "_configured", replace(hunter_profile.current(), plan_id=plan_id))
    # Keep real HTTP account/session lookup. Only the engineering catalog's game
    # ID and optional artwork are controlled alongside the fake provider bodies.
    monkeypatch.setattr(
        store,
        "rows",
        lambda sql, params=(): (
            [{"id": "pokemon"}]
            if sql == "SELECT id FROM games WHERE game_key='pokemon'"
            else _STORE_ROWS(sql, params)
        ),
    )
    monkeypatch.setattr(discovery, "settings", settings)
    monkeypatch.setattr(hunter_views, "_images", lambda *args: None)
    allowance = hunter_budget.TraversalAllowance(plan_id, **hunter_profile.PLAN_LIMITS)
    monkeypatch.setattr(hunter_budget, "TRAVERSAL_ALLOWANCE", allowance)
    integrated.pages[0] = deepcopy(integrated.pages[1])
    actor = restricted["actor"]
    client = restricted["a"]
    api = "/api/shopping/hunter/"
    started = post(client, api, {"scope": "both"})
    assert started.status_code == 200
    parent = hunter._runs[started.json()["run_id"]]
    assert parent.auth_session == client.session.session_key
    while True:
        asyncio.run(hunter._acquire_traversal(parent, ("fixture-client", "CANARY_SECRET"), actor))
        received = client.get(api, {"run_id": parent.id})
        assert received.status_code == 200
        current = received.json()
        if parent.next_index == 12:
            break
        continuation = post(client, f"{api}{parent.id}/continue/", {"cursor": current["continuation_cursor"]})
        assert continuation.status_code == 200
    chosen = [row["id"] for row in current["results"]]
    assert len(chosen) == 2 and len(integrated.calls) == 13
    assert post(client, f"{api}{parent.id}/analyze-lots/", {"result_ids": chosen}).status_code == 200
    assert post(client, f"{api}{parent.id}/lot-detail-intent/", {"result_ids": chosen}).status_code == 200
    assert len(integrated.calls) == 13
    started_detail = post(client, f"{api}{parent.id}/analyze-lot-details/", {"result_ids": chosen})
    assert started_detail.status_code == 200
    detail = hunter_lot_details._runs[started_detail.json()["detail_action_id"]]
    binding = parent.owner[2]
    asyncio.run(hunter_lot_details._acquire(detail, actor, binding, ("fixture-client", "CANARY_SECRET")))
    loaded = client.get(f"{api}lot-details/{detail.id}/")
    assert loaded.status_code == 200 and len(loaded.json()["reviews"]) == 2
    assert len(integrated.calls) == 15
    assert hunter_budget.remaining_traversal(restricted["root"], allowance) == dict.fromkeys(
        hunter_budget.TRAVERSAL_LIMIT_KEYS,
        0,
    )
    assert post(client, api, {"scope": "both"}).status_code == 400
    assert post(client, f"{api}lot-details/{detail.id}/stop/", {}).status_code == 200
    assert post(client, f"{api}{parent.id}/stop/", {}).status_code == 200
    assert len(integrated.calls) == 15


@pytest.mark.parametrize("during", ["parent_comparison", "detail_parsing", "after_detail_completed"])
def test_authorization_expiry_during_parsing_suppresses_publication_without_refund(
    integrated, monkeypatch, during
):
    valid = True

    def check():
        if not valid:
            raise ValueError("Controlled authorization expiry during local processing")

    selected = hunter_profile.ExecutionProfile(
        integrated.env.actor.user_id,
        integrated.env.root,
        authorization_check=check,
    )
    monkeypatch.setattr(hunter_profile, "_configured", selected)
    monkeypatch.setattr(hunter_profile, "require_current", lambda: selected)
    allowance = hunter_budget.TraversalAllowance(hunter_profile.PLAN_ID, **hunter_profile.PLAN_LIMITS)
    monkeypatch.setattr(hunter_budget, "TRAVERSAL_ALLOWANCE", allowance)
    actor = integrated.env.actor
    started = hunter.start(actor, "binding", {"scope": "lots"})
    parent = hunter._runs[started["run_id"]]
    if during == "parent_comparison":
        original = hunter.hunter_catalog.compare

        def compare(*args, **kwargs):
            nonlocal valid
            result = original(*args, **kwargs)
            valid = False
            return result

        monkeypatch.setattr(hunter.hunter_catalog, "compare", compare)
        with pytest.raises(ValueError, match="authorization expiry"):
            asyncio.run(hunter._acquire_traversal(parent, ("fixture-client", "CANARY_SECRET"), actor))
        assert not parent.raws
        remaining = hunter_budget.remaining_traversal(integrated.env.root, allowance)
        assert remaining["oauth"] == 0 and remaining["browse"] == 10 and remaining["total"] == 12
    else:
        asyncio.run(hunter._acquire_traversal(parent, ("fixture-client", "CANARY_SECRET"), actor))
        received = hunter.status(actor, "binding", parent.id)
        started_detail = hunter_lot_details.start(actor, "binding", parent.id, [received["results"][0]["id"]])
        detail = hunter_lot_details._runs[started_detail["detail_action_id"]]
        original = hunter_lots.parse

        def parse(*args, **kwargs):
            nonlocal valid
            result = original(*args, **kwargs)
            valid = False
            return result

        if during == "detail_parsing":
            monkeypatch.setattr(hunter_lots, "parse", parse)
            with pytest.raises(ValueError, match="authorization expiry"):
                asyncio.run(
                    hunter_lot_details._acquire(detail, actor, "binding", ("fixture-client", "CANARY_SECRET"))
                )
            assert not detail.raws and not hunter_lots._reviews
        else:
            asyncio.run(
                hunter_lot_details._acquire(detail, actor, "binding", ("fixture-client", "CANARY_SECRET"))
            )
            valid = False
            # Completed temporary content remains locally readable after provider
            # authorization ends. Existing account/source/lease checks still run.
            loaded = hunter_lot_details.status(actor, "binding", detail.id)
            assert len(loaded["reviews"]) == 1
            assert hunter.status(actor, "binding", parent.id)["results"]
            hunter_lot_details.stop(actor, "binding", detail.id)
            hunter.stop(actor, "binding", parent.id)
            assert not parent.raws and not detail.raws
        remaining = hunter_budget.remaining_traversal(integrated.env.root, allowance)
        assert remaining["detail"] == 1 and remaining["total"] == 11
