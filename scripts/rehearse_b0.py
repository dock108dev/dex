"""Rehearse only on a verified snapshot; all output remains private and disposable."""

import argparse
import json
import sqlite3
from pathlib import Path

from pokemon_hunter.migration import compare, digest, import_snapshot, restore, snapshot_files

parser = argparse.ArgumentParser()
parser.add_argument("--snapshot", type=Path, required=True)
parser.add_argument("--manifest", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
files = snapshot_files(args.snapshot)
manifest = json.loads(args.manifest.read_text())
assert {r["path"]: r["sha256"] for r in manifest} == {p: digest(b) for p, b in files.items()}
args.output.mkdir(parents=True, mode=0o700, exist_ok=False)
target = args.output / "inventory.db"
batch = import_snapshot(args.snapshot, target)
first = compare(args.snapshot, target, batch)
with sqlite3.connect(target) as db:
    before = list(db.iterdump())
assert import_snapshot(args.snapshot, target) == batch
with sqlite3.connect(target) as db:
    assert list(db.iterdump()) == before
assert compare(args.snapshot, target, batch) == first
restored = args.output / "restored"
restore(target, batch, restored)
assert snapshot_files(restored) == files
for p in restored.rglob("*.db"):
    with sqlite3.connect(f"{p.resolve().as_uri()}?mode=ro", uri=True) as db:
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
assert snapshot_files(args.snapshot) == files
report = {
    **first,
    "batch_id": batch,
    "repeat_import": "identical logical database",
    "restore": "all archived bytes equal; SQLite integrity OK",
    "snapshot_unchanged": True,
}
(args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
