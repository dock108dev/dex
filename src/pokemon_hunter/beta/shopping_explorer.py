"""Indexed explorer selection; page complete group summaries before decoding."""

import re

from django.db import connection

from . import account_read_build as builds
from . import (
    canonical_species,
    image_bindings,
    image_mappings,
    shopping_context,
    store,
)
from . import (
    discovery_catalog as dc,
)
from .account_read_select import search_ranks


def search(read, raw, context, offset):
    actor, build = read.actor, read.build
    sets = store.rows(
        "SELECT o.value AS id,o.label AS name FROM cr_options o WHERE o.build=%s AND o.scope IN ('retained','shared') AND o.field='set' AND EXISTS(SELECT 1 FROM cr_postings p JOIN ar_membership a ON a.user_id=%s AND a.id=p.group_id AND a.available=1 WHERE p.build=o.build AND p.scope IN ('retained','shared') AND p.field='set' AND p.value=o.value)",
        [build, actor.user_id],
    )
    sets.sort(key=lambda row: (row["name"].casefold(), row["id"]))
    query, fractions = re.subn(r"(?<!\w)(\d{1,4})\s*/\s*\d{1,4}(?!\w)", r"\1", raw.get("q", ""))
    words, inferred_set = dc.query_parts(query, sets)
    selected_set = raw.get("set_id") or inferred_set
    if selected_set:
        selected = [s for s in sets if selected_set in {s["id"], s["name"]}]
        if not selected:
            raise ValueError("Choose a supported catalog set")
        selected_set = selected[0]["id"]
    missing = raw.get("intent") == "missing" or context["kind"] in {"missing", "goal"}
    goal = context["query"].get("goal")
    scope = raw.get("scope", "kanto" if missing and not goal else "all")
    where, args = ["m.user_id=%s", "m.available=1"], [actor.user_id]
    if selected_set:
        where.append("m.set_id=%s")
        args.append(selected_set)
    if context.get("species"):
        where.append("m.species=%s")
        args.append(context["species"])
    if context.get("group"):
        where.append("m.id=%s")
        args.append(context["group"])
    if scope in {"kanto", "johto"}:
        where.append("m.species BETWEEN %s AND %s")
        args.extend((1, 151) if scope == "kanto" else (152, 251))
    residual, residual_args = [], []
    numbers = [token for token in words.split() if token.isdecimal()]
    for number in numbers:
        where.append(
            "m.id IN (SELECT group_id FROM cr_postings WHERE build=%s AND scope IN ('retained','shared') AND field='shopping_number' AND value=%s)"
        )
        args.extend([build, number])
    if words and not numbers:
        ranks, values = search_ranks(build, read.state["catalog_stride"], words, "retained")
        where.append("m.rank_set IN (" + ranks + ")")
        args.extend(values)
    if words:
        # Same Unicode/punctuation and whole-number semantics as the legacy
        # explorer. The FTS superset is intersected before these residuals run.
        connection.connection.create_function("dex_shopping_normal", 1, dc._normal, deterministic=True)
        hay = "dex_shopping_normal(json_extract(g.payload,'$.name') || ' ' || json_extract(g.payload,'$.collector_number'))"
        for token in words.split():
            residual.append(
                "instr(' ' || " + hay + " || ' ',%s)>0" if token.isdecimal() else "instr(" + hay + ",%s)>0"
            )
            residual_args.append(" " + token + " " if token.isdecimal() else token)
    child, child_args = (
        ["c.build=%s", "c.scope IN ('retained','shared')", "c.group_id=m.id", "c.published=1"],
        [build],
    )
    if context.get("child"):
        child.append("c.id=%s")
        child_args.append(context["child"])
    if goal:
        child.append(
            "EXISTS(SELECT 1 FROM ar_goal_printings p JOIN ar_goal_items i ON i.user_id=p.user_id AND i.id=p.item_id WHERE p.user_id=%s AND p.goal_id=%s AND p.printing_id=c.id AND i.status<>'owned')"
        )
        child_args.extend([actor.user_id, goal])
    elif missing and raw.get("missing_basis", "species") == "species":
        where.append(
            "m.species IN (SELECT CAST(s.id AS INTEGER) FROM ar_species s WHERE s.user_id=%s AND CAST(s.id AS INTEGER) BETWEEN 1 AND 151 AND json_extract(s.summary,'$.current_present')=0)"
        )
        args.append(actor.user_id)
        child.append(
            "EXISTS(SELECT 1 FROM ar_scope_catalog p INDEXED BY sqlite_autoindex_ar_scope_catalog_1 WHERE p.build=c.build AND p.id=c.id AND p.species=m.species)"
        )
    elif missing:
        child.append(
            "NOT EXISTS(SELECT 1 FROM ar_copies p WHERE p.user_id=%s AND p.printing_id=c.id AND p.current=1 AND p.exact=1)"
        )
        child_args.append(actor.user_id)
    # Available numbered species groups already establish a published Pokémon
    # child of that species. Current species presence applies to the whole group.
    if goal or (missing and raw.get("missing_basis", "species") != "species") or context.get("child"):
        where.append(
            "EXISTS(SELECT 1 FROM cr_children c INDEXED BY cr_child_group WHERE " + " AND ".join(child) + ")"
        )
        args.extend(child_args)
    if scope in {"rares", "bulk"}:
        where.append(
            "EXISTS(SELECT 1 FROM cr_children c JOIN ar_catalog p ON p.build=c.build AND p.id=c.id WHERE c.build=%s AND c.scope IN ('retained','shared') AND c.group_id=m.id AND "
            + (
                "instr(lower(json_extract(p.payload,'$.attributes.rarity')),'rare')>0"
                if scope == "rares"
                else "lower(json_extract(p.payload,'$.attributes.rarity')) IN ('common','uncommon')"
            )
            + ")"
        )
        args.append(build)
    index = (
        "sqlite_autoindex_ar_membership_1"
        if numbers or context.get("group")
        else "ar_membership_available_set"
    )
    matched = (
        f"SELECT m.id,m.rank_set,m.species FROM ar_membership m INDEXED BY {index} WHERE "
        + " AND ".join(where)
    )
    if residual:
        matched = (
            "WITH narrowed AS MATERIALIZED ("
            + matched
            + ") SELECT m.id,m.rank_set,m.species FROM narrowed m JOIN ar_groups g ON g.user_id=%s AND g.id=m.id WHERE "
            + " AND ".join(residual)
        )
        args.extend([actor.user_id, *residual_args])
    registry = canonical_species.registry()
    broad = [n for n, s in registry.items() if n <= 251 and words and dc._normal(s["name"]) == words]
    mode = (
        "species"
        if broad and not selected_set and not context.get("species") and not context.get("group")
        else "cards"
    )
    variants = []
    if mode == "species":
        rows = []
        for number in broad:
            current = read.species(number)
            if missing and not goal and (number > 151 or current["present"]):
                continue
            count = store.rows(
                "SELECT COUNT(*) AS n FROM (" + matched + ") WHERE species=%s", [*args, number]
            )[0]["n"]
            if (
                goal
                and not count
                and not store.rows(
                    "SELECT 1 FROM ar_goal_items WHERE user_id=%s AND goal_id=%s AND species=%s AND status<>'owned' LIMIT 1",
                    [actor.user_id, goal, number],
                )
            ):
                continue
            if scope == "kanto" and number > 151 or scope == "johto" and number <= 151:
                continue
            rows.append(
                dict(
                    dex=number,
                    name=registry[number]["name"],
                    current_present=current["present"],
                    matching_cards=count,
                    species_artwork=image_mappings.species_artwork(number)
                    if image_bindings.enabled()
                    else None,
                )
            )
        total = len(rows)
    else:
        found = store.rows(
            "WITH matching AS MATERIALIZED ("
            + matched
            + "), page AS (SELECT id,rank_set FROM matching ORDER BY rank_set,id LIMIT 40 OFFSET %s) SELECT t.n,g.id,g.payload,g.sha,a.payload AS art,a.sha AS art_sha FROM (SELECT COUNT(*) AS n FROM matching) t LEFT JOIN page ON 1 LEFT JOIN ar_groups g ON g.user_id=%s AND g.id=page.id LEFT JOIN ar_artwork a ON a.user_id=g.user_id AND a.id=g.id ORDER BY page.rank_set,page.id",
            [*args, offset, actor.user_id],
        )
        total = found[0]["n"]
        rows = []
        for row in found:
            if row["id"] is None:
                continue
            value = builds.decode(row)
            if image_bindings.enabled() and row["art"] is not None:
                value["reference_image"] = builds.decode(dict(payload=row["art"], sha=row["art_sha"]))
            value["selected_child"] = context.get("child") if value["id"] == context.get("group") else None
            rows.append(value)
    if context.get("group"):
        variants = read.variants(context["group"])
    shopping_context.finish(actor, context)
    return dict(
        mode=mode,
        results=rows,
        total=total,
        offset=offset,
        has_more=mode == "cards" and offset + 40 < total,
        sets=sets,
        applied_set_id=selected_set,
        variants=variants,
        context=context,
        generation=read.state["generation"],
        number_note="Matches use the number before /. Confirm full numbering and set in each result."
        if fractions
        else "",
    )
