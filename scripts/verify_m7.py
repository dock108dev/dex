"""Strict all-table/file preservation and one actual-browser frozen save."""

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path

from backup_m6 import backup, filemap


def rows(db, table):
    return sorted([dict(r) for r in db.execute(f'SELECT * FROM "{table}"')], key=repr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--baseline", type=Path, required=True)
    ap.add_argument("--private", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--phase", choices=["installed", "before-restart", "after-restart"], required=True)
    a = ap.parse_args()
    with (
        sqlite3.connect(f"file:{a.root / 'inventory.db'}?mode=ro", uri=True) as db,
        sqlite3.connect(f"file:{a.baseline / 'inventory.db'}?mode=ro", uri=True) as old,
    ):
        db.row_factory = old.row_factory = sqlite3.Row
        tables = sorted(r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'"))
        assert tables == sorted(
            r[0] for r in old.execute("SELECT name FROM sqlite_master WHERE type='table'")
        )
        assert filemap(a.root) == filemap(a.baseline), "Protected file bytes changed"
        for t in tables:
            current, previous = rows(db, t), rows(old, t)
            if t == "saved_pack_research" and a.phase != "installed":
                assert all(r in current for r in previous), "Prior save changed"
                fresh = [r for r in current if r["id"] not in {v["id"] for v in previous}]
                assert len(fresh) == 1, "Expected exactly one new actual-browser M7 save"
                saved = fresh[0]
                assert hashlib.sha256(saved["snapshot"].encode()).hexdigest() == saved["snapshot_sha256"]
            else:
                assert current == previous, f"Protected table changed: {t}"
    metadata = None
    if a.phase != "installed":
        metadata = {k: saved[k] for k in ("id", "name", "created_at", "snapshot_sha256")}
        if a.phase == "before-restart":
            receipt = backup(a.root, a.private / "browser-before-restart-root")
            restored = backup(
                a.private / "browser-before-restart-root", a.private / "browser-before-restart-restored"
            )
            assert receipt == restored
            (a.private / "browser-before-restart-receipt.json").write_text(json.dumps(receipt, indent=2))
            (a.private / "browser-saved-before-restart.json").write_text(json.dumps(metadata, indent=2))
        else:
            assert metadata == json.loads((a.private / "browser-saved-before-restart.json").read_text())
            with (
                sqlite3.connect(f"file:{a.root / 'inventory.db'}?mode=ro", uri=True) as db,
                sqlite3.connect(
                    f"file:{a.private / 'browser-before-restart-root/inventory.db'}?mode=ro", uri=True
                ) as copy,
            ):
                db.row_factory = copy.row_factory = sqlite3.Row
                for t in tables:
                    assert rows(db, t) == rows(copy, t), f"Row changed after restart: {t}"
            assert filemap(a.root) == filemap(a.private / "browser-before-restart-root")
    a.output.write_text(
        json.dumps(
            dict(
                phase=a.phase,
                table_count=len(tables),
                all_original_rows_and_files_identical=True,
                authentication_and_sessions_exact=True,
                old_frozen_saves_identical=True,
                new_browser_saved=metadata,
                all_rows_identical_after_restart=a.phase == "after-restart",
            ),
            indent=2,
        )
        + "\n"
    )
    print("Strict preservation verified:", a.phase)


if __name__ == "__main__":
    main()
