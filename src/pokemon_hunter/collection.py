"""Card ownership is truth; all species and set counts are projections."""

import json
import os
import re
import tempfile
import threading
from pathlib import Path

LOCK = threading.RLock()


class CollectionInputError(ValueError):
    """Fixed ownership-validation messages safe for the original app's response."""


def canonical_name(name):
    return " ".join(name.casefold().replace("♀", " female").replace("♂", " male").replace("’", "'").split())


def derive(data):
    for species in data["pokedex"].values():
        species["eligible_cards"] = []
        species["dex_owned"] = False
    for card_id, card in data["cards"].items():
        if "quantity" in card:
            card["owned"] = card.pop("quantity") > 0
        card.setdefault("owned", False)
        card.setdefault("first_edition", False)
        if card["dex_eligible"]:
            row = data["pokedex"][str(card["pokemon_dex"])]
            row["eligible_cards"].append(card_id)
            row["dex_owned"] |= card["owned"]
    return data


def build(root: Path):
    legacy = json.loads((root / "config/pokedex.json").read_text())
    sources = json.loads((root / "config/catalog/sources.json").read_text())
    data = {
        "metadata": {
            "schema_version": 2,
            "dex_range": [1, 251],
            "eligible_sets": [s["id"] for s in sources["sets"]],
            "catalog_source": sources,
            "ownership_import_complete": False,
            "ownership_note": "",
            "rules": {
                "dark_pokemon_count": False,
                "trainer_owned_pokemon_count": False,
                "normal_team_rocket_cards_count": True,
            },
            "import_issues": [],
        },
        "cards": {},
        "pokedex": {
            str(r["dex_number"]): {
                "dex_number": r["dex_number"],
                "name": r["pokemon_name"],
                "generation": r["generation"],
                "legacy_species_owned": r["owned"],
            }
            for r in legacy
        },
    }
    for s in sources["sets"]:
        for raw in json.loads((root / f"config/catalog/{s['id']}.json").read_text()):
            numbers = raw.get("nationalPokedexNumbers", [])
            dex = numbers[0] if len(numbers) == 1 and numbers[0] <= 251 else None
            # Unown letter forms represent the same species; named/trainer/Dark cards do not.
            normal = dex and (
                canonical_name(raw["name"]) == canonical_name(data["pokedex"][str(dex)]["name"])
                or (dex == 201 and re.fullmatch(r"Unown \[?[A-Z!?]\]?", raw["name"]))
            )
            card_id = f"{s['id']}-{raw['number']}"
            data["cards"][card_id] = {
                "card_id": card_id,
                "source_id": raw["id"],
                "pokemon_dex": dex,
                "name": raw["name"],
                "set_id": s["id"],
                "set": s["name"],
                "number": raw["number"],
                "rarity": raw.get("rarity", "Unknown"),
                "holo": "Holo" in raw.get("rarity", ""),
                "supertype": raw["supertype"],
                "dex_eligible": bool(normal and raw["supertype"] == "Pokémon"),
                "owned": False,
                "first_edition": False,
                "ownership_recorded": False,
            }
    source = json.loads((root / "sources/confirmed-ownership.json").read_text())
    owned = {f"{set_id}-{number}" for set_id, numbers in source["sets"].items() for number in numbers}
    if owned - data["cards"].keys():
        raise ValueError("Confirmed ownership contains an unknown printing")
    for key, card in data["cards"].items():
        card.update(owned=key in owned, ownership_recorded=True)
    data["metadata"].update(
        imported_cards=len(owned),
        ownership_import_complete=True,
        ownership_note="Confirmed collection imported September 27, 2026. Ownership is tracked per printing; first edition is marked separately.",
        ownership_source="sources/confirmed-ownership.json",
    )
    return derive(data)


def read(path):
    return derive(json.loads(path.read_text()))


def save(path, data):
    derive(data)
    if path.is_symlink():
        raise OSError("Collection writes require a regular destination, not a symlink")
    # Unique 0600 files keep replacement private even under a permissive umask.
    # Retain a failed private temporary write rather than overwriting the source.
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
    ) as output:
        json.dump(data, output, ensure_ascii=False, indent=2)
        output.write("\n")
    os.replace(output.name, path)


def update_card(path, card_id, owned, first_edition=False):
    if type(owned) is not bool or type(first_edition) is not bool:
        raise CollectionInputError("Owned and first edition must be checkboxes")
    if first_edition and not owned:
        raise CollectionInputError("Mark the card owned before marking first edition")
    with LOCK:
        data = read(path)
        if card_id not in data["cards"]:
            raise CollectionInputError("Unknown card")
        card = data["cards"][card_id]
        if first_edition and card["set_id"] in ("base_set_2", "wizards_black_star_promos"):
            raise CollectionInputError("This set has no standard first-edition printing")
        card.update(owned=owned, first_edition=first_edition, ownership_recorded=True)
        save(path, data)
        return data


def totals(data):
    rows = list(data["pokedex"].values())
    k = sum(r["dex_owned"] for r in rows if r["generation"] == 1)
    j = sum(r["dex_owned"] for r in rows if r["generation"] == 2)
    return {
        "kanto": k,
        "johto": j,
        "total": k + j,
        "exact_cards": sum(c["owned"] for c in data["cards"].values()),
        "unavailable_species": sum(not r["eligible_cards"] for r in rows),
    }
