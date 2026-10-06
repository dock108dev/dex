"""Retained rendered-source shopping delta; no network or app changes."""

import json

from prepare_d7 import OUT, ROOT, write

from pokemon_hunter.beta.catalog_imports import fingerprint


def run():
    ledger = json.loads((OUT / "source-ledger.json").read_text())
    attempts = {a["key"]: a for a in ledger["attempts"]}
    prior = json.loads((ROOT / "config/sealed/d6-20261005/package.json").read_text())
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
    p.update(schema_version="dex-sealed-v1", provider="pokemon-public-reviewed", version="d7-shopping-v1")
    before = []

    def source(key, authority, supports):
        a = attempts[key]
        file = (
            next(e for e in a.get("evidence", []) if e["path"].endswith(".txt"))
            if "evidence" in a
            else {"sha256": a["sha256"]}
        )
        sid = "d7:" + key
        p["sources"].append(
            dict(
                id=sid,
                provider="pokemon" if authority.startswith("official") else "bestbuy",
                url=a["url"],
                retrieved_at=a.get("observed_at", a.get("retrieved_at")),
                sha256=file["sha256"],
                language="en",
                market="US",
                authority=authority,
                status="usable",
                subjects=[],
                supports=supports,
                rights="Retained public text, checklist and page screenshot research evidence; no bulk card artwork redistribution",
                note="Original rendered observation. UTC dates and individual text/screenshot hashes retained in D7 source ledger.",
            )
        )
        return sid

    def subjects(sid, *ids):
        s = next(s for s in p["sources"] if s["id"] == sid)
        s["subjects"].extend(x for x in ids if x not in s["subjects"])

    def correction(kind, old, new):
        before.append(dict(kind=kind, id=old["id"], before_sha256=fingerprint(old), before=old))
        p[kind].append(new)
        p["corrections"].append(
            dict(
                kind=kind,
                id=old["id"],
                before_sha256=fingerprint(old),
                reason="D7 newly applicable official evidence; preserve identity and earlier sources",
            )
        )

    sc = source("official-crown-etb", "official-product", ["product-identity", "product-contents"])
    ss = source("official-stellar-bundle", "official-product", ["product-identity", "product-contents"])
    sp = source("official-prismatic-bundle", "official-product", ["product-identity", "product-contents"])
    sd = source("prismatic-checklist", "official-card", ["printing-identity", "booster-membership"])
    foil = {13, 14, 22, 23, 28, 29, 30, 33, 34, 59, 60, 64, 75, 76, 78, 82, 146, 149, 153, 155, 161, 167, 179}
    normal = {1, 2, 3, 18, 19, 20, 21, 24, 47, 48, 61, 62, 63, 74, 77, 79, 81}
    indexed = {r["id"]: r for r in prior["printings"]}
    for old in prior["memberships"]:
        r = indexed[old["printing_id"]]
        if r["expansion_id"] != "tcgdex:en:sv08.5":
            continue
        v = json.loads(r["variant"]) if r["variant"] else {}
        if set(v) != {"type"}:
            continue
        n = int(r["number"])
        if not ((n in foil and v["type"] == "holo") or (n in normal and v["type"] == "normal")):
            continue
        new = dict(old, status="booster", sources=old["sources"] + [sd])
        correction("memberships", old, new)
        subjects(sd, new["id"], r["id"])
    # Existing Target identity remains distinct from the different Best Buy UPC.
    old = prior["products"][0]
    new = dict(
        old, sources=old["sources"] + [ss], contents="complete", total_packs=6, guaranteed_cards_known=True
    )
    correction("products", old, new)
    subjects(ss, new["id"])
    old = prior["packs"][0]
    new = dict(old, sources=old["sources"] + [ss], quantity=6)
    correction("packs", old, new)
    subjects(ss, new["id"])
    crown = "pokemon:us:crown-zenith-etb:bestbuy6527309"
    prism = "pokemon:us:prismatic-bundle:196214112544"
    for pid, name, sku, version, total, typ, sid, eid in [
        (
            crown,
            "Pokémon TCG: Crown Zenith Elite Trainer Box",
            "BestBuy:6527309;Model:290-87147",
            "US-English-standard-2023-retail",
            10,
            "elite-trainer-box",
            sc,
            "tcgdex:en:swsh12.5",
        ),
        (
            prism,
            "Pokémon TCG: Scarlet & Violet—Prismatic Evolutions Booster Bundle",
            "UPC:196214112544;Model:10-10025-101",
            "US-English-2025-standard-bundle",
            6,
            "booster-bundle",
            sp,
            "tcgdex:en:sv08.5",
        ),
    ]:
        p["products"].append(
            dict(
                id=pid,
                sources=[sid],
                name=name,
                sku=sku,
                version=version,
                market="US",
                language="en",
                product_type=typ,
                contents="complete",
                total_packs=total,
                guaranteed_cards_known=True,
            )
        )
        packid = "d7:pack:" + ("crown" if pid == crown else "prismatic")
        p["packs"].append(dict(id=packid, sources=[sid], product_id=pid, expansion_id=eid, quantity=total))
        subjects(sid, pid, packid)
    p["sources"][0]["note"] += (
        " Standard ETB only, not Pokémon Center Plus. Official ten packs and one etched foil Lucario VSTAR promo are independently documented. Lucario #448 is outside beta; its guaranteed inclusion is retained separately in guaranteed-components.json and contributes zero #001–251 guaranteed targets."
    )
    next(s for s in p["sources"] if s["id"] == ss)["note"] += (
        " Applies to original Target US-English standard bundle design; retained UPC820650858550 is the Target identity, not asserted by the official page. Six expansion packs expressly documented; no guaranteed Pokémon card stated. BestBuy UPC820650878558 remains a separate unresolved version below."
    )
    next(s for s in p["sources"] if s["id"] == sp)["note"] += (
        " Official six expansion packs expressly documented. Public product image/name and English packaging match observed model10-10025-101/UPC196214112544; retailer owns these identifiers. No guaranteed Pokémon card stated."
    )
    next(s for s in p["sources"] if s["id"] == sd)["note"] += (
        " Official US gallery links to this exact CDN PDF; full page visually reviewed with standard black versus foil red legend. Only matching plain normal/holo #001–251 printings corrected; reverse, Poké Ball, Master Ball, cosmos and stamps remain unknown."
    )
    # Exact different UPC retained without asserting that official contents apply to this version.
    other = "pokemon:us:stellar-crown-bundle:820650878558"
    p["products"].append(
        dict(
            id=other,
            sources=[],
            name="Pokémon TCG: Stellar Crown 6pk Booster Bundle",
            sku="UPC:820650878558;Model:190-87855",
            version="US-English-BestBuy-version-unresolved",
            market="US",
            language="en",
            product_type="booster-bundle",
            contents="unknown",
            total_packs=None,
            guaranteed_cards_known=False,
        )
    )
    p["packs"].append(
        dict(
            id="d7:pack:stellar-bestbuy",
            sources=[],
            product_id=other,
            expansion_id="tcgdex:en:sv07",
            quantity=None,
        )
    )
    rows = [
        ("bestbuy-crown", crown, "bestbuy:6527309:d7", None, "unknown", "out-of-stock", None),
        ("bestbuy-stellar", other, "bestbuy:6588397:d7", None, "unknown", "out-of-stock", None),
        (
            "bestbuy-prismatic",
            prism,
            "bestbuy:10734203:card-dog-tcg:d7",
            "CARD DOG TCG",
            "marketplace",
            "unknown",
            10500,
        ),
    ]
    for key, pid, oid, seller, kind, stock, price in rows:
        sid = source(key, "retailer", ["product-identity", "offer-observation"])
        a = attempts[key]
        obsid = oid + ":" + a["observed_at"].replace("-", "").replace(":", "").replace(".", "")
        p["offers"].append(
            dict(
                id=oid,
                sources=[sid],
                product_id=pid,
                retailer="Best Buy",
                seller=seller,
                seller_kind=kind,
                market="US",
                currency="USD",
                url=a["actual_url"],
            )
        )
        note = "Rendered listing expressly says no longer available in new condition; price, actual seller and shipping unknown."
        if key == "bestbuy-prismatic":
            note = "Actual seller CARD DOG TCG, marketplace, new offer USD105.00, active Add to cart and high-demand notice. Stock remains unknown: account required and site-selected shipping08869/location confirmation prevent an unqualified availability claim. No account/login/location change or cart interaction. Shipping charge, tax, delivery date and owner delivery eligibility unknown."
        p["observations"].append(
            dict(
                id=obsid,
                sources=[sid],
                offer_id=oid,
                checked_at=a["observed_at"],
                stock=stock,
                price_minor=price,
                shipping_minor=None,
                note=note,
            )
        )
        subjects(sid, pid, oid, obsid)
        if pid == other:
            p["products"][-1]["sources"] = [sid]
            p["packs"][-1]["sources"] = [sid]
            subjects(sid, "d7:pack:stellar-bestbuy")
    write(ROOT / "config/sealed/d7-20261005/shopping-package.json", p)
    write(OUT / "shopping-correction-before.json", before)
    write(
        OUT / "guaranteed-components.json",
        dict(
            product_id=crown,
            source=sc,
            components=[
                dict(
                    name="Lucario VSTAR etched foil promo",
                    quantity=1,
                    canonical_dex=448,
                    beta_scope="outside-251",
                    exact_printing="unresolved; no above-251 card acquisition",
                    qualifying_guaranteed_targets=0,
                )
            ],
            bundles=dict(
                prismatic="No guaranteed Pokémon card stated in official six-pack description",
                stellar="No guaranteed Pokémon card stated in official six-pack contents list",
            ),
        ),
    )
    write(
        OUT / "distribution-review.json",
        dict(
            new_confirmed_standard_relationships=len(p["memberships"]),
            species=len({indexed[m["printing_id"]]["species_id"] for m in p["memberships"]}),
            checklist=attempts["prismatic-checklist"]["sha256"],
            review="Self-review of official full-page legend and numbered names; not independent review",
            memberships=p["memberships"],
            unknown_variants="Reverse, ball treatments, cosmos, stamps not inferred",
        ),
    )
    print(
        "Shopping products",
        len(p["products"]),
        "documented",
        3,
        "identified sellers",
        1,
        "eligible offers",
        0,
        "new distributions",
        len(p["memberships"]),
    )


if __name__ == "__main__":
    run()
