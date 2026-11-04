"""Display admission for temporary Browse images and aware auction timestamps."""

import hashlib
import re
from urllib.parse import urlsplit

from .hunter_query import utc_time


def result_handle(run_id, item_id):
    """Stable opaque identity within one temporary run; never grants access."""
    return hashlib.sha256((run_id + "\0" + item_id).encode()).hexdigest()[:24]


def end_timestamp(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        return utc_time(value).isoformat()
    except (ValueError, OverflowError):
        return None


def seller_image(image):
    """Only the official summary's eBay image CDN; no storage/proxy/download.

    CSP independently allows this single origin on local Discovery pages. Browser
    failures retain the labelled fixed-size fallback. URLs never enter exports.
    """
    value = image.get("imageUrl") if isinstance(image, dict) else None
    if not isinstance(value, str) or re.search(r"[\\\x00-\x20\x7f]", value):
        return None
    try:
        url = urlsplit(value)
        if (
            url.scheme != "https"
            or url.netloc != "i.ebayimg.com"
            or url.query
            or url.fragment
            or not re.fullmatch(r"/images/g/[A-Za-z0-9_~%-]+/s-l[0-9]+\.(?:jpg|jpeg|png|webp)", url.path)
        ):
            return None
    except ValueError:
        return None
    return value


def received_rows(raws):
    """Received lot summaries only; no identity, ownership or reference assessment.

    Review admission remains in discovery.review_candidate. This projection cannot
    authorize review, imply supported contents, or publish a reference/derivative.
    """
    from decimal import Decimal

    from pokemon_hunter.security import ebay_url

    from . import listing_prices

    rows, seen = [], set()
    for raw in raws:
        item_id = raw.get("itemId")
        if not isinstance(item_id, str) or not item_id or item_id in seen:
            continue
        seen.add(item_id)
        observed = listing_prices.prices(raw, currency="USD")
        price = observed["price"]["amount"]
        shipping = listing_prices.summary_shipping(raw)
        subtotal = (
            str(Decimal(price) + Decimal(shipping)) if price is not None and shipping is not None else None
        )
        auction = observed["price_kind"] == "current_bid"
        rows.append(
            dict(
                item_id=item_id,
                title=str(raw.get("title") or ""),
                item_url=ebay_url(raw.get("itemWebUrl")),
                seller_image=seller_image(raw.get("image")),
                listing_price=price,
                current_bid=price if auction else None,
                buy_now_price=observed["buy_now"]["amount"],
                shipping=shipping,
                delivered_total=subtotal,
                currency="USD",
                price_kind="current_bid" if auction else "fixed_price",
                ends_at=end_timestamp(raw.get("itemEndDate")),
                discovery_kind="unassessed",
                discovery_eligibility="unassessed",
                classification="unpriced",
                reason="Received listing; contents and collection fit need assessment.",
                reference=None,
                comparison={},
                proposed_identity=None,
                identity_candidates=[],
                save_allowed=False,
                save_reason="Temporary received listing; not saved research.",
            )
        )
    return rows
