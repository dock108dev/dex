"""Reviewed broad-card intent in the existing immutable operation journal."""

import csv
import io
import json

from . import collection, effective_collection, store
from . import ownership_declarations as declarations

KINDS = {"mark_owned", "remove_card", "card_quantity", "declaration_correction", "source_select"}


def source_scope(source):
    header = next(csv.reader(io.StringIO(source["source_text"].lstrip("\ufeff"))))
    if header in (declarations.FULL_HEADERS, declarations.PHOTO_HEADERS):
        return "full251"
    rows = declarations.parse(source["source_text"], source["source_sha256"])
    if rows:
        return rows[0]["source_scope"]
    # Even an empty declaration has an authoritative header scope.
    return "johto" if header == declarations.GEN2_HEADERS else "kanto"


def resolve_identity(actor, request):
    literal = {}
    for key in ("set_name", "name", "number"):
        value = request.get(key)
        if not isinstance(value, str) or not value.strip() or value != value.strip():
            raise ValueError("Supply the literal set, card name and number")
        literal[key] = value
    language = request.get("language")
    if language is not None and (not isinstance(language, str) or not language):
        raise ValueError("Supply a supported language reference")
    rows = effective_collection.project(actor)["cards"]
    matched = [r for r in rows if all(r[key] == value for key, value in literal.items())]
    if len(matched) != 1:
        raise ValueError("Card identity is unresolved; choose an authoritative literal card")
    row = matched[0]
    if row["identity_status"] == "conflict":
        raise collection.ReviewConflict("Card identity conflicts with catalog evidence; review its identity")
    entries = [p for p in collection.catalog(actor, include_archived=True) if p["id"] in row["printing_ids"]]
    languages = {p["language"] for p in entries}
    if language is not None and (not entries or languages != {language}):
        raise ValueError("Language differs from the supported card identity")
    literal.update(pokemon_dex=row["pokemon_dex"], candidate_printing_ids=row["printing_ids"])
    if language is not None:
        literal["language"] = language
    return literal, row


def plan(actor, kind, request, operation_id):
    actor = store.verified(actor)
    if kind not in KINDS:
        raise ValueError("Unsupported collection intent")
    result = dict(creates=[], updates=[], deletes=[], errors=[], warnings=[], checklist=[])
    if kind == "source_select":
        sources = store.rows(
            "SELECT * FROM ownership_declarations WHERE id=%s AND user_id=%s",
            [request.get("source_id"), actor.user_id],
        )
        if len(sources) != 1:
            raise ValueError("Choose an account-local retained collection source")
        source = sources[0]
        scope = request.get("scope")
        if scope not in {"full251", "kanto", "johto"} or request.get("replacement") != "replace":
            raise ValueError("Choose an explicit replacement scope and replacement intent")
        supported_scope = source_scope(source)
        if supported_scope != "full251" and supported_scope != scope:
            raise ValueError("Replacement scope is not supported by this source")
        result.update(selected_source_id=source["id"], source_scope=scope, replacement="replace")
        result["warnings"].append(
            "Replace current presence and quantity intent only within the reviewed scope. Retained copies and original source text remain historical evidence."
        )
    else:
        identity, current = resolve_identity(actor, request)
        intent = dict(kind=kind, identity=identity)
        if kind == "card_quantity":
            if "established_total_quantity" not in request:
                raise ValueError("Supply a complete total or null for Quantity unknown")
            total = request["established_total_quantity"]
            if total is not None and (type(total) is not int or total <= 0):
                raise ValueError(
                    "Total quantity must be a positive integer or null; use Remove card from collection for zero"
                )
            if total is not None and not current["present"]:
                raise collection.ReviewConflict("Mark this card owned before attesting its complete total")
            if total is not None and total < len(current["current_copy_ids"]):
                raise collection.ReviewConflict(
                    "Total quantity conflicts with supported current copy records; review the records or attest a complete compatible total"
                )
            intent["established_total_quantity"] = total
        elif kind == "remove_card":
            ids = set(identity["candidate_printing_ids"])
            for copy in collection.copies(actor):
                if copy.get("printing_id") in ids:
                    copy = collection.one(actor, "copy", copy["id"])
                    result["updates"].append(
                        dict(
                            kind="copy",
                            before=copy,
                            after={**copy, "state": "removed", "revision": copy["revision"] + 1},
                        )
                    )
            result["warnings"].append(
                "Remove card from collection means no copies remain owned. Matching active records become removed; their IDs, photos, attributes and history are retained."
            )
        elif kind == "declaration_correction":
            result["warnings"].append(
                "Correct declaration support only. No physical copy is removed; surviving supported copies may keep the card Owned. Original declaration text is unchanged."
            )
        else:
            result["warnings"].append(
                "Mark owned with Quantity unknown. No physical copy, edition, condition, grade, variant or value is created."
            )
        result["card_intent"] = intent
    return augment_plan(actor, kind, request, operation_id, result)


def augment_plan(actor, kind, request, operation_id, prepared):
    """Attach current-effect preview to a complete plan without writing or acquisition."""
    actor = store.verified(actor)
    if prepared.get("selected_source_id") and "source_scope" not in prepared:
        source = next((c["row"] for c in prepared["creates"] if c["kind"] == "declaration"), None)
        if source is None:
            rows = store.rows(
                "SELECT * FROM ownership_declarations WHERE id=%s AND user_id=%s",
                [prepared["selected_source_id"], actor.user_id],
            )
            source = rows[0] if rows else None
        if source is None:
            raise collection.Conflict("Selected source is unavailable")
        scope = request.get("scope") or source_scope(source)
        if scope not in {"full251", "kanto", "johto"} or (
            source_scope(source) != "full251" and scope != source_scope(source)
        ):
            raise ValueError("Replacement scope is not supported by this source")
        prepared["source_scope"] = scope
        if request.get("replacement") is not None and request["replacement"] != "replace":
            raise ValueError("Choose explicit replacement intent")
        if scope == "full251" or request.get("replacement") == "replace":
            prepared["replacement"] = "replace"
        if (
            scope != "full251"
            and effective_collection.project(actor)["selected_source"]
            and request.get("replacement") != "replace"
        ):
            prepared["errors"].append(
                "Scoped source after a full selection requires explicit replacement intent"
            )
    before = effective_collection.project(actor)
    if any(c["kind"] == "ambiguous-operation-order" for c in before["conflicts"]):
        raise collection.Conflict(
            "Collection operation order is unsupported; retain evidence and review the journal"
        )
    pending = dict(
        id=operation_id,
        user_id=actor.user_id,
        kind=kind,
        generation=collection.generation(actor),
        plan=prepared,
    )
    after = effective_collection.project(actor, pending=pending)
    old = {r["id"]: r for r in before["cards"]}
    new = {r["id"]: r for r in after["cards"]}
    if prepared.get("source_preview"):
        before_owned = {int(n) for n, row in before["species"].items() if row["present"]}
        after_owned = {int(n) for n, row in after["species"].items() if row["present"]}
        prepared["source_preview"].update(
            owned=len(after_owned),
            missing=251 - len(after_owned),
            added=sorted(after_owned - before_owned),
            removed=sorted(before_owned - after_owned),
        )
    prepared["reviewed_effects"] = dict(
        replacement_scope=prepared.get("source_scope"),
        added_cards=[r for key, r in new.items() if r["present"] and not old.get(key, {}).get("present")],
        removed_cards=[r for key, r in old.items() if r["present"] and not new.get(key, {}).get("present")],
        added_species=[
            int(n)
            for n, s in after["species"].items()
            if s["present"] and not before["species"][n]["present"]
        ],
        removed_species=[
            int(n)
            for n, s in before["species"].items()
            if s["present"] and not after["species"][n]["present"]
        ],
        quantity_changes=[
            dict(
                set_name=r["set_name"],
                name=r["name"],
                number=r["number"],
                before=old.get(key, {}).get("established_total_quantity"),
                after=r["established_total_quantity"],
            )
            for key, r in new.items()
            if old.get(key, {}).get("established_total_quantity") != r["established_total_quantity"]
        ],
        affected_copy_ids=sorted(
            {
                (c.get("before") or c.get("after") or c.get("row"))["id"]
                for c in prepared["creates"] + prepared["updates"] + prepared["deletes"]
                if c["kind"] == "copy"
            }
        ),
        conflicts=after["conflicts"]
        + [
            dict(set_name=r["set_name"], name=r["name"], number=r["number"], conflicts=r["conflicts"])
            for r in after["cards"]
            if r["conflicts"]
        ],
    )
    return prepared


def _scope_contains(scope, n):
    return scope == "full251" or (n is not None and (1 <= n <= 151 if scope == "kanto" else 152 <= n <= 251))


def _identities(actor, operation):
    plan = operation["plan"]
    result = []
    if plan.get("card_intent"):
        result.append(plan["card_intent"]["identity"])
    by_id = {p["id"]: p for p in collection.catalog(actor, include_archived=True)}
    for change in operation["changes"]:
        if change["kind"] != "copy":
            continue
        for image in (change.get("before"), change.get("after")):
            p = by_id.get(image.get("printing_id")) if image else None
            if p:
                result.append(
                    dict(
                        set_name=p["set_name"],
                        name=p["name"],
                        number=p["collector_number"],
                        pokemon_dex=p["attributes"].get("pokemon_dex"),
                    )
                )
    return result


def check_undo(actor, operation):
    """Protect journal-only effects and source dependencies before undo writes."""
    actor = store.verified(actor)
    if any(
        c["kind"] == "ambiguous-operation-order" for c in effective_collection.project(actor)["conflicts"]
    ):
        raise collection.Conflict(
            "Collection operation order is unsupported; retain evidence and review the journal"
        )
    intents = _identities(actor, operation)
    scope = operation["plan"].get("source_scope") if operation["plan"].get("selected_source_id") else None
    for later in store.rows(
        "SELECT * FROM collection_operations WHERE user_id=%s AND state='confirmed' AND generation>%s",
        [actor.user_id, operation["generation"]],
    ):
        later["plan"] = json.loads(later["plan"])
        later["changes"] = json.loads(later["changes"])
        newer_intents = _identities(actor, later)
        later_scope = (
            later["plan"].get("source_scope", "full251") if later["plan"].get("selected_source_id") else None
        )
        same = any(
            all(a.get(k) == b.get(k) for k in ("set_name", "name", "number"))
            for a in intents
            for b in newer_intents
        )
        if operation["plan"].get("card_intent") and (
            same or (later_scope and any(_scope_contains(later_scope, i.get("pokemon_dex")) for i in intents))
        ):
            raise collection.Conflict(
                "Newer card intent or source boundary depends on this operation; undo the dependent operation first"
            )
        if later["plan"].get("card_intent") and same:
            raise collection.Conflict(
                "Newer card intent depends on this copy operation; undo the dependent intent first"
            )
        if scope and (
            any(_scope_contains(scope, i.get("pokemon_dex")) for i in newer_intents)
            or (later_scope and (scope == "full251" or later_scope == "full251" or scope == later_scope))
        ):
            raise collection.Conflict(
                "Newer collection intent depends on this source boundary; undo the dependent operation first"
            )
