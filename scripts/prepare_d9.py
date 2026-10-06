"""Retained-only D9 selection and static catalog preparation; no network I/O."""

import hashlib
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/d9-20261006"
RETAINED = Path("/Users/michaelfuscoletti/dex-private/m7-20261006T180707Z/browser-before-restart-root")
CODES = [
    "lc",
    "2018sm",
    "me01",
    "miscp",
    "pop2",
    "tk-hs-r",
    "ex11",
    "ex15",
    "ex12",
    "ex2",
    "dp7",
    "dp4",
    "sm1",
    "xy9",
    "swshp",
    "swsh8",
    "sv04.5",
    "hgssp",
    "bw11",
    "si1",
]


def write(p, v):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(v, indent=2, ensure_ascii=False) + "\n")


def select():
    p = ROOT / "evidence/m7-20261006/candidate.json"
    candidate = json.loads(p.read_text())
    assert (
        hashlib.sha256(p.read_bytes()).hexdigest()
        == "e8c73b23557a8b40dbadd7fcee2adfdb94953518944f71e829ee35a1b23cbd6c"
    )
    assert p.with_suffix(".sha256").read_text().split()[0] == hashlib.sha256(p.read_bytes()).hexdigest()
    mismatches = [
        f
        for f, h in candidate["files"].items()
        if not Path(f).is_file() or hashlib.sha256(Path(f).read_bytes()).hexdigest() != h
    ]
    assert not mismatches
    write(
        OUT / "entry-verification.json",
        dict(
            candidate_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
            files=len(candidate["files"]),
            mismatches=mismatches,
            reconciled_additions=["docs/M7_CANDIDATE_REVIEW.md", "evidence/m7-review-20261006/review.json"],
            application_source_drift=False,
            owner_operated=False,
        ),
    )
    archive = ROOT / "evidence/d6-20261005/raw/tcgdex-archive.raw"
    h = hashlib.sha256(archive.read_bytes()).hexdigest()
    integrity = json.loads((ROOT / "evidence/d6-20261005/archive-integrity.json").read_text())
    source = json.loads((ROOT / "evidence/d6-20261005/source-ledger.json").read_text())
    bulk = next(a for a in source["attempts"] if a.get("key") == "tcgdex-archive")
    assert h == bulk["sha256"] == "1431e3be180cc5c8e491e480fd78b2b721155622372591d9f82bfb8aa83a6cce"
    assert (
        integrity["exact_commit"] == "99c994747cf7519a3e51166cc932de79a88bd4b3"
        and integrity["archive_matches_complete_git_tree"]
        and integrity["git_blob_hashes_match"]
    )
    with sqlite3.connect(f"file:{RETAINED / 'inventory.db'}?mode=ro", uri=True) as db:
        assessed = {
            s["set_id"]
            for (p,) in db.execute("SELECT package FROM catalog_batches WHERE state='published'")
            for s in json.loads(p)["sets"]
        }
    assert len(assessed) == 48
    # Existing reviewed canonical mapping projects two earlier punctuation aliases.
    aliases = {"tcgdex:en:sv08-5": "tcgdex:en:sv08.5", "tcgdex:en:swsh12-5": "tcgdex:en:swsh12.5"}
    assessed = {aliases.get(i, i) for i in assessed}
    u = json.loads((ROOT / "evidence/d7-20261005/universe.json").read_text())
    us = {s["provider_set_id"]: s for s in u["sets"]}
    eras = {s["era"] for s in u["sets"] if s["id"] in assessed}
    selected = []
    for c in CODES:
        s = us[c]
        assert (
            s["id"] not in assessed
            and s["medium"] == "physical"
            and s["language"] == "en"
            and s["enumeration_complete"]
            and s["release_status"] == "released"
            and not s["gaps"]
        )
        selected.append(
            dict(
                set_id=s["id"],
                source_set_id=c,
                canonical_set_id=s["id"],
                catalog_set_key=c.replace(".", "-"),
                name=s["name"],
                era=s["era"],
                expected_numbered_targets=s["target_numbered_count"],
                full_source_rows=s["english_source_records"],
                source_enumeration_complete=True,
                currently_unassessed=True,
                rationale="Introduce an unrepresented era"
                if s["era"] not in eras
                else "Substantive additional Kanto/Johto coverage, including owned species; promo, named and ordinary cards retained",
            )
        )
    targets = sum(s["expected_numbered_targets"] for s in selected)
    assert targets <= 1500 and len(selected) <= 20
    write(
        OUT / "selection-plan.json",
        dict(
            selection_rule="Fixed ordered twenty-code cross-era tranche; six unrepresented eras first, followed by substantive species coverage and supplemental promo sets; independent of owner missing list",
            sets=selected,
            expected_numbered_targets=targets,
            installed_assessed_excluded=sorted(assessed),
            reconciled_installed_aliases=aliases,
            unrepresented_eras_added=sorted({s["era"] for s in selected} - {*eras}),
            source_sha256=h,
            source_time=bulk["retrieved_at"],
            source_commit=integrity["exact_commit"],
            partially_assessed_sets_excluded=True,
            held_d8_replacements_excluded=True,
        ),
    )


if __name__ == "__main__":
    select()
    import prepare_d9_packages

    prepare_d9_packages.run()
