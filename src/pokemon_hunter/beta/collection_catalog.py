"""Shared printing metadata reads; callers own authorization and output allowlists."""

import json

from django.conf import settings

from . import store


def catalog_entries(
    query="",
    set_id="",
    include_archived=False,
    *,
    published_only=False,
    printing_ids=None,
    group_keys=None,
    game_key=None,
):
    """Read shared metadata internally; callers choose an explicit output projection.

    Early account-only roots have no reviewed publication state, so they expose
    no printing catalog to guests. Their canonical species registry still works.
    """
    if published_only and not settings.B4_ENABLED:
        return []
    conditions, params = [], []
    if (settings.B4_ENABLED and not include_archived) or published_only:
        conditions.append("p.publication_state='published' AND s.publication_state='published'")
    if game_key is not None:
        conditions.append("s.game_id IN (SELECT id FROM games WHERE game_key=%s)")
        params.append(game_key)
    if printing_ids is not None:
        ids = tuple(dict.fromkeys(printing_ids))
        if not ids:
            return []
        conditions.append("p.id IN (" + ",".join(["%s"] * len(ids)) + ")")
        params.extend(ids)
    if group_keys is not None:
        if not group_keys:
            return []
        if len(group_keys) > 100:
            raise ValueError("Choose at most 100 image identity groups")
        groups = []
        for key in group_keys:
            if len(key) != 4:
                raise ValueError("Choose a literal image identity group")
            terms = []
            for column, value in zip(
                ("s.game_id", "p.set_id", "p.language", "p.collector_number"), key, strict=True
            ):
                terms.append(column + (" IS NULL" if value is None else "=%s"))
                if value is not None:
                    params.append(value)
            groups.append("(" + " AND ".join(terms) + ")")
        conditions.append("(" + " OR ".join(groups) + ")")
    result = store.rows(
        "SELECT p.*,s.game_id,s.name AS set_name,s.aliases AS set_aliases,"
        + ("s.publication_state" if settings.B4_ENABLED else "'published'")
        + " AS set_publication_state,s.catalog_version,s.coverage_status "
        "FROM printings p JOIN catalog_sets s ON s.id=p.set_id "
        + ("WHERE " + " AND ".join(conditions) + " " if conditions else "")
        + "ORDER BY s.name,p.collector_number",
        params,
    )
    if getattr(settings, "STAGING", False):
        result = [
            r
            for r in result
            if json.loads(r["provenance"]).get("provider", "").split(":")[0] in {"tcgdex", "dex-synthetic"}
        ]
    from .read_diagnostics import decoded

    decoded(len(result))
    for row in result:
        row["set_aliases"] = json.loads(row["set_aliases"])
        row["attributes"] = json.loads(row["attributes"])
        row["unresolved_fields"] = json.loads(row["unresolved_fields"])
        row["name"] = row["attributes"].get("name", "Unidentified card")
        from .catalog_variants import display

        display(row)
    return [
        r
        for r in result
        if (not set_id or r["set_id"] == set_id)
        and all(
            token
            in (
                r["name"] + " " + r["collector_number"] + " " + r["set_name"] + " " + r["variant_label"]
            ).casefold()
            for token in query.casefold().split()
        )
    ]


def set_options(actor):
    """Enumerate sets without decoding printings; retain ordinary visibility rules."""
    store.verified(actor)
    if getattr(settings, "STAGING", False):
        pairs = {(p["set_id"], p["set_name"]) for p in catalog_entries()}
        result = [dict(id=key, name=name) for key, name in sorted(pairs)]
    else:
        printing_scope = " WHERE p.publication_state='published'" if settings.B4_ENABLED else ""
        set_scope = " AND s.publication_state='published'" if settings.B4_ENABLED else ""
        result = store.rows(
            "SELECT s.id,s.name FROM catalog_sets s WHERE s.id IN "
            "(SELECT DISTINCT p.set_id FROM printings p"
            + printing_scope
            + ")"
            + set_scope
            + " ORDER BY s.name,s.id"
        )
    store.verified(actor)
    return result
