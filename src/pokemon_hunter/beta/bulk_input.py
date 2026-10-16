"""Resolve finite bulk inputs against the current authorized catalog and collection.

Input-only formats remain publicly available here for existing callers; their
implementation lives in bulk_formats. This module owns no collection writer.
"""

import json
import re

from pokemon_hunter.migration import digest, encode

from . import card_groups, collection, effective_collection, store
from .bulk_formats import (
    ACTIONS as ACTIONS,
)
from .bulk_formats import (
    COLUMNS as COLUMNS,
)
from .bulk_formats import (
    DEFAULT_FIELDS as DEFAULT_FIELDS,
)
from .bulk_formats import (
    LIMIT as LIMIT,
)
from .bulk_formats import (
    MAX_BYTES as MAX_BYTES,
)
from .bulk_formats import (
    ROW_FIELDS as ROW_FIELDS,
)
from .bulk_formats import (
    SCHEMA as SCHEMA,
)
from .bulk_formats import (
    envelope as envelope,
)
from .bulk_formats import (
    export_rows as export_rows,
)
from .bulk_formats import (
    fingerprint as fingerprint,
)
from .bulk_formats import (
    parse_csv as parse_csv,
)
from .bulk_formats import (
    parse_paste as parse_paste,
)
from .bulk_formats import (
    positive as positive,
)
from .bulk_formats import (
    template as template,
)
from .collection_imports import FIELDS


def catalog_state(actor):
    entries = collection.catalog(actor)
    pokemon = {g["id"] for g in store.rows("SELECT id FROM games WHERE game_key='pokemon'")}
    grouped = card_groups.build_groups(entries, pokemon_game_ids=pokemon)
    return entries, grouped


def number_matches(number, groups):
    exact = [g for g in groups if g["collector_number"] == number]
    if exact:
        return exact
    if not re.fullmatch(r"[0-9]+(?:/[0-9]+)?", number):
        return []
    parts = number.split("/")
    return [
        g
        for g in groups
        if re.fullmatch(r"[0-9]+(?:/[0-9]+)?", g["collector_number"])
        and int(g["collector_number"].split("/")[0]) == int(parts[0])
        and (len(parts) == 1 or g["collector_number"].split("/")[1:] == parts[1:])
    ]


def normalize(actor, data):
    """Validate every row before duplicate/exclusion decisions; never select an arbitrary child."""
    entries, grouped = catalog_state(actor)
    groups = grouped["groups"]
    games = {g["id"]: g["game_key"] for g in store.rows("SELECT id,game_key FROM games")}
    aliases = {}
    for mapping in store.rows(
        "SELECT provider,external_id,internal_id FROM external_mappings WHERE entity_kind='set'"
    ):
        for alias in (mapping["external_id"], mapping["provider"] + ":" + mapping["external_id"]):
            aliases.setdefault(alias, set()).add(mapping["internal_id"])
    for s in store.rows("SELECT id,aliases FROM catalog_sets"):
        for alias in json.loads(s["aliases"]):
            aliases.setdefault(alias, set()).add(s["id"])
    current = effective_collection.project(actor)
    by_literal = {(r["set_name"], r["name"], r["number"]): r for r in current["cards"]}
    binders = collection.binders(actor)
    binder_ids = {b["id"] for b in binders}
    defaults = data["defaults"]
    lot = data.get("lot", {})
    if lot:
        collection.attributes(
            actor,
            {
                "purchase_amount": lot.get("lot_amount"),
                "purchase_currency": lot.get("lot_currency"),
                "purchase_date": lot.get("lot_date"),
            },
        )
    output, seen, certificates = [], {}, {}
    expanded = 0
    for raw in data["rows"]:
        result = dict(row_id=raw["row_id"], included=raw.get("included", True), errors=[], warnings=[])
        output.append(result)
        try:
            if type(result["included"]) is not bool or type(raw.get("keep_unknown", False)) is not bool:
                raise ValueError("Included and Keep variant unknown must be explicit choices")
            if any(
                not isinstance(v, (str, int, bool, type(None))) for k, v in raw.items() if k != "literal_text"
            ):
                raise ValueError("Row values must be text")
            row = {**defaults}
            if any(raw.get(k) for k in ("printing_id", "group_id", "set_id", "set")):
                row.pop("set_id", None)
                row.pop("set", None)
            for k, v in raw.items():
                if v != "":
                    row[k] = (
                        None
                        if v == "unknown" and k not in {"total", "row_id", *raw.get("literal_text", [])}
                        else v
                    )
            action = row.get("action", "add_copies")
            if action not in ACTIONS:
                raise ValueError("action: choose add_copies, set_total or mark_owned")
            result["action"] = action
            candidates = groups
            for key, field in (
                ("game", None),
                ("set_id", "set_id"),
                ("set", "set_name"),
                ("language", "language"),
                ("group_id", "id"),
                ("name", "name"),
            ):
                value = row.get(key)
                if value:
                    candidates = [
                        g
                        for g in candidates
                        if (
                            (games.get(g["game_id"]) if key == "game" else g[field]) == value
                            or (key == "set" and aliases.get(value) == {g["set_id"]})
                        )
                    ]
            if row.get("number"):
                candidates = number_matches(str(row["number"]).strip(), candidates)
            if row.get("printing_id"):
                candidates = [
                    g for g in candidates if row["printing_id"] in {p["id"] for p in g["_children"]}
                ]
            if not (
                row.get("printing_id")
                or row.get("group_id")
                or ((row.get("set_id") or row.get("set")) and row.get("number"))
            ):
                raise ValueError("identity: choose a printing or a set and card number")
            if len(candidates) != 1:
                raise ValueError("identity: no unique supported card; correct set/language/number/name")
            g = candidates[0]
            key = (g["set_name"], g["name"], g["collector_number"])
            existing = by_literal.get(key)
            if not existing or existing["identity_status"] == "conflict":
                raise ValueError("identity: conflicting catalog evidence needs correction")
            identity = dict(
                set_name=g["set_name"],
                name=g["name"],
                number=g["collector_number"],
                language=g["language"],
                pokemon_dex=g["pokemon_dex"],
                candidate_printing_ids=sorted(p["id"] for p in g["_children"]),
            )
            result.update(
                group_id=g["id"],
                identity=identity,
                existing={
                    k: existing[k]
                    for k in (
                        "present",
                        "established_total_quantity",
                        "recorded_copy_count",
                    )
                },
                current_copy_count=len(existing["current_copy_ids"]),
                url=g["url"],
                matched_number=g["collector_number"],
            )
            if row.get("number") and row["number"] != g["collector_number"]:
                result["warnings"].append("Number alias resolved to " + g["collector_number"])
            children = g["_children"]
            for field in ("printing_id", "edition", "finish", "variant"):
                value = row.get(field)
                if value:
                    children = [p for p in children if p["id" if field == "printing_id" else field] == value]
            if not children:
                raise ValueError("variant: this combination is not supported for this card")
            result["candidates"] = [
                dict(
                    id=p["id"],
                    edition=p["edition"],
                    finish=p["finish"],
                    variant=p["variant"],
                    unresolved_fields=p["unresolved_fields"],
                )
                for p in children
            ]
            copy_fields = set(FIELDS) | {"location", "purchase_basis"}
            if action != "add_copies":
                if any(row.get(k) is not None and row.get(k) != "" for k in copy_fields | {"quantity"}):
                    raise ValueError("Copy fields and quantity are not applicable to this action; clear them")
                if any(row.get(k) for k in ("printing_id", "edition", "finish", "variant")):
                    result["warnings"].append("Broad action grants no exact variant ownership")
                if action == "mark_owned":
                    if row.get("total") not in (None, ""):
                        raise ValueError("total: not applicable to Mark owned")
                    result["noop"] = existing["present"]
                else:
                    if not existing["present"]:
                        raise ValueError("total: mark this card owned in a separate reviewed batch first")
                    total = row.get("total")
                    total = None if total == "unknown" else positive(total)
                    if total is not None and total < len(existing["current_copy_ids"]):
                        raise ValueError("total: below current supported physical-copy count")
                    result["total"] = total
                result["quantity"] = 0
            else:
                if row.get("total") not in (None, ""):
                    raise ValueError("total: not applicable to Add physical copies")
                quantity = positive(row.get("quantity", 1))
                if quantity > 1 and row.get("certificate"):
                    raise ValueError("certificate: use separate copy rows, never clone one certificate")
                if bool(row.get("grading_company")) != bool(row.get("grade")):
                    raise ValueError("grading_company and grade must be paired")
                if row.get("purchase_amount") and row.get("purchase_basis") != "per_copy":
                    raise ValueError("purchase_basis: choose per_copy for a per-copy amount")
                if row.get("purchase_basis") not in (None, "", "per_copy"):
                    raise ValueError("purchase_basis: only per_copy is supported")
                attrs = {k: row.get(k) for k in FIELDS}
                location = row.get("location")
                if location:
                    if not isinstance(location, str) or len(location) > 1000:
                        raise ValueError("location: at most 1,000 characters")
                    attrs["notes"] = "\n".join(filter(None, [attrs.get("notes"), "Location: " + location]))
                if attrs.get("binder_id") and attrs["binder_id"] not in binder_ids:
                    raise ValueError("binder_id: choose an existing binder in this account")
                if attrs.get("purchase_date") and not re.fullmatch(
                    r"[0-9]{4}-[0-9]{2}-[0-9]{2}", attrs["purchase_date"]
                ):
                    raise ValueError("purchase_date: use YYYY-MM-DD")
                attrs = collection.attributes(actor, attrs, binder_ids)
                result.update(
                    quantity=quantity,
                    attributes=attrs,
                    printing_id=None,
                    unresolved_fields=["edition", "finish", "variant"],
                )
                if row.get("keep_unknown"):
                    result["provisional_identity"] = encode(
                        dict(
                            group_binding=dict(
                                group_id=g["id"],
                                identity=identity,
                                candidate_printing_ids=sorted(p["id"] for p in children),
                                catalog_versions=sorted({p["catalog_version"] for p in children}),
                            ),
                            unresolved_fields=["edition", "finish", "variant"],
                        )
                    )
                elif len(children) == 1:
                    p = children[0]
                    result.update(printing_id=p["id"], unresolved_fields=p["unresolved_fields"])
                else:
                    raise ValueError("variant: select a supported child or choose Keep variant unknown")
                if row.get("purchase_amount") and quantity > 1:
                    result["warnings"].append(f"Per-copy purchase amount is repeated on {quantity} copies")
                if existing["recorded_copy_count"]:
                    result["warnings"].append("Existing records do not prove this is the same physical copy")
                cert = attrs.get("certificate")
                if cert and result["included"] and row.get("duplicate_decision") != "skip":
                    certificates.setdefault(cert, []).append(result)
            previous = (
                seen.setdefault(key, [])
                if result["included"] and row.get("duplicate_decision") != "skip"
                else []
            )
            if previous:
                if action != "add_copies" or any(r["action"] != action for r in previous):
                    for r in [*previous, result]:
                        r["errors"].append("Conflicting or repeated actions for the same broad card identity")
                elif row.get("duplicate_decision") not in {"different", "skip"}:
                    result["errors"].append(
                        "Repeated card input: choose Different copies or Same copy / skip"
                    )
            previous.append(result)
            decision = row.get("duplicate_decision")
            if decision not in (None, "", "different", "skip"):
                raise ValueError("Choose a supported duplicate decision")
            result["skipped"] = decision == "skip"
            if result["included"] and not result["skipped"]:
                expanded += result["quantity"] if action == "add_copies" else int(not result.get("noop"))
        except (ValueError, TypeError) as exc:
            result["errors"].append(str(exc))
    for matches in certificates.values():
        if len(matches) > 1:
            for result in matches:
                raw = next(r for r in data["rows"] if r["row_id"] == result["row_id"])
                if raw.get("duplicate_decision") != "different":
                    result["errors"].append("Repeated certificate: confirm Different copies or correct it")
    if expanded > LIMIT:
        raise ValueError("Expanded copies/intents exceed 2,000; no splitting or partial confirmation")
    return dict(
        rows=output,
        expanded=expanded,
        catalog_hash=digest(
            encode(dict(entries=entries, aliases={k: sorted(v) for k, v in aliases.items()})).encode()
        ),
        binder_hash=digest(encode(binders).encode()),
        generation=current["generation"],
        lot=data.get("lot", {}),
    )
