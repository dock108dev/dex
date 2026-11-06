"""Deterministic catalog-only LV-02A manifest; never acquire prices or change the root."""

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from pokemon_hunter.beta import price_snapshot_contract as rules
from pokemon_hunter.beta import reference_inventory as inventory

SEED = "dex-lv02a-20261104-v1"
SETS = ("Base Set", "Jungle", "Fossil")


def manifest(entries):
    rows, denominators = [], []
    for name in SETS:
        candidates = [p for p in entries.values() if p["set_name"] == name]
        if len(candidates) < 20:
            raise ValueError("Pilot requires 20 catalog entries per selected set")

        def rank(p):
            return hashlib.sha256((SEED + ":" + p["id"]).encode()).hexdigest()

        candidates.sort(key=rank)
        chosen = []

        def add(p):
            if p not in chosen:
                chosen.append(p)

        if name == "Fossil":
            for number in ("10", "25"):
                matches = [p for p in candidates if p["name"] == "Lapras" and p["collector_number"] == number]
                if len(matches) != 1:
                    raise ValueError("Pilot Lapras catalog identity is absent or ambiguous")
                add(matches[0])
        variants = defaultdict(list)
        strata = defaultdict(list)
        for p in candidates:
            variants[tuple(p.get(k) or "" for k in ("edition", "finish", "variant"))].append(p)
            attrs = p["attributes"]
            strata[(attrs.get("supertype", "unknown"), attrs.get("rarity", "unknown"))].append(p)
        for key in sorted(variants):
            add(variants[key][0])
        while len(chosen) < 20:
            for key in sorted(strata):
                remaining = [p for p in strata[key] if p not in chosen]
                if remaining and len(chosen) < 20:
                    add(remaining[0])
        if len(chosen) != 20:
            raise ValueError("Variant strata exceed the predeclared pilot budget")
        denominators.append(dict(set_name=name, catalog_printings=len(candidates), selected=20))
        for p in chosen:
            rows.append(
                dict(
                    pilot_id=f"P{len(rows) + 1:02}",
                    printing_id=p["id"],
                    name=p["name"],
                    set_name=name,
                    identity={k: p.get(k) for k in rules.IDENTITY},
                    stratum={k: p["attributes"].get(k) for k in ("supertype", "rarity")},
                    unresolved_identity=[k for k in rules.IDENTITY if not p.get(k)],
                    source_match="not_reviewed_no_permitted_current_input",
                    eligible_reference=False,
                )
            )
    baskets = []
    for i, name in enumerate(SETS):
        selected = rows[i * 20 : (i + 1) * 20]
        for j, quantities in enumerate(((1, 2, 4, 1, 3), (1, 1, 1, 8, 12))):
            contents = [
                dict(pilot_id=p["pilot_id"], quantity=q)
                for p, q in zip(selected[j * 5 : j * 5 + 5], quantities)
            ]
            baskets.append(
                dict(
                    basket_id=f"B{i * 2 + j + 1}",
                    set_name=name,
                    contents=contents,
                    stated_quantity=sum(quantities),
                    priced_quantity=0,
                    value=None,
                    coverage="unavailable",
                    basis=None,
                    unresolved_value_concentration="unknown",
                )
            )
    return dict(
        schema="dex-lv02a-pilot-v1",
        seed=SEED,
        evidence_class="actual_catalog_metadata",
        denominators=denominators,
        rows=rows,
        authored_engineering_baskets=baskets,
        real_price_proof="pending",
        target_eligible=57,
        provider_operations=0,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    with inventory.bounded():
        result = manifest(inventory.catalog_metadata(args.root.absolute()))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
