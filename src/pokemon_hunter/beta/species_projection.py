"""Thin current/saved species reads; canonical identity and existing policies own truth."""

from urllib.parse import urlencode

from django.http import Http404

from . import (
    canonical_species,
    card_groups,
    collection,
    collection_goals,
    effective_collection,
    image_bindings,
    image_mappings,
    public_catalog,
    species_scope,
    store,
)

FILTERS = {"q", "region", "goal", "owned", "gaps"} | species_scope.KEYS
LIST_STATE = FILTERS | {"scroll", "focus", "selecting", "page", "page_size"}


def filters(raw):
    if set(raw) - FILTERS or len(urlencode(raw)) > species_scope.MAX_ENCODED:
        raise ValueError("Choose supported Pokémon filters")
    values = {key: raw.get(key, "") for key in FILTERS}
    if any(
        not isinstance(value, str)
        or len(value) > (species_scope.MAX_FIELD if key in species_scope.MULTI else 160)
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
        for key, value in values.items()
    ):
        raise ValueError("Choose shorter Pokémon filters")
    values.update(species_scope.validate(raw))
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
    if set(raw) - LIST_STATE or len(urlencode(raw)) > 1800:
        raise ValueError("Choose supported Pokédex context")
    filters({key: value for key, value in raw.items() if key in FILTERS})
    for key, minimum, maximum in (
        ("scroll", 0, 10000000),
        ("focus", 1, 251),
        ("page", 1, 2**53 - 1),
        ("page_size", 1, 100),
    ):
        if key in raw:
            card_groups._integer(raw[key], key, minimum, maximum)
    if "selecting" in raw and raw["selecting"] != "1":
        raise ValueError("Choose a supported selection mode")
    return raw


def require_dex(dex):
    if type(dex) is not int or not 1 <= dex <= 251:
        raise Http404
    return dex


def authorize_goal(actor, goal_id, version=None):
    """Shell/link authorization without materializing frozen membership or progress."""
    actor = store.verified(actor)
    rows = store.rows(
        "SELECT version FROM collection_goals WHERE user_id=%s AND id=%s", [actor.user_id, goal_id]
    )
    if not rows:
        raise ValueError("This saved goal is unavailable. Choose another goal in Goals.")
    if version is not None and version != rows[0]["version"]:
        raise collection.Conflict("Saved goal changed; reopen it from Goals")


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
    dates = species_scope.release_dates()
    languages = {row["id"]: row["language"] for row in catalog}
    indexed = {
        card["id"]: species_scope.metadata({**card, "language": languages[card["id"]]}, dates)
        for card in cards
    }
    set_candidates = {}
    for card in cards:
        fact = {key: indexed[card["id"]][key] for key in ("set", "era", "release")}
        set_candidates.setdefault(card["set_name"], {})[(card["set_id"], languages[card["id"]])] = fact
    set_facts = {name: next(iter(rows.values())) for name, rows in set_candidates.items() if len(rows) == 1}
    by_species = {}
    for card in cards:
        if card["pokemon_dex"]:
            by_species.setdefault(card["pokemon_dex"], []).append(indexed[card["id"]])
    owned_by_species, card_states = {}, {}
    restricted = any(selected[key] for key in species_scope.KEYS)
    for evidence in effective["cards"]:
        if not evidence["present"]:
            continue
        rows = (
            species_scope.owned_evidence(evidence, indexed, set_facts)
            if evidence["identity_status"] != "conflict"
            else [{}]
        )
        state = species_scope.classify(rows, selected)
        card_states[evidence["id"]] = state
        owned_by_species.setdefault(evidence["pokemon_dex"], []).extend(rows)
    # Tiles expose canonical group IDs, not internal effective assertion IDs.
    # Use the same complete-child identity join as the authoritative card adapter.
    assertion_states = {
        frozenset(row["printing_ids"]): card_states[row["id"]]
        for row in effective["cards"]
        if row["id"] in card_states and row["printing_ids"] and row["identity_status"] != "conflict"
    }
    grouped = card_groups.build_groups(catalog, pokemon_game_ids=pokemon_games)
    group_states = {
        group["id"]: assertion_states.get(
            frozenset(child["id"] for child in group["_children"]), "unresolved"
        )
        for group in grouped["groups"]
        if frozenset(child["id"] for child in group["_children"]) in assertion_states
    }
    registry = canonical_species.registry()
    goal_present = (
        {row["pokemon_dex"] for row in goal["progress"] if row.get("status") == "owned"}
        if goal and scope["supported"]
        else set()
    )
    membership = set(scope["membership"]) if scope["supported"] else set(range(1, 252))
    species = []
    for dex in sorted(membership):
        current = effective["species"][str(dex)]
        evidence = owned_by_species.get(dex, [])
        if current["unresolved"]:
            evidence = [*evidence, {}]
        state = species_scope.classify(evidence, selected)
        present = current["present"] if not restricted else state == "collected"
        eligible = [species_scope.match(row, selected) for row in by_species.get(dex, [])]
        row = dict(
            dex=dex,
            name=registry[dex]["name"],
            region="kanto" if dex <= 151 else "johto",
            url=f"/pokedex/{dex}/",
            current_present=current["present"],
            scoped_present=present,
            scope_status="collected"
            if present
            else "unresolved"
            if state == "unresolved" or None in eligible
            else "no_indexed"
            if True not in eligible
            else "missing",
            eligible_indexed_printings=sum(value is True for value in eligible),
            goal_present=dex in goal_present if goal and scope["supported"] else None,
            details_needed=bool(current["present"] and current["unresolved"]),
            species_quantity=None,
            species_artwork=image_mappings.species_artwork(dex) if image_bindings.enabled() else None,
        )
        species.append(row)
    region_species = [row for row in species if not selected["region"] or row["region"] == selected["region"]]

    def progress(field):
        return dict(
            satisfied=sum(bool(row[field]) for row in region_species),
            total=len(region_species),
            units="species",
        )

    original_progress = (
        dict(satisfied=goal["satisfied"], total=goal["total"], units=scope["units"])
        if goal
        else progress("current_present")
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
        if (
            selected["owned"] == "owned"
            and not row["scoped_present"]
            or selected["owned"] == "missing"
            and row["scoped_present"]
        ):
            return False
        return True

    result = dict(
        public=False,
        account_id=actor.user_id,
        generation=generation,
        species=[row for row in region_species if matches(row)],
        filters=selected,
        scope=scope,
        progress=original_progress,
        current_progress=progress("current_present"),
        scoped_progress=progress("scoped_present"),
        restricted=restricted,
        scope_cards=card_states,
        scope_groups=group_states,
        coverage=dict(
            indexed_printings=len(indexed),
            dated_printings=sum(bool(r["release"]) for r in indexed.values()),
            unknown_dates=sum(not r["release"] for r in indexed.values()),
            eligible_species=sum(row["eligible_indexed_printings"] > 0 for row in region_species),
            unresolved_species=sum(row["scope_status"] == "unresolved" for row in region_species),
        ),
        date_basis="Retained English release dates; regional and edition release applicability unresolved. Promo-series start dates excluded. Unknown dates do not confirm dated completion.",
        sets=sorted(
            {card["set_id"]: dict(id=card["set_id"], name=card["set_name"]) for card in cards}.values(),
            key=lambda r: (r["name"].casefold(), r["id"]),
        ),
        eras=sorted({card["era"] for card in cards}),
        types=sorted({card["supertype"] for card in cards}),
        rarities=sorted({card["rarity"] for card in cards}),
        finishes=sorted({card["finish"] or "Unknown" for card in cards}),
        years=sorted({row["release"]["start"][:4] for row in indexed.values() if row["release"]}),
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
