from datetime import UTC, datetime

from .classifier import detect_sets, lot_rejection
from .models import Listing, Settings
from .parser import extract_count
from .pricing import apply_pricing, money, shipping
from .scoring import score
from .security import ebay_url


def evaluate(
    raw: dict, settings: Settings, catalog: dict, missing: tuple[float, float], now: datetime | None = None
) -> Listing:
    now = now or datetime.now(UTC)
    options = raw.get("buyingOptions", [])
    # Dual-option listings use auction economics and cannot be alerted twice.
    auction = "AUCTION" in options
    title = raw.get("title", "")
    description = raw.get("description") or raw.get("shortDescription") or ""
    text = title + " " + description
    listing = Listing(
        ebay_item_id=raw["itemId"],
        title=title,
        url=raw.get("itemWebUrl", ""),
        listing_type="auction" if auction else "bin",
        item_price=money(raw.get("currentBidPrice") if auction else raw.get("price"), settings.currency),
        shipping_price=shipping(raw, settings.currency),
        bid_count=raw.get("bidCount"),
        seller=raw.get("seller", {}).get("username"),
        condition=raw.get("condition"),
        queries=set(raw.get("_queries", [])),
    )
    listing.count = extract_count(text)
    listing.detected_sets, listing.excluded_sets, listing.purity = detect_sets(text, catalog)
    if "FIXED_PRICE" not in options and not auction:
        listing.rejection_reasons.append("Unsupported buying option")
    if ebay_url(listing.url) is None:
        listing.rejection_reasons.append("Missing or invalid eBay listing link")
    end = raw.get("itemEndDate")
    if end:
        try:
            listing.end_time = datetime.fromisoformat(end.replace("Z", "+00:00"))
            if listing.end_time.tzinfo is None:
                raise ValueError("Missing timezone")
            listing.end_time = listing.end_time.astimezone(UTC)
            if listing.end_time <= now:
                listing.rejection_reasons.append("Listing has ended")
        except ValueError:
            listing.end_time = None
            listing.rejection_reasons.append("Invalid listing end time")
    if auction and listing.end_time is None:
        listing.rejection_reasons.append("Auction end time is unknown")
    if raw.get("estimatedAvailabilities") and all(
        a.get("estimatedAvailabilityStatus") == "OUT_OF_STOCK" for a in raw["estimatedAvailabilities"]
    ):
        listing.rejection_reasons.append("Out of stock")
    if listing.purity == "unknown":
        listing.rejection_reasons.append("No eligible set or plausible vintage era detected")
    rejection = lot_rejection(text)
    if rejection:
        listing.rejection_reasons.append(rejection)
    apply_pricing(listing, settings)
    score(listing, settings, missing, text)
    return listing
