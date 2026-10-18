"""Fixed owner-selected qualification allowances, independent of temporary results.

Only consumed operation metadata is retained. File locking makes concurrent
workers/processes share the same allowance; failures and uncertain sends count.
There is deliberately no reset, date rollover, refund or API-selected allowance.
"""

import fcntl
import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .discovery_transport import ProviderFailure

ALLOWANCE = "hunt-01-20261016"
LIMITS = {"oauth": 1, "browse": 2, "total": 3, "auction": 1, "buy_it_now": 1}
MAX_LEDGER_BYTES = 65536


def path(root):
    root = Path(root).resolve()
    key = hashlib.sha256(str(root).encode()).hexdigest()
    return root.parent / ".dex-shopping-discovery" / key / (ALLOWANCE + ".jsonl")


def _counts(stream):
    stream.seek(0)
    data = stream.read(MAX_LEDGER_BYTES + 1)
    if len(data) > MAX_LEDGER_BYTES:
        raise ValueError("Hunter allowance accounting exceeds its bound")
    counts = {key: 0 for key in LIMITS}
    for line in data.splitlines():
        row = json.loads(line)
        if (
            set(row) != {"allowance", "run_id", "stage", "lane", "at"}
            or row["allowance"] != ALLOWANCE
            or row["stage"] not in {"oauth", "browse"}
            or row["lane"] not in ({"auction", "buy_it_now"} if row["stage"] == "browse" else {None})
        ):
            raise ValueError("Hunter allowance accounting is unavailable")
        counts[row["stage"]] += 1
        counts["total"] += 1
        if row["lane"] is not None:
            counts[row["lane"]] += 1
    return counts


def consume(run, stage):
    if stage not in {"oauth", "browse"}:
        raise ProviderFailure(stage)
    lane = getattr(run, "current_lane", None) if stage == "browse" else None
    if stage == "browse" and lane not in {"auction", "buy_it_now"}:
        raise ProviderFailure(stage)
    target = path(run.owner[0])
    try:
        if target.parent.is_symlink():
            raise ValueError("Hunter allowance accounting is unavailable")
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd = os.open(target, os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "r+") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            counts = _counts(stream)
            if (
                counts[stage] >= LIMITS[stage]
                or counts["total"] >= LIMITS["total"]
                or lane is not None
                and counts[lane] >= LIMITS[lane]
            ):
                raise ValueError("The selected Hunter allowance is consumed")
            stream.write(
                json.dumps(
                    {
                        "allowance": ALLOWANCE,
                        "run_id": run.id,
                        "stage": stage,
                        "lane": lane,
                        "at": datetime.now(UTC).isoformat(),
                    },
                    separators=(",", ":"),
                )
                + "\n"
            )
            stream.flush()
            os.fsync(stream.fileno())
    except (OSError, ValueError, TypeError):
        raise ProviderFailure(stage) from None


def remaining(root):
    """Read-only metadata; an absent ledger has consumed nothing."""
    target = path(root)
    try:
        fd = os.open(target, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return dict(LIMITS)
    with os.fdopen(fd) as stream:
        fcntl.flock(stream, fcntl.LOCK_SH)
        counts = _counts(stream)
    return {key: max(0, value - counts[key]) for key, value in LIMITS.items()}


# Traversal has a distinct allowance contract. The original fixed identity, path,
# limits and consumed records above remain unchanged. No production allowance
# is activated by this implementation. Future authorization must select exact
# numeric limits in trusted server configuration, never in an HTTP action.
TRAVERSAL_ALLOWANCE = None
TRAVERSAL_LIMIT_KEYS = ("oauth", "browse", "detail", "resolution", "total", "auction", "buy_it_now", "lots")
MAX_TRAVERSAL_LEDGER_BYTES = 1024 * 1024


@dataclass(frozen=True)
class TraversalAllowance:
    id: str
    oauth: int = 0
    browse: int = 0
    detail: int = 0
    resolution: int = 0
    total: int = 0
    auction: int = 0
    buy_it_now: int = 0
    lots: int = 0

    def __post_init__(self):
        if (
            not isinstance(self.id, str)
            or not (
                re.fullmatch(r"hunt-04-[a-z0-9][a-z0-9-]{0,80}", self.id)
                or self.id == "hunt-07-completion-v1"
            )
            or any(
                type(getattr(self, key)) is not int or not 0 <= getattr(self, key) <= 1000
                for key in TRAVERSAL_LIMIT_KEYS
            )
            or self.total < sum(getattr(self, key) for key in ("oauth", "browse", "detail", "resolution"))
            or self.auction + self.buy_it_now < self.browse
            or self.lots > self.total
            or self.id == "hunt-07-completion-v1"
            and self.limits
            != dict(oauth=1, browse=12, detail=2, resolution=0, total=15, auction=8, buy_it_now=4, lots=8)
        ):
            raise ValueError("Choose an explicitly authorized finite traversal allowance")

    @property
    def limits(self):
        return {key: getattr(self, key) for key in TRAVERSAL_LIMIT_KEYS}

    @property
    def fingerprint(self):
        return hashlib.sha256(json.dumps(self.limits, sort_keys=True).encode()).hexdigest()


def traversal_path(root, allowance):
    if type(allowance) is not TraversalAllowance:
        raise ValueError("The traversal allowance is not activated")
    root = Path(root).resolve()
    key = hashlib.sha256(str(root).encode()).hexdigest()
    return root.parent / ".dex-shopping-discovery" / key / (allowance.id + ".jsonl")


def _traversal_counts(stream, allowance):
    stream.seek(0)
    data = stream.read(MAX_TRAVERSAL_LEDGER_BYTES + 1)
    if len(data.encode()) > MAX_TRAVERSAL_LEDGER_BYTES:
        raise ValueError("Traversal allowance accounting exceeds its bound")
    counts = dict.fromkeys(TRAVERSAL_LIMIT_KEYS, 0)
    dispatched = set()
    for line in data.splitlines():
        row = json.loads(line)
        if (
            not isinstance(row, dict)
            or set(row) != {"allowance", "limits", "run_id", "stage", "lane", "scope", "dispatch_id", "at"}
            or row["allowance"] != allowance.id
            or row["limits"] != allowance.fingerprint
            or row["stage"] not in {"oauth", "browse", "detail", "resolution"}
            or row["scope"] not in {"singles", "lots"}
            or row["lane"] not in ({"auction", "buy_it_now"} if row["stage"] == "browse" else {None})
            or any(
                not isinstance(row[key], str) or not row[key] or len(row[key]) > 200
                for key in ("run_id", "dispatch_id")
            )
        ):
            raise ValueError("Traversal allowance accounting is unavailable")
        key = (row["run_id"], row["stage"], row["dispatch_id"])
        if key in dispatched:
            raise ValueError("Traversal allowance contains a duplicate dispatch")
        dispatched.add(key)
        counts[row["stage"]] += 1
        counts["total"] += 1
        if row["lane"] is not None:
            counts[row["lane"]] += 1
        if row["stage"] != "oauth" and row["scope"] == "lots":
            counts["lots"] += 1
    if any(counts[key] > allowance.limits[key] for key in counts):
        raise ValueError("Traversal allowance accounting exceeds its authorization")
    return counts, dispatched


def consume_traversal(root, run_id, stage, lane=None, *, dispatch_id, allowance=None, scope="singles"):
    """Durably admit exactly one send before transport, including uncertain sends.

    The stable dispatch ID is the captured cursor (or an explicit detail ID).
    Concurrent workers cannot admit that operation twice. There is no refund,
    reset, day boundary or hidden allowance fallback.
    """
    from .hunter_policy import OrdinaryAllowance

    if type(allowance) is OrdinaryAllowance:
        from . import hunter_policy

        return hunter_policy.consume(
            root, run_id, stage, lane, dispatch_id=dispatch_id, allowance=allowance, scope=scope
        )
    if (
        type(allowance) is not TraversalAllowance
        or stage not in {"oauth", "browse", "detail", "resolution"}
        or scope not in {"singles", "lots"}
        or lane not in ({"auction", "buy_it_now"} if stage == "browse" else {None})
        or any(not isinstance(value, str) or not value or len(value) > 200 for value in (run_id, dispatch_id))
    ):
        raise ProviderFailure(stage)
    target = traversal_path(root, allowance)
    try:
        if target.parent.is_symlink():
            raise ValueError("Traversal allowance accounting is unavailable")
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd = os.open(target, os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "r+") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            counts, dispatched = _traversal_counts(stream, allowance)
            keys = [stage, "total"] + ([lane] if lane is not None else [])
            if scope == "lots" and stage != "oauth":
                keys.append("lots")
            if (run_id, stage, dispatch_id) in dispatched or any(
                counts[key] >= allowance.limits[key] for key in keys
            ):
                raise ValueError("The traversal operation is already consumed or unavailable")
            stream.write(
                json.dumps(
                    {
                        "allowance": allowance.id,
                        "limits": allowance.fingerprint,
                        "run_id": run_id,
                        "stage": stage,
                        "lane": lane,
                        "scope": scope,
                        "dispatch_id": dispatch_id,
                        "at": datetime.now(UTC).isoformat(),
                    },
                    separators=(",", ":"),
                )
                + "\n"
            )
            stream.flush()
            os.fsync(stream.fileno())
    except (OSError, ValueError, TypeError):
        raise ProviderFailure(stage) from None


def remaining_traversal(root, allowance=None):
    """Read only. Disabled production configuration reports zero capacity."""
    from .hunter_policy import OrdinaryAllowance

    if type(allowance) is OrdinaryAllowance:
        from . import hunter_policy

        return hunter_policy.remaining(root, allowance)
    if allowance is None:
        return dict.fromkeys(TRAVERSAL_LIMIT_KEYS, 0)
    target = traversal_path(root, allowance)
    try:
        fd = os.open(target, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return allowance.limits
    with os.fdopen(fd) as stream:
        fcntl.flock(stream, fcntl.LOCK_SH)
        counts, _ = _traversal_counts(stream, allowance)
    return {key: max(0, value - counts[key]) for key, value in allowance.limits.items()}


def is_traversal_allowance(allowance):
    """Historical fixed and deliberately selected ordinary policies are distinct."""
    from .hunter_policy import OrdinaryAllowance

    return type(allowance) in {TraversalAllowance, OrdinaryAllowance}
