"""Official listing money admission through Shopping's decimal and rounding policy.

Supplied summaries/details only: no acquisition, reference valuation or storage.
Foreign amounts can be displayed, but never converted into USD comparisons.
"""

import re
from decimal import Decimal

from . import shopping_math as math


def money(value, currency="USD"):
    if not isinstance(value, dict) or value.get("currency") != currency:
        return None
    try:
        return math.money(math.amount(value.get("value")))
    except ValueError:
        return None


def component(value, *, currency=None):
    if not isinstance(value, dict) or not re.fullmatch(r"[A-Z]{3}", str(value.get("currency", ""))):
        return dict(amount=None, currency=None)
    return dict(amount=money(value, currency or value["currency"]), currency=value["currency"])


def prices(raw, *, currency=None):
    """An absent auction bid never falls back to the optional buy-now amount."""
    options = raw.get("buyingOptions", [])
    if not isinstance(options, list) or not all(isinstance(option, str) for option in options):
        options = []
    auction = "AUCTION" in options
    buy_now = component(raw.get("price") if "FIXED_PRICE" in options else None, currency=currency)
    bid = component(raw.get("currentBidPrice") if auction else None, currency=currency)
    return dict(
        buying_options=[option for option in ("AUCTION", "FIXED_PRICE") if option in options],
        current_bid=bid,
        buy_now=buy_now,
        price=bid if auction else buy_now,
        price_kind="current_bid" if auction else "current_asking_price",
    )


def summary_shipping(raw):
    """Lowest explicitly priced supported USD option; absence never means free."""
    options = raw.get("shippingOptions")
    if not isinstance(options, list):
        return None
    amounts = [
        money(option.get("shippingCost"))
        for option in options
        if isinstance(option, dict) and option.get("shippingCostType") in (None, "FIXED", "CALCULATED")
    ]
    return min((amount for amount in amounts if amount is not None), key=Decimal, default=None)


def detail_shipping(raw):
    """Review inputs need one agreed amount/currency; conflicting options stay unknown."""
    options = raw.get("shippingOptions")
    if not isinstance(options, list):
        return dict(amount=None, currency=None)
    amounts = {
        (value["amount"], value["currency"])
        for option in options
        if isinstance(option, dict)
        for value in [component(option.get("shippingCost"))]
    }
    return (
        dict(zip(("amount", "currency"), next(iter(amounts))))
        if len(amounts) == 1
        else dict(amount=None, currency=None)
    )
