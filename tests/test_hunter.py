"""Engineering-only Hunter actions with disposable accounting and fake I/O."""

import asyncio
import threading
import time
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from django.http import Http404

from pokemon_hunter.beta import discovery as d
from pokemon_hunter.beta import hunter as h
from pokemon_hunter.beta import hunter_budget as budget
from pokemon_hunter.beta import hunter_query as query
from pokemon_hunter.beta.discovery_transport import ProviderFailure


@pytest.fixture
def hunt(tmp_path, monkeypatch):
    actor = SimpleNamespace(user_id="fixture-account", subject=1)
    monkeypatch.setattr(d, "settings", SimpleNamespace(ROOT=tmp_path))
    monkeypatch.setattr(d.store, "verified", lambda who: who)
    monkeypatch.setattr(d, "close_old_connections", lambda: None)
    monkeypatch.setattr(h, "close_old_connections", lambda: None)
    monkeypatch.setattr(d, "_authorize", lambda *args: None)
    monkeypatch.setattr(
        h.ebay_hunts,
        "configuration",
        lambda: (
            SimpleNamespace(environment="production"),
            {"EBAY_CLIENT_ID": "fixture-client", "EBAY_CLIENT_SECRET": "CANARY_SECRET"},
        ),
    )
    monkeypatch.setattr(
        h.hunter_catalog,
        "compare",
        lambda who, raws, **kw: [
            {"item_id": r["itemId"], "hunt_status": "unmatched", "reference": None} for r in raws
        ],
    )
    h._runs.clear()
    d._tokens.clear()
    Fake.calls = []
    monkeypatch.setattr(h, "Transport", Fake)
    yield SimpleNamespace(actor=actor, root=tmp_path, monkeypatch=monkeypatch)
    for run in h._runs.values():
        run.cancel.set()
    h._runs.clear()
    d._tokens.clear()


def run_for(env):
    window = query.plan(datetime.now(UTC))
    run = h.Run(
        "fixture-run",
        (str(env.root), env.actor.user_id, "binding"),
        d.Choices(english_vintage=False),
        None,
        list(window["requests"]),
        window=window,
    )
    h._runs[run.id] = run
    return run


class Fake:
    calls = []

    async def request(self, stage, **kwargs):
        self.calls.append((stage, deepcopy(kwargs)))
        if stage == "oauth":
            return {"access_token": "CANARY_TOKEN", "expires_in": 300, "token_type": "Bearer"}
        lane = kwargs["search_options"]["hunter"]["lane"]
        end = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        rows = [
            {
                "itemId": "v1|123|0",
                "title": "CANARY_CONTENT",
                "buyingOptions": ["AUCTION", "FIXED_PRICE"],
                "itemEndDate": end,
            },
            {"itemId": "v1|456|0", "buyingOptions": ["FIXED_PRICE"]},
        ]
        return {
            "itemSummaries": rows[:1] if lane == "auction" else rows,
            "next": "https://evil.invalid/next",
            "total": 1000,
        }

    async def close(self):
        pass


def test_two_pages_mixed_dedup_no_followup_and_sanitized_counts(hunt):
    run = run_for(hunt)
    asyncio.run(h._acquire(run, ("fixture-client", "CANARY_SECRET")))
    assert [stage for stage, _ in Fake.calls] == ["oauth", "browse", "browse"]
    assert run.counts == {"oauth": 1, "browse": 2, "total": 3, "summary_count": 3, "duplicates": 1}
    assert len(run.raws) == 2 and run.state == "complete"
    result = h.status(hunt.actor, "binding", run.id)
    assert result["coverage"]["unmatched"] == 2
    assert result["results"][0]["lanes"] == ["auction", "buy_it_now"]
    assert result["results"][1]["lanes"] == ["buy_it_now"]
    assert result["has_next"] is False and result["coverage_complete"] is False
    assert all(lane["truncated"] for lane in result["lanes"])
    assert budget.remaining(hunt.root) == {"oauth": 0, "browse": 0, "total": 0, "auction": 0, "buy_it_now": 0}
    ledger = budget.path(hunt.root).read_text()
    for secret in ("CANARY", "TOKEN", "CONTENT", "SECRET", "evil.invalid"):
        assert secret not in ledger
    # Reopening/comparison/Stop/leases perform no HTTP operations.
    lease = h.summary_lease(hunt.actor, "binding", run.id, result["results"][0]["id"])
    assert lease["created"] == run.created
    assert h.status(hunt.actor, "binding", run.id)["results"]
    h.stop(hunt.actor, "binding", run.id)
    assert len(Fake.calls) == 3 and not h.status(hunt.actor, "binding", run.id)["results"]


def test_allowance_survives_run_and_token_memory_restart(hunt):
    first = run_for(hunt)
    asyncio.run(h._acquire(first, ("fixture-client", "CANARY_SECRET")))
    d._tokens.clear()
    second = run_for(hunt)
    second.id = "new-process-run"
    with pytest.raises(ProviderFailure):
        asyncio.run(h._acquire(second, ("fixture-client", "CANARY_SECRET")))
    assert len(Fake.calls) == 3 and second.counts["total"] == 0
    with pytest.raises(ValueError, match="allowance"):
        h.start(hunt.actor, "binding", {})


def test_duplicate_latest_availability_replaces_old_mixed_options(hunt):
    class Changed(Fake):
        async def request(self, stage, **kwargs):
            payload = await super().request(stage, **kwargs)
            if stage == "browse" and kwargs["search_options"]["hunter"]["lane"] == "buy_it_now":
                payload["itemSummaries"][0]["buyingOptions"] = ["AUCTION"]
                payload["itemSummaries"][0]["minimumPriceToBid"] = {"value": "2", "currency": "USD"}
            return payload

    hunt.monkeypatch.setattr(h, "Transport", Changed)
    run = run_for(hunt)
    asyncio.run(h._acquire(run, ("fixture-client", "secret")))
    assert run.raws[0]["buyingOptions"] == ["AUCTION"]
    assert run.raws[0]["minimumPriceToBid"]["value"] == "2"
    assert run.raws[0]["_hunt_lanes"] == ["auction", "buy_it_now"]


def test_concurrent_admission_is_atomic_and_no_detail_budget(hunt):
    runs = [run_for(hunt) for _ in range(8)]
    for index, run in enumerate(runs):
        run.current_lane = "auction" if index % 2 else "buy_it_now"
    admitted = []

    def consume(run):
        try:
            budget.consume(run, "browse")
            admitted.append(True)
        except ProviderFailure:
            pass

    threads = [threading.Thread(target=consume, args=(run,)) for run in runs]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(admitted) == 2 and budget.remaining(hunt.root)["browse"] == 0
    with pytest.raises(ProviderFailure):
        budget.consume(runs[0], "detail")


@pytest.mark.parametrize(
    "raw", [{"query": "x"}, {"continuation_run": "x"}, {"goal_id": "x"}, {"limit": 400}, []]
)
def test_no_card_query_continuation_or_budget_override(hunt, raw):
    with pytest.raises(ValueError):
        h.start(hunt.actor, "binding", raw)
    assert not Fake.calls


@pytest.mark.parametrize("stage", ["oauth", "browse"])
def test_first_failure_consumes_attempt_and_never_retries(hunt, stage):
    class Fails(Fake):
        async def request(self, operation, **kwargs):
            if operation == stage:
                self.calls.append((operation, {}))
                raise ProviderFailure(operation, 401)
            return await super().request(operation, **kwargs)

    hunt.monkeypatch.setattr(h, "Transport", Fails)
    run = run_for(hunt)
    h._worker(run, hunt.actor, ("fixture-client", "CANARY_SECRET"))
    assert run.state == "failed" and not run.raws
    assert [s for s, _ in Fake.calls] == (["oauth"] if stage == "oauth" else ["oauth", "browse"])
    assert budget.remaining(hunt.root)[stage] == budget.LIMITS[stage] - 1


def test_token_reuse_does_not_spend_oauth(hunt):
    run = run_for(hunt)
    import hashlib

    key = hashlib.sha256((run.owner[0] + "\0fixture-client\0CANARY_SECRET").encode()).hexdigest()
    d._tokens[key] = ("ELIGIBLE_TOKEN", time.monotonic() + 100)
    asyncio.run(h._acquire(run, ("fixture-client", "CANARY_SECRET")))
    assert [s for s, _ in Fake.calls] == ["browse", "browse"]
    assert budget.remaining(hunt.root) == {"oauth": 1, "browse": 0, "total": 1, "auction": 0, "buy_it_now": 0}


def test_account_session_revocation_and_stop_isolation(hunt):
    run = run_for(hunt)
    for actor, binding in ((hunt.actor, "other-binding"), (SimpleNamespace(user_id="other"), "binding")):
        with pytest.raises(Http404):
            h.stop(actor, binding, run.id)
    run.auth_session = "actual-auth-session"
    from django.core.exceptions import PermissionDenied

    hunt.monkeypatch.setattr(d, "_authorize", lambda *args: (_ for _ in ()).throw(PermissionDenied()))
    with pytest.raises(PermissionDenied):
        h.status(hunt.actor, "binding", run.id)
    assert not Fake.calls


def test_stop_inflight_suppresses_later_dispatch_and_publication(hunt):
    entered = threading.Event()

    class Slow(Fake):
        async def request(self, stage, **kwargs):
            self.calls.append((stage, {}))
            entered.set()
            await asyncio.sleep(3)

    hunt.monkeypatch.setattr(h, "Transport", Slow)
    run = run_for(hunt)
    worker = threading.Thread(target=h._worker, args=(run, hunt.actor, ("fixture-client", "secret")))
    worker.start()
    assert entered.wait(2)
    h.stop(hunt.actor, "binding", run.id)
    worker.join(2)
    assert not worker.is_alive() and run.state == "stopped" and not run.raws
    assert len(Fake.calls) == 1 and budget.remaining(hunt.root)["oauth"] == 0


def test_deadline_suppresses_slow_authorization_without_send(hunt):
    hunt.monkeypatch.setattr(d, "OVERALL_SECONDS", 0.03)
    hunt.monkeypatch.setattr(d, "_authorize", lambda *args: time.sleep(0.1))
    run = run_for(hunt)
    h._worker(run, hunt.actor, ("fixture-client", "secret"))
    assert not Fake.calls and run.timed_out and not run.raws


def test_deadline_rechecked_after_durable_allowance_admission(hunt):
    hunt.monkeypatch.setattr(d, "OVERALL_SECONDS", 0.03)
    consume = budget.consume

    def slow(run, stage):
        consume(run, stage)
        time.sleep(0.08)

    hunt.monkeypatch.setattr(budget, "consume", slow)
    run = run_for(hunt)
    h._worker(run, hunt.actor, ("fixture-client", "secret"))
    assert not Fake.calls and run.timed_out and not run.raws
    assert budget.remaining(hunt.root)["oauth"] == 0


def test_201_summaries_fail_without_second_lane(hunt):
    class Oversized(Fake):
        async def request(self, stage, **kwargs):
            payload = await super().request(stage, **kwargs)
            if stage == "browse":
                payload["itemSummaries"] = [{"itemId": str(n)} for n in range(201)]
            return payload

    hunt.monkeypatch.setattr(h, "Transport", Oversized)
    run = run_for(hunt)
    h._worker(run, hunt.actor, ("fixture-client", "secret"))
    assert run.state == "failed" and len(Fake.calls) == 2
    assert run.lanes[0]["state"] == "failed" and run.lanes[0]["attempted"] == 1
    assert run.lanes[1]["state"] == "planned" and run.lanes[1]["attempted"] == 0


def test_full_400_summary_contract_and_per_lane_allowance(hunt):
    class Full(Fake):
        async def request(self, stage, **kwargs):
            payload = await super().request(stage, **kwargs)
            if stage == "browse":
                lane = kwargs["search_options"]["hunter"]["lane"]
                base = payload["itemSummaries"][0]
                payload["itemSummaries"] = [{**base, "itemId": lane + str(n)} for n in range(200)]
            return payload

    hunt.monkeypatch.setattr(h, "Transport", Full)
    run = run_for(hunt)
    asyncio.run(h._acquire(run, ("fixture-client", "secret")))
    assert len(run.raws) == 400 and run.counts["summary_count"] == 400
    assert all(lane["received"] == 200 and lane["attempted"] == 1 for lane in run.lanes)
    # Another process cannot spend an unused generic Browse slot on a second
    # auction attempt after that particular lane has consumed its permission.
    other = run_for(hunt)
    other.current_lane = "auction"
    with pytest.raises(ProviderFailure):
        budget.consume(other, "browse")


def test_initial_local_matching_cannot_publish_after_deadline(hunt):
    hunt.monkeypatch.setattr(d, "OVERALL_SECONDS", 0.03)
    hunt.monkeypatch.setattr(h.hunter_catalog, "compare", lambda *a, **k: time.sleep(0.1) or [])
    run = run_for(hunt)
    h._worker(run, hunt.actor, ("fixture-client", "secret"))
    assert run.timed_out and run.state == "failed" and not run.raws
    assert len(Fake.calls) == 3


def test_invalid_identity_and_rejected_auction_accounted(hunt):
    run = run_for(hunt)
    run.state = "complete"
    run.raws = [
        {
            "itemId": "v1|1|0",
            "_hunt_lanes": ["auction"],
            "_hunt_observed_at": run.window["start"],
            "buyingOptions": ["AUCTION"],
            "itemEndDate": "bad-time",
        }
    ]
    result = h.status(hunt.actor, "binding", run.id)
    assert result["coverage"]["rejected"] == 1
    assert result["results"][0]["reason"] == "invalid_end_time"


def test_expiry_erases_raws_and_lease_does_not_renew(hunt):
    run = run_for(hunt)
    asyncio.run(h._acquire(run, ("fixture-client", "secret")))
    result = h.status(hunt.actor, "binding", run.id)
    run.created -= d.EPHEMERAL_SECONDS
    assert h.status(hunt.actor, "binding", run.id)["state"] == "expired"
    assert not run.raws
    with pytest.raises(Http404):
        h.summary_lease(hunt.actor, "binding", run.id, result["results"][0]["id"])


def test_corrupt_budget_fails_closed_without_send(hunt):
    target = budget.path(hunt.root)
    target.parent.mkdir(parents=True)
    target.write_text("partial")
    run = run_for(hunt)
    h._worker(run, hunt.actor, ("fixture-client", "secret"))
    assert not Fake.calls and run.state == "failed"
