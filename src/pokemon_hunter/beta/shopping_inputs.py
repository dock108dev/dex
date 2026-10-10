"""Shopping input shapes and scalar validation, without account or persistence access.

Both saved-research preparation and the four-scenario calculator use this policy.
Catalog eligibility and authenticated writes remain in their service boundaries.
"""

from pokemon_hunter.security import ebay_url

from . import hunt_values
from . import shopping_math as math


def fields(value, allowed, required=()):
    if not isinstance(value, dict) or set(value) - set(allowed) or set(required) - set(value):
        raise ValueError("Unsupported or missing shopping fields")


def text(value, limit=2000):
    if (
        not isinstance(value, str)
        or len(value) > limit
        or any(ord(c) < 32 and c not in "\n\t" for c in value)
    ):
        raise ValueError("Invalid shopping text")
    return value


def validate_request(raw):
    fields(
        raw,
        {
            "selected_cards",
            "value_references",
            "unknown_contents",
            "goal_id",
            "goal_version",
            "listing_observation",
            "planned_bid",
            "delivery_cost_inputs",
        },
        {
            "selected_cards",
            "value_references",
            "unknown_contents",
            "listing_observation",
            "planned_bid",
            "delivery_cost_inputs",
        },
    )
    if (
        not isinstance(raw["selected_cards"], list)
        or len(raw["selected_cards"]) > 200
        or not isinstance(raw["value_references"], list)
        or len(raw["value_references"]) > 1000
    ):
        raise ValueError("At most 200 selection lines and 1000 retained alternatives")
    fields(raw["unknown_contents"], {"quantity", "notes"}, {"quantity"})
    if "notes" in raw["unknown_contents"]:
        text(raw["unknown_contents"]["notes"])
    for line in raw["selected_cards"]:
        fields(
            line,
            {
                "selection_id",
                "printing_id",
                "quantity",
                "assumptions",
                "edition",
                "condition",
                "grade",
                "grader",
                "completion_confirmed",
                "chosen_value_reference",
            },
            {
                "selection_id",
                "printing_id",
                "quantity",
                "assumptions",
                "completion_confirmed",
                "chosen_value_reference",
            },
        )
        for key in ("selection_id", "printing_id", "assumptions", "edition", "condition", "grade", "grader"):
            text(line.get(key, ""))
        if not line["selection_id"] or type(line["completion_confirmed"]) is not bool:
            raise ValueError("Explicit physical identification required")
        math.quantity(line["quantity"])
    for r in raw["value_references"]:
        fields(
            r,
            {
                "reference_id",
                "kind",
                "amount",
                "currency",
                "as_of",
                "source_url",
                "assumptions",
                "value_scope",
                "applies_to_quantities",
                "observation_id",
                "printing_id",
            },
            {"reference_id", "kind"},
        )
        text(r["reference_id"], 200)
        if r["kind"] not in {"guide", "manual"}:
            raise ValueError("Select guide or explicit manual estimate")
        if r["kind"] == "guide":
            fields(
                r,
                {"reference_id", "kind", "observation_id", "printing_id"},
                {"reference_id", "kind", "observation_id", "printing_id"},
            )
        if r["kind"] == "manual":
            math.amount(r.get("amount"))
            text(r.get("currency"), 10)
            text(r.get("as_of"), 40)
            if not text(r.get("assumptions")):
                raise ValueError("Manual estimate needs explicit assumptions")
            if r.get("source_url") and not hunt_values._source(r["source_url"]):
                raise ValueError("Unsafe estimate source URL")
    for name in math.BASES:
        basis = raw[name]
        fields(
            basis,
            {"amount", "currency", "status", "date", "price_kind", "source_url", "notes", "observed_at"},
            {"price_kind"},
        )
        if basis["price_kind"] not in (
            {"current_bid", "current_asking_price"}
            if name == "listing_observation"
            else {"personal_planned_bid"}
        ):
            raise ValueError("Invalid price kind")
        if basis.get("source_url") and (len(basis["source_url"]) > 2000 or not ebay_url(basis["source_url"])):
            raise ValueError("Listing requires a safe HTTPS eBay URL")
        validate_component(basis)
    fields(raw["delivery_cost_inputs"], math.BASES, math.BASES)
    for costs in raw["delivery_cost_inputs"].values():
        fields(costs, math.COSTS, math.COSTS)
        for component in costs.values():
            fields(component, {"amount", "currency", "status", "date", "notes", "applies_to_both"})
            validate_component(component)


def validate_component(c):
    if c.get("amount") is not None:
        math.amount(c["amount"])
    if c.get("status") not in {"known", "unknown"}:
        raise ValueError("Explicit known/unknown amount status required")
    for key in ("currency", "date", "notes", "observed_at"):
        if c.get(key) is not None:
            text(c[key])
    if "applies_to_both" in c and type(c["applies_to_both"]) is not bool:
        raise ValueError("Explicit shared-cost decision required")
