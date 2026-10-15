"""Finite read-only collection-to-Shopping context; never supplies lot quantities."""

import re

from django.http import Http404

from . import (
    canonical_species,
    card_groups,
    collection,
    collection_goals,
    effective_collection,
    lot_calculator,
    public_catalog,
    store,
)

FIELDS = {"species", "group", "child", "goal", "version", "generation", "return"}


def resolve(who, raw, *, legacy_goal=False):
    who = store.verified(who)
    if set(raw) - FIELDS:
        raise ValueError("Choose supported Shopping context fields")
    if any(
        not isinstance(value, str)
        or not value
        or len(value) > (4096 if key == "return" else 160)
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
        for key, value in raw.items()
    ):
        raise ValueError("Choose bounded Shopping context")
    if "species" in raw and "group" in raw or "child" in raw and "group" not in raw:
        raise ValueError("Choose a species or a card group with an optional explicit printing")
    if "version" in raw and not raw.get("goal"):
        raise ValueError("A retained version requires its saved goal")
    if raw.get("goal") and "version" not in raw and not legacy_goal:
        raise ValueError("A saved goal requires its retained version")
    if "group" in raw and not re.fullmatch(r"dg1-[0-9a-f]{64}", raw["group"]):
        raise ValueError("Choose a canonical card group")
    if "species" in raw:
        card_groups._integer(raw["species"], "species", 1, 251)
    if "version" in raw and not re.fullmatch(r"[0-9a-f]{64}", raw["version"]):
        raise ValueError("Choose an exact retained goal version")
    generation = collection.generation(who)
    if (
        "generation" in raw
        and card_groups._integer(raw["generation"], "collection generation", 0, 10**18) != generation
    ):
        raise collection.Conflict("Collection changed; reopen Shopping from your collection")
    result = dict(
        account_id=who.user_id,
        generation=generation,
        kind="all",
        label="Vintage cards · Base Set through Neo Destiny",
        return_url=raw.get("return", ""),
        query=dict(raw),
        available=True,
        needs_selection=False,
        current_present=None,
        goal_kind=None,
        goal_version=None,
    )
    if raw.get("return"):
        from .navigation import authorize_destination

        authorize_destination(who, raw["return"])
    goal = None
    if raw.get("goal"):
        try:
            goal = collection.one(who, "goal", raw["goal"])
        except Http404 as error:
            if legacy_goal and "version" not in raw:
                raise ValueError("Choose one of your collection goals") from error
            raise
        if "version" in raw:
            if not re.fullmatch(r"[0-9a-f]{64}", raw["version"]):
                raise ValueError("Choose an exact retained goal version")
            if raw["version"] != goal["version"]:
                raise collection.Conflict("Saved goal changed; reopen it from Goals")
        result.update(
            kind="goal",
            label=f"Saved goal: {goal['name']}",
            goal_kind=goal["kind"],
            goal_version=goal["version"],
        )
    if "species" in raw:
        number = card_groups._integer(raw["species"], "species", 1, 251)
        current = effective_collection.project(who)
        result.update(
            kind="species",
            species=number,
            label=f"Finding cards for {canonical_species.registry()[number]['name']}"
            + (f" · Saved goal: {goal['name']}" if goal else ""),
            current_present=current["species"][str(number)]["present"],
            needs_selection=True,
        )
    if "group" in raw:
        if not re.fullmatch(r"dg1-[0-9a-f]{64}", raw["group"]):
            raise ValueError("Choose a canonical card group")
        detail = card_groups.detail(who, raw["group"], selected_child=raw.get("child"))
        group, child = detail["group"], detail["selected_child"]
        result.update(
            kind="printing" if child else "group",
            label=f"Finding {group['name']} · {group['set_name']} #{group['collector_number']}"
            + (f" · {child['id']}" if child else " · Choose a printing"),
            group=group["id"],
            child=child["id"] if child else None,
            printing_ids=[row["id"] for row in detail["variants"] if row["available"]],
            current_present=group["present"],
            available=bool(child["available"]) if child else bool(group["catalog_available"]),
            needs_selection=child is None,
        )
    if goal:
        import json

        loaded_goal = collection.goals(who, goal_id=goal["id"], include_updates=False)[0]
        result["goal_progress"] = dict(satisfied=loaded_goal["satisfied"], total=loaded_goal["total"])
        result["goal_units"] = (
            "species" if json.loads(goal["definition"]).get("policy") == "species" else "printings"
        )
        result["goal_policy"] = (
            "Frozen declaration snapshot"
            if goal["kind"] in collection_goals.OWNERSHIP_KINDS
            else "Frozen species membership · current qualified copies"
            if result["goal_units"] == "species"
            else "Frozen printing membership · current qualified copies"
        )
        if result["kind"] in {"group", "printing"}:
            result["label"] += f" · Saved goal: {goal['name']}"
    store.verified(who)
    if collection.generation(who) != generation:
        raise collection.Conflict("Collection changed during Shopping context read")
    return result


def catalog(who, context, query="", *, printing="", offset=0):
    """Select only admitted local printings, independently of ownership and quantities."""
    raw = context["query"]
    goal_id = raw.get("goal", "")
    if context["kind"] == "goal":
        return lot_calculator.browse_page(who, query, goal_id=goal_id, printing_id=printing, offset=offset)
    entries = lot_calculator.catalog(
        who, query, include_goals=bool(goal_id), goal_ids=None if goal_id else set()
    )
    if goal_id:
        import json

        goal = collection.one(who, "goal", goal_id)
        ids = {key for item in json.loads(goal["definition"])["items"] for key in item["printing_ids"]}
        entries = [row for row in entries if row["id"] in ids]
    if context["kind"] == "species":
        species_ids = {
            row["id"]
            for row in public_catalog.cards(entries)
            if row["pokemon_dex"] == context["species"] and row["supertype"] == "Pokémon"
        }
        entries = [row for row in entries if row["id"] in species_ids]
    if context["kind"] in {"group", "printing"}:
        entries = [row for row in entries if row["id"] in context["printing_ids"]]
    if (
        printing
        and context["kind"] in {"group", "printing"}
        and printing != context.get("child")
        and printing not in context["printing_ids"]
    ):
        raise Http404("Printing does not belong to this available group")
    if context.get("child") and printing and printing != context["child"]:
        raise ValueError("Keep the explicit selected printing context")
    selected = context.get("child") or printing
    if selected:
        entries = [row for row in entries if row["id"] == selected]
    selectable = entries[offset : offset + 40]
    cards = (
        lot_calculator.priced_cards(who, selectable)
        if selected
        else [dict(lot_calculator.shopping.identity(row), cells={}, price_reasons={}) for row in selectable]
    )
    if not entries:
        context.update(
            available=False,
            unavailable="This target is archived, missing or outside the calculator’s supported catalog. Choose another target explicitly.",
        )
    return dict(cards=cards, total=len(entries), offset=offset, missing_items=[], selected_missing_item="")


def finish(who, context):
    store.verified(who)
    if collection.generation(who) != context["generation"]:
        raise collection.Conflict("Collection changed during Shopping read")
    if context["query"].get("goal"):
        goal = collection.one(who, "goal", context["query"]["goal"])
        if goal["version"] != context["goal_version"]:
            raise collection.Conflict("Saved goal changed during Shopping read")
    return context
