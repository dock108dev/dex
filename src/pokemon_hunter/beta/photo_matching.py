"""Normalize visible card evidence without inventing catalog variants."""

import re


def normalized(value, field):
    text = re.sub(r"\s+", " ", str(value or "").strip().casefold())
    if field == "collector_number":
        text = text.split("/", 1)[0].strip()
        return str(int(text)) if text.isascii() and text.isdigit() else text
    aliases = {
        "language": {"english": "en", "japanese": "ja", "jpn": "ja"},
        "edition": {
            "1st edition": "first_edition",
            "first edition": "first_edition",
            "1st-edition": "first_edition",
        },
        "finish": {
            "holofoil": "holo",
            "holographic": "holo",
            "non-holo": "nonholo",
            "non holo": "nonholo",
            "normal": "nonholo",
        },
        "set_name": {"base": "base set", "base set unlimited": "base set"},
    }
    return aliases.get(field, {}).get(text, text)


def matches(clue, catalog):
    if not clue or clue.get("status") != "readable" or not clue.get("name") or not clue.get("number"):
        return []
    fields = {
        "name": "name",
        "number": "collector_number",
        "set_name": "set_name",
        "language": "language",
        "edition": "edition",
        "finish": "finish",
        "variant": "variant",
    }
    result = []
    for card in catalog:
        if all(
            not clue.get(k)
            or (field in {"edition", "finish", "variant"} and not card[field])
            or normalized(card[field], field) == normalized(clue[k], field)
            for k, field in fields.items()
        ):
            result.append(card)
    return result[:100]
