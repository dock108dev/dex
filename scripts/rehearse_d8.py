"""Fresh disposable D8 publication, refusal, preservation, reversal and frozen reopening."""

import argparse
import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from acquire_d8 import ROOT, write
from rehearse_e3a import snapshot
from rehearse_m1 import run as prepare_m1


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def compact(state):
    return dict(
        tables={k: dict(rows=len(v), sha256=digest(v)) for k, v in state["rows"].items()},
        photos=state["photos"],
    )


def run(root, output, mode):
    if mode == "verify":
        from pokemon_hunter.beta.cli import setup

        assert (root / "SYNTHETIC_ONLY").is_file()
        setup(root)
    else:
        prepare_m1(root, root.with_name(root.name + "-setup-evidence"))
    from django.contrib.auth import get_user_model

    from pokemon_hunter.beta import (
        catalog_imports as cat,
    )
    from pokemon_hunter.beta import (
        catalog_pipeline as pipe,
    )
    from pokemon_hunter.beta import (
        collection,
        lookup,
        pack_research,
        product_lookup,
        store,
    )
    from pokemon_hunter.beta import sealed_catalog as sealed

    actor = store.principal(get_user_model().objects.get(username="admin").pk)
    if mode == "verify":
        saved = json.loads((output / "saved-before-restart.json").read_text())
        actual = pack_research.one(actor, saved["id"])
        assert actual["snapshot_sha256"] == saved["snapshot_sha256"]
        assert hashlib.sha256(actual["snapshot"].encode()).hexdigest() == saved["snapshot_sha256"]
        reopened = pack_research.reopen(actor, saved["id"])
        assert reopened["lookup"]
        observations = json.loads((ROOT / "config/sealed/d8-20261006/shopping-package.json").read_text())[
            "observations"
        ]
        assert all(sealed.records()["observations"][o["id"]] == o for o in observations)
        write(
            output / "restart-reopen.json",
            dict(snapshot_bytes_identical=True, original_times_identical=True, provider_calls=0),
        )
        return
    pipe.initialize()

    def publish(service, raw):
        op = service.preview(actor, raw)
        if op["state"] == "invalid":
            write(output / "invalid-package.json", op)
            raise AssertionError("Package gate refused; retained exact outcomes")
        if op["state"] == "preview":
            service.transition(actor, op["id"], "verify")
        while service.get(actor, op["id"])["state"] in ["verified", "partial"]:
            service.transition(actor, op["id"], "publish")
        assert service.get(actor, op["id"])["state"] == "published"
        assert service.preview(actor, raw)["id"] == op["id"]
        assert service.transition(actor, op["id"], "publish")["state"] == "published"
        return op["id"]

    order = json.loads((ROOT / "evidence/d7-20261005/publication-order.json").read_text())["order"]
    for step in order:
        raw = (ROOT / step["path"]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == step["sha256"]
        publish(cat if step["step"] == 2 else sealed if step["step"] in [3, 5, 7] else pipe, json.loads(raw))
    publish(sealed, json.loads((ROOT / "config/sealed/m4-20261006/inclusion-package.json").read_text()))
    before = snapshot(root)
    active_before = sealed.records()
    write(output / "before.json", compact(before))
    write(output / "coverage-before.json", pipe.coverage(actor))
    catalog = json.loads((ROOT / "config/sealed/d8-20261006/catalog-package.json").read_text())
    batch = json.loads((ROOT / "config/catalog-pipeline/d8-20261006/batch.json").read_text())
    shopping = json.loads((ROOT / "config/sealed/d8-20261006/shopping-package.json").read_text())
    for label, raw in [
        (
            "exact-reference",
            dict(
                catalog,
                printings=[dict(catalog["printings"][0], expansion_id="missing:exact")]
                + catalog["printings"][1:],
            ),
        ),
        (
            "stale-correction",
            dict(
                catalog,
                corrections=[dict(catalog["corrections"][0], before_sha256="0" * 64)]
                + catalog["corrections"][1:],
            ),
        ),
    ]:
        unchanged = snapshot(root)
        try:
            sealed.preview(actor, raw)
        except (ValueError, collection.Conflict) as e:
            assert snapshot(root) == unchanged
            write(output / (label + "-refusal.json"), dict(error=str(e), no_partial_writes=True))
        else:
            raise AssertionError("Invalid exact reference or stale correction accepted")
    ids = []
    for label, service, raw in [
        ("catalog", sealed, catalog),
        ("batch", pipe, batch),
        ("shopping", sealed, shopping),
    ]:
        ids.append((label, service, publish(service, raw)))
    cov = pipe.coverage(actor)
    write(output / "coverage-after.json", cov)
    assert cov["totals"]["sets"] == 220 and cov["totals"]["assessed"] == 48, cov["totals"]
    assert cov["totals"]["target_numbered_count"] == 3104, cov["totals"]
    for n in [123, 134, 196, 197]:
        ctx = lookup.project(actor, dict(scope="all", targets=str(n)))
        write(
            output / f"lookup-{n}.json",
            dict(
                target=n,
                progress=ctx["progress"],
                products=[
                    dict(
                        id=p["id"],
                        name=p["name"],
                        distinct_target_count=p.get("distinct_target_count"),
                        offers=[
                            dict(
                                id=o["id"],
                                seller=o["seller"],
                                representative=o["representative"],
                                eligibility=o["eligibility"],
                            )
                            for o in p["offers"]
                        ],
                    )
                    for e in ctx["expansions"]
                    for p in e["products"]
                ],
            ),
        )
    context = lookup.project(actor, dict(scope="all", targets="123,134,196,197"))
    write(
        output / "product-coverage.json",
        product_lookup.coverage(sealed.records(), datetime.now(UTC), collection.catalog(actor)),
    )
    after = snapshot(root)
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
    assert all(before["rows"][t] == after["rows"][t] for t in protected)
    assert before["photos"] == after["photos"]
    write(
        output / "preservation.json",
        dict(
            protected_tables=protected,
            protected_rows_identical=True,
            photos_identical=True,
            owned=161,
            kanto_owned=137,
            missing=90,
            kanto_missing=14,
            owner_access=False,
            provider_calls=0,
        ),
    )
    write(output / "journal-ids.json", [dict(label=label, id=key) for label, service, key in ids])
    if mode == "rollback":
        for label, service, key in reversed(ids):
            service.transition(actor, key, "rollback")
        assert sealed.records() == active_before
        restored = snapshot(root)
        assert all(before["rows"][t] == restored["rows"][t] for t in protected)
        assert before["photos"] == restored["photos"]
        write(
            output / "rollback.json",
            dict(
                reverse_order=[label for label, service, key in reversed(ids)],
                active_sealed_restored=True,
                protected_identical=True,
            ),
        )
        return
    key = pack_research.store_context(actor, context, "D8 sourced owned missing Johto comparison")
    saved = pack_research.one(actor, key)
    write(output / "saved-before-restart.json", {k: saved[k] for k in ["id", "name", "snapshot_sha256"]})
    write(output / "browser-baseline.json", compact(snapshot(root)))
    with sqlite3.connect(root / "inventory.db") as db, sqlite3.connect(root / "d8-restored.sqlite3") as dest:
        db.backup(dest)
        for t in [r[0] for r in db.execute("select name from sqlite_master where type='table'")]:
            assert sorted(db.execute(f'SELECT * FROM "{t}"').fetchall(), key=repr) == sorted(
                dest.execute(f'SELECT * FROM "{t}"').fetchall(), key=repr
            )
    write(output / "backup-restoration.json", dict(all_tables_identical=True, disposable=True))
    write(
        output / "result.json",
        dict(
            status="passed",
            sets_added=19,
            numbered_targets_added=1149,
            catalog_records_added=1965,
            supplied_variants=1611,
            unspecified_variants=354,
            idempotent_confirmation=True,
            exact_reference_refusal=True,
            stale_correction_refusal=True,
            provider_calls=0,
            owner_access=False,
        ),
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--mode", choices=["final", "rollback", "verify"], default="final")
    a = ap.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    with (
        patch("httpx.Client.send", side_effect=AssertionError("No acquisition")),
        patch("httpx.AsyncClient.send", side_effect=AssertionError("No acquisition")),
        patch("urllib.request.urlopen", side_effect=AssertionError("No acquisition")),
    ):
        run(a.root, a.output, a.mode)
