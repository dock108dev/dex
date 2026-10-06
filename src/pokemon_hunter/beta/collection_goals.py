"""Frozen account-local species declarations, independent of exact card resolution."""

import csv
import io
import json

from pokemon_hunter.inventory import stable_id
from pokemon_hunter.migration import encode

from . import broad_goals, store
from . import ownership_declarations as declarations

KIND = "original151_collection"
TARGET_KIND = "collection_species"
OWNERSHIP_KINDS = {KIND, TARGET_KIND}
KINDS = {"original151", *OWNERSHIP_KINDS}
POLICY = {
    **broad_goals.POLICY,
    "id": "original-151-collection-v1",
    "eligibility": "Canonical species across eras, including Dark, named and EX cards; one slot per species.",
    "ownership": "Declared species in the explicitly selected account-local full collection source, frozen at this version. Printing resolution and physical copies are separate.",
}
TARGET_POLICY = {
    **POLICY,
    "id": "collection-selected-species-v1",
    "denominator": "selected-canonical-national-dex-001-251",
}
COVERAGE = "Collection species ownership is independent of reviewed printing coverage. Catalog and booster coverage remain qualified separately."
SOURCE_FIELDS = {"id", "user_id", "source_sha256", "source_text", "revision"}


def full_source(row):
    declarations.parse(row["source_text"], row["source_sha256"])
    return next(csv.reader(io.StringIO(row["source_text"].lstrip("\ufeff")))) in [
        declarations.FULL_HEADERS,
        declarations.PHOTO_HEADERS,
    ]


def sources(actor):
    store.verified(actor)
    if not declarations.available():
        return []
    rows = store.rows("SELECT * FROM ownership_declarations WHERE user_id=%s ORDER BY id", [actor.user_id])
    return [r for r in rows if full_source(r)]


def latest(actor):
    rows = sources(actor)
    by_id = {r["id"]: r for r in rows}
    for op in store.rows(
        "SELECT plan FROM collection_operations WHERE user_id=%s AND state='confirmed' ORDER BY generation DESC,created DESC,id DESC",
        [actor.user_id],
    ):
        plan = json.loads(op["plan"])
        if plan.get("selected_source_id") in by_id:
            return by_id[plan["selected_source_id"]]
        for change in plan.get("creates", []):
            if change["kind"] == "declaration" and change["row"]["id"] in by_id:
                return by_id[change["row"]["id"]]
    return rows[-1] if rows else None


def source(actor, key):
    matches = [r for r in sources(actor) if r["id"] == key]
    if not matches:
        raise ValueError("Select an account-local full collection source")
    return matches[0]


def reference(row):
    return {k: row[k] for k in ("id", "user_id", "source_sha256", "revision")}


def owned(row, upper=151):
    rows = declarations.parse(row["source_text"], row["source_sha256"])
    if not full_source(row):
        raise ValueError("A complete 251 collection source is required")
    return sorted({r["pokemon_dex"] for r in rows if r["pokemon_dex"] <= upper})


def definition(actor, entries, key):
    row = source(actor, key)
    return dict(
        broad_goals.definition(entries),
        eligibility_policy=POLICY,
        coverage=COVERAGE,
        collection_source=reference(row),
        owned_species=owned(row),
    )


def targets(raw):
    if (
        not isinstance(raw, list)
        or not 1 <= len(raw) <= 251
        or any(type(n) is not int or not 1 <= n <= 251 for n in raw)
        or len(set(raw)) != len(raw)
    ):
        raise ValueError("Select distinct canonical species within 1–251")
    return sorted(raw)


def targets_definition(actor, entries, key, numbers):
    numbers = targets(numbers)
    row = source(actor, key)
    selected, refs = broad_goals.reviewed(entries, 251)
    return dict(
        policy="species",
        eligibility_policy=TARGET_POLICY,
        coverage=COVERAGE,
        catalog_references=refs,
        catalog_versions=sorted({r["version"] for r in refs}),
        items=broad_goals.species_items(selected, numbers),
        collection_source=reference(row),
        owned_species=sorted(set(owned(row, 251)).intersection(numbers)),
    )


def validate(d, row):
    if (
        not isinstance(d, dict)
        or d.get("eligibility_policy") not in (POLICY, TARGET_POLICY)
        or d.get("coverage") != COVERAGE
    ):
        raise ValueError("Unsupported collection goal policy")
    if not isinstance(d.get("owned_species"), list) or any(type(n) is not int for n in d["owned_species"]):
        raise ValueError("Invalid canonical species snapshot")
    if d.get("collection_source") != reference(row) or d.get("owned_species") != sorted(
        set(owned(row, 251)).intersection(i["pokemon_dex"] for i in d["items"])
    ):
        raise ValueError("Collection source or species snapshot differs")
    base = {k: v for k, v in d.items() if k not in {"collection_source", "owned_species"}}
    numbers = targets([i["pokemon_dex"] for i in d["items"]])
    if d["eligibility_policy"] == POLICY and numbers != list(range(1, 152)):
        raise ValueError("Original 151 membership differs")
    broad_goals.validate(
        dict(base, eligibility_policy=broad_goals.POLICY, coverage=broad_goals.COVERAGE),
        upper=251 if d["eligibility_policy"] == TARGET_POLICY else 151,
        targets=numbers,
    )
    return d


def progress(d, active, available):
    base = broad_goals.progress(dict(d, eligibility_policy=broad_goals.POLICY), active, available)
    species = set(d["owned_species"])
    items = [
        dict(
            i,
            status="owned"
            if i["pokemon_dex"] in species
            else "missing"
            if i["qualifying_printings"]
            else "unavailable",
        )
        for i in base["progress"]
    ]
    return dict(
        base,
        progress=items,
        satisfied=len(species),
        missing=len(items) - len(species),
        missing_with_coverage=sum(i["status"] == "missing" for i in items),
        reviewed_printing_species=base["satisfied"],
        collection_source=d.get("collection_source"),
    )


def exported(actor, goals):
    ids = {g["definition"]["collection_source"]["id"] for g in goals if g["kind"] in OWNERSHIP_KINDS}
    return [{k: r[k] for k in SOURCE_FIELDS} for r in sources(actor) if r["id"] in ids]


def import_sources(actor, data, entries, active):
    rows = data.get("collection_sources", [])
    if not isinstance(rows, list) or len(rows) > 200:
        raise ValueError("Invalid collection sources")
    by_id, mapped, creates = {}, {}, []
    for r in rows:
        if (
            not isinstance(r, dict)
            or set(r) != SOURCE_FIELDS
            or not isinstance(r["user_id"], str)
            or type(r["revision"]) is not int
            or r["revision"] != 0
        ):
            raise ValueError("Invalid collection source fields")
        if r["id"] != stable_id("owner-presence", r["user_id"] + r["source_sha256"]) or r["id"] in by_id:
            raise ValueError("Invalid or duplicate source identity")
        owned(r)
        by_id[r["id"]] = r
        new = dict(
            r, id=stable_id("owner-presence", actor.user_id + r["source_sha256"]), user_id=actor.user_id
        )
        if any(value["id"] == new["id"] for value in mapped.values()):
            raise ValueError("Collection sources collide after account remapping")
        mapped[r["id"]] = new
        existing = store.rows(
            "SELECT * FROM ownership_declarations WHERE id=%s AND user_id=%s", [new["id"], actor.user_id]
        )
        if existing:
            if {k: existing[0][k] for k in SOURCE_FIELDS} != new:
                raise ValueError("Existing collection source differs")
        else:
            new = dict(
                new,
                reconciliation=encode(
                    declarations.reconcile(actor, new["source_text"], new["source_sha256"], entries, active)
                ),
            )
            creates.append(dict(kind="declaration", row=new))
    referenced = set()
    for g in data.get("goals", []):
        if g.get("kind") not in OWNERSHIP_KINDS:
            continue
        ref = g.get("definition", {}).get("collection_source", {})
        r = by_id.get(ref.get("id"))
        if not r or r["user_id"] != g.get("user_id"):
            raise ValueError("Collection source must belong to exported goal account")
        validate(g["definition"], r)
        referenced.add(r["id"])
    if referenced != set(by_id):
        raise ValueError("Unreferenced collection source")
    return by_id, mapped, creates
