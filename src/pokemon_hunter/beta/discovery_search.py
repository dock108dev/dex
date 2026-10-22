"""Local query intent and seller-product classification; no acquisition or values.

The eBay web search's manufactured years are not a canonical collection range.
English/vintage words express intent without pretending unverified taxonomy
aspects are supported filters. A selected set always reaches the wire query.
"""

import re

SET_ALIASES = (
    ("Base Set 2", r"\bbase\s*(?:set\s*)?2\b"),
    ("Base Set", r"\bbase(?!\s*(?:set\s*)?2\b)(?:\s+set)?\b"),
    ("Team Rocket", r"\bteam\s+rocket\b"),
    ("Jungle", r"\bjungle\b"),
    ("Fossil", r"\bfossil\b"),
    ("Gym Heroes", r"\bgym\s+heroes\b"),
    ("Gym Challenge", r"\bgym\s+challenge\b"),
    ("Neo Genesis", r"\bneo\s+genesis\b"),
    ("Neo Discovery", r"\bneo\s+discovery\b"),
    ("Neo Revelation", r"\bneo\s+revelation\b"),
    ("Neo Destiny", r"\bneo\s+destiny\b"),
)


def canonical_query(value):
    # The longer Base Set 2 alias must win independently of Base Set.
    for name, pattern in SET_ALIASES:
        value = re.sub(pattern, name, value, flags=re.I)
    return " ".join(value.split())


def submitted_query(value, *, set_name=None, english_vintage=False):
    value = canonical_query(value)
    if set_name:
        for _, pattern in SET_ALIASES:
            value = re.sub(pattern, " ", value, flags=re.I)
        # Known non-alias sets need the same authoritative replacement behavior.
        value = re.sub(re.escape(set_name), " ", value, flags=re.I)
    suffix = [set_name] if set_name else []
    if english_vintage:
        if not re.search(r"\benglish\b", value, re.I):
            suffix.append("English")
        if not set_name and not re.search(r"\b(?:vintage|wotc)\b", value, re.I):
            suffix.append("vintage")
    end = " ".join(suffix)
    # Keep authoritative suffixes even for a maximum-length typed phrase.
    return " ".join((value[: max(0, 200 - len(end) - 1)].strip(), end)).strip()


def product_kind(text):
    """Separate supported loose lots from unsupported sealed/random products."""
    if re.search(
        r"\b(?:mystery|repack(?:ed)?|random(?:ized)?|curated|sealed|booster|elite\s+trainer|"
        r"theme\s+deck|starter\s+deck|proxy|replica|custom)\b",
        text,
        re.I,
    ):
        return "unsupported"
    if re.search(r"\b(?:choose|pick\s+(?:your|from)|complete\s+set|master\s+set)\b", text, re.I):
        return "unsupported"
    if re.search(r"\b(?:lot|lots|binder|collection|bulk|bundle|mixed)\b", text, re.I):
        return "mixed_lot"
    if re.search(r"\b(?:[2-9]|[1-9]\d+)\s+cards\b|(?:\bx\s*[2-9]\d*\b|\b[2-9]\d*\s*[x×]\b)", text, re.I):
        return "mixed_lot"
    return "single"
