"""Discovery HTTP authority, explicit actions and retained calculator navigation."""

import json
import uuid

from test_b1 import env as env
from test_b2 import b2 as b2
from test_lot_calculator import post
from test_lot_calculator import workspace as workspace
from test_migration import snapshot as snapshot
from test_shopping import shop as shop

from pokemon_hunter.beta import discovery


def test_shopping_front_door_and_contextual_calculator(workspace, monkeypatch):
    monkeypatch.setattr(discovery, "start", lambda *args: (_ for _ in ()).throw(AssertionError()))
    page = workspace["a"].get("/shopping/")
    assert page.status_code == 200
    assert page.headers["Cache-Control"] == "private, no-store"
    for label in (b"Find deals", b"Find missing cards", b"Check a listing", b"discovery.js"):
        assert label in page.content
    calculator = workspace["a"].get("/shopping/calculator/")
    assert calculator.status_code == 200 and b"lot_calculator.js" in calculator.content
    assert workspace["a"].get("/shopping/", {"species": "2"}).status_code == 200
    assert workspace["a"].get("/shopping/", {"species": "invalid"}).status_code == 400
    for filename in ("discovery.js", "discovery.css"):
        assert workspace["a"].get("/collection-assets/" + filename).status_code == 200


def test_metadata_and_polling_are_private_reads(workspace, monkeypatch):
    monkeypatch.setattr(discovery, "metadata", lambda actor: {"defaults": {}, "sets": [], "provider": {}})
    metadata = workspace["a"].get("/api/shopping/discovery/")
    assert metadata.status_code == 200 and "goals" in metadata.json()
    assert "no-store" in metadata.headers["Cache-Control"]
    seen = []
    monkeypatch.setattr(discovery, "status", lambda *args: seen.append(args) or {"state": "complete"})
    key = str(uuid.uuid4())
    assert workspace["a"].get("/api/shopping/discovery/", {"run_id": key}).status_code == 200
    assert seen[0][2] == key and seen[0][1]
    assert workspace["a"].get("/api/shopping/discovery/", {"run_id": key, "extra": "1"}).status_code == 400


def test_actions_require_csrf_and_have_bound_session(workspace, monkeypatch):
    seen = []
    monkeypatch.setattr(discovery, "start", lambda *args: seen.append(args) or {"state": "queued"})
    url = "/api/shopping/discovery/"
    assert workspace["a"].post(url, json.dumps({}), content_type="application/json").status_code == 403
    assert not seen
    result = post(workspace, url, {"intent": "deals"})
    assert result.status_code == 200 and seen[0][2] == {"intent": "deals"}
    post(workspace, url, {"intent": "deals"}, client=workspace["b"])
    assert seen[0][0].user_id != seen[1][0].user_id
    assert seen[0][1] != seen[1][1]


def test_stop_and_reveal_accept_no_replacement_data(workspace, monkeypatch):
    calls = []
    monkeypatch.setattr(discovery, "stop", lambda *args: calls.append(args) or {"state": "stopped"})
    monkeypatch.setattr(discovery, "reveal", lambda *args: calls.append(args) or {"state": "complete"})
    key = str(uuid.uuid4())
    stop = f"/api/shopping/discovery/{key}/stop/"
    reveal = f"/api/shopping/discovery/{key}/reveal/result-1/"
    assert post(workspace, stop, {}).status_code == 200
    assert post(workspace, reveal, {}).status_code == 200
    assert len(calls) == 2
    assert post(workspace, stop, {"query": "replacement"}).status_code == 400
    assert post(workspace, reveal, {"query": "replacement"}).status_code == 400
    assert len(calls) == 2


def test_legacy_search_cannot_dispatch(workspace, monkeypatch):
    from django.conf import settings
    from django.urls import clear_url_caches

    # The shared fixture may have loaded its URLconf before parity was enabled.
    from pokemon_hunter.beta import urls

    monkeypatch.setattr(settings, "PARITY_ENABLED", True)
    import importlib

    importlib.reload(urls)
    clear_url_caches()
    from pokemon_hunter.beta import parity
    from pokemon_hunter.beta.discovery_transport import Transport

    assert not hasattr(parity, "search")
    monkeypatch.setattr(Transport, "request", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError()))
    response = post(workspace, "/api/hunts/", {"query": "pokemon"})
    assert response.status_code == 410
    assert response.json()["shopping_url"] == "/shopping/"
