"""Create sourced M3 delta from pinned files and visually reviewed official checklist."""

import copy
import json

from prepare_d7 import DEST, OUT, PIN, ROOT, write


def run():
    ledger = json.loads((ROOT / "evidence/d6-20261005/source-ledger.json").read_text())
    attempts = {a.get("key"): a for a in ledger["attempts"]}
    old = json.loads((ROOT / "config/sealed/2026-10-04/package.json").read_text())
    p = {
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
    p.update(
        schema_version="dex-sealed-v1", provider="tcgdex", version="d7-catalog-sealed-" + PIN[:12] + "-v1"
    )
    batch = json.loads((DEST / "batch.json").read_text())
    indexed = {r["external_id"]: r for r in json.loads((OUT / "target-printings.json").read_text())}
    universe = {s["provider_set_id"]: s for s in json.loads((OUT / "universe.json").read_text())["sets"]}
    before = []
    from pokemon_hunter.beta.catalog_imports import fingerprint

    sourceid = "d7:bulk"
    p["sources"].append(
        dict(
            id=sourceid,
            provider="tcgdex",
            url=attempts["tcgdex-archive"]["url"],
            retrieved_at=attempts["tcgdex-archive"]["retrieved_at"],
            sha256=attempts["tcgdex-archive"]["sha256"],
            language="en",
            market="US",
            authority="provider",
            status="usable",
            subjects=[],
            supports=["printing-identity", "universe"],
            rights="MIT; Copyright (c) 2021 TCGdex; no artwork redistribution",
            note="Pinned "
            + PIN
            + "; exact file identities and extracted variants retained in archive-file-manifest, target-printings and provider-mappings. Distribution is independently reviewed.",
        )
    )
    for a in batch["sets"]:
        bridge = copy.deepcopy(a["package"])
        code = bridge["set_key"].replace("sv08-5", "sv08.5").replace("swsh12-5", "swsh12.5")
        eid = "tcgdex:en:" + code
        ex = next((e for e in old["expansions"] if e["id"] == eid), None)
        if ex:
            ex = copy.deepcopy(ex)
            before.append(
                dict(kind="expansions", id=eid, before_sha256=fingerprint(ex), before=copy.deepcopy(ex))
            )
            ex["sources"].append(sourceid)
            p["corrections"].append(
                dict(
                    kind="expansions",
                    id=eid,
                    before_sha256=before[-1]["before_sha256"],
                    reason="Pinned bulk snapshot adds enumeration provenance while preserving published expansion identity and prior sources",
                )
            )
        else:
            ex = dict(
                id=eid,
                sources=[sourceid],
                name=bridge["set_name"],
                language="en",
                series=a["era"],
                medium="physical",
                expected_printings=universe[code]["expected_full_set_count"],
            )
        p["expansions"].append(ex)
        p["sources"][0]["subjects"].append(eid)
        p["mappings"].append(
            dict(
                provider="tcgdex",
                language="en",
                kind="expansions",
                external_id=bridge["set_key"],
                internal_id=eid,
            )
        )
        links = []
        for card in bridge["cards"]:
            rid = "tcgdex:en:" + card["external_id"]
            numbered = a["numbered_mappings"][card["external_id"]]
            assert numbered in indexed
            printing = dict(
                id=rid,
                sources=[sourceid],
                expansion_id=eid,
                species_id=f"ndex:{card['metadata']['pokemon_dex']:04}",
                name=card["name"],
                number=card["number"],
                language="en",
                rarity=card["metadata"]["rarity"],
                finish=card["finish"],
                variant=card["variant"],
                category="pokemon",
            )
            membership = dict(
                id="pool:en:" + card["external_id"],
                sources=[sourceid],
                printing_id=rid,
                expansion_id=eid,
                status="unknown",
            )
            p["printings"].append(printing)
            p["memberships"].append(membership)
            p["sources"][0]["subjects"] += [rid, membership["id"]]
            p["mappings"].append(
                dict(
                    provider="tcgdex",
                    language="en",
                    kind="printings",
                    external_id=card["external_id"],
                    internal_id=rid,
                )
            )
            links.append(dict(printing_id=rid, external_id=card["external_id"]))
        if not any(c["edition"] not in [None, "unlimited"] for c in bridge["cards"]):
            p["bridges"].append(dict(expansion_id=eid, package=bridge, links=links))
    write(ROOT / "config/sealed/d7-20261005/catalog-package.json", p)
    write(OUT / "catalog-correction-before.json", before)
    print("D7 sealed catalog", len(p["printings"]), "bridges", len(p["bridges"]))


if __name__ == "__main__":
    run()
