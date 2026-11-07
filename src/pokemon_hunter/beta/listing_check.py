"""Official identifier-only autofill and temporary account/session reviews.

No seller page fetch, persistence, ownership/goal write or reference acquisition.
Detail workers reuse discovery's token, journal, deadline and Stop machinery.
"""

import asyncio
import re
import threading
import time
import uuid
from copy import deepcopy
from datetime import datetime
from threading import Timer

from django.db import close_old_connections
from django.http import Http404

from pokemon_hunter.parser import extract_count

from . import discovery as d
from . import discovery_comparison as dc
from . import (
    ebay_hunts,
    hunter_lot_parser,
    image_bindings,
    lot_assessment,
    shopping,
    shopping_contents,
    shopping_index,
)
from . import lot_calculator as lot
from .diagnostics import async_closing, failure
from .discovery_search import product_kind
from .discovery_transport import ProviderFailure, Transport

# Preserve established service imports while keeping detail projection stateless.
from .listing_details import details as details
from .listing_details import parse_identifier as parse_identifier
from .listing_details import validate_response as validate_response

_reviews = {}


class AdmissionRefused(ValueError):
    """A local detail rejection before any acquisition worker can dispatch."""


def start(actor, session, identifier, *, auth_session=None):
    parse_identifier(identifier)  # Before configuration, admission or any I/O.
    owner = d._owner(actor, session)
    provider, values = ebay_hunts.configuration()
    credentials = (values.get("EBAY_CLIENT_ID"), values.get("EBAY_CLIENT_SECRET"))
    if provider.environment != "production" or not all(credentials):
        raise ValueError("The saved Production configuration is unavailable.")
    run = d.Run(
        str(uuid.uuid4()),
        owner,
        d.Choices(),
        None,
        [],
        operation="detail",
        identifier=identifier,
        auth_session=auth_session,
    )
    run.counts = {"oauth": 0, "detail": 0, "resolution": 0, "total": 0}
    try:
        _bind_policy(run, actor)
    except ValueError as error:
        raise AdmissionRefused(str(error)) from error
    with d._lock:
        for old in d._runs.values():
            if old.owner == owner and old.operation == "detail" and old.state in {"queued", "running"}:
                old.cancel.set()
                old.raws.clear()
                old.state = "stopped"
        d._runs[run.id] = run
    d._journal(run, "action", "admitted")
    d._arm_deadline(run)
    expiry = Timer(d.EPHEMERAL_SECONDS, d._expire, args=(run.id,))
    expiry.daemon = True
    expiry.start()
    threading.Thread(
        target=_worker, args=(run, actor, credentials), daemon=True, name="dex-listing-check"
    ).start()
    return _summary(run)


def _bind_policy(run, actor):
    """Bind explicit standalone details to the same durable ordinary accounting."""
    from . import hunter_policy

    if not hunter_policy.present(run.owner[0]):
        return
    run.allowance = hunter_policy.current(actor)
    if run.allowance is None:
        raise ValueError("Official details need current Hunter usage settings; no request was sent.")
    hunter_policy.bind(run, actor)

    def admit(stage):
        if stage not in {"oauth", "detail", "resolution"}:
            raise ProviderFailure(stage)
        hunter_policy.check(run)
        hunter_policy.consume(
            run.owner[0],
            run.id,
            "detail" if stage == "resolution" else stage,
            None,
            dispatch_id=f"{stage}:{run.counts['total'] + 1}",
            allowance=run.allowance,
            scope="lots",
        )

    run.admit = admit


async def _acquire(run, credentials, actor=None):
    transport = Transport()
    async with async_closing(transport, "shopping_transport_close_failed"):
        token = await d.access_token(run, transport, credentials, actor)
        stage = "detail" if parse_identifier(run.identifier)["rest"] else "resolution"
        raw = await d._dispatch(
            run, transport, stage, run.deadline, actor=actor, token=token, identifier=run.identifier
        )
        value = details(run.identifier, raw)
        if actor is not None:
            if run.auth_session is not None:
                await asyncio.to_thread(d._authorize, actor, run.auth_session)
            else:
                await asyncio.to_thread(d._authorize, actor)
        with run.lock:
            d._check_acquisition(run)
            run.raws = [value]
            run.acquired_at = time.monotonic()
            run.state = "complete"


def _worker(run, actor, credentials):
    close_old_connections()
    try:
        d.store.verified(actor)
        with run.lock:
            d._check_acquisition(run)
            run.state = "running"
        asyncio.run(_acquire(run, credentials, actor))
    except Exception as exc:
        if not isinstance(exc, d._Stopped):
            failure("shopping_listing_failed", exc)
        with run.lock:
            run.raws.clear()
            if run.cancel.is_set():
                if not run.timed_out:
                    run.state = "stopped"
            else:
                run.state = "failed"
                code = f" (HTTP {exc.status})" if isinstance(exc, ProviderFailure) and exc.status else ""
                run.error = (
                    f"eBay listing load stopped{code}. No retry was made. Your review remains available."
                )
    finally:
        close_old_connections()


def _summary(run):
    d._acquisition_timeout(run)
    return dict(
        run_id=run.id,
        state=run.state,
        running=run.state in {"queued", "running"},
        error=run.error,
        counts=dict(run.counts),
        expires_in_seconds=max(0, int(d.EPHEMERAL_SECONDS - (time.monotonic() - run.created))),
    )


def status(actor, session, key):
    run = d._lookup(actor, session, key)
    if run.operation != "detail":
        raise Http404
    with run.lock:
        result = _summary(run)
        value = (
            deepcopy(run.raws[0])
            if run.state == "complete" and not run.cancel.is_set() and run.raws
            else None
        )
    if value:
        value = _proposals(actor, value)
        # Complete alternatives already live in contents; parser candidates are
        # operation-local working data, not a second browser payload.
        value.get("seller_contents", {}).pop("proposals", None)
        # The projection cannot extend the original detail lease. Reauthorize
        # before publishing even if the expiry timer has not fired yet.
        if d._lookup(actor, session, key) is not run:
            raise Http404
        with run.lock:
            if not run.cancel.is_set() and run.state == "complete":
                result["listing"] = value
    return result


@shopping_index.indexed
def _proposals(actor, value, *, summary=None):
    official = value.get("_contents_kind") == "official_detail"
    clues = dict(value["clues"], text=value.pop("match_text"))
    indexed = shopping_index.current(actor)
    entries = (
        indexed.proposals(
            hunter_lot_parser.catalog_text(
                summary or value.get("_contents_source", {}),
                value.get("_contents_source") if value.get("_contents_kind") == "official_detail" else None,
            )
        )
        if indexed
        else lot.catalog(actor, include_goals=True, include_current=True)
    )
    matched = dc._matches(entries, clues)
    single = (
        len(matched) == 1
        and not clues["conflicts"]
        and product_kind(clues["text"]) == "single"
        and extract_count(clues["text"]).denominator in (None, 1)
        and value.get("seller_lot_size") in (None, 1)
        and str(value.get("api_lot_size") or "1") == "1"
        and not re.search(
            r"\b(lot|collection|binder|random|choose|pick|set)\b",
            value["title"].replace(matched[0]["set_name"] if matched else "", ""),
            re.I,
        )
    )
    artwork = image_bindings.catalog_images(actor, matched) if single else {}
    value["proposals"] = [
        dict(shopping.identity(p), quantity=0, artwork=artwork.get(p["id"])) for p in matched
    ]
    value["unknown_contents"] = value["seller_lot_size"]
    value["contents"] = shopping_contents.project(value, entries, summary=summary)
    if official:
        _selected_contents(value)
    return value


def _selected_contents(value):
    """Apply the same evidence-selected quantities to either official-detail path."""
    parsed = value["seller_contents"]
    selected = {p["printing_id"]: p for p in parsed["proposals"] if p["included_quantity"]}
    entries = {p["id"]: p for group in parsed["proposals"] for p in group["candidates"]}
    unresolved = [dict(p, quantity=0) for p in value.get("proposals", []) if p["id"] not in selected]
    value["proposals"] = [
        dict(
            entries[pid],
            quantity=p["included_quantity"],
            **{k: p["clues"].get(k) for k in ("condition", "grade", "grader")},
        )
        for pid, p in selected.items()
    ] + unresolved
    value["unknown_contents"] = parsed["unknown_remainder"]


@shopping_index.indexed
def catalog(actor, query="", restore=None):
    """Bounded local identities and checked card references, without source values."""
    if restore is not None and len(restore) > 200:
        raise ValueError("Restore at most 200 identities")
    indexed = shopping_index.current(actor)
    if indexed and restore is None:
        entries, total = shopping_contents.search(indexed, query)
        artwork = image_bindings.catalog_images(actor, entries) if entries else {}
        return dict(
            cards=[dict(shopping.identity(p), artwork=artwork.get(p["id"])) for p in entries], total=total
        )
    entries = (
        indexed.supported(indexed.printings(restore))
        if indexed and restore is not None
        else lot.catalog(actor, query, include_goals=True, include_current=True, printing_ids=restore)
    )
    total, entries = len(entries), entries[: 200 if restore is not None else 40]
    artwork = image_bindings.catalog_images(actor, entries) if entries else {}
    return dict(
        cards=[dict(shopping.identity(p), artwork=artwork.get(p["id"])) for p in entries], total=total
    )


def _context(source, actor=None, review=None):
    selected = source.get("selected_target")
    from . import shopping_intent

    fit = (
        shopping_intent.fit(actor, source["choices"], source["raw"].get("title", ""), review)
        if actor and source["choices"].get("collection_intent")
        else None
    )
    return dict(
        collection_fit=fit,
        choices=source["choices"],
        scope=d.goal_hunts.public(source["scope"]),
        scope_label=source.get("scope_label")
        or (
            "Find deals · owned cards included"
            if source["choices"].get("intent") == "deals"
            else "Current collection · Original 151 · missing species"
        ),
        selected_target=selected,
    )


@shopping_index.indexed
def candidate(actor, session, run_id, result_id):
    """Project an eligible selected summary; entering review never loads details."""
    source = d.review_candidate(actor, session, run_id, result_id)
    raw = source.get("detail") or source["raw"]
    value = _proposals(
        actor,
        details(raw.get("itemId"), raw, source_kind="official_detail" if source.get("detail") else "summary"),
        summary=source.get("summary"),
    )
    automatic = source.get("detail") is not None
    suggestions = source.get("result", {}).get("identity_candidates") or []
    ids = list(dict.fromkeys(row.get("printing_id") for row in suggestions if row.get("printing_id")))
    strict_ids = {row["id"] for row in value["proposals"]}
    if ids and not automatic:
        checked = catalog(actor, restore=ids)["cards"]
        strict = {row["id"]: row for row in value["proposals"]}
        value["proposals"] = [
            dict(row, quantity=strict.get(row["id"], {}).get("quantity", 0)) for row in checked
        ]
        value["proposals"] += [row for row in strict.values() if row["id"] not in ids]
    selected_child = source["choices"].get("printing_id")
    scope_differs = bool(ids) and set(ids) != strict_ids
    selected_differs = selected_child and any(row["id"] != selected_child for row in value["proposals"])
    if not automatic and (
        source.get("result", {}).get("discovery_kind") == "mixed_lot" or scope_differs or selected_differs
    ):
        for proposal in value["proposals"]:
            proposal["quantity"] = 0
        value["unknown_contents"] = value["seller_lot_size"]
    # Automatic selection above consumes the parsed proposals before this
    # duplicate candidate graph is removed. Keep every public contents choice.
    value.get("seller_contents", {}).pop("proposals", None)
    value["discovery_origin"] = dict(run_id=run_id, result_id=result_id)
    restore_ids = list(
        dict.fromkeys(
            [p["id"] for p in value["proposals"]]
            + [p["id"] for entry in value["contents"] for p in entry["candidates"]]
        )
    )
    # Reuse the current admitted index for a small optional restore projection,
    # including the ordinary checked artwork descriptors. Large families remain
    # complete above and use the existing bounded catalog restore on the client.
    restore_cards = catalog(actor, restore=restore_ids)["cards"] if 0 < len(restore_ids) <= 40 else []
    # Recheck the source after image/catalog projection so Stop cannot publish
    # a summary whose original lease ended while local work was running.
    current_source = d.review_candidate(actor, session, run_id, result_id)
    if any(current_source.get(k) != source.get(k) for k in ("raw", "detail", "content_revision", "created")):
        raise ValueError("Listing evidence changed during review; reopen the current assessment")
    return dict(
        listing=value,
        restore_cards=restore_cards,
        expires_in_seconds=source["expires_in_seconds"],
        context=_context(source, actor),
    )


def stop(actor, session, key):
    run = d._lookup(actor, session, key)
    if run.operation != "detail":
        raise Http404
    d.stop(actor, session, key)
    return _summary(run)


@shopping_index.indexed
def review(actor, session, value=None, lease=None):
    owner = d._owner(actor, session)
    context = None
    with d._lock:
        current = _reviews.get(owner)
        if current and time.monotonic() - current[0] >= d.EPHEMERAL_SECONDS:
            _reviews.pop(owner, None)
            current = None
        if value is not None:
            if not current or lease != current[2]:
                raise ValueError(
                    "This temporary review expired. Reopen Check a listing/lot; expired details cannot be retained again."
                )
            validate_review(actor, value)
            origin = value.get("detail_run")
            if origin:
                detail = d._lookup(actor, session, origin)
                with detail.lock:
                    if detail.operation != "detail" or detail.state != "complete" or detail.cancel.is_set():
                        raise ValueError(
                            "Loaded details are no longer available. Your current edits remain on screen."
                        )
                    created = min(current[0], detail.created)
            else:
                created = current[0]
            if value.get("discovery_origin"):
                source = d.review_candidate(actor, session, **value["discovery_origin"])
                created = min(created, source["created"])
                context = _context(source, actor, value)
            if time.monotonic() - created >= d.EPHEMERAL_SECONDS:
                raise ValueError("This temporary review expired. Your edits remain on screen.")
            previous_created = current[0]
            _reviews[owner] = (created, deepcopy(value), current[2])
            if created < previous_created:
                timer = Timer(
                    max(0, created + d.EPHEMERAL_SECONDS - time.monotonic()),
                    _erase_review,
                    args=(owner, created),
                )
                timer.daemon = True
                timer.start()
            current = _reviews[owner]
        if lease is not None and (not current or current[2] != lease):
            raise ValueError("The original review lease is unavailable.")
        if not current:
            created = time.monotonic()
            current = (created, None, str(uuid.uuid4()))
            _reviews[owner] = current
            timer = Timer(d.EPHEMERAL_SECONDS, _erase_review, args=(owner, created))
            timer.daemon = True
            timer.start()
        if current[1] and current[1].get("detail_run"):
            try:
                origin = d._lookup(actor, session, current[1]["detail_run"])
            except Http404:
                _reviews.pop(owner, None)
                raise
            if origin.cancel.is_set() or origin.state != "complete":
                _reviews.pop(owner, None)
                raise ValueError(
                    "Loaded details expired or were stopped. Reopen the checker for manual entry."
                )
        if current[1] and current[1].get("discovery_origin") and context is None:
            try:
                context = _context(
                    d.review_candidate(actor, session, **current[1]["discovery_origin"]), actor, current[1]
                )
            except (Http404, ValueError):
                _reviews.pop(owner, None)
                raise ValueError(
                    "The temporary offer expired or was stopped. Reopen Shopping to continue."
                ) from None
        return dict(
            review=deepcopy(current[1]),
            revision=shopping.digest(current[1]),
            lease=current[2],
            expires_in_seconds=max(0, int(d.EPHEMERAL_SECONDS - (time.monotonic() - current[0]))),
            context=context,
        )


def _erase_review(owner, created):
    with d._lock:
        current = _reviews.get(owner)
        if current and current[0] <= created:
            _reviews.pop(owner, None)


def validate_review(actor, value):
    shopping.fields(
        value,
        {
            "title",
            "listing_url",
            "price",
            "shipping",
            "tax",
            "other_costs",
            "currency",
            "unknown_contents",
            "cards",
            "detail_run",
            "discovery_origin",
            "price_kind",
            "budget",
            "tax_rate",
            "planned_bid",
            "buy_now_price",
            "buy_now_currency",
            "seller_card_count",
            "lot_units",
            "stock_quantity",
            "remainder_auto",
            "contents",
            "authored_fields",
        },
        {"cards", "currency", "unknown_contents"},
    )
    shopping_contents.check_authored(
        value,
        {
            "title",
            "listing_url",
            "price",
            "currency",
            "shipping",
            "tax",
            "other_costs",
            "budget",
            "tax_rate",
            "planned_bid",
            "unknown_contents",
            "price_kind",
        },
    )
    shopping_contents.validate(value.get("contents", []))
    for key in (
        "title",
        "listing_url",
        "price",
        "shipping",
        "tax",
        "other_costs",
        "budget",
        "tax_rate",
        "planned_bid",
        "buy_now_price",
    ):
        if not isinstance(value.get(key, ""), str) or len(value.get(key, "")) > 2048:
            raise ValueError("Use bounded review fields.")
    for key in ("budget", "tax_rate"):
        if value.get(key):
            shopping.math.amount(value[key])
    if value.get("tax_rate") and (value.get("tax") or shopping.math.amount(value["tax_rate"]) > 100):
        raise ValueError("Choose either fixed tax or a rate on bid plus shipping up to 100%.")
    if not isinstance(value["currency"], str) or not re.fullmatch(r"[A-Z]{3}", value["currency"]):
        raise ValueError("Use a three-letter currency.")
    if value.get("detail_run") is not None:
        uuid.UUID(value["detail_run"])
    if value.get("discovery_origin") is not None:
        origin = value["discovery_origin"]
        shopping.fields(origin, {"run_id", "result_id"}, {"run_id", "result_id"})
        uuid.UUID(origin["run_id"])
        if not isinstance(origin["result_id"], str) or not re.fullmatch(
            r"[A-Za-z0-9_-]{1,160}", origin["result_id"]
        ):
            raise ValueError("Choose a checked temporary offer.")
    if value.get("price_kind", "current_asking_price") not in {"current_bid", "current_asking_price"}:
        raise ValueError("Choose current bid or asking price.")
    if value.get("buy_now_currency") and not re.fullmatch(r"[A-Z]{3}", value["buy_now_currency"]):
        raise ValueError("Use a three-letter buy-now currency.")
    for key in ("seller_card_count", "lot_units", "stock_quantity"):
        if value.get(key) is not None and (type(value[key]) is not int or not 0 <= value[key] <= 1000000):
            raise ValueError("Use bounded whole listing quantities.")
    if "remainder_auto" in value and type(value["remainder_auto"]) is not bool:
        raise ValueError("Choose whether the remainder follows the stated card count.")
    unknown = value["unknown_contents"]
    if unknown is not None and (type(unknown) is not int or not 0 <= unknown <= 100000):
        raise ValueError("Unknown contents needs a whole quantity or blank.")
    if not isinstance(value["cards"], list) or len(value["cards"]) > 200:
        raise ValueError("At most 200 card identities.")
    seen = set()
    for row in value["cards"]:
        shopping.fields(
            row,
            {
                "printing_id",
                "quantity",
                "condition",
                "grade",
                "grader",
                "language",
                "edition",
                "finish",
                "authored_fields",
            },
            {"printing_id", "quantity"},
        )
        shopping_contents.check_authored(
            row, {"quantity", "condition", "grade", "grader", "language", "edition", "finish"}
        )
        if not isinstance(row["printing_id"], str) or row["printing_id"] in seen:
            raise ValueError("Choose a distinct supported printing.")
        seen.add(row["printing_id"])
        if type(row["quantity"]) is not int or not 0 <= row["quantity"] <= 100000:
            raise ValueError("Use whole card quantities.")
        for key in ("condition", "grade", "grader", "language", "edition", "finish"):
            if not isinstance(row.get(key, ""), str) or len(row.get(key, "")) > 100:
                raise ValueError("Use bounded card attributes.")
    if sum(r["quantity"] for r in value["cards"]) + (unknown or 0) > 100000:
        raise ValueError("At most 100000 cards in one review.")
    indexed = shopping_index.current(actor)
    selected = (
        indexed.supported(indexed.printings(seen))
        if indexed
        else lot.catalog(actor, include_goals=True, include_current=True, printing_ids=seen)
    )
    allowed = {p["id"] for p in selected}
    if seen - allowed:
        raise ValueError("Choose a distinct supported printing.")

    return selected


@shopping_index.indexed
def saved_comparison(actor, session, revision, lease):
    owner = d._owner(actor, session)

    def checked():
        with d._lock:
            current = _reviews.get(owner)
            if (
                not current
                or current[2] != lease
                or current[1] is None
                or shopping.digest(current[1]) != revision
                or time.monotonic() >= current[0] + d.EPHEMERAL_SECONDS
            ):
                raise ValueError("Review changed or expired. Reopen the current review.")
            value = current[1]
            offers = []
            origin = value.get("discovery_origin")
            if origin:
                run = d._lookup_owned(owner, origin["run_id"])
                with run.lock:
                    source = d._summary_lease(run, origin["result_id"])
                    raw = source.get("detail") or source["raw"]
                offers.append(
                    dict(
                        details(
                            raw.get("itemId"),
                            raw,
                            source_kind="official_detail" if source.get("detail") else "summary",
                        ),
                        _content_revision=source.get("content_revision"),
                    )
                )
            if value.get("detail_run"):
                run = d._lookup_owned(owner, value["detail_run"])
                with run.lock:
                    if (
                        run.operation != "detail"
                        or run.state != "complete"
                        or run.cancel.is_set()
                        or not run.raws
                    ):
                        raise ValueError("Listing details expired or stopped.")
                    offers.append(deepcopy(run.raws[0]))
            if len({offer["item_id"] for offer in offers}) > 1:
                raise ValueError("Summary and details refer to different offers.")
            for offer in offers:
                if offer["price_kind"] != value.get("price_kind"):
                    raise ValueError("Offer type differs from the selected listing.")
                if offer.get("ends_at") and datetime.fromisoformat(offer["ends_at"]) <= datetime.now(
                    shopping.TZ
                ):
                    raise ValueError("This listing has ended.")
            return value, offers

    value, offers = checked()
    if value.get("discovery_origin"):
        run = d._lookup_owned(owner, value["discovery_origin"]["run_id"])
        d._context_current(actor, run.choices)
    reference_checks = []
    result = compare(actor, value, offers=offers, _checks=reference_checks)
    result["assessment"]["seller_url"] = offers[-1]["item_url"] if offers else None
    result["assessment"]["ends_at"] = min((o["ends_at"] for o in offers if o.get("ends_at")), default=None)

    def publish():
        for check in reference_checks:
            check()
        references = result["assessment"]["evidence"]
        if result["assessment"]["maximum"] is not None or any(r["snapshot_version"] for r in references):
            with lot.price_snapshots.selected(
                (r["printing_id"] for r in value["cards"]), eligible_on=datetime.now(shopping.TZ).date()
            ):
                active, status = lot.price_snapshots.display_current()
            allowed = {
                (r["_snapshot_version"], r["_contract_sha256"], r["printing_id"], r["grade"], r["grader"])
                for r in active
            }
            if status == "invalid_snapshot" or any(
                (
                    r["snapshot_version"],
                    item["source_contract"],
                    r["printing_id"],
                    item["grade"],
                    item["grader"],
                )
                not in allowed
                for r in references
                if r["snapshot_version"]
                for item in (r, *r["conflicts"])
            ):
                raise ValueError("A reference expired, changed or was withdrawn. Compare again.")
        if checked()[1] != offers:
            raise ValueError("Offer changed during comparison. Compare again.")

    indexed = shopping_index.current(actor)
    if indexed:
        indexed.publication_checks.append(publish)
    else:
        d.store.verified(actor)
        publish()
    return result


def compare(actor, value, *, offers=(), _checks=None):
    selected = validate_review(actor, value)
    now = datetime.now(shopping.TZ)
    currency = value["currency"]

    def cost(key):
        amount = value.get(key) or None
        return dict(
            amount=amount,
            currency=currency,
            status="known" if amount else "unknown",
            date=now.date().isoformat(),
        )

    base = dict(
        cost("price"),
        price_kind=value.get("price_kind", "current_asking_price"),
        source_url=value.get("listing_url") or None,
    )
    raw = dict(
        cards=[
            dict(
                printing_id=r["printing_id"],
                quantity=r["quantity"],
                values={g: dict(mode="guide") for g in lot.COLUMNS},
            )
            for r in value["cards"]
            if r["quantity"]
        ],
        listing_observation=base,
        planned_bid=dict(cost("planned_bid"), price_kind="personal_planned_bid"),
        delivery_cost_inputs={
            basis: {key: cost(key) for key in ("shipping", "tax", "other_costs")}
            for basis in shopping.math.BASES
        },
    )
    if value.get("tax_rate") and value.get("shipping"):
        for basis in shopping.math.BASES:
            if raw[basis]["amount"] is not None:
                tax = lot_assessment.tax_due(
                    *(
                        shopping.math.amount(v)
                        for v in (raw[basis]["amount"], value["shipping"], value["tax_rate"])
                    )
                )
                raw["delivery_cost_inputs"][basis]["tax"].update(amount=str(tax), status="known")
    with lot.price_snapshots.selected(p["id"] for p in selected):
        records = lot.retained_records()
    from .read_diagnostics import phase

    # Seller evidence needs numbered parents and sibling variants as well as
    # the selected children. The selected cost/reference rows remain unchanged.
    evidence_entries = selected
    if offers and offers[-1].get("_contents_source"):
        source = offers[-1]["_contents_source"]
        indexed = shopping_index.current(actor)
        evidence_entries = (
            indexed.proposals(hunter_lot_parser.catalog_text(source, source))
            if indexed
            else lot.catalog(actor, include_goals=True, include_current=True)
        )
    with phase("composition_ms"):
        result = _assessed(
            actor, value, selected, raw, records, now, offers, evidence_entries=evidence_entries
        )
    # Keep the strict tax-aware assessment/ceiling intact. The same automatic
    # benchmark engine also consumes explicitly corrected physical selections.
    if offers and offers[-1].get("_contents_source"):
        from . import hunter_lots

        source = offers[-1]["_contents_source"]
        proposal = hunter_lot_parser.parse(source, evidence_entries, detail=source)
        corrections = dict(
            cards=[
                {
                    k: v
                    for k, v in card.items()
                    if k in {"printing_id", "quantity", *card.get("authored_fields", [])}
                }
                for card in value["cards"]
                if card["quantity"]
            ],
            unknown_contents=value["unknown_contents"],
        )
        try:
            _, result["benchmark"] = hunter_lots._compare(
                actor, source, proposal, corrections, selected, records, _checks=_checks
            )
        except ValueError as error:
            result["benchmark"] = dict(assessment_version="dex-lot-value-v3", unavailable=str(error))
    return result


def _assessed(actor, value, selected, raw, records, now, offers, *, evidence_entries=None):
    payload = lot.prepare(
        actor,
        raw,
        now=now,
        catalog_entries=selected,
        reference_records=records,
        review_traits={r["printing_id"]: r for r in value["cards"]},
        unknown_quantity=value["unknown_contents"],
    )
    # Temporary comparison only: no raw records or save payload leave this service.
    scenarios = {}
    for g, scenario in payload["scenarios"].items():
        scenarios[g] = dict(
            result=scenario["result"], references=[dc._reference(r) for r in scenario["references"]]
        )
    return dict(
        assessment=lot_assessment.assess(
            value,
            {p["id"]: p for p in (evidence_entries if evidence_entries is not None else selected)},
            records,
            now.date(),
            scenarios["raw"]["result"]["comparisons"],
            offers,
            raw,
        ),
        scenarios=scenarios,
        save_allowed=False,
        note="Temporary review and comparison only; saving and export are unavailable. Dated references are not fresh quotations or a maximum bid. Current bids and planned manual bids are not final purchase costs. Generic grade scenarios do not establish an exact slab match. Unknown contents receive no value.",
    )
