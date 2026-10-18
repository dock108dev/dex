"""Explicit, disabled-by-default official lot details on the shared allowance.

This is an engineering service contract. Ordinary local lot analysis never enters
it. A trusted future allowance must be captured by the original Hunter run before
any provider dispatch is possible. The original source expiry always wins.
"""

import asyncio
import threading
import time
import uuid
from copy import deepcopy
from datetime import UTC, datetime

from django.db import close_old_connections
from django.http import Http404

from . import discovery as d
from . import ebay_hunts, hunter, hunter_budget, listing_details
from .diagnostics import async_closing, failure
from .discovery_transport import ProviderFailure, Transport

MAX_DETAIL_BATCH = 2  # The established explicit detail action limit is unchanged.
_runs = {}
_lock = threading.RLock()


def _lookup(actor, session_key, action_id):
    owner = d._owner(actor, session_key)
    with _lock:
        run = _runs.get(str(action_id))
    if run is None or run.owner != owner:
        raise Http404
    d._acquisition_timeout(run)
    if time.monotonic() - run.created >= d.EPHEMERAL_SECONDS:
        _expire(run.id)
        raise Http404
    # The original source owns account/session and independent Stop authority.
    hunter.summary_lease(actor, session_key, run.parent_run_id, run.result_ids[0])
    return run


def _expire(action_id):
    with _lock:
        run = _runs.pop(action_id, None)
    if run:
        with run.lock:
            run.cancel.set()
            run.raws.clear()
            run.state = "expired"


def erase_parent(run_id):
    """Erase all detail bodies and reviews when the original Hunt stops/expires."""
    from . import hunter_lots

    with _lock:
        keys = [key for key, run in _runs.items() if run.parent_run_id == str(run_id)]
    for key in keys:
        _expire(key)
    hunter_lots.erase_parent(run_id)


def _summary(run):
    return dict(
        detail_action_id=run.id,
        state=run.state,
        running=run.state in {"queued", "running"},
        counts=dict(run.counts),
        error=run.error,
        expires_in_seconds=max(0, int(run.created + d.EPHEMERAL_SECONDS - time.monotonic())),
        source_lease_renews=False,
        reviews=[],
    )


def _checked_detail(actor, session_key, parent_run_id, result_id, raw):
    """Latest body owns all market fields; only trusted acquisition paths transfer."""
    source = hunter.summary_lease(actor, session_key, parent_run_id, result_id)
    parent = hunter._lookup(actor, session_key, parent_run_id)
    listing_details.validate_response(source["raw"].get("itemId"), raw)
    observation = deepcopy(raw)
    for key in ("_hunt_paths", "_hunt_lanes"):
        observation.pop(key, None)
        if key in source["raw"]:
            observation[key] = deepcopy(source["raw"][key])
    if None not in hunter._eligibility(parent, observation, datetime.now(UTC)):
        raise ValueError("Official details are ended, unavailable or outside the captured Hunt scope")
    return source


def start(actor, session_key, run_id, result_ids):
    from . import hunter_lots

    hunter_lots._selected_ids(result_ids, maximum=MAX_DETAIL_BATCH)
    intent = hunter_lots.detail_intent(actor, session_key, run_id, result_ids)
    parent = hunter._lookup(actor, session_key, run_id)
    allowance = getattr(parent, "allowance", None)
    if not hunter_budget.is_traversal_allowance(allowance):
        raise ValueError("No future official lot-detail allowance is active")
    remaining = hunter_budget.remaining_traversal(parent.owner[0], allowance)
    if (
        remaining["detail"] < len(result_ids)
        or remaining["total"] < len(result_ids)
        or remaining["lots"] < len(result_ids)
    ):
        raise ValueError("The captured shared allowance cannot admit the selected lot details")
    provider, values = ebay_hunts.configuration()
    credentials = (values.get("EBAY_CLIENT_ID"), values.get("EBAY_CLIENT_SECRET"))
    if provider.environment != "production" or not all(credentials):
        raise ValueError("The saved Production configuration is unavailable")
    with _lock:
        if any(
            r.owner == parent.owner and r.parent_run_id == parent.id and r.state in {"queued", "running"}
            for r in _runs.values()
        ):
            raise ValueError("An official detail action is already running for this Hunt")
        run = d.Run(
            str(uuid.uuid4()),
            parent.owner,
            parent.choices,
            None,
            intent["requests"],
            operation="detail",
            auth_session=parent.auth_session,
            created=parent.created,
            cancel=threading.Event(),
            lock=parent.lock,
            counts=dict(oauth=0, detail=0, resolution=0, total=0),
            deadline=min(time.monotonic() + d.OVERALL_SECONDS, parent.created + d.EPHEMERAL_SECONDS),
        )
        run.parent_run_id = parent.id
        run.result_ids = tuple(result_ids)
        run.review_ids = []
        run.current_item = None

        def admit(stage):
            if stage not in {"oauth", "detail"}:
                raise ProviderFailure(stage)
            hunter_budget.consume_traversal(
                parent.owner[0],
                parent.id,
                stage,
                dispatch_id="lot-detail:" + (run.id if stage == "oauth" else run.current_item),
                allowance=allowance,
                scope="lots",
            )

        run.admit = admit
        _runs[run.id] = run
    expiry = threading.Timer(
        max(0, parent.created + d.EPHEMERAL_SECONDS - time.monotonic()), _expire, args=(run.id,)
    )
    expiry.daemon = True
    expiry.start()
    watchdog = threading.Timer(max(0, run.deadline - time.monotonic()), d._acquisition_timeout, args=(run,))
    watchdog.daemon = True
    watchdog.start()
    threading.Thread(
        target=_worker,
        args=(run, actor, session_key, credentials),
        daemon=True,
        name="dex-hunter-lot-details",
    ).start()
    return _summary(run)


async def _acquire(run, actor, session_key, credentials):
    transport = Transport()
    async with async_closing(transport, "shopping_transport_close_failed"):
        token = await d.access_token(run, transport, credentials, actor)
        acquired = []
        for request in run.queries:
            # Authorization and original availability are checked before each send.
            await asyncio.to_thread(
                hunter.summary_lease, actor, session_key, run.parent_run_id, request["result_id"]
            )
            run.current_item = request["item_id"]
            body = await d._dispatch(
                run, transport, "detail", run.deadline, actor=actor, token=token, identifier=run.current_item
            )
            await asyncio.to_thread(
                _checked_detail, actor, session_key, run.parent_run_id, request["result_id"], body
            )
            # Parse before retaining: hostile/oversized text fails this path.
            from . import hunter_lots

            source = await asyncio.to_thread(
                hunter.summary_lease, actor, session_key, run.parent_run_id, request["result_id"]
            )
            entries = await asyncio.to_thread(hunter_lots._catalog, actor)
            hunter_lots.parse(source["raw"], entries, detail=body)
            acquired.append(dict(result_id=request["result_id"], raw=body))
        for result_id in run.result_ids:
            await asyncio.to_thread(hunter.summary_lease, actor, session_key, run.parent_run_id, result_id)
        with run.lock:
            d._check_acquisition(run)
            run.raws = acquired
            run.acquired_at = time.monotonic()
            run.state = "complete"


def _worker(run, actor, session_key, credentials):
    close_old_connections()
    try:
        with run.lock:
            d._check_acquisition(run)
            run.state = "running"
        asyncio.run(_acquire(run, actor, session_key, credentials))
    except Exception as exc:
        if not isinstance(exc, d._Stopped):
            failure("hunter_lot_detail_failed", exc)
        with run.lock:
            run.raws.clear()
            run.state = "stopped" if run.cancel.is_set() and not run.timed_out else "failed"
            run.error = "Official lot detail action stopped; no retry was made"
    finally:
        close_old_connections()


def leased_detail(actor, session_key, action_id, origin):
    run = _lookup(actor, session_key, action_id)
    if run.parent_run_id != origin["run_id"]:
        raise Http404
    with run.lock:
        if run.cancel.is_set() or run.state != "complete":
            raise Http404
        raw = next((r["raw"] for r in run.raws if r["result_id"] == origin["result_id"]), None)
        if raw is None:
            raise Http404
        body = deepcopy(raw)
    _checked_detail(actor, session_key, run.parent_run_id, origin["result_id"], body)
    return body


def status(actor, session_key, action_id):
    from . import hunter_lots

    run = _lookup(actor, session_key, action_id)
    with run.lock:
        result = _summary(run)
        if run.state != "complete" or run.cancel.is_set():
            return result
        if not run.review_ids:
            # Parent lock serializes this first transfer and concurrent status reads.
            reviews = [
                hunter_lots.analyze(actor, session_key, run.parent_run_id, key, _detail_action=run.id)
                for key in run.result_ids
            ]
            run.review_ids = [review["review_id"] for review in reviews]
        else:
            reviews = [hunter_lots.read(actor, session_key, key) for key in run.review_ids]
        d._check_acquisition(run, authorization=False)
        result["reviews"] = reviews
        return hunter_lots._bounded_response(result)


def stop(actor, session_key, action_id):
    from . import hunter_lots

    run = _lookup(actor, session_key, action_id)
    with run.lock:
        run.cancel.set()
        run.raws.clear()
        run.state = "stopped"
        hunter_lots.erase_detail(run.id)
        return _summary(run)
