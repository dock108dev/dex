"""Deferred SQLite snapshots without changing mutation transaction semantics."""

from contextlib import contextmanager

from django.db import connection, transaction


@contextmanager
def snapshot():
    if connection.vendor != "sqlite":
        from .catalog_read_build import Unavailable

        raise Unavailable("unsupported_database")
    if connection.in_atomic_block:
        raise RuntimeError("Catalog read snapshots require an outermost transaction")
    connection.ensure_connection()
    if getattr(connection, "_catalog_read_connection", None) is not connection.connection:
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA cache_size=-65536")
            cursor.execute("PRAGMA temp_store=MEMORY")
        connection._catalog_read_connection = connection.connection
    mode = connection.transaction_mode
    connection.transaction_mode = "DEFERRED"
    try:
        with transaction.atomic():
            yield
    finally:
        connection.transaction_mode = mode
