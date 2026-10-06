"""Frozen goal membership with current, account-scoped ownership for hunt scoring."""

import json
from copy import deepcopy

from pokemon_hunter.collection import derive

from . import collection as service
from . import collection_goals, store


def snapshot(actor, key):
    if key is None:
        return None
    goal = service.one(actor, "goal", key)
    return {
        "id": goal["id"],
        "name": goal["name"],
        "version": goal["version"],
        "kind": goal["kind"],
        "definition": json.loads(goal["definition"]),
    }


def project(actor, data, scope):
    if scope is None:
        return data
    definition = scope["definition"]
    policy = definition["policy"]
    allowed = {key for item in definition["items"] for key in item["printing_ids"]}
    frozen_species = {
        key: item.get("pokemon_dex") for item in definition["items"] for key in item["printing_ids"]
    }
    exact_owned = service.exact_owned_printings(service.copies(actor))
    game_names = {game["id"]: game["name"] for game in store.rows("SELECT id,name FROM games")}
    catalog = {printing["id"]: printing for printing in data["catalog"]}
    source_cards = dict(data["cards"])
    if scope.get("kind") in collection_goals.KINDS:
        sets = {
            r["internal_id"]: r["external_id"]
            for r in store.rows(
                "SELECT * FROM external_mappings WHERE provider='legacy' AND entity_kind='set'"
            )
        }
        # Archived metadata remains recognizable within a retained version only.
        for p in service.catalog(actor, include_archived=True):
            if p["id"] not in allowed or p["id"] in catalog:
                continue
            catalog[p["id"]] = p
            key = json.loads(p["provenance"]).get("legacy_id") or "catalog-" + p["id"]
            source_cards[key] = {
                **p["attributes"],
                "card_id": key,
                "printing_id": p["id"],
                "set_id": sets.get(p["set_id"], p["set_id"]),
                "set": p["set_name"],
                "number": p["collector_number"],
                "variant": p["variant"],
                "owned": False,
                "first_edition": False,
            }
    cards = {}
    for key, card in source_cards.items():
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
        elif scope.get("kind") in collection_goals.KINDS:
            card["owned"] = card["printing_id"] in exact_owned
            card["pokemon_dex"] = frozen_species[card["printing_id"]]
            card["dex_eligible"] = True
        elif policy == "species":
            card["dex_eligible"] = isinstance(card["pokemon_dex"], int) and 1 <= card["pokemon_dex"] <= 251
        cards[key] = card
    scoped = (
        derive({"cards": cards, "pokedex": deepcopy(data["pokedex"])})
        if policy == "species"
        else {"cards": cards}
    )
    if scope.get("kind") in collection_goals.OWNERSHIP_KINDS:
        # Species scoring never labels unowned exact card printings as owned.
        for number, species in scoped["pokedex"].items():
            species["dex_owned"] = int(number) in definition["owned_species"]
    return {
        **data,
        **scoped,
        "catalog": list(catalog.values()),
        "goal_scope": True,
        "completion": "species" if policy == "species" else "printings",
    }


def public(scope):
    if scope is None:
        return None
    return {
        "id": scope["id"],
        "name": scope["name"],
        "version": scope.get("version"),
        "policy": scope["definition"]["policy"],
        "ownership_basis": (
            "Frozen declared collection species; exact printing identity remains separate"
            if scope.get("kind") in collection_goals.OWNERSHIP_KINDS
            else "Current account ownership compared with frozen search membership"
        ),
    }
