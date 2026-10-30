"""Finite listings-first singles core. No scheduling, details or durable results.

The existing Shopping dispatch/token/admission/arithmetic authorities are reused.
This backend boundary is intentionally independent of the vintage/card-query
Discovery choices. LOT-01 can consume the leased summaries and local adapter.
"""

import asyncio
import hashlib
import json
import threading
import time
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from threading import Timer

from django.db import close_old_connections
from django.http import Http404

from . import (
    collection,
    discovery,
    discovery_listing,
    ebay_hunts,
    hunter_budget,
    hunter_catalog,
    hunter_coverage,
    hunter_policy,
    hunter_query,
    hunter_ranking,
    hunter_traversal,
    store,
)
from .diagnostics import async_closing, failure
from .discovery_transport import ProviderFailure, Transport

MAX_SUMMARIES = 400
_runs = {}
_lock = threading.RLock()


class InvalidResultCursor(ValueError):
    """The ordered local projection no longer matches a received page cursor."""


@dataclass
class Run(discovery.Run):
    operation: str = "hunter"
    window: dict = field(default_factory=dict)
    lanes: list = field(default_factory=list)
    current_lane: str | None = None
    current_scope: str = "singles"
    traversal: object | None = None
    allowance: object | None = None
    next_index: int = 0
    action_counts: dict | None = None
    coverage_counts: dict = field(default_factory=dict)
    retention_bytes: int = 0
    skipped_partitions: set = field(default_factory=set)
    coverage_reasons: dict = field(default_factory=dict)

    def admit(self, stage):
        if self.traversal is None:
            hunter_budget.consume(self, stage)
        else:
            hunter_budget.consume_traversal(
                self.owner[0],
                self.id,
                stage,
                self.current_lane if stage == "browse" else None,
                dispatch_id=f"{self.traversal.id}:{self.next_index}"
                if stage == "browse"
                else f"{self.id}:oauth",
                allowance=self.allowance,
                scope=self.current_scope,
            )


def _summary(run):
    discovery._acquisition_timeout(run)
    result = {
        "run_id": run.id,
        "state": run.state,
        "running": run.state in {"queued", "running"},
        "expires_in_seconds": max(0, int(discovery.EPHEMERAL_SECONDS - (time.monotonic() - run.created))),
        "window": {key: run.window[key] for key in ("start", "end")},
        "counts": {
            "duplicates": 0,
            "invalid_identity": 0,
            **run.counts,
            "pages": sum(lane["pages"] for lane in run.lanes),
            "truncated_pages": sum(lane["truncated"] for lane in run.lanes),
        },
        "lanes": deepcopy(run.lanes or _planned_lanes(run)),
        "has_next": False,
        "coverage_complete": False,
        "error": run.error,
        "results": [],
        "note": "Bounded sample: at most one auction page and one Buy It Now page. No continuation or detail requests. References retain their original dates. Temporary results expire within 30 minutes or on restart; saving/export is unavailable.",
    }
    if run.traversal is not None:
        capacity = hunter_budget.remaining_traversal(run.owner[0], allowance=run.allowance)
        result.update(
            traversal_allowance_id=run.allowance.id if run.allowance else None,
            traversal_remaining=capacity,
            continuation_blocked_reason="allowance_exhausted"
            if capacity["browse"] < 1 or capacity["total"] < 1
            else None,
            plan=run.traversal.public(),
            has_next=run.state == "complete" and run.traversal.cursor(run.next_index) is not None,
            continuation_cursor=run.traversal.cursor(run.next_index) if run.state == "complete" else None,
            traversal_coverage={
                **run.coverage_counts,
                "retained": len(run.raws),
                "remaining_pages": len(run.traversal.requests) - run.next_index,
                "skipped_partitions": sorted(run.skipped_partitions),
                "exhaustive_market_snapshot": False,
                "reasons": dict(run.coverage_reasons),
                "rejected_meaning": "malformed provider item identities; local offer rejections are in coverage",
                "truncated_meaning": "pages with advisory evidence of further results",
            },
            note="Finite captured traversal. Continue requires an explicit action and remaining allowance. Totals and page hints are advisory; market coverage is never exhaustive. Temporary results retain the original lease.",
        )
    return result


def _planned_lanes(run):
    return [
        {
            "lane": request["lane"],
            "pages": 0,
            "attempted": 0,
            "received": 0,
            "state": "planned",
            "truncated": False,
            "total_reported": None,
        }
        for request in run.queries
    ]


def _lookup(actor, session_key, run_id):
    owner = discovery._owner(actor, session_key)
    with _lock:
        run = _runs.get(str(run_id))
    if run is None or run.owner != owner:
        raise Http404
    if run.auth_session is not None:
        discovery._authorize(actor, run.auth_session)
    discovery._acquisition_timeout(run)
    if time.monotonic() - run.created >= discovery.EPHEMERAL_SECONDS:
        _expire(run.id)
    return run


def _clear_dependents(run_id):
    from . import hunter_lot_details, listing_interpretation

    hunter_lot_details.erase_parent(run_id)
    listing_interpretation.erase_parent("hunter", run_id)


def _expire(run_id):
    with _lock:
        run = _runs.get(run_id)
    if run:
        with run.lock:
            run.cancel.set()
            run.raws.clear()
            run.seen.clear()
            run.state = "expired"
        _clear_dependents(run.id)


def metadata(actor, session_key):
    from .hunter_installed import current_allowance

    owner = discovery._owner(actor, session_key)
    allowance = current_allowance(actor)
    capacity = hunter_budget.remaining_traversal(owner[0], allowance=allowance)
    available = allowance is not None and capacity["browse"] > 0 and capacity["total"] > 0
    usage = hunter_policy.status(actor) if getattr(actor, "role", None) == "owner" else None
    return {
        "usage_policy": usage,
        "allowance": hunter_budget.ALLOWANCE,
        "remaining": hunter_budget.remaining(owner[0]),
        "traversal_allowance_enabled": allowance is not None,
        "traversal_allowance_id": allowance.id if allowance else None,
        "traversal_remaining": capacity,
        "acquisition_available": available,
        "acquisition_unavailable_reason": None
        if available
        else "Hunt is unavailable because no authorized acquisition allowance remains. No marketplace search has run.",
        "scope_label": "US / English Pokémon TCG · all years and generations · auctions ending in the captured next 24 hours plus available Buy It Now offers · owned cards included",
        "max_pages_per_action": 2,
        "max_cumulative_summaries": hunter_traversal.MAX_CUMULATIVE_SUMMARIES,
        "max_retained_summaries": hunter_traversal.MAX_RETAINED_SUMMARIES,
        "max_retained_bytes": 8 * 1024 * 1024,
        "max_summaries_per_page": 200,
        "max_result_summaries": 200,
        "max_response_bytes": hunter_query.RESPONSE_BYTE_LIMIT,
        "comparison_chunk_summaries": hunter_catalog.MAX_ROWS,
        "request_seconds": discovery.REQUEST_SECONDS,
        "overall_seconds_per_action": discovery.OVERALL_SECONDS,
        "temporary_seconds": discovery.EPHEMERAL_SECONDS,
    }


def start(actor, session_key, raw, *, auth_session=None):
    from .hunter_installed import check_dispatch, current_allowance

    owner = discovery._owner(actor, session_key)
    if (
        not isinstance(raw, dict)
        or set(raw) - {"scope"}
        or raw.get("scope", "singles") not in {"singles", "lots", "both"}
    ):
        raise ValueError(
            "Hunt takes only a singles, lots or both scope; no filters, paging or budget overrides"
        )
    plan = hunter_traversal.build_plan(datetime.now(UTC), scope=raw.get("scope", "singles"))
    allowance = current_allowance(actor)
    capacity = hunter_budget.remaining_traversal(owner[0], allowance=allowance)
    if allowance is None or capacity["browse"] < 1 or capacity["total"] < 1:
        raise ValueError("No authorized traversal allowance remains; the HUNT-01 allowance stays consumed")
    provider, values = ebay_hunts.configuration()
    if provider.environment != "production":
        raise ValueError("Hunter needs the saved Production eBay configuration")
    credentials = (values.get("EBAY_CLIENT_ID"), values.get("EBAY_CLIENT_SECRET"))
    if not all(credentials):
        raise ValueError("The saved Production eBay credentials are unavailable")
    run = Run(
        str(uuid.uuid4()),
        owner,
        discovery.Choices(english_vintage=False),
        None,
        [],
        auth_session=auth_session,
        window={"start": plan.start, "end": plan.end},
        traversal=plan,
        allowance=allowance,
        action_counts={},
    )
    hunter_policy.bind(run, actor)
    check_dispatch(run)
    with _lock:
        for old in _runs.values():
            if (
                type(run.allowance) is not hunter_policy.OrdinaryAllowance
                and old.owner == owner
                and old.state in {"queued", "running"}
            ):
                with old.lock:
                    old.cancel.set()
                    old.raws.clear()
                    old.state = "stopped"
                    _clear_dependents(old.id)
        _runs[run.id] = run
    _launch(run, actor, credentials)
    return _summary(run)


def _launch(run, actor, credentials):
    discovery._journal(run, "action", "admitted")
    discovery._arm_deadline(run)
    expiry = Timer(
        max(0, discovery.EPHEMERAL_SECONDS - (time.monotonic() - run.created)), _expire, args=(run.id,)
    )
    expiry.daemon = True
    expiry.start()
    threading.Thread(
        target=_worker, args=(run, actor, credentials), daemon=True, name="dex-price-hunter"
    ).start()


def continue_run(actor, session_key, run_id, raw):
    from .hunter_installed import current_allowance

    run = _lookup(actor, session_key, run_id)
    if not isinstance(raw, dict) or set(raw) != {"cursor"}:
        raise ValueError("Continue takes only the captured continuation cursor")
    with run.lock:
        if run.traversal is None or run.state != "complete" or run.cancel.is_set():
            raise ValueError("This Hunt cannot continue")
        expected = run.traversal.cursor(run.next_index)
        if expected is None or raw["cursor"] != expected:
            raise ValueError("The continuation cursor is repeated, incompatible or nonadvancing")
        if current_allowance(actor, existing=run.allowance) is None:
            raise ValueError("The captured installed Hunter authority is unavailable")
        remaining = hunter_budget.remaining_traversal(run.owner[0], allowance=run.allowance)
        if remaining["browse"] < 1 or remaining["total"] < 1:
            raise ValueError("The authorized traversal allowance is consumed")
        provider, values = ebay_hunts.configuration()
        credentials = (values.get("EBAY_CLIENT_ID"), values.get("EBAY_CLIENT_SECRET"))
        if provider.environment != "production" or not all(credentials):
            raise ValueError("The saved Production eBay configuration is unavailable")
        run.state = "queued"
        run.deadline = None
        run.acquired_at = None
        run.action_counts = {}
        run.error = None
        _launch(run, actor, credentials)
        return _summary(run)


def stop(actor, session_key, run_id):
    run = _lookup(actor, session_key, run_id)
    with run.lock:
        run.cancel.set()
        run.raws.clear()
        run.seen.clear()
        run.state = "stopped"
        _clear_dependents(run.id)
        discovery._journal(run, "action", "stopped")
        return _summary(run)


def _eligibility(run, raw, now):
    paths = raw.get("_hunt_paths") or [
        ("singles" if run.traversal is None else run.traversal.scope, lane)
        for lane in raw.get("_hunt_lanes", [])
    ]
    return [
        hunter_query.lane_eligibility(raw, lane, run.window["start"], run.window["end"], now=now, scope=scope)
        for scope, lane in paths
    ]


def status(actor, session_key, run_id, *, cursor=None):
    run = _lookup(actor, session_key, run_id)
    with run.lock:
        result = _summary(run)
        if type(run.allowance) is hunter_policy.OrdinaryAllowance:
            result["usage_policy"] = hunter_policy.status(actor)
        if run.cancel.is_set() or run.state != "complete":
            return result
        raws = deepcopy(run.raws)
        snapshot_next_index = run.next_index
    now = datetime.now(UTC)
    eligible, rejected = [], []
    for raw in raws:
        reasons = _eligibility(run, raw, now)
        if None in reasons:
            eligible.append(raw)
        else:
            rejected.append(
                {
                    "item_id": raw["itemId"],
                    "hunt_status": "rejected",
                    "reason": reasons[0],
                    "reference": None,
                    "classification": "unpriced",
                    "save_allowed": False,
                }
            )
    # These values/derivatives are never cached. Every read re-enters the normal
    # source admission/expiry/withdrawal path, independently of listing lifetime.
    catalog_generation = collection.generation(actor) if len(eligible) > hunter_catalog.MAX_ROWS else None
    rows = []
    for offset in range(0, len(eligible), hunter_catalog.MAX_ROWS):
        rows.extend(
            hunter_catalog.compare(actor, eligible[offset : offset + hunter_catalog.MAX_ROWS], now=now)
        )
    if catalog_generation is not None and collection.generation(actor) != catalog_generation:
        raise collection.Conflict("Catalog changed between Hunter comparison chunks; read results again")
    rows = hunter_ranking.order(rows + rejected)
    by_id = {raw["itemId"]: raw for raw in raws}
    coverage = {
        key: 0
        for key in (
            "matched",
            "comparable",
            "conditional",
            "ambiguous",
            "unpriced",
            "unmatched",
            "rejected",
            "unsupported",
        )
    }
    coverage["rejected"] = run.counts.get("invalid_identity", 0)
    for row in rows:
        state = row["hunt_status"]
        if state in {"priced", "conditional", "unpriced"}:
            coverage["matched"] += 1
        key = "comparable" if state == "priced" else state
        coverage[key] += 1
        item_id = str(row.pop("item_id"))
        raw = by_id[item_id]
        row.update(
            id=discovery_listing.result_handle(run.id, item_id),
            observed_at=raw["_hunt_observed_at"],
            lanes=list(raw["_hunt_lanes"]),
            scopes=list(raw.get("_hunt_scopes", ["singles"])),
            final_purchase_price=None,
            planned_manual_bid=None,
        )
    if run.auth_session is not None:
        discovery._authorize(actor, run.auth_session)
    else:
        store.verified(actor)
    with run.lock:
        discovery._acquisition_timeout(run)
        if run.cancel.is_set() or run.state != "complete":
            return _summary(run)
        if not run.cancel.is_set() and run.state == "complete":
            if run.raws != raws or run.next_index != snapshot_next_index:
                raise collection.Conflict("Hunt changed while preparing local results; read again")
            revision = hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()
            offset = 0
            if cursor is not None:
                offsets = {
                    hashlib.sha256(f"{run.id}:local:{revision}:{n}".encode()).hexdigest(): n
                    for n in range(1, len(rows))
                }
                if cursor not in offsets:
                    raise InvalidResultCursor("Choose a valid local result cursor")
                offset = offsets[cursor]
            result["coverage"] = {**coverage, "unique": len(raws), "results": len(rows)}
            result["coverage_diagnostics"] = hunter_coverage.summarize(
                rows,
                fetched=run.coverage_counts.get("fetched", run.counts.get("summary_count")),
                retained=len(raws),
            )
            selected, used = [], len(json.dumps(result, default=str).encode()) + 4096
            for row in rows[offset : offset + 200]:
                row_bytes = len(json.dumps(row, default=str, ensure_ascii=True).encode())
                if used + row_bytes > hunter_query.RESPONSE_BYTE_LIMIT:
                    break
                selected.append(row)
                used += row_bytes + 2
            if rows[offset:] and not selected:
                selected = [
                    {
                        "id": rows[offset]["id"],
                        "hunt_status": "unpriced",
                        "reason": "response_byte_limit",
                        "reference": None,
                    }
                ]
            end = offset + len(selected)
            result["results"] = selected
            result["result_cursor"] = (
                hashlib.sha256(f"{run.id}:local:{revision}:{end}".encode()).hexdigest()
                if end < len(rows)
                else None
            )
            result["result_page"] = {
                "offset": offset,
                "returned": len(selected),
                "total": len(rows),
                "remaining": len(rows) - end,
            }
    return result


def summary_lease(actor, session_key, run_id, result_id):
    """LOT-01 integration boundary: same temporary lease, no detail acquisition.

    A future explicit lot analyzer can read already available seller text and
    identity/quantity clues. This method neither interprets lots nor values one
    as a single. Callers must preserve created/expiry and recheck this lease.
    """
    run = _lookup(actor, session_key, run_id)
    with run.lock:
        if run.cancel.is_set() or run.state != "complete":
            raise Http404
        raw = next(
            (r for r in run.raws if discovery_listing.result_handle(run.id, r["itemId"]) == result_id), None
        )
        if raw is None:
            raise Http404
        reasons = _eligibility(run, raw, datetime.now(UTC))
        if None not in reasons:
            raise ValueError("The listing is ended, unavailable or outside the captured Hunt scope")
        return {
            "raw": deepcopy(raw),
            "created": run.created,
            "expires_in_seconds": _summary(run)["expires_in_seconds"],
            # Internal lease metadata only; public responses project plan fields.
            "_allowance": run.allowance,
        }


async def _acquire(run, credentials, actor=None):
    discovery._arm_deadline(run)
    transport = Transport()
    rows_by_id = {}
    run.lanes = _planned_lanes(run)
    async with async_closing(transport, "shopping_transport_close_failed"):
        token = await discovery.access_token(run, transport, credentials, actor)
        for request, lane in zip(run.queries, run.lanes, strict=True):
            run.current_lane = request["lane"]
            before = run.counts["browse"]
            lane["state"] = "requesting"
            try:
                payload = await discovery._dispatch(
                    run,
                    transport,
                    "browse",
                    run.deadline,
                    actor=actor,
                    token=token,
                    search_options={"hunter": request},
                )
                rows = payload.get("itemSummaries", [])
                if (
                    not isinstance(rows, list)
                    or len(rows) > 200
                    or any(not isinstance(r, dict) for r in rows)
                ):
                    raise ProviderFailure("browse")
            except Exception:
                lane["state"] = "failed"
                raise
            finally:
                lane["attempted"] = run.counts["browse"] - before
            with run.lock:
                discovery._check_acquisition(run)
                run.counts["summary_count"] += len(rows)
                if run.counts["summary_count"] > MAX_SUMMARIES:
                    raise ProviderFailure("browse")
                total = payload.get("total")
                truncated = bool(payload.get("next")) or (type(total) is int and total > len(rows))
                lane.update(
                    pages=1,
                    state="complete",
                    received=len(rows),
                    truncated=truncated,
                    total_reported=total if type(total) is int else None,
                )
                for raw in rows:
                    key = raw.get("itemId")
                    if not isinstance(key, str) or not key or len(key) > 200:
                        run.counts["invalid_identity"] = run.counts.get("invalid_identity", 0) + 1
                        continue
                    if key in rows_by_id:
                        run.counts["duplicates"] = run.counts.get("duplicates", 0) + 1
                        previous = rows_by_id[key]
                        if request["lane"] not in previous["_hunt_lanes"]:
                            previous["_hunt_lanes"].append(request["lane"])
                        # The latest whole observation owns option availability
                        # and amounts. Unioning old options could resurrect BIN
                        # after a bid removed it. Lane history is separate.
                        rows_by_id[key] = {
                            **deepcopy(raw),
                            "_hunt_lanes": list(previous["_hunt_lanes"]),
                            "_hunt_observed_at": datetime.now(UTC).isoformat(),
                        }
                    else:
                        rows_by_id[key] = {
                            **deepcopy(raw),
                            "_hunt_lanes": [request["lane"]],
                            "_hunt_observed_at": datetime.now(UTC).isoformat(),
                        }
                run.offset += 1
    discovery._check_acquisition(run)
    if actor is not None:
        await asyncio.to_thread(discovery._authorize, actor, run.auth_session)
        began = time.monotonic()
        # First local matching is part of the 75-second publication deadline.
        # Source values are discarded and re-admitted on subsequent local reads.
        await asyncio.to_thread(hunter_catalog.compare, actor, list(rows_by_id.values()))
        run.counts["local_match_milliseconds"] = round((time.monotonic() - began) * 1000, 3)
        await asyncio.to_thread(discovery._authorize, actor, run.auth_session)
    with run.lock:
        discovery._check_acquisition(run)
        run.raws = list(rows_by_id.values())
        run.acquired_at = time.monotonic()
        run.state = "complete"


def _worker(run, actor, credentials):
    close_old_connections()
    try:
        with run.lock:
            discovery._check_acquisition(run)
            run.state = "running"
        asyncio.run(
            _acquire_traversal(run, credentials, actor)
            if run.traversal is not None
            else _acquire(run, credentials, actor)
        )
    except discovery._Stopped:
        with run.lock:
            if not run.timed_out:
                run.state = "stopped"
            run.raws.clear()
    except Exception as exc:
        failure("hunter_acquisition_failed", exc)
        with run.lock:
            run.raws.clear()
            if not run.cancel.is_set():
                run.state = "failed"
                run.error = "Hunter stopped at its first failure. Consumed or uncertain operations remain counted; no automatic retry or continuation is permitted."
    finally:
        if run.state in {"failed", "stopped", "expired"}:
            _clear_dependents(run.id)
        close_old_connections()


async def _acquire_traversal(run, credentials, actor=None):
    """At most two pages per explicit action; no next URL controls transport."""
    discovery._arm_deadline(run)
    transport = Transport()
    rows_by_id = {raw["itemId"]: raw for raw in run.raws}
    counts = run.coverage_counts
    for key in ("fetched", "unique", "duplicates", "rejected", "skipped", "pages", "truncated"):
        counts.setdefault(key, 0)
    async with async_closing(transport, "shopping_transport_close_failed"):
        token = await discovery.access_token(run, transport, credentials, actor)
        dispatched = 0
        while run.next_index < len(run.traversal.requests) and dispatched < 2:
            request = run.traversal.requests[run.next_index]
            if request.partition_id in run.skipped_partitions:
                run.next_index += 1
                counts["skipped_pages"] = counts.get("skipped_pages", 0) + 1
                run.coverage_reasons["empty_partition_page_skipped"] = (
                    run.coverage_reasons.get("empty_partition_page_skipped", 0) + 1
                )
                continue
            run.current_lane = request.lane
            run.current_scope = request.scope
            lane = {
                "lane": request.lane,
                "scope": request.scope,
                "partition": request.partition_id,
                "pages": 0,
                "attempted": 0,
                "received": 0,
                "state": "requesting",
                "truncated": False,
                "total_reported": None,
            }
            run.lanes.append(lane)
            before = run.counts["browse"]
            try:
                payload = await discovery._dispatch(
                    run,
                    transport,
                    "browse",
                    run.deadline,
                    actor=actor,
                    token=token,
                    search_options={"hunter": request},
                )
                hint = hunter_traversal.inspect_page(request, payload)
                rows = payload.get("itemSummaries", [])
                if (
                    not isinstance(rows, list)
                    or len(rows) > 200
                    or any(not isinstance(r, dict) for r in rows)
                ):
                    raise ProviderFailure("browse")
                with run.lock:
                    discovery._check_acquisition(run)
                    counts["fetched"] += len(rows)
                    run.counts["summary_count"] += len(rows)
                    if counts["fetched"] > hunter_traversal.MAX_CUMULATIVE_SUMMARIES:
                        raise ProviderFailure("browse")
                    counts["pages"] += 1
                    lane.update(
                        pages=1,
                        received=len(rows),
                        state="complete",
                        truncated=bool(hint.get("truncated", payload.get("next"))),
                        total_reported=payload.get("total") if type(payload.get("total")) is int else None,
                    )
                    if hint.get("total_inconsistent"):
                        run.coverage_reasons["inconsistent_provider_total"] = (
                            run.coverage_reasons.get("inconsistent_provider_total", 0) + 1
                        )
                    if lane["truncated"]:
                        counts["truncated"] += 1
                        last_offset = max(
                            r.offset for r in run.traversal.requests if r.partition_id == request.partition_id
                        )
                        if request.offset == last_offset:
                            run.coverage_reasons["partition_page_cap"] = (
                                run.coverage_reasons.get("partition_page_cap", 0) + 1
                            )
                    for raw in rows:
                        key = raw.get("itemId")
                        if not isinstance(key, str) or not key or len(key) > 200:
                            counts["rejected"] += 1
                            run.coverage_reasons["invalid_item_identity"] = (
                                run.coverage_reasons.get("invalid_item_identity", 0) + 1
                            )
                            run.counts["invalid_identity"] = run.counts.get("invalid_identity", 0) + 1
                            continue
                        if key in run.seen:
                            counts["duplicates"] += 1
                            run.counts["duplicates"] = run.counts.get("duplicates", 0) + 1
                            if key not in rows_by_id:
                                continue
                        else:
                            run.seen.add(key)
                            counts["unique"] += 1
                        previous = rows_by_id.get(key)
                        lanes = list(previous.get("_hunt_lanes", [])) if previous else []
                        if request.lane not in lanes:
                            lanes.append(request.lane)
                        paths = list(previous.get("_hunt_paths", [])) if previous else []
                        path = [request.scope, request.lane]
                        if path not in paths:
                            paths.append(path)
                        scopes = sorted({scope for scope, _ in paths})
                        observation = {
                            **deepcopy(raw),
                            "_hunt_scopes": scopes,
                            "_hunt_paths": paths,
                            "_hunt_lanes": lanes,
                            "_hunt_observed_at": datetime.now(UTC).isoformat(),
                        }
                        size = len(json.dumps(observation, ensure_ascii=True).encode())
                        old_size = len(json.dumps(previous, ensure_ascii=True).encode()) if previous else 0
                        if (
                            previous is None
                            and len(rows_by_id) >= hunter_traversal.MAX_RETAINED_SUMMARIES
                            or run.retention_bytes - old_size + size > 8 * 1024 * 1024
                        ):
                            if previous:
                                del rows_by_id[key]
                                run.retention_bytes -= old_size
                            counts["skipped"] += 1
                            counts["retention_limited"] = True
                            run.coverage_reasons["temporary_retention_cap"] = (
                                run.coverage_reasons.get("temporary_retention_cap", 0) + 1
                            )
                            continue
                        rows_by_id[key] = observation
                        run.retention_bytes += size - old_size
                    run.next_index += 1
                    if not rows:
                        run.skipped_partitions.add(request.partition_id)
                    run.offset += 1
                    dispatched += 1
            except Exception:
                lane["state"] = "failed"
                raise
            finally:
                lane["attempted"] = run.counts["browse"] - before
    discovery._check_acquisition(run)
    with run.lock:
        while (
            run.next_index < len(run.traversal.requests)
            and run.traversal.requests[run.next_index].partition_id in run.skipped_partitions
        ):
            run.next_index += 1
            counts["skipped_pages"] = counts.get("skipped_pages", 0) + 1
            run.coverage_reasons["empty_partition_page_skipped"] = (
                run.coverage_reasons.get("empty_partition_page_skipped", 0) + 1
            )
    if actor is not None:
        await asyncio.to_thread(discovery._authorize, actor, run.auth_session)
        began = time.monotonic()
        retained = list(rows_by_id.values())
        for offset in range(0, len(retained), hunter_catalog.MAX_ROWS):
            await asyncio.to_thread(
                hunter_catalog.compare, actor, retained[offset : offset + hunter_catalog.MAX_ROWS]
            )
        run.counts["local_match_milliseconds"] = round((time.monotonic() - began) * 1000, 3)
        await asyncio.to_thread(discovery._authorize, actor, run.auth_session)
    with run.lock:
        discovery._check_acquisition(run)
        run.raws = list(rows_by_id.values())
        run.acquired_at = time.monotonic()
        run.state = "complete"
