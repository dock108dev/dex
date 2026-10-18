"""Dry-run already retained TCGCSV files; explicit staging never acquires or activates.

Use only private managed staging inputs. The existing read-only Hunter audit supplies
catalog and eligible identity metadata. Report output contains no reference values,
source contracts, source URLs, raw records or derivatives. An independently admitted
contract is required separately before --stage can write a candidate package.
"""

import argparse
import copy
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import qualify_hunter as audit

from pokemon_hunter.beta import price_snapshot_contract as rules
from pokemon_hunter.beta import tcgcsv_offline


def _managed_input(root, path):
    staging = root / "price-snapshots" / "staging"
    candidate = path.absolute()
    if (
        not candidate.is_relative_to(staging)
        or candidate == staging
        or candidate.resolve(strict=True) != candidate
    ):
        raise ValueError("Retained inputs must be inside private managed staging")
    for item in (staging, *candidate.relative_to(staging).parents):
        checked = item if item.is_absolute() else staging / item
        if checked.is_symlink() or not checked.is_dir() or checked.stat().st_mode & 0o077:
            raise ValueError("Managed inputs require owner-only unlinked directories")
    if (
        candidate.is_symlink()
        or not candidate.is_file()
        or candidate.stat().st_mode & 0o077
        or candidate.stat().st_nlink != 1
    ):
        raise ValueError("Retained input must be an owner-only unlinked regular file")
    if staging.is_symlink() or staging.stat().st_mode & 0o077:
        raise ValueError("Managed staging must be owner-only")
    return candidate


def _current(root):
    pointer = root / "price-snapshots" / "active.json"
    value = audit.read_json(pointer) if pointer.exists() else {"current": None, "previous": None}
    if not isinstance(value, dict) or set(value) != {"current", "previous"}:
        raise ValueError("Invalid existing release pointer")
    return value["current"]


def _stage(root, package, path, *, expected_current, expected_contract_sha256, catalog_sha256, now):
    """Admission and composition precede the only write; activation remains separate."""
    from pokemon_hunter.beta import cli
    from pokemon_hunter.beta import price_snapshots as prices

    if package is None:
        raise ValueError("No qualified observations to stage")
    stage = root / "price-snapshots" / "staging"
    path = path.absolute()
    if path.parent != stage or path.is_symlink() or path.exists():
        raise ValueError("Choose a new single managed staging file")
    part = next(iter(rules.source_packages(package).values()))
    policy = part["contract"]
    if rules.digest(policy) != expected_contract_sha256:
        raise ValueError("Reviewed source contract identity changed")
    try:
        registry = audit.read_json(root / "price-contracts.json")
    except audit.AuditFailure:
        raise ValueError("Independent exact source admission is required before staging") from None
    if not isinstance(registry, dict) or registry.get(policy["review_id"]) != expected_contract_sha256:
        raise ValueError("Independent exact source admission is required before staging")
    expected = None if expected_current == "none" else audit._uuid(expected_current)
    if _current(root) != expected:
        raise ValueError("Current release changed; repeat the local dry-run")
    cli.setup(root)
    # preview/load validate and read; they do not prune or activate. Carry all
    # surviving admitted sources through the normal existing release schema.
    candidate = copy.deepcopy(package)
    if expected is not None:
        current = prices.preview(prices.directory() / (expected + ".json"), now=now)
        if current["release_month"] != candidate["release_month"]:
            raise ValueError("Cross-month source composition needs separate compatible engineering")
        for old in rules.source_packages(current).values():
            key = old["contract"]["review_id"]
            if key in candidate["contracts"]:
                raise ValueError("Source replacement requires a separate complete replacement projection")
            candidate["contracts"][key] = {
                "contract": old["contract"],
                "expires_at": old["expires_at"],
            }
            candidate["records"].extend(dict(row, contract_id=key) for row in old["records"])
    catalog = audit.catalog_metadata(root)
    if rules.digest(catalog) != catalog_sha256:
        raise ValueError("Catalog changed; repeat the local dry-run and exact mapping review")
    rules.validate(candidate, catalog, now=now)
    if rules.serialized_bytes(candidate) > rules.MAX_RELEASE_BYTES:
        raise ValueError("Combined release exceeds the existing finite package limit")
    prices.reviewed(candidate)
    if _current(root) != expected:
        raise ValueError("Current release changed before staging")
    prices.atomic(path, candidate)
    return {"staged": True, "activated": False, "preserved_source_count": len(candidate["contracts"]) - 1}


def run(args, *, now=None):
    now = now or datetime.now(timezone.utc)
    root = args.root.expanduser().absolute()
    if root.is_symlink() or not root.is_dir() or root.resolve(strict=True) != root:
        raise ValueError("Existing installation required")
    if (
        args.report.is_symlink()
        or args.report.exists()
        or not args.report.parent.is_dir()
        or args.report.resolve().is_relative_to(root)
    ):
        raise ValueError("Choose a new metadata report file in an existing directory")
    manifest_path = _managed_input(root, args.manifest)
    manifest = tcgcsv_offline.read_manifest(manifest_path)
    shards = manifest.get("shards")
    if not isinstance(shards, list) or len(shards) > 68:
        raise ValueError("A finite retained group inventory is required")
    for shard in shards:
        if not isinstance(shard, dict):
            raise ValueError("Explicit retained group files required")
        for key in ("products", "prices"):
            relative = shard.get(key)
            if not isinstance(relative, str) or Path(relative).is_absolute() or ".." in Path(relative).parts:
                raise ValueError("Explicit local retained filenames required")
            _managed_input(root, manifest_path.parent / relative)
    entries = audit.catalog_metadata(root)
    snapshots, _, _, _ = audit.snapshot_metadata(root, entries, now)
    legacy, _, _, _ = audit.legacy_metadata(root, entries, now.date())
    baseline = {pid for pid in entries if "eligible" in snapshots[pid] or "eligible" in legacy[pid]}
    package, report = tcgcsv_offline.prepare(
        entries,
        manifest,
        input_directory=manifest_path.parent,
        now=now,
        baseline_eligible=baseline,
        target_ids=sorted({binding["printing_id"] for binding in manifest["bindings"]}),
    )
    report.update(
        customer_writes=0,
        provider_operations=0,
        actual_acquired_coverage_increase=0,
        activated=False,
        staged=False,
        evidence_class="Offline retained-input projection; source acquisition and actual activation unperformed",
    )
    if args.stage:
        if not args.expected_current or not args.expected_contract_sha256:
            raise ValueError("Staging requires expected current release and reviewed contract digest")
        report.update(
            _stage(
                root,
                package,
                args.stage,
                expected_current=args.expected_current,
                expected_contract_sha256=args.expected_contract_sha256,
                catalog_sha256=rules.digest(entries),
                now=now,
            )
        )
        report["customer_writes"] = 1
    # Reports are metadata only. A private atomic file prevents accidentally
    # overwriting an existing artifact or echoing private input on failures.
    descriptor = os.open(args.report, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--stage", type=Path)
    parser.add_argument("--expected-current")
    parser.add_argument("--expected-contract-sha256")
    args = parser.parse_args(argv)
    try:
        report = run(args)
    except (ValueError, TypeError, KeyError, OSError, sqlite3.DatabaseError, audit.AuditFailure):
        parser.exit(
            2, "Offline preparation refused; no acquisition or activation occurred. Input details withheld.\n"
        )
    print(json.dumps({key: report[key] for key in ("staged", "activated", "provider_operations")}))


if __name__ == "__main__":
    main()
