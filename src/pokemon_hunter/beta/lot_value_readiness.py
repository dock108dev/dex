"""LV readiness over existing authorities, without Django setup or customer writes.

This operator projection is not an HTTP health check, price store, source admission
or appraisal. It does not read account records, credentials or seller evidence.
"""

import json
import sqlite3
from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from . import price_snapshot_contract as rules
from . import reference_inventory as inventory
from .account_read_schema import VERSION as ACCOUNT_VERSION
from .catalog_read_schema import POLICY, VERSION

PRIORITY = ("Base Set", "Jungle", "Fossil")
MAX_REPORT_BYTES = 4 * 1024 * 1024
ACTIONS = {
    "catalog_unavailable": "Inspect authoritative catalog/schema with the compatible runtime; do not initialize.",
    "runtime_incompatible": "Package and qualify the successor, then deliver its explicit read-schema transition.",
    "missing_snapshot": "Prepare an admitted reference release from permitted retained inputs; activation is separate.",
    "sources_expired": "Prepare a permitted replacement within a new finite acquisition scope if inputs are absent.",
    "sources_withdrawn": "Retain revocations; select a different independently admitted source.",
    "sources_unadmitted": "Resolve the exact independent contract review; the package cannot approve itself.",
    "sources_preparation_missing": "Explicitly prepare surviving source indexes through the supported activation route after authorization.",
    "sources_invalid": "Reconcile sealed source, catalog identity and contract; do not activate invalid input.",
    "raw_condition_capability_missing": "LV-02 must resolve a lawful condition-applicable raw contract/adapter; mixed-condition guides cannot supply it.",
    "no_eligible_raw_references": "Prepare current applicable raw references for the declared scope; approvals alone supply no coverage.",
    "no_condition_applicable_references": "Condition-specific ceilings remain unavailable; eligible broad guides can still be used.",
    "partial_coverage": "Report the uncovered printings explicitly; only supported contents may contribute a subtotal.",
    "fixture_evidence_only": "Use real independently admitted records before claiming customer price readiness.",
    "inspection_failed": "Inspect local metadata with the compatible operator; preserve state and do not repair on read.",
}


def compatibility(root):
    """Version/policy preflight only; the ordinary runtime owns full health checks."""
    path = root / "inventory.db"
    inventory.watch(path)
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=0.1)) as db:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        schemas = [r[0] for r in db.execute("SELECT version FROM catalog_read_schema LIMIT 3")]
        accounts = [r[0] for r in db.execute("SELECT version FROM account_read_schema LIMIT 3")]
        active = db.execute(
            "SELECT b.policy,b.status,b.revision=r.value FROM catalog_read_active a "
            "JOIN catalog_read_builds b ON b.id=a.build JOIN catalog_read_revision r ON r.id=a.id "
            "WHERE a.id=1 LIMIT 2"
        ).fetchall()
    matches = schemas == [VERSION] and accounts == [ACCOUNT_VERSION]
    policy_matches = len(active) == 1 and active[0][0] == POLICY
    current = len(active) == 1 and active[0][1:] == ("ready", 1)
    return {
        "check": "schema_policy_preflight_not_full_runtime_health",
        "catalog_schema_matches": schemas == [VERSION],
        "account_schema_matches": accounts == [ACCOUNT_VERSION],
        "catalog_policy_matches": policy_matches,
        "catalog_revision_current": current,
        "compatible_with_checkout": matches and policy_matches and current,
        "expected_catalog_schema": VERSION,
        "expected_account_schema": ACCOUNT_VERSION,
    }


def project(root, *, now=None, version=1):
    """Return metadata only. No output contains contracts, amounts or private IDs."""
    if version not in (1, 2, 3):
        raise ValueError("Unsupported readiness version")
    root = Path(root).expanduser().absolute()
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("An aware inspection time is required")
    now = now.astimezone(timezone.utc)
    try:
        with inventory.bounded() as budget:
            if root.is_symlink() or not root.is_dir() or root.resolve() != root:
                raise inventory.AuditFailure("Existing unlinked installation required")
            result = _project(root, now, version)
            result["bounds"] = {
                "seconds": 30,
                "catalog_rows": inventory.MAX_CATALOG_ROWS,
                "catalog_bytes": rules.MAX_CATALOG_BYTES,
                "json_file_bytes": rules.MAX_BYTES,
                "total_json_bytes": rules.MAX_RELEASE_BYTES + 4 * rules.MAX_BYTES,
                "source_rows": rules.MAX_ROWS,
                "release_rows": rules.MAX_RELEASE_ROWS,
                "sources": inventory.MAX_SOURCES,
                "report_bytes": MAX_REPORT_BYTES,
            }
            if len(json.dumps(result).encode()) > MAX_REPORT_BYTES:
                raise inventory.AuditFailure("Metadata report exceeds the finite byte limit")
            budget.check()
        return result
    except (
        inventory.AuditFailure,
        OSError,
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        RecursionError,
        sqlite3.DatabaseError,
    ):
        # Never stringify exceptions: source parsers can embed private record bytes.
        return {
            "schema": f"dex-lot-value-readiness-v{version}",
            "assessed_at": now.isoformat(),
            "state": "unavailable",
            "ready": False,
            "reasons": [dict(code="inspection_failed", action=ACTIONS["inspection_failed"])],
            "customer_writes": 0,
            "provider_operations": 0,
        }


def _project(root, now, version):
    entries = inventory.catalog_metadata(root)
    try:
        runtime = compatibility(root)
    except sqlite3.DatabaseError:
        runtime = {"compatible_with_checkout": False, "check": "schema_metadata_unavailable"}
    approval_path = root / "price-contracts.json"
    inventory.watch(approval_path)
    approvals = inventory.read_json(approval_path) if approval_path.exists() else {}
    if not isinstance(approvals, dict) or any(not inventory._valid_digest(v) for v in approvals.values()):
        raise inventory.AuditFailure("Invalid approvals")
    fixture_path = root / "SYNTHETIC_ONLY"
    inventory.watch(fixture_path)
    synthetic = fixture_path.is_file()
    references, eligible_raw, eligible_graded = Counter(), set(), set()
    dates, expiries, source_rights = set(), set(), Counter()
    eligible_sold, eligible_ceilings = set(), set()
    eligible_native, eligible_exact = set(), set()
    condition_sold, condition_guides = set(), set()
    variants = defaultdict(lambda: dict(catalog=set(), guide=set(), sold=set(), ceiling=set()))

    def observe(part, state):
        if state:
            return
        policy = part["contract"]
        if policy["provider"] == "dex-engineering-fixture":
            references["fixture_records"] += len(part["records"])
        for right, allowed in policy["rights"].items():
            source_rights[right + ("_allowed" if allowed else "_denied")] += 1
        if part["expires_at"]:
            expiries.add(part["expires_at"])
        for row in part["records"]:
            pid = row["printing_id"]
            reason = rules.reason(row, entries[pid], now.date())
            references["records_" + reason] += 1
            basis = "publisher_build" if "reference_as_of" in row else "valuation"
            references["date_basis_" + basis] += 1
            if rules.reference_date(row):
                dates.add(rules.reference_date(row))
            if row["grade"] != "raw":
                if reason == "eligible":
                    eligible_graded.add(pid)
                continue
            references["raw_records"] += 1
            if not row.get("condition"):
                references["raw_condition_unavailable"] += 1
            if row.get("valuation_qualification", "reviewed") != "reviewed":
                references["uncalibrated_records"] += 1
                continue
            if reason == "eligible":
                from .valuation_evidence import is_native

                if rules.exact_native_identity(row, entries[pid]):
                    eligible_exact.add(pid)
                if is_native(row):
                    eligible_native.add(pid)
                    continue
                p = entries[pid]
                variant_key = (p["set_id"], p.get("edition"), p.get("finish"), p.get("variant"))
                if row["estimate_kind"] == "dex_sold_estimate":
                    if row.get("condition") is not None:
                        condition_sold.add(pid)
                        continue
                    eligible_sold.add(pid)
                    variants[variant_key]["sold"].add(pid)
                    continue
                if row.get("condition") and row.get("ceiling_applicable"):
                    eligible_ceilings.add(pid)
                    variants[variant_key]["ceiling"].add(pid)
                if row.get("condition") is not None:
                    condition_guides.add(pid)
                    continue
                eligible_raw.add(pid)
                variants[variant_key]["guide"].add(pid)
                key = (
                    "conditional_market"
                    if row.get("match_scope") == "conditional_market"
                    else "condition_unspecified"
                )
                references["eligible_raw_" + key] += 1

    _, snapshot_counts, _, snapshot_status = inventory.snapshot_metadata(
        root, entries, now, observe=observe, require_prepared=True
    )
    legacy = Counter()
    legacy_dates = set()

    def legacy_observe(rows):
        for row in rows:
            legacy["records"] += 1
            if row.get("as_of"):
                legacy_dates.add(row["as_of"])
            legacy[
                "records_" + inventory.reference_policy.fresh(row.get("as_of"), now.date().isoformat())
            ] += 1
            if str(row.get("grade")) == "raw":
                legacy["raw_records"] += 1
                if not row.get("condition"):
                    legacy["raw_condition_unavailable"] += 1

    _, _, _, legacy_status = inventory.legacy_metadata(root, entries, now.date(), observe=legacy_observe)
    dimensions = {k: Counter() for k in ("language", "edition", "finish")}
    sets = defaultdict(Counter)
    for pid, printing in entries.items():
        variants[
            (printing["set_id"], printing.get("edition"), printing.get("finish"), printing.get("variant"))
        ]["catalog"].add(pid)
        for key, counts in dimensions.items():
            counts[printing.get(key) or "unresolved"] += 1
        group = sets[(printing["set_id"], printing["set_name"])]
        group["catalog_printings"] += 1
        complete = all(printing.get(k) for k in rules.IDENTITY)
        group["exact_identity_printings" if complete else "unresolved_identity_printings"] += 1
        group["eligible_raw_guide_printings"] += int(pid in eligible_raw)
        group["eligible_graded_guide_printings"] += int(pid in eligible_graded)
        group["eligible_sold_printings"] += int(pid in eligible_sold)
        group["strict_ceiling_applicable_printings"] += int(pid in eligible_ceilings)
    scope = []
    for (sid, name), counts in sorted(
        sets.items(),
        key=lambda item: (
            PRIORITY.index(item[0][1]) if item[0][1] in PRIORITY else 3,
            item[0][1],
            item[0][0],
        ),
    ):
        scope.append(
            dict(
                set_id=sid,
                set_name=name,
                preparation_priority=name in PRIORITY,
                exact_identity_printings=counts["exact_identity_printings"],
                unresolved_identity_printings=counts["unresolved_identity_printings"],
                **{
                    k: v
                    for k, v in counts.items()
                    if k not in {"exact_identity_printings", "unresolved_identity_printings"}
                },
                condition_applicable_raw_printings=0,
                missing_raw_guide_printings=counts["catalog_printings"]
                - counts["eligible_raw_guide_printings"],
            )
        )
    codes = []
    if not entries:
        codes.append("catalog_unavailable")
    if not runtime["compatible_with_checkout"]:
        codes.append("runtime_incompatible")
    if snapshot_status == "missing":
        codes.append("missing_snapshot")
    for state in ("expired", "withdrawn", "unadmitted", "invalid", "preparation_missing"):
        if snapshot_counts["sources_" + state]:
            codes.append("sources_" + state)
    if snapshot_counts["sources_fixture_rejected"]:
        codes.append("sources_invalid")
    if not eligible_raw:
        codes.append("no_eligible_raw_references")
    elif len(eligible_raw) < len(entries):
        codes.append("partial_coverage")
    codes.append("raw_condition_capability_missing")
    if synthetic:
        codes.append("fixture_evidence_only")
    result = {
        "schema": f"dex-lot-value-readiness-v{version}",
        "assessed_at": now.isoformat(),
        "evidence_class": "isolated_engineering" if synthetic else "actual_installation_metadata",
        "state": "blocked",
        "ready": False,
        "readiness_basis": "condition_applicable_ungraded_lot_value",
        "runtime": runtime,
        "catalog": {"printings": len(entries), "sets": len(scope), "scope": "all_published_pokemon"},
        "supported_scope": scope,
        "printing_dimensions": {k: dict(v) for k, v in dimensions.items()},
        "coverage": {
            "eligible_raw_guide_printings": len(eligible_raw),
            "condition_applicable_raw_printings": 0,
            "missing_condition_applicable_raw_printings": len(entries),
        },
        "snapshots": {
            "status": snapshot_status,
            **snapshot_counts,
            **references,
            "reference_dates": sorted(dates),
            "source_expiries": sorted(expiries),
            "rights_counts": dict(source_rights),
        },
        "retained_guides": {"status": legacy_status, **legacy, "reference_dates": sorted(legacy_dates)},
        "contract_approvals": len(approvals),
        "capabilities": {
            "offline_preparation": True,
            "explicit_activation": True,
            "scheduled_refresh": False,
            "raw_condition_snapshot_field": False,
            "provider_permission_verified_by_this_check": False,
        },
        "reasons": [dict(code=code, action=ACTIONS[code]) for code in dict.fromkeys(codes)],
        "customer_writes": 0,
        "provider_operations": 0,
    }

    if version in (2, 3):
        total = len(entries)
        ready_ids = eligible_raw | eligible_sold
        result["reasons"] = [
            r
            for r in result["reasons"]
            if r["code"]
            not in {"raw_condition_capability_missing", "no_eligible_raw_references", "partial_coverage"}
        ]
        if not ready_ids:
            result["reasons"].append(
                dict(code="no_eligible_raw_references", action=ACTIONS["no_eligible_raw_references"])
            )
        elif len(ready_ids) < total:
            result["reasons"].append(dict(code="partial_coverage", action=ACTIONS["partial_coverage"]))
        if not eligible_ceilings:
            result["reasons"].append(
                dict(
                    code="no_condition_applicable_references",
                    action=ACTIONS["no_condition_applicable_references"],
                )
            )
        for group in result["supported_scope"]:
            group["condition_applicable_raw_printings"] = group["strict_ceiling_applicable_printings"]
        result["readiness_basis"] = "per_printing_benchmark_not_whole_lot_or_runtime"
        result["state"] = (
            "ready" if total and len(ready_ids) == total else "partial" if ready_ids else "blocked"
        )
        result["ready"] = bool(total and len(ready_ids) == total and not synthetic)
        if synthetic:
            result["state"] = "isolated_engineering"
        result["coverage"].update(
            eligible_sold_printings=len(eligible_sold),
            condition_scoped_sold_printings=len(condition_sold),
            condition_scoped_guide_printings=len(condition_guides),
            eligible_benchmark_printings=len(ready_ids),
            missing_benchmark_printings=total - len(ready_ids),
            condition_applicable_raw_printings=len(eligible_ceilings),
            missing_condition_applicable_raw_printings=total - len(eligible_ceilings),
        )
        result["readiness"] = dict(
            source_access="not_established_by_metadata_inspection",
            sold_available=bool(eligible_sold) and not synthetic,
            guide_available=bool(eligible_raw) and not synthetic,
            strict_ceiling_available=bool(eligible_ceilings) and not synthetic,
            runtime_compatible=runtime["compatible_with_checkout"],
        )
        result["variant_coverage"] = [
            dict(
                set_id=key[0],
                edition=key[1],
                finish=key[2],
                variant=key[3],
                **{name + "_printings": len(ids) for name, ids in values.items()},
            )
            for key, values in sorted(variants.items(), key=lambda item: str(item[0]))
        ]
        result["capabilities"].update(
            raw_condition_snapshot_field=True,
            sold_evidence_contract=True,
            real_calibration_verified_by_this_check=False,
            offline_bounded_refresh=True,
        )
    if version == 3:
        from .catalog_variants import family_projection

        families = defaultdict(list)
        for printing in entries.values():
            parent = printing["attributes"].get("parent_printing_id")
            if parent:
                families[parent].append(printing)
        parents_with_alternatives = set()
        invalid_links = 0
        eligible = eligible_exact
        for parent, children in families.items():
            if parent not in entries:
                invalid_links += len(children)
                continue
            family = family_projection(entries[parent], children)
            for child in family["alternatives"]:
                if child["status"] != "supported":
                    invalid_links += 1
                elif child["child_id"] in eligible:
                    parents_with_alternatives.add(parent)
        result["coverage"].update(
            eligible_native_guide_printings=len(eligible_native),
            parents_with_eligible_priced_alternatives=len(parents_with_alternatives),
            linked_parent_entries=len(families),
            catalog_denominator=len(entries),
            unsupported_catalog_relations=invalid_links,
            source_absence="not_established_by_active_inventory",
        )
        result["readiness"]["native_guide_available"] = bool(eligible_native) and not synthetic
        result["capabilities"].update(publisher_native_guide=True, parent_alternative_measure=True)
        result["readiness_basis"] = "normalized_and_native_bases_reported_separately"
    return result
