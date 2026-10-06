"""Meaningful offline lifecycle and retained publication/snapshot regressions."""

import copy
import sqlite3
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.http import Http404
from test_packs import b2 as b2
from test_packs import b3 as b3
from test_packs import b4 as b4
from test_packs import e1 as e1
from test_packs import env as env
from test_packs import ready
from test_packs import snapshot as snapshot

from pokemon_hunter.beta import collection, pack_research, refresh, sealed_catalog, store


@pytest.fixture
def replay(e1, monkeypatch):
    monkeypatch.setattr(settings, "ROOT", e1["root"])
    (e1["root"] / "SYNTHETIC_ONLY").touch()
    g = ready(e1)
    refresh.initialize()
    pack_research.initialize()
    e1["goal"] = g
    e1["product"] = next(iter(sealed_catalog.records()["products"]))
    with (
        patch("httpx.Client.send", side_effect=AssertionError("No acquisition")) as http,
        patch("httpx.AsyncClient.send", side_effect=AssertionError("No acquisition")) as async_http,
        patch("pokemon_hunter.beta.ebay_hunts.search", side_effect=AssertionError("No acquisition")) as ebay,
    ):
        yield e1
        assert http.call_count == async_http.call_count == ebay.call_count == 0


def run(e, sources, timeout=2):
    key = refresh.start(e["actor"], e["product"], sources, timeout)
    refresh.execute(e["actor"], key)
    return refresh.get(e["actor"], key)


def publish(e, r, index=0):
    a = r["attempts"][index]
    for action in ("preview", "verify", "publish"):
        refresh.review(e["actor"], r["id"], a["id"], action)


def test_success_explicit_review_duplicate_replay_original_times_and_snapshot(replay):
    e = replay
    who = e["actor"]
    protected = collection.export_data(who)
    prior = store.rows("SELECT * FROM sealed_observations ORDER BY id")
    saved = pack_research.save(who, e["goal"]["id"], goal_version=e["goal"]["version"])
    frozen = pack_research.one(who, saved)
    first = run(e, ["success"])
    assert first["status"] == "completed" and first["consumed"] == 1
    a = first["attempts"][0]
    assert a["started_at"] and a["ended_at"] and a["deadline"] and a["execution_token"]
    assert store.rows("SELECT * FROM sealed_observations ORDER BY id") == prior
    with pytest.raises(ValueError):
        refresh.review(who, first["id"], a["id"], "publish")
    publish(e, first)
    published = store.rows("SELECT * FROM sealed_observations ORDER BY id")
    assert len(published) == len(prior) + 1 and all(r in published for r in prior)
    for _ in range(2):
        again = run(e, ["success"])
        assert again["attempts"][0]["candidate"] == a["candidate"]
        publish(e, again)
        refresh.execute(who, again["id"])
        assert refresh.get(who, again["id"])["consumed"] == 1
    assert store.rows("SELECT * FROM sealed_observations ORDER BY id") == published
    assert collection.export_data(who) == protected
    connection.close()
    pack_research.reopen(who, saved)
    assert pack_research.one(who, saved) == frozen
    result = sealed_catalog.report(who)
    replay_obs = [o for o in result["observations"] if o["id"].startswith("synthetic:")]
    assert all(
        not o["fresh"] and not o["buy_now"] and o["checked_at"].startswith("2020-") for o in replay_obs
    )


def test_partial_failure_unknown_is_observation_and_specific_errors(replay):
    r = run(replay, ["success", "denied", "unknown", "malformed", "identity-mismatch"])
    assert r["status"] == "failed" and r["consumed"] == r["attempt_limit"] == 5
    assert [a["status"] for a in r["attempts"]] == ["completed", "failed", "completed", "failed", "failed"]
    assert "Denied access" in r["attempts"][1]["reason"]
    assert "Unusable content" in r["attempts"][3]["reason"]
    assert "Identity mismatch" in r["attempts"][4]["reason"]
    assert r["attempts"][2]["candidate"]["observations"][0]["stock"] == "unknown"
    assert all(a["candidate"] is None for a in r["attempts"] if a["status"] == "failed")
    assert all(a["ended_at"] <= b["started_at"] for a, b in zip(r["attempts"], r["attempts"][1:]))
    publish(replay, r)


def test_timeout_cancel_recovery_consumed_budget_and_late_duplicate_delivery(replay, monkeypatch):
    e, who = replay, replay["actor"]
    timed = run(e, ["timeout", "success"], 1)
    assert [a["status"] for a in timed["attempts"]] == ["timeout", "completed"]
    key = refresh.start(who, e["product"], ["slow", "success"])
    original = refresh.claim(who, key)
    assert original is not None and refresh.claim(who, key) is None
    attempt = refresh.reserve(who, key, original["attempts"][0]["id"])
    with pytest.raises(ValueError, match="already executing"):
        refresh.reserve(who, key, original["attempts"][1]["id"])
    candidate = refresh.ReplayAdapter().execute(
        original["scope"], {**attempt, "source_id": "replay:success"}, lambda: None
    )
    assert refresh.deliver(who, key, attempt, candidate)
    assert not refresh.deliver(who, key, attempt, candidate)
    refresh.stop(who, key)
    assert refresh.get(who, key)["consumed"] == 1
    assert refresh.get(who, key)["attempts"][1]["started_at"] is None
    refresh.execute(who, key)
    assert refresh.get(who, key)["consumed"] == 1
    # An actual adapter observes cancellation through its checkpoint.
    with patch.object(
        refresh.ReplayAdapter,
        "execute",
        side_effect=lambda scope, attempt, checkpoint: refresh.stop(who, attempt["run_id"]),
    ):
        cancelled = run(e, ["slow", "success"])
    assert cancelled["status"] == "stopped" and cancelled["consumed"] == 1
    assert all(a["candidate"] is None for a in cancelled["attempts"])
    key = refresh.start(who, e["product"], ["slow", "success"], 1)
    original = refresh.claim(who, key)
    attempt = refresh.reserve(who, key, original["attempts"][0]["id"])
    connection.close()
    refresh.recover(who)  # Fresh connection cannot steal an unexpired execution.
    assert refresh.get(who, key)["status"] == "running"
    later = (sealed_catalog.instant(attempt["deadline"]) + timedelta(seconds=1)).isoformat()
    monkeypatch.setattr(refresh, "now", lambda: later)
    refresh.recover(who)
    recovered = refresh.get(who, key)
    assert recovered["status"] == "stopped" and recovered["consumed"] == 1
    assert [a["status"] for a in recovered["attempts"]] == ["interrupted", "cancelled"]
    assert not refresh.deliver(who, key, attempt, candidate)
    refresh.execute(who, key)
    assert refresh.get(who, key)["consumed"] == 1


def test_scope_validation_authorization_csrf_and_owner_unavailability(replay):
    e, who = replay, replay["actor"]
    r = run(e, ["success"])
    for principal in (e["member"],):
        with pytest.raises(Http404):
            refresh.get(principal, r["id"])
        for operation in (
            lambda: refresh.start(principal, e["product"], ["success"]),
            lambda: refresh.stop(principal, r["id"]),
            lambda: refresh.review(principal, r["id"], r["attempts"][0]["id"], "preview"),
        ):
            with pytest.raises(PermissionDenied):
                operation()
    for sources in ([], ["success", "success"], ["live-http"]):
        with pytest.raises(ValueError):
            refresh.start(who, e["product"], sources)
    for timeout in (0, 31, True):
        with pytest.raises(ValueError):
            refresh.start(who, e["product"], ["success"], timeout)
    assert e["a"].post("/packs/refresh/start/", {}).status_code == 403
    assert e["a"].get("/packs/refresh/start/").status_code == 405
    assert b"Start bounded replay" in e["a"].get("/packs/refresh/").content
    assert b"Start bounded replay" not in e["b"].get("/packs/refresh/").content
    (e["root"] / "SYNTHETIC_ONLY").unlink()
    page = e["a"].get("/packs/refresh/")
    assert b"Live refresh unavailable" in page.content and b"Start bounded replay" not in page.content
    with pytest.raises(PermissionDenied):
        refresh.start(who, e["product"], ["success"])


def test_adapter_relationship_and_scope_conflicts_cannot_publish(replay):
    e = replay
    original = refresh.ReplayAdapter.execute

    def unsupported(self, scope, attempt, checkpoint):
        raw = original(self, scope, attempt, checkpoint)
        raw["products"] = [copy.deepcopy(scope["product_identity"])]
        return raw

    with patch.object(refresh.ReplayAdapter, "execute", unsupported):
        r = run(e, ["success"])
    assert r["status"] == "failed" and r["attempts"][0]["candidate"] is None
    with pytest.raises(ValueError):
        refresh.review(e["actor"], r["id"], r["attempts"][0]["id"], "preview")


def test_migration_is_additive_and_repeatable(replay):
    def database():
        with sqlite3.connect(replay["root"] / "inventory.db") as db:
            return list(db.iterdump())

    before = database()
    refresh.initialize()
    assert database() == before


def test_concurrent_execution_claim_and_second_owner_isolation(replay):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from django.db import close_old_connections

    e, who = replay, replay["actor"]
    key = refresh.start(who, e["product"], ["success"])
    barrier = Barrier(2)

    def claim():
        close_old_connections()
        try:
            barrier.wait(timeout=5)
            return refresh.claim(who, key)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(claim) for _ in range(2)]
        claimed = [f.result(timeout=10) for f in futures]
    assert sum(r is not None for r in claimed) == 1
    assert refresh.get(who, key)["consumed"] == 0
    collection.execute("UPDATE users SET role='owner' WHERE id=%s", [e["member"].user_id])
    second_owner = store.principal(e["member"].subject)
    for operation in (
        lambda: refresh.get(second_owner, key),
        lambda: refresh.stop(second_owner, key),
        lambda: refresh.review(
            second_owner,
            key,
            claimed[0]["attempts"][0]["id"] if claimed[0] else claimed[1]["attempts"][0]["id"],
            "preview",
        ),
    ):
        with pytest.raises(Http404):
            operation()
    refresh.stop(who, key)
    # A cached principal does not retain revoked authority.
    collection.execute("UPDATE users SET state='revoked' WHERE id=%s", [who.user_id])
    with pytest.raises(PermissionDenied):
        refresh.start(who, e["product"], ["success"])
