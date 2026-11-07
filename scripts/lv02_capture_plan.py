"""Prepare the fixed LV-02 two-stage proposal offline. This never dispatches.

Stage two needs successful durable stage-one history and an explicitly reviewed
retained groups digest. No changed dates, groups, limits or retry identifiers.
"""

import argparse
import hashlib
import json
from pathlib import Path

from scripts import tcgcsv_capture_contract as contract
from scripts.tcgcsv_capture_history import _history, _read_private_json

GROUPS = [
    {"group_id": 604, "name": "Base Set"},
    {"group_id": 630, "name": "Fossil"},
    {"group_id": 635, "name": "Jungle"},
]
NOT_BEFORE = "2026-11-05T00:00:00Z"


def scope_digest(plan):
    return hashlib.sha256(contract._json_bytes({k: v for k, v in plan.items() if k != "plan_id"})).hexdigest()


def prepare(root, *, reviewed_groups_sha256=None):
    root = root.absolute()
    metadata = root.parent / ".dex-tcgcsv-metadata/attempts.json"
    accounting = root.parent / ".dex-tcgcsv-snapshots" / hashlib.sha256(str(root).encode()).hexdigest()
    # Read existing history; no mkdir, locks, reservations or replacement ledger.
    _history(accounting, metadata)
    limits = dict(
        contract.BATCH_LIMITS,
        file_bytes=8 * contract.MIB,
        total_seconds=35,
        aggregate_input_bytes=8 * contract.MIB,
        product_rows=30000,
        price_rows=30000,
    )
    first = contract.make_batch_plan(
        root,
        GROUPS,
        NOT_BEFORE,
        "0" * 64,
        plan_id="lv02-proof-metadata-once-v1",
        purpose="metadata_bootstrap",
        limits=limits,
    )
    first["metadata_ledger_path"] = str(metadata)
    contract.validate_batch_plan(first, root)
    if reviewed_groups_sha256 is None:
        return first
    selection = scope_digest(first)
    journal = accounting / ("batch-" + selection + ".jsonl")
    # The existing history reader already validates safety and the event grammar.
    events = [json.loads(line) for line in journal.read_bytes().splitlines()]
    if (
        events[0].get("plan_sha256") != contract.validate_batch_plan(first, root)
        or events[-1].get("stage") != "closed"
        or events[-1].get("status") != "captured"
        or events[-1].get("consumed") != 2
    ):
        raise ValueError("Successful exact metadata stage required; stopped stages cannot be retried")
    destination = root / "price-snapshots/staging/hunt11-batches" / selection
    path = destination / "groups.json"
    _read_private_json(path, 8 * contract.MIB)
    body = path.read_bytes()
    digest = hashlib.sha256(body).hexdigest()
    received = [e for e in events if e.get("stage") == "received" and e.get("filename") == "groups.json"]
    # Capture records are bounded noncontent evidence; the reviewer binds retained bytes separately.
    if len(received) != 1 or digest != reviewed_groups_sha256 or received[0].get("groups_sha256") != digest:
        raise ValueError("Exact retained group review digest required")
    contract._validate(body, "groups", groups=GROUPS)
    metadata_report = _read_private_json(destination / "capture-metadata.json", 65536)
    if (
        metadata_report.get("plan_sha256") != contract.validate_batch_plan(first, root)
        or metadata_report.get("provider_operations") != 2
        or metadata_report.get("status") != "captured"
    ):
        raise ValueError("Metadata capture receipt mismatch")
    second = contract.make_batch_plan(
        root,
        GROUPS,
        NOT_BEFORE,
        digest,
        plan_id="lv02-proof-groups-once-v1",
        purpose="refresh",
        refresh_cadence="selected_groups",
        limits=dict(limits, total_seconds=145, aggregate_input_bytes=48 * contract.MIB),
    )
    second.update(metadata_ledger_path=str(metadata), retained_groups_path=str(path.relative_to(root)))
    contract.validate_batch_plan(second, root)
    return second


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--reviewed-groups-sha256")
    args = parser.parse_args()
    plan = prepare(args.root, reviewed_groups_sha256=args.reviewed_groups_sha256)
    print(json.dumps(plan, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
