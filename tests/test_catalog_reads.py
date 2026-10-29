"""PERF-02 qualification uses disposable engineering state only."""

import json
import sqlite3
from unittest.mock import patch

import pytest
from django.db import connection
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_effective_collection import cx as cx
from test_migration import snapshot as snapshot
from test_ownership_declarations import migrate as declarations_migrate
from test_sealed_catalog import e1 as e1

from pokemon_hunter.beta import card_groups, collection, public_catalog, store
from pokemon_hunter.beta import catalog_read_build as builds
from pokemon_hunter.beta import catalog_read_queries as reads
from pokemon_hunter.beta.catalog_read_schema import ACCOUNT_AUTHORITIES, CATALOG_AUTHORITIES, migrate


def clone(cx, **changes):
    row = store.rows("SELECT * FROM printings WHERE id=%s", [cx["by_legacy"]["a"]["id"]])[0]
    row.update(changes)
    collection.execute(
        "INSERT INTO printings (" + ",".join(row) + ") VALUES (" + ",".join(["%s"] * len(row)) + ")",
        list(row.values()),
    )
    return row


@pytest.fixture
def prepared(cx):
    declarations_migrate(cx)
    migrate()
    build = builds.prepare()
    builds.activate(build)
    return cx


def test_public_parity_and_bounded_routes(prepared):
    expected = card_groups.list_groups()
    actual = reads.groups()
    assert actual["groups"] == expected["groups"]
    assert actual["total"] == expected["total"]
    assert reads.evidence()["total"] == len(expected["unresolved"])
    key = actual["groups"][0]["id"]
    old = card_groups.detail(None, key)
    assert reads.detail(key=key)["group"] == old["group"]
    assert reads.variants(key=key)["variants"] == old["variants"]
    for route in (
        "card-groups/",
        f"card-groups/{key}/",
        f"card-groups/{key}/variants/",
        "catalog/",
        "card-group-filters/",
        "species/2/card-groups/",
        "pokedex-species/",
        "evidence/",
    ):
        response = prepared["client"]().get("/api/v2/public/" + route)
        assert response.status_code == 200, response.content
        assert response.json()["read_version"] == 2
        assert response["Cache-Control"] == "no-store"
    assert prepared["client"]().get("/api/v2/public/card-groups/?page=1&page=2").status_code == 400
    for raw in (
        {"page_size": "101"},
        {"scope": "owned"},
        {"account_id": "x"},
        {"sort": "weird"},
        {"species": "252"},
    ):
        with pytest.raises(ValueError):
            reads.groups(raw)
    assert reads.resolve(key="a")["child"] == prepared["by_legacy"]["a"]["id"]
    with (
        patch.object(public_catalog, "entries", side_effect=AssertionError("full load")),
        patch.object(collection, "catalog_entries", side_effect=AssertionError("full load")),
    ):
        assert reads.groups()["groups"] == actual["groups"]


def test_publication_invalidates_before_rebuild_and_stale_token_is_409(prepared):
    client = prepared["client"]()
    token = reads.groups()["catalog_revision"]
    old = builds.active()[0]["id"]
    candidate = builds.prepare()
    collection.execute(
        "UPDATE printings SET publication_state='archived' WHERE id=%s", [prepared["by_legacy"]["a"]["id"]]
    )
    with pytest.raises(collection.Conflict):
        builds.activate(candidate)
    assert client.get("/api/v2/public/card-groups/").status_code == 503
    assert client.get("/api/v2/public/card-groups/", {"catalog_revision": token}).status_code == 409
    new = builds.prepare()
    builds.activate(new)
    assert reads.groups()["total"] == 2
    assert store.rows("SELECT id FROM catalog_read_builds WHERE id=%s", [old])
    assert store.rows(
        "SELECT id FROM cr_children WHERE build=%s AND scope IN ('retained','shared') AND id=%s",
        [new, prepared["by_legacy"]["a"]["id"]],
    )


def test_corrupt_missing_incompatible_and_interrupted(prepared):
    old = builds.active()[0]["id"]
    with patch.object(builds, "validate", side_effect=RuntimeError("interrupted")):
        with pytest.raises(RuntimeError):
            builds.prepare()
    assert builds.active()[0]["id"] == old
    candidate = builds.prepare()
    collection.execute("UPDATE cr_groups SET payload='{}' WHERE build=%s", [candidate])
    with pytest.raises(builds.Unavailable):
        builds.activate(candidate)
    collection.execute("DELETE FROM cr_grams WHERE build=%s", [old])
    with pytest.raises(builds.Unavailable):
        reads.groups()
    build = builds.prepare()
    builds.activate(build)
    collection.execute("UPDATE catalog_read_schema SET version=99")
    with pytest.raises(builds.Unavailable):
        reads.groups()
    collection.execute("UPDATE catalog_read_schema SET version=1")
    collection.execute("DELETE FROM catalog_read_active")
    with pytest.raises(builds.Unavailable):
        reads.groups()


def test_migration_and_account_preview_exclusion(prepared):
    migrate()
    names = {r["name"] for r in store.rows("SELECT name FROM sqlite_master WHERE type='trigger'")}
    for table in (*CATALOG_AUTHORITIES, *ACCOUNT_AUTHORITIES):
        for event in ("insert", "update", "delete"):
            prefix = "cr_rev" if table in CATALOG_AUTHORITIES else "cr_account"
            assert f"{prefix}_{table}_{event}" in names
    generation = collection.generation(prepared["actor"])
    before = store.rows("SELECT * FROM account_read_revisions")
    preview = collection.preview(
        prepared["actor"],
        "add",
        dict(printing_id=prepared["by_legacy"]["c"]["id"], duplicate_policy="allow"),
        "00000000-0000-0000-0000-000000000001",
    )
    assert store.rows("SELECT * FROM account_read_revisions") == before
    assert collection.generation(prepared["actor"]) == generation
    token = reads.groups()["catalog_revision"]
    collection.confirm(prepared["actor"], preview["id"])
    assert store.rows("SELECT * FROM account_read_revisions") != before
    assert reads.groups()["catalog_revision"] == token
    collection.undo(prepared["actor"], preview["id"])
    assert collection.generation(prepared["actor"]) == generation + 2
    # Raw older-code writes still advance authority without a Python adapter.
    with sqlite3.connect(prepared["root"] / "inventory.db") as db:
        db.execute("UPDATE games SET name=name")
    with pytest.raises(builds.Unavailable):
        reads.groups()


def test_unicode_short_search_variants_and_conflicts(prepared):
    clone(
        prepared,
        id="variant-1",
        finish="holo",
        edition="first_edition",
        attributes=json.dumps(dict(name="Ivysaur", pokemon_dex=2, supertype="Pokémon")),
    )
    clone(prepared, id="variant-2", finish="normal", edition=None, provenance=json.dumps({"legacy_id": "a"}))
    builds.activate(builds.prepare())
    for q in ("", "a", "i", "IvY", "44", "base 2", "é", "'", "%", "_", "saur 44"):
        for sort in ("set", "name", "number"):
            for filters in (
                {"q": q, "sort": sort},
                {"q": q, "finish": "holo"},
                {"q": q, "finish": "normal", "edition": "first_edition"},
            ):
                expected = card_groups.list_groups(None, filters)
                result = reads.groups(filters)
                assert result["total"] == expected["total"]
                assert [r["id"] for r in result["groups"]] == [r["id"] for r in expected["groups"]]
    with pytest.raises(collection.Conflict):
        reads.resolve(key="a")
    clone(
        prepared,
        id="conflicting",
        attributes=json.dumps(dict(name="Other", pokemon_dex=2, supertype="Pokémon")),
    )
    builds.activate(builds.prepare())
    assert reads.evidence()["total"] == len(card_groups.project()["unresolved"])


def test_oversized_evidence_is_downloadable_without_truncation(prepared):
    long_name = "Long " * 10000 + "end"
    clone(
        prepared,
        id="conflicting-long",
        attributes=json.dumps(dict(name=long_name, pokemon_dex=2, supertype="Pokémon")),
    )
    builds.activate(builds.prepare())
    result = reads.evidence()
    record = next(r["record"] for r in result["evidence"] if r["record"].get("oversized"))
    response = prepared["client"]().get(record["url"])
    assert response.status_code == 200
    assert long_name in response.content.decode()
    assert response["Content-Disposition"].startswith("attachment")
    assert len(json.dumps(result).encode()) < 128 * 1024


def test_concurrent_authority_change_rejects_release_and_cpu_has_no_write_lock(prepared):
    dbpath = prepared["root"] / "inventory.db"
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA journal_mode=WAL")
    original = reads.payload
    changed = False

    def concurrent(row, *args, **kwargs):
        nonlocal changed
        if not changed:
            changed = True
            with sqlite3.connect(dbpath, timeout=0.1) as other:
                other.execute("UPDATE printings SET collector_number=collector_number")
        return original(row, *args, **kwargs)

    with patch.object(reads, "payload", side_effect=concurrent):
        with pytest.raises(collection.Conflict):
            reads.groups()
    original_build = builds.materialize

    def mutate_during_cpu(*args):
        with sqlite3.connect(dbpath, timeout=0.1) as other:
            other.execute("UPDATE games SET name=name")
        return original_build(*args)

    with patch.object(builds, "materialize", side_effect=mutate_during_cpu):
        candidate = builds.prepare()
    with pytest.raises(collection.Conflict):
        builds.activate(candidate)


def test_old_reader_survives_activation_and_explicit_cleanup(prepared):
    import threading

    from pokemon_hunter.beta.catalog_read_schema import TABLES

    with connection.cursor() as cursor:
        cursor.execute("PRAGMA journal_mode=WAL")
    old = builds.active()[0]["id"]
    candidate = builds.prepare()
    original = reads.payload
    errors = []
    changed = False

    def release_old():
        try:
            builds.activate(candidate)
            builds.discard(old)
        except Exception as exc:
            errors.append(exc)
        finally:
            connection.close()

    def concurrent(row, *args, **kwargs):
        nonlocal changed
        if not changed:
            changed = True
            thread = threading.Thread(target=release_old)
            thread.start()
            thread.join(3)
            assert not thread.is_alive()
        return original(row, *args, **kwargs)

    with patch.object(reads, "payload", side_effect=concurrent):
        assert reads.groups()["total"] == 3
    assert not errors
    for table in TABLES:
        assert not store.rows(f"SELECT 1 FROM {table} WHERE build=%s", [old])
    assert builds.active()[0]["id"] == candidate
    with pytest.raises(ValueError):
        builds.discard(candidate)


def test_unprepared_get_never_migrates_or_rebuilds(cx):
    assert cx["client"]().get("/api/v2/public/card-groups/").status_code == 503
    assert not store.rows("SELECT 1 FROM sqlite_master WHERE name='catalog_read_schema'")


def test_internal_metadata_preserves_archived_and_unresolved(prepared):
    from pokemon_hunter.beta import catalog_read_internal as internal

    child = prepared["by_legacy"]["a"]["id"]
    collection.execute(
        "UPDATE printings SET publication_state='archived',unresolved_fields='[\"name\"]' WHERE id=%s",
        [child],
    )
    builds.activate(builds.prepare())
    snap = internal.current()
    row = internal.printing_metadata(snap, [child])[0]
    assert not row["published"] and row["group_id"] is None
    assert row["printing"]["id"] == child
    assert internal.alias_candidates(snap, "a")["printing_ids"] == [child]
    assert internal.account_key(prepared["actor"])["internal_account_id"] == prepared["actor"].user_id
    with pytest.raises(ValueError):
        internal.printing_metadata(snap, [str(n) for n in range(101)])


def test_pipeline_revision_backstop_and_schema_reentry(prepared):
    from pokemon_hunter.beta import catalog_pipeline

    if "catalog_batches" not in connection.introspection.table_names():
        catalog_pipeline.initialize()
    with pytest.raises(builds.Unavailable):
        reads.groups()
    migrate()
    builds.activate(builds.prepare())
    revision = builds.revision()
    collection.execute(
        "INSERT INTO catalog_batches(id,user_id,package,package_hash,state,baseline,outcomes) VALUES('epoch',%s,'{}','epoch','preview','{}','[]')",
        [prepared["actor"].user_id],
    )
    assert builds.revision() > revision
    builds.activate(builds.prepare())
    revision = builds.revision()
    collection.execute("DROP TRIGGER cr_rev_catalog_batches_update")
    collection.execute("UPDATE catalog_batches SET package='{}' WHERE id='epoch'")
    assert builds.revision() == revision
    with pytest.raises(builds.Unavailable):
        reads.groups()
    migrate()
    assert builds.revision() > revision
    with pytest.raises(builds.Unavailable):
        reads.groups()


def test_complete_options_variants_and_oversized_resources(prepared):
    for n in range(205):
        clone(prepared, id=f"variant-{n}", variant=f"variant-{n:03}")
    enormous = "literal-" + "é" * 4000
    clone(prepared, id="enormous", variant=enormous)
    builds.activate(builds.prepare())
    first = reads.options({"field": "variant"})
    assert first["total"] == 206 and len(first["options"]) == 40 and first["next"]
    all_options = []
    for page in range(1, first["pages"] + 1):
        result = reads.options({"field": "variant", "page": str(page)})
        all_options.extend(result["options"])
        assert len(json.dumps(result).encode()) <= 32768
    assert len(all_options) == first["total"]
    pointer = next(r for r in all_options if r.get("oversized"))
    assert prepared["client"]().get(pointer["url"]).json()["record"]["value"] == enormous
    key = reads.resolve(key=prepared["by_legacy"]["a"]["id"])["group_id"]
    variants = reads.variants(key=key)
    assert variants["total"] == 207 and len(variants["variants"]) == 40
    selected = reads.detail({"child": "enormous"}, key=key)["selected_child"]
    assert selected["oversized"]
    assert prepared["client"]().get(selected["url"]).json()["record"]["variant"] == enormous
    group = reads.groups({"q": "variant-1"})["groups"][0]
    response = prepared["client"]().get(group["matching_variants"]["url"], {"q": "variant-1"})
    assert response.status_code == 200 and response.json()["total"] == 100


def test_search_order_and_species_reference(prepared):
    for i, (number, name) in enumerate(
        [("2", "Flabébé"), ("10", "Farfetch’d"), ("01", "Straße"), ("A-2", "MR. Mime"), ("A-10", "雪")]
    ):
        clone(
            prepared,
            id=f"order-{i}",
            collector_number=number,
            attributes=json.dumps(dict(name=name, pokemon_dex=25, supertype="Pokémon")),
        )
    builds.activate(builds.prepare())
    for sort in ("set", "name", "number"):
        for q in ("", "é", "BÉ", "strasse", "fetch’d", "mr.", "雪", "A-", "saur 44"):
            expected = card_groups.list_groups(None, {"sort": sort, "q": q, "page_size": "2"})
            result = reads.groups({"sort": sort, "q": q, "page_size": "2"})
            assert result["total"] == expected["total"]
            assert [r["id"] for r in result["groups"]] == [r["id"] for r in expected["groups"]]
            for page in range(1, result["pages"] + 1):
                current = reads.groups({"sort": sort, "q": q, "page_size": "2", "page": str(page)})
                oracle = card_groups.list_groups(
                    None, {"sort": sort, "q": q, "page_size": "2", "page": str(page)}
                )
                assert [r["id"] for r in current["groups"]] == [r["id"] for r in oracle["groups"]]
    for query in (
        {},
        {"q": "pikachu"},
        {"q": "#25"},
        {"q": "000025"},
        {"q": "flabébé"},
        {"region": "johto"},
        {"type": "Pokémon"},
        {"era": "Unknown"},
    ):
        expected = public_catalog.pokedex(query)["species"]
        result = reads.species({**query, "page_size": "100"})
        assert result["total"] == len(expected)
        for actual, oracle in zip(result["species"], expected[:100], strict=True):
            assert {k: actual[k] for k in oracle} == oracle


def test_fts_corruption_and_incompatible_backend_fail_explicitly(prepared):
    collection.execute("INSERT INTO cr_gram_index(cr_gram_index) VALUES('delete-all')")
    with pytest.raises(builds.Unavailable):
        reads.groups()
    with patch.object(connection, "vendor", "postgresql"):
        with pytest.raises(builds.Unavailable):
            reads.groups()
    from django.test import override_settings

    with override_settings(B4_ENABLED=False):
        with pytest.raises(builds.Unavailable):
            reads.groups()


def test_prepare_integrity_rejects_tampering_and_no_private_fields(prepared):
    old = builds.active()[0]["id"]
    original = builds.validate

    def tamper(build):
        collection.execute(
            "UPDATE cr_groups SET payload='{}',sha=%s WHERE build=%s", [builds.digest("{}"), build]
        )
        return original(build)

    with patch.object(builds, "validate", side_effect=tamper):
        with pytest.raises(builds.Unavailable):
            builds.prepare()
    assert builds.active()[0]["id"] == old
    text = json.dumps(reads.groups()) + json.dumps(reads.printings()) + json.dumps(reads.species())
    for forbidden in (
        "source_text",
        "provenance",
        "purchase_amount",
        "photo_references",
        "auth_subject",
        "account_id",
    ):
        assert forbidden not in text


def test_explicit_corruption_and_missing_schema_recovery(prepared):
    from pokemon_hunter.beta.catalog_read_schema import repair

    before = store.rows("SELECT id,attributes FROM printings ORDER BY id")
    accounts = store.rows("SELECT * FROM account_read_revisions")
    collection.execute("INSERT INTO cr_gram_index(cr_gram_index) VALUES('delete-all')")
    with pytest.raises(builds.Unavailable):
        reads.groups()
    builds.repair_index()
    builds.activate(builds.prepare())
    assert reads.groups()["total"] == 3
    revision = builds.revision()
    collection.execute("DROP TABLE cr_match")
    with pytest.raises(builds.Unavailable):
        reads.groups()
    repair()
    assert builds.revision() == revision + 1
    assert store.rows("SELECT * FROM account_read_revisions") == accounts
    assert store.rows("SELECT id,attributes FROM printings ORDER BY id") == before
    builds.activate(builds.prepare())
    assert reads.groups()["total"] == 3
    collection.execute("UPDATE catalog_read_builds SET stride=stride+1")
    with pytest.raises(builds.Unavailable):
        reads.groups()


def test_mixed_scopes_conflicts_and_literal_publication(prepared):
    from pokemon_hunter.beta import catalog_read_internal as internal

    original = prepared["by_legacy"]["a"]["id"]
    clone(prepared, id="archived", publication_state="archived")
    builds.activate(builds.prepare())
    key = reads.resolve(key=original)["group_id"]
    assert reads.detail(key=key)["variants"]["total"] == 1
    assert reads.printings({"q": "Ivysaur"})["total"] == 1
    assert internal.alias_candidates(internal.current(), "a")["total"] == 2
    clone(
        prepared,
        id="archived-conflict",
        publication_state="archived",
        attributes=json.dumps(dict(name="Contradiction", pokemon_dex=2, supertype="Pokémon")),
    )
    builds.activate(builds.prepare())
    assert reads.resolve(key=original)["group_id"] == key
    assert internal.printing_metadata(internal.current(), [original])[0]["group_id"] is None
    old = reads.groups()["catalog_revision"]
    collection.execute("UPDATE printings SET publication_state='published' WHERE id='archived-conflict'")
    with pytest.raises(collection.Conflict):
        reads.groups({"catalog_revision": old})
    builds.activate(builds.prepare())
    assert reads.groups()["total"] == 2
    assert reads.unresolved_printings()["total"] == 2
    assert reads.evidence()["total"] == 1


def test_pickers_same_child_and_arbitrary_deep_pages(prepared):
    clone(
        prepared,
        id="term-a",
        provenance="{}",
        attributes=json.dumps(
            dict(name="Ivysaur", pokemon_dex=2, supertype="Pokémon", variant_label="UniqueAB")
        ),
    )
    clone(
        prepared,
        id="term-b",
        provenance="{}",
        attributes=json.dumps(
            dict(name="Ivysaur", pokemon_dex=2, supertype="Pokémon", variant_label="UniqueCD")
        ),
    )
    clone(
        prepared,
        id="long-word",
        collector_number="65",
        provenance="{}",
        attributes=json.dumps(
            dict(name="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNO", pokemon_dex=2, supertype="Pokémon")
        ),
    )
    builds.activate(builds.prepare())
    assert reads.groups({"q": "UniqueAB UniqueCD"})["total"] == 0
    assert reads.printings({"q": "UniqueAB UniqueCD"})["total"] == 0
    for query in ("ivysaur", "uniqueab", "jklmnopqr", "set 44", "2"):
        expected = [
            r
            for r in public_catalog.entries()
            if all(
                t
                in (
                    " ".join(str(r[k]) for k in ("name", "collector_number", "set_name"))
                    + " "
                    + r["variant_label"]
                ).casefold()
                for t in query.split()
            )
        ]
        for sort in ("set", "name", "number"):
            ids = []
            first = reads.printings({"q": query, "page_size": "2", "sort": sort})
            assert first["total"] == len(expected)
            for page in range(1, first["pages"] + 1):
                ids.extend(
                    r["id"]
                    for r in reads.printings({"q": query, "page_size": "2", "sort": sort, "page": str(page)})[
                        "cards"
                    ]
                )
            assert len(ids) == len(set(ids))
            assert set(ids) == {r["id"] for r in expected}
    for service in (reads.groups, reads.printings, reads.evidence, reads.options, reads.unresolved_printings):
        assert service({"page": "9" * 160})["page"] == int("9" * 160)
    assert reads.groups({"page": "9" * 160, "q": "ivysaur"})["groups"] == []


def test_publication_adapter_invalidates_without_revising_collection(prepared):
    from test_b4 import publish

    from pokemon_hunter.beta import catalog_imports

    generation = collection.generation(prepared["actor"])
    operation = publish(prepared)
    with pytest.raises(builds.Unavailable):
        reads.groups()
    builds.activate(builds.prepare())
    catalog_imports.transition(prepared["actor"], operation["id"], "rollback")
    with pytest.raises(builds.Unavailable):
        reads.groups()
    assert collection.generation(prepared["actor"]) == generation


def test_operator_explicit_lifecycle_on_existing_engineering_root(prepared, tmp_path):
    import subprocess
    import sys

    (prepared["root"] / "B4_ISOLATED").touch()
    base = [
        sys.executable,
        "-m",
        "pokemon_hunter.beta.catalog_read_operator",
        "--root",
        str(prepared["root"]),
    ]

    def run(*args):
        return subprocess.run([*base, *args], capture_output=True, text=True, check=True, timeout=30).stdout

    original = json.loads(run("status"))
    run("migrate")
    assert json.loads(run("status")) == original
    candidate = json.loads(run("prepare"))
    assert candidate["activated"] is False
    assert json.loads(run("status")) == original
    run("activate", "--build", str(candidate["build"]))
    assert json.loads(run("status"))["build"] == candidate["build"]
    run("discard", "--build", str(original["build"]))
    absent = tmp_path / "must-not-initialize"
    rejected = subprocess.run(
        [*base[:-1], str(absent), "migrate"], capture_output=True, text=True, timeout=30
    )
    assert rejected.returncode != 0 and not absent.exists()


def test_validation_serializes_competing_writer_and_activation_rechecks_authority(prepared):
    import threading

    with connection.cursor() as cursor:
        cursor.execute("PRAGMA journal_mode=WAL")
    entered = threading.Event()
    finished = threading.Event()
    errors = []

    def write_authority():
        try:
            with sqlite3.connect(prepared["root"] / "inventory.db", timeout=5) as other:
                entered.set()
                other.execute("UPDATE games SET name=name")
        except Exception as exc:
            errors.append(exc)
        finally:
            finished.set()

    writer = threading.Thread(target=write_authority)
    original = builds.validate_payload
    started = False

    def overlap(table, row):
        nonlocal started
        if not started:
            started = True
            writer.start()
            assert entered.wait(2)
            # A deferred reader permits this writer to commit, then cannot upgrade
            # its stale snapshot for the FTS check/status write. An immediate
            # maintenance transaction holds the writer until validation commits.
            finished.wait(0.1)
        return original(table, row)

    try:
        with patch.object(builds, "validate_payload", side_effect=overlap):
            candidate = builds.prepare()
    finally:
        if started:
            writer.join(6)
    assert started and not writer.is_alive() and not errors
    assert store.rows("SELECT status FROM catalog_read_builds WHERE id=%s", [candidate]) == [
        {"status": "validated"}
    ]
    with pytest.raises(collection.Conflict):
        builds.activate(candidate)
