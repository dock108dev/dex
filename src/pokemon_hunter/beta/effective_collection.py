"""Read-only, account-authorized current presence, separate from copy/goal policy.

A confirmed explicit full-source selection is an ownership boundary. Inherited
copies may describe a declared card but cannot restore ownership omitted there.
Later confirmed copy creations support presence while active; metadata changes
and identity resolution never confer that admission. Recorded copies are not an
attestation of exhaustive quantity. Saved goals do not consume this projection.
"""

import json
import re

from pokemon_hunter.inventory import stable_id

from . import collection, collection_goals, store
from . import ownership_declarations as declarations

SELECTION_KINDS = {"owner_declaration", "collection_correct", "source_select"}
ADDITION_KINDS = {"add", "set", "photo", "import", "bulk"}
CARD_PART = re.compile(r"(?:✓(?:D|EX)? )?([^;#()]+) #([A-Za-z0-9-]+) \(([^()]+)\)")


def declared_cards(row):
    """Literal card assertions only; incomplete/malformed cells remain species evidence."""
    parts = (row.get("source_cell") or "").split(";")
    matches = [CARD_PART.fullmatch(part.strip()) for part in parts]
    if not all(matches):
        return []
    return [dict(name=m[1].strip(), number=m[2], rarity=m[3]) for m in matches]


def _key(set_name, name, number):
    return set_name, declarations.normalized_name(name), number


def _number(value):
    return value if type(value) is int and 1 <= value <= 251 else None


def _json(value, default):
    return json.loads(value) if isinstance(value, str) else value or default


def project(actor, *, catalog=None, active=None, pending=None):
    """Return current broad presence without writes, acquisition or inferred totals.

    `cards` are literal identity assertions, not the canonical display-group API.
    `printings` provide broad presence for known candidates and independent exact
    copy qualification. Neither broad field establishes variant completion.
    """
    actor = store.verified(actor)
    read_generation = collection.generation(actor)
    authoritative_catalog = collection.catalog(actor, include_archived=True)
    catalog_by_id = {p["id"]: p for p in authoritative_catalog}
    if catalog is not None and any(catalog_by_id.get(p["id"]) != p for p in catalog):
        raise ValueError("Catalog projection inputs differ from supported metadata")
    # A filtered/publication-only caller cannot hide current archived identities.
    catalog = authoritative_catalog
    pokemon_games = {r["id"] for r in store.rows("SELECT id FROM games WHERE game_key='pokemon'")}

    def species_number(p):
        if p["game_id"] not in pokemon_games or p["attributes"].get("supertype") in {"Trainer", "Energy"}:
            return None
        return _number(p["attributes"].get("pokemon_dex"))

    authoritative_active = collection.copies(actor)
    active = authoritative_active if active is None else active
    # Optional preloaded records never bypass the account boundary.
    if any(c.get("user_id") != actor.user_id for c in active):
        raise ValueError("Copy projection inputs must belong to the current account")
    if {c["id"]: c for c in active} != {c["id"]: c for c in authoritative_active}:
        raise ValueError("Copy projection inputs differ from the current account records")
    if pending is not None:
        if pending.get("user_id") != actor.user_id or pending.get("generation") != read_generation:
            raise ValueError("Pending projection must belong to this account and current generation")
        simulated = {c["id"]: c for c in active}
        for change in pending["plan"].get("updates", []):
            if change["kind"] == "copy":
                simulated[change["after"]["id"]] = change["after"]
        for change in pending["plan"].get("creates", []):
            if change["kind"] == "copy":
                simulated[change["row"]["id"]] = change["row"]
        for change in pending["plan"].get("deletes", []):
            if change["kind"] == "copy":
                simulated.pop(change["before"]["id"], None)
        active = list(simulated.values())
    active = [c for c in active if c.get("state") == "active"]
    by_id = {p["id"]: p for p in catalog}
    candidates_by_key, copies_by_printing = {}, {}
    for p in catalog:
        candidates_by_key.setdefault(_key(p["set_name"], p["name"], p["collector_number"]), []).append(p)
    for copy in active:
        copies_by_printing.setdefault(copy.get("printing_id"), []).append(copy)
    conflicts = []
    history = store.rows(
        "SELECT * FROM collection_operations WHERE user_id=%s ORDER BY generation,id",
        [actor.user_id],
    )
    for op in history:
        op["plan"] = _json(op["plan"], {})
        op["changes"] = _json(op["changes"], [])
    if pending is not None:
        pending = {**pending, "state": "confirmed"}
        pending["changes"] = (
            [dict(kind=c["kind"], before=None, after=c["row"]) for c in pending["plan"].get("creates", [])]
            + pending["plan"].get("updates", [])
            + [{**c, "after": None} for c in pending["plan"].get("deletes", [])]
        )
        history = [op for op in history if op["id"] != pending["id"]] + [pending]
    from .copy_identity import binding

    history_by_id = {op["id"]: op for op in history}

    def admitted_binding(image):
        return binding(image, history_by_id.get(image.get("batch_id")), history=True)

    operations = [op for op in history if op["state"] == "confirmed"]
    excluded_creation_ids = {
        change["row"]["id"]
        for op in history
        if op["state"] != "confirmed" and op["kind"] in ADDITION_KINDS
        for change in op["plan"].get("creates", [])
        if change.get("kind") == "copy"
    }
    generations = {}
    for op in operations:
        value = op["generation"]
        generations.setdefault(value, []).append(op["id"])
    invalid_generations = {
        value for value, ids in generations.items() if type(value) is not int or len(ids) > 1
    }
    excluded_creation_ids.update(
        change["after"]["id"]
        for op in operations
        if op["kind"] in ADDITION_KINDS and op["generation"] in invalid_generations
        for change in op["changes"]
        if change.get("kind") == "copy" and change.get("before") is None and change.get("after")
    )
    for value in sorted(invalid_generations, key=str):
        conflicts.append(
            dict(kind="ambiguous-operation-order", generation=value, operation_ids=generations[value])
        )
    sources = (
        store.rows("SELECT * FROM ownership_declarations WHERE user_id=%s", [actor.user_id])
        if declarations.available()
        else []
    )
    sources = {s["id"]: s for s in sources}
    if pending is not None:
        sources.update(
            {
                c["row"]["id"]: c["row"]
                for c in pending["plan"].get("creates", [])
                if c["kind"] == "declaration"
            }
        )
    selections, scoped = [], {}
    for op in operations:
        if op["kind"] not in SELECTION_KINDS or not op["plan"].get("selected_source_id"):
            continue
        key = op["plan"]["selected_source_id"]
        source = sources.get(key)
        if source is None:
            selections.append((op, None, []))
            continue
        rows = declarations.parse(source["source_text"], source["source_sha256"])
        if (
            op["plan"].get("source_scope", "full251" if collection_goals.full_source(source) else "scoped")
            == "full251"
        ):
            selections.append((op, source, rows))
        else:
            scope = op["plan"].get("source_scope") or (rows[0]["source_scope"] if rows else "unknown")
            scoped[scope] = (op, source, rows)
    chosen = selections[-1] if selections else None
    selected, boundary, selected_rows = None, None, []
    baseline_valid = True
    baseline_sources = []
    if chosen:
        op, source, selected_rows = chosen
        boundary = dict(operation_id=op["id"], generation=op["generation"])
        baseline_valid = source is not None and op["generation"] not in invalid_generations
        if source is None:
            conflicts.append(
                dict(
                    kind="missing-selected-source",
                    source_id=op["plan"]["selected_source_id"],
                    operation_ids=[op["id"]],
                )
            )
            selected = dict(id=op["plan"]["selected_source_id"], unresolved=True)
        else:
            selected = collection_goals.reference(source)
            if baseline_valid:
                baseline_sources = [(op, source, selected_rows)]
            else:
                selected["unresolved"] = True
                boundary["unresolved"] = True
        applicable_scoped = {}
        for scope, (scope_op, scope_source, scope_rows) in scoped.items():
            if (
                type(scope_op["generation"]) is not int
                or type(op["generation"]) is not int
                or scope_op["generation"] <= op["generation"]
            ):
                continue
            if (
                scope_op["plan"].get("replacement") != "replace"
                or scope_op["generation"] in invalid_generations
            ):
                conflicts.append(
                    dict(
                        kind="scoped-selection-after-full-source",
                        source_id=scope_source["id"],
                        operation_ids=[scope_op["id"]],
                    )
                )
                continue
            applicable_scoped[scope] = (scope_op, scope_source, scope_rows)
        scoped = applicable_scoped
        for scope, value in scoped.items():
            lower, upper = (1, 151) if scope == "kanto" else (152, 251)
            baseline_sources = [
                (o, src, [r for r in rs if not lower <= r["pokemon_dex"] <= upper])
                for o, src, rs in baseline_sources
            ]
            baseline_sources.append(
                (value[0], value[1], [r for r in value[2] if lower <= r["pokemon_dex"] <= upper])
            )
        selected_rows = [r for _, _, rs in baseline_sources for r in rs]
    elif scoped:
        baseline_sources = [
            (v[0], v[1], [r for r in v[2] if (r["pokemon_dex"] <= 151) == (scope == "kanto")])
            for scope, v in scoped.items()
            if v[0]["generation"] not in invalid_generations
        ]
        selected_rows = [r for _, _, rows in baseline_sources for r in rows]
    scoped_sources = {
        scope: dict(
            source=collection_goals.reference(source),
            boundary=dict(operation_id=op["id"], generation=op["generation"]),
        )
        for scope, (op, source, _) in scoped.items()
    }
    cards, species = {}, {}
    for n in range(1, 252):
        species[str(n)] = dict(
            pokemon_dex=n,
            present=False,
            established_total_quantity=None,
            recorded_copy_count=0,
            recorded_copy_ids=[],
            current_copy_ids=[],
            card_ids=[],
            source_ids=[],
            operation_ids=[],
            unresolved=False,
            conflicts=[],
        )

    def card(set_name, name, number, pokemon_dex=None):
        key = _key(set_name, name, number)
        if key not in cards:
            candidates = candidates_by_key.get(key, [])
            set_ids = {p["set_id"] for p in candidates}
            numbers = {species_number(p) for p in candidates} - {None}
            languages = {p.get("language") for p in candidates}
            collision = (
                len(set_ids) > 1
                or len(languages) > 1
                or len(numbers) > 1
                or (pokemon_dex is not None and numbers and numbers != {pokemon_dex})
            )
            row_conflicts = [dict(kind="catalog-identity-collision")] if collision else []
            row = dict(
                id=stable_id("effective-card", json.dumps(key, ensure_ascii=False)),
                set_name=set_name,
                name=name,
                number=number,
                pokemon_dex=pokemon_dex,
                printing_ids=sorted(p["id"] for p in candidates) if not collision else [],
                identity_status="conflict" if collision else "card-known-variant-unresolved",
                present=False,
                established_total_quantity=None,
                recorded_copy_count=0,
                recorded_copy_ids=[],
                current_copy_ids=[],
                exact_printing_owned_ids=[],
                declared=False,
                source_ids=[],
                operation_ids=[],
                conflicts=row_conflicts,
            )
            cards[key] = row
        row = cards[key]
        if pokemon_dex is not None and row["pokemon_dex"] not in {None, pokemon_dex}:
            row["identity_status"] = "conflict"
            row["printing_ids"] = []
            row["conflicts"].append(dict(kind="species-identity-collision", pokemon_dex=pokemon_dex))
        if row["pokemon_dex"] is None and pokemon_dex is not None:
            row["pokemon_dex"] = pokemon_dex
        return row

    for p in catalog:
        card(p["set_name"], p["name"], p["collector_number"], species_number(p))
    for op, source, rows in baseline_sources:
        for declaration in rows:
            n = declaration["pokemon_dex"]
            s = species[str(n)]
            s["present"] = True
            s["source_ids"].append(source["id"])
            s["operation_ids"].append(op["id"])
            identities = declared_cards(declaration)
            s["unresolved"] |= not bool(identities)
            for identity in identities:
                row = card(declaration["set_name"], identity["name"], identity["number"], n)
                row["present"] = row["declared"] = True
                row["source_ids"].append(source["id"])
                row["operation_ids"].append(op["id"])
                s["card_ids"].append(row["id"])
    creation = {}
    for op in operations:
        if op["kind"] not in ADDITION_KINDS or op["generation"] in invalid_generations:
            continue
        for change in op["changes"]:
            if change.get("kind") == "copy" and change.get("before") is None and change.get("after"):
                copy_id = change["after"]["id"]
                if copy_id in creation:
                    conflicts.append(dict(kind="copy-creation-collision", copy_id=copy_id))
                    creation[copy_id] = None
                else:
                    creation[copy_id] = op
    qualified = collection.exact_owned_printings(
        [
            {
                **c,
                "unresolved_fields": json.dumps(
                    by_id.get(c.get("printing_id"), {}).get("unresolved_fields", [])
                ),
            }
            for c in active
        ],
        set(by_id),
    )
    for copy in active:
        p = by_id.get(copy.get("printing_id"))
        op = creation.get(copy["id"])
        identity = _json(copy.get("provisional_identity"), {})
        bound = binding(copy, op) if not p else None
        literal = bound["identity"] if bound else None
        n = species_number(p) if p else literal.get("pokemon_dex") if literal else None
        scope = "kanto" if n is not None and n <= 151 else "johto" if n else None
        copy_boundary = scoped_sources.get(scope, {}).get("boundary") or boundary
        admitted = copy_boundary is None or (
            op is not None
            and type(copy_boundary["generation"]) is int
            and not copy_boundary.get("unresolved")
            and op["generation"] > copy_boundary["generation"]
        )
        excluded_creation = copy["id"] in excluded_creation_ids
        if excluded_creation:
            admitted = False
            conflicts.append(dict(kind="copy-with-unconfirmed-creation", copy_id=copy["id"]))
        if p or literal:
            row = (
                card(p["set_name"], p["name"], p["collector_number"], n)
                if p
                else card(literal["set_name"], literal["name"], literal["number"], n)
            )
            row["recorded_copy_ids"].append(copy["id"])
            # Matching inherited records can describe the source's known card.
            current = not excluded_creation and (
                admitted
                or (
                    baseline_valid
                    and row["declared"]
                    and (literal is not None or p["id"] in row["printing_ids"])
                )
            )
            if current:
                row["present"] = True
                row["current_copy_ids"].append(copy["id"])
                if p and p["id"] in qualified and not identity.get("unresolved_fields"):
                    row["exact_printing_owned_ids"].append(p["id"])
                if op:
                    row["operation_ids"].append(op["id"])
            else:
                row["conflicts"].append(dict(kind="copy-omitted-by-selected-source", copy_id=copy["id"]))
        else:
            row = None
            current = admitted
            if current:
                conflicts.append(
                    dict(
                        kind="unresolved-current-copy",
                        copy_id=copy["id"],
                        printing_id=copy.get("printing_id"),
                    )
                )
        if n is not None:
            s = species[str(n)]
            s["recorded_copy_ids"].append(copy["id"])
            if current:
                s["present"] = True
                s["current_copy_ids"].append(copy["id"])
                s["unresolved"] |= row is None
                if row:
                    s["card_ids"].append(row["id"])
                if op:
                    s["operation_ids"].append(op["id"])
    # Journal-only card intent obeys the last source boundary for its scope.
    from . import collection_defaults

    intents = {}
    for op in operations:
        if op["generation"] in invalid_generations:
            continue
        for intent in collection_defaults.intents(op["plan"]):
            identity = intent["identity"]
            n = identity.get("pokemon_dex")
            scope = "kanto" if n and n <= 151 else "johto" if n else None
            source_boundary = scoped_sources.get(scope, {}).get("boundary") or boundary
            if source_boundary and (
                source_boundary.get("unresolved") or op["generation"] <= source_boundary["generation"]
            ):
                continue
            key = _key(identity["set_name"], identity["name"], identity["number"])
            intents.setdefault(key, []).append((op, intent))
    for key, events in intents.items():
        identity = events[0][1]["identity"]
        row = card(identity["set_name"], identity["name"], identity["number"], identity.get("pokemon_dex"))
        correction_event = next(
            ((o, i) for o, i in reversed(events) if i["kind"] == "declaration_correction"), None
        )
        if correction_event:
            row["declared"] = False
            row["source_ids"] = []
            row["present"] = bool(row["current_copy_ids"])
            row["operation_ids"].append(correction_event[0]["id"])
        presence_event = next(
            ((op, i) for op, i in reversed(events) if i["kind"] in {"mark_owned", "remove_card"}),
            None,
        )
        if presence_event:
            op, intent = presence_event
            row["operation_ids"].append(op["id"])
            if intent["kind"] in {"remove_card", "declaration_correction"}:
                row["declared"] = False
                row["source_ids"] = []
                if intent["kind"] == "remove_card":
                    row["current_copy_ids"] = [
                        cid
                        for cid in row["current_copy_ids"]
                        if creation.get(cid) and creation[cid]["generation"] > op["generation"]
                    ]
                    row["exact_printing_owned_ids"] = [
                        p["id"]
                        for p in catalog
                        if any(
                            c["id"] in row["current_copy_ids"] and c.get("printing_id") == p["id"]
                            for c in active
                        )
                        and p["id"] in qualified
                    ]
                row["present"] = bool(row["current_copy_ids"])
            else:
                row["present"] = True
        quantity_event = next(
            (
                (op, i)
                for op, i in reversed(events)
                if i["kind"] in {"card_quantity", "card_defaults", "mark_owned", "remove_card"}
            ),
            None,
        )
        if quantity_event:
            op, intent = quantity_event
            total = intent.get("established_total_quantity")
            # Undoing a copy mutation cannot resurrect the earlier exhaustive total.
            changed_after = any(
                later["state"] in {"confirmed", "undone"}
                and type(later["generation"]) is int
                and later["generation"] > op["generation"]
                and (
                    any(
                        i["kind"] in {"mark_owned", "remove_card"}
                        and _key(i["identity"]["set_name"], i["identity"]["name"], i["identity"]["number"])
                        == key
                        for i in collection_defaults.intents(later["plan"])
                    )
                    or any(
                        c["kind"] == "copy"
                        and (
                            c.get("before") is None
                            or c.get("after") is None
                            or c["before"].get("state") != c["after"].get("state")
                        )
                        and any(
                            image
                            and (
                                image.get("printing_id") in row["printing_ids"]
                                or (
                                    admitted_binding(image)
                                    and _key(
                                        **{
                                            k: admitted_binding(image)["identity"][k]
                                            for k in ("set_name", "name", "number")
                                        }
                                    )
                                    == key
                                )
                            )
                            for image in (c.get("before"), c.get("after"))
                        )
                        for c in later["changes"]
                    )
                )
                for later in history
            )
            row["established_total_quantity"] = total if row["present"] and not changed_after else None
            row["operation_ids"].append(op["id"])
        variant_event = next(
            (i for _, i in reversed(events) if i["kind"] in {"card_defaults", "mark_owned", "remove_card"}),
            None,
        )
        if row["present"] and variant_event and variant_event["kind"] == "card_defaults":
            row["owned_variant"] = variant_event["owned_variant"]
            if collection_defaults.variant_exception(row, {c["id"]: c for c in active}, by_id):
                row["owned_variant"] = None
            row["owned_variant_printing_ids"] = collection_defaults.variant_printing_ids(row, catalog)
        if row["established_total_quantity"] is not None and row["established_total_quantity"] < len(
            row["current_copy_ids"]
        ):
            row["conflicts"].append(
                dict(
                    kind="quantity-current-copy-conflict",
                    attested_total=row["established_total_quantity"],
                    supported_copy_count=len(row["current_copy_ids"]),
                )
            )
            row["established_total_quantity"] = None
    # Rebuild species presence from current card support and unresolved declaration marks.
    for n, s in species.items():
        rows = [r for r in cards.values() if r["pokemon_dex"] == int(n)]
        s["present"] = bool(s["unresolved"] or any(r["present"] for r in rows))
        s["current_copy_ids"] = [cid for r in rows for cid in r["current_copy_ids"]]
        s["card_ids"] = [r["id"] for r in rows if r["present"]]
        s["operation_ids"] = [oid for r in rows if r["present"] for oid in r["operation_ids"]] + (
            s["operation_ids"] if s["unresolved"] else []
        )
        s["source_ids"] = [sid for r in rows if r["present"] for sid in r["source_ids"]] + (
            s["source_ids"] if s["unresolved"] else []
        )
    printings = {}
    for p in catalog:
        row = cards[_key(p["set_name"], p["name"], p["collector_number"])]
        matching = copies_by_printing.get(p["id"], [])
        printings[p["id"]] = dict(
            present=bool(
                any(c["id"] in row["current_copy_ids"] for c in matching)
                or (row["present"] and p["id"] in row["printing_ids"])
            ),
            established_total_quantity=None,
            recorded_copy_count=len(matching),
            recorded_copy_ids=[c["id"] for c in matching],
            current_copy_ids=[c["id"] for c in matching if c["id"] in row["current_copy_ids"]],
            exact_printing_owned=p["id"] in row["exact_printing_owned_ids"],
            card_ids=[row["id"]],
            identity_status=row["identity_status"],
            source_ids=sorted(set(row["source_ids"])),
            operation_ids=sorted(set(row["operation_ids"])),
            conflicts=row["conflicts"],
        )
    for row in [*cards.values(), *species.values()]:
        for field in (
            "recorded_copy_ids",
            "current_copy_ids",
            "source_ids",
            "operation_ids",
            "card_ids",
            "exact_printing_owned_ids",
        ):
            if field in row:
                row[field] = sorted(set(row[field]))
        row["recorded_copy_count"] = len(row["recorded_copy_ids"])
    store.verified(actor)
    if collection.generation(actor) != read_generation:
        raise collection.Conflict("Collection changed during projection; reload the current view")
    return dict(
        user_id=actor.user_id,
        generation=read_generation,
        selected_source=selected,
        source_boundary=boundary,
        has_selected_source=bool(chosen or scoped_sources),
        scoped_sources=scoped_sources,
        historical_source_ids=sorted(sources),
        declaration_rows=selected_rows,
        cards=sorted(cards.values(), key=lambda r: (r["set_name"], r["number"] or "", r["name"])),
        species=species,
        printings=printings,
        conflicts=conflicts,
    )
