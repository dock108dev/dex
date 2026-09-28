"""Single ownership boundary for HTTP, file bytes, export and future worker execution."""

import json
from dataclasses import dataclass

from django.core.exceptions import PermissionDenied
from django.db import connection
from django.http import Http404

from pokemon_hunter.migration import vintage_progress


@dataclass(frozen=True)
class Principal:
    subject: int
    user_id: str
    role: str


def rows(sql, params=()):
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        return [dict(zip([c[0] for c in cursor.description], r, strict=True)) for r in cursor.fetchall()]


def principal(subject):
    found = rows(
        """SELECT u.id,u.role FROM users u JOIN auth_user a
                    ON u.auth_subject=CAST(a.id AS TEXT)
                    WHERE a.id=%s AND a.is_active=TRUE AND u.state='active'""",
        [subject],
    )
    if not found:
        raise PermissionDenied
    return Principal(subject, found[0]["id"], found[0]["role"])


def verified(actor):
    # Re-resolve at every operation; a queued actor cannot retain revoked privileges.
    current = principal(actor.subject)
    if current != actor:
        raise PermissionDenied
    return current


def collection(actor):
    actor = verified(actor)
    return rows(
        """SELECT c.*,p.collector_number,p.edition,p.unresolved_fields,p.attributes
                   FROM owned_copies c LEFT JOIN printings p ON p.id=c.printing_id
                   WHERE c.user_id=%s ORDER BY c.id""",
        [actor.user_id],
    )


def progress(copies):
    return vintage_progress(
        {
            r["id"]: {**json.loads(r["attributes"] or "{}"), "owned": True}
            for r in copies
            if r["state"] == "active"
        }
    )


def resource(actor, kind, key):
    actor = verified(actor)
    if kind == "inventory":
        found = rows("SELECT * FROM owned_copies WHERE id=%s AND user_id=%s", [key, actor.user_id])
    elif kind == "hunts":
        found = rows(
            "SELECT * FROM saved_hunts WHERE batch_id=%s AND legacy_id=%s AND user_id=%s",
            [key[0], key[1], actor.user_id],
        )
    elif kind == "archives":
        found = rows(
            "SELECT * FROM private_archives WHERE batch_id=%s AND path=%s AND user_id=%s",
            [key[0], key[1], actor.user_id],
        )
    elif kind in {"photos", "scan_jobs", "goals", "request_evidence"}:
        found = rows(
            "SELECT * FROM b1_private_resources WHERE id=%s AND kind=%s AND user_id=%s",
            [key, kind, actor.user_id],
        )
    else:
        raise Http404
    if not found:
        raise Http404
    return found[0]


def worker_resource(job_id, kind, resource_id):
    """Trusted worker gets its actor from a persisted job, never an HTTP user-id field.

    Only the authorization contract exists in B1. No scan/goal/photo worker is scheduled.
    """
    jobs = rows(
        """SELECT j.*,u.auth_subject FROM b1_private_resources j JOIN users u ON j.user_id=u.id
                   WHERE j.id=%s AND j.kind='scan_jobs'""",
        [job_id],
    )
    if not jobs:
        raise Http404
    actor = principal(jobs[0]["auth_subject"])
    return resource(actor, kind, resource_id)


def catalog_admin(actor):
    if verified(actor).role != "owner":
        raise PermissionDenied
    return rows("SELECT id,name,coverage_status FROM catalog_sets ORDER BY id")
