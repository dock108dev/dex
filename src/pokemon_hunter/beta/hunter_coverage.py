"""Pure temporary comparison explanations over already admitted Hunter rows.

Primary dispositions remain mutually exclusive. Reasons overlap, count each row
at most once per reason, and never narrow retrieval or grant reference admission.
No roots, provider access, snapshot reads, prices or seller identities are needed
for aggregate reports. Ordinary reads must rebuild rows through hunter_catalog.
"""

from collections import Counter

from . import discovery_matching

MAX_ROWS = 800
LABELS = {
    "missing_catalog_identity": "Seller text does not identify a card in the local catalog",
    "multiple_printings": "Several printings remain plausible; confirm the exact printing",
    "missing_set_claim": "Seller text does not establish the catalog set",
    "missing_number_claim": "Seller text does not establish the collector number",
    "literal_number_conflict": "Seller collector-number claims conflict with the catalog or one another",
    "literal_set_conflict": "Seller set claims conflict with the proposed catalog printing",
    "language_conflict": "Seller language conflicts with another claim, the printing or reference",
    "finish_conflict": "Seller finish conflicts with another claim, the printing or reference",
    "edition_conflict": "Seller edition conflicts with another claim, the printing or reference",
    "condition_conflict": "Seller condition conflicts with another claim or the reference",
    "grading_conflict": "Literal grader or grade is conflicting, unsupported or inapplicable",
    "printing_claim_conflict": "Printing attributes are conflicting or unresolved",
    "catalog_unavailable": "The matching catalog printing or set is unavailable",
    "identity_incomplete": "Seller identity, edition, finish or condition still needs confirmation",
    "missing_reference": "No admitted reference is available for this exact printing and grade",
    "stale_reference": "The reference date is older than the permitted 30 days",
    "missing_reference_date": "A reference date is missing; capture time cannot establish freshness",
    "future_reference_date": "The reference date is in the future",
    "withdrawn_reference": "The reference or source has been withdrawn",
    "expired_reference": "The reference or source lease has expired",
    "unavailable_reference_source": "Reference sources are expired, withdrawn or no longer admitted",
    "invalid_reference_source": "The reference snapshot is invalid or unreviewed",
    "inapplicable_reference": "Available references do not fit this printing, condition or grade",
    "conditional_reference": "The admitted reference is conditional; it does not establish an exact match",
    "competing_references": "Competing reference observations remain separate",
    "unknown_listing_amount": "A supported USD listing amount is unavailable",
    "unknown_shipping": "Shipping is unknown",
    "unknown_tax": "Tax is unknown",
    "unknown_other_costs": "Other costs are unknown",
    "incomplete_delivered_cost": "Known costs form a subtotal; a complete delivered comparison is unavailable",
    "auction_scenario": "The current bid is an auction scenario, not the final purchase price",
    "lot_contents_review": "Loose-lot contents and quantities require review before a whole-lot comparison",
    "unreconciled_lot_contents": "The complete lot contents and quantities have not been reconciled",
    "unpriced_lot_contents": "Some reviewed lot contents have no applicable admitted reference",
    "unsupported_product": "Excluded product type; a single-card reference cannot value this offer",
    "unsupported_offer": "A supported auction or Buy It Now offer is unavailable",
    "locally_rejected": "The received offer is ended, unavailable or outside the captured Hunt scope",
}


def _result(codes, **fields):
    codes = sorted(set(codes).intersection(LABELS))
    return dict(codes=codes, reasons=[LABELS[code] for code in codes], **fields)


def identity_codes(candidates, clues):
    """Explain retained literal evidence without making another identity choice."""
    named = discovery_matching.literal_candidates(candidates, clues["text"])
    if not named:
        return ["missing_catalog_identity"]
    codes = []
    set_matches = [p for p in named if discovery_matching.set_claimed(p, clues["text"])]
    if not set_matches:
        codes.append("missing_set_claim")
    # Lack of a number and a contradictory number are distinct local causes.
    if not any(discovery_matching.number_claims(p, clues["text"]) for p in named):
        codes.append("missing_number_claim")
    if any(discovery_matching.evidence(p, clues)["conflicts"] for p in set_matches):
        codes.append("literal_number_conflict")
    return codes


def _reference_codes(row):
    """Translate existing content-free authority messages, never seller text.

    Older guide adapters supply fixed explanations rather than structured reason
    codes. Unknown unavailable causes stay unspecified; erased source records
    are never reconstructed to distinguish an unobserved historical withdrawal.
    """
    if row.get("reference"):
        return []
    text = str(row.get("reason", "")).casefold()
    status = str(row.get("reference_lifecycle_status", ""))
    codes = []
    for code, found in (
        ("stale_reference", "stale" in text or "older than 30 days" in text),
        ("missing_reference_date", "date missing" in text or "invalid_or_missing_date" in text),
        ("future_reference_date", "future" in text),
        ("withdrawn_reference", "withdrawn" in text or status == "withdrawn_snapshot"),
        ("expired_reference", "expired" in text or status == "expired_snapshot"),
        ("unavailable_reference_source", status == "sources_unavailable"),
        ("invalid_reference_source", status == "invalid_snapshot"),
    ):
        if found:
            codes.append(code)
    if any(
        token in text
        for token in ("conflict", "rejected", "unsupported grade", "not applicable", "no longer eligible")
    ):
        codes.append("inapplicable_reference")
    for token, code in (
        ("condition", "condition_conflict"),
        ("grader", "grading_conflict"),
        ("edition", "edition_conflict"),
        ("finish", "finish_conflict"),
        ("language", "language_conflict"),
    ):
        if "conflict" in text and token in text:
            codes.append(code)
    if not codes:
        codes.append("missing_reference")
    return codes


def diagnose(row, *, identity_reasons=()):
    """Describe one fresh projection; this function cannot admit a reference."""
    if row.get("hunt_status") == "rejected":
        return _result(
            ["locally_rejected"],
            admitted_reference=False,
            complete_delivered_comparison=False,
            conditional_opportunity=False,
        )
    kind = row.get("discovery_kind")
    if kind in {"mixed_lot", "unsupported"}:
        return _result(
            ["lot_contents_review" if kind == "mixed_lot" else "unsupported_product"],
            admitted_reference=False,
            complete_delivered_comparison=False,
            conditional_opportunity=False,
        )
    codes = list(identity_reasons)
    identity = row.get("identity_status")
    if identity == "unmatched":
        codes.append("missing_catalog_identity")
    if (
        identity == "ambiguous"
        or row.get("identity_candidates_total", 0) > 1
        and not row.get("proposed_identity")
    ):
        codes.append("multiple_printings")
    if identity == "unavailable":
        codes.append("catalog_unavailable")
    issues = " ".join(row.get("identity_diagnostics", [])).casefold()
    for token, code in (
        ("language", "language_conflict"),
        ("finish", "finish_conflict"),
        ("edition", "edition_conflict"),
        ("condition", "condition_conflict"),
        ("grader", "grading_conflict"),
        ("grade", "grading_conflict"),
        ("collector-number", "literal_number_conflict"),
        ("set claims", "literal_set_conflict"),
    ):
        if token in issues:
            codes.append(code)
    if identity == "conflicting" and not issues:
        codes.append("printing_claim_conflict")
    elif "special, altered" in issues or "unresolved printing" in issues:
        codes.append("printing_claim_conflict")
    if row.get("identity_uncertainties"):
        codes.append("identity_incomplete")
    admitted = bool(
        row.get("reference")
        and identity == "matched"
        and row.get("reference_eligibility") in {"eligible", "conditional"}
    )
    if admitted:
        ref = row["reference"]
        if ref.get("match_status") != "exact":
            codes.append("conditional_reference")
        proposed = row.get("proposed_identity") or {}
        if row.get("reference_eligibility") == "conditional" and (
            any(proposed.get(key) is None for key in ("language", "edition", "finish", "condition"))
            or ref.get("grader") != proposed.get("grader")
            and proposed.get("grade") != "raw"
        ):
            codes.append("identity_incomplete")
        if ref.get("conflicts"):
            codes.append("competing_references")
    elif (
        row.get("proposed_identity")
        and identity == "matched"
        and {"FIXED_PRICE", "AUCTION"}.intersection(row.get("buying_options", []))
    ):
        codes.extend(_reference_codes(row))
    scenarios = row.get("opportunity", {}).get("scenarios", [])
    supported = [s for s in scenarios if s.get("reference_amount") is not None]
    primary = next((s for s in supported if s.get("kind") == "buy_it_now"), None)
    scenario = primary or (supported[0] if supported else (scenarios[0] if scenarios else None))
    if scenario:
        if scenario.get("listing_amount") is None:
            codes.append("unknown_listing_amount")
        codes.extend("unknown_" + name for name in scenario.get("unknown_cost_components", []))
        if not scenario.get("delivered_cost_complete"):
            codes.append("incomplete_delivered_cost")
        if scenario.get("offer_meaning") == "auction_scenario":
            codes.append("auction_scenario")
    elif not {"FIXED_PRICE", "AUCTION"}.intersection(row.get("buying_options", [])):
        codes.append("unsupported_offer")
    complete = bool(
        admitted
        and primary
        and primary.get("applicability") == "eligible"
        and row["reference"].get("match_status") == "exact"
        and primary.get("delivered_cost_complete")
        and primary.get("complete_delivered_cost") is not None
    )
    return _result(
        codes,
        admitted_reference=admitted,
        complete_delivered_comparison=complete,
        conditional_opportunity=bool(
            admitted and scenario and scenario.get("gap", {}).get("amount") is not None and not complete
        ),
    )


def summarize(rows, *, fetched=None, retained=None):
    """Aggregate all retained rows, before local response paging, without I/O.

    ``fetched`` counts raw provider observations, including duplicates and rows
    not retained. Missing acquisition metadata stays null. Retained rows are the
    denominator for reasons and primary outcomes, never the fetched population.
    """
    if not isinstance(rows, list) or len(rows) > MAX_ROWS:
        raise ValueError("Coverage requires at most 800 retained rows")
    for value in (fetched, retained):
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError("Coverage counts must be nonnegative integers or null")
    if retained is not None and retained != len(rows):
        raise ValueError("Retained coverage denominator must match the projected rows")
    outcomes, reasons = Counter(), Counter()
    denominators = Counter(
        dict.fromkeys(
            (
                "eligible_singles",
                "lots",
                "excluded_products",
                "matched_identities",
                "admitted_references",
                "complete_comparisons",
                "conditional_opportunities",
            ),
            0,
        )
    )
    for row in rows:
        diagnostic = row.get("comparison_diagnostics") or diagnose(row)
        outcomes[row.get("hunt_status", "unpriced")] += 1
        reasons.update(set(diagnostic["codes"]).intersection(LABELS))
        eligible = row.get("hunt_status") != "rejected"
        denominators["eligible_singles"] += bool(eligible and row.get("discovery_kind") == "single")
        denominators["lots"] += bool(eligible and row.get("discovery_kind") == "mixed_lot")
        denominators["excluded_products"] += bool(eligible and row.get("discovery_kind") == "unsupported")
        denominators["matched_identities"] += bool(eligible and row.get("identity_status") == "matched")
        denominators["admitted_references"] += diagnostic["admitted_reference"]
        denominators["complete_comparisons"] += diagnostic["complete_delivered_comparison"]
        denominators["conditional_opportunities"] += diagnostic["conditional_opportunity"]
    return dict(
        denominators=dict(fetched=fetched, retained=len(rows), **denominators),
        primary_outcomes=dict(outcomes),
        reason_counts=dict(sorted(reasons.items())),
        reason_labels={code: LABELS[code] for code in sorted(reasons)},
        reason_denominator="retained",
        reasons_overlap=True,
        complete_comparison_meaning="Exact applicable reference and available Buy It Now offer with shipping, tax and other costs all explicitly known",
        legacy_priced_meaning="Legacy priced status admits a literal reference; it does not establish a complete delivered comparison",
    )


def lot_diagnostics(*, reconciled, unknown_contents, unpriced_units, costs, reference_count):
    """Explain a reviewed lot's unknown remainder, reference gaps and costs."""
    codes = []
    if not reconciled or unknown_contents is None or unknown_contents:
        codes.append("unreconciled_lot_contents")
    if unpriced_units:
        codes.append("unpriced_lot_contents")
    if not reference_count:
        codes.append("missing_reference")
    for key in ("shipping", "tax", "other_costs"):
        if costs.get(key) in (None, ""):
            codes.append("unknown_" + key)
    if costs.get("price") in (None, ""):
        codes.append("unknown_listing_amount")
    if any(code.startswith("unknown_") for code in codes):
        codes.append("incomplete_delivered_cost")
    if costs.get("price_kind") == "current_bid":
        codes.append("auction_scenario")
    return _result(codes)
