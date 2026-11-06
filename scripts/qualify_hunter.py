"""Bounded local Hunter coverage audit; aggregate metadata only, no acquisition.

This deliberately avoids the normal snapshot readers: their expiry/source pruning
is correct for comparison but can write. Private records are validated only in
memory. No private values, mappings, contracts, dates or source IDs enter output.
"""

import argparse
import json
import sqlite3
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from pokemon_hunter.beta import price_snapshot_contract as rules
from pokemon_hunter.beta.lot_calculator import SETS as CALCULATOR_SETS
from pokemon_hunter.beta.reference_inventory import (
    LEGACY_SHA256,
    MAX_CATALOG_ROWS,
    MAX_LEGACY_ROWS,
    MAX_SOURCES,
    STATES,
    AuditFailure,
    catalog_metadata,
    legacy_metadata,
    snapshot_metadata,
)
from pokemon_hunter.beta.reference_inventory import (
    _uuid as _uuid,
)
from pokemon_hunter.beta.reference_inventory import (
    read_json as read_json,
)


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
