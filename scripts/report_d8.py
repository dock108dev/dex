"""Closeout exact chains and all-251 coverage from disposable published records."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from acquire_d8 import OUT, ROOT, write


def run(root):
    from pokemon_hunter.beta.cli import setup

    setup(root)
    from pokemon_hunter.beta import offer_filters, product_lookup
    from pokemon_hunter.beta import sealed_catalog as sealed

    rec = sealed.records()
    now = datetime.now(UTC)
    members = {m["printing_id"]: m for m in rec["memberships"].values()}
    coverage = product_lookup.coverage(rec, now)
    indexed = json.loads((ROOT / "evidence/d7-20261005/target-printings.json").read_text())
    selected = json.loads((OUT / "selection-reconciliation.json").read_text())
    matrices = []
    products = [
        "pokemon:us:crown-zenith-etb:bestbuy6527309",
        "pokemon:us:prismatic-bundle:196214112544",
        "pokemon:us:stellar-crown-bundle:820650858550",
        "pokemon:us:stellar-crown-bundle:820650878558",
    ]
    for pid in products:
        product = rec["products"][pid]
        packs = [p for p in rec["packs"].values() if p["product_id"] == pid]
        expansions = {p["expansion_id"] for p in packs if p["quantity"] is not None}
        chains = []
        for p in rec["printings"].values():
            if p["expansion_id"] not in expansions or members.get(p["id"], {}).get("status") != "booster":
                continue
            n = int(p["species_id"].split(":")[-1])
            assert 1 <= n <= 251
            chains.append(
                dict(
                    species=n,
                    printing_id=p["id"],
                    number=p["number"],
                    name=p["name"],
                    finish=p["finish"],
                    variant=p["variant"],
                    expansion_id=p["expansion_id"],
                    membership_id=members[p["id"]]["id"],
                    distribution_sources=members[p["id"]]["sources"],
                    pack_ids=[x["id"] for x in packs if x["expansion_id"] == p["expansion_id"]],
                    product_id=pid,
                )
            )
        offers = []
        for o in rec["offers"].values():
            if o["product_id"] != pid:
                continue
            history = sorted(
                [x for x in rec["observations"].values() if x["offer_id"] == o["id"]],
                key=offer_filters.observation_key,
            )
            latest = history[0] if history else None
            decision = offer_filters.eligibility(
                o,
                latest,
                dict(product, distinct_target_count=len({c["species"] for c in chains})),
                rec["sources"],
                now,
            )
            offers.append(
                dict(
                    offer=o,
                    observation=latest,
                    eligibility=decision,
                    observation_age_seconds=(
                        now - offer_filters.instant(latest["checked_at"])
                    ).total_seconds()
                    if latest and latest["checked_at"]
                    else None,
                )
            )
        matrices.append(
            dict(
                product=product,
                packs=packs,
                chains=chains,
                possible_species=sorted({c["species"] for c in chains}),
                offers=offers,
                qualifying_guaranteed_targets=0,
            )
        )
    write(
        OUT / "chain-matrices.json",
        dict(
            evaluated_at=now.isoformat(),
            products=matrices,
            unmatched_candidate="Evolve Crown exact version unresolved; not merged",
            possible_pulls="No guaranteed species or probabilities inferred",
        ),
    )
    # Keep overlapping gap dimensions rather than claiming one exclusive completion state.
    all251 = []
    for n in range(1, 252):
        raw = [p for p in indexed if p["medium"] == "physical" and p["species"] == n]
        chains = [c for m in matrices for c in m["chains"] if c["species"] == n]
        known_boosters = [
            p["id"]
            for p in rec["printings"].values()
            if p["species_id"] == f"ndex:{n:04}" and members.get(p["id"], {}).get("status") == "booster"
        ]
        compatible = [m for m in matrices if n in m["possible_species"]]
        observed = [o for m in compatible for o in m["offers"] if o["observation"]]
        eligible = [o for o in observed if o["eligibility"]["recommendation_eligible"]]
        speciesrow = next(c for c in coverage if c["dex"] == n)
        all251.append(
            dict(
                pokemon_dex=n,
                published_evidence=speciesrow,
                source_numbered_printings=len(raw),
                source_supplied_variants=sum(len(p["english_variants"]) for p in raw),
                printing_only=bool(raw) and not known_boosters,
                known_booster_distribution=bool(known_boosters),
                booster_printing_ids=known_boosters,
                documented_products=[m["product"]["id"] for m in compatible],
                observed_offers=[o["offer"]["id"] for o in observed],
                eligible_offers=[o["offer"]["id"] for o in eligible],
                unavailable_offers=[
                    o["offer"]["id"] for o in observed if o["observation"]["stock"] == "out-of-stock"
                ],
                access_limited_offers=[
                    o["offer"]["id"] for o in observed if o["observation"]["stock"] == "unknown"
                ],
                unresearched_gaps=[
                    "Additional variants,distribution,products and sellers remain unresearched"
                ],
                exact_chains=chains,
            )
        )
    write(
        OUT / "all251-coverage.json",
        dict(
            evaluated_at=now.isoformat(),
            rows=all251,
            source_enumeration="Pinned historical 220 English sets /205 physical /15 digital;6991 physical numbered targets;188 complete physical source enumerations. Not today completeness.",
            prepared=selected,
            disposable_publication=json.loads((OUT / "validation-final4/result.json").read_text()),
        ),
    )
    # Associate offer/observation references explicitly, preserving original source times.
    unique = {o["offer"]["id"]: o for m in matrices for o in m["offers"]}
    eligible = [k for k, o in unique.items() if o["eligibility"]["recommendation_eligible"]]
    write(
        OUT / "eligibility-closeout.json",
        dict(
            evaluated_at=now.isoformat(),
            recommendation_eligible_offers=eligible,
            purchase_ready_offers=[k for k, o in unique.items() if o["eligibility"]["purchase_ready"]],
            eligible_species=[r["pokemon_dex"] for r in all251 if r["eligible_offers"]],
            shipping_tax="Unknown; no delivered total",
            freshness_hours=24,
            decisions=unique,
        ),
    )
    ledger = json.loads((OUT / "source-ledger.json").read_text())
    sources = []
    for a in ledger["attempts"]:
        p = ROOT / a["response_path"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == a["sha256"]
        sources.append(a)
    inherited = []
    for k, s in rec["sources"].items():
        if k.startswith(("d6:", "d7:", "m4:")):
            inherited.append(
                dict(
                    id=k,
                    url=s["url"],
                    sha256=s["sha256"],
                    retrieved_at=s["retrieved_at"],
                    note="Previously retained source, no D8 date refresh",
                )
            )
    write(OUT / "raw-source-manifest.json", dict(attempts=sources, inherited_sources=inherited))
    write(
        OUT / "closeout-summary.json",
        dict(
            unpublished_sets=19,
            new_numbered_targets=1149,
            new_catalog_records=1965,
            explicit_supplied_variants=1611,
            unspecified_variant_rows=354,
            assessed_sets=48,
            numbered_targets_total=3104,
            published_records_total=5067,
            recommendation_eligible_offers=len(eligible),
            eligible_species=sum(bool(r["eligible_offers"]) for r in all251),
            purchase_ready_offers=0,
            observations_added=7,
            discovery_operations=sum(a["category"] == "discovery" for a in sources),
            official_operations=sum(a["category"] == "official" for a in sources),
            seller_operations=sum(a["category"] == "seller" for a in sources),
            total_operations=len(sources),
            acquisition_seconds=(
                datetime.fromisoformat(ledger["closed_at"]) - datetime.fromisoformat(ledger["started_at"])
            ).total_seconds(),
            retries=sum(a.get("retry", False) for a in sources),
        ),
    )
    print(json.dumps(json.loads((OUT / "closeout-summary.json").read_text())))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    run(p.parse_args().root)
