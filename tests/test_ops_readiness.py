"""OPS-READINESS: disposable engineering state only, no customer/runtime access."""

import asyncio
import json
import time
from unittest.mock import patch

import pytest
from test_account_reads import prepared as prepared
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_effective_collection import add
from test_effective_collection import cx as cx
from test_migration import snapshot as snapshot
from test_sealed_catalog import e1 as e1

from pokemon_hunter.beta import account_read_build as accounts
from pokemon_hunter.beta import catalog_read_build as catalogs
from pokemon_hunter.beta import collection, read_diagnostics, readiness, store


def test_restart_read_only_and_independent_accounts(prepared):
    before = store.rows("SELECT * FROM catalog_read_builds")
    with (
        patch.object(catalogs, "prepare", side_effect=AssertionError),
        patch.object(accounts, "prepare", side_effect=AssertionError),
    ):
        for _ in range(3):
            start = time.perf_counter()
            assert readiness.startup()["ready"]
            assert (time.perf_counter() - start) < 2
            assert readiness.inspect(prepared["actor"])["ready"]
    assert store.rows("SELECT * FROM catalog_read_builds") == before
    assert prepared["client"]().get("/livez/").json() == {"alive": True}
    assert prepared["client"]().get("/readyz/").status_code == 200
    assert prepared["client"]().get("/api/v2/readiness/").status_code == 403
    assert prepared["a"].get("/api/v2/readiness/").json()["ready"]
    other = prepared["b"].get("/api/v2/readiness/")
    assert other.status_code == 503
    assert other.json()["category"] == "account_not_prepared"
    assert prepared["a"].get("/api/v2/readiness/", HTTP_X_DEX_READ_ACCOUNT="other").status_code == 403
    assert "no-store" in other["Cache-Control"]


@pytest.mark.parametrize(
    "sql,code",
    [
        ("DROP TABLE catalog_read_schema", "schema_missing"),
        ("UPDATE catalog_read_schema SET version=99", "incompatible_schema"),
        ("UPDATE catalog_read_revision SET value=value+1", "catalog_stale"),
        ("UPDATE catalog_read_builds SET policy='old'", "incompatible_policy"),
        ("UPDATE catalog_read_builds SET seal='broken'", "manifest_corrupt"),
        ("DELETE FROM catalog_read_active", "manifest_missing"),
        ("UPDATE catalog_read_builds SET status='preparing'", "preparation_interrupted"),
        ("UPDATE cr_groups SET payload='broken'", "derived_corrupt"),
        ("DROP INDEX cr_public_order_set", "infrastructure_missing"),
        ("DROP TRIGGER cr_rev_printings_update", "infrastructure_missing"),
    ],
)
def test_catalog_faults(prepared, sql, code):
    authority = store.rows("SELECT * FROM owned_copies ORDER BY id")
    collection.execute(sql)
    start = time.perf_counter()
    state = readiness.inspect()
    assert state["category"] == code
    assert time.perf_counter() - start < 2
    assert prepared["a"].get("/login/").status_code == 200
    assert store.rows("SELECT * FROM owned_copies ORDER BY id") == authority


@pytest.mark.parametrize(
    "sql,code",
    [
        ("UPDATE account_read_state SET policy='effective-collection-1'", "account_policy_incompatible"),
        ("DELETE FROM account_read_state", "account_not_prepared"),
        ("UPDATE account_read_state SET generation=-1", "account_corrupt"),
        ("UPDATE ar_groups SET payload='broken'", "account_corrupt"),
        ("DROP INDEX ar_owned", "infrastructure_missing"),
        ("UPDATE account_read_schema SET version=99", "incompatible_schema"),
    ],
)
def test_account_faults_are_private(prepared, sql, code):
    collection.execute(sql)
    assert readiness.inspect()["ready"]
    state = readiness.inspect(prepared["actor"])
    assert state["category"] == code
    assert prepared["actor"].user_id not in json.dumps(state)


def test_confirmation_recovery_does_not_resubmit(prepared):
    with patch.object(accounts, "_refresh", side_effect=RuntimeError("private failure")):
        operation = add(prepared)
    assert operation["state"] == "confirmed"
    assert not readiness.inspect(prepared["actor"])["ready"]
    authority = store.rows("SELECT * FROM owned_copies ORDER BY id")
    operations = store.rows("SELECT * FROM collection_operations ORDER BY id")
    accounts.prepare(prepared["actor"])
    assert readiness.inspect(prepared["actor"])["ready"]
    assert store.rows("SELECT * FROM owned_copies ORDER BY id") == authority
    assert store.rows("SELECT * FROM collection_operations ORDER BY id") == operations


def test_repair_and_authority_change_rejects_activation(prepared):
    from pokemon_hunter.beta import catalog_read_schema

    build = catalogs.prepare()
    collection.execute("UPDATE catalog_read_revision SET value=value+1")
    with pytest.raises(collection.Conflict):
        catalogs.activate(build)
    assert readiness.inspect()["category"] == "catalog_stale"
    catalog_read_schema.repair()
    from pokemon_hunter.beta import account_read_schema

    account_read_schema.repair()
    catalogs.activate(catalogs.prepare())
    accounts.prepare(prepared["actor"])
    assert readiness.inspect(prepared["actor"])["ready"]


def test_diagnostics_redacted_and_bounded(prepared):
    read_diagnostics.recent.clear()
    response = prepared["a"].get(
        "/api/v2/my-card-groups/?q=SECRET_QUERY", HTTP_AUTHORIZATION="SECRET_CREDENTIAL"
    )
    assert response.status_code == 200
    record = read_diagnostics.recent[-1]
    assert record["route"] == "api/v2/my-card-groups/"
    assert record["id"] == response["X-Dex-Diagnostic-ID"]
    assert record["query_count"] > 0 and record["sql_fetch_ms"] >= 0
    assert record["payload_bytes"] == len(response.content)
    assert record["serialization_ms"] is not None
    assert record["fetch_coverage"] == "request_cursors"
    text = json.dumps(record)
    for secret in ("SECRET_QUERY", "SECRET_CREDENTIAL", prepared["actor"].user_id):
        assert secret not in text
    for _ in range(300):
        read_diagnostics.emit({"event": "test", "unsafe": "SECRET"})
    assert len(read_diagnostics.recent) == 256
    assert "unsafe" not in json.dumps(list(read_diagnostics.recent))


def test_admission_bounds_cancel_and_shutdown():
    from pokemon_hunter.beta.serving import REQUEST_SLOTS, LimitedApplication

    async def scenario():
        entered = 0
        high = 0
        release = asyncio.Event()

        async def app(scope, receive, send):
            nonlocal entered, high
            entered += 1
            high = max(high, entered)
            try:
                await release.wait()
            finally:
                entered -= 1

        limited = LimitedApplication(app)
        messages = []

        async def send(message):
            messages.append(message)

        tasks = [asyncio.create_task(limited({"type": "http"}, None, send)) for _ in range(REQUEST_SLOTS)]
        await asyncio.sleep(0.02)
        await limited({"type": "http"}, None, send)
        assert messages[0]["status"] == 503
        assert high == REQUEST_SLOTS
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        assert limited.slots._value == REQUEST_SLOTS
        release.set()
        await limited({"type": "http"}, None, send)

    asyncio.run(scenario())


def test_health_never_writes_or_prepares(prepared):
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("PRAGMA query_only=ON")
    try:
        with (
            patch.object(catalogs, "prepare", side_effect=AssertionError),
            patch.object(accounts, "prepare", side_effect=AssertionError),
        ):
            assert readiness.inspect()["ready"]
            assert readiness.inspect(prepared["actor"])["ready"]
    finally:
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA query_only=OFF")


def test_bounded_probe_interrupts_runaway_sql(prepared):
    def slow():
        store.rows(
            "WITH RECURSIVE loop(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM loop WHERE x<1000000000) SELECT SUM(x) FROM loop"
        )

    with patch.object(catalogs, "active", side_effect=slow):
        started = time.perf_counter()
        assert readiness.inspect()["category"] == "check_deadline"
        assert time.perf_counter() - started < 2
    assert readiness.inspect()["ready"]  # progress handler and timeout restored


def test_log_rotation_and_rate_bound(tmp_path):
    import logging
    from logging.handlers import RotatingFileHandler

    logger = read_diagnostics.logger
    previous = list(logger.handlers)
    logger.handlers = [logging.NullHandler()]
    try:
        read_diagnostics.configure(tmp_path)
        handler = next(h for h in logger.handlers if isinstance(h, RotatingFileHandler))
        assert handler.maxBytes == 1024 * 1024 and handler.backupCount == 2
        # Test rotation with a smaller bound; production bound stays fixed.
        handler.maxBytes = 512
        for _ in range(50):
            logger.info(json.dumps({"event": "test", "phase": "x" * 90}))
        files = list((tmp_path / "diagnostics").iterdir())
        assert len(files) == 3
        assert all(p.stat().st_mode & 0o077 == 0 for p in files)
        with (
            patch.object(logger, "info") as output,
            patch.object(read_diagnostics, "_window", time.monotonic()),
            patch.object(read_diagnostics, "_emitted", 0),
        ):
            for _ in range(100):
                read_diagnostics.emit({"event": "test"})
            assert output.call_count == 60
    finally:
        for handler in logger.handlers:
            handler.close()
        logger.handlers = previous


def test_lifespan_joins_before_shutdown_acknowledgment():
    from pokemon_hunter.beta.serving import ShutdownApplication

    async def scenario():
        events = []
        messages = iter([{"type": "lifespan.startup"}, {"type": "lifespan.shutdown"}])

        async def receive():
            return next(messages)

        async def send(message):
            events.append(message["type"])

        app = ShutdownApplication(None, lambda: events.append("workers_joined"))
        await app({"type": "lifespan"}, receive, send)
        assert events == ["lifespan.startup.complete", "workers_joined", "lifespan.shutdown.complete"]

    asyncio.run(scenario())


@pytest.mark.parametrize("sort", ["set", "name", "number"])
@pytest.mark.parametrize("page", ["1", "2", "99999999999999999999999999"])
def test_owned_search_totals_and_empty_pages(prepared, sort, page):
    from pokemon_hunter.beta import account_read_queries, card_groups

    for query in ("a", "saur", "%", "é", "no-such-card"):
        selectors = dict(scope="owned", q=query, sort=sort, page=page, page_size="1")
        reference = card_groups.list_groups(prepared["actor"], selectors)
        actual = account_read_queries.groups(prepared["actor"], selectors)
        assert actual["total"] == reference["total"]
        assert [r["id"] for r in actual["groups"]] == [r["id"] for r in reference["groups"]]


def test_static_assets_have_a_bounded_separate_lane():
    from pokemon_hunter.beta.serving import LimitedApplication

    async def scenario():
        release = asyncio.Event()
        asset_called = asyncio.Event()

        async def app(scope, receive, send):
            if scope["path"].startswith("/collection-assets/"):
                asset_called.set()
            else:
                await release.wait()

        async def send(message):
            pass

        limited = LimitedApplication(app)
        dynamic = asyncio.create_task(limited({"type": "http", "path": "/api/v2/card-groups/"}, None, send))
        await asyncio.sleep(0.01)
        await limited({"type": "http", "path": "/collection-assets/collection.js"}, None, send)
        assert asset_called.is_set()
        assert limited.asset_slots._value == 4
        release.set()
        await dynamic
        assert limited.slots._value == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("path", ["/cards/", "/card-library/", "/pokedex/", "/api/v2/my-card-groups/"])
def test_browsing_is_not_blocked_by_legacy_comparison(path):
    from pokemon_hunter.beta.serving import LimitedApplication

    async def scenario():
        entered = asyncio.Event()
        release = asyncio.Event()
        called = []

        async def app(scope, receive, send):
            called.append(scope["path"])
            if scope["path"] == "/api/shopping/hunter/":
                entered.set()
                await release.wait()

        messages = []

        async def send(message):
            messages.append(message)

        limited = LimitedApplication(app)
        slow = asyncio.create_task(
            limited({"type": "http", "method": "GET", "path": "/api/shopping/hunter/"}, None, send)
        )
        await entered.wait()
        try:
            await limited({"type": "http", "method": "GET", "path": path}, None, send)
            assert path in called
            assert not messages
        finally:
            release.set()
            await slow

    asyncio.run(scenario())


def test_reserved_browsing_slot_stays_bounded_and_never_admits_mutations():
    from pokemon_hunter.beta.serving import LimitedApplication

    async def scenario():
        release = asyncio.Event()
        entered = []
        messages = []

        async def app(scope, receive, send):
            entered.append(scope["path"])
            await release.wait()

        async def send(message):
            messages.append(message)

        limited = LimitedApplication(app)
        ordinary = asyncio.create_task(
            limited({"type": "http", "method": "POST", "path": "/api/operations/"}, None, send)
        )
        browsing = asyncio.create_task(
            limited({"type": "http", "method": "GET", "path": "/cards/"}, None, send)
        )
        await asyncio.sleep(0.02)
        try:
            assert len(entered) == 2
            for method, path in [
                ("GET", "/api/v2/my-card-groups/"),
                ("POST", "/api/v2/card-groups/"),
                ("GET", "/api/v2/public/resources/group/example/"),
            ]:
                messages.clear()
                await limited({"type": "http", "method": method, "path": path}, None, send)
                assert messages[0]["status"] == 503
                assert len(entered) == 2
        finally:
            ordinary.cancel()
            browsing.cancel()
            await asyncio.gather(ordinary, browsing, return_exceptions=True)
        assert limited.slots._value == limited.browse_slots._value == 1

    asyncio.run(scenario())
