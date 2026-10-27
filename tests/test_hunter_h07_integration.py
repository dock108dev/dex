"""Integrated Hunter contracts: disposable roots and fake I/O only.

These cases join the ordinary Hunter/lot/detail services. Authentication, catalog
and reference cells are controlled fixtures; provider transport never uses a
socket. Source admission itself is covered by the separate reference suites.
"""

import asyncio
import json
import threading
import time
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from django.http import Http404
from test_hunter import hunt as hunt
from test_hunter_lots import printing, raw

from pokemon_hunter.beta import collection, discovery, lot_calculator, store
from pokemon_hunter.beta import discovery_comparison as comparison
from pokemon_hunter.beta import hunter as hunter
from pokemon_hunter.beta import hunter_budget as budget
from pokemon_hunter.beta import hunter_lot_details as details
from pokemon_hunter.beta import hunter_lots as lots
from pokemon_hunter.beta.discovery_transport import ProviderFailure


@pytest.fixture
def integrated(hunt, monkeypatch):
    state = SimpleNamespace(calls=[], references=True, detail_hook=None)
    first = raw(itemId="v1|123456789012|123456789007", leafCategoryIds=["183455"])
    second = raw(itemId="v1|123456789012|123456789008", leafCategoryIds=["183455"])
    state.pages = [[], [first, second]]
    state.bodies = {
        row["itemId"]: dict(
            row,
            title="Pokemon lot of 5 cards",
            shortDescription="",
            description="3x Charizard Base Set 4/102 English Unlimited Non Holo; "
            "2x Blastoise Base Set 2/102 English Unlimited Non Holo",
            price=dict(value="7.00", currency="USD"),
        )
        for row in (first, second)
    }
    entries = [printing("charizard"), printing("blastoise", "Blastoise", number="2/102")]
    monkeypatch.setattr(store, "rows", lambda *a, **kw: [dict(id="pokemon")])
    monkeypatch.setattr(collection, "catalog", lambda *a, **kw: deepcopy(entries))
    monkeypatch.setattr(collection, "generation", lambda *a: 1)
    monkeypatch.setattr(lot_calculator, "retained_records", lambda: [])
    monkeypatch.setattr(hunter, "_launch", lambda *a: None)
    monkeypatch.setattr(details, "_worker", lambda *a: None)

    def cells(printing, records, today, clues):
        if not state.references:
            return {}, {"raw": "Controlled withdrawn reference"}
        return dict(
            raw=dict(
                amount="10.00" if printing["id"] == "charizard" else "5.00",
                currency="USD",
                as_of=today.isoformat(),
                grade="raw",
                grader=None,
                value_scope="per_card",
                match_status="exact",
                provenance="controlled_engineering_reference",
                raw_record=dict(condition="NM", language="en", edition="unlimited", finish="normal"),
            )
        ), {}

    monkeypatch.setattr(comparison, "_reference_cells", cells)

    class FakeTransport:
        async def request(self, stage, **kwargs):
            state.calls.append((stage, kwargs.get("identifier")))
            if stage == "oauth":
                return dict(access_token="offline-token", expires_in=3600, token_type="Bearer")
            if stage == "browse":
                request = kwargs["search_options"]["hunter"]
                return dict(
                    itemSummaries=deepcopy(state.pages[request.ordinal % len(state.pages)]),
                    offset=request.offset,
                    next=f"https://ignored.invalid/?offset={request.offset + 200}",
                    total=0,
                )
            assert stage == "detail"
            if state.detail_hook:
                state.detail_hook(kwargs["identifier"])
            return deepcopy(state.bodies[kwargs["identifier"]])

        async def close(self):
            pass

    monkeypatch.setattr(hunter, "Transport", FakeTransport)
    monkeypatch.setattr(details, "Transport", FakeTransport)
    selected = budget.TraversalAllowance(
        "hunt-04-hunt07-integrated-offline",
        oauth=1,
        browse=12,
        detail=2,
        total=15,
        auction=8,
        buy_it_now=4,
        lots=8,
    )
    monkeypatch.setattr(budget, "TRAVERSAL_ALLOWANCE", selected)
    lots._reviews.clear()
    details._runs.clear()
    state.env = hunt
    state.allowance = selected
    yield state
    for action in list(details._runs.values()):
        action.cancel.set()
    details._runs.clear()
    lots._reviews.clear()


def acquire(state, *, scope="lots"):
    actor = state.env.actor
    started = hunter.start(actor, "binding", dict(scope=scope))
    parent = hunter._runs[started["run_id"]]
    asyncio.run(hunter._acquire_traversal(parent, ("fixture-client", "CANARY_SECRET"), actor))
    return parent, hunter.status(actor, "binding", parent.id)


def acquire_detail(state, parent, result_ids):
    actor = state.env.actor
    started = details.start(actor, "binding", parent.id, result_ids)
    action = details._runs[started["detail_action_id"]]
    asyncio.run(details._acquire(action, actor, "binding", ("fixture-client", "CANARY_SECRET")))
    return action, details.status(actor, "binding", action.id)


def correct_detail(state, review):
    # The newly fetched description contradicts the retained summary. A person
    # must resolve those quantity claims before the five-card lot can be valued.
    return lots.correct(
        state.env.actor,
        "binding",
        review["review_id"],
        dict(
            revision=review["revision"],
            cards=[dict(printing_id="charizard", quantity=3), dict(printing_id="blastoise", quantity=2)],
            unknown_contents=0,
            costs=dict(tax="0", other_costs="0"),
        ),
    )


def test_dst_window_latest_observation_and_all_fetched_dispositions(integrated, monkeypatch):
    # The local clock falls back during this captured 24-hour UTC interval.
    clock = SimpleNamespace(now=datetime(2026, 11, 1, 1, 30, tzinfo=ZoneInfo("America/New_York")))

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock.now.astimezone(tz) if tz else clock.now.replace(tzinfo=None)

    monkeypatch.setattr(hunter, "datetime", Clock)
    start = clock.now.astimezone(UTC)
    end = start + timedelta(hours=24)

    def auction(item_id, ending, **changes):
        return dict(
            itemId=item_id,
            buyingOptions=["AUCTION"],
            itemEndDate=ending.isoformat(),
            leafCategoryIds=["183454"],
            **changes,
        )

    integrated.pages = [
        [
            auction("v1|1|0", start),
            auction("v1|2|0", end.astimezone(ZoneInfo("America/New_York"))),
            auction("v1|3|0", end + timedelta(microseconds=1)),
            auction("v1|4|0", start + timedelta(hours=1), currentBidPrice=dict(value="2", currency="USD")),
            {"itemId": ""},
        ],
        [
            dict(itemId="v1|4|0", buyingOptions=["FIXED_PRICE"], price=dict(value="9", currency="USD")),
            dict(
                itemId="v1|5|0",
                buyingOptions=["FIXED_PRICE"],
                estimatedAvailabilities=[dict(estimatedAvailabilityStatus="OUT_OF_STOCK")],
            ),
        ],
    ]
    parent, result = acquire(integrated, scope="singles")
    assert parent.window == dict(start="2026-11-01T05:30:00Z", end="2026-11-02T05:30:00Z")
    rows = {row["id"]: row for row in result["results"]}
    for item_id, reason in (
        ("v1|1|0", "ended_offer"),
        ("v1|3|0", "outside_auction_window"),
        ("v1|5|0", "unavailable"),
    ):
        assert rows[hunter._handle(parent, item_id)]["reason"] == reason
    changed = hunter.summary_lease(
        integrated.env.actor, "binding", parent.id, hunter._handle(parent, "v1|4|0")
    )
    assert changed["raw"]["price"]["value"] == "9" and "currentBidPrice" not in changed["raw"]
    assert changed["raw"]["_hunt_lanes"] == ["auction", "buy_it_now"]
    coverage = result["traversal_coverage"]
    assert {
        key: coverage[key] for key in ("fetched", "unique", "duplicates", "rejected", "retained", "skipped")
    } == dict(fetched=7, unique=5, duplicates=1, rejected=1, retained=5, skipped=0)
    assert coverage["fetched"] == coverage["unique"] + coverage["duplicates"] + coverage["rejected"]
    assert coverage["unique"] == coverage["retained"] + coverage["skipped"]
    assert result["coverage"]["rejected"] == 4 and result["coverage"]["unmatched"] == 2
    assert coverage["reasons"]["inconsistent_provider_total"] == 2
    assert not result["coverage_complete"] and len(integrated.calls) == 3


def test_auction_expiry_invalidates_real_local_page_cursor_without_acquisition(integrated, monkeypatch):
    clock = SimpleNamespace(now=datetime(2026, 11, 1, 5, 30, tzinfo=UTC))

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock.now.astimezone(tz) if tz else clock.now.replace(tzinfo=None)

    monkeypatch.setattr(hunter, "datetime", Clock)
    integrated.pages = [
        [
            dict(
                itemId=f"v1|{index}|0",
                buyingOptions=["AUCTION"],
                itemEndDate=(clock.now + timedelta(seconds=1)).isoformat(),
            )
            for index in range(200)
        ],
        [dict(itemId="v1|201|0", buyingOptions=["FIXED_PRICE"])],
    ]
    parent, first = acquire(integrated, scope="singles")
    assert first["result_page"]["remaining"] == 1
    second = hunter.status(integrated.env.actor, "binding", parent.id, cursor=first["result_cursor"])
    assert second["result_page"]["offset"] == 200
    clock.now += timedelta(seconds=1)
    with pytest.raises(hunter.InvalidResultCursor):
        hunter.status(integrated.env.actor, "binding", parent.id, cursor=first["result_cursor"])
    fresh = hunter.status(integrated.env.actor, "binding", parent.id)
    assert fresh["result_page"]["offset"] == 0
    assert fresh["coverage"]["rejected"] == 200 and fresh["coverage"]["unmatched"] == 1
    assert len(integrated.calls) == 3


def test_listing_to_local_review_to_official_detail_and_correction_share_budget(integrated):
    actor = integrated.env.actor
    parent, result = acquire(integrated)
    created = parent.created
    result_id = result["results"][0]["id"]
    local = lots.analyze(actor, "binding", parent.id, result_id)
    assert local["comparison"]["priced_card_quantity"] == 3
    assert local["comparison"]["result"]["known_selected_subtotal"] == "25.00"
    before = budget.remaining_traversal(integrated.env.root, integrated.allowance)
    intent = lots.detail_intent(actor, "binding", parent.id, [result_id])
    assert intent["dispatch_allowed"] and not intent["intent_grants_capacity"]
    assert len(integrated.calls) == 3
    action, loaded = acquire_detail(integrated, parent, [result_id])
    review = loaded["reviews"][0]
    assert action.created == created and parent.created == created
    assert action.cancel is not parent.cancel and action.lock is parent.lock
    assert [stage for stage, _ in integrated.calls] == ["oauth", "browse", "browse", "detail"]
    assert review["provenance"]["detail_fetched"] and review["comparison"]["priced_card_quantity"] == 0
    assert review["proposal"]["quantity_issues"]
    assert review["review"]["costs"]["price"] == "7.00"
    corrected = correct_detail(integrated, review)
    assert corrected["comparison"]["priced_card_quantity"] == 5
    assert corrected["comparison"]["result"]["known_selected_subtotal"] == "40.00"
    assert corrected["comparison"]["whole_lot_price_count"] == 1
    assert corrected["comparison"]["complete_delivered_comparison"]
    assert (
        corrected["comparison"]["result"]["comparisons"]["listing_observation"][
            "full_selected_reference_minus_delivered_cost"
        ]
        == "32.00"
    )
    remaining = budget.remaining_traversal(integrated.env.root, integrated.allowance)
    assert remaining["detail"] == before["detail"] - 1 and remaining["total"] == before["total"] - 1
    assert remaining["oauth"] == before["oauth"] == 0
    assert not budget.path(integrated.env.root).exists()
    details.stop(actor, "binding", action.id)
    with pytest.raises(Http404):
        lots.read(actor, "binding", review["review_id"])
    assert not parent.cancel.is_set() and lots.read(actor, "binding", local["review_id"])
    assert len(integrated.calls) == 4


def test_concurrent_detail_actions_and_reads_publish_one_review_set(integrated):
    actor = integrated.env.actor
    parent, result = acquire(integrated)
    selected = [row["id"] for row in result["results"]]
    started = details.start(actor, "binding", parent.id, selected)
    action = details._runs[started["detail_action_id"]]
    with pytest.raises(ValueError, match="already running"):
        details.start(actor, "binding", parent.id, selected)
    asyncio.run(details._acquire(action, actor, "binding", ("fixture-client", "CANARY_SECRET")))
    barrier = threading.Barrier(8)
    snapshots, failures = [], []

    def poll():
        try:
            barrier.wait()
            snapshots.append(details.status(actor, "binding", action.id))
        except Exception as exc:
            failures.append(type(exc).__name__)

    workers = [threading.Thread(target=poll) for _ in range(8)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(3)
    assert not failures and all(not worker.is_alive() for worker in workers) and len(snapshots) == 8
    assert len({tuple(review["review_id"] for review in value["reviews"]) for value in snapshots}) == 1
    assert len(lots._reviews) == 2
    assert [stage for stage, _ in integrated.calls].count("detail") == 2
    assert budget.remaining_traversal(integrated.env.root, integrated.allowance)["detail"] == 0


@pytest.mark.parametrize(
    "invalidate", ["parent_stop", "parent_expiry", "wrong_session", "reference_withdrawal"]
)
def test_open_detail_reviews_recheck_parent_authority_and_current_references(integrated, invalidate):
    actor = integrated.env.actor
    parent, result = acquire(integrated)
    action, loaded = acquire_detail(integrated, parent, [result["results"][0]["id"]])
    review_id = loaded["reviews"][0]["review_id"]
    assert correct_detail(integrated, loaded["reviews"][0])["comparison"]["priced_card_quantity"] == 5
    if invalidate == "reference_withdrawal":
        integrated.references = False
        withdrawn = details.status(actor, "binding", action.id)["reviews"][0]
        assert withdrawn["comparison"]["priced_card_quantity"] == 0
        assert withdrawn["comparison"]["references"] == []
        assert withdrawn["comparison"]["result"]["known_selected_subtotal"] is None
        assert not withdrawn["comparison"]["complete_delivered_comparison"]
    elif invalidate == "wrong_session":
        with pytest.raises(Http404):
            details.status(actor, "changed-session", action.id)
        with pytest.raises(Http404):
            lots.read(actor, "changed-session", review_id)
        assert details.status(actor, "binding", action.id)["reviews"]
    else:
        if invalidate == "parent_stop":
            hunter.stop(actor, "binding", parent.id)
        else:
            parent.created = time.monotonic() - discovery.EPHEMERAL_SECONDS - 1
            assert hunter.status(actor, "binding", parent.id)["state"] == "expired"
        assert not parent.raws and action.id not in details._runs and review_id not in lots._reviews
        with pytest.raises(Http404):
            lots.read(actor, "binding", review_id)
    assert len(integrated.calls) == 4


def test_uncertain_first_detail_consumes_shared_budget_and_suppresses_second(integrated):
    actor = integrated.env.actor
    parent, result = acquire(integrated)
    selected = [row["id"] for row in result["results"]]
    started = details.start(actor, "binding", parent.id, selected)
    action = details._runs[started["detail_action_id"]]

    def fail(identifier):
        raise ProviderFailure("detail", uncertain=True)

    integrated.detail_hook = fail
    with pytest.raises(ProviderFailure):
        asyncio.run(details._acquire(action, actor, "binding", ("fixture-client", "CANARY_SECRET")))
    assert not action.raws and not lots._reviews
    assert len(integrated.calls) == 4
    remaining = budget.remaining_traversal(integrated.env.root, integrated.allowance)
    assert remaining["detail"] == 1 and remaining["total"] == 11
    records = [
        json.loads(line)
        for line in budget.traversal_path(integrated.env.root, integrated.allowance).read_text().splitlines()
    ]
    assert [record["stage"] for record in records] == ["oauth", "browse", "browse", "detail"]
    # The original selected pair now exceeds remaining capacity. No replacement
    # action, automatic retry, second detail, or refund follows the uncertainty.
    action.state = "failed"
    with pytest.raises(ValueError, match="cannot admit"):
        details.start(actor, "binding", parent.id, selected)
    assert len(integrated.calls) == 4


def test_completed_continuation_during_lot_projection_rejects_obsolete_cost(integrated, monkeypatch):
    actor = integrated.env.actor
    parent, result = acquire(integrated)
    result_id = result["results"][0]["id"]
    review = lots.analyze(actor, "binding", parent.id, result_id)
    original = lots._compare

    def changed_during_projection(*args, **kwargs):
        calculated = original(*args, **kwargs)
        integrated.pages[1][0]["price"]["value"] = "9.00"
        hunter.continue_run(
            actor, "binding", parent.id, dict(cursor=parent.traversal.cursor(parent.next_index))
        )
        asyncio.run(hunter._acquire_traversal(parent, ("fixture-client", "CANARY_SECRET"), actor))
        return calculated

    monkeypatch.setattr(lots, "_compare", changed_during_projection)
    with pytest.raises(collection.Conflict, match="changed"):
        lots.read(actor, "binding", review["review_id"])
    assert hunter.summary_lease(actor, "binding", parent.id, result_id)["raw"]["price"]["value"] == "9.00"
    assert [stage for stage, _ in integrated.calls] == ["oauth", "browse", "browse", "browse", "browse"]


def test_completed_continuation_during_result_projection_rejects_obsolete_rows(integrated, monkeypatch):
    actor = integrated.env.actor
    parent, _ = acquire(integrated)
    original = hunter.hunter_catalog.compare
    changed = False

    def changed_during_projection(*args, **kwargs):
        nonlocal changed
        calculated = original(*args, **kwargs)
        if not changed:
            changed = True
            integrated.pages[1][0]["price"]["value"] = "9.00"
            hunter.continue_run(
                actor, "binding", parent.id, dict(cursor=parent.traversal.cursor(parent.next_index))
            )
            asyncio.run(hunter._acquire_traversal(parent, ("fixture-client", "CANARY_SECRET"), actor))
        return calculated

    monkeypatch.setattr(hunter.hunter_catalog, "compare", changed_during_projection)
    with pytest.raises(collection.Conflict, match="changed"):
        hunter.status(actor, "binding", parent.id)
    assert [stage for stage, _ in integrated.calls] == ["oauth", "browse", "browse", "browse", "browse"]


def test_completed_correction_during_review_read_rejects_obsolete_revision(integrated, monkeypatch):
    actor = integrated.env.actor
    parent, result = acquire(integrated)
    review = lots.analyze(actor, "binding", parent.id, result["results"][0]["id"])
    original = lots._compare
    changed = False

    def corrected_during_projection(*args, **kwargs):
        nonlocal changed
        calculated = original(*args, **kwargs)
        if not changed:
            changed = True
            lots.correct(
                actor,
                "binding",
                review["review_id"],
                dict(
                    revision=1,
                    cards=[
                        dict(printing_id="charizard", quantity=1),
                        dict(printing_id="blastoise", quantity=1),
                    ],
                    unknown_contents=0,
                ),
            )
        return calculated

    monkeypatch.setattr(lots, "_compare", corrected_during_projection)
    with pytest.raises(collection.Conflict, match="changed"):
        lots.read(actor, "binding", review["review_id"])
    latest = lots.read(actor, "binding", review["review_id"])
    assert latest["revision"] == 2 and latest["comparison"]["priced_card_quantity"] == 2
    assert len(integrated.calls) == 3


def test_parent_stop_during_result_projection_publishes_current_stopped_state(integrated, monkeypatch):
    actor = integrated.env.actor
    parent, _ = acquire(integrated)
    original = hunter.hunter_catalog.compare

    def stopped_during_projection(*args, **kwargs):
        calculated = original(*args, **kwargs)
        hunter.stop(actor, "binding", parent.id)
        return calculated

    monkeypatch.setattr(hunter.hunter_catalog, "compare", stopped_during_projection)
    response = hunter.status(actor, "binding", parent.id)
    assert response["state"] == "stopped" and not response["running"]
    assert response["results"] == [] and not response["has_next"]
    assert len(integrated.calls) == 3
