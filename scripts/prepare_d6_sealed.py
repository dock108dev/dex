"""Create sourced M3 delta from pinned files and visually reviewed official checklist."""

import copy
import json

from prepare_d6 import DEST, OUT, PIN, ROOT, write


def run():
    ledger = json.loads((OUT / "source-ledger.json").read_text())
    attempts = {a.get("key"): a for a in ledger["attempts"]}
    old = json.loads((ROOT / "config/sealed/2026-10-04-151/package.json").read_text())
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
    p.update(schema_version="dex-sealed-v1", provider="tcgdex", version="d6-sealed-" + PIN[:12] + "-v2")
    batch = json.loads((DEST / "batch.json").read_text())
    indexed = {r["external_id"]: r for r in json.loads((OUT / "target-printings.json").read_text())}
    universe = {s["provider_set_id"]: s for s in json.loads((OUT / "universe.json").read_text())["sets"]}
    before = []
    from pokemon_hunter.beta.catalog_imports import fingerprint

    sourceid = "d6:bulk"
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
    checklist = attempts["crown-checklist"]
    checkid = "d6:crown-checklist"
    p["sources"].append(
        dict(
            id=checkid,
            provider="pokemon",
            url=checklist["url"],
            retrieved_at=checklist["retrieved_at"],
            sha256=checklist["sha256"],
            language="en",
            market="US",
            authority="official-card",
            status="usable",
            subjects=[],
            supports=["printing-identity", "booster-membership"],
            rights="Official checklist retained as research evidence; no card artwork extracted",
            note="Visual review of full single page and legend. Standard black/foil red squares support matching plain normal/holo cards only. Parallel blue squares, stamped, jumbo and other variants remain unknown in this first distribution review.",
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
            v = json.loads(card["variant"]) if card["variant"] else None
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
            # Official checklist numbers verified below; standard foil for these plain source variants.
            if code == "swsh12.5" and v and set(v) == {"type"} and v["type"] in ["normal", "holo"]:
                num = int(card["number"])
                # Standard foil rows (red) from visual checklist; standard nonfoil rows black.
                foil = {18, 19, 20, 21, 59, 60, 107, 108}
                nonfoil = {1, 2, 3, 4, 6, 7, 8, 29, 30, 57, 58, 61, 68, 75, 84, 86, 106, 109}
                if num in (foil if v["type"] == "holo" else nonfoil):
                    membership["status"] = "booster"
                    membership["sources"].append(checkid)
                    printing["sources"].append(checkid)
                    p["sources"][1]["subjects"] += [rid, membership["id"]]
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
    # Exact static Target listing identity; no search-derived price/stock or invented seller.
    target = attempts["target-stellar"]
    sid = "d6:target-stellar"
    pid = "pokemon:us:stellar-crown-bundle:820650858550"
    offer = "target:91619942:d6"
    observation = offer + ":20261006T031602"
    p["sources"].append(
        dict(
            id=sid,
            provider="target",
            url=target["url"],
            retrieved_at=target["retrieved_at"],
            sha256=target["sha256"],
            language="en",
            market="US",
            authority="retailer",
            status="usable",
            subjects=[pid, "d6:stellar-pack", offer, observation],
            supports=["product-identity", "offer-observation"],
            rights="Retained public listing research observation",
            note="Static title and UPC identify exact US English Booster Bundle; dynamic seller, price and availability are absent in retained HTML. Search results are excluded. Default site location is not an owner delivery quote.",
        )
    )
    p["products"] = [
        dict(
            id=pid,
            sources=[sid],
            name="Pokémon TCG Scarlet & Violet—Stellar Crown Booster Bundle",
            sku="UPC:820650858550",
            version="US-English-2024-retailer-identity",
            market="US",
            language="en",
            product_type="booster-bundle",
            contents="unknown",
            total_packs=None,
            guaranteed_cards_known=False,
        )
    ]
    p["packs"] = [
        dict(
            id="d6:stellar-pack", sources=[sid], product_id=pid, expansion_id="tcgdex:en:sv07", quantity=None
        )
    ]
    p["offers"] = [
        dict(
            id=offer,
            sources=[sid],
            product_id=pid,
            retailer="Target",
            seller=None,
            seller_kind="unknown",
            market="US",
            currency="USD",
            url=target["url"],
        )
    ]
    p["observations"] = [
        dict(
            id=observation,
            sources=[sid],
            offer_id=offer,
            checked_at=target["retrieved_at"],
            stock="unknown",
            price_minor=None,
            shipping_minor=None,
            note="Original listing retrieval. Static identity only; dynamic price/stock/seller were not observed. Official contents inaccessible. No current purchasability established.",
        )
    ]
    write(ROOT / "config/sealed/d6-20261005/package.json", p)
    write(OUT / "sealed-correction-before.json", before)
    write(
        OUT / "distribution-review.json",
        dict(
            checklist_sha256=checklist["sha256"],
            visual_page="crown-checklist.png",
            booster=[m for m in p["memberships"] if m["status"] == "booster"],
            unknown=sum(m["status"] == "unknown" for m in p["memberships"]),
            confirmed_products=0,
            current_eligible_offers=0,
            prerequisite="Publish config/catalog-pipeline/retained-20261004.json using existing M2 services first; canonical species and expansion sources remain retained October 4 evidence",
        ),
    )
    print(
        "Sealed printings",
        len(p["printings"]),
        "confirmed booster",
        sum(m["status"] == "booster" for m in p["memberships"]),
    )


if __name__ == "__main__":
    run()
