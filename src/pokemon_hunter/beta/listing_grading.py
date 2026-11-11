"""Seller-claimed grading status for a single card, not authentication."""

import re


def status(raw, text):
    """Return raw, graded or unknown; contradictory claims remain unknown."""
    negative_pattern = (
        r"\b(?:ungraded|(?:not|non|no)[ -]+(?:professionally[ -]+)?graded|graded\s*:\s*(?:no|false))\b"
    )
    negative = bool(re.search(negative_pattern, text, re.I))
    positive_text = re.sub(negative_pattern, "", text, flags=re.I)
    # A negated slab mention alone does not prove the card is ungraded.
    positive_text = re.sub(r"\b(?:no|not|without)[ -]+slabs?\b", "", positive_text, flags=re.I)
    positive = bool(
        re.search(
            r"\b(?:graded|slabs?|gem[ -]*mint|grade\s*\d|(?:PSA|BGS|CGC|SGC)\s*[-:]?\s*(?:10|[1-9](?:\.5)?)(?![\d.]))\b",
            positive_text,
            re.I,
        )
    )
    aspects = raw.get("localizedAspects") or []
    if isinstance(aspects, list):
        for aspect in aspects:
            if not isinstance(aspect, dict) or str(aspect.get("name", "")).strip().casefold() != "graded":
                continue
            value = str(aspect.get("value", "")).strip().casefold()
            positive |= value in {"yes", "true"}
            negative |= value in {"no", "false"}
    if positive == negative:
        return "unknown"
    return "graded" if positive else "raw"
