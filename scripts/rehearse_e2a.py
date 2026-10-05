"""Offline E2a review/copy preservation rehearsal; synthetic roots only, no owner input."""

import argparse
import json
import shutil
import sqlite3
import uuid
from pathlib import Path
from unittest.mock import patch

from pokemon_hunter.migration import digest, encode


def run(seed, root, output):
    if not (seed / "SYNTHETIC_ONLY").is_file() or root.exists() or output.exists():
        raise ValueError("Require synthetic seed and fresh root/evidence paths")
    shutil.copytree(seed, root)
    output.mkdir(mode=0o700, parents=True)
    from pokemon_hunter.beta.cli import setup

    setup(root)
    from django.contrib.auth import get_user_model
    from django.db import connection

    from pokemon_hunter.beta import catalog_imports as legacy
    from pokemon_hunter.beta import collection as inv
    from pokemon_hunter.beta import parity, store
    from pokemon_hunter.beta import sealed_catalog as cat

    actor = store.principal(get_user_model().objects.get(username="admin").pk)
    other = store.principal(get_user_model().objects.get(username="synthetic-member").pk)
    project = Path(__file__).resolve().parents[1]
    evidence = root / "parity-evidence"
    for name in ("hunt.json", "demo_hunts.json", "raw_values.json"):
        (evidence / name).write_bytes((project / "config" / name).read_bytes())

    def rows():
        return {t: store.rows(f"SELECT * FROM {t}") for t in connection.introspection.table_names()}

    def apply(who, kind, request):
        op = inv.preview(who, kind, request, str(uuid.uuid4()))
        return inv.confirm(who, op["id"])

    # An older saved hunt is part of the preservation boundary before publication.
    vintage = next(g for g in inv.goals(actor) if g["kind"] == "vintage")
    with patch("pokemon_hunter.beta.ebay_hunts.search", side_effect=AssertionError("No acquisition")):
        old_hunt = parity.search(actor, dict(demo=True, goal_id=vintage["id"], intent="missing"))
    before = rows()
    with sqlite3.connect(root / "inventory.db") as source, sqlite3.connect(output / "before.sqlite3") as dest:
        source.backup(dest)
    cat.initialize()
    cat.initialize()
    with sqlite3.connect(root / "inventory.db") as db:
        legacy.initialize(db)
        legacy.initialize(db)
    assert rows() == {**before, **{t: [] for t in rows() if t not in before}}
    packages = []
    for name in ("2026-10-04", "2026-10-04-151"):
        path = project / "config/sealed" / name / "package.json"
        p = json.loads(path.read_text())
        op = cat.preview(actor, p)
        cat.transition(actor, op["id"], "verify")
        cat.transition(actor, op["id"], "publish")
        packages.append(
            dict(
                path=str(path.relative_to(project)),
                sha256=digest(path.read_bytes()),
                service_fingerprint=op["package_hash"],
            )
        )
    public = rows()
    for t, records in before.items():
        assert all(r in public[t] for r in records), t
    op = apply(actor, "goal", dict(name="Rehearsal Original 151", goal_kind="original151"))
    first_id = op["changes"][0]["after"]["id"]
    first = inv.one(actor, "goal", first_id)
    with patch("pokemon_hunter.beta.ebay_hunts.search", side_effect=AssertionError("No acquisition")):
        hunt = parity.search(actor, dict(demo=True, goal_id=first_id, intent="missing"))
        reopened = parity.hunt_response(
            actor, store.resource(actor, "hunts", (hunt["batch"], 1)), hunt["batch"], 1
        )
        assert reopened["goal"]["version"] == first["version"]
    update = dict(name=first["name"], goal_kind="original151", id=first_id, revision=0)
    cancelled = inv.preview(actor, "goal_edit", update, str(uuid.uuid4()))
    assert inv.one(actor, "goal", first_id) == first
    assert len(inv.goals(actor)) == len(before["collection_goals"]) // 2 + 1
    new = apply(actor, "goal_edit", update)
    inv.confirm(actor, new["id"])
    assert inv.one(actor, "goal", first_id) == first
    exported = inv.export_data(actor)
    apply(other, "import", dict(text=json.dumps(exported), format="json", duplicate_policy="allow"))
    new_goals = [g for g in inv.goals(other) if g["kind"] == "original151"]
    assert len(new_goals) == 2
    assert {g["definition"]["lineage"]["number"] for g in new_goals} == {1, 2}
    with patch("pokemon_hunter.beta.ebay_hunts.search", side_effect=AssertionError("No acquisition")):
        replay = parity.hunt_response(
            actor, store.resource(actor, "hunts", (hunt["batch"], 1)), hunt["batch"], 1
        )
        old_replay = parity.hunt_response(
            actor, store.resource(actor, "hunts", (old_hunt["batch"], 1)), old_hunt["batch"], 1
        )
    assert replay["goal"] == reopened["goal"]
    assert old_replay["goal"] == old_hunt["goal"]
    after = rows()
    protected = (
        "owned_copies",
        "collection_goals",
        "saved_hunts",
        "scan_jobs",
        "scan_photos",
        "users",
        "binders",
    )
    for t in protected:
        assert all(r in after[t] for r in before[t]), t
    # Imported copies are explicitly synthetic and belong to the second account only.
    assert [r for r in after["owned_copies"] if r["user_id"] == actor.user_id] == [
        r for r in before["owned_copies"] if r["user_id"] == actor.user_id
    ]
    connection.close()
    with sqlite3.connect(root / "inventory.db") as source, sqlite3.connect(output / "after.sqlite3") as dest:
        source.backup(dest)
    normalized_before = json.loads(json.dumps(before, default=str))
    result = dict(
        evidence_class="offline synthetic SQLite copied state; no owner acceptance",
        baseline_table_hashes={
            t: digest(encode(sorted(r, key=encode)).encode()) for t, r in normalized_before.items()
        },
        protected_tables=protected,
        preexisting_rows_preserved=True,
        migration_repeat_preserved=True,
        no_e2a_schema_change=True,
        version_reopen=True,
        cancelled_preview_no_goal_writes=True,
        confirmation_idempotent=True,
        export_import_lineage_remapped=True,
        old_and_new_hunt_scope_preserved=True,
        provider_calls=0,
        package_hashes=packages,
        first_version=first["version"],
        cancelled_operation=cancelled["id"],
        successor_version=new["changes"][0]["after"]["version"],
    )
    (output / "preservation.json").write_text(json.dumps(result, indent=2) + "\n")
    (output / "first-goal.json").write_text(
        json.dumps(next(g for g in exported["goals"] if g["id"] == first_id), indent=2) + "\n"
    )
    print(json.dumps({k: v for k, v in result.items() if k != "baseline_table_hashes"}, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seed", type=Path, required=True)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    run(args.seed.resolve(), args.root.resolve(), args.output.resolve())
