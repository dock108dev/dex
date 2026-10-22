"""Authorized image adapters. No descriptor grants access or establishes possession."""

from urllib.parse import quote

from django.conf import settings

from . import collection, store


def enabled():
    return not getattr(settings, "STAGING", False)


def catalog_images(actor, catalog):
    """Bind all supported private catalog references regardless of possession."""
    actor = store.verified(actor)
    generation = collection.generation(actor)
    authoritative = collection.catalog(actor, include_archived=True)
    by_id = {row["id"]: row for row in authoritative}
    if any(by_id.get(row["id"]) != row for row in catalog):
        raise ValueError("Image catalog differs from authorized metadata")
    if not enabled():
        return {}
    from . import card_groups, image_mappings

    game_ids = {row["id"] for row in store.rows("SELECT id FROM games WHERE game_key='pokemon'")}
    requested = {row["id"] for row in catalog}
    # Keep every sibling in a requested identity group so collisions and variant
    # ambiguity retain their ordinary checks. Unrelated groups need no images.
    keys = {
        tuple(row.get(key) for key in ("game_id", "set_id", "language", "collector_number"))
        for row in catalog
    }
    relevant = [
        row
        for row in authoritative
        if tuple(row.get(key) for key in ("game_id", "set_id", "language", "collector_number")) in keys
    ]
    built = card_groups.build_groups(relevant, pokemon_game_ids=game_ids)
    result = {}
    for group in built["groups"]:
        descriptor = image_mappings.card_group_reference(group, group["_children"], pokemon_game_ids=game_ids)
        descriptor = dict(
            descriptor,
            name=group["name"],
            set_name=group["set_name"],
            number=group["collector_number"],
            pokemon_dex=group["pokemon_dex"],
        )
        for child in group["_children"]:
            if child["id"] in requested:
                result[child["id"]] = descriptor
    store.verified(actor)
    if collection.generation(actor) != generation:
        raise collection.Conflict("Collection changed while binding images; reload")
    return result


def private_copy_photos(actor, copy_ids):
    """Read actual job/photo associations; provisional JSON and paths are ignored."""
    actor = store.verified(actor)
    generation = collection.generation(actor)
    keys = set(copy_ids)
    result = {key: [] for key in keys}
    if not getattr(settings, "B3_ENABLED", False):
        return result
    from .scans import authorized_photo_rows

    # One scoped query independent of the number of displayed copies.
    for row in authorized_photo_rows(actor):
        if row["copy_id"] not in keys:
            continue
        result[row["copy_id"]].append(
            dict(
                role="private_copy_photo",
                bound_identity=dict(copy_id=row["copy_id"], photo_id=row["id"]),
                precision="physical_copy_photo",
                availability="reference",
                image_url=f"/scan-photos/{quote(row['id'], safe='')}/",
                width=320,
                height=320,
                dimensions_basis="display_box; intrinsic_dimensions_unavailable",
                alt="Your saved copy photo",
                source_id="authorized-private-scan",
                reason=None,
            )
        )
    store.verified(actor)
    if collection.generation(actor) != generation:
        raise collection.Conflict("Collection changed while binding photos; reload")
    return result
