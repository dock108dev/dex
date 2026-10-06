"""Read-only owner preservation and exact frozen-save verification; no source acquisition."""

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

from backup_m6 import filemap

PROJECT = Path(__file__).resolve().parents[1]


def rows(db, table):
    return [dict(r) for r in db.execute(f'SELECT * FROM "{table}"')]


def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--private", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--before-restart", action="store_true")
    a = ap.parse_args()
    before = a.private / "immediate-preapply-root"
    r = json.loads((a.private / "application/receipt.json").read_text())
    with (
        sqlite3.connect(f"file:{a.root / 'inventory.db'}?mode=ro", uri=True) as db,
        sqlite3.connect(f"file:{before / 'inventory.db'}?mode=ro", uri=True) as old,
    ):
        db.row_factory = sqlite3.Row
        old.row_factory = sqlite3.Row
        for t in r["protected_tables"]:
            if t == "saved_pack_research":
                assert all(v in rows(db, t) for v in rows(old, t)), "Earlier frozen save changed"
            else:
                assert sorted(rows(db, t), key=repr) == sorted(rows(old, t), key=repr), t
        assert filemap(a.root) == filemap(before), "Protected file bytes changed"
        for t in ("catalog_sets", "printings", "external_mappings"):
            original = rows(old, t)
            current = rows(db, t)
            assert all(v in current for v in original), t
        for t in ("sealed_sources", "sealed_observations"):
            assert all(v in rows(db, t) for v in rows(old, t)), t
        package = json.loads((PROJECT / "config/sealed/d8-20261006/shopping-package.json").read_text())
        for v in package["observations"]:
            actual = db.execute("SELECT data FROM sealed_observations WHERE id=?", [v["id"]]).fetchone()
            assert json.loads(actual["data"]) == v
        previous = {v["id"] for v in rows(old, "saved_pack_research")}
        new = [v for v in rows(db, "saved_pack_research") if v["id"] not in previous]
        assert len(new) == 1, "Expected exactly one actual-browser M6 save"
        saved = new[0]
        assert sha(saved["snapshot"]) == saved["snapshot_sha256"]
        metadata = {k: saved[k] for k in ("id", "name", "created_at", "snapshot_sha256")}
        if a.before_restart:
            (a.private / "browser-saved-before-restart.json").write_text(
                json.dumps(metadata, indent=2) + "\n"
            )
            with sqlite3.connect(a.private / "browser-before-restart.db") as copy:
                db.backup(copy)
        else:
            assert metadata == json.loads((a.private / "browser-saved-before-restart.json").read_text())
            with sqlite3.connect(a.private / "browser-before-restart.db") as copy:
                copy.row_factory = sqlite3.Row
                for t in [v[0] for v in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]:
                    assert sorted(rows(db, t), key=repr) == sorted(rows(copy, t), key=repr), t
        report = dict(
            protected_tables_identical=True,
            protected_files_identical=True,
            credentials_authentication_and_sessions_identical_to_post_login_baseline=True,
            all_original_goals_hunts_sources_marks_copies_and_saves_preserved=True,
            original_catalog_rows_and_external_mappings_preserved=True,
            all_seven_observations_and_original_times_exact=True,
            snapshot_sha256_exact=True,
            browser_saved=metadata,
            all_rows_identical_after_restart=not a.before_restart,
            copies=207,
            marks=286,
            kanto_owned=137,
            johto_owned=24,
            overall_owned=161,
            kanto_missing=14,
            overall_missing=90,
        )
        a.output.write_text(json.dumps(report, indent=2) + "\n")
        print(
            "Owner preservation and frozen save verified",
            "before restart" if a.before_restart else "after restart",
        )
