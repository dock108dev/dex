"""Process-local, opt-in Hunter execution profile; never selected by HTTP or env.

The guarded operator verifies its frozen identity and independent authorizations
before calling ``configure`` and the ordinary ``cli.setup``. This module neither
migrates state nor grants acquisition capacity. Ordinary startup is unchanged.
"""

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

PROFILE = "hunter-execution-v1"
ORIGIN = "http://127.0.0.1:8011"
ALLOWED_ACTIONS = (
    "sign_in",
    "sign_out",
    "hunter_page",
    "hunter_metadata",
    "hunter_received_results",
    "hunt_both_once",
    "explicit_continue",
    "parent_stop",
    "local_lot_analysis",
    "local_lot_correction",
    "selected_detail_intent",
    "selected_official_details",
    "detail_status",
    "detail_stop",
    "hunter_assets",
    "authorized_catalog_artwork",
)
ALLOWED_WORKERS = (
    "price_snapshot_expiry",
    "explicit_hunter_acquisition",
    "explicit_selected_detail",
    "temporary_lease_and_action_deadline_timers",
)
EXPECTED_WRITES = (
    "auth_user.last_login",
    "django_session",
    "axes_accessattempt",
    "axes_accesslog",
    "managed_price_snapshot_expiry_and_withdrawal_cleanup",
    "independent_source_revocation_registries",
    "independent_acquisition_attempt_journals",
    "temporary_process_memory_only_for_summaries_details_reviews",
)
ASSETS = frozenset(
    {
        "glass.css",
        "collection.css",
        "collection-base.css",
        "collection-browse.css",
        "navigation.js",
        "hunter.css",
        "hunter.js",
        "listing-time.js",
        "hunter-review.js",
    }
)
PLAN_LIMITS = dict(oauth=1, browse=12, detail=2, resolution=0, total=15, auction=8, buy_it_now=4, lots=8)
PLAN_ID = "hunt-04-qualification-v1"
COMPLETION_PLAN_ID = "hunt-07-completion-v1"


@dataclass(frozen=True)
class ExecutionProfile:
    account_id: str
    root: Path
    configuration_root: Path | None = None
    authorization_check: Callable | None = field(default=None, repr=False, compare=False)
    name: str = PROFILE
    plan_id: str = PLAN_ID


_configured = None
_start_lock = threading.Lock()
_started = False


def current():
    return _configured


def configure(account_id, root, *, configuration_root=None, authorization_check=None, plan_id=PLAN_ID):
    """Select a verified profile before Django setup, without reads that mutate.

    Only the trusted operator calls this function. Its identity/preflight checks
    precede selection; no environment variable can activate this profile.
    """
    global _configured
    from django.conf import settings

    from .staging_config import profile

    if _configured is not None or settings.configured or profile() != "local":
        raise RuntimeError("Hunter execution must be selected once before local application setup")
    if (
        not isinstance(account_id, str)
        or not account_id
        or len(account_id) > 200
        or account_id != account_id.strip()
        or any(ord(char) < 32 for char in account_id)
    ):
        raise ValueError("A verified execution account is required")
    root = Path(root)
    if not root.is_absolute() or not root.is_dir():
        raise ValueError("A verified existing execution root is required")
    root = root.resolve(strict=True)
    if configuration_root is not None:
        configuration_root = Path(configuration_root)
        if not configuration_root.is_absolute() or not configuration_root.is_dir():
            raise ValueError("A verified existing configuration root is required")
        configuration_root = configuration_root.resolve(strict=True)
    if authorization_check is not None and not callable(authorization_check):
        raise ValueError("The acquisition authorization boundary must be a trusted callable")
    if plan_id not in {PLAN_ID, COMPLETION_PLAN_ID}:
        raise ValueError("Only the reviewed fixed execution plans are supported")
    _configured = ExecutionProfile(account_id, root, configuration_root, authorization_check, plan_id=plan_id)
    return _configured


def apply_settings(values):
    """Called only by settings import; fail before startup workers or requests."""
    selected = current()
    if selected is None:
        return
    if values["STAGING"] or values["ROOT"] != selected.root or not values["B2_ENABLED"]:
        raise RuntimeError("Hunter execution requires the verified local collection root")
    values["HUNTER_EXECUTION_PROFILE"] = PROFILE
    values["ROOT_URLCONF"] = "pokemon_hunter.beta.hunter_profile_urls"
    values["LOGIN_REDIRECT_URL"] = "/shopping/hunter/"
    values["LOGOUT_REDIRECT_URL"] = "/login/"
    # The route allowlist is authoritative. Disabling these presentation flags
    # also prevents accidental scan/body-limit or photo configuration expansion.
    values["B3_ENABLED"] = values["B4_ENABLED"] = False
    auth = "django.contrib.auth.middleware.AuthenticationMiddleware"
    values["MIDDLEWARE"].insert(values["MIDDLEWARE"].index(auth) + 1, __name__ + ".ExpectedAccountMiddleware")


def require_current():
    from django.conf import settings

    selected = current()
    if (
        selected is None
        or settings.ROOT != selected.root
        or getattr(settings, "HUNTER_EXECUTION_PROFILE", None) != PROFILE
        or settings.ROOT_URLCONF != "pokemon_hunter.beta.hunter_profile_urls"
        or getattr(settings, "STAGING", False)
    ):
        raise RuntimeError("The verified Hunter execution profile is unavailable")
    return selected


class ExpectedAccountMiddleware:
    """Re-resolve active account authority on every authenticated request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.core.exceptions import PermissionDenied

        from . import security, store

        selected = require_current()
        if request.user.is_authenticated:
            try:
                who = store.principal(request.user.pk)
                if who.user_id != selected.account_id:
                    raise PermissionDenied
            except PermissionDenied:
                return security.forbidden("This sign-in is outside the selected Hunter execution account")
        return self.get_response(request)


def start_once(request):
    """One captured Both traversal; HTTP cannot replace the frozen plan."""
    from . import hunter_budget, hunter_views
    from .collection_views import body

    global _started
    selected = require_current()
    require_acquisition()
    if body(request) != {"scope": "both"}:
        raise ValueError("The selected execution requires one Both Hunt with no replacement fields")
    with _start_lock:
        allowance = hunter_budget.TRAVERSAL_ALLOWANCE
        if (
            type(allowance) is not hunter_budget.TraversalAllowance
            or selected.plan_id not in {PLAN_ID, COMPLETION_PLAN_ID}
            or allowance.id != selected.plan_id
            or allowance.limits != PLAN_LIMITS
        ):
            raise ValueError("The exact finite execution allowance is not authorized")
        remaining = hunter_budget.remaining_traversal(selected.root, allowance)
        untouched = (
            remaining == PLAN_LIMITS
            if selected.plan_id == COMPLETION_PLAN_ID
            else remaining["browse"] == PLAN_LIMITS["browse"]
        )
        if _started or not untouched:
            raise ValueError(
                "This execution already selected a Hunt; no restart or replacement traversal is permitted"
            )
        # An uncertain/failed start must not silently select a replacement run.
        _started = True
        return hunter_views.hunts(request)


def require_acquisition():
    """An active profile alone grants no provider authorization."""
    selected = require_current()
    if selected.authorization_check is None:
        raise ValueError("Separate finite provider authorization is unavailable")
    selected.authorization_check()


def check_dispatch(run):
    """Recheck trusted authorization at each send and before body publication."""
    selected = current()
    if selected is None:
        return
    if run.operation not in {"hunter", "detail"} or tuple(run.owner[:2]) != (
        str(selected.root),
        selected.account_id,
    ):
        raise ValueError("The action is outside the selected Hunter execution identity")
    if selected.plan_id == COMPLETION_PLAN_ID:
        from .hunter_budget import TraversalAllowance

        allowance = getattr(run, "allowance", None)
        if run.operation == "detail":
            from . import hunter

            parent = hunter._runs.get(getattr(run, "parent_run_id", None))
            if parent is None or parent.owner != run.owner:
                raise ValueError("The detail action has no matching completion parent")
            allowance = parent.allowance
        if (
            type(allowance) is not TraversalAllowance
            or allowance.id != COMPLETION_PLAN_ID
            or allowance.limits != PLAN_LIMITS
        ):
            raise ValueError("The action does not retain the reviewed completion allowance")
    require_acquisition()


def shutdown():
    """Cancel before erasing leased content; late workers cannot publish it."""
    from . import hunter, hunter_lot_details, hunter_lots

    with hunter._lock:
        parents = list(hunter._runs)
    for key in parents:
        hunter._expire(key)
    # Also remove an orphan detail action defensively. Workers retain cancel
    # tokens and recheck them under the shared parent lock before publication.
    with hunter_lot_details._lock:
        details = list(hunter_lot_details._runs)
    for key in details:
        hunter_lot_details._expire(key)
    with hunter._lock:
        hunter._runs.clear()
    with hunter_lots._lock:
        hunter_lots._reviews.clear()


def serve():
    """Run the fixed-origin profile; the only startup worker prunes prices."""
    require_current()
    import uvicorn

    from .asgi import get_asgi_application
    from .price_snapshots import expiry_worker

    stop = threading.Event()
    worker = None
    try:
        application = get_asgi_application()
        worker = threading.Thread(target=expiry_worker, args=(stop,), daemon=True, name="dex-price-expiry")
        worker.start()
        uvicorn.run(
            application,
            host="127.0.0.1",
            port=8011,
            access_log=False,
            proxy_headers=False,
            log_level="warning",
        )
    finally:
        shutdown()
        stop.set()
        if worker is not None and worker.ident is not None:
            worker.join(timeout=5)
            if worker.is_alive():
                from .diagnostics import failure

                failure("price_worker_shutdown_incomplete", TimeoutError())
