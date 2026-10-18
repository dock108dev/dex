"""Conditional market references preserve unresolved collection variants."""

import json

EDITION = {
    "unlimited": "unlimited",
    "standard": "unlimited",
    "1st-edition": "first_edition",
    "first_edition": "first_edition",
}
FINISH = {
    "holo": "holo",
    "holofoil": "holo",
    "normal": "normal",
    "nonfoil": "normal",
    "reverse": "reverse-holo",
    "reverse-holo": "reverse-holo",
    "reverse-holofoil": "reverse-holo",
}
SUBTYPES = {
    "Holofoil": ("unspecified", "holo"),
    "Normal": ("unspecified", "normal"),
    "Reverse Holofoil": ("unspecified", "reverse-holo"),
    "Unlimited Holofoil": ("unlimited", "holo"),
    "Unlimited": ("unlimited", "normal"),
    "1st Edition Holofoil": ("first_edition", "holo"),
    "1st Edition": ("first_edition", "normal"),
}


def compatible(printing, edition, finish):
    """Unknown fit is conditional; a known conflicting or special variant is refused."""
    if printing.get("language") != "en":
        return False
    known = printing.get("edition")
    if known and (known not in EDITION or EDITION[known] != edition):
        return False
    known = printing.get("finish")
    if known and (known not in FINISH or FINISH[known] != finish):
        return False
    variant = printing.get("variant")
    if variant:
        if variant in FINISH:
            return FINISH[variant] == finish
        try:
            value = json.loads(variant)
        except (ValueError, TypeError):
            return False
        if not isinstance(value, dict) or set(value) - {"type", "stamp"}:
            return False
        if value.get("type") not in FINISH or FINISH[value["type"]] != finish:
            return False
        if "stamp" in value and (value["stamp"] != ["1st-edition"] or edition != "first_edition"):
            return False
    return True


def applicable(row, printing):
    provider = row["provider_identity"]
    subtype = provider["variant"]
    return (
        subtype in SUBTYPES
        and (provider["edition"], provider["finish"]) == SUBTYPES[subtype]
        and provider["language"] == printing.get("language")
        and compatible(printing, provider["edition"], provider["finish"])
    )
