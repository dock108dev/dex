"""Literal local seller identity evidence shared by Discovery and Hunter.

Names/tokens only narrow the published catalog. Exact proposals still require a
literal set alias, card name and collector number. These are seller claims, not
physical-card verification, and no price or acquisition scope is selected here.
"""

import re
import unicodedata

from .discovery_search import canonical_query

_NUMBER = r"(?:[a-z]*[0-9]+[a-z]*|[a-z]+-[0-9]+)(?:\s*/\s*[a-z0-9-]+)?"


def literal(value):
    return " ".join(unicodedata.normalize("NFC", str(value)).replace("’", "'").split())


def names(printing):
    """Only retained names/explicit name aliases; never generated nicknames."""
    aliases = printing.get("attributes", {}).get("name_aliases", [])
    return tuple(
        dict.fromkeys(
            literal(value)
            for value in [printing["name"], *(aliases if isinstance(aliases, list) else [])]
            if isinstance(value, str) and value.strip()
        )
    )


def set_names(printing):
    aliases = printing.get("set_aliases", [])
    return tuple(
        dict.fromkeys(
            canonical_query(literal(value))
            for value in [printing["set_name"], *(aliases if isinstance(aliases, list) else [])]
            if isinstance(value, str) and value.strip()
        )
    )


def _phrase(value):
    return re.escape(literal(value)).replace(r"\ ", r"\s+")


def set_spans(printing, text):
    """Literal set-alias positions, including the Base Set / Base Set 2 rule."""
    text = canonical_query(literal(text))
    spans = []
    for name in set_names(printing):
        pattern = r"(?<!\w)" + _phrase(name) + r"(?!\w)"
        if name.casefold() == "base set":
            pattern += r"(?!\s*2\b(?!\s*/))"
        spans.extend(match.span() for match in re.finditer(pattern, text, re.I))
    return sorted(set(spans))


def set_claimed(printing, text):
    return bool(set_spans(printing, text))


def without_sets(printings, text):
    """Keep literal set names out of product heuristics, never identity checks.

    A confirmed single from Legendary Collection does not become a loose lot
    because its set contains the word 'Collection'. Seller product claims outside
    those exact aliases, including a separate 'lot' or 'sealed', remain visible.
    """
    text = canonical_query(literal(text))
    spans = {span for printing in printings for span in set_spans(printing, text)}
    for start, end in sorted(spans, reverse=True):
        text = text[:start] + " " * (end - start) + text[end:]
    return text


def name_spans(printing, text):
    text = literal(text)
    spans = []
    for name in names(printing):
        for match in re.finditer(r"(?<![\w'’])" + _phrase(name) + r"(?![\w'’])", text, re.I):
            # A plain Pikachu cannot stand in for Dark/Light/owner's Pikachu.
            prefix = text[max(0, match.start() - 80) : match.start()].strip()
            if re.search(r"(?:dark|light|\w+['’]s)\s*$", prefix, re.I):
                continue
            spans.append(match.span())
    return sorted(set(spans))


def literal_candidates(printings, text):
    """A retained longer name cannot collapse to a contained plain name."""
    found = [(printing, name_spans(printing, text)) for printing in printings]
    spans = {span for _, matches in found for span in matches}
    return [
        printing
        for printing, matches in found
        if any(
            not any(other != span and other[0] <= span[0] and other[1] >= span[1] for other in spans)
            for span in matches
        )
    ]


def without_names(printings, text):
    """Apply seller-product/attribute heuristics outside exact literal names."""
    text = literal(text)
    spans = {span for printing in printings for span in name_spans(printing, text)}
    for start, end in sorted(spans, reverse=True):
        text = text[:start] + " " * (end - start) + text[end:]
    return text


def _part(value):
    match = re.fullmatch(r"([a-z]*)([0-9]+)([a-z]*)", value, re.I)
    return (
        (match[1].casefold(), match[2].lstrip("0") or "0", match[3].casefold()) if match else value.casefold()
    )


def number_key(value):
    return tuple(_part(part.strip()) for part in literal(value).split("/"))


def number_claims(printing, text):
    """Numbers touching the name, or explicit #/fraction clues elsewhere.

    A bare year, set number, price or slab grade elsewhere cannot establish a
    collector number. Literal fractions remain whole, including denominators.
    """
    text = literal(text)
    adjacent, explicit = [], []
    for _, end in name_spans(printing, text):
        match = re.match(r"\s*(#\s*|no\.?\s*)?(" + _NUMBER + r")(?![\w/])", text[end:], re.I)
        if match:
            (explicit if match[1] else adjacent).append(match[2])
        # Catalogs can retain literal identifiers outside numeric grammars. They
        # need their exact spelling, not an invented numeric alias.
        retained = re.match(
            r"\s*(#\s*|no\.?\s*)?(" + _phrase(printing["collector_number"]) + r")(?![\w/])",
            text[end:],
            re.I,
        )
        if retained:
            (explicit if retained[1] else adjacent).append(retained[2])
    for match in re.finditer(r"(?<![\w/])#\s*(" + _NUMBER + r")(?![\w/])", text, re.I):
        explicit.append(match[1])
    for match in re.finditer(r"(?<![\w/])#\s*([a-z0-9]+(?:[-/][a-z0-9]+)+)(?![\w/])", text, re.I):
        explicit.append(match[1])
    for match in re.finditer(
        r"(?<![\w/])#\s*(" + _phrase(printing["collector_number"]) + r")(?![\w/])", text, re.I
    ):
        explicit.append(match[1])
    for match in re.finditer(r"(?<![\w/])(" + _NUMBER + r")(?![\w/])", text, re.I):
        if "/" in match[1]:
            explicit.append(match[1])
    if explicit:
        expected = number_key(printing["collector_number"])[0]
        adjacent = [
            claim
            for claim in adjacent
            if not (
                len(claim) == 4
                and claim.isdigit()
                and 1996 <= int(claim) <= 2099
                and number_key(claim)[0] != expected
            )
        ]
    return list(dict.fromkeys(re.sub(r"\s*/\s*", "/", claim) for claim in adjacent + explicit))


def evidence(printing, clues):
    """Return exact-number fit and diagnostics; no fuzzy evidence can fit."""
    text = clues["text"]
    if not name_spans(printing, text) or not set_claimed(printing, text):
        return dict(matched=False, claims=[], conflicts=[], uncertainties=[])
    claims = number_claims(printing, text)
    expected = number_key(printing["collector_number"])
    same = [claim for claim in claims if number_key(claim)[0] == expected[0]]
    if claims and (not same or any(number_key(claim)[0] != expected[0] for claim in claims)):
        return dict(
            matched=False,
            claims=claims,
            conflicts=["Seller collector-number claims conflict with the catalog printing or one another"],
            uncertainties=[],
        )
    conflicting = [
        claim
        for claim in same
        if len(expected) > 1 and len(number_key(claim)) > 1 and number_key(claim)[1:] != expected[1:]
    ]
    # A repeated description cannot turn contradictory fractions into a match.
    denominators = {number_key(claim)[1:] for claim in same if len(number_key(claim)) > 1}
    if conflicting or len(denominators) > 1:
        return dict(
            matched=False,
            claims=same,
            conflicts=[
                "Seller collector-number denominator conflicts with the catalog or another seller claim"
            ],
            uncertainties=[],
        )
    uncertainties = []
    if same and len(expected) == 1 and denominators:
        uncertainties.append(
            "The seller's collector-number denominator is unavailable in the catalog identity"
        )
    if same and len(expected) > 1 and not denominators:
        uncertainties.append("Seller text omits the catalog collector-number denominator")
    return dict(matched=bool(same), claims=same, conflicts=[], uncertainties=uncertainties)


def unavailable(printing):
    if any(
        printing.get(key, "published") != "published"
        for key in ("publication_state", "set_publication_state")
    ):
        return "The matching catalog printing or set is archived/unavailable; no sibling was substituted"
    return None
