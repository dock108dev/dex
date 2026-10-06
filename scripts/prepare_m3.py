"""Build clearly synthetic product cases; no acquisition or current offer claim."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def package():
    p = {
        k: []
        for k in (
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
        )
    }
    p.update(schema_version="dex-sealed-v1", provider="m3-synthetic", version="m3-synthetic-v1")
    ex = "m3:en:johto"
    printing = "m3:en:kingdra:normal"
    p["expansions"] = [
        dict(
            id=ex,
            sources=["m3-card"],
            name="Synthetic Johto distribution",
            language="en",
            series="neo",
            medium="physical",
            expected_printings=1,
        )
    ]
    p["printings"] = [
        dict(
            id=printing,
            sources=["m3-card"],
            expansion_id=ex,
            species_id="ndex:0230",
            name="Synthetic Kingdra",
            number="1",
            language="en",
            rarity="Rare",
            finish="normal",
            variant="normal",
            category="pokemon",
        )
    ]
    p["memberships"] = [
        dict(
            id="m3:kingdra:pool", sources=["m3-card"], printing_id=printing, expansion_id=ex, status="booster"
        )
    ]
    p["mappings"] = [
        dict(provider="m3-synthetic", language="en", kind="expansions", external_id="johto", internal_id=ex),
        dict(
            provider="m3-synthetic",
            language="en",
            kind="printings",
            external_id="kingdra",
            internal_id=printing,
        ),
    ]
    bridge = dict(
        schema_version="dex-catalog-v1",
        game="pokemon",
        set_key="johto",
        set_name="Synthetic Johto distribution",
        language="en",
        aliases=[],
        provider="m3-synthetic",
        version="m3-synthetic-v1",
        source_url="https://example.test/m3/card",
        source_sha256=hashlib.sha256(b"synthetic-card").hexdigest(),
        metadata_permission="Synthetic qualification only",
        image_permission="not-included",
        coverage="catalog-entries",
        expected_count=1,
        cards=[
            dict(
                external_id="kingdra",
                number="1",
                name="Synthetic Kingdra",
                edition=None,
                finish="normal",
                variant="normal",
                metadata=dict(pokemon_dex=230, dex_eligible=True, supertype="Pokémon", rarity="Rare"),
            )
        ],
    )
    p["bridges"] = [
        dict(expansion_id=ex, package=bridge, links=[dict(printing_id=printing, external_id="kingdra")])
    ]
    for code, contents, total in [
        ("mixed", "mixed-known", 4),
        ("guaranteed", "complete", 0),
        ("assortment", "unknown", None),
    ]:
        pid = "m3:product:" + code
        p["products"].append(
            dict(
                id=pid,
                sources=["m3-product"],
                name="Synthetic " + code + " product",
                sku="SYNTHETIC-" + code,
                version="fixture-v1",
                market="US",
                language="en",
                product_type="deck" if total == 0 else "box",
                contents=contents,
                total_packs=total,
                guaranteed_cards_known=contents != "unknown",
            )
        )
        if code == "mixed":
            for suffix, e, q in [("151", "tcgdex:en:sv03.5", 3), ("johto", ex, 1)]:
                p["packs"].append(
                    dict(
                        id="m3:pack:" + suffix,
                        sources=["m3-product"],
                        product_id=pid,
                        expansion_id=e,
                        quantity=q,
                    )
                )
        if code == "assortment":
            p["packs"].append(
                dict(
                    id="m3:pack:unknown",
                    sources=["m3-product"],
                    product_id=pid,
                    expansion_id="tcgdex:en:sv03.5",
                    quantity=None,
                )
            )
            p["packs"].append(
                dict(
                    id="m3:pack:random",
                    sources=["m3-product"],
                    product_id=pid,
                    expansion_id=None,
                    quantity=None,
                )
            )
        if code in {"mixed", "guaranteed"}:
            p["guaranteed"].append(
                dict(
                    id="m3:guaranteed:" + code,
                    sources=["m3-product"],
                    product_id=pid,
                    printing_id=printing,
                    quantity=1,
                )
            )
    for code, kind, stock, time, price in [
        ("fresh", "direct", "in-stock", "2026-10-06T03:00:00+00:00", 2500),
        ("market", "marketplace", "in-stock", "2026-10-06T03:00:00+00:00", 2000),
        ("stale", "direct", "in-stock", "2026-10-01T12:00:00+00:00", 1500),
        ("unavailable", "direct", "out-of-stock", "2026-10-06T03:00:00+00:00", 2500),
        ("unknown", "unknown", "unknown", "2026-10-06T03:00:00+00:00", None),
    ]:
        oid = "m3:offer:" + code
        p["offers"].append(
            dict(
                id=oid,
                sources=["m3-retailer"],
                product_id="m3:product:mixed",
                retailer="Synthetic retailer",
                seller=None if kind == "unknown" else "Synthetic " + kind + " seller",
                seller_kind=kind,
                market="US",
                currency="USD",
                url="https://example.test/m3/" + code,
            )
        )
        p["observations"].append(
            dict(
                id=oid + ":observation",
                sources=["m3-retailer"],
                offer_id=oid,
                checked_at=time,
                stock=stock,
                price_minor=price,
                shipping_minor=500 if code == "market" else None,
                note="Synthetic behavior only; original fixture time, no live stock",
            )
        )
    for sid, authority, kinds, supports in [
        (
            "m3-card",
            "official-card",
            ["expansions", "printings", "memberships"],
            ["printing-identity", "distribution-membership"],
        ),
        (
            "m3-product",
            "official-product",
            ["products", "packs", "guaranteed"],
            ["product-identity", "product-contents"],
        ),
        ("m3-retailer", "retailer", ["offers", "observations"], ["offer-observation"]),
    ]:
        p["sources"].append(
            dict(
                id=sid,
                provider="m3-synthetic",
                url="https://example.test/m3/" + sid,
                retrieved_at="2026-10-06T03:00:00+00:00",
                sha256=hashlib.sha256(("synthetic-" + sid).encode()).hexdigest(),
                language="en",
                market="US",
                authority=authority,
                status="usable",
                subjects=[r["id"] for k in kinds for r in p[k]],
                supports=supports,
                rights="Synthetic engineering fixture only",
                note="SYNTHETIC: fabricated qualification input; not official or seller evidence",
            )
        )
    return p


if __name__ == "__main__":
    path = ROOT / "config/sealed/m3-synthetic/package.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(package(), indent=2) + "\n")
    print("Wrote clearly synthetic qualification package")
