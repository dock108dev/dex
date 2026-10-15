"""Private, read-only identification thumbnails for reviewed owned cards.

These are reference scans, never photographs or verification of the owner's
copies. Fair use is the owner's selected basis, not a provider artwork license.
No image bytes are fetched, saved, exported or added to the public catalog here.
"""

from . import collection as collection
from . import effective_collection, image_bindings, store

# Retain the established presentation order; image identities belong to image_mappings.
DISPLAY_SET_ORDER = (
    "Base Set",
    "Jungle",
    "Fossil",
    "Base Set 2",
    "Team Rocket",
    "Wizards Black Star Promos",
    "Gym Heroes",
    "Gym Challenge",
    "Neo Genesis",
    "Neo Discovery",
    "Neo Revelation",
    "Neo Destiny",
    "Plasma Storm",
    "Mysterious Treasures",
    "Call of Legends",
    "Diamond & Pearl",
    "Dark Explorers",
    "EX Trainer Kit 2 — Minun",
)


def owned_cards(who, *, catalog=None, active=None, effective=None):
    """Artwork consumes the authorized current presence projection."""
    store.verified(who)
    if not image_bindings.enabled():
        return []
    if catalog is None:
        catalog = collection.catalog(who, include_archived=True)
    effective = checked_effective(who, catalog=catalog, active=active, effective=effective)
    mapped = image_bindings.catalog_images(who, catalog)

    def reference(row):
        if not row["printing_ids"]:
            from .image_mappings import declared_card_reference

            return declared_card_reference(row)["image_url"]
        candidates = {
            mapped[key]["image_url"]
            for key in row["printing_ids"]
            if key in mapped
            and mapped[key]["name"] == row["name"]
            and mapped[key]["set_name"] == row["set_name"]
            and mapped[key]["number"] == row["number"]
        }
        return next(iter(candidates)) if len(candidates) == 1 else None

    cards = [
        dict(
            set_name=r["set_name"],
            name=r["name"],
            number=r["number"],
            pokemon_dex=r["pokemon_dex"],
            declared=r["declared"],
            copies=r["recorded_copy_count"],
            image_url=reference(r),
        )
        for r in effective["cards"]
        if r["present"]
    ]
    order = {name: i for i, name in enumerate(DISPLAY_SET_ORDER)}
    return sorted(
        cards,
        key=lambda r: (
            order.get(r["set_name"], len(order)),
            r["set_name"],
            int(r["number"]) if r["number"] and r["number"].isdigit() else 0,
            r["number"] or "",
            r["name"],
        ),
    )


def reference_images(who, **kwargs):
    return [
        {k: r[k] for k in ("name", "set_name", "number", "image_url", "pokemon_dex")}
        for r in owned_cards(who, **kwargs)
        if r["image_url"]
    ]


def checked_effective(who, *, catalog=None, active=None, effective=None):
    """An overlay is evidence only when equal to a fresh authorized projection."""
    store.verified(who)
    if effective is not None and effective.get("user_id") != who.user_id:
        raise ValueError("Artwork projection must belong to the current account")
    generation = collection.generation(who)
    current = effective_collection.project(who, catalog=catalog, active=active)
    if effective is not None and effective != current:
        raise ValueError("Artwork projection differs from the current authorized collection")
    store.verified(who)
    if collection.generation(who) != generation:
        raise collection.Conflict("Collection changed while binding artwork; reload")
    return current
