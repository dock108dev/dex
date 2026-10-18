"""Bounded local Hunter coverage audit; aggregate metadata only, no acquisition.

This deliberately avoids the normal snapshot readers: their expiry/source pruning
is correct for comparison but can write. Private records are validated only in
memory. No private values, mappings, contracts, dates or source IDs enter output.
"""

import argparse
import hashlib
import json
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from pokemon_hunter import reference_policy
from pokemon_hunter.beta import price_snapshot_contract as rules
from pokemon_hunter.beta import price_snapshot_sources
from pokemon_hunter.beta.lot_calculator import SETS as CALCULATOR_SETS

MAX_CATALOG_ROWS = 200_000
MAX_LEGACY_ROWS = 100_000
MAX_SOURCES = 32
LEGACY_SHA256 = "72d61c466c74b8a702cee9fd744a5485633c236c0dcbfaa07c26a3fafac27b03"
STATES = (
    "eligible",
    "stale",
    "expired",
    "withdrawn",
    "unadmitted",
    "inapplicable",
    "invalid",
    "unpriced",
)


class AuditFailure(Exception):
    """A deliberately content-free failure: don't expose private parser errors."""


def read_json(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > rules.MAX_BYTES:
        raise AuditFailure("Missing, linked or oversized audit input")
    with path.open("rb") as source:
        raw = source.read(rules.MAX_BYTES + 1)
    if len(raw) > rules.MAX_BYTES:
        raise AuditFailure("Oversized audit input")
    try:
        return json.loads(raw, object_pairs_hook=rules.unique_object, parse_constant=rules.invalid_constant)
    except (ValueError, UnicodeError):
        raise AuditFailure("Malformed audit input") from None


def catalog_metadata(root):
    path = root / "inventory.db"
    if path.is_symlink() or not path.is_file():
        raise AuditFailure("Existing local catalog required")
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as database:
        database.execute("PRAGMA query_only=ON")
        rows = database.execute(
            "SELECT p.*,s.game_id,s.name AS set_name,s.catalog_version,s.coverage_status "
            "FROM printings p JOIN catalog_sets s ON s.id=p.set_id "
            "JOIN games g ON g.id=s.game_id WHERE g.game_key='pokemon' "
            "AND p.publication_state='published' AND s.publication_state='published' "
            "ORDER BY p.id LIMIT ?",
            (MAX_CATALOG_ROWS + 1,),
        )
        names = [field[0] for field in rows.description]
        found = rows.fetchall()
    if len(found) > MAX_CATALOG_ROWS:
        raise AuditFailure("Catalog exceeds the finite audit limit")
    entries = {}
    for values in found:
        printing = dict(zip(names, values, strict=True))
        printing["attributes"] = json.loads(printing["attributes"])
        printing["name"] = printing["attributes"].get("name", "Unidentified card")
        entries[printing["id"]] = printing
    return entries


def _uuid(value):
    if not isinstance(value, str) or str(UUID(value)) != value:
        raise AuditFailure("Invalid local release identity")
    return value


def _valid_digest(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _record_state(row, printing, today):
    reason = rules.reason(row, printing, today)
    return "eligible" if reason == "eligible" else "stale" if reason == "stale" else "inapplicable"


def _source_state(part, digest, version, admitted, denied_sources, revoked_versions, now, synthetic):
    if version in revoked_versions or digest in denied_sources["contracts"]:
        return "withdrawn"
    if version + ":" + digest in denied_sources["releases"]:
        return "withdrawn"
    expiry = part.get("expires_at")
    if expiry is not None and rules.timestamp(expiry) <= now:
        return "expired"
    policy = part.get("contract", {})
    fixture = policy.get("provider") == "dex-engineering-fixture"
    if not (fixture and synthetic) and admitted.get(policy.get("review_id")) != digest:
        return "unadmitted"
    return None


def snapshot_metadata(root, entries, now):
    """Read current shards without pruning; return only per-identity states."""
    base = root / "price-snapshots"
    states, counts, unmapped = defaultdict(set), Counter(), set()
    pointer = read_json(base / "active.json") if (base / "active.json").exists() else {}
    version = pointer.get("current")
    if version is None:
        return states, counts, unmapped, "missing"
    _uuid(version)
    key = rules.digest(str(root.resolve()))
    revocation_base = root.parent / ".dex-price-revocations"
    denied_path = revocation_base / (key + ".json")
    source_path = revocation_base / (key + "-sources.json")
    revoked_versions = read_json(denied_path) if denied_path.exists() else []
    if not denied_path.is_file():
        raise AuditFailure("Independent lifecycle registry is required")
    if not isinstance(revoked_versions, list):
        raise AuditFailure("Invalid independent release registry")
    for item in revoked_versions:
        _uuid(item)
    admitted_path = root / "price-contracts.json"
    admitted = read_json(admitted_path) if admitted_path.exists() else {}
    if not isinstance(admitted, dict):
        raise AuditFailure("Invalid source admission registry")
    seals = read_json(base / "versions.json")
    package = read_json(base / (version + ".json"))
    if package.get("version") != version:
        raise AuditFailure("Current release identity mismatch")
    denied_sources = {"contracts": [], "releases": []}
    if source_path.exists():
        denied_sources = read_json(source_path)
    if not isinstance(denied_sources, dict) or set(denied_sources) != {"contracts", "releases"}:
        raise AuditFailure("Invalid independent source registry")
    if any(not isinstance(value, list) for value in denied_sources.values()):
        raise AuditFailure("Invalid independent source registry")
    if not all(_valid_digest(value) for value in denied_sources["contracts"]):
        raise AuditFailure("Invalid independent source registry")
    for value in denied_sources["releases"]:
        release, digest = value.split(":")
        _uuid(release)
        if not _valid_digest(digest):
            raise AuditFailure("Invalid independent source registry")
    seal = seals.get(version, {})
    if seal.get("sha256") != rules.digest(package):
        raise AuditFailure("Current release fingerprint mismatch")
    parts = []
    if package.get("schema") == "dex-price-release-v2":
        price_snapshot_sources.descriptor(package)
        if not source_path.is_file() or not denied_path.is_file():
            raise AuditFailure("Independent lifecycle registries are required")
        sources = package.get("sources")
        if not isinstance(sources, dict) or not 1 <= len(sources) <= MAX_SOURCES:
            raise AuditFailure("Invalid source inventory")
        for digest, metadata in sources.items():
            if not _valid_digest(digest):
                raise AuditFailure("Invalid source inventory")
            # Expired/withdrawn shards can already have been removed by the normal
            # worker. Count their source state without inventing a record count.
            unavailable = _source_state(
                {
                    "expires_at": metadata.get("expires_at"),
                    "contract": {"review_id": metadata.get("review_id")},
                },
                digest,
                version,
                admitted,
                denied_sources,
                revoked_versions,
                now,
                False,
            )
            shard = base / version / (digest + ".json")
            if not shard.exists() and unavailable:
                counts["sources_" + unavailable] += 1
                continue
            part = read_json(shard)
            if seal.get("sources", {}).get(digest) != rules.digest(part):
                raise AuditFailure("Source fingerprint mismatch")
            if rules.digest(part.get("contract")) != digest or (
                part.get("version"),
                part.get("release_month"),
                part.get("expires_at"),
            ) != (version, package.get("release_month"), metadata.get("expires_at")):
                raise AuditFailure("Source identity mismatch")
            parts.append((part, digest))
    elif package.get("schema") == "dex-price-snapshot-v1":
        parts.append((package, rules.digest(package.get("contract"))))
    else:
        raise AuditFailure("Unsupported local release")
    if sum(len(part.get("records", [])) for part, _ in parts) > rules.MAX_RELEASE_ROWS:
        raise AuditFailure("Combined observation ceiling exceeded")
    if (
        sum(len(part.get("contract", {}).get("mappings", {})) for part, _ in parts)
        > rules.MAX_RELEASE_MAPPINGS
    ):
        raise AuditFailure("Combined mapping ceiling exceeded")
    if sum(rules.serialized_bytes(part) for part, _ in parts) > rules.MAX_RELEASE_BYTES:
        raise AuditFailure("Combined source byte ceiling exceeded")
    for part, digest in parts:
        source_state = _source_state(
            part,
            digest,
            version,
            admitted,
            denied_sources,
            revoked_versions,
            now,
            (root / "SYNTHETIC_ONLY").is_file(),
        )
        records = part.get("records")
        if not isinstance(records, list) or not 1 <= len(records) <= rules.MAX_ROWS:
            raise AuditFailure("Invalid source record count")
        counts["sources_" + (source_state or "admitted")] += 1
        # Pure validation has no app-root access. Sources with expired or
        # withdrawn rights cannot contribute eligible observations.
        if source_state is None:
            try:
                rules.validate(part, entries, now=now)
            except (ValueError, KeyError, TypeError):
                source_state = "invalid"
        for row in records:
            counts["records"] += 1
            pid = row.get("printing_id")
            if pid not in entries:
                counts["records_unmapped"] += 1
                if isinstance(pid, str):
                    unmapped.add(pid)
                continue
            state = source_state or _record_state(row, entries[pid], now.date())
            states[pid].add(state)
            counts["records_" + state] += 1
    return states, counts, unmapped, "inspected_without_cleanup"


def legacy_metadata(root, entries, today, *, expected_sha256=LEGACY_SHA256):
    path = root / "parity-evidence/market_values.json"
    states, counts, unmapped = defaultdict(set), Counter(), set()
    if not path.exists():
        return states, counts, unmapped, "missing"
    rows = read_json(path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha256:
        return states, counts, unmapped, "unadmitted_bytes"
    if not isinstance(rows, list) or len(rows) > MAX_LEGACY_ROWS:
        raise AuditFailure("Invalid retained guide record count")
    by_legacy = defaultdict(list)
    for printing in entries.values():
        legacy_id = json.loads(printing["provenance"]).get("legacy_id")
        if legacy_id:
            by_legacy[legacy_id].append(printing)
    for row in rows:
        counts["records"] += 1
        key = row.get("card_id")
        matches = by_legacy.get(key, [])
        if not matches:
            counts["records_unmapped"] += 1
            if isinstance(key, str):
                unmapped.add(key)
            continue
        for printing in matches:
            state = reference_policy.fresh(row.get("as_of"), today.isoformat())
            if state != "stale":
                state = "eligible" if reference_policy.valid_record(row, today, guide=True) else "invalid"
            if (
                row.get("edition") != (printing.get("edition") or "standard")
                or str(row.get("grade")) not in rules.COLUMNS
                or str(row.get("grade")) != "raw"
                and (row.get("estimated") or not row.get("grader"))
                or any(row.get(k) not in (None, printing.get(k)) for k in ("language", "finish", "variant"))
                or str(row.get("grade")) == "raw"
                and row.get("grader") not in {"Guide", "PSA"}
            ):
                state = "inapplicable"
            states[printing["id"]].add(state)
            counts["printing_observations_" + state] += 1
    return states, counts, unmapped, "inspected_without_cleanup"


def audit(root, *, now=None, legacy_sha256=LEGACY_SHA256):
    """Return a report safe to retain; never compare listings or use a network."""
    started = time.perf_counter()
    root = root.resolve()
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise AuditFailure("An aware audit time is required")
    now = now.astimezone(timezone.utc)
    entries = catalog_metadata(root)
    catalog_seconds = time.perf_counter() - started
    snapshots, snapshot_counts, snapshot_unmapped, snapshot_status = snapshot_metadata(root, entries, now)
    legacy, legacy_counts, legacy_unmapped, legacy_status = legacy_metadata(
        root, entries, now.date(), expected_sha256=legacy_sha256
    )
    coverage = Counter()
    groups = {
        key: Counter()
        for key in (
            "calculator_eleven_sets",
            "outside_calculator_eleven_sets",
            "pokemon",
            "trainer_energy_or_other",
            "identified_species_above_251",
            "species_number_unavailable",
        )
    }
    metadata = Counter()
    sets = set()
    for pid, printing in entries.items():
        choices = snapshots[pid] | legacy[pid]
        selected_state = next((state for state in STATES if state in choices), "unpriced")
        coverage[selected_state] += 1
        sets.add(printing["set_id"])
        number = printing["attributes"].get("pokemon_dex")
        scope = (
            "calculator_eleven_sets"
            if printing["set_name"] in CALCULATOR_SETS
            else "outside_calculator_eleven_sets"
        )
        groups[scope][selected_state] += 1
        card_type = (
            "pokemon" if printing["attributes"].get("supertype") == "Pokémon" else "trainer_energy_or_other"
        )
        groups[card_type][selected_state] += 1
        if type(number) is int and number > 251:
            metadata["species_above_251_printings"] += 1
            groups["identified_species_above_251"][selected_state] += 1
        if type(number) is not int:
            groups["species_number_unavailable"][selected_state] += 1
        if printing["attributes"].get("supertype") != "Pokémon":
            metadata["trainer_energy_or_other_printings"] += 1
        if printing.get("language") != "en":
            metadata["non_english_printings"] += 1
    return {
        "evidence_class": (
            "synthetic engineering metadata audit; no provider acquisition or customer evidence"
            if (root / "SYNTHETIC_ONLY").is_file()
            else "actual-root read-only metadata audit; no provider acquisition or listing qualification"
        ),
        "audited_at": now.isoformat(),
        "catalog": {"printings": len(entries), "sets": len(sets), **metadata},
        "reference_coverage_by_printing": {state: coverage[state] for state in STATES},
        "reference_coverage_groups": {
            key: {"catalog_printings": sum(counts.values()), **{state: counts[state] for state in STATES}}
            for key, counts in groups.items()
        },
        "unmapped_reference_identities": {
            "snapshot": len(snapshot_unmapped),
            "retained": len(legacy_unmapped),
        },
        "snapshots": {"status": snapshot_status, **snapshot_counts},
        "retained_guides": {"status": legacy_status, **legacy_counts},
        "measurements_seconds": {
            "catalog_read_once": round(catalog_seconds, 6),
            "complete_metadata_audit": round(time.perf_counter() - started, 6),
        },
        "bounds": {
            "catalog_rows": MAX_CATALOG_ROWS,
            "bytes_per_json_file": rules.MAX_BYTES,
            "snapshot_rows_per_source": rules.MAX_ROWS,
            "snapshot_sources": MAX_SOURCES,
            "combined_snapshot_rows": rules.MAX_RELEASE_ROWS,
            "combined_snapshot_mappings": rules.MAX_RELEASE_MAPPINGS,
            "combined_snapshot_bytes": rules.MAX_RELEASE_BYTES,
            "retained_rows": MAX_LEGACY_ROWS,
        },
        "private_content_retained": False,
        "customer_writes": 0,
        "provider_operations": 0,
        "notes": [
            "Eligible means a locally admitted dated reference, with seller identity and condition applicability still required.",
            "Removed expired/withdrawn shards have unknown historical record counts; source counts remain explicit.",
            "Coverage counts the published local catalog once and does not bound marketplace acquisition.",
            "Coverage groups overlap; species-number metadata is not a complete all-generation catalog denominator.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = audit(args.root)
    except (AuditFailure, ValueError, KeyError, TypeError, OSError, sqlite3.DatabaseError):
        # Private JSON may contain source text in parser errors. Never print it.
        print(
            "Hunter metadata audit failed closed; no provider request or local cleanup was attempted.",
            file=sys.stderr,
        )
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
