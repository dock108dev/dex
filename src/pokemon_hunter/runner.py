import fcntl
import json
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from .beta.diagnostics import closing, failure
from .database import Database
from .ebay import discover
from .normalize import evaluate
from .notifier import digest_text
from .pokedex import missing_rates, summary
from .scoring import PRIORITIES


@contextmanager
def run_lock(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with db_path.with_suffix(".lock").open("a") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another watcher run is already active") from None
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def run(db_path, settings, catalog, queries, pokedex, notifier, *, client=None, fixtures=None, now=None):
    now = now or datetime.now(UTC)
    with run_lock(db_path):
        with closing(Database(db_path), "watcher_database_close_failed") as db:
            return _run(db, settings, catalog, queries, pokedex, notifier, client, fixtures, now)


def _run(db, settings, catalog, queries, pokedex, notifier, client, fixtures, now):
    run_id = None
    observed = 0
    alerted = 0
    notes = []
    paths = []
    try:
        run_id = db.start_run(now)
        db.sync_pokedex(pokedex)
        missing = missing_rates(pokedex)
        if fixtures is not None:
            raw_items = fixtures
        else:
            if not settings.delivery_postal_code:
                raise ValueError("Set delivery_postal_code before a live search")
            raw_items = discover(client, queries)
            # Fetch details only for the best preliminary candidates, or
            # plausible vintage lots whose title lacks a count.
            preliminary = [(evaluate(x, settings, catalog, missing, now), x) for x in raw_items]
            plausible = [
                (p, x)
                for p, x in preliminary
                if p.purity != "unknown" and (p.qualifying or p.count.denominator is None)
            ]
            plausible.sort(key=lambda pair: (pair[0].qualifying, pair[0].pokedex_score), reverse=True)
            if len(plausible) > settings.search.detail_limit:
                notes.append("Description enrichment cap reached; remaining items use title evidence")
            for _, raw in plausible[: settings.search.detail_limit]:
                detail = client.detail(raw["itemId"])
                raw.update(detail)
            notes += client.warnings
        # Fixture input can also contain duplicate IDs. Live discovery merges query metadata.
        unique = {}
        for raw in raw_items:
            key = raw["itemId"]
            old = unique.get(key, {})
            sources = set(old.get("_queries", [])) | set(raw.get("_queries", []))
            unique[key] = {**old, **raw, "_queries": sorted(sources)}
        due = []
        current = {}
        for raw in unique.values():
            listing = evaluate(raw, settings, catalog, missing, now)
            previous = db.observe(listing, now)
            observed += 1
            current[listing.ebay_item_id] = listing
            if db.due(listing, previous, settings, now):
                due.append(listing)
        db.expire(now)
        # Failed deliveries are retried only after rechecking current evidence.
        # A missed/expired/no-longer-cheap item is never sent from an old snapshot.
        pending = db.pending()
        candidates = {x.ebay_item_id: x for x in due}
        for row in pending:
            for item in json.loads(row["listings"]):
                listing = current.get(item["ebay_item_id"])
                if listing and listing.qualifying:
                    candidates[listing.ebay_item_id] = listing
        due = sorted(
            candidates.values(), key=lambda x: (-PRIORITIES[x.priority], -x.pokedex_score, x.ebay_item_id)
        )
        hits = due[: settings.alerts.max_hits]
        if hits:
            digest_id = (
                pending[0]["id"] if pending else now.strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
            )
            body = digest_text(hits, now, summary(pokedex))
            if fixtures is not None:
                body = "OFFLINE DEMO — synthetic examples, not live eBay offers\n\n" + body
            if pending:
                with db.conn:
                    db.conn.execute(
                        "UPDATE digests SET body=?,listings=? WHERE id=?",
                        (body, json.dumps([x.model_dump(mode="json") for x in hits]), digest_id),
                    )
            else:
                db.queue(digest_id, now, body, hits)
            paths.append(str(notifier.send(digest_id, body)))
            db.delivered(digest_id, now)
            alerted = len(hits)
        # Stale pending snapshots are never delivered; observations retain
        # their history. Unsent eligible candidates remain available next run.
        with db.conn:
            db.conn.execute("DELETE FROM digests WHERE delivered_at IS NULL")
        db.finish_run(
            run_id, now, "COMPLETED_WITH_WARNINGS" if notes else "COMPLETED", observed, alerted, notes
        )
        return {"observed": observed, "alerted": alerted, "reports": paths, "notes": notes}
    except BaseException as exc:
        # Interruptions propagate too, after recording the incomplete run if possible.
        failure("watcher_run_failed", exc)
        if run_id is not None:
            try:
                status = "FAILED" if isinstance(exc, Exception) else "INTERRUPTED"
                db.finish_run(run_id, now, status, observed, alerted, [type(exc).__name__])
            except Exception as write_error:
                failure("watcher_failure_status_write_failed", write_error)
        raise
