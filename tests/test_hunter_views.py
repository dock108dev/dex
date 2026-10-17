"""Hunter boundary uses normal account authority and CSRF, engineering roots only."""

import json
import uuid

from test_b1 import env as env
from test_b2 import b2 as b2
from test_lot_calculator import post
from test_lot_calculator import workspace as workspace
from test_migration import snapshot as snapshot
from test_shopping import shop as shop

from pokemon_hunter.beta import hunter


def test_authenticated_csrf_bound_start_and_private_metadata(workspace, monkeypatch):
    url = "/api/shopping/hunter/"
    calls = []
    monkeypatch.setattr(hunter, "metadata", lambda *args: {"remaining": {"browse": 2}})
    assert workspace["client"]().get(url).status_code == 302
    result = workspace["a"].get(url)
    assert result.status_code == 200 and "no-store" in result.headers["Cache-Control"]

    def start(*args, auth_session=None):
        calls.append((args, auth_session))
        return {"state": "queued"}

    monkeypatch.setattr(hunter, "start", start)
    assert workspace["a"].post(url, json.dumps({}), content_type="application/json").status_code == 403
    assert not calls
    assert post(workspace, url, {}).status_code == 200
    assert calls[0][0][2] == {} and calls[0][1] == workspace["a"].session.session_key
    assert post(workspace, url, {}, client=workspace["b"]).status_code == 200
    assert calls[0][0][0].user_id != calls[1][0][0].user_id
    assert calls[0][0][1] != calls[1][0][1]


def test_poll_and_independent_stop_no_replacement_inputs(workspace, monkeypatch):
    key = str(uuid.uuid4())
    calls = []
    monkeypatch.setattr(hunter, "status", lambda *args: calls.append(args) or {"state": "complete"})
    monkeypatch.setattr(hunter, "stop", lambda *args: calls.append(args) or {"state": "stopped"})
    url = "/api/shopping/hunter/"
    assert workspace["a"].get(url, {"run_id": key}).status_code == 200
    assert workspace["a"].get(url, {"run_id": key, "extra": "x"}).status_code == 400
    stop = f"{url}{key}/stop/"
    assert post(workspace, stop, {}).status_code == 200
    assert post(workspace, stop, {"query": "x"}).status_code == 400
    assert len(calls) == 2 and calls[0][2] == key


def test_continuation_and_lot_contracts_use_private_csrf_actions(workspace, monkeypatch):
    from pokemon_hunter.beta import hunter_lots

    run = str(uuid.uuid4())
    review = str(uuid.uuid4())
    calls = []
    monkeypatch.setattr(hunter, "continue_run", lambda *args: calls.append(args) or {"state": "queued"})
    monkeypatch.setattr(hunter_lots, "selected_batch", lambda *args: calls.append(args) or {"reviews": []})
    monkeypatch.setattr(hunter_lots, "detail_intent", lambda *args: calls.append(args) or {"enabled": False})
    monkeypatch.setattr(hunter_lots, "read", lambda *args: calls.append(args) or {"review_id": review})
    monkeypatch.setattr(hunter_lots, "correct", lambda *args: calls.append(args) or {"review_id": review})
    base = f"/api/shopping/hunter/{run}/"
    for route, raw in (
        ("continue/", {"cursor": "captured"}),
        ("analyze-lots/", {"result_ids": ["one"]}),
        ("lot-detail-intent/", {"result_ids": ["one"]}),
    ):
        url = base + route
        assert workspace["a"].post(url, json.dumps(raw), content_type="application/json").status_code == 403
        result = post(workspace, url, raw)
        assert result.status_code == 200 and "no-store" in result.headers["Cache-Control"]
    url = f"/api/shopping/hunter/lot-review/{review}/"
    assert workspace["a"].get(url).status_code == 200
    assert post(workspace, url, {"revision": 1}).status_code == 200
    assert workspace["a"].get(url, {"extra": "x"}).status_code == 400
    assert post(workspace, base + "analyze-lots/", {"result_ids": [], "filters": {}}).status_code == 400
    assert len(calls) == 5


def test_explicit_official_lot_detail_start_poll_stop(workspace, monkeypatch):
    from pokemon_hunter.beta import hunter_lot_details

    run, action = str(uuid.uuid4()), str(uuid.uuid4())
    calls = []
    monkeypatch.setattr(hunter_lot_details, "start", lambda *args: calls.append(args) or {"state": "queued"})
    monkeypatch.setattr(
        hunter_lot_details, "status", lambda *args: calls.append(args) or {"state": "complete"}
    )
    monkeypatch.setattr(hunter_lot_details, "stop", lambda *args: calls.append(args) or {"state": "stopped"})
    url = f"/api/shopping/hunter/{run}/analyze-lot-details/"
    assert (
        workspace["a"]
        .post(url, json.dumps({"result_ids": ["one"]}), content_type="application/json")
        .status_code
        == 403
    )
    assert post(workspace, url, {"result_ids": ["one"]}).status_code == 200
    status = f"/api/shopping/hunter/lot-details/{action}/"
    assert workspace["a"].get(status).status_code == 200
    assert post(workspace, status + "stop/", {}).status_code == 200
    assert len(calls) == 3


def test_hunter_response_body_cap(workspace, monkeypatch):
    monkeypatch.setattr(hunter, "metadata", lambda *args: {"oversized": "X" * (2 * 1024 * 1024)})
    response = workspace["a"].get("/api/shopping/hunter/")
    assert response.status_code == 400
    assert len(response.content) < 4096
