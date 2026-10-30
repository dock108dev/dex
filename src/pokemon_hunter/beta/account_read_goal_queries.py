"""Private prepared goal summaries, progress and declaration-source projections."""

from django.http import Http404

from . import account_read_build as builds
from . import store
from .account_read_context import page_result, payload, read, url
from .catalog_read_build import Unavailable
from .catalog_read_queries import paging
from .catalog_read_select import offset


@read
def goal_options(actor, build, state, raw):
    page, size = paging(raw)
    total = store.rows("SELECT COUNT(*) AS n FROM ar_goals WHERE user_id=%s", [actor.user_id])[0]["n"]
    rows = store.rows(
        "SELECT id,summary AS payload,summary_sha AS sha FROM ar_goals WHERE user_id=%s ORDER BY id LIMIT %s OFFSET %s",
        [actor.user_id, size, offset(page, size)],
    )
    return page_result(
        [{k: v for k, v in builds.decode(r).items() if k in {"id", "name", "supported"}} for r in rows],
        "goals",
        total,
        page,
        size,
    )


@read
def goal_workspace(actor, build, state, raw, key=None):
    """Goal summaries and indexed progress, never copies or current catalog projection."""
    page, size = paging(raw)
    clause = "user_id=%s" + (" AND id=%s" if key else "")
    args = [actor.user_id, key] if key else [actor.user_id]
    total = store.rows("SELECT COUNT(*) AS n FROM ar_goals WHERE " + clause, args)[0]["n"]
    if key and not total:
        raise Http404
    rows = store.rows(
        "SELECT id,summary AS payload,summary_sha AS sha FROM ar_goals WHERE "
        + clause
        + " ORDER BY id LIMIT %s OFFSET %s",
        [*args, size, offset(page, size)],
    )
    ids = [r["id"] for r in rows]
    stats = (
        store.rows(
            "SELECT goal_id,status,COUNT(*) AS n FROM ar_goal_items WHERE user_id=%s AND goal_id IN ("
            + ",".join(["%s"] * len(ids))
            + ") GROUP BY goal_id,status",
            [actor.user_id, *ids],
        )
        if ids
        else []
    )
    items = []
    for row in rows:
        goal = builds.decode(row)
        if "header" not in goal:
            raise Unavailable("goal_header_preparation_required")
        counts = {r["status"]: r["n"] for r in stats if r["goal_id"] == goal["id"]}
        goal.update(
            total=sum(counts.values()),
            satisfied=counts.get("owned", 0),
            missing=counts.get("missing", 0),
            unavailable=counts.get("unavailable", 0),
        )
        goal["items_url"] = url(state, f"goals/{goal['id']}/items/")
        if len(builds.encode(goal).encode()) > 1100:
            goal = dict(id=goal["id"], oversized=True, url=url(state, f"resources/goal-header/{goal['id']}/"))
        items.append(goal)
    return page_result(items, "goals", total, page, size)


@read
def goal_items(actor, build, state, raw, key):
    page, size = paging(raw, ("q", "status"))
    if not store.rows("SELECT id FROM ar_goals WHERE user_id=%s AND id=%s", [actor.user_id, key]):
        raise Http404
    clause, args = "user_id=%s AND goal_id=%s", [actor.user_id, key]
    if raw.get("status"):
        if raw["status"] not in {"owned", "missing", "unavailable"}:
            raise ValueError("Choose supported progress")
        clause += " AND status=%s"
        args.append(raw["status"])
    if raw.get("q"):
        if len(raw["q"]) > 160:
            raise ValueError("Choose a short query")
        clause += " AND instr(lower(json_extract(payload,'$.label')),%s)>0"
        args.append(raw["q"].lower())
    total = store.rows("SELECT COUNT(*) AS n FROM ar_goal_items WHERE " + clause, args)[0]["n"]
    rows = store.rows(
        "SELECT id,CASE WHEN bytes<=1100 THEN payload END AS payload,sha FROM ar_goal_items WHERE "
        + clause
        + " ORDER BY rank LIMIT %s OFFSET %s",
        [*args, size, offset(page, size)],
    )
    return page_result([payload(r, state, "goal-item") for r in rows], "items", total, page, size)


@read
def goal_sources(actor, build, state, raw):
    from . import collection_goals

    page, size = paging(raw)
    total = store.rows("SELECT COUNT(*) AS n FROM ownership_declarations WHERE user_id=%s", [actor.user_id])[
        0
    ]["n"]
    rows = store.rows(
        "SELECT * FROM ownership_declarations WHERE user_id=%s ORDER BY id LIMIT %s OFFSET %s",
        [actor.user_id, size, offset(page, size)],
    )
    items = []
    for row in rows:
        available = collection_goals.full_source(row)
        owned = len(collection_goals.owned(row)) if available else None
        items.append(
            dict(
                id=row["id"],
                name=f"{owned} owned species · source {row['source_sha256'][:12]}"
                if available
                else "Regional source — unavailable for a full-source goal",
                available=available,
                owned=owned,
                source_sha256=row["source_sha256"],
            )
        )
    return page_result(items, "sources", total, page, size)
