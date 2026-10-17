"""Checked, listings-first HUNT-01 acquisition and local eligibility contract.

No credentials, account/catalog reads, HTTP, paging or persistence belong here.
The scope is EBAY_US CCG singles, Pokémon TCG, English, all years, including
Trainer/Energy cards. It is independent of locally indexed cards and ownership.

Verified against public eBay documentation on 2026-10-16; fetching these public
documents required no OAuth, Browse or Taxonomy operation. The public category
page establishes singles 183454 and the Game/Language labels. Its additional
Card Type refinement is deliberately absent from the Hunter request.
"""

import unicodedata
from datetime import UTC, datetime, timedelta

MARKETPLACE = "EBAY_US"
SINGLES_CATEGORY = "183454"
GAME = "Pokémon TCG"
PAGE_LIMIT = 200
SUMMARY_LIMIT = 2 * PAGE_LIMIT
RESPONSE_BYTE_LIMIT = 2 * 1024 * 1024
LANES = ("auction", "buy_it_now")
PUBLIC_SOURCES = {
    "browse_specification": (
        "https://developer.ebay.com/api-docs/master/buy/browse/openapi/3/buy_browse_v1_oas3.json"
    ),
    "field_filters": "https://developer.ebay.com/api-docs/buy/static/ref-buy-browse-filters.html",
    "us_singles_game_language": (
        "https://www.ebay.com/b/Pokemon-Pokemon-TCG-English-Individual-Trading-Card-Games/183454/bn_56895478"
    ),
    "us_mixed_lots_game_language": (
        "https://www.ebay.com/b/Pokemon-TCG-Collectible-Card-Game-Mixed-Card-Lots/183455/bn_16565008"
    ),
}


def utc_time(value):
    """Accept an aware datetime or ISO timestamp; never infer a missing zone."""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("Hunter requires an aware timestamp") from None
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Hunter requires an aware timestamp")
    return value.astimezone(UTC)


def _stamp(value):
    return utc_time(value).isoformat().replace("+00:00", "Z")


def _window(start, end):
    start, end = utc_time(start), utc_time(end)
    if end - start != timedelta(hours=24):
        raise ValueError("Hunter requires one captured 24-hour window")
    return start, end


def plan(start, *, page_size=PAGE_LIMIT):
    """Capture exactly one initial page per lane; no query depends on a card."""
    if type(page_size) is not int or not 1 <= page_size <= PAGE_LIMIT:
        raise ValueError("Hunter pages contain between 1 and 200 summaries")
    start = utc_time(start)
    start_stamp, end_stamp = _stamp(start), _stamp(start + timedelta(hours=24))
    return {
        "start": start_stamp,
        "end": end_stamp,
        "requests": tuple(
            dict(lane=lane, start=start_stamp, end=end_stamp, limit=page_size) for lane in LANES
        ),
    }


def checked_params(request):
    """Recheck a finite internal request at the transport boundary.

    Arbitrary category/filter/query/offset/URL keys cannot enter this separate
    contract. Ordinary Shopping's 20-summary transport remains unchanged.
    """
    from .hunter_traversal import LOT_CATEGORY, Request, checked_request

    if type(request) is Request:
        checked_request(request)
        return _wire_params(
            request.lane,
            request.limit,
            utc_time(request.start),
            utc_time(request.end),
            LOT_CATEGORY if request.scope == "lots" else SINGLES_CATEGORY,
            request.offset,
        )
    if not isinstance(request, dict) or set(request) != {"lane", "start", "end", "limit"}:
        raise ValueError("Choose the checked Hunter request shape")
    lane, page_size = request["lane"], request["limit"]
    if lane not in LANES or type(page_size) is not int or not 1 <= page_size <= PAGE_LIMIT:
        raise ValueError("Choose a supported finite Hunter lane and page size")
    start, end = _window(request["start"], request["end"])
    return _wire_params(lane, page_size, start, end, SINGLES_CATEGORY, 0)


def _wire_params(lane, page_size, start, end, category, offset):
    option = "AUCTION" if lane == "auction" else "FIXED_PRICE"
    filters = [f"buyingOptions:{{{option}}}", "deliveryCountry:US", "itemLocationCountry:US"]
    if lane == "auction":
        filters.append(f"itemEndDate:[{_stamp(start)}..{_stamp(end)}]")
    params = {
        "category_ids": category,
        "aspect_filter": f"categoryId:{category},Game:{{{GAME}}},Language:{{English}}",
        "filter": ",".join(filters),
        "limit": page_size,
        "offset": offset,
        "fieldgroups": "EXTENDED",
    }
    if lane == "auction":
        params["sort"] = "endingSoonest"
    return params


def _fold(value):
    return "".join(
        c for c in unicodedata.normalize("NFKD", value.casefold()) if not unicodedata.combining(c)
    ).strip()


def _scope_conflict(raw, scope="singles"):
    # Search scope is established on the wire. Missing optional summary metadata
    # does not require the seller to repeat Pokémon or English in their title.
    if raw.get("listingMarketplaceId") not in (None, MARKETPLACE):
        return True
    from .hunter_traversal import LOT_CATEGORY, SCOPES

    if scope not in SCOPES:
        raise ValueError("Choose the singles or loose-lot scope")
    category = LOT_CATEGORY if scope == "lots" else SINGLES_CATEGORY
    leaves = raw.get("leafCategoryIds")
    if isinstance(leaves, list) and leaves and category not in leaves:
        return True
    for aspect in raw.get("localizedAspects", []) if isinstance(raw.get("localizedAspects"), list) else []:
        if not isinstance(aspect, dict):
            continue
        name, value = aspect.get("name"), aspect.get("value")
        if not isinstance(name, str) or not isinstance(value, str) or not value.strip():
            continue
        if _fold(name) == "game" and _fold(value) != _fold(GAME):
            return True
        if _fold(name) == "language" and _fold(value) != "english":
            return True
    return False


def lane_eligibility(raw, lane, start, end, *, now=None, scope="singles"):
    """Return None when eligible, otherwise a stable local rejection reason.

    Window endpoints are inclusive. An offer must also remain available at
    ``now``; thus an auction exactly at the start is already ended when checked
    at that same instant. A mixed listing can fail the auction lane yet remain
    eligible in the BIN lane if its ending time is later than the window.
    """
    if lane not in LANES:
        raise ValueError("Choose a supported Hunter lane")
    start, end = _window(start, end)
    now = utc_time(now if now is not None else datetime.now(UTC))
    if not isinstance(raw, dict):
        return "malformed_summary"
    if _scope_conflict(raw, scope):
        return "scope_conflict"
    options = raw.get("buyingOptions")
    if not isinstance(options, list) or not all(isinstance(option, str) for option in options):
        return "unsupported_buying_options"
    if ("AUCTION" if lane == "auction" else "FIXED_PRICE") not in options:
        return "buying_option_unavailable"
    availability = raw.get("estimatedAvailabilities")
    if isinstance(availability, list) and any(
        isinstance(row, dict) and row.get("estimatedAvailabilityStatus") in {"OUT_OF_STOCK", "UNAVAILABLE"}
        for row in availability
    ):
        return "unavailable"
    raw_end = raw.get("itemEndDate")
    if raw_end is None:
        return "invalid_end_time" if lane == "auction" else None
    try:
        end_time = utc_time(raw_end)
    except ValueError:
        return "invalid_end_time"
    if end_time <= now:
        return "ended_offer"
    if lane == "auction" and not start <= end_time <= end:
        return "outside_auction_window"
    return None
