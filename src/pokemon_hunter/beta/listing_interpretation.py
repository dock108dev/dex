"""Ephemeral, session-bound explicit interpretation of already authorized seller text."""

import asyncio
import hashlib
import json
import threading
import time
import uuid
from copy import deepcopy

from django.conf import settings
from django.db import close_old_connections
from django.http import Http404

from . import collection, discovery, hunter, hunter_lot_parser, ollama_gateway

_jobs = {}
_lock = threading.RLock()
_slot = threading.Lock()


def source(actor, session, origin, *, admit=False):
    if origin["kind"] == "hunter":
        return hunter.summary_lease(actor, session, origin["run_id"], origin["result_id"])
    if origin["kind"] == "discovery":
        if admit:
            # Validate the selected visible result once; subsequent lease checks do
            # not recompute catalog/price comparisons to read unchanged seller text.
            return discovery.review_candidate(actor, session, origin["run_id"], origin["result_id"])
        return discovery.summary_lease(actor, session, origin["run_id"], origin["result_id"])
    raise ValueError("Choose an existing Shopping or Hunter result")


def _fingerprint(value):
    return hashlib.sha256(json.dumps(value["raw"], sort_keys=True).encode()).hexdigest()


def _erase(key):
    with _lock:
        job = _jobs.pop(key, None)
        if job:
            job["cancel"].set()
            job["result"] = None
            if job.get("timer"):
                job["timer"].cancel()


def erase_parent(kind, run_id):
    """Parent Stop/expiry erases derived seller content without a browser poll."""
    with _lock:
        for key, job in list(_jobs.items()):
            if job["origin"]["kind"] == kind and job["origin"]["run_id"] == str(run_id):
                _erase(key)


def _sweep():
    for key, job in list(_jobs.items()):
        if time.monotonic() >= job["expires"]:
            _erase(key)


def start(actor, session, auth_session, origin):
    if set(origin) != {"kind", "run_id", "result_id"} or any(
        not isinstance(v, str) or not v or len(v) > 160 for v in origin.values()
    ):
        raise ValueError("Choose one existing listing")
    discovery._authorize(actor, auth_session)
    leased = source(actor, session, origin, admit=True)
    fields = hunter_lot_parser.interpretation_fields(leased["raw"])
    config = ollama_gateway.configuration(settings.ROOT)
    with _lock:
        _sweep()
        if len(_jobs) >= 64 or not _slot.acquire(blocking=False):
            raise ValueError("Another local analysis is running. Wait or stop it first.")
        key = str(uuid.uuid4())
        job = dict(
            owner=discovery._owner(actor, session),
            origin=dict(origin),
            fingerprint=_fingerprint(leased),
            expires=time.monotonic() + min(240, leased["expires_in_seconds"]),
            cancel=threading.Event(),
            state="running",
            result=None,
            error=None,
        )
        _jobs[key] = job
    try:
        timer = threading.Timer(max(0, job["expires"] - time.monotonic()), _erase, args=(key,))
        timer.daemon = True
        job["timer"] = timer
        timer.start()
        threading.Thread(
            target=_worker,
            args=(key, job, actor, session, auth_session, config, fields),
            daemon=True,
        ).start()
    except Exception:
        _erase(key)
        _slot.release()
        raise
    return dict(id=key, state="running")


def _worker(key, job, actor, session, auth_session, config, fields):
    close_old_connections()
    next_check = 0.0

    def cancelled(*, force=False):
        nonlocal next_check
        if job["cancel"].is_set() or time.monotonic() >= job["expires"]:
            return True
        if force or time.monotonic() >= next_check:
            next_check = time.monotonic() + 1
            try:
                discovery._authorize(actor, auth_session)
                if _fingerprint(source(actor, session, job["origin"])) != job["fingerprint"]:
                    return True
            except Exception:
                return True
            finally:
                close_old_connections()
        return False

    try:
        # Reauthorize before scheduling any gateway work. Admission may precede
        # worker startup by enough time for logout, Stop or source expiry.
        if cancelled(force=True):
            raise ollama_gateway.Unavailable("Analysis expired or stopped.")

        # Authority checks occur in this worker's synchronous context, not an async ORM context.
        async def run():
            task = asyncio.create_task(ollama_gateway.extract(config, fields, cancelled=job["cancel"].is_set))
            try:
                while not task.done():
                    if await asyncio.to_thread(cancelled):
                        job["cancel"].set()
                    await asyncio.wait({task}, timeout=0.1)
                return await task
            finally:
                if not task.done():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)

        raw = asyncio.run(run())
        result = hunter_lot_parser.interpretation_result(fields, raw)
        leased = source(actor, session, job["origin"])
        entries = collection.catalog(actor)
        parsed = hunter_lot_parser.parse(leased["raw"], entries)
        names = {p["name"].casefold() for p in entries}
        sets = {p["set_name"].casefold() for p in entries}
        for fact in result["facts"][:]:
            allowed = names if fact["field"] == "name" else sets if fact["field"] == "set" else None
            if allowed is not None and fact["value"].casefold() not in allowed:
                result["facts"].remove(fact)
                result["warnings"].append(
                    f"Unresolved {fact['field']} suggestion; use the original evidence for manual correction."
                )
                if fact["field"] not in result["unknown_fields"]:
                    result["unknown_fields"].append(fact["field"])
        result["catalog_matches"] = [
            dict(name=p["name"], printing_id=p["printing_id"], reasons=p["reasons"])
            for p in parsed["proposals"][:20]
        ]
        result["warnings"].extend(parsed.get("quantity_issues", []))
        result["listing_id"] = leased["raw"].get("itemId")
        # The periodic check is throttled only while receiving. A fast response
        # still needs current authority before publication.
        if cancelled(force=True):
            raise ollama_gateway.Unavailable("Analysis expired or stopped.")
        with _lock:
            if _jobs.get(key) is job and not job["cancel"].is_set():
                job.update(state="complete", result=result)
    except Exception:
        with _lock:
            if _jobs.get(key) is job and job["state"] == "running":
                job.update(
                    state="unavailable",
                    result=None,
                    error="Analysis unavailable or incomplete. Review manually.",
                )
    finally:
        _slot.release()
        close_old_connections()


def read(actor, session, key, *, stop=False):
    owner = discovery._owner(actor, session)
    with _lock:
        _sweep()
        job = _jobs.get(str(key))
        if not job or job["owner"] != owner:
            raise Http404
        origin, fingerprint = dict(job["origin"]), job["fingerprint"]
        if stop:
            job["cancel"].set()
            job.update(state="stopped", result=None, error=None)
    try:
        leased = source(actor, session, origin)
        if _fingerprint(leased) != fingerprint:
            raise Http404
    except Exception:
        _erase(str(key))
        raise Http404 from None
    with _lock:
        if time.monotonic() >= job["expires"] or _jobs.get(str(key)) is not job:
            raise Http404
        return dict(id=str(key), state=job["state"], result=deepcopy(job["result"]), error=job["error"])
