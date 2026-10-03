"""Frozen goal membership with current, account-scoped ownership for hunt scoring."""

import json
from copy import deepcopy

from pokemon_hunter.collection import derive

from . import collection as service
from . import store


def snapshot(actor, key):
    if key is None:
        return None
    goal = service.one(actor, "goal", key)
    return {"id": goal["id"], "name": goal["name"], "definition": json.loads(goal["definition"])}


def project(actor, data, scope):
    if scope is None:
        return data
    definition = scope["definition"]
    policy = definition["policy"]
    allowed = {key for item in definition["items"] for key in item["printing_ids"]}
    exact_owned = service.exact_owned_printings(service.copies(actor))
    game_names = {game["id"]: game["name"] for game in store.rows("SELECT id,name FROM games")}
    catalog = {printing["id"]: printing for printing in data["catalog"]}
    cards = {}
    for key, card in data["cards"].items():
        if card["printing_id"] not in allowed:
            continue
        card = dict(card)
        card.setdefault("dex_eligible", False)
        card.setdefault("pokemon_dex", None)
        game_id = catalog[card["printing_id"]]["game_id"]
        if game_id not in game_names:
            raise ValueError("Goal catalog references an unavailable game")
        game_name = game_names[game_id]
        card["game_name"] = "Pokemon" if game_name == "Pokémon" else game_name
        if policy == "exact":
            card["owned"] = (
                card["printing_id"] in exact_owned and not catalog[card["printing_id"]]["unresolved_fields"]
            )
        elif policy == "species":
            card["dex_eligible"] = isinstance(card["pokemon_dex"], int) and 1 <= card["pokemon_dex"] <= 251
        cards[key] = card
    scoped = (
        derive({"cards": cards, "pokedex": deepcopy(data["pokedex"])})
        if policy == "species"
        else {"cards": cards}
    )
    return {
        **data,
        **scoped,
        "goal_scope": True,
        "completion": "species" if policy == "species" else "printings",
    }


def public(scope):
    if scope is None:
        return None
    return {"id": scope["id"], "name": scope["name"], "policy": scope["definition"]["policy"]}
