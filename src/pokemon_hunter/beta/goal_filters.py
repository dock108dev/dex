"""Reusable catalog filters and frozen species/printing goal membership."""

FIELDS = {"game_id", "set_ids", "card_type", "rarities", "pokemon_dex_min", "pokemon_dex_max", "completion"}


def filters(raw, entries, games):
    if not isinstance(raw, dict) or set(raw) - FIELDS:
        raise ValueError("Choose supported goal filters")
    game = next((g for g in games if g["id"] == raw.get("game_id")), None)
    if game is None:
        raise ValueError("Choose a supported game")
    game_entries = [p for p in entries if p["game_id"] == game["id"]]
    if not game_entries:
        raise ValueError("This game has no published catalog entries")
    sets, rarities = raw.get("set_ids", []), raw.get("rarities", [])
    for values in (sets, rarities):
        if (
            not isinstance(values, list)
            or any(not isinstance(v, str) for v in values)
            or len(values) != len(set(values))
        ):
            raise ValueError("Filters must be lists without repeated values")
    if not set(sets) <= {p["set_id"] for p in game_entries}:
        raise ValueError("Choose published sets from this game")
    if not set(rarities) <= {p["attributes"].get("rarity", "Unknown") or "Unknown" for p in game_entries}:
        raise ValueError("Choose supported rarities")
    card_type = raw.get("card_type", "all")
    types = {p["attributes"].get("supertype", "Unknown") or "Unknown" for p in game_entries}
    if card_type != "all" and card_type not in types:
        raise ValueError("Choose a supported card type")
    completion = raw.get("completion", "printings")
    if completion not in {"species", "printings"}:
        raise ValueError("Choose species or printing completion")
    low, high = raw.get("pokemon_dex_min"), raw.get("pokemon_dex_max")
    if completion == "species":
        if game["game_key"] != "pokemon":
            raise ValueError("Species completion requires the Pokémon catalog")
        # Synthetic/legacy catalogs may lack a supertype; dex eligibility remains the rule.
        if card_type not in {"all", "Pokémon", "Unknown"}:
            raise ValueError("Species completion requires Pokémon cards")
        low = 1 if low is None else low
        high = 251 if high is None else high
    if low is not None or high is not None:
        if (
            game["game_key"] != "pokemon"
            or type(low) is not int
            or type(high) is not int
            or not 1 <= low <= high <= 251
        ):
            raise ValueError("Choose a Pokémon range within 1–251")
    return {
        "game_id": game["id"],
        "set_ids": sorted(sets),
        "card_type": card_type,
        "rarities": sorted(rarities),
        "pokemon_dex_min": low,
        "pokemon_dex_max": high,
        "completion": completion,
    }


def matches(p, scope):
    a = p["attributes"]
    number = a.get("pokemon_dex")
    return (
        p["game_id"] == scope["game_id"]
        and (not scope["set_ids"] or p["set_id"] in scope["set_ids"])
        and (scope["card_type"] == "all" or (a.get("supertype") or "Unknown") == scope["card_type"])
        and (not scope["rarities"] or (a.get("rarity") or "Unknown") in scope["rarities"])
        and (
            scope["pokemon_dex_min"] is None
            or type(number) is int
            and scope["pokemon_dex_min"] <= number <= scope["pokemon_dex_max"]
        )
        and (scope["completion"] != "species" or bool(a.get("dex_eligible")))
    )


def printing_items(entries):
    """One frozen item shape for filtered, set and custom printing checklists."""
    return [
        {
            "label": f"{p['name']} · {p['set_name']} #{p['collector_number']}",
            "printing_ids": [p["id"]],
            "unresolved": bool(p["unresolved_fields"]),
            "edition": p["edition"],
            "finish": p["finish"],
            "variant": p["variant"],
        }
        for p in entries
    ]


def definition(raw, entries, games, policy="catalog"):
    scope = filters(raw, entries, games)
    selected = [p for p in entries if matches(p, scope)]
    if scope["completion"] == "species":
        items = []
        for number in range(scope["pokemon_dex_min"], scope["pokemon_dex_max"] + 1):
            members = [p for p in selected if p["attributes"].get("pokemon_dex") == number]
            label = members[0]["name"] if members else f"Species {number:03}"
            items.append(
                {
                    "label": f"#{number:03} {label}",
                    "pokemon_dex": number,
                    "printing_ids": sorted(p["id"] for p in members),
                    "unresolved": False,
                }
            )
        policy = "species"
        coverage = "One eligible printing per species, from your selected catalog filters. Species without matching printings remain unavailable."
    else:
        if policy not in {"catalog", "exact"} or not selected:
            raise ValueError("Choose filters with available printings and a supported completion policy")
        items = printing_items(selected)
        coverage = "Selected published printings only. Unresolved variants do not establish exact-variant completion."
    if len(items) > 2000:
        raise ValueError("Narrow this goal to at most 2000 members")
    return {
        "policy": policy,
        "items": items,
        "filters": scope,
        "catalog_versions": sorted({p["catalog_version"] for p in selected}),
        "coverage": coverage,
    }
