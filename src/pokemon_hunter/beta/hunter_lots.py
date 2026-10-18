"""Bounded local seller-content proposals and leased Ungraded lot reviews.

No provider transport or collection writers are used here. Reviews retain only
corrections and an opaque original Hunter origin; every read re-enters that lease
and normal reference admission. Official detail acquisition remains a future gate.
"""

import hashlib
import json
import re
import threading
import time
import uuid
from copy import deepcopy
from datetime import UTC, datetime
from html.parser import HTMLParser

from django.http import Http404

from . import (
    collection,
    discovery,
    discovery_matching,
    hunter,
    hunter_catalog,
    hunter_coverage,
    listing_details,
    shopping,
    store,
)
from . import discovery_comparison as dc
from . import lot_calculator as lot

MAX_TEXT_BYTES = 65536
MAX_TOKENS = 8192
MAX_SEGMENTS = 400
MAX_SEGMENT_CHARS = 2048
MAX_ITEMS = 200
MAX_QUANTITY = 100000
MAX_CANDIDATES = 40
MAX_CANDIDATE_BINDINGS = 200
MAX_SELECTED_BATCH = 8
MAX_REVIEWS = 16
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_reviews = {}
_lock = threading.RLock()
_BLOCKS = {"br", "p", "div", "li", "ul", "ol", "tr", "td", "h1", "h2", "h3"}
_HIDDEN = {"script", "style", "iframe", "object", "svg", "template"}


def _selected_ids(result_ids, maximum=MAX_SELECTED_BATCH):
    if (
        not isinstance(result_ids, list)
        or not 1 <= len(result_ids) <= maximum
        or any(
            not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", value)
            for value in result_ids
        )
        or len(set(result_ids)) != len(result_ids)
    ):
        raise ValueError(f"Select between one and {maximum} distinct temporary lot handles")


def _bounded_response(value):
    if len(json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode("utf-8")) > MAX_RESPONSE_BYTES:
        raise ValueError("Lot response exceeds 2 MiB; choose fewer items or refine contents locally")
    return value


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

    ``detail`` is a future internal adapter input, never a client-supplied body.
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


def _catalog(actor):
    games = {r["id"] for r in store.rows("SELECT id FROM games WHERE game_key='pokemon'")}
    return [p for p in collection.catalog(actor, include_archived=True) if p["game_id"] in games]


def _source(actor, session_key, origin):
    return hunter.summary_lease(actor, session_key, **origin)


def _initial_cards(proposal):
    cards = {}
    for row in proposal["proposals"]:
        if row["included_quantity"]:
            pid = row["printing_id"]
            traits = {
                k: row["clues"].get(k) or ""
                for k in ("language", "edition", "finish", "condition", "grade", "grader")
            }
            cards.setdefault(pid, dict(printing_id=pid, quantity=0, **traits))["quantity"] += row[
                "included_quantity"
            ]
    return list(cards.values())


def _cost_inputs(raw):
    price = listing_details.prices(raw)
    options = raw.get("shippingOptions", [])
    shipping = (
        {
            (value["amount"], value["currency"])
            for option in options
            if isinstance(option, dict)
            for value in [listing_details._money(option.get("shippingCost"))]
        }
        if isinstance(options, list)
        else set()
    )
    shipping_amount = (
        next(iter(shipping))[0] if len(shipping) == 1 and next(iter(shipping))[1] == "USD" else ""
    )
    minimum = listing_details._money(raw.get("minimumPriceToBid"))
    return dict(
        price=price["price"]["amount"] or "",
        currency=price["price"]["currency"] or "USD",
        price_kind=price["price_kind"],
        shipping=shipping_amount or "",
        tax="",
        other_costs="",
        planned_bid="",
        buy_now_price=price["buy_now"]["amount"],
        buy_now_currency=price["buy_now"]["currency"],
        minimum_next_bid=minimum["amount"]
        if price["price_kind"] == "current_bid" and minimum["currency"] == "USD"
        else None,
        minimum_next_bid_currency=minimum["currency"] if price["price_kind"] == "current_bid" else None,
    )


def _compare(actor, raw, proposal, corrections, entries, records=None):
    cards = corrections["cards"] if corrections else _initial_cards(proposal)
    if corrections:
        inherited = {
            candidate["id"]: {
                key: row["clues"].get(key) or ""
                for key in ("language", "edition", "finish", "condition", "grade", "grader")
            }
            for row in proposal["proposals"]
            for candidate in row["candidates"]
        }
        cards = [dict(dict(grade="raw") | inherited.get(card["printing_id"], {}), **card) for card in cards]
    unknown = corrections["unknown_contents"] if corrections else proposal["unknown_remainder"]
    costs = dict(_cost_inputs(raw), **(corrections.get("costs", {}) if corrections else {}))
    now = datetime.now(UTC)
    date = now.astimezone(shopping.TZ).date().isoformat()

    def cost(key):
        value = costs.get(key) or None
        return dict(
            amount=value,
            currency=costs["currency"],
            status="known" if value is not None else "unknown",
            date=date,
        )

    records = lot.retained_records() if records is None else records
    references = hunter_catalog.ReferenceIndex(records)
    traits = {c["printing_id"]: c for c in cards}

    reference_reasons = {}
    repeated_conflicts = {
        candidate["id"]: set(row.get("conflicting_fields", []))
        for row in proposal["proposals"]
        for candidate in row["candidates"]
        if row.get("conflicting_fields")
    }
    corrected_fields = {row["printing_id"]: set(row) for row in corrections["cards"]} if corrections else {}

    def cells(p, records, today):
        if repeated_conflicts.get(p["id"], set()) - corrected_fields.get(p["id"], set()):
            reference_reasons[p["id"]] = "Conflicting seller mentions require explicit attribute correction"
            return dict.fromkeys(lot.COLUMNS)
        unavailable = discovery_matching.unavailable(p)
        if unavailable:
            reference_reasons[p["id"]] = unavailable
            return dict.fromkeys(lot.COLUMNS)
        row = traits[p["id"]]
        clues = dc._clues(
            dict(
                title=" ".join(
                    str(row.get(k) or "") for k in ("language", "edition", "finish", "grade", "grader")
                ),
                condition=row.get("condition", ""),
            )
        )
        clues.update({k: row.get(k) or None for k in ("language", "edition", "finish", "grader")})
        clues.update(
            grade=row.get("grade") or "raw", graded=row.get("grade", "raw") not in {"raw", "unknown", ""}
        )
        values, reasons = dc._reference_cells(p, references.for_printing(p), today, clues)
        reference_reasons[p["id"]] = reasons.get("raw", "No applicable admitted Ungraded reference")
        return dict.fromkeys(lot.COLUMNS) | values

    prepared = lot.prepare(
        actor,
        dict(
            cards=[
                dict(
                    printing_id=c["printing_id"],
                    quantity=c["quantity"],
                    values={g: dict(mode="guide") for g in lot.COLUMNS},
                )
                for c in cards
                if c["quantity"]
            ],
            listing_observation=dict(cost("price"), price_kind=costs["price_kind"], source_url=None),
            planned_bid=dict(cost("planned_bid"), price_kind="personal_planned_bid"),
            delivery_cost_inputs={
                basis: {key: cost(key) for key in shopping.math.COSTS} for basis in shopping.math.BASES
            },
        ),
        now=now,
        review_traits=traits,
        unknown_quantity=unknown,
        catalog_entries=entries,
        reference_records=records,
        reference_cells=cells,
    )
    scenario = prepared["scenarios"]["raw"]
    result = scenario["result"]
    reconciled = unknown == 0 and (corrections is not None or not proposal["quantity_issues"])
    comparison = result["comparisons"]["listing_observation"]
    complete = (
        reconciled
        and result["coverage"]["unpriced_units"] == 0
        and bool(cards)
        and comparison["full_delivered_cost"] is not None
    )
    if not reconciled:
        for basis in result["comparisons"].values():
            basis["full_selected_reference_minus_delivered_cost"] = None
        result["full_lot_total"] = None
    unpriced_ids = set(result["unpriced_selection_ids"])
    return dict(cards=cards, unknown_contents=unknown, costs=costs), dict(
        scenario="Ungraded",
        result=result,
        references=[dc._reference(r) for r in scenario["references"]],
        priced_card_quantity=result["coverage"]["priced_units"],
        unpriced_card_quantity=result["coverage"]["unpriced_units"],
        priced_cards=[
            dict(
                printing_id=c["printing_id"],
                quantity=c["quantity"],
                reference_subtotal=result["line_displays"].get(c["printing_id"]),
            )
            for c in cards
            if c["printing_id"] not in unpriced_ids
        ],
        unpriced_matches=[
            dict(
                printing_id=c["printing_id"],
                quantity=c["quantity"],
                reason=reference_reasons.get(c["printing_id"], "No applicable admitted Ungraded reference"),
            )
            for c in cards
            if c["printing_id"] in unpriced_ids
        ],
        quantities_reconciled=reconciled,
        complete_delivered_comparison=complete,
        comparison_diagnostics=hunter_coverage.lot_diagnostics(
            reconciled=reconciled,
            unknown_contents=unknown,
            unpriced_units=result["coverage"]["unpriced_units"],
            costs=costs,
            reference_count=len(scenario["references"]),
        ),
        label="Complete delivered reference comparison"
        if complete
        else "Priced subtotal; incomplete lot comparison",
        whole_lot_price_count=1,
        comparison_kind="auction_current_bid_scenario"
        if costs["price_kind"] == "current_bid"
        else "buy_it_now_reference_comparison",
        minimum_next_bid=costs.get("minimum_next_bid"),
        minimum_next_bid_currency=costs.get("minimum_next_bid_currency"),
        buy_now_amount=costs.get("buy_now_price"),
        final_purchase_price=None,
        save_allowed=False,
        limitations=[
            "Dated references are not resale EV, profit, a bid limit or purchase advice",
            *([] if reconciled else proposal["quantity_issues"]),
        ],
    )


def _erase(key):
    with _lock:
        _reviews.pop(key, None)


def erase_parent(run_id):
    """Called by the original Hunter Stop/expiry path, without renewing rights."""
    with _lock:
        keys = [key for key, value in _reviews.items() if value["origin"]["run_id"] == str(run_id)]
        for key in keys:
            _reviews.pop(key, None)


def erase_detail(action_id):
    with _lock:
        keys = [key for key, value in _reviews.items() if value.get("detail_action") == str(action_id)]
        for key in keys:
            _reviews.pop(key, None)


def analyze(actor, session_key, run_id, result_id, *, _detail_action=None, _context=None):
    """Explicit local Analyze lot; no implicit official detail request."""
    owner = discovery._owner(actor, session_key)
    origin = dict(run_id=run_id, result_id=result_id)
    source = _source(actor, session_key, origin)
    with _lock:
        owned = [(key, value) for key, value in _reviews.items() if value["owner"] == owner]
        if len(owned) >= MAX_REVIEWS:
            raise ValueError("At most 16 temporary lot reviews; let an existing lease expire")
        key = str(uuid.uuid4())
        _reviews[key] = dict(
            owner=owner,
            origin=origin,
            created=source["created"],
            revision=1,
            corrections=None,
            detail_action=_detail_action,
        )
    timer = threading.Timer(
        max(0, source["created"] + discovery.EPHEMERAL_SECONDS - time.monotonic()), _erase, args=(key,)
    )
    timer.daemon = True
    timer.start()
    try:
        return read(actor, session_key, key, _context=_context)
    except Exception:
        _erase(key)
        raise


def _lookup(actor, session_key, review_id):
    owner = discovery._owner(actor, session_key)
    with _lock:
        review = _reviews.get(str(review_id))
        if review is None or review["owner"] != owner:
            raise Http404
        value = deepcopy(review)
    try:
        source = _source(actor, session_key, value["origin"])
    except (Http404, ValueError):
        _erase(str(review_id))
        raise
    return value, source


def read(actor, session_key, review_id, *, _context=None):
    value, source = _lookup(actor, session_key, review_id)
    generation = _context["generation"] if _context else collection.generation(actor)
    entries = _context["entries"] if _context else _catalog(actor)
    detail = None
    if value.get("detail_action"):
        from . import hunter_lot_details

        detail = hunter_lot_details.leased_detail(actor, session_key, value["detail_action"], value["origin"])
    proposal = parse(source["raw"], entries, detail=detail, _index=_context["index"] if _context else None)
    review, comparison = _compare(
        actor,
        detail or source["raw"],
        proposal,
        value["corrections"],
        entries,
        records=_context["records"] if _context else None,
    )
    current_source = _source(actor, session_key, value["origin"])
    if current_source["raw"] != source["raw"] or current_source["created"] != source["created"]:
        raise collection.Conflict("Listing changed while reviewing lot contents; reload")
    source = current_source
    if collection.generation(actor) != generation:
        raise collection.Conflict("Catalog changed while reviewing lot contents; reload")
    with _lock:
        current = _reviews.get(str(review_id))
        if current is None or current["owner"] != value["owner"]:
            raise Http404
        if current["revision"] != value["revision"]:
            raise collection.Conflict("Lot review changed while preparing comparison; reload")
    return _bounded_response(
        dict(
            review_id=str(review_id),
            revision=value["revision"],
            expires_in_seconds=source["expires_in_seconds"],
            proposal=proposal,
            review=review,
            comparison=comparison,
            provenance=dict(
                origin=value["origin"],
                item_id=source["raw"].get("itemId"),
                source="authorized_official_detail" if detail else "authorized_summary",
                detail_fetched=detail is not None,
            ),
            correction_contract=dict(
                required=["revision", "cards", "unknown_contents"],
                optional=["costs"],
                explicit_zero_remainder="User confirms all contents identified",
                source_lease_renews=False,
                explicit_card_attributes={
                    card["printing_id"]: sorted(
                        set(card) & {"condition", "grade", "grader", "language", "edition", "finish"}
                    )
                    for card in (value["corrections"]["cards"] if value["corrections"] else [])
                },
            ),
            save_allowed=False,
        )
    )


def correct(actor, session_key, review_id, raw):
    value, _ = _lookup(actor, session_key, review_id)
    shopping.fields(
        raw, {"revision", "cards", "unknown_contents", "costs"}, {"revision", "cards", "unknown_contents"}
    )
    if type(raw["revision"]) is not int or raw["revision"] != value["revision"]:
        raise collection.Conflict("Lot review changed; reload before correcting")
    cards = raw["cards"]
    if not isinstance(cards, list) or len(cards) > MAX_ITEMS:
        raise ValueError("At most 200 distinct printing corrections")
    entries = {p["id"] for p in _catalog(actor)}
    seen = set()
    for card in cards:
        shopping.fields(
            card,
            {"printing_id", "quantity", "condition", "grade", "grader", "language", "edition", "finish"},
            {"printing_id", "quantity"},
        )
        if card["printing_id"] not in entries or card["printing_id"] in seen:
            raise ValueError("Choose distinct published Pokémon printings")
        seen.add(card["printing_id"])
        shopping.math.quantity(card["quantity"])
        for field in ("condition", "grade", "grader", "language", "edition", "finish"):
            if not isinstance(card.get(field, ""), str) or len(card.get(field, "")) > 100:
                raise ValueError("Use bounded printing attributes")
    unknown = raw["unknown_contents"]
    if unknown is not None and (type(unknown) is not int or not 0 <= unknown <= MAX_QUANTITY):
        raise ValueError("Use a bounded whole unknown remainder or null")
    if sum(c["quantity"] for c in cards) + (unknown or 0) > MAX_QUANTITY:
        raise ValueError("At most 100000 cards per lot review")
    costs = raw.get("costs", {})
    shopping.fields(costs, {"price", "shipping", "tax", "other_costs", "planned_bid"}, set())
    for amount in costs.values():
        if amount != "":
            shopping.math.amount(amount)
    _source(actor, session_key, value["origin"])
    with _lock:
        current = _reviews.get(str(review_id))
        if current is None or current["revision"] != value["revision"]:
            raise collection.Conflict("Lot review changed or expired; reload")
        current["corrections"] = deepcopy(dict(cards=cards, unknown_contents=unknown, costs=costs))
        current["revision"] += 1
    return read(actor, session_key, review_id)


def selected_batch(actor, session_key, run_id, result_ids):
    _selected_ids(result_ids)
    # Batch work shares catalog/reference admission and indexing, without caching
    # those admitted values into a later read or renewing any provider lease.
    generation = collection.generation(actor)
    entries = _catalog(actor)
    context = dict(
        generation=generation,
        entries=entries,
        index=hunter_catalog.IdentityIndex(entries),
        records=lot.retained_records(),
    )
    reviews = []
    try:
        for result_id in result_ids:
            reviews.append(analyze(actor, session_key, run_id, result_id, _context=context))
        for result_id in result_ids:
            _source(actor, session_key, dict(run_id=run_id, result_id=result_id))
        return _bounded_response(dict(reviews=reviews, provider_operations=0))
    except Exception:
        for review in reviews:
            _erase(review["review_id"])
        raise


def detail_intent(actor, session_key, run_id, result_ids):
    """Executable-shape future contract, intentionally incapable of dispatch.

    A future allowance must separately authorize every official getItem and bind
    its shared durable ledger. Reads, corrections and analysis never call this.
    """
    _selected_ids(result_ids, maximum=2)
    from . import hunter_budget

    requests, remaining, allowance = [], [], None
    for result_id in result_ids:
        source = _source(actor, session_key, dict(run_id=run_id, result_id=result_id))
        item_id = source["raw"].get("itemId")
        parsed = listing_details.parse_identifier(item_id)
        if parsed["rest"] is None:
            raise ValueError("Official detail analysis requires an exact REST item and variation ID")
        requests.append(dict(operation="getItem", item_id=item_id, result_id=result_id))
        remaining.append(source["expires_in_seconds"])
        allowance = source.get("_allowance")
    capacity = hunter_budget.remaining_traversal(discovery._owner(actor, session_key)[0], allowance)
    enabled = (
        hunter_budget.is_traversal_allowance(allowance)
        and capacity["detail"] >= len(requests)
        and capacity["lots"] >= len(requests)
        and capacity["total"] >= len(requests)
    )
    return dict(
        enabled=enabled,
        dispatch_allowed=enabled,
        reason="Captured allowance can admit the selected official details; authentication remains checked at execution"
        if enabled
        else "No captured allowance remains for the selected official details",
        intent_grants_capacity=False,
        remaining_capacity=capacity,
        requests=requests,
        maximum_operations=dict(oauth=1, browse=0, detail=len(requests), total=1 + len(requests)),
        original_lease_remaining_seconds=min(remaining),
        lease_renews=False,
        request_seconds=discovery.REQUEST_SECONDS,
        action_seconds=discovery.OVERALL_SECONDS,
        max_response_bytes=2 * 1024 * 1024,
        parser_text_bytes=MAX_TEXT_BYTES,
        ledger_identity=allowance.id if hunter_budget.is_traversal_allowance(allowance) else None,
        stop="Cancel independently, consume uncertain attempts and suppress late publication",
        transfer="Future detail adapter must preserve the earlier of summary and detail creation/expiry",
    )
