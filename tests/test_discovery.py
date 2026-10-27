"""Disposable discovery state and fake transports; never load customer keys/data."""

import asyncio
import json
import threading
import time
from copy import deepcopy
from types import SimpleNamespace

import httpx
import pytest
from django.http import Http404

from pokemon_hunter.beta import discovery as d
from pokemon_hunter.beta.discovery_transport import ProviderFailure, Transport


@pytest.fixture
def discovery(tmp_path, monkeypatch):
    actor = SimpleNamespace(user_id="test-account", subject=1)
    monkeypatch.setattr(d, "settings", SimpleNamespace(ROOT=tmp_path, STAGING=False))
    monkeypatch.setattr(d.store, "verified", lambda who: who)
    monkeypatch.setattr(d, "close_old_connections", lambda: None)
    monkeypatch.setattr(
        d.ebay_hunts,
        "configuration",
        lambda: (
            SimpleNamespace(environment="production"),
            {"EBAY_CLIENT_ID": "fixture-client", "EBAY_CLIENT_SECRET": "CANARY_SECRET"},
        ),
    )
    monkeypatch.setattr(d.goal_hunts, "snapshot", lambda who, key: None)
    monkeypatch.setattr(d.goal_hunts, "project", lambda who, data, scope: deepcopy(data))
    cards, catalog = {}, []
    for number, name in enumerate(("Abra", "Bellsprout", "Chansey", "Diglett", "Eevee", "Farfetch'd"), 1):
        key = "p" + str(number)
        p = dict(
            id=key,
            printing_id=key,
            set_id="base_set",
            set_name="Base Set",
            name=name,
            collector_number=str(number),
            attributes={},
            language="en",
            edition="standard",
            finish="regular",
            variant="regular",
        )
        catalog.append(p)
        cards[key] = dict(
            card_id=key,
            printing_id=key,
            set_id="base_set",
            set="Base Set",
            name=name,
            number=str(number),
            pokemon_dex=number,
            dex_eligible=True,
            rarity="Rare" if number == 3 else "Common",
            owned=number == 1,
            exact_printing_owned=number == 1,
        )
    data = dict(
        cards=cards, catalog=catalog, pokedex={str(n): {"dex_owned": n in (1, 2)} for n in range(1, 7)}
    )
    monkeypatch.setattr(d.parity, "projection", lambda who, **kwargs: deepcopy(data))
    from pokemon_hunter.beta import collection

    monkeypatch.setattr(collection, "catalog", lambda who: deepcopy(data["catalog"]))
    monkeypatch.setattr(d.store, "rows", lambda *args: [])

    monkeypatch.setattr(d, "_sets", lambda who: {"base_set": "Base Set"})
    d._runs.clear()
    d._tokens.clear()
    yield SimpleNamespace(actor=actor, root=tmp_path, data=data, monkeypatch=monkeypatch)
    for run in d._runs.values():
        run.cancel.set()
    d._runs.clear()
    d._tokens.clear()


def run_for(env, *, choices=None, queries=None):
    return d.Run(
        "test-run",
        (str(env.root), env.actor.user_id, "session"),
        choices or d.Choices(product_type="both"),
        None,
        queries or ["q1", "q2", "q3", "q4", "q5"],
    )


def ledger(env):
    import hashlib

    key = hashlib.sha256(str(env.root).encode()).hexdigest()
    return env.root.parent / ".dex-shopping-discovery" / key / "attempts.jsonl"


class FakeTransport:
    calls = []
    rows = [{"itemId": "test-item", "title": "CANARY_LISTING_PRICE_CONTENT"}]

    async def request(self, stage, **kwargs):
        self.calls.append((stage, kwargs))
        if stage == "oauth":
            return dict(access_token="CANARY_TOKEN", expires_in=300, token_type="Application Access Token")
        return {"itemSummaries": deepcopy(self.rows)}

    async def close(self):
        pass


def test_temporary_result_ttl_is_remaining_time_not_renewed(discovery):
    run = run_for(discovery)
    run.created -= 10
    before = d._summary(run)["expires_in_seconds"]
    assert 0 < before <= d.EPHEMERAL_SECONDS - 10
    assert d._summary(run)["expires_in_seconds"] <= before
    run.created -= d.EPHEMERAL_SECONDS
    assert d._summary(run)["expires_in_seconds"] == 0


def test_default_one_browse_token_reuse_and_no_content_journal(discovery):
    FakeTransport.calls = []
    discovery.monkeypatch.setattr(d, "Transport", FakeTransport)
    first = run_for(discovery)
    asyncio.run(d._acquire(first, ("fixture-client", "CANARY_SECRET")))
    assert first.state == "complete" and first.offset == 1
    assert first.counts == {"oauth": 1, "browse": 1, "total": 2, "summary_count": 1}
    second = run_for(discovery)
    second.id = "second-run"
    asyncio.run(d._acquire(second, ("fixture-client", "CANARY_SECRET")))
    assert [c[0] for c in FakeTransport.calls] == ["oauth", "browse", "browse"]
    assert second.counts["oauth"] == 0
    text = ledger(discovery).read_text()
    assert all(value not in text for value in ("CANARY_SECRET", "CANARY_TOKEN", "CANARY_LISTING", "q1"))
    records = [json.loads(line) for line in text.splitlines()]
    assert {r["state"] for r in records} == {"admitted", "in_flight", "completed"}


def test_four_browse_ceiling_and_cross_query_dedup(discovery):
    FakeTransport.calls = []
    discovery.monkeypatch.setattr(d, "Transport", FakeTransport)
    run = run_for(discovery, choices=d.Choices(browse_requests=4))
    asyncio.run(d._acquire(run, ("fixture-client", "CANARY_SECRET")))
    assert run.counts["oauth"] == 1 and run.counts["browse"] == 4 and run.offset == 4
    assert len(run.raws) == 1
    with pytest.raises(ValueError):
        d.Choices(browse_requests=5)


def test_next_uses_captured_choices_and_deduplicates(discovery):
    FakeTransport.calls = []
    discovery.monkeypatch.setattr(d, "Transport", FakeTransport)

    # Execute inline so this test never depends on timing or a database thread.
    class Immediate:
        def __init__(self, target, args, **kwargs):
            self.target, self.args = target, args

        def start(self):
            self.target(*self.args)

    discovery.monkeypatch.setattr(d, "threading", SimpleNamespace(Thread=Immediate))
    first = d.start(discovery.actor, "session", {})
    second = d.start(discovery.actor, "session", {"continuation_run": first["run_id"]})
    assert second["choices"] == first["choices"]
    assert second["queries_completed"] == 2
    assert len(d._runs[second["run_id"]].raws) == 1
    with pytest.raises(ValueError, match="changing"):
        d.start(discovery.actor, "session", {"continuation_run": first["run_id"], "query": "changed"})


def test_account_session_isolation_and_stop_no_dispatch(discovery):
    run = run_for(discovery)
    d._runs[run.id] = run
    with pytest.raises(Http404):
        d.status(discovery.actor, "different-session", run.id)
    with pytest.raises(Http404):
        d.status(SimpleNamespace(user_id="other", subject=2), "session", run.id)
    assert d.stop(discovery.actor, "session", run.id)["state"] == "stopped"
    FakeTransport.calls = []
    discovery.monkeypatch.setattr(d, "Transport", FakeTransport)
    with pytest.raises(d._Stopped):
        asyncio.run(d._acquire(run, ("fixture-client", "CANARY_SECRET")))
    assert not FakeTransport.calls and not run.raws


def test_stop_cancels_inflight_and_prevents_publication_later_dispatch(discovery):
    active = threading.Event()

    class Slow(FakeTransport):
        calls = []

        async def request(self, stage, **kwargs):
            self.calls.append(stage)
            active.set()
            await asyncio.sleep(5)

    discovery.monkeypatch.setattr(d, "Transport", Slow)
    run = run_for(discovery, choices=d.Choices(browse_requests=4))
    d._runs[run.id] = run
    thread = threading.Thread(target=d._worker, args=(run, discovery.actor, ("fixture", "secret")))
    thread.start()
    assert active.wait(2)
    d.stop(discovery.actor, "session", run.id)
    thread.join(2)
    assert not thread.is_alive() and run.state == "stopped" and not run.raws
    assert Slow.calls == ["oauth"] and run.counts["total"] == 1
    records = ledger(discovery).read_text()
    assert '"state":"uncertain"' in records


@pytest.mark.parametrize("failure", ["http", "interrupt", "too_many"])
def test_failure_ends_action_without_retry(discovery, failure):
    class Fails(FakeTransport):
        calls = []

        async def request(self, stage, **kwargs):
            self.calls.append(stage)
            if stage == "browse":
                if failure == "http":
                    raise ProviderFailure(stage, 401)
                if failure == "interrupt":
                    raise ConnectionError("CANARY_SECRET_BODY")
                return {"itemSummaries": [{"itemId": str(n)} for n in range(21)]}
            return dict(access_token="CANARY_TOKEN", expires_in=300, token_type="Bearer")

    discovery.monkeypatch.setattr(d, "Transport", Fails)
    run = run_for(discovery, choices=d.Choices(browse_requests=4))
    d._worker(run, discovery.actor, ("fixture", "secret"))
    assert run.state == "failed" and Fails.calls == ["oauth", "browse"]
    assert not run.raws and "CANARY" not in run.error


def test_request_and_overall_deadlines(discovery):
    class Slow(FakeTransport):
        calls = []

        async def request(self, stage, **kwargs):
            self.calls.append((stage, kwargs["timeout"]))
            await asyncio.sleep(0.2)
            return await super().request(stage, **kwargs)

    discovery.monkeypatch.setattr(d, "Transport", Slow)
    discovery.monkeypatch.setattr(d, "REQUEST_SECONDS", 0.03)
    discovery.monkeypatch.setattr(d, "OVERALL_SECONDS", 0.05)
    run = run_for(discovery)
    began = time.monotonic()
    d._worker(run, discovery.actor, ("fixture", "secret"))
    assert time.monotonic() - began < 0.5
    assert run.state == "failed" and run.counts["total"] == 1
    assert Slow.calls[0][1] <= 0.03


@pytest.mark.parametrize("slow_call", [1, 3])
def test_overall_watchdog_blocks_slow_authorization_dispatch_and_publication(discovery, slow_call):
    entered, release = threading.Event(), threading.Event()
    calls = 0
    clock = SimpleNamespace(now=time.monotonic())
    watchdogs = []

    class ControlledTimer:
        def __init__(self, interval, callback, args):
            self.interval, self.callback, self.args = interval, callback, args

        def start(self):
            watchdogs.append(self)

    def authorize(actor):
        nonlocal calls
        calls += 1
        if calls == slow_call:
            entered.set()
            assert release.wait(10)

    FakeTransport.calls = []
    discovery.monkeypatch.setattr(d, "Transport", FakeTransport)
    discovery.monkeypatch.setattr(d, "_authorize", authorize)
    # Reach the selected authorization boundary before expiring acquisition.
    # Real disk accounting/thread scheduling must not race a 40 ms deadline.
    # The adjacent timer test exercises actual timer scheduling separately.
    discovery.monkeypatch.setattr(d, "time", SimpleNamespace(monotonic=lambda: clock.now))
    discovery.monkeypatch.setattr(d, "Timer", ControlledTimer)
    run = run_for(discovery)
    d._runs[run.id] = run
    thread = threading.Thread(target=d._worker, args=(run, discovery.actor, ("fixture", "secret")))
    thread.start()
    try:
        assert entered.wait(5)
        assert len(watchdogs) == 1
        watchdog = watchdogs[0]
        assert watchdog.interval == d.OVERALL_SECONDS
        clock.now = run.deadline + 1
        watchdog.callback(*watchdog.args)
        assert run.cancel.is_set()
        assert run.timed_out and run.state == "failed" and not run.raws
        assert d.status(discovery.actor, "session", run.id)["results"] == []
    finally:
        release.set()
        thread.join(5)
    assert not thread.is_alive() and run.state == "failed" and not run.raws
    assert [stage for stage, _ in FakeTransport.calls] == ([] if slow_call == 1 else ["oauth", "browse"])


def test_overall_timer_preserves_timely_results_and_rejects_late_publication(discovery):
    discovery.monkeypatch.setattr(d, "OVERALL_SECONDS", 0.03)
    unfinished = run_for(discovery)
    unfinished.state = "running"
    d._arm_deadline(unfinished)
    assert unfinished.cancel.wait(0.5)
    assert unfinished.state == "failed" and unfinished.timed_out

    finished = run_for(discovery)
    finished.id = "finished"
    d._arm_deadline(finished)
    finished.acquired_at = time.monotonic()
    finished.state = "complete"
    finished.raws = [{"itemId": "timely"}]
    assert not finished.cancel.wait(0.06)
    assert finished.state == "complete" and finished.raws
    # Local reads enforce the boundary even if a delayed callback or stale
    # worker attempted to publish after its fixed deadline.
    late = run_for(discovery)
    late.id = "late"
    late.deadline = time.monotonic() - 1
    late.acquired_at = time.monotonic()
    late.state = "complete"
    late.raws = [{"itemId": "late"}]
    d._runs[late.id] = late
    status = d.status(discovery.actor, "session", late.id)
    assert status["state"] == "failed" and not status["results"] and not late.raws


def test_expiry_erases_provider_content_without_browser_poll(discovery):
    run = run_for(discovery)
    run.state = "complete"
    run.raws = [{"itemId": "item", "title": "CANARY_PROVIDER_CONTENT"}]
    run.seen = {"item"}
    run.revealed = {"handle"}
    d._runs[run.id] = run
    d._expire(run.id)
    assert run.state == "expired" and run.cancel.is_set()
    assert not run.raws and not run.seen and not run.revealed


def test_account_revocation_inflight_blocks_publication_and_next_dispatch(discovery):
    from django.core.exceptions import PermissionDenied

    revoked = False

    def verified(who):
        if revoked:
            raise PermissionDenied
        return who

    class Revokes(FakeTransport):
        calls = []

        async def request(self, stage, **kwargs):
            nonlocal revoked
            self.calls.append(stage)
            if stage == "browse":
                revoked = True
                return {"itemSummaries": [{"itemId": "one"}]}
            return dict(access_token="token", expires_in=300, token_type="Bearer")

    discovery.monkeypatch.setattr(d.store, "verified", verified)
    discovery.monkeypatch.setattr(d, "Transport", Revokes)
    run = run_for(discovery, choices=d.Choices(browse_requests=4))
    d._worker(run, discovery.actor, ("fixture", "secret"))
    assert run.state == "failed" and not run.raws
    assert Revokes.calls == ["oauth", "browse"]


@pytest.mark.parametrize("label", ["Bearer", "Application Access Token", "application access token"])
def test_documented_application_token_label(discovery, label):
    class Label(FakeTransport):
        async def request(self, stage, **kwargs):
            if stage == "oauth":
                return dict(access_token="token", expires_in=300, token_type=label)
            return {"itemSummaries": []}

    discovery.monkeypatch.setattr(d, "Transport", Label)
    run = run_for(discovery)
    d._worker(run, discovery.actor, ("fixture", "secret"))
    assert run.state == "complete"


def test_exact_transport_country_only_20_no_paging_or_redirect():
    requests = []

    class Stream(httpx.AsyncByteStream):
        def __init__(self, body):
            self.body = json.dumps(body).encode()

        async def __aiter__(self):
            yield self.body

    async def handler(request):
        requests.append(request)
        if request.url.path.endswith("token"):
            return httpx.Response(200, stream=Stream({"access_token": "fake", "expires_in": 300}))
        return httpx.Response(200, stream=Stream({"itemSummaries": [], "next": "https://bad.invalid"}))

    async def execute():
        transport = Transport(transport=httpx.MockTransport(handler))
        try:
            await transport.request("oauth", timeout=30, credentials=("fixture", "secret"))
            await transport.request("browse", timeout=30, token="fake", query="Pokemon Base Set Abra 43")
        finally:
            await transport.close()

    asyncio.run(execute())
    assert len(requests) == 2
    request = requests[1]
    assert request.headers["x-ebay-c-marketplace-id"] == "EBAY_US"
    assert dict(request.url.params) == {
        "q": "Pokemon Base Set Abra 43",
        "filter": "buyingOptions:{FIXED_PRICE|AUCTION},deliveryCountry:US,itemLocationCountry:US",
        "limit": "20",
        "offset": "0",
        "fieldgroups": "EXTENDED",
        "sort": "endingSoonest",
    }
    assert "x-ebay-c-enduserctx" not in request.headers
    assert all(v <= 30 for v in request.extensions["timeout"].values())


def test_selected_set_typed_query_and_captured_provider_choices_reach_wire(discovery):
    FakeTransport.calls = []
    discovery.monkeypatch.setattr(d, "Transport", FakeTransport)

    class Immediate:
        def __init__(self, target, args, **kwargs):
            self.target, self.args = target, args

        def start(self):
            self.target(*self.args)

    discovery.monkeypatch.setattr(d, "threading", SimpleNamespace(Thread=Immediate))
    result = d.start(
        discovery.actor,
        "session",
        {
            "query": "Abra base 2",
            "set_id": "base_set",
            "product_type": "mixed_lots",
            "sort": "ending_soonest",
            "english_vintage": True,
        },
    )
    assert result["state"] == "complete"
    browse = next(kwargs for stage, kwargs in FakeTransport.calls if stage == "browse")
    assert browse["query"] is None
    assert browse["search_options"]["named"].query == "Abra English"
    assert browse["search_options"]["named"].set_name == "Base Set"
    assert "2" not in browse["search_options"]["named"].query
    assert browse["search_options"]["named"].sort == "ending_soonest"
    assert browse["search_options"]["named"].category == "183455"
    assert result["choices"]["product_type"] == "mixed_lots"


def test_revoked_login_after_response_prevents_discovery_publication(discovery):
    from django.core.exceptions import PermissionDenied

    revoked, checks = [], []

    class RevokedAtResponse(FakeTransport):
        calls = []

        async def request(self, stage, **kwargs):
            result = await super().request(stage, **kwargs)
            if stage == "browse":
                revoked.append(True)
            return result

    def authorize(actor, session=None):
        checks.append(session)
        if revoked:
            raise PermissionDenied

    discovery.monkeypatch.setattr(d, "Transport", RevokedAtResponse)
    discovery.monkeypatch.setattr(d, "_authorize", authorize)
    run = run_for(discovery)
    run.auth_session = "real-django-session-key"
    d._worker(run, discovery.actor, ("fixture-client", "secret"))
    assert run.state == "failed" and run.raws == []
    assert checks == [run.auth_session] * 3
    assert [stage for stage, _ in RevokedAtResponse.calls] == ["oauth", "browse"]
    assert run.counts["total"] == 2
