"""Offline D2b identity/evidence assessment; never acquires or publishes sources."""

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/d2b-20261005"
PRIOR = ROOT / "evidence/e1c-20261005/validation-final/candidate.json"
EXPECTED = "eaa007e9cb13ad628e438645e00486af95bc8742fec952f1f6f98f0baf764464"
PACKAGE = ROOT / "config/sealed/2026-10-05-det1-e1c/package.json"
NORMAL = ROOT / "config/sealed/2026-10-05-det1/normalization.json"


def sha(p):
    assert "b2-parity-20260928/review-local" not in str(p)
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read(p):
    return json.loads(Path(p).read_text())


def emit(name, value, check):
    text = json.dumps(value, indent=2, ensure_ascii=False) + "\n"
    path = OUT / name
    if check:
        assert path.read_text() == text, "Assessment drift: " + name
    else:
        path.write_text(text)


def run(check):
    assert sha(PRIOR) == EXPECTED
    prior = read(PRIOR)
    p, n = read(PACKAGE), read(NORMAL)
    sources = {s["id"]: s for s in p["sources"]}
    species = {s["id"]: s for s in p["species"]}
    norms = {r["printing_id"]: r for r in n["rows"]}
    members = {m["printing_id"]: m for m in p["memberships"]}
    bridge = {c["external_id"]: c for c in p["bridges"][0]["package"]["cards"]}
    ledger = read(ROOT / "evidence/d1d-20261005/attempt-ledger.json")
    attempts = {a["key"]: a for a in ledger["attempts"]}
    lock = read(ROOT / "evidence/d1d-20261005/inputs.json")
    for f, h in lock["files"].items():
        assert sha(f) == h, "Source lock drift: " + f
    assert len(p["printings"]) == len(norms) == len(members) == len(bridge) == 18
    assert set(norms) == set(members) == {r["id"] for r in p["printings"]}
    raw_set = read(attempts["set"]["response_path"])
    assert {c["id"] for c in raw_set["cards"]} == {r["provider_id"] for r in norms.values()}
    rows = []
    for printing in p["printings"]:
        ident = printing["id"]
        r = norms[ident]
        m = members[ident]
        a = attempts[r["provider_id"]]
        raw = read(a["response_path"])
        s = sources["d1d:" + r["provider_id"]]
        for path, key in [
            ("response_path", "response_sha256"),
            ("headers_path", "headers_sha256"),
            ("transport_evidence_path", "transport_sha256"),
        ]:
            assert sha(a[path]) == a[key]
        assert s["sha256"] == r["source_sha256"] == a["response_sha256"]
        assert raw["id"] == r["provider_id"] and raw["localId"] == r["number"]
        assert raw["set"]["id"] == "det1" and raw["dexId"] == [species[r["species_id"]]["dex"]]
        assert raw["variants"] == r["provider_variant_flags"]
        assert raw["variants_detailed"] == r["provider_variant_description"]
        assert printing["species_id"] == r["species_id"] and printing["number"] == r["number"] + "/18"
        assert m["status"] == r["membership"] == "unknown" and printing["finish"] is None
        card = bridge[r["provider_id"] + ":provider-normal-generated"]
        assert card["edition"] is None and card["finish"] is None
        target = f"English Detective Pikachu {printing['name']} #{printing['number']} ({ident})"
        rows.append(
            {
                "provider_id": r["provider_id"],
                "printing_id": ident,
                "membership_id": m["id"],
                "expansion_id": printing["expansion_id"],
                "canonical_species_id": r["species_id"],
                "canonical_species": r["canonical_name"],
                "provider_card_name": printing["name"],
                "collector_number": printing["number"],
                "language": printing["language"],
                "verified_market": None,
                "provider_variant_identity": printing["variant"],
                "provider_variant_description": r["provider_variant_description"],
                "provider_variant_flags": r["provider_variant_flags"],
                "distribution_status": m["status"],
                "membership_provenance": m["sources"],
                "source": s,
                "raw_evidence_path": a["response_path"],
                "raw_sha256": a["response_sha256"],
                "set_raw_sha256": attempts["set"]["response_sha256"],
                "retained_support": [
                    "Provider numbered set/card identity and English endpoint metadata",
                    "Provider dexId joined to pinned official canonical registry",
                    "Provider-described generated normal standard variant only",
                ],
                "question_1_checklist_distribution": {
                    "status": "unknown",
                    "required": f"Official English checklist/card evidence identifying {target}, with a legend or statement explicitly assigning booster, promo or deck distribution; a mere set listing is insufficient.",
                },
                "question_2_product_pack_contents": {
                    "status": "unknown",
                    "required": "Official exact product SKU/version/market documenting Detective Pikachu expansion packs and quantities; separately record other expansion packs and guaranteed cards. This alone does not prove any individual card is in a pack.",
                },
                "question_3_variant_language": {
                    "status": "unknown",
                    "required": f"Explicit English number/name/set match for {target}, and a reviewed mapping from the official card description to provider-normal-generated without equating normal with nonfoil. Ambiguous variant stays unknown; a different printing requires a distinct reviewed identity.",
                },
                "question_4_physical_attributes": {
                    "status": "unknown",
                    "finish": None,
                    "edition": None,
                    "required": "Separate exact-issue physical evidence for each attribute. Record any future finding as a proposed identity review; keep physical finish/edition null in this follow-on.",
                },
                "booster_required": f"Official usable card/checklist distribution statement and legend covering {target}, exact English variant applicability, and physical expansion identity. Product pack-count evidence is separately required for a shopping chain.",
                "promo_required": f"Official guaranteed inclusion or promotion identifying {target}, exact number, English release and matching variant; a product featuring the same species/name is insufficient and says nothing about booster exclusion.",
                "deck_required": f"Official exact English deck list identifying {target} and matching variant; deck inclusion alone cannot prove deck-only. Explicit exclusive-distribution evidence is needed for deck-only status.",
                "limitations": [
                    "Provider-generated variant has no verified physical finish or edition",
                    "English endpoint does not establish US release/market",
                    "Variant flags and provider set list do not prove distribution",
                    "Existing single status cannot express overlapping booster/promo/deck availability; do not force a conflicting result into it",
                ],
                "original151_successor_printing": r["original151"],
                "missing18_research_overlap": r["species_id"] == "ndex:0122",
                "authenticated_account_missingness": None,
            }
        )
    assert (
        len({r["printing_id"] for r in rows})
        == len({r["membership_id"] for r in rows})
        == len({r["collector_number"] for r in rows})
        == 18
    )
    assert sum(r["original151_successor_printing"] for r in rows) == 13
    assert [r["canonical_species"] for r in rows if r["missing18_research_overlap"]] == ["Mr. Mime"]
    audit_files, refs, official = {}, [], []
    for f, h in prior["files"].items():
        q = Path(f) if Path(f).is_absolute() else ROOT / f
        if not ("source-evidence" in f or f.startswith(("config/", "docs/", "evidence/"))):
            continue
        if q.suffix.lower() in {".png", ".pdf", ".jpg", ".sqlite3"}:
            continue
        try:
            retained = OUT / "baseline-snapshots" / q.name
            assessed = (
                retained
                if f in {"docs/PM_STATUS.md", "docs/ROADMAP.md", "docs/history/README.md"}
                and retained.exists()
                else q
            )
            content = assessed.read_text()
        except UnicodeError:
            continue
        audit_files[f] = sha(assessed)
        assert audit_files[f] == h
        for url in sorted(set(re.findall(r'https?://[^\s<>"\x27)]+', content))):
            if any(x in url.lower() for x in ["detective", "det1", "pikachu"]):
                refs.append({"file": f, "url": url})
                if re.match(r"https://(?:[^/]+\.)?(?:pokemon\.com|pokemoncenter\.com)/", url):
                    official.append({"file": f, "url": url})
    assert not official, "Unexpected retained exact official reference: review manually"
    indexes = ["config/sealed/2026-10-04/source-index.json", "config/sealed/2026-10-04-151/source-index.json"]
    emit(
        "reference-audit.json",
        {
            "scope": "E1c candidate config/docs/evidence UTF-8 files and D1d raw/header/transport bytes; no synthetic account databases",
            "files": audit_files,
            "source_indexes": indexes,
            "detective_or_pikachu_references": refs,
            "exact_official_detective_references": official,
            "finding": "No exact official Detective Pikachu reference retained in reviewed source indexes/package references. General expansion index is an access-denied challenge; official 151 checklist/product references concern another expansion. Discovery required; availability unverified.",
        },
        check,
    )
    emit(
        "evidence-matrix.json",
        {
            "schema_version": "dex-d2b-assessment-v1",
            "as_of": "2026-10-05",
            "package": str(PACKAGE.relative_to(ROOT)),
            "package_sha256": sha(PACKAGE),
            "normalization_sha256": sha(NORMAL),
            "rows": rows,
        },
        check,
    )
    emit(
        "validation.json",
        {
            "identity_rows": 18,
            "unique_printing_ids": 18,
            "unique_membership_ids": 18,
            "unique_collector_numbers": 18,
            "unknown_relationships": 18,
            "original151_successor_printings": 13,
            "missing18_research_overlap": ["Mr. Mime"],
            "source_lock_files_verified": len(lock["files"]),
            "raw_detail_hashes_verified": 18,
            "exact_official_references_retained": 0,
            "acquisition_calls": 0,
            "catalog_publications": 0,
            "physical_attributes_changed": 0,
            "application_suite_rerun": False,
            "browser_rerun": False,
            "owner_root_accessed": False,
            "evidence_class": "Offline retained-byte assessment only",
        },
        check,
    )
    print(
        "D2b PASS: 18 exact identities; source hashes verified; 18 unknown; 13 successor; no official Detective Pikachu reference retained."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    run(parser.parse_args().check)
