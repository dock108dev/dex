"""Printing offsets into the sole managed source copy. No prices in the index."""

import hashlib
import json
import os
from functools import lru_cache

import orjson

from . import price_snapshot_contract as rules
from . import price_snapshots as storage


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def prepare(path, part, fingerprint):
    # atomic() writes canonical ASCII JSON. Compute offsets only after full admission.
    prefix = b"{" + b",".join(encoded(k) + b":" + encoded(part[k]) for k in sorted(part) if k < "records")
    start = len(prefix + b',"records":')
    offset = start + 1
    locations = {}
    for row in part["records"]:
        size = len(encoded(row))
        locations.setdefault(row["printing_id"], []).append([offset, size])
        offset += size + 1
    policy = part["contract"]
    index = dict(
        format=1,
        source=fingerprint,
        array=[start, offset - start],
        locations=locations,
        save=policy["rights"]["immutable_save"],
        policy_url=policy["policy_url"],
    )
    storage.atomic(path.with_suffix(".idx"), index)
    return rules.digest(index)


def stamp(stat):
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


@lru_cache(maxsize=64)
def verify(path, identity, expected):
    # Cache verification of immutable file identity only, never source observations.
    if identity[2] > rules.MAX_BYTES:
        raise ValueError("Prepared source exceeds its size limit")
    with path.open("rb") as stream:
        if (
            stamp(os.fstat(stream.fileno())) != identity
            or hashlib.file_digest(stream, "sha256").hexdigest() != expected
        ):
            raise ValueError("Prepared source bytes changed")


@lru_cache(maxsize=32)
def offsets(path, identity, expected):
    verify(path, identity, expected)
    value = storage.read(path)
    if not isinstance(value, dict) or value.get("format") != 1 or rules.digest(value) != expected:
        raise ValueError("Invalid prepared source index")
    return value


def records(path, fingerprint, index_sha, ids):
    index_path = path.with_suffix(".idx")
    if path.is_symlink() or index_path.is_symlink() or not path.is_file() or not index_path.is_file():
        raise ValueError("Prepared source is unavailable")
    index = offsets(index_path, stamp(index_path.stat()), index_sha)
    if index["source"] != fingerprint:
        raise ValueError("Prepared source version changed")
    with path.open("rb") as stream:
        identity = stamp(os.fstat(stream.fileno()))
        verify(path, identity, fingerprint)
        if ids is None:
            start, length = index["array"]
            stream.seek(start)
            # Only decode records after the immutable source seal is verified.
            # Keep canonical writes/admission on the existing strict JSON path;
            # this avoids Python's bulk decoder cost without retaining prices.
            rows = orjson.loads(stream.read(length))
        else:
            rows = []
            for pid in sorted(ids):
                for start, length in index["locations"].get(pid, ()):
                    stream.seek(start)
                    row = orjson.loads(stream.read(length))
                    if row["printing_id"] != pid:
                        raise ValueError("Prepared source printing changed")
                    rows.append(row)
        if stamp(path.stat()) != identity or stamp(os.fstat(stream.fileno())) != identity:
            raise ValueError("Prepared source changed during read")
    return rows, index
