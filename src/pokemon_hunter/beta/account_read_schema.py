"""Explicit disposable SQLite account-read infrastructure; never installed by GET."""

from django.db import connection, transaction

from . import collection, store

VERSION = 1
POLICY = "effective-collection-2-goal-headers"
SCOPE_FIELDS = (
    "set_id TEXT,set_name TEXT,era TEXT,type TEXT,rarity TEXT,finish TEXT,card TEXT,start TEXT,end TEXT"
)
TABLES = {
    "ar_variant_ownership": "id TEXT,group_id TEXT,component TEXT,PRIMARY KEY(user_id,id)",
    "ar_scope_owned": "id TEXT,component TEXT,species INTEGER," + SCOPE_FIELDS + ",PRIMARY KEY(user_id,id)",
    "ar_evidence_links": "id TEXT, group_id TEXT, component TEXT, PRIMARY KEY(user_id,id,group_id)",
    "ar_goals": "id TEXT, version TEXT, summary TEXT, summary_sha TEXT, payload TEXT, sha TEXT, bytes INTEGER, PRIMARY KEY(user_id,id)",
    "ar_goal_items": "id TEXT, goal_id TEXT, rank INTEGER, species INTEGER, status TEXT, payload TEXT, sha TEXT, bytes INTEGER, PRIMARY KEY(user_id,id)",
    "ar_goal_printings": "goal_id TEXT, item_id TEXT, printing_id TEXT, PRIMARY KEY(user_id,goal_id,item_id,printing_id)",
    "ar_membership": "id TEXT, component TEXT, present INTEGER, available INTEGER, species INTEGER, set_id TEXT, language TEXT, rank_set INTEGER, rank_name INTEGER, rank_number INTEGER, PRIMARY KEY(user_id,id)",
    "ar_groups": "id TEXT, assertion_id TEXT, component TEXT, present INTEGER, recorded INTEGER, available INTEGER, payload TEXT, sha TEXT, bytes INTEGER, PRIMARY KEY(user_id,id)",
    "ar_cards": "id TEXT, component TEXT, literal TEXT, species INTEGER, payload TEXT, sha TEXT, bytes INTEGER, PRIMARY KEY(user_id,id)",
    "ar_species": "id TEXT, summary TEXT, summary_sha TEXT, payload TEXT, sha TEXT, bytes INTEGER, PRIMARY KEY(user_id,id)",
    "ar_artwork": "id TEXT, component TEXT, payload TEXT, sha TEXT, bytes INTEGER, PRIMARY KEY(user_id,id)",
    "ar_copies": "id TEXT, component TEXT, group_id TEXT, printing_id TEXT, state TEXT, current INTEGER, exact INTEGER, payload TEXT, sha TEXT, bytes INTEGER, PRIMARY KEY(user_id,id)",
    "ar_evidence": "id TEXT, component TEXT, payload TEXT, sha TEXT, bytes INTEGER, PRIMARY KEY(user_id,id)",
    "ar_operations": "id TEXT, payload TEXT, sha TEXT, bytes INTEGER, PRIMARY KEY(user_id,id)",
    "ar_dependencies": "component TEXT, operation_id TEXT, PRIMARY KEY(user_id,component,operation_id)",
}
TRIGGERS = tuple(
    f"{table}_{event}"
    for table in (*TABLES, "ar_catalog", "ar_scope_catalog", "ar_scope_date_counts", "ar_scope_options")
    for event in ("insert", "update", "delete")
)


def migrate():
    if connection.vendor != "sqlite":
        raise ValueError("Account reads are qualified only on SQLite")
    with transaction.atomic(), connection.cursor() as cursor:
        tables = set(connection.introspection.table_names())
        if "catalog_read_schema" not in tables:
            raise ValueError("Migrate shared catalog reads first")
        if "account_read_schema" in tables:
            if store.rows("SELECT version FROM account_read_schema") != [{"version": VERSION}]:
                raise ValueError("Incompatible account read schema")
            return
        cursor.execute("CREATE TABLE account_read_schema(version INTEGER PRIMARY KEY)")
        cursor.execute("INSERT INTO account_read_schema VALUES(%s)", [VERSION])
        cursor.execute(
            "CREATE TABLE account_read_state(user_id TEXT PRIMARY KEY, generation INTEGER, revision INTEGER, catalog_token TEXT, catalog_equivalent INTEGER, policy TEXT, source_digest TEXT, status TEXT, sources TEXT, source_sha TEXT, counts TEXT, seal TEXT)"
        )
        # Full authoritative metadata is retained once per catalog build for policy
        # evaluation, separate from the bounded display metadata in cr_printings.
        cursor.execute(
            "CREATE TABLE ar_catalog(build INTEGER, id TEXT, component TEXT, literal TEXT, payload TEXT, sha TEXT, PRIMARY KEY(build,id)) WITHOUT ROWID"
        )
        cursor.execute(
            "CREATE TABLE ar_scope_catalog(build INTEGER,id TEXT,species INTEGER,"
            + SCOPE_FIELDS
            + ",PRIMARY KEY(build,id)) WITHOUT ROWID"
        )
        cursor.execute(
            "CREATE INDEX ar_scope_species ON ar_scope_catalog(build,species,set_id,set_name,era,type,rarity,finish,card,start,end)"
        )
        cursor.execute(
            "CREATE TABLE ar_scope_date_counts(build INTEGER,id INTEGER,species INTEGER,finish TEXT,start TEXT,end TEXT,n INTEGER,PRIMARY KEY(build,id)) WITHOUT ROWID"
        )
        cursor.execute(
            "CREATE INDEX ar_scope_date_counts_species ON ar_scope_date_counts(build,species,finish,start,end,n)"
        )
        cursor.execute(
            "CREATE TABLE ar_scope_options(build INTEGER,field TEXT,rank INTEGER,value TEXT,label TEXT,PRIMARY KEY(build,field,rank)) WITHOUT ROWID"
        )
        cursor.execute("CREATE INDEX ar_scope_set_names ON ar_scope_catalog(build,set_name,id)")
        cursor.execute("CREATE INDEX ar_scope_dates ON ar_scope_catalog(build,species,finish,start,end)")
        cursor.execute("CREATE INDEX ar_scope_set_options ON ar_scope_catalog(build,set_id,set_name)")
        cursor.execute("CREATE INDEX ar_catalog_component ON ar_catalog(build,component,id)")
        cursor.execute("CREATE INDEX ar_catalog_literal ON ar_catalog(build,literal,component)")
        for table, definition in TABLES.items():
            cursor.execute(f"CREATE TABLE {table}(user_id TEXT NOT NULL,{definition}) WITHOUT ROWID")
            cursor.execute(f"CREATE INDEX {table}_count ON {table}(user_id)")
            for event, ref in (("INSERT", "NEW"), ("UPDATE", "OLD"), ("DELETE", "OLD")):
                target = "IN (OLD.user_id,NEW.user_id)" if event == "UPDATE" else f"={ref}.user_id"
                cursor.execute(
                    f"CREATE TRIGGER {table}_{event.lower()} AFTER {event} ON {table} BEGIN UPDATE account_read_state SET status='corrupt' WHERE user_id {target} AND status='ready'; END"
                )
        for table in (
            "ar_groups",
            "ar_cards",
            "ar_copies",
            "ar_evidence",
            "ar_artwork",
            "ar_membership",
            "ar_scope_owned",
            "ar_variant_ownership",
        ):
            cursor.execute(f"CREATE INDEX {table}_component ON {table}(user_id,component,id)")
        cursor.execute(
            "CREATE INDEX ar_dependency_operation ON ar_dependencies(user_id,operation_id,component)"
        )
        cursor.execute("CREATE INDEX ar_owned ON ar_groups(user_id,present,id)")
        cursor.execute("CREATE INDEX ar_available ON ar_groups(user_id,available,id)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS ar_retained_identity ON cr_groups(build,id,rank_set,rank_name,rank_number,species,set_id,language) WHERE scope IN ('retained','shared')"
        )
        for sort in ("set", "name", "number"):
            for scope in ("present", "available"):
                cursor.execute(
                    f"CREATE INDEX ar_membership_{scope}_{sort} ON ar_membership(user_id,{scope},rank_{sort},id,species,set_id,language)"
                )
            cursor.execute(
                f"CREATE INDEX IF NOT EXISTS ar_retained_order_{sort} ON cr_groups(build,rank_{sort},id,species,set_id,language) WHERE scope IN ('retained','shared')"
            )

        cursor.execute(
            "CREATE INDEX ar_scope_owned_dates ON ar_scope_owned(user_id,species,finish,start,end)"
        )
        cursor.execute("CREATE INDEX ar_copy_state ON ar_copies(user_id,state)")
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS ar_private_picker ON cr_printings(build,id,published,group_id,search,json_extract(payload,'$.set_id'),json_extract(payload,'$.language')) WHERE scope IN ('retained','shared')"
        )
        cursor.execute("CREATE INDEX ar_copy_group ON ar_copies(user_id,group_id,state,id)")
        cursor.execute("CREATE INDEX ar_copy_printing ON ar_copies(user_id,printing_id,state,id)")
        cursor.execute(
            "CREATE INDEX ar_scope_owned_species ON ar_scope_owned(user_id,species,set_id,set_name,era,type,rarity,finish,card,start,end)"
        )
        cursor.execute("CREATE INDEX ar_card_species ON ar_cards(user_id,species,id)")
        cursor.execute("CREATE INDEX ar_card_literal ON ar_cards(user_id,literal,component)")
        cursor.execute("CREATE INDEX ar_evidence_group ON ar_evidence_links(user_id,group_id,id)")
        cursor.execute("CREATE INDEX ar_evidence_links_component ON ar_evidence_links(user_id,component,id)")
        cursor.execute(
            "CREATE INDEX ar_goal_lookup ON ar_goal_printings(user_id,printing_id,goal_id,item_id)"
        )
        cursor.execute("CREATE INDEX ar_goal_species ON ar_goal_items(user_id,goal_id,species,status,id)")
        for table in ("ar_catalog", "ar_scope_catalog", "ar_scope_date_counts", "ar_scope_options"):
            for event in ("INSERT", "UPDATE", "DELETE"):
                cursor.execute(
                    f"CREATE TRIGGER {table}_{event.lower()} AFTER {event} ON {table} BEGIN UPDATE account_read_state SET status='corrupt' WHERE status='ready'; END"
                )


def check():
    from .catalog_read_build import Unavailable

    found = store.rows(
        "SELECT (SELECT version FROM account_read_schema) AS version, (SELECT COUNT(*) FROM sqlite_master WHERE type='trigger' AND name IN ("
        + ",".join(["%s"] * len(TRIGGERS))
        + ")) AS triggers",
        TRIGGERS,
    )[0]
    if found["version"] != VERSION:
        raise Unavailable("incompatible_schema")
    if found["triggers"] != len(TRIGGERS):
        raise Unavailable("account_schema_infrastructure")


def discard(actor):
    """Explicit account-only disposal; authority and revision counters are untouched."""
    actor = store.verified(actor)
    with transaction.atomic():
        for table in TABLES:
            collection.execute(f"DELETE FROM {table} WHERE user_id=%s", [actor.user_id])
        collection.execute("DELETE FROM account_read_state WHERE user_id=%s", [actor.user_id])


def repair():
    """Explicit all-account derived repair; preserve every authority/revision table."""
    if connection.vendor != "sqlite":
        raise ValueError("Account reads are qualified only on SQLite")
    with transaction.atomic(), connection.cursor() as cursor:
        if store.rows("SELECT version FROM account_read_schema") != [{"version": VERSION}]:
            raise ValueError("Incompatible schema needs an explicit version transition")
        for table in (
            *TABLES,
            "ar_catalog",
            "ar_scope_catalog",
            "ar_scope_date_counts",
            "ar_scope_options",
            "account_read_state",
            "account_read_schema",
        ):
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
        migrate()
