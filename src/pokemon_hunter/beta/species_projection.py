"""Thin current/saved species reads; canonical identity and existing policies own truth."""

from django.http import Http404

from . import (
    canonical_species,
    card_groups,
    collection,
    collection_goals,
    effective_collection,
    image_bindings,
    image_mappings,
    ownership_declarations,
    public_catalog,
    store,
)

FILTERS = {"q", "region", "goal", "owned", "set", "era", "type", "rarity", "card", "gaps"}
LIST_STATE = FILTERS | {"scroll", "focus", "selecting"}


def filters(raw):
    if set(raw) - FILTERS:
        raise ValueError("Choose supported Pokémon filters")
    values = {key: raw.get(key, "") for key in FILTERS}
    if any(
        not isinstance(value, str)
        or len(value) > 160
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
        for value in values.values()
    ):
        raise ValueError("Choose shorter Pokémon filters")
    values["region"] = {"all": "", "1": "kanto", "2": "johto"}.get(values["region"], values["region"])
    if values["region"] not in {"", "kanto", "johto"}:
        raise ValueError("Choose Kanto or Johto")
    if values["owned"] not in {"", "all", "owned", "missing"}:
        raise ValueError("Choose Collected or Not collected")
    if values["gaps"] not in {"", "true", "false"}:
        raise ValueError("Choose whether to keep metadata gaps visible")
    values["owned"] = values["owned"] or "all"
    values["gaps"] = values["gaps"] or "true"
    return values


def list_state(raw):
    """Validate UI-only fields independently of the read service's filter contract."""
    if set(raw) - LIST_STATE:
        raise ValueError("Choose supported Pokédex context")
    filters({key: value for key, value in raw.items() if key in FILTERS})
    for key, minimum, maximum in (("scroll", 0, 10000000), ("focus", 1, 251)):
        if key in raw:
            card_groups._integer(raw[key], key, minimum, maximum)
    if "selecting" in raw and raw["selecting"] != "1":
        raise ValueError("Choose a supported selection mode")
    return raw


def require_dex(dex):
    if type(dex) is not int or not 1 <= dex <= 251:
        raise Http404
    return dex


def _scope(actor, goal_id):
    scope = dict(
        kind="current",
        goal_id=None,
        name="Current collection",
        units="species",
        supported=True,
        membership=list(range(1, 252)),
        goals_url="/goals/",
    )
    if not goal_id:
        return scope, None
    try:
        found = collection.goals(actor, goal_id=goal_id, include_updates=False)
    except (Http404, ValueError) as error:
        raise ValueError("This saved goal is unavailable. Choose another goal in Goals.") from error
    if len(found) != 1:
        raise ValueError("This saved goal is unavailable. Choose another goal in Goals.")
    goal = found[0]
    scope.update(goal_id=goal_id, name=goal["name"], revision=goal["revision"], version=goal["version"])
    definition = goal["definition"]
    # Explicit frozen species membership is authoritative; catalog attributes cannot rebuild it.
    supported_policy = goal["kind"] in collection_goals.KINDS or (
        goal["kind"] == "filtered" and definition.get("filters", {}).get("completion") == "species"
    )
    if not supported_policy or definition.get("policy") != "species":
        units = "species" if definition.get("policy") == "species" else "printings"
        scope.update(
            kind="unsupported_goal" if units == "species" else "printing_goal",
            units=units,
            supported=False,
            membership=[],
        )
    else:
        membership = [item.get("pokemon_dex") for item in definition["items"]]
        if any(type(number) is not int or not 1 <= number <= 251 for number in membership) or len(
            set(membership)
        ) != len(membership):
            raise ValueError("This saved goal has unsupported species membership. Review it in Goals.")
        scope.update(
            kind="saved_declaration"
            if goal["kind"] in collection_goals.OWNERSHIP_KINDS
            else "qualified_species",
            membership=membership,
        )
    return scope, goal


def project(actor, raw=None):
    """Fresh account/generation checked projection, with no parity/valuation dependency."""
    raw = dict(raw or {})
    expected = raw.pop("generation", None)
    selected = filters(raw)
    actor = store.verified(actor)
    generation = collection.generation(actor)
    if expected is not None:
        value = card_groups._integer(expected, "collection generation", 0, 10**18)
        if value != generation:
            raise collection.Conflict("Collection changed; reload the Pokémon view")
    effective = effective_collection.project(actor)
    scope, goal = _scope(actor, selected["goal"])
    catalog = collection.catalog(actor, include_archived=True)
    cards = public_catalog.cards(catalog)
    pokemon_games = {row["id"] for row in store.rows("SELECT id FROM games WHERE game_key='pokemon'")}
    allowed_ids = {row["id"] for row in catalog if row["game_id"] in pokemon_games}
    cards = [row for row in cards if row["id"] in allowed_ids and row["supertype"] == "Pokémon"]
    if goal and scope["supported"]:
        frozen_ids = {key for item in goal["definition"]["items"] for key in item["printing_ids"]}
        cards = [row for row in cards if row["id"] in frozen_ids]
    by_species = {}
    for card in cards:
        if card["pokemon_dex"]:
            by_species.setdefault(card["pokemon_dex"], []).append(
                dict(
                    set=card["set_id"],
                    set_name=card["set_name"],
                    era=card["era"],
                    type=card["supertype"],
                    rarity=card["rarity"],
                    card=f"{card['name']} {card['collector_number']}",
                )
            )
    # Effective declarations contribute only their retained literal metadata, never a fabricated printing.
    sets_by_name = {}
    for row in catalog:
        sets_by_name.setdefault(row["set_name"], set()).add(row["set_id"])
    declaration_rows = effective["declaration_rows"]
    if goal and scope["kind"] == "saved_declaration":
        source = collection_goals.source(actor, goal["definition"]["collection_source"]["id"])
        declaration_rows = ownership_declarations.parse(source["source_text"], source["source_sha256"])
    for row in declaration_rows:
        set_name = row.get("source_set") or "Unknown"
        matching_sets = sets_by_name.get(set_name, set())
        set_id = next(iter(matching_sets)) if len(matching_sets) == 1 else set_name
        by_species.setdefault(row["pokemon_dex"], []).append(
            dict(
                set=set_id,
                set_name=set_name,
                era="Unknown",
                type="Pokémon",
                rarity=row.get("declared_rarity") or "Unknown",
                card=row.get("source_cell") if effective_collection.declared_cards(row) else "Unknown",
            )
        )
    registry = canonical_species.registry()
    goal_present = (
        {row["pokemon_dex"] for row in goal["progress"] if row.get("status") == "owned"}
        if goal and scope["supported"]
        else set()
    )
    membership = set(scope["membership"]) if scope["supported"] else set(range(1, 252))
    species = []
    for dex in range(1, 252):
        if dex not in membership:
            continue
        current = effective["species"][str(dex)]
        row = dict(
            dex=dex,
            name=registry[dex]["name"],
            region="kanto" if dex <= 151 else "johto",
            url=f"/pokedex/{dex}/",
            current_present=current["present"],
            goal_present=dex in goal_present if goal and scope["supported"] else None,
            details_needed=bool(current["present"] and current["unresolved"]),
            species_quantity=None,
        )
        row["species_artwork"] = image_mappings.species_artwork(dex) if image_bindings.enabled() else None
        species.append(row)
    region_species = [row for row in species if not selected["region"] or row["region"] == selected["region"]]
    progress = dict(
        satisfied=sum(
            row["goal_present"] if goal and scope["supported"] else row["current_present"]
            for row in region_species
        ),
        total=len(region_species),
        units="species",
    )
    if goal and not scope["supported"]:
        progress = dict(satisfied=goal["satisfied"], total=goal["total"], units=scope["units"])
    current_progress = dict(
        satisfied=sum(row["current_present"] for row in region_species),
        total=len(region_species),
        units="species",
    )
    query = selected["q"].strip().casefold()
    number_query = query.removeprefix("#")

    def matches(row):
        if (
            query
            and query not in row["name"].casefold()
            and not (number_query.isascii() and number_query.isdecimal() and int(number_query) == row["dex"])
        ):
            return False
        present = row["goal_present"] if goal and scope["supported"] else row["current_present"]
        if selected["owned"] == "owned" and not present or selected["owned"] == "missing" and present:
            return False
        keys = ("set", "era", "type", "rarity", "card")
        if not any(selected[key] for key in keys):
            return True
        metadata = by_species.get(row["dex"], [])
        if not metadata:
            return selected["gaps"] == "true"
        return any(
            all(
                not selected[key]
                or selected["gaps"] == "true"
                and card[key] == "Unknown"
                or key == "card"
                and selected[key].casefold() in card[key].casefold()
                or key == "set"
                and selected[key] in {card["set"], card["set_name"]}
                or key != "card"
                and selected[key] == card[key]
                for key in keys
            )
            for card in metadata
        )

    result = dict(
        public=False,
        account_id=actor.user_id,
        generation=generation,
        species=[row for row in region_species if matches(row)],
        filters=selected,
        scope=scope,
        progress=progress,
        current_progress=current_progress,
        sets=sorted(
            {
                row["set"]: dict(id=row["set"], name=row["set_name"])
                for rows in by_species.values()
                for row in rows
                if row["set"] != "Unknown"
            }.values(),
            key=lambda row: (row["name"].casefold(), row["id"]),
        ),
        eras=sorted({row["era"] for rows in by_species.values() for row in rows}),
        types=sorted({row["type"] for rows in by_species.values() for row in rows}),
        rarities=sorted({row["rarity"] for rows in by_species.values() for row in rows}),
    )
    result["filtered_count"] = len(result["species"])
    store.verified(actor)
    if (
        collection.generation(actor) != generation
        or effective["generation"] != generation
        or effective["user_id"] != actor.user_id
    ):
        raise collection.Conflict("Collection changed during Pokémon reading; reload")
    return result
