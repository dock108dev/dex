"""Explicit source-neutral offline preparation using managed snapshot authorities.

No transport, schedule, recurrence or provider allowance exists here. A supplied
already-acquired package is validated, independently admitted and staged once.
Noncontent preparation reservations survive managed-price removal and restart.
Existing acquisition journals remain separate and are never reset or renewed.
"""

import fcntl
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone

from django.conf import settings

from . import price_snapshot_contract as rules
from . import price_snapshots as storage

MAX_PREPARATIONS = 1000
MAX_SECONDS = 30


def _base():
    root = settings.ROOT.absolute()
    if root.resolve() != root or not root.is_dir():
        raise ValueError("Existing unlinked installation required")
    return storage.revocations().parent / (rules.digest(str(root)) + "-preparation")


def _safe(path):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("Linked preparation path refused")
    if path.exists() and (path.stat().st_mode & 0o077 or path.stat().st_nlink != 1 and path.is_file()):
        raise ValueError("Preparation state must be private and unlinked")


@contextmanager
def _lock():
    base = _base()
    _safe(base)
    storage.private_mkdir(base)
    path = base / "execution.lock"
    _safe(path)
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError("Reference preparation already active") from None
        yield base
    finally:
        os.close(fd)


def stop():
    """Durable Stop can interrupt work without waiting on the execution lock."""
    base = _base()
    _safe(base)
    storage.private_mkdir(base)
    with storage.locked():
        storage.atomic(base / "stop.json", True)


def resume():
    """Explicit local operator action only; does not renew a reservation."""
    with _lock() as base:
        (base / "stop.json").unlink(missing_ok=True)


def _history(base):
    path = base / "reservations.json"
    _safe(path)
    if not path.exists():
        if (base / "initialized.json").exists():
            raise ValueError("Preparation accounting missing; restore cannot renew it")
        return {}
    value = storage.read(path)
    if not isinstance(value, dict) or len(value) > MAX_PREPARATIONS:
        raise ValueError("Invalid preparation accounting")
    for key, row in value.items():
        if len(key) != 64 or any(c not in "0123456789abcdef" for c in key) or not isinstance(row, dict):
            raise ValueError("Invalid preparation reservation")
        if (
            set(row) != {"state", "at", "provider_operations"}
            or row["state"] not in {"reserved", "staged", "failed", "activated"}
            or row["provider_operations"] != 0
        ):
            raise ValueError("Invalid preparation history")
        rules.timestamp(row["at"])
    return value


def _scope(package):
    # Renaming a release/observation or recapturing it does not create new work.
    parts = rules.source_packages(package)
    return rules.digest(
        {
            key: dict(
                contract=part["contract"],
                records=sorted(
                    [
                        {k: v for k, v in row.items() if k not in {"observation_id", "captured_at"}}
                        for row in part["records"]
                    ],
                    key=rules.digest,
                ),
            )
            for key, part in sorted(parts.items())
        }
    )


def prepare(package, *, expected_current, now=None, clock=time.monotonic):
    """Validate/stage one supplied package. Failure leaves active state untouched."""
    now = now or datetime.now(timezone.utc)
    started = clock()
    with _lock() as base:

        def check():
            _safe(base / "stop.json")
            if (base / "stop.json").exists():
                raise ValueError("Reference preparation stopped")
            if clock() - started >= MAX_SECONDS:
                raise ValueError("Reference preparation deadline exceeded")

        check()
        rules.validate(package, storage.entries(), now=now)
        storage.reviewed(package)
        if package["version"] in storage.denied():
            raise ValueError("Removed release cannot be prepared again")
        if storage.state()["current"] != expected_current:
            raise ValueError("Active release changed before preparation")
        history = _history(base)
        key = _scope(package)
        if key in history or len(history) >= MAX_PREPARATIONS:
            raise ValueError("Preparation reserved previously or capacity exhausted")
        if history and now < max(rules.timestamp(r["at"]) for r in history.values()):
            raise ValueError("Preparation clock rollback")
        check()
        history[key] = dict(state="reserved", at=now.isoformat(), provider_operations=0)
        storage.atomic(base / "reservations.json", history)
        storage.atomic(base / "initialized.json", True)
        destination = storage.directory() / "staging" / (package["version"] + ".json")
        created = False
        try:
            check()
            with storage.locked():
                if storage.state()["current"] != expected_current:
                    raise ValueError("Active release changed during preparation")
                if destination.exists():
                    raise ValueError("Staging version already exists")
                storage.reviewed(package)
                check()
                storage.atomic(destination, package)
                created = True
                storage.preview(destination, now=now)
                check()
            history[key]["state"] = "staged"
            storage.atomic(base / "reservations.json", history)
        except BaseException:
            # No active pointer has changed. Reserved work remains consumed.
            if created:
                destination.unlink(missing_ok=True)
            history[key]["state"] = "failed"
            storage.atomic(base / "reservations.json", history)
            raise
        return dict(
            schema="dex-reference-preparation-v1",
            state="staged",
            version=package["version"],
            expected_current=expected_current,
            reservation=key,
            provider_operations=0,
        )


def activate(version, *, expected_current, now=None):
    """Explicit activation under Stop/overlap lock; existing lifecycle owns CAS/indexes."""
    from uuid import UUID

    if str(UUID(version)) != version:
        raise ValueError("Canonical staged version required")
    with _lock() as base:
        if (base / "stop.json").exists():
            raise ValueError("Reference preparation stopped")
        path = storage.directory() / "staging" / (version + ".json")
        package = storage.preview(path, now=now)
        key = _scope(package)
        history = _history(base)
        if history.get(key, {}).get("state") != "staged":
            raise ValueError("No matching completed preparation reservation")

        # storage.activate rechecks admission, expiry and expected_current atomically.
        def guard():
            if (base / "stop.json").exists():
                raise ValueError("Reference preparation stopped")

        result = storage.activate(path, expected_current, now=now, guard=guard)
        history[key]["state"] = "activated"
        storage.atomic(base / "reservations.json", history)
        return result
