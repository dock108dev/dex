"""Exact counts and page selection over compact records before metadata expansion."""

from . import store


def select(build, filters, *, printing=False):
    if not any(filters.get(f) for f in ("q", "species", "set", "language", "edition", "finish", "variant")):
        return unfiltered(build, filters, printing=printing)
    if filters.get("q", "").strip() and not any(
        filters.get(f) for f in ("species", "set", "language", "edition", "finish", "variant")
    ):
        from .catalog_read_search import select_search

        return select_search(build, filters, printing=printing)
    variants = any(filters.get(f) for f in ("edition", "finish", "variant"))
    grouped = not printing and not variants
    table = "cr_groups" if grouped else "cr_match"
    index = "cr_public_order_set" if grouped else "sqlite_autoindex_cr_match_1"
    if variants:
        field = next(f for f in ("edition", "finish", "variant") if filters.get(f))
        index = "cr_match_" + field
    conditions, params = ["m.build=%s", "m.scope IN ('public','shared')"], [build]
    for field in ("species", "set", "language", "edition", "finish", "variant"):
        if filters.get(field):
            column = "set_id" if field == "set" else field
            conditions.append(f"m.{column}=%s")
            params.append(filters[field])
    tokens = filters.get("q", "").casefold().split()
    grams = sorted(
        {token[i : i + min(3, len(token))] for token in tokens for i in range(max(1, len(token) - 2))}
    )
    if grams and not variants:
        stride = store.rows("SELECT stride FROM catalog_read_builds WHERE id=%s", [build])[0]["stride"]
        conditions.append(
            "+m.rank_set IN (SELECT (rowid-%s)/%s FROM cr_gram_index WHERE cr_gram_index MATCH %s)"
        )
        params.extend(
            [
                build,
                stride,
                f"{build} AND spublic AND " + " AND ".join("g" + gram.encode().hex() for gram in grams),
            ]
        )
    if tokens:
        residual = " AND ".join("instr(m.search,%s)>0" for _ in tokens)
        params.extend(tokens)
        if grouped:
            residual = (
                "("
                + residual
                + " OR m.rank_set IN (SELECT rank_set FROM cr_match WHERE build=%s AND scope IN ('public','shared') AND "
                + " AND ".join("instr(search,%s)>0" for _ in tokens)
                + "))"
            )
            params.extend([build, *tokens])
        conditions.append(residual)
    page, size = filters["page"], filters["page_size"]
    sort = "rank_" + filters["sort"]
    columns = "m.rank_set" + ((",m.id" + (",m." + sort if sort != "rank_set" else "")) if printing else "")
    distinct = "DISTINCT " if variants and not printing else ""
    matched = f"SELECT {distinct}{columns} FROM {table} m INDEXED BY {index} WHERE " + " AND ".join(
        conditions
    )
    if printing:
        selected = f"SELECT * FROM matching ORDER BY {sort},id LIMIT %s OFFSET %s"
        selected_params = [size, offset(page, size)]
        metadata = "cr_children"
        join = "g.id=page.id"
        index = ""
    elif sort == "rank_set":
        selected = "SELECT rank_set FROM matching ORDER BY rank_set LIMIT %s OFFSET %s"
        selected_params = [size, offset(page, size)]
        metadata = "cr_groups"
        join = "g.rank_set=page.rank_set"
        index = " INDEXED BY cr_public_order_set"
    else:
        selected = f"SELECT g.id,g.{sort} FROM cr_groups g INDEXED BY cr_public_order_{filters['sort']} WHERE g.build=%s AND g.scope IN ('public','shared') AND +g.rank_set IN (SELECT rank_set FROM matching) ORDER BY g.{sort},g.id LIMIT %s OFFSET %s"
        selected_params = [build, size, offset(page, size)]
        metadata = "cr_groups"
        join = "g.id=page.id"
        index = ""
    query = f"WITH matching AS MATERIALIZED ({matched}), page AS MATERIALIZED ({selected}), total AS (SELECT COUNT(*) AS n FROM matching) SELECT total.n,g.id,CASE WHEN g.bytes<=900 THEN g.payload END AS payload,g.sha FROM total LEFT JOIN page ON 1=1 LEFT JOIN {metadata} g{index} ON g.build=%s AND g.scope IN ('public','shared') AND {join} ORDER BY page.{sort},g.id"
    rows = store.rows(query, [*params, *selected_params, build])
    return rows[0]["n"], [r for r in rows if r["id"] is not None]


def unfiltered(build, filters, *, printing=False):
    table = "cr_match" if printing else "cr_groups"
    metadata = "cr_children" if printing else "cr_groups"
    index = "cr_public_match" if printing else "cr_public_order"
    total = store.rows(
        f"SELECT COUNT(*) AS n FROM {table} INDEXED BY {index}_set WHERE build=%s AND scope IN ('public','shared')",
        [build],
    )[0]["n"]
    rank = "rank_" + filters["sort"]
    # Keep the bounded page outermost: SQLite 3.45 otherwise expands metadata
    # before matching page IDs, turning each page into a catalog-wide nested loop.
    rows = store.rows(
        f"WITH page AS MATERIALIZED (SELECT id,{rank} FROM {table} INDEXED BY {index}_{filters['sort']} WHERE build=%s AND scope IN ('public','shared') ORDER BY {rank},id LIMIT %s OFFSET %s) SELECT g.id,CASE WHEN g.bytes<=900 THEN g.payload END AS payload,g.sha FROM page CROSS JOIN {metadata} g ON g.build=%s AND g.scope IN ('public','shared') AND g.id=page.id ORDER BY page.{rank},g.id",
        [build, filters["page_size"], offset(filters["page"], filters["page_size"]), build],
    )
    return total, rows


def offset(page, size):
    """Preserve V1's arbitrarily deep empty pages without overflowing SQLite integers."""
    return min((page - 1) * size, (1 << 63) - 1)
