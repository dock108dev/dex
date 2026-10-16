"""Bounded, account/session-private Shopping discovery; listing content is ephemeral.

Only sanitized attempt transitions are durable. Browsing, comparison, Stop and
reveal never write saved_hunts, inventory, goals, references or browser storage.
"""

import asyncio
import hashlib
import json
import os
import threading
import time
import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from threading import Timer
from typing import Literal

from django.conf import settings
from django.db import close_old_connections
from django.http import Http404
from pydantic import BaseModel, Field, StrictInt, field_validator

from . import ebay_hunts, goal_hunts, parity, store
from .discovery_transport import ProviderFailure, Transport

MAX_OAUTH = 1
MAX_BROWSE = 4
MAX_SUMMARIES = 20
REQUEST_SECONDS = 30
OVERALL_SECONDS = 75
EPHEMERAL_SECONDS = 1800
VINTAGE = (
    "Base Set",
    "Jungle",
    "Fossil",
    "Base Set 2",
    "Team Rocket",
    "Gym Heroes",
    "Gym Challenge",
    "Neo Genesis",
    "Neo Discovery",
    "Neo Revelation",
    "Neo Destiny",
)


class Choices(BaseModel):
    model_config = {"extra": "forbid"}

    intent: Literal["deals", "missing"] = "deals"
    missing_basis: Literal["printing", "species"] = "printing"
    goal_id: str | None = Field(default=None, min_length=1, max_length=64)
    focus: Literal["all", "kanto", "johto", "rares", "bulk"] = "all"
    budget: Decimal | None = Field(default=None, ge=0, le=10000)
    query: str = Field(default="", max_length=200)
    set_id: str | None = Field(default=None, min_length=1, max_length=100)
    browse_requests: StrictInt = Field(default=1, ge=1, le=MAX_BROWSE)

    @field_validator("query")
    @classmethod
    def trim(cls, value):
        return value.strip()


@dataclass
class Run:
    id: str
    owner: tuple
    choices: Choices
    scope: dict | None
    queries: list
    operation: str = "browse"
    identifier: str | None = None
    auth_session: str | None = None
    offset: int = 0
    raws: list = field(default_factory=list)
    seen: set = field(default_factory=set)
    revealed: set = field(default_factory=set)
    state: str = "queued"
    error: str | None = None
    created: float = field(default_factory=time.monotonic)
    deadline: float | None = None
    acquired_at: float | None = None
    timed_out: bool = False
    counts: dict = field(default_factory=lambda: {"oauth": 0, "browse": 0, "total": 0, "summary_count": 0})
    cancel: threading.Event = field(default_factory=threading.Event)
    lock: threading.RLock = field(default_factory=threading.RLock)


_runs = {}
_lock = threading.RLock()
_journal_lock = threading.Lock()
_token_lock = threading.Lock()
_tokens = {}


def _owner(actor, session_key):
    store.verified(actor)
    if not isinstance(session_key, str) or not session_key:
        raise ValueError("Sign in again before starting a search")
    return str(Path(settings.ROOT).resolve()), actor.user_id, session_key


def _candidate_data(actor, choices, scope):
    data = goal_hunts.project(actor, parity.projection(actor), scope)
    cards = list(data["cards"].values())
    if choices.set_id:
        cards = [c for c in cards if choices.set_id in (c["set_id"], c["set"])]
    if choices.focus in ("kanto", "johto"):
        cards = [
            c
            for c in cards
            if isinstance(c.get("pokemon_dex"), int)
            and (1 <= c["pokemon_dex"] <= 151 if choices.focus == "kanto" else 152 <= c["pokemon_dex"] <= 251)
        ]
    elif choices.focus == "rares":
        cards = [c for c in cards if "rare" in c.get("rarity", "").lower()]
    elif choices.focus == "bulk":
        cards = [c for c in cards if c.get("rarity", "").lower() in {"common", "uncommon"}]
    if choices.intent == "missing":
        species = scope["definition"]["policy"] == "species" if scope else choices.missing_basis == "species"
        if species:
            cards = [
                c
                for c in cards
                if c.get("dex_eligible") and not data["pokedex"][str(c["pokemon_dex"])]["dex_owned"]
            ]
        else:
            cards = [
                c for c in cards if not (c["owned"] if scope else c.get("exact_printing_owned", c["owned"]))
            ]
    by_printing = {c["printing_id"]: c for c in cards}
    candidates = [{**by_printing[p["id"]], **p} for p in data["catalog"] if p["id"] in by_printing]
    # The supported dated vintage comparison coverage leads automatic discovery;
    # remaining catalog entries stay available and can be shown as unpriced.
    candidates.sort(
        key=lambda c: (
            VINTAGE.index(c["set_name"]) if c["set_name"] in VINTAGE else len(VINTAGE),
            c["set_name"],
            c["name"],
            c["collector_number"],
            c["id"],
        )
    )
    return candidates


def query_plan(candidates, query=""):
    if query:
        return [query]
    return list(
        dict.fromkeys(
            f"Pokemon {c['set_name']} {c['name']} {c['collector_number']}"[:200] for c in candidates
        )
    )


def metadata(actor):
    store.verified(actor)
    data = parity.projection(actor)
    sets = {c["set_id"]: c["set"] for c in data["cards"].values()}
    return {
        "provider": ebay_hunts.status(),
        "defaults": Choices().model_dump(mode="json"),
        "sets": [{"id": key, "name": name} for key, name in sorted(sets.items(), key=lambda pair: pair[1])],
    }


def _journal(run, stage, state, **extra):
    """Append before dispatch; no query, credential, listing or price content."""
    root = Path(run.owner[0])
    root_key = hashlib.sha256(str(root).encode()).hexdigest()
    directory = root.parent / ".dex-shopping-discovery" / root_key
    with _journal_lock:
        if directory.is_symlink():
            raise ValueError("Discovery request accounting is unavailable")
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = directory / "attempts.jsonl"
        if path.is_symlink():
            raise ValueError("Discovery request accounting is unavailable")
        record = {
            "version": 1,
            "run_id": run.id,
            "at": datetime.now(UTC).isoformat(),
            "stage": stage,
            "state": state,
            **extra,
        }
        fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "a") as stream:
            stream.write(json.dumps(record, separators=(",", ":")) + "\n")
            stream.flush()
            os.fsync(stream.fileno())


def _lookup(actor, session_key, run_id):
    owner = _owner(actor, session_key)
    with _lock:
        run = _runs.get(str(run_id))
        if run is None or run.owner != owner:
            raise Http404
        _acquisition_timeout(run)
        if time.monotonic() - run.created >= EPHEMERAL_SECONDS:
            run.cancel.set()
            run.raws.clear()
            run.seen.clear()
            run.state = "expired"
        return run


def _acquisition_timeout(run):
    """A watchdog and local reads enforce the same fixed publication boundary."""
    with run.lock:
        if (
            run.deadline is None
            or time.monotonic() < run.deadline
            or (run.acquired_at is not None and run.acquired_at <= run.deadline)
            or run.state not in {"queued", "running", "complete"}
        ):
            return
        run.timed_out = True
        run.cancel.set()
        run.raws.clear()
        run.revealed.clear()
        run.state = "failed"
        run.error = "This search reached its overall time limit. No later requests or results will be published. Start a new search explicitly."


def _arm_deadline(run):
    with run.lock:
        if run.deadline is not None:
            return
        run.deadline = time.monotonic() + OVERALL_SECONDS
    watchdog = Timer(OVERALL_SECONDS, _acquisition_timeout, args=(run,))
    watchdog.daemon = True
    watchdog.start()


def _check_acquisition(run):
    _acquisition_timeout(run)
    if run.cancel.is_set():
        raise _Stopped


def _expire(run_id):
    """Erase temporary provider content even when the browser never polls again."""
    with _lock:
        run = _runs.get(run_id)
    if run is None:
        return
    with run.lock:
        run.cancel.set()
        run.raws.clear()
        run.seen.clear()
        run.revealed.clear()
        run.state = "expired"


def _scope_label(run):
    if run.choices.intent == "deals":
        return "Catalog discovery, including cards already owned"
    if run.scope:
        units = "species" if run.scope["definition"]["policy"] == "species" else "exact printings"
        return f"Frozen goal: {run.scope['name']} · missing {units} in its saved checklist"
    return "Current collection: missing " + (
        "species" if run.choices.missing_basis == "species" else "exact printings"
    )


def _summary(run):
    _acquisition_timeout(run)
    return {
        "run_id": run.id,
        "expires_in_seconds": max(0, int(EPHEMERAL_SECONDS - (time.monotonic() - run.created))),
        "state": run.state,
        "running": run.state in {"queued", "running"},
        "choices": run.choices.model_dump(mode="json"),
        "scope_label": _scope_label(run),
        "goal": goal_hunts.public(run.scope),
        "counts": dict(run.counts),
        "queries_total": len(run.queries),
        "queries_completed": run.offset,
        "has_next": run.state == "complete" and run.offset < len(run.queries),
        "continuation_run": run.id,
        "error": run.error,
        "note": "Temporary eBay summaries; seller text proposes identity. Prices exclude tax. References retain their source dates; searching does not refresh them. Results expire when the server restarts or after 30 minutes.",
        "results": [],
    }


def status(actor, session_key, run_id):
    run = _lookup(actor, session_key, run_id)
    with run.lock:
        result = _summary(run)
        if run.cancel.is_set() or run.state not in {"complete", "failed"}:
            return result
        raws, revealed = deepcopy(run.raws), set(run.revealed)
    # Admission, expiry, withdrawal, rights and current ownership are evaluated on
    # every local read. Restricted guide cells/derivatives are never cached.
    from .discovery_comparison import compare

    candidates = _candidate_data(actor, run.choices, run.scope)
    rows = compare(actor, raws, candidates)
    visible = []
    for row in rows:
        row = dict(row)
        item_id = str(row.pop("item_id", ""))
        handle = hashlib.sha256((run.id + "\0" + item_id).encode()).hexdigest()[:24]
        row["id"], row["revealed"] = handle, handle in revealed
        if not row["revealed"]:
            for key in ("title", "item_url", "url", "shortDescription"):
                row.pop(key, None)
            row["proposed_identity"] = None
            if row.get("reference"):
                row["reference"] = {**row["reference"], "source_url": None}
                row["reference"]["conflicts"] = [
                    {**conflict, "source_url": None} for conflict in row["reference"].get("conflicts", [])
                ]
        if run.choices.budget is not None:
            minimum = row.get("delivered_total") or row.get("listing_price")
            if minimum is not None and Decimal(minimum) > run.choices.budget:
                continue
        visible.append(row)

    with run.lock:
        if not run.cancel.is_set() and run.state in {"complete", "failed"}:
            result["results"] = visible
    if not result["results"] and run.state == "complete":
        result["limitation"] = (
            "No summaries in this batch matched the selected cards and budget with an admitted comparison. "
            "Unknown shipping and ambiguous identity can limit comparisons; Next results searches the next captured catalog choice."
        )
    return result


def reveal(actor, session_key, run_id, result_id):
    run = _lookup(actor, session_key, run_id)
    current = status(actor, session_key, run_id)
    if result_id not in {r["id"] for r in current["results"]}:
        raise Http404
    with run.lock:
        run.revealed.add(result_id)
    return status(actor, session_key, run_id)


def stop(actor, session_key, run_id):
    run = _lookup(actor, session_key, run_id)
    with run.lock:
        run.cancel.set()
        run.state = "stopped"
        run.raws.clear()
        run.revealed.clear()
        _journal(run, "action", "stopped")
        return _summary(run)


def start(actor, session_key, raw):
    owner = _owner(actor, session_key)
    if not isinstance(raw, dict):
        raise ValueError("Choose search options")
    continuation = raw.get("continuation_run")
    if continuation:
        if set(raw) != {"continuation_run"}:
            raise ValueError("Start a new search after changing search choices")
        previous = _lookup(actor, session_key, continuation)
        with previous.lock:
            if previous.state != "complete" or previous.offset >= len(previous.queries):
                raise ValueError("No next results remain for this search")
            run = Run(
                str(uuid.uuid4()),
                owner,
                previous.choices,
                deepcopy(previous.scope),
                list(previous.queries),
                offset=previous.offset,
                raws=deepcopy(previous.raws),
                seen=set(previous.seen),
            )
    else:
        choices = Choices.model_validate(raw)
        # A deal search never needs a selected goal; goal membership applies only
        # to the explicit missing-card workflow.
        if choices.intent == "deals" and choices.goal_id:
            raise ValueError("Use Find missing cards to search a frozen goal")
        scope = goal_hunts.snapshot(actor, choices.goal_id)
        candidates = _candidate_data(actor, choices, scope)
        run = Run(str(uuid.uuid4()), owner, choices, scope, query_plan(candidates, choices.query))
    # Validate the one saved Production configuration locally before a worker is
    # admitted. Country/postal choices are fixed by the transport, not old YAML.
    provider, values = ebay_hunts.configuration()
    if provider.environment != "production":
        raise ValueError("Find deals needs the saved Production eBay configuration")
    credentials = (values.get("EBAY_CLIENT_ID"), values.get("EBAY_CLIENT_SECRET"))
    if not all(credentials):
        raise ValueError("The saved Production eBay credentials are unavailable")
    with _lock:
        for old in _runs.values():
            if old.owner == owner and old.state in {"queued", "running"}:
                old.cancel.set()
                old.state = "stopped"
                old.raws.clear()
        _runs[run.id] = run
    _journal(run, "action", "admitted")
    _arm_deadline(run)
    expiry = Timer(EPHEMERAL_SECONDS, _expire, args=(run.id,))
    expiry.daemon = True
    expiry.start()
    if not run.queries:
        run.acquired_at = time.monotonic()
        run.state = "complete"
    else:
        threading.Thread(
            target=_worker, args=(run, actor, credentials), daemon=True, name="dex-shopping-discovery"
        ).start()
    return _summary(run)


class _Stopped(Exception):
    pass


def _authorize(actor, session_key=None):
    close_old_connections()
    try:
        store.verified(actor)
        if session_key is not None:
            from django.contrib.sessions.models import Session
            from django.core.exceptions import PermissionDenied
            from django.utils import timezone

            row = Session.objects.filter(session_key=session_key, expire_date__gt=timezone.now()).first()
            if row is None or row.get_decoded().get("_auth_user_id") != str(actor.subject):
                raise PermissionDenied
    finally:
        close_old_connections()


async def _dispatch(run, transport, stage, deadline, *, actor=None, **kwargs):
    _check_acquisition(run)
    if actor is not None:
        if run.auth_session is not None:
            await asyncio.to_thread(_authorize, actor, run.auth_session)
        else:
            await asyncio.to_thread(_authorize, actor)
    with run.lock:
        _check_acquisition(run)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ProviderFailure(stage, uncertain=False)
        limits = (
            {"oauth": MAX_OAUTH, "browse": MAX_BROWSE}
            if run.operation == "browse"
            else {"oauth": 1, "detail": 2, "resolution": 2}
        )
        if (
            stage not in limits
            or run.counts.get(stage, 0) >= limits[stage]
            or (
                run.operation != "browse"
                and run.counts.get("detail", 0) + run.counts.get("resolution", 0) >= 2
            )
        ):
            raise ProviderFailure(stage, uncertain=False)
        run.counts[stage] = run.counts.get(stage, 0) + 1
        run.counts["total"] += 1
        sequence = run.counts["total"]
        _journal(run, stage, "admitted", attempt=sequence)
        _journal(run, stage, "in_flight", attempt=sequence)
        # Stop and admission share this lock; no dispatch is scheduled after Stop.
        task = asyncio.create_task(
            transport.request(stage, timeout=min(REQUEST_SECONDS, remaining), **kwargs)
        )
    expires = min(deadline, time.monotonic() + REQUEST_SECONDS)
    try:
        while not task.done():
            if run.cancel.is_set():
                raise _Stopped
            remaining = expires - time.monotonic()
            if remaining <= 0:
                raise ProviderFailure(stage, uncertain=True)
            await asyncio.wait({task}, timeout=min(0.05, remaining))
        value = task.result()
        if run.cancel.is_set():
            raise _Stopped
        _journal(run, stage, "completed", attempt=sequence, http_status=200)
        return value
    except _Stopped:
        _journal(run, stage, "uncertain", attempt=sequence, reason="stopped_in_flight")
        raise
    except ProviderFailure as exc:
        _journal(
            run,
            stage,
            "uncertain" if exc.uncertain else "failed",
            attempt=sequence,
            **({"http_status": exc.status} if exc.status else {}),
        )
        raise
    except Exception:
        _journal(run, stage, "uncertain", attempt=sequence)
        raise ProviderFailure(stage, uncertain=True) from None
    finally:
        if not task.done():
            task.cancel()
        if task.done():
            try:
                task.result()
            except (Exception, asyncio.CancelledError):
                pass
        else:
            await asyncio.wait({task}, timeout=0.25)


async def access_token(run, transport, credentials, actor=None):
    deadline = run.deadline
    cache_key = hashlib.sha256((run.owner[0] + "\0" + "\0".join(credentials)).encode()).hexdigest()
    with _token_lock:
        token, expiry = _tokens.get(cache_key, (None, 0))
    if not token or time.monotonic() >= expiry:
        payload = await _dispatch(run, transport, "oauth", deadline, credentials=credentials, actor=actor)
        token, lifetime, label = (
            payload.get("access_token"),
            payload.get("expires_in"),
            payload.get("token_type"),
        )
        if (
            not isinstance(token, str)
            or not token.strip()
            or len(token) > 8192
            or type(lifetime) is not int
            or lifetime <= 0
            or not isinstance(label, str)
            or label.casefold() not in {"bearer", "application access token"}
        ):
            raise ProviderFailure("oauth")
        with _token_lock:
            _tokens[cache_key] = token, time.monotonic() + max(0, lifetime - 60)
    return token


async def _acquire(run, credentials, actor=None):
    _arm_deadline(run)
    transport = Transport()
    deadline = run.deadline
    try:
        token = await access_token(run, transport, credentials, actor)
        remaining_queries = run.queries[run.offset : run.offset + run.choices.browse_requests]
        additions = []
        for query in remaining_queries:
            payload = await _dispatch(
                run, transport, "browse", deadline, token=token, query=query, actor=actor
            )
            rows = payload.get("itemSummaries", [])
            if (
                not isinstance(rows, list)
                or len(rows) > MAX_SUMMARIES
                or any(not isinstance(r, dict) for r in rows)
            ):
                raise ProviderFailure("browse")
            with run.lock:
                if run.cancel.is_set():
                    raise _Stopped
                run.counts["summary_count"] += len(rows)
                for row in rows:
                    key = row.get("itemId")
                    if not isinstance(key, str) or not key or key in run.seen:
                        continue
                    run.seen.add(key)
                    additions.append(row)
                run.offset += 1
    finally:
        await asyncio.wait_for(transport.close(), timeout=0.5)
    _check_acquisition(run)
    if actor is not None:
        await asyncio.to_thread(_authorize, actor)
    with run.lock:
        _check_acquisition(run)
        run.raws.extend(additions)
        run.acquired_at = time.monotonic()
        run.state = "complete"


def _worker(run, actor, credentials):
    _arm_deadline(run)
    close_old_connections()
    try:
        store.verified(actor)
        with run.lock:
            if run.cancel.is_set():
                return
            run.state = "running"
        asyncio.run(_acquire(run, credentials, actor))
    except _Stopped:
        with run.lock:
            if not run.timed_out:
                run.state = "stopped"
            run.raws.clear()
    except Exception as exc:
        with run.lock:
            if run.cancel.is_set():
                if not run.timed_out:
                    run.state = "stopped"
                run.raws.clear()
            else:
                run.state = "failed"
                stage = exc.stage.title() if isinstance(exc, ProviderFailure) else "Search"
                code = f" (HTTP {exc.status})" if isinstance(exc, ProviderFailure) and exc.status else ""
                run.error = f"eBay {stage} stopped{code}. No automatic retry was made. Review the connection and start a new search explicitly."
    finally:
        credentials = None
        close_old_connections()
