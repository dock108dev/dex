"""Offline finite-plan, checked-wire and original-cursor qualification."""

import asyncio
import json
import threading
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
import pytest

from pokemon_hunter.beta import hunter_query as query
from pokemon_hunter.beta import hunter_traversal as traversal
from pokemon_hunter.beta.discovery_transport import ProviderFailure, Transport

START = datetime(2026, 11, 1, 0, 30, tzinfo=ZoneInfo("America/New_York"))


class Stream(httpx.AsyncByteStream):
    def __init__(self, payload):
        self.body = json.dumps(payload).encode()

    async def __aiter__(self):
        yield self.body


def test_plan_captures_utc_day_across_fall_clock_change_and_inclusive_overlap():
    plan = traversal.build_plan(START)
    assert plan.start == "2026-11-01T04:30:00Z"
    assert plan.end == "2026-11-02T04:30:00Z"
    assert len(plan.requests) == 12 and len(plan.partitions) == 5
    assert max(p.depth for p in plan.partitions) == 2
    auctions = plan.partitions[:-1]
    assert auctions[0].start == plan.start and auctions[-1].end == plan.end
    assert all(left.end == right.start for left, right in zip(auctions, auctions[1:]))
    assert plan == traversal.build_plan(START.astimezone(UTC))
    for request in plan.requests:
        assert (request.window_start, request.window_end) == (plan.start, plan.end)
        assert query.checked_params(request)["offset"] == request.offset
    assert plan.public()["limits"] == {
        "cumulative_summaries": 2400,
        "pages": 12,
        "partitions": 8,
        "partition_depth": 2,
        "retained_summaries": 800,
        "comparison_chunk": 400,
        "response_summaries": 200,
        "action_pages": 2,
        "page_summaries": 200,
        "page_bytes": 2 * 1024 * 1024,
    }


def test_separate_loose_lot_category_and_same_broad_filter_semantics():
    singles, lots = (traversal.build_plan(START, scope=scope) for scope in traversal.SCOPES)
    assert singles.id != lots.id
    for request in lots.requests:
        params = query.checked_params(request)
        assert params["category_ids"] == "183455"
        assert params["aspect_filter"] == "categoryId:183455,Game:{Pokémon TCG},Language:{English}"
        assert "q" not in params
        assert ("itemEndDate" in params["filter"]) == (request.lane == "auction")
        assert params["offset"] <= 600
    raw = {"buyingOptions": ["FIXED_PRICE"], "leafCategoryIds": ["183455"]}
    assert query.lane_eligibility(raw, "buy_it_now", lots.start, lots.end, now=START, scope="lots") is None
    assert query.lane_eligibility(raw, "buy_it_now", lots.start, lots.end, now=START) == "scope_conflict"


def test_composite_plan_keeps_caps_and_internally_checks_each_scope():
    plan = traversal.build_plan(START, scope="both")
    assert len(plan.requests) == 12 and len(plan.partitions) == 6
    assert max(partition.depth for partition in plan.partitions) == 1
    assert plan.public()["acquisition_scopes"] == ["singles", "lots"]
    assert sum(request.limit for request in plan.requests) == 2400
    for actual_scope in traversal.SCOPES:
        requests = [request for request in plan.requests if request.scope == actual_scope]
        assert len(requests) == 6
        assert sum(request.lane == "auction" for request in requests) == 4
        auctions = [
            partition
            for partition in plan.partitions
            if partition.scope == actual_scope and partition.lane == "auction"
        ]
        assert auctions[0].start == plan.start and auctions[0].end == auctions[1].start
        assert auctions[1].end == plan.end
        for request in requests:
            assert request.plan_scope == "both" and request.plan_id == plan.id
            assert query.checked_params(request)["category_ids"] == (
                "183454" if actual_scope == "singles" else "183455"
            )
            with pytest.raises(ValueError):
                query.checked_params(replace(request, plan_scope=actual_scope))
    assert plan.cursor() != traversal.build_plan(START).cursor()


@pytest.mark.parametrize(
    "changes",
    [
        {"offset": 9999},
        {"offset": False},
        {"offset": 0.0},
        {"limit": True},
        {"scope": "other"},
        {"plan_id": "client-plan"},
        {"start": "2026-11-01T04:30:01Z"},
        {"end": "2026-11-04T04:30:00Z"},
        {"partition_depth": 3},
        {"partition_id": "untrusted"},
        {"ordinal": True},
        {"window_end": "2026-11-03T04:30:00Z"},
    ],
)
def test_transport_rebuild_rejects_forged_request(changes):
    request = replace(traversal.build_plan(START).requests[0], **changes)
    with pytest.raises(ValueError):
        query.checked_params(request)


@pytest.mark.parametrize("cursor", [None, 0, "", "00:x", "99:x", "-1:x", "0:x", "0:" + "x" * 100])
def test_cursor_malformed_or_outside_plan_fails(cursor):
    with pytest.raises(ValueError):
        traversal.build_plan(START).request(cursor)


def test_cursors_bind_original_plan_and_advance_to_finite_end():
    plan = traversal.build_plan(START)
    other = traversal.build_plan(START + timedelta(seconds=1))
    with pytest.raises(ValueError):
        other.request(plan.cursor())
    cursor = plan.cursor()
    for index in range(12):
        assert plan.index(cursor) == index
        assert plan.request(cursor) is plan.requests[index]
        cursor = plan.next_cursor(cursor)
    assert cursor is None


def test_hint_urls_are_never_dispatch_instructions_and_totals_are_advisory():
    request = traversal.build_plan(START).requests[0]
    hint = traversal.inspect_page(
        request,
        {
            "itemSummaries": [{"itemId": "v1|1|0"}],
            "total": 0,
            "next": "https://evil.invalid/path?offset=9999&q=Mew&filter=arbitrary",
        },
    )
    assert hint["total_inconsistent"] and hint["truncated"]
    assert hint["reason"] == "provider_hints_are_advisory"
    next_request = traversal.build_plan(START).request(traversal.build_plan(START).cursor(1))
    assert query.checked_params(next_request)["offset"] == 0
    assert traversal.inspect_page(request, {"itemSummaries": [], "total": -1})["total_reported"] is None


@pytest.mark.parametrize(
    "payload",
    [
        {"offset": 1},
        {"offset": False},
        {"next": "https://api.ebay.com/search?offset=0"},
        {"next": "https://api.ebay.com/search?offset=200&offset=400"},
        {"next": {"url": "x"}},
        {"next": "x" * 8193},
        {"itemSummaries": [{}] * 201},
        {"itemSummaries": ["malformed"]},
    ],
)
def test_stalled_or_malformed_page_rejected(payload):
    with pytest.raises(ValueError):
        traversal.inspect_page(traversal.build_plan(START).requests[0], payload)


def test_nonadvancing_forward_page_is_rejected():
    request = traversal.build_plan(START).requests[-1]
    assert request.offset == 200
    with pytest.raises(ValueError, match="advance"):
        traversal.inspect_page(request, {"next": "https://api.ebay.com/search?offset=100"})


def test_claim_is_atomic_repeat_fails_and_stop_suppresses_late_publication():
    progress = traversal.Progress(traversal.build_plan(START))
    cursor = progress.cursor
    accepted = []
    barrier = threading.Barrier(8)

    def claim():
        barrier.wait()
        try:
            accepted.append(progress.claim(cursor))
        except ValueError:
            pass

    threads = [threading.Thread(target=claim) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(accepted) == progress.attempted == 1
    progress.stop()
    with pytest.raises(ValueError):
        progress.publish(cursor, {"itemSummaries": [{"itemId": "v1|1|0"}]})
    assert progress.fetched == progress.completed == 0
    assert progress.coverage()["attempted_pages"] == 1


def test_all_captured_pages_have_bounded_cumulative_work_and_no_exhaustiveness_claim():
    progress = traversal.Progress(traversal.build_plan(START))
    for _ in range(12):
        cursor = progress.cursor
        progress.claim(cursor)
        progress.publish(cursor, {"itemSummaries": [{}] * 200, "total": 1000000})
        with pytest.raises(ValueError):
            progress.claim(cursor)
    assert progress.cursor is None
    assert progress.fetched == 2400 and progress.completed == 12
    coverage = progress.coverage()
    assert coverage["remaining_pages"] == coverage["remaining_summaries_upper_bound"] == 0
    assert coverage["truncated_pages"] == 12 and coverage["coverage_complete"] is False


def test_failed_or_uncertain_page_stays_attempted_and_has_no_retry():
    progress = traversal.Progress(traversal.build_plan(START))
    cursor = progress.cursor
    progress.claim(cursor)
    progress.fail(cursor)
    with pytest.raises(ValueError):
        progress.claim(cursor)
    assert progress.attempted == 1 and progress.completed == 0


def test_checked_request_reaches_one_fixed_endpoint_and_response_is_page_bounded():
    sent = []
    request = traversal.build_plan(START, scope="lots").requests[-1]

    async def handler(wire):
        sent.append(wire)
        return httpx.Response(200, stream=Stream({"itemSummaries": [{}] * 200}))

    async def execute():
        transport = Transport(transport=httpx.MockTransport(handler))
        try:
            return await transport.request(
                "browse", timeout=30, token="offline", search_options={"hunter": request}
            )
        finally:
            await transport.close()

    assert len(asyncio.run(execute())["itemSummaries"]) == 200
    assert len(sent) == 1
    assert sent[0].url.host == "api.ebay.com" and sent[0].url.path == "/buy/browse/v1/item_summary/search"
    assert dict(sent[0].url.params) == {
        key: str(value) for key, value in query.checked_params(request).items()
    }


def test_traversal_smaller_page_limit_rejected_at_transport():
    async def handler(wire):
        return httpx.Response(200, stream=Stream({"itemSummaries": [{}, {}]}))

    async def execute():
        transport = Transport(transport=httpx.MockTransport(handler))
        try:
            await transport.request(
                "browse",
                timeout=30,
                token="offline",
                search_options={
                    "hunter": traversal.build_plan(START, page_size=1).requests[0],
                },
            )
        finally:
            await transport.close()

    with pytest.raises(ProviderFailure):
        asyncio.run(execute())
