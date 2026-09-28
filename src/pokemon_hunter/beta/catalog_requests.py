"""Submitter-scoped requests and consent-limited reviewer evidence."""

import json
import time
import uuid

from django.core.exceptions import PermissionDenied
from django.http import Http404

from pokemon_hunter.migration import encode

from . import catalog_imports as catalogs
from . import collection as inv
from . import scans, store
from . import transactions as transaction
from .catalog_reconcile import request_set_id


def clean_hints(data):
    allowed = {"game", "set", "language", "name", "number", "variant"}
    if not isinstance(data, dict) or set(data) - allowed:
        raise ValueError("Unsupported hint fields")
    result = {k: data.get(k, "").strip() for k in allowed if isinstance(data.get(k, ""), str)}
    if len(result) != len(allowed) or any(len(v) > 160 for v in result.values()):
        raise ValueError("Use short text hints")
    return result


def submission(actor, key):
    store.verified(actor)
    rows = store.rows("SELECT * FROM catalog_submissions WHERE id=%s AND user_id=%s", [key, actor.user_id])
    if not rows:
        raise Http404
    return rows[0]


def origin(actor, kind, key):
    if kind == "scan":
        j = scans.job(actor, key)
        if j["state"] in {"queued", "processing", "cancelled"}:
            raise ValueError("Finish or review this scan first")
        return j.get("copy_id"), key
    if kind == "copy":
        c = inv.one(actor, "copy", key)
        if c["state"] != "active" or c["printing_id"]:
            raise ValueError("Choose an active provisional copy")
        job = json.loads(c["provisional_identity"] or "{}").get("scan_job")
        if job:
            scans.job(actor, job)
        return key, job
    raise ValueError("Choose a scan or provisional copy")


def copy_for(actor, s):
    if s["origin"] == "copy":
        rows = store.rows(
            "SELECT * FROM owned_copies WHERE id=%s AND user_id=%s", [s["origin_id"], actor.user_id]
        )
    else:
        rows = store.rows(
            "SELECT c.* FROM owned_copies c JOIN scan_jobs j ON j.copy_id=c.id WHERE j.id=%s AND c.user_id=%s",
            [s["origin_id"], actor.user_id],
        )
    return rows[0] if rows and rows[0]["state"] == "active" else None


@transaction.atomic
def create(actor, data):
    store.verified(actor)
    kind = data.get("origin")
    key = data.get("origin_id")
    origin(actor, kind, key)
    hints = clean_hints(data.get("hints", {}))
    share = data.get("share_photos", False)
    if type(share) is not bool:
        raise ValueError("Photo sharing must be explicit true or false")
    prior = store.rows(
        "SELECT id FROM catalog_submissions WHERE user_id=%s AND origin=%s AND origin_id=%s",
        [actor.user_id, kind, key],
    )
    if prior:
        return detail(actor, prior[0]["id"])
    if (
        store.rows(
            "SELECT count(*) AS n FROM catalog_submissions WHERE user_id=%s AND created>%s",
            [actor.user_id, time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time() - 86400))],
        )[0]["n"]
        >= 30
    ):
        raise ValueError("Daily request limit reached")
    reviewed = store.rows(
        "SELECT identity_key FROM catalog_aliases WHERE game=%s AND language=%s AND alias=%s",
        [hints["game"], hints["language"], catalogs.normalized(hints["set"])],
    )
    identity = reviewed[0]["identity_key"] if reviewed else None
    found = (
        store.rows("SELECT id FROM catalog_requests WHERE identity_key=%s", [identity]) if identity else []
    )
    rid = found[0]["id"] if found else str(uuid.uuid4())
    if not found:
        state = (
            "published"
            if identity
            and store.rows(
                "SELECT id FROM catalog_sets WHERE id=%s AND publication_state='published'",
                [request_set_id(identity)],
            )
            else "new"
        )
        inv.execute(
            "INSERT INTO catalog_requests(id,identity_key,state) VALUES(%s,%s,%s)", [rid, identity, state]
        )
    sid = str(uuid.uuid4())
    inv.execute(
        "INSERT INTO catalog_submissions(id,request_id,user_id,origin,origin_id,hints,share_photos) VALUES(%s,%s,%s,%s,%s,%s,%s)",
        [sid, rid, actor.user_id, kind, key, encode(hints), int(share)],
    )
    catalogs.audit(actor, "request-created", rid, {"submission": sid, "share_photos": share})
    return detail(actor, sid)


def proposed(actor, s):
    c = copy_for(actor, s)
    if not c or c["printing_id"]:
        return []
    hints = json.loads(s["hints"])
    request = store.rows("SELECT * FROM catalog_requests WHERE id=%s", [s["request_id"]])[0]
    key = request["identity_key"]
    if not key:
        return []
    sid = request_set_id(key)
    candidates = inv.catalog(actor, set_id=sid)
    # Never infer a card from a set alone. Owners can correct hints and search again.
    if not hints["name"] and not hints["number"]:
        return []
    return [
        {
            k: p[k]
            for k in (
                "id",
                "name",
                "collector_number",
                "set_name",
                "catalog_version",
                "edition",
                "finish",
                "variant",
                "unresolved_fields",
            )
        }
        for p in candidates
        if (not hints["name"] or catalogs.normalized(hints["name"]) == catalogs.normalized(p["name"]))
        and (not hints["number"] or hints["number"] == p["collector_number"])
        and (not hints["variant"] or hints["variant"] == p["variant"])
    ][:20]


def detail(actor, key):
    s = submission(actor, key)
    request = store.rows("SELECT * FROM catalog_requests WHERE id=%s", [s["request_id"]])[0]
    c = copy_for(actor, s)
    return {
        **s,
        "hints": json.loads(s["hints"]),
        "request": request,
        "copy": c,
        "candidates": proposed(actor, s),
        "operation": inv.operation(actor, s["resolution_op"]) if s["resolution_op"] else None,
    }


def mine(actor):
    store.verified(actor)
    return [
        detail(actor, s["id"])
        for s in store.rows(
            "SELECT id FROM catalog_submissions WHERE user_id=%s ORDER BY created DESC,id DESC",
            [actor.user_id],
        )
    ]


@transaction.atomic
def update(actor, key, data):
    s = submission(actor, key)
    hints = clean_hints(data.get("hints", json.loads(s["hints"])))
    share = data.get("share_photos", bool(s["share_photos"]))
    if type(share) is not bool:
        raise ValueError("Photo sharing must be explicit")
    inv.execute(
        "UPDATE catalog_submissions SET hints=%s,share_photos=%s WHERE id=%s",
        [encode(hints), int(share), key],
    )
    catalogs.audit(
        actor, "request-consent-hints", s["request_id"], {"submission": key, "share_photos": share}
    )
    return detail(actor, key)


@transaction.atomic
def resolve(actor, key, data):
    s = submission(actor, key)
    if s["resolution_op"]:
        return detail(actor, key)
    c = copy_for(actor, s)
    if not c or c["printing_id"] or c["revision"] != data.get("revision"):
        raise inv.Conflict("Copy changed; reload the proposal")
    if data.get("printing_id") not in {p["id"] for p in proposed(actor, s)}:
        raise inv.Conflict("Proposal no longer available; reload after catalog publication")
    op = inv.preview(
        actor, "resolve", {"id": c["id"], "revision": c["revision"], "printing_id": data["printing_id"]}, key
    )
    inv.confirm(actor, op["id"])
    inv.execute("UPDATE catalog_submissions SET resolution_op=%s WHERE id=%s", [op["id"], key])
    return detail(actor, key)


def review_list(actor):
    catalogs.admin(actor)
    requests = store.rows("SELECT * FROM catalog_requests ORDER BY id DESC")
    for r in requests:
        r["requesters"] = store.rows(
            "SELECT count(DISTINCT user_id) AS n FROM catalog_submissions WHERE request_id=%s", [r["id"]]
        )[0]["n"]
        r["submissions"] = []
        for s in store.rows("SELECT * FROM catalog_submissions WHERE request_id=%s", [r["id"]]):
            item = {
                "id": s["id"],
                "hints": json.loads(s["hints"]),
                "share_photos": bool(s["share_photos"]),
                "photos": [],
            }
            if s["share_photos"]:
                try:
                    owner = store.rows("SELECT auth_subject FROM users WHERE id=%s", [s["user_id"]])[0]
                    who = store.principal(owner["auth_subject"])
                    _, job = origin_for_evidence(who, s)
                    if job:
                        item["photos"] = scans.job(who, job)["photos"]
                except (
                    Http404,
                    ValueError,
                    PermissionDenied,
                ):
                    pass
            r["submissions"].append(item)
    return requests


def origin_for_evidence(actor, s):
    if s["origin"] == "scan":
        j = scans.job(actor, s["origin_id"])
        return j["copy_id"], j["id"]
    c = inv.one(actor, "copy", s["origin_id"])
    return c["id"], json.loads(c["provisional_identity"] or "{}").get("scan_job")


def shared_photo(actor, submission_id, photo_id):
    catalogs.admin(actor)
    rows = store.rows("SELECT * FROM catalog_submissions WHERE id=%s AND share_photos=1", [submission_id])
    if not rows:
        raise Http404
    s = rows[0]
    owner = store.rows("SELECT auth_subject FROM users WHERE id=%s", [s["user_id"]])[0]
    who = store.principal(owner["auth_subject"])
    cid, jid = origin_for_evidence(who, s)
    if cid and not store.rows(
        "SELECT id FROM owned_copies WHERE id=%s AND user_id=%s AND state='active'", [cid, who.user_id]
    ):
        raise Http404
    if not jid:
        raise Http404
    job = scans.job(who, jid)

    if (not job["operation_id"] and job["created"] < time.time() - 7 * 86400) or photo_id not in job[
        "photos"
    ]:
        raise Http404
    return bytes(
        store.rows(
            "SELECT content FROM scan_photos WHERE id=%s AND job_id=%s AND user_id=%s",
            [photo_id, jid, who.user_id],
        )[0]["content"]
    )


@transaction.atomic
def review(actor, key, data):
    catalogs.admin(actor)
    rows = store.rows("SELECT * FROM catalog_requests WHERE id=%s", [key])
    if not rows:
        raise Http404
    r = rows[0]
    if r["revision"] != data.get("revision"):
        raise inv.Conflict("Request changed; reload before reviewing")
    if r["merged_into"]:
        raise ValueError("Review the destination of this merged request")
    action = data.get("action")
    if action == "merge":
        target = store.rows("SELECT * FROM catalog_requests WHERE id=%s", [data.get("target")])
        if not target or target[0]["id"] == key or target[0]["merged_into"]:
            raise ValueError("Choose a different active destination request")
        target = target[0]
        inv.execute("UPDATE catalog_submissions SET request_id=%s WHERE request_id=%s", [target["id"], key])
        if r["identity_key"]:
            if not target["identity_key"]:
                inv.execute("UPDATE catalog_requests SET identity_key=NULL WHERE id=%s", [key])
                inv.execute(
                    "UPDATE catalog_requests SET identity_key=%s WHERE id=%s",
                    [r["identity_key"], target["id"]],
                )
            else:
                inv.execute(
                    "UPDATE catalog_aliases SET identity_key=%s WHERE identity_key=%s",
                    [target["identity_key"], r["identity_key"]],
                )
                inv.execute("UPDATE catalog_requests SET identity_key=NULL WHERE id=%s", [key])
        inv.execute(
            "UPDATE catalog_requests SET state='merged',merged_into=%s,revision=revision+1 WHERE id=%s",
            [target["id"], key],
        )
        inv.execute("UPDATE catalog_requests SET revision=revision+1 WHERE id=%s", [target["id"]])
    else:
        state = data.get("state")
        if state not in {"new", "needs-evidence", "ready", "ingesting", "verified", "rejected"}:
            raise ValueError("Choose a review state; published comes from the importer")
        decision = data.get("decision", "")
        if not isinstance(decision, str) or len(decision) > 1000:
            raise ValueError("Use a short decision")
        identity = r["identity_key"]
        if data.get("set_key"):
            identity = catalogs.identity(data.get("game"), data["set_key"], data.get("language"))
            conflict = store.rows(
                "SELECT id FROM catalog_requests WHERE identity_key=%s AND id<>%s", [identity, key]
            )
            if conflict:
                raise inv.Conflict(
                    "Canonical identity already has a request; merge into " + conflict[0]["id"]
                )
            if r["identity_key"] and r["identity_key"] != identity:
                raise inv.Conflict("Reviewed identities are stable; merge into a corrected request")
            aliases = data.get("aliases", [])
            if (
                not isinstance(aliases, list)
                or len(aliases) > 20
                or any(not isinstance(a, str) for a in aliases)
            ):
                raise ValueError("Use a short alias list")
            catalogs.aliases(
                {
                    "game": data["game"],
                    "set_key": data["set_key"],
                    "language": data["language"],
                    "set_name": data["set_key"],
                    "aliases": aliases,
                }
            )
        inv.execute(
            "UPDATE catalog_requests SET identity_key=%s,state=%s,decision=%s,revision=revision+1 WHERE id=%s",
            [identity, state, decision, key],
        )
    catalogs.audit(actor, "request-" + str(action), key, {k: v for k, v in data.items() if k != "revision"})
    return review_list(actor)
