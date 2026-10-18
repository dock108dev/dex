"""Optional finite Hunter authority for the ordinary local installation.

Installation grants no acquisition. An owner-selected private document can bind
one reviewed allocation to this root, account and exact package bytes. The fixed
independent ledger survives restarts; changing a document never renews capacity.
This module never creates authorization, a ledger or provider work.
"""

import hashlib
import json
import os
import re
import stat
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from . import hunter_budget

PLAN_ID = "hunt-04-installed-v1"
LIMITS = dict(oauth=1, browse=12, detail=2, resolution=0, total=15, auction=8, buy_it_now=4, lots=8)
CONFIG_NAME = "hunter-installed.json"
MAX_CONFIG_BYTES = 8192
_FIELDS = {"version", "plan", "root", "account_id", "package_sha256", "expires_at", "selected", "limits"}
_lock = threading.RLock()
_configured = None
_parent_run_id = None


@dataclass(frozen=True)
class InstalledAuthority:
    root: Path
    account_id: str
    package_sha256: str
    expires_at: datetime
    document_sha256: str
    allowance: hunter_budget.TraversalAllowance


def package_digest():
    """Digest every installed application member, excluding interpreter caches."""
    package = Path(__file__).resolve().parents[1]
    members = {}
    for path in sorted(package.rglob("*")):
        relative = path.relative_to(package)
        if "__pycache__" in relative.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        if path.is_symlink():
            raise ValueError("Installed Hunter package identity is unavailable")
        if path.is_file():
            with path.open("rb") as source:
                members[relative.as_posix()] = hashlib.file_digest(source, "sha256").hexdigest()
    return hashlib.sha256(json.dumps(members, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def proposal(root, account_id):
    """Return an unselected review template; never write private authority."""
    return dict(
        version=1,
        plan=PLAN_ID,
        root=str(Path(root).resolve(strict=True)),
        account_id=account_id,
        package_sha256=package_digest(),
        expires_at=None,
        selected=False,
        limits=dict(LIMITS),
    )


def _document(root):
    path = root / CONFIG_NAME
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return None, None
    with os.fdopen(descriptor, "rb") as source:
        info = os.fstat(source.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_mode & 0o077
            or info.st_size > MAX_CONFIG_BYTES
        ):
            raise ValueError("Installed Hunter authority must be a private regular file")
        data = source.read(MAX_CONFIG_BYTES + 1)
    if len(data) > MAX_CONFIG_BYTES:
        raise ValueError("Installed Hunter authority exceeds its bound")
    try:
        value = json.loads(data)
    except (UnicodeError, ValueError):
        raise ValueError("Installed Hunter authority is unavailable") from None
    return value, hashlib.sha256(data).hexdigest()


def _parse(root, value, digest):
    if not isinstance(value, dict) or set(value) != _FIELDS:
        raise ValueError("Use the exact reviewed installed Hunter authority")
    if (
        type(value["version"]) is not int
        or value["version"] != 1
        or value["plan"] != PLAN_ID
        or value["root"] != str(root)
        or not isinstance(value["account_id"], str)
        or not 1 <= len(value["account_id"]) <= 160
        or type(value["selected"]) is not bool
        or value["limits"] != LIMITS
        or any(type(value["limits"].get(key)) is not int for key in LIMITS)
        or not isinstance(value["package_sha256"], str)
        or not re.fullmatch(r"[a-f0-9]{64}", value["package_sha256"])
    ):
        raise ValueError("Installed Hunter authority does not match its reviewed binding")
    if value["selected"] is False:
        return None
    try:
        expiry = datetime.fromisoformat(value["expires_at"])
        if expiry.utcoffset() != UTC.utcoffset(None) or expiry <= datetime.now(UTC):
            raise ValueError
    except (TypeError, ValueError):
        raise ValueError("Installed Hunter authority is expired or unavailable") from None
    if package_digest() != value["package_sha256"]:
        raise ValueError("Installed Hunter package differs from its selected authority")
    return InstalledAuthority(
        root,
        value["account_id"],
        value["package_sha256"],
        expiry,
        digest,
        hunter_budget.TraversalAllowance(PLAN_ID, **LIMITS),
    )


def configure():
    """Select once before ordinary workers; absence keeps production disabled."""
    from django.conf import settings

    global _configured, _parent_run_id
    with _lock:
        if _configured is not None:
            raise ValueError("Installed Hunter authority is already selected")
        if getattr(settings, "STAGING", False):
            hunter_budget.TRAVERSAL_ALLOWANCE = None
            return None
        root = Path(settings.ROOT).resolve(strict=True)
        # This authority is optional. An expired, malformed, withdrawn or
        # mismatched document disables acquisition while collection use remains
        # available. No private parse/operating-system details reach the UI.
        try:
            value, digest = _document(root)
            selected = None if value is None else _parse(root, value, digest)
        except (OSError, TypeError, ValueError):
            selected = None
        _configured, _parent_run_id = selected, None
        hunter_budget.TRAVERSAL_ALLOWANCE = None if selected is None else selected.allowance
        return selected


def _verify(selected):
    value, digest = _document(selected.root)
    if digest != selected.document_sha256 or _parse(selected.root, value, digest) != selected:
        raise ValueError("Installed Hunter authority changed or was withdrawn")


def current_allowance(actor, *, existing=None):
    """Current acquisition availability; local retained reads do not call this."""
    from . import discovery, hunter_policy

    root = discovery.settings.ROOT
    if hunter_policy.present(root):
        return hunter_policy.current(actor, root=root, existing=existing)
    if type(existing) is hunter_policy.OrdinaryAllowance:
        return None
    with _lock:
        selected = _configured
        if selected is None:
            return hunter_budget.TRAVERSAL_ALLOWANCE if existing is None else existing
        try:
            _verify(selected)
        except (OSError, ValueError):
            return None
        if actor.user_id != selected.account_id or existing is not None and existing != selected.allowance:
            return None
        if existing is None and (
            _parent_run_id is not None
            or hunter_budget.remaining_traversal(selected.root, selected.allowance) != LIMITS
        ):
            return None
        return selected.allowance


def check_dispatch(run):
    """Recheck each send/publication while preserving independent local Stop."""
    if run.operation not in {"hunter", "detail"}:
        return
    from . import hunter_policy

    allowance = getattr(run, "allowance", None)
    if run.operation == "detail":
        from . import hunter

        parent = hunter._runs.get(getattr(run, "parent_run_id", None))
        allowance = getattr(parent, "allowance", None)
    if type(allowance) is hunter_policy.OrdinaryAllowance or hunter_policy.present(run.owner[0]):
        hunter_policy.check(run)
        return
    with _lock:
        selected = _configured
        if selected is None:
            return  # Default-disabled service and the separate temporary profile remain unchanged.
        _verify(selected)
        if tuple(run.owner[:2]) != (str(selected.root), selected.account_id):
            raise ValueError("Hunter action is outside the installed root and account")
        parent = run
        if run.operation == "detail":
            from . import hunter

            parent = hunter._runs.get(getattr(run, "parent_run_id", None))
            if parent is None or parent.owner != run.owner:
                raise ValueError("Hunter details have no matching installed parent")
        if getattr(parent, "allowance", None) != selected.allowance:
            raise ValueError("Hunter action does not retain the selected installed allowance")
        ledger = hunter_budget.traversal_path(selected.root, selected.allowance)
        if ledger.parent.is_symlink() or ledger.is_symlink():
            raise ValueError("Installed Hunter accounting is unavailable")
        if ledger.exists():
            descriptor = os.open(ledger, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(descriptor) as source:
                import fcntl

                fcntl.flock(source, fcntl.LOCK_SH)
                hunter_budget._traversal_counts(source, selected.allowance)
                source.seek(0)
                if any(json.loads(line)["run_id"] != parent.id for line in source if line.strip()):
                    raise ValueError("Installed Hunter allocation already belongs to its original Hunt")
        global _parent_run_id
        if _parent_run_id is not None and _parent_run_id != parent.id:
            raise ValueError("Installed Hunter allocation cannot replace its selected Hunt")
        _parent_run_id = parent.id
