"""Indexed gram intersection with compact residuals, counts and bounded expansion."""

from . import store
from .catalog_read_select import offset as page_offset


def select_search(build, filters, *, printing=False):
    tokens = filters["q"].casefold().split()
    grams = sorted(
        {token[i : i + min(3, len(token))] for token in tokens for i in range(max(1, len(token) - 2))}
    )
    stride = store.rows("SELECT stride FROM catalog_read_builds WHERE id=%s", [build])[0]["stride"]
    grams_match = f"{build} AND spublic AND " + " AND ".join("g" + gram.encode().hex() for gram in grams)
    positive = " AND ".join("p" + part.encode().hex() for part in tokens)
    match = grams_match + " NOT (" + positive + ")"
    fast_match = f"{build} AND spublic AND (" + positive + ")"
    common = " AND ".join("instr(r.search,%s)>0" for _ in tokens)
    child = " AND ".join("instr(c.search,%s)>0" for _ in tokens)
    rank_expr = "(cr_gram_index.rowid-%s)/%s"
    matched = f"SELECT {rank_expr} AS rank_set, ((cr_gram_index.rowid-%s) %% %s)/4 AS children FROM cr_gram_index WHERE cr_gram_index MATCH %s UNION ALL SELECT {rank_expr} AS rank_set, CASE WHEN {common} THEN r.public_children ELSE (SELECT COUNT(*) FROM cr_match c WHERE c.build=%s AND c.scope IN ('public','shared') AND c.rank_set={rank_expr} AND {child}) END AS children FROM cr_gram_index JOIN cr_gram_residual r ON r.doc_id=cr_gram_index.rowid WHERE cr_gram_index MATCH %s"
    params = [
        build,
        stride,
        build,
        stride,
        fast_match,
        build,
        stride,
        *tokens,
        build,
        build,
        stride,
        *tokens,
        match,
    ]
    rank = "rank_" + filters["sort"]
    size, offset = filters["page_size"], page_offset(filters["page"], filters["page_size"])
    match_params = list(params)
    if printing:
        if rank == "rank_set":
            candidates = "SELECT rank_set FROM matching WHERE children>0 ORDER BY rank_set LIMIT %s"
            candidate_params = [min(offset + size, (1 << 63) - 1)]
        else:
            candidates = f"SELECT rank_set FROM cr_groups INDEXED BY cr_public_order_{filters['sort']} WHERE build=%s AND scope IN ('public','shared') AND +rank_set IN (SELECT rank_set FROM matching WHERE children>0) ORDER BY {rank},id LIMIT %s"
            candidate_params = [build, min(offset + size, (1 << 63) - 1)]
        page = f"SELECT c.id,c.{rank} FROM cr_match c INDEXED BY cr_public_match_{filters['sort']} WHERE c.build=%s AND c.scope IN ('public','shared') AND c.rank_set IN ({candidates}) AND {child} ORDER BY c.{rank},c.id LIMIT %s OFFSET %s"
        params.extend([build, *candidate_params, *tokens, size, offset])
        total = "COALESCE(SUM(children),0)"
        table = "cr_children"
    else:
        if rank == "rank_set":
            page = "SELECT rank_set FROM matching WHERE children>0 ORDER BY rank_set LIMIT %s OFFSET %s"
            params.extend([size, offset])
        else:
            page = f"SELECT g.rank_set,g.{rank} FROM cr_groups g INDEXED BY cr_public_order_{filters['sort']} WHERE g.build=%s AND g.scope IN ('public','shared') AND +g.rank_set IN (SELECT rank_set FROM matching WHERE children>0) ORDER BY g.{rank},g.id LIMIT %s OFFSET %s"
            params.extend([build, size, offset])
        total = "COUNT(*)"
        table = "cr_groups"
    join = "g.id=page.id" if printing else "g.rank_set=page.rank_set"
    index = "" if printing else " INDEXED BY cr_public_order_set"
    query = f"WITH matching AS MATERIALIZED ({matched}), page AS MATERIALIZED ({page}), total AS (SELECT {total} AS n FROM matching WHERE children>0) SELECT total.n,g.id,CASE WHEN g.bytes<=900 THEN g.payload END AS payload,g.sha FROM total LEFT JOIN page ON 1=1 LEFT JOIN {table} g{index} ON g.build=%s AND g.scope IN ('public','shared') AND {join} ORDER BY page.{rank},g.id"
    if rank == "rank_set":
        # Count the complete positive posting list, but materialize only enough
        # positive candidates for this page. Residual matches remain exact.
        positive_query, residual_query = matched.split(" UNION ALL ", 1)
        positive_count = "COALESCE(SUM(((rowid-%s) %% %s)/4),0)" if printing else "COUNT(*)"
        count_params = [build, stride, fast_match] if printing else [fast_match]
        count_query = f"SELECT {positive_count} FROM cr_gram_index WHERE cr_gram_index MATCH %s"
        total_query = f"SELECT ({count_query})+(SELECT {total} FROM residual WHERE children>0) AS n"
        query = f"WITH residual AS MATERIALIZED ({residual_query}), matching AS MATERIALIZED (SELECT * FROM ({positive_query} ORDER BY rowid LIMIT %s) UNION ALL SELECT * FROM residual), page AS MATERIALIZED ({page}), total AS ({total_query}) SELECT total.n,g.id,CASE WHEN g.bytes<=900 THEN g.payload END AS payload,g.sha FROM total LEFT JOIN page ON 1=1 LEFT JOIN {table} g{index} ON g.build=%s AND g.scope IN ('public','shared') AND {join} ORDER BY page.{rank},g.id"
        params = [
            *match_params[5:],
            *match_params[:5],
            min(offset + size, (1 << 63) - 1),
            *params[len(match_params) :],
            *count_params,
        ]
    else:
        # Ordered compact common text can establish positive page membership
        # directly. Only same-child residuals need the full matching rank list.
        _, residual_query = matched.split(" UNION ALL ", 1)
        common_group = " AND ".join("instr(g.search,%s)>0" for _ in tokens)
        candidates = f"SELECT g.rank_set,g.{rank} FROM cr_groups g INDEXED BY cr_public_order_{filters['sort']} WHERE g.build=%s AND g.scope IN ('public','shared') AND (({common_group}) OR g.rank_set IN (SELECT rank_set FROM residual WHERE children>0)) ORDER BY g.{rank},g.id LIMIT %s OFFSET %s"
        candidate_params = [
            build,
            *tokens,
            min(offset + size, (1 << 63) - 1) if printing else size,
            0 if printing else offset,
        ]
        positive_count = "COALESCE(SUM(((rowid-%s) %% %s)/4),0)" if printing else "COUNT(*)"
        count_params = [build, stride, fast_match] if printing else [fast_match]
        total_query = f"SELECT (SELECT {positive_count} FROM cr_gram_index WHERE cr_gram_index MATCH %s)+(SELECT {total} FROM residual WHERE children>0) AS n"
        if printing:
            page = f"SELECT c.id,c.{rank} FROM candidates CROSS JOIN cr_match c WHERE c.build=%s AND c.scope IN ('public','shared') AND c.rank_set=candidates.rank_set AND {child} ORDER BY c.{rank},c.id LIMIT %s OFFSET %s"
            page_params = [build, *tokens, size, offset]
        else:
            page, page_params = "SELECT * FROM candidates", []
        query = f"WITH residual AS MATERIALIZED ({residual_query}), candidates AS MATERIALIZED ({candidates}), page AS MATERIALIZED ({page}), total AS ({total_query}) SELECT total.n,g.id,CASE WHEN g.bytes<=900 THEN g.payload END AS payload,g.sha FROM total LEFT JOIN page ON 1=1 LEFT JOIN {table} g{index} ON g.build=%s AND g.scope IN ('public','shared') AND {join} ORDER BY page.{rank},g.id"
        params = [*match_params[5:], *candidate_params, *page_params, *count_params]
    rows = store.rows(query, [*params, build])
    return rows[0]["n"], [r for r in rows if r["id"] is not None]
