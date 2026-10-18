"""Reconcile a frozen ambiguous cohort against retained evidence, entirely offline.

This is an evidence report, never a catalog writer or price crosswalk. A numbered
card, a list of available variants and a particular physical printing are separate
identities. In particular, a shared product ID cannot select an edition.
"""

import argparse
import hashlib
import json
import socket
import sqlite3
import sys
import tarfile
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prepare_d6 as retained  # noqa: E402
import qualify_hunter as audit  # noqa: E402

from pokemon_hunter.beta import market_identity  # noqa: E402
from pokemon_hunter.beta import price_snapshot_contract as rules  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
PIN = "99c994747cf7519a3e51166cc932de79a88bd4b3"
ARCHIVE_SHA256 = "1431e3be180cc5c8e491e480fd78b2b721155622372591d9f82bfb8aa83a6cce"
BATCH_COUNTS = {1: 77, 2: 207, 3: 255, 4: 121}
PAIR_COUNTS = {
    "Normal / Reverse Holofoil": 308,
    "Holofoil / Reverse Holofoil": 47,
    "1st Edition / Unlimited": 241,
    "1st Edition Holofoil / Unlimited Holofoil": 64,
}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def no_network(*_args, **_kwargs):
    raise ValueError("Identity reconciliation forbids network access")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def verify_publication(publication, old_manifest):
    """Verify both the published package and the original member-hash lineage."""
    package = publication["package"]
    encoded = json.dumps(package, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    require(sha(encoded) == publication["package_hash"], "Published package hash conflict")
    legacy = package.get("reconcile_legacy_set")
    if legacy:
        require(old_manifest["commit"] == package["version"], "Original source revision conflict")
        original = old_manifest["sets"].get(legacy)
        require(original is not None, "Original set manifest missing")
        require(
            sha(json.dumps(original, sort_keys=True).encode()) == package["source_sha256"],
            "Original set manifest hash conflict",
        )
    else:
        require(package["source_sha256"] == ARCHIVE_SHA256, "Publication archive lineage conflict")


def classify(source):
    """Describe evidence strength without assigning any variant to an existing ID.

    No availability-flag expansion and no inference from rarity, number, an absent
    stamp, product ID or common finish. Unsupported shapes remain explicit.
    """
    variants = source.get("variants")
    if variants is None or variants == []:
        return "source_variant_detail_absent", [], []
    accepted, excluded = retained.english_variants(variants)
    if excluded or not accepted:
        return "source_variant_shape_or_language_unresolved", accepted, excluded
    if len(accepted) > 1:
        return "numbered_identity_spans_multiple_variants", accepted, excluded
    return "single_source_variant_without_identity_assignment", accepted, excluded


def freeze(batches):
    rows, seen = [], set()
    for batch, report in sorted(batches.items()):
        selected = [r for r in report["decisions"] if r["decision"] == "ambiguous_supported_subtypes"]
        require(len(selected) == BATCH_COUNTS[batch], "Frozen batch count changed")
        for row in selected:
            pid = row["printing_id"]
            require(pid not in seen, "Duplicate printing in frozen cohort")
            seen.add(pid)
            require(
                all(row["catalog_identity"][k] is None for k in ("edition", "finish", "variant")),
                "Frozen identity is no longer unspecified",
            )
            require(len(row["candidates"]) == 1, "Expected exactly one literal product")
            require(len(row["candidates"][0]["supported_subtypes"]) == 2, "Expected two subtype alternatives")
            rows.append(dict(batch=batch, **row))
    require(len(rows) == 660, "Incomplete 660-identity cohort")
    require(
        dict(Counter(" / ".join(r["candidates"][0]["supported_subtypes"]) for r in rows)) == PAIR_COUNTS,
        "Subtype pair counts changed",
    )
    return sorted(rows, key=lambda r: r["printing_id"])


def collect(root, repo=REPO):
    """Read only catalog/publication metadata; no prices or private user rows."""
    inputs = {}

    def read(relative):
        path = repo / relative
        raw = path.read_bytes()
        inputs[relative] = dict(sha256=sha(raw), bytes=len(raw))
        return json.loads(raw)

    base = "reports/hunt-11-s3-20261017"
    batches = {i: read(f"{base}/batch-{i}/mapping-decisions.json") for i in BATCH_COUNTS}
    cohort = freeze(batches)
    entries = audit.catalog_metadata(root)
    catalog_sha = rules.digest(entries)
    for i, batch in batches.items():
        scope = read(f"{base}/batch-{i}/scope.json")
        independent = read(f"{base}/batch-{i}/independent-identity-review.json")
        require(
            batch["catalog_identity_sha256"] == catalog_sha == scope["catalog_identity_sha256"],
            "Current catalog differs from frozen S3 catalog",
        )
        require(
            rules.digest(scope) == batch["scope_sha256"] == independent["scope_sha256"],
            "S3 scope identity conflict",
        )
        unhashed = {k: v for k, v in batch.items() if k != "identity_decisions_sha256"}
        require(rules.digest(unhashed) == batch["identity_decisions_sha256"], "S3 decision digest conflict")
        require(
            independent["all_passed"]
            and independent["identity_decisions_sha256"] == batch["identity_decisions_sha256"],
            "Final S3 independent review mismatch",
        )
    inventory = read("reports/hunt-11-s1-20261017/printing-review-inventory.json")
    groups = read("reports/hunt-11-s1-20261017/group-inventory.json")
    require(
        inventory["catalog_identity_sha256"] == groups["catalog_identity_sha256"] == catalog_sha,
        "S1 inventory lineage conflict",
    )
    by_id = {r["printing_id"]: r for r in inventory["printings"]}
    universe = read("evidence/d7-20261005/universe.json")
    candidate = read("evidence/d7-20261005/candidate.json")
    archive_manifest = read("evidence/d6-20261005/archive-file-manifest.json")
    raw_manifest = read("evidence/d6-20261005/raw-source-manifest.json")
    old_manifest = read("config/catalog-imports/staging-ten/source-manifest.json")
    sets = {s["provider_set_id"]: s for s in universe["sets"]}
    archive_path = "evidence/d6-20261005/raw/tcgdex-archive.raw"
    archive_bytes = (repo / archive_path).read_bytes()
    inputs[archive_path] = dict(sha256=sha(archive_bytes), bytes=len(archive_bytes))
    require(
        sha(archive_bytes)
        == ARCHIVE_SHA256
        == universe["source_sha256"]
        == archive_manifest["archive_sha256"],
        "Pinned archive identity conflict",
    )
    require(archive_manifest["commit"] == PIN, "Pinned member manifest revision conflict")
    require(
        any(
            r.get("path") == archive_path and r.get("sha256") == ARCHIVE_SHA256
            for r in raw_manifest["responses"]
        ),
        "Archive acquisition lineage missing",
    )
    require(
        candidate["files"].get("evidence/d7-20261005/universe.json")
        == inputs["evidence/d7-20261005/universe.json"]["sha256"],
        "D7 candidate universe identity conflict",
    )

    with sqlite3.connect((root / "inventory.db").as_uri() + "?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        publications = [
            dict(r)
            for r in db.execute(
                "SELECT id,set_id,package_hash,package FROM catalog_imports WHERE state='published'"
            )
        ]
        mappings = [
            dict(r)
            for r in db.execute(
                "SELECT provider,entity_kind,external_id,internal_id FROM external_mappings WHERE entity_kind='printing'"
            )
        ]
        db.rollback()
    for p in publications:
        p["package"] = json.loads(p["package"])

    ledger, manifest_rows = [], []
    with tarfile.open(repo / archive_path) as archive:
        members = {m.name.split("/", 1)[-1]: m for m in archive.getmembers() if m.isfile()}
        # Read selected metadata in archive order; random seeks in a compressed
        # archive otherwise decompress it hundreds of times. No extraction to disk.
        prefix = f"https://github.com/tcgdex/cards-database/blob/{PIN}/"
        source_paths = {}
        needed = set()
        for row in cohort:
            current = entries[row["printing_id"]]
            provenance = json.loads(current["provenance"])
            matching = [
                p
                for p in publications
                if p["set_id"] == current["set_id"]
                and p["package"]["version"] == provenance["source_version"]
            ]
            require(len(matching) == 1, "No unique exact-version publication")
            source_set = sets[matching[0]["package"]["set_key"]]
            require(source_set["source_url"].startswith(prefix), "Unexpected source revision")
            set_path = source_set["source_url"].removeprefix(prefix)
            path = set_path.removesuffix(".ts") + "/" + current["collector_number"] + ".ts"
            needed.update((set_path, path))
        require(needed <= members.keys(), "Missing exact source member")
        for path in sorted(needed, key=lambda name: members[name].offset_data):
            source_paths[path] = archive.extractfile(members[path]).read()
        for row in cohort:
            pid = row["printing_id"]
            current = entries[pid]
            require(
                all(current[k] == v for k, v in row["catalog_identity"].items()),
                "Canonical identity differs from retained decision",
            )
            require(by_id[pid]["source_group_id"] == row["group_id"], "Source group crosswalk conflict")
            require(not row["candidates"][0]["identity_conflicts"], "Conflicted source candidate")
            require(row["selected_binding"] is None, "Ambiguous identity already assigned")
            provenance = json.loads(current["provenance"])
            matching = [
                p
                for p in publications
                if p["set_id"] == current["set_id"]
                and p["package"]["version"] == provenance["source_version"]
            ]
            require(len(matching) == 1, "No unique exact-version publication")
            publication = matching[0]
            package = publication["package"]
            verify_publication(publication, old_manifest)
            cards = [c for c in package["cards"] if c["external_id"] == provenance["external_id"]]
            require(len(cards) == 1, "Published card external identity conflict")
            published_card = cards[0]
            require(
                published_card["number"] == current["collector_number"]
                and published_card["name"] == current["name"],
                "Published literal identity conflict",
            )
            require(
                package["source_sha256"] == provenance["source_sha256"], "Publication source hash conflict"
            )
            require(
                all(published_card.get(k) is None for k in ("edition", "finish", "variant")),
                "Demonstrated omitted field requires separate correction review",
            )
            exact_mapping = dict(
                provider=provenance["provider"],
                entity_kind="printing",
                external_id=provenance["external_id"],
                internal_id=pid,
            )
            require(exact_mapping in mappings, "External mapping does not preserve printing")
            code = package["set_key"]
            set_evidence = sets[code]
            require(
                set_evidence["language"] == "en" and set_evidence["medium"] == "physical",
                "English physical source required",
            )
            prefix = f"https://github.com/tcgdex/cards-database/blob/{PIN}/"
            require(set_evidence["source_url"].startswith(prefix), "Unexpected source revision")
            set_path = set_evidence["source_url"].removeprefix(prefix)
            path = set_path.removesuffix(".ts") + "/" + published_card["number"] + ".ts"
            require(path in members, "Missing exact card member")
            raw = source_paths[path]
            require(sha(raw) == archive_manifest["files"][path]["sha256"], "Card member identity conflict")
            set_raw = source_paths[set_path]
            require(sha(set_raw) == set_evidence["source_sha256"], "Source set member conflict")
            source = retained.parse(raw.decode())
            require(source["name"]["en"] == current["name"], "Literal card name conflict")
            cause, variants, exclusions = classify(source)
            candidate = row["candidates"][0]
            require(
                all(
                    market_identity.compatible(current, *market_identity.SUBTYPES[s])
                    for s in candidate["supported_subtypes"]
                ),
                "Unsupported subtype substitution",
            )
            source_product_ids = sorted(
                {
                    v.get("thirdParty", {}).get("tcgplayer")
                    for v in variants
                    if type(v.get("thirdParty", {}).get("tcgplayer")) is int
                }
            )
            if not variants and type(source.get("thirdParty", {}).get("tcgplayer")) is int:
                source_product_ids = [source["thirdParty"]["tcgplayer"]]
            require(
                not source_product_ids or source_product_ids == [candidate["product_id"]],
                "Retained product crosswalk conflicts with S3 candidate",
            )
            old_hash = old_manifest["sets"].get(package.get("reconcile_legacy_set"), {}).get(path)
            lineage = (
                "original_card_bytes_identical"
                if old_hash == sha(raw)
                else "newer_same_card_corroboration_original_bytes_differ"
                if old_hash
                else "same_pinned_archive_as_publication"
            )
            record = dict(
                printing_id=pid,
                batch=row["batch"],
                canonical_identity=row["catalog_identity"],
                canonical_catalog_version=current["catalog_version"],
                provenance=provenance,
                source_group_id=row["group_id"],
                source_candidate=candidate,
                root_cause=cause,
                disposition="preserve_unknown_no_canonical_change",
                evidence=[
                    dict(
                        location=f"{base}/batch-{row['batch']}/mapping-decisions.json",
                        selector=f"decisions[printing_id={pid}]",
                        establishes="One literal product, two alternatives; no chosen subtype",
                    ),
                    dict(
                        location="actual-root/inventory.db:catalog_imports",
                        publication_id=publication["id"],
                        package_hash=publication["package_hash"],
                        package_identity_sha256=rules.digest(package),
                        card=published_card,
                        establishes="Published edition/finish/variant were null; no importer field loss",
                    ),
                    dict(
                        location="actual-root/inventory.db:external_mappings",
                        mapping=exact_mapping,
                        establishes="Existing external ID still addresses the same printing",
                    ),
                    dict(
                        location=archive_path,
                        member=path,
                        sha256=sha(raw),
                        source_url=prefix + path,
                        source_identity=f"tcgdex:en:{code}-{published_card['number']}",
                        revision=PIN,
                        relevant_field="variants",
                        field_present="variants" in source,
                        variants=source.get("variants"),
                        english_variants=variants,
                        excluded=exclusions,
                        shared_product_ids=source_product_ids,
                        lineage=lineage,
                        original_member_sha256=old_hash,
                        establishes="Multiple available variants, no assignment to this ID"
                        if variants
                        else "No per-card variant field; rarity/product identity cannot select finish",
                    ),
                ],
                correction=None,
                affected_records=[],
                mapping_resolved=False,
                newly_price_eligible=False,
                remaining_uncertainty="No variant-specific assignment for the preserved identity; no replacement price observation",
                next_requirement=(
                    "Review literal successor variant identities and parent/child representation; preserve old ID, owned copies and frozen goals"
                    if variants
                    else "Retain unspecified parent; establish literal English physical variant evidence before successor publication"
                ),
            )
            ledger.append(record)
            manifest_rows.append(
                dict(
                    printing_id=pid,
                    batch=row["batch"],
                    s3_decision_sha256=rules.digest({k: v for k, v in row.items() if k != "batch"}),
                    evidence_decision_sha256=rules.digest(record),
                )
            )
    require(
        rules.digest(audit.catalog_metadata(root)) == catalog_sha, "Catalog changed during reconciliation"
    )
    for relative in (
        "scripts/reconcile_tcgcsv_identity.py",
        "scripts/prepare_d6.py",
        "scripts/review_tcgcsv_batch.py",
        "scripts/audit_tcgcsv_batch.py",
        "src/pokemon_hunter/beta/catalog_imports.py",
        "src/pokemon_hunter/beta/market_identity.py",
        "src/pokemon_hunter/beta/tcgcsv_offline.py",
    ):
        raw = (repo / relative).read_bytes()
        inputs[relative] = dict(sha256=sha(raw), bytes=len(raw))
    summaries = {}
    for dimension in ("batch", "set", "pair", "root_cause", "outcome", "lineage"):
        grouped = defaultdict(list)
        for r in ledger:
            key = {
                "batch": str(r["batch"]),
                "set": r["canonical_identity"]["set_name"],
                "pair": " / ".join(r["source_candidate"]["supported_subtypes"]),
                "root_cause": r["root_cause"],
                "outcome": r["disposition"],
                "lineage": r["evidence"][-1]["lineage"],
            }[dimension]
            grouped[key].append(r)
        summaries[dimension] = {
            k: dict(identities=len(v), outcomes=dict(Counter(r["disposition"] for r in v)))
            for k, v in sorted(grouped.items())
        }
    return {
        "cohort-manifest.json": dict(
            schema="dex-hunt11-s4-cohort-v1",
            catalog_identity_sha256=catalog_sha,
            identities=len(ledger),
            inputs=inputs,
            printings=manifest_rows,
        ),
        "decision-ledger.json": dict(
            schema="dex-hunt11-s4-evidence-v1", decisions=ledger, provider_operations=0, customer_writes=0
        ),
        "outcome-summary.json": dict(
            identities=660,
            mapping_resolved=0,
            remaining_unknown=660,
            corrections=0,
            newly_price_eligible=0,
            summaries=summaries,
        ),
        "refresh-handoff.json": dict(
            schema="dex-hunt11-s4-refresh-v1",
            ready_target_ids=[],
            groups=[],
            products=[],
            subtypes=[],
            request_ceiling=0,
            selected_for_execution=False,
            reason="No exact subtype assignment proven; all groups remain consumed. Resolve representation first.",
            future_source_requirements="Existing finite refresh mode, durable consumed history, daily pacing, newer matching build, Stop, independent mapping/admission, actual observations and ordinary retention",
        ),
        "representation-handoff.json": dict(
            schema="dex-hunt11-s4-representation-v1",
            provider_operations=0,
            cohorts={
                cause: [
                    dict(
                        printing_id=r["printing_id"],
                        source_group_id=r["source_group_id"],
                        product_id=r["source_candidate"]["product_id"],
                        source_subtypes=r["source_candidate"]["supported_subtypes"],
                        evidence_member=r["evidence"][-1]["member"],
                    )
                    for r in ledger
                    if r["root_cause"] == cause
                ]
                for cause in sorted({r["root_cause"] for r in ledger})
            },
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    socket.socket = socket.create_connection = socket.getaddrinfo = no_network
    result = collect(args.root.resolve())
    require(args.output.is_dir() and not args.output.is_symlink(), "Existing report directory required")
    require(all(not (args.output / name).exists() for name in result), "Refusing to overwrite prior evidence")
    for name, value in result.items():
        with (args.output / name).open("x") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
    print(json.dumps(result["outcome-summary.json"]))


if __name__ == "__main__":
    main()
