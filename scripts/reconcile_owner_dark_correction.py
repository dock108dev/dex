"""Bounded D2c private copied-state rehearsal and explicitly authorized owner apply."""

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import uuid
from pathlib import Path

OWNER_ROOT = Path("/Users/michaelfuscoletti/dex-private/b2-parity-20260928/review-local")
OWNER_ID = "c0ab1a69-817e-50d1-b636-0acf6061357c"
SOURCE = Path(__file__).resolve().parents[1] / "outputs/my-have-dex-001-251-with-cards-corrected.csv"
SHA = "bae718f35db673213fbebc6dc21359ddb990f5878adc93a7fe9b3d580ef7a348"


def snapshot(root):
    with sqlite3.connect(root / "inventory.db") as db:
        result = {}
        for (name,) in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ):
            rows = db.execute(f'SELECT * FROM "{name}"').fetchall()
            serialized = sorted(
                json.dumps(r, default=lambda x: {"bytes": bytes(x).hex()}, sort_keys=True) for r in rows
            )
            result[name] = dict(
                count=len(rows), sha256=hashlib.sha256(json.dumps(serialized).encode()).hexdigest()
            )
        return result


def file_hashes(root):
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*")
        if p.is_file()
        and p.name not in {"inventory.db", "inventory.db-wal", "inventory.db-shm", "inventory.db-journal"}
    }


def backup(root, output):
    target = output / "restorable-root"
    shutil.copytree(root, target)
    with sqlite3.connect(root / "inventory.db") as source, sqlite3.connect(target / "inventory.db") as dest:
        source.backup(dest)
    assert snapshot(root) == snapshot(target)
    assert file_hashes(root) == file_hashes(target)
    return target


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["rehearse", "apply"], required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--rehearsal", type=Path)
    args = p.parse_args()
    os.umask(0o077)
    output = args.output.resolve()
    if output.is_relative_to(SOURCE.parents[1]) or output.exists():
        raise ValueError("Fresh private output outside repository required")
    raw = SOURCE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SHA
    output.mkdir(parents=True, mode=0o700)
    before = snapshot(OWNER_ROOT)
    protected_files = file_hashes(OWNER_ROOT)
    saved = backup(OWNER_ROOT, output)
    if args.mode == "rehearse":
        root = output / "copied-owner"
        shutil.copytree(saved, root)
    else:
        assert args.rehearsal is not None
        receipt = json.loads((args.rehearsal / "receipt.json").read_text())
        assert receipt["class"] == "copied-owner-rehearsal" and receipt["accepted"]
        assert receipt["baseline"] == before and receipt["source_sha256"] == SHA
        assert receipt["implementation"] == implementation()
        root = OWNER_ROOT
    from pokemon_hunter.beta.cli import setup

    setup(root)
    from django.db import connection

    from pokemon_hunter.beta import collection as inv
    from pokemon_hunter.beta import ownership_declarations as decl
    from pokemon_hunter.beta import store, transactions

    owners = store.rows("SELECT id,auth_subject FROM users WHERE role='owner' AND state='active'")
    assert owners == [dict(id=OWNER_ID, auth_subject="1")]
    actor = store.principal(1)
    protected_export = inv.export_data(actor)
    prior_declarations = decl.summary(actor)
    with transactions.atomic():
        with connection.cursor() as cursor:
            decl.initialize(cursor)
            decl.initialize(cursor)
        op = inv.preview(actor, "owner_declaration", dict(text=raw.decode(), sha256=SHA), str(uuid.uuid4()))
        assert not op["plan"]["errors"] and len(op["plan"]["checklist"]) == 216
        (output / "reconciliation.json").write_text(json.dumps(op["plan"], indent=2))
        applied = inv.confirm(actor, op["id"])
        assert inv.confirm(actor, op["id"]) == applied
        again = inv.preview(
            actor, "owner_declaration", dict(text=raw.decode(), sha256=SHA), str(uuid.uuid4())
        )
        assert not again["plan"]["creates"]
        inv.confirm(actor, again["id"])
        declared = decl.summary(actor)
        assert declared["species"] == 135 and declared["marked_cells"] == 192
        assert declared["gen2"]["species"] == 24 and declared["gen2"]["marked_cells"] == 24
        assert inv.export_data(actor) == protected_export
    if args.mode == "rehearse":
        inv.undo(actor, op["id"])
        assert decl.summary(actor) == prior_declarations
        assert inv.export_data(actor) == protected_export
        # Restore a fresh copy instead of resuming the now-undone source operation.
        connection.close()
        restored = output / "restored-owner"
        shutil.copytree(saved, restored)
        assert snapshot(restored) == before
        # Rehearsal acceptance includes both transaction undo and exact database restore.
    after = snapshot(root)
    allowed = {"ownership_declarations", "collection_operations", "collection_generations"}
    unchanged = [t for t in before if t not in allowed and before[t] == after[t]]
    unexpected = [t for t in before if t not in allowed and before[t] != after[t]]
    assert not unexpected
    assert file_hashes(root) == protected_files
    receipt = dict(
        accepted=True,
        **{"class": "copied-owner-rehearsal" if args.mode == "rehearse" else "actual-owner-update"},
        root=str(root),
        owner_id=actor.user_id,
        source_sha256=SHA,
        baseline=before,
        protected_files=protected_files,
        protected_file_bytes_unchanged=True,
        after=after,
        unchanged_tables=unchanged,
        unexpected_changes=unexpected,
        operation_id=op["id"],
        declared=declared,
        existing_copies=len(protected_export["copies"]),
        goal_count=len(protected_export["goals"]),
        frozen_goals_unchanged=True,
        backup=str(saved),
        implementation=implementation(),
        acquisition_calls=0,
    )
    (output / "receipt.json").write_text(json.dumps(receipt, indent=2))
    (output / "rollback.txt").write_text(
        "Stop the local app before a full restore. Preserve the current root separately. Restore restorable-root as the owner root with private permissions intact. SQLite backup and complete-root restore were qualified on copied state. For declaration-only undo without discarding later unrelated work, use collection.undo with the retained owner operation ID; later edits block destructive undo. No original copies were added, removed or edited.\n"
    )
    print(
        json.dumps(
            {k: receipt[k] for k in ["class", "accepted", "existing_copies", "goal_count", "operation_id"]}
        )
    )


def implementation():
    project = SOURCE.parents[1]
    paths = [
        "src/pokemon_hunter/beta/ownership_declarations.py",
        "src/pokemon_hunter/beta/collection.py",
        "src/pokemon_hunter/beta/collection_views.py",
        "src/pokemon_hunter/beta/static/collection.js",
        "scripts/reconcile_owner_dark_correction.py",
    ]
    return {p: hashlib.sha256((project / p).read_bytes()).hexdigest() for p in paths}


if __name__ == "__main__":
    main()
