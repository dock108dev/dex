"""Exact public seller observations; unknowns remain unknown and history is additive."""

import json

from acquire_d8 import OUT, ROOT, write


def run():
    ledger = json.loads((OUT / "source-ledger.json").read_text())
    attempts = {a["key"]: a for a in ledger["attempts"]}
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
    p.update(schema_version="dex-sealed-v1", provider="pokemon-public-reviewed", version="d8-shopping-v1")
    crown = "pokemon:us:crown-zenith-etb:bestbuy6527309"
    prism = "pokemon:us:prismatic-bundle:196214112544"
    stellar = "pokemon:us:stellar-crown-bundle:820650858550"
    other = "pokemon:us:stellar-crown-bundle:820650878558"
    data = [
        (
            "bestbuy-crown-rendered",
            crown,
            "Best Buy",
            None,
            "unknown",
            "out-of-stock",
            None,
            "Model290-87147 / SKU6527309; explicitly no longer available in new condition. Price, actual seller and fulfillment unresolved. Default store hint is not owner applicability.",
        ),
        (
            "bestbuy-prismatic",
            prism,
            "Best Buy",
            "CARD DOG TCG",
            "marketplace",
            "unknown",
            None,
            "Model10-10025-101 / SKU10734203; expressly sold and shipped by CARD DOG TCG. Current rendered capture supplies no item price or stock; never copy prior USD105 or search-review prices. Shipping, tax and delivery unknown. AI review/Q&A ignored.",
        ),
        (
            "bestbuy-stellar",
            other,
            "Best Buy",
            None,
            "unknown",
            "out-of-stock",
            None,
            "Model190-87855 / SKU6588397; no longer available in new condition. UPC820650878558 is retained historical identity, not newly exposed. Contents remain unresolved and separate from Target UPC820650858550.",
        ),
        (
            "token-prismatic",
            prism,
            "TokenMTG",
            "TokenMTG",
            "direct",
            "in-stock",
            12000,
            "Exact barcode196214112544. Public primary-retailer sealed set listing says 7 in stock, USD120 Excl.VAT, free shop pickup; retained raw HTML and supplemental rendered capture agree. Merchant Token/TokenMTG in Edgewater MD verified on public contact page. No marketplace. Explicit used/rip selection absent; factory-sealed condition not separately stated beyond sealed category. Fulfillment party not separately named. Shipping price, tax, destination eligibility, dates and any delivered total unknown; no checkout or location input. No verified backend availability attestation.",
        ),
        (
            "salt-prismatic",
            prism,
            "Salt City Games",
            "Salt City Games",
            "direct",
            "out-of-stock",
            8499,
            "Exact UPC196214112544 / PUI10-10025-101. Sold out. Banner says free shipping over USD75 and item free shipping available, while shipping is calculated at checkout; no unconditional charge or delivered total inferred. Pickup availability failed; no refresh. Tax unknown. New/sealed condition not separately supplied.",
        ),
        (
            "target-stellar-rendered",
            stellar,
            "Target",
            None,
            "unknown",
            "unknown",
            None,
            "Exact retained URL TCIN91619942. Fresh static/rendered product title and generic cart control expose no seller, price or stock. Site default location hints were not entered by operator and do not prove owner availability. UPC820650858550 remains retained identity; no new UPC claim. Search snippet USD27.99/out of stock is discovery only. Shipping/tax unknown.",
        ),
        (
            "retreat-stellar",
            stellar,
            "RetreatCost",
            "RetreatCost",
            "direct",
            "out-of-stock",
            2699,
            "Exact UPC820650858550, explicit Out of stock, USD26.99, maximum two units. Public US merchant footer references Bucks County PA. New/sealed condition and fulfillment party not separately named. Shipping, tax and delivery unknown.",
        ),
    ]
    sidecar = []
    for key, pid, retailer, seller, kind, stock, price, note in data:
        a = attempts[key]
        sid = "d8:" + key
        oid = "d8:offer:" + key
        obid = "d8:observation:" + key
        assert a["sha256"] and a["outcome"] not in ["failed", "denial-or-challenge"]
        p["sources"].append(
            dict(
                id=sid,
                provider=retailer.lower().replace(" ", "-"),
                url=a["url"],
                retrieved_at=a["observed_at"],
                sha256=a["sha256"],
                language="en",
                market="US",
                authority="retailer",
                status="usable",
                subjects=[pid, oid, obid],
                supports=["product-identity", "offer-observation"],
                rights="Public text retained for dated research; no artwork redistribution",
                note=note,
            )
        )
        p["offers"].append(
            dict(
                id=oid,
                sources=[sid],
                product_id=pid,
                retailer=retailer,
                seller=seller,
                seller_kind=kind,
                market="US",
                currency="USD",
                url=a["url"],
            )
        )
        p["observations"].append(
            dict(
                id=obid,
                sources=[sid],
                offer_id=oid,
                checked_at=a["observed_at"],
                stock=stock,
                price_minor=price,
                shipping_minor=None,
                note=note,
            )
        )
        sidecar.append(
            dict(
                product_id=pid,
                offer_id=oid,
                observation_id=obid,
                url=a["url"],
                source_sha256=a["sha256"],
                observed_at=a["observed_at"],
                actual_seller=seller,
                fulfillment_party="CARD DOG TCG" if key == "bestbuy-prismatic" else None,
                stock_wording={
                    "token-prismatic": "7 in stock",
                    "salt-prismatic": "Sold out",
                    "retreat-stellar": "Out of stock",
                    "bestbuy-crown-rendered": "This item is no longer available in new condition.",
                    "bestbuy-stellar": "This item is no longer available in new condition.",
                }.get(key),
                price_minor=price,
                currency="USD",
                shipping_minor=None,
                tax_minor=None,
                sealed_condition="Sealed product category; no separate factory-sealed statement"
                if key == "token-prismatic"
                else "No longer available new"
                if stock == "out-of-stock" and key.startswith("bestbuy")
                else "not expressly supplied",
                delivery_mode="shipping/pickup controls; eligibility unknown"
                if key in ["token-prismatic", "target-stellar-rendered"]
                else "unknown",
                location_constraints=note,
            )
        )
    # Supplementary exact static and rendered source hashes do not refresh original observations.
    sidecar.append(
        dict(
            candidate_only=True,
            url=attempts["evolve-crown"]["url"],
            source_sha256=attempts["evolve-crown"]["sha256"],
            observed_at=attempts["evolve-crown"]["observed_at"],
            retailer="Evolve Card Shop",
            actual_seller="Evolve Card Shop",
            stock_wording="13 in stock",
            price_minor=43000,
            currency="USD",
            shipping_minor=None,
            tax_minor=None,
            sealed_condition="not expressly supplied",
            reason="Title/ten packs/Lucario match standard design, but exact SKU/UPC/model unresolved. Not merged or imported as the Best Buy product. Free-shipping threshold does not establish destination applicability.",
        )
    )
    write(ROOT / "config/sealed/d8-20261006/shopping-package.json", p)
    write(OUT / "seller-observations.json", sidecar)
    write(
        OUT / "shopping-exceptions.json",
        dict(
            unmatched_candidates=[x for x in sidecar if x.get("candidate_only")],
            partial=[
                "Target stock/price/actual seller",
                "Best Buy Prismatic current stock/price",
                "Best Buy Stellar official contents",
                "Explicit factory-sealed condition and destination applicability remain limited",
            ],
            schema="Shipping/tax/modes/fulfillment/condition not separate schema fields: full source note plus sidecar preserve unknowns. No importer bypass.",
        ),
    )
    print("D8 dated observations", len(p["observations"]))


if __name__ == "__main__":
    run()
