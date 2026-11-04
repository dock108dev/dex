"""Single ownership boundary for HTTP, file bytes, export and future worker execution."""

import json
from contextlib import contextmanager
from contextvars import ContextVar
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


def principal(subject, *, with_generation=False):
    found = rows(
        "SELECT u.id,u.role"
        + (
            ",COALESCE((SELECT value FROM collection_generations WHERE user_id=u.id),0) AS generation"
            if with_generation
            else ""
        )
        + """ FROM users u JOIN auth_user a
                    ON u.auth_subject=CAST(a.id AS TEXT)
                    WHERE a.id=%s AND a.is_active=TRUE AND u.state='active'""",
        [subject],
    )
    if not found:
        raise PermissionDenied
    result = Principal(subject, found[0]["id"], found[0]["role"])
    return (result, found[0]["generation"]) if with_generation else result


_read_authority = ContextVar("store_read_authority", default=None)


@contextmanager
def read_authority(actor):
    """Reuse one principal only within a checked read snapshot.

    The outer reader verifies before entry and again after leaving its transaction.
    The mutable lifetime flag prevents copied contexts retaining this permission.
    Never use this scope around mutations or worker dispatch.
    """
    scope = [actor, True]
    token = _read_authority.set(scope)
    try:
        yield
    finally:
        scope[1] = False
        _read_authority.reset(token)


def verified(actor):
    scope = _read_authority.get()
    if scope is not None and scope[1] and scope[0] == actor:
        return actor
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
    else:
        raise Http404
    if not found:
        raise Http404
    return found[0]


def catalog_admin(actor):
    if verified(actor).role != "owner":
        raise PermissionDenied
    return rows("SELECT id,name,coverage_status FROM catalog_sets ORDER BY id")
