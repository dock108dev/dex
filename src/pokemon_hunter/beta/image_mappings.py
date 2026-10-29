"""Reviewed, read-only image identities; access policy belongs to checked adapters.

These private-use references never establish possession or variant qualification.
No network, image-byte storage, collection mutation or arbitrary URL input occurs.
"""

import hashlib
import json
from functools import cache
from pathlib import Path

from . import canonical_species, card_groups

MAPPING_FILE = Path(__file__).with_name("data") / "cx04_image_mappings.json"
MAPPING_SHA256 = "3c0f45c18650dd923962f93b486a891c63505dd726d2bdca4ce144783248903d"
GROUP_IDENTITY = (*card_groups.IDENTITY_FIELDS, "set_name", "pokemon_dex")


@cache
def _reviewed():
    raw = MAPPING_FILE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != MAPPING_SHA256:
        raise ValueError("Reviewed image mapping drift; explicit mapping review required")
    data = json.loads(raw)
    # Keep the all-era lookup constant-time; duplicate literal identities fail closed.
    index = {}
    for row in data["cards"]:
        key = tuple(
            row[field] for field in ("set_name", "name", "language", "collector_number", "pokemon_dex")
        )
        index[key] = None if key in index else row
    data["card_index"] = index
    return data


def _descriptor(role, identity, *, alt, precision, image_url=None, source_id=None, reason=None):
    return dict(
        role=role,
        bound_identity=identity,
        precision=precision,
        availability="reference" if image_url else "unavailable",
        image_url=image_url,
        width=475 if role == "species_artwork" else 245,
        height=475 if role == "species_artwork" else 337,
        alt=alt,
        source_id=source_id,
        reason=reason,
    )


def species_artwork(dex):
    """Canonical species only, identical for collected and uncollected Pokémon."""
    if type(dex) is not int or not 1 <= dex <= 251:
        return _descriptor(
            "species_artwork",
            None,
            alt="Pokémon artwork unavailable",
            precision="species",
            reason="outside_reviewed_species_scope",
        )
    canonical = canonical_species.registry()[dex]
    row = next((row for row in _reviewed()["species"] if row["dex"] == dex), None)
    if row is None or row["species_id"] != canonical["id"] or row["name"] != canonical["name"]:
        return _descriptor(
            "species_artwork",
            dict(species_id=canonical["id"], pokemon_dex=dex),
            alt=f"{canonical['name']} artwork unavailable",
            precision="species",
            reason="missing_or_conflicting_species_mapping",
        )
    return _descriptor(
        "species_artwork",
        dict(species_id=canonical["id"], pokemon_dex=dex),
        alt=canonical["name"],
        precision="species",
        image_url=row["image_url"],
        source_id="pokeapi-official-artwork",
    )


def _validated_group(group, catalog, pokemon_game_ids):
    if group.get("game_id") not in pokemon_game_ids or group.get("identity_status") != "resolved":
        return None
    built = card_groups.build_groups(catalog, pokemon_game_ids=pokemon_game_ids)
    return next(
        (
            row
            for row in built["groups"]
            if row["id"] == group.get("id")
            and all(row[field] == group.get(field) for field in GROUP_IDENTITY)
        ),
        None,
    )


def _card_mapping(set_name, name, language, number, pokemon_dex):
    """One literal lookup; missing and duplicate reviewed identities stay unavailable."""
    return _reviewed()["card_index"].get((set_name, name, language, number, pokemon_dex))


def card_group_reference(group, catalog, *, pokemon_game_ids):
    """Literal reviewed identity, independent of possession/publication/child order.

    Callers supply authoritative checked group children or the full checked catalog,
    and game IDs from the reviewed Pokémon game registry, never a client selector.
    """
    identity = {field: group.get(field) for field in ("id", *GROUP_IDENTITY)}
    alt = f"{group.get('name') or 'Card'} · {group.get('set_name') or 'Unknown set'} #{group.get('collector_number') or '?'}"
    validated = _validated_group(group, catalog, pokemon_game_ids)
    row = (
        None
        if validated is None
        else _card_mapping(
            validated["set_name"],
            validated["name"],
            validated["language"],
            validated["collector_number"],
            validated["pokemon_dex"],
        )
    )
    return _descriptor(
        "card_group_reference",
        identity,
        alt=alt,
        precision="card_group",
        image_url=row["image_url"] if row else None,
        source_id="tcgdex-reference" if row else None,
        reason=None if row else "unsupported_or_conflicting_card_identity",
    )


def exact_child_artwork(group, child, catalog, *, pokemon_game_ids):
    """An ordinary set/number URL never proves selected edition/finish depiction."""
    validated = _validated_group(group, catalog, pokemon_game_ids)
    identity = dict(group_id=group.get("id"), printing_id=child.get("id") if child else None)
    if child is None:
        reason = "no_selected_child"
    elif validated is None or child.get("id") not in {row["id"] for row in validated["_children"]}:
        reason = "unsupported_or_conflicting_child_identity"
    elif child.get("available") is False:
        reason = "archived_child"
    else:
        reason = "independent_asset_identity_missing"
    return _descriptor(
        "exact_child_artwork",
        identity,
        alt="Selected variant image unavailable",
        precision="exact_child",
        reason=reason,
    )


def declared_card_reference(assertion):
    """Literal reference for an internal, current declaration without catalog IDs.

    This does not resolve catalog support, language, ownership or exact variants.
    The caller must supply the account-checked effective collection assertion.
    """
    identity = {field: assertion.get(field) for field in ("id", "set_name", "name", "number", "pokemon_dex")}
    row = (
        _card_mapping(
            identity["set_name"], identity["name"], "en", identity["number"], identity["pokemon_dex"]
        )
        if assertion.get("identity_status") != "conflict" and not assertion.get("conflicts")
        else None
    )
    return _descriptor(
        "card_group_reference",
        identity,
        alt=f"{identity['name']} · {identity['set_name']} #{identity['number']} · English card reference",
        precision="declared_card_reference",
        image_url=row["image_url"] if row else None,
        source_id="tcgdex-reference" if row else None,
        reason=None if row else "unsupported_or_conflicting_card_identity",
    )


def indexed_group_reference(group, *, pokemon_game_ids):
    """Descriptor for a digest-checked prepared group, already canonicalized at build.

    Call only after indexed visibility and row integrity checks. Never accept a group
    supplied by a client. This uses the same reviewed literal mapping and source policy
    as card_group_reference, without rebuilding unrelated catalog siblings on GET.
    """
    valid = group.get("game_id") in pokemon_game_ids and group.get("identity_status") == "resolved"
    row = (
        _card_mapping(
            group["set_name"],
            group["name"],
            group["language"],
            group["collector_number"],
            group["pokemon_dex"],
        )
        if valid
        else None
    )
    return _descriptor(
        "card_group_reference",
        {field: group.get(field) for field in ("id", *GROUP_IDENTITY)},
        alt=f"{group.get('name') or 'Card'} · {group.get('set_name') or 'Unknown set'} #{group.get('collector_number') or '?'}",
        precision="card_group",
        image_url=row["image_url"] if row else None,
        source_id="tcgdex-reference" if row else None,
        reason=None if row else "unsupported_or_conflicting_card_identity",
    )
