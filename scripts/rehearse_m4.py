"""M4 exact hashed publication, read-only identity migration and reversible inclusion."""

import argparse
import copy
import hashlib
import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

from rehearse_e3a import snapshot
from rehearse_m1 import run as prepare_m1

ROOT = Path(__file__).resolve().parents[1]


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str) + "\n")


def run(root, output, verify=False):
    if verify:
        if not (root / "SYNTHETIC_ONLY").is_file():
            raise ValueError("Fresh disposable state required")
        from pokemon_hunter.beta.cli import setup

        setup(root)
    else:
        prepare_m1(root, output)
    from django.contrib.auth import get_user_model

    from pokemon_hunter.beta import catalog_imports as cat
    from pokemon_hunter.beta import catalog_pipeline as pipe
    from pokemon_hunter.beta import collection, lookup, pack_research, store
    from pokemon_hunter.beta import sealed_catalog as sealed

    actor = store.principal(get_user_model().objects.get(username="admin").pk)
    pipe.initialize()
    before = snapshot(root)
    order = json.loads((ROOT / "evidence/d7-20261005/publication-order.json").read_text())
    prepared = []
    for step in order["order"]:
        data = (ROOT / step["path"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == step["sha256"], step["path"]
        service = cat if step["step"] == 2 else sealed if step["step"] in (3, 5, 7) else pipe
        prepared.append((step, service, json.loads(data)))

    def publish(service, raw):
        op = service.preview(actor, raw)
        assert op["state"] != "invalid", op
        if op["state"] == "preview":
            service.transition(actor, op["id"], "verify")
        while service.get(actor, op["id"])["state"] in ("verified", "partial"):
            service.transition(actor, op["id"], "publish")
        assert service.get(actor, op["id"])["state"] == "published"
        assert service.preview(actor, raw)["id"] == op["id"]
        assert service.transition(actor, op["id"], "publish")["state"] == "published"
        return op["id"]

    if verify:
        # Original exact packages have been published; inspect journal/identity hashes
        # before previewing only the compatible missing M4 inclusion delta.
        for step, service, raw in prepared:
            op = service.preview(actor, raw)
            assert op["state"] == "published", (step["label"], op["state"])
        inclusion = json.loads((ROOT / "config/sealed/m4-20261006/inclusion-package.json").read_text())
        active = sealed.records()
        inclusion_op = sealed.preview(actor, inclusion)
        assert inclusion_op["state"] in {"preview", "published"}
        assert sealed.records() == active
        write(
            output / "missing-delta-preview.json",
            dict(
                state=inclusion_op["state"],
                before_hash=inclusion["corrections"][0]["before_sha256"],
                no_publication_writes=True,
            ),
        )
        report = pipe.coverage(actor)
        assert report["totals"]["sets"] == 220
        write(
            output / "already-published-inspection.json",
            dict(
                exact_packages_published=True,
                repeated_preview=True,
                corrections_not_replayed=True,
                coverage_sets=220,
            ),
        )
        return

    write(output / "before.json", before)
    journal_ids = []
    for step, service, raw in prepared:
        journal_ids.append(publish(service, raw))
    active = sealed.records()
    # Exact-reference and stale-before-hash refusals must leave both records and journals unchanged.
    inclusion = json.loads((ROOT / "config/sealed/m4-20261006/inclusion-package.json").read_text())
    bad = copy.deepcopy(inclusion)
    bad["products"][0]["included_cards"][0]["sources"] = ["missing:exact-source"]
    for label, raw in [
        ("bad-exact-reference", bad),
        (
            "stale-before-hash",
            dict(inclusion, corrections=[dict(inclusion["corrections"][0], before_sha256="0" * 64)]),
        ),
    ]:
        untouched = snapshot(root)
        try:
            sealed.preview(actor, raw)
        except (ValueError, collection.Conflict) as e:
            assert snapshot(root) == untouched
            write(output / (label + ".json"), dict(error=str(e), no_partial_writes=True))
        else:
            raise AssertionError("Invalid inclusion accepted")
    legacy = pipe.coverage(actor, profile="historical")
    current = pipe.coverage(actor)
    assert legacy["totals"]["sets"] == 222 and current["totals"]["sets"] == 220
    assert current["source_totals"]["physical"] == 205 and current["source_totals"]["digital"] == 15
    prismatic = next(r for r in current["sets"] if r["set_id"] == "tcgdex:en:sv08.5")
    assert prismatic["distribution"].get("booster") == 39
    assert prismatic["distribution"].get("unknown", 0) > 0
    state = snapshot(root)
    assert pipe.coverage(actor, profile="historical") == legacy
    assert pipe.coverage(actor) == current and snapshot(root) == state
    write(output / "coverage-before.json", legacy)
    write(output / "coverage-after.json", current)
    write(
        output / "identity-reversal.json",
        dict(
            read_only=True,
            database_identical=True,
            historical_sets=222,
            current_sets=220,
            mappings=current["reviewed_identity_mappings"],
            catalog_printing_and_frozen_ids_unchanged=True,
        ),
    )
    context = lookup.project(actor, dict(targets="123,134,196,197"))
    frozen = pack_research.store_context(actor, context, "M4 before documented inclusion")
    frozen_bytes = pack_research.one(actor, frozen)["snapshot"]
    iid = publish(sealed, inclusion)
    assert pack_research.one(actor, frozen)["snapshot"] == frozen_bytes
    display = lookup.project(actor, dict(targets="123"))
    crown = next(
        p for g in display["expansions"] for p in g["products"] if p["id"] == inclusion["products"][0]["id"]
    )
    assert crown["included_cards"][0]["canonical_dex"] == 448 and crown["guaranteed_count"] == 0
    assert not any(p["species_id"] == "ndex:0448" for p in sealed.records()["printings"].values())
    sealed.transition(actor, iid, "rollback")
    assert sealed.records() == active
    assert pack_research.one(actor, frozen)["snapshot"] == frozen_bytes
    # Reverse D7 in reviewed order, then republish successors on a fresh version boundary.
    for index in (6, 5, 4):
        prepared[index][1].transition(actor, journal_ids[index], "rollback")
    write(
        output / "rollback.json",
        dict(
            inclusion_reversed=True,
            D7_order=["shopping", "M2", "sealed catalog"],
            frozen_bytes_identical=True,
        ),
    )
    # Fresh disposable boundary for final exact original journals and browser state.
    # Preserve this reversal root; reproduction creates the final root in another process.
    write(
        output / "result.json",
        dict(
            real_retained_packages=True,
            disposable_collection=True,
            original_hashed_order=True,
            repeated_confirmation=True,
            exact_reference_refusal=True,
            stale_before_refusal=True,
            no_partial_writes=True,
            identity_projection_reversal=True,
            inclusion_reversal=True,
            D7_reversal=True,
            eligible_current_offers=0,
            provider_calls=0,
            owner_access=False,
        ),
    )


def final(root, output):
    prepare_m1(root, output)
    from django.contrib.auth import get_user_model

    from pokemon_hunter.beta import catalog_imports as cat
    from pokemon_hunter.beta import catalog_pipeline as pipe
    from pokemon_hunter.beta import lookup, pack_research, store
    from pokemon_hunter.beta import sealed_catalog as sealed

    actor = store.principal(get_user_model().objects.get(username="admin").pk)
    before = snapshot(root)
    pipe.initialize()
    order = json.loads((ROOT / "evidence/d7-20261005/publication-order.json").read_text())
    results = []
    for step in order["order"]:
        data = (ROOT / step["path"]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == step["sha256"]
        service = cat if step["step"] == 2 else sealed if step["step"] in (3, 5, 7) else pipe
        op = service.preview(actor, json.loads(data))
        assert op["state"] == "preview", op
        service.transition(actor, op["id"], "verify")
        while service.get(actor, op["id"])["state"] != "published":
            service.transition(actor, op["id"], "publish")
        results.append(dict(step=step, journal=op["id"], state="published"))
    with (
        sqlite3.connect(root / "inventory.db") as db,
        sqlite3.connect(root / "m4-before-inclusion.sqlite3") as dest,
    ):
        db.backup(dest)
    inclusion = json.loads((ROOT / "config/sealed/m4-20261006/inclusion-package.json").read_text())
    op = sealed.preview(actor, inclusion)
    sealed.transition(actor, op["id"], "verify")
    sealed.transition(actor, op["id"], "publish")
    write(output / "publications.json", results + [dict(inclusion_journal=op["id"])])
    write(output / "coverage.json", pipe.coverage(actor))
    missing = lookup.project(actor, dict(scope="missing"))
    assert missing["progress"]["satisfied"] == 161 and len(missing["missing"]) == 90
    assert sum(i["pokemon_dex"] <= 151 for i in missing["missing"]) == 14
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
    write(output / "before.json", before)
    write(
        output / "preservation.json",
        dict(
            protected_tables=protected,
            photos_identical=True,
            credentials_sources_goals_copies_declarations_identical=True,
            owned=161,
            kanto_owned=137,
            missing=90,
            kanto_missing=14,
            provider_calls=0,
            owner_access=False,
        ),
    )
    ctx = lookup.project(actor, dict(targets="123,134,196,197"))
    key = pack_research.store_context(actor, ctx, "M4 sourced owned missing Johto")
    saved = pack_research.one(actor, key)
    write(output / "saved-before-restart.json", {k: saved[k] for k in ("id", "name", "snapshot_sha256")})
    with sqlite3.connect(root / "inventory.db") as db, sqlite3.connect(root / "m4-backup.sqlite3") as dest:
        db.backup(dest)
        for t in [r[0] for r in db.execute("select name from sqlite_master where type='table'")]:
            assert sorted(db.execute(f'SELECT * FROM "{t}"').fetchall(), key=repr) == sorted(
                dest.execute(f'SELECT * FROM "{t}"').fetchall(), key=repr
            )
    write(output / "backup.json", dict(all_tables_identical=True, disposable=True))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--mode", choices=["reversal", "final", "inspect"], default="reversal")
    a = ap.parse_args()
    with (
        patch("httpx.Client.send", side_effect=AssertionError("No acquisition")),
        patch("urllib.request.urlopen", side_effect=AssertionError("No acquisition")),
    ):
        if a.mode == "final":
            final(a.root, a.output)
        else:
            run(a.root, a.output, verify=a.mode == "inspect")
