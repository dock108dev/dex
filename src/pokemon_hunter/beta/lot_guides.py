"""Guide cells over admitted records, independent of selectors and persistence.

Both browse and evaluation use this projection. Source rights/expiry admission
remain with the snapshot lifecycle; this module never loads or acquires records.
"""

import json
from copy import deepcopy

from pokemon_hunter import reference_policy as references

from . import price_snapshot_contract as snapshot_rules
from . import shopping
from . import shopping_math as math

COLUMNS = snapshot_rules.COLUMNS


def legacy_cells(printing, records, today):
    key = json.loads(printing["provenance"]).get("legacy_id")
    result = {}
    for grade in COLUMNS:
        candidates = []
        for row in records:
            if not isinstance(row, dict) or row.get("card_id") != key or str(row.get("grade")) != grade:
                continue
            edition = printing.get("edition") or "standard"
            reason = "eligible"
            if row.get("edition") != edition or references.valid_record(row, today, guide=True) is None:
                reason = "edition_currency_source_date_or_amount_unavailable"
            elif grade != "raw" and (row.get("estimated") or not row.get("grader")):
                reason = "estimated_or_unknown_graded_basis"
            elif any(row.get(k) not in (None, printing.get(k)) for k in ("language", "finish", "variant")):
                reason = "conflicting_printing_identity"
            elif grade == "raw" and row.get("grader") not in {"Guide", "PSA"}:
                reason = "unsupported_raw_basis"
            # Generic grade fields retain the literal grader; no PSA8/9 mapping.
            ref = dict(
                reference_id="retained-" + shopping.digest(row),
                kind="guide",
                value_scope="per_card",
                amount=row.get("value"),
                currency=row.get("currency"),
                as_of=row.get("as_of"),
                source_url=row.get("source_url"),
                grade=grade,
                grader=row.get("grader"),
                estimated=row.get("estimated"),
                edition=row.get("edition"),
                raw_record=deepcopy(row),
                record_sha256=shopping.digest(row),
                printing_id=printing["id"],
                provenance="retained_guide_conditional",
                match_status="conditional" if reason == "eligible" else "unavailable",
                assumptions=[
                    "Catalog fit and physical condition are conditional; generic grader is not certification."
                ],
                admission="preexisting_retained_guide_boundary",
                basis_eligibility=reason,
            )
            ref["eligibility"] = math.eligibility(ref, today.isoformat())
            if ref["eligibility"] == "eligible":
                candidates.append(ref)
        result[grade] = max(candidates, key=lambda r: r["as_of"]) if candidates else None
    return result


def cell_details(printing, records, today):
    old = legacy_cells(printing, [r for r in records if "_snapshot_version" not in r], today)
    result, reasons = dict(old), {}
    for grade in COLUMNS:
        matching = [
            r
            for r in records
            if r.get("printing_id") == printing["id"] and r.get("grade") == grade and "_snapshot_version" in r
        ]
        eligible = [r for r in matching if snapshot_rules.reason(r, printing, today) == "eligible"]
        if eligible:
            # Newest admitted date basis, then capture; provenance breaks exact ties.
            # No averaging or silent grader/printing equivalence is introduced.
            def rank(r):
                return (
                    snapshot_rules.reference_date(r),
                    snapshot_rules.timestamp(r["captured_at"]),
                    r["grader"],
                    r["_contract_sha256"],
                    r["observation_id"],
                )

            row = max(eligible, key=rank)
            if old[grade] is None or snapshot_rules.reference_date(row) >= old[grade]["as_of"]:
                conditional = row.get("match_scope") == "conditional_market"
                result[grade] = dict(
                    reference_id="snapshot-" + row["observation_id"],
                    kind="guide",
                    value_scope="per_card",
                    amount=row["value"],
                    currency=row["currency"],
                    as_of=snapshot_rules.reference_date(row),
                    valuation_as_of=row["as_of"],
                    date_basis="publisher_build" if "reference_as_of" in row else "valuation",
                    publisher_built_at=row.get("publisher_built_at"),
                    source_url=row["source_url"],
                    source_version=row["source_version"],
                    grade=grade,
                    grader=row["grader"],
                    estimated=row["estimated"],
                    estimate_kind=row["estimate_kind"],
                    captured_at=row["captured_at"],
                    provider_identity=row["provider_identity"],
                    printing_id=printing["id"],
                    provenance="reviewed_private_snapshot",
                    raw_record=deepcopy(row),
                    record_sha256=shopping.digest(row),
                    snapshot_version=row["_snapshot_version"],
                    match_status="conditional" if conditional else "exact",
                    assumptions=[
                        "TCGplayer market reference across conditions; verify edition and finish against your card. "
                        + "Provider subtype: "
                        + row["provider_identity"]["variant"]
                    ]
                    if conditional
                    else [],
                    admission="reviewed_snapshot_contract",
                    eligibility="eligible",
                    basis_eligibility="eligible",
                    save_allowed=row["_save_allowed"],
                    expires_at=row["_expires_at"],
                    source_contract=row["_contract_sha256"],
                    source_review=row["_review_id"],
                    conflicts=[
                        dict(
                            source_contract=other["_contract_sha256"],
                            source_review=other["_review_id"],
                            source_url=other["source_url"],
                            as_of=snapshot_rules.reference_date(other),
                            date_basis="publisher_build" if "reference_as_of" in other else "valuation",
                            grader=other["grader"],
                            expires_at=other["_expires_at"],
                            save_allowed=other["_save_allowed"],
                            explanation="Competing source observation; not averaged or treated as the same grader",
                        )
                        for other in sorted(eligible, key=rank, reverse=True)
                        if other != row
                    ],
                )
        issues = [snapshot_rules.reason(r, printing, today) for r in matching]
        key = json.loads(printing["provenance"]).get("legacy_id")
        historic = [
            r
            for r in records
            if "_snapshot_version" not in r and r.get("card_id") == key and str(r.get("grade")) == grade
        ]
        if result[grade]:
            reasons[grade] = (
                "Conditional ungraded market reference; verify edition and condition"
                if result[grade].get("match_status") == "conditional"
                and result[grade].get("snapshot_version")
                else "Available reviewed snapshot"
                if result[grade].get("snapshot_version")
                else ("Legacy September reference; capture and provider valuation dates unverified")
            )
        elif issues:
            labels = {
                "invalid_or_missing_date": "Provider valuation date missing; capture date cannot establish freshness",
                "stale": "Provider valuation date is older than 30 days",
                "future": "Provider valuation date is in the future",
                "rejected_installed_identity": "Rejected: installed printing identity changed",
                "rejected_provider_identity": "Rejected: provider set or number conflicts",
                "rejected_unresolved_or_conflicting_variant": "Rejected: edition, finish or variant fit is unresolved",
            }
            reasons[grade] = "; ".join(sorted({labels.get(issue, issue) for issue in issues}))
        elif historic:
            age = math.fresh(historic[0].get("as_of"), today.isoformat())
            reasons[grade] = age if age != "eligible" else "Rejected identity or unsupported grade basis"
        else:
            status = getattr(records, "status", "active_snapshot")
            reasons[grade] = {
                "missing_snapshot": "No active private snapshot; no retained observation for this printing and grade",
                "invalid_snapshot": "Private snapshot is invalid or unreviewed; no eligible retained observation",
            }.get(status, "Missing observation for this exact printing and grade")
    return result, reasons


def cells(printing, records, today):
    return cell_details(printing, records, today)[0]
