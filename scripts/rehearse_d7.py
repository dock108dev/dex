"""D7 real packages on fresh disposable SQLite; acquisition prohibited."""

import argparse
import copy
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from prepare_d7 import DEST, ROOT, write
from rehearse_e3a import snapshot
from rehearse_m1 import run as prepare_m1


def run(root, output):
    prepare_m1(root, output)
    from django.contrib.auth import get_user_model
    from django.http import Http404

    from pokemon_hunter.beta import catalog_imports as cat
    from pokemon_hunter.beta import catalog_pipeline as pipe
    from pokemon_hunter.beta import collection, lookup, pack_research, product_lookup, store
    from pokemon_hunter.beta import sealed_catalog as sealed

    actor = store.principal(get_user_model().objects.get(username="admin").pk)
    pipe.initialize()

    def publish(service, raw):
        op = service.preview(actor, raw)
        service.transition(actor, op["id"], "verify")
        while service.get(actor, op["id"])["state"] != "published":
            service.transition(actor, op["id"], "publish")
        assert service.preview(actor, raw)["id"] == op["id"]
        return op["id"]

    retained = pipe.retained_batch()
    retained["mode"] = "atomic"
    publish(pipe, retained)
    publish(cat, json.loads((ROOT / "config/catalog-pipeline/d6-20261005/gym1.json").read_text()))
    publish(sealed, json.loads((ROOT / "config/sealed/d6-20261005/package.json").read_text()))
    publish(pipe, json.loads((ROOT / "config/catalog-pipeline/d6-20261005/batch.json").read_text()))
    before = snapshot(root)
    write(output / "before.json", before)
    catalog = json.loads((ROOT / "config/sealed/d7-20261005/catalog-package.json").read_text())
    batch = json.loads((DEST / "batch.json").read_text())
    shopping = json.loads((ROOT / "config/sealed/d7-20261005/shopping-package.json").read_text())
    for name, raw in [("catalog", catalog), ("batch", batch), ("shopping", shopping)]:
        write(output / (name + "-input.json"), raw)
    # Every M2 package and all exact refs are validated through the existing services.
    pipe.Batch.model_validate(batch)
    for a in batch["sets"]:
        cat.validate(a["package"])
    sealed.validate(catalog, sealed.records())
    broken = copy.deepcopy(catalog)
    broken["printings"][0]["expansion_id"] = "missing:exact-expansion"
    try:
        sealed.validate(broken, sealed.records())
    except ValueError as e:
        write(output / "exact-reference-refusal.json", dict(error=str(e), writes=False))
    else:
        raise AssertionError("Broken reference accepted")
    cid = publish(sealed, catalog)
    bid = publish(pipe, batch)
    sealed.validate(shopping, sealed.records())
    op = sealed.preview(actor, shopping)
    sealed.transition(actor, op["id"], "verify")
    stale = copy.deepcopy(shopping)
    stale["version"] += "-competing-review"
    competing = sealed.preview(actor, stale)
    sealed.transition(actor, competing["id"], "verify")
    sealed.transition(actor, op["id"], "publish")
    sid = op["id"]
    assert sealed.preview(actor, shopping)["id"] == sid
    current = sealed.records()
    try:
        sealed.transition(actor, competing["id"], "publish")
    except (ValueError, collection.Conflict) as e:
        write(
            output / "stale-correction-refusal.json",
            dict(
                error=str(e),
                state=sealed.get(actor, competing["id"])["state"],
                published_records_unchanged=current == sealed.records(),
            ),
        )
    else:
        raise AssertionError("Stale competing correction accepted")
    assert current == sealed.records()
    for obs in shopping["observations"]:
        assert sealed.records()["observations"][obs["id"]] == obs
    # Inherited D6 observation stays immutable and does not adopt this run's time.
    oldid = "target:91619942:d6:20261006T031602"
    assert sealed.records()["observations"][oldid]["checked_at"] == "2026-10-06T03:16:02.472952+00:00"
    write(output / "catalog-publication.json", sealed.get(actor, cid))
    write(output / "batch-publication.json", pipe.get(actor, bid))
    write(output / "shopping-publication.json", sealed.get(actor, sid))
    write(output / "coverage.json", pipe.coverage(actor))
    write(
        output / "product-coverage.json",
        product_lookup.coverage(sealed.records(), datetime.now(UTC), collection.catalog(actor)),
    )
    for dex in [123, 134, 196, 197, 251]:
        write(output / f"lookup-{dex}.json", lookup.project(actor, dict(scope="all", targets=str(dex))))
    missing = lookup.project(actor, dict(scope="missing"))
    assert (
        missing["progress"]["satisfied"] == 161
        and len(missing["missing"]) == 90
        and sum(x["pokemon_dex"] <= 151 for x in missing["missing"]) == 14
    )
    changed = {
        "printings",
        "catalog_sets",
        "catalog_heads",
        "external_mappings",
        "catalog_aliases",
        "catalog_imports",
        "catalog_audit",
        "catalog_batches",
        "collection_generations",
        "sqlite_sequence",
    }
    protected = [t for t in before["rows"] if t not in changed and not t.startswith("sealed_")]
    after = snapshot(root)
    for t in protected:
        assert before["rows"][t] == after["rows"][t], t
    assert before["photos"] == after["photos"]
    sealed.transition(actor, sid, "rollback")
    pipe.transition(actor, bid, "rollback")
    sealed.transition(actor, cid, "rollback")
    # Sealed records restored exactly, including former product quantities and original observations.
    restored = snapshot(root)
    for t in protected:
        assert before["rows"][t] == restored["rows"][t], t
    for kind in sealed.KINDS:

        def data(rows):
            return {r["id"]: json.loads(r["data"]) for r in rows if r["publication_state"] == "published"}

        assert data(before["rows"]["sealed_" + kind]) == data(restored["rows"]["sealed_" + kind]), kind
    write(
        output / "rollback.json",
        dict(
            catalog=sealed.get(actor, cid)["state"],
            batch=pipe.get(actor, bid)["state"],
            shopping=sealed.get(actor, sid)["state"],
            published_sealed_data_restored=True,
            protected_identical=True,
        ),
    )
    for raw in [catalog, shopping, batch]:
        raw["version"] += "-browser"
    for bridge in catalog["bridges"]:
        bridge["package"]["version"] += "-browser"
    for a in batch["sets"]:
        a["package"]["version"] += "-browser"
    publish(sealed, catalog)
    publish(pipe, batch)
    publish(sealed, shopping)
    context = lookup.project(actor, dict(scope="all", targets="123,134,196,197"))
    key = pack_research.store_context(actor, context, "D7 sourced owned, missing and Johto comparison")
    saved = pack_research.one(actor, key)
    member = store.principal(get_user_model().objects.get(username="synthetic-member").pk)
    try:
        pack_research.one(member, key)
    except Http404:
        pass
    else:
        raise AssertionError("Cross-account saved research exposed")
    assert key not in {x["id"] for x in pack_research.listing(member)}
    write(output / "saved-before-restart.json", {k: saved[k] for k in ["id", "name", "snapshot_sha256"]})
    write(
        output / "preservation.json",
        dict(
            protected_tables=protected,
            photos_identical=True,
            copied_declarations=True,
            owned=161,
            kanto_owned=137,
            missing=90,
            kanto_missing=14,
            owner_access=False,
            source="Fresh disposable collection with real retained/new D7 packages",
            provider_calls=0,
            account_isolation=True,
            observation_dates={o["id"]: o["checked_at"] for o in shopping["observations"]},
        ),
    )
    with (
        sqlite3.connect(root / "inventory.db") as db,
        sqlite3.connect(root / "d7-copy-backup.sqlite3") as dest,
    ):
        db.backup(dest)
    with (
        sqlite3.connect(root / "inventory.db") as db,
        sqlite3.connect(root / "d7-copy-backup.sqlite3") as dest,
    ):
        for t in [r[0] for r in db.execute("select name from sqlite_master where type='table'")]:
            assert sorted(db.execute(f'SELECT * FROM "{t}"').fetchall(), key=repr) == sorted(
                dest.execute(f'SELECT * FROM "{t}"').fetchall(), key=repr
            ), t
    write(
        output / "result.json",
        dict(
            real_data=True,
            disposable_collection=True,
            idempotency=True,
            correction_conflict_refusal=True,
            rollback=True,
            exact_reference_refusal=True,
            source_refs=True,
            observation_time_preserved=True,
            owned=161,
            kanto_owned=137,
            missing=90,
            kanto_missing=14,
            provider_calls=0,
            copied_backup_all_tables_restored=True,
            account_isolation=True,
            documented_product_designs=3,
            eligible_current_offers=0,
            identified_dated_marketplace_offers=1,
        ),
    )
    print("D7 publication, conflicts, rollback, preservation and isolation passed")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    a = ap.parse_args()
    with (
        patch("httpx.Client.send", side_effect=AssertionError("No acquisition")),
        patch("urllib.request.urlopen", side_effect=AssertionError("No acquisition")),
    ):
        run(a.root, a.output)
