"""Allowlisted account records and differential writes within checked dependency closures."""

from . import card_groups, collection, store
from .catalog_read_records import digest, encode

COPY_READ_FIELDS = (
    "id",
    "printing_id",
    "provisional_identity",
    "binder_id",
    "condition",
    "purchase_amount",
    "purchase_currency",
    "purchase_date",
    "notes",
    "grading_company",
    "grade",
    "certificate",
    "batch_id",
    "legacy_id",
    "first_edition_selected",
    "state",
    "revision",
    "source_copy_id",
)


def put(table, actor, values, payload, *, previous=None):
    if table == "ar_copies":
        payload = {key: payload[key] for key in COPY_READ_FIELDS if key in payload}
    text = encode(payload)
    if table == "ar_goals":
        summary = {k: v for k, v in payload.items() if k != "definition"}
        values = dict(values, summary=encode(summary), summary_sha=digest(encode(summary)))
    if table == "ar_species":
        from .canonical_species import registry

        n = int(values["id"])
        summary = dict(
            dex=n,
            name=registry()[n]["name"],
            region="kanto" if n <= 151 else "johto",
            current_present=payload["present"],
            scoped_present=payload["present"],
            species_quantity=None,
            recorded_copy_count=payload["recorded_copy_count"],
            current_copy_count=len(payload["current_copy_ids"]),
            details_needed=payload["unresolved"],
        )
        values = dict(values, summary=encode(summary), summary_sha=digest(encode(summary)))
    record = dict(user_id=actor.user_id, **values, payload=text, sha=digest(text), bytes=len(text.encode()))
    if (
        previous is not None
        and previous.get("sha") == record["sha"]
        and all(previous.get(key) == value for key, value in values.items())
    ):
        return
    columns = list(record)
    collection.execute(
        f"INSERT OR REPLACE INTO {table} ({','.join(columns)}) VALUES ({','.join(['%s'] * len(columns))})",
        list(record.values()),
    )


def persist(actor, projected, grouped, copies, by_id, by_literal, *, build, only=None):
    from .account_read_build import GLOBAL, UNKNOWN, image_component, literal

    tables = ("ar_groups", "ar_cards", "ar_copies", "ar_evidence", "ar_artwork", "ar_membership")
    previous = {}
    if only is not None:
        placeholders = ",".join(["%s"] * len(only))
        for table in tables:
            columns = (
                "*"
                if table == "ar_membership"
                else "id,component,sha"
                + (
                    ",group_id,printing_id,state,current,exact"
                    if table == "ar_copies"
                    else ",literal,species"
                    if table == "ar_cards"
                    else ",assertion_id,present,recorded,available"
                    if table == "ar_groups"
                    else ""
                )
            )
            previous[table] = {
                r["id"]: r
                for r in store.rows(
                    f"SELECT {columns} FROM {table} INDEXED BY {table}_component WHERE user_id=%s AND component IN ({placeholders})",
                    [actor.user_id, *sorted(only)],
                )
            }

    def write(table, values, payload):
        prior = previous.get(table, {}).pop(values["id"], None)
        put(table, actor, values, payload, previous=prior)

    def card_component(row):
        return by_literal.get(literal(row), "literal:" + literal(row))

    for row in projected["cards"]:
        component = card_component(row)
        if only is None or component in only:
            write(
                "ar_cards",
                dict(id=row["id"], component=component, literal=literal(row), species=row["pokemon_dex"]),
                row,
            )
    ids = [g["id"] for g in grouped["groups"]]
    rank_rows = (
        store.rows(
            "SELECT id,rank_set,rank_name,rank_number FROM cr_groups WHERE build=%s AND scope IN ('retained','shared')"
            + (" AND id IN (" + ",".join(["%s"] * len(ids)) + ")" if only is not None and ids else ""),
            [build, *(ids if only is not None else [])],
        )
        if ids
        else []
    )
    ranks = {r["id"]: r for r in rank_rows}
    copy_groups = {}
    current_ids = {key for row in projected["cards"] for key in row["current_copy_ids"]}
    current_ids.update(
        row["copy_id"] for row in projected["conflicts"] if row["kind"] == "unresolved-current-copy"
    )
    exact_ids = {key for row in projected["cards"] for key in row["exact_printing_owned_ids"]}
    if only is not None:
        collection.execute(
            "DELETE FROM ar_variant_ownership WHERE user_id=%s AND component IN ("
            + ",".join(["%s"] * len(only))
            + ")",
            [actor.user_id, *sorted(only)],
        )
    for group in grouped["groups"]:
        component = by_id[group["_children"][0]["id"]]
        if only is not None and component not in only:
            continue
        rank = ranks[group["id"]]
        membership = dict(
            user_id=actor.user_id,
            id=group["id"],
            component=component,
            present=int(group["present"]),
            available=int(group["catalog_available"]),
            species=group["pokemon_dex"],
            set_id=group["set_id"],
            language=group["language"],
            rank_set=rank["rank_set"],
            rank_name=rank["rank_name"],
            rank_number=rank["rank_number"],
        )
        prior = previous.get("ar_membership", {}).pop(group["id"], None)
        if prior != membership:
            collection.execute(
                "INSERT OR REPLACE INTO ar_membership VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                list(membership.values()),
            )
        # No large ID arrays in the primary record; separate indexed resources own them.
        payload = card_groups._summary(group, True)
        artwork = payload.pop("reference_image", None)
        if artwork is not None:
            write("ar_artwork", dict(id=group["id"], component=component), artwork)
        write(
            "ar_groups",
            dict(
                id=group["id"],
                component=component,
                present=int(group["present"]),
                recorded=group["recorded_copy_count"],
                assertion_id=group.get("assertion_id"),
                available=int(group["catalog_available"]),
            ),
            payload,
        )
        for printing_id in group.get("owned_variant_printing_ids", []):
            collection.execute(
                "INSERT OR REPLACE INTO ar_variant_ownership VALUES(%s,%s,%s,%s)",
                [actor.user_id, printing_id, group["id"], component],
            )
        for key in group["recorded_copy_ids"]:
            copy_groups[key] = group["id"]
        current_ids.update(group["current_copy_ids"])
        exact_ids.update(group["exact_printing_owned_ids"])
    for row in copies:
        component = image_component(row, by_id, by_literal)
        if only is None or component in only:
            group_id = copy_groups.get(row["id"])
            if group_id is None and row.get("printing_id"):
                group_id = grouped["printing_to_group"].get(row["printing_id"])
            if group_id is None and not row.get("printing_id"):
                from .copy_identity import binding

                bound = binding(row)
                if bound and bound["group_id"] in {g["id"] for g in grouped["groups"]}:
                    group_id = bound["group_id"]
            write(
                "ar_copies",
                dict(
                    id=row["id"],
                    component=component,
                    group_id=group_id,
                    printing_id=row.get("printing_id"),
                    state=row["state"],
                    current=int(row["id"] in current_ids),
                    exact=int(row.get("printing_id") in exact_ids and row["id"] in current_ids),
                ),
                row,
            )
    if only is not None:
        collection.execute(
            "DELETE FROM ar_evidence_links WHERE user_id=%s AND component IN ("
            + ",".join(["%s"] * len(only))
            + ")",
            [actor.user_id, *sorted(only)],
        )
    for row in grouped["unresolved"]:
        evidence = row.get("evidence", {})
        component = card_component(evidence) if {"set_name", "name", "number"} <= set(evidence) else UNKNOWN
        if row["kind"] == "unmapped-collection-copy":
            component = image_component(evidence, by_id, by_literal)
        # Unresolved source and global-order evidence are regenerated on explicit source prep.
        if row["kind"] in {"unresolved-species-mark", "effective-collection-conflict"}:
            component = GLOBAL
            copy_id = evidence.get("copy_id")
            if copy_id:
                copy = next((c for c in copies if c["id"] == copy_id), None)
                component = image_component(copy, by_id, by_literal) if copy else UNKNOWN
        if only is None or component in only:
            write("ar_evidence", dict(id=digest(encode(row)), component=component), row)
            links = {
                grouped["printing_to_group"][key]
                for key in row.get("printing_ids", [])
                if key in grouped["printing_to_group"]
            }
            if row["kind"] == "effective-collection-conflict":
                links.add("*")
            for group_id in links:
                collection.execute(
                    "INSERT OR REPLACE INTO ar_evidence_links VALUES(%s,%s,%s,%s)",
                    [actor.user_id, digest(encode(row)), group_id, component],
                )

    for table, rows in previous.items():
        if rows:
            collection.execute(
                f"DELETE FROM {table} WHERE user_id=%s AND id IN (" + ",".join(["%s"] * len(rows)) + ")",
                [actor.user_id, *rows],
            )
