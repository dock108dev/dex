"""Shared printing metadata reads; callers own authorization and output allowlists."""

import json

from django.conf import settings

from . import store


def catalog_entries(query="", set_id="", include_archived=False, *, published_only=False, printing_ids=None):
    """Read shared metadata internally; callers choose an explicit output projection.

    Early account-only roots have no reviewed publication state, so they expose
    no printing catalog to guests. Their canonical species registry still works.
    """
    if published_only and not settings.B4_ENABLED:
        return []
    conditions, params = [], []
    if (settings.B4_ENABLED and not include_archived) or published_only:
        conditions.append("p.publication_state='published' AND s.publication_state='published'")
    if printing_ids is not None:
        ids = tuple(dict.fromkeys(printing_ids))
        if not ids:
            return []
        conditions.append("p.id IN (" + ",".join(["%s"] * len(ids)) + ")")
        params.extend(ids)
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
