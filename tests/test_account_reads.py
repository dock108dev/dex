"""PERF-03 engineering-only state: policy parity, invalidation and isolation."""

from unittest.mock import patch

import pytest
from django.db import connection
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_effective_collection import add, select
from test_effective_collection import cx as cx
from test_migration import snapshot as snapshot
from test_ownership_declarations import migrate as declarations_migrate
from test_sealed_catalog import e1 as e1

from pokemon_hunter.beta import account_read_build as accounts
from pokemon_hunter.beta import account_read_schema as schema
from pokemon_hunter.beta import card_groups, collection, effective_collection, store
from pokemon_hunter.beta import catalog_read_build as catalogs
from pokemon_hunter.beta.catalog_read_schema import migrate


@pytest.fixture
def prepared(cx):
    declarations_migrate(cx)
    migrate()
    catalogs.activate(catalogs.prepare())
    schema.migrate()
    accounts.prepare(cx["actor"])
    return cx


def parity(cx):
    actor = cx["actor"]
    token = accounts.catalog_current().token
    accounts.state(actor, token)
    expected = card_groups.project(actor)
    rows = store.rows("SELECT * FROM ar_groups WHERE user_id=%s ORDER BY id", [actor.user_id])
    assert [accounts.decode(r) for r in rows] == sorted(
        [
            {k: v for k, v in card_groups._summary(g, True).items() if k != "reference_image"}
            for g in expected["groups"]
        ],
        key=lambda r: r["id"],
    )
    reference = effective_collection.project(actor)
    cards = [
        accounts.decode(r) for r in store.rows("SELECT * FROM ar_cards WHERE user_id=%s", [actor.user_id])
    ]
    assert sorted(cards, key=lambda r: r["id"]) == sorted(reference["cards"], key=lambda r: r["id"])
    species = {
        r["id"]: accounts.decode(r)
        for r in store.rows("SELECT * FROM ar_species WHERE user_id=%s", [actor.user_id])
    }
    assert species == reference["species"]


def test_prepare_restart_and_policy_parity(prepared):
    parity(prepared)
    connection.close()
    with patch.object(collection, "catalog", side_effect=AssertionError("full reconstruction")):
        assert accounts.state(prepared["actor"], accounts.catalog_current().token)["status"] == "ready"


def test_add_undo_incremental_policy_parity(prepared):
    original = store.rows
    plans = {}

    def measured(sql, params=()):
        if "component IN" in sql and ("FROM ar_catalog " in sql or "FROM ar_cards " in sql):
            plans[sql] = original("EXPLAIN QUERY PLAN " + sql, params)
        return original(sql, params)

    with (
        patch.object(accounts, "prepare", side_effect=AssertionError("whole account refresh")),
        patch.object(store, "rows", side_effect=measured),
    ):
        op = add(prepared)
        parity(prepared)
        collection.undo(prepared["actor"], op["id"])
        parity(prepared)
    assert len(plans) >= 3
    for sql, plan in plans.items():
        assert any("component=?" in row["detail"] for row in plan), (sql, plan)


def test_source_replacement_and_unknown_quantities(prepared):
    select(prepared, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}})
    parity(prepared)
    add(prepared)
    parity(prepared)


def test_failed_refresh_preserves_confirmation_and_replay(prepared):
    with patch.object(accounts, "_refresh", side_effect=RuntimeError("injected")):
        op = add(prepared)
    assert op["state"] == "confirmed"
    assert collection.confirm(prepared["actor"], op["id"])["state"] == "confirmed"
    with pytest.raises(catalogs.Unavailable):
        accounts.state(prepared["actor"], accounts.catalog_current().token)
    accounts.prepare(prepared["actor"])
    parity(prepared)


def test_maintenance_and_catalog_invalidate(prepared):
    collection.execute(
        "UPDATE owned_copies SET notes='maintenance' WHERE user_id=%s", [prepared["actor"].user_id]
    )
    with pytest.raises(catalogs.Unavailable):
        accounts.state(prepared["actor"], accounts.catalog_current().token)
    accounts.prepare(prepared["actor"])
    collection.execute(
        "UPDATE printings SET publication_state='archived' WHERE id=%s", [prepared["by_legacy"]["a"]["id"]]
    )
    catalogs.activate(catalogs.prepare())
    with pytest.raises(catalogs.Unavailable):
        accounts.state(prepared["actor"], accounts.catalog_current().token)
    accounts.prepare(prepared["actor"])
    parity(prepared)


def test_corrupt_rows_invalidate_manifest(prepared):
    collection.execute("UPDATE ar_groups SET payload='{}' WHERE user_id=%s", [prepared["actor"].user_id])
    with pytest.raises(catalogs.Unavailable):
        accounts.state(prepared["actor"], accounts.catalog_current().token)
    accounts.prepare(prepared["actor"])
    parity(prepared)


def test_private_routes_restart_bounded_and_selectors(prepared):
    client = prepared["a"]
    key = card_groups.list_groups(prepared["actor"])["groups"][0]["id"]
    routes = [
        "card-groups/",
        "my-card-groups/",
        "card-group-filters/",
        f"card-groups/{key}/",
        f"card-groups/{key}/variants/",
        f"card-groups/{key}/copies/",
        f"card-groups/{key}/history/",
        "species/2/card-groups/",
        "pokedex-species/",
        "evidence/",
        "collection-context/",
        "catalog/",
        "catalog-unresolved/",
        "duplicate-counts/?ids=" + prepared["by_legacy"]["a"]["id"],
    ]
    with (
        patch.object(collection, "catalog", side_effect=AssertionError("catalog replay")),
        patch.object(effective_collection, "project", side_effect=AssertionError("journal replay")),
    ):
        for route in routes:
            response = client.get("/api/v2/" + route)
            assert response.status_code == 200, (route, response.content)
            assert response.json()["account_id"] == prepared["actor"].user_id
            assert response.json()["read_version"] == 2
            assert response["Cache-Control"] == "private, no-store"
    assert client.get("/api/v2/card-groups/?page=1&page=2").status_code == 400
    assert client.get("/api/v2/card-groups/?account_id=x").status_code == 400
    assert client.get("/api/v2/card-groups/?generation=999").status_code == 409
    for route in routes:
        assert prepared["client"]().get("/api/v2/" + route).status_code == 403
        assert prepared["b"].get("/api/v2/" + route).status_code == 503
    accounts.prepare(prepared["member"])
    assert prepared["b"].get("/api/v2/my-card-groups/").json()["total"] == 0
    copy = collection.copies(prepared["actor"])[0]
    assert prepared["b"].get(f"/api/v2/resources/copy/{copy['id']}/").status_code == 404


def test_role_and_revocation_checked_after_read(prepared):
    from pokemon_hunter.beta import account_read_queries as reads

    original = reads.page_result

    def changed(*args, **kwargs):
        collection.execute("UPDATE users SET role='member' WHERE id=%s", [prepared["actor"].user_id])
        return original(*args, **kwargs)

    with patch.object(reads, "page_result", side_effect=changed):
        assert prepared["a"].get("/api/v2/my-card-groups/").status_code == 403
    collection.execute("UPDATE users SET state='revoked' WHERE id=%s", [prepared["actor"].user_id])
    assert prepared["a"].get("/api/v2/card-groups/").status_code == 403


def test_metadata_edit_remove_quantity_and_recovery(prepared):
    from test_effective_collection import apply, remove

    actor = prepared["actor"]
    copy = collection.copies(actor)[0]
    for kind, request in (
        ("edit", dict(id=copy["id"], revision=copy["revision"], attributes=dict(condition="NM"))),
    ):
        op = apply(actor, kind, request)
        parity(prepared)
        collection.undo(actor, op["id"])
        parity(prepared)
    op = remove(prepared, collection.copies(actor)[0])
    parity(prepared)
    collection.undo(actor, op["id"])
    parity(prepared)
    schema.discard(actor)
    assert prepared["a"].get("/api/v2/card-groups/").status_code == 503
    accounts.prepare(actor)
    parity(prepared)
    schema.repair()
    assert prepared["a"].get("/api/v2/card-groups/").status_code == 503
    accounts.prepare(actor)
    parity(prepared)


def test_oversized_evidence_independent_download_and_corrupt_source(prepared):
    from pokemon_hunter.beta import account_read_queries as reads

    actor = prepared["actor"]
    row = store.rows("SELECT id FROM ar_copies WHERE user_id=%s LIMIT 1", [actor.user_id])[0]
    collection.execute("UPDATE owned_copies SET notes=%s WHERE id=%s", ["é" * 2000, row["id"]])
    accounts.prepare(actor)
    record = reads.resource(actor, kind="copy", key=row["id"])["record"]
    assert record["notes"] == "é" * 2000
    assert prepared["a"].get(f"/api/v2/resources/copy/{row['id']}/").status_code == 200
    collection.execute("UPDATE account_read_state SET sources='{}' WHERE user_id=%s", [actor.user_id])
    op = add(prepared)
    assert op["state"] == "confirmed"
    assert prepared["a"].get("/api/v2/card-groups/").status_code == 503


def test_bulk_copy_and_unresolved_binding_use_incremental_policy(prepared):
    from test_bulk_onboarding import commit, row

    from pokemon_hunter.beta import collection_drafts

    collection_drafts.initialize()
    with patch.object(accounts, "prepare", side_effect=AssertionError("whole account")):
        op = commit(prepared, [row(prepared, quantity=2)])
        parity(prepared)
        collection.undo(prepared["actor"], op["id"])
        parity(prepared)
        op = commit(prepared, [dict(row_id="p", set="Base Set 2", number="18", keep_unknown=True)])
        parity(prepared)
        collection.undo(prepared["actor"], op["id"])
        parity(prepared)


def test_group_search_filter_and_pagination_parity(prepared):
    from pokemon_hunter.beta import account_read_queries as reads

    for scope in ("catalog", "owned"):
        for q in ("", "a", "saur", "44", "%", "é"):
            for sort in ("set", "name", "number"):
                raw = dict(scope=scope, q=q, sort=sort, page_size="1")
                expected = card_groups.list_groups(prepared["actor"], raw)
                actual = reads.groups(prepared["actor"], raw)
                assert actual["total"] == expected["total"]
                assert [r["id"] for r in actual["groups"]] == [r["id"] for r in expected["groups"]]


def test_wal_read_detects_external_maintenance(prepared):
    import sqlite3

    from pokemon_hunter.beta import account_read_queries as reads

    collection.execute("PRAGMA journal_mode=WAL")
    original = reads.page_result

    def concurrent(*args, **kwargs):
        with sqlite3.connect(prepared["root"] / "inventory.db") as db:
            db.execute(
                "UPDATE owned_copies SET notes='concurrent' WHERE user_id=?", [prepared["actor"].user_id]
            )
        return original(*args, **kwargs)

    with patch.object(reads, "page_result", side_effect=concurrent):
        assert prepared["a"].get("/api/v2/my-card-groups/").status_code == 409
    assert prepared["a"].get("/api/v2/my-card-groups/").status_code == 503


def test_declaration_only_card_shares_species_dependency_closure(prepared):
    from test_collection_intents import identity
    from test_effective_collection import apply

    select(prepared, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon); Ivysaur #99 (Rare)"}})
    parity(prepared)
    apply(prepared["actor"], "card_quantity", {**identity(prepared, "a"), "established_total_quantity": 3})
    parity(prepared)
    add(prepared, "a")
    parity(prepared)


def test_frozen_goal_scope_survives_source_replacement(prepared):
    from test_collection_goals import create

    from pokemon_hunter.beta import account_read_queries as reads

    _, source = select(prepared, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}})
    goal = create(prepared, source)
    token = reads.species(prepared["actor"], {"goal": goal["id"], "version": goal["version"], "q": "Ivysaur"})
    assert token["species"][0]["goal_present"] is True
    select(prepared)
    actual = reads.species(
        prepared["actor"], {"goal": goal["id"], "version": goal["version"], "q": "Ivysaur"}
    )
    assert actual["species"][0]["goal_present"] is True
    assert actual["species"][0]["current_present"] is False
    with pytest.raises(collection.Conflict):
        reads.species(prepared["actor"], {"goal": goal["id"], "version": "stale"})
    accounts.prepare(prepared["member"])
    assert prepared["b"].get("/api/v2/pokedex-species/", {"goal": goal["id"]}).status_code == 404


def test_private_catalog_retains_nonpublic_membership(prepared):
    from test_catalog_reads import clone

    from pokemon_hunter.beta import account_read_queries as reads

    clone(prepared, id="private-japanese", language="ja", collector_number="99")
    catalogs.activate(catalogs.prepare())
    accounts.prepare(prepared["actor"])
    state = accounts.state(prepared["actor"], accounts.catalog_current().token)
    assert not state["catalog_equivalent"]
    expected = card_groups.list_groups(prepared["actor"])
    actual = reads.groups(prepared["actor"])
    assert actual["total"] == expected["total"]
    assert {r["id"] for r in actual["groups"]} == {r["id"] for r in expected["groups"]}
    assert any(r["language"] == "ja" for r in actual["groups"])
    for raw in ({"q": "99"}, {"q": "Ivysaur", "language": "ja"}):
        expected = card_groups.list_groups(prepared["actor"], raw)
        actual = reads.groups(prepared["actor"], raw)
        assert actual["total"] == expected["total"]
        assert {r["id"] for r in actual["groups"]} == {r["id"] for r in expected["groups"]}
    assert "ja" in {r["value"] for r in reads.options(prepared["actor"], {"field": "language"})["options"]}


def test_unresolved_source_species_aggregate_and_literal_readdition(prepared):
    from test_effective_collection import apply

    select(prepared, {2: {"Base Set 2": "✓"}})
    add(prepared, "a")
    parity(prepared)
    copy = next(
        c
        for c in collection.copies(prepared["actor"])
        if c["printing_id"] == prepared["by_legacy"]["a"]["id"]
    )
    apply(prepared["actor"], "remove", dict(id=copy["id"], revision=copy["revision"]))
    parity(prepared)
    select(prepared, {2: {"Base Set 2": "✓ Ivysaur #99 (Rare)"}})
    apply(prepared["actor"], "remove_card", dict(set_name="Base Set 2", name="Ivysaur", number="99"))
    parity(prepared)
    apply(prepared["actor"], "mark_owned", dict(set_name="Base Set 2", name="Ivysaur", number="99"))
    parity(prepared)


def test_species_scope_matches_authoritative_projection(prepared):
    from pokemon_hunter.beta import account_read_queries as reads
    from pokemon_hunter.beta import species_projection

    select(prepared, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}, 3: {"Base Set 2": "✓"}})
    add(prepared, "a")
    for selectors in (
        {},
        {"set": "Base Set 2"},
        {"finish": "holo"},
        {"finish": "normal"},
        {"rarity": "Unknown"},
        {"year": "2000"},
        {"released": "Unknown"},
        {"card": "Ivysaur 44"},
        {"type": "Pokémon", "owned": "owned"},
        {"q": "#2"},
        {"region": "johto"},
    ):
        expected = species_projection.project(prepared["actor"], selectors)
        actual = reads.species(prepared["actor"], {**selectors, "page_size": "100"})
        assert actual["total"] == len(expected["species"]), selectors
        for got, wanted in zip(actual["species"], expected["species"], strict=False):
            for field in (
                "dex",
                "current_present",
                "scoped_present",
                "scope_status",
                "eligible_indexed_printings",
                "goal_present",
            ):
                assert got[field] == wanted[field], (selectors, field, got, wanted)
        assert actual["current_progress"] == expected["current_progress"]
        assert actual["scoped_progress"] == expected["scoped_progress"]
        assert actual["coverage"] == expected["coverage"]


def test_all_subresources_session_isolation_and_logout(prepared):
    from pokemon_hunter.beta import account_read_queries as reads

    actor = prepared["actor"]
    group = reads.groups(actor)["groups"][0]["id"]
    copy = collection.copies(actor)[0]["id"]
    routes = [
        "species-filter-options/",
        f"card-groups/{group}/artwork/",
        f"card-groups/{group}/evidence/",
        f"aliases/{group}/",
        f"copies/{copy}/photos/",
        f"resources/copy/{copy}/",
        "resources/species/2/",
    ]
    for route in routes:
        response = prepared["a"].get("/api/v2/" + route)
        assert response.status_code == 200, (route, response.content)
        assert response["Cache-Control"] == "private, no-store"
    accounts.prepare(prepared["member"])
    assert prepared["b"].get(f"/api/v2/resources/copy/{copy}/").status_code == 404
    assert prepared["b"].get(f"/api/v2/copies/{copy}/photos/").status_code == 404
    prepared["a"].logout()
    for route in routes:
        assert prepared["a"].get("/api/v2/" + route).status_code == 403
    assert prepared["login"](prepared["a"], "collector", prepared["other_password"]).status_code == 302
    assert prepared["a"].get("/api/v2/my-card-groups/").json()["total"] == 0
    assert prepared["a"].get(f"/api/v2/resources/copy/{copy}/").status_code == 404


def test_partial_derived_failure_rolls_back_without_losing_receipt(prepared):
    original = accounts.persist

    def interrupted(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("Interrupted after derived writes")

    with patch.object(accounts, "persist", side_effect=interrupted):
        operation = add(prepared)
    assert operation["state"] == "confirmed"
    assert collection.confirm(prepared["actor"], operation["id"])["state"] == "confirmed"
    assert prepared["a"].get("/api/v2/my-card-groups/").status_code == 503
    accounts.prepare(prepared["actor"])
    parity(prepared)


def test_catalog_revision_changes_during_private_read(prepared):
    import sqlite3

    from pokemon_hunter.beta import account_read_queries as reads

    collection.execute("PRAGMA journal_mode=WAL")
    original = reads.page_result

    def changed(*args, **kwargs):
        with sqlite3.connect(prepared["root"] / "inventory.db") as db:
            db.execute(
                "UPDATE printings SET collector_number=collector_number || 'x' WHERE id=?",
                [prepared["by_legacy"]["a"]["id"]],
            )
        return original(*args, **kwargs)

    with patch.object(reads, "page_result", side_effect=changed):
        assert prepared["a"].get("/api/v2/card-groups/").status_code == 409
    assert prepared["a"].get("/api/v2/card-groups/").status_code == 503


def test_scope_sql_three_valued_date_policy(prepared):
    from pokemon_hunter.beta import account_read_species, species_scope

    evidence = [
        {},
        dict(set="s", set_name="Set", finish=None, release=dict(start="2000-01-01", end="2000-12-31")),
        dict(set="s", set_name="Set", finish="holo", release=dict(start="1999-12-01", end="2000-01-31")),
    ]
    for selected in (
        {"year": "2000"},
        {"released": "Unknown"},
        {"year": '["1999","2000"]'},
        {"date_from": "2000-03-01"},
        {"released": "pre-2000", "finish": "holo"},
        {"set": "Set", "finish": "normal"},
        {"released": "Unknown", "set": "Set"},
    ):
        expression, args = account_read_species.expression(selected)
        for row in evidence:
            columns = ",".join("%s AS " + field for field in account_read_species.FIELDS)
            got = store.rows(
                "SELECT (" + expression + ") AS matched FROM (SELECT " + columns + ")",
                [*args, *account_read_species.values(row)],
            )[0]["matched"]
            expected = species_scope.match(row, selected)
            assert got == expected, (selected, row, got, expected)


def test_resolve_and_import_remain_authoritative(prepared):
    import json

    from test_effective_collection import apply

    actor = prepared["actor"]
    op = apply(
        actor, "photo", dict(provisional_identity=json.dumps(dict(note="Unidentified engineering copy")))
    )
    parity(prepared)
    copy = op["changes"][0]["after"]
    resolved = apply(
        actor,
        "resolve",
        dict(id=copy["id"], revision=copy["revision"], printing_id=prepared["by_legacy"]["a"]["id"]),
    )
    parity(prepared)
    collection.undo(actor, resolved["id"])
    parity(prepared)
    apply(
        actor,
        "import",
        dict(
            format="json",
            text=json.dumps([dict(printing_id=prepared["by_legacy"]["c"]["id"], notes="engineering import")]),
            duplicate_policy="allow",
        ),
    )
    parity(prepared)


def test_declared_variant_is_separate_from_exact_physical_copy(prepared):
    from test_collection_defaults import request
    from test_effective_collection import apply, remove

    from pokemon_hunter.beta import account_read_queries as reads

    actor = prepared["actor"]
    key = prepared["by_legacy"]["a"]["id"]
    remove(prepared, next(c for c in collection.copies(actor) if c["printing_id"] == key))
    collection.execute(
        "UPDATE printings SET edition=NULL,finish='normal',variant=%s,unresolved_fields=%s WHERE id=%s",
        ['{"type":"normal"}', '["edition"]', key],
    )
    catalogs.activate(catalogs.prepare())
    accounts.prepare(actor)
    select(prepared, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}})
    op = apply(actor, "card_defaults", request(prepared))
    parity(prepared)
    group = reads.groups(actor, {"scope": "owned"})["groups"][0]
    variant = next(v for v in reads.variants(actor, key=group["id"])["variants"] if v["id"] == key)
    assert variant["declared_variant_owned"] and not variant["exact_printing_owned"]
    assert variant["established_total_quantity"] is None
    assert reads.detail(actor, key=group["id"])["ownership_evidence_url"]
    collection.undo(actor, op["id"])
    assert not next(v for v in reads.variants(actor, key=group["id"])["variants"] if v["id"] == key)[
        "declared_variant_owned"
    ]
    parity(prepared)


def test_failure_to_mark_unavailable_cannot_erase_confirmation(prepared):
    from django.db import DatabaseError

    original = collection.execute

    def broken(sql, params=()):
        if "SET status='unavailable'" in sql:
            raise DatabaseError("Recovery state unavailable")
        return original(sql, params)

    with (
        patch.object(accounts, "_refresh", side_effect=RuntimeError("injected")),
        patch.object(collection, "execute", side_effect=broken),
    ):
        op = add(prepared)
    assert op["state"] == "confirmed"
    assert collection.confirm(prepared["actor"], op["id"])["state"] == "confirmed"
    assert prepared["a"].get("/api/v2/my-card-groups/").status_code == 503
    accounts.prepare(prepared["actor"])
    parity(prepared)


def test_explicit_operator_lifecycle_on_existing_engineering_root(prepared):
    import subprocess
    import sys

    (prepared["root"] / "B4_ISOLATED").touch()

    def run(action):
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "pokemon_hunter.beta.account_read_operator",
                "--root",
                str(prepared["root"]),
                "--username",
                "admin",
                action,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

    assert run("status").returncode == 0
    assert run("discard").returncode == 0
    assert prepared["a"].get("/api/v2/my-card-groups/").status_code == 503
    outcome = run("prepare")
    assert outcome.returncode == 0, outcome.stderr
    parity(prepared)


def test_species_set_candidates_keep_unknowns_with_index_seeks(prepared):
    from pokemon_hunter.beta import account_read_species

    build = accounts.catalog_current().build
    examples = [
        ("probe-id", "wanted", "Other name"),
        ("probe-name", "different", "wanted"),
        ("probe-null", None, "No evidence"),
        ("probe-unknown", "Unknown", "No evidence"),
        ("probe-excluded", "different", "Different name"),
    ]
    for key, set_id, set_name in examples:
        collection.execute(
            "INSERT INTO ar_scope_catalog(build,id,species,set_id,set_name) VALUES(%s,%s,25,%s,%s)",
            [build, key, set_id, set_name],
        )
    predicate, args = account_read_species.candidates(build, {"set": "wanted"})
    sql = "SELECT id FROM ar_scope_catalog WHERE build=%s" + predicate
    found = {row["id"] for row in store.rows(sql, [build, *args])}
    assert found.intersection(row[0] for row in examples) == {row[0] for row in examples[:-1]}
    plans = [row["detail"] for row in store.rows("EXPLAIN QUERY PLAN " + sql, [build, *args])]
    set_plans = [plan for plan in plans if "ar_scope_set_options" in plan]
    assert len(set_plans) == 2
    assert all("build=? AND set_id=?" in plan for plan in set_plans), plans
