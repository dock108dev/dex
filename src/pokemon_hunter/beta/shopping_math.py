"""Exact USD arithmetic over captured, authority-validated projections.

No catalog, ownership writers, provider access or persistence in this module.
"""

import re
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal, localcontext

CAP = Decimal("1000000000000")
CENT = Decimal("0.01")
BASES = ("listing_observation", "planned_bid")
COSTS = ("shipping", "tax", "other_costs")


def amount(value):
    if not isinstance(value, str) or not re.fullmatch(r"(?:0|[1-9][0-9]{0,12})(?:\.[0-9]{1,6})?", value):
        raise ValueError("invalid_decimal_string_or_precision")
    result = Decimal(value)
    if result > CAP:
        raise ValueError("amount_above_cap")
    return result


def quantity(value):
    if type(value) is not int or not 1 <= value <= 100000:
        raise ValueError("invalid_quantity")
    return value


def money(value):
    if value is None:
        return None
    rounded = value.quantize(CENT, rounding=ROUND_HALF_EVEN)
    return format(abs(rounded) if rounded == 0 else rounded, ".2f")


def fresh(as_of, evaluation_date):
    try:
        age = (date.fromisoformat(evaluation_date) - date.fromisoformat(as_of)).days
        return "eligible" if 0 <= age <= 30 else "future" if age < 0 else "stale"
    except (ValueError, TypeError):
        return "invalid_or_missing_date"


def eligibility(ref, today):
    if ref.get("amount") is None:
        return "missing_amount"
    try:
        amount(ref["amount"])
    except ValueError as exc:
        return str(exc)
    if ref.get("currency") != "USD":
        return "unsupported_or_missing_currency"
    age = fresh(ref.get("as_of"), today)
    if age != "eligible":
        return age
    if ref.get("match_status") not in {"exact", "conditional"}:
        return "unresolved_or_conflicting_value_basis"
    if ref.get("match_status") == "conditional" and not ref.get("assumptions"):
        return "conditional_without_assumptions"
    return "eligible"


def bounded_sum(values, reason):
    result = sum(values, Decimal(0)) if values else None
    if result is not None and result > CAP:
        raise ValueError(reason)
    return result


def fraction(n, d):
    return [n, d] if d else None


def useful_values(data, selected, refs, terms):
    goal = data.get("frozen_goal")
    unavailable = dict(
        status="unavailable",
        reason="no_frozen_goal",
        known_useful_subtotal=None,
        full_useful_total=None,
        confirmed_distinct_gain=None,
        full_distinct_gain=None,
    )
    if not goal:
        return unavailable, None, None
    if data["ownership_context"].get("availability") != "complete":
        return dict(unavailable, reason="unavailable_ownership_context"), None, None
    owned = set(goal["owned_item_ids"])
    remaining = {i["item_id"] for i in goal["items"]} - owned
    useful = dict.fromkeys(selected, 0)
    representatives, unknown = [], []
    for sid, line in sorted(selected.items()):
        matches = [i for i in goal["items"] if line["printing_id"] in i["printing_ids"]]
        # One physical unit cannot satisfy several checklist slots of one goal.
        if len(matches) > 1:
            raise ValueError("conflicting_goal_item_mapping")
        if line["completion_identity_status"] == "unknown":
            if any(i["item_id"] in remaining for i in matches) or line["printing_id"] is None:
                unknown.append(sid)
            continue
        for item in sorted(matches, key=lambda i: i["item_id"]):
            if item["item_id"] in remaining:
                useful[sid] += 1
                representatives.append(dict(selection_id=sid, item_id=item["item_id"], unit=1))
                remaining.remove(item["item_id"])
    values, allocated, unallocated = [], 0, []
    for term in terms:
        u = sum(useful[sid] for sid in term["selection_ids"])
        if not u:
            continue
        if term["value_scope"] == "selection_group_total":
            if u != sum(selected[sid]["quantity"] for sid in term["selection_ids"]):
                unallocated.append(term["reference_id"])
                continue
            values.append(term["exact"])
        else:
            values.append(amount(refs[term["reference_id"]]["amount"]) * u)
        allocated += u
    count = sum(useful.values())
    known = bounded_sum(values, "useful_subtotal_above_cap")
    if not count and not unknown:
        known = Decimal(0)
    full = known if allocated == count and not unknown else None
    won = sorted(r["item_id"] for r in representatives)
    result = dict(
        status="full" if full is not None else "partial" if known is not None else "unavailable",
        policy=goal["policy"],
        goal_id=goal["goal_id"],
        definition_sha256=goal["definition_sha256"],
        owned_item_ids=sorted(owned),
        incremental_item_ids=won,
        confirmed_distinct_gain=len(won),
        full_distinct_gain=len(won) if not unknown else None,
        unknown_completion_selection_ids=unknown,
        useful_quantities=useful,
        representatives=representatives,
        useful_units=count,
        allocated_useful_units=allocated,
        useful_unit_fraction=fraction(allocated, count),
        known_useful_subtotal=money(known),
        full_useful_total=money(full),
        unallocated_group_reference_ids=unallocated,
        reason="one_unit_per_incremental_item"
        if full is not None
        else "unknown_identity_or_unpriced_useful_units_or_group_allocation",
    )
    return result, known, full


def comparisons(data, known, full, useful_known, useful_full):
    result = {}
    for name in BASES:
        basis = data[name]
        components = {
            "base_price": basis,
            **{k: data["delivery_cost_inputs"][name].get(k, {}) for k in COSTS},
        }
        values, reasons = {}, {}
        for key, component in components.items():
            reason = "eligible"
            if component.get("amount") is None or component.get("status") != "known":
                reason = "unknown_component"
            elif component.get("currency") != "USD":
                reason = "unsupported_or_missing_currency"
            elif key == "base_price" and fresh(basis.get("date"), data["evaluation_date"]) in {
                "future",
                "invalid_or_missing_date",
            }:
                reason = "future_invalid_or_missing_price_date"
            try:
                value = amount(component.get("amount"))
            except ValueError as exc:
                if reason == "eligible":
                    reason = str(exc)
            else:
                if reason == "eligible":
                    values[key] = value
            reasons[key] = reason
        missing = [k for k in components if k not in values]
        cost = bounded_sum(list(values.values()), "cost_total_above_cap")
        delivered = cost if not missing else None
        base = values.get("base_price")

        def diff(a, b):
            return money(a - b) if a is not None and b is not None else None

        result[name] = dict(
            price_kind=basis["price_kind"],
            price_date=basis.get("date"),
            base_price=money(base),
            known_cost_subtotal=money(cost),
            full_delivered_cost=money(delivered),
            unknown_or_ineligible_components=missing,
            cost_component_eligibility=reasons,
            known_selected_reference_minus_base_price=diff(known, base),
            full_selected_reference_minus_base_price=diff(full, base),
            full_selected_reference_minus_delivered_cost=diff(full, delivered),
            known_reference_minus_known_costs_partial=diff(known, cost),
            known_goal_useful_reference_minus_base_price=diff(useful_known, base),
            full_goal_useful_reference_minus_base_price=diff(useful_full, base),
            full_goal_useful_reference_minus_delivered_cost=diff(useful_full, delivered),
            known_goal_useful_reference_minus_known_costs_partial=diff(useful_known, cost),
            full_reference_difference_percent=money((full - base) / full * 100)
            if full is not None and full > 0 and base is not None
            else None,
            comparison_coverage="full_selected"
            if full is not None
            else "partial_selected"
            if known is not None
            else "unavailable",
            meaning="dated_reference_difference_only_not_profit_or_advice",
        )
    return result


def evaluate(data):
    with localcontext() as ctx:
        ctx.prec = 40
        ctx.rounding = ROUND_HALF_EVEN
        return _evaluate(data)


def _evaluate(data):
    lines, references = data["selected_cards"], data["value_references"]
    selected = {s["selection_id"]: s for s in lines}
    refs = {r["reference_id"]: r for r in references}
    if len(selected) != len(lines) or len(refs) != len(references):
        raise ValueError("duplicate_selection_or_reference_id")
    for line in lines:
        quantity(line["quantity"])
    units = sum(s["quantity"] for s in lines)
    if units > 100000:
        raise ValueError("selected_quantity_above_cap")
    unknown = data["unknown_contents"]["quantity"]
    if unknown is not None and (type(unknown) is not int or unknown < 0 or unknown + units > 100000):
        raise ValueError("invalid_unknown_quantity")
    active = {}
    for line in lines:
        rid = line["chosen_value_reference"]
        if rid is not None:
            if rid not in refs:
                raise ValueError("missing_reference")
            active.setdefault(rid, []).append(line["selection_id"])
    terms, priced, reasons = [], set(), {}
    for rid, ids in active.items():
        ref = refs[rid]
        reason = eligibility(ref, data["evaluation_date"])
        scope = ref["value_scope"]
        if scope == "selection_group_total":
            captured = ref["applies_to_quantities"]
            for q in captured.values():
                quantity(q)
            if set(captured) != set(ids) or any(captured[k] != selected[k]["quantity"] for k in ids):
                reason = "group_scope_or_quantities_require_review"
            # Reject overlap among active captured groups, including partly detached groups.
            if any(
                set(captured).intersection(refs[other].get("applies_to_quantities", {}))
                for other in active
                if other != rid and refs[other]["value_scope"] == scope
            ):
                reason = "overlapping_active_groups"
            value = amount(ref["amount"]) if reason == "eligible" else None
        elif scope == "per_card":
            value = (
                sum((amount(ref["amount"]) * selected[k]["quantity"] for k in ids), Decimal(0))
                if reason == "eligible"
                else None
            )
        else:
            raise ValueError("invalid_value_scope")
        if value is not None and value > CAP:
            raise ValueError("line_or_reference_above_cap")
        reasons[rid] = reason
        if value is not None:
            terms.append(
                dict(
                    reference_id=rid,
                    selection_ids=sorted(ids),
                    exact=value,
                    value_scope=scope,
                    provenance=ref["provenance"],
                    as_of=ref["as_of"],
                    match_status=ref["match_status"],
                )
            )
            priced.update(ids)
    known = bounded_sum([t["exact"] for t in terms], "subtotal_above_cap")
    full = known if lines and len(priced) == len(lines) else None
    priced_units = sum(selected[k]["quantity"] for k in priced)
    coverage = dict(
        selected_units=units,
        priced_units=priced_units,
        unpriced_units=units - priced_units,
        selected_lines=len(lines),
        priced_lines=len(priced),
        unknown_content_units=unknown,
        lot_unit_denominator=units + unknown if unknown is not None else None,
        selected_unit_fraction=fraction(priced_units, units),
        selected_line_fraction=fraction(len(priced), len(lines)),
        lot_unit_fraction=fraction(priced_units, units + unknown) if unknown is not None else None,
    )
    goal, useful_known, useful_full = useful_values(data, selected, refs, terms)
    rounded = sum((t["exact"].quantize(CENT, rounding=ROUND_HALF_EVEN) for t in terms), Decimal(0))
    # Each per-card line display rounds independently; group totals display once.
    displays = sum(
        (
            amount(refs[t["reference_id"]]["amount"])
            .__mul__(selected[k]["quantity"])
            .quantize(CENT, rounding=ROUND_HALF_EVEN)
            for t in terms
            for k in t["selection_ids"]
            if t["value_scope"] == "per_card"
        ),
        Decimal(0),
    )
    displays += sum(
        (
            t["exact"].quantize(CENT, rounding=ROUND_HALF_EVEN)
            for t in terms
            if t["value_scope"] == "selection_group_total"
        ),
        Decimal(0),
    )
    return dict(
        selected_status="full" if full is not None else "partial" if known is not None else "unavailable",
        known_selected_subtotal=money(known),
        full_selected_total=money(full),
        full_lot_total=money(full) if unknown == 0 else None,
        coverage=coverage,
        reference_eligibility=reasons,
        unpriced_selection_ids=sorted(set(selected) - priced),
        line_displays={
            sid: money(amount(refs[line["chosen_value_reference"]]["amount"]) * line["quantity"])
            for sid, line in selected.items()
            if sid in priced and refs[line["chosen_value_reference"]]["value_scope"] == "per_card"
        },
        reference_terms=[
            dict(
                **{k: v for k, v in t.items() if k != "exact"},
                exact_amount=format(t["exact"], "f"),
                display_amount=money(t["exact"]),
            )
            for t in terms
        ],
        display_rounding_reconciliation=money(known.quantize(CENT, rounding=ROUND_HALF_EVEN) - rounded)
        if known is not None
        else None,
        line_display_rounding_reconciliation=money(known.quantize(CENT, rounding=ROUND_HALF_EVEN) - displays)
        if known is not None
        else None,
        goal=goal,
        comparisons=comparisons(data, known, full, useful_known, useful_full),
    )
