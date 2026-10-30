"""HTTP authority and explicit action boundary, with no network calls."""

import json
import uuid

from test_b1 import env as env
from test_b2 import b2 as b2
from test_lot_calculator import post
from test_lot_calculator import workspace as workspace
from test_migration import snapshot as snapshot
from test_shopping import shop as shop

from pokemon_hunter.beta import listing_interpretation as service
from pokemon_hunter.beta import ollama_gateway


def test_readiness_does_not_expose_exception_details(workspace, monkeypatch):
    def unavailable(root):
        raise ollama_gateway.Unavailable("private config /secret/ollama.json token=engineering-secret")

    monkeypatch.setattr(ollama_gateway, "configuration", unavailable)
    response = workspace["a"].get("/api/listing-interpretation/readiness/")
    assert response.status_code == 200
    assert response.json()["configured"] is False
    assert response.json()["message"] == (
        "Local listing analysis is not configured. Manual review remains available."
    )
    assert b"engineering-secret" not in response.content
    assert b"/secret/" not in response.content
    assert "no-store" in response["Cache-Control"]


def test_readiness_configured_without_provider_call(workspace, monkeypatch):
    monkeypatch.setattr(ollama_gateway, "configuration", lambda root: object())
    response = workspace["a"].get("/api/listing-interpretation/readiness/")
    assert response.status_code == 200
    assert response.json()["configured"] is True
    assert "no-store" in response["Cache-Control"]


def test_explicit_action_authority(workspace, monkeypatch):
    calls = []
    monkeypatch.setattr(service, "start", lambda *a: calls.append(a) or dict(id="test", state="running"))
    url = "/api/listing-interpretation/"
    data = dict(kind="hunter", run_id="run", result_id="result")
    assert workspace["a"].get(url).status_code == 405
    assert workspace["a"].post(url, json.dumps(data), content_type="application/json").status_code == 403
    assert not calls
    response = post(workspace, url, data)
    assert response.status_code == 200 and "no-store" in response["Cache-Control"]
    assert calls[0][2] == workspace["a"].session.session_key
    assert post(workspace, url, dict(data, title="injected")).status_code == 400
    assert len(calls) == 1


def test_status_stop_and_asset(workspace, monkeypatch):
    calls = []
    monkeypatch.setattr(service, "read", lambda *a, **kw: calls.append((a, kw)) or dict(state="running"))
    url = "/api/listing-interpretation/" + str(uuid.uuid4()) + "/"
    assert workspace["a"].get(url, {"title": "replacement"}).status_code == 400
    assert workspace["a"].get(url).status_code == 200
    assert calls[-1][1] == {}
    assert post(workspace, url + "stop/", {}).status_code == 200
    assert calls[-1][1] == dict(stop=True)
    assert post(workspace, url + "stop/", {"text": "bad"}).status_code == 400
    assert workspace["a"].get("/collection-assets/listing-interpretation.js").status_code == 200


def test_temporary_review_renderer():
    import subprocess
    from pathlib import Path

    result = subprocess.run(
        ["node", "scripts/test-listing-interpretation.cjs"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
