"""Disposable frozen-goal membership and indexed progress dependencies."""

from django.db import connection

from . import account_read_build as builds
from . import collection, collection_goals, store
from .catalog_read_build import Unavailable
from .goal_progress import evaluate


def prepare(actor):
    goals = collection.goals(actor, include_updates=True)
    for goal in goals:
        definition = goal["definition"]
        supported = definition.get("policy") == "species" and (
            goal["kind"] in collection_goals.KINDS
            or goal["kind"] == "filtered"
            and definition.get("filters", {}).get("completion") == "species"
        )
        builds.put(
            "ar_goals",
            actor,
            dict(id=goal["id"], version=goal["version"]),
            dict(
                id=goal["id"],
                version=goal["version"],
                revision=goal["revision"],
                name=goal["name"],
                kind=goal["kind"],
                definition=definition,
                supported=supported,
                header={
                    k: v
                    for k, v in definition.items()
                    if k not in {"items", "catalog_references", "owned_species"}
                },
                successor_ids=goal.get("successor_ids", []),
                coverage_update_available=goal.get("coverage_update_available", False),
                collection_update_available=goal.get("collection_update_available", False),
            ),
        )
        for rank, item in enumerate(goal["progress"]):
            key = builds.digest(builds.encode([goal["id"], rank]))
            builds.put(
                "ar_goal_items",
                actor,
                dict(
                    id=key,
                    goal_id=goal["id"],
                    rank=rank,
                    species=item.get("pokemon_dex"),
                    status=item["status"],
                ),
                item,
            )
            with connection.cursor() as cursor:
                cursor.executemany(
                    "INSERT INTO ar_goal_printings VALUES(%s,%s,%s,%s)",
                    [(actor.user_id, goal["id"], key, p) for p in item["printing_ids"]],
                )


def refresh(actor, build, printing_ids, operation):
    if any(c["kind"] == "goal" for c in operation["changes"]):
        for table in ("ar_goals", "ar_goal_items", "ar_goal_printings"):
            collection.execute(f"DELETE FROM {table} WHERE user_id=%s", [actor.user_id])
        prepare(actor)
        return
    if not printing_ids:
        return
    ids = sorted(printing_ids)
    rows = builds.bounded(
        store.rows(
            "SELECT i.* FROM ar_goal_items i WHERE i.user_id=%s AND i.id IN (SELECT item_id FROM ar_goal_printings WHERE user_id=%s AND printing_id IN ("
            + ",".join(["%s"] * len(ids))
            + ")) LIMIT %s",
            [actor.user_id, actor.user_id, *ids, builds.MAX_INPUT_ROWS + 1],
        )
    )
    goals = {}
    for row in rows:
        if row["goal_id"] not in goals:
            goals[row["goal_id"]] = builds.decode(
                store.rows(
                    "SELECT * FROM ar_goals WHERE user_id=%s AND id=%s", [actor.user_id, row["goal_id"]]
                )[0]
            )
        goal = goals[row["goal_id"]]
        item = builds.decode(row)
        frozen = item["printing_ids"]
        if len(frozen) > builds.MAX_INPUT_ROWS:
            raise Unavailable("large_frozen_goal_dependency")
        if frozen:
            placeholders = ",".join(["%s"] * len(frozen))
            copies = store.rows(
                "SELECT c.*,p.unresolved_fields FROM owned_copies c LEFT JOIN printings p ON p.id=c.printing_id WHERE c.user_id=%s AND c.state='active' AND c.printing_id IN ("
                + placeholders
                + ")",
                [actor.user_id, *frozen],
            )
            available = {
                r["id"]
                for r in store.rows(
                    "SELECT id FROM cr_printings WHERE build=%s AND scope IN ('retained','shared') AND published=1 AND id IN ("
                    + placeholders
                    + ")",
                    [build, *frozen],
                )
            }
        else:
            copies, available = [], set()
        projected = evaluate(
            goal["kind"],
            dict(goal["definition"], items=[goal["definition"]["items"][row["rank"]]]),
            copies,
            available,
            available,
        )["progress"][0]
        builds.put(
            "ar_goal_items",
            actor,
            dict(
                id=row["id"],
                goal_id=row["goal_id"],
                rank=row["rank"],
                species=row["species"],
                status=projected["status"],
            ),
            projected,
        )


def scope(actor, raw):
    key = raw.get("goal")
    if not key:
        if raw.get("version"):
            raise ValueError("Goal version requires a goal")
        return None
    rows = store.rows(
        "SELECT id,summary AS payload,summary_sha AS sha FROM ar_goals WHERE user_id=%s AND id=%s",
        [actor.user_id, key],
    )
    if not rows:
        from django.http import Http404

        raise Http404
    goal = builds.decode(rows[0])
    if raw.get("version") and raw["version"] != goal["version"]:
        raise collection.Conflict("Frozen goal version changed")
    if not goal["supported"]:
        raise ValueError("Choose a supported species goal")
    return goal
