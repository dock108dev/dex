"""Fresh M1 disposable state, source-byte identity and preserved-history audit."""

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

from rehearse_e2d import run as prepare_e2d
from rehearse_e3a import snapshot


def run(root, output, verify=False):
    from pokemon_hunter.beta.cli import setup

    if not verify:
        prepare_e2d(root, output)
    else:
        if not (root / "SYNTHETIC_ONLY").is_file():
            raise ValueError("Disposable synthetic state required")
        setup(root)
    from django.contrib.auth import get_user_model

    from pokemon_hunter.beta import collection as inv
    from pokemon_hunter.beta import collection_goals as goals
    from pokemon_hunter.beta import lookup, pack_research, store

    actor = store.principal(get_user_model().objects.get(username="admin").pk)
    if not verify:
        old = next(g for g in inv.goals(actor) if g["kind"] == "original151")
        key = pack_research.save(
            actor, old["id"], research_name="Pre-M1 reviewed-copy research", goal_version=old["version"]
        )
        for name in ("hunt.json", "demo_hunts.json", "raw_values.json"):
            (root / "parity-evidence" / name).write_bytes(
                (Path(__file__).resolve().parents[1] / "config" / name).read_bytes()
            )
        (root / "m1-before.json").write_text(json.dumps(snapshot(root), default=str))
        report = dict(
            synthetic=True,
            legacy_saved_id=key,
            legacy_saved_sha256=hashlib.sha256(
                pack_research.one(actor, key)["snapshot"].encode()
            ).hexdigest(),
            source_sha256=goals.latest(actor)["source_sha256"],
            provider_calls=0,
        )
        (output / "m1-setup.json").write_text(json.dumps(report, indent=2) + "\n")
    else:
        before = json.loads((root / "m1-before.json").read_text())
        after = snapshot(root)
        excluded = {
            "collection_operations",
            "collection_generations",
            "collection_goals",
            "saved_pack_research",
            "ownership_declarations",
            "auth_user",
            "django_session",
            "axes_accesslog",
            "sqlite_sequence",
            "import_batches",
            "saved_hunts",
            "hunts",
            "hunt_items",
            "hunt_collected",
        }
        identical = [t for t in before["rows"] if t not in excluded]
        assert all(before["rows"][t] == after["rows"][t] for t in identical)
        assert before["photos"] == after["photos"]

        def auth(rows):
            return [{k: v for k, v in r.items() if k != "last_login"} for r in rows]

        assert auth(before["rows"]["auth_user"]) == auth(after["rows"]["auth_user"])
        for t in ("import_batches", "saved_hunts", "hunts", "hunt_items", "hunt_collected"):
            if t in before["rows"]:
                assert all(r in after["rows"][t] for r in before["rows"][t]), t
        for t in ("ownership_declarations", "collection_goals", "saved_pack_research"):
            assert all(r in after["rows"][t] for r in before["rows"][t]), t
        current = goals.latest(actor)
        assert current["source_sha256"] == "511dec82f4434e1e90ae27ec634e85e546f7559d43cc61d4cabec310d4ccc1b2"
        all_missing = lookup.project(actor, dict(scope="missing"))
        assert all_missing["progress"]["satisfied"] == 161 and len(all_missing["missing"]) == 90
        assert len([i for i in all_missing["missing"] if i["pokemon_dex"] <= 151]) == 14
        stored = pack_research.listing(actor)
        assert len(stored) >= 2
        reopened = [pack_research.reopen(actor, r["id"]) for r in stored]
        assert any(c.get("lookup") for c in reopened)
        report = dict(
            synthetic=True,
            identical_tables=identical,
            photos_identical=True,
            inherited_sources_goals_research_retained=True,
            current_owned=161,
            current_missing=90,
            kanto_missing=14,
            goals=[
                dict(id=g["id"], kind=g["kind"], owned=g["satisfied"], total=g["total"])
                for g in inv.goals(actor)
            ],
            saved_count=len(stored),
            lookup_contexts=[
                dict(
                    name=c["saved"]["name"],
                    scope=c.get("lookup_request"),
                    snapshot_sha256=c["saved"]["snapshot_sha256"],
                )
                for c in reopened
            ],
            provider_calls=0,
        )
        # Restore the original backup into another disposable database and compare every table.
        restored = root / "m1-restored.sqlite3"
        with sqlite3.connect(root / "e2d-before.sqlite3") as source, sqlite3.connect(restored) as dest:
            source.backup(dest)
        original = json.loads((root / "e2d-before.json").read_text())
        with sqlite3.connect(restored) as db:
            db.row_factory = sqlite3.Row
            for table, expected in original["rows"].items():
                rows = sorted(
                    [dict(r) for r in db.execute(f'SELECT * FROM "{table}"')],
                    key=lambda r: json.dumps(r, sort_keys=True, default=str),
                )
                assert json.loads(json.dumps(rows, default=str)) == expected, table
        report["restored_all_tables_identical"] = True
        report["credentials_and_inherited_hunts_preserved"] = True
        # Read-only verification of the original backup retained by preparation.
        with sqlite3.connect(root / "e2d-before.sqlite3") as db:
            assert (
                db.execute(
                    "SELECT count(*) FROM collection_goals WHERE kind='collection_species'"
                ).fetchone()[0]
                == 0
            )
        report["rollback_backup_verified"] = True
        (output / "m1-verification.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--verify", action="store_true")
    a = p.parse_args()
    with (
        patch("httpx.Client.send", side_effect=AssertionError("No acquisition")),
        patch("urllib.request.urlopen", side_effect=AssertionError("No acquisition")),
    ):
        run(a.root.resolve(), a.output.resolve(), a.verify)
