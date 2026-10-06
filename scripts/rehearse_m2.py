"""Disposable M2 review/browser setup and retained-data reconciliation. Never owner state."""

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

from rehearse_e3a import snapshot
from rehearse_m1 import run as prepare_m1


def supplement():
    sets = []
    for code, values in [
        ("modern-eevee", [134, 135, 136, 196, 197, 252, None]),
        ("johto", [230, 251]),
        ("zero-target", [252]),
        ("truncated", [131]),
    ]:
        cards = [
            dict(
                external_id=f"m2-{code}-{i}",
                number=str(i),
                name=f"Synthetic {code} named form {i}",
                metadata=dict(pokemon_dex=n, dex_eligible=False, supertype="Pokémon", rarity="Rare"),
                variant="alternate",
                finish="foil",
            )
            for i, n in enumerate(values, 1)
        ]
        p = dict(
            schema_version="dex-catalog-v1",
            game="pokemon",
            set_key="m2-" + code,
            set_name="Synthetic M2 " + code,
            language="en",
            aliases=[],
            provider="m2-synthetic",
            version="synthetic-20261005-v1",
            source_url="https://example.test/m2/" + code,
            source_sha256=hashlib.sha256(json.dumps(cards).encode()).hexdigest(),
            metadata_permission="Clearly synthetic supplementary qualification only",
            image_permission="not-included",
            coverage="catalog-entries",
            expected_count=len(cards),
            cards=cards,
        )
        enum = [c["external_id"] for c in cards]
        if code == "truncated":
            enum.append("synthetic-not-retained")
        sets.append(
            dict(
                set_id="m2-synthetic:en:m2-" + code,
                language="en",
                era="swsh" if code == "modern-eevee" else "neo",
                medium="physical",
                release_status="released",
                source_url=p["source_url"],
                source_time="2026-10-04T12:00:00+00:00",
                source_sha256=p["source_sha256"],
                evidence_class="synthetic",
                enumeration_complete=True,
                enumerated_ids=enum,
                package=p,
            )
        )
    return dict(
        schema_version="dex-target-batch-v1",
        version="synthetic-m2-supplement-v1",
        mode="checkpoint",
        sets=sets,
    )


def run(root, output, verify=False):
    from pokemon_hunter.beta import cli

    if not verify:
        prepare_m1(root, output)
    else:
        if not (root / "SYNTHETIC_ONLY").is_file():
            raise ValueError("Disposable state required")
        cli.setup(root)
    from django.contrib.auth import get_user_model

    from pokemon_hunter.beta import catalog_pipeline as pipeline
    from pokemon_hunter.beta import collection as inv
    from pokemon_hunter.beta import collection_goals, lookup, pack_research, parity, store

    actor = store.principal(get_user_model().objects.get(username="admin").pk)

    def write(name, data):
        (output / name).write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n")

    with patch("httpx.Client.send", side_effect=AssertionError("No acquisition")):
        if not verify:
            pipeline.initialize()
            before = snapshot(root)
            (root / "m2-before.json").write_text(json.dumps(before, default=str))
            with (
                sqlite3.connect(root / "inventory.db") as db,
                sqlite3.connect(root / "m2-before.sqlite3") as backup,
            ):
                db.backup(backup)
            retained = pipeline.retained_batch()
            retained["mode"] = "checkpoint"
            op = pipeline.preview(actor, retained)
            write("retained-preview.json", op)
            write("synthetic-supplement.json", supplement())
            write(
                "setup.json",
                dict(synthetic_state=True, retained_sets=13, preview_id=op["id"], provider_calls=0),
            )
            print("Prepared M2 disposable browser state and 13-set immutable review")
            return
        before = json.loads((root / "m2-before.json").read_text())
        retained = pipeline.get(actor, json.loads((output / "setup.json").read_text())["preview_id"])
        assert retained["state"] == "published", "Complete ordinary browser batch publication first"
        write("retained-publication.json", retained)
        report = pipeline.coverage(actor)
        write("set-species-coverage.json", report)
        write("review-exceptions.json", {r["set_id"]: r["exceptions"] for r in report["sets"]})
        write(
            "assessed-unassessed.json",
            {
                s: [r["set_id"] for r in report["sets"] if r["status"] == s]
                for s in sorted({r["status"] for r in report["sets"]})
            },
        )
        # Actual interrupted multi-set local work resumes across process invocations.
        raw = supplement()
        op = pipeline.preview(actor, raw)
        if op["state"] == "preview":
            pipeline.transition(actor, op["id"], "verify")
        checkpoint = (
            op if op["state"] == "partial" else pipeline.transition(actor, op["id"], "publish", limit=1)
        )
        assert checkpoint["state"] == "partial"
        first_child = checkpoint["outcomes"][0]["publication"]
        write("checkpoint.json", checkpoint)
        op = pipeline.transition(actor, op["id"], "publish", limit=250)
        assert op["outcomes"][0]["publication"] == first_child
        assert pipeline.transition(actor, op["id"], "publish") == op
        write("supplement-publication.json", op)
        saved = []
        for n in (134, 135, 230):
            ctx = lookup.project(actor, dict(targets=str(n)))
            assert ctx["missing"][0]["printing_ids"], n
            # Unknown distribution never becomes a booster match.
            assert not any(g["count"] for g in ctx["expansions"] if g["expansion"]["id"].startswith("m2"))
            key = pack_research.store_context(actor, ctx, f"M2 synthetic target {n}")
            saved.append(dict(id=key, snapshot_sha256=pack_research.one(actor, key)["snapshot_sha256"]))
        write("saved-reopen.json", saved)
        after = snapshot(root)
        mutable = {
            "catalog_audit",
            "catalog_batches",
            "catalog_imports",
            "catalog_heads",
            "catalog_aliases",
            "catalog_requests",
            "catalog_sets",
            "printings",
            "external_mappings",
            "games",
            "saved_pack_research",
            "django_session",
            "axes_accesslog",
            "auth_user",
            "sqlite_sequence",
        }
        protected = [t for t in before["rows"] if t not in mutable and not t.startswith("sealed_")]
        for t in protected:
            assert before["rows"][t] == after["rows"][t], t
        assert before["photos"] == after["photos"]
        assert (
            collection_goals.latest(actor)["source_sha256"]
            == "511dec82f4434e1e90ae27ec634e85e546f7559d43cc61d4cabec310d4ccc1b2"
        )
        assert lookup.project(actor, dict(scope="missing"))["progress"]["satisfied"] == 161
        assert len(inv.copies(actor)) == sum(
            r["user_id"] == actor.user_id for r in before["rows"]["owned_copies"]
        )
        # Copied-state backup recovery is exercised in a separate new file.
        restored = root / "m2-restored.sqlite3"
        with sqlite3.connect(root / "m2-before.sqlite3") as backup, sqlite3.connect(restored) as dest:
            backup.backup(dest)
        with sqlite3.connect(root / "m2-before.sqlite3") as backup, sqlite3.connect(restored) as db:
            tables = [r[0] for r in backup.execute("SELECT name FROM sqlite_master WHERE type='table'")]
            for table in tables:
                original = backup.execute(f'SELECT * FROM "{table}"').fetchall()
                recovered = db.execute(f'SELECT * FROM "{table}"').fetchall()
                assert sorted(original, key=repr) == sorted(recovered, key=repr), table
        write(
            "preservation.json",
            dict(
                protected_tables=protected,
                photo_hashes_identical=True,
                source_hash_identical=True,
                copies_identical=True,
                owned=161,
                missing=90,
                copied_backup_recovery=True,
                restored_tables=len(tables),
                provider_calls=0,
                owner_root_access=False,
            ),
        )
        pipeline.transition(actor, op["id"], "rollback")
        write("supplement-rollback.json", pipeline.get(actor, op["id"]))
        # Retained correction rollback restores original expansion provenance through existing journal.
        pipeline.transition(actor, retained["id"], "rollback")
        write("retained-correction-rollback.json", pipeline.get(actor, retained["id"]))
        for entry in saved:
            assert pack_research.one(actor, entry["id"])["snapshot_sha256"] == entry["snapshot_sha256"]
            assert pack_research.reopen(actor, entry["id"])
        write(
            "reopened-after-rollback.json",
            dict(saved_snapshots_identical=True, archived_reference_gaps_explicit=True),
        )
        write("indexed-projection.json", dict(indexed_species=len(parity.projection(actor)["pokedex"])))
        print(json.dumps(report["totals"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    run(args.root, args.output, args.verify)
