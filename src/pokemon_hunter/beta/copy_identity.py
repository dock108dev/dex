"""Group-bound copy authority comes from original bulk admission, never arbitrary JSON."""

import json

from . import store


def binding(copy, creation=None, *, history=False):
    if not copy or copy.get("printing_id"):
        return None
    value = json.loads(copy.get("provisional_identity") or "{}").get("group_binding")
    if not value:
        return None
    if creation is None:
        operations = store.rows(
            "SELECT kind,changes,state FROM collection_operations WHERE user_id=%s AND id=%s",
            [copy["user_id"], copy.get("batch_id")],
        )
        if not operations:
            return None
        creation = {**operations[0], "changes": json.loads(operations[0]["changes"])}
    if creation.get("kind") != "bulk" or creation.get("state") not in (
        {"confirmed", "undone"} if history else {"confirmed"}
    ):
        return None
    for change in creation.get("changes", []):
        image = change.get("after")
        if (
            change.get("kind") == "copy"
            and change.get("before") is None
            and image
            and image["id"] == copy["id"]
        ):
            original = json.loads(image.get("provisional_identity") or "{}").get("group_binding")
            if value == original:
                return value
    return None


def matches(copy, printing_ids, identity):
    if copy.get("printing_id") in printing_ids:
        return True
    bound = binding(copy)
    return bool(
        bound and all(bound["identity"].get(k) == identity.get(k) for k in ("set_name", "name", "number"))
    )
