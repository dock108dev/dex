"""Exact product applicability and per-target gaps over published evidence only."""

import json

from . import canonical_species, offer_filters


def applicability(records, selected):
    """Selected sealed printing IDs; frozen goals decide which IDs enter this projection."""
    members = {m["printing_id"]: m for m in records["memberships"].values()}
    result = {}
    for product in records["products"].values():
        packs = [p for p in records["packs"].values() if p["product_id"] == product["id"]]
        guaranteed = [g for g in records["guaranteed"].values() if g["product_id"] == product["id"]]
        documented = {p["expansion_id"] for p in packs if p["expansion_id"] and p["quantity"] is not None}
        possible = {
            records["printings"][pid]["species_id"]
            for pid in selected
            if members.get(pid, {}).get("status") == "booster"
            and records["printings"][pid]["expansion_id"] in documented
        }
        included = {
            records["printings"][g["printing_id"]]["species_id"]
            for g in guaranteed
            if g["printing_id"] in selected
        }
        result[product["id"]] = dict(
            possible_targets=sorted(possible),
            guaranteed_targets=sorted(included),
            possible_count=len(possible),
            guaranteed_count=len(included),
            distinct_target_count=len(possible | included),
        )
    return result


def coverage(records, now, indexed=None):
    """Exact all-251 chain IDs; absence is unresearched unless a source asserts it."""
    output = []
    catalog = {}
    for row in indexed or []:
        attrs = json.loads(row["attributes"]) if isinstance(row["attributes"], str) else row["attributes"]
        dex = attrs.get("pokemon_dex")
        if (
            attrs.get("game_key") == "pokemon"
            and attrs.get("supertype") == "Pokémon"
            and type(dex) is int
            and 1 <= dex <= 251
            and row.get("language") == "en"
            and row.get("publication_state", "published") == "published"
        ):
            catalog.setdefault(dex, []).append(row["id"])
    members = {m["printing_id"]: m for m in records["memberships"].values()}
    for dex in range(1, 252):
        pid = f"ndex:{dex:04}"
        printings = [
            p for p in records["printings"].values() if p["species_id"] == pid and p["language"] == "en"
        ]
        selected = {p["id"] for p in printings}
        products = applicability(records, selected)
        compatible = {k: v for k, v in products.items() if v["distinct_target_count"]}
        expansions = {p["expansion_id"] for p in printings}
        candidates = {p["product_id"] for p in records["packs"].values() if p["expansion_id"] in expansions}
        candidates.update(
            g["product_id"] for g in records["guaranteed"].values() if g["printing_id"] in selected
        )
        offers = []
        for offer in records["offers"].values():
            if offer["product_id"] not in candidates:
                continue
            history = sorted(
                (o for o in records["observations"].values() if o["offer_id"] == offer["id"]),
                key=offer_filters.observation_key,
            )
            latest = history[0] if history else None
            offers.append(
                dict(
                    id=offer["id"],
                    product_id=offer["product_id"],
                    observation_id=latest["id"] if latest else None,
                    eligibility=offer_filters.eligibility(
                        offer,
                        latest,
                        dict(records["products"][offer["product_id"]], **products[offer["product_id"]]),
                        records["sources"],
                        now,
                    ),
                )
            )
        gaps = []
        if not printings:
            gaps.append("sealed-printing-bridge-unresolved" if catalog.get(dex) else "printing-unresearched")
        if any(members.get(p["id"], {}).get("status", "unknown") == "unknown" for p in printings):
            gaps.append("distribution-unresolved")
        if not compatible:
            gaps.append("documented-product-unresearched")
        if not offers:
            gaps.append("seller-offer-unresearched")
        if not any(o["eligibility"]["recommendation_eligible"] for o in offers):
            gaps.append("current-eligible-offer-unverified")
        output.append(
            dict(
                dex=dex,
                name=canonical_species.registry()[dex]["name"],
                printing_ids=sorted(selected),
                catalog_printing_ids=sorted(catalog.get(dex, [])),
                distribution={p["id"]: members.get(p["id"], {}).get("status", "unknown") for p in printings},
                products=compatible,
                indexed_product_candidates=sorted(candidates),
                offers=offers,
                gaps=gaps,
                researched_absence=False,
            )
        )
    return output
