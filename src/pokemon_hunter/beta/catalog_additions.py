"""Immutable numbered-parent extensions of an existing reviewed catalog.

The original set version remains the reference identity contract. Extension versions
and full retained enumeration describe separate, historical publication evidence.
"""

import json
from typing import Literal

from pydantic import Field

from pokemon_hunter.inventory import stable_id
from pokemon_hunter.migration import encode

from . import catalog_imports as cat
from . import store

SCHEMA = "dex-catalog-additions-v1"


class Package(cat.Package):
    schema_version: Literal["dex-catalog-additions-v1"]
    source_set_key: str = Field(min_length=1, max_length=80)
    source_time: str = Field(min_length=1, max_length=80)
    source_members: dict[str, dict[str, str]]
    set_id: str = Field(min_length=1, max_length=120)
    set_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    enumeration: list[cat.Record] = Field(min_length=1, max_length=2000)
    represented: dict[str, dict[str, str]]
    coverage: Literal["catalog-entries"]


def validate(raw):
    p = Package.model_validate(raw).model_dump()
    if p.pop("reconcile_legacy_set") is not None or p["aliases"]:
        raise ValueError("Extensions retain existing aliases and reviewed set mappings")
    cat.identity(p["game"], p["set_key"], p["language"])
    if p["game"] != "pokemon" or p["language"] != "en":
        raise ValueError("Only reviewed English Pokemon numbered extensions are supported")
    for group in (p["cards"], p["enumeration"]):
        for c in group:
            if c.pop("legacy_id") is not None or c["metadata"] is None:
                raise ValueError("Resolved metadata and no reassigned legacy identity required")
            if any(c[k] is not None for k in ("edition", "finish", "variant")):
                raise ValueError("Numbered additions require unknown physical attributes")
        if len({c["external_id"] for c in group}) != len(group) or len({c["number"] for c in group}) != len(
            group
        ):
            raise ValueError("Duplicate numbered or external identity")
    if any(
        not bindings or any(not (key == external or key.startswith(external + ":")) for key in bindings)
        for external, bindings in p["represented"].items()
    ):
        raise ValueError("Unreviewed represented mapping spelling")
    full = {c["external_id"]: c for c in p["enumeration"]}
    import re

    from .sealed_catalog import instant

    instant(p["source_time"])
    if set(p["source_members"]) != set(full) or any(
        set(m) != {"path", "sha256"} or not m["path"] or re.fullmatch(r"[a-f0-9]{64}", m["sha256"]) is None
        for m in p["source_members"].values()
    ):
        raise ValueError("Every enumerated identity requires retained member provenance")
    new = {c["external_id"]: c for c in p["cards"]}
    if (
        len(full) != p["expected_count"]
        or set(full) != set(new) | set(p["represented"])
        or set(new) & set(p["represented"])
        or any(full.get(k) != c for k, c in new.items())
    ):
        raise ValueError("Full enumeration must partition represented records and exact additions")
    return p


def rows_for(p):
    baseline = cat.snapshot(p["set_id"])
    if len(baseline["sets"]) != 1:
        raise ValueError("An existing published set is required")
    s = baseline["sets"][0]
    provider = p["provider"] + ":" + p["language"]
    mapping = store.rows(
        "SELECT internal_id FROM external_mappings WHERE provider=%s AND entity_kind='set' AND external_id=%s",
        [provider, p["source_set_key"]],
    )
    game = store.rows("SELECT game_key FROM games WHERE id=%s", [s["game_id"]])
    if (
        cat.fingerprint(s) != p["set_sha256"]
        or s["publication_state"] != "published"
        or s["language"] != p["language"]
        or not game
        or game[0]["game_key"] != p["game"]
        or mapping != [{"internal_id": s["id"]}]
    ):
        raise ValueError("Existing set row or reviewed provider mapping changed")
    existing = {r["id"]: r for r in baseline["cards"]}
    all_records = {r["external_id"]: r for r in p["enumeration"]}
    # Check the full represented cohort, including archived identities, without editing it.
    represented_package = dict(
        p,
        cards=[
            dict(all_records[e], external_id=key)
            for e, bindings in p["represented"].items()
            for key in bindings
        ],
    )
    mappings, _, _ = cat.identity_rows(represented_package, s["id"], provider)
    for external, bindings in p["represented"].items():
        for key, pid in bindings.items():
            row = existing.get(pid)
            c = all_records[external]
            if not row or mappings.get(key) != pid or row["collector_number"] != c["number"]:
                raise ValueError("Represented numbered identity or mapping changed")
            attrs = json.loads(row["attributes"])
            if any(attrs.get(k) != c["metadata"].get(k) for k in ("pokemon_dex", "supertype")):
                raise ValueError("Represented category/species conflict")
    mappings, identities, numbers = cat.identity_rows(p, s["id"], provider)
    result = dict(existing)
    for c in p["cards"]:
        pid = stable_id("catalog-printing", provider + ":" + c["external_id"])
        if mappings.get(c["external_id"], pid) != pid:
            raise ValueError("External identity is already mapped to a different printing")
        if numbers.get((c["number"], None, None, None), set()) - {pid}:
            raise ValueError("Numbered identity already exists; explicit reuse review required")
        row = dict(
            id=pid,
            set_id=s["id"],
            collector_number=c["number"],
            language=p["language"],
            edition=None,
            finish=None,
            variant=None,
            unresolved_fields=encode(["edition", "finish", "variant"]),
            attributes=encode(dict(name=c["name"], game_key=p["game"], synthetic=False, **c["metadata"])),
            provenance=encode(
                dict(
                    provider=provider,
                    external_id=c["external_id"],
                    source_version=p["version"],
                    source_sha256=p["source_sha256"],
                    extension_schema=SCHEMA,
                    source_url=p["source_url"],
                    source_time=p["source_time"],
                    source_member=p["source_members"][c["external_id"]],
                )
            ),
            publication_state="published",
        )
        old = identities.get(pid)
        if old and dict(old, publication_state="published") != row:
            raise ValueError("Stable identity has different extension evidence; use a forward repair")
        result[pid] = row
    return s, list(result.values())


def guard_rollback(op):
    """Protect all added numbered parents, even without parent_printing_id."""
    if op["package"]["schema_version"] != SCHEMA:
        return
    from .collection import Conflict

    added = {r["id"]: r for r in op["preview"]["added"]}
    for pid, row in added.items():
        if store.rows("SELECT id FROM owned_copies WHERE printing_id=%s LIMIT 1", [pid]):
            raise Conflict("A new numbered identity has collection activity; use a forward repair")
        provenance = json.loads(row["provenance"])
        allowed = dict(
            provider=provenance["provider"],
            entity_kind="printing",
            external_id=provenance["external_id"],
            internal_id=pid,
        )
        if any(
            m != allowed for m in store.rows("SELECT * FROM external_mappings WHERE internal_id=%s", [pid])
        ):
            raise Conflict("Later mappings depend on an addition; use a forward repair")
    if not added:
        return
    from django.db import connection

    tables = set(connection.introspection.table_names())
    for table, column in (("import_records", "printing_id"), ("sealed_bridges", "catalog_id")):
        if table in tables:
            for pid in added:
                if store.rows(f"SELECT {column} FROM {table} WHERE {column}=%s LIMIT 1", [pid]):
                    raise Conflict(
                        "Later publication or import records depend on an addition; use a forward repair"
                    )
    for row in store.rows("SELECT id,attributes FROM printings"):
        if json.loads(row["attributes"]).get("parent_printing_id") in added:
            raise Conflict("Descendant variants depend on an addition; use a forward repair")
    for goal in store.rows("SELECT definition FROM collection_goals"):
        if any(pid in goal["definition"] for pid in added):
            raise Conflict("A frozen goal references an addition; use a forward repair")
    for journal in store.rows("SELECT id,package,baseline FROM catalog_imports WHERE state='published'"):
        if journal["id"] != op["id"] and any(
            pid in journal["package"] or pid in journal["baseline"] for pid in added
        ):
            raise Conflict("A later publication depends on an addition; use a forward repair")
