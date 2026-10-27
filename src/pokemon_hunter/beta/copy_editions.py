"""Explicit edition selection shared by individual and photo-batch review."""

import json

from pokemon_hunter.migration import encode


def is_first(printing):
    """Both retained catalog spellings represent the same first-edition identity."""
    return printing["edition"] in {"first_edition", "1st-edition"}


def require_first_supported(printing):
    legacy = json.loads(printing["provenance"]).get("legacy_id", "")
    if legacy.startswith(("base_set_2-", "wizards_black_star_promos-")):
        raise ValueError("This set has no standard first-edition printing")


def select(before, printing, selection):
    if selection not in {"first_edition", "unresolved"}:
        raise ValueError("Choose first_edition or unresolved; unchecked never means unlimited")
    if selection == "first_edition":
        require_first_supported(printing)
    identity = json.loads(before.get("provisional_identity") or "{}")
    unresolved = set(identity.get("unresolved_fields", [])) | set(printing["unresolved_fields"])
    if selection == "first_edition":
        unresolved.discard("edition")
    else:
        unresolved.add("edition")
    identity.update(edition_selection=selection, unresolved_fields=sorted(unresolved))
    return {
        **before,
        "first_edition_selected": int(selection == "first_edition"),
        "provisional_identity": encode(identity),
        "revision": before["revision"] + 1,
    }
