"""Reconcile only pinned retained bytes. No database access or network operations."""

import argparse
import hashlib
import json
import uuid
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/d1c-20261005"
PRIVATE = Path("/Users/michaelfuscoletti/dex-private")


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(name, value, check):
    data = value if isinstance(value, str) else json.dumps(value, indent=2, ensure_ascii=False) + "\n"
    path = OUT / name
    if check:
        assert path.read_text() == data, f"Output drift: {path}"
    else:
        path.write_text(data)


def run(check=False):
    lock = read(OUT / "inputs.json")
    for path, expected in lock["files"].items():
        assert digest(path) == expected, f"Source hash mismatch: {path}"
    u = read(ROOT / "config/sealed/2026-10-04/universe.json")
    index = read(ROOT / "config/sealed/2026-10-04/source-index.json")
    rawroot = PRIVATE / "d1-e1-20261004/source-evidence"
    detailroot = PRIVATE / "d1-e1b-20261004/source-evidence"
    for filename, expected in read(detailroot / "retained-hashes.json").items():
        assert digest(detailroot / filename) == expected, filename
    detailindex = read(detailroot / "index.json")
    for metadata in detailindex.values():
        if metadata.get("file") and metadata.get("sha256"):
            assert digest(detailroot / metadata["file"]) == metadata["sha256"]
    rawsets = read(rawroot / "sets.raw")
    assert len(rawsets) == len(u["sets"]) == 220
    assert {r["id"] for r in rawsets} == {r["id"].split(":", 2)[2] for r in u["sets"]}
    assert len({r["id"] for r in u["sets"]}) == 220
    sourcechecks = []
    for key in ["sets", "series", "set151", "official-checklist", "sg"] + sorted(
        k for k in index if k.startswith("series-")
    ):
        path = rawroot / (key + ".raw")
        assert digest(path) == index[key]["sha256"], key
        sourcechecks.append({"id": key, **index[key], "retained_path": str(path)})
    p = read(ROOT / "config/sealed/2026-10-04-151/package.json")
    reconciliation = read(ROOT / "config/sealed/2026-10-04-151/reconciliation.json")
    reportpath = PRIVATE / "d1-e1b-20261004/rehearsal-evidence-3/report.json"
    report = read(reportpath)
    assert {r["printing_id"] for r in report["printings_bridged"]} == {r["id"] for r in p["printings"]}
    assert report["booster_memberships_evidenced"] == 207
    projectionpath = ROOT / "evidence/e6a-20261005/rehearsal-final/version-1.json"
    refs = read(projectionpath)["goal"]["definition"]["catalog_references"]
    members = {r["printing_id"]: r["status"] for r in p["memberships"]}
    rows, conflicts, unmatched, gaps = [], [], [], []
    for entry in u["sets"]:
        code = entry["id"].split(":", 2)[2]
        rawseries = read(rawroot / ("series-" + entry["series"] + ".raw"))
        seriesentry = [s for s in rawseries["sets"] if s["id"] == code]
        rowconflicts = []
        if len(seriesentry) != 1 or seriesentry[0]["cardCount"]["total"] != entry["expected_printings"]:
            rowconflicts.append({"set_id": entry["id"], "reason": "series count/identity conflict"})
        classification = (
            "digital-only" if entry["medium"] == "digital" else "physical-unresolved-product-class"
        )
        if entry["medium"] == "physical" and "promo" in entry["name"].lower():
            classification = "physical-promo-label"
        elif entry["medium"] == "physical" and (
            entry["series"] in ["tk", "mc", "pop", "misc"]
            or code
            in [
                "si1",
                "ex5.5",
                "bog",
                "sp",
                "ru1",
                "xya",
                "fut2020",
                "sve",
                "mee",
                "exu",
                "rc",
                "sma",
                "cel25cc",
            ]
            or code.endswith("tg")
            or code.endswith("gg")
        ):
            classification = "physical-special-product-or-subset"
        packages, ids, numbers, eligible, variantids, published, membershipgaps = [], [], [], None, [], [], []
        publication = "no-retained-reviewed-publication"
        if code in u["existing_shipped_packages"]:
            path = ROOT / u["existing_shipped_packages"][code]["package"]
            cp = read(path)
            packages.append(str(path.relative_to(ROOT)))
            if (cp["provider"], cp["language"], cp["set_key"]) != ("tcgdex", "en", code):
                rowconflicts.append(
                    {"set_id": entry["id"], "reason": "explicit provider/language/set mismatch"}
                )
            ids = [f"tcgdex:en:{c['external_id']}" for c in cp["cards"]]
            numbers = [c["number"] for c in cp["cards"]]
            eligible = (
                sum(c.get("metadata", {}).get("dex_eligible", False) for c in cp["cards"])
                if all("metadata" in c for c in cp["cards"])
                else None
            )
            sid = (
                str(
                    uuid.uuid5(
                        uuid.UUID("c40655cd-2748-49cc-877f-88c05d3a4473"),
                        "set:pokemon:" + cp["reconcile_legacy_set"],
                    )
                )
                if cp.get("reconcile_legacy_set")
                else str(
                    uuid.uuid5(
                        uuid.UUID("c40655cd-2748-49cc-877f-88c05d3a4473"), "catalog-set:pokemon:en:" + code
                    )
                )
            )
            published = [r for r in refs if r["version"] == cp["version"] and r["set_id"] == sid]
            assert len(published) == 1, code
            # Names only select the journal reference after exact package provider/code checks.
            publication = "synthetic-published-reference; packaged-identities"
        if code == "sv03.5":
            packages = ["config/sealed/2026-10-04-151/package.json"]
            ids = [f"tcgdex:en:{r['provider_id']}" for r in reconciliation["rows"]]
            numbers = [r["number"] for r in reconciliation["rows"]]
            variantids = [r["id"] for r in p["printings"]]
            eligible = sum(r["category"] == "pokemon" for r in reconciliation["rows"])
            published = [{"reference": str(reportpath), "bridged": len(report["printings_bridged"])}]
            publication = "synthetic-publication-and-bridge-demonstrated"
            membershipgaps = [g for r in reconciliation["rows"] for g in r["gaps"]]
        duplicates = [i for i, count in Counter(ids).items() if count > 1]
        if duplicates:
            rowconflicts.append(
                {"set_id": entry["id"], "reason": "duplicate printing identities", "identities": duplicates}
            )
        conflicts.extend(rowconflicts)
        expected = entry["expected_printings"]
        confirmed = len(set(ids)) if not rowconflicts else 0
        status = (
            "identity-conflicted"
            if rowconflicts
            else (
                "absent"
                if not ids
                else ("complete-numbered" if expected == confirmed else "partial-numbered")
            )
        )
        exactmissing = []
        # Universe counts do not enumerate unknown card identities. Never fabricate 1..N.
        row = {
            **entry,
            "provider": "tcgdex",
            "set_code": code,
            "series_name": rawseries["name"],
            "classification": classification,
            "classification_authority": "provider medium/series; name-based promo/special triage only, official distribution unresolved",
            "expected_numbered_count": expected,
            "expected_variant_count": None,
            "retained_numbered_count": len(set(ids)),
            "reviewed_numbered_count": confirmed,
            "synthetic_imported_catalog_records": (len(variantids) if variantids else confirmed),
            "confirmed_numbered_count": confirmed,
            "numbered_status": status,
            "numbered_count_gap": None if expected is None else max(0, expected - confirmed),
            "exact_missing_numbered_identities": exactmissing,
            "missing_identity_limit": "No card-level universe retained for uncovered set; count gap only"
            if not ids
            else None,
            "numbered_identities": ids,
            "numbers": numbers,
            "eligible_pokemon_numbered_count": eligible,
            "reviewed_variant_record_count": len(variantids),
            "variant_identities": variantids,
            "variant_status": "partial-physical-relationships" if variantids else "unknown",
            "confirmed_standard_variant_count": 0
            if rowconflicts
            else sum(members[i] == "booster" for i in variantids),
            "unresolved_variant_relationships": membershipgaps,
            "membership_status": "207-standard-supported;177-extra-unknown"
            if variantids
            else "not-independently-reviewed",
            "publication_status": publication,
            "owner_publication_status": "not-assessed",
            "packages": packages,
            "publication_evidence": published,
            "evidence_refs": [
                "config/sealed/2026-10-04/universe.json",
                "config/sealed/2026-10-04/source-index.json",
                str(rawroot / ("series-" + entry["series"] + ".raw")),
            ]
            + packages,
            "conflicts": rowconflicts,
        }
        rows.append(row)
        if status != "complete-numbered" or membershipgaps or row["variant_status"] == "unknown":
            gaps.append(
                {
                    k: row[k]
                    for k in [
                        "id",
                        "name",
                        "series",
                        "medium",
                        "classification",
                        "numbered_status",
                        "numbered_count_gap",
                        "exact_missing_numbered_identities",
                        "missing_identity_limit",
                        "variant_status",
                        "membership_status",
                        "unresolved_variant_relationships",
                        "conflicts",
                    ]
                }
            )
    known = {r["set_code"] for r in rows}
    for path in sorted((ROOT / "config/catalog-imports").rglob("*.json")):
        d = read(path)
        if "set_key" in d and d["set_key"] not in known:
            unmatched.append(
                {
                    "path": str(path.relative_to(ROOT)),
                    "set_code": d["set_key"],
                    "language": d.get("language"),
                    "reason": "outside retained provider universe; synthetic package excluded",
                }
            )
    series = defaultdict(list)
    for r in rows:
        series[r["series"]].append(r)
    summary = [
        {
            "series": key,
            "name": group[0]["series_name"],
            "sets": len(group),
            "physical": sum(r["medium"] == "physical" for r in group),
            "digital": sum(r["medium"] == "digital" for r in group),
            "complete_numbered": sum(r["numbered_status"] == "complete-numbered" for r in group),
            "absent": sum(r["numbered_status"] == "absent" for r in group),
            "conflicted": sum(r["numbered_status"] == "identity-conflicted" for r in group),
            "expected_numbered": sum(
                r["expected_numbered_count"] for r in group if r["expected_numbered_count"] is not None
            ),
            "unknown_expected_sets": sum(r["expected_numbered_count"] is None for r in group),
            "reviewed_numbered": sum(r["confirmed_numbered_count"] for r in group),
            "numbered_count_gap": sum(r["numbered_count_gap"] or 0 for r in group),
            "absent_set_ids": [r["id"] for r in group if r["numbered_status"] == "absent"],
        }
        for key, group in sorted(series.items())
    ]
    totals = {
        "sets": len(rows),
        "physical": sum(r["medium"] == "physical" for r in rows),
        "digital": sum(r["medium"] == "digital" for r in rows),
        "complete_numbered": sum(r["numbered_status"] == "complete-numbered" for r in rows),
        "absent_physical": sum(r["medium"] == "physical" and r["numbered_status"] == "absent" for r in rows),
        "absent_digital": sum(r["medium"] == "digital" and r["numbered_status"] == "absent" for r in rows),
        "reviewed_numbered": sum(r["confirmed_numbered_count"] for r in rows),
        "reviewed_catalog_records": sum(
            r["synthetic_imported_catalog_records"] for r in rows if not r["conflicts"]
        ),
        "expected_numbered": sum(
            r["expected_numbered_count"] for r in rows if r["expected_numbered_count"] is not None
        ),
        "numbered_count_gap": sum(r["numbered_count_gap"] or 0 for r in rows),
        "conflicts": len(conflicts),
    }
    assert sum(r["sets"] for r in summary) == 220
    assert totals["physical"] == 205 and totals["digital"] == 15
    assert totals["reviewed_numbered"] + totals["numbered_count_gap"] == totals["expected_numbered"]
    missing_lines = [
        "# Absent physical English sets — October 5, 2026",
        "",
        "Relative to retained October 4 TCGdex universe; 193 sets. Counts are retained provider totals; printing IDs and variants remain unknown.",
        "",
        "| Stable set identity | Name | Series | Count gap |",
        "|---|---|---|---:|",
    ]
    for row in rows:
        if row["medium"] == "physical" and row["numbered_status"] == "absent":
            missing_lines.append(
                f"| `{row['id']}` | {row['name']} | {row['series']} | {row['numbered_count_gap']} |"
            )
    write("missing-physical-sets.md", "\n".join(missing_lines) + "\n", check)
    write(
        "per-set.json",
        {"as_of": "2026-10-05", "universe_date": "2026-10-04", "rows": rows, "totals": totals},
        check,
    )
    write(
        "gaps.json",
        {
            "sets": gaps,
            "absent_physical_set_ids": [
                r["id"] for r in rows if r["medium"] == "physical" and r["numbered_status"] == "absent"
            ],
            "conflicts": conflicts,
            "unmatched_catalog_packages": unmatched,
            "excluded_legacy_catalogs": "config/catalog/*.json: legacy reference not additive publication; explicit reconcile_legacy_set mappings in staging packages",
            "excluded_synthetic": unmatched,
            "duplicate_policy": "duplicate exact identities stop affected join; old Scyther and repeated packages coalesce by stable ID, never add",
        },
        check,
    )
    write("series-summary.json", {"as_of": "2026-10-05", "rows": summary, "totals": totals}, check)
    write(
        "source-verification.json",
        {
            "sources": sourcechecks,
            "pinned_input_files_verified": len(lock["files"]),
            "checks": [
                "220 unique universe IDs",
                "raw universe/series identity and count match",
                "numbered totals reconcile",
                "conflicts excluded",
                "384 bridge IDs match retained report",
                "207 independently supported memberships",
                "all cited retained source hashes match",
            ],
            "totals": totals,
        },
        check,
    )
    print(json.dumps(totals, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    run(parser.parse_args().check)
