"""Selected execution profile: disposable state and fake transport/startup only."""

import asyncio
import json
import os
import subprocess
import sys
import threading
import time
import uuid
from types import SimpleNamespace

import pytest
from test_b1 import env as env
from test_b2 import b2 as b2
from test_migration import snapshot as snapshot

from pokemon_hunter.beta import hunter_profile as profile


@pytest.fixture
def restricted(b2, monkeypatch):
    from django.conf import settings
    from django.test import override_settings

    selected = profile.ExecutionProfile(b2["actor"].user_id, b2["root"], authorization_check=lambda: None)
    monkeypatch.setattr(profile, "_configured", selected)
    monkeypatch.setattr(profile, "_started", False)
    middleware = list(settings.MIDDLEWARE)
    auth = "django.contrib.auth.middleware.AuthenticationMiddleware"
    middleware.insert(
        middleware.index(auth) + 1, "pokemon_hunter.beta.hunter_profile.ExpectedAccountMiddleware"
    )
    with override_settings(
        ROOT=b2["root"],
        ROOT_URLCONF="pokemon_hunter.beta.hunter_profile_urls",
        HUNTER_EXECUTION_PROFILE=profile.PROFILE,
        MIDDLEWARE=middleware,
        LOGIN_REDIRECT_URL="/shopping/hunter/",
        LOGOUT_REDIRECT_URL="/login/",
    ):
        # Clients must load the selected middleware chain after profile selection.
        b2["a"].handler._middleware_chain = None
        b2["b"].handler._middleware_chain = None
        yield b2


def post(client, path, raw, *, csrf=True):
    return client.post(
        path,
        json.dumps(raw),
        content_type="application/json",
        **({"HTTP_X_CSRFTOKEN": client.cookies["dex_b1_csrf"].value} if csrf else {}),
    )


def test_profile_selection_is_process_local_before_django_and_has_no_writes(tmp_path):
    root = tmp_path / "engineering"
    root.mkdir()
    code = """
from pathlib import Path
from pokemon_hunter.beta import hunter_profile as p
from django.conf import settings
root = Path(__import__('sys').argv[1])
assert p.current() is None
selected = p.configure('controlled-account', root, configuration_root=root)
assert selected.root == root.resolve() and selected.configuration_root == root.resolve()
assert not settings.configured
try:
    p.configure('replacement-account', root)
except RuntimeError:
    pass
else:
    raise AssertionError('profile reselected')
assert list(root.iterdir()) == []
"""
    completed = subprocess.run(
        [sys.executable, "-c", code, str(root)],
        capture_output=True,
        text=True,
        env={**os.environ, "DEX_PROFILE": "local", "DEX_HUNTER_PROFILE": "ignored"},
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert list(root.iterdir()) == []


@pytest.mark.parametrize("reason", ["root", "staging", "collection"])
def test_settings_reject_mismatch_before_any_worker_or_request(tmp_path, monkeypatch, reason):
    monkeypatch.setattr(profile, "_configured", profile.ExecutionProfile("controlled", tmp_path))
    values = dict(STAGING=False, ROOT=tmp_path, B2_ENABLED=True)
    values[{"root": "ROOT", "staging": "STAGING", "collection": "B2_ENABLED"}[reason]] = {
        "root": tmp_path / "other",
        "staging": True,
        "collection": False,
    }[reason]
    with pytest.raises(RuntimeError, match="verified local collection root"):
        profile.apply_settings(values)
    assert list(tmp_path.iterdir()) == []


def test_settings_integrate_allowlist_and_disable_unselected_features(tmp_path, monkeypatch):
    monkeypatch.setattr(profile, "_configured", profile.ExecutionProfile("controlled", tmp_path))
    auth = "django.contrib.auth.middleware.AuthenticationMiddleware"
    values = dict(
        STAGING=False, ROOT=tmp_path, B2_ENABLED=True, B3_ENABLED=True, B4_ENABLED=True, MIDDLEWARE=[auth]
    )
    profile.apply_settings(values)
    assert values["ROOT_URLCONF"] == "pokemon_hunter.beta.hunter_profile_urls"
    assert values["LOGIN_REDIRECT_URL"] == "/shopping/hunter/"
    assert values["LOGOUT_REDIRECT_URL"] == "/login/"
    assert not values["B3_ENABLED"] and not values["B4_ENABLED"]
    assert values["MIDDLEWARE"] == [auth, "pokemon_hunter.beta.hunter_profile.ExpectedAccountMiddleware"]


def test_normal_signin_csrf_and_expected_account(restricted, monkeypatch):
    from pokemon_hunter.beta import hunter

    monkeypatch.setattr(hunter, "metadata", lambda *args: {"acquisition_available": False})
    guest = restricted["client"]()
    assert guest.get("/shopping/hunter/").status_code == 302
    assert guest.get("/login/").status_code == 200
    assert guest.post("/login/", {"username": "admin", "password": restricted["password"]}).status_code == 403
    result = restricted["login"](guest, "admin", restricted["password"])
    assert result.status_code == 302 and result.url == "/shopping/hunter/"
    assert guest.get("/shopping/hunter/").status_code == 200
    response = guest.get("/api/shopping/hunter/")
    assert response.status_code == 200
    assert {"private", "no-store"} <= set(response.headers["Cache-Control"].replace(" ", "").split(","))
    assert guest.cookies["dex_b1_session"]["httponly"]
    assert guest.cookies["dex_b1_session"]["samesite"] == "Strict"
    assert guest.post("/logout/").status_code == 403
    assert (
        guest.post("/logout/", {"csrfmiddlewaretoken": guest.cookies["dex_b1_csrf"].value}).url == "/login/"
    )
    assert guest.get("/shopping/hunter/").status_code == 302


def test_wrong_account_refused_before_login_session_or_last_login_write(restricted):
    from django.contrib.sessions.models import Session

    other = restricted["second"]
    other.refresh_from_db()
    last_login = other.last_login
    count = Session.objects.count()
    client = restricted["client"]()
    result = restricted["login"](client, "collector", restricted["other_password"])
    assert result.status_code == 200 and "dex_b1_session" not in client.cookies
    other.refresh_from_db()
    assert other.last_login == last_login and Session.objects.count() == count
    assert restricted["b"].get("/shopping/hunter/").status_code == 403
    assert restricted["b"].get("/api/shopping/hunter/").status_code == 403
    assert restricted["b"].get("/collection-assets/hunter.js").status_code == 403


@pytest.mark.parametrize(
    "path",
    [
        "/api/operations/preview/",
        "/api/goals/",
        "/api/binders/",
        "/api/bulk/save/",
        "/api/scans/",
        "/api/photo-batches/create/",
        "/api/shopping/discovery/",
        "/api/shopping/listing/",
        "/packs/refresh/start/",
        "/catalog-pipeline/preview/",
        "/support/delete/",
        "/recovery/",
        "/collection-assets/collection.js",
    ],
)
def test_unselected_routes_refuse_with_no_collection_writes(restricted, path):
    from pokemon_hunter.beta import store

    tables = ("owned_copies", "collection_goals", "collection_operations", "collection_drafts")
    present = {row["name"] for row in store.rows("SELECT name FROM sqlite_master WHERE type='table'")}

    def snapshot():
        return {
            table: store.rows(f"SELECT * FROM {table} ORDER BY rowid") for table in tables if table in present
        }

    before = snapshot()
    assert restricted["a"].get(path).status_code == 404
    assert post(restricted["a"], path, {}).status_code in {404, 405}
    assert snapshot() == before


def test_only_hunter_assets_and_existing_loopback_boundary(restricted):
    client = restricted["a"]
    for asset in profile.ASSETS:
        assert client.get("/collection-assets/" + asset).status_code == 200
    for options in (
        {"HTTP_HOST": "127.0.0.1:8999"},
        {"REMOTE_ADDR": "192.0.2.1"},
        {"HTTP_ORIGIN": "https://unselected.invalid"},
        {"HTTP_X_FORWARDED_FOR": "127.0.0.1"},
    ):
        assert client.get("/shopping/hunter/", **options).status_code == 403


def test_missing_allowance_and_unselected_scope_cannot_start_or_create_ledger(restricted, monkeypatch):
    from pokemon_hunter.beta import hunter, hunter_budget

    monkeypatch.setattr(hunter_budget, "TRAVERSAL_ALLOWANCE", None)
    monkeypatch.setattr(hunter, "start", lambda *a, **kw: pytest.fail("No selected allowance"))
    url = "/api/shopping/hunter/"
    for raw in (
        {},
        {"scope": "singles"},
        {"scope": "lots"},
        {"scope": "both", "root": "elsewhere"},
        {"scope": "both"},
    ):
        assert post(restricted["a"], url, raw).status_code == 400
    assert not (restricted["root"].parent / ".dex-shopping-discovery").exists()
    assert not profile._started


def test_start_is_once_and_cannot_replace_partial_ledger(restricted, monkeypatch):
    from pokemon_hunter.beta import hunter, hunter_budget

    calls = []
    allowance = hunter_budget.TraversalAllowance(profile.PLAN_ID, **profile.PLAN_LIMITS)
    monkeypatch.setattr(hunter_budget, "TRAVERSAL_ALLOWANCE", allowance)
    monkeypatch.setattr(hunter, "start", lambda *args, **kw: calls.append(args) or {"state": "queued"})
    url = "/api/shopping/hunter/"
    assert post(restricted["a"], url, {"scope": "both"}, csrf=False).status_code == 403
    assert not profile._started
    assert post(restricted["a"], url, {"scope": "both"}).status_code == 200
    assert post(restricted["a"], url, {"scope": "both"}).status_code == 400
    assert len(calls) == 1
    monkeypatch.setattr(profile, "_started", False)  # Simulate lost temporary process memory.
    hunter_budget.consume_traversal(
        restricted["root"],
        "fixture-run",
        "browse",
        "auction",
        dispatch_id="fixture-first-page",
        allowance=allowance,
    )
    assert post(restricted["a"], url, {"scope": "both"}).status_code == 400
    assert len(calls) == 1


def test_revocation_is_rechecked_and_configuration_root_is_private_server_choice(
    restricted, monkeypatch, tmp_path
):
    from django.db import connection

    from pokemon_hunter.beta import ebay_hunts

    selected = profile.ExecutionProfile(restricted["actor"].user_id, restricted["root"], tmp_path)
    monkeypatch.setattr(profile, "_configured", selected)
    assert ebay_hunts.configuration_root() == tmp_path
    with connection.cursor() as cursor:
        cursor.execute("UPDATE users SET state='revoked' WHERE id=%s", [selected.account_id])
    assert restricted["a"].get("/api/shopping/hunter/").status_code == 403
    assert restricted["a"].get("/collection-assets/hunter.js").status_code == 403


def test_authorization_withdrawal_blocks_new_actions_but_not_independent_stops(restricted, monkeypatch):
    from pokemon_hunter.beta import hunter, hunter_lot_details

    def revoked():
        raise ValueError("Controlled withdrawn authorization")

    monkeypatch.setattr(
        profile,
        "_configured",
        profile.ExecutionProfile(
            restricted["actor"].user_id,
            restricted["root"],
            authorization_check=revoked,
        ),
    )
    key = str(uuid.uuid4())
    calls = []
    monkeypatch.setattr(hunter, "stop", lambda *args: calls.append("parent") or {"state": "stopped"})
    monkeypatch.setattr(
        hunter_lot_details, "stop", lambda *args: calls.append("detail") or {"state": "stopped"}
    )
    monkeypatch.setattr(hunter, "continue_run", lambda *args: pytest.fail("Withdrawn authorization"))
    monkeypatch.setattr(hunter_lot_details, "start", lambda *args: pytest.fail("Withdrawn authorization"))
    for path, raw in (
        ("/api/shopping/hunter/", {"scope": "both"}),
        (f"/api/shopping/hunter/{key}/continue/", {"cursor": "controlled"}),
        (f"/api/shopping/hunter/{key}/analyze-lot-details/", {"result_ids": ["controlled"]}),
    ):
        assert post(restricted["a"], path, raw).status_code == 400
    assert post(restricted["a"], f"/api/shopping/hunter/{key}/stop/", {}).status_code == 200
    assert post(restricted["a"], f"/api/shopping/hunter/lot-details/{key}/stop/", {}).status_code == 200
    assert calls == ["parent", "detail"] and not profile._started


@pytest.mark.parametrize("withdraw", ["before", "after_admission", "after_response"])
def test_each_dispatch_rechecks_authorization_and_preserves_consumed_attempts(
    restricted, monkeypatch, withdraw
):
    from pokemon_hunter.beta import discovery, hunter_budget
    from pokemon_hunter.beta.discovery_transport import ProviderFailure

    valid = withdraw != "before"

    def check():
        if not valid:
            raise ValueError("Controlled expired authorization")

    monkeypatch.setattr(
        profile,
        "_configured",
        profile.ExecutionProfile(
            restricted["actor"].user_id,
            restricted["root"],
            authorization_check=check,
        ),
    )
    allowance = hunter_budget.TraversalAllowance(profile.PLAN_ID, **profile.PLAN_LIMITS)
    run = discovery.Run(
        "controlled-run",
        (str(restricted["root"]), restricted["actor"].user_id, "binding"),
        discovery.Choices(),
        None,
        [],
        operation="hunter",
        deadline=time.monotonic() + 10,
    )
    journals, sends = [], []
    monkeypatch.setattr(discovery, "_journal", lambda *args, **kw: journals.append((args[1:], kw)))

    def admit(stage):
        nonlocal valid
        hunter_budget.consume_traversal(
            restricted["root"], run.id, stage, "auction", dispatch_id="controlled-send", allowance=allowance
        )
        if withdraw == "after_admission":
            valid = False

    run.admit = admit

    class FakeTransport:
        async def request(self, stage, **kwargs):
            nonlocal valid
            sends.append(stage)
            if withdraw == "after_response":
                valid = False
            return {"never": "published"}

    with pytest.raises(ProviderFailure if withdraw == "after_response" else ValueError):
        asyncio.run(discovery._dispatch(run, FakeTransport(), "browse", run.deadline))
    remaining = hunter_budget.remaining_traversal(restricted["root"], allowance)
    assert remaining["browse"] == (12 if withdraw == "before" else 11)
    assert sends == (["browse"] if withdraw == "after_response" else [])
    assert not run.raws
    assert not any(args[1] == "completed" for args, _ in journals)


@pytest.mark.parametrize("failure", [None, RuntimeError, KeyboardInterrupt, "application"])
def test_only_expiry_worker_and_shutdown_erases_content_on_completion_or_interruption(
    restricted, monkeypatch, failure
):
    import uvicorn

    from pokemon_hunter.beta import asgi, hunter, hunter_lot_details, hunter_lots, price_snapshots

    parent = SimpleNamespace(
        id="controlled-parent",
        lock=threading.RLock(),
        cancel=threading.Event(),
        raws=[{"title": "never durable"}],
        seen={"controlled"},
        state="running",
    )
    detail = SimpleNamespace(
        id="controlled-detail",
        parent_run_id=parent.id,
        lock=parent.lock,
        cancel=threading.Event(),
        raws=[{"description": "never durable"}],
        state="running",
    )
    monkeypatch.setattr(hunter, "_runs", {parent.id: parent})
    monkeypatch.setattr(hunter_lot_details, "_runs", {detail.id: detail})
    monkeypatch.setattr(hunter_lots, "_reviews", {"controlled-review": {"origin": {"run_id": parent.id}}})
    active, stopped = threading.Event(), threading.Event()
    calls = []

    def expiry(stop):
        active.set()
        assert stop.wait(5)
        stopped.set()

    def application():
        if failure == "application":
            raise RuntimeError("controlled startup failure")
        return "controlled-asgi"

    def run(app, **kwargs):
        assert active.wait(2)
        assert app == "controlled-asgi"
        calls.append(kwargs)
        if failure:
            raise failure()

    monkeypatch.setattr(asgi, "get_asgi_application", application)
    monkeypatch.setattr(price_snapshots, "expiry_worker", expiry)
    monkeypatch.setattr(uvicorn, "run", run)
    if failure:
        with pytest.raises(RuntimeError if failure == "application" else failure):
            profile.serve()
    else:
        profile.serve()
    assert parent.cancel.is_set() and detail.cancel.is_set()
    assert not parent.raws and not parent.seen and not detail.raws
    assert not hunter._runs and not hunter_lot_details._runs and not hunter_lots._reviews
    if failure != "application":
        assert stopped.is_set()
        assert calls == [
            dict(host="127.0.0.1", port=8011, access_log=False, proxy_headers=False, log_level="warning")
        ]
    else:
        assert not active.is_set() and not calls
