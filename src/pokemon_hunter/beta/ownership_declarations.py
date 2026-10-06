"""Account-local presence evidence, independent of physical copies and frozen goals."""

import csv
import io
import json
import re

from django.db import connection

from pokemon_hunter.inventory import stable_id
from pokemon_hunter.migration import digest, encode

from . import store
from .canonical_species import registry

HEADERS = [
    "Dex",
    "Pokemon",
    "Base",
    "Base 2",
    "Jungle",
    "Fossil",
    "Team Rocket",
    "Wizards Black Star Promos",
    "Neo Genesis",
    "Neo Discovery",
    "Neo Revelation",
    "Neo Destiny",
    "Boundaries Crossed",
]
GEN2_HEADERS = ["Dex", "Pokemon", "Neo Genesis", "Neo Discovery", "Plasma Storm", "Dark Explorers"]
FULL_HEADERS = (
    ["Dex", "Pokemon", "Status", "Base Set", "Base Set 2"] + HEADERS[4:] + ["Plasma Storm", "Dark Explorers"]
)
PHOTO_HEADERS = FULL_HEADERS + [
    "Call of Legends",
    "Diamond & Pearl",
    "Mysterious Treasures",
    "EX Trainer Kit 2 — Minun",
    "Ownership notes",
]
ALIASES = {"Base": "Base Set", "Base 2": "Base Set 2"}


def initialize(db):
    db.execute("""CREATE TABLE IF NOT EXISTS ownership_declarations(
        id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
        source_sha256 TEXT NOT NULL, source_text TEXT NOT NULL,
        reconciliation TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0,
        UNIQUE(user_id,source_sha256))""")


def available():
    return "ownership_declarations" in connection.introspection.table_names()


def parse(text, sha256):
    if not isinstance(text, str) or len(text.encode()) > 100_000 or digest(text.encode()) != sha256:
        raise ValueError("Declaration source bytes/hash mismatch or oversized input")
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff"), newline=""))
    full = reader.fieldnames in [FULL_HEADERS, PHOTO_HEADERS]
    card_columns = [k for k in (reader.fieldnames or [])[3 if full else 2 :] if k != "Ownership notes"]
    if full:
        lower, upper = 1, 251
    elif reader.fieldnames == HEADERS:
        lower, upper = 1, 151
    elif reader.fieldnames == GEN2_HEADERS:
        lower, upper = 152, 251
    else:
        raise ValueError("Unsupported collection declaration columns")
    names = registry()
    result, seen = [], set()
    for row in reader:
        try:
            n = int(row["Dex"])
        except (ValueError, TypeError):
            raise ValueError("Invalid species number") from None
        if not lower <= n <= upper or n in seen or None in row or None in row.values():
            raise ValueError("Invalid, duplicate or out-of-scope species row")
        seen.add(n)
        # Symbols differ between the retained canonical registry and owner's ledger.
        name = row["Pokemon"].replace("♀", " Female").replace("♂", " Male")
        canonical = names[n]["name"].replace("♀", " Female").replace("♂", " Male")
        if name.casefold() != canonical.casefold():
            raise ValueError("Species name/number mismatch")
        if full and (
            row["Status"] not in {"Owned", "Missing"}
            or (row["Status"] == "Owned") != any(row[k] for k in card_columns)
        ):
            raise ValueError("Declared status and card marks disagree")
        for label in card_columns:
            cell = row[label]
            marker = cell.split(" ", 1)[0] if full and cell else cell
            if marker not in {"", "✓", "✓D", "✓EX"}:
                raise ValueError("Unknown ownership marker")
            if marker == "✓D" and (label != "Team Rocket" or not 1 <= n <= 151):
                raise ValueError("Unreviewed special marker applicability")
            if marker == "✓EX" and (label != "Plasma Storm" or not 1 <= n <= 251):
                raise ValueError("Unreviewed special marker applicability")
            if marker:
                detail = (
                    re.fullmatch(r"✓(?:D|EX)? (.+) #([A-Za-z0-9-]+) \(([^()]+)\)", cell) if full else None
                )
                result.append(
                    dict(
                        pokemon_dex=n,
                        name=row["Pokemon"],
                        set_name=ALIASES.get(label, label),
                        source_set=label,
                        marker=marker,
                        source_cell=cell,
                        ownership_notes=row.get("Ownership notes", ""),
                        source_scope="full251" if full else "kanto" if lower == 1 else "johto",
                        declared_card_name=detail[1] if detail else None,
                        declared_card_number=detail[2] if detail else None,
                        declared_rarity=detail[3] if detail else None,
                    )
                )
    if full and seen != set(range(1, 252)):
        raise ValueError("Full declaration must enumerate all 251 species")
    if not result and not full:
        raise ValueError("Empty declaration")
    return result


def normalized_name(name):
    return name.casefold().replace(" ♀", "♀").replace(" ♂", "♂").replace("♀", " female").replace("♂", " male")


def reconcile(actor, text, sha256, entries, active):
    store.verified(actor)
    rows = parse(text, sha256)
    for row in rows:
        candidates = [
            p
            for p in entries
            if p["set_name"] == row["set_name"]
            and p["attributes"].get("pokemon_dex") == row["pokemon_dex"]
            and normalized_name(p["name"]) == normalized_name(row.get("declared_card_name") or row["name"])
            and (not row.get("declared_card_number") or p["collector_number"] == row["declared_card_number"])
        ]
        # No retained marker legend establishes D semantics. Retain it literally.
        if row["marker"] != "✓":
            candidates = []
        ids = {p["id"] for p in candidates}
        matches = [c["id"] for c in active if c["printing_id"] in ids]
        row.update(
            candidate_printing_ids=sorted(ids),
            existing_copy_ids=sorted(matches),
            status="marker-review"
            if row["marker"] != "✓"
            else "existing-presence"
            if matches
            else "printing-ambiguous"
            if len(ids) > 1
            else "physical-attributes-unverified"
            if ids
            else "catalog-gap",
            exact_printing_verified=False,
            quantity=None,
            finish=None,
            edition=None,
        )
    return rows


def plan(actor, request, operation_id, entries, active):
    if store.verified(actor).role != "owner":
        raise ValueError("Only the owner can import a collection declaration")
    if not available():
        raise ValueError("Presence-declaration migration required")
    rows = reconcile(actor, request.get("text"), request.get("sha256"), entries, active)
    key = stable_id("owner-presence", actor.user_id + request["sha256"])
    prior = store.rows(
        "SELECT * FROM ownership_declarations WHERE id=%s AND user_id=%s", [key, actor.user_id]
    )
    creates = (
        []
        if prior
        else [
            dict(
                kind="declaration",
                row=dict(
                    id=key,
                    user_id=actor.user_id,
                    source_sha256=request["sha256"],
                    source_text=request["text"],
                    reconciliation=encode(rows),
                    revision=0,
                ),
            )
        ]
    )
    from . import collection_goals

    before = collection_goals.latest(actor)
    before_owned = set(collection_goals.owned(before, 251)) if before else set()
    after_owned = {r["pokemon_dex"] for r in rows}
    return dict(
        selected_source_id=key,
        source_preview=dict(
            owned=len(after_owned),
            missing=251 - len(after_owned),
            marks=len(rows),
            added=sorted(after_owned - before_owned),
            removed=sorted(before_owned - after_owned),
            source_sha256=request["sha256"],
            source_before=before["source_sha256"] if before else None,
        ),
        creates=creates,
        updates=[],
        deletes=[],
        errors=[],
        warnings=[
            "Presence only. Copies, quantities, physical attributes and frozen goal eligibility are unchanged. Special markers require review before printing resolution."
        ],
        checklist=rows,
    )


def summary(actor, lower=1, upper=151):
    store.verified(actor)
    batches = (
        store.rows("SELECT * FROM ownership_declarations WHERE user_id=%s ORDER BY id", [actor.user_id])
        if available()
        else []
    )
    from .collection_goals import full_source

    full_batches = {b["id"]: b for b in batches if full_source(b)}
    if full_batches:
        selected = None
        operations = store.rows(
            "SELECT plan FROM collection_operations WHERE user_id=%s AND state='confirmed' ORDER BY generation DESC,created DESC,id DESC",
            [actor.user_id],
        )
        for operation in operations:
            plan = json.loads(operation["plan"])
            if plan.get("selected_source_id") in full_batches:
                selected = full_batches[plan["selected_source_id"]]
                break
            for change in plan.get("creates", []):
                if change.get("kind") == "declaration" and change["row"]["id"] in full_batches:
                    selected = full_batches[change["row"]["id"]]
                    break
            if selected:
                break
        batches = [selected or full_batches[sorted(full_batches)[-1]]]
    rows = [r for b in batches for r in json.loads(b["reconciliation"]) if lower <= r["pokemon_dex"] <= upper]
    owned = {r["pokemon_dex"] for r in rows}
    names = registry()
    from . import broad_goals, collection

    catalog = collection.catalog(actor)
    reviewed = broad_goals.progress(
        broad_goals.definition(catalog), collection.copies(actor), {p["id"] for p in catalog}
    )
    result = dict(
        species=len(owned),
        total=upper - lower + 1,
        marked_cells=len(rows),
        rows=rows,
        missing=[
            dict(pokemon_dex=n, name=names[n]["name"]) for n in range(lower, upper + 1) if n not in owned
        ],
        source_sha256=[
            b["source_sha256"]
            for b in batches
            if any(lower <= r["pokemon_dex"] <= upper for r in json.loads(b["reconciliation"]))
        ],
        reviewed_printing_species=reviewed["satisfied"] if lower == 1 else None,
        reviewed_coverage_species=151 - reviewed["unavailable"] if lower == 1 else None,
        exact_identity_unverified_cells=len(rows),
        unresolved_cells=sum(r["status"] != "existing-presence" for r in rows),
    )

    if lower == 1:
        result["gen2"] = summary(actor, 152, 251)
    return result


def correction(actor, request):
    from . import collection_goals
    from .collection import Conflict

    source = collection_goals.source(actor, request.get("source_id"))
    if collection_goals.latest(actor)["id"] != source["id"]:
        raise Conflict("Collection source changed; review the latest source")
    n = request.get("pokemon_dex")
    if type(n) is not int or not 1 <= n <= 251 or type(request.get("owned")) is not bool:
        raise ValueError("Choose an in-scope species and ownership")
    reader = csv.DictReader(io.StringIO(source["source_text"].lstrip("\ufeff"), newline=""))
    rows = list(reader)
    row = next(r for r in rows if int(r["Dex"]) == n)
    fields = reader.fieldnames
    columns = [k for k in fields[3:] if k != "Ownership notes"]
    if request["owned"]:
        key, value = request.get("source_set"), request.get("card_text")
        if key not in columns or not isinstance(value, str) or not value.strip():
            raise ValueError("Supply a card declaration in a supported source set")
        row[key] = value.strip()
        row["Status"] = "Owned"
    else:
        row["Status"] = "Missing"
        for key in columns:
            row[key] = ""
    if "Ownership notes" in fields and "notes" in request:
        if not isinstance(request["notes"], str) or len(request["notes"]) > 2000:
            raise ValueError("Notes must be text")
        row["Ownership notes"] = request["notes"]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    text = stream.getvalue()
    parse(text, digest(text.encode()))
    return dict(text=text, sha256=digest(text.encode()))
