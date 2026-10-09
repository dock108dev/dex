"""Explicit guest projections over reviewed catalog metadata only.

No account principal, ownership file, private source or provider request is used.
Raw catalog attributes and provenance stay inside the metadata service.
"""

from django.http import Http404

from . import broad_goals, canonical_species, collection, lookup, offer_filters, packs, store

FILTERS = {"q", "set", "era", "region", "type"}
CARD_FIELDS = (
    "id",
    "set_id",
    "set_name",
    "collector_number",
    "edition",
    "finish",
    "variant",
    "name",
    "catalog_version",
    "coverage_status",
    "unresolved_fields",
)


def entries():
    rows = collection.catalog_entries(published_only=True)
    if not rows:
        return []
    games = {row["id"] for row in store.rows("SELECT id FROM games WHERE game_key='pokemon'")}
    return [row for row in rows if row["game_id"] in games and row["language"] == "en"]


def cards(rows):
    from .catalog_pipeline import indexed_eras

    eras = indexed_eras() if rows else {}
    result = []
    for row in rows:
        attributes = row["attributes"]
        number = attributes.get("pokemon_dex")
        if type(number) is not int or not 1 <= number <= 251:
            number = None
        projected = {key: row.get(key) for key in CARD_FIELDS}
        projected["unresolved_fields"] = [
            value for value in row["unresolved_fields"] if isinstance(value, str)
        ]
        for key in CARD_FIELDS:
            if (
                key != "unresolved_fields"
                and projected[key] is not None
                and not isinstance(projected[key], str)
            ):
                projected[key] = None
        result.append(
            dict(
                projected,
                pokemon_dex=number,
                rarity=attributes.get("rarity") if isinstance(attributes.get("rarity"), str) else "Unknown",
                supertype=attributes.get("supertype")
                if isinstance(attributes.get("supertype"), str)
                else "Unknown",
                era=eras.get(row["set_id"]) or "Unknown",
            )
        )
    return result


def pokedex(raw, dex=None):
    if set(raw) - FILTERS:
        raise ValueError("Public browsing accepts catalog filters only. Sign in for collection tools.")
    filters = {key: raw.get(key, "") for key in FILTERS}
    if any(not isinstance(value, str) or len(value) > 160 for value in filters.values()):
        raise ValueError("Choose shorter text filters.")
    if filters["region"] not in {"", "kanto", "johto"}:
        raise ValueError("Choose Kanto or Johto.")
    if dex is not None and not 1 <= dex <= 251:
        raise Http404
    all_cards = cards(entries())
    registry = canonical_species.registry()
    by_species = {}
    for card in all_cards:
        if card["pokemon_dex"] and card["supertype"] == "Pokémon":
            by_species.setdefault(card["pokemon_dex"], []).append(card)
    species = [
        dict(
            dex=number,
            name=registry[number]["name"],
            region="kanto" if number <= 151 else "johto",
            printing_count=len(by_species.get(number, [])),
        )
        for number in range(1, 252)
    ]
    selected_species = next((row for row in species if row["dex"] == dex), None)
    query = filters["q"].strip().casefold()
    numeric_query = query.removeprefix("#")

    def matches(card):
        return (
            (not filters["set"] or card["set_id"] == filters["set"])
            and (not filters["era"] or card["era"] == filters["era"])
            and (not filters["type"] or card["supertype"] == filters["type"])
            and (
                not filters["region"]
                or card["pokemon_dex"] is not None
                and ("kanto" if card["pokemon_dex"] <= 151 else "johto") == filters["region"]
            )
            and (
                not query
                or numeric_query.isdecimal()
                and card["pokemon_dex"] == int(numeric_query)
                or query
                in " ".join(card[key] or "" for key in ("name", "collector_number", "set_name")).casefold()
            )
            and (dex is None or card["pokemon_dex"] == dex)
        )

    visible_cards = [card for card in all_cards if matches(card)]
    matching_numbers = {card["pokemon_dex"] for card in visible_cards}
    has_card_filter = any(filters[key] for key in ("set", "era", "type"))
    visible_species = [
        row
        for row in species
        if (dex is None or row["dex"] == dex)
        and (not filters["region"] or row["region"] == filters["region"])
        and (not has_card_filter or row["dex"] in matching_numbers)
        and (
            not query
            or row["dex"] in matching_numbers
            or query in row["name"].casefold()
            or numeric_query.isdecimal()
            and row["dex"] == int(numeric_query)
        )
    ]
    return dict(
        public=True,
        species=visible_species,
        selected_species=selected_species,
        cards=visible_cards,
        filters=filters,
        sets=sorted(
            {card["set_id"]: dict(id=card["set_id"], name=card["set_name"]) for card in all_cards}.values(),
            key=lambda row: row["name"],
        ),
        eras=sorted({card["era"] for card in all_cards}),
        types=sorted({card["supertype"] for card in all_cards}),
        counts=dict(
            species=len(visible_species), printings=len(visible_cards), indexed_species=len(by_species)
        ),
    )


def pack_lookup(raw, filters=None, expansion=""):
    scope = lookup.request(raw)
    if scope["goal"] or scope["scope"] != "all":
        raise ValueError(
            "Sign in to use a saved goal or missing-only lookup. Public lookup covers all selected Pokémon."
        )
    numbers = (
        [int(number) for number in scope["targets"].split(",")] if scope["targets"] else list(range(1, 252))
    )
    catalog = entries()
    if scope["printing"]:
        printing = next((row for row in catalog if row["id"] == scope["printing"]), None)
        if not printing or not broad_goals.eligible(printing, 251):
            raise ValueError("Choose a currently published printing with a canonical Pokémon identity.")
        numbers = [printing["attributes"]["pokemon_dex"]]
    selected, references = broad_goals.reviewed(catalog, 251)
    items = broad_goals.species_items(selected, numbers, frozen_labels=False)
    if scope["printing"]:
        for item in items:
            item["printing_ids"] = [key for key in item["printing_ids"] if key == scope["printing"]]
    for item in items:
        item["status"] = "indexed" if item["printing_ids"] else "unavailable"
    definition = dict(catalog_references=references)
    filters = offer_filters.validate(filters)
    result = dict(
        public=True,
        lookup=True,
        supported=True,
        research_enabled=False,
        lookup_goals=[],
        lookup_request=scope,
        goal=dict(name="Selected Pokémon" if len(numbers) < 251 else "Original 251"),
        progress=dict(total=len(items), unavailable=sum(not item["printing_ids"] for item in items)),
        missing=items,
        species="",
        expansion=expansion,
        expansions=[],
        limitations=[],
        offer_filters=filters,
    )
    return packs.project_evidence(
        result, definition, items, {row["id"] for row in catalog}, expansion, filters=filters
    )
