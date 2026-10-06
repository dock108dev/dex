"""Prepare selected verified cached literals, preserving provider variants and exact IDs."""

import copy
import hashlib
import json
import tarfile

from prepare_d7 import english_variants, parse
from prepare_d9 import OUT, ROOT, write

from pokemon_hunter.beta.catalog_imports import fingerprint

PIN = "99c994747cf7519a3e51166cc932de79a88bd4b3"
DEST = ROOT / "config/catalog-pipeline/d9-20261006"
SEALED = ROOT / "config/sealed/d9-20261006"
ARCHIVE_HASH = "1431e3be180cc5c8e491e480fd78b2b721155622372591d9f82bfb8aa83a6cce"


def run():
    archive = ROOT / "evidence/d6-20261005/raw/tcgdex-archive.raw"
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == ARCHIVE_HASH
    source = json.loads((ROOT / "evidence/d6-20261005/source-ledger.json").read_text())
    bulk = next(a for a in source["attempts"] if a.get("key") == "tcgdex-archive")
    assert bulk["sha256"] == ARCHIVE_HASH and PIN in bulk["url"]
    selection = json.loads((OUT / "selection-plan.json").read_text())
    codes = {a["set_id"].split(":")[-1] for a in selection["sets"]}
    universe = json.loads((ROOT / "evidence/d7-20261005/universe.json").read_text())
    us = {s["provider_set_id"]: s for s in universe["sets"]}
    indexed = [
        r
        for r in json.loads((ROOT / "evidence/d7-20261005/target-printings.json").read_text())
        if r["provider_set_id"] in codes and r["medium"] == "physical"
    ]
    assert len(indexed) == selection["expected_numbered_targets"] <= 1500 and len(codes) <= 20
    manifest = json.loads((ROOT / "evidence/d7-20261005/archive-file-manifest.json").read_text())
    rawhashes = {}
    rawrecords = {}
    with tarfile.open(archive) as tar:
        wanted = {r["file"] for r in indexed}
        for m in tar.getmembers():
            path = m.name.split("/", 1)[-1]
            if path in wanted:
                raw = tar.extractfile(m).read()
                h = hashlib.sha256(raw).hexdigest()
                assert h == manifest["files"][path]["sha256"]
                rawhashes[path] = h
                rawrecords[path] = parse(raw.decode())
    exceptions = []
    mapping = []
    assessments = []
    summary = []
    for code in sorted(codes):
        rows = [r for r in indexed if r["provider_set_id"] == code]
        se = us[code]
        cards = []
        numbered = {}
        for r in rows:
            c = rawrecords[r["file"]]
            assert c["category"] == "Pokemon" and c["dexId"] == [r["species"]]
            variants, excluded = english_variants(c.get("variants", []))
            if excluded:
                exceptions.append(
                    dict(
                        numbered_id=r["external_id"],
                        reason="excluded-or-unresolved-variant-shape",
                        raw=excluded,
                    )
                )
            if not variants and not excluded:
                variants = [None]
                exceptions.append(
                    dict(
                        numbered_id=r["external_id"],
                        reason="provider-variant-unspecified",
                        note="Null physical attributes, not an inferred normal printing",
                    )
                )
            seen = set()
            for v in variants:
                variant = (
                    json.dumps(
                        {k: x for k, x in v.items() if k != "thirdParty"},
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    if v
                    else None
                )
                suffix = hashlib.sha256(variant.encode()).hexdigest()[:16] if variant else "unspecified"
                eid = r["external_id"] + ":" + suffix
                if eid in seen:
                    exceptions.append(
                        dict(numbered_id=r["external_id"], reason="identical-variant-coalesced")
                    )
                    continue
                seen.add(eid)
                edition = "1st-edition" if v and "1st-edition" in v.get("stamp", []) else None
                cards.append(
                    dict(
                        external_id=eid,
                        number=r["number"],
                        name=c["name"]["en"],
                        finish=v.get("type") if v else None,
                        variant=variant,
                        edition=edition,
                        metadata=dict(
                            pokemon_dex=r["species"],
                            dex_eligible=True,
                            supertype="Pokémon",
                            rarity=c.get("rarity") or "Unknown",
                        ),
                    )
                )
                numbered[eid] = r["external_id"]
                mapping.append(
                    dict(
                        external_id=eid,
                        numbered_id=r["external_id"],
                        species=r["species"],
                        set_id=se["id"],
                        file=r["file"],
                        file_sha256=rawhashes[r["file"]],
                        raw_variant=v,
                        distribution="unknown",
                    )
                )
        p = dict(
            schema_version="dex-catalog-v1",
            game="pokemon",
            provider="tcgdex",
            version="d9-" + PIN[:12] + "-v1",
            set_key=code.replace(".", "-"),
            set_name=se["name"],
            language="en",
            aliases=[],
            source_url=bulk["url"],
            source_sha256=ARCHIVE_HASH,
            metadata_permission="MIT; Copyright (c) 2021 TCGdex; retained evidence/d7-20261005/TCGDEX_LICENSE.txt",
            image_permission="not-included",
            coverage="partial",
            expected_count=max(se["expected_full_set_count"], len(cards)),
            cards=cards,
        )
        a = dict(
            set_id=se["id"],
            language="en",
            era=se["era"],
            medium="physical",
            release_status=se["release_status"],
            source_url=bulk["url"],
            source_time=bulk["retrieved_at"],
            source_sha256=ARCHIVE_HASH,
            evidence_class="retained-real-source",
            enumeration_complete=False,
            enumerated_ids=sorted({r["external_id"] for r in rows}),
            numbered_mappings=numbered,
            expected_target_count=len(rows),
            package=p,
        )
        assessments.append(a)
        write(DEST / (p["set_key"] + ".json"), p)
        summary.append(
            dict(
                set_id=se["id"],
                name=se["name"],
                era=se["era"],
                numbered_targets=len(rows),
                package_rows=len(cards),
                supplied_english_variants=sum(len(english_variants(r["variants"])[0]) for r in rows),
                source_enumeration_complete=se["enumeration_complete"],
                application_assessment="partial",
                distribution="unknown",
                physical_variant_completeness="unknown",
            )
        )
    batch = dict(
        schema_version="dex-target-batch-v1",
        version="d9-" + PIN[:12] + "-v1",
        mode="checkpoint",
        sets=assessments,
    )
    write(DEST / "batch.json", batch)
    base = {}
    paths = [
        "config/sealed/2026-10-04/package.json",
        "config/sealed/2026-10-04-151/package.json",
        "config/sealed/d6-20261005/package.json",
        "config/sealed/d7-20261005/catalog-package.json",
        "config/sealed/d7-20261005/shopping-package.json",
        "config/sealed/m4-20261006/inclusion-package.json",
    ]
    for path in paths:
        for kind, rows in json.loads((ROOT / path).read_text()).items():
            if isinstance(rows, list):
                for row in rows:
                    if isinstance(row, dict) and "id" in row:
                        base.setdefault(kind, {})[row["id"]] = row
    sealed = {
        k: []
        for k in [
            "sources",
            "species",
            "expansions",
            "printings",
            "memberships",
            "products",
            "packs",
            "guaranteed",
            "offers",
            "observations",
            "coverage",
            "mappings",
            "bridges",
            "corrections",
        ]
    }
    sealed.update(
        schema_version="dex-sealed-v1", provider="tcgdex", version="d9-catalog-sealed-" + PIN[:12] + "-v1"
    )
    sid = "d9:bulk"
    source = dict(
        id=sid,
        provider="tcgdex",
        url=bulk["url"],
        retrieved_at=bulk["retrieved_at"],
        sha256=ARCHIVE_HASH,
        language="en",
        market="US",
        authority="provider",
        status="usable",
        subjects=[],
        supports=["printing-identity", "universe"],
        rights="MIT metadata; no artwork",
        note="Pinned static source; English US-market release applicability not independently established. Physical variant/distribution gaps remain explicit.",
    )
    sealed["sources"].append(source)
    before = []
    for a in assessments:
        p = a["package"]
        eid = a["set_id"]
        ex = copy.deepcopy(base["expansions"][eid])
        before.append(
            dict(kind="expansions", id=eid, before_sha256=fingerprint(ex), before=copy.deepcopy(ex))
        )
        ex["sources"].append(sid)
        sealed["expansions"].append(ex)
        sealed["corrections"].append(
            dict(
                kind="expansions",
                id=eid,
                before_sha256=before[-1]["before_sha256"],
                reason="Add original pinned-source provenance without changing canonical expansion identity",
            )
        )
        source["subjects"].append(eid)
        sealed["mappings"].append(
            dict(
                provider="tcgdex", language="en", kind="expansions", external_id=p["set_key"], internal_id=eid
            )
        )
        links = []
        for c in p["cards"]:
            rid = "tcgdex:en:" + c["external_id"]
            mid = "pool:en:" + c["external_id"]
            sealed["printings"].append(
                dict(
                    id=rid,
                    sources=[sid],
                    expansion_id=eid,
                    species_id=f"ndex:{c['metadata']['pokemon_dex']:04}",
                    name=c["name"],
                    number=c["number"],
                    language="en",
                    rarity=c["metadata"]["rarity"],
                    finish=c["finish"],
                    variant=c["variant"],
                    category="pokemon",
                )
            )
            sealed["memberships"].append(
                dict(id=mid, sources=[sid], printing_id=rid, expansion_id=eid, status="unknown")
            )
            source["subjects"] += [rid, mid]
            sealed["mappings"].append(
                dict(
                    provider="tcgdex",
                    language="en",
                    kind="printings",
                    external_id=c["external_id"],
                    internal_id=rid,
                )
            )
            links.append(dict(printing_id=rid, external_id=c["external_id"]))
        # Preserve unsupported edition records in catalog; never discard variants to satisfy bridge.
        if all(c["edition"] in [None, "unlimited"] for c in p["cards"]):
            sealed["bridges"].append(dict(expansion_id=eid, package=p, links=links))
        else:
            exceptions.append(
                dict(
                    set_id=eid,
                    reason="bridge-edition-gate",
                    repair="Retain full catalog package; exact engineering handoff required",
                )
            )
    # Existing sealed-format assessment preserves dotted canonical IDs without adding an alias.
    for a in assessments:
        if "." not in a["set_id"].split(":")[-1]:
            continue
        eid = a["set_id"]
        sub = {k: [] for k in sealed if isinstance(sealed[k], list)}
        sub.update(
            schema_version="dex-sealed-v1",
            provider="tcgdex",
            version="d9-assessment-" + eid.split(":")[-1].replace(".", "-") + "-v1",
        )
        sub["sources"] = copy.deepcopy(sealed["sources"])
        sub["expansions"] = [copy.deepcopy(e) for e in sealed["expansions"] if e["id"] == eid]
        sub["printings"] = [copy.deepcopy(e) for e in sealed["printings"] if e["expansion_id"] == eid]
        sub["memberships"] = [copy.deepcopy(e) for e in sealed["memberships"] if e["expansion_id"] == eid]
        sub["mappings"] = [
            copy.deepcopy(e)
            for e in sealed["mappings"]
            if e["internal_id"] == eid or e["internal_id"] in {r["id"] for r in sub["printings"]}
        ]
        a["numbered_mappings"] = {"tcgdex:en:" + k: v for k, v in a["numbered_mappings"].items()}
        a["package"] = sub
    write(DEST / "batch.json", batch)
    write(
        OUT / "assessment-format-review.json",
        dict(
            note="Use existing dex-sealed-v1 assessment for canonical dotted sv04.5; matching main catalog prerequisites provide bridges. No punctuation alias, ID rename, schema change or variant omission.",
            sealed_assessments=[
                a["set_id"] for a in assessments if a["package"]["schema_version"] == "dex-sealed-v1"
            ],
        ),
    )
    write(SEALED / "catalog-package.json", sealed)
    write(OUT / "catalog-correction-before.json", before)
    write(
        OUT / "tranche-review.json",
        dict(
            commit=PIN,
            source_time=bulk["retrieved_at"],
            archive_sha256=ARCHIVE_HASH,
            numbered_targets=len(indexed),
            supplied_english_variants=sum(s["supplied_english_variants"] for s in summary),
            package_rows=len(mapping),
            sets=summary,
        ),
    )
    write(
        OUT / "archive-file-manifest.json",
        dict(commit=PIN, archive_sha256=ARCHIVE_HASH, selected_target_file_hashes=rawhashes),
    )
    write(OUT / "target-printings.json", indexed)
    write(OUT / "provider-mappings.json", mapping)
    write(OUT / "exceptions.json", exceptions)
    write(
        OUT / "distribution-gaps.json",
        [
            dict(
                set_id=a["set_id"],
                numbered_targets=a["expected_target_count"],
                all_supplied_relationships="unknown; cached metadata alone is not booster evidence",
            )
            for a in assessments
        ],
    )
    write(OUT / "mapping-gaps.json", [dict(set_id=us[c]["id"], gaps=us[c]["gaps"]) for c in sorted(codes)])
    print(
        json.dumps(
            dict(
                sets=len(assessments),
                numbered_targets=len(indexed),
                supplied_variants=sum(s["supplied_english_variants"] for s in summary),
                package_rows=len(mapping),
                bridges=len(sealed["bridges"]),
            )
        )
    )


if __name__ == "__main__":
    run()
