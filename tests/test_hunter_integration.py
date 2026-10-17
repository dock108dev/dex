"""Traversal/API integration in disposable engineering roots; fake transport only."""

import asyncio
import json
import threading
from datetime import UTC, datetime

import pytest
from django.http import Http404
from test_hunter import Fake
from test_hunter import hunt as hunt

from pokemon_hunter.beta import hunter as h
from pokemon_hunter.beta import hunter_budget as b
from pokemon_hunter.beta import hunter_traversal as t


def traversal(env, *, scope="singles"):
    plan = t.build_plan(datetime.now(UTC), scope=scope)
    allowance = b.TraversalAllowance(
        "hunt-04-engineering", oauth=1, browse=12, total=13, auction=8, buy_it_now=4, lots=12
    )
    run = h.Run(
        "traversal-fixture",
        (str(env.root), env.actor.user_id, "binding"),
        h.discovery.Choices(english_vintage=False),
        None,
        [],
        window={"start": plan.start, "end": plan.end},
        traversal=plan,
        allowance=allowance,
        action_counts={},
    )
    h._runs[run.id] = run
    return run


class Pages(Fake):
    async def request(self, stage, **kwargs):
        self.calls.append((stage, {}))
        if stage == "oauth":
            return {"access_token": "CANARY_TOKEN", "expires_in": 300, "token_type": "Bearer"}
        request = kwargs["search_options"]["hunter"]
        return {
            "itemSummaries": [
                {
                    "itemId": f"v1|{request.ordinal * 200 + i}|0",
                    "buyingOptions": ["FIXED_PRICE"],
                    "title": "Fixture",
                    "price": {"value": "1", "currency": "USD"},
                }
                for i in range(200)
            ],
            "offset": request.offset,
            "next": f"https://evil.invalid/?offset={request.offset + 200}",
            "total": 999999,
        }


def test_disabled_new_acquisition_preserves_old_allowance(hunt):
    with pytest.raises(ValueError, match="allowance"):
        h.start(hunt.actor, "binding", {})
    assert not Fake.calls and not b.path(hunt.root).exists()
    assert h.metadata(hunt.actor, "binding")["traversal_remaining"]["total"] == 0


def test_finite_continuations_same_window_lease_chunked_and_local_pages(hunt):
    hunt.monkeypatch.setattr(h, "Transport", Pages)
    run = traversal(hunt)
    created = run.created
    window = dict(run.window)
    sizes = []

    def compare(actor, raws, **kw):
        sizes.append(len(raws))
        return [{"item_id": raw["itemId"], "hunt_status": "unmatched", "reference": None} for raw in raws]

    hunt.monkeypatch.setattr(h.hunter_catalog, "compare", compare)
    for action in range(6):
        if action:
            run.action_counts = {}
        asyncio.run(h._acquire_traversal(run, ("fixture-client", "secret")))
    assert len(Fake.calls) == 13
    assert run.created == created and run.window == window
    assert len(run.raws) == 800 and len(run.seen) == 2400
    assert run.coverage_counts["fetched"] == 2400
    assert run.coverage_counts["unique"] == 2400
    assert run.coverage_counts["skipped"] == 1600
    first = h.status(hunt.actor, "binding", run.id)
    assert len(first["results"]) == 200 and first["result_page"]["remaining"] == 600
    assert len(json.dumps(first).encode()) <= h.hunter_query.RESPONSE_BYTE_LIMIT
    second = h.status(hunt.actor, "binding", run.id, cursor=first["result_cursor"])
    assert len(second["results"]) == 200
    assert first["results"][0]["id"] != second["results"][0]["id"]
    assert max(sizes) <= 400 and sizes == [400, 400]
    assert first["coverage"]["rejected"] == 400
    assert not first["has_next"] and not first["coverage_complete"]
    assert b.remaining_traversal(hunt.root, run.allowance)["total"] == 0
    assert not b.path(hunt.root).exists()
    assert len(Fake.calls) == 13


def test_continuation_is_explicit_exact_and_atomic(hunt):
    run = traversal(hunt)
    run.state = "complete"
    run.next_index = 2
    launches = []
    hunt.monkeypatch.setattr(h, "_launch", lambda *args: launches.append(args))
    for raw in (
        {"cursor": "bad"},
        {"cursor": run.traversal.cursor(0)},
        {"cursor": run.traversal.cursor(2), "scope": "lots"},
    ):
        with pytest.raises(ValueError):
            h.continue_run(hunt.actor, "binding", run.id, raw)
    cursor = run.traversal.cursor(2)
    result = h.continue_run(hunt.actor, "binding", run.id, {"cursor": cursor})
    assert result["state"] == "queued" and len(launches) == 1
    with pytest.raises(ValueError):
        h.continue_run(hunt.actor, "binding", run.id, {"cursor": cursor})
    with pytest.raises(Http404):
        h.continue_run(hunt.actor, "another-session", run.id, {"cursor": cursor})


def test_stopped_later_page_does_not_publish(hunt):
    entered = threading.Event()

    class Slow(Pages):
        async def request(self, stage, **kwargs):
            entered.set()
            await asyncio.sleep(3)
            return await super().request(stage, **kwargs)

    hunt.monkeypatch.setattr(h, "Transport", Slow)
    run = traversal(hunt)
    worker = threading.Thread(target=h._worker, args=(run, hunt.actor, ("fixture-client", "secret")))
    worker.start()
    assert entered.wait(2)
    h.stop(hunt.actor, "binding", run.id)
    worker.join(2)
    assert not worker.is_alive() and not run.raws and run.state == "stopped"
    assert b.remaining_traversal(hunt.root, run.allowance)["oauth"] == 0


def test_overlap_latest_observation_variation_and_lot_eligibility(hunt):
    class Overlap(Pages):
        async def request(self, stage, **kwargs):
            result = await super().request(stage, **kwargs)
            if stage == "browse":
                request = kwargs["search_options"]["hunter"]
                result["itemSummaries"] = [
                    {
                        "itemId": "v1|123|7",
                        "buyingOptions": ["FIXED_PRICE"],
                        "price": {"value": str(request.ordinal + 1), "currency": "USD"},
                        "leafCategoryIds": ["183455"],
                    },
                    {"itemId": "v1|123|8", "buyingOptions": ["FIXED_PRICE"], "leafCategoryIds": ["183455"]},
                ]
            return result

    hunt.monkeypatch.setattr(h, "Transport", Overlap)
    run = traversal(hunt, scope="lots")
    asyncio.run(h._acquire_traversal(run, ("fixture-client", "secret")))
    assert len(run.raws) == 2 and run.coverage_counts["duplicates"] == 2
    assert run.raws[0]["price"]["value"] == "2"
    result = h.status(hunt.actor, "binding", run.id)
    assert result["coverage"]["unmatched"] == 2
    assert result["traversal_coverage"]["unique"] == 2


def test_empty_partitions_skip_remaining_pages_without_phantom_continuation(hunt):
    class Empty(Pages):
        async def request(self, stage, **kwargs):
            payload = await super().request(stage, **kwargs)
            if stage == "browse":
                payload["itemSummaries"] = []
                payload.pop("next")
                payload["total"] = 0
            return payload

    hunt.monkeypatch.setattr(h, "Transport", Empty)
    run = traversal(hunt)
    for action in range(3):
        run.action_counts = {}
        asyncio.run(h._acquire_traversal(run, ("fixture-client", "secret")))
    assert run.next_index == len(run.traversal.requests)
    assert not h.status(hunt.actor, "binding", run.id)["has_next"]
    assert run.coverage_counts["skipped_pages"] == 7
    assert len(Fake.calls) == 6  # one token plus each of five partitions


def test_local_cursor_rejects_changed_reference_ordering(hunt):
    hunt.monkeypatch.setattr(h, "Transport", Pages)
    run = traversal(hunt)
    asyncio.run(h._acquire_traversal(run, ("fixture-client", "secret")))
    first = h.status(hunt.actor, "binding", run.id)
    assert first["result_cursor"]
    hunt.monkeypatch.setattr(
        h.hunter_catalog,
        "compare",
        lambda actor, raws, **kw: [
            {
                "item_id": raw["itemId"],
                "hunt_status": "unpriced",
                "reference": None,
                "reason": "reference_withdrawn",
            }
            for raw in raws
        ],
    )
    with pytest.raises(ValueError, match="cursor"):
        h.status(hunt.actor, "binding", run.id, cursor=first["result_cursor"])
    assert len(Fake.calls) == 3


def test_catalog_change_between_comparison_chunks_fails_closed(hunt):
    run = traversal(hunt)
    run.state = "complete"
    run.raws = [
        {
            "itemId": str(i),
            "buyingOptions": ["FIXED_PRICE"],
            "_hunt_lanes": ["buy_it_now"],
            "_hunt_observed_at": run.window["start"],
        }
        for i in range(501)
    ]
    versions = iter([1, 2])
    hunt.monkeypatch.setattr(h.collection, "generation", lambda *args: next(versions))
    with pytest.raises(h.collection.Conflict, match="between"):
        h.status(hunt.actor, "binding", run.id)
    assert not Fake.calls


def test_cross_singles_lot_paths_share_latest_exact_variation_observation(hunt):
    class Across(Pages):
        async def request(self, stage, **kwargs):
            payload = await super().request(stage, **kwargs)
            if stage == "browse":
                request = kwargs["search_options"]["hunter"]
                payload["itemSummaries"] = [
                    {
                        "itemId": "v1|99|7",
                        "title": request.scope,
                        "buyingOptions": ["FIXED_PRICE"],
                        "leafCategoryIds": ["183455" if request.scope == "lots" else "183454"],
                        "price": {"value": str(request.ordinal + 1), "currency": "USD"},
                    }
                ]
            return payload

    hunt.monkeypatch.setattr(h, "Transport", Across)
    run = traversal(hunt, scope="both")
    for _ in range(6):
        run.action_counts = {}
        asyncio.run(h._acquire_traversal(run, ("fixture-client", "secret")))
    assert len(run.raws) == 1 and run.coverage_counts["duplicates"] == 11
    assert run.raws[0]["_hunt_scopes"] == ["lots", "singles"]
    assert run.raws[0]["price"]["value"] == "12"
    assert run.raws[0]["leafCategoryIds"] == ["183455"]
    result = h.status(hunt.actor, "binding", run.id)
    assert result["coverage"]["unmatched"] == 1
    assert b.remaining_traversal(hunt.root, run.allowance)["lots"] == 6
