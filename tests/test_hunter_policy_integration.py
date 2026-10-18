"""Ordinary-policy full workers with fixture transport and disposable accounting."""

import threading
import time
from types import SimpleNamespace

import pytest
from test_hunter import hunt as hunt
from test_hunter_h07_integration import integrated as integrated

from pokemon_hunter.beta import (
    hunter,
    hunter_budget,
    hunter_installed,
    hunter_lot_details,
    hunter_lots,
    hunter_policy,
)

_LAUNCH = hunter._launch
_DETAIL_WORKER = hunter_lot_details._worker


def _finished(run):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        with run.lock:
            if run.state not in {"queued", "running"}:
                assert run.state == "complete", (run.state, run.error)
                return
        time.sleep(0.005)
    pytest.fail("Offline worker did not complete within its bounded test deadline")


@pytest.fixture
def ordinary_workers(integrated, monkeypatch):
    actor, root = integrated.env.actor, integrated.env.root
    actor.role = "owner"
    monkeypatch.setattr("django.conf.settings", SimpleNamespace(ROOT=root, STAGING=False))
    monkeypatch.setattr(hunter_installed, "_configured", None)
    monkeypatch.setattr(hunter_installed, "package_digest", lambda: "a" * 64)
    monkeypatch.setattr(hunter, "_launch", _LAUNCH)
    monkeypatch.setattr(hunter_lot_details, "_worker", _DETAIL_WORKER)
    monkeypatch.setattr(hunter_lot_details, "close_old_connections", lambda: None)
    integrated.pages = [integrated.pages[1], integrated.pages[1]]
    hunter_policy.select(
        actor,
        dict(
            enabled=True,
            per_hunt_limit=15,
            daily_limit=15,
            timezone="UTC",
            recurring=True,
            expires_at=None,
            revision=0,
        ),
    )
    yield integrated
    for worker in threading.enumerate():
        if worker.name in {"dex-price-hunter", "dex-hunter-lot-details"}:
            worker.join(3)
            assert not worker.is_alive(), "Offline worker leaked past fixture teardown"


def test_real_workers_successive_hunts_continue_detail_and_local_stop(ordinary_workers):
    state = ordinary_workers
    actor, root = state.env.actor, state.env.root
    first = hunter.start(actor, "binding", dict(scope="lots"))
    parent = hunter._runs[first["run_id"]]
    _finished(parent)
    result = hunter.status(actor, "binding", parent.id)
    assert [stage for stage, item in state.calls] == ["oauth", "browse", "browse"]
    assert result["usage_policy"]["used"] == 3
    cursor = result["continuation_cursor"]
    assert cursor
    hunter.continue_run(actor, "binding", parent.id, dict(cursor=cursor))
    _finished(parent)
    assert [stage for stage, item in state.calls] == ["oauth", "browse", "browse", "browse", "browse"]
    result = hunter.status(actor, "binding", parent.id)
    result_id = result["results"][0]["id"]
    review = hunter_lots.analyze(actor, "binding", parent.id, result_id)
    detail = hunter_lot_details.start(actor, "binding", parent.id, [result_id])
    action = hunter_lot_details._runs[detail["detail_action_id"]]
    _finished(action)
    loaded = hunter_lot_details.status(actor, "binding", action.id)
    assert loaded["reviews"]
    assert hunter_policy.status(actor)["used"] == 6
    second = hunter.start(actor, "binding", dict(scope="lots"))
    second_parent = hunter._runs[second["run_id"]]
    _finished(second_parent)
    assert second_parent.id != parent.id and not parent.cancel.is_set()
    assert hunter_policy.status(actor)["used"] == 8
    assert hunter_policy.status(actor)["remaining"] == 7
    assert hunter_budget.remaining_traversal(root, parent.allowance)["total"] == 7
    before = list(state.calls)
    hunter.status(actor, "binding", parent.id)
    hunter.status(actor, "binding", second_parent.id)
    hunter_lots.read(actor, "binding", review["review_id"])
    hunter_lots.detail_intent(actor, "binding", parent.id, [result_id])
    hunter_lot_details.stop(actor, "binding", action.id)
    assert not parent.cancel.is_set() and not second_parent.cancel.is_set()
    hunter.stop(actor, "binding", parent.id)
    assert not second_parent.cancel.is_set()
    assert state.calls == before
    assert hunter_policy.status(actor)["used"] == 8
    journal = hunter_policy._storage(root) / hunter_policy.JOURNAL_NAME
    assert journal.exists()
    assert not hunter_budget.traversal_path(root, state.allowance).exists()


def test_pause_during_real_detail_worker_suppresses_late_publication(ordinary_workers):
    state = ordinary_workers
    actor = state.env.actor
    started = hunter.start(actor, "binding", dict(scope="lots"))
    parent = hunter._runs[started["run_id"]]
    _finished(parent)
    result = hunter.status(actor, "binding", parent.id)

    def pause(identifier):
        selected = hunter_policy.status(actor)
        hunter_policy.select(
            actor,
            {
                key: selected[key]
                for key in (
                    "per_hunt_limit",
                    "daily_limit",
                    "timezone",
                    "recurring",
                    "expires_at",
                    "revision",
                )
            }
            | dict(enabled=False),
        )

    state.detail_hook = pause
    selected = hunter_lot_details.start(actor, "binding", parent.id, [result["results"][0]["id"]])
    action = hunter_lot_details._runs[selected["detail_action_id"]]
    deadline = time.monotonic() + 5
    while action.state in {"queued", "running"} and time.monotonic() < deadline:
        time.sleep(0.005)
    assert action.state == "failed" and not action.raws
    assert hunter_policy.status(actor)["used"] == 4
    assert hunter_lot_details.status(actor, "binding", action.id)["reviews"] == []
    assert hunter.status(actor, "binding", parent.id)["results"]
    assert len(state.calls) == 4


def test_independent_detail_stop_in_flight_keeps_debit_and_parent(ordinary_workers):
    state = ordinary_workers
    actor = state.env.actor
    started = hunter.start(actor, "binding", dict(scope="lots"))
    parent = hunter._runs[started["run_id"]]
    _finished(parent)
    result = hunter.status(actor, "binding", parent.id)
    entered, release = threading.Event(), threading.Event()

    def in_flight(identifier):
        entered.set()
        assert release.wait(2)

    state.detail_hook = in_flight
    selected = hunter_lot_details.start(actor, "binding", parent.id, [result["results"][0]["id"]])
    action = hunter_lot_details._runs[selected["detail_action_id"]]
    assert entered.wait(2)
    hunter_lot_details.stop(actor, "binding", action.id)
    release.set()
    deadline = time.monotonic() + 5
    while action.state in {"queued", "running"} and time.monotonic() < deadline:
        time.sleep(0.005)
    assert action.state == "stopped" and not action.raws
    assert not parent.cancel.is_set() and parent.state == "complete"
    assert hunter_policy.status(actor)["used"] == 4
    assert len(state.calls) == 4
