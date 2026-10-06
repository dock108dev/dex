"""New reconciliation: retained metadata counts versus demonstrated synthetic publication."""

import argparse
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/e1c-20261005/reconciliation"


def run(check=False):
    lock = json.loads((ROOT / "evidence/d1d-20261005/inputs.json").read_text())
    for path, sha in lock["files"].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == sha
    results = json.loads((ROOT / "evidence/e1c-20261005/publication.json").read_text())
    successor = json.loads((ROOT / "evidence/e1c-20261005/successor-publication.json").read_text())
    assert results["numbered_cards"] == 18 and results["reviewed_restoration"]
    assert successor["additions"] == 13 and successor["confirmed_pack_species"] == 0
    original = ROOT / "evidence/d1d-20261005/reconciliation"
    data = {
        name: copy.deepcopy(json.loads((original / name).read_text()))
        for name in ("per-set.json", "series-summary.json", "gaps.json")
    }
    per = data["per-set.json"]
    target = next(r for r in per["rows"] if r["id"] == "tcgdex:en:det1")
    target.update(
        numbered_status="complete-numbered-metadata-synthetic-publication-demonstrated",
        publication_status="reviewed-synthetic-18-card-publication-rollback-restoration-qualified",
        synthetic_imported_catalog_records=18,
        packages=target["packages"] + ["config/sealed/2026-10-05-det1-e1c/package.json"],
        evidence_refs=target["evidence_refs"]
        + [
            "evidence/e1c-20261005/publication.json",
            "evidence/e1c-20261005/preservation.json",
            "evidence/e1c-20261005/successor-publication.json",
        ],
    )
    per["baseline"] = "evidence/d1d-20261005/reconciliation/per-set.json"
    per["evidence_class"] = (
        "Retained real metadata; historical synthetic demonstrations plus E1c full-set synthetic publication, not owner installation coverage"
    )
    totals = per["totals"]
    totals.update(
        reviewed_catalog_records=1393,
        d1d_synthetic_imported=18,
        numbered_sets_with_retained_synthetic_publication=13,
        normalized_publication_pending_sets=0,
    )
    data["series-summary.json"]["totals"] = totals
    sm = next(r for r in data["series-summary.json"]["rows"] if r["series"] == "sm")
    sm["normalized_publication_pending"] = 0
    sm["synthetic_publication_demonstrated"] = 1
    gaps = data["gaps.json"]
    next(r for r in gaps["sets"] if r["id"] == target["id"])["numbered_status"] = target["numbered_status"]
    gaps["pending_publication_set_ids"] = []
    gaps["d1d_import_blocker"] = None
    gaps["remaining_blocker"] = (
        "Detective Pikachu official booster/promo/deck applicability for all 18 relationships is unverified"
    )
    for name, value in data.items():
        text = json.dumps(value, indent=2, ensure_ascii=False) + "\n"
        if check:
            assert (OUT / name).read_text() == text
        else:
            OUT.mkdir(parents=True, exist_ok=True)
            (OUT / name).write_text(text)
    print(
        "Metadata counts unchanged; 18 synthetic publications demonstrated; 192 absent physical sets, 18 relationships unknown"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    run(parser.parse_args().check)
