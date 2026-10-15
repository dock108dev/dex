"""Private, read-only identification thumbnails for owned vintage cards.

These are reference scans, never photographs or verification of the owner's
copies. Fair use is the owner's selected basis, not a provider artwork license.
No image bytes are fetched, saved, exported or added to the public catalog here.
"""

import re

from django.conf import settings

from . import collection as collection
from . import effective_collection, store
from . import ownership_declarations as declarations

# Explicit English set identities; never infer an image from species alone.
SETS = {
    "Base Set": ("base", "base1"),
    "Jungle": ("base", "base2"),
    "Fossil": ("base", "base3"),
    "Base Set 2": ("base", "base4"),
    "Team Rocket": ("base", "base5"),
    "Wizards Black Star Promos": ("base", "basep"),
    "Gym Heroes": ("gym", "gym1"),
    "Gym Challenge": ("gym", "gym2"),
    "Neo Genesis": ("neo", "neo1"),
    "Neo Discovery": ("neo", "neo2"),
    "Neo Revelation": ("neo", "neo3"),
    "Neo Destiny": ("neo", "neo4"),
}


def thumbnail(set_name, name, number, catalog):
    """Require a literal number and matching English catalog card name/set."""
    if set_name not in SETS or not isinstance(number, str) or not re.fullmatch(r"[1-9][0-9]{0,2}", number):
        return None
    matches = [
        p
        for p in catalog
        if p["set_name"] == set_name
        and p["collector_number"] == number
        and p.get("language") == "en"
        and declarations.normalized_name(p["name"]) == declarations.normalized_name(name)
    ]
    if not matches:
        return None
    series, key = SETS[set_name]
    return f"https://assets.tcgdex.net/en/{series}/{key}/{number}/low.webp"


def owned_cards(who, *, catalog=None, active=None, effective=None):
    """Artwork consumes the authorized current presence projection."""
    store.verified(who)
    if getattr(settings, "STAGING", False):
        return []
    if catalog is None:
        catalog = collection.catalog(who, include_archived=True)
    effective = checked_effective(who, catalog=catalog, active=active, effective=effective)
    from .image_bindings import catalog_images

    mapped = catalog_images(who, catalog)

    def reference(row):
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
        if r["present"] and r["set_name"] in SETS
    ]
    order = {name: i for i, name in enumerate(SETS)}
    return sorted(
        cards,
        key=lambda r: (
            order[r["set_name"]],
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


def reference_for(set_name, name, number, images):
    return next(
        (
            r
            for r in images
            if r["set_name"] == set_name
            and r["number"] == number
            and declarations.normalized_name(r["name"]) == declarations.normalized_name(name)
        ),
        None,
    )


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
