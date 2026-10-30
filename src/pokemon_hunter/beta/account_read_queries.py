"""Private V2 reads: bounded expansion of checked durable account representations."""

import json

from django.http import Http404

from . import account_read_build as builds
from . import card_groups, collection, store

# Keep existing route and service imports stable while sharing one read boundary.
from .account_read_context import BASE as BASE
from .account_read_context import page_result as page_result
from .account_read_context import payload as payload
from .account_read_context import read as read
from .account_read_context import url as url
from .account_read_goal_queries import goal_items as goal_items
from .account_read_goal_queries import goal_options as goal_options
from .account_read_goal_queries import goal_sources as goal_sources
from .account_read_goal_queries import goal_workspace as goal_workspace
from .catalog_read_build import Unavailable
from .catalog_read_queries import paging
from .catalog_read_select import offset


def group_row(actor, build, key):
    rows = store.rows(
        "SELECT a.id,a.assertion_id,CASE WHEN a.bytes<=1100 THEN a.payload END AS payload,a.sha FROM ar_groups a JOIN cr_groups g ON g.id=a.id AND g.build=%s AND g.scope IN ('retained','shared') WHERE a.user_id=%s AND a.id=%s AND (a.present=1 OR a.recorded>0 OR a.available=1)",
        [build, actor.user_id, key],
    )
    if not rows:
        raise Http404("Group unavailable")
    return rows[0]


def condition(actor, build, filters, stride):
    scope = filters.get("scope", "catalog")
    clauses = ["g.user_id=%s"]
    params = [actor.user_id]
    clauses.append("g.present=1" if scope == "owned" else "g.available=1")
    for field, column in (("species", "species"), ("set", "set_id"), ("language", "language")):
        if filters.get(field):
            clauses.append(f"g.{column}=%s")
            params.append(filters[field])
    if (
        scope == "owned"
        and filters.get("q", "").strip()
        and not any(filters.get(f) for f in ("edition", "finish", "variant"))
    ):
        from .account_read_select import search_ranks

        sql, values = search_ranks(build, stride, filters["q"], "retained")
        clauses.append("+g.rank_set IN (" + sql + ")")
        params.extend(values)
    elif filters.get("q") or any(filters.get(f) for f in ("edition", "finish", "variant")):
        child_scope = "retained"
        child_clauses = ["m.build=%s", f"m.scope IN ('{child_scope}','shared')"]
        if scope == "catalog":
            child_clauses.append(
                "EXISTS(SELECT 1 FROM cr_printings p WHERE p.build=m.build AND p.scope IN ('retained','shared') AND p.id=m.id AND p.published=1)"
            )
        params.append(build)
        for field in ("edition", "finish", "variant"):
            if filters.get(field):
                child_clauses.append(f"m.{field}=%s")
                params.append(filters[field])
        for token in filters.get("q", "").casefold().split():
            child_clauses.append("instr(m.search,%s)>0")
            params.append(token)
        clauses.append(
            "+g.rank_set IN (SELECT m.rank_set FROM cr_match m WHERE " + " AND ".join(child_clauses) + ")"
        )
    return " AND ".join(clauses), params


@read
def groups(actor, build, state, raw, *, dex=None, owned=False):
    if owned:
        if "scope" in raw:
            raise ValueError("My Cards has fixed owned scope")
        raw["scope"] = "owned"
    if dex is not None:
        if not 1 <= dex <= 251:
            raise Http404
        if "species" in raw or "scope" in raw:
            raise ValueError("Species has fixed scope")
        raw["species"] = str(dex)
    filters = card_groups._filters(raw, dict(public=False, generation=state["generation"]))
    page, size = filters["page"], filters["page_size"]
    if state["catalog_equivalent"] and filters.get("scope", "catalog") == "catalog":
        from .catalog_read_select import select

        total, selected = select(build, filters)
        ids = [r["id"] for r in selected]
        rows = (
            store.rows(
                "SELECT id,CASE WHEN bytes<=1100 THEN payload END AS payload,sha FROM ar_groups WHERE user_id=%s AND id IN ("
                + ",".join(["%s"] * len(ids))
                + ")",
                [actor.user_id, *ids],
            )
            if ids
            else []
        )
        by_id = {r["id"]: r for r in rows}
        if len(by_id) != len(ids):
            raise Unavailable("account_membership_incomplete")
        rows = [by_id[key] for key in ids]
    else:
        where, params = condition(actor, build, filters, state["catalog_stride"])
        flag = "present" if filters.get("scope") == "owned" else "available"
        join = f" FROM ar_membership g INDEXED BY ar_membership_{flag}_{filters['sort']} WHERE " + where
        page, size = filters["page"], filters["page_size"]
        total = store.rows("SELECT COUNT(*) AS n" + join, params)[0]["n"]
        page_join, page_params = join, params
        if (
            flag == "present"
            and filters.get("q", "").strip()
            and not any(filters.get(field) for field in ("edition", "finish", "variant"))
        ):
            # Exact total uses the complete FTS postings. Page membership can use
            # compact common text and only same-child/substring residual ranks,
            # avoiding a second full positive posting list for forty selected IDs.
            from .account_read_select import search_ranks

            tokens = filters["q"].casefold().split()
            search, values = search_ranks(build, state["catalog_stride"], filters["q"], "retained")
            residual = search.split(" UNION ALL ", 1)[1]
            base_filters = dict(filters, q="")
            base_where, base_params = condition(actor, build, base_filters, state["catalog_stride"])
            common = " AND ".join("instr(c.search,%s)>0" for _ in tokens)
            page_join = (
                f" FROM ar_membership g INDEXED BY ar_membership_{flag}_{filters['sort']} WHERE "
                + base_where
                + " AND (EXISTS(SELECT 1 FROM cr_groups c WHERE c.build=%s "
                + "AND c.scope IN ('retained','shared') AND c.id=g.id AND "
                + common
                + ") OR +g.rank_set IN ("
                + residual
                + "))"
            )
            page_params = [*base_params, build, *tokens, *values[3:]]
        rows = (
            store.rows(
                "WITH page AS MATERIALIZED (SELECT g.id,g.rank_"
                + filters["sort"]
                + " AS rank"
                + page_join
                + f" ORDER BY g.rank_{filters['sort']},g.id LIMIT %s OFFSET %s) SELECT a.id,CASE WHEN a.bytes<=1100 THEN a.payload END AS payload,a.sha FROM page JOIN ar_groups a ON a.id=page.id AND a.user_id=%s ORDER BY page.rank,a.id",
                [*page_params, size, offset(page, size), actor.user_id],
            )
            if offset(page, size) < total
            else []
        )

    result = page_result([payload(r, state, "group") for r in rows], "groups", total, page, size)
    result.update(
        scope=filters.get("scope", "catalog"),
        unresolved=dict(total=json.loads(state["counts"])["ar_evidence"], url=url(state, "evidence/")),
    )
    result["matching_filters"] = {k: raw[k] for k in ("q", "edition", "finish", "variant") if raw.get(k)}
    return result


@read
def detail(actor, build, state, raw, *, key):
    if set(raw) - {"child"} or any(not isinstance(v, str) or len(v) > 160 for v in raw.values()):
        raise ValueError("Choose a supported child")
    group = group_row(actor, build, key)
    selected = None
    if "child" in raw:
        children = store.rows(
            "SELECT id,CASE WHEN bytes<=1100 THEN payload END AS payload,sha FROM cr_children WHERE build=%s AND scope IN ('retained','shared') AND group_id=%s AND id=%s",
            [build, key, raw["child"]],
        )
        if not children:
            raise Http404("Child unavailable")
        selected = payload(children[0], state, "printing")
    counts = store.rows(
        "SELECT (SELECT COUNT(*) FROM cr_children WHERE build=%s AND scope IN ('retained','shared') AND group_id=%s) AS variants, (SELECT COUNT(*) FROM ar_copies WHERE user_id=%s AND group_id=%s AND state='active') AS copies, (SELECT COUNT(*) FROM ar_copies WHERE user_id=%s AND group_id=%s AND state<>'active') AS history, (SELECT COUNT(DISTINCT id) FROM ar_evidence_links WHERE user_id=%s AND group_id IN (%s,'*')) AS evidence",
        [build, key, actor.user_id, key, actor.user_id, key, actor.user_id, key],
    )[0]
    evidence_total = counts.pop("evidence")
    return dict(
        group=payload(group, state, "group"),
        selected_child=selected,
        ownership_evidence_url=url(state, f"resources/card/{group['assertion_id']}/")
        if group["assertion_id"]
        else None,
        artwork_url=url(state, f"card-groups/{key}/artwork/"),
        **{
            name: dict(total=total, url=url(state, f"card-groups/{key}/{name}/"))
            for name, total in counts.items()
        },
        unresolved=dict(total=evidence_total, url=url(state, f"card-groups/{key}/evidence/")),
    )


@read
def variants(actor, build, state, raw, *, key):
    page, size = paging(raw, ("q", "edition", "finish", "variant"))
    group_row(actor, build, key)
    clauses, params = ["p.build=%s", "p.scope IN ('retained','shared')", "p.group_id=%s"], [build, key]
    for field in ("edition", "finish", "variant"):
        if raw.get(field):
            clauses.append(f"p.{field}=%s")
            params.append(raw[field])
    for word in raw.get("q", "").casefold().split():
        clauses.append("instr(p.search,%s)>0")
        params.append(word)
    where = " AND ".join(clauses)
    total = store.rows("SELECT COUNT(*) AS n FROM cr_children p WHERE " + where, params)[0]["n"]
    rows = store.rows(
        "SELECT p.id,CASE WHEN p.bytes<=1100 THEN p.payload END AS payload,p.sha,EXISTS(SELECT 1 FROM ar_copies c INDEXED BY ar_copy_printing WHERE c.user_id=%s AND c.printing_id=p.id AND c.current=1 AND c.exact=1) AS owned,EXISTS(SELECT 1 FROM ar_variant_ownership v WHERE v.user_id=%s AND v.id=p.id) AS declared FROM cr_children p INDEXED BY cr_child_group WHERE "
        + where
        + " ORDER BY p.id LIMIT %s OFFSET %s",
        [actor.user_id, actor.user_id, *params, size, offset(page, size)],
    )
    return page_result(
        [
            dict(
                payload(r, state, "printing"),
                established_total_quantity=None,
                exact_printing_owned=bool(r["owned"]),
                declared_variant_owned=bool(r["declared"]),
            )
            for r in rows
        ],
        "variants",
        total,
        page,
        size,
    )


@read
def copies(actor, build, state, raw, *, key, history=False):
    page, size = paging(raw)
    group_row(actor, build, key)
    where = "user_id=%s AND group_id=%s AND state" + ("<>'active'" if history else "='active'")
    params = [actor.user_id, key]
    total = store.rows("SELECT COUNT(*) AS n FROM ar_copies WHERE " + where, params)[0]["n"]
    rows = store.rows(
        "SELECT id,CASE WHEN bytes<=1100 THEN payload END AS payload,sha,current,exact FROM ar_copies WHERE "
        + where
        + " ORDER BY id LIMIT %s OFFSET %s",
        [*params, size, offset(page, size)],
    )
    return page_result(
        [
            dict(payload(r, state, "copy"), current=bool(r["current"]), exact_printing_owned=bool(r["exact"]))
            for r in rows
        ],
        "history" if history else "copies",
        total,
        page,
        size,
    )


@read
def evidence(actor, build, state, raw, *, key=None):
    page, size = paging(raw)
    where, params = "user_id=%s", [actor.user_id]
    total = json.loads(state["counts"])["ar_evidence"]
    if key is not None:
        group_row(actor, build, key)
        where += " AND id IN (SELECT id FROM ar_evidence_links WHERE user_id=%s AND group_id IN (%s,'*'))"
        params.extend([actor.user_id, key])
        total = store.rows("SELECT COUNT(*) AS n FROM ar_evidence WHERE " + where, params)[0]["n"]
    rows = store.rows(
        "SELECT id,CASE WHEN bytes<=1100 THEN payload END AS payload,sha FROM ar_evidence WHERE "
        + where
        + " ORDER BY id LIMIT %s OFFSET %s",
        [*params, size, offset(page, size)],
    )
    return page_result(
        [dict(id=r["id"], record=payload(r, state, "evidence")) for r in rows], "evidence", total, page, size
    )


def option_selection(actor, build, state, field, scope):
    membership = "a.present=1" if scope == "owned" else "a.available=1"
    where = (
        "o.build=%s AND o.scope IN ('retained','shared') AND o.field=%s AND EXISTS(SELECT 1 FROM cr_postings p JOIN ar_groups a ON a.id=p.group_id AND a.user_id=%s WHERE p.build=o.build AND p.scope IN ('retained','shared') AND p.field=o.field AND p.value=o.value AND "
        + membership
        + ")"
    )
    params = [build, field, actor.user_id]
    if scope == "catalog":
        if state["catalog_equivalent"]:
            where = where.replace("('retained','shared')", "('public','shared')")
        else:
            where += (
                " AND o.value IN (SELECT DISTINCT m."
                + ("set_id" if field == "set" else field)
                + " FROM cr_match m JOIN cr_printings c ON c.build=m.build AND c.id=m.id AND c.scope IN ('retained','shared') AND c.published=1 WHERE m.build=%s AND m.scope IN ('retained','shared'))"
            )
            params.append(build)
    return where, params


@read
def options(actor, build, state, raw):
    page, size = paging(raw, ("field", "scope"))
    field, scope = raw.get("field", "set"), raw.get("scope", "catalog")
    if field not in {"set", "language", "edition", "finish", "variant"} or scope not in {"catalog", "owned"}:
        raise ValueError("Choose supported filter options")
    where, params = option_selection(actor, build, state, field, scope)
    total = store.rows("SELECT COUNT(*) AS n FROM cr_options o WHERE " + where, params)[0]["n"]
    rows = store.rows(
        "SELECT o.rank,o.bytes,CASE WHEN o.bytes<=200 THEN o.value END AS value,CASE WHEN o.bytes<=200 THEN o.label END AS label FROM cr_options o WHERE "
        + where
        + " ORDER BY o.rank LIMIT %s OFFSET %s",
        [*params, size, offset(page, size)],
    )
    items = [
        dict(value=r["value"], label=r["label"])
        if r["bytes"] <= 200
        else dict(oversized=True, url=url(state, f"resources/option/{field}-{r['rank']}/", scope=scope))
        for r in rows
    ]
    result = page_result(items, "options", total, page, size)
    result.update(
        field=field,
        scope=scope,
        next=url(state, "card-group-filters/", field=field, scope=scope, page=page + 1, page_size=size)
        if page * size < total
        else None,
    )
    return result


@read
def species(actor, build, state, raw):
    from . import account_read_goals, account_read_species, species_projection, species_scope

    page, size = paging(raw, tuple(species_projection.FILTERS | {"version"}))
    selected = species_projection.filters({k: v for k, v in raw.items() if k in species_projection.FILTERS})
    goal = account_read_goals.scope(actor, raw)
    match, match_args = account_read_species.expression(selected)
    restricted = any(selected[k] for k in species_scope.KEYS)
    unresolved_match = species_scope.match({}, selected)
    compact_dates = not any(selected[k] for k in ("set", "era", "type", "rarity", "card"))
    catalog_index = "ar_scope_date_counts_species" if compact_dates else "ar_scope_species"
    catalog_table = "ar_scope_date_counts" if compact_dates else "ar_scope_catalog"
    weight = "n" if compact_dates else "1"
    candidates, candidate_args = account_read_species.candidates(build, selected)
    if candidates:
        catalog_index = "sqlite_autoindex_ar_scope_catalog_1"
    owned_index = "ar_scope_owned_dates" if compact_dates else "ar_scope_owned_species"
    # Aggregate scalar facts in SQLite; expand only the selected species summaries.
    common = f"SUM(({match})) AS yes,SUM(({match}) IS NULL) AS unknown"
    catalog_common = f"SUM(({match})*{weight}) AS yes,SUM((({match}) IS NULL)*{weight}) AS unknown"
    ctes = f"WITH catalog AS (SELECT species,{catalog_common},SUM({weight}) AS indexed,SUM((start IS NOT NULL)*{weight}) AS dated FROM {catalog_table} INDEXED BY {catalog_index} WHERE build=%s{candidates} GROUP BY species), owned AS (SELECT species,{common} FROM ar_scope_owned INDEXED BY {owned_index} WHERE user_id=%s GROUP BY species), base AS (SELECT s.id,s.summary AS payload,s.summary_sha AS sha,CAST(s.id AS INTEGER) AS dex,json_extract(s.summary,'$.current_present') AS present,CASE WHEN %s THEN (COALESCE(o.yes,0)>0 OR (json_extract(s.summary,'$.details_needed') AND {int(unresolved_match is True)})) ELSE json_extract(s.summary,'$.current_present') END AS scoped,COALESCE(c.yes,0) AS eligible,COALESCE(c.unknown,0) AS catalog_unknown,COALESCE(o.unknown,0)>0 OR (json_extract(s.summary,'$.details_needed') AND {int(unresolved_match is None)}) AS uncertain,COALESCE(c.indexed,0) AS indexed,COALESCE(c.dated,0) AS dated,{{goal}} AS goal_status FROM ar_species s LEFT JOIN catalog c ON c.species=CAST(s.id AS INTEGER) LEFT JOIN owned o ON o.species=CAST(s.id AS INTEGER) WHERE s.user_id=%s{{membership}})"
    args = [
        *match_args,
        *match_args,
        build,
        *candidate_args,
        *match_args,
        *match_args,
        actor.user_id,
        restricted,
    ]
    goal_column = (
        "(SELECT status FROM ar_goal_items i WHERE i.user_id=s.user_id AND i.goal_id=%s AND i.species=CAST(s.id AS INTEGER))"
        if goal
        else "NULL"
    )
    if goal:
        args.append(goal["id"])
    args.append(actor.user_id)
    membership = (
        " AND EXISTS(SELECT 1 FROM ar_goal_items i WHERE i.user_id=s.user_id AND i.goal_id=%s AND i.species=CAST(s.id AS INTEGER))"
        if goal
        else ""
    )
    if goal:
        args.append(goal["id"])
    ctes = ctes.replace("{goal}", goal_column).replace("{membership}", membership)
    region = (
        "dex<=151" if selected["region"] == "kanto" else "dex>151" if selected["region"] == "johto" else "1"
    )
    where = ["1"]
    if selected["owned"] != "all":
        where.append("scoped=%s")
        args.append(int(selected["owned"] == "owned"))
    q = selected["q"].strip().casefold()
    if q:
        where.append("(instr(lower(json_extract(payload,'$.name')),%s)>0 OR dex=%s)")
        args.extend(
            [
                q,
                int(q.removeprefix("#"))
                if q.removeprefix("#").isascii() and q.removeprefix("#").isdecimal()
                else 0,
            ]
        )
    ctes += (
        ", region AS MATERIALIZED (SELECT * FROM base WHERE "
        + region
        + "), result AS MATERIALIZED (SELECT * FROM region WHERE "
        + " AND ".join(where)
        + ")"
    )
    rows = store.rows(
        ctes
        + " SELECT p.*,t.total,t.members,t.current_total,t.scoped_total,t.indexed_total,t.dated_total,t.eligible_total,t.unresolved_total FROM (SELECT (SELECT COUNT(*) FROM result) AS total,COUNT(*) AS members,COALESCE(SUM(present),0) AS current_total,COALESCE(SUM(scoped),0) AS scoped_total,(SELECT COALESCE(SUM(n),0) FROM ar_scope_date_counts WHERE build=%s) AS indexed_total,(SELECT COALESCE(SUM((start IS NOT NULL)*n),0) FROM ar_scope_date_counts WHERE build=%s) AS dated_total,COALESCE(SUM(eligible>0),0) AS eligible_total,COALESCE(SUM(NOT scoped AND (uncertain OR catalog_unknown>0)),0) AS unresolved_total FROM region) t LEFT JOIN (SELECT * FROM result ORDER BY dex LIMIT %s OFFSET %s) p ON 1",
        [*args, build, build, size, offset(page, size)],
    )
    totals = rows[0]
    items = []
    for row in rows:
        if row["id"] is None:
            continue
        item = payload(row, state, "species")
        item.update(
            scoped_present=bool(row["scoped"]),
            scope_status="collected"
            if row["scoped"]
            else "unresolved"
            if row["uncertain"] or row["catalog_unknown"]
            else "no_indexed"
            if not row["eligible"]
            else "missing",
            eligible_indexed_printings=row["eligible"],
            goal_present=(row["goal_status"] == "owned") if goal else None,
            evidence_url=url(state, f"resources/species/{row['id']}/"),
        )
        items.append(item)
    result = page_result(items, "species", totals["total"], page, size)
    result.update(
        filters=selected,
        restricted=restricted,
        current_progress=dict(satisfied=totals["current_total"], total=totals["members"], units="species"),
        scoped_progress=dict(satisfied=totals["scoped_total"], total=totals["members"], units="species"),
        coverage=dict(
            indexed_printings=totals["indexed_total"],
            dated_printings=totals["dated_total"],
            unknown_dates=totals["indexed_total"] - totals["dated_total"],
            eligible_species=totals["eligible_total"],
            unresolved_species=totals["unresolved_total"],
        ),
    )
    if goal:
        totals_goal = store.rows(
            "SELECT COUNT(*) AS total, SUM(status='owned') AS satisfied FROM ar_goal_items WHERE user_id=%s AND goal_id=%s",
            [actor.user_id, goal["id"]],
        )[0]
        result["progress"] = dict(total=totals_goal["total"], satisfied=totals_goal["satisfied"] or 0)
    result["scope"] = (
        dict(
            kind="frozen_goal",
            progress_basis="saved_declaration"
            if goal["kind"] in {"original151_collection", "collection_species"}
            else "qualified_current_copies",
            supported=True,
            units="species",
            goal_id=goal["id"],
            version=goal["version"],
            revision=goal["revision"],
            name=goal["name"],
        )
        if goal
        else dict(kind="current", goal_id=None)
    )
    return result


@read
def species_options(actor, build, state, raw):
    from . import account_read_species

    page, size = paging(raw, ("field",))
    field = raw.get("field", "set")
    sql, args = account_read_species.option_query(build, field)
    total = store.rows("SELECT COUNT(*) AS n FROM (" + sql + ")", args)[0]["n"]
    rows = store.rows(
        "SELECT CASE WHEN length(CAST(value AS BLOB))+length(CAST(label AS BLOB))<=200 THEN value END AS value,CASE WHEN length(CAST(value AS BLOB))+length(CAST(label AS BLOB))<=200 THEN label END AS label FROM ("
        + sql
        + ") LIMIT %s OFFSET %s",
        [*args, size, offset(page, size)],
    )
    items = [
        r
        if r["value"] is not None
        else dict(
            oversized=True, url=url(state, f"resources/species-option/{field}-{offset(page, size) + i}/")
        )
        for i, r in enumerate(rows)
    ]
    result = page_result(items, "options", total, page, size)
    result.update(
        field=field,
        next=url(state, "species-filter-options/", field=field, page=page + 1, page_size=size)
        if page * size < total
        else None,
    )
    return result


@read
def artwork(actor, build, state, raw, *, key):
    if raw:
        raise ValueError("Unsupported artwork selectors")
    group_row(actor, build, key)
    rows = store.rows(
        "SELECT id,payload,sha FROM ar_artwork WHERE user_id=%s AND id=%s", [actor.user_id, key]
    )
    return dict(reference_image=payload(rows[0], state, "artwork", full=True) if rows else None)


@read
def context(actor, build, state, raw):
    if raw:
        raise ValueError("Context has no data selectors")
    counts = store.rows(
        "SELECT (SELECT COUNT(*) FROM ar_membership WHERE user_id=%s AND present=1) AS owned_groups,(SELECT COUNT(*) FROM ar_copies WHERE user_id=%s AND state='active') AS recorded_copy_count",
        [actor.user_id, actor.user_id],
    )[0]
    return dict(
        collection=dict(**counts, unresolved=json.loads(state["counts"])["ar_evidence"]),
        links=dict(
            groups=url(state, "my-card-groups/"),
            duplicates=url(state, "duplicate-counts/"),
            species=url(state, "pokedex-species/"),
        ),
    )


@read
def duplicates(actor, build, state, raw):
    if set(raw) != {"ids"} or not isinstance(raw["ids"], str) or len(raw["ids"]) > 16000:
        raise ValueError("Supply bounded literal printing IDs")
    ids = raw["ids"].split(",")
    if not 1 <= len(ids) <= 100 or len(set(ids)) != len(ids) or any(not key or len(key) > 160 for key in ids):
        raise ValueError("Choose at most 100 distinct printing IDs")
    placeholders = ",".join(["%s"] * len(ids))
    found = store.rows(
        f"SELECT id FROM cr_printings WHERE build=%s AND scope IN ('retained','shared') AND id IN ({placeholders})",
        [build, *ids],
    )
    if len(found) != len(ids):
        raise ValueError("Unknown printing ID")
    rows = store.rows(
        f"SELECT printing_id,COUNT(*) AS recorded,SUM(current) AS current FROM ar_copies WHERE user_id=%s AND state='active' AND printing_id IN ({placeholders}) GROUP BY printing_id",
        [actor.user_id, *ids],
    )
    counts = {
        r["printing_id"]: dict(recorded_copy_count=r["recorded"], current_copy_count=r["current"])
        for r in rows
    }
    return dict(
        printings=[
            dict(id=key, **counts.get(key, dict(recorded_copy_count=0, current_copy_count=0))) for key in ids
        ]
    )


@read
def resource(actor, build, state, raw, *, kind, key):
    if kind == "species-option":
        from . import account_read_species

        if raw:
            raise ValueError("Unsupported option selectors")
        field, sep, rank = key.rpartition("-")
        if not sep:
            raise Http404
        rank = card_groups._integer(rank, "option", 0)
        sql, args = account_read_species.option_query(build, field)
        rows = store.rows(sql + " LIMIT 1 OFFSET %s", [*args, rank])
        if not rows:
            raise Http404
        return dict(record=rows[0])
    if kind == "option":
        if set(raw) - {"scope"} or raw.get("scope", "catalog") not in {"catalog", "owned"}:
            raise ValueError("Unsupported option selectors")
        field, sep, rank = key.rpartition("-")
        if field not in {"set", "language", "edition", "finish", "variant"} or not sep:
            raise Http404
        rank = card_groups._integer(rank, "option", 0)
        scope = raw.get("scope", "catalog")
        where, args = option_selection(actor, build, state, field, scope)
        options = store.rows(
            "SELECT value,label FROM cr_options o WHERE " + where + " AND o.rank=%s", [*args, rank]
        )
        if not options:
            raise Http404
        return dict(record=options[0])
    if raw:
        raise ValueError("Unsupported resource selectors")
    if kind in {"entry-set", "entry-game"}:
        table = "catalog_sets" if kind == "entry-set" else "games"
        columns = "id,name,game_id,language" if kind == "entry-set" else "id,name,game_key"
        rows = store.rows(f"SELECT {columns} FROM {table} WHERE id=%s", [key])
        if not rows:
            raise Http404
        return dict(record=rows[0])
    tables = dict(
        group="ar_groups",
        copy="ar_copies",
        evidence="ar_evidence",
        species="ar_species",
        card="ar_cards",
        artwork="ar_artwork",
        goal="ar_goals",
    )
    tables["goal-item"] = "ar_goal_items"
    if kind in {"group", "artwork"}:
        group_row(actor, build, key)
    if kind == "goal-header":
        rows = store.rows(
            "SELECT id,summary AS payload,summary_sha AS sha FROM ar_goals WHERE user_id=%s AND id=%s",
            [actor.user_id, key],
        )
        if not rows:
            raise Http404
        goal = builds.decode(rows[0])
        if "header" not in goal:
            raise Unavailable("goal_header_preparation_required")
        counts = {
            r["status"]: r["n"]
            for r in store.rows(
                "SELECT status,COUNT(*) AS n FROM ar_goal_items WHERE user_id=%s AND goal_id=%s GROUP BY status",
                [actor.user_id, key],
            )
        }
        goal.update(
            total=sum(counts.values()),
            satisfied=counts.get("owned", 0),
            missing=counts.get("missing", 0),
            unavailable=counts.get("unavailable", 0),
            items_url=url(state, f"goals/{key}/items/"),
        )
        return dict(record=goal)
    if kind in tables:
        rows = store.rows(
            f"SELECT id,payload,sha FROM {tables[kind]} WHERE user_id=%s AND id=%s", [actor.user_id, key]
        )
    elif kind == "printing":
        rows = store.rows(
            "SELECT p.id,p.payload,p.sha,p.group_id FROM cr_printings p WHERE p.build=%s AND p.scope IN ('retained','shared') AND p.id=%s AND (p.group_id IS NULL OR p.published=1 OR EXISTS(SELECT 1 FROM ar_groups a WHERE a.user_id=%s AND a.id=p.group_id AND (a.present=1 OR a.recorded>0)))",
            [build, key, actor.user_id],
        )
        if rows and rows[0]["group_id"]:
            group_row(actor, build, rows[0]["group_id"])
    else:
        raise Http404
    if not rows:
        raise Http404
    return dict(record=payload(rows[0], state, kind, full=True))


@read
def printings(actor, build, state, raw, *, unresolved=False):
    page, size = paging(raw, ("q", "set", "language"))
    clauses, params = (
        [
            "p.build=%s",
            "p.scope IN ('retained','shared')",
            "(p.group_id IS NULL OR p.published=1 OR EXISTS(SELECT 1 FROM ar_groups a WHERE a.user_id=%s AND a.id=p.group_id AND (a.present=1 OR a.recorded>0)))",
        ],
        [build, actor.user_id],
    )
    if unresolved:
        clauses.append("p.group_id IS NULL")
    for field, expression in (
        ("set", "json_extract(p.payload,'$.set_id')"),
        ("language", "json_extract(p.payload,'$.language')"),
    ):
        if raw.get(field):
            clauses.append(f"{expression}=%s")
            params.append(raw[field])
    for part in raw.get("q", "").casefold().split():
        clauses.append("instr(p.search,%s)>0")
        params.append(part)
    where = " AND ".join(clauses)
    total = store.rows(
        "SELECT COUNT(*) AS n FROM cr_printings p INDEXED BY ar_private_picker WHERE " + where, params
    )[0]["n"]
    rows = store.rows(
        "SELECT id,CASE WHEN bytes<=1100 THEN payload END AS payload,sha FROM cr_printings p INDEXED BY ar_private_picker WHERE "
        + where
        + " ORDER BY id LIMIT %s OFFSET %s",
        [*params, size, offset(page, size)],
    )
    return page_result([payload(r, state, "printing") for r in rows], "printings", total, page, size)


@read
def photos(actor, build, state, raw, *, key):
    if raw:
        raise ValueError("Unsupported photo selectors")
    from . import image_bindings

    copy = collection.one(actor, "copy", key)
    if copy["state"] != "active":
        raise Http404
    return dict(copy_id=key, photo_references=image_bindings.private_copy_photos(actor, [key])[key])


@read
def resolve(actor, build, state, raw, *, key):
    if raw or len(key) > 160:
        raise ValueError("Unsupported alias selector")
    found = store.rows(
        "SELECT a.printing_id,c.group_id FROM cr_aliases a LEFT JOIN cr_children c ON c.build=a.build AND c.scope IN ('retained','shared') AND c.id=a.printing_id WHERE a.build=%s AND a.scope IN ('retained','shared') AND a.alias=%s LIMIT 2",
        [build, key],
    )
    if key.startswith(card_groups.NAMESPACE):
        if found:
            raise collection.ReviewConflict("alias_namespace")
        group_row(actor, build, key)
        return dict(group_id=key, child=None, url=card_groups.canonical_url(key))
    if len(found) > 1:
        raise collection.ReviewConflict("alias_ambiguous")
    if not found or not found[0]["group_id"]:
        raise Http404
    group_row(actor, build, found[0]["group_id"])
    return dict(
        group_id=found[0]["group_id"],
        child=found[0]["printing_id"],
        url=card_groups.canonical_url(found[0]["group_id"], found[0]["printing_id"]),
    )


@read
def species_owned_groups(actor, build, state, raw, *, dex):
    """Bounded card page with server-evaluated same-evidence scope qualification."""
    from . import account_read_species, species_projection, species_scope

    allowed = set(species_scope.KEYS) | {"page", "page_size"}
    if set(raw) - allowed:
        raise ValueError("Choose supported card scope")
    selected = species_projection.filters({k: v for k, v in raw.items() if k in species_scope.KEYS})
    species_projection.require_dex(dex)
    result = groups.__wrapped__(
        actor,
        build,
        state,
        {**{k: v for k, v in raw.items() if k in {"page", "page_size"}}, "species": str(dex)},
        owned=True,
    )
    ids = [g["id"] for g in result["groups"]]
    states = {}
    if ids:
        match, args = account_read_species.expression(selected)
        rows = store.rows(
            "SELECT g.id,MAX((" + match + ")) AS yes,MAX((" + match + ") IS NULL) AS unknown "
            "FROM ar_groups g LEFT JOIN ar_scope_owned s ON s.user_id=g.user_id AND s.component=g.component "
            "WHERE g.user_id=%s AND g.id IN (" + ",".join(["%s"] * len(ids)) + ") GROUP BY g.id",
            [*args, *args, actor.user_id, *ids],
        )
        states = {
            r["id"]: "collected" if r["yes"] else "unresolved" if r["unknown"] else "outside" for r in rows
        }
    result["scope_groups"] = states
    return result


@read
def binders(actor, build, state, raw):
    page, size = paging(raw)
    total = store.rows("SELECT COUNT(*) AS n FROM binders WHERE user_id=%s", [actor.user_id])[0]["n"]
    rows = store.rows(
        "SELECT id,name FROM binders WHERE user_id=%s ORDER BY name,id LIMIT %s OFFSET %s",
        [actor.user_id, size, offset(page, size)],
    )
    return page_result(rows, "binders", total, page, size)


@read
def selection_groups(actor, build, state, raw):
    """Resolve a bounded candidate set without inferring possession in the browser."""
    if set(raw) != {"ids"} or not isinstance(raw["ids"], str) or len(raw["ids"]) > 16000:
        raise ValueError("Supply bounded printing IDs")
    ids = raw["ids"].split(",")
    if not 1 <= len(ids) <= 100 or len(set(ids)) != len(ids) or any(not key or len(key) > 160 for key in ids):
        raise ValueError("Choose at most 100 distinct printing IDs")
    rows = store.rows(
        "SELECT p.id,p.group_id FROM cr_printings p WHERE p.build=%s AND p.scope IN ('retained','shared') AND p.id IN ("
        + ",".join(["%s"] * len(ids))
        + ") AND (p.published=1 OR EXISTS(SELECT 1 FROM ar_groups g WHERE g.user_id=%s AND g.id=p.group_id AND (g.present=1 OR g.recorded>0)))",
        [build, *ids, actor.user_id],
    )
    keys = sorted({r["group_id"] for r in rows if r["group_id"]})
    selected = (
        store.rows(
            "SELECT id,CASE WHEN bytes<=1100 THEN payload END AS payload,sha FROM ar_groups WHERE user_id=%s AND id IN ("
            + ",".join(["%s"] * len(keys))
            + ")",
            [actor.user_id, *keys],
        )
        if keys
        else []
    )
    return dict(groups=[payload(g, state, "group") for g in selected], candidates=rows)


@read
def entry_options(actor, build, state, raw):
    """Paged editor dictionaries; collection authority stays in mutation preview."""
    page, size = paging(raw, ("field", "game", "game_key"))
    if size > 50:
        raise ValueError("Choose at most 50 entry choices per page")
    field = raw.get("field", "set")
    if field == "game":
        if raw.get("game"):
            raise ValueError("Game selector requires set choices")
        source, args = "SELECT id,game_key,name FROM games", []
        if raw.get("game_key"):
            source += " WHERE game_key=%s"
            args.append(raw["game_key"])
    elif field == "set":
        if raw.get("game_key"):
            raise ValueError("Game key requires game choices")
        source = "SELECT id,name,game_id,language FROM catalog_sets"
        args = []
        if raw.get("game"):
            source += " WHERE game_id=%s"
            args.append(raw["game"])
    else:
        raise ValueError("Choose game or set options")
    total = store.rows("SELECT COUNT(*) AS n FROM (" + source + ")", args)[0]["n"]
    rows = store.rows(source + " ORDER BY name,id LIMIT %s OFFSET %s", [*args, size, offset(page, size)])
    return page_result(
        [
            r
            if len(builds.encode(r).encode()) <= 250
            else dict(id=r["id"], oversized=True, url=url(state, f"resources/entry-{field}/{r['id']}/"))
            for r in rows
        ],
        "options",
        total,
        page,
        size,
    )


@read
def labels(actor, build, state, raw):
    """Resolve at most 100 selected literals without downloading their dictionaries."""
    if set(raw) != {"items"} or len(raw["items"]) > 20000:
        raise ValueError("Choose bounded label references")
    items = json.loads(raw["items"])
    if not isinstance(items, list) or len(items) > 100:
        raise ValueError("Choose at most 100 labels")
    kinds = {
        "set",
        "game",
        "binder",
        "goal",
        "printing",
        "language",
        "edition",
        "finish",
        "variant",
        "era",
        "type",
        "rarity",
    }
    if any(
        not isinstance(i, dict)
        or set(i) != {"kind", "id"}
        or i["kind"] not in kinds
        or not isinstance(i["id"], str)
        or len(i["id"]) > 160
        for i in items
    ):
        raise ValueError("Choose valid label references")
    found = {}
    for kind in sorted({i["kind"] for i in items}):
        ids = sorted({i["id"] for i in items if i["kind"] == kind})
        marks = ",".join(["%s"] * len(ids))
        if kind in {"set", "game", "binder", "goal"}:
            table = {"set": "catalog_sets", "game": "games", "binder": "binders", "goal": "collection_goals"}[
                kind
            ]
            private = kind in {"binder", "goal"}
            rows = store.rows(
                f"SELECT id,name AS label FROM {table} WHERE id IN ({marks})"
                + (" AND user_id=%s" if private else ""),
                [*ids, *([actor.user_id] if private else [])],
            )
        elif kind == "printing":
            rows = store.rows(
                "SELECT p.id,json_extract(p.payload,'$.name') || ' · #' || COALESCE(json_extract(p.payload,'$.collector_number'),'') AS label FROM cr_printings p WHERE p.build=%s AND p.scope IN ('retained','shared') AND p.id IN ("
                + marks
                + ") AND (p.published=1 OR EXISTS(SELECT 1 FROM ar_copies c WHERE c.user_id=%s AND c.printing_id=p.id))",
                [build, *ids, actor.user_id],
            )
        else:
            if kind in {"language", "edition", "finish", "variant"}:
                rows = store.rows(
                    "SELECT value AS id,label FROM cr_options WHERE build=%s AND scope IN ('retained','shared') AND field=%s AND value IN ("
                    + marks
                    + ")",
                    [build, kind, *ids],
                )
            else:
                from . import account_read_species

                sql, args = account_read_species.option_query(build, kind)
                rows = store.rows(
                    "SELECT value AS id,label FROM (" + sql + ") WHERE value IN (" + marks + ")",
                    [*args, *ids],
                )
        found.update({(kind, r["id"]): r["label"] for r in rows})
    result = []
    for item in items:
        label = found.get((item["kind"], item["id"]))
        row = dict(**item, label=label, available=label is not None)
        if label and len(label.encode()) > 1000:
            kind = "entry-" + item["kind"] if item["kind"] in {"set", "game"} else item["kind"]
            row.update(
                label="Large label — open complete record",
                oversized=True,
                url=url(state, f"resources/{kind}/{item['id']}/"),
            )
        result.append(row)
    return dict(labels=result)


@read
def selected_groups(actor, build, state, raw):
    if set(raw) != {"ids"} or len(raw["ids"]) > 17000:
        raise ValueError("Choose bounded groups")
    ids = raw["ids"].split(",")
    if not 1 <= len(ids) <= 100 or len(set(ids)) != len(ids) or any(not i or len(i) > 160 for i in ids):
        raise ValueError("Choose at most 100 distinct groups")
    rows = store.rows(
        "SELECT a.id,CASE WHEN a.bytes<=1100 THEN a.payload END AS payload,a.sha FROM ar_groups a JOIN cr_groups g ON g.id=a.id AND g.build=%s AND g.scope IN ('retained','shared') WHERE a.user_id=%s AND a.id IN ("
        + ",".join(["%s"] * len(ids))
        + ") AND (a.present=1 OR a.recorded>0 OR a.available=1)",
        [build, actor.user_id, *ids],
    )
    return dict(groups=[payload(r, state, "group") for r in rows])


@read
def group_artwork(actor, build, state, raw):
    from . import image_bindings
    from .catalog_read_queries import artwork_ids

    ids = artwork_ids(raw)
    if not image_bindings.enabled():
        return dict(artwork={})
    rows = store.rows(
        "SELECT i.id,i.payload,i.sha FROM ar_artwork i JOIN ar_groups g ON g.user_id=i.user_id AND g.id=i.id WHERE i.user_id=%s AND i.id IN ("
        + ",".join(["%s"] * len(ids))
        + ") AND (g.present=1 OR g.recorded>0 OR g.available=1)",
        [actor.user_id, *ids],
    )
    return dict(artwork={r["id"]: payload(r, state, "artwork", full=True) for r in rows})


@read
def species_artwork(actor, build, state, raw):
    from .catalog_read_queries import species_artwork_records

    return dict(artwork=species_artwork_records(raw))
