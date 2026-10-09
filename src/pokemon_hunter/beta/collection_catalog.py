"""Shared printing metadata reads; callers own authorization and output allowlists."""

import json

from django.conf import settings

from . import store


def catalog_entries(query="", set_id="", include_archived=False, *, published_only=False):
    """Read shared metadata internally; callers choose an explicit output projection.

    Early account-only roots have no reviewed publication state, so they expose
    no printing catalog to guests. Their canonical species registry still works.
    """
    if published_only and not settings.B4_ENABLED:
        return []
    result = store.rows(
        "SELECT p.*,s.game_id,s.name AS set_name,s.catalog_version,s.coverage_status FROM printings p JOIN catalog_sets s ON s.id=p.set_id "
        + (
            "WHERE p.publication_state='published' AND s.publication_state='published' "
            if (settings.B4_ENABLED and not include_archived) or published_only
            else ""
        )
        + "ORDER BY s.name,p.collector_number"
    )
    if getattr(settings, "STAGING", False):
        result = [
            r
            for r in result
            if json.loads(r["provenance"]).get("provider", "").split(":")[0] in {"tcgdex", "dex-synthetic"}
        ]
    for row in result:
        row["attributes"] = json.loads(row["attributes"])
        row["unresolved_fields"] = json.loads(row["unresolved_fields"])
        row["name"] = row["attributes"].get("name", "Unidentified card")
    return [
        r
        for r in result
        if (not set_id or r["set_id"] == set_id)
        and query.casefold() in (r["name"] + " " + r["collector_number"] + " " + r["set_name"]).casefold()
    ]
