"""Display admission for temporary Browse images and aware auction timestamps."""

import re
from urllib.parse import urlsplit

from .hunter_query import utc_time


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
