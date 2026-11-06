"""LV-03 explicit automatic action; never a multiplication of click allowances."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from . import discovery_paging, hunter_query, listing_details

CONTRACT = "dex-lot-hunt-v2"
LIMITS = dict(oauth=1, browse=2, detail=2, resolution=0, total=5)
SUMMARY_LIMIT = 40
CANDIDATE_LIMIT = 2
RESPONSE_BYTES = 2 * 1024 * 1024
OAUTH_BYTES = 32 * 1024
AGGREGATE_BYTES = 4 * RESPONSE_BYTES + OAUTH_BYTES
REQUEST_SECONDS = 30
JOB_SECONDS = 120
LEASE_SECONDS = 1800
CONCURRENCY = 1
# BIN first, with one independent detail slot; unused slots are not transferred.
LANES = ("buy_it_now", "auction")


@dataclass(frozen=True)
class Page:
    named: discovery_paging.NamedPage
    lane: str
    start: str


def checked_params(page):
    if type(page) is not Page or page.lane not in LANES or page.named.offset != 0:
        raise ValueError("Choose a captured lot Hunt page")
    params = discovery_paging.checked_params(page.named)
    if page.named.category != "183455":
        raise ValueError("Automatic lot Hunts require the mixed-lot category")
    start = hunter_query.utc_time(page.start)
    option = "FIXED_PRICE" if page.lane == "buy_it_now" else "AUCTION"
    params["filter"] = f"buyingOptions:{{{option}}},deliveryCountry:US,itemLocationCountry:US"
    if page.lane == "auction":
        end = start + timedelta(hours=72)
        params["filter"] += f",itemEndDate:[{start.isoformat()}..{end.isoformat()}]"
        params["sort"] = "endingSoonest"
    else:
        params.pop("sort", None)
    return params


def identity(raw):
    parsed = listing_details.parse_identifier(raw.get("itemId"))
    # Summary acquisition must provide stable exact Browse identity. Resolution
    # is explicitly zero; a numeric/parent identity cannot spend a second call.
    if parsed["rest"] is None:
        raise ValueError("Exact item/variation identity is unavailable")
    return parsed["rest"]


def lanes(raw, *, now=None):
    now = now or datetime.now(UTC)
    options = raw.get("buyingOptions", [])
    if not isinstance(options, list) or not all(isinstance(v, str) for v in options):
        return ()
    availability = raw.get("estimatedAvailabilities", [])
    if not isinstance(availability, list) or any(
        not isinstance(v, dict)
        or v.get("estimatedAvailabilityStatus") is not None
        and not isinstance(v["estimatedAvailabilityStatus"], str)
        or v.get("estimatedAvailabilityStatus") in ("OUT_OF_STOCK", "UNAVAILABLE")
        for v in availability
    ):
        return ()
    end = raw.get("itemEndDate")
    try:
        end = hunter_query.utc_time(end) if end is not None else None
    except ValueError:
        return ()
    if end is not None and end <= now:
        return ()
    return tuple(
        lane
        for lane in LANES
        if (lane == "buy_it_now" and "FIXED_PRICE" in options)
        or (
            lane == "auction"
            and "AUCTION" in options
            and end is not None
            and now < end <= now + timedelta(hours=72)
        )
    )


class ByteBudget:
    """One streamed byte meter shared by OAuth, summaries and details."""

    def __init__(self):
        self.used = 0

    def take(self, size):
        self.used += size
        if self.used > AGGREGATE_BYTES:
            from .discovery_transport import ProviderFailure

            raise ProviderFailure("aggregate_bytes")
