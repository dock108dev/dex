"""Read current or retained missing species without expanding printing catalogs."""

from . import account_read_build, account_read_context, account_read_goals, collection, store


def _targets(actor, raw):
    from .shopping_index import current

    indexed = current(actor)
    key = tuple(sorted(raw.items()))
    if indexed and key in getattr(indexed, "intent_targets", {}):
        return indexed.intent_targets[key]
    if set(raw) - {"goal", "version", "scope", "generation"}:
        raise ValueError("Choose supported collection intent fields")
    scope = raw.get("scope", "all")
    if scope not in {"all", "kanto", "johto"}:
        raise ValueError("Choose a species region")
    if raw.get("goal") and not raw.get("version"):
        raise ValueError("Keep the frozen goal version")
    goal = account_read_goals.scope(actor, raw)
    where, args = ["s.user_id=%s"], [actor.user_id]
    if scope != "all":
        where.append("CAST(s.id AS INTEGER) " + ("<=151" if scope == "kanto" else ">151"))
    if goal:
        where.append(
            "EXISTS(SELECT 1 FROM ar_goal_items i WHERE i.user_id=s.user_id AND i.goal_id=%s AND i.species=CAST(s.id AS INTEGER) AND i.status!='owned')"
        )
        args.append(goal["id"])
    else:
        where.append("json_extract(s.summary,'$.current_present')=0")
    rows = store.rows(
        "SELECT s.summary AS payload,s.summary_sha AS sha FROM ar_species s WHERE "
        + " AND ".join(where)
        + " ORDER BY CAST(s.id AS INTEGER)",
        args,
    )
    result = dict(
        targets=[
            dict(species=r["dex"], name=r["name"]) for row in rows for r in [account_read_build.decode(row)]
        ],
        scope=scope,
        goal_version=goal["version"] if goal else None,
    )

    if indexed:
        if not hasattr(indexed, "intent_targets"):
            indexed.intent_targets = {}
        indexed.intent_targets[key] = result
    return result


@account_read_context.read
def targets(actor, build, state, raw):
    return _targets(actor, raw)


def validate(actor, choices):
    if not choices.collection_intent:
        return
    from .shopping_index import current

    raw = dict(scope=choices.focus)
    if choices.goal_id:
        raw.update(goal=choices.goal_id, version=choices.goal_version)
    indexed = current(actor)
    result = (
        _targets(actor, raw) if indexed else targets(actor, dict(raw, generation=str(choices.generation)))
    )
    if choices.species not in {r["species"] for r in result["targets"]}:
        raise collection.Conflict(
            "Selected Pokémon is no longer missing in this scope; choose a current target"
        )


def fit(actor, choices, title, review=None):
    """Unique possible additions, never confirmation of seller contents or value."""
    from . import discovery_matching
    from .shopping_index import current

    raw = dict(scope=choices["focus"])
    if choices.get("goal_id"):
        raw.update(goal=choices["goal_id"], version=choices["goal_version"])
    missing = {r["species"]: r["name"] for r in _targets(actor, raw)["targets"]}
    mentioned = [n for n, name in missing.items() if discovery_matching.name_spans({"name": name}, title)]
    included = None
    outside_scope = []
    frozen_species = {}
    if review is not None:
        rows = current(actor).printings([r["printing_id"] for r in review["cards"] if r["quantity"] > 0])
        if choices.get("goal_id") and rows:
            frozen_species = {
                r["printing_id"]: r["species"]
                for r in store.rows(
                    "SELECT p.printing_id,i.species FROM ar_goal_printings p JOIN ar_goal_items i ON i.user_id=p.user_id AND i.id=p.item_id WHERE p.user_id=%s AND p.goal_id=%s AND p.printing_id IN (SELECT value FROM json_each(%s))",
                    [actor.user_id, choices["goal_id"], account_read_build.encode([p["id"] for p in rows])],
                )
            }
            outside_scope = [p["id"] for p in rows if p["id"] not in frozen_species]
            rows = [p for p in rows if p["id"] in frozen_species]
        included = sorted(
            {
                frozen_species.get(p["id"], p["attributes"].get("pokemon_dex"))
                for p in rows
                if frozen_species.get(p["id"], p["attributes"].get("pokemon_dex")) in missing
                and p["attributes"].get("supertype") == "Pokémon"
            }
        )
    return dict(
        mentioned_species=mentioned,
        included_species=included,
        mentioned_names=[missing[n] for n in mentioned],
        included_names=[missing[n] for n in included] if included is not None else None,
        outside_scope_ids=outside_scope,
        included_provenance="User-included review identities; seller contents remain unverified"
        if review
        else None,
        unknown_contents=review.get("unknown_contents") if review else None,
        note="Each potentially new species counts once. Exact-printing ownership is separate. Mentions alone confirm neither contents, collection gain nor value.",
    )
