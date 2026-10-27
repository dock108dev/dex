"""Read-only reviewed mutation plans; transaction application remains in collection.

Explicit account-scoped readers preserve the public service boundary without an
import back into the transaction facade. Building a plan never applies its rows.
"""

import json

from django.http import Http404

from pokemon_hunter.inventory import stable_id
from pokemon_hunter.migration import digest, encode

from . import broad_goals, collection_goals, collection_imports, copy_editions, store
from .collection_imports import FIELDS


def build(
    actor,
    kind,
    request,
    operation_id,
    *,
    catalog,
    copies,
    goals,
    one,
    attributes,
    name,
    goal_definition,
    parse_import,
    conflict_error,
):
    """Produces immutable reviewed intent; confirmation recomputes before applying."""
    from . import collection_intents

    if kind in collection_intents.KINDS:
        return collection_intents.plan(actor, kind, request, operation_id)
    result = {"creates": [], "updates": [], "deletes": [], "errors": [], "warnings": [], "checklist": []}

    def create(entity, row):
        result["creates"].append({"kind": entity, "row": row})

    def copy(raw, index, source_id=None, pending=()):
        p = resolve(raw.get("printing_id")) if raw.get("printing_id") else None
        provisional = raw.get("provisional_identity")
        if not p and (not isinstance(provisional, str) or not provisional):
            raise ValueError("Choose a printing or retain a supported provisional identity from an export")
        if provisional:
            try:
                if not isinstance(json.loads(provisional), dict):
                    raise ValueError
            except (ValueError, TypeError):
                raise ValueError("Invalid provisional identity") from None
        if raw.get("first_edition_selected", 0) not in (0, 1):
            raise ValueError("first_edition_selected: use 0 or 1")
        attrs = attributes(actor, {k: raw.get(k) for k in FIELDS}, pending)
        cid = stable_id(
            "b2-copy",
            f"{actor.user_id}:{source_id}" if source_id else f"{actor.user_id}:{operation_id}:{index}",
        )
        if store.rows("SELECT id FROM owned_copies WHERE id=%s", [cid]):
            raise ValueError(
                "This source copy identity was already imported; use the original operation or undo"
            )
        row = {
            "id": cid,
            "user_id": actor.user_id,
            "printing_id": p["id"] if p else None,
            "provisional_identity": provisional or encode({"unresolved_fields": p["unresolved_fields"]}),
            **attrs,
            "batch_id": operation_id,
            "legacy_id": None,
            "first_edition_selected": int(
                raw.get("first_edition_selected", copy_editions.is_first(p) if p else 0)
            ),
            "state": "active",
            "revision": 0,
            "source_copy_id": source_id,
        }
        if kind == "bulk" and raw.get("first_edition_selected") and p:
            from .copy_editions import select

            row = {**select(row, p, "first_edition"), "revision": 0}
        create("copy", row)

    if kind == "collection_correct":
        from .ownership_declarations import correction

        request = correction(actor, request)
    if kind in {"owner_declaration", "collection_correct"}:
        from .ownership_declarations import plan as declaration_plan

        prepared = declaration_plan(actor, request, operation_id, catalog(actor), copies(actor))
        return collection_intents.augment_plan(actor, kind, request, operation_id, prepared)

    catalog_rows = catalog(actor, include_archived=(kind == "import"))
    catalog_by_id = {p["id"]: p for p in catalog_rows}

    def resolve(key):
        if key not in catalog_by_id:
            raise ValueError("Choose a supported catalog printing")
        return catalog_by_id[key]

    owned = copies(actor)
    counts = {}
    for c in owned:
        counts[c["printing_id"]] = counts.get(c["printing_id"], 0) + 1
    policy = request.get("duplicate_policy")
    if kind in {"add", "set", "import"} and policy not in {"skip", "allow", "reject"}:
        raise ValueError("Choose an explicit duplicate policy: skip, allow or reject")
    if kind == "bulk":
        from .collection_drafts import plan_input

        draft, normalized = plan_input(actor, request)
        from .photo_batches import draft_guard

        photo_review = draft_guard(actor, draft)
        if photo_review:
            result["photo_review"] = photo_review
            from .photo_additions import prepare

            prepare(actor, normalized["rows"], owned, catalog_by_id, result)
        result.update(
            bulk=normalized, card_intents=[], draft_id=draft["id"], draft_revision=draft["revision"]
        )
        result["errors"] = [
            f"Row {r['row_id']}: {error}"
            for r in normalized["rows"]
            if r["included"]
            for error in r["errors"]
        ]
        for row in normalized["rows"]:
            if row["errors"] or not row["included"] or row.get("skipped") or row.get("noop"):
                continue
            if row["action"] == "add_copies":
                for i in range(row["quantity"]):
                    copy(
                        {
                            "printing_id": row["printing_id"],
                            "provisional_identity": row.get("provisional_identity"),
                            **row["attributes"],
                            **({"first_edition_selected": 1} if row.get("first_edition_selected") else {}),
                        },
                        f"{row['row_id']}:{i}",
                    )
            else:
                intent = dict(
                    kind="mark_owned" if row["action"] == "mark_owned" else "card_quantity",
                    identity=row["identity"],
                )
                if row["action"] == "set_total":
                    intent["established_total_quantity"] = row["total"]
                result["card_intents"].append(intent)
        result["warnings"].append("Whole-lot context is retained once; no cost is allocated to copies.")
    elif kind in {"add", "set"}:
        attributes(actor, request.get("attributes", {}))
        entries = (
            [resolve(request.get("printing_id"))]
            if kind == "add"
            else catalog(actor, set_id=request.get("set_id") or "missing")
        )
        if not entries:
            raise ValueError("No supported checklist entries")
        for i, p in enumerate(entries):
            count = counts.get(p["id"], 0)
            proposed = not count or policy == "allow"
            result["checklist"].append(
                {
                    "printing_id": p["id"],
                    "name": p["name"],
                    "number": p["collector_number"],
                    "set": p["set_name"],
                    "existing_copies": count,
                    "proposed_copies": int(proposed),
                    "edition": p["edition"],
                    "finish": p["finish"],
                    "variant": p["variant"],
                    "unresolved": p["unresolved_fields"],
                    "coverage": p["coverage_status"],
                    "catalog_version": p["catalog_version"],
                }
            )
            if count:
                result["warnings"].append(
                    f"{p['name']} #{p['collector_number']}: {count} existing copies; policy {policy}."
                )
                if policy == "reject":
                    result["errors"].append(f"Already owned: {p['name']} #{p['collector_number']}")
            if proposed:
                attrs = request.get("attributes", {})
                if not isinstance(attrs, dict):
                    raise ValueError("Copy attributes must be an object")
                attributes(actor, attrs)
                copy({"printing_id": p["id"], **attrs}, i)
        result["warnings"].append(
            "Only listed catalog entries are proposed. Unresolved editions/variants stay unset; full variant coverage is not established."
        )
    elif kind == "resolve":
        before = one(actor, "copy", request.get("id"))
        if (
            before["state"] != "active"
            or before["printing_id"]
            or before["revision"] != request.get("revision")
        ):
            raise conflict_error("Only an unchanged active provisional copy can be resolved")
        p = resolve(request.get("printing_id"))
        identity = json.loads(before["provisional_identity"] or "{}")
        from .copy_identity import binding as admitted_group_binding

        binding = admitted_group_binding(before)
        if binding:
            from .card_groups import build_groups

            pokemon_games = {g["id"] for g in store.rows("SELECT id FROM games WHERE game_key='pokemon'")}
            target_groups = build_groups([p], pokemon_game_ids=pokemon_games)["groups"]
            if len(target_groups) != 1 or target_groups[0]["id"] != binding["group_id"]:
                raise ValueError(
                    "Resolution must retain this provisional copy's original game, set and card group"
                )
            literal = binding["identity"]
            if any(
                p[field] != literal[key]
                for field, key in (
                    ("set_name", "set_name"),
                    ("name", "name"),
                    ("collector_number", "number"),
                    ("language", "language"),
                )
            ):
                raise ValueError("Resolution must retain this provisional copy's bound card identity")
        identity["resolution"] = {
            "printing_id": p["id"],
            "catalog_version": p["catalog_version"],
            "operation": operation_id,
        }
        identity["unresolved_fields"] = p["unresolved_fields"]
        after = {
            **before,
            "printing_id": p["id"],
            "provisional_identity": encode(identity),
            "revision": before["revision"] + 1,
        }
        result["updates"].append({"kind": "copy", "before": before, "after": after})
    elif kind == "photo":
        copy(
            {
                "printing_id": request.get("printing_id"),
                "provisional_identity": request.get("provisional_identity"),
                **request.get("attributes", {}),
            },
            0,
        )
    elif kind in {"edit", "edition", "remove", "binder_edit", "binder_remove", "goal_remove"}:
        entity = "binder" if kind.startswith("binder") else "goal" if kind.startswith("goal") else "copy"
        before = one(actor, entity, request.get("id"))
        if request.get("revision") != before["revision"]:
            raise conflict_error("This record changed. Reload it before making a new preview.")
        if entity == "goal" and (
            before["kind"] in collection_goals.KINDS
            or any(
                g["definition"].get("lineage", {}).get("predecessor_id") == before["id"] for g in goals(actor)
            )
        ):
            raise conflict_error("Retained goal versions cannot be removed")
        if entity == "copy" and before["state"] != "active":
            raise conflict_error("This copy has already been removed")
        if kind == "edit":
            attrs = request.get("attributes", {})
            after = {
                **before,
                **attributes(actor, {**{k: before[k] for k in FIELDS}, **attrs}),
                "revision": before["revision"] + 1,
            }
        elif kind == "edition":
            from .copy_editions import select

            p = resolve(before["printing_id"])
            after = select(before, p, request.get("selection"))
            result["warnings"].append(
                f"{p['name']} #{p['collector_number']} · {p['set_name']}: only this physical copy changes. Finish and variant uncertainty remain; unchecked means edition unresolved."
            )
        elif kind == "remove":
            after = {**before, "state": "removed", "revision": before["revision"] + 1}
        elif kind == "binder_edit":
            after = {**before, "name": name(request.get("name")), "revision": before["revision"] + 1}
        else:
            if entity == "binder" and store.rows(
                "SELECT id FROM owned_copies WHERE binder_id=%s AND user_id=%s", [before["id"], actor.user_id]
            ):
                raise conflict_error(
                    "Move active copies out first. Restore removed copies with undo, then move them out before removing this binder."
                )
            result["deletes"].append({"kind": entity, "before": before})
            return result
        result["updates"].append({"kind": entity, "before": before, "after": after})
    elif kind == "binder":
        create(
            "binder",
            {
                "id": stable_id("b2-binder", actor.user_id + operation_id),
                "user_id": actor.user_id,
                "name": name(request.get("name")),
                "revision": 0,
            },
        )
    elif kind in {"goal", "goal_edit"}:
        definition = goal_definition(actor, request)
        fields = {
            "name": name(request.get("name")),
            "kind": request["goal_kind"],
            "version": digest(encode(definition).encode()),
            "definition": encode(definition),
        }
        if request["goal_kind"] in collection_goals.KINDS:
            gid = stable_id("b2-goal", actor.user_id + operation_id)
            lineage = dict(root_id=gid, predecessor_id=None, predecessor_version=None, number=1)
            available = {p["id"] for p in catalog_rows}
            if kind == "goal_edit":
                before = one(actor, "goal", request.get("id"))
                if before["revision"] != request.get("revision"):
                    raise conflict_error("Goal changed; preview again")
                old = json.loads(before["definition"])
                if old["policy"] != "species" or (
                    request["goal_kind"] != collection_goals.TARGET_KIND and len(old["items"]) != 151
                ):
                    raise ValueError("Only an Original 151 species goal can be versioned here")
                old_lineage = old.get("lineage", dict(root_id=before["id"], number=1))
                # A concurrent successor invalidates the preview even though its predecessor is immutable.
                if any(
                    g["definition"].get("lineage", {}).get("predecessor_id") == before["id"]
                    for g in goals(actor)
                ):
                    raise conflict_error("This version already has a successor; choose that version")
                lineage = dict(
                    root_id=old_lineage["root_id"],
                    predecessor_id=before["id"],
                    predecessor_version=before["version"],
                    number=old_lineage["number"] + 1,
                )
                result["goal_difference"] = broad_goals.difference(old, definition, owned, available)
                result["goal_difference"]["progress_before"] = next(
                    g["satisfied"] for g in goals(actor) if g["id"] == before["id"]
                )
                if request["goal_kind"] in collection_goals.OWNERSHIP_KINDS:
                    result["goal_difference"].update(
                        source_before=old.get("collection_source"),
                        source_after=definition["collection_source"],
                        species_added=sorted(
                            set(definition["owned_species"]) - set(old.get("owned_species", []))
                        ),
                        species_removed=sorted(
                            set(old.get("owned_species", [])) - set(definition["owned_species"])
                        ),
                    )
                result["goal_predecessor"] = before
            definition["lineage"] = lineage
            fields.update(version=digest(encode(definition).encode()), definition=encode(definition))
            result["goal_progress"] = broad_goals.progress(definition, owned, available)
            create("goal", dict(id=gid, user_id=actor.user_id, **fields, revision=0))
        elif kind == "goal_edit":
            before = one(actor, "goal", request.get("id"))
            if before["kind"] in collection_goals.KINDS or any(
                g["definition"].get("lineage", {}).get("predecessor_id") == before["id"] for g in goals(actor)
            ):
                raise ValueError("Broad versions cannot be overwritten; create an explicit successor")
            if before["revision"] != request.get("revision"):
                raise conflict_error("This goal changed. Reload before editing its filters.")
            result["updates"].append(
                {
                    "kind": "goal",
                    "before": before,
                    "after": {**before, **fields, "revision": before["revision"] + 1},
                }
            )
        else:
            create(
                "goal",
                {
                    "id": stable_id("b2-goal", actor.user_id + operation_id),
                    "user_id": actor.user_id,
                    **fields,
                    "revision": 0,
                },
            )
        result["warnings"].append(
            "Tracking adds no copies. Membership and denominator are frozen at this version."
        )
    elif kind == "import":
        data = parse_import(request.get("text"), request.get("format"))
        binder_map = {}
        for b in data.get("binders", []):
            if not isinstance(b, dict) or not isinstance(b.get("id"), str) or b["id"] in binder_map:
                raise ValueError("Invalid or duplicate binder identity")
            bid = stable_id("b2-binder-import", actor.user_id + operation_id + b["id"])
            binder_map[b["id"]] = bid
            create(
                "binder", {"id": bid, "user_id": actor.user_id, "name": name(b.get("name")), "revision": 0}
            )
        seen = set()
        for index, raw in enumerate(data["copies"], 1):
            try:
                if not isinstance(raw, dict):
                    raise ValueError("Row must be an object")
                allowed = {
                    "id",
                    "printing_id",
                    "provisional_identity",
                    "first_edition_selected",
                    "source_copy_id",
                    "user_id",
                    "batch_id",
                    "legacy_id",
                    "state",
                    "revision",
                    "collector_number",
                    "edition",
                    "unresolved_fields",
                    "attributes",
                    *FIELDS,
                }
                if set(raw) - allowed:
                    raise ValueError("Unsupported columns in row")
                raw = dict(raw)
                source = (
                    raw.get("source_copy_id")
                    or raw.get("id")
                    or digest((request["text"] + str(index)).encode())
                )
                if not isinstance(source, str) or len(source) > 200 or source in seen:
                    raise ValueError("Invalid or repeated source copy identity")
                seen.add(source)
                if raw.get("state", "active") != "active":
                    raise ValueError("Only active copies can be imported")
                if raw.get("binder_id") in binder_map:
                    raw["binder_id"] = binder_map[raw["binder_id"]]
                # Validate even skipped rows; malformed rows cannot disappear behind duplicate policy.
                attributes(actor, {k: raw.get(k) for k in FIELDS}, binder_map.values())
                p = resolve(raw["printing_id"]) if raw.get("printing_id") else None
                if p:
                    for field in ("edition", "unresolved_fields", "attributes"):
                        if field in raw and raw[field] != (
                            encode(p[field]) if field in {"unresolved_fields", "attributes"} else p[field]
                        ):
                            raise ValueError(
                                "Catalog identity differs from the exported snapshot; reconcile before importing"
                            )
                    identity = json.loads(raw.get("provisional_identity") or "{}")
                    if not isinstance(identity, dict):
                        raise ValueError("Invalid provisional identity")
                    selection = identity.get("edition_selection")
                    if selection not in (None, "first_edition", "unresolved"):
                        raise ValueError("Invalid copy edition selection")
                    expected = selection == "first_edition" if selection else copy_editions.is_first(p)
                    if expected:
                        copy_editions.require_first_supported(p)
                    if selection and "first_edition_selected" not in raw:
                        raise ValueError("Copy edition selection requires its explicit first-edition flag")
                    if selection == "unresolved" and "edition" not in identity.get("unresolved_fields", []):
                        raise ValueError("Unresolved edition must retain edition uncertainty")
                    if "first_edition_selected" in raw and raw["first_edition_selected"] != int(expected):
                        raise ValueError("First-edition selection conflicts with the catalog identity")
                count = counts.get(raw.get("printing_id"), 0) if p else 0
                result["checklist"].append(
                    {
                        "row": index,
                        "name": p["name"] if p else "Provisional identity",
                        "printing_id": raw.get("printing_id"),
                        "existing_copies": count,
                        "proposed_copies": int(not count or policy == "allow"),
                        "unresolved": p["unresolved_fields"] if p else ["identity"],
                    }
                )
                if count and policy == "reject":
                    raise ValueError("Duplicate printing; choose allow or skip explicitly")
                if count and policy == "skip":
                    continue
                copy(raw, index, source, binder_map.values())
                counts[raw.get("printing_id")] = count + 1
            except (ValueError, Http404) as error:
                result["errors"].append(
                    f"Row {index}: {str(error) or 'Binder is not available to this account'}"
                )
        sources, mapped, declarations = collection_goals.import_sources(actor, data, catalog_rows, owned)
        result["creates"].extend(declarations)
        imported_broad = broad_goals.remap_imports(
            data.get("goals", []), actor.user_id, operation_id, sources, mapped
        )
        seen_goals = set()
        for g in data.get("goals", []):
            if not isinstance(g, dict) or not isinstance(g.get("id"), str) or g["id"] in seen_goals:
                raise ValueError("Invalid or duplicate goal identity")
            seen_goals.add(g["id"])
            definition = collection_imports.goal_definition(g)
            collection_imports.validate_membership(
                g,
                definition,
                catalog_rows,
                games=store.rows("SELECT id,game_key,name FROM games") if g["kind"] == "filtered" else (),
                vintage_template=goal_definition(actor, {"goal_kind": "vintage"})
                if g["kind"] == "vintage"
                else None,
            )
            create(
                "goal",
                {
                    "id": stable_id("b2-goal-import", actor.user_id + operation_id + g["id"]),
                    "user_id": actor.user_id,
                    "name": name(g.get("name")),
                    "kind": g.get("kind", "custom"),
                    "version": digest(encode(imported_broad[g["id"]]).encode())
                    if g["id"] in imported_broad
                    else g["version"],
                    "definition": encode(imported_broad.get(g["id"], definition)),
                    "revision": 0,
                },
            )
        result["warnings"].append(
            "Source copy identities are retained; account-local IDs are remapped. Review every error and the explicit duplicate policy before confirming."
        )
    else:
        raise ValueError("Unsupported operation")
    return collection_intents.augment_plan(actor, kind, request, operation_id, result)
