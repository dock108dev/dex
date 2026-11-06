"""Bounded, source-neutral comparable-sale experiment. No acquisition or persistence.

A policy is an engineering candidate until independently admitted with calibration.
Observed spread is descriptive; these estimates never supply a strict bid ceiling.
"""

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import timedelta, timezone
from decimal import Decimal, localcontext

from . import price_snapshot_contract as rules
from . import shopping_math

MAX_SALES = 2000
CONDITIONS = {None, "NM", "LP", "MP", "HP", "DMG"}


@dataclass(frozen=True)
class Policy:
    method: str = "median"
    window_days: int = 30
    half_life_days: int | None = None
    minimum_unique: int = 10

    def __post_init__(self):
        if (
            self.method not in {"median", "recency_weighted_median"}
            or type(self.window_days) is not int
            or self.window_days not in {30, 90}
            or type(self.minimum_unique) is not int
            or self.minimum_unique not in {5, 10}
            or (self.method == "median" and self.half_life_days is not None)
            or (
                self.method != "median"
                and (type(self.half_life_days) is not int or self.half_life_days not in {14, 30})
            )
        ):
            raise ValueError("Unsupported predeclared estimator policy")


def policies():
    return [
        Policy(method, window, half, minimum)
        for method in ("median", "recency_weighted_median")
        for window in (30, 90)
        for half in ((None,) if method == "median" else (14, 30))
        for minimum in (5, 10)
    ]


def median(values):
    values = sorted(values)
    n = len(values)
    return values[n // 2] if n % 2 else (values[n // 2 - 1] + values[n // 2]) / 2


def _reason(sale, identity, now, policy, condition):
    required = {
        "origin",
        "sale_id",
        "identity",
        "grade",
        "condition",
        "sold_at",
        "captured_at",
        "amount",
        "shipping",
        "currency",
        "quantity",
        "amount_basis",
        "price_semantics",
        "accepted_offer",
        "accepted_amount_known",
        "source_url",
    }
    if not isinstance(sale, dict) or set(sale) != required:
        return "invalid_sale"
    try:
        for key in ("origin", "sale_id"):
            rules.text(sale[key])
        if (
            not isinstance(sale["identity"], dict)
            or sale["identity"] != identity
            or not all(identity.values())
        ):
            return "wrong_or_unresolved_identity"
        if sale["grade"] != "raw":
            return "graded"
        if sale["condition"] not in CONDITIONS:
            return "invalid_condition"
        if condition is not None and sale["condition"] != condition:
            return "wrong_condition"
        if type(sale["quantity"]) is not int or sale["quantity"] != 1:
            return "unsupported_quantity"
        if sale["currency"] != "USD" or sale["amount_basis"] != "item_excluding_shipping_tax":
            return "incompatible_money_basis"
        if sale["price_semantics"] not in {"transaction_amount", "reported_closed_price_unverified_payment"}:
            return "not_sold_amount"
        if type(sale["accepted_offer"]) is not bool or type(sale["accepted_amount_known"]) is not bool:
            return "unknown_offer_semantics"
        if sale["accepted_offer"] and not sale["accepted_amount_known"]:
            return "unknown_accepted_amount"
        if not rules.references.source_url(sale["source_url"]):
            return "invalid_provenance"
        shopping_math.amount(sale["amount"])
        if sale["shipping"] is not None:
            shopping_math.amount(sale["shipping"])
        sold = rules.timestamp(sale["sold_at"]).astimezone(timezone.utc)
        captured = rules.timestamp(sale["captured_at"]).astimezone(timezone.utc)
        if sold > captured or captured > now or sold > now:
            return "future_sale_or_capture"
        if sold < now - timedelta(days=policy.window_days):
            return "outside_lookback"
    except (ValueError, TypeError, KeyError):
        return "invalid_sale"
    return None


def estimate(sales, identity, *, now, policy=None, condition=None):
    """Deduplicate by original marketplace identity, never by reseller/collector ID."""
    policy = policy or Policy()
    if not isinstance(policy, Policy) or now.tzinfo is None or condition not in CONDITIONS:
        raise ValueError("Explicit valid estimator context required")
    if not isinstance(identity, dict) or set(identity) != set(rules.IDENTITY):
        raise ValueError("Exact printing identity required")
    if (
        not isinstance(sales, list)
        or len(sales) > MAX_SALES
        or rules.serialized_bytes(sales) > rules.MAX_BYTES
    ):
        raise ValueError("Comparable evidence exceeds its finite bound")
    now = now.astimezone(timezone.utc)
    groups, excluded = defaultdict(list), Counter()
    for sale in sales:
        if not isinstance(sale, dict) or not all(
            isinstance(sale.get(k), str) and sale[k] for k in ("origin", "sale_id")
        ):
            excluded["missing_original_sale_identity"] += 1
        else:
            groups[(sale["origin"], sale["sale_id"])].append(sale)
    used = []
    for key, copies in sorted(groups.items()):
        # Capture timestamp and intermediary URL may differ for a cross-provider copy.
        fingerprints = {
            rules.digest({k: v for k, v in s.items() if k not in {"captured_at", "source_url"}})
            for s in copies
        }
        if len(fingerprints) != 1:
            excluded["conflicting_duplicate"] += len(copies)
            continue
        # Every copy must validate: a malformed duplicate cannot launder evidence.
        reasons = [_reason(s, identity, now, policy, condition) for s in copies]
        if any(reasons):
            excluded[next(r for r in reasons if r)] += len(copies)
            continue
        excluded["duplicate"] += len(copies) - 1
        sale = min(copies, key=lambda s: (rules.timestamp(s["captured_at"]), s["source_url"]))
        used.append(sale)
    values = [shopping_math.amount(s["amount"]) for s in used]
    with localcontext() as ctx:
        ctx.prec = 34
        weights = [
            Decimal(1)
            if policy.method == "median"
            else Decimal(2)
            ** (
                -Decimal(str((now - rules.timestamp(s["sold_at"])).total_seconds()))
                / Decimal(86400 * policy.half_life_days)
            )
            for s in used
        ]
        total = sum(weights, Decimal(0))
        effective = total * total / sum((w * w for w in weights), Decimal(0)) if weights else Decimal(0)
        value = None
        if len(used) >= policy.minimum_unique and effective >= 5:
            if policy.method == "median":
                value = median(values)
            else:
                ordered = sorted(zip(values, weights))
                cumulative = Decimal(0)
                for i, (amount, weight) in enumerate(ordered):
                    cumulative += weight
                    if cumulative >= total / 2:
                        value = (
                            (amount + ordered[i + 1][0]) / 2
                            if cumulative == total / 2 and i + 1 < len(ordered)
                            else amount
                        )
                        break
    dates = sorted(rules.timestamp(s["sold_at"]).astimezone(timezone.utc).isoformat() for s in used)
    ordered = sorted(values)
    spread = (
        None
        if not values
        else dict(
            minimum=str(ordered[0]),
            maximum=str(ordered[-1]),
            q25=str(ordered[(len(ordered) - 1) // 4]),
            q75=str(ordered[(3 * (len(ordered) - 1)) // 4]),
            meaning="observed_order_statistics_not_confidence_bounds",
        )
    )
    return dict(
        schema="dex-sold-estimate-v1",
        value=format(value.quantize(Decimal("0.000001")), "f") if value is not None else None,
        currency="USD",
        amount_basis="item_excluding_shipping_tax",
        basis="sold_estimate",
        condition=condition,
        condition_strata=dict(Counter(s["condition"] or "unknown" for s in used)),
        policy=asdict(policy),
        calculated_at=now.isoformat(),
        unique_sales=len(used),
        effective_sample_size=str(effective),
        used_sale_ids=[dict(origin=s["origin"], sale_id=s["sale_id"]) for s in used],
        excluded={k: v for k, v in sorted(excluded.items()) if v},
        sold_from=dates[0] if dates else None,
        sold_through=dates[-1] if dates else None,
        spread=spread,
        reason="eligible_candidate" if value is not None else "sparse_evidence",
        payment_verified=False,
        strict_ceiling_ready=False,
    )
