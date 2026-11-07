"""One explicit, bounded Hunt: discovery, seller details, existing local assessment.

Provider content lives only in the original account/session lease. The progress
journal is noncontent; ordinary Hunter policy remains the sole debit authority.
No model, photo, reference acquisition, continuation or automatic provider retry.
"""

import asyncio
import fcntl
import hashlib
import json
import os
import re
import threading
import time
from copy import deepcopy
from datetime import UTC, datetime, timedelta

from django.db import close_old_connections
from django.http import Http404

from . import discovery as d
from . import (
    discovery_listing,
    discovery_lot_values,
    discovery_paging,
    hunter_policy,
    listing_details,
    listing_prices,
    read_diagnostics,
    shopping_index,
)
from . import lot_hunt_contract as contract
from . import lot_hunt_journal as journal
from .diagnostics import async_closing, failure
from .discovery_transport import ProviderFailure, Transport

RUNNING = journal.ACTIVE
ERASED = {"stopped", "expired", "conflict", "unauthorized", "restart_uncertain"}
_runs = {}
_lock = threading.RLock()


class AdmissionUnavailable(ValueError):
    MESSAGES = {
        "lot_hunt_policy": "Automatic Hunt is unavailable. Open Hunter usage settings and select current limits first.",
        "lot_hunt_capacity": "Automatic Hunt needs five remaining shared operations and two detail slots. Check Hunter usage settings; no requests were sent.",
    }

    def __init__(self, code):
        self.code = code
        super().__init__(self.MESSAGES[code])


class Halt(Exception):
    def __init__(self, state, reason):
        self.state, self.reason = state, reason


@shopping_index.indexed
def _revision(actor):
    indexed = shopping_index.current(actor)
    if indexed:
        data = (indexed.build, indexed.state)
    else:
        from . import collection, hunter_lots

        data = (collection.generation(actor), hunter_lots._catalog(actor))
    return {"binding": hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()}


def _guard(run, actor, *, acquiring=True):
    if run.cancel.is_set():
        raise Halt(run.state if run.state in ERASED else "stopped", "Hunt stopped")
    if time.monotonic() >= run.created + contract.LEASE_SECONDS:
        raise Halt("expired", "Original seller-content lease expired")
    if acquiring and time.monotonic() >= run.deadline:
        raise Halt("exhausted", "Hunt deadline reached; no late publication")
    d._authorize(actor, run.auth_session)
    hunter_policy.check(run)
    d._context_current(actor, run.choices)
    if _revision(actor)["binding"] != run.binding:
        raise Halt("conflict", "Account or catalog revision changed; start a new Hunt explicitly")


def _reason(run, reason):
    run.reasons[reason] = run.reasons.get(reason, 0) + 1


def _progress(run, state=None):
    with run.lock:
        if state:
            if run.state not in RUNNING:
                raise Halt(run.state, "Job already terminated")
            run.state = state
        run.progress["unprocessed"] = max(0, run.progress["eligible"] - run.progress["assessed"])
        journal.record(run)


def _finish(run, state, reason=None, *, erase=False):
    with run.lock:
        # Stop/expiry wins over every late success/failure path.
        if run.state in ERASED or (run.state not in RUNNING and state not in ERASED):
            state = run.state
        run.state, run.error = state, reason
        if erase or state in ERASED:
            run.cancel.set()
            run.raws.clear()
            run.details.clear()
            run.summaries.clear()
            run.assessed.clear()
            run.observations.clear()
            run.content_revision += 1
        _progress(run)


def _summary(run):
    return dict(
        contract=contract.CONTRACT,
        run_id=run.id,
        state=run.state,
        running=run.state in RUNNING,
        counts=dict(run.counts),
        progress=dict(run.progress),
        reasons=dict(run.reasons),
        content_revision=run.content_revision,
        choices=run.choices.model_dump(mode="json"),
        scope_label=d._scope_label(run),
        results=[],
        has_next=False,
        values_checked=True,
        expires_in_seconds=max(0, int(run.created + contract.LEASE_SECONDS - time.monotonic())),
        limits=dict(contract.LIMITS),
        response_bytes=run.bytes.used,
        aggregate_byte_limit=contract.AGGREGATE_BYTES,
        error=run.error,
        note="Bounded Hunt: one BIN page, one auction page, at most two detail candidates. Seller-stated contents; partial marketplace coverage. References are not refreshed.",
    )


def _recovered(owner, key):
    row = journal.read(owner, key)
    if row["state"] in RUNNING:
        row.update(state="restart_uncertain", reason="Worker state is unavailable; no requests were replayed")
    return dict(
        contract=contract.CONTRACT,
        run_id=key,
        state=row["state"],
        running=False,
        counts=row["counts"],
        progress=row["progress"],
        reasons=row["reasons"],
        content_revision=row["content_revision"],
        results=[],
        has_next=False,
        values_checked=True,
        expires_in_seconds=0,
        error=row["reason"],
        content_available=False,
        note="Original accounting retained. Temporary results cannot be restored; no replay is permitted.",
    )


def owns(actor, session, key):
    owner = d._owner(actor, session)
    with d._lock:
        existing = d._runs.get(str(key))
    if existing is not None and existing.operation != "lot_hunt":
        return False
    try:
        journal.read(owner, str(key))
    except (Http404, FileNotFoundError):
        return False
    return True


def _lookup(actor, session, key):
    owner = d._owner(actor, session)
    with _lock:
        run = _runs.get(str(key))
    if run is not None and run.owner != owner:
        raise Http404
    return run, owner


def _admit(run, stage):
    # Called inside discovery's send lock, before it schedules the request.
    if stage not in contract.LIMITS or stage == "resolution":
        raise ProviderFailure(stage)
    hunter_policy.check(run)
    hunter_policy.consume(
        run.owner[0],
        run.id,
        stage,
        run.lane if stage == "browse" else None,
        dispatch_id=run.dispatch_id,
        allowance=run.allowance,
        scope="lots",
    )
    journal.record(run, reserved=stage)


def _acquisition_check(run):
    from .hunter_profile import check_dispatch

    check_dispatch(run)
    if run.state not in RUNNING:
        raise Halt(run.state, "Job already terminated")
    if run.cancel.is_set():
        raise d._Stopped
    if time.monotonic() >= run.deadline:
        raise Halt("exhausted", "Hunt deadline reached")
    if run.bytes.used > contract.AGGREGATE_BYTES:
        raise Halt("exhausted", "Aggregate response byte limit reached")
    hunter_policy.check(run)


def _launch(run, actor, credentials):
    threading.Thread(target=_worker, args=(run, actor, credentials), daemon=True, name="dex-lot-hunt").start()
    timer = threading.Timer(
        max(0, run.created + contract.LEASE_SECONDS - time.monotonic()), _expire, args=(run,)
    )
    timer.daemon = True
    timer.start()
    deadline = threading.Timer(max(0, run.deadline - time.monotonic()), _deadline, args=(run,))
    deadline.daemon = True
    deadline.start()


def _deadline(run):
    with run.lock:
        if run.state in RUNNING:
            _finish(run, "exhausted", "Hunt deadline reached; no late publication")


def _expire(run):
    _finish(run, "expired", "Original seller-content lease expired", erase=True)


@shopping_index.indexed
def _admission_context(actor, choices):
    d._context_current(actor, choices)
    scope = d.goal_hunts.snapshot(actor, choices.goal_id)
    set_name = None
    if choices.set_id:
        sets = d._sets(actor)
        set_name = sets.get(choices.set_id) or next((v for v in sets.values() if v == choices.set_id), None)
        if set_name is None:
            raise ValueError("Choose an available set")
    return dict(scope=scope, set_name=set_name, binding=_revision(actor)["binding"])


def start(actor, session, raw, request_id, *, auth_session=None):
    owner = d._owner(actor, session)
    if not isinstance(raw, dict) or raw.get("acquisition_contract") != contract.CONTRACT:
        raise ValueError("Choose the bounded automatic Hunt contract explicitly")
    choices = d.Choices.model_validate({k: v for k, v in raw.items() if k != "acquisition_contract"})
    if choices.product_type != "mixed_lots" or choices.browse_requests != 1:
        raise ValueError("Automatic Hunt has two fixed lanes; no client request limits or continuation")
    if choices.intent == "deals" and choices.goal_id:
        raise ValueError("Use missing-card scope for a frozen goal")
    with read_diagnostics.phase("hunt_context_ms"):
        prepared = _admission_context(actor, choices)
    scope = prepared["scope"]
    if choices.collection_intent:
        from .canonical_species import registry

        choices.query = registry()[choices.species]["name"]
    if not choices.query:
        raise ValueError("Enter a Pokémon or card name")
    with read_diagnostics.phase("hunt_policy_ms"):
        allowance, capacity = hunter_policy.admission(actor, root=owner[0])
    if allowance is None:
        raise AdmissionUnavailable("lot_hunt_policy")
    # Reserve headroom for both lanes and both detail slots even with a warm token.
    if any(capacity[k] < v for k, v in dict(total=5, browse=2, detail=2, lots=4).items()):
        raise AdmissionUnavailable("lot_hunt_capacity")
    provider, values = d.ebay_hunts.configuration()
    credentials = (values.get("EBAY_CLIENT_ID"), values.get("EBAY_CLIENT_SECRET"))
    if provider.environment != "production" or not all(credentials):
        raise ValueError("Saved Production configuration is unavailable")
    set_name = prepared["set_name"]
    page = discovery_paging.first_pages(choices.query, "mixed_lots", "ending_soonest", set_name=set_name)[0]
    run = d.Run(
        journal.run_id(owner, request_id),
        owner,
        choices,
        scope,
        [],
        operation="lot_hunt",
        auth_session=auth_session,
    )
    run.deadline = run.created + contract.JOB_SECONDS
    run.request_seconds = contract.REQUEST_SECONDS
    run.expires_at = (datetime.now(UTC) + timedelta(seconds=contract.LEASE_SECONDS)).isoformat()
    run.binding = prepared["binding"]
    run.allowance = allowance
    run.content_revision = 0
    run.counts = dict.fromkeys((*contract.LIMITS, "summary_count"), 0)
    run.progress = dict.fromkeys(
        (
            "searched",
            "received",
            "unique",
            "eligible",
            "enriched",
            "assessed",
            "ready",
            "partial",
            "unprocessed",
        ),
        0,
    )
    run.reasons, run.details, run.summaries, run.assessed = {}, {}, {}, set()
    run.observations = {}
    run.bytes = contract.ByteBudget()
    run.destination = getattr(provider, "delivery_postal_code", None) or None
    if run.destination is not None and not re.fullmatch(r"[0-9]{5}(?:-[0-9]{4})?", run.destination):
        raise ValueError("Configured US shipping destination is invalid")
    run.pages = tuple(contract.Page(page, lane, datetime.now(UTC).isoformat()) for lane in contract.LANES)
    run.lane, run.dispatch_id = None, "oauth"
    run.admit = lambda stage: _admit(run, stage)
    run.acquisition_check = lambda: _acquisition_check(run)
    with read_diagnostics.phase("hunt_journal_ms"):
        journal.record(run, initial=True)
    with _lock:
        _runs[run.id] = run
    try:
        with read_diagnostics.phase("hunt_bind_ms"):
            hunter_policy.bind(run, actor)
    except Exception:
        _finish(run, "failed", "Policy capture failed; no requests sent")
        raise
    # Existing review/summary lease APIs keep working on the same parent.
    with d._lock:
        d._runs[run.id] = run
    result = _summary(run)
    with read_diagnostics.phase("hunt_launch_ms"):
        _launch(run, actor, credentials)
    return result


async def _send(run, actor, transport, stage, **kwargs):
    await asyncio.to_thread(_guard, run, actor)
    if run.bytes.used >= contract.AGGREGATE_BYTES:
        raise Halt("exhausted", "Aggregate response byte limit reached")
    capacity = await asyncio.to_thread(hunter_policy.remaining, run.owner[0], run.allowance)
    if capacity.get(stage, 0) < 1 or capacity["total"] < 1:
        raise Halt("exhausted", "Captured shared request capacity is exhausted")
    value = await d._dispatch(run, transport, stage, run.deadline, actor=actor, **kwargs)
    await asyncio.to_thread(_guard, run, actor)
    return value


class MeteredTransport:
    def __init__(self, run):
        self.transport, self.run = Transport(), run

    async def request(self, stage, **kwargs):
        return await self.transport.request(
            stage, byte_budget=self.run.bytes, destination=self.run.destination, **kwargs
        )

    async def close(self):
        await self.transport.close()


def _received(run, page, body):
    rows = body.get("itemSummaries", [])
    if not isinstance(rows, list) or len(rows) > 20 or any(not isinstance(r, dict) for r in rows):
        raise ProviderFailure("browse")
    with run.lock:
        _acquisition_check(run)
        run.progress["searched"] += 1
        run.progress["received"] += len(rows)
        run.counts["summary_count"] += len(rows)
        for raw in rows:
            try:
                key = contract.identity(raw)
            except ValueError:
                _reason(run, "invalid_identity")
                continue
            if key in run.seen:
                _reason(run, "duplicate_candidate")
                continue
            run.seen.add(key)
            run.progress["unique"] += 1
            eligible = contract.lanes(raw)
            if not eligible:
                _reason(run, "ineligible_offer")
                continue
            run.progress["eligible"] += 1
            value = {k: deepcopy(v) for k, v in raw.items() if not k.startswith("_")}
            parsed = listing_details.parse_identifier(key)
            value["itemWebUrl"] = f"https://www.ebay.com/itm/{parsed['legacy']}" + (
                f"?var={parsed['variation']}" if parsed["variation"] != "0" else ""
            )
            if run.destination is None:
                value["shippingOptions"] = (
                    [
                        option
                        for option in value.get("shippingOptions", [])
                        if isinstance(option, dict) and option.get("shippingCostType") == "FIXED"
                    ]
                    if isinstance(value.get("shippingOptions", []), list)
                    else []
                )
            run.observations[key] = datetime.now(UTC).isoformat()
            value["_discovery_category"] = page.named.category
            run.raws.append(value)
            run.summaries[key] = deepcopy(value)
        run.content_revision += 1
        _progress(run)


def _selection_priority(row, page):
    # Search facets and returned position are never seller assertions.
    text = " ".join(v[:4096] for k in ("title", "shortDescription") if isinstance(v := row.get(k), str))
    aspects = row.get("localizedAspects")
    aspects = aspects[:100] if isinstance(aspects, list) else []
    contents = [
        a["value"][:500]
        for a in aspects
        if isinstance(a, dict)
        and isinstance(a.get("value"), str)
        and str(a.get("name", "")).casefold() in {"contents", "cards included"}
    ]
    text = " ".join([text, *contents]).casefold()

    def mentions(name):
        return bool(name and re.search(r"(?<!\w)" + re.escape(name.casefold()) + r"(?!\w)", text))

    target = mentions(page.query)
    set_match = mentions(page.set_name) or any(
        isinstance(a, dict)
        and str(a.get("name", "")).casefold() == "set"
        and page.set_name
        and str(a.get("value", "")).casefold() == page.set_name.casefold()
        for a in aspects
    )
    numbered = bool(re.search(r"\b\d+/\d+\b|\b\d+\s*[x×]\s*[a-z]", text))
    list_signal = bool(
        contents
        or numbered
        or re.search(
            r"\b(?:contents|cards included|includes|contains)\s*[:–-]|\b(?:itemized|card list)\b", text
        )
    )
    mixed = bool(re.search(r"\b(?:lot|bundle|collection|mixed|assortment)\b|\b\d+[ -]cards?\b", text))
    uncertain = bool(re.search(r"\b(?:mystery|random|may include|not guaranteed|choose your)\b", text))
    return (
        not uncertain,
        mixed and target and list_signal,
        target and list_signal,
        target,
        bool(set_match),
        numbered,
        list_signal,
        mixed,
    )


def _select(run):
    # Compare feasible pairs so a dual-option listing cannot starve the other lane.
    choices = {lane: [] for lane in contract.LANES}
    for row in sorted(run.raws, key=lambda r: r["itemId"]):
        priority = _selection_priority(row, run.pages[0].named)
        for lane in contract.lanes(row):
            choices[lane].append((priority, row["itemId"]))
    best, selected = (), []
    for buy in [*choices["buy_it_now"], None]:
        for auction in [*choices["auction"], None]:
            pair = [entry for entry in (buy, auction) if entry]
            keys = [key for _, key in pair]
            if len(keys) != len(set(keys)):
                continue
            score = (len(pair), *map(sum, zip(*(priority for priority, _ in pair), strict=True)))
            if score > best:
                best, selected = score, keys
    return selected


@shopping_index.indexed
def _assess(actor, run, raws):
    checks = []
    revision = run.content_revision
    if _revision(actor)["binding"] != run.binding:
        raise Halt("conflict", "Account or catalog revision changed")
    rows = discovery_listing.received_rows(raws)
    discovery_lot_values.project(
        actor, raws, rows, details=run.details, summaries=run.summaries, _checks=checks
    )
    if run.cancel.is_set() or revision != run.content_revision:
        raise Halt("conflict", "Listing content changed during assessment")
    indexed = shopping_index.current(actor)
    if indexed:
        indexed.publication_checks.append(lambda: _check_content(run, revision))
    return {"results": rows, "reference_checks": checks}


def _check_content(run, revision):
    if (
        run.cancel.is_set()
        or revision != run.content_revision
        or time.monotonic() >= run.created + contract.LEASE_SECONDS
    ):
        raise Halt("conflict", "Listing lease or revision changed")


async def _acquire(run, actor, credentials):
    transport = MeteredTransport(run)
    async with async_closing(transport, "shopping_transport_close_failed"):
        await asyncio.to_thread(_guard, run, actor)
        token = await d.access_token(run, transport, credentials, actor)
        # Acquire both discovery lanes before spending ANY detail capacity.
        for page in run.pages:
            run.lane, run.dispatch_id = page.lane, "page:" + page.lane
            _progress(run, "discovering")
            try:
                body = await _send(
                    run, actor, transport, "browse", token=token, search_options={"lot_hunt": page}
                )
                _received(run, page, body)
            except ProviderFailure:
                _reason(run, "summary_request_failed")
                _progress(run)
        selected = _select(run)
        if run.progress["eligible"] > len(selected):
            _reason(run, "candidate_limit")
        for key in selected:
            run.lane, run.dispatch_id = None, "detail:" + key
            _progress(run, "fetching_details")
            if key not in run.details:
                try:
                    body = await _send(run, actor, transport, "detail", token=token, identifier=key)
                    projection = listing_details.details(key, body)
                    if not contract.lanes(body):
                        raise ValueError("Offer no longer eligible")
                    # Details replace market fields, never fill missing shipping from a summary.
                    body = {k: v for k, v in body.items() if not k.startswith("_")}
                    if run.destination is None:
                        # A calculated quote needs the configured delivery destination.
                        body["shippingOptions"] = [
                            option
                            for option in body.get("shippingOptions", [])
                            if isinstance(option, dict) and option.get("shippingCostType") == "FIXED"
                        ]
                    shipping = listing_prices.detail_shipping(body)
                    body["shippingOptions"] = (
                        [{"shippingCost": {"value": shipping["amount"], "currency": shipping["currency"]}}]
                        if shipping["amount"] is not None
                        else []
                    )
                    body["itemWebUrl"] = projection["item_url"]
                    body["_discovery_category"] = "183455"
                    with run.lock:
                        _acquisition_check(run)
                        run.details[key] = body
                        run.observations[key] = datetime.now(UTC).isoformat()
                        run.raws = [deepcopy(body) if r["itemId"] == key else r for r in run.raws]
                        run.content_revision += 1
                        run.progress["enriched"] += 1
                except (ProviderFailure, ValueError):
                    _reason(run, "detail_request_failed")
                    _progress(run)
                    continue
            _progress(run, "assessing")
            try:
                await asyncio.to_thread(_record_assessment, actor, run, key)
            except (ValueError, RuntimeError):
                _reason(run, "assessment_unavailable")
                _progress(run)
    await asyncio.to_thread(_guard, run, actor)
    if run.reasons:
        state = "partial" if run.raws else "failed"
    else:
        state = "success"
    run.acquired_at = time.monotonic()
    _finish(run, state)


def _record_assessment(actor, run, key):
    # Publication guards may re-open the local reference database. Keep that
    # synchronous work on the worker thread, including the last source check.
    with run.lock:
        _guard(run, actor)
        raw = deepcopy(run.details[key])
        revision = run.content_revision
    result = _assess(actor, run, [raw])
    with run.lock:
        _guard(run, actor)
        _check_content(run, revision)
        for check in result["reference_checks"]:
            check()
        _guard(run, actor)
        _acquisition_check(run)
        run.assessed.add(key)
        run.progress["assessed"] += 1
        ready = _complete(result["results"][0].get("lot_value", {}))
        run.progress["ready" if ready else "partial"] += 1
        if not ready:
            _reason(run, "contents_or_references_unavailable")
        _progress(run)


def _worker(run, actor, credentials):
    close_old_connections()
    descriptor = None
    try:
        # Cross-process concurrency is one automatic job per installation. Busy
        # is terminal, with no hidden queue, provider retry or allowance renewal.
        path = hunter_policy._directory(hunter_policy._root(run.owner[0])) / "lot-hunt-worker.lock"
        descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        hunter_policy._private(descriptor, 0)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            _finish(
                run,
                "busy",
                "Another automatic Hunt is active. Reload its status or start a new Hunt after it finishes.",
            )
            return
        asyncio.run(_acquire(run, actor, credentials))
    except Halt as exc:
        _finish(run, exc.state, exc.reason, erase=exc.state in ERASED)
    except d._Stopped:
        _finish(run, "stopped", "Hunt stopped", erase=True)
    except Exception as exc:
        failure("automatic_lot_hunt_failed", exc)
        # Authorization loss cannot retain publishable seller data.
        from django.core.exceptions import PermissionDenied

        from .collection import Conflict

        erase = isinstance(exc, (PermissionDenied, Conflict))
        _finish(
            run,
            "unauthorized" if erase else "partial" if run.raws else "failed",
            "Hunt ended; no automatic request retry",
            erase=erase,
        )
    finally:
        if descriptor is not None:
            os.close(descriptor)
        close_old_connections()


def _complete(value):
    return value.get("total") is not None or any(
        g.get("complete") and g.get("total") is not None for g in value.get("native_guides", [])
    )


def status(actor, session, key):
    with _lock:
        run = _runs.get(str(key))
    if run is None:
        return _recovered(d._owner(actor, session), key)
    # Hold the content snapshot through indexed publication. An ordinary worker
    # page/detail completion must not invalidate its own concurrent status read.
    # Stop/expiry and revision checks still run inside this bounded local read.
    with run.lock:
        return _status(actor, session, run)


@shopping_index.indexed
def _status(actor, session, run):
    if run.owner != d._owner(actor, session):
        raise Http404
    if run.state in RUNNING and time.monotonic() >= run.deadline:
        _deadline(run)
    try:
        _guard(run, actor, acquiring=False)
    except Halt as exc:
        if run.state not in ERASED:
            _finish(run, exc.state, exc.reason, erase=True)
    except Exception:
        _finish(run, "unauthorized", "Authority changed; previous results were removed", erase=True)
    with run.lock:
        result = _summary(run)
        if run.state in ERASED:
            return result
        revision = run.content_revision
        raws = deepcopy([r for r in run.raws if contract.lanes(r)])
        assessed = set(run.assessed)
    # Read current references every time. No amounts/derivatives are persisted.
    rows = discovery_listing.received_rows(raws)
    # Parse every received seller summary locally. Full details still improve
    # two candidates within the unchanged five-operation acquisition contract.
    selected = (
        raws
        if run.state in RUNNING | {"success", "partial"}
        else [r for r in raws if r["itemId"] in assessed]
    )
    checks = []
    if selected:
        try:
            assessment = _assess(actor, run, selected)
            checks = assessment["reference_checks"]
            assessed_rows = assessment["results"]
            values = {r["item_id"]: r for r in assessed_rows}
            rows = [values.get(r["item_id"], r) for r in rows]
        except Halt as exc:
            _finish(run, exc.state, exc.reason, erase=True)
            return _summary(run)
        except (ValueError, RuntimeError):
            result["error"] = "Local assessment is unavailable; supported listing facts remain visible"
    rows = [row for row in rows if d.within_budget(row, run.choices)]
    discovery_lot_values.rank(rows, raws)
    from . import lot_recommendations

    lot_recommendations.rank(rows, run.choices)
    for row in rows:
        item = row.pop("item_id")
        row.update(
            id=discovery_listing.result_handle(run.id, item),
            revealed=True,
            evidence_kind="seller_details" if item in run.details else "seller_summary",
            observed_at=run.observations.get(item),
            expires_at=run.expires_at,
            content_revision=revision,
            assessment_state="ready"
            if _complete(row.get("lot_value", {}))
            else "partial"
            if item in assessed or row.get("lot_value", {}).get("identified_quantity")
            else "unprocessed",
        )
    try:
        _guard(run, actor, acquiring=False)
        for check in checks:
            check()
        _guard(run, actor, acquiring=False)
        with run.lock:
            _check_content(run, revision)
            for row in rows:
                # The HTTP envelope applies its final serialized bound after authorization.
                row["title"] = row.get("title", "")[:500]
                if len(row.get("seller_image") or "") > 512:
                    row["seller_image"] = None
                if value := row.get("lot_value"):
                    row["lot_value"] = discovery_lot_values.compact(value)
                    row["evidence_version"] = _evidence_version(value)
                order = row["value_order"]
                for lane, entry in list(order["lanes"].items()):
                    order["lanes"][lane] = {k: entry[k] for k in ("group", "rank", "score")}
                if combined := order["combined"]:
                    order["combined"] = {k: combined[k] for k in ("group", "combined_rank", "score")}
                order["native"] = [
                    {k: entry[k] for k in ("lane", "cohort", "rank")} for entry in order["native"]
                ]
            result["results"] = rows
            result["progress"]["ready"] = sum(r["assessment_state"] == "ready" for r in rows)
            result["progress"]["partial"] = sum(r["assessment_state"] == "partial" for r in rows)
            if result["state"] == "success" and result["progress"]["partial"]:
                result["state"] = "partial"
                result["reasons"]["current_assessment_unavailable"] = result["progress"]["partial"]
            result["coverage"] = dict(
                received=run.progress["received"], shown=len(rows), filtered=len(run.raws) - len(rows)
            )
    except Halt as exc:
        _finish(run, exc.state, exc.reason, erase=True)
        return _summary(run)
    return result


def _evidence_version(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def evidence(actor, session, key, handle, revision):
    run, _ = _lookup(actor, session, key)
    if run is None:
        raise Http404
    with run.lock:
        return _evidence(actor, run, handle, revision)


@shopping_index.indexed
def _evidence(actor, run, handle, revision):
    try:
        _guard(run, actor, acquiring=False)
        _check_content(run, revision)
        raw = next(
            (r for r in run.raws if discovery_listing.result_handle(run.id, r["itemId"]) == handle), None
        )
        if raw is None or not contract.lanes(raw):
            raise Http404
        item = raw["itemId"]
        assessment = _assess(actor, run, [raw])
        value = assessment["results"][0]["lot_value"]
        version = _evidence_version(value)
        for check in assessment["reference_checks"]:
            check()
        if not contract.lanes(next((r for r in run.raws if r["itemId"] == item), {})):
            raise Http404
        _guard(run, actor, acquiring=False)
        _check_content(run, revision)
    except Halt as exc:
        raise ValueError(exc.reason) from exc
    return dict(
        run_id=run.id, id=handle, content_revision=revision, evidence_version=version, lot_value=value
    )


def stop(actor, session, key):
    run, owner = _lookup(actor, session, key)
    if run is None:
        return _recovered(owner, key)
    _finish(run, "stopped", "Hunt stopped; consumed requests remain charged", erase=True)
    from . import listing_interpretation

    listing_interpretation.erase_parent("discovery", run.id)
    return _summary(run)
