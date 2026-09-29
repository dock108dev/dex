"""Shared browser-boundary rules for local and authenticated applications."""

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
