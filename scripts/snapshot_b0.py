"""Private source snapshot with consistent SQLite backup, including committed WAL pages."""

import argparse
import json
import shutil
import sqlite3
from pathlib import Path

from pokemon_hunter.migration import digest

parser = argparse.ArgumentParser()
parser.add_argument("--source", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
root, output = args.source.resolve(), args.output.resolve()
if output.is_relative_to(root):
    raise ValueError("Private backup must be outside the project")
output.mkdir(parents=True, mode=0o700, exist_ok=False)
manifest = []
for p in sorted(root.rglob("*")):
    rel = p.relative_to(root)
    if any(x in {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache"} for x in rel.parts):
        continue
    if not p.is_file() or p.name.endswith(("-wal", "-shm", "-journal")):
        continue
    q = output / "snapshot" / rel
    q.parent.mkdir(parents=True, exist_ok=True)
    if p.read_bytes()[:16] == b"SQLite format 3\x00":
        with sqlite3.connect(f"{p.as_uri()}?mode=ro", uri=True) as source, sqlite3.connect(q) as target:
            source.backup(target)
            target.execute("PRAGMA journal_mode=DELETE")
            assert target.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        kind = "sqlite-backup"
    else:
        shutil.copy2(p, q)
        assert p.read_bytes() == q.read_bytes(), "Source changed during snapshot; retry into a new directory"
        kind = "bytes"
    manifest.append(
        {"path": str(rel), "kind": kind, "sha256": digest(q.read_bytes()), "size": q.stat().st_size}
    )
(output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(f"Verified {len(manifest)} files; private manifest saved")
