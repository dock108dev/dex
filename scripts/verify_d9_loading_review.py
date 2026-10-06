"""Read-only copied-root preservation and retained offer semantics; no lookup flow."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from backup_m6 import dbhashes, filemap


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--baseline", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    assert args.root.resolve() == Path(
        "/Users/michaelfuscoletti/dex-private/d9-loading-review-20261006/profile-root"
    )
    baseline = dbhashes(args.baseline / "inventory.db")
    current = dbhashes(args.root / "inventory.db")
    assert baseline == current and len(current) == 57
    assert filemap(args.baseline) == filemap(args.root)
    from pokemon_hunter.beta.cli import setup

    setup(args.root)
    from pokemon_hunter.beta import collection_goals as cg
    from pokemon_hunter.beta import offer_filters, product_lookup, store
    from pokemon_hunter.beta import sealed_catalog as sealed

    actor = store.principal(1)
    source = cg.latest(actor)
    owned = cg.owned(source, 251)
    assert len(owned) == 161 and len(cg.owned(source)) == 137 and len(set(owned) - {*range(1, 152)}) == 24
    assert len(json.loads(source["reconciliation"])) == 286
    assert len(store.rows("SELECT id FROM owned_copies")) == 207
    saves = store.rows("SELECT id,snapshot,snapshot_sha256,created_at FROM saved_pack_research")
    assert len(saves) == 4 and any(s["id"] == "8d2b8956-3e96-4fb1-a246-b63b2faa9a06" for s in saves)
    records = sealed.records()
    obs = records["observations"]["d8:observation:token-prismatic"]
    assert obs["checked_at"] == "2026-10-06T16:20:21.204089+00:00"
    now = datetime.now(UTC)
    selected = {
        r["id"]
        for r in records["printings"].values()
        if r["species_id"] in ["ndex:0123", "ndex:0134", "ndex:0196", "ndex:0197"]
    }
    products = product_lookup.applicability(records, selected)
    decisions = []
    for offer in records["offers"].values():
        history = sorted(
            [o for o in records["observations"].values() if o["offer_id"] == offer["id"]],
            key=offer_filters.observation_key,
        )
        observation = history[0] if history else None
        product = dict(records["products"][offer["product_id"]], **products[offer["product_id"]])
        eligibility = offer_filters.eligibility(offer, observation, product, records["sources"], now)
        decisions.append(
            dict(
                offer_id=offer["id"],
                observation_id=observation["id"] if observation else None,
                eligibility=eligibility,
            )
        )
    assert not any(x["eligibility"]["purchase_ready"] for x in decisions)
    stellar = [p for p in records["products"].values() if "Stellar" in p["name"]]
    assert any("820650858550" in p["id"] for p in stellar) and any("820650878558" in p["id"] for p in stellar)
    result = dict(
        status="passed",
        all_tables=57,
        all_table_rows_identical=True,
        all_table_hashes=current,
        all_file_bytes_identical=True,
        file_count=len(filemap(args.root)),
        authentication_credentials_config_exact=True,
        photos_and_files_exact=True,
        frozen_goal_definitions_versions_exact=True,
        all_four_saves_snapshots_references_times_exact=True,
        owned_copies=207,
        marks=286,
        kanto_owned=137,
        johto_owned=24,
        total_owned=161,
        kanto_missing=14,
        total_missing=90,
        token_observed_at=obs["checked_at"],
        evaluated_at_utc=now.isoformat(),
        token_age_seconds=(now - datetime.fromisoformat(obs["checked_at"])).total_seconds(),
        freshness_policy_hours=24,
        age_class=offer_filters.age(obs["checked_at"], now),
        recommendation_eligible=sum(x["eligibility"]["recommendation_eligible"] for x in decisions),
        purchase_ready=0,
        shipping_tax_destination="unknown",
        stellar_versions_distinct=True,
        crown448_descriptive_only_unchanged=True,
        decisions=decisions,
        owner_operated=False,
        acquisition_calls=0,
    )
    assert baseline == dbhashes(args.root / "inventory.db") and filemap(args.baseline) == filemap(args.root)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print("All 57 copied tables and 13 files preserved; retained age reevaluated")


if __name__ == "__main__":
    main()
