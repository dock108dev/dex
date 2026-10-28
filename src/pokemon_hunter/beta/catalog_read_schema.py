"""Explicit additive SQLite read schema. Never called by startup or a GET."""

from django.db import connection, transaction

VERSION = 1
POLICY = "1:dg1:published-pokemon-en:images-1"
CATALOG_AUTHORITIES = (
    "games",
    "catalog_sets",
    "printings",
    "catalog_heads",
    "catalog_aliases",
    "external_mappings",
)
ACCOUNT_AUTHORITIES = (
    "owned_copies",
    "ownership_declarations",
    "import_batches",
    "import_records",
    "collection_goals",
    "collection_operations",
)
TABLES = {
    "cr_groups": "scope TEXT, id TEXT, species INTEGER, set_id TEXT, language TEXT, search TEXT, rank_set INTEGER, rank_name INTEGER, rank_number INTEGER, bytes INTEGER, payload TEXT, sha TEXT, PRIMARY KEY(build,scope,id)",
    "cr_children": "scope TEXT, id TEXT, group_id TEXT, published INTEGER, edition TEXT, finish TEXT, variant TEXT, search TEXT, bytes INTEGER, payload TEXT, sha TEXT, PRIMARY KEY(build,scope,id)",
    "cr_printings": "scope TEXT, id TEXT, group_id TEXT, published INTEGER, edition TEXT, finish TEXT, variant TEXT, search TEXT, bytes INTEGER, payload TEXT, sha TEXT, PRIMARY KEY(build,scope,id)",
    "cr_species": "scope TEXT, id TEXT, species INTEGER, set_id TEXT, era TEXT, supertype TEXT, search TEXT, PRIMARY KEY(build,scope,id)",
    "cr_gram_residual": "scope TEXT, doc_id INTEGER PRIMARY KEY, search TEXT, public_children INTEGER, UNIQUE(build,scope,doc_id)",
    "cr_match": "scope TEXT, rank_set INTEGER, rank_name INTEGER, rank_number INTEGER, id TEXT, species INTEGER, set_id TEXT, language TEXT, edition TEXT, finish TEXT, variant TEXT, search TEXT, PRIMARY KEY(build,scope,rank_set,id)",
    "cr_aliases": "scope TEXT, alias TEXT, printing_id TEXT, PRIMARY KEY(build,scope,alias,printing_id)",
    "cr_evidence": "scope TEXT, id TEXT, bytes INTEGER, payload TEXT, sha TEXT, PRIMARY KEY(build,scope,id)",
    "cr_options": "scope TEXT, field TEXT, rank INTEGER, value TEXT, label TEXT, bytes INTEGER, PRIMARY KEY(build,scope,field,rank)",
    "cr_postings": "scope TEXT, field TEXT, value TEXT, group_id TEXT, PRIMARY KEY(build,scope,field,value,group_id)",
    "cr_grams": "scope TEXT, group_id INTEGER, terms TEXT, doc_id INTEGER PRIMARY KEY, UNIQUE(build,scope,group_id)",
}


def migrate():
    if connection.vendor != "sqlite":
        raise ValueError("Catalog read schema is qualified only on SQLite")
    with transaction.atomic(), connection.cursor() as c:
        tables = set(connection.introspection.table_names())
        required = set(CATALOG_AUTHORITIES) | set(ACCOUNT_AUTHORITIES)
        if required - tables:
            raise ValueError("Install catalog, collection and declaration schemas before read migration")
        if "catalog_read_schema" in tables:
            c.execute("SELECT version FROM catalog_read_schema")
            if c.fetchall() != [(VERSION,)]:
                raise ValueError("Incompatible catalog read schema")
            optional_triggers(c, tables)
            return
        c.execute("CREATE TABLE catalog_read_schema(version INTEGER PRIMARY KEY)")
        c.execute("INSERT INTO catalog_read_schema VALUES (%s)", [VERSION])
        c.execute(
            "CREATE TABLE catalog_read_revision(id INTEGER PRIMARY KEY CHECK(id=1), value INTEGER NOT NULL)"
        )
        c.execute("INSERT INTO catalog_read_revision VALUES(1,1)")
        c.execute("CREATE TABLE account_read_revisions(user_id TEXT PRIMARY KEY, value INTEGER NOT NULL)")
        c.execute(
            "CREATE TABLE catalog_read_builds(id INTEGER PRIMARY KEY, revision INTEGER, policy TEXT, status TEXT, counts TEXT, checksum TEXT, builder TEXT, stride INTEGER, seal TEXT)"
        )
        c.execute("CREATE TABLE catalog_read_active(id INTEGER PRIMARY KEY CHECK(id=1), build INTEGER)")
        for table, definition in TABLES.items():
            c.execute(
                f"CREATE TABLE {table}(build INTEGER NOT NULL REFERENCES catalog_read_builds(id),{definition})"
                + ("" if table in {"cr_grams", "cr_gram_residual"} else " WITHOUT ROWID")
            )
            for event, ref in (("INSERT", "NEW"), ("UPDATE", "OLD"), ("DELETE", "OLD")):
                target = "IN (OLD.build,NEW.build)" if event == "UPDATE" else f"={ref}.build"
                c.execute(
                    f"CREATE TRIGGER {table}_{event.lower()} AFTER {event} ON {table} BEGIN UPDATE catalog_read_builds SET status='corrupt' WHERE id {target} AND status IN ('ready','validated'); END"
                )
        c.execute(
            "CREATE VIRTUAL TABLE cr_gram_index USING fts5(terms, build, content='cr_grams', content_rowid='doc_id', tokenize='ascii',detail=none,columnsize=0)"
        )
        c.execute(
            "CREATE TRIGGER cr_fts_insert AFTER INSERT ON cr_grams WHEN (SELECT status FROM catalog_read_builds WHERE id=new.build)<>'preparing' BEGIN INSERT INTO cr_gram_index(rowid,terms,build) VALUES(new.doc_id,new.terms,new.build); END"
        )
        c.execute(
            "CREATE TRIGGER cr_fts_delete AFTER DELETE ON cr_grams WHEN (SELECT status FROM catalog_read_builds WHERE id=old.build)<>'preparing' BEGIN INSERT INTO cr_gram_index(cr_gram_index,rowid,terms,build) VALUES('delete',old.doc_id,old.terms,old.build); END"
        )
        c.execute(
            "CREATE TRIGGER cr_fts_update AFTER UPDATE ON cr_grams WHEN (SELECT status FROM catalog_read_builds WHERE id=old.build)<>'preparing' BEGIN INSERT INTO cr_gram_index(cr_gram_index,rowid,terms,build) VALUES('delete',old.doc_id,old.terms,old.build); INSERT INTO cr_gram_index(rowid,terms,build) VALUES(new.doc_id,new.terms,new.build); END"
        )
        c.execute("CREATE INDEX cr_gram_rowid ON cr_grams(doc_id,scope,group_id)")
        c.execute("CREATE INDEX cr_gram_lookup ON cr_grams(build,scope,group_id)")
        c.execute(
            "CREATE INDEX cr_public_species ON cr_species(build,species,supertype,set_id,era,search) WHERE scope IN ('public','shared')"
        )
        c.execute("CREATE INDEX cr_printing_unresolved ON cr_printings(build,scope,group_id,id)")
        for sort in ("set", "name", "number"):
            c.execute(
                f"CREATE INDEX cr_public_order_{sort} ON cr_groups(build,rank_{sort},id,search,species,set_id,language{',rank_set' if sort != 'set' else ''}) WHERE scope IN ('public','shared')"
            )
            c.execute(f"CREATE INDEX cr_order_{sort} ON cr_groups(build,scope,rank_{sort},id,search,species)")
        c.execute(
            "CREATE INDEX cr_group_species ON cr_groups(build,scope,species,id,rank_set,rank_name,rank_number,search)"
        )
        c.execute(
            "CREATE INDEX cr_child_group ON cr_children(build,scope,group_id,id,search,edition,finish,variant)"
        )
        for sort in ("set", "name", "number"):
            c.execute(
                f"CREATE INDEX cr_public_match_{sort} ON cr_match(build,rank_{sort},id,search,rank_set) WHERE scope IN ('public','shared')"
            )
        for field in ("edition", "finish", "variant"):
            remaining = ",".join(f for f in ("edition", "finish", "variant") if f != field)
            c.execute(
                f"CREATE INDEX cr_match_{field} ON cr_match(build,{field},rank_set,{remaining},search,species,set_id,language,rank_name,rank_number) WHERE scope IN ('public','shared')"
            )
            c.execute(f"CREATE INDEX cr_child_{field} ON cr_children(build,scope,{field},group_id)")
        for table in CATALOG_AUTHORITIES:
            for event in ("INSERT", "UPDATE", "DELETE"):
                c.execute(
                    f"CREATE TRIGGER cr_rev_{table}_{event.lower()} AFTER {event} ON {table} BEGIN UPDATE catalog_read_revision SET value=value+1 WHERE id=1; END"
                )
        for table in ACCOUNT_AUTHORITIES:
            for event in ("INSERT", "UPDATE", "DELETE"):
                refs = ["NEW"] if event == "INSERT" else ["OLD"] if event == "DELETE" else ["OLD", "NEW"]
                statements = []
                for ref in refs:
                    owner = (
                        f"{ref}.user_id"
                        if table != "import_records"
                        else f"(SELECT user_id FROM import_batches WHERE id={ref}.batch_id)"
                    )
                    condition = f"{owner} IS NOT NULL"
                    if table == "collection_operations":
                        condition += f" AND {ref}.state<>'preview'"
                    statements.append(
                        f"INSERT INTO account_read_revisions(user_id,value) SELECT {owner},1 WHERE {condition} ON CONFLICT(user_id) DO UPDATE SET value=value+1;"
                    )
                c.execute(
                    f"CREATE TRIGGER cr_account_{table}_{event.lower()} AFTER {event} ON {table} BEGIN {' '.join(statements)} END"
                )

        optional_triggers(c, tables)


def optional_triggers(cursor, tables):
    # Pipeline era metadata is authoritative when that optional capability exists.
    if "catalog_batches" in tables:
        cursor.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='trigger' AND name IN ('cr_rev_catalog_batches_insert','cr_rev_catalog_batches_update','cr_rev_catalog_batches_delete')"
        )
        if cursor.fetchone()[0] != 3:
            cursor.execute("UPDATE catalog_read_revision SET value=value+1 WHERE id=1")
        for event in ("INSERT", "UPDATE", "DELETE"):
            cursor.execute(
                f"CREATE TRIGGER IF NOT EXISTS cr_rev_catalog_batches_{event.lower()} AFTER {event} ON catalog_batches BEGIN UPDATE catalog_read_revision SET value=value+1 WHERE id=1; END"
            )


TRIGGER_NAMES = tuple(
    [f"cr_rev_{table}_{event}" for table in CATALOG_AUTHORITIES for event in ("insert", "update", "delete")]
    + [
        f"cr_account_{table}_{event}"
        for table in ACCOUNT_AUTHORITIES
        for event in ("insert", "update", "delete")
    ]
    + [f"{table}_{event}" for table in TABLES for event in ("insert", "update", "delete")]
    + [f"cr_fts_{event}" for event in ("insert", "update", "delete")]
)


def repair():
    """Explicit derived-schema repair, preserving both monotonic revision backstops.

    Never call from startup/GET. No catalog, user, collection or journal table is
    dropped, restored or rewritten. SQLite transactions protect existing readers.
    """
    if connection.vendor != "sqlite":
        raise ValueError("Catalog read schema is qualified only on SQLite")
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SELECT value FROM catalog_read_revision WHERE id=1")
        previous = cursor.fetchone()
        if previous is None:
            raise ValueError("Missing authority revision requires database recovery")
        cursor.execute("SELECT user_id,value FROM account_read_revisions")
        accounts = cursor.fetchall()
        cursor.execute("SELECT version FROM catalog_read_schema")
        if cursor.fetchall() != [(VERSION,)]:
            raise ValueError("Incompatible schema requires an explicit version migration")
        for name in (
            *TRIGGER_NAMES,
            *(f"cr_rev_catalog_batches_{event}" for event in ("insert", "update", "delete")),
        ):
            cursor.execute(f"DROP TRIGGER IF EXISTS {name}")
        cursor.execute("DROP TABLE IF EXISTS cr_gram_index")
        for table in TABLES:
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
        for table in (
            "catalog_read_active",
            "catalog_read_builds",
            "catalog_read_schema",
            "catalog_read_revision",
            "account_read_revisions",
        ):
            cursor.execute(f"DROP TABLE {table}")
        migrate()
        cursor.execute("UPDATE catalog_read_revision SET value=%s WHERE id=1", [previous[0] + 1])
        cursor.executemany("INSERT INTO account_read_revisions VALUES(%s,%s)", accounts)
