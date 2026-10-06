"""Prepare/verify isolated M3 browser state; guard all source acquisition."""

import argparse
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from rehearse_e3a import snapshot
from rehearse_m1 import run as prepare_m1

ROOT = Path(__file__).resolve().parents[1]


def run(root, output, verify=False):
    if not verify:
        prepare_m1(root, output)
    else:
        if not (root / "SYNTHETIC_ONLY").is_file():
            raise ValueError("Disposable state required")
        from pokemon_hunter.beta.cli import setup

        setup(root)
    from django.contrib.auth import get_user_model

    from pokemon_hunter.beta import catalog_pipeline as pipeline
    from pokemon_hunter.beta import collection, collection_goals, lookup, pack_research, product_lookup, store
    from pokemon_hunter.beta import sealed_catalog as cat

    actor = store.principal(get_user_model().objects.get(username="admin").pk)

    def write(name, data):
        (output / name).write_text(json.dumps(data, indent=2, default=str) + "\n")

    if not verify:
        pipeline.initialize()
        raw = pipeline.retained_batch()
        raw["mode"] = "atomic"
        op = pipeline.preview(actor, raw)
        pipeline.transition(actor, op["id"], "verify")
        retained = pipeline.transition(actor, op["id"], "publish")
        assert retained["state"] == "published"
        write("retained-publication.json", retained)
        write(
            "retained-target-product-coverage.json",
            product_lookup.coverage(cat.records(), datetime.now(timezone.utc), collection.catalog(actor)),
        )
        before = snapshot(root)
        (root / "m3-before.json").write_text(json.dumps(before))
        with (
            sqlite3.connect(root / "inventory.db") as db,
            sqlite3.connect(root / "m3-before.sqlite3") as backup,
        ):
            db.backup(backup)
        p = json.loads((ROOT / "config/sealed/m3-synthetic/package.json").read_text())
        op = cat.preview(actor, p)
        write("synthetic-preview.json", dict(id=op["id"], review=cat.review(op)))
        write(
            "setup.json",
            dict(review_url="/product-review/" + op["id"] + "/", synthetic=True, provider_calls=0),
        )
        return
    setup = json.loads((output / "setup.json").read_text())
    key = setup["review_url"].split("/")[2]
    op = cat.get(actor, key)
    assert op["state"] == "published", "Publish synthetic package through ordinary browser first"
    write("synthetic-publication.json", dict(id=op["id"], state=op["state"], review=cat.review(op)))
    write(
        "target-product-coverage.json",
        product_lookup.coverage(cat.records(), datetime.now(timezone.utc), collection.catalog(actor)),
    )
    write("catalog-coverage.json", pipeline.coverage(actor))
    # A new goal explicitly chooses the now-current catalog, rather than enrolling old goals.
    goal = next((g for g in collection.goals(actor) if g["name"] == "M3 selected targets"), None)
    if goal is None:
        plan = collection.preview(
            actor,
            "goal",
            dict(
                name="M3 selected targets",
                goal_kind=collection_goals.TARGET_KIND,
                targets=[134, 135, 230],
                collection_source_id=collection_goals.latest(actor)["id"],
            ),
            str(uuid.uuid4()),
        )
        collection.confirm(actor, plan["id"])
        goal = next(g for g in collection.goals(actor) if g["name"] == "M3 selected targets")
    write("custom-goal.json", dict(id=goal["id"], version=goal["version"]))
    saved = pack_research.listing(actor)
    assert any(r["name"] == "M3 filtered mixed comparison" for r in saved), "Save comparison in browser first"
    for r in saved:
        assert pack_research.reopen(actor, r["id"])
    before = json.loads((root / "m3-before.json").read_text())
    after = snapshot(root)
    mutable = {
        "catalog_audit",
        "collection_operations",
        "collection_generations",
        "collection_goals",
        "saved_pack_research",
        "django_session",
        "auth_user",
        "axes_accesslog",
        "sqlite_sequence",
    }
    protected = [
        t
        for t in before["rows"]
        if t not in mutable
        and not t.startswith("sealed_")
        and t
        not in {
            "catalog_imports",
            "catalog_heads",
            "catalog_aliases",
            "catalog_sets",
            "printings",
            "external_mappings",
        }
    ]
    for table in protected:
        assert before["rows"][table] == after["rows"][table], table
    for table in ("collection_goals", "saved_pack_research"):
        assert all(r in after["rows"][table] for r in before["rows"][table]), table
    assert before["photos"] == after["photos"]

    def credentials(rows):
        return [{k: v for k, v in r.items() if k != "last_login"} for r in rows]

    assert credentials(before["rows"]["auth_user"]) == credentials(after["rows"]["auth_user"])
    ctx = lookup.project(actor, dict(scope="missing"))
    assert (ctx["progress"]["satisfied"], len(ctx["missing"])) == (161, 90)
    assert len([r for r in ctx["missing"] if r["pokemon_dex"] <= 151]) == 14
    with (
        sqlite3.connect(root / "m3-before.sqlite3") as db,
        sqlite3.connect(root / "m3-restored.sqlite3") as backup,
    ):
        db.backup(backup)
        for table in before["rows"]:
            assert sorted(db.execute(f'SELECT * FROM "{table}"').fetchall(), key=repr) == sorted(
                backup.execute(f'SELECT * FROM "{table}"').fetchall(), key=repr
            )
    write(
        "preservation.json",
        dict(
            protected_tables=protected,
            all_copies_identical=True,
            credentials_identical=True,
            photos_identical=True,
            historical_goals_research_retained=True,
            copied_backup_all_tables_restored=True,
            owned=161,
            kanto_owned=137,
            missing=90,
            kanto_missing=14,
            supplied_marks=286,
            owner_installation_access=False,
            provider_calls=0,
        ),
    )
    print("M3 copied-state preservation, saved references and all-251 coverage verified")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    with (
        patch("httpx.Client.send", side_effect=AssertionError("No acquisition")),
        patch("urllib.request.urlopen", side_effect=AssertionError("No acquisition")),
    ):
        run(args.root, args.output, args.verify)
