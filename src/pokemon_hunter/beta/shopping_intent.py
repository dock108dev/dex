"""Read current or retained missing species without expanding printing catalogs."""

from . import account_read_build, account_read_context, account_read_goals, collection, store


def _targets(actor, raw, build=None):
    from .shopping_index import current

    indexed = current(actor)
    build = indexed.build if indexed else build
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
    goal_key = raw.get("goal")
    goal = None if goal_key else account_read_goals.scope(actor, raw)
    where, args = ["s.user_id=%s"], [actor.user_id]
    if scope != "all":
        where.append("CAST(s.id AS INTEGER) " + ("<=151" if scope == "kanto" else ">151"))
    if goal_key:
        where.append(
            "EXISTS(SELECT 1 FROM ar_goal_items i WHERE i.user_id=s.user_id AND i.goal_id=%s AND i.status!='owned' AND (i.species=CAST(s.id AS INTEGER) OR (i.species IS NULL AND EXISTS(SELECT 1 FROM ar_goal_printings p JOIN ar_catalog c ON c.id=p.printing_id AND c.build=%s WHERE p.user_id=i.user_id AND p.goal_id=i.goal_id AND p.item_id=i.id AND CAST(json_extract(c.payload,'$.attributes.pokemon_dex') AS INTEGER)=CAST(s.id AS INTEGER)))))"
        )
        args.extend([goal_key, build])
    else:
        where.append("json_extract(s.summary,'$.current_present')=0")
    query = (
        "SELECT s.summary AS payload,s.summary_sha AS sha FROM ar_species s WHERE "
        + " AND ".join(where)
        + " ORDER BY CAST(s.id AS INTEGER)"
    )
    if goal_key:
        rows = store.rows(
            "SELECT 'goal' AS kind,0 AS rank,summary AS payload,summary_sha AS sha FROM ar_goals WHERE user_id=%s AND id=%s UNION ALL SELECT 'target',CAST(s.id AS INTEGER),s.summary,s.summary_sha FROM ar_species s WHERE "
            + " AND ".join(where)
            + " ORDER BY rank",
            [actor.user_id, goal_key, *args],
        )
        headers = [r for r in rows if r["kind"] == "goal"]
        if not headers:
            from django.http import Http404

            raise Http404
        goal = account_read_build.decode(headers[0])
        if raw["version"] != goal["version"]:
            raise collection.Conflict("Frozen goal version changed")
        if not goal["supported"] and goal["header"].get("policy") not in {"exact", "catalog"}:
            raise ValueError("Choose a supported collection goal")
        rows = [r for r in rows if r["kind"] == "target"]
    else:
        rows = store.rows(query, args)
    result = dict(
        targets=[
            dict(species=r["dex"], name=r["name"]) for row in rows for r in [account_read_build.decode(row)]
        ],
        scope=scope,
        goal_version=goal["version"] if goal else None,
        goal_policy=goal["header"]["policy"] if goal else "species",
    )

    if indexed:
        if not hasattr(indexed, "intent_targets"):
            indexed.intent_targets = {}
        indexed.intent_targets[key] = result
    return result


@account_read_context.read
def targets(actor, build, state, raw):
    return _targets(actor, raw, build)


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
    targets = _targets(actor, raw)
    missing = {r["species"]: r["name"] for r in targets["targets"]}
    mentioned = [n for n, name in missing.items() if discovery_matching.name_spans({"name": name}, title)]
    included = None
    outside_scope = []
    frozen_species = {}
    included_printings = None
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
            if targets["goal_policy"] in {"exact", "catalog"}:
                candidates = store.rows(
                    "SELECT p.printing_id,i.payload,i.sha,i.status FROM ar_goal_printings p JOIN ar_goal_items i ON i.user_id=p.user_id AND i.id=p.item_id WHERE p.user_id=%s AND p.goal_id=%s AND p.printing_id IN (SELECT value FROM json_each(%s))",
                    [actor.user_id, choices["goal_id"], account_read_build.encode([p["id"] for p in rows])],
                )
                eligible = {
                    r["printing_id"]
                    for r in candidates
                    if r["status"] != "owned"
                    and (
                        targets["goal_policy"] != "exact"
                        or not account_read_build.decode(r).get("unresolved")
                    )
                }
                included_printings = [
                    dict(
                        id=p["id"],
                        name=p["name"],
                        set_name=p["set_name"],
                        collector_number=p["collector_number"],
                        language=p.get("language"),
                        edition=p.get("edition"),
                        finish=p.get("finish"),
                        variant=p.get("variant"),
                    )
                    for p in rows
                    if p["id"] in eligible
                ]
                rows = [p for p in rows if p["id"] in eligible]
        if targets["goal_policy"] in {"exact", "catalog"} and included_printings is None:
            included_printings = []
        included = sorted(
            {
                (frozen_species.get(p["id"]) or p["attributes"].get("pokemon_dex"))
                for p in rows
                if (frozen_species.get(p["id"]) or p["attributes"].get("pokemon_dex")) in missing
                and p["attributes"].get("supertype") == "Pokémon"
            }
        )
    return dict(
        mentioned_species=mentioned,
        included_species=included,
        goal_policy=targets["goal_policy"],
        included_printings=included_printings,
        mentioned_names=[missing[n] for n in mentioned],
        included_names=[missing[n] for n in included] if included is not None else None,
        outside_scope_ids=outside_scope,
        included_provenance="User-included review identities; seller contents remain unverified"
        if review
        else None,
        unknown_contents=review.get("unknown_contents") if review else None,
        note="Each potentially new species counts once. Exact-printing ownership is separate. Mentions alone confirm neither contents, collection gain nor value.",
    )
