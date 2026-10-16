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

from . import discovery as d
from . import discovery_comparison as dc
from . import ebay_hunts, shopping
from . import lot_calculator as lot
from .discovery_transport import ProviderFailure, Transport

# Preserve established service imports while keeping detail projection stateless.
from .listing_details import details as details
from .listing_details import parse_identifier as parse_identifier
from .listing_details import validate_response as validate_response

_reviews = {}


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


async def _acquire(run, credentials, actor=None):
    transport = Transport()
    try:
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
    finally:
        await asyncio.wait_for(transport.close(), timeout=0.5)


def _worker(run, actor, credentials):
    close_old_connections()
    try:
        d.store.verified(actor)
        with run.lock:
            d._check_acquisition(run)
            run.state = "running"
        asyncio.run(_acquire(run, credentials, actor))
    except Exception as exc:
        with run.lock:
            run.raws.clear()
            if run.cancel.is_set():
                if not run.timed_out:
                    run.state = "stopped"
            else:
                run.state = "failed"
                code = f" (HTTP {exc.status})" if isinstance(exc, ProviderFailure) and exc.status else ""
                run.error = (
                    str(exc)
                    if isinstance(exc, ValueError)
                    else f"eBay listing load stopped{code}. No retry was made. Your review remains available."
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
        clues = dict(value["clues"], text=value.pop("match_text"))
        matched = dc._matches(lot.catalog(actor, include_goals=True), clues)[:40]
        single = (
            len(matched) == 1
            and not clues["conflicts"]
            and str(value.get("api_lot_size") or "1") == "1"
            and not re.search(
                r"\b(lot|collection|binder|random|choose|pick|set)\b",
                value["title"].replace(matched[0]["set_name"] if matched else "", ""),
                re.I,
            )
        )
        value["proposals"] = [dict(shopping.identity(p), quantity=1 if single else 0) for p in matched]
        value["unknown_contents"] = 0 if single else value["seller_lot_size"]
        with run.lock:
            if not run.cancel.is_set() and run.state == "complete":
                result["listing"] = value
    return result


def stop(actor, session, key):
    run = d._lookup(actor, session, key)
    if run.operation != "detail":
        raise Http404
    d.stop(actor, session, key)
    return _summary(run)


def review(actor, session, value=None, lease=None):
    owner = d._owner(actor, session)
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
        if not current:
            created = time.monotonic()
            current = (created, None, str(uuid.uuid4()))
            _reviews[owner] = current
            timer = Timer(d.EPHEMERAL_SECONDS, _erase_review, args=(owner, created))
            timer.daemon = True
            timer.start()
        if current[1] and current[1].get("detail_run"):
            origin = d._lookup(actor, session, current[1]["detail_run"])
            if origin.cancel.is_set() or origin.state != "complete":
                _reviews.pop(owner, None)
                raise ValueError(
                    "Loaded details expired or were stopped. Reopen the checker for manual entry."
                )
        return dict(
            review=deepcopy(current[1]),
            lease=current[2],
            expires_in_seconds=max(0, int(d.EPHEMERAL_SECONDS - (time.monotonic() - current[0]))),
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
        },
        {"cards", "currency", "unknown_contents"},
    )
    for key in ("title", "listing_url", "price", "shipping", "tax", "other_costs"):
        if not isinstance(value.get(key, ""), str) or len(value.get(key, "")) > 2048:
            raise ValueError("Use bounded review fields.")
    if not isinstance(value["currency"], str) or not re.fullmatch(r"[A-Z]{3}", value["currency"]):
        raise ValueError("Use a three-letter currency.")
    if value.get("detail_run") is not None:
        uuid.UUID(value["detail_run"])
    unknown = value["unknown_contents"]
    if unknown is not None and (type(unknown) is not int or not 0 <= unknown <= 100000):
        raise ValueError("Unknown contents needs a whole quantity or blank.")
    if not isinstance(value["cards"], list) or len(value["cards"]) > 200:
        raise ValueError("At most 200 card identities.")
    allowed = {p["id"] for p in lot.catalog(actor, include_goals=True)}
    seen = set()
    for row in value["cards"]:
        shopping.fields(
            row,
            {"printing_id", "quantity", "condition", "grade", "grader", "language", "edition", "finish"},
            {"printing_id", "quantity"},
        )
        if row["printing_id"] not in allowed or row["printing_id"] in seen:
            raise ValueError("Choose a distinct supported printing.")
        seen.add(row["printing_id"])
        if type(row["quantity"]) is not int or not 0 <= row["quantity"] <= 100000:
            raise ValueError("Use whole card quantities.")
        for key in ("condition", "grade", "grader", "language", "edition", "finish"):
            if not isinstance(row.get(key, ""), str) or len(row.get(key, "")) > 100:
                raise ValueError("Use bounded card attributes.")
    if sum(r["quantity"] for r in value["cards"]) + (unknown or 0) > 100000:
        raise ValueError("At most 100000 cards in one review.")


def compare(actor, value):
    validate_review(actor, value)
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

    base = dict(cost("price"), price_kind="current_asking_price", source_url=value.get("listing_url") or None)
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
        planned_bid=dict(
            amount=None,
            currency=currency,
            status="unknown",
            date=now.date().isoformat(),
            price_kind="personal_planned_bid",
        ),
        delivery_cost_inputs={
            basis: {key: cost(key) for key in ("shipping", "tax", "other_costs")}
            for basis in shopping.math.BASES
        },
    )
    payload = lot.prepare(
        actor,
        raw,
        now=now,
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
        scenarios=scenarios,
        save_allowed=False,
        note="Temporary review and comparison only; saving and export are unavailable. Dated references are not fresh quotations. Generic grade scenarios do not establish an exact slab match. Unknown contents receive no value.",
    )
