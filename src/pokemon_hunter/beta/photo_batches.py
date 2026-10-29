"""Private photo/stage/crop associations. Collection writes use the shared bulk-entry service.

The independent, fsynced journal is authoritative for admissions, consumed attempts
and deletion tombstones when a database is recovered. It contains no pixels or clues.
"""

import json
import time
import uuid

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.http import Http404

from pokemon_hunter.inventory import stable_id
from pokemon_hunter.migration import encode

from . import (
    bulk_input,
    collection,
    collection_drafts,
    photo_batch_images,
    scan_config,
    store,
    transactions,
)
from . import photo_contracts as protocol
from .photo_batch_images import crop_bytes as crop_bytes
from .photo_batch_images import source as source
from .photo_batch_journal import append as append
from .photo_batch_journal import journal as journal
from .photo_batch_journal import journal_path as journal_path
from .photo_batch_journal import reservations as reservations
from .photo_batch_journal import tombstones as tombstones
from .photo_payload_cleanup import cleanup_payloads

TERMINAL = {"cancelled", "expired"}


def available():
    return not settings.STAGING and "scan_batches" in connection.introspection.table_names()


@transactions.atomic
def initialize():
    """Explicit local additive migration; never called by startup or reads."""
    if settings.STAGING or not collection_drafts.available() or not settings.B3_ENABLED:
        raise ValueError("Local scans and existing bulk migration are required")
    statements = [
        """CREATE TABLE IF NOT EXISTS scan_batches(
        id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),version TEXT NOT NULL,
        revision INTEGER NOT NULL,state TEXT NOT NULL,created REAL NOT NULL,draft_id TEXT,
        duplicates_reviewed INTEGER NOT NULL DEFAULT 0)""",
        """CREATE TABLE IF NOT EXISTS scan_batch_photos(
        id TEXT PRIMARY KEY,batch_id TEXT NOT NULL REFERENCES scan_batches(id),user_id TEXT NOT NULL,
        source_hash TEXT NOT NULL,source_bytes INTEGER NOT NULL,created REAL NOT NULL,
        revision INTEGER NOT NULL,reviewed INTEGER NOT NULL,content BLOB NOT NULL,
        proposal TEXT NOT NULL DEFAULT '{}',state TEXT NOT NULL,position INTEGER NOT NULL DEFAULT 0,
        UNIQUE(batch_id,source_hash))""",
        """CREATE TABLE IF NOT EXISTS scan_batch_crops(
        id TEXT PRIMARY KEY,photo_id TEXT NOT NULL REFERENCES scan_batch_photos(id),user_id TEXT NOT NULL,
        revision INTEGER NOT NULL,geometry TEXT NOT NULL,content BLOB NOT NULL,
        proposal TEXT NOT NULL DEFAULT '{}',row_json TEXT NOT NULL DEFAULT '{}',
        included INTEGER NOT NULL DEFAULT 0,retain INTEGER NOT NULL DEFAULT 0,
        decision TEXT NOT NULL DEFAULT '',copy_id TEXT,state TEXT NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS scan_batch_stages(
        id TEXT PRIMARY KEY,batch_id TEXT NOT NULL REFERENCES scan_batches(id),photo_id TEXT NOT NULL,
        user_id TEXT NOT NULL,stage TEXT NOT NULL,photo_revision INTEGER NOT NULL,
        session_key TEXT NOT NULL,state TEXT NOT NULL,created REAL NOT NULL,started REAL,
        allowance REAL NOT NULL,elapsed REAL,usage TEXT,error TEXT NOT NULL DEFAULT '')""",
        "CREATE INDEX IF NOT EXISTS scan_batch_account ON scan_batches(user_id,state)",
        "CREATE INDEX IF NOT EXISTS scan_batch_stage_queue ON scan_batch_stages(state,created)",
    ]
    for sql in statements:
        collection.execute(sql)


def get(actor, key):
    store.verified(actor)
    if not available():
        raise ValueError("Photo batches need the additive local enable-photo-batches migration")
    rows = store.rows("SELECT * FROM scan_batches WHERE id=%s AND user_id=%s", [str(key), actor.user_id])
    if not rows:
        raise Http404
    batch = rows[0]
    if batch["draft_id"]:
        d = collection_drafts.get(actor, batch["draft_id"])
        if d["state"] in {"cancelled", "expired"}:
            batch["state"] = "cancelled"
    if batch["id"] in tombstones():
        batch["state"] = "cancelled"
    if batch["created"] + 7 * 86400 <= time.time() and not batch["draft_id"]:
        batch["state"] = "expired"
    return batch


def mutable(actor, key, revision):
    batch = get(actor, key)
    if type(revision) is not int or batch["revision"] != revision:
        raise collection.Conflict("Photo batch changed. Reload before editing.")
    if batch["state"] != "editing" or batch["draft_id"]:
        raise collection.Conflict("Resume its shared review/receipt or start a separate physical batch")
    if store.rows(
        "SELECT id FROM scan_batch_stages WHERE batch_id=%s AND state IN ('queued','processing')", [key]
    ):
        raise collection.Conflict("Stop analysis before editing photos or crops")
    return batch


def bump(key):
    collection.execute("UPDATE scan_batches SET revision=revision+1,duplicates_reviewed=0 WHERE id=%s", [key])


@transactions.atomic
def create(actor, key):
    store.verified(actor)
    key = str(uuid.UUID(key))
    if not available():
        raise ValueError("Photo batches are unavailable; use manual bulk entry")
    if store.rows("SELECT id FROM scan_batches WHERE id=%s", [key]):
        return detail(actor, key)
    count = store.rows(
        "SELECT count(*) AS n FROM scan_batches WHERE user_id=%s AND state='editing' AND created>%s",
        [actor.user_id, time.time() - 7 * 86400],
    )[0]["n"]
    if count >= 100:
        raise ValueError("Cancel an existing photo batch first")
    collection.execute(
        "INSERT INTO scan_batches(id,user_id,version,revision,state,created) VALUES(%s,%s,%s,1,'editing',%s)",
        [key, actor.user_id, protocol.VERSION, time.time()],
    )
    return detail(actor, key)


def photo(actor, batch_id, key):
    batch = get(actor, batch_id)
    rows = store.rows(
        "SELECT * FROM scan_batch_photos WHERE id=%s AND batch_id=%s AND user_id=%s",
        [str(key), batch_id, actor.user_id],
    )
    if not rows or rows[0]["state"] != "active" or batch["state"] in TERMINAL or str(key) in tombstones():
        raise Http404
    if rows[0]["created"] + 7 * 86400 <= time.time() or not rows[0]["content"]:
        raise Http404
    return rows[0]


def recent_admissions(actor):
    since = time.time() - 86400
    count = store.rows(
        "SELECT count(*) AS n FROM scan_photos p JOIN scan_jobs j ON p.job_id=j.id WHERE j.user_id=%s AND j.created>%s",
        [actor.user_id, since],
    )[0]["n"]
    # Deleted single-job photos must still count, including old jobs without photos.
    count = max(
        count,
        store.rows(
            "SELECT count(*) AS n FROM scan_jobs WHERE user_id=%s AND created>%s", [actor.user_id, since]
        )[0]["n"],
    )
    if available():
        records = journal()
        singles = {
            r["job_id"]: r["count"]
            for r in records
            if r["event"] == "single_admit" and r["user_id"] == actor.user_id and r["at"] > since
        }
        legacy = store.rows(
            "SELECT id FROM scan_jobs WHERE user_id=%s AND created>%s", [actor.user_id, since]
        )
        # Count each existing source, preserving new two-image admissions after deletion.
        job_counts = {
            r["id"]: max(
                1, store.rows("SELECT count(*) AS n FROM scan_photos WHERE job_id=%s", [r["id"]])[0]["n"]
            )
            for r in legacy
        }
        job_counts.update(singles)
        count = sum(job_counts.values())
        photos = {
            r["photo_id"]
            for r in records
            if r["event"] == "admit" and r["user_id"] == actor.user_id and r["at"] > since
        }
        photos.update(
            r["id"]
            for r in store.rows(
                "SELECT id FROM scan_batch_photos WHERE user_id=%s AND created>%s", [actor.user_id, since]
            )
        )
        count += len(photos)
    return count


@transactions.atomic
def admit(actor, key, revision, upload):
    mutable(actor, key, revision)
    content, digest, size = source(upload)
    prior = store.rows(
        "SELECT id,batch_id FROM scan_batch_photos WHERE user_id=%s AND source_hash=%s",
        [actor.user_id, digest],
    )
    if prior:
        return detail(
            actor, prior[0]["batch_id"]
        )  # Repeat admission never dispatches, consumes or revives a deletion.
    if any(
        r["event"] == "admit" and r["user_id"] == actor.user_id and r.get("source_hash") == digest
        for r in journal()
    ):
        raise ValueError(
            "This photo was already admitted; recover its existing photo batch without resubmission"
        )
    records = [r for r in journal() if r["event"] == "admit" and r["batch_id"] == key]
    existing = store.rows("SELECT id,source_bytes FROM scan_batch_photos WHERE batch_id=%s", [key])
    sizes = {r["photo_id"]: r["source_bytes"] for r in records}
    sizes.update({r["id"]: r["source_bytes"] for r in existing})
    if len(sizes) >= 5 or sum(sizes.values()) + size > 40_000_000:
        raise ValueError("Five admissions including retakes and 40 MB per batch maximum")
    if recent_admissions(actor) >= 20:
        raise ValueError("Shared limit of 20 source photos per account per 24 hours reached")
    pid = str(uuid.uuid4())
    append("admit", user_id=actor.user_id, batch_id=key, photo_id=pid, source_bytes=size, source_hash=digest)
    collection.execute(
        "INSERT INTO scan_batch_photos(id,batch_id,user_id,source_hash,source_bytes,created,revision,reviewed,content,state) VALUES(%s,%s,%s,%s,%s,%s,1,0,%s,'active')",
        [pid, key, actor.user_id, digest, size, time.time(), content],
    )
    collection.execute("UPDATE scan_batch_photos SET position=%s WHERE id=%s", [len(sizes), pid])
    bump(key)
    return detail(actor, key)


@transactions.atomic
def retake(actor, key, revision, pid, upload, same_objects):
    mutable(actor, key, revision)
    old = photo(actor, key, pid)
    if same_objects is not True:
        raise ValueError("Confirm this retake shows the same physical objects, or stage it separately")
    prior = {r["id"] for r in store.rows("SELECT id FROM scan_batch_photos WHERE batch_id=%s", [key])}
    updated = admit(actor, key, revision, upload)
    if updated["id"] != key:
        return updated
    new = [p for p in updated["photos"] if p["id"] not in prior]
    if not new:
        return updated  # Hash replay cannot move/erase any original associations.
    replacement = photo(actor, key, new[0]["id"])
    for c in store.rows("SELECT * FROM scan_batch_crops WHERE photo_id=%s AND state='active'", [pid]):
        content = crop_bytes(bytes(replacement["content"]), json.loads(c["geometry"]))
        collection.execute(
            "UPDATE scan_batch_crops SET photo_id=%s,revision=revision+1,content=%s,proposal='{}',row_json='{}',included=0,retain=0,decision='' WHERE id=%s",
            [replacement["id"], content, c["id"]],
        )
    collection.execute(
        "UPDATE scan_batch_photos SET position=%s WHERE id=%s", [old["position"], replacement["id"]]
    )
    delete_photo(pid)
    return detail(actor, key)


@transactions.atomic
def reorder(actor, key, revision, photo_ids):
    mutable(actor, key, revision)
    current = {
        p["id"]
        for p in store.rows("SELECT id FROM scan_batch_photos WHERE batch_id=%s AND state='active'", [key])
    }
    if not isinstance(photo_ids, list) or len(photo_ids) != len(current) or set(photo_ids) != current:
        raise ValueError("Order every active photo exactly once")
    for i, pid in enumerate(photo_ids):
        collection.execute("UPDATE scan_batch_photos SET position=%s WHERE id=%s", [i, pid])
    bump(key)
    return detail(actor, key)


@transactions.atomic
def layout(actor, key, revision, pid, boxes):
    mutable(actor, key, revision)
    p = photo(actor, key, pid)
    if not isinstance(boxes, list) or not 1 <= len(boxes) <= 15:
        raise ValueError("Review between 1 and 15 cards. A 16th requires a retake.")
    # IDs belong to this source/revision. Edits invalidate proposals and selected identities.
    old = {
        r["id"]: r
        for r in store.rows("SELECT * FROM scan_batch_crops WHERE photo_id=%s AND state='active'", [pid])
    }
    checked, ids = [], set()
    for raw in boxes:
        if not isinstance(raw, dict) or set(raw) != {"id", "box"}:
            raise ValueError("Use crop ID and geometry")
        cid = str(uuid.UUID(raw["id"])) if raw["id"] else str(uuid.uuid4())
        if cid in ids or (raw["id"] and cid not in old):
            raise ValueError("Unexpected/repeated crop ID")
        ids.add(cid)
        box = protocol.Box.model_validate(raw["box"]).model_dump()
        checked.append((cid, box, crop_bytes(bytes(p["content"]), box)))
    for cid in old:
        if cid not in ids:
            append("delete", object_id=cid)
            collection.execute(
                "UPDATE scan_batch_crops SET state='deleted',content=%s,proposal='{}',row_json='{}' WHERE id=%s",
                [b"", cid],
            )
    for cid, box, content in checked:
        if cid in old:
            collection.execute(
                "UPDATE scan_batch_crops SET revision=revision+1,geometry=%s,content=%s,proposal='{}',row_json='{}',included=0,retain=0,decision='' WHERE id=%s",
                [encode(box), content, cid],
            )
        else:
            collection.execute(
                "INSERT INTO scan_batch_crops(id,photo_id,user_id,revision,geometry,content,state) VALUES(%s,%s,%s,1,%s,%s,'active')",
                [cid, pid, actor.user_id, encode(box), content],
            )
    collection.execute("UPDATE scan_batch_photos SET revision=revision+1,reviewed=1 WHERE id=%s", [pid])
    bump(key)
    return detail(actor, key)


@transactions.atomic
def select_crop(actor, key, revision, cid, row, included, retain, decision):
    mutable(actor, key, revision)
    crops = store.rows(
        "SELECT c.* FROM scan_batch_crops c JOIN scan_batch_photos p ON c.photo_id=p.id WHERE c.id=%s AND c.user_id=%s AND p.batch_id=%s AND p.state='active' AND c.state='active'",
        [cid, actor.user_id, key],
    )
    if not crops:
        raise Http404
    photo(actor, key, crops[0]["photo_id"])
    if (
        type(included) is not bool
        or type(retain) is not bool
        or decision not in {"different", "same", "unsure", ""}
    ):
        raise ValueError("Explicit inclusion, retention and physical-copy decision required")
    if included and decision != "different":
        raise ValueError(
            "Only reviewed distinct physical copies may be included; exclude same/uncertain cards"
        )
    if not isinstance(row, dict) or set(row) & {
        "row_id",
        "quantity",
        "action",
        "included",
        "duplicate_decision",
    }:
        raise ValueError("One physical copy per crop; identity/copy attributes only")
    data = dict(
        row, row_id=cid, quantity=1, action="add_copies", included=included, duplicate_decision="different"
    )
    normalized = bulk_input.normalize(actor, bulk_input.envelope(dict(rows=[data])))["rows"][0]
    if included and normalized["errors"]:
        raise ValueError("Choose an actual catalog identity or supported unknown variant")
    collection.execute(
        "UPDATE scan_batch_crops SET row_json=%s,included=%s,retain=%s,decision=%s WHERE id=%s",
        [encode(data), int(included), int(retain and included), decision, cid],
    )
    bump(key)
    return detail(actor, key)


@transactions.atomic
def analyze(actor, key, revision, pid, stage, session_key, consent, notes=""):
    """Old clients receive an explicit unavailable response; no work is admitted."""
    get(actor, key)
    scan_config.require_recognition()


def process_one(stop=None, *, selected_only=False):
    """Retire old AI work without erasing photos, reviews or consumed reservations."""
    if not available():
        return False
    with transactions.atomic():
        collection.execute(
            "UPDATE scan_batch_stages SET state='cancelled',error=%s WHERE state IN ('queued','processing')",
            [scan_config.UNAVAILABLE],
        )
    return False


@transactions.atomic
def stop_analysis(actor, key):
    get(actor, key)
    # Stop is independent of revision and ordinary busy controls; it is never a resend.
    collection.execute(
        "UPDATE scan_batch_stages SET state='cancelled',error='Stopped; attempts remain consumed' WHERE batch_id=%s AND state IN ('queued','processing')",
        [key],
    )
    return detail(actor, key)


@transactions.atomic
def remove_photo(actor, key, revision, pid):
    mutable(actor, key, revision)
    photo(actor, key, pid)
    delete_photo(pid)
    bump(key)
    return detail(actor, key)


def delete_crop(cid):
    if cid not in tombstones():
        append("delete", object_id=cid)
    collection.execute(
        "UPDATE scan_batch_crops SET state='deleted',content=%s,proposal='{}',row_json='{}',retain=0 WHERE id=%s",
        [b"", cid],
    )


def delete_photo(pid):
    if pid not in tombstones():
        append("delete", object_id=pid)
    for c in store.rows("SELECT id FROM scan_batch_crops WHERE photo_id=%s AND state<>'retained'", [pid]):
        delete_crop(c["id"])
    collection.execute(
        "UPDATE scan_batch_photos SET state='deleted',content=%s,proposal='{}' WHERE id=%s", [b"", pid]
    )


@transactions.atomic
def cancel(actor, key):
    b = get(actor, key)
    if b["draft_id"]:
        d = collection_drafts.get(actor, b["draft_id"])
        if d["state"] == "confirmed":
            raise ValueError("Use the existing receipt's Undo for a confirmed batch")
        if d["state"] not in {"cancelled", "expired"}:
            collection_drafts.cancel(actor, d["id"], d["revision"])
    stop_analysis(actor, key)
    if key not in tombstones():
        append("delete", object_id=key)
    for p in store.rows("SELECT id FROM scan_batch_photos WHERE batch_id=%s", [key]):
        delete_photo(p["id"])
    collection.execute("UPDATE scan_batches SET state='cancelled',revision=revision+1 WHERE id=%s", [key])
    return detail(actor, key)


@transactions.atomic
def delete_images(actor, key):
    get(actor, key)
    stop_analysis(actor, key)
    for c in store.rows(
        "SELECT c.id FROM scan_batch_crops c JOIN scan_batch_photos p ON c.photo_id=p.id WHERE p.batch_id=%s",
        [key],
    ):
        delete_crop(c["id"])
    for p in store.rows("SELECT id FROM scan_batch_photos WHERE batch_id=%s", [key]):
        delete_photo(p["id"])
    return detail(actor, key)


def cancel_draft_images(actor, draft_id):
    if not available():
        return
    for b in store.rows(
        "SELECT id FROM scan_batches WHERE draft_id=%s AND user_id=%s AND state<>'confirmed'",
        [draft_id, actor.user_id],
    ):
        if b["id"] not in tombstones():
            append("delete", object_id=b["id"])
        delete_images(actor, b["id"])
        collection.execute("UPDATE scan_batches SET state='cancelled' WHERE id=%s", [b["id"]])


@transactions.atomic
def handoff(actor, key, revision, duplicates_reviewed, manual_rows):
    b = get(actor, key)
    if b["draft_id"]:
        return dict(draft=collection_drafts.get(actor, b["draft_id"]), batch=detail(actor, key))
    mutable(actor, key, revision)
    if duplicates_reviewed is not True:
        raise ValueError("Review physical-card duplicates across every photo and manual row")
    photos = store.rows("SELECT * FROM scan_batch_photos WHERE batch_id=%s AND state='active'", [key])
    if not photos or any(not p["reviewed"] for p in photos):
        raise ValueError("Review the count and layout of every photo")
    crops = store.rows(
        "SELECT c.* FROM scan_batch_crops c JOIN scan_batch_photos p ON c.photo_id=p.id WHERE p.batch_id=%s AND p.state='active' AND c.state='active' ORDER BY c.id",
        [key],
    )
    if not 1 <= len(crops) <= 75 or any(c["decision"] not in {"different", "same", "unsure"} for c in crops):
        raise ValueError("Every crop needs an inclusion and physical-copy decision")
    for p in photos:
        photo(actor, key, p["id"])
    rows = []
    for c in crops:
        r = json.loads(c["row_json"])
        if c["included"] and (not r or c["decision"] != "different"):
            raise ValueError("Included crops need a human catalog choice and distinct-copy decision")
        rows.append(r or dict(row_id=c["id"], included=False))
    if not isinstance(manual_rows, list) or len(manual_rows) + len(rows) > 75:
        raise ValueError("At most 75 candidate physical cards including manual rows")
    # Manual entries are explicit separate physical objects, or excluded duplicates of crops.
    for r in manual_rows:
        if (
            r.get("row_id") in {c["id"] for c in crops}
            or r.get("quantity", 1) != 1
            or r.get("action", "add_copies") != "add_copies"
        ):
            raise ValueError("Each manual row must identify one distinct physical card")
        if r.get("included", True) and r.get("duplicate_decision") != "different":
            raise ValueError("Review manual-row physical duplicates too")
    data = bulk_input.envelope(dict(rows=rows + manual_rows))
    norm = bulk_input.normalize(actor, data)
    if any(r["included"] and r["errors"] for r in norm["rows"]) or not any(
        r["included"] for r in norm["rows"]
    ):
        raise ValueError("Resolve included identities before shared review")
    d = collection_drafts.save(actor, data, new_batch=True, batch_identity=key)
    collection.execute(
        "UPDATE scan_batches SET draft_id=%s,state='review',revision=revision+1,duplicates_reviewed=1 WHERE id=%s",
        [d["id"], key],
    )
    return dict(draft=d, batch=detail(actor, key))


def draft_guard(actor, draft):
    """Shared bulk Review/Confirm also calls this check, preventing endpoint bypass."""
    if not available():
        return None
    rows = store.rows(
        "SELECT id FROM scan_batches WHERE draft_id=%s AND user_id=%s", [draft["id"], actor.user_id]
    )
    if not rows:
        return None
    b = get(actor, rows[0]["id"])
    if b["state"] != "review" or not b["duplicates_reviewed"]:
        raise collection.Conflict("Photo batch is cancelled or unavailable")
    crops = store.rows(
        "SELECT c.* FROM scan_batch_crops c JOIN scan_batch_photos p ON c.photo_id=p.id WHERE p.batch_id=%s AND c.state='active' AND p.state='active'",
        [b["id"]],
    )
    # A copy crop can only bind to its stable, single-quantity bulk source row.
    for c in crops:
        photo(actor, b["id"], c["photo_id"])
    if time.time() >= b["created"] + 7 * 86400:
        raise collection.Conflict("Photo batch expired; start a new manual batch")
    by_id = {c["id"]: c for c in crops}
    for r in draft["input_json"]["rows"]:
        if r.get("included", True):
            if (
                r.get("quantity", 1) not in {1, "1"}
                or r.get("action", "add_copies") != "add_copies"
                or r.get("duplicate_decision") != "different"
            ):
                raise collection.Conflict(
                    "Photo review rows must each remain one reviewed distinct physical card"
                )
            if r["row_id"] in by_id and not by_id[r["row_id"]]["included"]:
                raise collection.Conflict("Reinclude an excluded crop in photo review first")
    if len(draft["input_json"]["rows"]) > 75:
        raise ValueError("At most 75 photo/manual candidate cards")
    final_rows = {r["row_id"]: r for r in draft["input_json"]["rows"]}
    return dict(
        batch_id=b["id"],
        version=protocol.VERSION,
        excluded_crops=[
            c["id"]
            for c in crops
            if not c["included"] or not final_rows.get(c["id"], {}).get("included", False)
        ],
        retained_crops=[
            c["id"] for c in crops if c["retain"] and final_rows.get(c["id"], {}).get("included", False)
        ],
        physical_duplicates_reviewed=True,
    )


def finish(actor, draft, op):
    summary = draft_guard(actor, draft)
    if not summary:
        return
    for c in store.rows(
        "SELECT c.* FROM scan_batch_crops c JOIN scan_batch_photos p ON c.photo_id=p.id WHERE p.batch_id=%s AND c.state='active'",
        [summary["batch_id"]],
    ):
        cid = stable_id("b2-copy", f"{actor.user_id}:{op['id']}:{c['id']}:0")
        found = store.rows(
            "SELECT id FROM owned_copies WHERE id=%s AND user_id=%s AND state='active'", [cid, actor.user_id]
        )
        if c["retain"] and c["included"] and found:
            collection.execute(
                "UPDATE scan_batch_crops SET copy_id=%s,state='retained',proposal='{}',row_json='{}' WHERE id=%s",
                [cid, c["id"]],
            )
        else:
            delete_crop(c["id"])
    for p in store.rows("SELECT id FROM scan_batch_photos WHERE batch_id=%s", [summary["batch_id"]]):
        delete_photo(p["id"])
    collection.execute("UPDATE scan_batches SET state='confirmed' WHERE id=%s", [summary["batch_id"]])


def authorized_photo_rows(actor, key=None, content=False, *, copy_ids=None):
    if not available():
        return []
    store.verified(actor)
    if copy_ids is not None and (not copy_ids or len(copy_ids) > 100):
        return []
    deleted = tombstones()
    rows = store.rows(
        "SELECT c.id,c.copy_id,"
        + ("c.content," if content else "")
        + "c.state,c.photo_id,p.batch_id,p.created,b.state AS batch_state FROM scan_batch_crops c JOIN scan_batch_photos p ON c.photo_id=p.id JOIN scan_batches b ON p.batch_id=b.id WHERE c.user_id=%s AND p.user_id=%s AND b.user_id=%s AND LENGTH(c.content)>0 AND c.state IN ('active','retained')"
        + (" AND c.id=%s" if key else "")
        + (" AND c.copy_id IN (" + ",".join(["%s"] * len(copy_ids)) + ")" if copy_ids is not None else ""),
        [actor.user_id] * 3 + ([str(key)] if key else []) + (list(copy_ids) if copy_ids is not None else []),
    )
    result = []
    for c in rows:
        if c["id"] in deleted or c["batch_id"] in deleted:
            continue
        if c["state"] == "retained":
            if not store.rows(
                "SELECT id FROM owned_copies WHERE id=%s AND user_id=%s AND state='active'",
                [c["copy_id"], actor.user_id],
            ):
                continue
        elif (
            get(actor, c["batch_id"])["state"] in TERMINAL
            or c["created"] + 7 * 86400 <= time.time()
            or c["photo_id"] in deleted
            or c["batch_state"] in TERMINAL
        ):
            continue
        result.append({k: c[k] for k in (("id", "copy_id", "content") if content else ("id", "copy_id"))})
    store.verified(actor)
    return result


def revoke_inactive_crops():
    if not available():
        return
    for c in store.rows(
        "SELECT c.id FROM scan_batch_crops c WHERE c.state='retained' AND NOT EXISTS(SELECT 1 FROM owned_copies o WHERE o.id=c.copy_id AND o.user_id=c.user_id AND o.state='active')"
    ):
        delete_crop(c["id"])


@transactions.atomic
def cleanup():
    if not available():
        return
    cleanup_payloads(settings.ROOT)
    deleted = tombstones()
    for key in deleted:
        collection.execute("UPDATE scan_batches SET state='cancelled' WHERE id=%s", [key])
        collection.execute(
            "UPDATE scan_batch_photos SET state='deleted',content=%s,proposal='{}' WHERE id=%s", [b"", key]
        )
        collection.execute(
            "UPDATE scan_batch_crops SET state='deleted',content=%s,proposal='{}',row_json='{}' WHERE id=%s",
            [b"", key],
        )
    for p in store.rows(
        "SELECT id FROM scan_batch_photos WHERE state='active' AND created<=%s", [time.time() - 7 * 86400]
    ):
        delete_photo(p["id"])
    collection.execute(
        "UPDATE scan_batch_stages SET state='failed',error='Unstarted reservation expired; continue manually' WHERE state='queued' AND created<%s",
        [time.time() - 80],
    )
    # Lost reservations remain charged in the journal. Existing claims are never retried.
    collection.execute(
        "UPDATE scan_batch_stages SET state='failed',error='Worker interrupted; reservation consumed. Continue manually.' WHERE state='processing' AND started<%s",
        [time.time() - 80],
    )
    for b in store.rows(
        "SELECT b.*,u.auth_subject FROM scan_batches b JOIN users u ON b.user_id=u.id WHERE b.state NOT IN ('cancelled','expired')"
    ):
        try:
            a = store.principal(int(b["auth_subject"]))
            revoked = False
        except PermissionDenied:
            a = None
            revoked = True
        draft = collection_drafts.get(a, b["draft_id"]) if a and b["draft_id"] else None
        expired = b["created"] + 7 * 86400 <= time.time() and b["state"] != "confirmed"
        if revoked or expired or (draft and draft["state"] in {"cancelled", "expired"}):
            if b["id"] not in tombstones():
                append("delete", object_id=b["id"])
            for c in store.rows(
                "SELECT c.id FROM scan_batch_crops c JOIN scan_batch_photos p ON c.photo_id=p.id WHERE p.batch_id=%s",
                [b["id"]],
            ):
                delete_crop(c["id"])
            for p in store.rows("SELECT id FROM scan_batch_photos WHERE batch_id=%s", [b["id"]]):
                delete_photo(p["id"])
            collection.execute(
                "UPDATE scan_batches SET state=%s WHERE id=%s",
                ["expired" if expired else "cancelled", b["id"]],
            )
            collection.execute(
                "UPDATE scan_batch_stages SET state='cancelled' WHERE batch_id=%s AND state IN ('queued','processing')",
                [b["id"]],
            )
    revoke_inactive_crops()


def candidates(actor, clue):
    from .photo_matching import matches

    return matches(clue, collection.catalog(actor))


def possible_duplicates(crops):
    # Storage reads stay with the service; image helpers receive only explicit bytes.
    hashes = {}
    for c in crops:
        if c["state"] != "active":
            continue
        row = store.rows("SELECT content FROM scan_batch_crops WHERE id=%s", [c["id"]])
        if row and row[0]["content"]:
            hashes[c["id"]] = photo_batch_images.perceptual_hash(bytes(row[0]["content"]))
    return photo_batch_images.duplicate_pairs(crops, hashes)


def detail(actor, key):
    b = get(actor, key)
    photos = store.rows(
        "SELECT id,revision,reviewed,source_bytes,created,state,proposal,position FROM scan_batch_photos WHERE batch_id=%s ORDER BY position,created,id",
        [key],
    )
    crops = store.rows(
        "SELECT c.id,c.photo_id,c.revision,c.geometry,c.proposal,c.row_json,c.included,c.retain,c.decision,c.copy_id,c.state FROM scan_batch_crops c JOIN scan_batch_photos p ON c.photo_id=p.id WHERE p.batch_id=%s ORDER BY c.photo_id,c.id",
        [key],
    )
    for p in photos:
        p["proposal"] = json.loads(p["proposal"])
    for c in crops:
        for field in ("geometry", "proposal", "row_json"):
            c[field] = json.loads(c[field])
        c["candidates"] = candidates(actor, c["proposal"])
    stages = store.rows(
        "SELECT id,photo_id,stage,photo_revision,state,allowance,elapsed,usage,error FROM scan_batch_stages WHERE batch_id=%s ORDER BY created",
        [key],
    )
    attempts = reservations(key)
    admissions = {
        r["photo_id"]: r["source_bytes"] for r in journal() if r["event"] == "admit" and r["batch_id"] == key
    }
    admissions.update({p["id"]: p["source_bytes"] for p in photos})
    for p in photos:
        own = [a for a in attempts.values() if a["photo_id"] == p["id"]]
        p["remaining_active_seconds"] = max(0, 75 - sum(a["charged"] for a in own))
        p["stage_attempts"] = {
            stage: sum(a["stage"] == stage for a in own) for stage in ("detection", "identity", "photo")
        }
    return dict(
        **b,
        recognition_enabled=scan_config.recognition_enabled(),
        source_admissions=len(admissions),
        source_bytes_used=sum(admissions.values()),
        photos=photos,
        crops=crops,
        stages=stages,
        possible_duplicates=possible_duplicates(crops),
        attempts=len(attempts),
        remaining_active_seconds=max(0, 180 - sum(r["charged"] for r in attempts.values())),
        remaining_capacity=None,
        cost_usd=None,
        model=None,
    )


@transactions.atomic
def confirm_cards(actor, key, revision, choices):
    """One user confirmation of the displayed cards; shared plan, policy and receipt remain authoritative."""
    b = get(actor, key)
    if b["draft_id"]:
        d = collection_drafts.get(actor, b["draft_id"])
        if d["state"] == "confirmed":
            return collection.operation(actor, d["confirmed_operation_id"])
        raise collection.Conflict("Resume the existing review before changing this batch")
    mutable(actor, key, revision)
    crops = store.rows(
        "SELECT c.id FROM scan_batch_crops c JOIN scan_batch_photos p ON c.photo_id=p.id WHERE p.batch_id=%s AND p.state='active' AND c.state='active'",
        [key],
    )
    ids = {c["id"] for c in crops}
    if (
        not isinstance(choices, list)
        or not 1 <= len(choices) <= 75
        or any(not isinstance(c, dict) or set(c) != {"id", "included", "row"} for c in choices)
        or len(choices) != len(ids)
        or {c["id"] for c in choices} != ids
    ):
        raise ValueError("Review every identified card exactly once")
    for c in choices:
        b = select_crop(
            actor,
            key,
            b["revision"],
            c["id"],
            c["row"],
            c["included"],
            False,
            "different" if c["included"] else "unsure",
        )
    # The displayed card review replaces a separate mandatory geometry/count form.
    collection.execute("UPDATE scan_batch_photos SET reviewed=1 WHERE batch_id=%s AND state='active'", [key])
    draft = handoff(actor, key, b["revision"], True, [])["draft"]
    prepared = collection_drafts.review(actor, draft["id"], draft["revision"])
    if prepared["operation"]["plan"]["errors"]:
        raise ValueError("Correct the selected card identities before adding")
    return collection_drafts.confirm(actor, draft["id"], draft["revision"])
