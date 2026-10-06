"""Independent #001–251 target browsing over retained reviewed product evidence."""

import json

from pokemon_hunter.migration import digest, encode

from . import broad_goals, collection, packs, store
from . import collection_goals as goals

FIELDS = {"goal", "targets", "scope", "printing"}


def request(raw):
    if not isinstance(raw, dict) or set(raw) - FIELDS:
        raise ValueError("Unsupported lookup scope")
    result = {k: raw.get(k, "") for k in FIELDS}
    if any(not isinstance(v, str) for v in result.values()):
        raise ValueError("Lookup fields require text")
    result["scope"] = result["scope"] or "all"
    if result["scope"] not in {"all", "missing"}:
        raise ValueError("Choose all targets or missing targets")
    if result["targets"]:
        parts = result["targets"].split(",")
        if any(not p.isdecimal() for p in parts):
            raise ValueError("Use canonical species numbers separated by commas")
        result["targets"] = ",".join(map(str, goals.targets(list(map(int, parts)))))
    return result


def project(actor, raw, filters=None, expansion=""):
    store.verified(actor)
    raw = request(raw)
    entries = collection.catalog(actor)
    goal = collection.one(actor, "goal", raw["goal"]) if raw["goal"] else None
    definition = json.loads(goal["definition"]) if goal else None
    numbers = [int(n) for n in raw["targets"].split(",")] if raw["targets"] else list(range(1, 252))
    if raw["printing"]:
        printing = next((p for p in entries if p["id"] == raw["printing"]), None)
        if not printing or not broad_goals.eligible(printing, 251):
            raise ValueError("Printing lacks an in-scope canonical Pokémon identity")
        numbers = [printing["attributes"]["pokemon_dex"]]
    allowed = None
    if definition:
        allowed = {p for i in definition["items"] for p in i["printing_ids"]}
        scope_species = {i.get("pokemon_dex") for i in definition["items"] if i.get("pokemon_dex")}
        if not scope_species:
            scope_species = {
                p["attributes"]["pokemon_dex"]
                for p in entries
                if p["id"] in allowed and broad_goals.eligible(p, 251)
            }
        numbers = sorted(set(numbers).intersection(scope_species))
        if not numbers:
            raise ValueError("No in-scope species in this goal and selection")
    source = (
        goals.source(actor, definition["collection_source"]["id"])
        if definition and "collection_source" in definition
        else goals.latest(actor)
    )
    if source:
        d = goals.targets_definition(actor, entries, source["id"], numbers)
        if definition and "owned_species" in definition:
            d["owned_species"] = sorted(set(numbers).intersection(definition["owned_species"]))
    else:
        selected, refs = broad_goals.reviewed(entries, 251)
        d = dict(
            policy="species",
            eligibility_policy=dict(broad_goals.POLICY, id="lookup-reviewed-species-v1"),
            coverage=broad_goals.COVERAGE,
            catalog_references=refs,
            catalog_versions=sorted({r["version"] for r in refs}),
            items=broad_goals.species_items(selected, numbers, frozen_labels=False),
        )
    if allowed is not None:
        for i in d["items"]:
            i["printing_ids"] = sorted(set(i["printing_ids"]).intersection(allowed))
        # Legacy goal ownership continues to come from its own policy, never a declaration.
        if "collection_source" not in definition:
            owned = {
                i.get("pokemon_dex")
                for g in collection.goals(actor)
                if g["id"] == goal["id"]
                for i in g["progress"]
                if i["status"] == "owned"
            }
            owned_printings = {
                p
                for g in collection.goals(actor)
                if g["id"] == goal["id"]
                for i in g["progress"]
                if i["status"] == "owned"
                for p in i["printing_ids"]
            }
            owned.update(
                p["attributes"].get("pokemon_dex")
                for p in entries
                if p["id"] in owned_printings and broad_goals.eligible(p, 251)
            )
            d["owned_species"] = sorted(set(numbers).intersection(owned))
            d["eligibility_policy"] = goals.TARGET_POLICY
            d.pop("collection_source", None)
    if raw["printing"]:
        for i in d["items"]:
            i["printing_ids"] = [p for p in i["printing_ids"] if p == raw["printing"]]
    key = "lookup:" + digest(encode(dict(scope=raw, definition=d, user_id=actor.user_id)).encode())
    d["lineage"] = dict(number=1, root_id=key, predecessor_id=None, predecessor_version=None)
    row = dict(
        id=key,
        user_id=actor.user_id,
        name=goal["name"] if goal else "Selected Pokémon" if len(numbers) < 251 else "Original 251",
        kind="lookup",
        definition=encode(d),
        version=digest(encode(d).encode()),
    )
    result = packs.project(
        actor, key, expansion=expansion, filters=filters, scope=row, include_owned=raw["scope"] == "all"
    )
    result.update(
        lookup=True,
        lookup_request=raw,
        source_goal_id=goal["id"] if goal else None,
        source_goal_version=goal["version"] if goal else None,
    )
    return result
