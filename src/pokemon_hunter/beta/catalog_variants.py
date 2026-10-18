"""Additive, evidenced physical variants through the catalog import journal.

Set versions describe the original numbered catalog. An additive variant package
has its own immutable version and never rewrites that catalog's identity fields.
Literal descriptors are indivisible evidence, not availability flags to multiply.
"""

import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from pokemon_hunter.inventory import stable_id
from pokemon_hunter.migration import encode

from . import store

SCHEMA = "dex-catalog-variants-v1"
PROVIDER = "dex-evidenced-variant"


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    source_url: str = Field(min_length=1, max_length=1000)
    revision: str = Field(min_length=1, max_length=120)
    archive_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    member: str = Field(min_length=1, max_length=300)
    member_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    lineage: str = Field(min_length=1, max_length=200)
    source_identity: str = Field(min_length=1, max_length=200)
    source_descriptor: dict
    original_member_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class Variant(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    parent_id: str = Field(min_length=1, max_length=120)
    parent_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    descriptor: dict
    evidence: Evidence


class Package(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal["dex-catalog-variants-v1"]
    game: Literal["pokemon"]
    set_id: str
    set_key: str
    set_name: str
    language: Literal["en"]
    provider: Literal["dex-evidenced-variant"]
    version: str = Field(min_length=1, max_length=120)
    source_url: str = Field(min_length=1, max_length=1000)
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    metadata_permission: str = Field(min_length=1, max_length=1000)
    image_permission: Literal["not-included"]
    coverage: Literal["partial"]
    expected_count: int = Field(ge=1, le=2000)
    cards: list[Variant] = Field(min_length=1, max_length=2000)


def descriptor(value):
    """Closed literal grammar; unknown evidence requires a future reviewed schema."""
    if (
        not isinstance(value, dict)
        or not value
        or set(value) - {"type", "stamp", "foil", "copyright", "subtype", "size", "other", "languages"}
    ):
        raise ValueError("Unsupported literal variant descriptor")
    if value.get("type") not in {"normal", "holo", "reverse"}:
        raise ValueError("Literal finish type required")
    for key in ("stamp", "other", "languages"):
        if key in value and (
            not isinstance(value[key], list)
            or not value[key]
            or any(not isinstance(v, str) or not v or len(v) > 120 for v in value[key])
            or len(set(value[key])) != len(value[key])
        ):
            raise ValueError("Invalid literal variant evidence")
    for key in ("foil", "copyright", "subtype", "size"):
        if key in value and (not isinstance(value[key], str) or not 1 <= len(value[key]) <= 120):
            raise ValueError("Invalid literal physical attribute")
    if "languages" in value and value["languages"] != ["en"]:
        raise ValueError("English evidence cannot assign another language")
    if "stamp" in value and value["stamp"] not in (["1st-edition"], ["25th-celebration"]):
        raise ValueError("Unreviewed stamp combination")
    if (
        value.get("stamp") == ["25th-celebration"]
        and value.get("size") != "jumbo"
        or "foil" in value
        and (value["foil"] != "galaxy" or value["type"] != "normal")
        or "subtype" in value
        and (value["subtype"] != "1999-2000-copyright" or value["type"] != "normal" or "stamp" in value)
    ):
        raise ValueError("Contradictory or unreviewed physical combination")
    return value


def physical(value):
    descriptor(value)
    edition = "first_edition" if value.get("stamp") == ["1st-edition"] else None
    finish = {"normal": "normal", "holo": "holo", "reverse": "reverse-holo"}[value["type"]]
    # A special foil cannot become an ordinary nonfoil merely from type: normal.
    if "foil" in value:
        finish = None
    return edition, finish, encode(value)


def label(value):
    parts = []
    if value.get("stamp") == ["1st-edition"]:
        parts.append("1st Edition")
    parts.append({"normal": "Normal", "holo": "Holo", "reverse": "Reverse Holo"}[value["type"]])
    parts.extend(
        f"{key.title()}: {value[key]}" for key in ("foil", "copyright", "subtype", "size") if key in value
    )
    if value.get("stamp") == ["25th-celebration"]:
        parts.append("25th celebration stamp")
    parts.extend(value.get("other", []))
    if value.get("stamp") != ["1st-edition"]:
        parts.append("edition not established")
    return " · ".join(parts)


def validate(raw):
    p = Package.model_validate(raw).model_dump()
    if len(p["cards"]) != p["expected_count"]:
        raise ValueError("Descriptor inventory count differs")
    seen = set()
    for card in p["cards"]:
        key = card["parent_id"], encode(descriptor(card["descriptor"]))
        if key in seen:
            raise ValueError("Repeated parent/descriptor")
        seen.add(key)
        if card["evidence"]["archive_sha256"] != p["source_sha256"]:
            raise ValueError("Variant archive lineage conflicts")
        if {k: v for k, v in card["evidence"]["source_descriptor"].items() if k != "thirdParty"} != card[
            "descriptor"
        ]:
            raise ValueError("Literal descriptor differs from retained source evidence")
    return p


def rows_for(p):
    from . import catalog_imports as cat

    baseline = cat.snapshot(p["set_id"])
    if len(baseline["sets"]) != 1:
        raise ValueError("An existing published numbered catalog is required")
    setrow = baseline["sets"][0]
    games = store.rows("SELECT game_key FROM games WHERE id=%s", [setrow["game_id"]])
    if (
        setrow["publication_state"] != "published"
        or setrow["name"] != p["set_name"]
        or setrow["language"] != p["language"]
        or not games
        or games[0]["game_key"] != p["game"]
    ):
        raise ValueError("Variant publication catalog mismatch")
    existing = {r["id"]: r for r in baseline["cards"]}
    rows = dict(existing)
    for proposal in p["cards"]:
        parent = existing.get(proposal["parent_id"])
        if (
            not parent
            or parent["publication_state"] != "published"
            or any(parent[k] is not None for k in ("edition", "finish", "variant"))
            or parent["language"] != p["language"]
            or cat.fingerprint(parent) != proposal["parent_sha256"]
            or json.loads(parent["attributes"]).get("parent_printing_id")
        ):
            raise ValueError("Parent changed or is not an unspecified numbered identity")
        value = proposal["descriptor"]
        edition, finish, variant = physical(value)
        external = parent["id"] + ":" + cat.fingerprint(value)
        pid = stable_id("catalog-printing", PROVIDER + ":en:" + external)
        matches = [
            r
            for r in existing.values()
            if all(
                r[k] == v
                for k, v in {
                    "collector_number": parent["collector_number"],
                    "language": parent["language"],
                    "edition": edition,
                    "finish": finish,
                    "variant": variant,
                }.items()
            )
        ]
        if len(matches) > 1:
            raise ValueError("Conflicting identical variants require reconciliation")
        prior = matches[0] if matches else None
        if prior:
            pid = prior["id"]
            parent_attrs = json.loads(parent["attributes"])
            prior_attrs = json.loads(prior["attributes"])
            if any(prior_attrs.get(k) != parent_attrs.get(k) for k in ("name", "supertype", "pokemon_dex")):
                raise ValueError("Identical physical fields conflict with numbered-card metadata")
            other = json.loads(prior["attributes"]).get("parent_printing_id")
            if other and other != parent["id"]:
                raise ValueError("Variant is linked to another parent")
        elif store.rows("SELECT id FROM printings WHERE id=%s", [pid]):
            raise ValueError("Stable variant ID conflicts with another physical identity")
        mappings = store.rows(
            "SELECT internal_id FROM external_mappings WHERE provider=%s AND entity_kind='printing' AND external_id=%s",
            [PROVIDER + ":en", external],
        )
        if mappings and mappings[0]["internal_id"] != pid:
            raise ValueError("Variant external mapping conflict")
        attrs = json.loads((prior or parent)["attributes"])
        attrs.update(parent_printing_id=parent["id"], physical_variant=value, variant_label=label(value))
        provenance = (
            json.loads(prior["provenance"])
            if prior
            else {
                "provider": PROVIDER + ":en",
                "external_id": external,
                "source_version": p["version"],
                "source_sha256": p["source_sha256"],
            }
        )
        evidence = dict(proposal["evidence"], descriptor=value, parent_id=parent["id"])
        if prior and provenance.get("variant_evidence") not in (None, evidence):
            raise ValueError("Existing variant evidence conflicts; use a forward reviewed correction")
        provenance["variant_evidence"] = evidence
        rows[pid] = dict(
            prior or {},
            id=pid,
            set_id=parent["set_id"],
            collector_number=parent["collector_number"],
            language=parent["language"],
            edition=edition,
            finish=finish,
            variant=variant,
            unresolved_fields=encode([k for k, v in (("edition", edition), ("finish", finish)) if v is None]),
            attributes=encode(attrs),
            provenance=encode(provenance),
            publication_state="published",
        )
    # Existing parent/sibling rows and the entire set row survive byte-for-byte.
    return setrow, list(rows.values())


def guard_replacement(baseline, cards):
    """A numbered-catalog replacement may not silently remove a variant family."""
    incoming = {c["id"]: c for c in cards}
    for old in baseline["cards"]:
        parent = json.loads(old["attributes"]).get("parent_printing_id")
        if old["publication_state"] == "published" and parent:
            if old["id"] not in incoming or parent not in incoming or incoming[old["id"]] != old:
                raise ValueError("Retain the evidenced variant family or prepare a forward reviewed repair")


def guard_rollback(op):
    from .collection import Conflict

    old_ids = {r["id"] for r in op["baseline"]["cards"]}
    added = [
        r["id"]
        for r in store.rows("SELECT id,attributes FROM printings WHERE set_id=%s", [op["set_id"]])
        if r["id"] not in old_ids and json.loads(r["attributes"]).get("parent_printing_id")
    ]
    if not added:
        return
    for pid in added:
        if store.rows("SELECT id FROM owned_copies WHERE printing_id=%s LIMIT 1", [pid]):
            raise Conflict("A new identity has collection activity; retain it and use a forward repair")
    for goal in store.rows("SELECT definition FROM collection_goals"):
        if any(pid in goal["definition"] for pid in added):
            raise Conflict("A frozen goal references a new identity; use a forward repair")


def display(row):
    attrs = row["attributes"]
    parent = attrs.get("parent_printing_id")
    row["parent_printing_id"] = parent
    row["numbered_card_id"] = parent or row["id"]
    row["variant_label"] = attrs.get("variant_label") or (
        "Variant not specified"
        if all(row.get(k) is None for k in ("edition", "finish", "variant"))
        else " · ".join(str(row[k]) for k in ("edition", "finish", "variant") if row.get(k))
    )
    return row


def seller_candidates(candidates, clues):
    families = {}
    for p in candidates:
        parent = p.get("parent_printing_id") or p.get("attributes", {}).get("parent_printing_id")
        families.setdefault(parent or p["id"], []).append(p)
    result = []
    special = bool(
        re.search(r"\b(?:jumbo|galaxy|celebration|copyright|1999[ -]+2000)\b", clues["text"], re.I)
    )
    for family in families.values():
        exact = []
        for p in family:
            value = p.get("attributes", {}).get("physical_variant")
            if not value or set(value) - {"type", "stamp", "languages"} or special:
                continue
            if (
                p.get("edition")
                and clues.get("edition") == p["edition"]
                and clues.get("finish") == p.get("finish")
            ):
                exact.append(p)
        result.extend(exact if len(exact) == 1 else family)
    return result
