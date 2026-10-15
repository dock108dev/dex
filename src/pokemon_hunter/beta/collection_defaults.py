"""Finite owner attestations over current cards, preserving explicit exceptions."""

import json

from . import collection, effective_collection, store


def _normal_metadata(printing):
    variant = printing.get("variant")
    if variant:
        try:
            variant = json.loads(variant)
        except (ValueError, TypeError):
            pass
        if variant not in ("normal", {"type": "normal"}):
            return False
    return printing.get("finish") in {None, "normal"} and printing.get("edition") not in {
        "first",
        "first_edition",
        "shadowless",
    }


def variant_exception(row, copies, catalog):
    return bool(row["exact_printing_owned_ids"]) or any(
        copy.get("first_edition_selected")
        or not _normal_metadata(catalog.get(copy.get("printing_id"), {}))
        or copy.get("notes") not in {None, "", "null"}
        for copy in (copies[cid] for cid in row["current_copy_ids"])
    )


def plan(actor, request):
    actor = store.verified(actor)
    ids = request.get("card_ids")
    if actor.role != "owner":
        raise ValueError("Only the owner can attest collection defaults")
    if (
        not isinstance(ids, list)
        or not 1 <= len(ids) <= 1000
        or any(not isinstance(key, str) for key in ids)
        or len(set(ids)) != len(ids)
        or request.get("quantity") != 1
        or type(request.get("quantity")) is not int
        or request.get("variant") != "normal"
    ):
        raise ValueError("Choose a finite list of owned cards, quantity 1 and normal variant")
    snapshot = effective_collection.project(actor)
    cards = {row["id"]: row for row in snapshot["cards"]}
    copies = {row["id"]: row for row in collection.copies(actor)}
    catalog = {row["id"]: row for row in collection.catalog(actor, include_archived=True)}
    intents = []
    for key in sorted(ids):
        row = cards.get(key)
        if not row or not row["present"] or row["identity_status"] == "conflict":
            raise collection.Conflict("A selected card is unavailable or no longer owned; review again")
        if row["established_total_quantity"] is None and len(row["current_copy_ids"]) > 1:
            raise collection.Conflict("Multiple recorded copies require an explicit total")
        exception = variant_exception(row, copies, catalog)
        intents.append(
            dict(
                kind="card_defaults",
                identity={
                    **{field: row[field] for field in ("set_name", "name", "number", "pokemon_dex")},
                    "candidate_printing_ids": row["printing_ids"],
                },
                established_total_quantity=row["established_total_quantity"] or 1,
                owned_variant=row.get("owned_variant") if exception else "normal",
            )
        )
    return dict(
        creates=[],
        updates=[],
        deletes=[],
        errors=[],
        checklist=[],
        warnings=[
            "Owner attestation: one normal card unless an existing quantity or variant note says otherwise. Copies, catalog metadata and frozen goals are preserved."
        ],
        card_intents=intents,
    )


def intents(plan):
    return ([plan["card_intent"]] if plan.get("card_intent") else []) + plan.get("card_intents", [])


def variant_printing_ids(row, catalog):
    """Known normal children only; unknown catalog fields never become exact proof."""
    if row.get("owned_variant") != "normal":
        return []
    return [
        p["id"]
        for p in catalog
        if p["id"] in row["printing_ids"] and p.get("finish") == "normal" and _normal_metadata(p)
    ]
