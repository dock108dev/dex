import re

from .parser import clean


def detect_sets(text: str, catalog: dict):
    text = clean(text)
    detected, excluded = set(), set()
    remaining = text
    # Match longer aliases first so Base Set 2 is not also Base Set.
    aliases = sorted(
        (
            (alias, name, group)
            for group in ("eligible", "excluded")
            for name, names in catalog[group].items()
            for alias in names
        ),
        key=lambda x: len(x[0]),
        reverse=True,
    )
    for alias, name, group in aliases:
        pattern = r"(?<!\w)" + re.escape(alias) + r"(?!\w)"
        if re.search(pattern, remaining):
            (detected if group == "eligible" else excluded).add(name)
            remaining = re.sub(pattern, " ", remaining)
    if re.search(r"\b(?:200[4-9]|20[1-9]\d)\b", text):
        excluded.add("later_year")
    if re.search(r"\b(?:japanese|korean|chinese|german|french|italian|spanish)\b", text):
        excluded.add("non_english")
    vague = bool(re.search(r"\b(?:wotc|neo|vintage|ereader|e-reader|johto)\b", text))
    if excluded and (detected or vague):
        purity = "mixed"
    elif detected:
        purity = "pure"
    elif vague:
        purity = "probably_pure"
    else:
        purity = "unknown"
    return detected, excluded, purity


def lot_rejection(text: str) -> str | None:
    text = clean(text)
    if re.search(
        r"\b(?:repack|mystery|god pack|custom pack|handmade booster|guaranteed holo|proxy|proxies|replica|digital|complete set|master set|pick your|choose|sealed|booster|packs? of)\b",
        text,
    ):
        return "Curated product, sealed pack, selection, replica, or complete set"
    if re.search(r"\b(?:trainers?|energ(?:y|ies))\s+only\b|\bonly\s+(?:trainers?|energy)\b", text):
        return "Trainer/energy-only lot"
    if re.search(r"\b(?:card sleeves?|card binders?|binder pages?|empty binders?|toploaders?)\b", text):
        return "Accessory product; card quantity cannot be trusted"
    if not re.search(r"\b(?:lot|bulk|random|collection|unsorted)\b", text):
        return "No evidence this is a bulk/random lot"
    return None
