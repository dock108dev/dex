"""Bounded, revision-bound reads. All catalog selection happens in SQLite."""

import json
from functools import wraps
from urllib.parse import urlencode

from django.db import DatabaseError
from django.http import Http404

from . import card_groups, store
from .catalog_read_build import Unavailable, active, digest, revision
from .catalog_read_select import offset
from .catalog_read_snapshot import snapshot
from .collection import Conflict

BASE = "/api/v2/public/"


def read(fn):
    @wraps(fn)
    def wrapped(raw=None, **kwargs):
        raw = dict(raw or {})
        token = raw.pop("catalog_revision", None)
        if token is not None and (not isinstance(token, str) or len(token) > 160):
            raise ValueError("Choose a catalog revision")
        try:
            with snapshot():
                manifest, current = active(token)
                result = fn(manifest["id"], current, raw, **kwargs)
            # Fresh transaction observes authority changes during WAL snapshot reads.
            if revision() != manifest["revision"]:
                raise Conflict("Catalog changed during read")
            result.update(read_version=2, catalog_revision=current, public=True)
            return result
        except (DatabaseError, IndexError, KeyError, json.JSONDecodeError) as exc:
            raise Unavailable("catalog_integrity") from exc

    return wrapped


def url(path, token, **params):
    return BASE + path + "?" + urlencode(dict(catalog_revision=token, **params))


def paging(raw, allowed=()):
    if set(raw) - {"page", "page_size", *allowed}:
        raise ValueError("Unsupported selector")
    if any(not isinstance(v, str) or len(v) > 160 for v in raw.values()):
        raise ValueError("Choose short text selectors")
    return (
        card_groups._integer(raw.get("page", "1"), "page", 1),
        card_groups._integer(raw.get("page_size", "40"), "page size", 1, 100),
    )


def payload(row, token, kind, key=None, *, full=False):
    if row["payload"] is None:
        return dict(
            id=row["id"] if len(row["id"]) <= 160 else None,
            oversized=True,
            url=url(f"resources/{kind}/sha-{row['sha']}/", token),
        )
    if digest(row["payload"]) != row["sha"]:
        raise Unavailable("corrupt_row")
    if not full and len(row["payload"].encode()) > 900:
        return dict(
            id=row["id"] if len(row["id"]) <= 160 else None,
            oversized=True,
            url=url(f"resources/{kind}/sha-{row['sha']}/", token),
        )
    from .read_diagnostics import decoded, phase

    decoded()
    with phase("composition_ms"):
        return json.loads(row["payload"])


@read
def groups(build, token, raw, *, dex=None):
    if dex is not None:
        if not 1 <= dex <= 251:
            raise Http404
        if "species" in raw or "scope" in raw:
            raise ValueError("Choose a supported species")
        raw["species"] = str(dex)
    filters = card_groups._filters(raw, {"public": True})
    from .catalog_read_select import select

    total, rows = select(build, filters)
    page, size = filters["page"], filters["page_size"]
    unresolved = store.rows(
        "SELECT COUNT(*) AS n FROM cr_evidence WHERE build=%s AND scope IN ('public','shared')", [build]
    )[0]["n"]
    summaries = [payload(r, token, "group") for r in rows]
    matching = {field: raw[field] for field in ("q", "edition", "finish", "variant") if raw.get(field)}
    if matching:
        for item in summaries:
            item["matching_variants"] = {
                "url": url(f"card-groups/{item['id']}/variants/", token),
                "selectors": "matching_filters",
            }
    return dict(
        groups=summaries,
        matching_filters=matching,
        total=total,
        page=page,
        page_size=size,
        pages=(total + size - 1) // size,
        scope="catalog",
        unresolved=dict(total=unresolved, url=url("evidence/", token)),
    )


def group_row(build, key):
    rows = store.rows(
        "SELECT id,CASE WHEN bytes<=900 THEN payload END AS payload,sha FROM cr_groups WHERE build=%s AND scope IN ('public','shared') AND id=%s",
        [build, key],
    )
    if not rows:
        raise Http404("Card group unavailable")
    return rows[0]


@read
def detail(build, token, raw, *, key):
    if set(raw) - {"child"} or any(not isinstance(v, str) or len(v) > 160 for v in raw.values()):
        raise ValueError("Choose a supported child")
    group = group_row(build, key)
    selected = None
    if "child" in raw:
        found = store.rows(
            "SELECT id,CASE WHEN bytes<=900 THEN payload END AS payload,sha FROM cr_children WHERE build=%s AND scope IN ('public','shared') AND group_id=%s AND id=%s",
            [build, key, raw["child"]],
        )
        if not found:
            raise Http404("Selected child does not belong to this accessible group")
        selected = payload(found[0], token, "printing")
    total = store.rows(
        "SELECT COUNT(*) AS n FROM cr_children WHERE build=%s AND scope IN ('public','shared') AND group_id=%s",
        [build, key],
    )[0]["n"]
    return dict(
        group=payload(group, token, "group"),
        selected_child=selected,
        variants=dict(total=total, url=url(f"card-groups/{key}/variants/", token)),
    )


@read
def variants(build, token, raw, *, key):
    page, size = paging(raw, ("q", "edition", "finish", "variant"))
    group_row(build, key)
    where, params = ["build=%s", "scope IN ('public','shared')", "group_id=%s"], [build, key]
    for field in ("edition", "finish", "variant"):
        if raw.get(field):
            where.append(f"{field}=%s")
            params.append(raw[field])
    for part in raw.get("q", "").casefold().split():
        where.append("instr(search,%s)>0")
        params.append(part)
    condition = " AND ".join(where)
    total = store.rows("SELECT COUNT(*) AS n FROM cr_children WHERE " + condition, params)[0]["n"]
    rows = store.rows(
        "SELECT id,CASE WHEN bytes<=900 THEN payload END AS payload,sha FROM cr_children INDEXED BY cr_child_group WHERE "
        + condition
        + " ORDER BY id LIMIT %s OFFSET %s",
        [*params, size, offset(page, size)],
    )
    return dict(
        variants=[payload(r, token, "printing") for r in rows],
        total=total,
        page=page,
        page_size=size,
        pages=(total + size - 1) // size,
    )


@read
def evidence(build, token, raw):
    page, size = paging(raw)
    total = store.rows(
        "SELECT COUNT(*) AS n FROM cr_evidence WHERE build=%s AND scope IN ('public','shared')", [build]
    )[0]["n"]
    rows = store.rows(
        "SELECT id,CASE WHEN bytes<=900 THEN payload END AS payload,sha FROM cr_evidence WHERE build=%s AND scope IN ('public','shared') ORDER BY id LIMIT %s OFFSET %s",
        [build, size, offset(page, size)],
    )
    return dict(
        evidence=[dict(id=r["id"], record=payload(r, token, "evidence")) for r in rows],
        total=total,
        page=page,
        page_size=size,
        pages=(total + size - 1) // size,
    )


@read
def options(build, token, raw):
    page, size = paging(raw, ("field", "value"))
    field = raw.get("field", "set")
    if field not in {"set", "language", "edition", "finish", "variant"}:
        raise ValueError("Choose a supported field")
    extra = " AND value=%s" if raw.get("value") else ""
    args = [build, field, *([raw["value"]] if raw.get("value") else [])]
    total = store.rows(
        "SELECT COUNT(*) AS n FROM cr_options WHERE build=%s AND scope IN ('public','shared') AND field=%s"
        + extra,
        args,
    )[0]["n"]
    rows = store.rows(
        "SELECT rank,bytes,CASE WHEN bytes<=250 THEN value END AS value,CASE WHEN bytes<=250 THEN label END AS label FROM cr_options WHERE build=%s AND scope IN ('public','shared') AND field=%s"
        + extra
        + " ORDER BY rank LIMIT %s OFFSET %s",
        [*args, size, offset(page, size)],
    )
    # A long literal is represented by a complete resource, never silently truncated.
    items = [
        dict(value=r["value"], label=r["label"])
        if r["bytes"] <= 250
        else dict(oversized=True, url=url(f"resources/option/{field}-{r['rank']}/", token))
        for r in rows
    ]
    return dict(
        field=field,
        options=items,
        total=total,
        page=page,
        page_size=size,
        pages=(total + size - 1) // size,
        next=url("card-group-filters/", token, field=field, page=page + 1, page_size=size)
        if page * size < total
        else None,
    )


@read
def resource(build, token, raw, *, kind, key):
    if raw:
        raise ValueError("Unsupported resource selector")
    table = {"group": "cr_groups", "printing": "cr_printings", "evidence": "cr_evidence"}.get(kind)
    if kind == "option":
        field, _, rank = key.rpartition("-")
        if field not in {"set", "language", "edition", "finish", "variant"}:
            raise Http404
        number = card_groups._integer(rank, "option", 0)
        if number > (1 << 63) - 1:
            raise Http404
        found = store.rows(
            "SELECT value,label FROM cr_options WHERE build=%s AND scope IN ('public','shared') AND field=%s AND rank=%s",
            [build, field, number],
        )
        if not found:
            raise Http404
        return dict(record=found[0])
    if not table:
        raise Http404
    field, value = ("sha", key[4:]) if key.startswith("sha-") and len(key) == 68 else ("id", key)
    found = store.rows(
        f"SELECT id,payload,sha FROM {table} WHERE build=%s AND scope IN ('public','shared') AND {field}=%s LIMIT 1",
        [build, value],
    )
    if not found:
        raise Http404
    return dict(record=payload(found[0], token, kind, full=True))


@read
def resolve(build, token, raw, *, key):
    if raw:
        raise ValueError("Unsupported alias selector")
    found = store.rows(
        "SELECT a.printing_id,c.group_id FROM cr_aliases a LEFT JOIN cr_children c ON c.build=a.build AND c.scope IN ('public','shared') AND c.id=a.printing_id WHERE a.build=%s AND a.scope IN ('public','shared') AND a.alias=%s LIMIT 2",
        [build, key],
    )
    if len(found) > 1:
        raise Conflict("Ambiguous catalog alias")
    if not found or not found[0]["group_id"]:
        raise Http404
    return dict(group_id=found[0]["group_id"], child=found[0]["printing_id"])


@read
def species(build, token, raw):
    from .catalog_read_species import summaries

    return summaries(build, token, raw)


@read
def printings(build, token, raw):
    """Bounded picker for manual/goal/photo/Shopping consumers; no full-array bootstrap."""
    filters = card_groups._filters(raw, {"public": True})
    from .catalog_read_select import select

    total, rows = select(build, filters, printing=True)
    page, size = filters["page"], filters["page_size"]
    unresolved = store.rows(
        "SELECT COUNT(*) AS n FROM cr_printings WHERE build=%s AND scope IN ('public','shared') AND group_id IS NULL",
        [build],
    )[0]["n"]
    return dict(
        cards=[payload(r, token, "printing") for r in rows],
        unresolved_printings=dict(total=unresolved, url=url("catalog-unresolved/", token)),
        total=total,
        page=page,
        page_size=size,
        pages=(total + size - 1) // size,
    )


@read
def unresolved_printings(build, token, raw):
    page, size = paging(raw, ("q",))
    where = "build=%s AND scope IN ('public','shared') AND group_id IS NULL"
    params = [build]
    for part in raw.get("q", "").casefold().split():
        where += " AND instr(search,%s)>0"
        params.append(part)
    total = store.rows("SELECT COUNT(*) AS n FROM cr_printings WHERE " + where, params)[0]["n"]
    rows = store.rows(
        "SELECT id,CASE WHEN bytes<=900 THEN payload END AS payload,sha FROM cr_printings INDEXED BY cr_printing_unresolved WHERE "
        + where
        + " ORDER BY id LIMIT %s OFFSET %s",
        [*params, size, offset(page, size)],
    )
    return dict(
        cards=[payload(r, token, "printing") for r in rows],
        total=total,
        page=page,
        page_size=size,
        pages=(total + size - 1) // size,
    )


def artwork_ids(raw):
    if set(raw) != {"ids"} or len(raw["ids"]) > 17000:
        raise ValueError("Choose bounded artwork")
    ids = raw["ids"].split(",")
    if not 1 <= len(ids) <= 100 or len(set(ids)) != len(ids) or any(not i or len(i) > 160 for i in ids):
        raise ValueError("Choose at most 100 distinct artwork identities")
    return ids


@read
def artwork(build, token, raw):
    from . import image_bindings, image_mappings

    ids = artwork_ids(raw)
    if not image_bindings.enabled():
        return dict(artwork={})
    rows = store.rows(
        "SELECT id,payload,sha FROM cr_groups WHERE build=%s AND scope IN ('public','shared') AND id IN ("
        + ",".join(["%s"] * len(ids))
        + ")",
        [build, *ids],
    )
    pokemon = {r["id"] for r in store.rows("SELECT id FROM games WHERE game_key='pokemon'")}
    return dict(
        artwork={
            r["id"]: image_mappings.indexed_group_reference(
                payload(r, token, "group", full=True), pokemon_game_ids=pokemon
            )
            for r in rows
        }
    )


def species_artwork_records(raw):
    from . import image_bindings, image_mappings

    ids = artwork_ids(raw)
    numbers = [card_groups._integer(i, "species", 1, 251) for i in ids]
    return {str(n): image_mappings.species_artwork(n) for n in numbers} if image_bindings.enabled() else {}


@read
def species_artwork(build, token, raw):
    return dict(artwork=species_artwork_records(raw))
