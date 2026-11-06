"""Noncontent progress/correlation beside existing independent Hunter accounting.

This is NOT an allowance or content store. Existing policy consumes every send.
Durable UUID correlations prevent replay after lost responses/restarts. A worker
process cannot resume another process's job or recover temporary seller content.
"""

import hashlib
import json
import os
import uuid
from datetime import UTC, datetime

from django.http import Http404

from . import hunter_policy as policy
from .lot_hunt_contract import CONTRACT

BOOT = uuid.uuid4().hex
NAME = "lot-hunt-progress.jsonl"
MAX_BYTES = 8 * 1024 * 1024
ACTIVE = {"queued", "discovering", "fetching_details", "assessing"}


def owner_key(owner):
    return hashlib.sha256(json.dumps(owner, separators=(",", ":")).encode()).hexdigest()


def run_id(owner, request_id):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, CONTRACT + owner_key(owner) + str(uuid.UUID(request_id))))


def _rows(root):
    path = policy._directory(root) / NAME
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return {}
    with os.fdopen(fd, "rb") as stream:
        policy._private(stream.fileno(), MAX_BYTES)
        data = stream.read(MAX_BYTES + 1)
    records = {}
    previous = "0" * 64
    for line in data.splitlines(keepends=True):
        if not line.endswith(b"\n"):
            raise ValueError("Hunt progress is uncertain; no resubmission permitted")
        row = json.loads(line)
        digest = row.pop("hash")
        if (
            row.get("previous") != previous
            or hashlib.sha256(json.dumps(row, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            != digest
            or row.get("contract") != CONTRACT
        ):
            raise ValueError("Hunt progress integrity is unavailable")
        row["hash"] = digest
        records[row["run_id"]] = row
        previous = digest
    return records


def _append(root, record, records):
    record = dict(record, previous=next(reversed(records.values()))["hash"] if records else "0" * 64)
    # Dict insertion order is not chronological when an earlier job progresses.
    path = policy._directory(root) / NAME
    if path.exists():
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            policy._private(stream.fileno(), MAX_BYTES)
            lines = stream.read().splitlines()
            if lines:
                record["previous"] = json.loads(lines[-1])["hash"]
    record["hash"] = hashlib.sha256(
        json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    data = (json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n").encode()
    fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    with os.fdopen(fd, "ab") as stream:
        policy._private(stream.fileno(), MAX_BYTES - len(data))
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    directory = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def record(run, *, initial=False, reserved=None):
    root = policy._root(run.owner[0])
    with policy._locked(root):
        rows = _rows(root)
        # The existing parent journal also prevents replay if progress is lost.
        if initial and (run.id in rows or run.id in policy._load(root)["parents"]):
            raise ValueError("This Hunt was already submitted; reload its original status")
        if not initial and (run.id not in rows or rows[run.id]["boot"] != BOOT):
            raise ValueError("Hunt progress cannot be resumed")
        counts = dict(run.counts)
        if reserved:
            counts[reserved] = counts.get(reserved, 0) + 1
            counts["total"] += 1
        _append(
            root,
            dict(
                contract=CONTRACT,
                run_id=run.id,
                owner=owner_key(run.owner),
                boot=BOOT,
                at=datetime.now(UTC).isoformat(),
                expires_at=run.expires_at,
                state=run.state,
                reason=run.error,
                counts=counts,
                progress=dict(run.progress),
                reasons=dict(run.reasons),
                content_revision=run.content_revision,
                response_bytes=run.bytes.used,
            ),
            rows,
        )


def read(owner, key):
    root = policy._root(owner[0])
    if not policy.present(root):
        raise Http404
    with policy._locked(root):
        row = _rows(root).get(str(key))
    if row is None or row["owner"] != owner_key(owner):
        raise Http404
    row = dict(row)
    if datetime.now(UTC) >= datetime.fromisoformat(row["expires_at"]):
        row.update(state="expired", reason="Original seller-content lease expired")
    elif row["boot"] != BOOT:
        row.update(
            state="restart_uncertain" if row["state"] in ACTIVE else row["state"],
            reason="Process restarted; temporary content is unavailable. No requests were replayed.",
        )
    return row
