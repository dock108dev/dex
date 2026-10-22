"""Image-led local Shopping search over the checked collection/card services.

These reads never acquire provider content, choose a child printing, or obtain prices.
"""

import re
import uuid

from . import (
    canonical_species,
    card_groups,
    collection,
    image_bindings,
    image_mappings,
    lot_calculator,
    shopping_context,
)

PAGE_FIELDS = shopping_context.FIELDS | {
    "run_id",
    "q",
    "set_id",
    "intent",
    "missing_basis",
    "scope",
    "budget",
    "product_type",
    "sort",
    "english_vintage",
    "result_filter",
    "scroll",
    "focus",
}
CATALOG_FIELDS = shopping_context.FIELDS | {"q", "set_id", "intent", "missing_basis", "scope", "offset"}


def validate_page(raw):
    """Finite UI state; provider summaries, prices and seller text never enter URLs."""
    if set(raw) - PAGE_FIELDS:
        raise ValueError("Choose supported Shopping search fields")
    for key, value in raw.items():
        if not isinstance(value, str) or len(value) > (4096 if key == "return" else 200):
            raise ValueError("Choose bounded Shopping search fields")
        if any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("Choose supported Shopping text")
    if raw.get("run_id"):
        uuid.UUID(raw["run_id"])
    for field, options in (
        ("intent", {"deals", "missing"}),
        ("missing_basis", {"species", "printing"}),
        ("scope", {"all", "kanto", "johto", "rares", "bulk"}),
        ("product_type", {"singles", "mixed_lots", "both"}),
        ("sort", {"best_match", "ending_soonest"}),
        ("english_vintage", {"0", "1"}),
        ("result_filter", {"all", "below", "conditional", "unpriced"}),
    ):
        if field in raw and raw[field] not in options:
            raise ValueError("Choose a supported Shopping option")
    if "scroll" in raw:
        card_groups._integer(raw["scroll"], "scroll position", 0, 10000000)
    if "focus" in raw and not re.fullmatch(
        r"(?:discovery-[a-z-]+|catalog-[a-zA-Z0-9-]+|offer-[a-zA-Z0-9_-]+)", raw["focus"]
    ):
        raise ValueError("Choose a supported Shopping focus")
    return raw


def _normal(value):
    return " ".join(re.findall(r"[\w]+", value.casefold()))


def query_parts(query, sets):
    """Recognize longest set aliases first, so Base and Base 2 never overlap."""
    normalized = _normal(query)
    aliases = []
    for row in sets:
        names = {_normal(row["name"])}
        if row["name"] == "Base Set":
            names.add("base")
        if row["name"] == "Base Set 2":
            names.update({"base 2", "base set2", "base2"})
        aliases.extend((name, row["id"]) for name in names if name)
    for alias, key in sorted(aliases, key=lambda item: (-len(item[0]), item[0])):
        match = re.search(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", normalized)
        if match:
            return (normalized[: match.start()] + " " + normalized[match.end() :]).strip(), key
    return normalized, None


def search(who, raw):
    if set(raw) - CATALOG_FIELDS:
        raise ValueError("Choose supported local search fields")
    validate_page({key: value for key, value in raw.items() if key != "offset"})
    offset = card_groups._integer(raw.get("offset", "0"), "local search offset", 0, 100000)
    context = shopping_context.resolve(
        who, {key: value for key, value in raw.items() if key in shopping_context.FIELDS}
    )
    snapshot = card_groups.project(who)
    available = [row for row in snapshot["groups"] if row["catalog_available"]]
    set_pairs = {(row["set_id"], row["set_name"]) for row in available}
    sets = [
        dict(id=key, name=name)
        for key, name in sorted(set_pairs, key=lambda item: (item[1].casefold(), item[0]))
    ]
    query = raw.get("q", "")
    # Catalogs may record a numerator alone. Keep their literal identity unchanged;
    # search the numerator and visibly explain that the printed total is unverified.
    number_query, fractions = re.subn(r"(?<!\w)(\d{1,4})\s*/\s*\d{1,4}(?!\w)", r"\1", query)
    words, inferred_set = query_parts(number_query, sets)
    selected_set = raw.get("set_id") or inferred_set
    if selected_set:
        selected = [row for row in sets if selected_set in {row["id"], row["name"]}]
        if not selected:
            raise ValueError("Choose a supported catalog set")
        selected_set = selected[0]["id"]
    missing = raw.get("intent") == "missing" or context["kind"] in {"missing", "goal"}
    allowed = None
    goal_missing_species = None
    if context["query"].get("goal"):
        allowed, _ = lot_calculator.missing_choices(who, context["query"]["goal"])
        goal = collection.goals(who, goal_id=context["query"]["goal"], include_updates=False)[0]
        goal_missing_species = {
            item.get("pokemon_dex") for item in goal["progress"] if item["status"] != "owned"
        }
    elif missing and raw.get("missing_basis", "species") == "species":
        allowed, _ = lot_calculator.current_missing_choices(who)
    elif missing:
        allowed = {
            child["id"]
            for row in available
            for child in row["_children"]
            if child["id"] not in row["exact_printing_owned_ids"]
        }
    if context["kind"] in {"group", "printing"}:
        available = [row for row in available if row["id"] == context["group"]]
    if context.get("child"):
        allowed = (allowed if allowed is not None else set(context["printing_ids"])) & {context["child"]}
    tokens = words.split()
    scope = raw.get("scope", "kanto" if missing and not context["query"].get("goal") else "all")
    matches = []
    for row in available:
        if selected_set and row["set_id"] != selected_set:
            continue
        if context.get("species") and row["pokemon_dex"] != context["species"]:
            continue
        if scope in {"kanto", "johto"} and not (
            type(row["pokemon_dex"]) is int
            and (1 <= row["pokemon_dex"] <= 151 if scope == "kanto" else 152 <= row["pokemon_dex"] <= 251)
        ):
            continue
        if allowed is not None and not allowed.intersection(row["_published_ids"]):
            continue
        if scope == "rares" and not any(
            "rare" in child.get("attributes", {}).get("rarity", "").casefold() for child in row["_children"]
        ):
            continue
        if scope == "bulk" and not any(
            child.get("attributes", {}).get("rarity", "").casefold() in {"common", "uncommon"}
            for child in row["_children"]
        ):
            continue
        haystack = _normal(" ".join((row["name"], row["collector_number"])))
        if tokens and not all(
            token in haystack.split()
            if token.isdecimal()
            else any(token in word for word in haystack.split())
            for token in tokens
        ):
            continue
        matches.append(row)
    registry = canonical_species.registry()
    broad = [
        number
        for number, species in registry.items()
        if number <= 251 and words and _normal(species["name"]) == words
    ]
    mode = (
        "species"
        if broad and not selected_set and not context.get("species") and not context.get("group")
        else "cards"
    )
    if mode == "species":
        rows = []
        for number in broad:
            groups = [row for row in matches if row["pokemon_dex"] == number]
            current = snapshot["effective"]["species"][str(number)]
            if missing and not context["query"].get("goal") and (number > 151 or current["present"]):
                continue
            if goal_missing_species is not None and number not in goal_missing_species and not groups:
                continue
            if scope == "kanto" and number > 151 or scope == "johto" and number <= 151:
                continue
            rows.append(
                dict(
                    dex=number,
                    name=registry[number]["name"],
                    current_present=current["present"],
                    matching_cards=len(groups),
                    species_artwork=image_mappings.species_artwork(number)
                    if image_bindings.enabled()
                    else None,
                )
            )
    else:
        rows = [card_groups._summary(row, True) for row in matches[offset : offset + 40]]
        for row in rows:
            row["selected_child"] = context.get("child") if row["id"] == context.get("group") else None
    shopping_context.finish(who, context)
    card_groups._finish_read(snapshot, who)
    selected_group = next((row for row in available if row["id"] == context.get("group")), None)
    variants = (
        [
            dict(
                id=child["id"],
                label=child.get("variant_label")
                or " · ".join(
                    filter(None, [child.get("edition"), child.get("finish"), child.get("variant")])
                ),
                available=child["id"] in selected_group["_published_ids"],
            )
            for child in selected_group["_children"]
        ]
        if selected_group
        else []
    )
    return dict(
        mode=mode,
        results=rows,
        total=len(rows) if mode == "species" else len(matches),
        offset=offset,
        has_more=mode == "cards" and offset + 40 < len(matches),
        sets=sets,
        applied_set_id=selected_set,
        variants=variants,
        context=context,
        generation=snapshot["generation"],
        number_note="Matches use the number before /. Confirm full numbering and set in each result."
        if fractions
        else "",
    )


def entry_refinements(who, raw, context):
    """Map checked collection UI scope to one set, without inventing provider filters."""
    from urllib.parse import parse_qsl, urlsplit

    from . import species_scope

    inherited = {}
    destination = context["return_url"]
    for _ in range(7):
        if not destination:
            break
        parts = urlsplit(destination)
        fields = dict(parse_qsl(parts.query, keep_blank_values=True))
        if parts.path in {"/pokedex/", "/cards/", "/card-library/"}:
            # Nearest supported set wins; broader criteria still need explaining.
            for key, value in fields.items():
                if (
                    value
                    and key not in inherited
                    and key in species_scope.KEYS | {"language", "edition", "variant"}
                ):
                    inherited[key] = value
        destination = fields.get("return", "")
    notes = []
    selected = species_scope.values(inherited.get("set", ""))
    # No inherited collection set needs a full ownership/group projection.
    # Use the same published catalog authority only when a set must be mapped.
    sets = {(row["set_id"], row["set_name"]) for row in collection.catalog(who)} if selected else set()
    mapped = next((name for key, name in sets if len(selected) == 1 and selected[0] in {key, name}), None)
    initial = dict(raw)
    if mapped:
        initial.setdefault("set_id", mapped)
        if initial["set_id"] not in {mapped, selected[0]}:
            notes.append("The selected card/search set replaces the original collection set.")
    elif selected:
        notes.append(
            "Shopping uses one supported set at a time. The original multiple or unavailable sets "
            "are not applied to this search."
        )
    unsupported = set(inherited) - {"set"}
    if unsupported:
        notes.append(
            "Other collection card filters are not applied in Shopping. "
            "Search words and Shopping choices define this search."
        )
    if notes:
        notes.append("Back retains your original collection filters.")
    return initial, " ".join(notes)
