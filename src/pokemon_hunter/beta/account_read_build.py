"""Explicit account preparation and bounded species/identity dependency refresh.

Authority remains in effective_collection and the mutation services. These rows
are disposable; a revision mismatch never invokes preparation from browsing.
"""

import json

from django.db import connection, transaction

from . import account_read_schema as schema
from . import card_groups, collection, store
from . import effective_collection as effective
from .account_read_records import persist as persist
from .account_read_records import put as put
from .catalog_read_build import Unavailable
from .catalog_read_internal import current as catalog_current
from .catalog_read_internal import finish as catalog_finish
from .catalog_read_records import digest, encode

GLOBAL = "global"
UNKNOWN = "unidentified"
MAX_INPUT_ROWS = 2000
MAX_INPUT_BYTES = 4 * 1024 * 1024


def literal(row):
    return encode(
        effective._key(row["set_name"], row["name"], row.get("collector_number", row.get("number")))
    )


def authority(actor):
    """One compact query; caller independently checks current principal."""
    row = store.rows(
        "SELECT COALESCE((SELECT value FROM collection_generations WHERE user_id=%s),0) AS generation, COALESCE((SELECT value FROM account_read_revisions WHERE user_id=%s),0) AS revision",
        [actor.user_id, actor.user_id],
    )[0]
    return row["generation"], row["revision"]


def seal(state):
    return digest(
        encode(
            {
                k: state[k]
                for k in (
                    "user_id",
                    "generation",
                    "revision",
                    "catalog_token",
                    "catalog_equivalent",
                    "policy",
                    "source_digest",
                    "source_sha",
                    "counts",
                )
            }
        )
    )


def state(actor, token, *, requested_generation=None, requested_revision=None):
    from .read_diagnostics import category

    category("account", "unavailable")
    rows = store.rows(
        "SELECT user_id,generation,revision,catalog_token,catalog_equivalent,policy,source_digest,status,source_sha,counts,seal,COALESCE((SELECT value FROM collection_generations WHERE user_id=account_read_state.user_id),0) AS current_generation,COALESCE((SELECT value FROM account_read_revisions WHERE user_id=account_read_state.user_id),0) AS current_revision FROM account_read_state WHERE user_id=%s",
        [actor.user_id],
    )
    if not rows:
        raise Unavailable("account_not_prepared")
    found = rows[0]
    if requested_generation is not None and int(requested_generation) != found["current_generation"]:
        raise collection.Conflict("Collection revision changed")
    if requested_revision is not None and (
        requested_revision != found["seal"]
        or (found["generation"], found["revision"])
        != (found["current_generation"], found["current_revision"])
    ):
        raise collection.Conflict("Account revision changed")
    if found["policy"] != schema.POLICY:
        raise Unavailable("account_policy_incompatible")
    if found["seal"] != seal(found) or found["status"] == "corrupt":
        raise Unavailable("account_corrupt")
    if (
        found["status"] != "ready"
        or found["policy"] != schema.POLICY
        or found["catalog_token"] != token
        or found["seal"] != seal(found)
        or (found["generation"], found["revision"])
        != (found["current_generation"], found["current_revision"])
    ):
        raise Unavailable("account_revision_unavailable")
    category("account", "ready")
    return found


def decode(row):
    from .read_diagnostics import decoded, phase

    decoded()
    if row["payload"] is None or digest(row["payload"]) != row["sha"]:
        raise Unavailable("account_row_integrity")
    with phase("composition_ms"):
        return json.loads(row["payload"])


def components(rows):
    """Keep broad/canonical identity collisions together, independently of ordering."""
    parent = {}

    def root(key):
        parent.setdefault(key, key)
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    labels = {}
    for row in rows:
        keys = [
            "literal:" + literal(row),
            "canonical:"
            + encode([row.get(k) for k in ("game_id", "set_id", "language", "collector_number")]),
        ]
        for key in keys[1:]:
            left, right = root(key), root(keys[0])
            parent[max(left, right)] = min(left, right)
        labels[row["id"]] = keys[0]
    return {key: digest(root(value)) for key, value in labels.items()}


def catalog_inputs(snapshot, rows):
    mapping = components(rows)
    existing = store.rows("SELECT COUNT(*) AS n FROM ar_catalog WHERE build=%s", [snapshot.build])[0]["n"]
    if existing:
        # Catalog tokens bind immutable builds; no untrusted caller can replace rows.
        if existing != len(rows):
            raise Unavailable("account_catalog_incomplete")
        return mapping
    with connection.cursor() as cursor:
        cursor.executemany(
            "INSERT INTO ar_catalog VALUES(%s,%s,%s,%s,%s,%s)",
            [
                (snapshot.build, r["id"], mapping[r["id"]], literal(r), encode(r), digest(encode(r)))
                for r in rows
            ],
        )
    return mapping


def image_component(image, by_id, by_literal):
    if image.get("printing_id") in by_id:
        return by_id[image["printing_id"]]
    provisional = effective._json(image.get("provisional_identity"), {})
    identity = provisional.get("group_binding", {}).get("identity", provisional.get("identity", provisional))
    if {"set_name", "name", "number"} <= set(identity):
        return by_literal.get(literal(identity), "literal:" + literal(identity))
    return UNKNOWN


def dependencies(op, by_id, by_literal):
    if op["kind"] in effective.SELECTION_KINDS:
        return {GLOBAL}
    from .collection_defaults import intents

    keys = {
        by_literal.get(literal(i["identity"]), "literal:" + literal(i["identity"]))
        for i in intents(op["plan"])
    }
    images = [c.get(side) for c in op["changes"] if c["kind"] == "copy" for side in ("before", "after")]
    images += [c["row"] for c in op["plan"].get("creates", []) if c["kind"] == "copy"]
    images += [
        c.get(side)
        for c in op["plan"].get("updates", [])
        if c["kind"] == "copy"
        for side in ("before", "after")
    ]
    for image in images:
        if image:
            keys.add(image_component(image, by_id, by_literal))
    return keys


def index_operation(actor, op, keys):
    put("ar_operations", actor, dict(id=op["id"]), op)
    collection.execute(
        "DELETE FROM ar_dependencies WHERE user_id=%s AND operation_id=%s", [actor.user_id, op["id"]]
    )
    with connection.cursor() as cursor:
        cursor.executemany(
            "INSERT INTO ar_dependencies VALUES(%s,%s,%s)", [(actor.user_id, k, op["id"]) for k in keys]
        )


def finish_state(actor, snapshot, source_bundle):
    generation, revision = authority(actor)
    counts = {
        table: store.rows(
            f"SELECT COUNT(*) AS n FROM {table} INDEXED BY {table}_count WHERE user_id=%s", [actor.user_id]
        )[0]["n"]
        for table in schema.TABLES
    }
    text = encode(source_bundle)
    record = dict(
        user_id=actor.user_id,
        generation=generation,
        revision=revision,
        catalog_token=snapshot.token,
        catalog_equivalent=int(source_bundle["catalog_equivalent"]),
        policy=schema.POLICY,
        source_digest=digest(encode(source_bundle["sources"])),
        status="ready",
        sources=text,
        source_sha=digest(text),
        counts=encode(counts),
    )
    record["seal"] = seal(record)
    collection.execute(
        "INSERT OR REPLACE INTO account_read_state ("
        + ",".join(record)
        + ") VALUES ("
        + ",".join(["%s"] * len(record))
        + ")",
        list(record.values()),
    )


def prepare(actor):
    """Whole-account preparation is explicit and atomic; never invoked by a read."""
    actor = store.verified(actor)
    schema.check()
    with transaction.atomic():
        snapshot = catalog_current()
        rows = collection.catalog(actor, include_archived=True)
        pokemon = {r["id"] for r in store.rows("SELECT id FROM games WHERE game_key='pokemon'")}
        by_id = catalog_inputs(snapshot, rows)
        from . import account_read_species

        scope_index, scope_facts = account_read_species.prepare(snapshot, rows, pokemon)
        by_literal = {literal(row): by_id[row["id"]] for row in rows}
        copies = store.collection(actor)
        history = store.rows(
            "SELECT * FROM collection_operations WHERE user_id=%s ORDER BY generation,id", [actor.user_id]
        )
        for op in history:
            op["plan"] = effective._json(op["plan"], {})
            op["changes"] = effective._json(op["changes"], [])
        sources = store.rows("SELECT * FROM ownership_declarations WHERE user_id=%s", [actor.user_id])
        generation = collection.generation(actor)
        projected = effective._evaluate(actor.user_id, generation, rows, copies, history, sources, pokemon)
        for card in projected["cards"]:
            if literal(card) not in by_literal and card["pokemon_dex"] is not None:
                by_literal[literal(card)] = "literal:" + literal(card)
        grouped = card_groups._compose(
            actor,
            generation,
            rows,
            [c for c in copies if c["state"] == "active"],
            projected,
            {r["id"] for r in rows if r["publication_state"] == r["set_publication_state"] == "published"},
            pokemon,
        )
        collection.execute(
            "UPDATE account_read_state SET status='preparing' WHERE user_id=%s", [actor.user_id]
        )
        for table in schema.TABLES:
            collection.execute(f"DELETE FROM {table} WHERE user_id=%s", [actor.user_id])
        persist(actor, projected, grouped, copies, by_id, by_literal, build=snapshot.build)
        account_read_species.persist(actor, projected["cards"], by_literal, literal, scope_index, scope_facts)
        for key, row in projected["species"].items():
            put("ar_species", actor, dict(id=key), row)
        for op in history:
            index_operation(actor, op, dependencies(op, by_id, by_literal))
        from . import account_read_goals

        account_read_goals.prepare(actor)
        # Reuse optimized published selection only after proving exact membership
        # equality against retained private groups. Otherwise retain private SQL.
        public = "SELECT id FROM cr_groups WHERE build=%s AND scope IN ('public','shared')"
        private = "SELECT id FROM cr_groups WHERE build=%s AND scope IN ('retained','shared') AND json_extract(payload,'$.catalog_available')=1"
        mismatch = store.rows(
            "SELECT EXISTS("
            + public
            + " EXCEPT "
            + private
            + ") OR EXISTS("
            + private
            + " EXCEPT "
            + public
            + ") AS different",
            [snapshot.build] * 4,
        )[0]["different"]
        bundle = dict(
            scope_facts=scope_facts,
            sources=sources,
            pokemon=sorted(pokemon),
            conflicts=projected["conflicts"],
            catalog_equivalent=not mismatch,
            selection_ids=[
                op["id"]
                for op in history
                if op["kind"] in effective.SELECTION_KINDS and op["state"] == "confirmed"
            ],
        )
        catalog_finish(snapshot)
        store.verified(actor)
        finish_state(actor, snapshot, bundle)
    return dict(generation=generation, catalog_revision=snapshot.token, status="ready")


def before_mutation(actor):
    """Capture only compatible prepared state. Legacy installations remain untouched."""
    if connection.vendor != "sqlite":
        return None
    if not store.rows("SELECT 1 FROM sqlite_master WHERE type='table' AND name='account_read_state'"):
        return None
    try:
        snapshot = catalog_current()
        found = state(actor, snapshot.token)
        found["sources"] = store.rows(
            "SELECT CASE WHEN length(CAST(sources AS BLOB))<=%s THEN sources END AS sources FROM account_read_state WHERE user_id=%s",
            [MAX_INPUT_BYTES, actor.user_id],
        )[0]["sources"]
        if found["sources"] is None:
            return None
        return snapshot, found
    except Exception:
        # Missing/damaged disposable infrastructure cannot block authority.
        return None


def bounded(rows):
    if len(rows) > MAX_INPUT_ROWS or sum(len(r.get("payload", "").encode()) for r in rows) > MAX_INPUT_BYTES:
        raise Unavailable("account_dependency_closure_too_large")
    return rows


def refresh(actor, previous, operation_id):
    """Best-effort derived savepoint, inside the authoritative mutation transaction.

    Failure cannot erase the confirmation receipt or relabel an older revision as
    current. Missing state remains unavailable until explicit operator preparation.
    """
    if previous is None:
        return
    try:
        with transaction.atomic():
            _refresh(actor, previous, operation_id)
    except Exception:
        # The authority transaction is still usable after rolling back the nested
        # savepoint. Store only a fixed state, never exception/private record text.
        try:
            with transaction.atomic():
                collection.execute(
                    "UPDATE account_read_state SET status='unavailable' WHERE user_id=%s", [actor.user_id]
                )
        except Exception:
            # Even broken recovery infrastructure cannot erase authority. Its
            # advanced revision makes the previous representation unusable.
            pass


def _refresh(actor, previous, operation_id):
    snapshot, prior = previous
    catalog_finish(snapshot)
    if prior["source_sha"] != digest(prior["sources"]):
        raise Unavailable("source_integrity")
    bundle = json.loads(prior["sources"])
    if any(not conflict.get("copy_id") for conflict in bundle["conflicts"]):
        raise Unavailable("global_conflict_requires_preparation")
    op = collection.operation(actor, operation_id)
    if op["kind"] in effective.SELECTION_KINDS or op["kind"] == "import":
        prepare(actor)
        return
    images = [c.get(side) for c in op["changes"] if c["kind"] == "copy" for side in ("before", "after")]
    ids = {image["printing_id"] for image in images if image and image.get("printing_id")}
    from .collection_defaults import intents

    literals = {literal(i["identity"]) for i in intents(op["plan"])}
    for image in images:
        if image and not image.get("printing_id"):
            provisional = effective._json(image.get("provisional_identity"), {})
            identity = provisional.get("group_binding", {}).get("identity")
            if identity:
                literals.add(literal(identity))
    if len(ids) + len(literals) > 100:
        raise Unavailable("large_edit_requires_preparation")
    predicates, params = [], [snapshot.build]
    for field, values in (("id", ids), ("literal", literals)):
        if values:
            predicates.append(f"{field} IN ({','.join(['%s'] * len(values))})")
            params.extend(sorted(values))
    selected = (
        store.rows(
            "SELECT id,literal,component FROM ar_catalog WHERE build=%s AND ("
            + " OR ".join(predicates)
            + ")",
            params,
        )
        if predicates
        else []
    )
    if literals:
        selected += store.rows(
            "SELECT id,literal,component FROM ar_cards WHERE user_id=%s AND literal IN ("
            + ",".join(["%s"] * len(literals))
            + ")",
            [actor.user_id, *sorted(literals)],
        )
    by_id = {r["id"]: r["component"] for r in selected}
    by_literal = {r["literal"]: r["component"] for r in selected}
    affected = dependencies(op, by_id, by_literal)
    affected.update(
        r["component"]
        for r in store.rows(
            "SELECT component FROM ar_dependencies WHERE user_id=%s AND operation_id=%s",
            [actor.user_id, operation_id],
        )
    )
    collection.execute("UPDATE account_read_state SET status='preparing' WHERE user_id=%s", [actor.user_id])
    index_operation(actor, op, affected)
    if affected:
        placeholders = ",".join(["%s"] * len(affected))
        parts = sorted(affected)
        catalog_rows = bounded(
            store.rows(
                f"SELECT * FROM ar_catalog INDEXED BY ar_catalog_component WHERE build=%s AND component IN ({placeholders}) LIMIT %s",
                [snapshot.build, *parts, MAX_INPUT_ROWS + 1],
            )
        )
        rows = [decode(r) for r in catalog_rows]
        by_id = {r["id"]: r["component"] for r in catalog_rows}
        by_literal = {r["literal"]: r["component"] for r in catalog_rows}
        existing_cards = bounded(
            store.rows(
                f"SELECT id,literal,component FROM ar_cards INDEXED BY ar_cards_component WHERE user_id=%s AND component IN ({placeholders}) LIMIT %s",
                [actor.user_id, *parts, MAX_INPUT_ROWS + 1],
            )
        )
        by_literal.update({r["literal"]: r["component"] for r in existing_cards})
        by_literal.update(
            {key.removeprefix("literal:"): key for key in affected if key.startswith("literal:")}
        )
        history_rows = bounded(
            store.rows(
                f"SELECT o.* FROM ar_operations o WHERE o.user_id=%s AND o.id IN (SELECT operation_id FROM ar_dependencies WHERE user_id=%s AND component IN ({placeholders},%s)) LIMIT %s",
                [actor.user_id, actor.user_id, *parts, GLOBAL, MAX_INPUT_ROWS + 1],
            )
        )
        history = sorted([decode(r) for r in history_rows], key=lambda r: (r["generation"], r["id"]))
        # Read current authority only for indexed dependencies, including newly
        # created rows. Do not trust the stored copy payload as mutation authority.
        copy_ids = {
            r["id"]
            for r in store.rows(
                f"SELECT id FROM ar_copies WHERE user_id=%s AND component IN ({placeholders}) LIMIT %s",
                [actor.user_id, *parts, MAX_INPUT_ROWS + 1],
            )
        }
        copy_ids.update(image["id"] for image in images if image)
        if len(copy_ids) > MAX_INPUT_ROWS:
            raise Unavailable("copy_closure_too_large")
        copies = (
            store.rows(
                "SELECT c.*,p.collector_number,p.edition,p.unresolved_fields,p.attributes FROM owned_copies c LEFT JOIN printings p ON p.id=c.printing_id WHERE c.user_id=%s AND c.id IN ("
                + ",".join(["%s"] * len(copy_ids))
                + ") ORDER BY c.id",
                [actor.user_id, *sorted(copy_ids)],
            )
            if copy_ids
            else []
        )
        prior_species = {
            r["species"]
            for r in store.rows(
                f"SELECT DISTINCT species FROM ar_cards INDEXED BY ar_cards_component WHERE user_id=%s AND component IN ({placeholders})",
                [actor.user_id, *parts],
            )
            if r["species"] is not None
        }
        generation = collection.generation(actor)
        projected = effective._evaluate(
            actor.user_id, generation, rows, copies, history, bundle["sources"], set(bundle["pokemon"])
        )
        projected["cards"] = [r for r in projected["cards"] if literal(r) in by_literal]
        projected["declaration_rows"] = []  # global evidence did not change
        grouped = card_groups._compose(
            actor,
            generation,
            rows,
            [c for c in copies if c["state"] == "active"],
            projected,
            {r["id"] for r in rows if r["publication_state"] == r["set_publication_state"] == "published"},
            set(bundle["pokemon"]),
        )
        persist(actor, projected, grouped, copies, by_id, by_literal, build=snapshot.build, only=affected)
        from . import account_read_species

        scope_rows = (
            store.rows(
                "SELECT * FROM ar_scope_catalog WHERE build=%s AND id IN ("
                + ",".join(["%s"] * len(by_id))
                + ")",
                [snapshot.build, *by_id],
            )
            if by_id
            else []
        )
        scope_index = {
            r["id"]: dict(
                set=r["set_id"],
                set_name=r["set_name"],
                era=r["era"],
                type=r["type"],
                rarity=r["rarity"],
                finish=r["finish"],
                card=r["card"],
                release=dict(start=r["start"], end=r["end"]) if r["start"] else None,
            )
            for r in scope_rows
        }
        account_read_species.persist(
            actor, projected["cards"], by_literal, literal, scope_index, bundle["scope_facts"], only=affected
        )
        species = (
            prior_species
            | {r["attributes"].get("pokemon_dex") for r in rows}
            | {r["pokemon_dex"] for r in projected["cards"]}
        )
        for n in species:
            if not effective._number(n):
                continue
            old = decode(
                store.rows("SELECT * FROM ar_species WHERE user_id=%s AND id=%s", [actor.user_id, str(n)])[0]
            )
            cards = [
                decode(r)
                for r in bounded(
                    store.rows(
                        "SELECT * FROM ar_cards WHERE user_id=%s AND species=%s LIMIT %s",
                        [actor.user_id, n, MAX_INPUT_ROWS + 1],
                    )
                )
            ]
            old["recorded_copy_ids"] = sorted(
                (set(old["recorded_copy_ids"]) - copy_ids)
                | set(projected["species"][str(n)]["recorded_copy_ids"])
            )
            old["operation_ids"] = (
                [key for key in old["operation_ids"] if key in bundle["selection_ids"]]
                if old["unresolved"]
                else []
            )
            if not old["unresolved"]:
                old["source_ids"] = []
            effective._species_rows(cards, {str(n): old})
            for field in ("recorded_copy_ids", "current_copy_ids", "source_ids", "operation_ids", "card_ids"):
                old[field] = sorted(set(old[field]))
            old["recorded_copy_count"] = len(old["recorded_copy_ids"])
            put("ar_species", actor, dict(id=str(n)), old)
    from . import account_read_goals

    account_read_goals.refresh(actor, snapshot.build, ids, op)
    store.verified(actor)
    catalog_finish(snapshot)
    finish_state(actor, snapshot, bundle)
