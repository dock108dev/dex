"""Fresh E2d synthetic browser state and preservation verification. No owner writes."""

import argparse
import hashlib
import json
import sqlite3
import uuid
from pathlib import Path
from unittest.mock import patch

from rehearse_e3a import snapshot

PROJECT = Path(__file__).resolve().parents[1]


def run(root, output, verify=False):
    from pokemon_hunter.beta import cli

    if verify:
        if not (root / "SYNTHETIC_ONLY").is_file():
            raise ValueError("Synthetic state required")
        cli.setup(root)
    else:
        if root.exists() or output.exists():
            raise ValueError("Fresh root and evidence paths required")
        from pokemon_hunter.beta import synthetic

        synthetic.prepare(root)
        output.mkdir(parents=True)
    from django.contrib.auth import get_user_model
    from django.db import connection

    from pokemon_hunter.beta import collection as inv
    from pokemon_hunter.beta import collection_goals, ownership_declarations, pack_research, store
    from pokemon_hunter.beta import sealed_catalog as cat
    from pokemon_hunter.inventory import connect
    from pokemon_hunter.migration import digest

    actor = store.principal(get_user_model().objects.get(username="admin").pk)
    if not verify:
        with connect(root / "inventory.db") as db:
            ownership_declarations.initialize(db)
            ownership_declarations.initialize(db)
        cat.initialize()
        pack_research.initialize()
        for name in ("2026-10-04", "2026-10-04-151"):
            package = json.loads((PROJECT / "config/sealed" / name / "package.json").read_text())
            op = cat.preview(actor, package)
            cat.transition(actor, op["id"], "verify")
            cat.transition(actor, op["id"], "publish")
        raw = (PROJECT / "outputs/my-have-dex-001-251-photo-reconciled.csv").read_bytes()
        op = inv.preview(
            actor, "owner_declaration", dict(text=raw.decode(), sha256=digest(raw)), str(uuid.uuid4())
        )
        inv.confirm(actor, op["id"])
        # Existing reviewed-copy goal remains distinct during the walkthrough.
        op = inv.preview(
            actor,
            "goal",
            dict(name="Synthetic reviewed-copy predecessor", goal_kind="original151"),
            str(uuid.uuid4()),
        )
        inv.confirm(actor, op["id"])
        (root / "e2d-before.json").write_text(json.dumps(snapshot(root), default=str))
        with (
            sqlite3.connect(root / "inventory.db") as source,
            sqlite3.connect(root / "e2d-before.sqlite3") as dest,
        ):
            source.backup(dest)
        report = dict(
            synthetic=True,
            csv_sha256=digest(raw),
            source=collection_goals.reference(collection_goals.sources(actor)[0]),
            acquisition_calls=0,
        )
    else:
        before = json.loads((root / "e2d-before.json").read_text())
        after = snapshot(root)
        protected = [
            t
            for t in before["rows"]
            if t
            not in {
                "collection_operations",
                "collection_generations",
                "collection_goals",
                "saved_pack_research",
                "django_session",
                "auth_user",
                "axes_accesslog",
                "sqlite_sequence",
            }
        ]
        assert all(before["rows"][t] == after["rows"][t] for t in protected)
        assert [{k: v for k, v in r.items() if k != "last_login"} for r in before["rows"]["auth_user"]] == [
            {k: v for k, v in r.items() if k != "last_login"} for r in after["rows"]["auth_user"]
        ]
        assert before["photos"] == after["photos"]
        assert all(r in after["rows"]["collection_goals"] for r in before["rows"]["collection_goals"])
        goals = [g for g in inv.goals(actor) if g["kind"] == collection_goals.KIND]
        assert goals and all((g["satisfied"], g["missing"]) == (137, 14) for g in goals)
        saved = pack_research.listing(actor)
        assert saved
        reopened = pack_research.reopen(actor, saved[0]["id"])
        assert reopened["progress"]["satisfied"] == 137 and reopened["progress"]["missing"] == 14
        connection.close()
        # Exercise a restored full database copy, leaving browser state intact.
        restored = root / "e2d-restored.sqlite3"
        with sqlite3.connect(root / "e2d-before.sqlite3") as source, sqlite3.connect(restored) as dest:
            source.backup(dest)
        with sqlite3.connect(restored) as db:
            assert (
                db.execute(
                    "SELECT count(*) FROM collection_goals WHERE kind=?", [collection_goals.KIND]
                ).fetchone()[0]
                == 0
            )
            assert db.execute("SELECT count(*) FROM ownership_declarations").fetchone()[0] == 1
        report = dict(
            synthetic=True,
            protected_tables=protected,
            inherited_goals_preserved=True,
            photos_preserved=True,
            goals=[
                dict(id=g["id"], version=g["version"], owned=g["satisfied"], missing=g["missing"])
                for g in goals
            ],
            restart_reopen=True,
            restored_backup_verified=True,
            saved_snapshot_sha256=hashlib.sha256(
                pack_research.one(actor, saved[0]["id"])["snapshot"].encode()
            ).hexdigest(),
            acquisition_calls=0,
        )
    (output / ("verification.json" if verify else "setup.json")).write_text(
        json.dumps(report, indent=2) + "\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    with (
        patch("httpx.Client.send", side_effect=AssertionError("No acquisition")),
        patch("urllib.request.urlopen", side_effect=AssertionError("No acquisition")),
    ):
        run(args.root.resolve(), args.output.resolve(), args.verify)
