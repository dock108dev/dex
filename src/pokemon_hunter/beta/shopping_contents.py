"""Temporary seller-evidence groups; no ownership, acquisition or value authority."""

import hashlib
import re

from . import hunter_lot_parser, shopping, store
from .account_read_build import encode
from .account_read_select import search_ranks


def project(value, entries, *, summary=None):
    source = value.pop("_contents_source", {"title": value["title"]})
    kind = value.pop("_contents_kind", "summary")
    # Parser strips markup; official detail stays a separate provenance field.
    raw = {
        k: source[k]
        for k in ("title", "shortDescription", "condition", "itemId", "buyingOptions", "localizedAspects")
        if k in source
    }
    raw.setdefault("title", value["title"])
    try:
        parsed = hunter_lot_parser.parse(
            summary or raw,
            entries,
            detail=source if kind == "official_detail" else None,
            complete_candidates=True,
        )
    except ValueError as exc:
        return [
            dict(
                key="unresolved",
                name="Unresolved contents",
                candidates=[],
                quantity=None,
                reasons=[str(exc)],
                evidence=[],
            )
        ]
    value["seller_contents"] = parsed
    if (
        parsed["unknown_remainder"] == 0
        and all(p["included_quantity"] and not p["reasons"] for p in parsed["proposals"])
        and len({p["clues"].get("finish") for p in parsed["proposals"] if p["included_quantity"]}) > 1
    ):
        # The per-card parser has accounted for the mixed-finish lot. A title
        # describing that union is not a contradiction on every individual card.
        value["clues"] = dict(
            value.get("clues", {}),
            conflicts=[
                issue
                for issue in value.get("clues", {}).get("conflicts", [])
                if issue != "Conflicting seller finish claims"
            ],
        )
    totals = set(parsed["seller_stated_totals"])
    # A null adapter total may itself mean conflicting structured claims. Do
    # not replace that conflict with the one number repeated in the title.
    totals.update(
        int(a["value"])
        for a in value.get("aspects", [])
        if a["name"].casefold() in {"number of cards", "lot size"}
        and re.fullmatch(r"[1-9][0-9]{0,5}", a["value"])
        and int(a["value"]) <= 100000
    )

    if value.get("seller_lot_size") is not None:
        totals.add(value["seller_lot_size"])
    if totals:
        value["seller_lot_size"] = next(iter(totals)) if len(totals) == 1 else None
        value["unknown_contents"] = value["seller_lot_size"]
        if len(totals) == 1:
            known = sum(p.get("quantity", 0) for p in value.get("proposals", []))
            value["unknown_contents"] = (
                value["seller_lot_size"] - known if value["seller_lot_size"] >= known else None
            )
    result = []
    rows = []
    for claim in parsed["proposals"]:
        families = {}
        for printing in claim["candidates"]:
            families.setdefault(printing["name"], []).append(printing)
        if len(families) <= 1:
            rows.append(claim)
        else:
            for name, family in families.items():
                key = hashlib.sha256((claim["proposal_id"] + "\0" + name).encode()).hexdigest()[:24]
                rows.append(
                    dict(claim, proposal_id=key, name=name.casefold(), candidates=family, quantity=None)
                )
    folded = set()
    for row in rows:
        # A generic repeated title mention is relevance, not another occurrence.
        if row["quantity"] is None and all(m["source_field"].endswith("title") for m in row["mentions"]):
            related = [
                other
                for other in rows
                if other is not row
                and not all(m["source_field"].endswith("title") for m in other["mentions"])
                and other["name"]
                and other["name"] == row["name"]
            ]
            if related:
                for other in related:
                    other["mentions"].extend(row["mentions"])
                folded.add(row["proposal_id"])
    for row in rows:
        if any(
            re.search(
                r"\b(?:not included|does not include|may (?:include|contain)|might (?:include|contain)|not guaranteed|example only|proxy|custom|replica)\b",
                m["text"],
                re.I,
            )
            for m in row["mentions"]
        ):
            row["quantity"] = None
            row["reasons"].append("Seller wording does not establish an included ordinary card")
        if row["proposal_id"] in folded:
            continue
        result.append(
            dict(
                key=row["proposal_id"],
                name=row["name"] or "Unresolved card group",
                candidates=[
                    {
                        k: p.get(k)
                        for k in (
                            "id",
                            "name",
                            "set_name",
                            "collector_number",
                            "language",
                            "edition",
                            "finish",
                            "variant",
                        )
                    }
                    for p in row["candidates"]
                ],
                quantity=row["quantity"],
                reasons=[
                    *row["reasons"],
                    *(["Conflicting seller-stated card counts"] if len(totals) > 1 else []),
                    *value.get("clues", {}).get("conflicts", []),
                ],
                evidence=[
                    dict(
                        m,
                        provenance=(
                            "Official detail · seller claim"
                            if kind == "official_detail" or m["source_field"].startswith("official_")
                            else "Official summary · seller claim"
                        ),
                    )
                    for m in row["mentions"] + row.get("scope_mentions", [])
                ],
            )
        )
    # Contradictory repeated quantities for the same family describe one
    # unresolved claim, not two occurrences to add together.
    families = {}
    for group in result:
        key = frozenset(p["id"] for p in group["candidates"])
        if key in families:
            previous = families[key]
            previous["quantity"] = None
            previous["evidence"].extend(group["evidence"])
            previous["reasons"] = list(
                dict.fromkeys(
                    [*previous["reasons"], *group["reasons"], "Repeated seller quantities need correction"]
                )
            )
        else:
            families[key] = group
    result = list(families.values())
    for index, row in enumerate(parsed["unresolved_contents"]):
        result.append(
            dict(
                key=f"unknown-{index}",
                name="Unrecognized contents",
                candidates=[],
                quantity=row["quantity"],
                reasons=[row["reason"]],
                evidence=[
                    dict(
                        text=row["text"],
                        source_field=row["source_field"],
                        provenance=(
                            "Official detail · seller claim"
                            if kind == "official_detail" or row["source_field"].startswith("official_")
                            else "Official summary · seller claim"
                        ),
                    )
                ],
            )
        )
    for i, claim in enumerate(parsed.get("excluded_claims", [])):
        result.append(
            dict(
                key=f"excluded-{i}",
                name="Excluded seller claim",
                candidates=[],
                quantity=None,
                reasons=[claim["reason"] + "; contents valuation unavailable for this claim"],
                evidence=[dict(m, provenance="Seller claim") for m in claim["mentions"]],
            )
        )
    return result or [
        dict(
            key="unresolved",
            name="Unresolved contents",
            candidates=[],
            quantity=None,
            reasons=["No supported card identity in the supplied text"],
            evidence=[],
        )
    ]


def check_authored(value, allowed):
    fields = value.get("authored_fields", [])
    if (
        not isinstance(fields, list)
        or len(fields) > len(allowed)
        or not all(isinstance(k, str) and k in allowed and k in value for k in fields)
    ):
        raise ValueError("Choose bounded authored review fields")


def validate(contents):
    # Display annotations are never consumed by fit, identity admission or maths.
    # Even a caller-authored annotation is explicitly unverified.
    if not isinstance(contents, list) or len(contents) > 200 or len(encode(contents).encode()) > 100000:
        raise ValueError("Contents notes exceed the temporary review limit")
    for row in contents:
        shopping.fields(
            row,
            {"key", "name", "candidates", "quantity", "reasons", "evidence"},
            {"key", "name", "candidates", "quantity", "reasons", "evidence"},
        )
        if not all(isinstance(row[k], str) and len(row[k]) <= 2048 for k in ("key", "name")):
            raise ValueError("Use bounded contents notes")
        if row["quantity"] is not None and (
            type(row["quantity"]) is not int or not 0 <= row["quantity"] <= 100000
        ):
            raise ValueError("Use whole contents quantities")
        if not isinstance(row["candidates"], list) or not all(
            isinstance(p, dict)
            and isinstance(p.get("id"), str)
            and set(p)
            <= {"id", "name", "set_name", "collector_number", "language", "edition", "finish", "variant"}
            and all(v is None or isinstance(v, str) for v in p.values())
            for p in row["candidates"]
        ):
            raise ValueError("Use supported contents alternatives")
        if not isinstance(row["reasons"], list) or not all(isinstance(r, str) for r in row["reasons"]):
            raise ValueError("Use text contents reasons")
        if not isinstance(row["evidence"], list) or not all(
            isinstance(e, dict)
            and all(isinstance(e.get(k), str) for k in ("text", "source_field", "provenance"))
            for e in row["evidence"]
        ):
            raise ValueError("Use bounded seller evidence")


def search(read, query):
    """Use prepared substring postings, then count/page before identity decoding."""
    from .account_read_build import decode

    where = [
        "c.build=%s",
        "c.published=1",
        "c.pokemon=1",
        "(c.standard=1 OR c.id IN (SELECT printing_id FROM ar_goal_printings WHERE user_id=%s))",
    ]
    args = [read.build, read.actor.user_id]
    if query.strip():
        ranks, params = search_ranks(read.build, read.state["catalog_stride"], query, "retained")
        where.append("(c.rank_set IS NULL OR c.rank_set IN (" + ranks + "))")
        args.extend(params)
    for word in query.casefold().split():
        where.append("instr(c.search,%s)>0")
        args.append(word)
    selected = " FROM ar_shopping_picker c WHERE " + " AND ".join(where)
    # The extra ID tells us whether the first page already establishes the
    # exact total. Expand metadata for at most 40 identities.
    rows = store.rows(
        "WITH candidates AS MATERIALIZED (SELECT c.id,c.ordinal"
        + selected
        + " ORDER BY c.ordinal LIMIT 41), page AS (SELECT id,ordinal FROM candidates ORDER BY ordinal LIMIT 40) "
        "SELECT (SELECT COUNT(*) FROM candidates) AS seen,a.id,a.payload,a.sha FROM page p "
        "JOIN ar_catalog a ON a.build=%s AND a.id=p.id ORDER BY p.ordinal",
        [*args, read.build],
    )
    total = rows[0]["seen"] if rows else 0
    if total > 40:
        total = store.rows("SELECT COUNT(*) AS n" + selected, args)[0]["n"]
    entries = [decode(row) for row in rows]
    read.metadata.update({p["id"]: p for p in entries})
    return entries, total
