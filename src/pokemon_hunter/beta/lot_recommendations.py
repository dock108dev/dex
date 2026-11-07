"""Explainable ordering of the received offers, never an authority to buy."""

import re
import unicodedata
from decimal import Decimal


def rank(rows, choices=None):
    def words(text):
        text = "".join(
            c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c)
        )
        return set(re.findall(r"\w+", text))

    query = getattr(choices, "query", "") or ""
    terms = words(query) - {"pokemon", "vintage", "card", "cards", "lot", "lots"}
    budget = getattr(choices, "budget", None)
    baseline = Decimal(str(budget)) if budget not in (None, "") else None
    buckets = {"auction": [], "buy_it_now": [], "combined": []}
    for row in rows:
        value = row.get("lot_value") or {}
        names = ", ".join(dict.fromkeys(c.get("name", "") for c in value.get("cards", [])))
        named = words(names)
        title = words(row.get("title", ""))
        random_contents = bool(title & {"mystery", "random", "custom", "proxy", "replica", "repack"})
        match = 0 if terms and terms <= named else 1 if not terms or terms <= title else 2
        row["buying_order"] = {}
        for lane, order in row["value_order"]["lanes"].items():
            costs = (value.get("benchmark_costs") or {}).get(lane, {})
            delivered = costs.get("delivered_before_tax")
            if delivered is None:
                delivered = row.get("buy_now_delivered_total" if lane == "buy_it_now" else "delivered_total")
            cost = Decimal(str(delivered)) if delivered is not None else None
            complete = order["group"] == "complete"
            score = Decimal(str(order["score"])) if complete and order["score"] is not None else None
            tier = 0 if score is not None and score > 0 else 2 if score is not None else 1
            over = baseline is not None and cost is not None and cost > baseline
            reason = (
                "Complete card reference exceeds price + shipping; tax still to check."
                if tier == 0
                else "Price + shipping meets or exceeds the complete card reference."
                if tier == 2
                else "Value not verified."
            )
            if random_contents:
                reason = "Random or custom contents; lower confidence in collection fit."
            if over:
                reason += " Above your baseline."
            recommendation = dict(
                rank=None,
                reason=reason,
                contents=names[:160] or "Contents not confirmed",
                lane=lane,
            )
            row["buying_order"][lane] = recommendation
            key = (
                random_contents,
                match,
                tier,
                bool(over) if tier != 0 else False,
                -score if tier == 0 else Decimal(0),
                -int(value.get("physically_selected_quantity") or value.get("identified_quantity") or 0),
                cost is None,
                cost
                if cost is not None
                else Decimal(
                    str(
                        costs.get("base")
                        or row.get("buy_now_price" if lane == "buy_it_now" else "listing_price")
                        or "Infinity"
                    )
                ),
                lane == "auction",
                row["item_id"],
            )
            buckets[lane].append((key, recommendation))
        preferred = "buy_it_now" if "buy_it_now" in row["buying_order"] else "auction"
        if preferred in row["buying_order"]:
            selected = row["buying_order"][preferred]
            row["buying_order"]["combined"] = dict(selected)
            key = next(k for k, entry in buckets[preferred] if entry is selected)
            buckets["combined"].append((key, row["buying_order"]["combined"]))
    for bucket in buckets.values():
        for position, (_, recommendation) in enumerate(sorted(bucket, key=lambda item: item[0]), 1):
            recommendation["rank"] = position
