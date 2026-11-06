"""Authored isolated LV-03 jobs with real journals and controlled HTTP streams."""

import fcntl
import json
import os
import uuid
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import httpx
import pytest
from django.core.exceptions import PermissionDenied
from django.http import Http404
from test_hunter_lots import entries as entries
from test_hunter_lots import raw
from test_hunter_policy import everyday as everyday

from pokemon_hunter.beta import collection, hunter_lots, lot_calculator
from pokemon_hunter.beta import discovery as d
from pokemon_hunter.beta import discovery_comparison as dc
from pokemon_hunter.beta import hunter_policy as policy
from pokemon_hunter.beta import lot_hunt as hunt
from pokemon_hunter.beta import lot_hunt_contract as contract
from pokemon_hunter.beta import lot_hunt_journal as journal
from pokemon_hunter.beta.discovery_transport import Transport


class Stream(httpx.AsyncByteStream):
    def __init__(self, data):
        self.data = data

    async def __aiter__(self):
        yield self.data


def offer(n=0, *, lane="buy_it_now", **changes):
    return raw(
        itemId=f"v1|{123456789012 + n}|0",
        shortDescription="",
        itemEndDate=(datetime.now(UTC) + timedelta(hours=10)).isoformat(),
        buyingOptions=["FIXED_PRICE"] if lane == "buy_it_now" else ["AUCTION"],
        currentBidPrice=dict(value="2", currency="USD"),
        **changes,
    )


@pytest.fixture
def env(everyday, entries, monkeypatch):
    e = everyday
    e.clock.now = datetime.now(UTC)
    e.choose(per_hunt_limit=5, daily_limit=100)
    monkeypatch.setattr(d, "_authorize", lambda *a: None)
    monkeypatch.setattr(d, "_context_current", lambda *a: None)
    monkeypatch.setattr(d.goal_hunts, "snapshot", lambda *a: None)
    monkeypatch.setattr(d, "_tokens", {})
    monkeypatch.setattr(d, "_runs", {})
    monkeypatch.setattr(d.store, "rows", lambda *a: [])
    monkeypatch.setattr(collection, "generation", lambda *a: 1)
    monkeypatch.setattr(hunter_lots, "_catalog", lambda *a: entries)
    monkeypatch.setattr(lot_calculator, "retained_records", lambda: [])
    monkeypatch.setattr(dc, "_reference_cells", lambda *a: ({}, {"raw": "Unavailable"}))
    monkeypatch.setattr(hunt, "_runs", {})
    monkeypatch.setattr(hunt, "_launch", lambda *a: None)
    monkeypatch.setattr(hunt, "close_old_connections", lambda: None)
    e.bin, e.auction = [offer()], [offer(1, lane="auction")]
    e.calls, e.details, e.hook = [], {}, None
    e.fail = set()

    async def handler(request):
        path = request.url.path
        stage = "oauth" if "oauth2" in path else "browse" if "item_summary" in path else "detail"
        e.calls.append(request)
        if e.hook:
            await e.hook(stage, request)
        if stage in e.fail:
            return httpx.Response(503, stream=Stream(b""))
        if stage == "oauth":
            value = dict(access_token="authored-secret", expires_in=3600, token_type="Bearer")
        elif stage == "browse":
            value = dict(itemSummaries=e.bin if "FIXED_PRICE" in request.url.params["filter"] else e.auction)
        else:
            key = path.rsplit("/", 1)[-1]
            source = next(r for r in e.bin + e.auction if r["itemId"] == key)
            value = e.details.get(key, dict(source, description=raw()["shortDescription"]))
        return httpx.Response(200, stream=Stream(json.dumps(value).encode()))

    monkeypatch.setattr(hunt, "Transport", lambda: Transport(transport=httpx.MockTransport(handler)))

    def start(**changes):
        request = dict(query="Pokemon", acquisition_contract=contract.CONTRACT)
        request.update(changes)
        result = d.start_action(e.actor, "session", request, str(uuid.uuid4()))
        return hunt._runs[result["run_id"]]

    def execute(run=None):
        run = run or start()
        hunt._worker(run, e.actor, ("fixture-client", "fixture-secret"))
        return run, hunt.status(e.actor, "session", run.id)

    e.start, e.execute = start, execute
    return e


def test_one_action_automatically_details_and_assesses_without_prices(env):
    run, result = env.execute()
    assert result["state"] == "partial"
    assert result["counts"]["total"] == policy.status(env.actor)["used"] == len(env.calls) == 5
    assert [r.url.path.rsplit("/", 1)[-1] for r in env.calls[:3]] == ["token", "search", "search"]
    assert result["progress"] == dict(
        searched=2,
        received=2,
        unique=2,
        eligible=2,
        enriched=2,
        assessed=2,
        ready=0,
        partial=2,
        unprocessed=0,
    )
    assert all(r["evidence_kind"] == "seller_details" for r in result["results"])
    assert all(r["lot_value"]["total"] is None for r in result["results"])
    assert all(r["lot_value"]["identified_quantity"] == 3 for r in result["results"])
    assert "FIXED_PRICE" in env.calls[1].url.params["filter"]
    assert "itemEndDate" in env.calls[2].url.params["filter"]
    for _ in range(3):
        d.status(env.actor, "session", run.id, values=True)
    assert len(env.calls) == 5
    content = (policy._storage(env.root) / journal.NAME).read_text()
    assert "Charizard" not in content and "authored-secret" not in content and "fixture-secret" not in content


def test_bin_not_starved_by_twenty_auctions_and_unique_cap(env):
    env.auction = [offer(i, lane="auction") for i in range(1, 21)]
    run, result = env.execute()
    assert result["progress"]["eligible"] == 21
    assert result["progress"]["enriched"] == 2
    assert result["progress"]["unprocessed"] == 19
    assert set(run.details) == {env.bin[0]["itemId"], env.auction[0]["itemId"]}
    assert result["reasons"]["candidate_limit"] == 1


def test_duplicate_dual_option_reuses_one_detail_and_keeps_both_prices(env):
    env.bin[0]["buyingOptions"] = ["FIXED_PRICE", "AUCTION"]
    env.auction = deepcopy(env.bin)
    run, result = env.execute()
    assert result["counts"]["total"] == 4 and result["progress"]["unique"] == 1
    assert len(run.details) == 1
    row = result["results"][0]
    assert row["current_bid"] == "2.00" and row["buy_now_price"] == "3.00"
    assert result["reasons"]["duplicate_candidate"] == 1


def test_variations_are_distinct(env):
    env.auction[0]["itemId"] = "v1|123456789012|123456789099"
    _, result = env.execute()
    assert result["progress"]["unique"] == result["progress"]["enriched"] == 2


@pytest.mark.parametrize(
    "shipping",
    [
        [],
        [
            {"shippingCost": {"value": "1", "currency": "USD"}},
            {"shippingCost": {"value": "2", "currency": "USD"}},
        ],
    ],
)
def test_missing_conflicting_detail_shipping_does_not_reuse_summary(env, shipping):
    env.details[env.bin[0]["itemId"]] = dict(
        env.bin[0], shippingOptions=shipping, description=raw()["shortDescription"]
    )
    _, result = env.execute()
    row = result["results"][0]
    assert row["shipping"] is row["delivered_total"] is row["buy_now_delivered_total"] is None


def test_partial_failure_preserves_other_lane_and_no_retry(env):
    async def hook(stage, request):
        if stage == "detail" and env.bin[0]["itemId"] in request.url.path:
            raise httpx.ReadTimeout("private transport text")

    env.hook = hook
    _, result = env.execute()
    assert len(env.calls) == result["counts"]["total"] == 5
    assert result["progress"]["assessed"] == 1
    assert result["state"] == "partial" and result["reasons"]["detail_request_failed"] == 1
    assert len(result["results"]) == 2


def test_stop_during_detail_prevents_late_publication(env):
    run = env.start()

    async def hook(stage, request):
        if stage == "detail":
            hunt.stop(env.actor, "session", run.id)

    env.hook = hook
    _, result = env.execute(run)
    assert result["state"] == "stopped" and result["results"] == []
    assert len(env.calls) == policy.status(env.actor)["used"] == 4
    assert run.raws == [] and run.details == {}


def test_stop_during_assessment_cannot_restore_success(env, monkeypatch):
    run = env.start()
    original = hunt._assess

    def assess(*args):
        value = original(*args)
        hunt.stop(env.actor, "session", run.id)
        return value

    monkeypatch.setattr(hunt, "_assess", assess)
    _, result = env.execute(run)
    assert result["state"] == "stopped" and result["results"] == []
    assert result["progress"]["assessed"] == 0


def test_restart_uncertainty_never_dispatches_or_renews(env, monkeypatch):
    request_id = str(uuid.uuid4())
    raw_request = dict(query="Pokemon", acquisition_contract=contract.CONTRACT)
    response = d.start_action(env.actor, "session", raw_request, request_id)
    run = hunt._runs[response["run_id"]]
    # Simulate a crash after a durable debit and before any response.
    run.dispatch_id = "oauth"
    hunt._admit(run, "oauth")
    monkeypatch.setattr(hunt, "_runs", {})
    monkeypatch.setattr(d, "_runs", {})
    monkeypatch.setattr(journal, "BOOT", "new-process")
    result = d.action_status(env.actor, "session", request_id)
    assert result["state"] == "restart_uncertain"
    assert result["counts"]["total"] == policy.status(env.actor)["used"] == 1
    with pytest.raises(ValueError, match="already submitted"):
        d.start_action(env.actor, "session", raw_request, request_id)
    assert env.calls == []


def test_account_and_navigation_session_isolation(env):
    run, _ = env.execute()
    with pytest.raises(Http404):
        hunt.status(env.actor, "other-session", run.id)
    with pytest.raises(Http404):
        hunt.status(SimpleNamespace(user_id="other", role="owner"), "session", run.id)


def test_revision_conflict_clears_content_and_blocks_next_send(env, monkeypatch):
    run = env.start()

    async def hook(stage, request):
        if stage == "browse":
            monkeypatch.setattr(collection, "generation", lambda *a: 2)

    env.hook = hook
    _, result = env.execute(run)
    assert result["state"] == "conflict" and result["results"] == []
    assert len(env.calls) == 2


def test_revoked_login_clears_content(env, monkeypatch):
    run = env.start()

    async def hook(stage, request):
        if stage == "detail":
            monkeypatch.setattr(d, "_authorize", lambda *a: (_ for _ in ()).throw(PermissionDenied()))

    env.hook = hook
    _, result = env.execute(run)
    assert result["state"] == "unauthorized" and result["results"] == []
    assert len(env.calls) == 4


def test_expiry_clears_original_lease_without_requests(env):
    run, _ = env.execute()
    run.created -= contract.LEASE_SECONDS
    result = hunt.status(env.actor, "session", run.id)
    assert result["state"] == "expired" and not result["results"]
    assert len(env.calls) == 5


def test_worker_busy_terminal_and_explicit_recovery(env):
    path = policy._storage(env.root) / "lot-hunt-worker.lock"
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _, result = env.execute()
        assert result["state"] == "busy" and result["counts"]["total"] == 0
    finally:
        os.close(descriptor)
    _, result = env.execute()
    assert result["progress"]["assessed"] == 2 and len(env.calls) == 5


def test_lost_progress_cannot_rebind_same_consumed_parent(env):
    request_id = str(uuid.uuid4())
    request = dict(query="Pokemon", acquisition_contract=contract.CONTRACT)
    result = d.start_action(env.actor, "session", request, request_id)
    path = policy._storage(env.root) / journal.NAME
    path.unlink()
    with pytest.raises(ValueError, match="already submitted"):
        d.start_action(env.actor, "session", request, request_id)
    assert result["counts"]["total"] == 0


@pytest.mark.parametrize(
    "hours,options,eligible",
    [
        (72, ["AUCTION"], ("auction",)),
        (73, ["AUCTION"], ()),
        (0, ["AUCTION"], ()),
        (73, ["FIXED_PRICE", "AUCTION"], ("buy_it_now",)),
        (None, ["FIXED_PRICE"], ("buy_it_now",)),
        (None, ["AUCTION"], ()),
    ],
)
def test_auction_72_hour_limit_independent_bin(hours, options, eligible):
    now = datetime.now(UTC)
    value = dict(
        buyingOptions=options,
        itemEndDate=(now + timedelta(hours=hours)).isoformat() if hours is not None else None,
    )
    assert contract.lanes(value, now=now) == eligible


def test_action_requires_new_contract_and_never_uses_spent_legacy_allowance(env):
    with pytest.raises(ValueError):
        hunt.start(env.actor, "session", {"query": "Pokemon"}, str(uuid.uuid4()))
    env.choose(per_hunt_limit=3)
    with pytest.raises(ValueError, match="five"):
        env.start()
    assert env.calls == []


def test_shared_budget_exhaustion_after_admission_has_truthful_terminal(env):
    run = env.start()

    async def hook(stage, request):
        if stage == "browse" and len(env.calls) == 2:
            other = env.parent("competing-parent")
            env.choose(per_hunt_limit=5, daily_limit=3)
            env.consume(other, "other-use")

    env.hook = hook
    _, result = env.execute(run)
    assert result["state"] == "exhausted"
    assert len(env.calls) == 2 and result["progress"]["assessed"] == 0
    assert policy.status(env.actor)["used"] == 3


def test_deadline_during_assessment_no_late_publication(env, monkeypatch):
    run = env.start()
    original = hunt._assess

    def assess(*args):
        value = original(*args)
        run.deadline = 0
        hunt._deadline(run)
        return value

    monkeypatch.setattr(hunt, "_assess", assess)
    _, result = env.execute(run)
    assert result["state"] == "exhausted" and result["progress"]["assessed"] == 0
    assert all("lot_value" not in r for r in result["results"])
    assert len(env.calls) == 4


def test_progress_corruption_fail_closed_no_replay(env):
    run = env.start()
    path = policy._storage(env.root) / journal.NAME
    with path.open("ab") as stream:
        stream.write(b'{"unfinished":')
    with pytest.raises(ValueError, match="uncertain"):
        journal.read(run.owner, run.id)
    assert env.calls == []


def test_configured_shipping_context_is_private_and_used(env, monkeypatch):
    monkeypatch.setattr(
        d.ebay_hunts,
        "configuration",
        lambda: (
            SimpleNamespace(environment="production", delivery_postal_code="90876"),
            dict(EBAY_CLIENT_ID="fixture-client", EBAY_CLIENT_SECRET="fixture-secret"),
        ),
    )
    _, result = env.execute()
    for request in env.calls[1:]:
        assert request.headers["X-EBAY-C-ENDUSERCTX"] == "contextualLocation=country%3DUS%2Czip%3D90876"
    assert "90876" not in json.dumps(result)
    assert "90876" not in (policy._storage(env.root) / journal.NAME).read_text()
    assert result["results"][0]["shipping"] == "1.00"


def test_absent_destination_cannot_publish_calculated_shipping(env):
    _, result = env.execute()
    assert all(r["shipping"] is None for r in result["results"])


def test_normalized_ready_and_source_withdrawal(env, monkeypatch):
    from test_hunter_lots import local  # noqa: F401

    enabled = [True]

    def cells(p, records, today, clues):
        if not enabled[0]:
            return {}, {"raw": "Withdrawn"}
        return dict(
            raw=dict(
                amount="10.00",
                currency="USD",
                as_of=today.isoformat(),
                grade="raw",
                grader=None,
                value_scope="per_card",
                match_status="exact",
                provenance="authored",
                source_url="https://example.test/authored",
                raw_record=dict(condition="NM", language="en", edition="unlimited", finish="normal"),
            )
        ), {}

    monkeypatch.setattr(dc, "_reference_cells", cells)
    run, result = env.execute()
    assert result["state"] == "success" and result["progress"]["ready"] == 2
    assert result["results"][0]["lot_value"]["total"] == "30.00"
    enabled[0] = False
    after = hunt.status(env.actor, "session", run.id)
    assert all(r["lot_value"]["total"] is None for r in after["results"])
    assert len(env.calls) == 5


def test_native_assessment_never_enters_normalized_comparison(env, entries, monkeypatch):
    from test_lv02_native_consumers import REFERENCE_CELLS, native_rows

    for entry in entries:
        entry["catalog_version"] = "authored-v1"
    monkeypatch.setattr(dc, "_reference_cells", REFERENCE_CELLS)
    records = native_rows(entries)
    monkeypatch.setattr(lot_calculator, "retained_records", lambda: records)
    _, result = env.execute()
    assert result["state"] == "success" and result["progress"]["ready"] == 2
    value = result["results"][0]["lot_value"]
    assert value["total"] is value["bid_difference"] is value["buy_now_difference"] is None
    assert value["native_guides"][0]["total"] == "30.00"


@pytest.mark.parametrize("kind", ["response", "aggregate", "compressed", "redirect"])
def test_actual_transport_byte_limits_no_retry(kind, monkeypatch):
    from pokemon_hunter.beta.discovery_transport import ProviderFailure

    calls = []

    async def handler(request):
        calls.append(request)
        return httpx.Response(
            302 if kind == "redirect" else 200,
            headers={"content-encoding": "gzip"} if kind == "compressed" else {},
            stream=Stream(b"x" * (contract.RESPONSE_BYTES + 1) if kind == "response" else b'{"ok":1}'),
        )

    meter = contract.ByteBudget()
    if kind == "aggregate":
        meter.used = contract.AGGREGATE_BYTES - 1

    async def execute():
        transport = Transport(transport=httpx.MockTransport(handler))
        try:
            with pytest.raises(ProviderFailure):
                await transport.request(
                    "detail", timeout=1, token="authored", identifier="v1|123456789012|0", byte_budget=meter
                )
        finally:
            await transport.close()

    import asyncio

    asyncio.run(execute())
    assert len(calls) == 1


def test_dispatch_is_reserved_before_transport_and_duplicate_send_rejected(env):
    run = env.start()

    async def hook(stage, request):
        receipt = journal.read(run.owner, run.id)
        assert receipt["counts"]["total"] == len(env.calls)
        assert policy.status(env.actor)["used"] == len(env.calls)

    env.hook = hook
    env.execute(run)
    from pokemon_hunter.beta.discovery_transport import ProviderFailure

    run.dispatch_id = "detail:" + next(iter(run.details))
    with pytest.raises(ProviderFailure):
        hunt._admit(run, "detail")
    assert policy.status(env.actor)["used"] == 5


def test_concurrent_duplicate_start_has_one_durable_parent(env):
    from concurrent.futures import ThreadPoolExecutor

    request_id = str(uuid.uuid4())
    request = dict(query="Pokemon", acquisition_contract=contract.CONTRACT)

    def submit(_):
        try:
            return d.start_action(env.actor, "session", request, request_id)
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, range(2)))
    assert sum(value is not None for value in results) == 1
    with policy._locked(env.root):
        assert len(policy._load(env.root)["parents"]) == 1
    assert env.calls == []


def test_continuation_cannot_renew_automatic_allowance(env):
    run, _ = env.execute()
    with pytest.raises(ValueError, match="No next"):
        d.start(env.actor, "session", {"continuation_run": run.id})
    assert policy.status(env.actor)["used"] == len(env.calls) == 5


def test_elapsed_offer_clears_readiness_without_acquiring(env):
    run, result = env.execute()
    run.raws[0]["itemEndDate"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    result = hunt.status(env.actor, "session", run.id)
    assert len(result["results"]) == 1
    assert result["progress"]["partial"] == 1
    assert len(env.calls) == 5


def test_listing_revision_conflict_rejects_assessment(env, monkeypatch):
    run = env.start()
    original = hunt.discovery_lot_values.project

    def project(*args, **kwargs):
        original(*args, **kwargs)
        run.content_revision += 1

    monkeypatch.setattr(hunt.discovery_lot_values, "project", project)
    _, result = env.execute(run)
    assert result["state"] == "conflict" and result["results"] == []
    assert result["progress"]["assessed"] == 0 and len(env.calls) == 4


def test_stop_between_value_read_and_final_publication_returns_stopped(env, monkeypatch):
    run, _ = env.execute()
    original = hunt._assess

    def assess(*args):
        result = original(*args)
        hunt.stop(env.actor, "session", run.id)
        return result

    monkeypatch.setattr(hunt, "_assess", assess)
    result = hunt.status(env.actor, "session", run.id)
    assert result["state"] == "stopped" and result["results"] == []
    assert len(env.calls) == 5


def test_status_snapshot_serializes_worker_content_without_cancelling_hunt(env, monkeypatch):
    import threading

    run = env.start()
    entered, finished = threading.Event(), threading.Event()
    original = hunt.discovery_listing.received_rows
    workers = []

    def advance():
        entered.set()
        with run.lock:
            run.content_revision += 1
        finished.set()

    def read(raws):
        worker = threading.Thread(target=advance)
        workers.append(worker)
        worker.start()
        assert entered.wait(1)
        assert not finished.wait(0.02)
        return original(raws)

    with monkeypatch.context() as context:
        context.setattr(hunt.discovery_listing, "received_rows", read)
        result = d.status(env.actor, "session", run.id)
    for worker in workers:
        worker.join(timeout=1)
        assert not worker.is_alive()
    assert finished.is_set() and not run.cancel.is_set()
    assert result["state"] == "queued" and result["results"] == []
    assert not env.calls
    _, complete = env.execute(run)
    assert complete["state"] == "partial" and len(env.calls) == 5
