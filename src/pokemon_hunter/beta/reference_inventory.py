"""Shared read-only catalog/reference inventory; never prune, prepare or activate.

Extracted from the Hunter coverage operator. Values exist only in bounded memory;
callers must publish allowlisted metadata, never these internal records.
"""

import hashlib
import json
import sqlite3
from collections import Counter, defaultdict
from contextlib import closing, contextmanager
from contextvars import ContextVar
from time import monotonic
from uuid import UUID

from pokemon_hunter import reference_policy
from pokemon_hunter.beta import price_snapshot_contract as rules
from pokemon_hunter.beta import price_snapshot_sources

MAX_CATALOG_ROWS = 200_000
MAX_LEGACY_ROWS = 100_000
MAX_SOURCES = 32
LEGACY_SHA256 = "72d61c466c74b8a702cee9fd744a5485633c236c0dcbfaa07c26a3fafac27b03"
STATES = (
    "eligible",
    "stale",
    "expired",
    "withdrawn",
    "unadmitted",
    "inapplicable",
    "invalid",
    "unpriced",
)


class AuditFailure(Exception):
    """A deliberately content-free failure: don't expose private parser errors."""


_guard = ContextVar("reference_inventory_guard", default=None)


class ReadBudget:
    """One finite inspection; filesystem races fail closed, no content is cached."""

    def __init__(self):
        self.deadline = monotonic() + 30
        self.bytes = 0
        self.paths = {}

    def check(self):
        if monotonic() > self.deadline:
            raise AuditFailure("Inspection deadline exceeded")

    def watch(self, path):
        self.check()
        # Reject links in any existing ancestor, including missing-file paths.
        if any(p.is_symlink() for p in (path, *path.parents)):
            raise AuditFailure("Linked inspection input")
        stamp = self.stamp(path)
        if path in self.paths and self.paths[path] != stamp:
            raise AuditFailure("Inspection inputs changed")
        self.paths[path] = stamp

    @staticmethod
    def stamp(path):
        try:
            stat = path.stat()
            return stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns
        except FileNotFoundError:
            return None

    def finish(self):
        self.check()
        if any(self.stamp(p) != stamp for p, stamp in self.paths.items()):
            raise AuditFailure("Inspection inputs changed")


@contextmanager
def bounded():
    budget = ReadBudget()
    token = _guard.set(budget)
    try:
        yield budget
        budget.finish()
    finally:
        _guard.reset(token)


def watch(path):
    guard = _guard.get()
    if guard:
        guard.watch(path)


def read_json(path):
    watch(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > rules.MAX_BYTES:
        raise AuditFailure("Missing, linked or oversized audit input")
    with path.open("rb") as source:
        raw = source.read(rules.MAX_BYTES + 1)
    if len(raw) > rules.MAX_BYTES:
        raise AuditFailure("Oversized audit input")
    guard = _guard.get()
    if guard:
        guard.bytes += len(raw)
        if guard.bytes > rules.MAX_RELEASE_BYTES + 4 * rules.MAX_BYTES:
            raise AuditFailure("Combined inspection byte limit exceeded")
        guard.check()
    try:
        return json.loads(raw, object_pairs_hook=rules.unique_object, parse_constant=rules.invalid_constant)
    except (ValueError, UnicodeError, RecursionError):
        raise AuditFailure("Malformed audit input") from None


def catalog_metadata(root):
    path = root / "inventory.db"
    if path.is_symlink() or not path.is_file():
        raise AuditFailure("Existing local catalog required")
    # A read-only SQLite WAL connection can create shared-memory sidecars.
    # Refuse that layout rather than using unsafe immutable reads of a live DB.
    with path.open("rb") as source:
        header = source.read(100)
    if len(header) < 100 or header[:16] != b"SQLite format 3\0" or header[18:20] != b"\x01\x01":
        raise AuditFailure("Read-only inventory requires the ordinary rollback-journal database")
    for candidate in (path, path.with_name(path.name + "-wal"), path.with_name(path.name + "-journal")):
        watch(candidate)
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=0.1)) as database:
        guard = _guard.get()
        if guard:
            database.set_progress_handler(lambda: int(monotonic() > guard.deadline), 1000)
        database.execute("PRAGMA query_only=ON")
        rows = database.execute(
            "SELECT p.*,s.game_id,s.name AS set_name,s.catalog_version,s.coverage_status "
            "FROM printings p JOIN catalog_sets s ON s.id=p.set_id "
            "JOIN games g ON g.id=s.game_id WHERE g.game_key='pokemon' "
            "AND p.publication_state='published' AND s.publication_state='published' "
            "ORDER BY p.id LIMIT ?",
            (MAX_CATALOG_ROWS + 1,),
        )
        names = [field[0] for field in rows.description]
        entries = {}
        byte_count = 0
        for count, values in enumerate(rows, 1):
            if count > MAX_CATALOG_ROWS:
                raise AuditFailure("Catalog exceeds the finite audit limit")
            byte_count += sum(len(v.encode()) for v in values if isinstance(v, str))
            if byte_count > rules.MAX_CATALOG_BYTES:
                raise AuditFailure("Catalog exceeds the finite byte limit")
            if guard:
                guard.check()
            printing = dict(zip(names, values, strict=True))
            printing["attributes"] = json.loads(printing["attributes"])
            printing["name"] = printing["attributes"].get("name", "Unidentified card")
            if printing["id"] in entries:
                raise AuditFailure("Duplicate catalog identity")
            entries[printing["id"]] = printing
    return entries


def _uuid(value):
    if not isinstance(value, str) or str(UUID(value)) != value:
        raise AuditFailure("Invalid local release identity")
    return value


def _valid_digest(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _record_state(row, printing, today):
    reason = rules.reason(row, printing, today)
    return "eligible" if reason == "eligible" else "stale" if reason == "stale" else "inapplicable"


def _source_state(part, digest, version, admitted, denied_sources, revoked_versions, now, synthetic):
    if version in revoked_versions or digest in denied_sources["contracts"]:
        return "withdrawn"
    if version + ":" + digest in denied_sources["releases"]:
        return "withdrawn"
    expiry = part.get("expires_at")
    if expiry is not None and rules.timestamp(expiry) <= now:
        return "expired"
    policy = part.get("contract", {})
    fixture = policy.get("provider") == "dex-engineering-fixture"
    if fixture and not synthetic:
        return "fixture_rejected"
    if not (fixture and synthetic) and admitted.get(policy.get("review_id")) != digest:
        return "unadmitted"
    return None


def snapshot_metadata(root, entries, now, *, observe=None, require_prepared=False):
    """Read current shards without pruning; return only per-identity states."""
    base = root / "price-snapshots"
    states, counts, unmapped = defaultdict(set), Counter(), set()
    watch(base)
    watch(base / "active.json")
    pointer = (
        read_json(base / "active.json")
        if (base / "active.json").exists()
        else {"current": None, "previous": None}
    )
    if not isinstance(pointer, dict) or set(pointer) != {"current", "previous"}:
        raise AuditFailure("Invalid active pointer")
    version = pointer.get("current")
    if version is None:
        return states, counts, unmapped, "missing"
    _uuid(version)
    key = rules.digest(str(root.resolve()))
    revocation_base = root.parent / ".dex-price-revocations"
    denied_path = revocation_base / (key + ".json")
    source_path = revocation_base / (key + "-sources.json")
    watch(denied_path)
    watch(source_path)
    revoked_versions = read_json(denied_path) if denied_path.exists() else []
    if not denied_path.is_file():
        raise AuditFailure("Independent lifecycle registry is required")
    if not isinstance(revoked_versions, list):
        raise AuditFailure("Invalid independent release registry")
    for item in revoked_versions:
        _uuid(item)
    admitted_path = root / "price-contracts.json"
    watch(admitted_path)
    admitted = read_json(admitted_path) if admitted_path.exists() else {}
    if not isinstance(admitted, dict):
        raise AuditFailure("Invalid source admission registry")
    seals = read_json(base / "versions.json")
    package = read_json(base / (version + ".json"))
    if package.get("version") != version:
        raise AuditFailure("Current release identity mismatch")
    denied_sources = {"contracts": [], "releases": []}
    if source_path.exists():
        denied_sources = read_json(source_path)
    if not isinstance(denied_sources, dict) or set(denied_sources) != {"contracts", "releases"}:
        raise AuditFailure("Invalid independent source registry")
    if any(not isinstance(value, list) for value in denied_sources.values()):
        raise AuditFailure("Invalid independent source registry")
    if not all(_valid_digest(value) for value in denied_sources["contracts"]):
        raise AuditFailure("Invalid independent source registry")
    for value in denied_sources["releases"]:
        release, digest = value.split(":")
        _uuid(release)
        if not _valid_digest(digest):
            raise AuditFailure("Invalid independent source registry")
    seal = seals.get(version, {})
    if seal.get("sha256") != rules.digest(package):
        raise AuditFailure("Current release fingerprint mismatch")
    parts = []
    if package.get("schema") == "dex-price-release-v2":
        price_snapshot_sources.descriptor(package)
        if not source_path.is_file() or not denied_path.is_file():
            raise AuditFailure("Independent lifecycle registries are required")
        sources = package.get("sources")
        if not isinstance(sources, dict) or not 1 <= len(sources) <= MAX_SOURCES:
            raise AuditFailure("Invalid source inventory")
        for digest, metadata in sources.items():
            if not _valid_digest(digest):
                raise AuditFailure("Invalid source inventory")
            # Expired/withdrawn shards can already have been removed by the normal
            # worker. Count their source state without inventing a record count.
            unavailable = _source_state(
                {
                    "expires_at": metadata.get("expires_at"),
                    "contract": {
                        "review_id": metadata.get("review_id"),
                        "provider": "dex-engineering-fixture" if metadata["fixture"] else None,
                    },
                },
                digest,
                version,
                admitted,
                denied_sources,
                revoked_versions,
                now,
                (root / "SYNTHETIC_ONLY").is_file(),
            )
            shard = base / version / (digest + ".json")
            if unavailable:
                counts["sources_" + unavailable] += 1
                continue
            part = read_json(shard)
            if seal.get("sources", {}).get(digest) != rules.digest(part):
                raise AuditFailure("Source fingerprint mismatch")
            if rules.digest(part.get("contract")) != digest or (
                part.get("version"),
                part.get("release_month"),
                part.get("expires_at"),
            ) != (version, package.get("release_month"), metadata.get("expires_at")):
                raise AuditFailure("Source identity mismatch")
            if require_prepared:
                from . import price_snapshot_index

                index_path = shard.with_suffix(".idx")
                watch(index_path)
                try:
                    prepared = read_json(index_path)
                    if rules.digest(prepared) != seal.get("indexes", {}).get(digest):
                        raise ValueError("Index seal mismatch")
                    span = prepared.get("array")
                    if (
                        not isinstance(span, list)
                        or len(span) != 2
                        or any(type(n) is not int or n < 0 for n in span)
                        or sum(span) > shard.stat().st_size
                    ):
                        raise ValueError("Invalid bounded index span")
                    # This existing reader only verifies/reads; no root setup or cleanup.
                    indexed, meta = price_snapshot_index.records(
                        shard, seal["sources"][digest], seal["indexes"][digest], None
                    )
                    if indexed != part["records"] or (meta["save"], meta["policy_url"]) != (
                        part["contract"]["rights"]["immutable_save"],
                        part["contract"]["policy_url"],
                    ):
                        raise ValueError("Index content mismatch")
                except (AuditFailure, ValueError, OSError, KeyError, TypeError):
                    counts["sources_preparation_missing"] += 1
                    continue
            parts.append((part, digest))
    elif package.get("schema") == "dex-price-snapshot-v1":
        parts.append((package, rules.digest(package.get("contract"))))
    else:
        raise AuditFailure("Unsupported local release")
    if sum(len(part.get("records", [])) for part, _ in parts) > rules.MAX_RELEASE_ROWS:
        raise AuditFailure("Combined observation ceiling exceeded")
    if (
        sum(len(part.get("contract", {}).get("mappings", {})) for part, _ in parts)
        > rules.MAX_RELEASE_MAPPINGS
    ):
        raise AuditFailure("Combined mapping ceiling exceeded")
    if sum(rules.serialized_bytes(part) for part, _ in parts) > rules.MAX_RELEASE_BYTES:
        raise AuditFailure("Combined source byte ceiling exceeded")
    for part, digest in parts:
        source_state = _source_state(
            part,
            digest,
            version,
            admitted,
            denied_sources,
            revoked_versions,
            now,
            (root / "SYNTHETIC_ONLY").is_file(),
        )
        records = part.get("records")
        if not isinstance(records, list) or not 1 <= len(records) <= rules.MAX_ROWS:
            raise AuditFailure("Invalid source record count")
        # Pure validation has no app-root access. Sources with expired or
        # withdrawn rights cannot contribute eligible observations.
        if source_state is None:
            try:
                rules.validate(part, entries, now=now)
            except (ValueError, KeyError, TypeError):
                source_state = "invalid"
        counts["sources_" + (source_state or "admitted")] += 1
        if observe:
            observe(part, source_state)
        for row in records:
            counts["records"] += 1
            pid = row.get("printing_id")
            if pid not in entries:
                counts["records_unmapped"] += 1
                if isinstance(pid, str):
                    unmapped.add(pid)
                continue
            state = source_state or _record_state(row, entries[pid], now.date())
            states[pid].add(state)
            counts["records_" + state] += 1
    return states, counts, unmapped, "inspected_without_cleanup"


def legacy_metadata(root, entries, today, *, expected_sha256=LEGACY_SHA256, observe=None):
    path = root / "parity-evidence/market_values.json"
    states, counts, unmapped = defaultdict(set), Counter(), set()
    watch(path)
    if not path.exists():
        return states, counts, unmapped, "missing"
    rows = read_json(path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha256:
        return states, counts, unmapped, "unadmitted_bytes"
    if not isinstance(rows, list) or len(rows) > MAX_LEGACY_ROWS:
        raise AuditFailure("Invalid retained guide record count")
    if observe:
        observe(rows)
    by_legacy = defaultdict(list)
    for printing in entries.values():
        legacy_id = json.loads(printing["provenance"]).get("legacy_id")
        if legacy_id:
            by_legacy[legacy_id].append(printing)
    for row in rows:
        counts["records"] += 1
        key = row.get("card_id")
        matches = by_legacy.get(key, [])
        if not matches:
            counts["records_unmapped"] += 1
            if isinstance(key, str):
                unmapped.add(key)
            continue
        for printing in matches:
            state = reference_policy.fresh(row.get("as_of"), today.isoformat())
            if state != "stale":
                state = "eligible" if reference_policy.valid_record(row, today, guide=True) else "invalid"
            if (
                row.get("edition") != (printing.get("edition") or "standard")
                or str(row.get("grade")) not in rules.COLUMNS
                or str(row.get("grade")) != "raw"
                and (row.get("estimated") or not row.get("grader"))
                or any(row.get(k) not in (None, printing.get(k)) for k in ("language", "finish", "variant"))
                or str(row.get("grade")) == "raw"
                and row.get("grader") not in {"Guide", "PSA"}
            ):
                state = "inapplicable"
            states[printing["id"]].add(state)
            counts["printing_observations_" + state] += 1
    return states, counts, unmapped, "inspected_without_cleanup"
