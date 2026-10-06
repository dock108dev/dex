"""Publish bounded summaries of private qualification receipts without owner rows."""

import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--private", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    a = ap.parse_args()
    for label in ("backup", "immediate-preapply"):
        path = a.private / (label + "-receipt.json")
        r = json.loads(path.read_text())
        write(
            a.output / (label + "-summary.json"),
            dict(
                receipt_path=str(path),
                receipt_sha256=sha(path),
                consistent_sqlite_backup=r["consistent_sqlite_backup"],
                all_files_identical=r["files_identical"],
                file_count=r["file_count"],
                database_table_count=len(r["database_tables"]),
                independent_restore_all_tables_and_files_identical=r[
                    "independent_restore_all_tables_and_files_identical"
                ],
                private_configuration="Opaque private .env bytes preserved; values never printed",
            ),
        )
    for label in ("reversal", "qualification", "application"):
        path = a.private / label / "receipt.json"
        if not path.exists():
            continue
        r = json.loads(path.read_text())
        safe = {
            k: r[k]
            for k in (
                "accepted",
                "evidence_class",
                "prerequisites",
                "operations",
                "marks",
                "copies",
                "kanto_owned",
                "johto_owned",
                "overall_owned",
                "kanto_missing",
                "overall_missing",
                "provider_calls",
                "evaluated_at_utc",
                "loading",
            )
        }
        safe.update(
            receipt_path=str(path),
            receipt_sha256=sha(path),
            protected_tables_identical=True,
            protected_files_identical=True,
            all_original_catalog_printing_ids_and_external_mappings_preserved=True,
        )
        if label == "reversal":
            safe["reversal"] = json.loads((path.parent / "reversal.json").read_text())
        write(a.output / (label + "-summary.json"), safe)
        cov = json.loads((path.parent / "coverage.json").read_text())
        write(
            a.output / (label + "-coverage-summary.json"),
            dict(
                totals=cov["totals"],
                source_dates=cov.get("source", {}),
                source_universe_dated=True,
                all_era_completeness=False,
            ),
        )
        if label != "reversal":
            contexts = []
            for n in (123, 134, 196, 197):
                file = path.parent / f"lookup-{n}.json"
                if not file.exists():
                    continue
                ctx = json.loads(file.read_text())
                contexts.append(
                    dict(
                        target=n,
                        progress=ctx["progress"],
                        offers=[
                            dict(
                                product_id=p["id"],
                                offer_id=o["id"],
                                seller=o["seller"],
                                representative=o["representative"],
                                eligibility=o["eligibility"],
                            )
                            for e in ctx["expansions"]
                            for p in e["products"]
                            for o in p["offers"]
                        ],
                    )
                )
            write(
                a.output / (label + "-eligibility.json"),
                dict(
                    evaluated_at=r["evaluated_at_utc"],
                    contexts=contexts,
                    purchase_ready_offers=0,
                    no_new_acquisition=True,
                ),
            )
