"""B2 collection operations in the existing inventory, with durable reviewed transactions.

All entry points re-resolve the session principal. SQLite IMMEDIATE transactions serialize
confirmation/undo; revisioned before/after images prevent stale edits and destructive undo.
"""

import csv
import io
import json
import re
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import connection, transaction
from django.http import Http404

from pokemon_hunter.inventory import stable_id
from pokemon_hunter.migration import COPY_FIELDS, digest, encode

from . import store

SCHEMA = "dex-collection-v2"
TABLES = {"copy": "owned_copies", "binder": "binders", "goal": "collection_goals"}
FIELDS = (*COPY_FIELDS, "binder_id")


class Conflict(ValueError):
    pass


def initialize(db):
    """Called only while creating a NEW isolated B2 root, never on owner-local."""
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
        "INSERT INTO collection_generations VALUES(%s,1) ON CONFLICT(user_id) DO UPDATE SET value=value+1",
        [actor.user_id],
    )


def catalog(actor, query="", set_id=""):
    store.verified(actor)
    result = store.rows(
        "SELECT p.*,s.name AS set_name,s.catalog_version,s.coverage_status FROM printings p JOIN catalog_sets s ON s.id=p.set_id ORDER BY s.name,p.collector_number"
    )
    for row in result:
        row["attributes"] = json.loads(row["attributes"])
        row["unresolved_fields"] = json.loads(row["unresolved_fields"])
        row["name"] = row["attributes"].get("name", "Unidentified card")
    return [
        r
        for r in result
        if (not set_id or r["set_id"] == set_id)
        and query.casefold() in (r["name"] + " " + r["collector_number"] + " " + r["set_name"]).casefold()
    ]


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


def goals(actor):
    store.verified(actor)
    active = copies(actor)
    owned = {c["printing_id"] for c in active}
    exact_owned = {
        c["printing_id"]
        for c in active
        if c["printing_id"]
        and not json.loads(c["unresolved_fields"] or "[]")
        and not json.loads(c["provisional_identity"] or "{}").get("unresolved_fields")
    }
    result = store.rows("SELECT * FROM collection_goals WHERE user_id=%s ORDER BY name,id", [actor.user_id])
    for g in result:
        definition = json.loads(g["definition"])
        items = definition["items"]
        matched = [
            i
            for i in items
            if owned.intersection(i["printing_ids"])
            and (
                definition["policy"] != "exact"
                or (not i["unresolved"] and exact_owned.intersection(i["printing_ids"]))
            )
        ]
        g.update(definition=definition, satisfied=len(matched), total=len(items))
    return result


def export_data(actor):
    store.verified(actor)
    return {
        "schema": SCHEMA,
        "copies": copies(actor),
        "binders": binders(actor),
        "goals": goals(actor),
        "vintage_251": store.progress(copies(actor)),
        "catalog_scope": "Pinned supported catalog; unresolved variants are not exact completion. No market value is inferred.",
    }


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
    policy = request.get("policy", "catalog")
    if policy not in {"catalog", "exact"}:
        raise ValueError("Choose catalog-entry or exact-variant completion")
    entries = catalog(actor)
    if kind == "vintage":
        templates = store.rows("SELECT * FROM goal_templates WHERE id='vintage-251'")
        if not templates:
            raise ValueError("Vintage 251 template is not available")
        items = [
            {
                "label": f"Species {n:03}",
                "printing_ids": [
                    p["id"]
                    for p in entries
                    if p["attributes"].get("dex_eligible") and p["attributes"].get("pokemon_dex") == n
                ],
                "unresolved": False,
            }
            for n in range(1, 252)
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
        "items": [
            {
                "label": f"{p['name']} · {p['set_name']} #{p['collector_number']}",
                "printing_ids": [p["id"]],
                "unresolved": bool(p["unresolved_fields"]),
                "edition": p["edition"],
                "finish": p["finish"],
                "variant": p["variant"],
            }
            for p in entries
        ],
        "catalog_versions": sorted({p["catalog_version"] for p in entries}),
        "coverage": "Pinned catalog entries only; edition/variant coverage is not established. This is not a master-set completeness claim.",
    }


def parse_import(raw, format):
    if not isinstance(raw, str) or len(raw.encode()) > 1_500_000:
        raise ValueError("Import text must be at most 1.5 MB")
    if format == "csv":
        reader = csv.DictReader(io.StringIO(raw))
        allowed = {"id", "printing_id", *FIELDS}
        if (
            not reader.fieldnames
            or set(reader.fieldnames) - allowed
            or "printing_id" not in reader.fieldnames
            or len(set(reader.fieldnames)) != len(reader.fieldnames)
        ):
            raise ValueError(
                "CSV needs printing_id and optional id, condition, purchase_amount, purchase_currency, purchase_date, notes, binder_id, grading_company, grade, certificate headers"
            )
        data = {"copies": list(reader)}
    elif format == "json":
        try:
            data = json.loads(raw, parse_float=Decimal)
        except (ValueError, TypeError):
            raise ValueError("Invalid JSON") from None
        if isinstance(data, list):
            data = {"copies": data}
        if not isinstance(data, dict) or set(data) - {
            "schema",
            "copies",
            "binders",
            "goals",
            "vintage_251",
            "catalog_scope",
        }:
            raise ValueError("Use an inventory JSON array or a supported export object")
        if data.get("schema") not in {None, SCHEMA}:
            raise ValueError("Unsupported export schema version")
    else:
        raise ValueError("Choose CSV or JSON")
    if not isinstance(data.get("copies"), list) or len(data["copies"]) > 2000:
        raise ValueError("Import must have a copies array of at most 2000 rows")
    for key in ("binders", "goals"):
        if not isinstance(data.get(key, []), list) or len(data.get(key, [])) > 200:
            raise ValueError(f"Import {key} must be a list of at most 200 entries")
    return data


def plan(actor, kind, request, operation_id):
    """Produces immutable reviewed intent; confirmation recomputes before applying."""
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
                raw.get("first_edition_selected", p["edition"] == "first_edition" if p else 0)
            ),
            "state": "active",
            "revision": 0,
            "source_copy_id": source_id,
        }
        create("copy", row)

    catalog_rows = catalog(actor)
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
    if kind in {"add", "set"}:
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
            raise Conflict("This record changed. Reload it before making a new preview.")
        if entity == "copy" and before["state"] != "active":
            raise Conflict("This copy has already been removed")
        if kind == "edit":
            attrs = request.get("attributes", {})
            after = {
                **before,
                **attributes(actor, {**{k: before[k] for k in FIELDS}, **attrs}),
                "revision": before["revision"] + 1,
            }
        elif kind == "edition":
            selected = request.get("selection")
            if selected not in {"first_edition", "unresolved"}:
                raise ValueError("Choose first_edition or unresolved; unchecked never means unlimited")
            p = resolve(before["printing_id"])
            legacy = json.loads(p["provenance"]).get("legacy_id", "")
            if selected == "first_edition" and legacy.startswith(
                ("base_set_2-", "wizards_black_star_promos-")
            ):
                raise ValueError("This set has no standard first-edition printing")
            identity = json.loads(before["provisional_identity"] or "{}")
            unresolved = set(identity.get("unresolved_fields", [])) | set(p["unresolved_fields"])
            if selected == "first_edition":
                unresolved.discard("edition")
            else:
                unresolved.add("edition")
            identity.update(edition_selection=selected, unresolved_fields=sorted(unresolved))
            after = {
                **before,
                "first_edition_selected": int(selected == "first_edition"),
                "provisional_identity": encode(identity),
                "revision": before["revision"] + 1,
            }
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
                raise Conflict(
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
    elif kind == "goal":
        definition = goal_definition(actor, request)
        create(
            "goal",
            {
                "id": stable_id("b2-goal", actor.user_id + operation_id),
                "user_id": actor.user_id,
                "name": name(request.get("name")),
                "kind": request["goal_kind"],
                "version": digest(encode(definition).encode()),
                "definition": encode(definition),
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
                    expected = selection == "first_edition" if selection else p["edition"] == "first_edition"
                    legacy = json.loads(p["provenance"]).get("legacy_id", "")
                    if expected and legacy.startswith(("base_set_2-", "wizards_black_star_promos-")):
                        raise ValueError("This set has no standard first-edition printing")
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
        seen_goals = set()
        for g in data.get("goals", []):
            if not isinstance(g, dict) or not isinstance(g.get("id"), str) or g["id"] in seen_goals:
                raise ValueError("Invalid or duplicate goal identity")
            seen_goals.add(g["id"])
            if g.get("kind") not in {"set", "custom", "vintage"}:
                raise ValueError("Unsupported goal kind")
            definition = g.get("definition")
            if not isinstance(definition, dict) or definition.get("policy") not in {
                "species",
                "catalog",
                "exact",
            }:
                raise ValueError("Invalid goal definition")
            if g.get("version") != digest(encode(definition).encode()):
                raise ValueError("Goal membership version does not match")
            if not isinstance(definition.get("items"), list) or not 0 < len(definition["items"]) <= 2000:
                raise ValueError("Invalid goal checklist")
            if (definition["policy"] == "species") != (g["kind"] == "vintage"):
                raise ValueError("Species policy requires the versioned Vintage 251 template")
            if g["kind"] == "vintage":
                template = goal_definition(actor, {"goal_kind": "vintage"})
                if (
                    len(definition["items"]) != 251
                    or definition.get("rules") != template["rules"]
                    or definition.get("template_version") != template["template_version"]
                ):
                    raise ValueError("Vintage 251 template version/rules differ")
                for index, item in enumerate(definition["items"]):
                    if (
                        not isinstance(item, dict)
                        or item.get("label") != template["items"][index]["label"]
                        or not isinstance(item.get("printing_ids"), list)
                        or not set(item["printing_ids"]) <= set(template["items"][index]["printing_ids"])
                    ):
                        raise ValueError("Vintage 251 membership violates its frozen species rules")
            supported = set(catalog_by_id)
            for item in definition["items"]:
                if (
                    not isinstance(item, dict)
                    or not isinstance(item.get("label"), str)
                    or not isinstance(item.get("printing_ids"), list)
                    or not set(item["printing_ids"]) <= supported
                    or not isinstance(item.get("unresolved"), bool)
                ):
                    raise ValueError("Unsupported goal member")
                if (
                    definition["policy"] == "exact"
                    and not item["unresolved"]
                    and any(resolve(p)["unresolved_fields"] for p in item["printing_ids"])
                ):
                    raise ValueError("Unresolved variant cannot satisfy exact completion")
            create(
                "goal",
                {
                    "id": stable_id("b2-goal-import", actor.user_id + operation_id + g["id"]),
                    "user_id": actor.user_id,
                    "name": name(g.get("name")),
                    "kind": g.get("kind", "custom"),
                    "version": g["version"],
                    "definition": encode(definition),
                    "revision": 0,
                },
            )
        result["warnings"].append(
            "Source copy identities are retained; account-local IDs are remapped. Review every error and the explicit duplicate policy before confirming."
        )
    else:
        raise ValueError("Unsupported operation")
    return result


@transaction.atomic
def preview(actor, kind, request, operation_id):
    store.verified(actor)
    if not isinstance(request, dict):
        raise ValueError("Operation request must be an object")
    allowed = {
        "photo": {"printing_id", "provisional_identity", "attributes"},
        "add": {"printing_id", "attributes", "duplicate_policy"},
        "set": {"set_id", "attributes", "duplicate_policy"},
        "edit": {"id", "revision", "attributes"},
        "edition": {"id", "revision", "selection"},
        "remove": {"id", "revision"},
        "binder": {"name"},
        "binder_edit": {"id", "revision", "name"},
        "binder_remove": {"id", "revision"},
        "goal": {"name", "goal_kind", "set_id", "policy", "printing_ids"},
        "goal_remove": {"id", "revision"},
        "import": {"format", "text", "duplicate_policy"},
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
    bump(actor)
    return operation(actor, key)


@transaction.atomic
def undo(actor, key):
    store.verified(actor)
    op = operation(actor, key)
    if op["state"] == "undone":
        return op
    if op["state"] != "confirmed":
        raise Conflict("Only a confirmed operation can be undone")
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
    bump(actor)
    return operation(actor, key)
