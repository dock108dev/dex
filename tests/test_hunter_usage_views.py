"""Ordinary owner usage settings use real private session/CSRF boundaries, offline."""

import json

import pytest
from django.conf import settings
from test_b1 import env as env
from test_b2 import b2 as b2
from test_lot_calculator import post
from test_lot_calculator import workspace as workspace
from test_migration import snapshot as snapshot
from test_shopping import shop as shop

from pokemon_hunter.beta import ebay_hunts, hunter, hunter_policy

URL = "/api/shopping/hunter/usage/"


@pytest.fixture(autouse=True)
def policy_root(workspace, monkeypatch):
    # Django setup is process-global; bind this file authority to each fresh
    # disposable account root rather than the first fixture's settings root.
    monkeypatch.setattr(settings, "ROOT", workspace["root"])


def selection(**changes):
    return dict(
        enabled=True,
        per_hunt_limit=5,
        daily_limit=12,
        timezone="America/New_York",
        recurring=False,
        expires_at=None,
        revision=0,
        **changes,
    )


def forbidden(*args, **kwargs):
    pytest.fail("Usage settings must not enter provider configuration or acquisition")


def test_missing_owner_settings_are_blank_disabled_private_and_read_only(workspace, monkeypatch):
    monkeypatch.setattr(ebay_hunts, "configuration", forbidden)
    monkeypatch.setattr(hunter, "start", forbidden)
    root = settings.ROOT
    assert not (root / hunter_policy.CONFIG_NAME).exists()
    assert workspace["client"]().get(URL).status_code == 302
    response = workspace["a"].get(URL)
    assert response.status_code == 200
    value = response.json()
    assert value["configured"] is False and value["enabled"] is False
    assert value["per_hunt_limit"] is None and value["daily_limit"] is None
    assert value["remaining"] == 0 and value["revision"] == 0
    assert value["authority"]["account_id"] == workspace["actor"].user_id
    assert "no-store" in response.headers["Cache-Control"]
    page = workspace["a"].get("/shopping/hunter/").content.decode()
    assert 'id="hunter-usage-form"' in page
    assert 'id="hunter-usage-per-hunt" type="number" min="1" max="15"' in page
    assert 'id="hunter-usage-daily" type="number" min="1" max="1000"' in page
    assert 'value="">Choose a timezone' in page
    assert 'value="">Choose once or recurring' in page
    assert 'value="">Choose an expiry' in page
    assert not any(
        (root / name).exists()
        for name in (hunter_policy.CONFIG_NAME, hunter_policy.JOURNAL_NAME, hunter_policy.LOCK_NAME)
    )


def test_owner_selection_requires_csrf_and_preserves_revision_and_usage(workspace, monkeypatch):
    monkeypatch.setattr(ebay_hunts, "configuration", forbidden)
    monkeypatch.setattr(hunter, "start", forbidden)
    denied = workspace["a"].post(URL, json.dumps(selection()), content_type="application/json")
    assert denied.status_code == 403
    assert not (settings.ROOT / hunter_policy.CONFIG_NAME).exists()
    saved = post(workspace, URL, selection())
    assert saved.status_code == 200, saved.content
    value = saved.json()
    assert value["configured"] and value["enabled"]
    assert value["revision"] == 1 and value["remaining"] == 12
    assert value["next_window_at"] is None
    assert value["authority"]["account_id"] == workspace["actor"].user_id
    paused = post(workspace, URL, {**selection(), "enabled": False, "revision": 1})
    assert paused.status_code == 200
    assert paused.json()["remaining"] == 0 and not paused.json()["enabled"]
    assert post(workspace, URL, selection()).status_code == 400
    assert workspace["a"].get(URL).json()["revision"] == 2
    assert hunter_policy.status(workspace["actor"])["used"] == 0


def test_usage_cannot_read_or_select_another_account(workspace, monkeypatch):
    monkeypatch.setattr(ebay_hunts, "configuration", forbidden)
    assert workspace["b"].get(URL).status_code == 403
    assert post(workspace, URL, selection(), client=workspace["b"]).status_code == 403
    page = workspace["b"].get("/shopping/hunter/")
    assert page.status_code == 200 and b'id="hunter-usage-form"' not in page.content
    assert not (settings.ROOT / hunter_policy.CONFIG_NAME).exists()


@pytest.mark.parametrize(
    "changes",
    [
        {"per_hunt_limit": 16},
        {"daily_limit": 0},
        {"per_hunt_limit": True},
        {"daily_limit": "12"},
        {"recurring": "true"},
        {"enabled": 1},
        {"timezone": "Unknown/Place"},
        {"root": "/another-root"},
        {"account_id": "another-account"},
        {"provider_url": "https://example.invalid"},
    ],
)
def test_server_rejects_malformed_or_replacement_authority(workspace, changes):
    response = post(workspace, URL, {**selection(), **changes})
    assert response.status_code == 400
    assert not (settings.ROOT / hunter_policy.CONFIG_NAME).exists()
    assert not (settings.ROOT / hunter_policy.JOURNAL_NAME).exists()


def test_usage_rejects_query_and_malformed_storage_without_replacement(workspace):
    assert workspace["a"].get(URL, {"account_id": "another-account"}).status_code == 400
    path = settings.ROOT / hunter_policy.CONFIG_NAME
    path.write_text("PRIVATE_MALFORMED_POLICY_CANARY")
    path.chmod(0o600)
    response = workspace["a"].get(URL)
    assert response.status_code == 200
    assert response.json()["configured"] and not response.json()["acquisition_available"]
    assert "unavailable" in response.json()["reason"]
    assert "PRIVATE_MALFORMED_POLICY_CANARY" not in response.content.decode()
    assert post(workspace, URL, selection()).status_code == 400
    assert path.read_text() == "PRIVATE_MALFORMED_POLICY_CANARY"


def test_inaccessible_settings_return_private_recovery_without_echoing_storage(workspace, monkeypatch):
    def inaccessible(*args):
        raise OSError("PRIVATE_STORAGE_CANARY")

    monkeypatch.setattr(hunter_policy, "select", inaccessible)
    response = post(workspace, URL, selection())
    assert response.status_code == 400
    assert response.json()["code"] == "hunter_usage_unavailable"
    assert "Check availability" in response.json()["error"]
    assert "PRIVATE_STORAGE_CANARY" not in response.content.decode()
    assert "no-store" in response.headers["Cache-Control"]
    assert response.json()["authority"]["account_id"] == workspace["actor"].user_id
