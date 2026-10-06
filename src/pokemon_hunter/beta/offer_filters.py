"""Pure retained-offer comparison and conservative link decisions. Never acquire."""

import ipaddress
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import urlsplit

FIELDS = ("stock", "age", "max_price", "currency", "sort")


def validate(values=None):
    values = values or {}
    f = {k: values.get(k, "") for k in FIELDS}
    f.update(stock=f["stock"] or "all", age=f["age"] or "all", sort=f["sort"] or "checked")
    if f["stock"] not in {"all", "in-stock", "out-of-stock", "unknown"}:
        raise ValueError("Invalid stock filter")
    if f["age"] not in {"all", "fresh", "older", "unknown"} or f["sort"] not in {"checked", "price"}:
        raise ValueError("Invalid observation age or sort")
    if f["currency"] and not re.fullmatch(r"[A-Z]{3}", f["currency"]):
        raise ValueError("Currency requires three uppercase letters")
    if f["max_price"]:
        if not re.fullmatch(r"\d{1,9}(?:\.\d{1,2})?", f["max_price"]) or not f["currency"]:
            raise ValueError("Maximum item price requires a nonnegative amount and explicit currency")
    if f["sort"] == "price" and not f["currency"]:
        raise ValueError("Comparable item price sorting requires an explicit currency")
    return f


def instant(value):
    try:
        d = datetime.fromisoformat(value)
        return d.astimezone(timezone.utc) if d.tzinfo else None
    except (ValueError, TypeError):
        return None


def age(value, now):
    checked = instant(value)
    if checked is None:
        return "unknown"
    delta = now - checked
    if delta < timedelta(0):
        return "future"
    return "fresh" if delta <= timedelta(hours=24) else "older"


def observation_key(o):
    checked = instant(o.get("checked_at"))
    return (checked is None, -checked.timestamp() if checked else 0, o["id"])


def safe_url(value):
    if not isinstance(value, str) or any(c.isspace() or ord(c) < 32 for c in value) or "\\" in value:
        return False
    try:
        u = urlsplit(value)
        host = u.hostname
        if not host:
            return False
        try:
            ipaddress.ip_address(host)
            valid_host = True
        except ValueError:
            valid_host = len(host) <= 253 and all(
                re.fullmatch(r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?", label)
                for label in host.encode("idna").decode("ascii").rstrip(".").split(".")
            )
        return bool(
            u.scheme in {"http", "https"}
            and valid_host
            and u.username is None
            and u.password is None
            and u.port != 0
            and not re.search(r"%(?:0[0-9a-f]|1[0-9a-f]|7f)", value, re.I)
        )
    except (ValueError, UnicodeError):
        return False


def eligibility(offer, observation, product, sources, now):
    """Decision and concrete reasons for source, matching seller offer, purchase claim.

    The supported schema and adapters cannot attest backend availability.
    Purchase remains unavailable; caller-supplied timestamps cannot enable it.
    """
    obs = observation or {}
    refs = [
        sources.get(k, {})
        for k in set(offer.get("sources", []) + obs.get("sources", []) + product.get("sources", []))
    ]
    usable = any(
        s.get("status") == "usable"
        and s.get("authority") == "retailer"
        and offer["id"] in s.get("subjects", [])
        and "offer-observation" in s.get("supports", [])
        for s in refs
    )
    synthetic = any("synthetic" in str(s).lower() or "replay" in str(s).lower() for s in refs)
    common = []
    if not safe_url(offer.get("url")):
        common.append("Unsafe or missing HTTP/HTTPS source URL")
    matching = list(common)
    if offer.get("product_id") != product.get("id") or not usable:
        matching.append("Exact product/offer lacks usable matching retailer evidence")
    if not offer.get("seller") or offer.get("seller_kind") not in {"direct", "marketplace"}:
        matching.append("Actual seller and direct/marketplace identity unresolved")
    if synthetic:
        matching.append("Synthetic/replay evidence cannot establish a real offer")
    purchase = list(matching)
    if product.get("contents") not in {"complete", "mixed-known"}:
        purchase.append("Exact contents unresolved")
    if product.get("distinct_target_count") == 0:
        purchase.append("No documented product applicability to the selected targets")
    if obs.get("price_minor") is None:
        purchase.append("Item price unknown")
    observed = any(
        s.get("status") == "usable"
        and s.get("authority") == "retailer"
        and obs.get("id") in s.get("subjects", [])
        and "offer-observation" in s.get("supports", [])
        and s.get("market") == offer.get("market")
        for s in (sources.get(k, {}) for k in obs.get("sources", []))
    )
    if not observed:
        purchase.append("Selected observation lacks usable matching retailer evidence")
    if obs.get("stock") != "in-stock":
        purchase.append("Availability is not observed in stock")
    if age(obs.get("checked_at"), now) != "fresh":
        purchase.append("Original checked time is outside the inclusive 24-hour window or unknown/future")
    identity = any(
        s.get("status") == "usable"
        and s.get("authority") == "official-product"
        and product.get("id") in s.get("subjects", [])
        and "product-identity" in s.get("supports", [])
        for s in (sources.get(k, {}) for k in product.get("sources", []))
    )
    if not identity:
        purchase.append("Exact official product identity evidence unavailable")
    recommendation = list(purchase)
    # No supported schema or adapter supplies a verified backend attestation.
    purchase.append(
        "Verified backend availability time unavailable or stale; tool-read recency alone is insufficient"
    )
    return {
        "source": not common,
        "source_reasons": common or ["Validated URL for manual review"],
        "offer": not matching,
        "offer_reasons": matching or ["Matching product and seller evidence"],
        "recommendation_eligible": not recommendation,
        "recommendation_reasons": recommendation
        or [
            "Exact product, seller, price and dated in-stock evidence qualify; shipping/tax may remain unknown"
        ],
        "behavior_eligible": not [
            r for r in recommendation if r != "Synthetic/replay evidence cannot establish a real offer"
        ],
        "synthetic": synthetic,
        "purchase_ready": False,
        "purchase_reasons": purchase,
    }


def apply(context, filters=None, sources=None, now=None, frozen=False):
    f = validate(filters)
    now = now or datetime.now(timezone.utc)
    context["offer_filters"] = f
    sources = sources or {}
    for group in context.get("expansions", []):
        for product in group["products"]:
            visible = []
            for offer in product["offers"]:
                history = sorted(offer["observations"], key=observation_key)
                for obs in history:
                    obs["age"] = age(obs.get("checked_at"), now)
                    obs["fresh"] = obs["age"] == "fresh"
                    obs["time_quality"] = obs.get("note") or "Source-time quality unknown"
                representative = history[0] if history else {}
                offer.update(
                    observations=history,
                    representative=representative,
                    eligibility=eligibility(offer, representative, product, sources, now),
                )
                if frozen and context.get("reference_gaps"):
                    offer["eligibility"]["recommendation_eligible"] = False
                    offer["eligibility"]["purchase_ready"] = False
                    offer["eligibility"]["recommendation_reasons"].append(
                        "Saved identity references changed or were archived; compare current indexed data explicitly"
                    )
                stock = representative.get("stock") or "unknown"
                observation_age = representative.get("age", "unknown")
                price = representative.get("price_minor")
                comparable = price is not None and offer.get("currency") == f["currency"]
                offer["price_comparable"] = comparable
                if not frozen and f["stock"] != "all" and stock != f["stock"]:
                    continue
                if not frozen and f["age"] != "all" and observation_age != f["age"]:
                    continue
                if (
                    not frozen
                    and f["max_price"]
                    and (not comparable or price > Decimal(f["max_price"]) * 100)
                ):
                    continue
                visible.append(offer)
            if f["sort"] == "price":
                visible.sort(
                    key=lambda o: (
                        not o["price_comparable"],
                        o["representative"].get("price_minor") if o["price_comparable"] else 0,
                        o["id"],
                    )
                )
            else:
                visible.sort(
                    key=lambda o: (
                        (observation_key(o["representative"]) if o["representative"] else (True, 0, "")),
                        o["id"],
                    )
                )
            if not frozen:
                product["offer_total"] = len(product["offers"])
            product["offers"] = visible
    return context
