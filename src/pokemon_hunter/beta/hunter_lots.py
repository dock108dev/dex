"""Bounded local seller-content proposals and leased Ungraded lot reviews.

No provider transport or collection writers are used here. Reviews retain only
corrections and an opaque original Hunter origin; every read re-enters that lease
and normal reference admission. Official detail acquisition belongs to
hunter_lot_details and its separate admission limits.
"""

import json
import re
import threading
import time
import uuid
from copy import deepcopy
from datetime import UTC, datetime

from django.http import Http404

from . import (
    collection,
    discovery,
    discovery_matching,
    hunter,
    hunter_catalog,
    hunter_coverage,
    listing_details,
    listing_prices,
    shopping,
    store,
)
from . import discovery_comparison as dc
from . import lot_calculator as lot
from .hunter_lot_parser import MAX_CANDIDATE_BINDINGS as MAX_CANDIDATE_BINDINGS
from .hunter_lot_parser import MAX_CANDIDATES as MAX_CANDIDATES
from .hunter_lot_parser import MAX_ITEMS as MAX_ITEMS
from .hunter_lot_parser import MAX_QUANTITY as MAX_QUANTITY
from .hunter_lot_parser import MAX_SEGMENT_CHARS as MAX_SEGMENT_CHARS
from .hunter_lot_parser import MAX_SEGMENTS as MAX_SEGMENTS
from .hunter_lot_parser import MAX_TEXT_BYTES as MAX_TEXT_BYTES
from .hunter_lot_parser import MAX_TOKENS as MAX_TOKENS
from .hunter_lot_parser import parse as parse

MAX_SELECTED_BATCH = 8
MAX_REVIEWS = 16
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_reviews = {}
_lock = threading.RLock()


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
    price = listing_prices.prices(raw)
    shipping = listing_prices.detail_shipping(raw)
    shipping_amount = shipping["amount"] if shipping["currency"] == "USD" else ""
    minimum = listing_prices.component(raw.get("minimumPriceToBid"))
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
