"""Preserve SQLite IMMEDIATE semantics across small PostgreSQL beta transactions.

One transaction-scoped advisory lock serializes application read/modify/write units.
Provider I/O remains outside these units. Django auth uses its normal constraints.
"""

from contextlib import contextmanager
from functools import wraps

from django.db import connection
from django.db import transaction as django_transaction


def atomic(func=None):
    if func is not None:

        @wraps(func)
        def wrapped(*args, **kwargs):
            with atomic():
                return func(*args, **kwargs)

        return wrapped

    @contextmanager
    def scope():
        with django_transaction.atomic():
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_advisory_xact_lock(41852005)")
            yield

    return scope()
