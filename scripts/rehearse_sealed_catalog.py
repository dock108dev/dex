"""E1 copied-state preservation, import/rollback and recovery on a synthetic root only."""

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path


def run(root, package_path, output):
    if not (root / "SYNTHETIC_ONLY").is_file():
        raise ValueError("Rehearsal accepts only an explicitly synthetic disposable root")
    if output.exists():
        raise ValueError("Use a fresh evidence directory")
    output.mkdir(mode=0o700, parents=True)
    from pokemon_hunter.beta.cli import setup

    setup(root)
    from django.contrib.auth import get_user_model
    from django.db import connection

    from pokemon_hunter.beta import deployment, sealed_catalog, store

    actor = store.principal(get_user_model().objects.get(username="admin").pk)

    def preserved():
        return {
            k: v
            for k, v in deployment.manifest().items()
            if not k.startswith("sealed_") and k != "catalog_audit"
        }

    before = preserved()
    connection.close()
    with (
        sqlite3.connect(root / "inventory.db") as old,
        sqlite3.connect(output / "before.copied.sqlite3") as dest,
    ):
        old.backup(dest)
    sealed_catalog.initialize()
    sealed_catalog.initialize()
    assert preserved() == before
    package = json.loads(package_path.read_text())
    op = sealed_catalog.preview(actor, package)
    (output / "review.json").write_text(json.dumps(sealed_catalog.review(op), indent=2))
    sealed_catalog.transition(actor, op["id"], "verify")
    sealed_catalog.transition(actor, op["id"], "publish")
    assert sealed_catalog.preview(actor, package)["id"] == op["id"]
    assert preserved() == before
    report = sealed_catalog.report(actor)
    (output / "coverage.json").write_text(json.dumps(report, indent=2))
    (output / "coverage.txt").write_text(sealed_catalog.summary(report) + "\n")
    sealed_catalog.transition(actor, op["id"], "rollback")
    assert preserved() == before
    assert all(n == 0 for n in sealed_catalog.report(actor)["counts"].values())
    connection.close()
    with (
        sqlite3.connect(output / "before.copied.sqlite3") as old,
        sqlite3.connect(output / "recovered.sqlite3") as dest,
    ):
        old.backup(dest)
    connection.settings_dict["NAME"] = output / "recovered.sqlite3"
    assert preserved() == before
    connection.close()
    connection.settings_dict["NAME"] = root / "inventory.db"
    # Leave the real public package published in the synthetic root using a new journal version.
    republished = sealed_catalog.preview(
        actor, {**package, "version": package["version"] + "-recovery-republish"}
    )
    sealed_catalog.transition(actor, republished["id"], "verify")
    sealed_catalog.transition(actor, republished["id"], "publish")
    assert preserved() == before
    result = dict(
        evidence_class="automated synthetic-state rehearsal with real public package",
        package_sha256=hashlib.sha256(package_path.read_bytes()).hexdigest(),
        package_fingerprint=op["package_hash"],
        preserved_tables=before,
        repeat_import_same_id=True,
        migration_repeat_preserved=True,
        publication_preserved=True,
        rollback_preserved=True,
        recovered_copy_preserved=True,
        final_import_id=republished["id"],
        initial_import_id=op["id"],
        counts=report["counts"],
    )
    (output / "preservation.json").write_text(json.dumps(result, indent=2))
    print(sealed_catalog.summary(sealed_catalog.report(actor)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.root.resolve(), args.package, args.output.resolve())
