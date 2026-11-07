"""Semantic equivalence and final-authority tests for indexed Shopping reads."""

import json
import uuid
from pathlib import Path

import pytest
from perf04_helpers import enable_read_fixture
from test_b1 import env as env
from test_b2 import b2 as b2
from test_discovery_catalog import visual as visual
from test_migration import snapshot as snapshot

from pokemon_hunter.beta import discovery, discovery_catalog, listing_check


def clean(value):
    return {
        k: v
        for k, v in value.items()
        if k
        not in {
            "read_version",
            "public",
            "catalog_revision",
            "account_revision",
            "account_id",
            "generation",
            "expires_in_seconds",
        }
    }


def test_release_dates_reused_only_inside_one_authorized_read(visual, monkeypatch):
    from pokemon_hunter.beta import shopping_index, species_scope

    enable_read_fixture(visual, monkeypatch)
    original = species_scope.release_dates
    reads = []

    def counted(**kwargs):
        value = original(**kwargs)
        reads.append(value)
        return value

    monkeypatch.setattr(species_scope, "release_dates", counted)

    @shopping_index.indexed
    def inspect(actor):
        indexed = shopping_index.current(actor)
        dates = indexed.release_dates()
        dates["caller-change"] = {"start": "1900-01-01"}
        assert "caller-change" not in indexed.release_dates()
        return {}

    inspect(visual["actor"])
    assert len(reads) == 1
    inspect(visual["actor"])
    assert len(reads) == 2


def test_explorer_equivalent_before_and_after_read_preparation(visual, monkeypatch):
    actor = visual["actor"]
    requests = [
        {},
        {"q": "Alakazam"},
        {"q": "Alakazam base"},
        {"q": "Alakazam base 2"},
        {"q": "Base 2 #1"},
        {"q": "Base 2 1/130"},
        {"q": "Gengar", "species": "94"},
        {"q": "Alakazam", "intent": "missing"},
        {"q": "Alakazam", "intent": "missing", "missing_basis": "printing"},
        {"scope": "rares"},
        {"scope": "bulk"},
        {"offset": "40"},
    ]
    baseline = [clean(discovery_catalog.search(actor, raw)) for raw in requests]
    group = baseline[3]["results"][0]["id"]
    requests.append({"group": group})
    baseline.append(clean(discovery_catalog.search(actor, requests[-1])))
    manual = {q: listing_check.catalog(actor, q) for q in ("Alakazam", "Base Set", "1", "")}
    enable_read_fixture(visual, monkeypatch)
    for q, expected in manual.items():
        assert clean(listing_check.catalog(actor, q)) == clean(expected)
    for raw, expected in zip(requests, baseline, strict=True):
        actual = clean(discovery_catalog.search(actor, raw))
        assert actual == expected, raw


@pytest.mark.parametrize(
    "title",
    [
        "Alakazam Base Set 2 1 two card lot",
        "Alakazam",
        "Hypno Base Set 2 23",
        "Alakazam Base Set 2 1/130 first edition holo",
        "Gengar Base Set 2 #999",
    ],
)
def test_candidate_equivalent_before_and_after_read_preparation(visual, monkeypatch, title):
    actor = visual["actor"]
    run = discovery.Run(
        str(uuid.uuid4()),
        discovery._owner(actor, "session"),
        discovery.Choices(query="Alakazam", product_type="both"),
        None,
        ["Alakazam"],
        state="complete",
        raws=[
            dict(
                itemId="v1|123456789012|0",
                title=title,
                buyingOptions=["FIXED_PRICE"],
                price={"value": "10", "currency": "USD"},
            )
        ],
    )
    discovery._runs[run.id] = run
    handle = discovery.discovery_listing.result_handle(run.id, run.raws[0]["itemId"])
    expected = clean(listing_check.candidate(actor, "session", run.id, handle))
    enable_read_fixture(visual, monkeypatch)
    actual = clean(listing_check.candidate(actor, "session", run.id, handle))
    assert actual == expected


def test_indexed_request_query_profile(visual, monkeypatch):
    from collections import Counter
    from types import SimpleNamespace

    from django.db import connection

    from pokemon_hunter.beta import navigation

    enable_read_fixture(visual, monkeypatch)
    actor = visual["actor"]
    client = visual["a"]
    binding = navigation.binding(SimpleNamespace(user=visual["owner"], session=client.session))[
        "navigation_binding"
    ]
    run = discovery.Run(
        str(uuid.uuid4()),
        discovery._owner(actor, binding),
        discovery.Choices(query="Hypno", product_type="both"),
        None,
        ["Hypno"],
        state="complete",
        raws=[dict(itemId="v1|123456789012|0", title="Hypno Base Set 2 23", buyingOptions=["FIXED_PRICE"])],
    )
    discovery._runs[run.id] = run
    handle = discovery.discovery_listing.result_handle(run.id, run.raws[0]["itemId"])
    queries = []

    def capture(execute, sql, params, many, context):
        queries.append(sql)
        return execute(sql, params, many, context)

    with connection.execute_wrapper(capture):
        response = client.get(
            "/api/shopping/listing/candidate/",
            {"discovery_run": run.id, "item_id": handle},
            HTTP_X_DEX_SHOPPING_BINDING=binding,
        )
    plans = []

    def explain(execute, sql, params, many, context):
        if sql.startswith("WITH matching"):
            with connection.cursor() as cursor:
                cursor.execute("EXPLAIN QUERY PLAN " + sql, params)
                plans.extend(cursor.fetchall())
        return execute(sql, params, many, context)

    with connection.execute_wrapper(explain):
        for raw in ({"intent": "missing"}, {"q": "Alakazam 1"}):
            assert client.get("/api/shopping/discovery/catalog/", raw).status_code == 200
    out = Path("reports/shop-12-finish")
    out.mkdir(parents=True, exist_ok=True)
    (out / "query-plans.json").write_text(json.dumps(plans, indent=2))
    (out / "query-profile.json").write_text(json.dumps(Counter(queries), indent=2))
    assert response.status_code == 200, response.content


def test_goal_and_missing_scope_equivalence(visual, monkeypatch):
    from django.http import Http404
    from test_b2 import apply

    from pokemon_hunter.beta import collection, goal_hunts

    goal = apply(
        visual,
        "goal",
        dict(
            name="Engineering frozen",
            goal_kind="custom",
            printing_ids=[p["id"] for p in collection.catalog(visual["actor"])],
        ),
    )["changes"][0]["after"]
    scope = goal_hunts.snapshot(visual["actor"], goal["id"])
    choices = [
        discovery.Choices(
            query="Alakazam",
            product_type="both",
            intent="missing",
            missing_basis=basis,
            goal_id=goal["id"] if frozen else None,
            goal_version=goal["version"] if frozen else None,
        )
        for frozen in (False, True)
        for basis in ("species", "printing")
    ]
    runs = []
    for choice in choices:
        r = discovery.Run(
            str(uuid.uuid4()),
            discovery._owner(visual["actor"], "session"),
            choice,
            scope if choice.goal_id else None,
            ["Alakazam"],
            state="complete",
            raws=[
                dict(itemId="v1|123456789012|0", title="Alakazam Base Set 2 1", buyingOptions=["FIXED_PRICE"])
            ],
        )
        discovery._runs[r.id] = r
        runs.append(r)

    def read(r):
        try:
            return clean(
                listing_check.candidate(
                    visual["actor"],
                    "session",
                    r.id,
                    discovery.discovery_listing.result_handle(r.id, r.raws[0]["itemId"]),
                )
            )
        except Http404:
            return "unavailable"

    expected = [read(r) for r in runs]
    raw = {"goal": goal["id"], "version": goal["version"], "intent": "missing"}
    explorer = clean(discovery_catalog.search(visual["actor"], raw))
    enable_read_fixture(visual, monkeypatch)
    assert [read(r) for r in runs] == expected
    assert clean(discovery_catalog.search(visual["actor"], raw)) == explorer


def test_complete_alias_and_sibling_candidates(visual, monkeypatch):
    from pokemon_hunter.beta import collection, discovery_matching, shopping_index, store

    first = store.rows("SELECT * FROM printings ORDER BY id LIMIT 1")[0]
    attrs = json.loads(first["attributes"])
    attrs.update(name="Mr. Mime", name_aliases=["Mimey", "İmposter"])
    first["attributes"] = json.dumps(attrs)
    for number, (key, name, edition) in enumerate(
        [
            ("alias-a", "Mr. Mime", "standard"),
            ("alias-b", "Mr. Mime", "first"),
            ("alias-c", "Dark Mr. Mime", "standard"),
            *[(f"alias-wide-{i}", "Mr. Mime", f"engineering-{i}") for i in range(60)],
        ]
    ):
        row = dict(first, id=key, edition=edition, attributes=json.dumps(dict(attrs, name=name)))
        cols = list(row)
        collection.execute(
            "INSERT INTO printings (" + ",".join(cols) + ") VALUES (" + ",".join(["%s"] * len(cols)) + ")",
            [row[k] for k in cols],
        )
    catalog = collection.catalog(visual["actor"], include_archived=True)
    texts = ["Mr. Mime", "Dark Mr. Mime", "Mimey #1", "imposter", "Imposter", "İmposter", "Alakazam Mr. Mime"]
    expected = {t: [p["id"] for p in catalog if discovery_matching.name_spans(p, t)] for t in texts}
    queries = ("Mr. Mime", "Dark Mr. Mime", "NoSuchPrinting")
    pages = [listing_check.catalog(visual["actor"], q) for q in queries]
    assert [page["total"] for page in pages] == [63, 1, 0]
    enable_read_fixture(visual, monkeypatch)
    for q, page in zip(queries, pages, strict=True):
        assert clean(listing_check.catalog(visual["actor"], q)) == clean(page)

    @shopping_index.indexed
    def read(actor):
        indexed = shopping_index.current(actor)
        return dict(found={t: [p["id"] for p in indexed.matching(t)] for t in texts})

    assert read(visual["actor"])["found"] == expected


@pytest.mark.parametrize("change", ["account", "generation", "catalog", "goal"])
def test_final_authority_change_prevents_publication(visual, monkeypatch, change):
    from django.core.exceptions import PermissionDenied

    from pokemon_hunter.beta import collection, shopping_index

    enable_read_fixture(visual, monkeypatch)

    @shopping_index.indexed
    def read(actor):
        value = discovery_catalog.search(actor, {"q": "Alakazam"})
        if change == "account":
            collection.execute("UPDATE users SET state='disabled' WHERE id=%s", [actor.user_id])
        elif change == "generation":
            collection.bump(actor)
        elif change == "catalog":
            collection.execute(
                "UPDATE printings SET edition='changed' WHERE id=%s", [visual["catalog"][0]["id"]]
            )
        else:
            collection.execute(
                "INSERT INTO account_read_revisions(user_id,value) VALUES(%s,1) ON CONFLICT(user_id) DO UPDATE SET value=value+1",
                [actor.user_id],
            )
        return value

    with pytest.raises((PermissionDenied, collection.Conflict)):
        read(visual["actor"])


def test_explicit_v2_transition_preserves_authority_and_requires_preparation(visual, monkeypatch):
    from pokemon_hunter.beta import (
        account_read_build as accounts,
    )
    from pokemon_hunter.beta import (
        account_read_queries as reads,
    )
    from pokemon_hunter.beta import (
        account_read_schema as schema,
    )
    from pokemon_hunter.beta import (
        collection,
        store,
    )
    from pokemon_hunter.beta.catalog_read_build import Unavailable

    enable_read_fixture(visual, monkeypatch)
    before = collection.export_data(visual["actor"])
    collection.execute("DROP TABLE ar_shopping_names")
    collection.execute("UPDATE account_read_schema SET version=2")
    state = store.rows("SELECT * FROM account_read_state WHERE user_id=%s", [visual["actor"].user_id])[0]
    state["policy"] = "effective-collection-2-goal-headers"
    collection.execute(
        "UPDATE account_read_state SET policy=%s,seal=%s WHERE user_id=%s",
        [state["policy"], accounts.seal(state), visual["actor"].user_id],
    )
    with pytest.raises(Unavailable):
        reads.groups(visual["actor"])
    schema.migrate()
    with pytest.raises(Unavailable):
        reads.groups(visual["actor"])
    accounts.prepare(visual["actor"])
    assert reads.groups(visual["actor"])["groups"]
    assert collection.export_data(visual["actor"]) == before


def test_stop_after_snapshot_checks_still_prevents_candidate_publication(visual, monkeypatch):
    from django.http import Http404

    from pokemon_hunter.beta import store

    enable_read_fixture(visual, monkeypatch)
    run = discovery.Run(
        str(uuid.uuid4()),
        discovery._owner(visual["actor"], "session"),
        discovery.Choices(query="Alakazam", product_type="both"),
        None,
        ["Alakazam"],
        state="complete",
        raws=[dict(itemId="v1|123456789012|0", title="Alakazam Base Set 2 1", buyingOptions=["FIXED_PRICE"])],
    )
    discovery._runs[run.id] = run
    rows = store.rows

    def stop(sql, params=()):
        value = rows(sql, params)
        if "AS catalog,(SELECT status FROM account_read_state" in sql:
            run.cancel.set()
        return value

    monkeypatch.setattr(store, "rows", stop)
    with pytest.raises(Http404):
        listing_check.candidate(
            visual["actor"],
            "session",
            run.id,
            discovery.discovery_listing.result_handle(run.id, run.raws[0]["itemId"]),
        )


def test_archived_selected_group_and_collision_equivalence(visual, monkeypatch):
    from test_b2 import add

    from pokemon_hunter.beta import card_groups, catalog_imports, collection, store
    from pokemon_hunter.inventory import connect

    with connect(visual["root"] / "inventory.db") as db:
        catalog_imports.initialize(db)

    from django.conf import settings

    monkeypatch.setattr(settings, "B4_ENABLED", True)
    add(visual)
    actor = visual["actor"]
    first = visual["catalog"][0]["id"]
    group = next(
        g for g in card_groups.project(actor)["groups"] if first in [c["id"] for c in g["_children"]]
    )
    collection.execute("UPDATE printings SET publication_state='archived' WHERE id=%s", [first])
    # A contradictory literal sibling must still suppress its entire group.
    row = store.rows("SELECT * FROM printings WHERE id=%s", ["shop04-base2-variant"])[0]
    attrs = json.loads(row["attributes"])
    attrs["name"] = "Contradictory Alakazam"
    collection.execute("UPDATE printings SET attributes=%s WHERE id=%s", [json.dumps(attrs), row["id"]])
    requests = [{}, {"group": group["id"]}, {"intent": "missing"}, {"q": "Alakazam 1"}, {"scope": "rares"}]
    expected = [clean(discovery_catalog.search(actor, raw)) for raw in requests]
    enable_read_fixture(visual, monkeypatch)
    assert [clean(discovery_catalog.search(actor, raw)) for raw in requests] == expected


@pytest.mark.parametrize("schema", ["catalog", "account"])
@pytest.mark.parametrize("combined", [False, True])
def test_schema_checks_reject_multiple_markers(visual, monkeypatch, schema, combined):
    from pokemon_hunter.beta import account_read_schema, catalog_read_build, collection
    from pokemon_hunter.beta.catalog_read_build import Unavailable

    enable_read_fixture(visual, monkeypatch)
    table = {"catalog": "catalog_read_schema", "account": "account_read_schema"}[schema]
    collection.execute(f"INSERT INTO {table} VALUES(99)")
    with pytest.raises(Unavailable, match="incompatible_schema"):
        if combined:
            listing_check.catalog(visual["actor"], "Alakazam")
        elif schema == "account":
            account_read_schema.check()
        else:
            catalog_read_build.check_schema()


def test_unnamed_restore_preserves_catalog_order(visual, monkeypatch):
    from pokemon_hunter.beta import collection, store

    key = visual["catalog"][0]["id"]
    attrs = json.loads(store.rows("SELECT attributes FROM printings WHERE id=%s", [key])[0]["attributes"])
    attrs["name"] = ""
    collection.execute("UPDATE printings SET attributes=%s WHERE id=%s", [json.dumps(attrs), key])
    ids = [p["id"] for p in visual["catalog"]]
    expected = listing_check.catalog(visual["actor"], restore=ids)
    enable_read_fixture(visual, monkeypatch)
    assert clean(listing_check.catalog(visual["actor"], restore=ids)) == clean(expected)
