"""Private offline snapshots: preview, contract-gated activation, rollback and removal.

No network, catalog writes, historical-guide updates or provider collectors.
Prices never enter operator summaries. Source review registers an exact contract
hash separately; packages cannot authorize themselves on ordinary installations.
"""

import fcntl
import json
import os
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from django.conf import settings

from . import price_snapshot_contract as rules
from . import price_snapshot_sources as sources

_read_only = ContextVar("price_snapshot_read_only", default=False)


_selection = ContextVar("snapshot_selection", default=(None, None))


@contextmanager
def selected(ids, *, eligible_on=None):
    token = _selection.set((frozenset(ids), eligible_on))
    try:
        yield
    finally:
        _selection.reset(token)


@contextmanager
def read_only():
    """Revalidate display rights without running operator cleanup on seller return."""
    token = _read_only.set(True)
    try:
        yield
    finally:
        _read_only.reset(token)


def directory():
    if getattr(settings, "STAGING", False):
        raise ValueError("Private snapshots are supported only on the local installation")
    return settings.ROOT / "price-snapshots"


def revocations():
    # Deliberately outside the app root: restoring an app backup cannot restore
    # a revoked version. The registry holds only random release IDs, never prices.
    key = rules.digest(str(settings.ROOT.resolve()))
    return settings.ROOT.parent / ".dex-price-revocations" / (key + ".json")


def read(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > rules.MAX_RELEASE_BYTES:
        raise ValueError("Snapshot file missing, linked or over the finite byte limit")
    with path.open("rb") as stream:
        data = stream.read(rules.MAX_RELEASE_BYTES + 1)
    if len(data) > rules.MAX_RELEASE_BYTES:
        raise ValueError("Snapshot exceeds the finite byte limit")
    return json.loads(data, object_pairs_hook=rules.unique_object, parse_constant=rules.invalid_constant)


def private_mkdir(path):
    if path.is_symlink():
        raise ValueError("Private snapshot paths cannot be symbolic links")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.stat().st_mode & 0o077:
        raise ValueError("Private snapshot directory must be owner-only")


def atomic(path, value):
    private_mkdir(path.parent)
    if path.is_symlink():
        raise ValueError("Private snapshot paths cannot be symbolic links")
    temporary = path.parent / ("." + str(uuid4()) + ".tmp")
    try:
        fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w") as output:
            json.dump(value, output, sort_keys=True, separators=(",", ":"))
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        temporary.unlink(missing_ok=True)


@contextmanager
def locked():
    base = directory()
    private_mkdir(base)
    path = base / ".lock"
    if path.is_symlink():
        raise ValueError("Private snapshot lock cannot be a symbolic link")
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(fd, "w") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def state():
    path = directory() / "active.json"
    value = read(path) if path.exists() else dict(current=None, previous=None)
    if not isinstance(value, dict) or set(value) != {"current", "previous"}:
        raise ValueError("Invalid active snapshot pointer")
    from uuid import UUID

    for version in value.values():
        if version is not None and (not isinstance(version, str) or str(UUID(version)) != version):
            raise ValueError("Invalid active snapshot version")
    return value


def seals():
    path = directory() / "versions.json"
    value = read(path) if path.exists() else {}
    if not isinstance(value, dict):
        raise ValueError("Invalid snapshot version manifest")
    return value


def denied():
    path = revocations()
    values = read(path) if path.exists() else []
    from uuid import UUID

    if not isinstance(values, list) or any(not isinstance(v, str) or str(UUID(v)) != v for v in values):
        raise ValueError("Invalid independent revocation registry")
    return values


def entries(printing_ids=None):
    from .collection_catalog import catalog_entries

    # The calculator's vintage browse selector is not a source/admission rule.
    # Reviewed contracts still pin every product/subtype and exact printing;
    # published all-era Pokémon metadata merely supplies validation identities.
    if printing_ids is None:
        return {p["id"]: p for p in catalog_entries(published_only=True, game_key="pokemon")}
    from .shopping_index import known_published_pokemon

    requested = set(printing_ids)
    known = known_published_pokemon(requested)
    if known is not None:
        return known
    ids = sorted(requested)
    return {
        p["id"]: p
        for start in range(0, len(ids), 500)
        for p in catalog_entries(
            published_only=True, game_key="pokemon", printing_ids=ids[start : start + 500]
        )
    }


def selectable(ids):
    """Membership-only validation for observations whose identity is checked at use."""
    from . import store
    from .shopping_index import known_published_pokemon

    ids = set(ids)
    if not settings.B4_ENABLED:
        return False
    known = known_published_pokemon(ids)
    if known is not None:
        return ids.issubset(known)
    count = store.rows(
        "SELECT COUNT(*) AS n FROM printings p JOIN catalog_sets s ON s.id=p.set_id JOIN games g ON g.id=s.game_id WHERE p.publication_state='published' AND s.publication_state='published' AND g.game_key='pokemon' AND p.id IN (SELECT value FROM json_each(%s))",
        [json.dumps(sorted(ids))],
    )[0]["n"]
    return count == len(ids)


def reviewed(package):
    if package["schema"] == "dex-price-snapshot-v2":
        for part in rules.source_packages(package).values():
            reviewed(part)
        return
    policy = package["contract"]
    if sources.blocked(package["version"], rules.digest(policy)):
        raise ValueError("Revoked source contract; restore excluded")
    if policy["provider"] == "dex-engineering-fixture":
        if (settings.ROOT / "SYNTHETIC_ONLY").is_file():
            return
        raise ValueError("Engineering fixtures cannot enter an ordinary installation")
    path = settings.ROOT / "price-contracts.json"
    registry = read(path) if path.exists() else {}
    if not isinstance(registry, dict):
        raise ValueError("Invalid source contract registry")
    if registry.get(policy["review_id"]) != rules.digest(policy):
        raise ValueError("Provider admission disabled: exact supported contract review is missing")


def preview(path, *, now=None):
    value = read(Path(path))
    if value.get("schema") == sources.SCHEMA:
        if value["version"] in denied():
            raise ValueError("Revoked snapshot; restore excluded")
        package = sources.load(Path(path), now=now)
        if package is None:
            raise ValueError("Release has no remaining admitted source observations")
        return package
    package = rules.validate(value, entries(), now=now)
    if package["version"] in denied():
        raise ValueError("Revoked snapshot; restore excluded")
    reviewed(package)
    sealed = seals().get(package["version"])
    if sealed is not None:
        if package["schema"] == "dex-price-snapshot-v2":
            expected = {
                rules.digest(part["contract"]): rules.digest(part)
                for part in rules.source_packages(package).values()
            }
            valid = sealed.get("sources") == expected
        else:
            valid = sealed.get("sha256") == rules.digest(package)
        if not valid:
            raise ValueError("Snapshot bytes changed after version validation")
    return package


def summary(package, *, today=None):
    today = today or datetime.now(timezone.utc).date()
    catalog = entries()
    counts = {}
    for row in package["records"]:
        result = rules.reason(row, catalog[row["printing_id"]], today)
        counts[result] = counts.get(result, 0) + 1
    return dict(
        version=package["version"],
        release_month=package["release_month"],
        records=len(package["records"]),
        decisions=counts,
        immutable_save=all(
            p["contract"]["rights"]["immutable_save"] for p in rules.source_packages(package).values()
        ),
        sources={
            key: dict(
                records=len(part["records"]),
                immutable_save=part["contract"]["rights"]["immutable_save"],
                expires_at=part["expires_at"],
            )
            for key, part in rules.source_packages(package).items()
        },
    )


def activate(path, expected_current, *, now=None):
    with locked():
        package = preview(path, now=now)
        old = state()
        if old["current"] != expected_current:
            raise ValueError("Active snapshot changed; preview again")
        version = package["version"]
        if package["schema"] == "dex-price-snapshot-v2":
            if not revocations().exists():
                atomic(revocations(), [])
            sources.install(package, Path(path))
            if old["current"] != version:
                atomic(directory() / "active.json", dict(current=version, previous=old["current"]))
            return summary(package)
        dest = directory() / (version + ".json")
        if dest.exists() and read(dest) != package:
            raise ValueError("A version cannot be overwritten")
        if not revocations().exists():
            atomic(revocations(), [])
        if not dest.exists():
            # Consume the only managed staging copy; never duplicate prices.
            source = Path(path)
            if source.parent.resolve() != (directory() / "staging").resolve() or source.is_symlink():
                raise ValueError("Input must be the single private staging copy")
            if source.stat().st_mode & 0o077:
                raise ValueError("Staged prices must be owner-only")
            os.replace(source, dest)
        versions = seals()
        versions[version] = dict(sha256=rules.digest(package), expires_at=package["expires_at"])
        atomic(directory() / "versions.json", versions)
        if old["current"] != version:
            atomic(directory() / "active.json", dict(current=version, previous=old["current"]))
        return summary(package)


def rollback(expected_current, *, now=None):
    with locked():
        old = state()
        if old["current"] != expected_current:
            raise ValueError("Active snapshot changed; rollback refused")
        previous = old["previous"]
        if previous:
            preview(directory() / (previous + ".json"), now=now)
        atomic(directory() / "active.json", dict(current=previous, previous=old["current"]))
        return dict(current=previous)


def remove(version):
    # Accept canonical random IDs only, never a caller-controlled path.
    from uuid import UUID

    if str(UUID(version)) != version:
        raise ValueError("Invalid snapshot version")
    with locked():
        blocked = denied()
        if version not in blocked:
            atomic(revocations(), blocked + [version])
        sources.remove_release(version)
        (directory() / (version + ".json")).unlink(missing_ok=True)
        staging = directory() / "staging"
        for path in staging.glob("*.json"):
            if read(path).get("version") == version:
                path.unlink()
        versions = seals()
        versions.pop(version, None)
        atomic(directory() / "versions.json", versions)
        old = state()
        atomic(directory() / "active.json", {k: None if v == version else v for k, v in old.items()})


def purge_expired(*, now=None):
    now = now or datetime.now(timezone.utc)
    base = directory()
    if not base.exists():
        return
    sources.prune(now=now)
    for version, sealed in list(seals().items()):
        expiry = sealed.get("expires_at")
        if version in denied() or expiry and rules.timestamp(expiry) <= now:
            remove(version)
    for path in list(base.glob("*.json")) + list((base / "staging").glob("*.json")):
        if path.name in {"active.json", "versions.json"}:
            continue
        package = read(path)
        if package.get("schema") not in {"dex-price-snapshot-v1", "dex-price-snapshot-v2", sources.SCHEMA}:
            continue
        expiry = package.get("expires_at")
        source_revoked = package.get("schema") == "dex-price-snapshot-v1" and sources.blocked(
            package["version"], rules.digest(package["contract"])
        )
        if package["version"] in denied() or source_revoked or expiry and rules.timestamp(expiry) <= now:
            remove(package["version"])


def current(*, now=None, sources_only=False):
    if not directory().exists():
        return [], "missing_snapshot"
    if not revocations().is_file():
        raise ValueError("Restore excluded: independent revocation registry is missing")
    ids, eligible_on = _selection.get()
    if ids is None and not sources_only and not _read_only.get():
        purge_expired(now=now)
    active = state()["current"]
    if not active:
        return [], "missing_snapshot"
    if active in denied():
        raise ValueError("Revoked snapshot; restore excluded")
    manifest = seals()
    if active not in manifest:
        raise ValueError("Restore excluded: snapshot version manifest is missing")
    path = directory() / (active + ".json")
    value = read(path)
    if value.get("schema") == sources.SCHEMA:
        if value["version"] != active:
            raise ValueError("Active release identity changed")
        return sources.prepared_rows(
            value, manifest[active], ids, now=now, sources_only=sources_only, eligible_on=eligible_on
        )
    package = preview(path, now=now)
    if package is None:
        return [], "sources_unavailable"
    parts = rules.source_packages(package)
    rows = []
    for key, part in parts.items():
        policy = part["contract"]
        contract_sha256 = rules.digest(policy)
        rows.extend(
            dict(
                row,
                _snapshot_version=package["version"],
                _contract_sha256=contract_sha256,
                _save_allowed=policy["rights"]["immutable_save"],
                _policy_url=policy["policy_url"],
                _review_id=key,
                _expires_at=part["expires_at"],
            )
            for row in part["records"]
        )
    if eligible_on is not None:
        catalog = entries(ids)
        rows = [
            r
            for r in rows
            if r["printing_id"] in catalog
            and rules.reason(r, catalog[r["printing_id"]], eligible_on) == "eligible"
        ]
    return rows, "active_snapshot"


def display_current(*, now=None, sources_only=False):
    """Fail closed with explicit unavailable status for current-page projections.

    Operator validation and permanent-save admission use strict current() and
    retain its errors. Historical guides remain independently admitted.
    """
    try:
        if sources_only:
            return current(now=now, sources_only=True) if now is not None else current(sources_only=True)
        return current() if now is None else current(now=now)
    except (ValueError, OSError, KeyError):
        return [], "invalid_snapshot"


def admit(reference, rows=None):
    if rows is None:
        rows, _ = current()
    raw = reference.get("raw_record")
    match = next((r for r in rows if r == raw), None)
    if not match or not match["_save_allowed"]:
        raise ValueError(
            "This source permits current display only; permanent comparison saving is unavailable"
        )
    # Refuse a forged amount/date/printing or derivative even when raw bytes are authentic.
    for key, target in (
        ("amount", "value"),
        ("printing_id", "printing_id"),
        ("grade", "grade"),
        ("grader", "grader"),
    ):
        if reference.get(key) != match[target]:
            raise ValueError("Snapshot reference differs from its admitted observation")
    if reference.get("as_of") != rules.reference_date(match):
        raise ValueError("Snapshot reference differs from its admitted date basis")
    if "reference_as_of" in match and (
        reference.get("date_basis") != "publisher_build"
        or reference.get("valuation_as_of") is not None
        or reference.get("publisher_built_at") != match["publisher_built_at"]
    ):
        raise ValueError("Build reference cannot be saved as a provider valuation")


def expiry_worker(stop):
    """Remove managed expired copies while serving, with no provider calls."""
    while not stop.wait(1):
        try:
            purge_expired()
        except (OSError, ValueError, KeyError):
            from .diagnostics import failure

            failure("price_snapshot_expiry_failed", ValueError())
