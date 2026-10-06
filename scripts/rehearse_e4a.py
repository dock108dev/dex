"""Fresh copied synthetic E4a migration, lifecycle examples and all-row preservation."""

import argparse
import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

from rehearse_e3a import snapshot
from rehearse_e5a import run as prepare_e5a
from rehearse_e5a import write


def principal(root):
    from pokemon_hunter.beta.cli import setup

    setup(root)
    from django.contrib.auth import get_user_model

    from pokemon_hunter.beta import store

    return store.principal(get_user_model().objects.get(username="admin").pk)


def prepare(seed, root, output):
    prepare_e5a(seed, root, output)
    who = principal(root)
    from django.db import connection

    from pokemon_hunter.beta import collection, pack_research, refresh

    goal = next(
        g
        for g in collection.goals(who)
        if g["kind"] == "original151" and g["definition"]["lineage"]["number"] == 2
    )
    key = pack_research.save(
        who, goal["id"], goal_version=goal["version"], research_name="E4a frozen before replay"
    )
    before = snapshot(root)
    refresh.initialize()
    refresh.initialize()
    after = snapshot(root)
    assert all(after["rows"][t] == rows for t, rows in before["rows"].items())
    assert before["photos"] == after["photos"]
    connection.close()
    with sqlite3.connect(root / "inventory.db") as db:
        db.execute("DROP TABLE refresh_attempts")
        db.execute("DROP TABLE refresh_runs")
    assert snapshot(root) == before
    refresh.initialize()
    write(
        output,
        "refresh-migration",
        dict(
            additive=True,
            repeatable=True,
            empty_schema_rollback_exact=True,
            existing_rows_unchanged=True,
            photo_bytes_unchanged=True,
            backend="SQLite copied synthetic; PostgreSQL execution unqualified",
        ),
    )
    write(output, "frozen-research", dict(id=key, goal=goal["id"]))
    write(output, "before", snapshot(root))


def exercise(root, output):
    who = principal(root)
    from pokemon_hunter.beta import refresh, sealed_catalog

    product = next(iter(sealed_catalog.records()["products"]))
    examples = []
    for sources in (
        ["success", "denied", "unknown", "malformed", "identity-mismatch"],
        ["timeout"],
        ["success"],
    ):
        key = refresh.start(who, product, sources, 1 if sources == ["timeout"] else 2)
        refresh.execute(who, key)
        examples.append(refresh.get(who, key))
    key = refresh.start(who, product, ["slow", "success"], 1)
    r = refresh.claim(who, key)
    refresh.reserve(who, key, r["attempts"][0]["id"])
    write(output, "interrupted-before-process-exit", refresh.get(who, key))
    write(output, "run-attempt-examples", examples)
    # Exit this process with a reserved attempt; the next process only terminalizes it.


def recover(root, output):
    who = principal(root)
    from pokemon_hunter.beta import refresh

    old = json.loads((output / "interrupted-before-process-exit.json").read_text())
    refresh.recover(who)
    row = refresh.get(who, old["id"])
    assert row["status"] == "stopped" and row["consumed"] == old["consumed"] == 1
    assert row["attempts"][0]["status"] == "interrupted"
    refresh.execute(who, row["id"])
    assert refresh.get(who, row["id"]) == row
    write(output, "restart-recovery", row)


def verify(root, output):
    who = principal(root)
    from pokemon_hunter.beta import pack_research

    key = json.loads((output / "frozen-research.json").read_text())["id"]
    pack_research.reopen(who, key)
    before = json.loads((output / "before.json").read_text())
    after = snapshot(root)
    append_only = {"sealed_sources", "sealed_observations", "sealed_imports", "catalog_audit"}
    mutable = {
        "refresh_runs",
        "refresh_attempts",
        "auth_user",
        "django_session",
        "axes_accesslog",
        "axes_accessattempt",
        "axes_accessfailurelog",
        "sqlite_sequence",
    }
    changed = {}
    for table, rows in before["rows"].items():
        new = after["rows"][table]
        if new != rows:
            changed[table] = dict(before=len(rows), after=len(new))
            if table in append_only:
                assert all(row in new for row in rows), table
            else:
                assert table in mutable, table
    assert set(after["rows"]) == set(before["rows"])
    # Authentication alone can change last_login, sessions and auth-log sequences.
    old_auth = [{k: v for k, v in row.items() if k != "last_login"} for row in before["rows"]["auth_user"]]
    new_auth = [{k: v for k, v in row.items() if k != "last_login"} for row in after["rows"]["auth_user"]]
    assert old_auth == new_auth
    old_seq = {r["name"]: r["seq"] for r in before["rows"]["sqlite_sequence"]}
    new_seq = {r["name"]: r["seq"] for r in after["rows"]["sqlite_sequence"]}
    assert {n for n in old_seq | new_seq if old_seq.get(n) != new_seq.get(n)} <= {
        "axes_accesslog",
        "axes_accessattempt",
        "axes_accessfailurelog",
    }
    assert before["photos"] == after["photos"]
    assert json.loads((output / "provider-calls.json").read_text())["calls"] == 0
    write(output, "after", after)
    write(
        output,
        "preservation",
        dict(
            all_existing_observations_retained=True,
            all_protected_rows_unchanged=True,
            saved_research_identical=True,
            photo_bytes_unchanged=True,
            changes_classified=changed,
            acquisition_calls=0,
        ),
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("prepare", "exercise", "recover", "verify"))
    p.add_argument("--seed", type=Path)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    count = {"calls": 0}

    def prohibited(*args, **kwargs):
        count["calls"] += 1
        raise AssertionError("No acquisition permitted")

    with (
        patch("httpx.Client.send", prohibited),
        patch("httpx.AsyncClient.send", prohibited),
        patch("pokemon_hunter.beta.ebay_hunts.search", prohibited),
        patch("urllib.request.urlopen", prohibited),
    ):
        if a.action == "prepare":
            prepare(a.seed, a.root, a.output)
        else:
            globals()[a.action](a.root, a.output)
    write(a.output, a.action + "-acquisition-calls", count)
