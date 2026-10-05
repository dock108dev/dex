"""Offline 151 detail/checklist reconciliation. Retained source bytes required; no I/O to providers."""

import argparse
import copy
import hashlib
import json
import re
import subprocess
from pathlib import Path

from pokemon_hunter.beta import catalog_imports as cat
from pokemon_hunter.beta import sealed_catalog as sealed


def prepare(sources, baseline, output):
    index = json.loads((sources / "index.json").read_text())
    for row in index.values():
        if hashlib.sha256((sources / row["file"]).read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError("Retained source hash mismatch")
    checklist = subprocess.check_output(
        ["pdftotext", "-layout", str(sources / "official-checklist.raw"), "-"], text=True
    )
    # Column-aware split; the energy symbol is graphical, so #207 is reviewed explicitly.
    official = {}
    for line in checklist.splitlines():
        for number, name in re.findall(r"(\d{3}) ■ (.*?)(?=\s{3,}|$)", line):
            official[number] = name.strip()
    if set(official) != {f"{i:03}" for i in range(1, 208)}:
        raise ValueError("Official 207-number checklist not reproduced")
    source_manifest = json.loads((sources / "retained-hashes.json").read_text())
    for filename, expected in source_manifest.items():
        if hashlib.sha256((sources / filename).read_bytes()).hexdigest() != expected:
            raise ValueError("Retained acquisition input changed: " + filename)
    p = copy.deepcopy(json.loads(baseline.read_text()))
    p["version"] = "2026-10-04-151-v2"
    p["provider"] = "reviewed-d1-e1b"
    old_printing = p["printings"][0]
    p["printings"] = []
    p["memberships"] = []
    p["mappings"] = [m for m in p["mappings"] if m["kind"] != "printings"]
    official_source = next(s for s in p["sources"] if s["id"] == "official-checklist")
    # New source assertion version retains the same official PDF bytes and retrieval time.
    official_source = {
        **official_source,
        "id": "official-checklist:151-review-v2",
        "subjects": [],
        "note": "All 207 numbered standard-set rows visually reviewed against foil/rarity legend. Parallel/reverse, stamps and alternate foils are not established as booster pulls by this PDF.",
    }
    p["sources"].append(official_source)
    rows = []
    links = []
    cards = []

    def names(s):
        return s.replace("’", "'").replace("♀", " female").replace("♂", " male").casefold()

    briefs = json.loads((sources / "set151.raw").read_text())["cards"]
    if len(briefs) != 207 or {r["localId"] for r in briefs} != set(official):
        raise ValueError("Provider checklist numbers do not reconcile all 207 official identities")
    for brief in briefs:
        n = brief["localId"]
        key = "scyther" if n == "123" else brief["id"]
        if key not in index:
            rows.append(
                dict(
                    number=n,
                    state="unresolved",
                    gaps=["Provider detail unavailable; source stopped"],
                    official_name=official[n],
                )
            )
            continue
        detail = json.loads((sources / index[key]["file"]).read_text())
        gaps = []
        if detail["id"] != brief["id"] or detail["localId"] != n or detail["set"]["id"] != "sv03.5":
            raise ValueError("Provider identity mismatch")
        if n != "207" and names(official[n]) != names(detail["name"]):
            raise ValueError("Official/provider name conflict: " + n)
        category = {"Pokemon": "pokemon", "Trainer": "trainer", "Energy": "energy"}[detail["category"]]
        dex = detail.get("dexId", [])
        if category == "pokemon" and (len(dex) != 1 or not 1 <= dex[0] <= 151):
            raise ValueError("Unresolved canonical mapping " + n)
        if category != "pokemon" and dex:
            raise ValueError("Trainer/Energy cannot map to species")
        species = f"ndex:{dex[0]:04}" if dex else None
        expected_category = (
            "pokemon"
            if int(n) <= 151 or 166 <= int(n) <= 193 or 198 <= int(n) <= 202 or n == "205"
            else "energy"
            if n == "207"
            else "trainer"
        )
        if category != expected_category:
            raise ValueError("Official/category conflict " + n)
        if category == "pokemon":
            canonical = next(s["name"] for s in p["species"] if s["id"] == species)
            if names(detail["name"].removesuffix(" ex")) != names(canonical):
                raise ValueError("Canonical name conflict " + n)
        sid = "detail:" + brief["id"]
        source = dict(
            id=sid,
            provider="tcgdex",
            url=index[key]["url"],
            retrieved_at=index[key]["retrieved_at"],
            sha256=index[key]["sha256"],
            language="en",
            market=None,
            authority="provider",
            status="usable",
            subjects=[],
            supports=["printing-identity"],
            rights="TCGdex MIT metadata; excludes artwork, rules and third-party prices",
            note="Detailed provider variants; source listing does not establish booster eligibility for reverse/stamped/alternate-foil records.",
        )
        p["sources"].append(source)
        variants = detail.get("variants_detailed", [])
        seen = set()
        for v in variants:
            clean = {k: value for k, value in v.items() if k not in {"thirdParty", "pricing"}}
            base = set(clean) <= {"type", "size", "variantId"} and clean.get("size") == "standard"
            variant = v["type"] if base else v["type"] + ":" + v["variantId"]
            if variant in seen:
                raise ValueError("Repeated detailed variant")
            seen.add(variant)
            pid = "tcgdex:en:" + brief["id"] + ":" + variant
            standard = base and v["type"] == (
                "normal" if detail["rarity"] in {"Common", "Uncommon"} else "holo"
            )
            finish = {"normal": "nonfoil", "holo": "holo", "reverse": "reverse-holo", "metal": "metal"}[
                v["type"]
            ]
            r = dict(
                id=pid,
                sources=[sid, official_source["id"]],
                expansion_id="tcgdex:en:sv03.5",
                species_id=species,
                name=detail["name"],
                number=n + "/165",
                language="en",
                rarity=detail["rarity"],
                finish=finish,
                variant=variant,
                category=category,
            )
            mid = "pool:en:" + brief["id"] + ":" + variant
            if pid == old_printing["id"]:
                r = old_printing
                mid = "pool:en:sv03.5-123:normal"
                membership = dict(
                    id=mid,
                    sources=["official-checklist"],
                    printing_id=pid,
                    expansion_id=r["expansion_id"],
                    status="booster",
                )
            else:
                membership = dict(
                    id=mid,
                    sources=[official_source["id"], sid],
                    printing_id=pid,
                    expansion_id=r["expansion_id"],
                    status="booster" if standard else "unknown",
                )
            p["printings"].append(r)
            p["memberships"].append(membership)
            source["subjects"].append(pid)
            official_source["subjects"] += [pid, mid]
            external = brief["id"] + ":" + variant
            p["mappings"].append(
                dict(
                    provider="tcgdex", language="en", kind="printings", external_id=external, internal_id=pid
                )
            )
            links.append(dict(printing_id=pid, external_id=external))
            cards.append(
                dict(
                    external_id=external,
                    number=r["number"],
                    name=r["name"],
                    metadata=dict(
                        pokemon_dex=dex[0] if dex else None,
                        dex_eligible=category == "pokemon",
                        supertype={"pokemon": "Pokémon", "trainer": "Trainer", "energy": "Energy"}[category],
                        rarity=r["rarity"],
                    ),
                    edition="unlimited",
                    finish=finish,
                    variant=variant,
                )
            )
            if not standard:
                gaps.append(
                    dict(
                        printing_id=pid,
                        detail_variant=clean,
                        issue="Provider variant retained; official booster/promo/deck status unresolved",
                    )
                )
        rows.append(
            dict(
                number=n,
                provider_id=brief["id"],
                official_name=official[n],
                provider_name=detail["name"],
                category=category,
                species_id=species,
                rarity=detail["rarity"],
                state="numbered-identity-reconciled",
                gaps=gaps,
                sources=[sid, official_source["id"]],
                variant_count=len(variants),
            )
        )
    # A second immutable observation supplements the earlier unknown observation.
    web = json.loads((sources / "web-observations.json").read_text())
    offer = p["offers"][0]
    obsid = offer["id"] + ":e1b-check"
    s = copy.deepcopy(next(s for s in p["sources"] if s["id"] == "target"))
    s.update(
        id="target:e1b-check",
        retrieved_at=web["checked_at"],
        sha256=hashlib.sha256((sources / "web-observations.json").read_bytes()).hexdigest(),
        subjects=[obsid],
        note="Rendered page product section: exact TCIN/UPC match, $27.99 out-of-stock. Seller/direct vs marketplace and shipping unknown. Retained extracted observation, not complete HTML.",
    )
    p["sources"].append(s)
    p["observations"].append(
        dict(
            id=obsid,
            sources=[s["id"]],
            offer_id=offer["id"],
            checked_at=web["checked_at"],
            stock="out-of-stock",
            price_minor=2799,
            shipping_minor=None,
            note=web["time_precision"] + "; explicit out-of-stock; seller unknown; no purchasability claim",
        )
    )
    p["coverage"][0]["gaps"] = [
        g for g in p["coverage"][0]["gaps"] if "only one" not in g and "Target seller/stock/price" not in g
    ] + [
        "151 numbered identities reconciled; reverse/stamped/alternate-foil booster status unresolved. All-era printing coverage remains incomplete.",
        "Target dated out-of-stock USD 27.99; seller and shipping unknown. Official product attempts access-error/iframe-only; exact product contents remain unknown.",
    ]
    p["coverage"][0]["id"] = "universe:en:151-v2"
    bridge = dict(
        schema_version="dex-catalog-v1",
        game="pokemon",
        set_key="sv03-5",
        set_name="Scarlet & Violet—151",
        language="en",
        aliases=["sv03.5"],
        provider="tcgdex",
        version=p["version"],
        source_url=index["set151"]["url"],
        source_sha256=index["set151"]["sha256"],
        metadata_permission="TCGdex MIT metadata; detailed source hashes in sealed package",
        image_permission="not-included",
        coverage="catalog-entries",
        expected_count=len(cards),
        cards=cards,
    )
    cat.validate(bridge)
    p["bridges"] = [dict(expansion_id="tcgdex:en:sv03.5", package=bridge, links=links)]
    sealed.validate(p)
    output.mkdir(parents=True, exist_ok=True)

    def save(name, data):
        (output / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")

    save("package.json", p)
    save(
        "reconciliation.json",
        dict(
            checklist_identities=207,
            reconciled=sum(r["state"] == "numbered-identity-reconciled" for r in rows),
            physical_provider_variants=len(p["printings"]),
            booster_memberships=sum(r["status"] == "booster" for r in p["memberships"]),
            rows=sorted(rows, key=lambda r: r["number"]),
            evidence_class="Real retained official checklist and provider details; operator source review; independent chain review open",
        ),
    )
    missing = json.loads((baseline.parent / "missing-18.json").read_text())
    missing["version"] = p["version"]
    for r in missing["rows"]:
        matches = [x for x in p["printings"] if x["species_id"] == r["species_id"]]
        r.update(
            state="printing-and-standard-booster-researched",
            normalized_printings=[x["id"] for x in matches],
            gaps=[
                "Official product contents unknown; no current purchasable offer; independent Scyther chain review and owner acceptance open"
            ],
            sources=sorted({s for x in matches for s in x["sources"]}),
            account_ownership="unchanged; research seed only",
        )
    save("missing-18.json", missing)
    save(
        "source-index.json",
        dict(
            provider=index,
            acquisition_attempts=json.loads((sources / "attempts.json").read_text()),
            web=web,
            baseline_package_sha256=hashlib.sha256(baseline.read_bytes()).hexdigest(),
        ),
    )
    save(
        "hashes.json",
        {
            f.name: hashlib.sha256(f.read_bytes()).hexdigest()
            for f in sorted(output.iterdir())
            if f.name != "hashes.json"
        },
    )
    print(
        json.dumps(
            dict(
                identities=len(rows),
                variants=len(cards),
                booster=sum(r["status"] == "booster" for r in p["memberships"]),
            )
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.sources, args.baseline, args.output)
