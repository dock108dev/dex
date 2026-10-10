"""V2 releases keep independent price copies, seals and source tombstones.

The immutable release descriptor contains no prices or price fingerprints.
Removing a source deletes its shards and seals without rewriting other sources.
"""

import re
from datetime import datetime, timezone
from uuid import UUID

from django.conf import settings

from . import price_snapshot_contract as rules
from . import price_snapshots as storage

SCHEMA = "dex-price-release-v2"


def registry_path():
    return storage.revocations().with_name(storage.revocations().stem + "-sources.json")


def denied():
    path = registry_path()
    value = storage.read(path) if path.exists() else dict(contracts=[], releases=[])
    if not isinstance(value, dict) or set(value) != {"contracts", "releases"}:
        raise ValueError("Invalid independent source revocations")
    if any(not isinstance(v, list) for v in value.values()):
        raise ValueError("Invalid independent source revocations")
    for digest in value["contracts"]:
        check_digest(digest)
    for key in value["releases"]:
        version, digest = key.split(":")
        if str(UUID(version)) != version:
            raise ValueError("Invalid source release revocation")
        check_digest(digest)
    return value


def check_digest(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("Canonical source contract digest required")


def blocked(version, digest):
    value = denied()
    return digest in value["contracts"] or version + ":" + digest in value["releases"]


def shard(version, digest):
    if str(UUID(version)) != version:
        raise ValueError("Invalid source release version")
    check_digest(digest)
    return storage.directory() / version / (digest + ".json")


def descriptor(value):
    if not isinstance(value, dict) or set(value) != {"schema", "version", "release_month", "sources"}:
        raise ValueError("Invalid multi-source release descriptor")
    if value["schema"] != SCHEMA or str(UUID(value["version"])) != value["version"]:
        raise ValueError("Invalid multi-source release identity")
    if not isinstance(value["sources"], dict) or not 1 <= len(value["sources"]) <= 32:
        raise ValueError("Invalid release source inventory")
    for digest, meta in value["sources"].items():
        check_digest(digest)
        if not isinstance(meta, dict) or set(meta) != {"review_id", "expires_at", "fixture"}:
            raise ValueError("Invalid release source metadata")
        rules.text(meta["review_id"])
        if type(meta["fixture"]) is not bool:
            raise ValueError("Invalid source fixture flag")
        if meta["expires_at"] is not None:
            rules.timestamp(meta["expires_at"])
    return value


def install(package, source):
    """Called under the existing release lock after full preview/admission."""
    version = package["version"]
    path = storage.directory() / (version + ".json")
    parts = rules.source_packages(package)
    value = dict(schema=SCHEMA, version=version, release_month=package["release_month"], sources={})
    fingerprints = {}
    for part in parts.values():
        policy = part["contract"]
        digest = rules.digest(policy)
        value["sources"][digest] = dict(
            review_id=policy["review_id"],
            expires_at=part["expires_at"],
            fixture=policy["provider"] == "dex-engineering-fixture",
        )
        fingerprints[digest] = rules.digest(part)
    if path.exists():
        if storage.read(path) != value or storage.seals().get(version, {}).get("sources") != fingerprints:
            raise ValueError("A version cannot be overwritten")
    else:
        if source.parent.resolve() != (storage.directory() / "staging").resolve() or source.is_symlink():
            raise ValueError("Input must be the single private staging copy")
        if source.stat().st_mode & 0o077:
            raise ValueError("Staged prices must be owner-only")
        for part in parts.values():
            target = shard(version, rules.digest(part["contract"]))
            if target.exists() and storage.read(target) != part:
                raise ValueError("A source version cannot be overwritten")
            storage.atomic(target, part)
        storage.atomic(path, value)
        source.unlink()
    versions = storage.seals()
    versions[version] = dict(sha256=rules.digest(value), expires_at=None, sources=fingerprints)
    storage.atomic(storage.directory() / "versions.json", versions)
    if not registry_path().exists():
        storage.atomic(registry_path(), dict(contracts=[], releases=[]))


def load(path, *, now=None):
    now = now or datetime.now(timezone.utc)
    value = descriptor(storage.read(path))
    version = value["version"]
    if not registry_path().is_file():
        raise ValueError("Restore excluded: independent source registry is missing")
    seal = storage.seals().get(version)
    if not seal or seal.get("sha256") != rules.digest(value):
        raise ValueError("Snapshot bytes changed after version validation")
    contracts, rows = {}, []
    for digest, meta in value["sources"].items():
        if blocked(version, digest):
            continue
        if meta["expires_at"] and rules.timestamp(meta["expires_at"]) <= now:
            continue
        part = storage.read(shard(version, digest))
        if seal.get("sources", {}).get(digest) != rules.digest(part):
            raise ValueError("Source snapshot bytes changed after version validation")
        if rules.digest(part.get("contract")) != digest or (
            part.get("version"),
            part.get("release_month"),
            part.get("expires_at"),
        ) != (version, value["release_month"], meta["expires_at"]):
            raise ValueError("Source contract or release identity changed")
        storage.reviewed(part)
        rules.validate(part, storage.entries(), now=now)
        key = part["contract"]["review_id"]
        contracts[key] = dict(contract=part["contract"], expires_at=part["expires_at"])
        rows.extend(dict(row, contract_id=key) for row in part["records"])
    if not rows:
        return None
    return dict(
        schema="dex-price-snapshot-v2",
        version=version,
        release_month=value["release_month"],
        contracts=contracts,
        records=rows,
    )


def drop(version, digest):
    """Called under the release lock; tombstone before deleting managed copies."""
    value = denied()
    key = version + ":" + digest
    if key not in value["releases"]:
        storage.atomic(registry_path(), dict(value, releases=value["releases"] + [key]))
    shard(version, digest).unlink(missing_ok=True)
    versions = storage.seals()
    if version in versions:
        versions[version].get("sources", {}).pop(digest, None)
        storage.atomic(storage.directory() / "versions.json", versions)


def prune(*, now=None):
    now = now or datetime.now(timezone.utc)
    base = storage.directory()
    if not base.exists():
        return
    with storage.locked():
        registry = settings.ROOT / "price-contracts.json"
        admitted = storage.read(registry) if registry.exists() else {}
        if not isinstance(admitted, dict):
            raise ValueError("Invalid source contract registry")
        for path in base.glob("*.json"):
            if path.name in {"active.json", "versions.json"}:
                continue
            value = storage.read(path)
            if value.get("schema") != SCHEMA:
                continue
            value = descriptor(value)
            seal = storage.seals().get(value["version"])
            if seal and seal.get("sha256") != rules.digest(value):
                raise ValueError("Snapshot bytes changed after version validation")
            for digest, meta in value["sources"].items():
                expiry = meta["expires_at"]
                reviewed = (
                    meta["fixture"]
                    and (settings.ROOT / "SYNTHETIC_ONLY").is_file()
                    or admitted.get(meta["review_id"]) == digest
                )
                if (
                    blocked(value["version"], digest)
                    or expiry
                    and rules.timestamp(expiry) <= now
                    or not reviewed
                ):
                    drop(value["version"], digest)
        # Interrupted pre-descriptor activation can leave shards. Their v1 contents
        # still identify their source, expiry and release; cleanup never needs prices.
        for path in base.glob("*/*.json"):
            if path.parent.name == "staging":
                continue
            part = storage.read(path)
            digest = rules.digest(part["contract"])
            expiry = part["expires_at"]
            try:
                storage.reviewed(part)
                reviewed = True
            except ValueError:
                reviewed = False
            if (
                blocked(part["version"], digest)
                or part["version"] in storage.denied()
                or (expiry and rules.timestamp(expiry) <= now)
                or not reviewed
            ):
                drop(part["version"], digest)
        for path in (base / "staging").glob("*.json"):
            value = storage.read(path)
            if value.get("schema") != "dex-price-snapshot-v2":
                continue
            keep = {}
            for key, part in rules.source_packages(value).items():
                digest, expiry = rules.digest(part["contract"]), part["expires_at"]
                try:
                    storage.reviewed(part)
                    reviewed = True
                except ValueError:
                    reviewed = False
                if (
                    blocked(part["version"], digest)
                    or expiry
                    and rules.timestamp(expiry) <= now
                    or not reviewed
                ):
                    drop(part["version"], digest)
                else:
                    keep[key] = value["contracts"][key]
            if keep == value["contracts"]:
                continue
            if keep:
                storage.atomic(
                    path,
                    dict(
                        value,
                        contracts=keep,
                        records=[row for row in value["records"] if row.get("contract_id") in keep],
                    ),
                )
            else:
                path.unlink()


def remove_source(digest):
    check_digest(digest)
    with storage.locked():
        value = denied()
        if digest not in value["contracts"]:
            storage.atomic(registry_path(), dict(value, contracts=value["contracts"] + [digest]))
    storage.purge_expired()


def remove_release(version):
    """Called under the existing version-removal lock, including orphan shards."""
    for path in (storage.directory() / version).glob("*.json"):
        check_digest(path.stem)
        drop(version, path.stem)
    for path in (storage.directory() / "staging").glob("*.json"):
        if storage.read(path).get("version") == version:
            path.unlink()
