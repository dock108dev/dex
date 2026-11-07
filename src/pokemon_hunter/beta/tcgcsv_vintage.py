"""Literal vintage product matching for one-off imports of retained TCGCSV feeds.

No requests, customer writes, price inference or source admission. A product name
and collector number must both agree; available subtypes remain distinct rows.
"""

import re
import unicodedata
from collections import defaultdict

from .market_identity import source_identity

SETS = {604: "Base Set", 635: "Jungle", 630: "Fossil", 1663: "Base Set"}


def number(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d+(?:/\d+)?", value.strip()):
        return None
    return str(int(value.strip().split("/")[0]))


def name(value, card_number):
    value = unicodedata.normalize("NFKC", value).replace("’", "'").casefold().strip()
    value = "".join(c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c))
    value = {"imposter professor oak": "impostor professor oak"}.get(value, value)
    suffix = re.search(r"\s*\((\d+)\)$", value)
    if suffix and str(int(suffix[1])) == card_number:
        value = value[: suffix.start()]
    for old, new in (("nidoran♂", "nidoran m"), ("nidoran♀", "nidoran f")):
        value = value.replace(old, new)
    return " ".join(value.split())


def product_number(product):
    values = [f.get("value") for f in product.get("extendedData", []) if f.get("name") == "Number"]
    return number(values[0]) if len(values) == 1 else None


def match_products(entries, products):
    """Return unique numbered parents; conflicts and non-card products stay out."""
    parents = defaultdict(list)
    for p in entries.values():
        n = number(p.get("collector_number"))
        if (
            p.get("set_name") in SETS.values()
            and p.get("language") == "en"
            and not any(p.get(k) for k in ("edition", "finish", "variant"))
            and n is not None
        ):
            parents[(p["set_name"], n, name(p["name"], n))].append(p)
    candidates = defaultdict(list)
    for product in products:
        n = product_number(product)
        group = product.get("groupId")
        if product.get("categoryId") == 3 and group in SETS and n is not None:
            candidates[(group, n, name(product["name"], n))].append(product)
    return [
        (parents[(SETS[key[0]], key[1], key[2])][0], values[0])
        for key, values in sorted(candidates.items())
        if len(values) == 1 and len(parents[(SETS[key[0]], key[1], key[2])]) == 1
    ]


def descriptor(subtype, group=None):
    """Only affirmative edition/finish labels can create physical alternatives."""
    edition, finish = source_identity(group, subtype)
    if edition not in {"unlimited", "first_edition"} or finish not in {"normal", "holo"}:
        return None
    result = {"type": finish}
    if edition == "first_edition":
        result["stamp"] = ["1st-edition"]
    else:
        result["edition"] = "unlimited"
    if str(group) == "1663":
        result["other"] = ["shadowless"]
    return result


def numbered_finish(printing):
    """Original English numbered sets encode holo status in the card number.

    These closed 1999 lists have no reverse-holo slot. Edition and special
    printings still require separate evidence; this does not infer either.
    """
    bounds = {"Base Set": (16, 102), "Jungle": (16, 64), "Fossil": (15, 62)}
    n = number(printing.get("collector_number"))
    limits = bounds.get(printing.get("set_name"))
    if printing.get("language") != "en" or not n or not limits or not 1 <= int(n) <= limits[1]:
        return None
    return "holo" if int(n) <= limits[0] else "normal"
