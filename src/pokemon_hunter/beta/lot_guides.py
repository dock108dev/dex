"""Guide cells over admitted records, independent of selectors and persistence.

Both browse and evaluation use this projection. Source rights/expiry admission
remain with the snapshot lifecycle; this module never loads or acquires records.
"""

import json
from copy import deepcopy

from pokemon_hunter import reference_policy as references

from . import price_snapshot_contract as snapshot_rules
from . import shopping, valuation_evidence
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
    source_status = getattr(records, "status", "active_snapshot")
    records = [
        r
        for r in records
        if not valuation_evidence.is_native(r)
        and r.get("estimate_kind") != "dex_sold_estimate"
        and r.get("valuation_qualification", "reviewed") == "reviewed"
    ]
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
                            source_version=other["source_version"],
                            as_of=snapshot_rules.reference_date(other),
                            valuation_as_of=other["as_of"],
                            date_basis="publisher_build" if "reference_as_of" in other else "valuation",
                            publisher_built_at=other.get("publisher_built_at"),
                            captured_at=other["captured_at"],
                            grade=other["grade"],
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
                "invalid_or_missing_date": "Reference date missing; capture date cannot establish freshness",
                "stale": "Reference date is older than 30 days",
                "future": "Reference date is in the future",
                "rejected_installed_identity": "Rejected: installed printing identity changed",
                "rejected_provider_identity": "Rejected: provider set or number conflicts",
                "rejected_unresolved_or_conflicting_variant": "Rejected: edition, finish or variant fit is unresolved",
            }
            reasons[grade] = "; ".join(sorted({labels.get(issue, issue) for issue in issues}))
        elif historic:
            age = math.fresh(historic[0].get("as_of"), today.isoformat())
            reasons[grade] = age if age != "eligible" else "Rejected identity or unsupported grade basis"
        else:
            status = source_status
            reasons[grade] = {
                "missing_snapshot": "No active private snapshot; no retained observation for this printing and grade",
                "invalid_snapshot": "Private snapshot is invalid or unreviewed; no eligible retained observation",
            }.get(status, "Missing observation for this exact printing and grade")
    return result, reasons


def cells(printing, records, today):
    return cell_details(printing, records, today)[0]


def normalized_cell(printing, records, today, *, condition=None):
    """Benchmark-only sold-first selector. Strict guide/ceiling callers stay separate."""
    selected = valuation_evidence.select(
        printing,
        [r for r in records if "_snapshot_version" in r],
        today=today,
        condition=condition,
    )
    row = selected["reference"]
    if row is None:
        return None
    estimate = row.get("evidence", {}).get("estimate")
    return dict(
        reference_id="snapshot-" + row["observation_id"],
        evidence_id=row["observation_id"],
        kind="guide",  # Existing calculator ingress; basis owns the displayed semantics.
        basis=selected["basis"],
        amount_basis="item_excluding_shipping_tax",
        method=estimate["policy"] if estimate else dict(method="publisher_guide"),
        sample={
            k: estimate[k]
            for k in (
                "unique_sales",
                "effective_sample_size",
                "excluded",
                "sold_from",
                "sold_through",
                "spread",
                "condition_strata",
                "calculated_at",
            )
        }
        if estimate
        else None,
        amount=row["value"],
        currency=row["currency"],
        value_scope="per_card",
        as_of=snapshot_rules.reference_date(row),
        valuation_as_of=row["as_of"],
        date_basis="publisher_build" if "reference_as_of" in row else "valuation",
        publisher_built_at=row.get("publisher_built_at"),
        captured_at=row["captured_at"],
        source_url=row["source_url"],
        source_version=row["source_version"],
        grade="raw",
        grader=row["grader"],
        estimated=row["estimated"],
        provider_identity=row["provider_identity"],
        printing_id=printing["id"],
        provenance="reviewed_private_snapshot",
        raw_record=deepcopy(row),
        record_sha256=shopping.digest(row),
        snapshot_version=row["_snapshot_version"],
        match_status="conditional" if row.get("match_scope") else "exact",
        assumptions=["Mixed-condition guide benchmark; not a condition-specific appraisal"]
        if row.get("match_scope")
        else [],
        admission="reviewed_snapshot_contract",
        eligibility="eligible",
        basis_eligibility="eligible",
        save_allowed=False,
        expires_at=row["_expires_at"],
        source_contract=row["_contract_sha256"],
        source_review=row["_review_id"],
    )


def native_cell(printing, records, today):
    """Separate display-only basis over lifecycle-admitted rows, never legacy cells."""
    rows = [r for r in records if "_snapshot_version" in r and r.get("_native_context")]
    selected = valuation_evidence.select(printing, rows, today=today, purpose="native")
    row = selected["reference"]
    if row is None:
        return None
    return dict(
        reference_id="snapshot-" + row["observation_id"],
        printing_id=printing["id"],
        evidence_id=row["observation_id"],
        basis=valuation_evidence.NATIVE,
        amount_basis=valuation_evidence.NATIVE_AMOUNT,
        native_money=dict(row["evidence"]["native_money"]),
        cohort=valuation_evidence.native_cohort(row),
        provider=row["_native_context"]["provider"],
        field=row["field"],
        amount=row["value"],
        currency=row["currency"],
        grade="raw",
        grader=row["grader"],
        condition=None,
        estimated=True,
        match_status="exact",
        value_scope="per_card",
        as_of=snapshot_rules.reference_date(row),
        valuation_as_of=row["as_of"],
        date_basis="publisher_build" if "reference_as_of" in row else "valuation",
        publisher_built_at=row.get("publisher_built_at"),
        captured_at=row["captured_at"],
        source_url=row["source_url"],
        source_version=row["source_version"],
        source_contract=row["_contract_sha256"],
        source_review=row["_review_id"],
        snapshot_version=row["_snapshot_version"],
        expires_at=row["_expires_at"],
        save_allowed=False,
        provider_identity=dict(row["provider_identity"]),
        capabilities=dict(
            display=True,
            native_arithmetic=True,
            normalized=False,
            delivered_comparison=False,
            sold=False,
            strict_ceiling=False,
        ),
    )


def family_alternatives(proposal, entries, records, today):
    """Ephemeral per-alternative display; no selection or family-total arithmetic."""
    from . import catalog_variants, discovery_comparison, hunter_catalog

    catalog = {p["id"]: p for p in entries}
    index = hunter_catalog.ReferenceIndex(records)
    result = []
    for line in proposal["proposals"]:
        binding = line.get("variant_selection")
        if not binding or not binding.get("alternatives"):
            continue
        parent = catalog.get(binding["parent_id"])
        if parent is None:
            continue
        expected = {
            k: binding[k]
            for k in ("parent_id", "parent_sha256", "catalog_version", "membership", "alternatives")
        }
        children = [catalog[a["child_id"]] for a in binding["alternatives"] if a["child_id"] in catalog]
        family = catalog_variants.family_projection(parent, children, expected=expected)
        alternatives = []
        for relation in family["alternatives"]:
            child = catalog[relation["child_id"]]
            ref = (
                native_cell(child, index.for_printing(child), today)
                if relation["status"] == "supported"
                else None
            )
            alternatives.append(
                dict(
                    child_id=child["id"],
                    name=child["name"],
                    edition=child.get("edition"),
                    finish=child.get("finish"),
                    language=child.get("language"),
                    descriptor=relation["descriptor"],
                    status=relation["status"],
                    variant_label=child.get("attributes", {}).get("variant_label")
                    or catalog_variants.label(relation["descriptor"])
                    if relation["status"] == "supported"
                    else "Physical descriptor requires review",
                    reference=discovery_comparison._reference(ref) if ref else None,
                )
            )
        result.append(
            dict(
                line_id=line["proposal_id"],
                parent_id=parent["id"],
                quantity=line["quantity"],
                selected_child_id=binding.get("selected_child_id"),
                membership=family["membership"],
                alternatives=alternatives,
            )
        )
    return result
