"""Actual HTTP/session integration on the disposable legacy-compatible database."""

import json
import uuid
from types import SimpleNamespace

from test_b1 import env as env
from test_b2 import b2 as b2
from test_lot_calculator import workspace as workspace
from test_migration import snapshot as snapshot
from test_shopping import shop as shop

from pokemon_hunter.beta import discovery as d
from pokemon_hunter.beta import hunter_installed, hunter_policy, lot_hunt


def test_ordinary_action_captures_auth_session_and_poll_stop_never_send(workspace, monkeypatch):
    actor = workspace["actor"]
    monkeypatch.setattr(hunter_installed, "package_digest", lambda: "a" * 64)
    hunter_policy.select(
        actor,
        dict(
            enabled=True,
            per_hunt_limit=5,
            daily_limit=10,
            timezone="UTC",
            recurring=False,
            expires_at=None,
            revision=0,
        ),
    )
    monkeypatch.setattr(
        d.ebay_hunts,
        "configuration",
        lambda: (
            SimpleNamespace(environment="production", delivery_postal_code=None),
            dict(EBAY_CLIENT_ID="authored", EBAY_CLIENT_SECRET="authored"),
        ),
    )
    launched = []
    monkeypatch.setattr(lot_hunt, "_launch", lambda *args: launched.append(args))
    client = workspace["a"]
    page = client.get("/shopping/")
    assert b"up to two offers (one per lane)" in page.content
    url = "/api/shopping/discovery/"
    request_id = str(uuid.uuid4())
    data = json.dumps(dict(query="Lapras", acquisition_contract="dex-lot-hunt-v2"))
    assert client.post(url, data, content_type="application/json").status_code == 403
    response = client.post(
        url,
        data,
        content_type="application/json",
        HTTP_X_CSRFTOKEN=client.cookies["dex_b1_csrf"].value,
        HTTP_X_DEX_SHOPPING_ACTION=request_id,
    )
    assert response.status_code == 200, response.content
    key = response.json()["run_id"]
    assert len(launched) == 1 and launched[0][0].auth_session == client.session.session_key
    for query in ({"run_id": key}, {"run_id": key, "view": "values"}, {"request_id": request_id}):
        result = client.get(url, query)
        assert result.status_code == 200, result.content
        assert result.json()["state"] == "queued"
        assert result.headers["Cache-Control"] == "private, no-store"
    other = workspace["b"].get(url, {"run_id": key})
    assert other.status_code == 404
    stopped = client.post(
        url + key + "/stop/",
        "{}",
        content_type="application/json",
        HTTP_X_CSRFTOKEN=client.cookies["dex_b1_csrf"].value,
    )
    assert stopped.status_code == 200 and stopped.json()["state"] == "stopped"
    assert len(launched) == 1 and hunter_policy.status(actor)["used"] == 0


def test_unavailable_policy_has_specific_predispatch_response(workspace):
    client = workspace["a"]
    client.get("/shopping/")
    response = client.post(
        "/api/shopping/discovery/",
        json.dumps(dict(query="Lapras", acquisition_contract="dex-lot-hunt-v2")),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=client.cookies["dex_b1_csrf"].value,
        HTTP_X_DEX_SHOPPING_ACTION=str(uuid.uuid4()),
    )
    assert response.status_code == 409 and response.json()["code"] == "lot_hunt_policy"
    assert "Hunter usage settings" in response.json()["error"]
