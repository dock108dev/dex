"""E5a fresh synthetic migration/rollback rehearsal and complete row preservation."""

import argparse
import json
import sqlite3
from pathlib import Path

from rehearse_e3a import prepare, snapshot


def write(output, name, value):
    (output / (name + ".json")).write_text(json.dumps(value, indent=2, default=str) + "\n")


def run(seed, root, output):
    prepare(seed, root, output)
    from django.contrib.auth import get_user_model
    from django.db import connection

    from pokemon_hunter.beta import pack_research as research
    from pokemon_hunter.beta import sealed_catalog as cat
    from pokemon_hunter.beta import store

    actor = store.principal(get_user_model().objects.get(username="admin").pk)
    for path in (
        "config/sealed/2026-10-04-d3-d4a/package.json",
        "config/sealed/2026-10-04-d5a/review-annotation.json",
        "config/sealed/2026-10-04-d5b/package.json",
    ):
        op = cat.preview(actor, json.loads(Path(path).read_text()))
        cat.transition(actor, op["id"], "verify")
        cat.transition(actor, op["id"], "publish")
        write(output, Path(path).parent.name + "-publication", cat.review(cat.get(actor, op["id"])))
    before = snapshot(root)
    research.initialize()
    research.initialize()
    after = snapshot(root)
    assert all(after["rows"][t] == rows for t, rows in before["rows"].items())
    assert after["rows"]["saved_pack_research"] == [] and before["photos"] == after["photos"]
    # Roll back schema on disposable empty table, then migrate from the fresh boundary.
    connection.close()
    with sqlite3.connect(root / "inventory.db") as db:
        db.execute("DROP TABLE saved_pack_research")
    assert snapshot(root) == before
    research.initialize()
    write(
        output,
        "migration",
        dict(
            additive=True,
            repeatable=True,
            empty_schema_rollback_exact=True,
            existing_rows_unchanged=True,
            photo_bytes_unchanged=True,
            backend="SQLite disposable synthetic; PostgreSQL DDL supported, not rehearsed",
        ),
    )
    write(output, "before", snapshot(root))


def verify(root, output):
    before = json.loads((output / "before.json").read_text())
    after = snapshot(root)
    allowed = {
        "saved_pack_research",
        "auth_user",
        "django_session",
        "axes_accessattempt",
        "axes_accesslog",
        "axes_accessfailurelog",
    }
    changed = {
        t: dict(before=len(rows), after=len(after["rows"].get(t, [])))
        for t, rows in before["rows"].items()
        if rows != after["rows"].get(t)
    }
    # SQLite AUTOINCREMENT bookkeeping may move only for observed auth log inserts.
    old_sequences = {r["name"]: r["seq"] for r in before["rows"].get("sqlite_sequence", [])}
    new_sequences = {r["name"]: r["seq"] for r in after["rows"].get("sqlite_sequence", [])}
    moved_sequences = {
        key for key in old_sequences | new_sequences if old_sequences.get(key) != new_sequences.get(key)
    }
    assert moved_sequences <= {"axes_accesslog", "axes_accessattempt", "axes_accessfailurelog"}, (
        moved_sequences
    )
    if "sqlite_sequence" in changed:
        changed["sqlite_sequence"]["only_auth_log_counters"] = sorted(moved_sequences)
    assert set(changed) <= allowed | {"sqlite_sequence"}, changed
    assert before["photos"] == after["photos"]
    calls = json.loads((output / "provider-calls.json").read_text())
    assert calls["calls"] == 0
    write(output, "after", after)
    write(
        output,
        "preservation",
        dict(
            all_other_tables_unchanged=True,
            unchanged_tables=sorted(set(before["rows"]) - set(changed)),
            changes_classified=changed,
            intentional_research_rows="saved_pack_research",
            login_bookkeeping=sorted(allowed - {"saved_pack_research"}),
            photo_bytes_unchanged=True,
            acquisition_calls=0,
        ),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    verify(args.root, args.output) if args.verify else run(args.seed, args.root, args.output)
