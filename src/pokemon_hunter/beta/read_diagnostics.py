"""Bounded allowlisted timing records, with no SQL, selectors or private values."""

import json
import logging
import threading
import time
import uuid
from collections import deque
from contextlib import contextmanager
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler

from django.db import connection
from django.http import JsonResponse

current = ContextVar("dex_read_diagnostic", default=None)
recent = deque(maxlen=256)
_lock = threading.Lock()
_window = 0.0
_emitted = 0
logger = logging.getLogger("dex.reads")
logger.propagate = False
logger.addHandler(logging.NullHandler())
FIELDS = frozenset(
    (
        "event",
        "phase",
        "elapsed_ms",
        "ready",
        "scope",
        "category",
        "recovery",
        "read_schema",
        "read_policy",
        "account_policy",
        "id",
        "route",
        "status",
        "sql_execute_ms",
        "sql_fetch_ms",
        "fetch_coverage",
        "decoded_coverage",
        "query_count",
        "fetched_rows",
        "decoded_rows",
        "composition_ms",
        "serialization_ms",
        "payload_bytes",
        "catalog",
        "account",
        "service_ms",
        "suppressed",
    )
)


def configure(root):
    """Ordinary local runtime only; at most 3 MiB, three private rotating files."""
    import os

    folder = root / "diagnostics"
    folder.mkdir(mode=0o700, exist_ok=True)
    if folder.is_symlink() or folder.stat().st_mode & 0o077:
        raise ValueError("Diagnostics directory must be private")
    path = folder / "reads.jsonl"
    if path.is_symlink():
        raise ValueError("Diagnostics file must be regular")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    os.close(fd)
    os.chmod(path, 0o600)

    # Rotation creates a new file using the ordinary process umask. Force 0600.
    class PrivateHandler(RotatingFileHandler):
        def _open(self):
            fd = os.open(self.baseFilename, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            return os.fdopen(fd, "a", encoding="utf-8")

    if not any(isinstance(h, RotatingFileHandler) for h in logger.handlers):
        handler = PrivateHandler(path, maxBytes=1024 * 1024, backupCount=2)
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def emit(record):
    global _window, _emitted
    safe = {key: value for key, value in record.items() if key in FIELDS}
    with _lock:
        now = time.monotonic()
        if now - _window >= 60:
            _window, _emitted = now, 0
        recent.append(safe)
        if _emitted < 60:
            logger.info(json.dumps(safe, separators=(",", ":")))
        _emitted += 1


@contextmanager
def phase(name):
    record = current.get()
    if record is None:
        yield
        return
    start = time.perf_counter()
    try:
        yield
    finally:
        record[name] = (record.get(name) or 0) + (time.perf_counter() - start) * 1000


def decoded(count=1):
    record = current.get()
    if record is not None:
        record["decoded_rows"] += count


def category(scope, value):
    record = current.get()
    if record is not None:
        record[scope] = value


def json_response(*args, **kwargs):
    with phase("serialization_ms"):
        return JsonResponse(*args, **kwargs)


class FetchCursor:
    """Time materialization separately from execution, including ORM cursors."""

    def __init__(self, cursor, record):
        self.cursor, self.record = cursor, record

    def __getattr__(self, name):
        return getattr(self.cursor, name)

    def fetch(self, method, *args):
        start = time.perf_counter()
        try:
            rows = getattr(self.cursor, method)(*args)
            self.record["fetched_rows"] += int(rows is not None) if method == "fetchone" else len(rows)
            return rows
        finally:
            self.record["sql_fetch_ms"] += (time.perf_counter() - start) * 1000

    def fetchone(self):
        return self.fetch("fetchone")

    def fetchmany(self, *args):
        return self.fetch("fetchmany", *args)

    def fetchall(self):
        return self.fetch("fetchall")

    def __iter__(self):
        return self

    def __next__(self):
        row = self.fetchone()
        if row is None:
            raise StopIteration
        return row


class Middleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from .account_read_schema import POLICY as account_policy
        from .catalog_read_schema import POLICY, VERSION

        record = dict(
            event="request",
            id=uuid.uuid4().hex,
            route="unresolved",
            status=500,
            sql_execute_ms=0.0,
            sql_fetch_ms=0.0,
            query_count=0,
            fetched_rows=0,
            decoded_rows=0,
            fetch_coverage="request_cursors",
            decoded_coverage="catalog_and_account_payload_decoders",
            composition_ms=None,
            service_ms=None,
            serialization_ms=None,
            payload_bytes=None,
            catalog="not_checked",
            account="not_checked",
            read_schema=VERSION,
            read_policy=POLICY,
            account_policy=account_policy,
        )
        token = current.set(record)
        start = time.perf_counter()

        def execute(run, sql, params, many, context):
            cursor = context["cursor"]
            if not isinstance(cursor.cursor, FetchCursor):
                cursor.cursor = FetchCursor(cursor.cursor, record)
            record["query_count"] += 1
            with phase("sql_execute_ms"):
                return run(sql, params, many, context)

        try:
            with connection.execute_wrapper(execute):
                response = self.get_response(request)
            record["status"] = response.status_code
            if not response.streaming:
                record["payload_bytes"] = len(response.content)
            response["X-Dex-Diagnostic-ID"] = record["id"]
            return response
        finally:
            match = getattr(request, "resolver_match", None)
            # Django's compiled route template, never request.path or resolver kwargs.
            record["route"] = str(match.route)[:160] if match is not None else "unresolved"
            record["elapsed_ms"] = (time.perf_counter() - start) * 1000
            current.reset(token)
            emit({k: round(v, 3) if isinstance(v, float) else v for k, v in record.items()})
