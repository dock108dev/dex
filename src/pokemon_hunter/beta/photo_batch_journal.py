"""Durable photo admission, attempt and deletion history outside recoverable databases.

This module owns only journal I/O and projection. Callers retain authorization,
transaction ordering and stage-selection locks; reads never create files.
"""

import fcntl
import hashlib
import json
import os
import time
from pathlib import Path

from django.conf import settings

from pokemon_hunter.migration import encode


def journal_path(create=False):
    root = Path(settings.ROOT).resolve()
    directory = root.parent / ".dex-photo-batches" / hashlib.sha256(str(root).encode()).hexdigest()
    if create:
        directory.parent.mkdir(mode=0o700, exist_ok=True)
        directory.mkdir(mode=0o700, exist_ok=True)
    return directory / "journal.jsonl"


def journal():
    # Read-only access is used by authorization, so it never creates/reset records.
    path = journal_path()
    if not path.exists():
        return []
    with path.open() as stream:
        fcntl.flock(stream, fcntl.LOCK_SH)
        try:
            records = [json.loads(line) for line in stream if line.strip()]
        except ValueError:
            raise ValueError(
                "Photo recovery journal is incomplete. Continue with manual bulk entry."
            ) from None
    return records


def append(event, **fields):
    record = dict(event=event, at=time.time(), **fields)
    fd = os.open(journal_path(create=True), os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        stream.write(encode(record) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return record


def tombstones(records=None):
    return {r["object_id"] for r in (journal() if records is None else records) if r["event"] == "delete"}


def reservations(key, records=None):
    records = journal() if records is None else records
    attempts = {r["id"]: r for r in records if r["event"] == "reserve" and r["batch_id"] == key}
    settled = {r["id"]: r["elapsed"] for r in records if r["event"] == "settle"}
    for aid, r in attempts.items():
        r["charged"] = min(r["allowance"], settled.get(aid, r["allowance"]))
    return attempts
