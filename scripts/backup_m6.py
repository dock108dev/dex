"""Complete private SQLite backup and independent restoration, without credential output."""

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def filemap(root):
    return {
        str(p.relative_to(root)): sha(p)
        for p in root.rglob("*")
        if p.is_file()
        and p.name not in {"inventory.db", "inventory.db-wal", "inventory.db-shm", "inventory.db-journal"}
    }


def dbhashes(path):
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
        tables = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        return {
            t: hashlib.sha256(
                json.dumps(
                    sorted(db.execute(f'SELECT * FROM "{t}"').fetchall(), key=repr), default=str
                ).encode()
            ).hexdigest()
            for t in tables
        }


def backup(source, destination):
    assert not destination.exists()
    initial = filemap(source)
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns(
            "inventory.db", "inventory.db-wal", "inventory.db-shm", "inventory.db-journal"
        ),
    )
    os.chmod(destination, 0o700)
    with (
        sqlite3.connect(f"file:{source / 'inventory.db'}?mode=ro", uri=True) as db,
        sqlite3.connect(destination / "inventory.db") as dest,
    ):
        db.backup(dest)
        assert dest.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    os.chmod(destination / "inventory.db", 0o600)
    assert initial == filemap(source) == filemap(destination), "Files changed across backup"
    return dict(
        files_identical=True,
        file_count=len(initial),
        file_hashes=initial,
        database_tables=dbhashes(destination / "inventory.db"),
        consistent_sqlite_backup=True,
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--destination", type=Path, required=True)
    ap.add_argument("--restore", type=Path)
    ap.add_argument("--receipt", type=Path, required=True)
    a = ap.parse_args()
    os.umask(0o077)
    receipt = backup(a.source, a.destination)
    if a.restore:
        restored = backup(a.destination, a.restore)
        assert receipt == restored
        receipt["independent_restore_all_tables_and_files_identical"] = True
    a.receipt.write_text(json.dumps(receipt, indent=2) + "\n")
    print("Complete private backup verified", "and independently restored" if a.restore else "")
