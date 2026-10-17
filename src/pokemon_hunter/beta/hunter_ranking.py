"""Local, temporary reference-gap scenarios over freshly admitted Hunter rows.

Identity and reference admission remain with hunter_catalog/Shopping. Monetary
admission, addition, differences and percentages remain with shopping_math.
Neither this module nor a rank acquires data, stores prices or recommends a bid.
"""

from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal

from . import shopping
from . import shopping_math as math

MAX_ROWS = 400
SCENARIOS = ("buy_it_now", "current_bid", "minimum_next_bid", "planned_manual_bid")
MEANING = "dated_reference_difference_only_not_resale_ev_profit_or_purchase_or_bid_advice"


def _amount(value):
    return format(math.amount(value), "f") if value is not None else None


def _component(value):
    return dict(amount=value, currency="USD", status="known" if value is not None else "unknown")


def _calculation(base, costs, reference, today, kind):
    basis = dict(_component(base), date=today, price_kind=kind)
    data = dict(
        evaluation_date=today,
        listing_observation=basis,
        planned_bid=dict(_component(None), date=today, price_kind="personal_planned_bid"),
        delivery_cost_inputs={
            name: {key: _component(costs[key]) for key in math.COSTS} for name in math.BASES
        },
    )
    value = math.amount(reference["amount"]) if reference else None
    return math.comparisons(data, value, value, None, None)["listing_observation"]


def _gap(cost, reference, today, kind):
    # Shopping owns the common reference denominator and half-even rounding.
    result = _calculation(cost, dict.fromkeys(math.COSTS), reference, today, kind)
    denominator = reference.get("amount") if reference else None
    return dict(
        amount=result["full_selected_reference_minus_base_price"],
        percent=result["full_reference_difference_percent"],
        percent_denominator="reference_amount",
        percent_status="missing_reference"
        if denominator is None
        else "nonpositive_reference"
        if math.amount(denominator) <= 0
        else "missing_cost"
        if cost is None
        else "available",
    )


def _reference(row, now):
    ref = row.get("reference")
    if (
        not ref
        or row.get("discovery_kind") != "single"
        or row.get("identity_status") != "matched"
        or row.get("reference_eligibility") not in {"eligible", "conditional"}
        or ref.get("match_status") not in {"exact", "conditional"}
        or ref.get("currency") != "USD"
    ):
        return None
    try:
        _amount(ref.get("amount"))
        if (
            ref.get("amount") is None
            or math.fresh(ref.get("as_of"), now.astimezone(shopping.TZ).date().isoformat()) != "eligible"
        ):
            return None
        if ref.get("expires_at"):
            expires = datetime.fromisoformat(ref["expires_at"].replace("Z", "+00:00"))
            if expires.tzinfo is None or expires.utcoffset() is None or expires <= now:
                return None
    except (TypeError, ValueError):
        return None
    return ref


def _scenario(row, kind, base, costs, reference, today):
    result = _calculation(base, costs, reference, today, kind)
    subtotal_value = (
        math.bounded_sum([math.amount(base), math.amount(costs["shipping"])], "cost_total_above_cap")
        if base is not None and costs["shipping"] is not None
        else None
    )
    subtotal = math.money(subtotal_value)
    delivered = result["full_delivered_cost"]
    known = result["known_cost_subtotal"] if base is not None else None
    included = [key for key in math.COSTS if costs[key] is not None]
    missing = [key for key in math.COSTS if costs[key] is None]
    basis = (
        "complete_delivered_cost"
        if delivered is not None
        else "listing_and_shipping_subtotal"
        if included == ["shipping"]
        else "listing_amount"
        if not included
        else "known_cost_subtotal"
    )
    compared_value = (
        math.bounded_sum(
            [math.amount(base), *[math.amount(costs[key]) for key in included]], "cost_total_above_cap"
        )
        if base is not None
        else None
    )
    compared_cost = format(compared_value, "f") if compared_value is not None else None
    applicability = row.get("reference_eligibility") if reference else "unpriced"
    gap = _gap(compared_cost, reference, today, kind)
    return dict(
        kind=kind,
        offer_meaning="currently_available_buy_it_now" if kind == "buy_it_now" else "auction_scenario",
        applicability=applicability,
        listing_amount=result["base_price"],
        shipping=math.money(math.amount(costs["shipping"])) if costs["shipping"] is not None else None,
        listing_and_shipping_subtotal=subtotal,
        tax=costs["tax"],
        other_costs=costs["other_costs"],
        complete_delivered_cost=delivered,
        delivered_cost_complete=delivered is not None,
        known_cost_subtotal=known,
        unknown_cost_components=missing,
        cost_basis=basis,
        included_cost_components=["listing_amount", *included],
        comparison_cost=math.money(compared_value),
        reference_basis="admitted_dated_per_card_reference",
        reference_amount=reference["amount"] if reference else None,
        reference_as_of=reference.get("as_of") if reference else None,
        reference_valuation_as_of=reference.get("valuation_as_of") if reference else None,
        reference_source_version=reference.get("source_version") if reference else None,
        gap=gap,
        gaps=dict(
            listing_amount=_gap(base, reference, today, kind),
            listing_and_shipping_subtotal=_gap(
                format(subtotal_value, "f") if subtotal_value is not None else None, reference, today, kind
            ),
            complete_delivered_cost=_gap(
                compared_cost if delivered is not None else None, reference, today, kind
            ),
        ),
        below_reference=Decimal(gap["amount"]) > 0 if gap["amount"] is not None else None,
        rank_group="/".join([kind, applicability, basis, "+".join(included)]),
        rank=None,
        final_purchase_price=None,
        meaning=MEANING,
    )


def project(rows, *, now=None, planned_bids=None, costs=None):
    """Annotate one <=400-row freshly admitted comparison batch, without I/O.

    Optional manual bids and delivery components are internally authorized USD
    decimal strings keyed by exact item ID. An absent component stays unknown;
    an explicit ``"0"`` is known zero. These inputs do not acquire final prices.
    Call hunter_catalog again on every local source/lifecycle read, then project;
    a previously projected row is never a source of reference authorization.
    """
    if not isinstance(rows, list) or len(rows) > MAX_ROWS:
        raise ValueError("Hunter ranking requires at most 400 comparison rows")
    now = now or datetime.now(UTC)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Hunter ranking observation time must be aware")
    now = now.astimezone(UTC)
    today = now.astimezone(shopping.TZ).date().isoformat()
    planned_bids = {} if planned_bids is None else planned_bids
    costs = {} if costs is None else costs
    if not isinstance(planned_bids, dict) or not isinstance(costs, dict):
        raise ValueError("Choose item-keyed manual bid and cost inputs")
    result = []
    for original in rows:
        row = deepcopy(original)
        key = row["item_id"]
        overrides = costs.get(key, {})
        if not isinstance(overrides, dict) or set(overrides) - set(math.COSTS):
            raise ValueError("Choose shipping, tax and other_costs only")
        components = {name: _amount(overrides.get(name, row.get(name))) for name in math.COSTS}
        reference = _reference(row, now)
        scenarios = []
        options = row.get("buying_options", [])
        if "FIXED_PRICE" in options and row.get("buy_now_available"):
            scenarios.append(
                _scenario(row, "buy_it_now", _amount(row.get("buy_now_price")), components, reference, today)
            )
        if "AUCTION" in options:
            for kind, value in (
                ("current_bid", row.get("current_bid")),
                ("minimum_next_bid", row.get("minimum_next_bid")),
                ("planned_manual_bid", planned_bids.get(key)),
            ):
                if kind == "current_bid" or value is not None:
                    scenarios.append(_scenario(row, kind, _amount(value), components, reference, today))
        primary = scenarios[0] if scenarios else None
        unranked_reason = (
            "no_applicable_reference"
            if reference is None
            else "no_supported_offer"
            if primary is None
            else "missing_listing_amount"
            if primary["listing_amount"] is None
            else "not_below_reference"
            if primary["below_reference"] is not True
            else None
        )
        row["opportunity"] = dict(
            primary_scenario=scenarios[0]["kind"] if scenarios else None,
            classification="unpriced"
            if reference is None
            else "auction_scenario"
            if primary and primary["offer_meaning"] == "auction_scenario"
            else "conditional_buy_it_now_comparison"
            if primary and primary["applicability"] == "conditional"
            else "applicable_buy_it_now_candidate"
            if primary
            else "unsupported_offer",
            scenarios=scenarios,
            rank=None,
            rank_group=None,
            meaning=MEANING,
            source_reason=row.get("reason"),
            identity_uncertainties=deepcopy(row.get("identity_uncertainties", [])),
            unranked_reason=unranked_reason,
        )
        row["planned_manual_bid"] = _amount(planned_bids.get(key)) if "AUCTION" in options else None
        row["final_purchase_price"] = None
        result.append(row)
    return order(result)


def order(rows):
    """Re-rank already projected chunks together without matching or source I/O.

    The retaining service owns its separate cumulative retention cap. Only
    equivalent scenario/applicability/cost-component groups share a numeric rank.
    All unpriced, unsupported and ambiguous rows remain in deterministic output.
    """
    grouped = {}
    for row in rows:
        opportunity = row.get("opportunity", {})
        opportunity.update(rank=None, rank_group=None)
        for scenario in opportunity.get("scenarios", []):
            scenario["rank"] = None
            if scenario["below_reference"] is True:
                grouped.setdefault(scenario["rank_group"], []).append((row, scenario))
    for members in grouped.values():
        members.sort(key=lambda pair: (-Decimal(pair[1]["gap"]["amount"]), pair[0]["item_id"]))
        for rank, (row, scenario) in enumerate(members, 1):
            scenario["rank"] = rank
            if row["opportunity"]["primary_scenario"] == scenario["kind"]:
                row["opportunity"].update(rank=rank, rank_group=scenario["rank_group"])

    def key(row):
        opportunity = row.get("opportunity", {})
        primary = next(
            (s for s in opportunity.get("scenarios", []) if s["kind"] == opportunity.get("primary_scenario")),
            None,
        )
        if primary is None or primary["applicability"] == "unpriced":
            return (9, "", 0, row["item_id"])
        band = (0 if primary["kind"] == "buy_it_now" else 2) + (primary["applicability"] == "conditional")
        return (band, primary["rank_group"], opportunity.get("rank") or 10**9, row["item_id"])

    return sorted(rows, key=key)
