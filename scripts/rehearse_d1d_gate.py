"""Fresh synthetic full-set bridge rejection; stop before verify or publication."""

import hashlib
import json
import sqlite3
import uuid
from pathlib import Path

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/d1d-20261005/synthetic-gate"
STATE = Path("/Users/michaelfuscoletti/dex-private/d1d-20261005/synthetic-gate")


def run():
    if OUT.exists() or STATE.exists():
        raise ValueError("Use a fresh disposable boundary")
    OUT.mkdir(parents=True)
    from pokemon_hunter.beta import synthetic

    synthetic.prepare(STATE)
    from django.contrib.auth import get_user_model
    from django.db import connection

    from pokemon_hunter.beta import collection as inv
    from pokemon_hunter.beta import sealed_catalog as cat
    from pokemon_hunter.beta import store

    cat.initialize()
    actor = store.principal(get_user_model().objects.get(username="admin").pk)
    op = inv.preview(
        actor,
        "goal",
        dict(name="D1d frozen synthetic Original 151", goal_kind="original151"),
        str(uuid.uuid4()),
    )
    inv.confirm(actor, op["id"])

    def snapshot():
        rows = {
            t: sorted(
                store.rows(f"SELECT * FROM {t}"), key=lambda r: json.dumps(r, sort_keys=True, default=str)
            )
            for t in connection.introspection.table_names()
        }
        return dict(
            rows=rows,
            photos={
                str(p.relative_to(STATE)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(STATE.rglob("*.png"))
            },
        )

    before = snapshot()
    with sqlite3.connect(STATE / "inventory.db") as db, sqlite3.connect(STATE / "before.sqlite3") as dest:
        db.backup(dest)
    rejected = json.loads((ROOT / "evidence/d1d-20261005/rejected-bridge-input.json").read_text())
    try:
        cat.preview(actor, rejected)
    except ValidationError as exc:
        errors = exc.errors(include_url=False)
    else:
        raise AssertionError("Unexpected gate success; stop and review")
    assert len(errors) == 4
    assert snapshot() == before
    # Byte-independent logical restoration of disposable baseline, never owner data.
    connection.close()
    with (
        sqlite3.connect(STATE / "before.sqlite3") as old,
        sqlite3.connect(STATE / "restored.sqlite3") as dest,
    ):
        old.backup(dest)
        assert dest.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    connection.settings_dict["NAME"] = STATE / "restored.sqlite3"
    assert snapshot() == before
    connection.close()
    connection.settings_dict["NAME"] = STATE / "inventory.db"
    result = dict(
        evidence_class="Fresh synthetic SQLite gate rejection; no D1d publication",
        root=str(STATE),
        errors=errors,
        all_tables_unchanged=True,
        photo_bytes_unchanged=True,
        frozen_goals_unchanged=True,
        restored_baseline_exact=True,
        d1d_preview_rejected=True,
        d1d_verify=False,
        d1d_publish=False,
        d1d_publication_rollback="not-executed-gate-blocked",
        d1d_idempotency="not-executed-gate-blocked",
        d1d_successor_preview="not-executed-gate-blocked",
        d1d_identity_conflict="not-executed-gate-blocked",
        provider_calls=0,
        baseline_table_counts={t: len(r) for t, r in before["rows"].items()},
        baseline_table_hashes={
            t: hashlib.sha256(json.dumps(r, sort_keys=True, default=str).encode()).hexdigest()
            for t, r in before["rows"].items()
        },
    )
    (OUT / "preservation.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        "Full 18-card preview rejected for four >251 mappings; all tables/photos/frozen goals unchanged; copied restoration exact"
    )


if __name__ == "__main__":
    run()
