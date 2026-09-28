from decimal import Decimal, InvalidOperation

from .models import Listing, Settings


def money(value: dict | None, currency: str) -> Decimal | None:
    if not isinstance(value, dict) or value.get("currency") != currency:
        return None
    try:
        amount = Decimal(str(value["value"]))
        return amount if amount.is_finite() and amount >= 0 else None
    except (KeyError, InvalidOperation, ValueError):
        return None


def shipping(raw: dict, currency: str) -> Decimal | None:
    # Only delivery options with explicit costs qualify; absent != free.
    amounts = [
        money(o.get("shippingCost"), currency)
        for o in raw.get("shippingOptions", [])
        if o.get("shippingCostType") in (None, "FIXED", "CALCULATED")
    ]
    known = [a for a in amounts if a is not None]
    return min(known) if known else None


def apply_pricing(listing: Listing, settings: Settings):
    if listing.item_price is None:
        listing.rejection_reasons.append("Missing price/current bid or unsupported currency")
    if listing.shipping_price is None:
        listing.rejection_reasons.append("Delivered shipping cost is unknown or unsupported")
    count = listing.count.denominator
    if count is None or count < settings.minimum_cards:
        listing.rejection_reasons.append(
            f"Requires a reliable count of at least {settings.minimum_cards} cards"
        )
    if listing.count.confidence < 0.6:
        listing.rejection_reasons.append("Card count is ambiguous")
    if listing.item_price is None or listing.shipping_price is None or not count:
        return
    listing.landed_price = listing.item_price + listing.shipping_price
    listing.cost_per_card = listing.landed_price / count
    auction = listing.listing_type == "auction"
    threshold = settings.thresholds.auction_per_card if auction else settings.thresholds.fixed_price_per_card
    cap = settings.maximum_purchase.auction if auction else settings.maximum_purchase.fixed_price
    if auction:
        budget = Decimal(count) * threshold
        if cap is not None:
            budget = min(budget, cap)
        listing.max_bid = max(Decimal(0), budget - listing.shipping_price).quantize(
            Decimal(".01"), rounding="ROUND_DOWN"
        )
    if listing.cost_per_card > threshold:
        listing.rejection_reasons.append("Delivered price per card exceeds threshold")
    if cap is not None and listing.landed_price > cap:
        listing.rejection_reasons.append("Delivered price exceeds total-spend limit")
