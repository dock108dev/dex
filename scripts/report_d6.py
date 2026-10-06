"""Reconcile retained evidence, provider conflicts and owner missing coverage."""

import csv
import hashlib
import json
import tarfile
from collections import Counter
from pathlib import Path

from prepare_d6 import OUT, ROOT, write


def run():
    primary = json.loads((OUT / "target-printings.json").read_text())
    universe = json.loads((OUT / "universe.json").read_text())
    tree = json.loads((OUT / "raw/tcgdex-tree.raw").read_text())
    assert not tree["truncated"]
    blobs = {r["path"]: r for r in tree["tree"] if r["type"] == "blob"}
    checked = []
    with tarfile.open(OUT / "raw/tcgdex-archive.raw") as t:
        for m in t.getmembers():
            if not m.isfile():
                continue
            path = m.name.split("/", 1)[-1]
            raw = t.extractfile(m).read()
            assert path in blobs, path
            gitsha = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
            assert gitsha == blobs[path]["sha"], path
            checked.append(path)
    assert set(checked) == set(blobs)
    write(
        OUT / "archive-integrity.json",
        dict(
            exact_commit=tree["sha"],
            file_count=len(checked),
            git_blob_hashes_match=True,
            archive_matches_complete_git_tree=True,
            file_extensions=dict(Counter(Path(p).suffix for p in checked)),
        ),
    )
    matches = []
    conflicts = []
    stats = []
    for code, secondary in [("swsh7", "swsh7"), ("sv08", "sv8"), ("hgss1", "hgss1"), ("gym2", "gym2")]:
        raw = json.loads((OUT / f"raw/secondary-{secondary}.raw").read_text())
        selected = {
            str(int(r["number"])) if r["number"].isdigit() else r["number"]: r
            for r in primary
            if r["provider_set_id"] == code
        }
        count = 0
        for r in raw:
            dex = r.get("nationalPokedexNumbers", [])
            if r.get("supertype") != "Pokémon" or not any(n <= 251 for n in dex):
                continue
            count += 1
            number = str(int(r["number"])) if r["number"].isdigit() else r["number"]
            p = selected.get(number)
            rec = dict(
                tcgdex_id=p["external_id"] if p else None,
                pokemontcg_id=r["id"],
                set=code,
                number=number,
                tcgdex_dex=[p["species"]] if p else None,
                secondary_dex=dex,
                tcgdex_name=p["name"] if p else None,
                secondary_name=r["name"],
            )
            if not p or dex != [p["species"]] or r["name"] != p["name"]:
                conflicts.append(rec)
            else:
                matches.append(rec)
        stats.append(dict(set=code, tcgdex_target_printings=len(selected), secondary_target_records=count))
    write(
        OUT / "secondary-crosscheck.json",
        dict(
            commit="39a26a144c8b6ef6c2fb17b2c29d0bb7121e3a11",
            scope="Four pinned historical JSON files; distinct provider identities preserved. Public downloading explicitly documented by README; no SPDX license found. No secondary-derived normalized publishing or artwork downloads.",
            sets=stats,
            matches=matches,
            conflicts=conflicts,
        ),
    )
    missing = list(
        csv.DictReader(
            (ROOT / "outputs/missing-90-pokemon-all-listed-packs-and-rarities.csv").open(encoding="utf-8-sig")
        )
    )
    assert len(missing) == 90
    ids = {int(r["Dex"]) for r in missing}
    assert sum(n <= 151 for n in ids) == 14
    species = json.loads((OUT / "species-coverage.json").read_text())
    dist = json.loads((OUT / "distribution-review.json").read_text())
    sealed = json.loads((ROOT / "config/sealed/d6-20261005/package.json").read_text())
    printings = {r["id"]: r for r in sealed["printings"]}
    boosted = Counter(int(printings[m["printing_id"]]["species_id"].split(":")[1]) for m in dist["booster"])
    imports = {r["species"]: [] for r in primary}
    for r in json.loads((OUT / "provider-mappings.json").read_text()):
        imports[r["species"]].append(r["external_id"])
    for s in species:
        n = s["pokemon_dex"]
        s.update(
            owned=n not in ids,
            region="Kanto" if n <= 151 else "Johto",
            missing=n in ids,
            importable_variant_records=len(imports.get(n, [])),
            confirmed_standard_booster_records=boosted[n],
            distribution="confirmed-standard-booster-and-unknown-other-printings"
            if boosted[n]
            else "unresearched",
            products="identity-only"
            if n
            in [
                int(r["species_id"].split(":")[1])
                for r in sealed["printings"]
                if r["expansion_id"] == "tcgdex:en:sv07"
            ]
            else "unresearched",
            current_offer="unverified",
            supported_absence=False,
        )
    write(OUT / "species-coverage.json", species)
    write(
        OUT / "current-missing.json",
        dict(
            ownership_source="outputs/my-have-dex-001-251-photo-reconciled.csv",
            missing_source="outputs/missing-90-pokemon-all-listed-packs-and-rarities.csv",
            kanto_owned=137,
            total_owned=161,
            kanto_missing=14,
            total_missing=90,
            rows=[r for r in species if r["missing"]],
        ),
    )
    ex = json.loads((OUT / "exceptions.json").read_text())
    queue = [
        dict(
            priority=1,
            reason="official-contents-access-denied",
            product="US English Stellar Crown Booster Bundle",
            next="New authorized source strategy or owner-retained official contents; no retry of closed hosts",
        ),
        dict(
            priority=1,
            reason="seller-price-stock-unverified",
            listing="Target 91619942",
            next="New authorized actual listing observation; preserve original unknown observation",
        ),
        dict(
            priority=2,
            reason="M2-complete-target-reconciliation",
            next="Bulk sidecar enumeration and target-only variant packages have different denominators; do not force complete publication coverage",
        ),
        dict(priority=2, reason="secondary-conflicts", count=len(conflicts)),
        dict(priority=3, reason="remaining-catalog-batches", count=205 - 10),
    ]
    queue += [dict(priority=3, **e) for e in ex]
    write(OUT / "exception-queue.json", queue)
    zero = [
        s["id"]
        for s in universe["sets"]
        if s["medium"] == "physical" and s["enumeration_complete"] and s["target_numbered_count"] == 0
    ]
    write(
        OUT / "set-coverage.json",
        dict(
            sets=universe["sets"],
            complete_source_enumerations=sum(s["enumeration_complete"] for s in universe["sets"]),
            physical_complete_source_enumerations=sum(
                s["enumeration_complete"] and s["medium"] == "physical" for s in universe["sets"]
            ),
            supported_zero_target_sets=zero,
            denominator="Provider file enumerations only; expected all-universe physical variant counts remain unknown",
        ),
    )
    print(
        json.dumps(
            dict(
                git_blobs=len(checked),
                secondary_matches=len(matches),
                secondary_conflicts=len(conflicts),
                missing=90,
                booster_targets=len(boosted),
                complete_physical=sum(
                    s["enumeration_complete"] and s["medium"] == "physical" for s in universe["sets"]
                ),
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    run()
