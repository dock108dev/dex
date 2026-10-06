"""Durable bounded replay lifecycle. No acquisition adapter or automatic retry exists."""

import json
import time
import uuid
from datetime import datetime, timedelta, timezone

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.http import Http404

from pokemon_hunter.migration import encode

from . import catalog_imports, collection, store, transactions
from . import sealed_catalog as catalog

SCENARIOS = ("success", "unknown", "denied", "malformed", "identity-mismatch", "timeout", "slow")


def now():
    return datetime.now(timezone.utc).isoformat()


def enabled():
    return not settings.STAGING and (settings.ROOT / "SYNTHETIC_ONLY").is_file()


def authorize(actor):
    actor = store.verified(actor)
    if not enabled():
        raise PermissionDenied("Live refresh unavailable; replay requires disposable synthetic state")
    catalog_imports.admin(actor)
    return actor


def initialize(db=None):
    statements = [
        """CREATE TABLE IF NOT EXISTS refresh_runs(
        id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),actor_subject INTEGER NOT NULL,
        created_at TEXT NOT NULL,status TEXT NOT NULL,attempt_limit INTEGER NOT NULL,
        timeout_seconds INTEGER NOT NULL,scope TEXT NOT NULL,started_at TEXT,ended_at TEXT,reason TEXT NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS refresh_attempts(
        id TEXT PRIMARY KEY,run_id TEXT NOT NULL REFERENCES refresh_runs(id),ordinal INTEGER NOT NULL,
        source_id TEXT NOT NULL,offer_id TEXT NOT NULL,status TEXT NOT NULL,started_at TEXT,ended_at TEXT,
        deadline TEXT,execution_token TEXT,reason TEXT NOT NULL,candidate TEXT,import_id TEXT,
        timestamp_quality TEXT NOT NULL,UNIQUE(run_id,ordinal))""",
    ]
    if db is not None:
        for sql in statements:
            db.execute(sql)
    else:
        with transactions.atomic(), connection.cursor() as cursor:
            for sql in statements:
                cursor.execute(sql)


def available():
    return "refresh_runs" in connection.introspection.table_names()


def get(actor, key):
    actor = store.verified(actor)
    found = store.rows("SELECT * FROM refresh_runs WHERE id=%s AND user_id=%s", [key, actor.user_id])
    if not found:
        raise Http404
    row = found[0]
    row["scope"] = json.loads(row["scope"])
    row["attempts"] = store.rows("SELECT * FROM refresh_attempts WHERE run_id=%s ORDER BY ordinal", [key])
    row["consumed"] = sum(a["started_at"] is not None for a in row["attempts"])
    for attempt in row["attempts"]:
        attempt["candidate"] = json.loads(attempt["candidate"]) if attempt["candidate"] else None
        if attempt["import_id"]:
            attempt["review_state"] = catalog.get(actor, attempt["import_id"])["state"]
    return row


@transactions.atomic
def start(actor, product, selections, timeout=2):
    actor = authorize(actor)
    if type(timeout) is not int or not 1 <= timeout <= 30:
        raise ValueError("Timeout must be 1–30 seconds per source")
    if not selections or len(selections) > 7 or len(set(selections)) != len(selections):
        raise ValueError("Select 1–7 distinct replay sources")
    current = catalog.records()
    if product not in current["products"]:
        raise ValueError("Select an exact published product")
    offers = sorted(o["id"] for o in current["offers"].values() if o["product_id"] == product)
    if not offers or any(s not in SCENARIOS for s in selections):
        raise ValueError("Unsupported replay scope")
    key = str(uuid.uuid4())
    scope = dict(
        product_id=product,
        offer_id=offers[0],
        sources=["replay:" + s for s in selections],
        evidence_class="synthetic replay only",
        product_identity=current["products"][product],
        offer_identity=current["offers"][offers[0]],
    )
    collection.execute(
        "INSERT INTO refresh_runs VALUES(%s,%s,%s,%s,'queued',%s,%s,%s,NULL,NULL,'')",
        [key, actor.user_id, actor.subject, now(), len(selections), timeout, encode(scope)],
    )
    for ordinal, scenario in enumerate(selections):
        collection.execute(
            "INSERT INTO refresh_attempts VALUES(%s,%s,%s,%s,%s,'planned',NULL,NULL,NULL,NULL,'',NULL,NULL,'synthetic historical fixture')",
            [str(uuid.uuid4()), key, ordinal, "replay:" + scenario, offers[0]],
        )
    return key


@transactions.atomic
def stop(actor, key, reason="Stopped by initiating account"):
    authorize(actor)
    row = get(actor, key)
    if row["status"] not in {"queued", "running"}:
        return row
    ended = now()
    collection.execute(
        "UPDATE refresh_runs SET status='stopped',ended_at=%s,reason=%s WHERE id=%s", [ended, reason, key]
    )
    collection.execute(
        "UPDATE refresh_attempts SET status='cancelled',ended_at=%s,reason=%s WHERE run_id=%s AND status IN ('planned','running')",
        [ended, reason, key],
    )
    return get(actor, key)


@transactions.atomic
def recover(actor):
    """Expired work is terminal, never reclaimed or executed. Unstarted runs stay queued."""
    authorize(actor)
    for row in store.rows(
        "SELECT id FROM refresh_runs WHERE user_id=%s AND status='running'", [actor.user_id]
    ):
        run = get(actor, row["id"])
        active = next((a for a in run["attempts"] if a["status"] == "running"), None)
        deadline = (
            active["deadline"]
            if active
            else (catalog.instant(run["started_at"]) + timedelta(seconds=run["timeout_seconds"])).isoformat()
        )
        if catalog.instant(deadline) <= catalog.instant(now()):
            stop(
                actor,
                run["id"],
                "Interrupted or expired execution; consumed attempts retained; start a new run explicitly",
            )
            if active:
                collection.execute(
                    "UPDATE refresh_attempts SET status='interrupted' WHERE id=%s", [active["id"]]
                )


class ReplayFailure(Exception):
    pass


class ReplayAdapter:
    def execute(self, scope, attempt, checkpoint):
        scenario = attempt["source_id"].removeprefix("replay:")
        delay = 15 if scenario in {"timeout", "slow"} else 0
        end = time.monotonic() + delay
        while time.monotonic() < end:
            checkpoint()
            time.sleep(0.05)
        checkpoint()
        if scenario == "denied":
            raise ReplayFailure("Denied access; no observation supplied")
        if scenario == "malformed":
            return {"unusable": True}
        offer_id = scope["offer_id"] if scenario != "identity-mismatch" else "unrelated:offer"
        # Identity and timestamps depend on original evidence, never execution/run time.
        variant = "unknown" if scenario == "unknown" else "success"
        suffix = catalog_imports.fingerprint([scope["offer_id"], variant])[:24]
        sid, oid = "synthetic:source:" + suffix, "synthetic:observation:" + suffix
        checked = "2020-01-01T00:00:00+00:00" if variant == "success" else "2020-01-02T00:00:00+00:00"
        source = dict(
            id=sid,
            provider="SYNTHETIC replay",
            url="https://example.invalid/replay/" + suffix,
            retrieved_at=checked,
            sha256=catalog_imports.fingerprint([offer_id, variant, checked]),
            language="en",
            market="US",
            authority="retailer",
            status="usable",
            subjects=[oid],
            supports=["offer-observation"],
            rights="Disposable synthetic fixture only",
            note="SYNTHETIC historical fixture; never live stock, seller verification or purchasability",
        )
        observation = dict(
            id=oid,
            sources=[sid],
            offer_id=offer_id,
            checked_at=checked,
            stock="unknown" if variant == "unknown" else "out-of-stock",
            price_minor=None,
            shipping_minor=None,
            note="SYNTHETIC historical fixture; original checked time exact within fixture, not a real source check",
        )
        return dict(
            schema_version="dex-sealed-v1",
            provider="synthetic-replay",
            version=suffix,
            **{
                k: [source] if k == "sources" else [observation] if k == "observations" else []
                for k in catalog.KINDS
            },
            mappings=[],
        )


@transactions.atomic
def claim(actor, key):
    authorize(actor)
    run = get(actor, key)
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE refresh_runs SET status='running',started_at=%s WHERE id=%s AND status='queued'",
            [now(), key],
        )
        claimed = cursor.rowcount == 1
    return run if claimed else None


@transactions.atomic
def reserve(actor, key, attempt_id):
    run = get(actor, key)
    authorize(actor)
    if run["status"] != "running":
        return None
    if any(a["status"] == "running" for a in run["attempts"]):
        raise ValueError("An attempt is already executing for this run")
    if run["consumed"] >= run["attempt_limit"]:
        raise ValueError("Attempt budget exhausted")
    started = now()
    token = str(uuid.uuid4())
    deadline = (catalog.instant(started) + timedelta(seconds=run["timeout_seconds"])).isoformat()
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE refresh_attempts SET status='running',started_at=%s,deadline=%s,execution_token=%s WHERE id=%s AND run_id=%s AND status='planned'",
            [started, deadline, token, attempt_id, key],
        )
        if cursor.rowcount != 1:
            return None
    return next(a for a in get(actor, key)["attempts"] if a["id"] == attempt_id)


def validate_candidate(run, candidate):
    # Reject unsupported relationships before they can enter the review pipeline.
    parsed = catalog.Package.model_validate(candidate).model_dump()
    if (
        any(parsed[k] for k in catalog.KINDS if k not in {"sources", "observations"})
        or parsed["mappings"]
        or parsed.get("corrections")
        or parsed.get("bridges")
    ):
        raise ValueError("Unsupported refresh relationship")
    if not parsed["observations"] or any(
        o["offer_id"] != run["scope"]["offer_id"] for o in parsed["observations"]
    ):
        raise ValueError("Identity mismatch; no supported observation")
    current = catalog.records()
    if (
        current["offers"].get(run["scope"]["offer_id"]) != run["scope"]["offer_identity"]
        or current["products"].get(run["scope"]["product_id"]) != run["scope"]["product_identity"]
    ):
        raise ValueError("Identity mismatch; retained scope changed")
    return catalog.check(candidate)


@transactions.atomic
def deliver(actor, key, attempt, candidate=None, status="completed", reason=""):
    authorize(actor)
    run = get(actor, key)
    if run["status"] != "running":
        return False
    if status == "completed":
        candidate = validate_candidate(run, candidate)
        if catalog.instant(now()) >= catalog.instant(attempt["deadline"]):
            status, candidate, reason = "timeout", None, "Replay timeout; no observation delivered"
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE refresh_attempts SET status=%s,ended_at=%s,reason=%s,candidate=%s WHERE id=%s AND run_id=%s AND status='running' AND execution_token=%s",
            [
                status,
                now(),
                reason,
                encode(candidate) if candidate else None,
                attempt["id"],
                key,
                attempt["execution_token"],
            ],
        )
        return cursor.rowcount == 1


@transactions.atomic
def finish(actor, key):
    row = get(actor, key)
    if row["status"] == "running":
        status = "completed" if all(a["status"] == "completed" for a in row["attempts"]) else "failed"
        collection.execute(
            "UPDATE refresh_runs SET status=%s,ended_at=%s,reason=%s WHERE id=%s",
            [
                status,
                now(),
                "Some sources failed; completed candidates remain available for review"
                if status == "failed"
                else "Replay completed; explicit review/publication required",
                key,
            ],
        )


def execute(actor, key):
    run = claim(actor, key)
    if run is None:
        return
    adapter = ReplayAdapter()
    for planned in run["attempts"]:
        attempt = reserve(actor, key, planned["id"])
        if attempt is None:
            break

        def checkpoint():
            authorize(actor)
            state = get(actor, key)
            if state["status"] != "running":
                raise ReplayFailure("Cancelled; no observation delivered")
            if catalog.instant(now()) >= catalog.instant(attempt["deadline"]):
                raise TimeoutError("Replay timeout; no observation delivered")

        try:
            candidate = adapter.execute(run["scope"], attempt, checkpoint)
            checkpoint()
            parsed = validate_candidate(run, candidate)
            deliver(actor, key, attempt, parsed)
        except TimeoutError:
            deliver(actor, key, attempt, status="timeout", reason="Replay timeout; no observation delivered")
        except (ValueError, ReplayFailure) as exc:
            reason = (
                (
                    "Identity mismatch; no supported observation"
                    if "Identity mismatch" in str(exc)
                    else "Unusable content; no supported observation"
                )
                if isinstance(exc, ValueError)
                else str(exc)
            )
            deliver(actor, key, attempt, status="failed", reason=reason)
        except Exception:
            # Retain unexpected failures without leaking exception/credential contents.
            deliver(
                actor,
                key,
                attempt,
                status="failed",
                reason="Replay execution failed; no observation delivered",
            )
    finish(actor, key)


@transactions.atomic
def review(actor, key, attempt_id, action):
    authorize(actor)
    attempt = next((a for a in get(actor, key)["attempts"] if a["id"] == attempt_id), None)
    if not attempt or attempt["status"] != "completed":
        raise ValueError("No completed candidate for this run")
    if action == "preview":
        op = catalog.preview(actor, attempt["candidate"])
        collection.execute("UPDATE refresh_attempts SET import_id=%s WHERE id=%s", [op["id"], attempt_id])
        return catalog.review(op)
    if action not in {"verify", "publish"} or not attempt["import_id"]:
        raise ValueError("Preview and verify before publication")
    op = catalog.get(actor, attempt["import_id"])
    if action == "verify" and op["state"] == "published":
        return op  # Identical prior publication already passed this review boundary.
    return catalog.transition(actor, attempt["import_id"], action)
