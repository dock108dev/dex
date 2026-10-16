"""Strict official listing identity and bounded seller-detail projection.

Stateless adapters over supplied identifiers and response bodies; no acquisition,
account reads, temporary review state or persistence. Seller claims stay claims.
"""

import re
from datetime import datetime
from urllib.parse import parse_qs, urlsplit

from . import discovery_comparison as dc
from . import shopping

_NUMBER = r"[1-9][0-9]{8,14}"
_REST = re.compile(rf"v1\|({_NUMBER})\|(0|{_NUMBER})")


def parse_identifier(value):
    error = "Paste a supported HTTPS ebay.com item URL, numeric item ID or literal v1|item|variation ID."
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError(error)
    value = value.strip()
    if not value or any(ord(c) < 33 or ord(c) > 126 for c in value) or "%" in value or "\\" in value:
        raise ValueError(error)
    match = _REST.fullmatch(value)
    if match:
        return dict(legacy=match[1], variation=match[2], rest=value)
    if re.fullmatch(_NUMBER, value):
        return dict(legacy=value, variation="0", rest=None)
    try:
        url = urlsplit(value)
        if (
            url.scheme != "https"
            or url.netloc not in {"ebay.com", "www.ebay.com", "m.ebay.com"}
            or url.fragment
            or url.username
            or url.password
            or url.port
        ):
            raise ValueError(error)
        match = re.fullmatch(rf"/itm/(?:[A-Za-z0-9_-]+/)?({_NUMBER})/?", url.path)
        if not match:
            raise ValueError(error)
        params = parse_qs(url.query, keep_blank_values=True, strict_parsing=True) if url.query else {}
        # Ordinary tracking is ignored, never fetched or sent to the API. Reject
        # duplicate/unknown selectors, empty values, URL-valued or encoded inputs.
        allowed = {
            "var",
            "hash",
            "_skw",
            "_nkw",
            "itmmeta",
            "itmprp",
            "mkcid",
            "mkevt",
            "mkrid",
            "campid",
            "toolid",
            "customid",
            "_trkparms",
            "_trksid",
        }
        if set(params) - allowed or any(len(v) != 1 or not v[0] for v in params.values()):
            raise ValueError(error)
        variation = params.get("var", ["0"])[0]
        if variation != "0" and not re.fullmatch(_NUMBER, variation):
            raise ValueError(error)
        return dict(legacy=match[1], variation=variation, rest=None)
    except (ValueError, TypeError):
        raise ValueError(error) from None


def validate_response(identifier, raw):
    requested = parse_identifier(identifier)
    returned = raw.get("itemId")
    matched = _REST.fullmatch(returned) if isinstance(returned, str) else None
    if not matched or (matched[1], matched[2]) != (requested["legacy"], requested["variation"]):
        raise ValueError(
            "eBay returned a different item or unresolved variation. Paste the exact variation URL or REST ID."
        )
    if raw.get("legacyItemId") not in (None, requested["legacy"]):
        raise ValueError("eBay returned a conflicting legacy item identity.")
    if requested["variation"] == "0" and (
        raw.get("primaryItemGroup") or raw.get("itemGroupType") or raw.get("itemGroupId")
    ):
        raise ValueError("This parent listing needs an exact variation URL or REST ID.")
    end = raw.get("itemEndDate")
    if end:
        try:
            ended = datetime.fromisoformat(end.replace("Z", "+00:00")) <= datetime.now(shopping.TZ)
        except (ValueError, TypeError):
            raise ValueError("Listing availability could not be resolved.") from None
        if ended:
            raise ValueError("This listing has ended. Manual and in-person checks remain available.")
    if any(
        r.get("estimatedAvailabilityStatus") in {"OUT_OF_STOCK", "UNAVAILABLE"}
        for r in raw.get("estimatedAvailabilities", [])
    ):
        raise ValueError("This listing is unavailable.")
    if "FIXED_PRICE" not in raw.get("buyingOptions", []) or "AUCTION" in raw.get("buyingOptions", []):
        raise ValueError(
            "Only fixed-price listing details are supported. Use manual entry for an auction observation."
        )
    return returned


def _text(value, maximum=500):
    return str(value or "")[:maximum]


def _money(value):
    if not isinstance(value, dict) or not re.fullmatch(r"[A-Z]{3}", str(value.get("currency", ""))):
        return {"amount": None, "currency": None}
    try:
        amount = shopping.math.money(shopping.math.amount(value.get("value")))
    except (ValueError, TypeError):
        amount = None
    return dict(amount=amount, currency=value["currency"])


def details(identifier, raw):
    item = validate_response(identifier, raw)
    aspects = [
        {"name": _text(a.get("name"), 80), "value": _text(a.get("value"))}
        for a in raw.get("localizedAspects", [])[:100]
        if isinstance(a, dict)
    ]
    condition = _text(raw.get("condition"))
    descriptors = raw.get("conditionDescriptors", [])[:30]
    # These are claims only. Never render seller description/HTML or remote images.
    evidence = " ".join(a["name"] + ": " + a["value"] for a in aspects)
    condition += " " + " ".join(
        _text(a.get("name"))
        + " "
        + " ".join(_text(v.get("content")) for v in a.get("values", []) if isinstance(v, dict))
        for a in descriptors
        if isinstance(a, dict)
    )
    clues = dc._clues(dict(title=_text(raw.get("title")), shortDescription=evidence, condition=condition))
    claims = {a["name"].casefold(): a["value"] for a in aspects}
    for descriptor in descriptors:
        if not isinstance(descriptor, dict):
            continue
        values = [
            v.get("content")
            for v in descriptor.get("values", [])
            if isinstance(v, dict) and isinstance(v.get("content"), str)
        ]
        if len(values) == 1:
            claims[_text(descriptor.get("name")).casefold()] = values[0]
    literal_grader = claims.get("professional grader", "")
    literal_grade = claims.get("grade", "")
    graders = re.findall(r"\b(PSA|BGS|CGC|SGC)\b", literal_grader, re.I)
    if len(graders) == 1 and literal_grade in {"8", "9", "10"}:
        proposed = (graders[0].upper(), literal_grade)
        if clues["grader"] and proposed != (clues["grader"], clues["grade"]):
            clues["conflicts"].append("Structured and title grade claims conflict")
        else:
            clues.update(grader=proposed[0], grade=proposed[1], graded=True)
            clues["conflicts"] = [
                issue
                for issue in clues["conflicts"]
                if issue != "No supported literal grader and grade combination"
            ]
    sizes = {
        int(a["value"])
        for a in aspects
        if a["name"].casefold() in {"number of cards", "lot size"}
        and re.fullmatch(r"[1-9][0-9]{0,5}", a["value"])
        and int(a["value"]) <= 100000
    }
    sizes.update(
        int(n)
        for n in re.findall(r"\blot\s+of\s+([1-9][0-9]{0,5})\b", _text(raw.get("title")), re.I)
        if int(n) <= 100000
    )
    size = next(iter(sizes)) if len(sizes) == 1 else None
    stock = [
        r.get("estimatedAvailableQuantity")
        for r in raw.get("estimatedAvailabilities", [])
        if type(r.get("estimatedAvailableQuantity")) is int
    ]
    shipping = [_money(s.get("shippingCost")) for s in raw.get("shippingOptions", []) if isinstance(s, dict)]
    # Country-only estimates may be absent or disagree by service. Never invent free shipping.
    unique = {(s["amount"], s["currency"]) for s in shipping}
    shipping = (
        dict(zip(("amount", "currency"), next(iter(unique))))
        if len(unique) == 1
        else dict(amount=None, currency=None)
    )
    parsed = parse_identifier(item)
    return dict(
        item_id=item,
        item_url=f"https://www.ebay.com/itm/{parsed['legacy']}"
        + (f"?var={parsed['variation']}" if parsed["variation"] != "0" else ""),
        title=_text(raw.get("title")),
        price=_money(raw.get("price")),
        shipping=shipping,
        condition=condition[:1000].strip(),
        aspects=aspects,
        seller_lot_size=size,
        api_lot_size=raw.get("lotSize")
        if isinstance(raw.get("lotSize"), (str, int))
        and str(raw["lotSize"]).isdigit()
        and len(str(raw["lotSize"])) <= 6
        else None,
        stock_quantity=stock[0] if len(set(stock)) == 1 else None,
        clues={k: v for k, v in clues.items() if k != "text"},
        match_text=clues["text"],
    )
