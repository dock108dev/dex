"""Add D1d normalized source coverage to a new dated reconciliation; retain D1c unchanged."""

import argparse
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/d1d-20261005/reconciliation"


def read(path):
    return json.loads(Path(path).read_text())


def run(check=False):
    lock = read(ROOT / "evidence/d1d-20261005/inputs.json")
    for path, sha in lock["files"].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == sha, "Input drift: " + path
    original = read(ROOT / "evidence/d1c-20261005/per-set.json")
    rows = copy.deepcopy(original["rows"])
    norm = read(ROOT / "config/sealed/2026-10-05-det1/normalization.json")
    p = read(ROOT / "config/sealed/2026-10-05-det1/package.json")
    assert norm["numbered_count"] == len(p["printings"]) == len(norm["rows"]) == 18
    target = next(r for r in rows if r["id"] == "tcgdex:en:det1")
    assert target["numbered_status"] == "absent" and target["expected_numbered_count"] == 18
    target.update(
        retained_numbered_count=18,
        reviewed_numbered_count=18,
        confirmed_numbered_count=18,
        numbered_status="complete-numbered-metadata-publication-blocked",
        numbered_count_gap=0,
        numbered_identities=["tcgdex:en:" + r["provider_id"] for r in norm["rows"]],
        numbers=[r["number"] for r in norm["rows"]],
        eligible_pokemon_numbered_count=13,
        canonical_species_count=18,
        eligible_policy="canonical Original 151 broad policy",
        reviewed_variant_record_count=18,
        variant_identities=[r["id"] for r in p["printings"]],
        variant_status="provider-descriptions-only-physical-variant-count-unknown",
        unresolved_variant_relationships=[r["id"] for r in p["printings"]],
        publication_status="blocked-before-preview-four-canonical-species-above-251",
        packages=["config/sealed/2026-10-05-det1/package.json"],
        evidence_refs=target["evidence_refs"]
        + [
            "evidence/d1d-20261005/attempt-ledger.json",
            "config/sealed/2026-10-05-det1/normalization.json",
            "evidence/d1d-20261005/synthetic-gate/preservation.json",
        ],
    )
    assert target["synthetic_imported_catalog_records"] == 0
    for a, b in zip(original["rows"], rows, strict=True):
        assert a == b or a["id"] == "tcgdex:en:det1"
    totals = copy.deepcopy(original["totals"])
    totals.update(
        complete_numbered=13,
        absent_physical=192,
        reviewed_numbered=1216,
        numbered_count_gap=22748,
        physical_numbered_gap=20268,
        reviewed_catalog_records=1375,
        normalized_catalog_records=1393,
        d1d_synthetic_imported=0,
        numbered_sets_with_retained_synthetic_publication=12,
        normalized_publication_pending_sets=1,
    )
    assert sum(r["confirmed_numbered_count"] for r in rows) == totals["reviewed_numbered"]
    assert sum(r["numbered_count_gap"] for r in rows) == totals["numbered_count_gap"]
    assert totals["reviewed_numbered"] + totals["numbered_count_gap"] == totals["expected_numbered"]
    summary = read(ROOT / "evidence/d1c-20261005/series-summary.json")
    sm = next(r for r in summary["rows"] if r["series"] == "sm")
    sm.update(
        complete_numbered=1,
        absent=17,
        reviewed_numbered=18,
        numbered_count_gap=2899,
        normalized_publication_pending=1,
    )
    sm["absent_set_ids"].remove("tcgdex:en:det1")
    summary["totals"] = totals
    gaps = read(ROOT / "evidence/d1c-20261005/gaps.json")
    gaps["absent_physical_set_ids"].remove("tcgdex:en:det1")
    g = next(r for r in gaps["sets"] if r["id"] == target["id"])
    for key in (
        "numbered_status",
        "numbered_count_gap",
        "variant_status",
        "unresolved_variant_relationships",
    ):
        g[key] = target[key]
    gaps["pending_publication_set_ids"] = ["tcgdex:en:det1"]
    gaps["d1d_import_blocker"] = (
        "Collection metadata caps canonical IDs at 251: det1-2, det1-3, det1-9, det1-18"
    )
    description = (
        "# D1d absent physical English sets — October 5, 2026\n\n"
        "Retained October 4 universe: 192 absent numbered sets. Detective Pikachu has 18 normalized identities but publication is blocked. Physical variant completeness remains unknown.\n\n"
        "| Stable identity | Name | Series | Count gap |\n|---|---|---|---:|\n"
    )
    for r in rows:
        if r["medium"] == "physical" and r["numbered_status"] == "absent":
            description += f"| `{r['id']}` | {r['name']} | {r['series']} | {r['numbered_count_gap']} |\n"
    outputs = {
        "per-set.json": dict(
            as_of="2026-10-05",
            universe_date="2026-10-04",
            baseline="evidence/d1c-20261005/per-set.json",
            rows=rows,
            totals=totals,
            evidence_class="Retained real-source metadata; D1d publication blocked, historical synthetic coverage unchanged",
        ),
        "series-summary.json": summary,
        "gaps.json": gaps,
        "missing-physical-sets.md": description,
    }
    for filename, data in outputs.items():
        text = data if isinstance(data, str) else json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        path = OUT / filename
        if check:
            assert path.read_text() == text, "Output drift: " + str(path)
        else:
            OUT.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
    print(json.dumps(totals, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    run(parser.parse_args().check)
