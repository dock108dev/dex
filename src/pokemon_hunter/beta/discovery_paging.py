"""Server-owned named Browse pages, checked again at the one-send boundary.

Official Browse v1.20.4 supports q + one category, limit/offset multiples and
at most 10,000 results. Dex deliberately stops after four 20-summary requests
TOTAL per named run, each requiring Search/More. Both alternates category lanes.
No returned next URL is fetched, persisted or accepted from the client.
"""

import re
from dataclasses import dataclass, replace

PAGE_SIZE = 20
MAX_PAGES = 4
CATEGORIES = {"mixed_lots": ("183455",), "singles": ("183454",), "both": ("183455", "183454")}


@dataclass(frozen=True)
class NamedPage:
    query: str
    category: str
    sort: str
    offset: int = 0
    set_name: str | None = None


def checked_params(page):
    if (
        type(page) is not NamedPage
        or not isinstance(page.query, str)
        or not page.query.strip()
        or len(page.query) > 200
        or page.category not in CATEGORIES["both"]
        or page.sort not in {"best_match", "ending_soonest"}
        or type(page.offset) is not int
        or page.offset < 0
        or page.offset >= MAX_PAGES * PAGE_SIZE
        or page.offset % PAGE_SIZE
        or (
            page.set_name is not None
            and (
                not isinstance(page.set_name, str)
                or not 1 <= len(page.set_name) <= 100
                or any(c in page.set_name for c in "{}|,:\\")
                or any(ord(c) < 32 for c in page.set_name)
            )
        )
    ):
        raise ValueError("Choose a checked finite named-search page")
    result = {
        "q": page.query,
        "category_ids": page.category,
        "filter": "buyingOptions:{FIXED_PRICE|AUCTION},deliveryCountry:US,itemLocationCountry:US",
        "limit": PAGE_SIZE,
        "offset": page.offset,
        "fieldgroups": "EXTENDED",
    }
    if page.set_name:
        result["aspect_filter"] = f"categoryId:{page.category},Set:{{{page.set_name}}}"
    if page.sort == "ending_soonest":
        result["sort"] = "endingSoonest"
    return result


def first_pages(query, product_type, sort, *, set_name=None):
    # Selected set is a seller aspect, not an extra keyword requirement. Keep
    # the name query like the owner's eBay search; never silently widen a facet.
    if set_name:
        query = " ".join(re.sub(re.escape(set_name), " ", query, flags=re.I).split())
        if not query:
            query = "Pokemon"
    pages = [NamedPage(query, category, sort, set_name=set_name) for category in CATEGORIES[product_type]]
    for page in pages:
        checked_params(page)
    return pages


def following(page, payload, rows):
    """Conservative exhaustion: a full page plus a valid larger total is needed."""
    total = payload.get("total")
    if type(total) is int and total > page.offset + PAGE_SIZE and len(rows) == PAGE_SIZE:
        return replace(page, offset=page.offset + PAGE_SIZE)
    return None
