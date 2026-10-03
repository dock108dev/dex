"""Shared browser-boundary rules for local and authenticated applications."""

import re
from urllib.parse import urlsplit

BROWSER_HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "same-origin",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-Robots-Tag": "noindex, nofollow, noarchive",
    "Permissions-Policy": "camera=(self), microphone=(), geolocation=()",
    "Content-Security-Policy": (
        "default-src 'self'; style-src 'self' 'unsafe-inline'; "
        "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
    ),
}


def loopback_authority(value):
    """Only the original app's two supported local hosts and valid optional ports."""
    if not isinstance(value, str):
        return False
    match = re.fullmatch(r"(?:127\.0\.0\.1|localhost)(?::([0-9]{1,5}))?", value)
    return bool(match and (match[1] is None or 1 <= int(match[1]) <= 65535))


def ebay_url(value):
    """Accept unambiguous HTTPS eBay links, not browser/parser disagreements."""
    if (
        not isinstance(value, str)
        or not value
        or any(ord(c) <= 32 or ord(c) == 127 or c == "\\" for c in value)
    ):
        return None
    try:
        parsed = urlsplit(value)
        host = parsed.hostname or ""
        if (
            parsed.scheme != "https"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 443)
            or not (host == "ebay.com" or host.endswith(".ebay.com"))
        ):
            return None
    except ValueError:
        return None
    return value
