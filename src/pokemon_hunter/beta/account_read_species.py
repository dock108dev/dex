"""Retained three-valued species scope facts; SQL selects before bounded decoding."""

from django.db import connection

from . import public_catalog, species_scope, store

FIELDS = ("set_id", "set_name", "era", "type", "rarity", "finish", "card", "start", "end")


def values(row):
    release = row.get("release") or {}
    return [
        row.get("set"),
        row.get("set_name"),
        row.get("era"),
        row.get("type"),
        row.get("rarity"),
        row.get("finish"),
        (row.get("card") or "").casefold() or None,
        release.get("start"),
        release.get("end"),
    ]


def prepare(snapshot, rows, pokemon):
    dates = species_scope.release_dates()
    allowed = {entry["id"] for entry in rows if entry["game_id"] in pokemon}
    cards = [r for r in public_catalog.cards(rows) if r["id"] in allowed and r["supertype"] == "Pokémon"]
    languages = {r["id"]: r["language"] for r in rows}
    indexed = {r["id"]: species_scope.metadata({**r, "language": languages[r["id"]]}, dates) for r in cards}
    candidates = {}
    for card in cards:
        fact = {k: indexed[card["id"]][k] for k in ("set", "era", "release")}
        candidates.setdefault(card["set_name"], {})[(card["set_id"], languages[card["id"]])] = fact
    facts = {name: next(iter(items.values())) for name, items in candidates.items() if len(items) == 1}
    if not store.rows("SELECT 1 FROM ar_scope_catalog WHERE build=%s LIMIT 1", [snapshot.build]):
        with connection.cursor() as cursor:
            cursor.executemany(
                "INSERT INTO ar_scope_catalog VALUES(" + ",".join(["%s"] * 12) + ")",
                [(snapshot.build, c["id"], c["pokemon_dex"], *values(indexed[c["id"]])) for c in cards],
            )
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO ar_scope_date_counts SELECT build,row_number() OVER (),species,finish,start,end,COUNT(*) FROM ar_scope_catalog WHERE build=%s GROUP BY build,species,finish,start,end",
                [snapshot.build],
            )
        for field in ("set", "era", "type", "rarity", "finish", "year"):
            sql, args = option_source(snapshot.build, field)
            options = store.rows(sql, args)
            with connection.cursor() as cursor:
                cursor.executemany(
                    "INSERT INTO ar_scope_options VALUES(%s,%s,%s,%s,%s)",
                    [(snapshot.build, field, i, r["value"], r["label"]) for i, r in enumerate(options)],
                )
    return indexed, facts


def persist(actor, cards, by_literal, literal, indexed, facts, only=None):
    from . import collection

    if only is not None:
        collection.execute(
            "DELETE FROM ar_scope_owned WHERE user_id=%s AND component IN ("
            + ",".join(["%s"] * len(only))
            + ")",
            [actor.user_id, *sorted(only)],
        )
    rows = []
    for card in cards:
        component = by_literal.get(literal(card), "literal:" + literal(card))
        if not card["present"] or only is not None and component not in only:
            continue
        evidence = (
            species_scope.owned_evidence(card, indexed, facts)
            if card["identity_status"] != "conflict"
            else [{}]
        )
        rows.extend(
            (actor.user_id, card["id"] + ":" + str(i), component, card["pokemon_dex"], *values(row))
            for i, row in enumerate(evidence)
        )
    with connection.cursor() as cursor:
        cursor.executemany(
            "INSERT OR REPLACE INTO ar_scope_owned VALUES(" + ",".join(["%s"] * 13) + ")", rows
        )


def expression(selected):
    """SQL NULL retains the policy's insufficient-evidence state."""
    clauses, params = [], []
    for field in ("set", "era", "type", "rarity", "finish"):
        wanted = species_scope.values(selected.get(field, ""))
        if not wanted:
            continue
        column = "set_id" if field == "set" else field
        marks = ",".join(["%s"] * len(wanted))
        match = f"{column} IN ({marks})"
        args = wanted
        if field == "set":
            match += f" OR set_name IN ({marks})"
            args = wanted + wanted
        clauses.append(f"CASE WHEN {column} IS NULL OR {column}='Unknown' THEN NULL ELSE ({match}) END")
        params.extend(args)
    if selected.get("card"):
        clauses.append("instr(card,%s)>0")
        params.append(selected["card"].casefold())
    periods, years = (
        species_scope.values(selected.get("released", "")),
        species_scope.values(selected.get("year", "")),
    )
    lower, upper = selected.get("date_from"), selected.get("date_to")
    if periods or years or lower or upper:
        ranges = [("0001-01-01", "9999-12-31")]
        for options in (
            (
                [("0001-01-01", "1999-12-31") for p in periods if p == "pre-2000"]
                + [("2000-01-01", "9999-12-31") for p in periods if p == "2000-onward"]
            )
            if periods
            else ranges,
            [(y + "-01-01", y + "-12-31") for y in years] if years else ranges,
            [(lower or "0001-01-01", upper or "9999-12-31")],
        ):
            ranges = [(max(a, c), min(b, d)) for a, b in ranges for c, d in options if max(a, c) <= min(b, d)]
        # Merge adjacent ranges just as the authoritative date policy does.
        from datetime import date

        merged = []
        for a, b in sorted(ranges):
            if (
                merged
                and date.fromisoformat(a).toordinal() <= date.fromisoformat(merged[-1][1]).toordinal() + 1
            ):
                merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
            else:
                merged.append((a, b))
        complete = " OR ".join("(start>=%s AND end<=%s)" for _ in merged) or "0"
        overlap = " OR ".join("(end>=%s AND start<=%s)" for _ in merged) or "0"
        unknown = "1" if "Unknown" in periods and not (years or lower or upper) else "NULL"
        clauses.append(
            f"CASE WHEN start IS NULL THEN {unknown} WHEN {complete} THEN 1 WHEN {overlap} THEN NULL ELSE 0 END"
        )
        params.extend(x for pair in merged for x in pair)
        params.extend(x for pair in merged for x in pair)
    return " AND ".join("(" + c + ")" for c in clauses) or "1", params


def option_source(build, field):
    columns = dict(
        set="set_id",
        era="era",
        type="type",
        rarity="rarity",
        finish="COALESCE(finish,'Unknown')",
        year="substr(start,1,4)",
    )
    if field not in columns:
        raise ValueError("Choose a supported species option field")
    column = columns[field]
    label = "set_name" if field == "set" else column
    return (
        f"SELECT {column} AS value,MIN({label}) AS label FROM ar_scope_catalog WHERE build=%s AND {column} IS NOT NULL GROUP BY {column} ORDER BY lower(MIN({label})),{column}",
        [build],
    )


def option_query(build, field):
    if field not in {"set", "era", "type", "rarity", "finish", "year"}:
        raise ValueError("Choose a supported species option field")
    return "SELECT value,label FROM ar_scope_options WHERE build=%s AND field=%s ORDER BY rank", [
        build,
        field,
    ]


def candidates(build, selected):
    """Set selectors prune only definitely excluded records; unknowns remain."""
    wanted = species_scope.values(selected.get("set", ""))
    if not wanted:
        return "", []
    marks = ",".join(["%s"] * len(wanted))
    return (
        f" AND id IN (SELECT id FROM ar_scope_catalog INDEXED BY ar_scope_set_names WHERE build=%s AND set_name IN ({marks}) UNION SELECT id FROM ar_scope_catalog INDEXED BY ar_scope_set_options WHERE build=%s AND set_id IN ({marks},'Unknown') UNION SELECT id FROM ar_scope_catalog INDEXED BY ar_scope_set_options WHERE build=%s AND set_id IS NULL)",
        [build, *wanted, build, *wanted, build],
    )
