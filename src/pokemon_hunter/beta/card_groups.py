"""Stable display identities above immutable catalog/copy records, with checked reads."""

import hashlib
import json
from urllib.parse import urlencode

from django.http import Http404

from . import collection, collection_intents, effective_collection, public_catalog, store
from .ownership_declarations import normalized_name

NAMESPACE = "dg1-"
FILTERS = {
    "scope",
    "generation",
    "q",
    "set",
    "language",
    "edition",
    "finish",
    "variant",
    "species",
    "page",
    "page_size",
    "sort",
}
PRIVATE_SUMMARY = (
    "present",
    "established_total_quantity",
    "recorded_copy_count",
    "current_copy_count",
    "exact_variant_count",
)
PRIVATE_DETAIL = ("recorded_copy_ids", "current_copy_ids", "exact_printing_owned_ids", "assertion_id")
IDENTITY_FIELDS = ("game_id", "set_id", "language", "collector_number", "name")
SUMMARY_FIELDS = (
    "id",
    "url",
    "game_id",
    "set_id",
    "set_name",
    "language",
    "name",
    "collector_number",
    "pokemon_dex",
    "identity_status",
    "variant_count",
    "published_variant_count",
    "catalog_available",
)


def canonical_url(group_id, selected_child=None):
    return f"/card-groups/{group_id}/" + (
        "?" + urlencode({"child": selected_child}) if selected_child else ""
    )


def _species(row, pokemon_game_ids=None):
    attributes = row.get("attributes") or {}
    if attributes.get("supertype") != "Pokémon" or (
        pokemon_game_ids is not None and row.get("game_id") not in pokemon_game_ids
    ):
        return None
    value = attributes.get("pokemon_dex")
    return value if type(value) is int and value > 0 else None


def build_groups(rows, *, pokemon_game_ids=None):
    """Pure catalog grouping; input rows are reviewed internal catalog metadata.

    Literal IDs/text never normalize into a group. A normalized-name collision
    detects contradictory spellings, but does not select one of them.
    """
    buckets, unresolved, groups, printing_to_group = {}, [], [], {}
    unique = {}
    for row in rows:
        printing_id = row.get("id")
        if printing_id in unique and unique[printing_id] != row:
            unresolved.append(dict(kind="duplicate-printing-identity", printing_ids=[printing_id]))
            unique[printing_id] = None
        elif printing_id not in unique:
            unique[printing_id] = row
    for row in unique.values():
        if row is None:
            continue
        missing = [
            field
            for field in (*IDENTITY_FIELDS, "set_name", "id")
            if not isinstance(row.get(field), str)
            or not row[field].strip()
            or row[field] != row[field].strip()
        ]
        fields = set(row.get("unresolved_fields") or [])
        blocked = fields.intersection(
            {
                "game",
                "game_id",
                "set",
                "set_id",
                "language",
                "number",
                "collector_number",
                "name",
                "pokemon_dex",
            }
        )
        if missing or blocked or row.get("name") == "Unidentified card":
            unresolved.append(
                dict(
                    kind="incomplete-catalog-identity",
                    printing_ids=[row.get("id")],
                    missing_fields=sorted(set(missing) | blocked),
                    label=f"{row.get('set_name', 'Unknown set')} · {row.get('name', 'Unknown card')} #{row.get('collector_number') or '?'}",
                )
            )
            continue
        key = tuple(row[field] for field in ("game_id", "set_id", "language", "collector_number"))
        buckets.setdefault(key, []).append(row)
    for children in buckets.values():
        names = {row["name"] for row in children}
        species = {_species(row, pokemon_game_ids) for row in children}
        set_names = {row["set_name"] for row in children}
        if len(names) != 1 or len(species) != 1 or len(set_names) != 1:
            unresolved.append(
                dict(
                    kind="catalog-identity-conflict",
                    printing_ids=sorted(row["id"] for row in children),
                    label="Conflicting name, species or set evidence; review this card identity",
                    identities=[
                        {field: row.get(field) for field in (*IDENTITY_FIELDS, "set_name")}
                        | {"pokemon_dex": _species(row, pokemon_game_ids)}
                        for row in sorted(children, key=lambda row: row["id"])
                    ],
                )
            )
            continue
        first = children[0]
        identity = [first[field] for field in IDENTITY_FIELDS] + [_species(first, pokemon_game_ids)]
        encoded = json.dumps(identity, ensure_ascii=False, separators=(",", ":"))
        group_id = NAMESPACE + hashlib.sha256(encoded.encode()).hexdigest()
        groups.append(
            dict(
                id=group_id,
                url=canonical_url(group_id),
                **{field: first[field] for field in IDENTITY_FIELDS},
                set_name=first["set_name"],
                pokemon_dex=_species(first, pokemon_game_ids),
                identity_status="resolved",
                _children=sorted(children, key=lambda row: row["id"]),
            )
        )
        printing_to_group.update({row["id"]: group_id for row in children})
    groups.sort(
        key=lambda row: (
            row["set_name"].casefold(),
            row["collector_number"],
            row["name"].casefold(),
            row["id"],
        )
    )
    return dict(
        groups=groups,
        unresolved=sorted(unresolved, key=lambda row: json.dumps(row, sort_keys=True)),
        printing_to_group=printing_to_group,
    )


def alias_inventory(rows):
    """All supported child destinations; duplicate aliases stay explicit."""
    aliases = {}
    for row in rows:
        provenance = row.get("provenance") or {}
        if isinstance(provenance, str):
            provenance = json.loads(provenance)
        for alias in (row["id"], "catalog-" + row["id"], provenance.get("legacy_id")):
            if isinstance(alias, str) and alias:
                aliases.setdefault(alias, set()).add(row["id"])
    return {key: sorted(value) for key, value in sorted(aliases.items())}


def _finish_read(snapshot, actor):
    if snapshot["public"]:
        if actor is not None:
            raise ValueError("Public projection cannot be reused as a private collection")
        return
    actor = store.verified(actor)
    if snapshot["user_id"] != actor.user_id:
        raise ValueError("Projection must belong to the current account")
    if collection.generation(actor) != snapshot["generation"]:
        raise collection.Conflict("Collection changed during grouping; reload the current view")


def project(actor=None):
    """Private projection is fresh, account bound and checked before/after reading."""
    if actor is None:
        published = public_catalog.entries()
        rows, effective, generation = published, None, None
        active = []
    else:
        actor = store.verified(actor)
        generation = collection.generation(actor)
        rows = collection.catalog(actor, include_archived=True)
        active = collection.copies(actor)
        effective = effective_collection.project(actor, catalog=rows, active=active)
        published = collection.catalog(actor)
    published_ids = {row["id"] for row in published}
    pokemon_game_ids = {row["id"] for row in store.rows("SELECT id FROM games WHERE game_key='pokemon'")}
    built = build_groups(rows, pokemon_game_ids=pokemon_game_ids)
    copies_by_printing = {}
    for copy in active:
        copies_by_printing.setdefault(copy.get("printing_id"), []).append(copy)
    mapped_assertions, unresolved = set(), list(built["unresolved"])
    by_literal = {}
    if effective:
        for assertion in effective["cards"]:
            key = (assertion["set_name"], normalized_name(assertion["name"]), assertion["number"])
            by_literal.setdefault(key, []).append(assertion)
    for group in built["groups"]:
        children = group["_children"]
        group.update(
            variant_count=len(children),
            published_variant_count=sum(row["id"] in published_ids for row in children),
            catalog_available=any(row["id"] in published_ids for row in children),
        )
        group["_published_ids"] = published_ids.intersection(row["id"] for row in children)
        if not effective:
            continue
        candidates = by_literal.get(
            (group["set_name"], normalized_name(group["name"]), group["collector_number"]), []
        )
        assertion = candidates[0] if len(candidates) == 1 else None
        child_ids = {row["id"] for row in children}
        mapped = (
            assertion is not None
            and assertion["identity_status"] != "conflict"
            and set(assertion["printing_ids"]) == child_ids
        )
        if mapped:
            mapped_assertions.add(assertion["id"])
        recorded = sorted(
            {copy["id"] for child_id in child_ids for copy in copies_by_printing.get(child_id, [])}
        )
        current = sorted(set(assertion["current_copy_ids"])) if mapped else []
        exact = sorted(child_ids.intersection(assertion["exact_printing_owned_ids"])) if mapped else []
        group.update(
            present=bool(mapped and assertion["present"]),
            established_total_quantity=assertion["established_total_quantity"] if mapped else None,
            recorded_copy_ids=recorded,
            recorded_copy_count=len(recorded),
            current_copy_ids=current,
            current_copy_count=len(current),
            exact_printing_owned_ids=exact,
            exact_variant_count=len(exact),
            assertion_id=assertion["id"] if mapped else None,
        )
        if assertion and not mapped:
            group["identity_status"] = "conflict"
    if effective:
        for assertion in effective["cards"]:
            if assertion["id"] not in mapped_assertions and (
                assertion["present"] or assertion["recorded_copy_ids"] or assertion["conflicts"]
            ):
                unresolved.append(dict(kind="unmapped-collection-card", evidence=assertion))
        seen = set()
        for declaration in effective["declaration_rows"]:
            if not effective_collection.declared_cards(declaration):
                encoded = json.dumps(declaration, sort_keys=True)
                if encoded not in seen:
                    seen.add(encoded)
                    unresolved.append(dict(kind="unresolved-species-mark", evidence=declaration))
        for copy in active:
            if copy.get("printing_id") not in built["printing_to_group"]:
                unresolved.append(dict(kind="unmapped-collection-copy", evidence=copy))
        unresolved.extend(
            dict(kind="effective-collection-conflict", evidence=row) for row in effective["conflicts"]
        )
    from . import image_bindings

    if actor is not None and image_bindings.enabled():
        for group in built["groups"]:
            # Carry checked metadata, not thousands of eager image descriptors.
            # Only the selected page/detail binds references in _summary.
            group["_reference_game_ids"] = pokemon_game_ids
    snapshot = dict(
        public=actor is None,
        generation=generation,
        user_id=actor.user_id if actor else None,
        groups=built["groups"],
        unresolved=unresolved,
        printing_to_group=built["printing_to_group"],
        aliases=alias_inventory(rows),
        active=active,
        effective=effective,
    )
    _finish_read(snapshot, actor)
    return snapshot


def _summary(group, private, detail=False):
    fields = (
        SUMMARY_FIELDS + (PRIVATE_SUMMARY if private else ()) + (PRIVATE_DETAIL if private and detail else ())
    )
    result = {field: group[field] for field in fields}
    if private and "_reference_game_ids" in group:
        from . import image_mappings

        result["reference_image"] = image_mappings.card_group_reference(
            group, group["_children"], pokemon_game_ids=group["_reference_game_ids"]
        )
    return result


def _filters(raw, snapshot):
    raw = dict(raw or {})
    if set(raw) - FILTERS:
        raise ValueError("Unsupported card-group filter")
    if any(not isinstance(value, str) or len(value) > 160 for value in raw.values()):
        raise ValueError("Card-group filters must be short text values")
    if raw.get("scope", "catalog") not in {"catalog", "owned"}:
        raise ValueError("Choose catalog or owned groups")
    if snapshot["public"] and (raw.get("scope") == "owned" or "generation" in raw):
        raise ValueError("Sign in for collection groups")
    if "generation" in raw:
        requested = _integer(raw["generation"], "generation", 0)
        if requested != snapshot["generation"]:
            raise collection.Conflict("Collection generation changed; reload the current view")
    for key, minimum, maximum, default in (
        ("page", 1, None, 1),
        ("page_size", 1, 100, 40),
        ("species", 1, 251, None),
    ):
        raw[key] = _integer(raw[key], key, minimum, maximum) if raw.get(key) else default
    raw.setdefault("sort", "set")
    if raw["sort"] not in {"set", "name", "number"}:
        raise ValueError("Choose set, name or number sorting")
    return raw


def _integer(value, label, minimum, maximum=None):
    if not value.isascii() or not value.isdecimal():
        raise ValueError(f"Choose an integer {label}")
    number = int(value)
    if number < minimum or maximum is not None and number > maximum:
        raise ValueError(f"Choose a supported {label}")
    return number


def _list(snapshot, raw, scope=None):
    filters = _filters(raw, snapshot)
    scope = scope or filters.get("scope", "catalog")
    if scope == "owned" and snapshot["public"]:
        raise ValueError("Sign in for collection groups")
    query = filters.get("q", "").casefold().strip()
    matched, matching_children = [], {}
    for group in snapshot["groups"]:
        if scope == "owned" and not group["present"] or scope == "catalog" and not group["catalog_available"]:
            continue
        if filters.get("species") and group["pokemon_dex"] != filters["species"]:
            continue
        if filters.get("set") and filters["set"] != group["set_id"]:
            continue
        if filters.get("language") and filters["language"] != group["language"]:
            continue
        if (
            query
            and query
            not in " ".join(group[field] for field in ("name", "set_name", "collector_number")).casefold()
        ):
            continue
        children = [
            child
            for child in group["_children"]
            if scope == "owned" or child["id"] in group["_published_ids"]
        ]
        matching = [
            child["id"]
            for child in children
            if all(
                not filters.get(field) or child.get(field) == filters[field]
                for field in ("edition", "finish", "variant")
            )
        ]
        if not matching:
            continue
        if any(filters.get(field) for field in ("edition", "finish", "variant")):
            matching_children[group["id"]] = sorted(matching)
        matched.append(group)
    first_field = {"set": "set_name", "name": "name", "number": "collector_number"}[filters["sort"]]
    matched.sort(
        key=lambda row: (
            row[first_field].casefold(),
            row["set_name"].casefold(),
            row["collector_number"],
            row["name"].casefold(),
            row["id"],
        )
    )
    page, size = filters["page"], filters["page_size"]
    total = len(matched)
    visible = []
    for group in matched[(page - 1) * size : page * size]:
        summary = _summary(group, not snapshot["public"])
        if group["id"] in matching_children:
            summary["matching_child_ids"] = matching_children[group["id"]]
        visible.append(summary)
    return dict(
        public=snapshot["public"],
        generation=snapshot["generation"],
        scope=scope,
        groups=visible,
        total=total,
        page=page,
        page_size=size,
        pages=(total + size - 1) // size,
        unresolved=snapshot["unresolved"] if not snapshot["public"] else snapshot["unresolved"],
    )


def list_groups(actor=None, raw=None, *, view=None):
    snapshot = project(actor)
    result = _list(snapshot, raw, view)
    _finish_read(snapshot, actor)
    return result


def filter_options(actor, raw=None):
    """Complete options for one authorized scope, independent of list pagination.

    This is metadata over the same projection used by list_groups, never a second
    ownership model or a client-side approximation from the current results page.
    Owned scope deliberately includes retained archived identities and children.
    """
    actor = store.verified(actor)
    raw = dict(raw or {})
    if set(raw) - {"scope", "generation"}:
        raise ValueError("Choose only scope and collection generation for filter options")
    snapshot = project(actor)
    filters = _filters(raw, snapshot)
    scope = filters.get("scope", "catalog")
    eligible = [
        group
        for group in snapshot["groups"]
        if (group["present"] if scope == "owned" else group["catalog_available"])
    ]
    sets = {(group["set_id"], group["set_name"]) for group in eligible}
    result = dict(
        public=snapshot["public"],
        generation=snapshot["generation"],
        scope=scope,
        sets=[
            dict(id=key, name=name) for key, name in sorted(sets, key=lambda row: (row[1].casefold(), row[0]))
        ],
        languages=sorted({group["language"] for group in eligible}),
    )
    children = [
        child
        for group in eligible
        for child in group["_children"]
        if scope == "owned" or child["id"] in group["_published_ids"]
    ]
    for field in ("edition", "finish", "variant"):
        result[{"edition": "editions", "finish": "finishes", "variant": "variants"}[field]] = sorted(
            {child[field] for child in children if isinstance(child.get(field), str) and child[field]},
            key=lambda value: (value.casefold(), value),
        )
    _finish_read(snapshot, actor)
    return result


def _group(snapshot, group_id):
    group = next((row for row in snapshot["groups"] if row["id"] == group_id), None)
    if not group or not (
        group["catalog_available"]
        or not snapshot["public"]
        and (group["present"] or group["recorded_copy_count"])
    ):
        raise Http404("Card group unavailable")
    return group


def _variant(row, group, private, metadata):
    variant = dict(metadata)
    variant.update(language=row["language"], available=row["id"] in group["_published_ids"])
    if private:
        variant.update(
            established_total_quantity=None,
            exact_printing_owned=row["id"] in group["exact_printing_owned_ids"],
        )
    return variant


def detail(actor, group_id, selected_child=None):
    snapshot = project(actor)
    group = _group(snapshot, group_id)
    children = (
        group["_children"]
        if not snapshot["public"]
        else [row for row in group["_children"] if row["id"] in group["_published_ids"]]
    )
    metadata = {row["id"]: row for row in public_catalog.cards(children)}
    variants = [_variant(row, group, not snapshot["public"], metadata[row["id"]]) for row in children]
    selected = next((row for row in variants if row["id"] == selected_child), None)
    if selected_child is not None and selected is None:
        raise Http404("Selected child does not belong to this accessible group")
    result = dict(
        public=snapshot["public"],
        generation=snapshot["generation"],
        group=_summary(group, not snapshot["public"], detail=True),
        variants=variants,
        selected_child=selected,
    )
    if not snapshot["public"]:
        child_ids = {row["id"] for row in children}
        result.update(
            copies=[row for row in snapshot["active"] if row.get("printing_id") in child_ids],
            history=store.rows(
                "SELECT * FROM owned_copies WHERE user_id=%s AND state<>'active' ORDER BY id", [actor.user_id]
            ),
            unresolved=[
                row
                for row in snapshot["unresolved"]
                if row.get("kind") == "effective-collection-conflict"
                or child_ids.intersection(row.get("printing_ids", []))
            ],
        )
        result["history"] = [row for row in result["history"] if row.get("printing_id") in child_ids]
        from . import image_bindings, image_mappings

        game_ids = {row["id"] for row in store.rows("SELECT id FROM games WHERE game_key='pokemon'")}
        result["selected_child_image"] = (
            image_mappings.exact_child_artwork(group, selected, children, pokemon_game_ids=game_ids)
            if selected is not None and image_bindings.enabled()
            else None
        )
        photos = image_bindings.private_copy_photos(actor, [row["id"] for row in result["copies"]])
        result["copies"] = [dict(row, photo_references=photos[row["id"]]) for row in result["copies"]]
    _finish_read(snapshot, actor)
    return result


def species(actor, dex, raw=None):
    if type(dex) is not int or not 1 <= dex <= 251:
        raise Http404
    snapshot = project(actor)
    filters = dict(raw or {}, species=str(dex))
    result = dict(
        public=snapshot["public"],
        generation=snapshot["generation"],
        pokemon_dex=dex,
        catalog=_list(snapshot, filters, "catalog"),
    )
    if not snapshot["public"]:
        result["owned"] = _list(snapshot, filters, "owned")
        result["unresolved"] = [
            row for row in snapshot["unresolved"] if (row.get("evidence") or {}).get("pokemon_dex") == dex
        ]
    _finish_read(snapshot, actor)
    return result


def resolve_destination(actor, key, group_id=None):
    snapshot = project(actor)
    if key.startswith(NAMESPACE) and key in snapshot["aliases"]:
        raise collection.ReviewConflict("alias_namespace")
    if key.startswith(NAMESPACE):
        group = _group(snapshot, key)
        if group_id is not None and group_id != key:
            raise Http404("Foreign card group")
        result = dict(group_id=key, url=group["url"], selected_child=None, status="resolved")
    else:
        candidates = snapshot["aliases"].get(key, [])
        if not candidates:
            raise Http404("Card identity unavailable")
        if len(candidates) != 1:
            raise collection.ReviewConflict("alias_ambiguous")
        child = candidates[0]
        resolved_group = snapshot["printing_to_group"].get(child)
        if not resolved_group:
            raise collection.ReviewConflict("identity_unresolved")
        _group(snapshot, resolved_group)
        if group_id is not None and group_id != resolved_group:
            raise Http404("Selected child does not belong to this group")
        result = dict(
            group_id=resolved_group,
            url=canonical_url(resolved_group, child),
            selected_child=child,
            status="resolved",
        )
    _finish_read(snapshot, actor)
    return result


def mutation_request(actor, group_id, kind, request, selected_child=None):
    """Only adapt an authoritative literal scope; collection.preview owns validation."""
    actor = store.verified(actor)
    if not isinstance(request, dict):
        raise ValueError("Supply a collection request object")
    resolved = detail(actor, group_id, selected_child)
    group = resolved["group"]
    if group["identity_status"] != "resolved" or not group["assertion_id"]:
        raise collection.ReviewConflict("identity_edit_unresolved")
    adapted = dict(request)
    literal = dict(
        set_name=group["set_name"],
        name=group["name"],
        number=group["collector_number"],
        language=group["language"],
    )
    if kind in {"mark_owned", "remove_card", "card_quantity", "declaration_correction"}:
        if any(key in adapted and adapted[key] != value for key, value in literal.items()):
            raise ValueError("Group adapter cannot replace the literal card identity")
        adapted = {**adapted, **literal}
        collection_intents.resolve_identity(actor, adapted)
    elif kind in {"add", "photo"}:
        if selected_child is None:
            raise ValueError("Select an exact child printing before adding a copy")
        if "printing_id" in adapted and adapted["printing_id"] != selected_child:
            raise ValueError("Requested printing differs from the selected child")
        adapted["printing_id"] = selected_child
    elif kind in {"remove", "edit", "edition", "resolve"}:
        copies = {row["id"]: row for row in resolved["copies"]}
        copy = copies.get(adapted.get("id"))
        if copy is None:
            raise Http404("Copy does not belong to this card group")
        if selected_child is not None and copy["printing_id"] != selected_child:
            raise ValueError("Copy does not match the selected child")
        if kind == "resolve" and adapted.get("printing_id") not in {
            row["id"] for row in resolved["variants"]
        }:
            raise ValueError("Resolution cannot replace the group identity")
    else:
        raise ValueError("Choose a supported card or copy intent")
    store.verified(actor)
    return adapted
