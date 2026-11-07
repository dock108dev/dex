"""Maintained SHOP-12 failure reproductions, using engineering state only."""

import asyncio
import uuid

import pytest
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_discovery import discovery as discovery
from test_migration import snapshot as snapshot

from pokemon_hunter.beta import collection, collection_catalog, listing_check
from pokemon_hunter.beta import discovery as d
from pokemon_hunter.beta.serving import LimitedApplication


def test_shopping_busy_is_predispatch_and_cancellation_releases_slot():
    async def run():
        entered = asyncio.Event()
        calls, output = [], []

        async def app(scope, receive, send):
            calls.append(scope["path"])
            if scope["path"] == "/api/shopping/listing/candidate/":
                entered.set()
                await asyncio.Event().wait()

        async def send(message):
            output.append(message)

        limited = LimitedApplication(app)

        def scope(path):
            return dict(type="http", method="GET", path=path)

        held = asyncio.create_task(limited(scope("/api/shopping/listing/candidate/"), None, send))
        await entered.wait()
        await limited(scope("/api/shopping/discovery/"), None, send)
        assert output[0]["status"] == 503
        assert output[1]["body"] == b'{"error":"runtime_busy"}'
        assert "/api/shopping/discovery/" not in calls
        stop_path = "/api/shopping/discovery/11111111-1111-4111-8111-111111111111/stop/"
        await limited(dict(type="http", method="POST", path=stop_path), None, send)
        assert output[-2]["status"] == 503 and stop_path not in calls
        await limited(scope("/api/v2/my-card-groups/"), None, send)
        assert "/api/v2/my-card-groups/" in calls
        held.cancel()
        await asyncio.gather(held, return_exceptions=True)
        assert limited.slots._value == 1

    asyncio.run(run())


def test_set_options_equal_visible_catalog_without_printing_decode(b4, monkeypatch):
    actor = b4["actor"]
    expected = {(p["set_id"], p["set_name"]) for p in collection.catalog(actor)}
    monkeypatch.setattr(collection_catalog, "catalog_entries", lambda *a, **k: pytest.fail("broad decode"))
    assert {(p["id"], p["name"]) for p in collection_catalog.set_options(actor)} == expected
    collection.execute("UPDATE printings SET publication_state='archived'")
    assert collection_catalog.set_options(actor) == []


def test_restore_passes_only_requested_ids_to_catalog(monkeypatch):
    calls = []
    monkeypatch.setattr(listing_check.lot, "catalog", lambda *a, **kw: calls.append(kw) or [])
    assert listing_check.catalog(None, restore=["literal-id"])["cards"] == []
    assert calls[0]["printing_ids"] == ["literal-id"]
    with pytest.raises(ValueError):
        listing_check.catalog(None, restore=list(map(str, range(201))))


def test_lost_action_response_reconciles_only_same_session_without_replay(discovery, monkeypatch):
    request_id = str(uuid.uuid4())
    calls = []
    monkeypatch.setattr(d, "start", lambda *a, **kw: calls.append(kw) or {"run_id": "original-run"})
    monkeypatch.setattr(d, "status", lambda actor, session, key: {"run_id": key, "counts": {"total": 1}})
    d.start_action(discovery.actor, "session", {}, request_id)
    assert d.action_status(discovery.actor, "session", request_id) == {
        "run_id": "original-run",
        "counts": {"total": 1},
    }
    assert d.action_status(discovery.actor, "other", request_id)["outcome_unknown"]
    with pytest.raises(ValueError, match="already submitted"):
        d.start_action(discovery.actor, "session", {}, request_id)
    assert len(calls) == 1


def test_exception_during_admission_never_becomes_replay_permission(discovery, monkeypatch):
    request_id = str(uuid.uuid4())

    def interrupted(*args, **kwargs):
        raise RuntimeError("interrupted after possible dispatch")

    monkeypatch.setattr(d, "start", interrupted)
    with pytest.raises(RuntimeError):
        d.start_action(discovery.actor, "session", {}, request_id)
    assert d.action_status(discovery.actor, "session", request_id)["outcome_unknown"]
    with pytest.raises(ValueError, match="already submitted"):
        d.start_action(discovery.actor, "session", {}, request_id)


def test_empty_goals_do_not_project_catalog_or_ownership(b4, monkeypatch):
    def broad(*args, **kwargs):
        pytest.fail("No goal requires this projection")

    monkeypatch.setattr(collection, "catalog", broad)
    monkeypatch.setattr(collection, "copies", broad)
    assert collection.goals(b4["actor"], include_updates=False) == []


def test_received_lot_status_avoids_assessment_but_keeps_original_authority(discovery, monkeypatch):
    from test_discovery import run_for

    run = run_for(discovery, choices=d.Choices(query="Venusaur", product_type="mixed_lots"))
    run.state = "complete"
    run.raws = [
        dict(
            itemId="engineering-item",
            title="Venusaur lot",
            buyingOptions=["AUCTION"],
            currentBidPrice=dict(value="10", currency="USD"),
        )
    ]
    d._runs[run.id] = run

    def assessment(*args, **kwargs):
        pytest.fail("Received summaries must not perform optional catalog/value assessment")

    monkeypatch.setattr(d, "_candidate_data", assessment)
    result = d.status(discovery.actor, "session", run.id, received=True)
    row = result["results"][0]
    assert row["current_bid"] == "10.00"
    assert row["shipping"] is None and row["delivered_total"] is None
    assert row["reference"] is None and row["comparison"] == {}
    assert row["discovery_eligibility"] == "unassessed"
    created = run.created
    d.stop(discovery.actor, "session", run.id)
    assert d.status(discovery.actor, "session", run.id, received=True)["results"] == []
    assert run.created == created


def test_received_projection_cannot_publish_after_stop(discovery, monkeypatch):
    from test_discovery import run_for

    run = run_for(discovery, choices=d.Choices(query="lot", product_type="mixed_lots"))
    run.state = "complete"
    run.raws = [dict(itemId="engineering-item")]
    d._runs[run.id] = run

    def stop_during_projection(raws):
        d.stop(discovery.actor, "session", run.id)
        return [dict(item_id="engineering-item")]

    monkeypatch.setattr(d.discovery_listing, "received_rows", stop_during_projection)
    assert d.status(discovery.actor, "session", run.id, received=True)["results"] == []


def test_concurrent_action_cannot_dispatch_twice(discovery, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    entered, release = Event(), Event()
    calls = []
    request_id = str(uuid.uuid4())

    def held(*args, **kwargs):
        calls.append(True)
        entered.set()
        assert release.wait(5)
        return {"run_id": "original-run"}

    monkeypatch.setattr(d, "start", held)
    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(d.start_action, discovery.actor, "session", {}, request_id)
        try:
            assert entered.wait(5)
            with pytest.raises(ValueError, match="already submitted"):
                d.start_action(discovery.actor, "session", {}, request_id)
            assert d.action_status(discovery.actor, "session", request_id)["outcome_unknown"]
            assert d.action_status(discovery.actor, "session", request_id, operation="detail")[
                "outcome_unknown"
            ]
        finally:
            release.set()
        assert first.result()["run_id"] == "original-run"
    assert calls == [True]


def test_small_artwork_binding_never_reads_the_whole_catalog(b4, monkeypatch):
    from pokemon_hunter.beta import image_bindings

    entries = collection.catalog(b4["actor"])
    expected = image_bindings.catalog_images(b4["actor"], entries[:1])
    monkeypatch.setattr(collection, "catalog", lambda *a, **k: pytest.fail("broad artwork read"))
    assert image_bindings.catalog_images(b4["actor"], entries[:1]) == expected


def test_automatic_values_preserve_session_and_stop_boundaries(discovery, monkeypatch):
    from django.http import Http404
    from test_discovery import run_for

    from pokemon_hunter.beta import discovery_lot_values

    run = run_for(discovery, choices=d.Choices(query="Lapras", product_type="mixed_lots"))
    run.state = "complete"
    run.raws = [dict(itemId="engineering-item")]
    d._runs[run.id] = run
    calls = []

    def value(actor, raws, rows, **kwargs):
        calls.append(True)
        rows[0]["lot_value"] = dict(total="25.00")

    monkeypatch.setattr(discovery_lot_values, "project", value)
    with pytest.raises(Http404):
        d.status(discovery.actor, "other-session", run.id, values=True)
    assert not calls
    assert (
        d.status(discovery.actor, "session", run.id, values=True)["results"][0]["lot_value"]["total"]
        == "25.00"
    )

    def stopped(actor, raws, rows, **kwargs):
        value(actor, raws, rows)
        d.stop(discovery.actor, "session", run.id)

    monkeypatch.setattr(discovery_lot_values, "project", stopped)
    assert d.status(discovery.actor, "session", run.id, values=True)["results"] == []


def test_detail_policy_refusal_reconciles_as_unsent_without_replay(discovery, monkeypatch):
    request_id = str(uuid.uuid4())
    calls = []

    def refused(*args, **kwargs):
        calls.append(True)
        raise listing_check.AdmissionRefused("Acquisition window expired")

    monkeypatch.setattr(listing_check, "start", refused)
    result = d.start_action(
        discovery.actor, "session", {"identifier": "123456789012"}, request_id, operation="detail"
    )
    assert result["not_dispatched"] and not result["running"]
    assert result["counts"]["total"] == 0
    assert d.action_status(discovery.actor, "session", request_id, operation="detail") == result
    result["counts"]["total"] = 99
    assert d.action_status(discovery.actor, "session", request_id, operation="detail")["counts"]["total"] == 0
    assert d.action_status(discovery.actor, "other", request_id, operation="detail")["outcome_unknown"]
    with pytest.raises(ValueError, match="already submitted"):
        d.start_action(
            discovery.actor, "session", {"identifier": "123456789012"}, request_id, operation="detail"
        )
    assert calls == [True]
