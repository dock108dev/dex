"""Read-only bounded readiness. Never migrate, prepare, replay or start workers."""

from contextlib import contextmanager
from time import perf_counter

from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from . import account_read_build as accounts
from . import account_read_schema as account_schema
from . import catalog_read_build as catalog
from . import store
from .catalog_read_schema import POLICY, VERSION
from .catalog_read_snapshot import snapshot

# Reserve the rest of the two-second spawn budget for imports and listener setup.
CHECK_SECONDS = 0.5
ACTIONS = {
    "ready": "none",
    "schema_missing": "migrate_then_prepare",
    "incompatible_schema": "select_compatible_runtime",
    "incompatible_policy": "prepare_then_activate",
    "manifest_missing": "prepare_then_activate",
    "preparation_interrupted": "prepare_new_candidate_then_activate",
    "catalog_stale": "prepare_then_activate",
    "manifest_corrupt": "prepare_new_candidate_then_activate",
    "derived_corrupt": "repair_derived_then_prepare",
    "infrastructure_missing": "repair_derived_schema_then_prepare",
    "account_not_prepared": "prepare_account",
    "account_stale": "prepare_account",
    "account_policy_incompatible": "prepare_account_goal_headers",
    "account_corrupt": "prepare_account",
    "storage_unavailable": "inspect_storage_preserve_authority",
    "check_deadline": "inspect_storage_contention",
    "unsupported_database": "use_qualified_runtime",
    "publication_capability_unavailable": "inspect_capabilities",
}


@contextmanager
def bounded():
    connection.ensure_connection()
    started = perf_counter()
    db = connection.connection
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA busy_timeout")
        timeout = cursor.fetchone()[0]
        cursor.execute("PRAGMA busy_timeout=100")
    db.set_progress_handler(lambda: int(perf_counter() - started > CHECK_SECONDS), 1000)
    try:
        yield
        if perf_counter() - started > CHECK_SECONDS:
            raise catalog.Unavailable("check_deadline")
    finally:
        db.set_progress_handler(None, 0)
        with connection.cursor() as cursor:
            cursor.execute(f"PRAGMA busy_timeout={int(timeout)}")


def result(code, scope):
    return dict(
        ready=code == "ready",
        scope=scope,
        category=code,
        recovery=ACTIONS[code],
        read_schema=VERSION,
        read_policy=POLICY,
        account_policy=account_schema.POLICY if scope == "account" else None,
    )


def inspect(actor=None):
    scope = "account" if actor is not None else "catalog"
    if connection.vendor != "sqlite":
        return result("unsupported_database", scope)
    if actor is not None:
        actor = store.verified(actor)
    started = perf_counter()
    try:
        with bounded(), snapshot():
            if not store.rows(
                "SELECT 1 FROM sqlite_master WHERE name='catalog_read_schema' AND type='table'"
            ):
                raise catalog.Unavailable("schema_missing")
            from .read_infrastructure import check

            check()
            manifest, token = catalog.active()
            if actor is not None:
                if not store.rows(
                    "SELECT 1 FROM sqlite_master WHERE name='account_read_schema' AND type='table'"
                ):
                    raise catalog.Unavailable("schema_missing")
                check(account=True)
                account_schema.check()
                accounts.state(actor, token)
        if actor is not None:
            store.verified(actor)
        code = "ready"
    except catalog.Unavailable as exc:
        raw = exc.args[0] if exc.args else ""
        code = (
            raw
            if raw in ACTIONS
            else {
                "missing_revision_infrastructure": "infrastructure_missing",
                "migrate_pipeline_revision_triggers": "infrastructure_missing",
                "account_schema_infrastructure": "infrastructure_missing",
                "search_index_incomplete": "derived_corrupt",
                "account_revision_unavailable": "account_stale",
            }.get(raw, "derived_corrupt")
        )
    except (DatabaseError, ValueError, TypeError, KeyError, IndexError):
        # Never infer that authoritative records are safe to rebuild from a SQLite error.
        code = "check_deadline" if perf_counter() - started >= CHECK_SECONDS else "storage_unavailable"
    return result(code, scope)


def response(data, status=None):
    reply = JsonResponse(data, status=status or (200 if data.get("ready") else 503))
    reply["Cache-Control"] = "private, no-store"
    if reply.status_code == 503:
        # No automatic retry/preparation is implied by this advice.
        data = dict(data, code="read_state_unavailable", error="read_state_unavailable")
        reply = JsonResponse(data, status=503)
        reply["Cache-Control"] = "private, no-store"
    return reply


@require_GET
def live(request):
    return response(dict(alive=True), 200)


@require_GET
def ready(request):
    return response(inspect())


@require_GET
def account(request):
    from .views import actor

    try:
        if not request.user.is_authenticated:
            raise PermissionDenied
        who = actor(request)
        expected = request.headers.get("X-Dex-Read-Account")
        if expected is not None and expected != who.user_id:
            raise PermissionDenied
        return response(inspect(who))
    except PermissionDenied:
        return response(dict(error="permission_denied"), 403)


def startup():
    from .read_diagnostics import emit

    started = perf_counter()
    state = inspect()
    emit(
        dict(
            event="startup",
            phase="catalog_validation",
            elapsed_ms=round((perf_counter() - started) * 1000, 3),
            **state,
        )
    )
    # Failure keeps sign-in and recovery reachable. Browsing revalidates independently.
    connection.close()
    return state
