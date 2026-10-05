"""Synthetic copied-state rehearsal for the reviewed 151 bridge and metadata correction."""

import argparse
import copy
import hashlib
import json
import sqlite3
from pathlib import Path


def run(root, package_path, output):
    if not (root / "SYNTHETIC_ONLY").is_file() or output.exists():
        raise ValueError("Use a synthetic disposable root and fresh evidence directory")
    output.mkdir(parents=True, mode=0o700)
    from pokemon_hunter.beta.cli import setup

    setup(root)
    from django.contrib.auth import get_user_model
    from django.db import connection

    from pokemon_hunter.beta import sealed_catalog as cat
    from pokemon_hunter.beta import store

    actor = store.principal(get_user_model().objects.get(username="admin").pk)

    def rows():
        names = connection.introspection.table_names()
        return {
            t: sorted(
                store.rows(f"SELECT * FROM {t}"), key=lambda r: json.dumps(r, sort_keys=True, default=str)
            )
            for t in names
            if not t.startswith("sealed_")
            and t not in {"catalog_audit", "catalog_imports", "catalog_heads", "catalog_aliases"}
        }

    before = rows()
    connection.close()
    with (
        sqlite3.connect(root / "inventory.db") as original,
        sqlite3.connect(output / "before.copied.sqlite3") as dest,
    ):
        original.backup(dest)
    cat.initialize()
    cat.initialize()
    assert rows() == before
    p = json.loads(package_path.read_text())

    def publish(raw):
        op = cat.preview(actor, raw)
        cat.transition(actor, op["id"], "verify")
        cat.transition(actor, op["id"], "publish")
        return cat.get(actor, op["id"])

    op = publish(p)
    assert cat.preview(actor, p)["id"] == op["id"]
    after = rows()
    for t, records in before.items():
        if t in {"printings", "catalog_sets", "external_mappings"}:
            assert all(r in after[t] for r in records), t
        else:
            assert after[t] == records, t
    report = cat.report(actor)
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    (output / "publication-mapping.json").write_text(json.dumps(cat.review(op), indent=2) + "\n")
    # This correction is explicitly synthetic, reverted before leaving the real data published.
    q = copy.deepcopy(p)
    q["version"] += "-synthetic-correction"
    q["bridges"][0]["package"]["version"] = q["version"]
    row = q["printings"][0]
    original = copy.deepcopy(row)
    source = copy.deepcopy(next(s for s in q["sources"] if s["id"] == row["sources"][0]))
    source.update(
        id="synthetic:correction-source",
        subjects=[row["id"]],
        note="Synthetic rehearsal evidence; no claim of real source correction",
    )
    q["sources"].append(source)
    row.update(name=row["name"] + " (synthetic reviewed label)", sources=row["sources"] + [source["id"]])
    q["bridges"][0]["package"]["cards"][0]["name"] = row["name"]
    q["corrections"] = [
        dict(
            kind="printings",
            id=row["id"],
            before_sha256=cat.cat.fingerprint(original),
            reason="Synthetic descriptive correction; canonical identity unchanged",
        )
    ]
    corrected = publish(q)
    assert cat.preview(actor, q)["id"] == corrected["id"]
    (output / "synthetic-correction.json").write_text(json.dumps(q, indent=2) + "\n")
    (output / "correction-review.json").write_text(json.dumps(cat.review(corrected), indent=2) + "\n")
    cat.transition(actor, corrected["id"], "rollback")
    assert cat.records()["printings"][original["id"]] == original
    assert rows() == after
    cat.transition(actor, op["id"], "rollback")
    for t, records in before.items():
        current = rows()[t]
        if t in {"printings", "catalog_sets", "external_mappings"}:
            assert all(r in current for r in records), t
        else:
            assert current == records, t
    assert not cat.records()["printings"]
    connection.close()
    with (
        sqlite3.connect(output / "before.copied.sqlite3") as backup,
        sqlite3.connect(output / "recovered.sqlite3") as dest,
    ):
        backup.backup(dest)
    connection.settings_dict["NAME"] = output / "recovered.sqlite3"
    assert rows() == before
    connection.close()
    connection.settings_dict["NAME"] = root / "inventory.db"
    recovered = copy.deepcopy(p)
    recovered["version"] += "-recovery"
    recovered["bridges"][0]["package"]["version"] = recovered["version"]
    final = publish(recovered)
    result = dict(
        evidence_class="Synthetic SQLite copied-state checks using real retained public data; no owner or independent source acceptance",
        package_sha256=hashlib.sha256(package_path.read_bytes()).hexdigest(),
        baseline_table_hashes={
            t: cat.cat.fingerprint(json.loads(json.dumps(r, default=str))) for t, r in before.items()
        },
        migration_repeat_preserved=True,
        preexisting_rows_preserved=True,
        correction_reverted=True,
        rollback_preserved=True,
        copied_recovery_preserved=True,
        idempotent=True,
        final_import_id=final["id"],
        counts=report["counts"],
        bridged=len(report["printings_bridged"]),
    )
    (output / "preservation.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "baseline_table_hashes"}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.root.resolve(), args.package, args.output.resolve())
