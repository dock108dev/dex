"""Private frozen Packs snapshots. Reopening never reprojects against current ownership."""

import hashlib
import json
import uuid
from datetime import datetime, timezone

from django.db import connection
from django.http import Http404

from pokemon_hunter.migration import encode

from . import collection, offer_filters, packs, sealed_catalog, store, transactions


def initialize(db=None):
    """Additive, idempotent SQLite/PostgreSQL feature migration; explicit operator action."""
    ddl = """CREATE TABLE IF NOT EXISTS saved_pack_research(
        id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),
        name TEXT NOT NULL,created_at TEXT NOT NULL,goal_id TEXT NOT NULL,
        snapshot TEXT NOT NULL,snapshot_sha256 TEXT NOT NULL)"""
    if db is not None:
        db.execute(ddl)
    else:
        with transactions.atomic(), connection.cursor() as cursor:
            cursor.execute(ddl)


def available():
    return "saved_pack_research" in connection.introspection.table_names()


def name(value):
    value = value.strip()
    if not value or len(value) > 160 or any(ord(c) < 32 for c in value):
        raise ValueError("Research name requires 1–160 printable characters")
    return value


def listing(actor):
    actor = store.verified(actor)
    if not available():
        return []
    return store.rows(
        "SELECT id,name,created_at,goal_id FROM saved_pack_research WHERE user_id=%s ORDER BY created_at DESC,id",
        [actor.user_id],
    )


def one(actor, key):
    actor = store.verified(actor)
    rows = store.rows("SELECT * FROM saved_pack_research WHERE id=%s AND user_id=%s", [key, actor.user_id])
    if not rows:
        raise Http404
    return rows[0]


def references(context, records):
    # Follow only exact referenced public identities, including unresolved relationships.
    ids = set()

    def walk(value):
        if isinstance(value, dict):
            for v in value.values():
                walk(v)
        elif isinstance(value, list):
            for v in value:
                walk(v)
        elif isinstance(value, str):
            ids.add(value)

    walk(context)
    selected = {k: {} for k in records}
    while True:
        before = len(ids)
        for kind, rows in records.items():
            for key, row in rows.items():
                if key in ids or (kind == "memberships" and row["printing_id"] in ids):
                    selected[kind][key] = row
                    walk(row)
        if len(ids) == before:
            return selected


@transactions.atomic
def save(actor, goal, species="", expansion="", research_name="", goal_version="", filters=None):
    actor = store.verified(actor)
    context = packs.project(actor, goal, species, expansion, filters=filters)
    if not context["supported"] or goal_version != context["goal"]["version"]:
        raise ValueError("Select an exact supported frozen goal version")
    if species and species not in {str(i["pokemon_dex"]) for i in context.get("missing", [])}:
        raise ValueError("Species must belong to the selected missing scope")
    if expansion and expansion not in {g["expansion"]["id"] for g in context.get("options", [])}:
        raise ValueError("Expansion must belong to the selected research")
    return store_context(actor, context, research_name)


def store_context(actor, context, research_name=""):
    store.verified(actor)
    goal = context["goal"]["id"]
    species = context.get("species", "")
    # Options are navigation metadata, not a second broader result snapshot.
    context["options"] = [dict(expansion=g["expansion"]) for g in context.get("options", [])]
    default = f"{context['goal']['name']} · v{context['goal']['definition']['lineage']['number']}"
    if species:
        default += f" · {next(i['label'] for i in context['missing'] if str(i['pokemon_dex']) == species)}"
    payload = dict(
        schema="dex-pack-research-v1",
        context=context,
        references=references(context, sealed_catalog.records()),
    )
    raw = encode(payload)
    key = str(uuid.uuid4())
    collection.execute(
        "INSERT INTO saved_pack_research VALUES(%s,%s,%s,%s,%s,%s,%s)",
        [
            key,
            actor.user_id,
            name(research_name or default),
            datetime.now(timezone.utc).isoformat(),
            goal,
            raw,
            hashlib.sha256(raw.encode()).hexdigest(),
        ],
    )
    return key


def reopen(actor, key, now=None):
    row = one(actor, key)
    if hashlib.sha256(row["snapshot"].encode()).hexdigest() != row["snapshot_sha256"]:
        raise ValueError("Retained research integrity mismatch")
    payload = json.loads(row["snapshot"])
    context = payload["context"]
    context["saved"] = {k: row[k] for k in ("id", "name", "created_at", "snapshot_sha256")}
    context["versions"] = []
    context["reference_gaps"] = []
    current = sealed_catalog.records() if "sealed_sources" in connection.introspection.table_names() else {}
    for kind, rows in payload["references"].items():
        for rid, retained in rows.items():
            if current.get(kind, {}).get(rid) != retained:
                context["reference_gaps"].append(
                    f"{kind}: {rid} is missing, archived or changed; saved evidence retained."
                )
    goals = store.rows(
        "SELECT * FROM collection_goals WHERE id=%s AND user_id=%s", [row["goal_id"], actor.user_id]
    )
    if not context.get("lookup") and (not goals or goals[0]["version"] != context["goal"]["version"]):
        context["reference_gaps"].append(
            "Selected frozen goal is missing or changed; saved version retained."
        )
    for ref in context["goal"]["definition"]["catalog_references"]:
        journals = store.rows("SELECT package_hash FROM catalog_imports WHERE id=%s", [ref["import_id"]])
        if not journals or journals[0]["package_hash"] != ref["package_sha256"]:
            context["reference_gaps"].append(
                f"Selected catalog review unavailable or changed: {ref['import_id']}"
            )
    # Time passes, but neither original observation dates nor stored context is rewritten.
    now = now or datetime.now(timezone.utc)
    return offer_filters.apply(
        context, context.get("offer_filters"), payload["references"].get("sources", {}), now, frozen=True
    )


@transactions.atomic
def rename(actor, key, value):
    row = one(actor, key)
    collection.execute(
        "UPDATE saved_pack_research SET name=%s WHERE id=%s AND user_id=%s",
        [name(value), row["id"], actor.user_id],
    )


@transactions.atomic
def remove(actor, key):
    row = one(actor, key)
    collection.execute(
        "DELETE FROM saved_pack_research WHERE id=%s AND user_id=%s", [row["id"], actor.user_id]
    )
