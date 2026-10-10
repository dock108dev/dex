"""Shared retained-reference admission; no provider, catalog or persistence access.

Legacy input coercion is retained here. Shopping decimal input precision, exact
identity, grade matching and source rights are enforced by their domain services.
"""

import ipaddress
from datetime import date
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

MAX_VALUE = Decimal("1000000000000")
MAX_AGE_DAYS = 30


def amount(value):
    try:
        result = Decimal(str(value))
        return result if result.is_finite() and 0 <= result <= MAX_VALUE else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def source_url(value):
    if (
        not isinstance(value, str)
        or len(value) > 2000
        or any(ord(c) <= 32 or ord(c) == 127 or c == "\\" for c in value)
    ):
        return None
    try:
        parsed = urlsplit(value)
        host = parsed.hostname or ""
        # Split once and scan each character once; no backtracking on untrusted hosts.
        labels = host.split(".")
        if (
            parsed.scheme != "https"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port not in (None, 443)
            or len(labels) < 2
            or not all(
                label and all("a" <= c <= "z" or "0" <= c <= "9" or c == "-" for c in label)
                for label in labels
            )
            or host.endswith(".localhost")
        ):
            return None
        try:
            if not ipaddress.ip_address(host).is_global:
                return None
        except ValueError:
            pass
    except ValueError:
        return None
    return value


def fresh(as_of, evaluation_date):
    try:
        age = (date.fromisoformat(evaluation_date) - date.fromisoformat(as_of)).days
        return "eligible" if 0 <= age <= MAX_AGE_DAYS else "future" if age < 0 else "stale"
    except (ValueError, TypeError):
        return "invalid_or_missing_date"


def valid_record(record, today, *, guide):
    if not isinstance(record, dict) or record.get("currency", "USD" if not guide else None) != "USD":
        return None
    if guide and record.get("variant_verified") is not True:
        return None
    source = source_url(record.get("source_url") or (None if guide else record.get("source")))
    observed = record.get("as_of")
    if fresh(observed, today.isoformat()) != "eligible":
        return None
    value = amount(record.get("value"))
    if source is None or value is None:
        return None
    return {
        "guidevalue": str(value.quantize(Decimal(".01"))),
        "source_url": source,
        "as_of": date.fromisoformat(observed).isoformat(),
    }
