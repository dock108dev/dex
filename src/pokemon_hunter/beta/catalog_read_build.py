"""Disposable catalog preparation from a consistent authoritative snapshot."""

import hashlib
import json
import uuid
from time import perf_counter

from django.conf import settings
from django.db import connection, transaction

from . import card_groups, collection_catalog, public_catalog, store
from .catalog_read_records import digest, encode
from .catalog_read_records import materialize as materialize
from .catalog_read_schema import POLICY, TABLES, TRIGGER_NAMES, VERSION
from .catalog_read_snapshot import snapshot


class Unavailable(Exception):
    """A fixed public repair response; diagnostic details stay server-side."""


def revision():
    return store.rows("SELECT value FROM catalog_read_revision WHERE id=1")[0]["value"]


def check_schema():
    if not settings.B4_ENABLED:
        raise Unavailable("publication_capability_unavailable")
    if connection.vendor != "sqlite":
        raise Unavailable("unsupported_database")
    if store.rows("SELECT version FROM catalog_read_schema") != [{"version": VERSION}]:
        raise Unavailable("incompatible_schema")
    coverage = store.rows(
        "SELECT (SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='catalog_batches') AS pipeline, (SELECT COUNT(*) FROM sqlite_master WHERE type='trigger' AND name IN ('cr_rev_catalog_batches_insert','cr_rev_catalog_batches_update','cr_rev_catalog_batches_delete')) AS triggers, (SELECT COUNT(*) FROM sqlite_master WHERE type='trigger' AND name IN ("
        + ",".join(["%s"] * len(TRIGGER_NAMES))
        + ")) AS required",
        TRIGGER_NAMES,
    )[0]
    if coverage["required"] != len(TRIGGER_NAMES):
        raise Unavailable("missing_revision_infrastructure")
    if coverage["pipeline"] and coverage["triggers"] != 3:
        raise Unavailable("migrate_pipeline_revision_triggers")


def prepare(*, timings=None):
    """Explicit maintenance only. A failed/interrupted candidate never replaces active state."""
    timings = timings if timings is not None else {}
    started = perf_counter()
    check_schema()
    with snapshot():
        source = revision()
        rows = collection_catalog.catalog_entries(include_archived=True)
        pokemon = {r["id"] for r in store.rows("SELECT id FROM games WHERE game_key='pokemon'")}
        aliases = store.rows("SELECT * FROM catalog_aliases")
        metadata = {r["id"]: r for r in public_catalog.cards(rows)}
    timings["snapshot_ms"] = (perf_counter() - started) * 1000
    started = perf_counter()
    data = materialize(rows, pokemon, aliases, metadata)
    common = {r[6]: r[5] for r in data["cr_groups"]}
    public_counts = {
        r[6]: json.loads(r[-2])["catalog_identity_count"]
        for r in data["cr_groups"]
        if r[0] in {"public", "shared"}
    }
    stride = 1 << (4 * max(public_counts.values(), default=0) + 3).bit_length()
    build = uuid.uuid4().int % ((1 << 63) - stride * (len(rows) + 1))
    codes = {"shared": 0, "public": 1, "retained": 2}
    data["cr_grams"] = [
        (
            scope,
            rank,
            terms + (" spublic sretained" if scope == "shared" else " s" + scope),
            build + rank * stride + public_counts.get(rank, 0) * 4 + codes[scope],
        )
        for scope, rank, terms in data["cr_grams"]
    ]
    data["cr_gram_residual"] = sorted(
        (r[0], r[3], common[r[1]], public_counts.get(r[1], 0)) for r in data["cr_grams"]
    )
    counts = {table: len(values) for table, values in data.items()}
    expected_hash = hashlib.sha256()
    for table, values in data.items():
        expected_hash.update(table.encode())
        for start in range(0, len(values), 2000):
            expected_hash.update(repr(values[start : start + 2000]).encode())
    from pathlib import Path

    package_hash = hashlib.sha256()
    for path in sorted(Path(__file__).parent.rglob("*.py")):
        package_hash.update(path.name.encode())
        package_hash.update(path.read_bytes())
    builder = package_hash.hexdigest()
    manifest = dict(
        id=build,
        revision=source,
        policy=POLICY,
        counts=encode(counts),
        checksum=expected_hash.hexdigest(),
        builder=builder,
        stride=stride,
    )
    seal = manifest_seal(manifest)
    timings["cpu_ms"] = (perf_counter() - started) * 1000
    started = perf_counter()
    with connection.cursor() as c:
        c.execute(
            "INSERT INTO catalog_read_builds VALUES(%s,%s,%s,'preparing',%s,%s,%s,%s,%s)",
            [build, source, POLICY, encode(counts), expected_hash.hexdigest(), builder, stride, seal],
        )
    for table, values in data.items():
        for start in range(0, len(values), 20000):
            chunk = values[start : start + 20000]
            with transaction.atomic(), connection.cursor() as c:
                c.executemany(
                    f"INSERT INTO {table} VALUES(" + ",".join(["%s"] * (len(chunk[0]) + 1)) + ")",
                    [(build, *row) for row in chunk],
                )
    with transaction.atomic(), connection.cursor() as c:
        c.execute("UPDATE catalog_read_builds SET status='indexing' WHERE id=%s", [build])
        c.execute(
            "INSERT INTO cr_gram_index(rowid,terms,build) SELECT doc_id,terms,build FROM cr_grams WHERE build=%s ORDER BY doc_id",
            [build],
        )
        c.execute("INSERT INTO cr_gram_index(cr_gram_index) VALUES('optimize')")
    timings["persist_ms"] = (perf_counter() - started) * 1000
    started = perf_counter()
    validate(build)
    timings["validate_ms"] = (perf_counter() - started) * 1000
    return build


def validate(build):
    """Full explicit integrity scan; not a browsing or startup operation."""
    # Validation writes the FTS integrity command and candidate status. Acquire
    # the configured IMMEDIATE maintenance transaction before reading; upgrading
    # a deferred snapshot after another writer commits fails with SQLITE_BUSY.
    with transaction.atomic():
        found = store.rows("SELECT * FROM catalog_read_builds WHERE id=%s", [build])
        if (
            not found
            or found[0]["status"] != "indexing"
            or found[0]["policy"] != POLICY
            or found[0]["seal"] != manifest_seal(found[0])
        ):
            raise Unavailable("invalid_candidate")
        expected = json.loads(found[0]["counts"])
        checksum = hashlib.sha256()
        with connection.cursor() as c:
            for table, definition in TABLES.items():
                checksum.update(table.encode())
                columns = ",".join(
                    part.strip().split()[0] for part in definition.split(", PRIMARY KEY")[0].split(",")
                )
                if table == "cr_grams":
                    columns = "scope,group_id,terms,doc_id"
                elif table == "cr_gram_residual":
                    columns = "scope,doc_id,search,public_children"
                c.execute(
                    f"SELECT {columns} FROM {table} WHERE build=%s ORDER BY "
                    + {
                        "cr_groups": "scope,id",
                        "cr_match": "scope,rank_set,id",
                        "cr_species": "scope,id",
                        "cr_children": "scope,id",
                        "cr_printings": "scope,id",
                        "cr_aliases": "scope,alias,printing_id",
                        "cr_evidence": "scope,id",
                        "cr_options": "scope,field,rank",
                        "cr_postings": "scope,field,value,group_id",
                        "cr_grams": "scope,group_id",
                        "cr_gram_residual": "scope,doc_id",
                    }[table],
                    [build],
                )
                count = 0
                while chunk := c.fetchmany(2000):
                    count += len(chunk)
                    for row in chunk:
                        if (
                            table in {"cr_groups", "cr_children", "cr_printings", "cr_evidence"}
                            and digest(row[-2]) != row[-1]
                        ):
                            raise Unavailable("corrupt_candidate")
                        validate_payload(table, row)
                    checksum.update(repr(chunk).encode())
                if count != expected[table]:
                    raise Unavailable("incomplete_candidate")
            c.execute("INSERT INTO cr_gram_index(cr_gram_index,rank) VALUES('integrity-check',1)")
            if checksum.hexdigest() != found[0]["checksum"]:
                raise Unavailable("candidate_checksum_mismatch")
            c.execute(
                "UPDATE catalog_read_builds SET status='validated',checksum=%s WHERE id=%s",
                [checksum.hexdigest(), build],
            )


def activate(build):
    """Short compare-and-swap, including authority revision. Older builds remain retained."""
    with transaction.atomic(), connection.cursor() as c:
        # Acquire the writer lock before comparison, not during preparation CPU work.
        c.execute("UPDATE catalog_read_revision SET value=value WHERE id=1")
        found = store.rows("SELECT * FROM catalog_read_builds WHERE id=%s", [build])
        if (
            not found
            or found[0]["status"] != "validated"
            or found[0]["policy"] != POLICY
            or found[0]["seal"] != manifest_seal(found[0])
        ):
            raise Unavailable("invalid_candidate")
        if found[0]["revision"] != revision():
            from .collection import Conflict

            raise Conflict("Catalog changed during preparation")
        c.execute("UPDATE catalog_read_builds SET status='ready' WHERE id=%s", [build])
        c.execute(
            "INSERT INTO catalog_read_active VALUES(1,%s) ON CONFLICT(id) DO UPDATE SET build=excluded.build",
            [build],
        )


def active(token=None):
    from .read_diagnostics import category

    category("catalog", "unavailable")
    check_schema()
    source = revision()
    current = f"{source}:{POLICY}"
    if token is not None and token != current:
        from .collection import Conflict

        raise Conflict("Catalog revision changed")
    found = store.rows(
        "SELECT b.* FROM catalog_read_active a JOIN catalog_read_builds b ON b.id=a.build WHERE a.id=1"
    )
    if not found:
        interrupted = store.rows(
            "SELECT 1 FROM catalog_read_builds WHERE status IN ('preparing','indexing') LIMIT 1"
        )
        raise Unavailable("preparation_interrupted" if interrupted else "manifest_missing")
    row = found[0]
    if row["policy"] != POLICY:
        raise Unavailable("incompatible_policy")
    if row["revision"] != source:
        raise Unavailable("catalog_stale")
    if row["status"] in {"preparing", "indexing"}:
        raise Unavailable("preparation_interrupted")
    if row["status"] != "ready":
        raise Unavailable("derived_corrupt")
    if len(row["checksum"] or "") != 64 or row["seal"] != manifest_seal(row):
        raise Unavailable("manifest_corrupt")
    documents = store.rows(
        "SELECT COUNT(*) AS n FROM cr_gram_index WHERE cr_gram_index MATCH %s", [str(found[0]["id"])]
    )[0]["n"]
    if documents != json.loads(found[0]["counts"])["cr_grams"]:
        raise Unavailable("search_index_incomplete")
    category("catalog", "ready")
    return found[0], current


def discard(build):
    """Explicit reclamation; SQLite snapshots retain rows needed by existing readers."""
    with transaction.atomic(), connection.cursor() as c:
        c.execute("UPDATE catalog_read_revision SET value=value WHERE id=1")
        if store.rows("SELECT 1 FROM catalog_read_active WHERE build=%s", [build]):
            raise ValueError("Cannot discard the active build")
        for table in TABLES:
            c.execute(f"DELETE FROM {table} WHERE build=%s", [build])
        c.execute("DELETE FROM catalog_read_builds WHERE id=%s", [build])


def validate_payload(table, row):
    if table == "cr_groups":
        group = json.loads(row[-2])
        if set(group) != set(card_groups.SUMMARY_FIELDS):
            raise Unavailable("group_allowlist")
        identity = [group[f] for f in card_groups.IDENTITY_FIELDS] + [group["pokemon_dex"]]
        # dg1 deliberately preserves literal input and original JSON ordering.
        canonical = json.dumps(identity, ensure_ascii=False, separators=(",", ":"))
        if group["id"] != card_groups.NAMESPACE + digest(canonical):
            raise Unavailable("identity_mismatch")
    elif table in {"cr_children", "cr_printings"}:
        card = json.loads(row[-2])
        allowed = set(public_catalog.CARD_FIELDS) | {
            "pokemon_dex",
            "rarity",
            "supertype",
            "era",
            "language",
            "available",
        }
        if set(card) != allowed:
            raise Unavailable("printing_allowlist")
        for field in public_catalog.CARD_FIELDS:
            value = card[field]
            if field == "unresolved_fields":
                if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                    raise Unavailable("printing_type")
            elif value is not None and not isinstance(value, str):
                raise Unavailable("printing_type")
    elif table == "cr_evidence":
        record = json.loads(row[-2])
        if set(record) - {"kind", "printing_ids", "missing_fields", "label", "identities"}:
            raise Unavailable("evidence_allowlist")


def manifest_seal(row):
    return digest(
        encode(
            {key: row[key] for key in ("id", "revision", "policy", "counts", "checksum", "builder", "stride")}
        )
    )


def repair_index():
    """Explicit corruption recovery; never called by a read or ordinary startup."""
    check_schema()
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            "UPDATE catalog_read_builds SET status='corrupt' WHERE status IN ('ready','validated')"
        )
        cursor.execute("INSERT INTO cr_gram_index(cr_gram_index) VALUES('rebuild')")
        cursor.execute("INSERT INTO cr_gram_index(cr_gram_index,rank) VALUES('integrity-check',1)")
