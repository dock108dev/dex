"""Shared frozen-goal progress policy; membership is never reconstructed from catalog."""

from . import broad_goals, collection_goals


def evaluate(kind, definition, active, available_ids, published_ids):
    if kind in collection_goals.KINDS:
        return broad_goals.progress(definition, active, available_ids)
    from .collection import exact_owned_printings

    owned = {c["printing_id"] for c in active}
    exact_owned = exact_owned_printings(active, published_ids)
    items = definition["items"]
    matched = [
        i
        for i in items
        if owned.intersection(i["printing_ids"])
        and (
            definition["policy"] != "exact"
            or (not i["unresolved"] and exact_owned.intersection(i["printing_ids"]))
        )
    ]
    progress = [
        dict(
            item,
            status="owned"
            if item in matched
            else "unavailable"
            if not available_ids.intersection(item["printing_ids"])
            else "missing",
        )
        for item in items
    ]
    unavailable = sum(i["status"] == "unavailable" for i in progress)
    return dict(
        satisfied=len(matched),
        total=len(items),
        progress=progress,
        unavailable=unavailable,
        missing=len(items) - len(matched) - unavailable,
    )
