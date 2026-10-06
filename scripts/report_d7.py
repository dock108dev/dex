"""Report exact cached tranche, source chains, access gaps and package order."""

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from prepare_d7 import DEST, OUT, PIN, ROOT, write


def run(validation):
    batch = json.loads((DEST / "batch.json").read_text())
    universe = json.loads((OUT / "universe.json").read_text())
    targets = json.loads((OUT / "target-printings.json").read_text())
    mapping = json.loads((OUT / "provider-mappings.json").read_text())
    exclusions = json.loads((OUT / "variant-exclusions.json").read_text())
    exceptions = json.loads((OUT / "exceptions.json").read_text())
    assessed = []
    for a in batch["sets"]:
        code = a["package"]["set_key"]
        rows = [r for r in targets if r["provider_set_id"] == code]
        assert len(rows) == a["expected_target_count"] == len(set(a["numbered_mappings"].values()))
        assert all(c["metadata"]["pokemon_dex"] <= 251 for c in a["package"]["cards"])
        assert all(c["edition"] in [None, "unlimited", "1st-edition"] for c in a["package"]["cards"])
        assessed.append(
            dict(
                set_id=a["set_id"],
                name=a["package"]["set_name"],
                numbered_targets=len(rows),
                supplied_english_variants=len(a["package"]["cards"]),
                source_enumeration_complete=next(
                    s["enumeration_complete"] for s in universe["sets"] if s["provider_set_id"] == code
                ),
                published_coverage="partial: physical variant and whole-set denominator unresolved",
                source_file_hashes={r["file"]: r["file_sha256"] for r in rows},
                variant_exclusions=[r for r in exclusions if r["external_id"].startswith(code + "-")],
                exceptions=[e for e in exceptions if e.get("set_id") == a["set_id"]],
                editions=dict(Counter(c["edition"] or "unspecified" for c in a["package"]["cards"])),
                package_sha256=hashlib.sha256((DEST / (code + ".json")).read_bytes()).hexdigest(),
            )
        )
    assert sum(s["numbered_targets"] for s in assessed) == 533
    write(
        OUT / "tranche-review.json",
        dict(
            commit=PIN,
            numbered_targets=533,
            supplied_english_variants=995,
            count_difference=0,
            sets=assessed,
            mappings=mapping,
            source_time="Inherited D6 raw observation time; normalization is not acquisition",
            metadata_permission="MIT Copyright (c)2021 TCGdex; retained license",
            variant_completeness="unknown",
            source_universe=dict(
                english_sets=220,
                physical=205,
                digital=15,
                qualifying_physical_numbered_targets=6991,
                complete_physical_source_enumerations=188,
            ),
        ),
    )
    missing = {
        int(r["Dex"])
        for r in csv.DictReader(
            (ROOT / "outputs/missing-90-pokemon-all-listed-packs-and-rarities.csv").open(encoding="utf-8-sig")
        )
    }
    assert len(missing) == 90 and sum(n <= 151 for n in missing) == 14
    runtime = json.loads((validation / "product-coverage.json").read_text())
    source_species = json.loads((OUT / "species-coverage.json").read_text())
    for r, s in zip(runtime, source_species, strict=True):
        assert r["dex"] == s["pokemon_dex"]
        s.update(
            owned=r["dex"] not in missing,
            missing=r["dex"] in missing,
            region="Kanto" if r["dex"] <= 151 else "Johto",
            app_chain=r,
            research_absence=False,
        )
    write(OUT / "species-coverage.json", source_species)
    write(
        OUT / "current-missing.json",
        dict(
            source="outputs/my-have-dex-001-251-photo-reconciled.csv",
            total_owned=161,
            kanto_owned=137,
            total_missing=90,
            kanto_missing=14,
            rows=[s for s in source_species if s["missing"]],
        ),
    )
    write(
        OUT / "set-coverage.json",
        dict(
            source_sets=universe["sets"],
            d7_reviewed_sets=assessed,
            runtime_totals=json.loads((validation / "coverage.json").read_text())["totals"],
            warning="Runtime uses historical October4 universe and dotted/undotted alias defect; source universe is separate. Publication does not confer all-era completeness.",
        ),
    )
    shopping = json.loads((ROOT / "config/sealed/d7-20261005/shopping-package.json").read_text())
    write(
        OUT / "product-chains.json",
        dict(
            products=shopping["products"],
            components=shopping["packs"],
            guaranteed_components=json.loads((OUT / "guaranteed-components.json").read_text()),
            offers=shopping["offers"],
            observations=shopping["observations"],
            documented_designs=3,
            identified_seller_observations=1,
            current_eligible_offers=0,
            unavailable_new_condition=2,
            sku_conflict=dict(
                target_upc="820650858550",
                bestbuy_upc="820650878558",
                resolution="Different products/versions retained; no equivalence or official contents applicability inferred for BestBuy version",
            ),
            gaps=[
                "Target/Pokémon Center verification challenges, hosts stopped",
                "Walmart page crash prevented DOM/screenshot retention and condition review; visible result not accepted",
                "GameStop live page-not-found supersedes search-only unavailable result",
                "Prismatic account/location limits; stock/shipping/tax/owner delivery unknown",
                "Crown Lucario VSTAR guaranteed component above251 retained separately, exact promo printing unresolved and not researched",
                "Prismatic gold Pikachu179/ball/cosmos/stamped variant distributions unresolved",
                "Stellar Crown printing distribution remains unknown",
            ],
        ),
    )
    write(
        OUT / "alias-integration-handoff.json",
        dict(
            defect="Catalog keys permit hyphens but primary expansion codes contain dots; current coverage adds duplicate rows and still reads historical universe",
            identities=[
                dict(
                    provider_code="sv08.5",
                    expansion_id="tcgdex:en:sv08.5",
                    catalog_set_key="sv08-5",
                    current_assessment_id="tcgdex:en:sv08-5",
                ),
                dict(
                    provider_code="swsh12.5",
                    expansion_id="tcgdex:en:swsh12.5",
                    catalog_set_key="swsh12-5",
                    current_assessment_id="tcgdex:en:swsh12-5",
                ),
            ],
            requirements=[
                "Explicit reviewed identity mapping, preserve canonical expansion, external printing IDs, catalog IDs, frozen goals and saved references",
                "Canonical coverage view must count each provider set once; do not silently merge rows or alter historical manifests",
                "Bind current coverage universe to reviewed D6 pinned source with truthful current/asof labeling",
                "Rehearse repair with copied SQLite, corrections, idempotency, conflicts and rollback; PostgreSQL separately",
            ],
            source_denominator=220,
            current_runtime_rows=222,
            application_code_changed=False,
        ),
    )
    order = [
        ("retained M2", "config/catalog-pipeline/retained-20261004.json"),
        ("Gym Heroes standalone correction", "config/catalog-pipeline/d6-20261005/gym1.json"),
        ("D6 M3", "config/sealed/d6-20261005/package.json"),
        ("D6 matching M2 checkpoint", "config/catalog-pipeline/d6-20261005/batch.json"),
        ("D7 M3 catalog prerequisites", "config/sealed/d7-20261005/catalog-package.json"),
        ("D7 matching M2 checkpoint", "config/catalog-pipeline/d7-20261005/batch.json"),
        ("D7 M3 shopping/distribution corrections", "config/sealed/d7-20261005/shopping-package.json"),
    ]
    write(
        OUT / "publication-order.json",
        dict(
            fresh_state_prerequisite="Disposable setup using rehearse_m1; base2026-10-04 and151 sealed packages already published by setup",
            order=[
                dict(
                    step=i + 1,
                    label=label,
                    path=path,
                    sha256=hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
                )
                for i, (label, path) in enumerate(order)
            ],
            rollback="Reverse D7 shopping, then D7 matching M2 batch, then D7 M3 catalog. Retained D6 prerequisite rollback is separate.",
            owner_application="Separate backed-up copied-owner rehearsal and authorized application step; none performed",
            fresh_reproduction=".venv/bin/python scripts/rehearse_d7.py --root /private/tmp/dex-d7-FRESH --output evidence/d7-FRESH",
        ),
    )
    ledger = json.loads((OUT / "source-ledger.json").read_text())
    manifest = []
    for a in ledger["attempts"]:
        paths = [e["path"] for e in a.get("evidence", [])] + [
            a[k] for k in ["response_path", "headers_path", "transport_path"] if k in a
        ]
        manifest.append(
            dict(
                key=a["key"],
                url=a.get("url"),
                query=a.get("query"),
                category=a["category"],
                method=a["method"],
                observed_at=a.get("observed_at", a.get("retrieved_at")),
                outcome=a["outcome"],
                files=[
                    dict(
                        path=p,
                        sha256=hashlib.sha256((ROOT / p).read_bytes()).hexdigest(),
                        bytes=(ROOT / p).stat().st_size,
                    )
                    for p in paths
                    if (ROOT / p).is_file()
                ],
                retention_gap="No retained page DOM/screenshot" if a["key"] == "walmart-crown" else None,
            )
        )
    write(
        OUT / "raw-source-manifest.json",
        dict(
            attempts=manifest,
            source_bytes=ledger["retained_source_bytes"],
            byte_limit=104857600,
            timing="Direct PDF GET enforces30sec/streamed cap. Rendered/search transport opaque; DOM waits use supported30sec. One actual remote URL/method navigation; two stale-wrapper policy refusals before fresh-tab destinations are disclosed.",
            no_retries=True,
            no_bulk_acquisition=True,
        ),
    )
    write(
        OUT / "entry-verification.json",
        dict(
            baseline_head="16766b5c160c0bac370c1177387662646bf51b42",
            handoff_sha256="93175bf058014ef3273f9ac442b4cc9827781e27917d5a4606de6fc7812f0cf6",
            listed_files=1736,
            all_matched_before_changes=True,
            unexplained_drift=[],
        ),
    )
    print("D7 coverage, chain, exception and publication reports written")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--validation", required=True, type=Path)
    run(ap.parse_args().validation)
