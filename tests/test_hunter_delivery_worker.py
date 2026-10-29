"""Ordinary delivery never resumes unselected recognition; all state is disposable."""

import sys
import threading
import uuid
from types import SimpleNamespace

import pytest
from django.db import transaction as django_transaction
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b3 import b3 as b3
from test_b3 import image, upload
from test_migration import snapshot as snapshot

from pokemon_hunter.beta import cli, scan_worker, scans, store


@pytest.fixture(autouse=True)
def selection(monkeypatch):
    monkeypatch.setattr(scans, "_serve_admissions", None)


def test_ordinary_restart_preserves_old_manual_queue(b3):
    (b3["root"] / "scan-config.json").write_text('{"mode":"manual"}')
    old = upload(b3)
    before = scans.job(b3["actor"], old["id"])
    scans.select_current_process()
    assert not scans.process_one()
    assert scans.job(b3["actor"], old["id"]) == before
    current = upload(b3)
    assert scans.process_one()
    assert scans.job(b3["actor"], current["id"])["state"] == "needs-confirmation"
    assert scans.job(b3["actor"], old["id"]) == before


def test_selection_requires_committed_explicit_admission_and_current_account(b3):
    scans.select_current_process()
    key = str(uuid.uuid4())
    with pytest.raises(RuntimeError, match="rollback"):
        with django_transaction.atomic():
            scans.create(b3["actor"], key, [image()])
            assert key not in scans._serve_admissions
            raise RuntimeError("rollback")
    assert key not in scans._serve_admissions
    assert not store.rows("SELECT id FROM scan_jobs WHERE id=%s", [key])
    assert not scans.process_one()

    old = upload(b3)
    scans.select_current_process()
    assert (
        b3["b"]
        .post(
            "/api/scans/",
            {"front": image(), "job_id": old["id"]},
            HTTP_X_CSRFTOKEN=b3["b"].cookies["dex_b1_csrf"].value,
        )
        .status_code
        == 404
    )
    assert not scans.process_one()
    # An explicit idempotent resubmit by the owning account can select its queued job.
    scans.create(b3["actor"], old["id"], [image()])
    assert scans.process_one()


def test_privileged_worker_retains_explicit_durable_queue_contract(b3):
    job = upload(b3)
    assert scans._serve_admissions is None
    assert scans.process_one()
    assert scans.job(b3["actor"], job["id"])["attempts"] == 1


@pytest.mark.parametrize(
    "selected_only,available,expected", [(True, True, True), (False, False, False), (False, True, True)]
)
def test_worker_keeps_cleanup_and_never_selects_deferred_batch_work(
    b3, monkeypatch, selected_only, available, expected
):
    stop = threading.Event()
    calls = []
    monkeypatch.setattr(scan_worker, "close_old_connections", lambda: None)
    monkeypatch.setattr(scan_worker.scans, "cleanup", lambda: calls.append("scan_cleanup"))
    monkeypatch.setattr(scan_worker.photo_batches, "cleanup", lambda: calls.append("batch_cleanup"))
    monkeypatch.setattr(scan_worker.photo_batches, "available", lambda: available)

    expected_selection = selected_only

    def batches(_, *, selected_only):
        assert selected_only is expected_selection
        calls.append("batch_process")
        return False

    def single(_):
        calls.append("single_process")
        stop.set()
        return False

    monkeypatch.setattr(scan_worker.photo_batches, "process_one", batches)
    monkeypatch.setattr(scan_worker.scans, "process_one", single)
    monkeypatch.setattr(scan_worker.signal, "signal", lambda *_: None)
    scan_worker.run(stop, selected_scans_only=selected_only)
    assert calls[:2] == ["scan_cleanup", "batch_cleanup"]
    assert ("batch_process" in calls) is expected
    assert calls[-1] == "single_process"


def test_ordinary_serve_selects_before_workers_and_retains_price_expiry(b3, monkeypatch):
    import uvicorn

    from pokemon_hunter.beta import asgi, price_snapshots

    (b3["root"] / "B3_ISOLATED").write_text("engineering test only\n")
    order, threads = [], []

    class Thread:
        def __init__(self, *, target, args, daemon, kwargs=None):
            self.target, self.args, self.kwargs = target, args, kwargs or {}
            threads.append(self)

        def start(self):
            assert scans._serve_admissions == set() or self.target is price_snapshots.expiry_worker
            order.append(self.target.__name__)

        def join(self, timeout):
            assert self.args[0].is_set()

        def is_alive(self):
            return False

    monkeypatch.setitem(
        sys.modules,
        "pokemon_hunter.beta.hunter_installed",
        SimpleNamespace(configure=lambda: order.append("installed_configuration")),
    )
    monkeypatch.setattr(cli, "setup", lambda _: None)
    monkeypatch.setattr(sys, "argv", ["dex", "--root", str(b3["root"]), "serve"])
    monkeypatch.setattr(threading, "Thread", Thread)
    monkeypatch.setattr(asgi, "get_asgi_application", lambda: "guarded-asgi")
    monkeypatch.setattr(uvicorn, "run", lambda app, **kwargs: order.append(app.application))
    cli.main()
    assert order == ["installed_configuration", "expiry_worker", "run", "guarded-asgi"]
    assert threads[1].kwargs == {"selected_scans_only": True}
