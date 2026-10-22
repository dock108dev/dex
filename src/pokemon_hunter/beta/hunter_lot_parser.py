"""Bounded interpretation of supplied seller text and authorized printing identities.

No acquisition, review persistence or collection mutation belongs here. Caller
services retain account/lease checks and admission of reference values.
"""

import hashlib
import re
from html.parser import HTMLParser

from . import discovery_comparison as dc
from . import discovery_matching, hunter_catalog, listing_details, shopping

MAX_TEXT_BYTES = 65536
MAX_TOKENS = 8192
MAX_SEGMENTS = 400
MAX_SEGMENT_CHARS = 2048
MAX_ITEMS = 200
MAX_QUANTITY = 100000
MAX_CANDIDATES = 40
MAX_CANDIDATE_BINDINGS = 200
_BLOCKS = {"br", "p", "div", "li", "ul", "ol", "tr", "td", "h1", "h2", "h3"}
_HIDDEN = {"script", "style", "iframe", "object", "svg", "template"}


class _PlainText(HTMLParser):
    """Discard markup, scripts and links without loading any external resource."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = []

    def handle_starttag(self, tag, attrs):
        if tag in _HIDDEN:
            self.hidden.append(tag)
        if tag in _BLOCKS and not self.hidden:
            self.parts.append("\n")

    def handle_startendtag(self, tag, attrs):
        if tag in _BLOCKS and not self.hidden:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if self.hidden and tag == self.hidden[-1]:
            self.hidden.pop()
        if tag in _BLOCKS and not self.hidden:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def _text(raw):
    if not isinstance(raw, str):
        raise ValueError("Seller content must be bounded text")
    parser = _PlainText()
    parser.feed(raw)
    parser.close()
    return "".join(parser.parts)


def _quantity(text, *, title=False):
    if re.search(r"\b[0-9]+\s*[x×]{2,}", text, re.I):
        return None, "Explicit per-card multiplicity is malformed"
    explicit_patterns = (
        r"^\s*(?:[-*•]\s+)?([+-]?[0-9]+(?:\.[0-9]+)?)\s*[x×]+\b",
        r"\b[x×]\s*([+-]?[0-9]+(?:\.[0-9]+)?)(?![\w.])",
        r"\b(?:qty|quantity)\s*[:=]?\s*([+-]?[0-9]+(?:\.[0-9]+)?)\b",
        r"\b([+-]?[0-9]+(?:\.[0-9]+)?)\s+copies?\b",
    )
    for pattern in explicit_patterns:
        for match in re.finditer(pattern, text, re.I):
            if not re.fullmatch(r"[1-9][0-9]{0,5}", match[1]) or int(match[1]) > MAX_QUANTITY:
                return None, "Explicit per-card multiplicity is invalid or exceeds the review limit"
    patterns = (
        r"^\s*(?:[-*•]\s+)?([1-9][0-9]{0,5})\s*[x×]\s+",
        r"^\s*(?:[-*•]\s+)?([1-9][0-9]{0,5})\s+(?:copies?\s+(?:of\s+)?|of\s+)",
        r"\s+[x×]\s*([1-9][0-9]{0,5})\s*$",
        r"\b[x×]\s*([1-9][0-9]{0,5})\b",
        r"\s*\(\s*([1-9][0-9]{0,5})\s+copies?\s*\)\s*$",
        r"\b(?:qty|quantity)\s*[:=]?\s*([1-9][0-9]{0,5})\b",
    )
    values = {int(m[1]) for pattern in patterns for m in re.finditer(pattern, text, re.I)}
    if len(values) > 1:
        return None, "Conflicting per-card quantities"
    if values:
        value = next(iter(values))
        if value > MAX_QUANTITY:
            return None, "Per-card quantity exceeds the review limit"
        return value, None
    if re.search(r"\b(?:pair|several|multiple|various|some|many|random|assorted|choose|pick)\b", text, re.I):
        return None, "Per-card quantity is ambiguous"
    return (None, "A title mention does not establish per-card multiplicity") if title else (1, None)


def _totals(text):
    text = re.sub(
        r"(?<!\d)[1-9][0-9]{0,2}(?:,[0-9]{3})+(?!\d)", lambda match: match[0].replace(",", ""), text
    )
    patterns = (
        r"\blot\s+of\s+([1-9][0-9]{0,5})\b",
        r"\b([1-9][0-9]{0,5})\s+(?:total\s+)?cards?\b",
        r"\btotal\s*(?:cards?\s*)?[:=]?\s*([1-9][0-9]{0,5})\b",
    )
    return {int(m[1]) for pattern in patterns for m in re.finditer(pattern, text, re.I)}


def _conflicting_fields(clues):
    fields = set()
    for issue in clues["conflicts"]:
        folded = issue.casefold()
        for token, field in (
            ("language", "language"),
            ("edition", "edition"),
            ("finish", "finish"),
            ("condition", "condition"),
        ):
            if token in folded:
                fields.add(field)
        if "grade" in folded:
            fields.update({"grade", "grader"})
    if len(clues.get("condition_claims", [])) > 1:
        fields.add("condition")
    return fields


def parse(raw, printings, *, detail=None, _index=None):
    """Parse supplied authorized text only, with hard work and quantity limits.

    ``detail`` is an internal authorized adapter input, never a client-supplied body.
    Its exact variation must match the summary. It grants no acquisition right.
    Repeated identical mentions across fields are evidence, not extra copies.
    """
    if not isinstance(raw, dict):
        raise ValueError("Choose an authorized listing summary")
    fields = [("title", raw.get("title", "")), ("summary", raw.get("shortDescription", ""))]
    if detail is not None:
        listing_details.validate_response(raw.get("itemId"), detail)
        fields.extend(
            [
                ("detail_title", detail.get("title", "")),
                ("official_description", detail.get("description", "")),
            ]
        )
        aspects = detail.get("localizedAspects", [])
        if not isinstance(aspects, list) or len(aspects) > 100:
            raise ValueError("Official lot details exceed 100 structured aspects")
        for aspect in aspects:
            if not isinstance(aspect, dict):
                raise ValueError("Unsupported official detail aspect")
            if str(aspect.get("name", "")).casefold() in {"number of cards", "lot size"}:
                value = aspect.get("value", "")
                if not isinstance(value, str) or len(value) > 100:
                    raise ValueError("Seller card-count aspect exceeds its bound")
                fields.append(("official_card_count", "total cards: " + value))
    if any(not isinstance(value, str) for _, value in fields):
        raise ValueError("Seller content must be bounded text")
    raw_bytes = sum(len(value.encode("utf-8")) for _, value in fields)
    if raw_bytes > MAX_TEXT_BYTES:
        raise ValueError("Seller text exceeds 65536 bytes; explicit manual review required")
    fields = [(name, _text(value)) for name, value in fields]
    if sum(len(re.findall(r"\S+", value)) for _, value in fields) > MAX_TOKENS:
        raise ValueError("Seller text exceeds 8192 tokens; explicit manual review required")
    segments = []
    totals = set()
    for field, value in fields:
        totals.update(_totals(value))
        # Avoid splitting collector fractions or thousands separators. A comma
        # between textual items is an ordinary seller list delimiter.
        for piece in re.split(r"[\n;]+|,(?![0-9]{3}\b)", value):
            piece = piece.strip()
            if not piece:
                continue
            if len(piece) > MAX_SEGMENT_CHARS:
                raise ValueError("Seller text segment exceeds 2048 characters; manual review required")
            segments.append((field, piece))
    if len(segments) > MAX_SEGMENTS:
        raise ValueError("Seller text exceeds 400 segments; manual review required")
    index = _index or hunter_catalog.IdentityIndex(printings)
    combined_text = " ".join(value for _, value in fields)
    combined_clues = dc._clues(dict(title=combined_text))
    literal_names = discovery_matching.literal_candidates(index.candidates(combined_clues), combined_text)
    product_claims = discovery_matching.without_names(literal_names, combined_text)
    exact_sets = [p for p in literal_names if discovery_matching.evidence(p, combined_clues)["matched"]]
    product_claims = discovery_matching.without_sets(exact_sets, product_claims)
    if dc.product_kind(product_claims) == "unsupported":
        raise ValueError(
            "Unsupported sealed, mystery, random or curated product; contents valuation unavailable"
        )
    proposals, seen, unresolved = [], {}, []
    candidate_bindings = 0
    for field, text in sorted(segments, key=lambda segment: segment[0].endswith("title")):
        # Multiplicity is parsed separately; it cannot become a conflicting
        # collector-number claim in the shared literal matcher.
        identity_text = re.sub(r"\b(?:qty|quantity)\s*[:=]?\s*[1-9][0-9]{0,5}\b", " ", text, flags=re.I)
        identity_text = re.sub(r"\b[x×]\s*[1-9][0-9]{0,5}\b", " ", identity_text, flags=re.I)
        clues = dc._clues(dict(title=identity_text, condition=raw.get("condition", "")))
        candidates = index.candidates(clues)
        plausible = dc._approx_matches(candidates, clues)
        if not plausible:
            # Headers/counts and innocuous listing prose are not invented cards.
            # Unrecognized explicit quantity lines are retained as unresolved.
            quantity, reason = _quantity(text, title=field.endswith("title"))
            if quantity is not None and re.search(r"(?:^\s*\d+\s*[x×]|\b(?:qty|quantity)\b)", text, re.I):
                unresolved.append(
                    dict(text=text, source_field=field, quantity=quantity, reason="No local card identity")
                )
                if len(proposals) + len(unresolved) > MAX_ITEMS:
                    raise ValueError("Lot exceeds 200 content items; explicit manual review required")
            continue
        exact = dc._matches(candidates, clues)
        quantity, quantity_reason = _quantity(text, title=field.endswith("title"))
        names = {p["name"].casefold() for p in plausible}
        reasons = list(clues["conflicts"])
        if quantity_reason:
            reasons.append(quantity_reason)
        if len(names) > 1:
            reasons.append("Multiple card names share one text segment; split and correct quantities")
            quantity = None
        if len(exact) != 1:
            reasons.append(
                "Printing needs correction" if exact else "Set or collector-number evidence is incomplete"
            )
        chosen = exact[0] if len(exact) == 1 and not clues["conflicts"] else None
        if chosen and dc._identity_conflicts(chosen, clues):
            reasons.extend(dc._identity_conflicts(chosen, clues))
            chosen = None
        if chosen and discovery_matching.unavailable(chosen):
            reasons.append(discovery_matching.unavailable(chosen))
            chosen = None
        candidate_rows = exact or plausible
        visible_candidates = candidate_rows[
            : min(MAX_CANDIDATES, MAX_CANDIDATE_BINDINGS - candidate_bindings)
        ]
        candidate_bindings += len(visible_candidates)
        if len(visible_candidates) < len(candidate_rows):
            reasons.append("Plausible printing choices exceed the bounded response; refine locally")
        # Same identity+quantity repeated in title/description never adds units.
        # Conflicting repeated quantities stay as separate unresolved claims.
        identity_key = tuple(sorted(p["id"] for p in candidate_rows))
        key = (identity_key, quantity)
        evidence = dict(source_field=field, text=text)
        if key in seen:
            previous = seen[key]
            previous["mentions"].append(evidence)
            conflicting = []
            for trait in ("language", "edition", "finish", "grader", "grade"):
                before, after = previous["clues"].get(trait), clues.get(trait)
                if before and after and before != after:
                    conflicting.append(trait)
            conditions = set(previous["clues"].get("condition_claims", [])) | set(
                clues.get("condition_claims", [])
            )
            if len(conditions) > 1:
                conflicting.append("condition")
            if reasons or conflicting:
                previous["included_quantity"] = 0
                previous["printing_id"] = None
                previous["conflicting_fields"] = sorted(
                    set(previous.get("conflicting_fields", []))
                    | set(conflicting)
                    | _conflicting_fields(clues)
                )
                previous["reasons"] = list(
                    dict.fromkeys(
                        [
                            *previous["reasons"],
                            *reasons,
                            "Repeated seller mentions contain conflicting identity or applicability claims",
                        ]
                    )
                )
                previous["clues"]["conflicts"] = list(
                    dict.fromkeys(
                        [
                            *previous["clues"]["conflicts"],
                            *clues["conflicts"],
                            "Repeated seller mentions require explicit attribute correction",
                        ]
                    )
                )
            continue
        other = [p for (ids, _), p in seen.items() if ids == identity_key]
        if (
            other
            and quantity is None
            and quantity_reason == "A title mention does not establish per-card multiplicity"
        ):
            other[0]["mentions"].append(evidence)
            continue
        if other:
            reasons.append("Repeated card mention has conflicting quantities; correct multiplicity")
            quantity = None
            for previous in other:
                previous["included_quantity"] = 0
                previous["reasons"].append(
                    "Repeated card mention has conflicting quantities; correct multiplicity"
                )
        row = dict(
            proposal_id=hashlib.sha256((str(len(proposals)) + "\0" + text).encode()).hexdigest()[:24],
            name=next(iter(names)) if len(names) == 1 else None,
            quantity=quantity,
            included_quantity=quantity if chosen and quantity and not reasons else 0,
            printing_id=chosen["id"] if chosen else None,
            candidates=[
                dict(shopping.identity(p), image_binding=dict(printing_id=p["id"], role="catalog_reference"))
                for p in visible_candidates
            ],
            candidates_total=len(candidate_rows),
            reasons=reasons,
            conflicting_fields=sorted(_conflicting_fields(clues)),
            clues={k: v for k, v in clues.items() if k != "text"},
            mentions=[evidence],
        )
        seen[key] = row
        proposals.append(row)
        if len(proposals) + len(unresolved) > MAX_ITEMS:
            raise ValueError("Lot exceeds 200 content items; explicit manual review required")
    if any(total > MAX_QUANTITY for total in totals):
        raise ValueError("Seller card total exceeds 100000 cards")
    total = next(iter(totals)) if len(totals) == 1 else None
    known = sum(p["included_quantity"] for p in proposals)
    if known > MAX_QUANTITY:
        raise ValueError("Proposed quantities exceed 100000 cards")
    unknown = total - known if total is not None and total >= known else None
    issues = []
    if len(totals) > 1:
        issues.append("Conflicting seller-stated total card counts")
    if total is not None and known > total:
        issues.append("Proposed quantities exceed the seller-stated card count")
    if not proposals:
        issues.append("Vague or photos-only contents remain unresolved")
    if unresolved or any(not p["included_quantity"] for p in proposals):
        issues.append("Unresolved identity or quantity claims require correction")
    if unknown is None or unknown:
        issues.append("The complete lot contents have not been reconciled")
    availability = raw.get("estimatedAvailabilities", [])
    stock = (
        {
            v.get("estimatedAvailableQuantity")
            for v in availability
            if isinstance(v, dict) and type(v.get("estimatedAvailableQuantity")) is int
        }
        if isinstance(availability, list)
        else set()
    )
    units = raw.get("lotSize")
    lot_units = (
        int(units) if isinstance(units, (int, str)) and re.fullmatch(r"[1-9][0-9]{0,5}", str(units)) else None
    )
    return dict(
        proposals=proposals,
        unresolved_contents=unresolved,
        seller_stated_total=total,
        seller_stated_totals=sorted(totals),
        included_quantity=known,
        unknown_remainder=unknown,
        stock_quantity=next(iter(stock)) if len(stock) == 1 else None,
        lot_units=lot_units,
        quantity_issues=issues,
        text_bytes=raw_bytes,
        segment_count=len(segments),
        detail_used=detail is not None,
    )
