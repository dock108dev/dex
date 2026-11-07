"""Explainable ordering of the received offers, never an authority to buy."""

import re
import unicodedata
from decimal import Decimal

from . import market_identity


def pre_2000_contents(value, entries, dates):
    """Require complete contents and retained release evidence, never a title keyword.

    Dates describe original set releases. Special/reprint variants and rolling
    promo series cannot inherit that date without their own release evidence.
    """
    cards = value.get("cards") or []
    if (
        not cards
        or value.get("contents_state") != "resolved"
        or value.get("unidentified_quantity") != 0
        or value.get("quantity_issues")
        or sum(c["quantity"] for c in cards) != value.get("stated_quantity")
    ):
        return False
    for card in cards:
        printing = entries[card["printing_id"]]
        released = dates.get(printing["set_id"])
        if not released or released["end"] >= "2000-01-01":
            return False
        if not any(
            market_identity.compatible(printing, edition, finish, shadowless=shadowless)
            for edition in ("unlimited", "first_edition")
            for finish in ("normal", "holo")
            for shadowless in (False, True)
        ):
            return False
    return True


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
        unique_names = list(dict.fromkeys(c.get("name", "") for c in value.get("cards", []) if c.get("name")))
        names = ", ".join(unique_names)
        contents = ", ".join(unique_names[:3])
        if len(unique_names) > 3:
            contents += f" +{len(unique_names) - 3} more"
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
            # A publisher guide is useful for screening, but never becomes a
            # normalized value, resale profit, condition claim or bid ceiling.
            guides = value.get("native_guides") or []
            guide = guides[0] if len(guides) == 1 else None
            guide_value = Decimal(str(guide["subtotal"])) if guide and guide.get("subtotal") else None
            guide_ratio = (
                cost / guide_value
                if guide_value and guide_value > 0 and guide.get("complete") and cost is not None
                else None
            )
            if score is None and guide_ratio is not None:
                tier = Decimal("0.5") if guide_ratio < 1 else Decimal("2.5")
            over = baseline is not None and cost is not None and cost > baseline
            estimate = value.get("total") or value.get("subtotal")
            estimate_complete = value.get("total") is not None
            if guide_value is not None and (
                estimate is None or not estimate_complete and guide.get("complete")
            ):
                estimate = str(guide_value)
                estimate_complete = bool(guide.get("complete"))
            estimate_ratio = (
                cost / Decimal(str(estimate))
                if estimate is not None
                and Decimal(str(estimate)) > 0
                and estimate_complete
                and cost is not None
                else None
            )
            reason = (
                "Complete card reference exceeds price + shipping; tax still to check."
                if tier == 0
                else "Price + shipping meets or exceeds the complete card reference."
                if tier == 2
                else "Value not verified."
            )
            if score is None and guide_value is not None:
                coverage = (
                    "whole lot" if guide.get("complete") else f"{guide['priced_quantity']} identified cards"
                )
                reason = f"${guide_value:,.2f} market guide for {coverage}."
                if guide_ratio is not None:
                    reason += f" Price + shipping is {guide_ratio:.0%} of guide."
                reason += " Mixed-condition estimate."
            if random_contents:
                reason = "Random or custom contents; lower confidence in collection fit."
            if over:
                reason += " Above your baseline."
            recommendation = dict(
                rank=None,
                reason=reason,
                contents=contents or "Contents not confirmed",
                all_pre_2000=bool(value.get("all_pre_2000")),
                estimate_amount=str(estimate) if estimate is not None else None,
                estimate_complete=estimate_complete,
                price_to_estimate=str(estimate_ratio) if estimate_ratio is not None else None,
                lane=lane,
                guide_amount=str(guide_value) if guide_value is not None else None,
                guide_complete=bool(guide and guide.get("complete")),
                price_to_guide=str(guide_ratio) if guide_ratio is not None else None,
            )
            row["buying_order"][lane] = recommendation
            key = (
                random_contents,
                match,
                tier,
                bool(over) if tier not in (0, Decimal("0.5")) else False,
                -score if tier == 0 else Decimal(0),
                # Compare ratios only within one exact source/date cohort.
                guide["cohort"] if guide_ratio is not None else "",
                guide_ratio if guide_ratio is not None else Decimal(0),
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
