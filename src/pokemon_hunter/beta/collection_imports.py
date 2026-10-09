"""Serialized collection imports and frozen checklist validation, without persistence.

The transaction service supplies the catalog, games and historical template;
this module never resolves accounts, remaps identities or writes collection rows.
"""

import csv
import io
import json
from decimal import Decimal

from pokemon_hunter.migration import COPY_FIELDS, digest, encode

from . import collection_goals, goal_filters

SCHEMA = "dex-collection-v2"
FIELDS = (*COPY_FIELDS, "binder_id")


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
            "collection_sources",
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


def goal_definition(g):
    """Validate the serialized policy and hash before loading membership context."""
    if g.get("kind") not in {
        "set",
        "custom",
        "vintage",
        "filtered",
        "original151",
        *collection_goals.OWNERSHIP_KINDS,
    }:
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
    if g["kind"] not in {"filtered", "original151", *collection_goals.OWNERSHIP_KINDS} and (
        definition["policy"] == "species"
    ) != (g["kind"] == "vintage"):
        raise ValueError("Species policy requires the versioned Vintage 251 template")
    return definition


def validate_membership(g, definition, catalog_rows, *, games=(), vintage_template=None):
    """Check frozen membership against explicitly supplied reviewed inputs."""
    catalog_by_id = {p["id"]: p for p in catalog_rows}
    if g["kind"] == "filtered":
        scope = goal_filters.filters(definition.get("filters"), catalog_rows, games)
        permitted = {p["id"] for p in catalog_rows if goal_filters.matches(p, scope)}
        if definition["filters"] != scope or (definition["policy"] == "species") != (
            scope["completion"] == "species"
        ):
            raise ValueError("Goal filters and completion policy differ")
        if definition["policy"] == "species":
            expected = list(range(scope["pokemon_dex_min"], scope["pokemon_dex_max"] + 1))
            if [i.get("pokemon_dex") for i in definition["items"] if isinstance(i, dict)] != expected:
                raise ValueError("Goal species membership differs from its filters")
        seen_printings = set()
        for item in definition["items"]:
            ids = item.get("printing_ids", []) if isinstance(item, dict) else []
            if (
                not isinstance(ids, list)
                or any(not isinstance(i, str) for i in ids)
                or len(ids) != len(set(ids))
                or not set(ids) <= permitted
            ):
                raise ValueError("Goal membership is outside its filters")
            if definition["policy"] == "species" and any(
                catalog_by_id[pid]["attributes"].get("pokemon_dex") != item["pokemon_dex"] for pid in ids
            ):
                raise ValueError("Printing belongs to a different species")
            if definition["policy"] != "species" and (len(ids) != 1 or seen_printings.intersection(ids)):
                raise ValueError("Printing checklist repeats an identity")
            seen_printings.update(ids)
    if g["kind"] == "vintage":
        template = vintage_template
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
            and any(catalog_by_id[p]["unresolved_fields"] for p in item["printing_ids"])
        ):
            raise ValueError("Unresolved variant cannot satisfy exact completion")
