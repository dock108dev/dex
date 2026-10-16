"""Revisioned account-private drafts and minimal replay identities, outside copy exports."""

import json
import uuid
from datetime import timedelta

from django.db import connection
from django.http import Http404
from django.utils import timezone

from pokemon_hunter.migration import encode

from . import bulk_input, collection, store, transactions


class DraftError(ValueError):
    pass


def available():
    return "collection_drafts" in connection.introspection.table_names()


@transactions.atomic
def initialize():
    """Explicit additive operator migration. Never run from a page read/startup."""
    collection.execute("""CREATE TABLE IF NOT EXISTS collection_drafts(
        id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),schema TEXT NOT NULL,
        revision INTEGER NOT NULL,state TEXT NOT NULL,input_json TEXT NOT NULL,input_hashes TEXT NOT NULL,
        created_at TEXT NOT NULL,updated_at TEXT NOT NULL,expires_at TEXT NOT NULL,
        confirmed_operation_id TEXT,review_operation_id TEXT)""")
    collection.execute(
        "CREATE INDEX IF NOT EXISTS collection_drafts_account ON collection_drafts(user_id,state)"
    )
    collection.execute("""CREATE TABLE IF NOT EXISTS collection_replays(
        user_id TEXT NOT NULL REFERENCES users(id),fingerprint TEXT NOT NULL,draft_id TEXT NOT NULL,
        operation_id TEXT,PRIMARY KEY(user_id,fingerprint))""")


def timestamp():
    return timezone.now().isoformat()


def require_schema():
    if not available():
        raise DraftError("Manual bulk entry requires the additive enable-bulk operator migration")


def get(actor, key):
    store.verified(actor)
    require_schema()
    rows = store.rows("SELECT * FROM collection_drafts WHERE id=%s AND user_id=%s", [key, actor.user_id])
    if not rows:
        raise Http404
    result = rows[0]
    for field in ("input_json", "input_hashes"):
        result[field] = json.loads(result[field])
    if result["state"] not in {"confirmed", "cancelled", "expired"} and result["expires_at"] <= timestamp():
        # Reads do not renew leases or write tombstones. All mutation guards also check the lease.
        result["state"] = "expired"
    return result


def revision_check(draft, revision):
    if type(revision) is not int or revision != draft["revision"]:
        raise collection.Conflict("Draft changed in another tab; reload before editing or reviewing")


def mutable(draft, revision):
    revision_check(draft, revision)
    if draft["state"] not in {"editing", "ready", "previewed"}:
        raise collection.Conflict(
            "This draft is terminal; use its receipt or start a separate physical batch"
        )


def listed(actor):
    store.verified(actor)
    require_schema()
    return store.rows(
        """SELECT id,revision,state,created_at,updated_at,expires_at,confirmed_operation_id
        FROM collection_drafts WHERE user_id=%s ORDER BY updated_at DESC LIMIT 150""",
        [actor.user_id],
    )


@transactions.atomic
def save(actor, raw, key=None, revision=None, new_batch=False, batch_identity=None):
    store.verified(actor)
    require_schema()
    if type(new_batch) is not bool:
        raise ValueError("New physical batch must be explicit")
    data = bulk_input.envelope(raw)
    fp = bulk_input.fingerprint(data)
    if key:
        draft = get(actor, key)
        mutable(draft, revision)
    elif not new_batch:
        replay = store.rows(
            "SELECT draft_id FROM collection_replays WHERE user_id=%s AND fingerprint=%s", [actor.user_id, fp]
        )
        if replay:
            return get(actor, replay[0]["draft_id"])
    batch_key = None
    if new_batch and batch_identity is not None:
        try:
            batch_key = str(uuid.uuid5(uuid.NAMESPACE_URL, actor.user_id + str(uuid.UUID(batch_identity))))
        except (ValueError, TypeError, AttributeError):
            raise ValueError("Use a stable physical-batch UUID") from None
        existing = store.rows(
            "SELECT id FROM collection_drafts WHERE id=%s AND user_id=%s", [batch_key, actor.user_id]
        )
        if existing and key is None:
            prior = get(actor, batch_key)
            if prior["input_hashes"]["fingerprint"] != fp:
                raise collection.Conflict(
                    "This physical-batch identity already has different input; resume its revision"
                )
            return prior
    now = timestamp()
    expiry = (timezone.now() + timedelta(days=7)).isoformat()
    if key is None and not data["rows"]:
        # Empty workspaces must not collapse all future batches into one replay identity.
        new_batch = True
    if key is None:
        count = store.rows(
            """SELECT COUNT(*) AS n FROM collection_drafts WHERE user_id=%s
            AND state IN ('editing','ready','previewed') AND expires_at>%s""",
            [actor.user_id, now],
        )[0]["n"]
        if count >= 100:
            raise ValueError("At most 100 open drafts per account; cancel an existing draft")
        key = batch_key or str(uuid.uuid4())
        # New physical batch has a separate namespace; original file receipt mapping survives.
        namespace = key if new_batch else ""
        hashes = dict(fingerprint=fp, namespace=namespace, parser=bulk_input.SCHEMA)
        if isinstance(raw.get("text"), str):
            hashes["source_sha256"] = bulk_input.digest(raw["text"].encode("utf-8"))
        collection.execute(
            """INSERT INTO collection_drafts VALUES(%s,%s,%s,1,'editing',%s,%s,%s,%s,%s,NULL,NULL)""",
            [key, actor.user_id, bulk_input.SCHEMA, encode(data), encode(hashes), now, now, expiry],
        )
    else:
        # Original upload identities remain aliases of this explicitly edited draft and its final receipt.
        hashes = {**draft["input_hashes"], "fingerprint": fp}
        collection.execute(
            """UPDATE collection_drafts SET revision=revision+1,state='editing',input_json=%s,
            input_hashes=%s,updated_at=%s,expires_at=%s,review_operation_id=NULL WHERE id=%s AND user_id=%s""",
            [encode(data), encode(hashes), now, expiry, key, actor.user_id],
        )
    mapping = fp if not hashes["namespace"] else hashes["namespace"] + ":" + fp
    row_keys = ["row:" + bulk_input.digest(r["row_id"].encode()) for r in data["rows"]]
    if row_keys and not hashes["namespace"]:
        matches = store.rows(
            "SELECT draft_id FROM collection_replays WHERE user_id=%s AND fingerprint IN ("
            + ",".join(["%s"] * len(row_keys))
            + ")",
            [actor.user_id, *row_keys],
        )
        if any(r["draft_id"] != key for r in matches):
            raise collection.Conflict(
                "Source row identity already belongs to another input; resume it or explicitly start a new physical batch"
            )
    prior = store.rows(
        "SELECT draft_id FROM collection_replays WHERE user_id=%s AND fingerprint=%s",
        [actor.user_id, mapping],
    )
    if prior and prior[0]["draft_id"] != key:
        raise collection.Conflict("Equivalent input already belongs to another draft; resume that draft")
    collection.execute(
        """INSERT INTO collection_replays(user_id,fingerprint,draft_id) VALUES(%s,%s,%s)
        ON CONFLICT(user_id,fingerprint) DO NOTHING""",
        [actor.user_id, mapping, key],
    )
    if hashes["namespace"]:
        # Reupload without an explicit new-batch action recovers the first saved result for this input.
        collection.execute(
            "INSERT INTO collection_replays(user_id,fingerprint,draft_id) VALUES(%s,%s,%s) "
            "ON CONFLICT(user_id,fingerprint) DO NOTHING",
            [actor.user_id, fp, key],
        )
    if row_keys:
        for row_key in row_keys:
            collection.execute(
                "INSERT INTO collection_replays(user_id,fingerprint,draft_id) VALUES(%s,%s,%s) "
                "ON CONFLICT(user_id,fingerprint) DO NOTHING",
                [actor.user_id, row_key, key],
            )
    return get(actor, key)


def plan_input(actor, request):
    if set(request) != {"draft_id", "revision", "input_hash"}:
        raise ValueError("Bulk plans require a saved draft revision")
    draft = get(actor, request["draft_id"])
    mutable(draft, request["revision"])
    if request["input_hash"] != draft["input_hashes"]["fingerprint"]:
        raise collection.Conflict("Draft input changed; review again")
    from .photo_batches import draft_guard

    draft_guard(actor, draft)
    return draft, bulk_input.normalize(actor, draft["input_json"])


@transactions.atomic
def review(actor, key, revision):
    draft = get(actor, key)
    mutable(draft, revision)
    op = collection.preview(
        actor,
        "bulk",
        dict(draft_id=key, revision=revision, input_hash=draft["input_hashes"]["fingerprint"]),
        str(uuid.uuid5(uuid.NAMESPACE_URL, key + ":" + str(revision))),
    )
    state = "editing" if op["plan"]["errors"] else "previewed"
    collection.execute(
        "UPDATE collection_drafts SET state=%s,review_operation_id=%s WHERE id=%s AND user_id=%s",
        [state, op["id"], key, actor.user_id],
    )
    return dict(draft=get(actor, key), operation=op)


@transactions.atomic
def confirm(actor, key, revision):
    draft = get(actor, key)
    revision_check(draft, revision)
    if draft["state"] == "confirmed":
        return collection.operation(actor, draft["confirmed_operation_id"])
    mutable(draft, revision)
    if draft["state"] != "previewed" or not draft["review_operation_id"]:
        raise collection.Conflict("Explicit Review is required before confirmation")
    return collection.confirm(actor, draft["review_operation_id"])


def finish(actor, op):
    """Called inside collection confirmation's same transaction, including generic recovery endpoints."""
    draft = get(actor, op["request"]["draft_id"])
    mutable(draft, op["request"]["revision"])
    if draft["state"] != "previewed" or draft["review_operation_id"] != op["id"]:
        raise collection.Conflict("Review this exact draft before confirming")
    collection.execute(
        """UPDATE collection_drafts SET state='confirmed',confirmed_operation_id=%s
        WHERE id=%s AND user_id=%s""",
        [op["id"], draft["id"], actor.user_id],
    )
    from .photo_batches import finish as finish_photos

    finish_photos(actor, draft, op)
    # Original uploads and explicit edited revisions all recover the actual reviewed receipt.
    collection.execute(
        "UPDATE collection_replays SET operation_id=%s WHERE user_id=%s AND draft_id=%s",
        [op["id"], actor.user_id, draft["id"]],
    )


@transactions.atomic
def cancel(actor, key, revision):
    draft = get(actor, key)
    revision_check(draft, revision)
    if draft["state"] == "confirmed":
        return draft  # Committed confirmations are recovered; Undo is a separate explicit action.
    mutable(draft, revision)
    collection.execute(
        "UPDATE collection_drafts SET state='cancelled',revision=revision+1,input_json=%s WHERE id=%s AND user_id=%s",
        [encode(dict(schema=bulk_input.SCHEMA, rows=[], defaults={}, lot={})), key, actor.user_id],
    )
    from .photo_batches import cancel_draft_images

    cancel_draft_images(actor, key)
    return get(actor, key)


@transactions.atomic
def purge_expired():
    """Operator cleanup leaves minimal replay/tombstone history; never erases operations."""
    empty = encode(dict(schema=bulk_input.SCHEMA, rows=[], defaults={}, lot={}))
    collection.execute(
        """UPDATE collection_drafts SET state='expired',input_json=%s
        WHERE expires_at<=%s AND state IN ('editing','ready','previewed')""",
        [empty, timestamp()],
    )


@transactions.atomic
def purge_revoked():
    """Revocation cleanup erases mutable input but preserves minimal replay/operation history."""
    if not available():
        return
    empty = encode(dict(schema=bulk_input.SCHEMA, rows=[], defaults={}, lot={}))
    collection.execute(
        """UPDATE collection_drafts SET input_json=%s,
        state=CASE WHEN state='confirmed' THEN state ELSE 'cancelled' END,revision=revision+1
        WHERE state NOT IN ('cancelled','expired') AND user_id IN
        (SELECT u.id FROM users u JOIN auth_user a ON u.auth_subject=CAST(a.id AS TEXT)
         WHERE u.state<>'active' OR a.is_active=FALSE)""",
        [empty],
    )
