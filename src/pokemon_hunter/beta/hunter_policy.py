"""Owner-selected everyday Hunter authority and append-only durable consumption.

The private journal is independent of historical qualification ledgers. One
installation lock serializes selection, parent capture and admission across
workers. Every admitted operation is fsynced before transport; no refund exists.
Only explicit selection creates authority, and reads never create files.
"""

import fcntl
import hashlib
import json
import os
import re
import stat
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import PermissionDenied

from . import store
from .discovery_transport import ProviderFailure

CONTRACT = "hunt-09-daily-v1"
CONFIG_NAME = "hunter-policy.json"
JOURNAL_NAME = "hunter-usage.jsonl"
LOCK_NAME = "hunter-policy.lock"
MAX_JOURNAL_BYTES = 32 * 1024 * 1024
LIMITS = dict(oauth=1, browse=12, detail=2, resolution=0, total=15, auction=8, buy_it_now=4, lots=8)
_FIELDS = {"enabled", "per_hunt_limit", "daily_limit", "timezone", "recurring", "expires_at", "revision"}


def _now():
    return datetime.now(UTC)


def _root(root=None):
    if root is None:
        from django.conf import settings

        root = settings.ROOT
    return Path(root).resolve(strict=True)


def _storage(root):
    key = hashlib.sha256(str(root).encode()).hexdigest()
    return root.parent / ".dex-shopping-discovery" / key / "everyday"


def _directory(root, *, create=False):
    target = _storage(root)
    for directory in (target.parent.parent, target.parent, target):
        if create:
            try:
                directory.mkdir(mode=0o700)
                parent_fd = os.open(directory.parent, os.O_RDONLY)
                try:
                    os.fsync(parent_fd)
                finally:
                    os.close(parent_fd)
            except FileExistsError:
                pass
        info = directory.lstat()
        if (
            not stat.S_ISDIR(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_mode & (0o022 if directory == target.parent.parent else 0o077)
        ):
            raise ValueError("Hunter independent accounting directory is unavailable")
    return target


def _owner(actor):
    actor = store.verified(actor)
    if getattr(actor, "role", None) != "owner":
        raise PermissionDenied
    return actor


def _digest():
    from .hunter_installed import package_digest

    return package_digest()


def _stamp(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None or result.utcoffset() != timedelta(0):
        raise ValueError("Hunter accounting requires UTC timestamps")
    return result


def _window(now, timezone):
    zone = ZoneInfo(timezone)
    day = now.astimezone(zone).date()
    start = datetime.combine(day, time.min, zone).astimezone(UTC)
    end = datetime.combine(day + timedelta(days=1), time.min, zone).astimezone(UTC)
    return start, end


def _private(fd, maximum):
    info = os.fstat(fd)
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.getuid()
        or info.st_mode & 0o077
        or info.st_nlink != 1
        or info.st_size > maximum
    ):
        raise ValueError("Hunter usage storage is unavailable")


def _read(path, maximum):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        _private(stream.fileno(), maximum)
        data = stream.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError("Hunter usage storage exceeds its bound")
    return data


@contextmanager
def _locked(root, *, create=False):
    target = _directory(root, create=create) / LOCK_NAME
    flags = os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK
    fd = os.open(target, flags | (os.O_CREAT if create else 0), 0o600)
    with os.fdopen(fd, "r+b") as stream:
        _private(stream.fileno(), 512)
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield stream


def present(root=None):
    """Whether ordinary policy storage exists, including damaged/incomplete state."""
    root = _root(root)
    if os.path.lexists(root / CONFIG_NAME) or os.path.lexists(_storage(root) / JOURNAL_NAME):
        return True
    try:
        return (_storage(root) / LOCK_NAME).lstat().st_size > 0
    except FileNotFoundError:
        return False
    except OSError:
        return True  # Inaccessible accounting must never enable historical fallback.


def _settings(raw, *, now):
    if not isinstance(raw, dict) or set(raw) != _FIELDS:
        raise ValueError("Choose the displayed Hunter usage settings only")
    if (
        type(raw["enabled"]) is not bool
        or type(raw["recurring"]) is not bool
        or type(raw["per_hunt_limit"]) is not int
        or not 1 <= raw["per_hunt_limit"] <= 15
        or type(raw["daily_limit"]) is not int
        or not 1 <= raw["daily_limit"] <= 1000
        or type(raw["revision"]) is not int
        or raw["revision"] < 0
        or not isinstance(raw["timezone"], str)
        or len(raw["timezone"]) > 80
    ):
        raise ValueError("Select a per-Hunt limit from 1 to 15 and daily limit from 1 to 1000")
    try:
        ZoneInfo(raw["timezone"])
    except (ValueError, ZoneInfoNotFoundError):
        raise ValueError("Choose a valid daily-window timezone") from None
    expiry = raw["expires_at"]
    if expiry is not None:
        try:
            expiry = _stamp(expiry)
        except (ValueError, TypeError):
            raise ValueError("Choose a future UTC expiry or leave expiry empty") from None
        if expiry <= now and raw["enabled"]:
            raise ValueError("Choose a future expiry")
    return {**raw, "expires_at": expiry.isoformat() if expiry else None}


def _load(root):
    marker = json.loads(_read(root / CONFIG_NAME, 8192))
    if (
        not isinstance(marker, dict)
        or set(marker) != {"version", "contract", "root", "account_id", "id"}
        or type(marker["version"]) is not int
        or marker["version"] != 1
        or marker["contract"] != CONTRACT
        or marker["root"] != str(root)
        or not isinstance(marker["account_id"], str)
        or not marker["account_id"]
        or not re.fullmatch(r"[a-f0-9]{32}", marker["id"])
    ):
        raise ValueError("Hunter policy binding is unavailable")
    anchor = json.loads(_read(_directory(root) / LOCK_NAME, 512))
    if (
        not isinstance(anchor, dict)
        or set(anchor) != {"id", "sequence", "hash"}
        or anchor["id"] != marker["id"]
    ):
        raise ValueError("Hunter durable installation binding differs")
    data = _read(_directory(root) / JOURNAL_NAME, MAX_JOURNAL_BYTES)
    if not data or not data.endswith(b"\n"):
        raise ValueError("Hunter usage accounting is unavailable")
    rows, previous, policy, parents, operations, package = [], "0" * 64, None, {}, [], None
    last, dispatched = None, set()
    for line in data.splitlines():
        row = json.loads(line)
        if (
            not isinstance(row, dict)
            or set(row) != {"sequence", "previous", "policy_id", "at", "kind", "data", "hash"}
            or type(row["sequence"]) is not int
            or row["sequence"] != len(rows) + 1
            or row["previous"] != previous
            or row["policy_id"] != marker["id"]
            or not isinstance(row["data"], dict)
        ):
            raise ValueError("Hunter usage accounting is unavailable")
        payload = {k: v for k, v in row.items() if k != "hash"}
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        at = _stamp(row["at"])
        if digest != row["hash"] or last is not None and at < last:
            raise ValueError("Hunter usage accounting is unavailable")
        fields = row["data"]
        if row["kind"] == "selection":
            if set(fields) != _FIELDS | {"window_start", "window_end", "package"}:
                raise ValueError("Hunter policy revision is unavailable")
            checked = _settings({k: fields[k] for k in _FIELDS}, now=at - timedelta(microseconds=1))
            if checked["revision"] != (1 if policy is None else policy["revision"] + 1):
                raise ValueError("Hunter policy revision is unavailable")
            if not re.fullmatch(r"[a-f0-9]{64}", fields["package"]):
                raise ValueError("Hunter package binding is unavailable")
            if _stamp(fields["window_start"]) >= _stamp(fields["window_end"]):
                raise ValueError("Hunter daily window is unavailable")
            policy, package = fields, fields["package"]
        elif row["kind"] == "rebind":
            if (
                policy is None
                or set(fields) != {"previous_package", "package", "contract"}
                or fields["previous_package"] != package
                or fields["contract"] != CONTRACT
                or not re.fullmatch(r"[a-f0-9]{64}", fields["package"])
            ):
                raise ValueError("Hunter qualified package binding is unavailable")
            package = fields["package"]
        elif row["kind"] == "parent":
            if (
                policy is None
                or set(fields)
                != {"run_id", "revision", "per_hunt_limit", "expires_at", "window_start", "window_end"}
                or fields["run_id"] in parents
                or not isinstance(fields["run_id"], str)
                or not 1 <= len(fields["run_id"]) <= 200
                or fields["revision"] != policy["revision"]
                or fields["per_hunt_limit"] != policy["per_hunt_limit"]
                or not at < _stamp(fields["expires_at"]) <= at + timedelta(minutes=30)
            ):
                raise ValueError("Hunter parent accounting is unavailable")
            parents[fields["run_id"]] = fields
        elif row["kind"] == "operation":
            if (
                policy is None
                or set(fields) != {"run_id", "stage", "lane", "scope", "dispatch_id", "revision"}
                or fields["run_id"] not in parents
                or fields["stage"] not in {"oauth", "browse", "detail"}
                or fields["scope"] not in {"singles", "lots"}
                or fields["lane"]
                not in ({"auction", "buy_it_now"} if fields["stage"] == "browse" else {None})
                or not isinstance(fields["dispatch_id"], str)
                or not 1 <= len(fields["dispatch_id"]) <= 200
                or fields["revision"] != policy["revision"]
            ):
                raise ValueError("Hunter operation accounting is unavailable")
            key = (fields["run_id"], fields["stage"], fields["dispatch_id"])
            if key in dispatched:
                raise ValueError("Hunter duplicate dispatch accounting is unavailable")
            dispatched.add(key)
            operations.append(row)
        else:
            raise ValueError("Hunter usage accounting is unavailable")
        rows.append(row)
        previous, last = row["hash"], at
    if policy is None or anchor["sequence"] != len(rows) or anchor["hash"] != rows[-1]["hash"]:
        raise ValueError("Hunter policy selection or journal tail is unavailable")
    return dict(
        marker=marker,
        rows=rows,
        policy=policy,
        parents=parents,
        operations=operations,
        package=package,
        last=last,
    )


def _append(root, state, kind, fields, now, *, create=False):
    previous = state["rows"][-1]["hash"] if state["rows"] else "0" * 64
    row = dict(
        sequence=len(state["rows"]) + 1,
        previous=previous,
        policy_id=state["marker"]["id"],
        at=now.isoformat(),
        kind=kind,
        data=fields,
    )
    row["hash"] = hashlib.sha256(json.dumps(row, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    data = (json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n").encode()
    flags = os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW | os.O_NONBLOCK
    fd = os.open(_directory(root) / JOURNAL_NAME, flags | (os.O_CREAT | os.O_EXCL if create else 0), 0o600)
    with os.fdopen(fd, "ab") as stream:
        _private(stream.fileno(), MAX_JOURNAL_BYTES - len(data))
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    # A separate durable tail anchor detects even valid-prefix truncation. If a
    # crash separates these two fsyncs, acquisition fails closed for recovery;
    # it never guesses which operation reached transport or restores old state.
    anchor = json.dumps(
        dict(id=state["marker"]["id"], sequence=row["sequence"], hash=row["hash"]),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    fd = os.open(_directory(root) / LOCK_NAME, os.O_WRONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "r+b") as stream:
        _private(stream.fileno(), 512)
        stream.seek(0)
        stream.write(anchor)
        stream.truncate()
        stream.flush()
        os.fsync(stream.fileno())
    if create:
        directory = os.open(_directory(root), os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)


def _period(state, now):
    policy = state["policy"]
    start, end = _stamp(policy["window_start"]), _stamp(policy["window_end"])
    if now >= end and policy["recurring"]:
        start, end = _window(now, policy["timezone"])
    return start, end


def _reason(state, now, *, package=True):
    policy = state["policy"]
    if now < state["last"]:
        return "The clock moved backwards. Acquisition is paused until it catches up."
    if package and state["package"] != _digest():
        return "This update needs a qualified compatibility binding before acquisition."
    if not policy["enabled"]:
        return "Hunter acquisition is paused."
    if policy["expires_at"] and now >= _stamp(policy["expires_at"]):
        return "The selected Hunter policy has expired."
    if not policy["recurring"] and now >= _stamp(policy["window_end"]):
        return "The selected daily window has ended. Select new usage settings to continue."
    return None


def _public(state, now):
    policy = state["policy"]
    start, end = _period(state, now)
    used = sum(_stamp(row["at"]) >= start and _stamp(row["at"]) < end for row in state["operations"])
    reason = _reason(state, now)
    remaining = max(0, policy["daily_limit"] - used)
    if not reason and not remaining:
        reason = "The selected daily limit is exhausted."
    return dict(
        configured=True,
        enabled=policy["enabled"],
        revision=policy["revision"],
        per_hunt_limit=policy["per_hunt_limit"],
        daily_limit=policy["daily_limit"],
        timezone=policy["timezone"],
        recurring=policy["recurring"],
        expires_at=policy["expires_at"],
        used=used,
        remaining=remaining if _reason(state, now) is None else 0,
        next_window_at=end.isoformat() if policy["recurring"] else None,
        window_start=start.isoformat(),
        window_end=end.isoformat(),
        reason=reason,
        acquisition_available=not reason,
    )


def status(actor):
    actor = _owner(actor)
    empty = dict(
        configured=False,
        enabled=False,
        revision=0,
        per_hunt_limit=None,
        daily_limit=None,
        timezone=None,
        recurring=None,
        expires_at=None,
        used=0,
        remaining=0,
        next_window_at=None,
        acquisition_available=False,
        reason="Choose your Hunter usage limits to enable acquisition.",
    )
    try:
        root = _root()
        if not present(root):
            return empty
        with _locked(root):
            state = _load(root)
            if state["marker"]["account_id"] != actor.user_id:
                raise ValueError("Hunter owner binding is unavailable")
            return _public(state, _now())
    except (OSError, ValueError, TypeError, KeyError):
        return {
            **empty,
            "configured": True,
            "reason": "Hunter usage settings or accounting are unavailable. Acquisition is disabled.",
        }


def select(actor, raw):
    actor = _owner(actor)
    root = _root()
    checked = _settings(raw, now=_now())
    with _locked(root, create=True) as lock_stream:
        now = _now()
        checked = _settings(raw, now=now)
        exists = present(root)
        if exists:
            state = _load(root)
            if state["marker"]["account_id"] != actor.user_id:
                raise ValueError("Hunter policy belongs to another owner")
            if now < state["last"] or state["package"] != _digest():
                raise ValueError("Hunter usage settings are temporarily unavailable")
            if checked["revision"] != state["policy"]["revision"]:
                raise ValueError("Hunter usage settings changed; reload before saving")
            previous_start, previous_end = _period(state, now)
        else:
            lock_stream.seek(0)
            if lock_stream.read():
                raise ValueError("Hunter usage accounting is missing; acquisition remains disabled")
            if checked["revision"] != 0:
                raise ValueError("Hunter usage accounting is missing; acquisition remains disabled")
            marker = dict(
                version=1, contract=CONTRACT, root=str(root), account_id=actor.user_id, id=uuid.uuid4().hex
            )
            state = dict(marker=marker, rows=[])
            previous_start = previous_end = None
        start, end = _window(now, checked["timezone"])
        # A timezone change never renews capacity: extend the current accounting
        # window to include both old and new days until their later midnight.
        if previous_end is not None and now < previous_end:
            start, end = min(start, previous_start), max(end, previous_end)
        fields = {
            **checked,
            "revision": checked["revision"] + 1,
            "window_start": start.isoformat(),
            "window_end": end.isoformat(),
            "package": _digest(),
        }
        _append(root, state, "selection", fields, now, create=not exists)
        if not exists:
            descriptor = os.open(
                root / CONFIG_NAME, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
            )
            with os.fdopen(descriptor, "w") as stream:
                json.dump(state["marker"], stream, separators=(",", ":"))
                stream.flush()
                os.fsync(stream.fileno())
            directory = os.open(root, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    return status(actor)


@dataclass(frozen=True)
class OrdinaryAllowance:
    root: str
    account_id: str
    policy_id: str
    parent_id: str | None = None

    @property
    def id(self):
        return CONTRACT + ":" + self.policy_id


def current(actor, *, root=None, existing=None):
    """Return only currently valid owner authority; never infer initial limits."""
    root = _root(root)
    if not present(root):
        return None
    try:
        _owner(actor)
        with _locked(root):
            state = _load(root)
            now = _now()
            if state["marker"]["account_id"] != actor.user_id or _reason(state, now):
                return None
            candidate = OrdinaryAllowance(str(root), actor.user_id, state["marker"]["id"])
            if existing is not None:
                if (
                    type(existing) is not OrdinaryAllowance
                    or replace(existing, parent_id=None) != candidate
                    or existing.parent_id not in state["parents"]
                ):
                    return None
                _parent(state, existing, now)
                return existing
            return candidate if _public(state, now)["remaining"] > 0 else None
    except (OSError, ValueError, TypeError, KeyError, PermissionDenied):
        return None


def bind(run, actor):
    allowance = run.allowance
    if type(allowance) is not OrdinaryAllowance:
        return
    _owner(actor)
    root = _root(allowance.root)
    with _locked(root):
        now = _now()
        state = _load(root)
        if (
            state["marker"]["id"] != allowance.policy_id
            or state["marker"]["account_id"] != actor.user_id
            or tuple(run.owner[:2]) != (str(root), actor.user_id)
            or _reason(state, now)
            or not _public(state, now)["remaining"]
        ):
            raise ValueError("The selected Hunter policy is unavailable")
        start, end = _period(state, now)
        _append(
            root,
            state,
            "parent",
            dict(
                run_id=run.id,
                revision=state["policy"]["revision"],
                per_hunt_limit=state["policy"]["per_hunt_limit"],
                expires_at=(now + timedelta(minutes=30)).isoformat(),
                window_start=start.isoformat(),
                window_end=end.isoformat(),
            ),
            now,
        )
    run.allowance = replace(allowance, parent_id=run.id)


def _parent(state, allowance, now):
    if (
        state["marker"]["id"] != allowance.policy_id
        or state["marker"]["account_id"] != allowance.account_id
        or state["marker"]["root"] != allowance.root
        or allowance.parent_id not in state["parents"]
    ):
        raise ValueError("Hunter parent does not match this policy")
    parent = state["parents"][allowance.parent_id]
    if now >= _stamp(parent["expires_at"]):
        raise ValueError("The captured Hunter lease expired")
    return parent


def _check(run):
    allowance = getattr(run, "allowance", None)
    if run.operation == "detail":
        from . import hunter

        parent = hunter._runs.get(getattr(run, "parent_run_id", None))
        if parent is None or parent.owner != run.owner:
            raise ValueError("Hunter details have no matching parent")
        allowance = parent.allowance
    if type(allowance) is not OrdinaryAllowance:
        raise ValueError("Hunter action has no ordinary policy binding")
    with _locked(_root(allowance.root)):
        state = _load(_root(allowance.root))
        now = _now()
        if tuple(run.owner[:2]) != (allowance.root, allowance.account_id) or _reason(state, now):
            raise ValueError("The selected Hunter policy is unavailable")
        parent = _parent(state, allowance, now)
        used = sum(row["data"]["run_id"] == allowance.parent_id for row in state["operations"])
        if (
            used > min(parent["per_hunt_limit"], state["policy"]["per_hunt_limit"])
            or _public(state, now)["used"] > state["policy"]["daily_limit"]
        ):
            raise ValueError("Hunter limits were reduced below consumed usage")


def check(run):
    try:
        _check(run)
    except (OSError, TypeError, KeyError):
        raise ValueError("Hunter policy or accounting is unavailable") from None


def _capacity(state, allowance, now):
    if _reason(state, now):
        return dict.fromkeys(LIMITS, 0)
    daily = _public(state, now)["remaining"]
    counts = dict.fromkeys(LIMITS, 0)
    ceiling = state["policy"]["per_hunt_limit"]
    if allowance.parent_id is not None:
        parent = _parent(state, allowance, now)
        ceiling = min(ceiling, parent["per_hunt_limit"])
        for row in state["operations"]:
            fields = row["data"]
            if fields["run_id"] != allowance.parent_id:
                continue
            counts["total"] += 1
            counts[fields["stage"]] += 1
            if fields["lane"] is not None:
                counts[fields["lane"]] += 1
            if fields["scope"] == "lots" and fields["stage"] != "oauth":
                counts["lots"] += 1
    total = min(daily, max(0, ceiling - counts["total"]))
    return {key: min(total, max(0, value - counts[key])) for key, value in LIMITS.items()}


def remaining(root, allowance):
    try:
        if _root(root) != _root(allowance.root):
            raise ValueError("Hunter installation differs")
        with _locked(_root(root)):
            state = _load(_root(root))
            if (
                state["marker"]["id"] != allowance.policy_id
                or state["marker"]["account_id"] != allowance.account_id
            ):
                raise ValueError("Hunter policy differs")
            return _capacity(state, allowance, _now())
    except (OSError, ValueError, TypeError, KeyError):
        return dict.fromkeys(LIMITS, 0)


def consume(root, run_id, stage, lane, *, dispatch_id, allowance, scope):
    try:
        if (
            _root(root) != _root(allowance.root)
            or run_id != allowance.parent_id
            or stage not in {"oauth", "browse", "detail"}
            or scope not in {"singles", "lots"}
            or lane not in ({"auction", "buy_it_now"} if stage == "browse" else {None})
            or not isinstance(dispatch_id, str)
            or not 1 <= len(dispatch_id) <= 200
        ):
            raise ValueError("Hunter operation is unavailable")
        root = _root(root)
        with _locked(root):
            now = _now()
            state = _load(root)
            capacity = _capacity(state, allowance, now)
            keys = (
                ["total", stage]
                + ([lane] if lane else [])
                + (["lots"] if scope == "lots" and stage != "oauth" else [])
            )
            if any(capacity[key] < 1 for key in keys) or any(
                (row["data"]["run_id"], row["data"]["stage"], row["data"]["dispatch_id"])
                == (run_id, stage, dispatch_id)
                for row in state["operations"]
            ):
                raise ValueError("Hunter capacity is consumed or the dispatch is repeated")
            _append(
                root,
                state,
                "operation",
                dict(
                    run_id=run_id,
                    stage=stage,
                    lane=lane,
                    scope=scope,
                    dispatch_id=dispatch_id,
                    revision=state["policy"]["revision"],
                ),
                now,
            )
    except (OSError, ValueError, TypeError, KeyError):
        raise ProviderFailure(stage) from None


def rebind_package(root, *, expected_previous, package_sha256, contract=CONTRACT):
    """Qualified local delivery only; retains every revision, parent and debit.

    This is deliberately absent from HTTP. Qualification must establish the same
    acquisition semantics and contract before adding the installed package hash.
    Changed provider/source/cost semantics require a new contract and selection.
    """
    root = _root(root)
    if not present(root):
        return False
    if (
        contract != CONTRACT
        or not re.fullmatch(r"[a-f0-9]{64}", package_sha256)
        or package_sha256 != _digest()
    ):
        raise ValueError("The delivered Hunter package is not qualified for this binding")
    with _locked(root):
        now = _now()
        state = _load(root)
        if state["package"] != expected_previous or now < state["last"]:
            raise ValueError("The previous Hunter package binding differs")
        _append(
            root,
            state,
            "rebind",
            dict(previous_package=expected_previous, package=package_sha256, contract=contract),
            now,
        )
    return True
