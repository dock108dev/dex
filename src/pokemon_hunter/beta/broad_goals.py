"""Original 151 v1: reviewed canonical Pokémon identity, independent of booster membership.

Frozen definitions live in the existing goal table/journal. No schema migration or
owner-root rewrite is needed. Lineage references always resolve within the account.
"""

import json
from pathlib import Path

from django.db import connection

from pokemon_hunter.migration import digest, encode

from . import catalog_imports as cat
from . import store

POLICY = {
    "id": "original-151-reviewed-v1",
    "denominator": "canonical-national-dex-001-151",
    "eligibility": "Reviewed published canonical Pokémon printings, including ex/V/GX, Dark, named/trainer-owned and regional forms. Trainers, Energy, artwork cameos and unresolved species identities excluded. Evolutions count only for their own canonical species; duplicate copies/printings fill one slot.",
    "ownership": "Active account-owned resolved copies only; provisional or unresolved copies do not count.",
    "distribution": "Booster membership and physical distribution are separate; provider existence alone is insufficient.",
}
COVERAGE = "Any era is the goal policy. Recognition is limited to the selected reviewed published catalogs; this is not complete all-era coverage. Booster membership is separate."
SPECIES = Path(__file__).resolve().parents[3] / "config/catalog-imports/staging-ten/species.json"


def eligible(p):
    a = p["attributes"]
    n = a.get("pokemon_dex")
    return a.get("supertype") == "Pokémon" and type(n) is int and 1 <= n <= 151


def reviewed(entries):
    if "catalog_heads" not in connection.introspection.table_names():
        return [], []
    heads = store.rows(
        "SELECT i.* FROM catalog_heads h JOIN catalog_imports i ON i.id=h.import_id WHERE i.state='published' ORDER BY i.set_id"
    )
    refs = []
    selected = []
    for h in heads:
        package = json.loads(h["package"])
        if package["game"] != "pokemon":
            continue
        members = [
            p
            for p in entries
            if p["set_id"] == h["set_id"]
            and p["catalog_version"] == package["version"]
            and p.get("publication_state") == "published"
        ]
        if not members:
            continue
        # Membership must be in the actual reviewed package, not merely a row in its set.
        _, approved = cat.rows_for(package)
        approved = {p["id"]: json.loads(p["attributes"]) for p in approved}
        selected.extend(p for p in members if eligible(p) and p["attributes"] == approved.get(p["id"]))
        refs.append(
            dict(
                set_id=h["set_id"],
                name=package["set_name"],
                version=package["version"],
                import_id=h["id"],
                package_sha256=h["package_hash"],
            )
        )
    return selected, refs


def definition(entries):
    selected, refs = reviewed(entries)
    names = json.loads(SPECIES.read_text())
    return dict(
        policy="species",
        eligibility_policy=POLICY,
        coverage=COVERAGE,
        catalog_references=refs,
        catalog_versions=sorted({r["version"] for r in refs}),
        items=[
            dict(
                label=f"#{n:03} {names[str(n)]['name']}",
                pokemon_dex=n,
                printing_ids=sorted(p["id"] for p in selected if p["attributes"]["pokemon_dex"] == n),
                unresolved=False,
            )
            for n in range(1, 152)
        ],
    )


def progress(d, active, available):
    from .collection import exact_owned_printings

    # A later publication cannot revoke an earlier version's reviewed ownership policy.
    # Current selectable coverage is reported separately from its frozen membership.
    owned = exact_owned_printings(active)
    items = [
        dict(
            i,
            status="owned"
            if owned.intersection(i["printing_ids"])
            else "missing"
            if available.intersection(i["printing_ids"])
            else "unavailable",
            qualifying_printings=len(available.intersection(i["printing_ids"])),
        )
        for i in d["items"]
    ]
    satisfied = sum(i["status"] == "owned" for i in items)
    return dict(
        progress=items,
        satisfied=satisfied,
        total=151,
        missing=151 - satisfied,
        missing_with_coverage=sum(i["status"] == "missing" for i in items),
        unavailable=sum(i["qualifying_printings"] == 0 for i in items),
        qualifying_printings=sum(i["qualifying_printings"] for i in items),
        frozen_qualifying_printings=sum(len(i["printing_ids"]) for i in items),
    )


def difference(before, after, active, available):
    old = {p for i in before["items"] for p in i["printing_ids"]}
    new = {p for i in after["items"] for p in i["printing_ids"]}
    return dict(
        added=sorted(new - old),
        removed=sorted(old - new),
        policy_before=before.get("eligibility_policy", before["policy"]),
        policy_after=after["eligibility_policy"],
        progress_before=progress(before, active, available)["satisfied"],
        progress_after=progress(after, active, available)["satisfied"],
    )


def validate(d):
    """Validate frozen imports against retained review journals, not supplied membership."""
    if not isinstance(d, dict):
        raise ValueError("Invalid goal definition")
    if d.get("eligibility_policy") != POLICY or d.get("policy") != "species" or d.get("coverage") != COVERAGE:
        raise ValueError("Unsupported Original 151 policy")
    refs = d.get("catalog_references")
    if (
        not isinstance(refs, list)
        or any(
            not isinstance(r, dict)
            or set(r) != {"set_id", "name", "version", "import_id", "package_sha256"}
            or any(not isinstance(v, str) for v in r.values())
            for r in refs
        )
        or len({r["set_id"] for r in refs}) != len(refs)
    ):
        raise ValueError("Invalid catalog references")
    permitted = {}
    for ref in refs:
        rows = store.rows("SELECT * FROM catalog_imports WHERE id=%s", [ref["import_id"]])
        if not rows or rows[0]["state"] not in {"published", "rolled-back"}:
            raise ValueError("Catalog review unavailable")
        h = rows[0]
        p = json.loads(h["package"])
        expected = dict(
            set_id=h["set_id"],
            name=p["set_name"],
            version=p["version"],
            import_id=h["id"],
            package_sha256=h["package_hash"],
        )
        if ref != expected or p["game"] != "pokemon":
            raise ValueError("Forged catalog reference")
        _, rows = cat.rows_for(p)
        for row in rows:
            row["attributes"] = json.loads(row["attributes"])
            if eligible(row):
                permitted[row["id"]] = row["attributes"]["pokemon_dex"]
    names = json.loads(SPECIES.read_text())
    expected = [
        dict(
            label=f"#{n:03} {names[str(n)]['name']}",
            pokemon_dex=n,
            printing_ids=sorted(p for p, number in permitted.items() if number == n),
            unresolved=False,
        )
        for n in range(1, 152)
    ]
    if d["items"] != expected or d.get("catalog_versions") != sorted({r["version"] for r in refs}):
        raise ValueError("Forged Original 151 membership")
    if set(d) != {
        "policy",
        "eligibility_policy",
        "coverage",
        "catalog_references",
        "catalog_versions",
        "items",
        "lineage",
    }:
        raise ValueError("Unsupported goal definition fields")
    return d


def remap_imports(goals, actor_id, operation_id):
    """Require a complete account-local lineage in the export and remap every reference."""
    from pokemon_hunter.inventory import stable_id

    if any(not isinstance(g, dict) or not isinstance(g.get("id"), str) for g in goals) or len(
        {g["id"] for g in goals}
    ) != len(goals):
        raise ValueError("Invalid or duplicate goal identity")
    by_id = {g["id"]: g for g in goals}
    result = {}
    for g in goals:
        if g.get("kind") != "original151":
            continue
        d = validate(g["definition"])
        lineage = d.get("lineage", {})
        if not isinstance(lineage, dict):
            raise ValueError("Invalid lineage")
        predecessor = lineage.get("predecessor_id")
        root = lineage.get("root_id")
        number = lineage.get("number")
        if (
            set(lineage) != {"root_id", "predecessor_id", "number", "predecessor_version"}
            or type(number) is not int
            or number < 1
            or not isinstance(root, str)
            or (predecessor is not None and not isinstance(predecessor, str))
            or root not in by_id
        ):
            raise ValueError("Invalid goal lineage")
        if number == 1:
            if root != g["id"] or predecessor is not None or lineage["predecessor_version"] is not None:
                raise ValueError("Invalid initial version")
        else:
            prior = by_id.get(predecessor)
            if (
                not prior
                or prior.get("user_id") != g.get("user_id")
                or prior["version"] != lineage["predecessor_version"]
            ):
                raise ValueError("Invalid predecessor reference")
            prior_lineage = prior["definition"].get("lineage", dict(number=1, root_id=prior["id"]))
            if prior_lineage["number"] != number - 1 or prior_lineage["root_id"] != root:
                raise ValueError("Invalid version sequence")
        result[g["id"]] = json.loads(encode(d))
    # Ordered by sequence so the remapped predecessor's digest is available.
    for key, d in sorted(result.items(), key=lambda item: item[1]["lineage"]["number"]):
        lineage = d["lineage"]
        previous = lineage["predecessor_id"]
        lineage["root_id"] = stable_id("b2-goal-import", actor_id + operation_id + lineage["root_id"])
        lineage["predecessor_id"] = (
            stable_id("b2-goal-import", actor_id + operation_id + previous) if previous else None
        )
        if previous in result:
            lineage["predecessor_version"] = digest(encode(result[previous]).encode())
    return result
