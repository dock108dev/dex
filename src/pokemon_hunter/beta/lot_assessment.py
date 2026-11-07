"""Conditional reference parity for explicitly included units of a reviewed lot."""

import json
from decimal import ROUND_CEILING, ROUND_FLOOR

from . import discovery_comparison as dc
from . import lot_guides, shopping_contents
from . import shopping_math as math


def tax_due(base, shipping, percent):
    return ((base + shipping) * percent / 100).quantize(math.CENT, rounding=ROUND_CEILING)


def ceiling(limit, fixed, shipping, rate):
    # Monotonic nonnegative costs. Search whole cents and check the unrounded limit.
    lo, hi = -1, int((limit / math.CENT).to_integral_value(rounding=ROUND_FLOOR))
    while lo < hi:
        mid = (lo + hi + 1) // 2
        bid = mid * math.CENT
        if bid + fixed + tax_due(bid, shipping, rate) <= limit:
            lo = mid
        else:
            hi = mid - 1
    return lo * math.CENT if lo >= 0 else None


def applicable(p, row, records, today):
    grade = row.get("grade")
    condition = dc._condition(row.get("condition"))
    grader = row.get("grader")
    if grade == "raw" and not condition:
        return None, "Specify the assessed raw condition"
    if grade != "raw" and (grade not in lot_guides.COLUMNS or grader not in {"PSA", "BGS", "SGC", "CGC"}):
        return None, "Specify the grade and literal grader"
    clues = {key: row.get(key) for key in ("language", "edition", "finish", "condition", "grader")}
    clues["graded"] = grade != "raw"
    admitted = []
    legacy = json.loads(p["provenance"]).get("legacy_id")
    for record in records:
        from .valuation_evidence import is_native

        if is_native(record):
            continue
        if record.get("estimate_kind") == "dex_sold_estimate":
            continue  # A median benchmark is not a strict bid ceiling.
        if "evidence" in record and record.get("ceiling_applicable") is not True:
            continue
        if str(record.get("grade")) != grade:
            continue
        snapshot = "_snapshot_version" in record
        if snapshot and record.get("printing_id") != p["id"]:
            continue
        if not snapshot and (not legacy or record.get("card_id") != legacy):
            continue
        if record.get("match_scope") == "conditional_market":
            continue
        identity = record.get("provider_identity") if snapshot else record
        if any(not p.get(k) or identity.get(k) != p[k] for k in ("language", "edition", "finish", "variant")):
            continue
        if grade == "raw" and dc._condition(record.get("condition")) != condition:
            continue
        if grade != "raw" and record.get("grader") != grader:
            continue
        admitted.append(record)
    ref = lot_guides.cells(p, admitted, today).get(grade)
    if not ref:
        return (
            None,
            f"No current admitted reference matching this printing and {condition if grade == 'raw' else f'{grader} {grade}'}",
        )
    return ref, dc.reference_issue(p, clues, ref, today)


def seller_constraints(offers, entries, included, units):
    # Rebuild seller constraints from the leased source and the server catalog.
    # Client-side contents groups and their candidate alternatives have no authority.
    issues, disputed = [], set()
    for offer in offers:
        projected = dict(offer)
        groups = shopping_contents.project(projected, list(entries.values()))
        for group in groups:
            ids = {p["id"] for p in group["candidates"]} & included.keys()
            for reason in group["reasons"]:
                if any(
                    word in reason.casefold()
                    for word in ("conflict", "contradict", "does not establish an included")
                ):
                    issues.append(f"{group['name']}: {reason}.")
                    disputed.update(ids)
            selected = [p for p in group["candidates"] if p["id"] in included]
            if (
                group["quantity"] is not None
                and selected
                and sum(included[p["id"]]["quantity"] for p in selected) != group["quantity"]
            ):
                disputed.update(ids)
                issues.append(
                    f"Reconcile the printing and quantity for {group['name']} with the seller evidence."
                )
            elif group["quantity"] and not selected:
                issues.append(f"Resolve the seller’s stated contents for {group['name']}.")
        if projected.get("seller_lot_size") not in (None, units):
            issues.append("Included quantities differ from the leased seller count.")
        issues.extend(projected["clues"]["conflicts"])
        for row in included.values():
            clues = projected["clues"]
            if (
                clues.get("condition_claims")
                and dc._condition(row.get("condition")) not in clues["condition_claims"]
                or clues.get("graded")
                and (row.get("grade"), row.get("grader")) != (clues.get("grade"), clues.get("grader"))
                or dc._identity_conflicts(entries[row["printing_id"]], clues)
            ):
                p = entries[row["printing_id"]]
                disputed.add(p["id"])
                reason = (
                    "the seller's condition claim has not been matched to an assessed raw condition; condition-specific value is unavailable."
                    if clues.get("condition_claims") and dc._condition(row.get("condition")) is None
                    else "the reviewed condition, grade or printing conflicts with the seller evidence."
                )
                issues.append(f"{p['name']} #{p['collector_number']}: {reason}")
    return issues, disputed


def assess(value, entries, records, today, comparisons, offers, request):
    included = {r["printing_id"]: r for r in value["cards"] if r["quantity"]}
    units = sum(r["quantity"] for r in included.values())
    issues, disputed = seller_constraints(offers, entries, included, units)
    if getattr(records, "status", None) == "invalid_snapshot":
        issues.append(
            "Private reference preparation is invalid. Revalidate the release before relying on a bid."
        )
    evidence, terms = [], []
    priced = 0
    for row in included.values():
        if row["printing_id"] in disputed:
            continue
        qty = row["quantity"]
        p = entries[row["printing_id"]]
        name = f"{p['name']} · {p['set_name']} #{p['collector_number']} · " + " / ".join(
            str(p.get(k) or "unknown") for k in ("language", "edition", "finish", "variant")
        )
        ref, issue = applicable(p, row, records, today)
        if issue:
            issues.append(f"{name}: {issue}.")
            continue
        term = math.amount(ref["amount"]) * qty
        terms.append(term)
        priced += qty
        evidence.append(
            dict(dc._reference(ref), printing_id=p["id"], name=name, quantity=qty, extended=math.money(term))
        )
    subtotal = math.bounded_sum(terms, "subtotal_above_cap")
    if not units:
        issues.append("Include the reviewed cards and their quantities.")
    if value["unknown_contents"] != 0:
        issues.append("Resolve the remaining unidentified cards.")
    if value.get("seller_card_count") not in (None, units):
        issues.append("Reconcile included quantities with the seller’s stated card count.")
    full = None if issues else subtotal
    auction = value.get("price_kind") == "current_bid"
    result = dict(
        auction=auction,
        costs={
            basis: {
                key: c[key]
                for key in (
                    "base_price",
                    "base_plus_shipping",
                    "before_tax",
                    "full_delivered_cost",
                    "unknown_or_ineligible_components",
                )
            }
            for basis, c in comparisons.items()
        },
        evidence=evidence,
        issues=issues,
        units=units,
        priced=priced,
        subtotal=math.money(subtotal),
        value=math.money(full),
        maximum=None,
    )
    if full is not None:
        for basis, cost in result["costs"].items():
            if cost["full_delivered_cost"] is not None:
                components = [request[basis], *request["delivery_cost_inputs"][basis].values()]
                delivered = sum(math.amount(c["amount"]) for c in components)
                cost["reference_difference"] = math.money(full - delivered)
    if not auction:
        return result
    if not offers:
        issues.append("Open a current auction in Shopping to verify the offer.")
    for key in math.COSTS:
        if key == "tax" and value.get("tax_rate"):
            continue
        if not value.get(key):
            issues.append(f"Enter {key.replace('_', ' ')} or confirm zero.")
    if value["currency"] != "USD" or any(o["price"]["currency"] not in (None, "USD") for o in offers):
        issues.append("USD cost inputs are required.")
    if not value.get("budget"):
        issues.append("Enter your all-in USD budget.")
    if issues:
        return result
    shipping = math.amount(value["shipping"])
    rate = math.amount(value.get("tax_rate") or "0")
    fixed = shipping + math.amount(value.get("tax") or "0") + math.amount(value["other_costs"])
    budget = math.amount(value["budget"])
    v, b = (ceiling(limit, fixed, shipping, rate) for limit in (full, budget))
    result.update(
        value_limit=math.money(v),
        budget_limit=math.money(b),
        budget=math.money(budget),
        binding="both" if v == b else "reference value" if full < budget else "budget",
    )
    if v is None or b is None:
        issues.append("No affordable bid. Mandatory costs alone exceed the limit.")
        return result
    maximum = min(v, b)
    result.update(maximum=math.money(maximum))
    for key in ("price", "planned_bid"):
        result[key + "_above"] = math.amount(value[key]) > maximum if value.get(key) else None
    return result
