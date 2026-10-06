"""Post-browser disposable preservation, exact frozen bytes and original dates."""

import argparse
import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from rehearse_e3a import snapshot
from rehearse_m4 import ROOT, write


def run(root, output):
    from pokemon_hunter.beta.cli import setup

    setup(root)
    from django.contrib.auth import get_user_model

    from pokemon_hunter.beta import catalog_pipeline as pipe
    from pokemon_hunter.beta import collection, lookup, product_lookup, store
    from pokemon_hunter.beta import sealed_catalog as sealed

    actor = store.principal(get_user_model().objects.get(username="admin").pk)
    before = json.loads((output.parent / "final1/before.json").read_text())
    after = snapshot(root)
    protected = json.loads((output.parent / "final1/preservation.json").read_text())["protected_tables"]
    append_only = {"collection_goals", "saved_pack_research", "collection_operations"}
    incidental = {"auth_user", "django_session", "axes_accesslog"}
    for t in protected:
        if t in append_only:
            assert all(r in after["rows"][t] for r in before["rows"][t]), t
        elif t not in incidental:
            assert before["rows"][t] == after["rows"][t], t

    def auth(rows):
        return [{k: v for k, v in r.items() if k != "last_login"} for r in rows]

    assert auth(before["rows"]["auth_user"]) == auth(after["rows"]["auth_user"])
    assert before["photos"] == after["photos"]
    records = sealed.records()
    observations = json.loads((ROOT / "config/sealed/d7-20261005/shopping-package.json").read_text())[
        "observations"
    ]
    for obs in observations:
        assert records["observations"][obs["id"]] == obs
    assert (
        records["observations"]["target:91619942:d6:20261006T031602"]["checked_at"]
        == "2026-10-06T03:16:02.472952+00:00"
    )
    saved = []
    with (
        sqlite3.connect(root / "inventory.db") as db,
        sqlite3.connect(root / "browser-before-restart.sqlite3") as prior,
    ):
        for key, raw in prior.execute("select id,snapshot from saved_pack_research"):
            actual = db.execute("select snapshot from saved_pack_research where id=?", [key]).fetchone()[0]
            assert actual.encode() == raw.encode()
            saved.append(dict(id=key, sha256=hashlib.sha256(raw.encode()).hexdigest(), bytes_identical=True))
        with sqlite3.connect(root / "m4-browser-restored.sqlite3") as restored:
            db.backup(restored)
            for t in [r[0] for r in db.execute("select name from sqlite_master where type='table'")]:
                assert sorted(db.execute(f'SELECT * FROM "{t}"').fetchall(), key=repr) == sorted(
                    restored.execute(f'SELECT * FROM "{t}"').fetchall(), key=repr
                ), t
    context = lookup.project(actor, dict(scope="missing"))
    assert context["progress"]["satisfied"] == 161 and len(context["missing"]) == 90
    assert sum(r["pokemon_dex"] <= 151 for r in context["missing"]) == 14
    report = pipe.coverage(actor)
    assert report["totals"]["sets"] == 220
    write(output / "current-coverage.json", report)
    chains = product_lookup.coverage(records, datetime.now(UTC), collection.catalog(actor))
    assert not any(o["eligibility"]["recommendation_eligible"] for r in chains for o in r["offers"])
    write(output / "target-product-coverage.json", chains)
    calls = json.loads((output / "provider-calls.json").read_text())
    assert calls["calls"] == 0 and calls["server_starts"] == 2
    write(
        output / "preservation.json",
        dict(
            protected_tables=protected,
            photos_identical=True,
            credentials_identical=True,
            original_goals_declarations_sources_copies_retained=True,
            saved_snapshots=saved,
            original_observations_identical=True,
            copied_backup_all_tables_identical=True,
            owned=161,
            kanto_owned=137,
            missing=90,
            kanto_missing=14,
            provider_calls=0,
            server_starts=2,
            owner_access=False,
            evidence_class="localhost disposable SQLite; real retained D6/D7 sources; synthetic collection and accounts",
        ),
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args()
    run(a.root, a.output)
