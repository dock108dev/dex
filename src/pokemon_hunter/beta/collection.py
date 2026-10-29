"""Physical-copy collection operations in the existing inventory, with durable reviewed transactions.

All entry points re-resolve the session principal. SQLite IMMEDIATE transactions serialize
confirmation/undo; revisioned before/after images prevent stale edits and destructive undo.
"""

import json
import re
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import connection
from django.http import Http404

from pokemon_hunter.inventory import stable_id
from pokemon_hunter.migration import encode

from . import broad_goals, collection_goals, collection_plans, goal_filters, store
from . import transactions as transaction
from .collection_catalog import catalog_entries as catalog_entries
from .collection_imports import FIELDS as FIELDS
from .collection_imports import SCHEMA as SCHEMA
from .collection_imports import parse_import as parse_import

TABLES = {
    "copy": "owned_copies",
    "binder": "binders",
    "goal": "collection_goals",
    "declaration": "ownership_declarations",
}


class Conflict(ValueError):
    pass


REVIEW_CONFLICT_DEFAULT = "Review the card identity and current records before trying again."
REVIEW_CONFLICT_MESSAGES = {
    "alias_namespace": "Card alias conflicts with the canonical group namespace; use the exact printing identifier",
    "alias_ambiguous": "Card alias is ambiguous; use the exact printing identifier",
    "identity_unresolved": "Card identity is unresolved; review catalog evidence",
    "identity_edit_unresolved": "Card identity is unresolved; review evidence before editing",
    "identity_conflict": "Card identity conflicts with catalog evidence; review its identity",
    "ownership_required": "Mark this card owned before attesting its complete total",
    "quantity_conflict": "Total quantity conflicts with supported current copy records; review the records or attest a complete compatible total",
}


class ReviewConflict(Conflict):
    """Select fixed public guidance by code; never expose arbitrary exception text."""

    def __init__(self, code):
        self.code = code
        super().__init__(REVIEW_CONFLICT_MESSAGES.get(code, REVIEW_CONFLICT_DEFAULT))


def initialize(db):
    """Initialize collection tables only in a new isolated root."""
    db.executescript("""
      ALTER TABLE owned_copies ADD COLUMN revision INTEGER NOT NULL DEFAULT 0;
      ALTER TABLE owned_copies ADD COLUMN source_copy_id TEXT;
      ALTER TABLE binders ADD COLUMN revision INTEGER NOT NULL DEFAULT 0;
      CREATE TABLE collection_goals(
        id TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),name TEXT NOT NULL,
        kind TEXT NOT NULL,version TEXT NOT NULL,definition TEXT NOT NULL,revision INTEGER NOT NULL DEFAULT 0);
      CREATE TABLE collection_operations(
        id TEXT NOT NULL,user_id TEXT NOT NULL REFERENCES users(id),kind TEXT NOT NULL,
        request TEXT NOT NULL,plan TEXT NOT NULL,state TEXT NOT NULL,changes TEXT NOT NULL,
        generation INTEGER NOT NULL,created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(id,user_id));
      CREATE TABLE collection_generations(user_id TEXT PRIMARY KEY REFERENCES users(id),value INTEGER NOT NULL);
      INSERT INTO schema_versions VALUES(2);
    """)


def execute(sql, params=()):
    with connection.cursor() as c:
        c.execute(sql, params)


def one(actor, kind, key):
    store.verified(actor)
    result = store.rows(f"SELECT * FROM {TABLES[kind]} WHERE id=%s AND user_id=%s", [key, actor.user_id])
    if not result:
        raise Http404
    return result[0]


def generation(actor):
    result = store.rows("SELECT value FROM collection_generations WHERE user_id=%s", [actor.user_id])
    return result[0]["value"] if result else 0


def bump(actor):
    execute(
        "INSERT INTO collection_generations VALUES(%s,1) ON CONFLICT(user_id) DO UPDATE SET value=collection_generations.value+1",
        [actor.user_id],
    )


def catalog(actor, query="", set_id="", include_archived=False):
    store.verified(actor)
    return catalog_entries(query, set_id, include_archived)


def printing(actor, key):
    result = [r for r in catalog(actor) if r["id"] == key]
    if not result:
        raise ValueError("Choose a supported catalog printing")
    return result[0]


def copies(actor):
    return [r for r in store.collection(actor) if r["state"] == "active"]


def binders(actor):
    store.verified(actor)
    return store.rows("SELECT * FROM binders WHERE user_id=%s ORDER BY name,id", [actor.user_id])


def exact_owned_printings(active, published_ids=None):
    """Resolved active copies only; callers may restrict to the published catalog."""
    return {
        c["printing_id"]
        for c in active
        if c["printing_id"]
        and (published_ids is None or c["printing_id"] in published_ids)
        and not json.loads(c["unresolved_fields"] or "[]")
        and not json.loads(c["provisional_identity"] or "{}").get("unresolved_fields")
    }


def goals(actor, *, goal_id=None, include_updates=True):
    store.verified(actor)
    active = copies(actor)
    available_ids = {p["id"] for p in catalog(actor)}
    published_ids = available_ids if settings.B4_ENABLED else None
    from .goal_progress import evaluate

    result = store.rows(
        "SELECT * FROM collection_goals WHERE user_id=%s"
        + (" AND id=%s" if goal_id is not None else "")
        + " ORDER BY name,id",
        [actor.user_id, goal_id] if goal_id is not None else [actor.user_id],
    )
    successor_ids = {}
    for row in result:
        predecessor = json.loads(row["definition"]).get("lineage", {}).get("predecessor_id")
        successor_ids.setdefault(predecessor, []).append(row["id"])
    current_broad = (
        broad_goals.definition(catalog(actor))
        if include_updates and any(g["kind"] in collection_goals.KINDS for g in result)
        else None
    )
    for g in result:
        g["successor_ids"] = successor_ids.get(g["id"], [])
        definition = json.loads(g["definition"])
        if g["kind"] in collection_goals.KINDS:
            g.update(
                definition=definition, **evaluate(g["kind"], definition, active, available_ids, published_ids)
            )
            g["coverage_update_available"] = include_updates and any(
                current_broad[k] != definition[k]
                for k in ("items", "catalog_references", "eligibility_policy")
            )
            if g["kind"] in collection_goals.OWNERSHIP_KINDS:
                row = collection_goals.source(actor, definition["collection_source"]["id"])
                collection_goals.validate(definition, row)
                current = (
                    (
                        collection_goals.targets_definition(
                            actor, catalog(actor), row["id"], [i["pokemon_dex"] for i in definition["items"]]
                        )
                        if g["kind"] == collection_goals.TARGET_KIND
                        else current_broad
                    )
                    if include_updates
                    else None
                )
                g["coverage_update_available"] = include_updates and any(
                    current[k] != definition[k] for k in ("items", "catalog_references")
                )
                g["collection_update_available"] = include_updates and any(
                    r["source_sha256"] != row["source_sha256"] for r in collection_goals.sources(actor)
                )
            continue
        g.update(
            definition=definition, **evaluate(g["kind"], definition, active, available_ids, published_ids)
        )
    return result


def export_data(actor):
    store.verified(actor)
    result = {
        "schema": SCHEMA,
        "copies": copies(actor),
        "binders": binders(actor),
        "goals": goals(actor),
        "vintage_251": store.progress(copies(actor)),
        "catalog_scope": "Pinned supported catalog; unresolved variants are not exact completion. No market value is inferred.",
    }
    if any(g["kind"] in collection_goals.OWNERSHIP_KINDS for g in result["goals"]):
        result["collection_sources"] = collection_goals.exported(actor, result["goals"])
    return result


def attributes(actor, raw, pending_binders=()):
    if not isinstance(raw, dict):
        raise ValueError("Copy attributes must be an object")
    unknown = set(raw) - set(FIELDS)
    if unknown:
        raise ValueError("Unsupported copy fields: " + ", ".join(sorted(unknown)))
    result = {}
    for key in FIELDS:
        value = raw.get(key)
        if value is not None and not isinstance(value, str):
            raise ValueError(f"{key}: supply text; money must be a decimal string")
        value = value.strip() if value else None
        if value and len(value) > (2000 if key == "notes" else 200):
            raise ValueError(f"{key}: value is too long")
        result[key] = value
    if result["condition"] not in {None, "NM", "LP", "MP", "HP", "DMG", "Mint"}:
        raise ValueError("condition: choose Mint, NM, LP, MP, HP, DMG or leave unknown")
    amount, currency = result["purchase_amount"], result["purchase_currency"]
    if amount is not None:
        try:
            number = Decimal(amount)
            if not re.fullmatch(r"\d{1,12}(\.\d{1,6})?", amount) or not number.is_finite() or number < 0:
                raise InvalidOperation
        except InvalidOperation:
            raise ValueError(
                "purchase_amount: use a non-negative exact decimal, up to 6 decimal places"
            ) from None
        if not currency:
            raise ValueError("purchase_currency: required when an amount is entered")
        result["purchase_amount"] = format(number, "f")
    if currency and not re.fullmatch(r"[A-Z]{3}", currency):
        raise ValueError("purchase_currency: use a three-letter uppercase currency code")
    if result["purchase_date"]:
        try:
            date.fromisoformat(result["purchase_date"])
        except ValueError:
            raise ValueError("purchase_date: use YYYY-MM-DD") from None
    if result["binder_id"] and result["binder_id"] not in pending_binders:
        one(actor, "binder", result["binder_id"])
    return result


def name(raw):
    if not isinstance(raw, str) or not raw.strip() or len(raw) > 120:
        raise ValueError("Enter a name of 1–120 characters")
    return raw.strip()


def goal_definition(actor, request):
    kind = request.get("goal_kind")
    if kind == collection_goals.TARGET_KIND:
        return collection_goals.targets_definition(
            actor, catalog(actor), request.get("collection_source_id"), request.get("targets")
        )
    if kind == collection_goals.KIND:
        return collection_goals.definition(actor, catalog(actor), request.get("collection_source_id"))
    if kind == "original151":
        return broad_goals.definition(catalog(actor))
    policy = request.get("policy", "catalog")
    if policy not in {"catalog", "exact"}:
        raise ValueError("Choose catalog-entry or exact-variant completion")
    entries = catalog(actor)
    if kind == "filtered":
        return goal_filters.definition(
            request.get("filters"),
            entries,
            store.rows("SELECT id,game_key,name FROM games ORDER BY name"),
            policy,
        )
    if kind == "vintage":
        templates = store.rows("SELECT * FROM goal_templates WHERE id='vintage-251'")
        if not templates:
            raise ValueError("Vintage 251 template is not available")
        # This persisted template keeps its historical label/field contract, but
        # membership grouping comes from the same builder as current goals/lookups.
        items = [
            {
                "label": f"Species {item['pokemon_dex']:03}",
                "printing_ids": item["printing_ids"],
                "unresolved": item["unresolved"],
            }
            for item in broad_goals.species_items(
                [
                    p
                    for p in entries
                    if p["attributes"].get("dex_eligible")
                    and p["attributes"].get("pokemon_dex") in range(1, 252)
                ],
                range(1, 252),
            )
        ]
        return {
            "policy": "species",
            "items": items,
            "template_version": templates[0]["version"],
            "rules": json.loads(templates[0]["rules"]),
            "coverage": "Frozen Vintage 251 eligible catalog membership",
        }
    if kind == "set":
        entries = [p for p in entries if p["set_id"] == request.get("set_id")]
    elif kind == "custom":
        keys = request.get("printing_ids", [])
        if not isinstance(keys, list) or not keys or len(keys) != len(set(keys)):
            raise ValueError("Select a non-empty checklist without repeated identities")
        entries = [p for p in entries if p["id"] in keys]
        if len(entries) != len(keys):
            raise ValueError("Checklist includes an unsupported printing")
    else:
        raise ValueError("Choose set, custom or Vintage 251 goal")
    if not entries:
        raise ValueError("No catalog entries available for this checklist")
    return {
        "policy": policy,
        "items": goal_filters.printing_items(entries),
        "catalog_versions": sorted({p["catalog_version"] for p in entries}),
        "coverage": "Pinned catalog entries only; edition/variant coverage is not established. This is not a master-set completeness claim.",
    }


def plan(actor, kind, request, operation_id):
    """Build reviewed intent with this service's account-scoped readers and errors."""
    return collection_plans.build(
        actor,
        kind,
        request,
        operation_id,
        catalog=catalog,
        copies=copies,
        goals=goals,
        one=one,
        attributes=attributes,
        name=name,
        goal_definition=goal_definition,
        parse_import=parse_import,
        conflict_error=Conflict,
    )


@transaction.atomic
def preview(actor, kind, request, operation_id):
    store.verified(actor)
    if not isinstance(request, dict):
        raise ValueError("Operation request must be an object")
    allowed = {
        "owner_declaration": {"text", "sha256", "scope", "replacement"},
        "mark_owned": {"set_name", "name", "number", "language"},
        "remove_card": {"set_name", "name", "number", "language"},
        "declaration_correction": {"set_name", "name", "number", "language"},
        "card_quantity": {"set_name", "name", "number", "language", "established_total_quantity"},
        "card_defaults": {"card_ids", "quantity", "variant"},
        "source_select": {"source_id", "scope", "replacement"},
        "collection_correct": {"source_id", "pokemon_dex", "owned", "source_set", "card_text", "notes"},
        "resolve": {"id", "revision", "printing_id"},
        "photo": {"printing_id", "provisional_identity", "attributes"},
        "add": {"printing_id", "attributes", "duplicate_policy"},
        "set": {"set_id", "attributes", "duplicate_policy"},
        "edit": {"id", "revision", "attributes"},
        "edition": {"id", "revision", "selection"},
        "remove": {"id", "revision"},
        "binder": {"name"},
        "binder_edit": {"id", "revision", "name"},
        "binder_remove": {"id", "revision"},
        "goal": {
            "name",
            "goal_kind",
            "set_id",
            "policy",
            "printing_ids",
            "filters",
            "collection_source_id",
            "targets",
        },
        "goal_edit": {
            "preserve_membership",
            "id",
            "revision",
            "name",
            "goal_kind",
            "set_id",
            "policy",
            "printing_ids",
            "filters",
            "collection_source_id",
            "targets",
        },
        "goal_remove": {"id", "revision"},
        "import": {"format", "text", "duplicate_policy"},
        "bulk": {"draft_id", "revision", "input_hash"},
    }
    if kind not in allowed or set(request) - allowed[kind]:
        raise ValueError("Unsupported operation fields")
    try:
        operation_id = str(uuid.UUID(operation_id))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("A stable UUID operation_id is required") from None
    operation_id = stable_id("b2-operation", actor.user_id + operation_id)
    if kind == "import":
        parse_import(request.get("text"), request.get("format"))
        operation_id = stable_id("b2-import", actor.user_id + encode(request))
    prior = store.rows(
        "SELECT * FROM collection_operations WHERE id=%s AND user_id=%s", [operation_id, actor.user_id]
    )
    if prior:
        if prior[0]["request"] != encode(request) or prior[0]["kind"] != kind:
            raise Conflict("Operation ID already belongs to different input. Start a new operation.")
        if prior[0]["state"] == "preview":
            # A fresh preview may refresh stale ownership, but confirmation itself never does.
            refreshed = plan(actor, kind, request, operation_id)
            execute(
                "UPDATE collection_operations SET plan=%s,generation=%s WHERE id=%s AND user_id=%s",
                [encode(refreshed), generation(actor), operation_id, actor.user_id],
            )
        return operation(actor, operation_id)
    prepared = plan(actor, kind, request, operation_id)
    execute(
        "INSERT INTO collection_operations(id,user_id,kind,request,plan,state,changes,generation) VALUES(%s,%s,%s,%s,%s,'preview','[]',%s)",
        [operation_id, actor.user_id, kind, encode(request), encode(prepared), generation(actor)],
    )
    return operation(actor, operation_id)


def operation(actor, key):
    store.verified(actor)
    result = store.rows(
        "SELECT * FROM collection_operations WHERE id=%s AND user_id=%s", [key, actor.user_id]
    )
    if not result:
        raise Http404
    row = result[0]
    for field in ("request", "plan", "changes"):
        row[field] = json.loads(row[field])
    return row


def write_row(kind, row, insert=False):
    table = TABLES[kind]
    if insert:
        execute(
            f"INSERT INTO {table} ({','.join(row)}) VALUES ({','.join(['%s'] * len(row))})",
            list(row.values()),
        )
    else:
        columns = [k for k in row if k not in {"id", "user_id"}]
        execute(
            f"UPDATE {table} SET {','.join(k + '=%s' for k in columns)} WHERE id=%s AND user_id=%s",
            [*(row[k] for k in columns), row["id"], row["user_id"]],
        )


@transaction.atomic
def confirm(actor, key):
    store.verified(actor)
    op = operation(actor, key)
    if op["state"] != "preview":
        return op
    if op["generation"] != generation(actor):
        raise Conflict("Your collection changed after preview. Create a fresh preview before confirming.")
    prepared = plan(actor, op["kind"], op["request"], key)
    if prepared != op["plan"]:
        raise Conflict("Catalog or ownership changed after preview. Create a fresh preview.")
    if prepared["errors"]:
        raise ValueError("Fix every row error before confirmation; no changes were applied")
    from . import account_read_build

    read_state = account_read_build.before_mutation(actor)
    changes = []
    if any(c["kind"] == "copy" for c in prepared["creates"]):
        execute(
            "INSERT INTO import_batches VALUES(%s,%s,%s,%s,%s)",
            [key, actor.user_id, key, SCHEMA, "confirmed"],
        )
    for change in prepared["creates"]:
        write_row(change["kind"], change["row"], insert=True)
        changes.append({"kind": change["kind"], "before": None, "after": change["row"]})
    for change in prepared["updates"]:
        write_row(change["kind"], change["after"])
        changes.append(change)
    for change in prepared["deletes"]:
        before = change["before"]
        execute(
            f"DELETE FROM {TABLES[change['kind']]} WHERE id=%s AND user_id=%s", [before["id"], actor.user_id]
        )
        changes.append({**change, "after": None})
    execute(
        "UPDATE collection_operations SET state='confirmed',changes=%s WHERE id=%s AND user_id=%s",
        [encode(changes), key, actor.user_id],
    )
    if op["kind"] == "bulk":
        from .collection_drafts import finish

        finish(actor, op)
    from .photo_batches import revoke_inactive_crops

    revoke_inactive_crops()
    bump(actor)
    account_read_build.refresh(actor, read_state, key)
    return operation(actor, key)


@transaction.atomic
def undo(actor, key):
    store.verified(actor)
    op = operation(actor, key)
    if op["state"] == "undone":
        return op
    if op["state"] != "confirmed":
        raise Conflict("Only a confirmed operation can be undone")
    if any(
        c["kind"] == "goal" and c["after"] and c["after"]["kind"] in collection_goals.KINDS
        for c in op["changes"]
    ):
        raise Conflict("Retained goal versions cannot be erased; preview an explicit successor")
    referenced_sources = {
        g["definition"]["collection_source"]["id"]
        for g in goals(actor)
        if g["kind"] in collection_goals.OWNERSHIP_KINDS
    }
    if any(
        c["kind"] == "declaration" and c["after"] and c["after"]["id"] in referenced_sources
        for c in op["changes"]
    ):
        raise Conflict("Retained goal depends on this collection source")
    created_sources = {
        c["after"]["id"]
        for c in op["changes"]
        if c["kind"] == "declaration" and c["before"] is None and c["after"]
    }
    if created_sources and any(
        json.loads(r["plan"]).get("selected_source_id") in created_sources
        for r in store.rows(
            "SELECT plan FROM collection_operations WHERE user_id=%s AND state='confirmed' AND id<>%s",
            [actor.user_id, key],
        )
    ):
        raise Conflict("A confirmed selection depends on this collection source; undo that selection first")
    from .collection_intents import check_undo

    check_undo(actor, op)
    predecessors = {g["definition"].get("lineage", {}).get("predecessor_id") for g in goals(actor)}
    if any(c["kind"] == "goal" and (c["after"] or c["before"])["id"] in predecessors for c in op["changes"]):
        raise Conflict("A retained successor depends on this version; undo would alter its predecessor")
    # Check ALL after-images before writing anything. Revisions detect even edited-back values.
    created_copies = {c["after"]["id"] for c in op["changes"] if c["kind"] == "copy" and c["before"] is None}
    for change in op["changes"]:
        before, after = change["before"], change["after"]
        row = after or before
        current = store.rows(
            f"SELECT * FROM {TABLES[change['kind']]} WHERE id=%s AND user_id=%s", [row["id"], actor.user_id]
        )
        if current != ([after] if after else []):
            raise Conflict(
                "A record changed after this operation. Undo is blocked to preserve subsequent edits; review the current record."
            )
        if change["kind"] == "binder" and before is None:
            refs = store.rows(
                "SELECT id FROM owned_copies WHERE binder_id=%s AND user_id=%s", [row["id"], actor.user_id]
            )
            if any(r["id"] not in created_copies for r in refs):
                raise Conflict("This binder is now used by another copy. Move that copy before undo.")
    from . import account_read_build

    read_state = account_read_build.before_mutation(actor)
    for change in reversed(op["changes"]):
        before, after = change["before"], change["after"]
        if before is None:
            # Added copies have no prior identity to restore. Remove exactly these rows;
            # their immutable provenance stays in the operation journal.
            execute(
                f"DELETE FROM {TABLES[change['kind']]} WHERE id=%s AND user_id=%s",
                [after["id"], actor.user_id],
            )
        else:
            write_row(
                change["kind"],
                {**before, "revision": (after or before)["revision"] + 1},
                insert=after is None,
            )
    execute(
        "UPDATE collection_operations SET state='undone' WHERE id=%s AND user_id=%s", [key, actor.user_id]
    )
    from .photo_batches import revoke_inactive_crops

    revoke_inactive_crops()
    bump(actor)
    account_read_build.refresh(actor, read_state, key)
    return operation(actor, key)
