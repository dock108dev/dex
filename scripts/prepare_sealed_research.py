"""Normalize retained D1/E1 responses offline. Never fetches sources or writes ownership.

Usage: python scripts/prepare_sealed_research.py --sources PRIVATE_DIR --output config/sealed/2026-10-04
Raw responses (including provider prices and denial pages) stay outside public packages.
"""

import argparse
import hashlib
import json
from pathlib import Path


def prepare(root, output):
    index = json.loads((root / "index.json").read_text())
    for row in index.values():
        if row.get("file") and (root / row["file"]).exists():
            if hashlib.sha256((root / row["file"]).read_bytes()).hexdigest() != row["sha256"]:
                raise ValueError("Retained source hash mismatch: " + row["file"])
    species_raw = json.loads((root / "species-normalized.json").read_text())
    # Verify derived species rows against official server-rendered data, including forms.
    import re

    page = (root / "sg.raw").read_text()
    official = None
    for encoded in re.findall(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)', page):
        decoded = json.loads(encoded)
        if '"initialPokemons":' in decoded:
            start = decoded.index('"initialPokemons":') + len('"initialPokemons":')
            all_forms = json.JSONDecoder().raw_decode(decoded[start:])[0]
            official = [r for r in all_forms if r["zukan_sub_id"] == 0]
            break
    if official != species_raw or {int(r["zukan_id"]) for r in official} != set(range(1, 1026)):
        raise ValueError("Official species registry is incomplete or normalized rows changed")
    printing = json.loads((root / "scyther.raw").read_text())
    if (
        printing["id"] != "sv03.5-123"
        or printing["dexId"] != [123]
        or printing["rarity"] != "Uncommon"
        or not printing["variants"]["normal"]
        or printing["set"]["id"] != "sv03.5"
    ):
        raise ValueError("Scyther provider evidence changed; explicit review required")
    if "820650853210" not in (root / "target.raw").read_text():
        raise ValueError("Retailer product identity absent")
    sets = json.loads((root / "sets.raw").read_text())
    series = {}
    conflicts = []
    for summary in json.loads((root / "series.raw").read_text()):
        path = root / ("series-" + summary["id"] + ".raw")
        if not path.is_file() or index["series-" + summary["id"]].get("status") != 200:
            continue
        for s in json.loads(path.read_text())["sets"]:
            if s["id"] in series and series[s["id"]] != summary["id"]:
                conflicts.append(s["id"])
            series[s["id"]] = summary["id"]
    sources = []

    def source(key, authority, language, market, subjects, supports, status="usable", note=""):
        r = index[key]
        sources.append(
            dict(
                id=key,
                provider="tcgdex"
                if authority == "provider"
                else "pokemon"
                if authority.startswith("official")
                else "target",
                url=r["url"],
                retrieved_at=r["retrieved_at"],
                sha256=r["sha256"],
                language=language,
                market=market,
                authority=authority,
                status=status,
                subjects=subjects,
                supports=supports,
                rights="MIT metadata only; no artwork, rules text or third-party prices"
                if authority == "provider"
                else "Referenced factual metadata only; raw source evidence retained privately",
                note=note,
            )
        )

    ids = [f"ndex:{int(r['zukan_id']):04}" for r in official]
    source(
        "sg",
        "official-species",
        "en",
        None,
        ids,
        ["species-identity"],
        note="English official Singapore registry; base forms only. Forms remain distinct from canonical species. Not a US shopping catalog.",
    )
    exids = ["tcgdex:en:" + s["id"] for s in sets]
    source(
        "sets",
        "provider",
        "en",
        None,
        exids,
        ["universe"],
        note="Provider snapshot includes digital Pocket and unreviewed release status; not proof of booster membership or complete official physical universe.",
    )
    for summary in json.loads((root / "series.raw").read_text()):
        key = "series-" + summary["id"]
        if key in index and index[key].get("status") == 200:
            source(
                key,
                "provider",
                "en",
                None,
                ["tcgdex:en:" + k for k, v in series.items() if v == summary["id"]],
                ["universe"],
            )
    pid = "tcgdex:en:sv03.5-123:normal"
    mid = "pool:en:sv03.5-123:normal"
    product = "upc:820650853210:us:en:2023"
    pack = product + ":packs"
    offer = "target:88897904:seller-unknown"
    obs = offer + ":20261004"
    source(
        "scyther",
        "provider",
        "en",
        None,
        [pid],
        ["printing-identity"],
        note="dexId [123], Uncommon, normal/reverse variants. Raw response contains excluded third-party price data; only normal variant imported.",
    )
    source("set151", "provider", "en", None, ["tcgdex:en:sv03.5"], ["universe"])
    source(
        "official-checklist",
        "official-card",
        "en",
        None,
        [pid, mid],
        ["printing-identity", "booster-membership"],
        note="Official 151 checklist: #123 Scyther, uncommon diamond, standard set nonfoil and parallel foil columns; standard pool membership reviewed independently of provider list.",
    )
    source(
        "official-product",
        "official-product",
        "en",
        "US",
        [product, pack],
        ["product-identity"],
        status="access-denied",
        note="HTTP 200 challenge page, no usable official contents. No bypass/retry. Official indexed expansion lists Booster Bundle existence; quantities unverified.",
    )
    source(
        "target",
        "retailer",
        "en",
        "US",
        [product, offer, obs],
        ["product-identity", "offer-observation"],
        note="TCIN 88897904 / UPC 820650853210, retailer description claims six 151 packs. Seller, purchasability, stock, price and shipping not exposed in retained public response; all unknown. Retail description is not official contents proof.",
    )
    species = [
        dict(id=i, sources=["sg"], dex=int(r["zukan_id"]), name=r["pokemon_name"])
        for i, r in zip(ids, official, strict=True)
    ]
    expansions = []
    for s in sets:
        era = series.get(s["id"])
        expansions.append(
            dict(
                id="tcgdex:en:" + s["id"],
                sources=["sets"] + (["series-" + era] if era else []),
                name=s["name"],
                language="en",
                series=era,
                medium="digital" if era == "tcgp" else "physical" if era else "unknown",
                expected_printings=s.get("cardCount", {}).get("total"),
            )
        )
    universe = [r["id"] for r in expansions if r["medium"] == "physical"]
    gaps = [
        "Official US expansion registry returned an access challenge; provider physical universe not officially reconciled.",
        "Release status unreviewed except Scyther 151 (2023-09-22 provider date); intended universe may include planned sets.",
        "All-era printing import incomplete: only one Scyther normal printing in this E1 package.",
        "Other languages are expansion scope, not imported.",
        "Official product quantities and guaranteed inclusions inaccessible; retailer claim of six packs is unqualified.",
        "Target seller/stock/price/shipping unknown; no current purchasable offer established.",
    ]
    mappings = [
        dict(
            provider="pokemon-national-dex",
            language="en",
            kind="species",
            external_id=str(r["dex"]),
            internal_id=r["id"],
        )
        for r in species
    ]
    mappings += [
        dict(
            provider="tcgdex",
            language="en",
            kind="expansions",
            external_id=s["id"],
            internal_id="tcgdex:en:" + s["id"],
        )
        for s in sets
    ]
    mappings += [
        dict(
            provider="tcgdex",
            language="en",
            kind="printings",
            external_id="sv03.5-123:normal",
            internal_id=pid,
        ),
        dict(
            provider="upc",
            language="en",
            kind="products",
            external_id="820650853210:US:2023",
            internal_id=product,
        ),
        dict(
            provider="target",
            language="en",
            kind="offers",
            external_id="88897904:seller-unknown",
            internal_id=offer,
        ),
    ]
    package = dict(
        schema_version="dex-sealed-v1",
        provider="reviewed-d1",
        version="2026-10-04-v1",
        sources=sources,
        species=species,
        expansions=expansions,
        printings=[
            dict(
                id=pid,
                sources=["scyther", "official-checklist"],
                expansion_id="tcgdex:en:sv03.5",
                species_id="ndex:0123",
                name="Scyther",
                number="123/165",
                language="en",
                rarity="Uncommon",
                finish="nonfoil",
                variant="normal",
                category="pokemon",
            )
        ],
        memberships=[
            dict(
                id=mid,
                sources=["official-checklist"],
                printing_id=pid,
                expansion_id="tcgdex:en:sv03.5",
                status="booster",
            )
        ],
        products=[
            dict(
                id=product,
                sources=["target", "official-product"],
                name="Pokémon TCG: Scarlet & Violet—151 Booster Bundle",
                sku="UPC:820650853210",
                version="2023-US-English-single-bundle",
                market="US",
                language="en",
                product_type="booster-bundle",
                contents="unknown",
                total_packs=None,
                guaranteed_cards_known=False,
            )
        ],
        packs=[
            dict(
                id=pack,
                sources=["target", "official-product"],
                product_id=product,
                expansion_id="tcgdex:en:sv03.5",
                quantity=None,
            )
        ],
        guaranteed=[],
        offers=[
            dict(
                id=offer,
                sources=["target"],
                product_id=product,
                retailer="Target",
                seller=None,
                seller_kind="unknown",
                market="US",
                currency="USD",
                url=index["target"]["url"],
            )
        ],
        observations=[
            dict(
                id=obs,
                sources=["target"],
                offer_id=offer,
                checked_at=index["target"]["retrieved_at"],
                stock="unknown",
                price_minor=None,
                shipping_minor=None,
                note="Public product identity verified; fulfillment/seller/stock/price unavailable. No purchase attempt.",
            )
        ],
        coverage=[
            dict(
                id="universe:en:20261004",
                sources=["sets", "sg"],
                language="en",
                market="US",
                intended_expansions=universe,
                species_count=len(species),
                gaps=gaps,
            )
        ],
        mappings=mappings,
    )
    from pokemon_hunter.beta.sealed_catalog import validate

    validate(package)
    output.mkdir(parents=True, exist_ok=True)

    def save(name, data):
        (output / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")

    save("package.json", package)
    shipped = {}
    for path in (Path(__file__).resolve().parents[1] / "config/catalog-imports").glob("**/*.json"):
        data = json.loads(path.read_text())
        if data.get("provider") == "tcgdex" and data.get("language") == "en" and data.get("cards"):
            shipped[data["set_key"]] = dict(
                package=str(path.relative_to(Path(__file__).resolve().parents[1])), count=len(data["cards"])
            )
    save(
        "universe.json",
        dict(
            version=package["version"],
            language="en",
            market="US",
            species_registry_count=len(species),
            provider_set_count=len(sets),
            physical_set_count=len(universe),
            digital_sets=[r["id"] for r in expansions if r["medium"] == "digital"],
            unknown_medium=[r["id"] for r in expansions if r["medium"] == "unknown"],
            series_conflicts=conflicts,
            existing_shipped_packages=shipped,
            existing_shipped_printings=sum(r["count"] for r in shipped.values()),
            sets_without_shipped_packages=[
                s["id"] for s in sets if "tcgdex:en:" + s["id"] in universe and s["id"] not in shipped
            ],
            new_e1_printings=1,
            sets=expansions,
            gaps=gaps,
        ),
    )
    missing = [
        (3, "Venusaur"),
        (17, "Pidgeotto"),
        (18, "Pidgeot"),
        (36, "Clefable"),
        (65, "Alakazam"),
        (94, "Gengar"),
        (97, "Hypno"),
        (113, "Chansey"),
        (115, "Kangaskhan"),
        (122, "Mr. Mime"),
        (123, "Scyther"),
        (130, "Gyarados"),
        (131, "Lapras"),
        (134, "Vaporeon"),
        (135, "Jolteon"),
        (136, "Flareon"),
        (144, "Articuno"),
        (146, "Moltres"),
    ]
    save(
        "missing-18.json",
        dict(
            version=package["version"],
            seed="Original-app ledger as specified by owner; not authenticated inventory",
            rows=[
                dict(
                    species_id=f"ndex:{n:04}",
                    name=name,
                    state="partially-researched",
                    sources=["sg", "official-checklist"]
                    + (["scyther", "target", "official-product"] if n == 123 else []),
                    printing_candidate=f"151 #{n:03}" + (" ex" if n in [3, 65, 115] else ""),
                    imported_printing=pid if n == 123 else None,
                    gaps=[
                        "Official pack quantities/guaranteed inclusions unverified; seller/stock/price unknown; independent chain review pending"
                    ]
                    if n == 123
                    else [
                        "Checklist candidate only; rarity/variant, species mapping, booster membership, product/offer chain not individually normalized or reviewed"
                    ],
                )
                for n, name in missing
            ],
        ),
    )
    denied = {"species", "official-species", "official-sets", "official-card", "official-product", "pc-offer"}
    save(
        "source-index.json",
        {
            k: {
                **{kk: vv for kk, vv in r.items() if kk != "file"},
                "evidence_quality": "access-denied-challenge"
                if k in denied
                else "http-failure"
                if r.get("status") != 200
                else "retained-response",
            }
            for k, r in index.items()
        },
    )
    (output / "TCGDEX_LICENSE.txt").write_bytes((root / "license.raw").read_bytes())
    save(
        "hashes.json",
        {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(output.iterdir())
            if p.name != "hashes.json" and p.is_file()
        },
    )
    print(
        json.dumps(
            {
                "species": len(species),
                "sets": len(sets),
                "physical": len(universe),
                "existing_shipped_sets": len(shipped),
                "existing_shipped_printings": sum(r["count"] for r in shipped.values()),
                "output": str(output),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.sources, args.output)
