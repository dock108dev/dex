"""Capture the owner's fixed five-request Silver Tempest snapshot, without import.

Bodies stay in private managed staging. An independent one-use journal permanently
consumes each attempt before transport; failed or interrupted pilots cannot retry.
Only the exact customer installation is accepted by the command-line interface.
"""

import argparse
import fcntl
import hashlib
import http.client
import json
import os
import re
import signal
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit

ACTUAL_ROOT = Path("/Users/michaelfuscoletti/dex-private/b2-parity-20260928/review-local")
PILOT = "hunt11-five-request-v1"
AUTHORIZATION = "if you can download the data from the site we should do that; we dont need dynamic pricing just snapshots"
MIB = 1024 * 1024
BODY_LIMIT = 8 * MIB
TOTAL_LIMIT = 24 * MIB
STAGING_LIMIT = 64 * MIB
ROW_LIMIT = 10000
REQUEST_SECONDS = 15
TOTAL_SECONDS = 90
SPACING_SECONDS = 0.25
STEPS = (
    ("build-before.txt", "https://tcgcsv.com/last-updated.txt", 1024, "text"),
    ("groups.json", "https://tcgcsv.com/tcgplayer/3/groups", BODY_LIMIT, "groups"),
    ("products.json", "https://tcgcsv.com/tcgplayer/3/3170/products", BODY_LIMIT, "products"),
    ("prices.json", "https://tcgcsv.com/tcgplayer/3/3170/prices", BODY_LIMIT, "prices"),
    ("build-after.txt", "https://tcgcsv.com/last-updated.txt", 1024, "text"),
)


class CaptureRefused(ValueError):
    """A sanitized reason code, never response contents or transport details."""


def _private_directory(path):
    """Create nested directories without accepting links or shared permissions."""
    if path.exists():
        if (
            path.is_symlink()
            or not path.is_dir()
            or path.resolve(strict=True) != path
            or path.stat().st_mode & 0o077
        ):
            raise CaptureRefused("unsafe_private_directory")
        return
    if not path.parent.exists():
        _private_directory(path.parent)
    if path.parent.is_symlink():
        raise CaptureRefused("linked_directory")
    path.mkdir(mode=0o700)
    _sync_directory(path.parent)


def _sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_new(path, data):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        _sync_directory(path.parent)
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _json_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _append(stream, value):
    stream.write(_json_bytes(value))
    stream.flush()
    os.fsync(stream.fileno())


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CaptureRefused("duplicate_json_key")
        result[key] = value
    return result


def _nonfinite(_):
    raise CaptureRefused("nonfinite_json_number")


def _validate(body, kind, *, group_id=3170, groups=None):
    if kind == "text":
        try:
            text = body.decode("utf-8").strip()
            built = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except (UnicodeError, ValueError):
            raise CaptureRefused("invalid_build_timestamp") from None
        aware = built.tzinfo is not None and built.utcoffset() is not None
        return {
            "publisher_build_text": text,
            "publisher_built_at": built.astimezone(timezone.utc).isoformat() if aware else None,
            "publisher_timezone_known": aware,
        }
    try:
        value = json.loads(
            body, object_pairs_hook=_unique_object, parse_constant=_nonfinite, parse_float=Decimal
        )
    except (UnicodeError, ValueError, RecursionError):
        raise CaptureRefused("invalid_json") from None
    expected = {"success", "errors", "results"}
    if kind != "prices":
        expected.add("totalItems")
    if (
        not isinstance(value, dict)
        or set(value) != expected
        or value["success"] is not True
        or value["errors"] != []
        or not isinstance(value["results"], list)
        or len(value["results"]) > ROW_LIMIT
        or any(not isinstance(row, dict) for row in value["results"])
    ):
        raise CaptureRefused("invalid_envelope")
    rows = value["results"]
    if kind != "prices" and (type(value["totalItems"]) is not int or value["totalItems"] != len(rows)):
        raise CaptureRefused("inconsistent_row_count")
    if kind == "groups":
        bindings = groups or [{"group_id": 3170, "name": "SWSH12: Silver Tempest"}]
        for binding in bindings:
            matches = [row for row in rows if row.get("groupId") == binding["group_id"]]
            if (
                len(matches) != 1
                or type(matches[0].get("groupId")) is not int
                or type(matches[0].get("categoryId")) is not int
                or matches[0]["categoryId"] != 3
                or matches[0].get("name") != binding["name"]
            ):
                raise CaptureRefused("group_binding_conflict")
        matches = [row for row in rows if row.get("groupId") == bindings[0]["group_id"]]
        if (
            len(matches) != 1
            or type(matches[0].get("groupId")) is not int
            or type(matches[0].get("categoryId")) is not int
            or matches[0]["categoryId"] != 3
            or matches[0].get("name") != bindings[0]["name"]
        ):
            raise CaptureRefused("group_binding_conflict")
    seen = set()
    if kind in {"products", "prices"}:
        for row in rows:
            product_id = row.get("productId")
            if type(product_id) is not int or not 0 < product_id <= 2147483647:
                raise CaptureRefused("invalid_product_identity")
            if kind == "products":
                if (
                    type(row.get("categoryId")) is not int
                    or row["categoryId"] != 3
                    or type(row.get("groupId")) is not int
                    or row["groupId"] != group_id
                    or not isinstance(row.get("name"), str)
                    or not row["name"].strip()
                    or not isinstance(row.get("extendedData"), list)
                    or len(row["extendedData"]) > 100
                ):
                    raise CaptureRefused("product_binding_conflict")
                identity = product_id
            else:
                subtype = row.get("subTypeName")
                if not isinstance(subtype, str) or not subtype.strip() or len(subtype) > 2000:
                    raise CaptureRefused("invalid_literal_subtype")
                identity = (product_id, subtype)
            if identity in seen:
                raise CaptureRefused("duplicate_record_identity")
            seen.add(identity)
    return {"rows": len(rows)}


def _staging_size(staging, limit=None):
    limit = STAGING_LIMIT if limit is None else limit
    size, count = 0, 0
    for path in staging.rglob("*"):
        count += 1
        if count > 10000 or path.is_symlink():
            raise CaptureRefused("unsafe_or_excessive_staging")
        if path.is_file():
            size += path.stat().st_size
            if size > limit:
                raise CaptureRefused("staging_capacity_exhausted")
        elif not path.is_dir():
            raise CaptureRefused("nonregular_staging_member")
    return size


class _Response:
    def __init__(self, connection, response):
        self.connection = connection
        self.response = response
        self.status = response.status
        headers = response.getheaders()
        critical = {"content-length", "content-type", "content-encoding", "transfer-encoding"}
        names = [key.lower() for key, _ in headers]
        if any(names.count(key) > 1 for key in critical):
            raise CaptureRefused("duplicate_response_framing")
        self.headers = {key.lower(): value for key, value in headers}
        if "content-length" in self.headers and "transfer-encoding" in self.headers:
            raise CaptureRefused("conflicting_response_framing")
        if self.headers.get("transfer-encoding", "chunked").lower() != "chunked":
            raise CaptureRefused("unsupported_response_framing")

    def read(self, size, timeout):
        if self.response.isclosed():
            return b""
        sock = self.connection.sock or getattr(getattr(self.response.fp, "raw", None), "_sock", None)
        if sock is None:
            raise CaptureRefused("transport_deadline_unavailable")
        sock.settimeout(timeout)
        return self.response.read1(size)


@contextmanager
def _request_deadline(seconds):
    """Main-thread watchdog bounds DNS, TLS, headers and body as one request."""
    previous_handler = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)
    if any(previous_timer):
        raise CaptureRefused("request_watchdog_unavailable")

    def expired(_number, _frame):
        raise CaptureRefused("request_deadline_exhausted")

    signal.signal(signal.SIGALRM, expired)
    try:
        signal.setitimer(signal.ITIMER_REAL, seconds)
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


@contextmanager
def transport(url, *, timeout, selected_urls=None):
    """One direct HTTPS GET: no proxy, redirects, retries, auth or fallback."""
    parts = urlsplit(url)
    if url not in (selected_urls or {step[1] for step in STEPS}) or parts.hostname != "tcgcsv.com":
        raise CaptureRefused("unselected_url")
    connection = http.client.HTTPSConnection("tcgcsv.com", timeout=timeout)
    started = time.monotonic()
    try:
        connection.connect()
        connection.sock.settimeout(max(0.001, timeout - (time.monotonic() - started)))
        connection.request(
            "GET",
            parts.path,
            headers={"User-Agent": "Dex/HUNT-11", "Accept-Encoding": "identity", "Connection": "close"},
        )
        connection.sock.settimeout(max(0.001, timeout - (time.monotonic() - started)))
        yield _Response(connection, connection.getresponse())
    finally:
        connection.close()


def _capture_pilot(root, *, open_response=transport, clock=time.monotonic, sleep=time.sleep, now=None):
    """Run this fixed capture once. Tests may inject transport and an isolated root."""
    root = Path(root).absolute()
    if not root.is_dir() or root.is_symlink() or root.resolve(strict=True) != root:
        raise CaptureRefused("existing_unlinked_installation_required")
    key = hashlib.sha256(str(root).encode()).hexdigest()
    accounting = root.parent / ".dex-tcgcsv-snapshots" / key
    _private_directory(accounting)
    journal = accounting / "hunt11-five-request-v1.jsonl"
    # O_EXCL makes the whole pilot one-use, including interrupted and zero-send runs.
    descriptor = os.open(journal, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    started, previous_start, total = clock(), None, 0
    created = []
    report = dict(
        schema="dex-tcgcsv-capture-v1",
        pilot=PILOT,
        category_id=3,
        group_id=3170,
        activated=False,
        imported=False,
        provider_operations=0,
        files=[],
        http_statuses=[],
        status="stopped",
    )
    timestamp = now or (lambda: datetime.now(timezone.utc).isoformat())
    with os.fdopen(descriptor, "wb") as stream:
        _append(
            stream,
            dict(
                stage="selected", at=timestamp(), pilot=PILOT, authorization=AUTHORIZATION, maximum_attempts=5
            ),
        )
        _sync_directory(accounting)
        try:
            staging = root / "price-snapshots" / "staging"
            _private_directory(staging)
            destination = staging / "hunt11" / "capture-v1"
            _private_directory(destination)
            baseline_size = _staging_size(staging)
            if any(destination.iterdir()):
                raise CaptureRefused("capture_destination_not_empty")
            first_build = None
            for index, (filename, url, ceiling, kind) in enumerate(STEPS, 1):
                if previous_start is not None:
                    sleep(max(0, SPACING_SECONDS - (clock() - previous_start)))
                remaining = TOTAL_SECONDS - (clock() - started)
                if remaining <= 0:
                    raise CaptureRefused("total_deadline_exhausted")
                if total >= TOTAL_LIMIT or baseline_size + total >= STAGING_LIMIT:
                    raise CaptureRefused("body_capacity_exhausted")
                request_start = clock()
                previous_start = request_start
                deadline = min(started + TOTAL_SECONDS, request_start + REQUEST_SECONDS)
                _append(
                    stream,
                    dict(
                        stage="consumed", attempt=index, at=timestamp(), endpoint=kind, maximum_bytes=ceiling
                    ),
                )
                report["provider_operations"] += 1
                with (
                    _request_deadline(min(REQUEST_SECONDS, remaining)),
                    open_response(url, timeout=min(REQUEST_SECONDS, remaining)) as response,
                ):
                    status = response.status
                    report["http_statuses"].append(status)
                    _append(stream, dict(stage="response", attempt=index, at=timestamp(), http_status=status))
                    if status != 200:
                        raise CaptureRefused("http_non_success")
                    media = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                    if media not in ({"text/plain"} if kind == "text" else {"application/json", "text/json"}):
                        raise CaptureRefused("media_mismatch")
                    if response.headers.get("content-encoding", "identity").lower() != "identity":
                        raise CaptureRefused("unsupported_content_encoding")
                    length = response.headers.get("content-length")
                    if length is not None:
                        try:
                            length = int(length)
                        except (ValueError, TypeError):
                            raise CaptureRefused("invalid_content_length") from None
                        if length < 0 or length > ceiling:
                            raise CaptureRefused("body_too_large")
                    body = bytearray()
                    while True:
                        seconds = deadline - clock()
                        if seconds <= 0:
                            raise CaptureRefused("request_deadline_exhausted")
                        chunk = response.read(min(65536, ceiling - len(body) + 1), seconds)
                        if not chunk:
                            break
                        body.extend(chunk)
                        if (
                            len(body) > ceiling
                            or total + len(body) > TOTAL_LIMIT
                            or baseline_size + total + len(body) > STAGING_LIMIT
                        ):
                            raise CaptureRefused("body_too_large")
                    if clock() > deadline:
                        raise CaptureRefused("request_deadline_exhausted")
                    if length is not None and length != len(body):
                        raise CaptureRefused("truncated_body")
                metadata = _validate(body, kind)
                if kind == "text":
                    if first_build is None:
                        first_build = metadata["publisher_build_text"]
                    elif first_build != metadata["publisher_build_text"]:
                        raise CaptureRefused("publisher_build_changed")
                path = destination / filename
                _write_new(path, body)
                created.append(path)
                total += len(body)
                item = dict(
                    attempt=index,
                    filename=filename,
                    bytes=len(body),
                    http_status=status,
                    captured_at=timestamp(),
                    **metadata,
                )
                report["files"].append(item)
                _append(stream, dict(stage="received", at=timestamp(), **item))
            report.update(
                status="captured",
                decoded_bytes=total,
                publisher_build_text=first_build,
                publisher_built_at=metadata["publisher_built_at"],
                publisher_timezone_known=metadata["publisher_timezone_known"],
                capture_directory="price-snapshots/staging/hunt11/capture-v1",
            )
            manifest = destination / "capture-metadata.json"
            encoded = _json_bytes(report)
            if baseline_size + total + len(encoded) > STAGING_LIMIT:
                raise CaptureRefused("staging_capacity_exhausted")
            _write_new(manifest, encoded)
            created.append(manifest)
            _append(
                stream,
                dict(
                    stage="closed", at=timestamp(), status="captured", consumed=report["provider_operations"]
                ),
            )
        except BaseException as error:
            for path in reversed(created):
                path.unlink(missing_ok=True)
            reason = str(error) if isinstance(error, CaptureRefused) else "transport_or_storage_failure"
            report.update(status="stopped", reason=reason, retained_bodies=0, decoded_bytes=total)
            _append(
                stream,
                dict(
                    stage="closed",
                    at=timestamp(),
                    status="stopped",
                    reason=reason,
                    consumed=report["provider_operations"],
                ),
            )
            if isinstance(error, (KeyboardInterrupt, SystemExit)):
                raise
    return report


# Batch execution is separately selected. The consumed historical pilot above stays
# closed under its original immutable journal name, even if PILOT is changed.
BATCH_LIMITS = {
    "file_bytes": 16 * MIB,
    "aggregate_input_bytes": 64 * MIB,
    "staging_bytes": 65 * MIB,
    "rows_per_file": 10000,
    "product_rows": 100000,
    "price_rows": 200000,
    "request_seconds": 15,
    "total_seconds": 180,
    "spacing_seconds": 1,
    "publication_spacing_seconds": 86400,
    "build_bytes": 1024,
    "metadata_bytes": 65536,
}


def _aware(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError
        return parsed.astimezone(timezone.utc)
    except (TypeError, AttributeError, ValueError):
        raise CaptureRefused("aware_timestamp_required") from None


def _accounting(root):
    root = Path(root).absolute()
    if not root.is_dir() or root.is_symlink() or root.resolve(strict=True) != root:
        raise CaptureRefused("existing_unlinked_installation_required")
    path = root.parent / ".dex-tcgcsv-snapshots" / hashlib.sha256(str(root).encode()).hexdigest()
    _private_directory(path)
    return path


@contextmanager
def _exclusive(path):
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(descriptor)
        if info.st_mode & 0o077 or info.st_nlink != 1:
            raise CaptureRefused("unsafe_accounting_file")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise CaptureRefused("execution_already_active") from None
        yield
    finally:
        os.close(descriptor)


def capture(root, **kwargs):
    with _exclusive(_accounting(root) / "execution.lock"):
        return _capture_pilot(root, **kwargs)


def batch_steps(groups, include_groups=False):
    steps = [{"filename": "build-before.txt", "url": STEPS[0][1], "kind": "text", "group_id": None}]
    if include_groups:
        steps.append({"filename": "groups.json", "url": STEPS[1][1], "kind": "groups", "group_id": None})
    for group in groups:
        group_id = group["group_id"]
        for kind in ("products", "prices"):
            steps.append(
                {
                    "filename": f"groups/{group_id}/{kind}.json",
                    "url": f"https://tcgcsv.com/tcgplayer/3/{group_id}/{kind}",
                    "kind": kind,
                    "group_id": group_id,
                }
            )
    steps.append({"filename": "build-after.txt", "url": STEPS[0][1], "kind": "text", "group_id": None})
    return steps


def make_batch_plan(
    root,
    groups,
    not_before,
    retained_groups_sha256,
    *,
    plan_id="hunt11-s1-first-batch-v1",
    include_groups=False,
    limits=None,
    purpose=None,
    refresh_cadence=None,
):
    plan = dict(
        schema="dex-tcgcsv-batch-plan-v1",
        plan_id=plan_id,
        root=str(Path(root).absolute()),
        not_before=not_before,
        groups=groups,
        include_groups=include_groups,
        retained_groups_sha256=retained_groups_sha256,
        limits=limits or dict(BATCH_LIMITS),
        steps=batch_steps(groups, include_groups),
        request_count=2 * len(groups) + 2 + int(include_groups),
    )
    # Omitted purpose preserves the exact legacy refresh plan and its digest.
    if purpose is not None:
        plan["purpose"] = purpose
    if refresh_cadence is not None:
        plan["refresh_cadence"] = refresh_cadence
    validate_batch_plan(plan, root)
    return plan


def validate_batch_plan(plan, root):
    keys = {
        "schema",
        "plan_id",
        "root",
        "not_before",
        "groups",
        "include_groups",
        "retained_groups_sha256",
        "limits",
        "steps",
        "request_count",
    }
    if (
        not isinstance(plan, dict)
        or not keys <= set(plan) <= keys | {"purpose", "refresh_cadence"}
        or plan["schema"] != "dex-tcgcsv-batch-plan-v1"
        or "purpose" in plan
        and (not isinstance(plan["purpose"], str) or plan["purpose"] not in {"refresh", "initial_fill"})
    ):
        raise CaptureRefused("invalid_batch_plan")
    if "refresh_cadence" in plan and (
        plan["refresh_cadence"] != "selected_groups"
        or plan.get("purpose", "refresh") != "refresh"
        or plan["include_groups"] is not False
    ):
        raise CaptureRefused("invalid_refresh_cadence")
    if (
        not isinstance(plan["plan_id"], str)
        or not re.fullmatch(r"[a-z][a-z0-9-]{1,79}", plan["plan_id"])
        or plan["root"] != str(Path(root).absolute())
        or type(plan["include_groups"]) is not bool
        or not isinstance(plan["retained_groups_sha256"], str)
        or not re.fullmatch(r"[0-9a-f]{64}", plan["retained_groups_sha256"])
    ):
        raise CaptureRefused("invalid_batch_identity")
    _aware(plan["not_before"])
    groups = plan["groups"]
    if not isinstance(groups, list) or not 1 <= len(groups) <= 68:
        raise CaptureRefused("invalid_batch_groups")
    seen = set()
    for group in groups:
        if (
            not isinstance(group, dict)
            or set(group) != {"group_id", "name"}
            or type(group["group_id"]) is not int
            or not 0 < group["group_id"] <= 2147483647
            or group["group_id"] in seen
            or not isinstance(group["name"], str)
            or not group["name"].strip()
            or len(group["name"]) > 2000
        ):
            raise CaptureRefused("invalid_batch_groups")
        seen.add(group["group_id"])
    limits = plan["limits"]
    if not isinstance(limits, dict) or set(limits) != set(BATCH_LIMITS):
        raise CaptureRefused("invalid_batch_limits")
    for key, maximum in BATCH_LIMITS.items():
        value = limits[key]
        if type(value) not in (int, float) or not 0 < value < float("inf"):
            raise CaptureRefused("invalid_batch_limits")
        if (
            key in {"spacing_seconds", "publication_spacing_seconds"}
            and value < maximum
            or key not in {"spacing_seconds", "publication_spacing_seconds"}
            and value > maximum
        ):
            raise CaptureRefused("batch_limit_expansion")
        if not key.endswith("seconds") and type(value) is not int:
            raise CaptureRefused("invalid_batch_limits")
    steps = batch_steps(groups, plan["include_groups"])
    if (
        plan["steps"] != steps
        or type(plan["request_count"]) is not int
        or plan["request_count"] != len(steps)
    ):
        raise CaptureRefused("batch_step_mismatch")
    return hashlib.sha256(_json_bytes(plan)).hexdigest()


def _read_private_json(path, ceiling=8 * MIB):
    if path.is_symlink() or path.resolve(strict=True) != path:
        raise CaptureRefused("unsafe_accounting_file")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if info.st_mode & 0o077 or info.st_nlink != 1 or info.st_size > ceiling:
            raise CaptureRefused("unsafe_accounting_file")
        body = stream.read(ceiling + 1)
    if len(body) > ceiling:
        raise CaptureRefused("accounting_capacity_exhausted")
    try:
        return json.loads(body, object_pairs_hook=_unique_object, parse_constant=_nonfinite)
    except (UnicodeError, ValueError, RecursionError):
        raise CaptureRefused("invalid_accounting") from None


def _history(accounting, metadata_ledger, *, group_history=None, resource_history=None):
    if not (accounting / "hunt11-five-request-v1.jsonl").is_file() or not metadata_ledger.is_file():
        raise CaptureRefused("historical_accounting_required")
    times, builds = [], []
    used_groups, unknown_groups, detailed_reservations = set(), False, set()
    group_times = {}
    files = sorted(accounting.glob("*.jsonl"))
    if len(files) > 1000:
        raise CaptureRefused("accounting_capacity_exhausted")
    for path in files:
        if (
            path.is_symlink()
            or path.stat().st_mode & 0o077
            or path.stat().st_nlink != 1
            or path.stat().st_size > 8 * MIB
        ):
            raise CaptureRefused("unsafe_accounting_file")
        try:
            lines = path.read_bytes().splitlines()
            if len(lines) > 10000:
                raise CaptureRefused("accounting_capacity_exhausted")
            consumed, closed, maximum = 0, False, None
            received_builds = []
            declared_groups, observed_groups, unknown_scope = None, set(), False
            reserved_at, consumed_times, observed_times = None, [], {}
            for index, line in enumerate(lines):
                row = json.loads(line, object_pairs_hook=_unique_object, parse_constant=_nonfinite)
                if not isinstance(row, dict) or closed:
                    raise ValueError
                stage = row.get("stage")
                if index == 0:
                    maximum = row.get("maximum_attempts")
                    if stage != "selected" or type(maximum) is not int or not 1 <= maximum <= 139:
                        raise ValueError
                    if "group_ids" in row:
                        reserved_at = _aware(row.get("at"))
                        declared_groups = row["group_ids"]
                        if (
                            not isinstance(declared_groups, list)
                            or not 1 <= len(declared_groups) <= 68
                            or any(
                                type(gid) is not int or not 0 < gid <= 2147483647 for gid in declared_groups
                            )
                            or len(set(declared_groups)) != len(declared_groups)
                        ):
                            raise ValueError
                    if "purpose" in row and (
                        not isinstance(row["purpose"], str)
                        or row["purpose"] not in {"refresh", "initial_fill"}
                    ):
                        raise ValueError
                elif stage == "consumed":
                    consumed += 1
                    if (
                        type(row.get("attempt")) is not int
                        or row["attempt"] != consumed
                        or consumed > maximum
                    ):
                        raise ValueError
                    consumed_at = _aware(row["at"])
                    times.append(consumed_at)
                    consumed_times.append(consumed_at)
                    if path.name != "hunt11-five-request-v1.jsonl":
                        endpoint, group_id = row.get("endpoint"), row.get("group_id")
                        if endpoint in {"products", "prices"}:
                            if type(group_id) is not int or not 0 < group_id <= 2147483647:
                                unknown_scope = True
                            else:
                                observed_groups.add(group_id)
                                observed_times[group_id] = max(
                                    observed_times.get(group_id, consumed_at), consumed_at
                                )
                        elif endpoint not in {"text", "groups"} or group_id is not None:
                            unknown_scope = True
                elif stage in {"response", "received"}:
                    if not consumed or type(row.get("attempt")) is not int or row["attempt"] != consumed:
                        raise ValueError
                    if stage == "received" and row.get("publisher_built_at"):
                        received_builds.append(_aware(row["publisher_built_at"]))
                elif stage == "closed":
                    if (
                        type(row.get("consumed")) is not int
                        or row["consumed"] != consumed
                        or row.get("status") not in {"captured", "stopped"}
                        or row["status"] == "captured"
                        and consumed != maximum
                    ):
                        raise ValueError
                    closed = True
                else:
                    raise ValueError
            if not lines:
                raise ValueError
            if path.name == "hunt11-five-request-v1.jsonl":
                if (
                    maximum != 5
                    or consumed != 5
                    or not closed
                    or row["status"] != "captured"
                    or len(received_builds) != 2
                    or received_builds[0] != received_builds[1]
                ):
                    raise ValueError
            if consumed or declared_groups is not None:
                if path.name == "hunt11-five-request-v1.jsonl":
                    # Its immutable five-step implementation binds both data requests to 3170.
                    used_groups.add(3170)
                    group_times[3170] = max(group_times.get(3170, min(consumed_times)), *consumed_times)
                else:
                    if declared_groups is not None:
                        used_groups.update(declared_groups)
                        if not observed_groups <= set(declared_groups):
                            raise ValueError
                        # A failed first build still reserves every selected group.
                        # Actual data attempts, including uncertain ones, can only
                        # advance that group's daily reservation.
                        for gid in declared_groups:
                            group_times[gid] = max(
                                group_times.get(gid, reserved_at),
                                reserved_at,
                                observed_times.get(gid, reserved_at),
                            )
                    else:
                        used_groups.update(observed_groups)
                        unknown_scope = unknown_scope or not observed_groups
                        for gid, at in observed_times.items():
                            group_times[gid] = max(group_times.get(gid, at), at)
                    unknown_groups = unknown_groups or unknown_scope
                if path.name.startswith("batch-"):
                    detailed_reservations.add("tcgcsv-" + path.stem)
            builds.extend(received_builds)
        except (KeyError, UnicodeError, ValueError, RecursionError):
            raise CaptureRefused("invalid_accounting") from None
    metadata = {"schema": "dex-tcgcsv-metadata-attempts-v1", "attempts": []}
    if metadata_ledger.exists():
        metadata = _read_private_json(metadata_ledger, MIB)
        if (
            not isinstance(metadata, dict)
            or set(metadata) != {"schema", "attempts"}
            or metadata["schema"] != "dex-tcgcsv-metadata-attempts-v1"
            or not isinstance(metadata["attempts"], list)
            or len(metadata["attempts"]) > 999
        ):
            raise CaptureRefused("invalid_accounting")
        for row in metadata["attempts"]:
            if (
                not isinstance(row, dict)
                or set(row) != {"plan", "manifest_sha256", "reserved_at", "status"}
                or row["status"] not in {"consumed", "complete", "stopped", "timeout", "failed"}
            ):
                raise CaptureRefused("invalid_accounting")
            times.append(_aware(row["reserved_at"]))
            if row["plan"] != "tcgcsv-pokemon-groups-first-v1" and row["plan"] not in detailed_reservations:
                # The documented historical metadata operator sends only the groups route.
                # Other incomplete reservations need their detailed durable group selection.
                unknown_groups = True
    if group_history is not None:
        group_history.update(groups=used_groups, unknown=unknown_groups)
    if resource_history is not None:
        resource_history.update(latest_by_group=group_times, unknown=unknown_groups)
    return max(times, default=None), max(builds, default=None), metadata


def _replace_metadata(path, value):
    temporary = path.with_suffix(".pending")
    created = False
    try:
        _write_new(temporary, _json_bytes(value))
        created = True
        os.replace(temporary, path)
        _sync_directory(path.parent)
    finally:
        if created:
            temporary.unlink(missing_ok=True)


def request_stop(root):
    accounting = _accounting(root)
    path = accounting / "STOP"
    try:
        _write_new(path, b"Stop requested; consumed attempts remain consumed.\n")
    except FileExistsError:
        pass
    return {"status": "stop_requested", "provider_operations": 0}


def clear_stop(root):
    accounting = _accounting(root)
    with _exclusive(accounting / "execution.lock"):
        (accounting / "STOP").unlink(missing_ok=True)
        _sync_directory(accounting)
    return {"status": "stop_cleared", "provider_operations": 0}


@contextmanager
def _batch_watchdog(check):
    previous = signal.getsignal(signal.SIGALRM)
    if any(signal.getitimer(signal.ITIMER_REAL)):
        raise CaptureRefused("request_watchdog_unavailable")

    def tick(_number, _frame):
        check()

    signal.signal(signal.SIGALRM, tick)
    try:
        signal.setitimer(signal.ITIMER_REAL, 0.05, 0.05)
        yield
        check()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def _batch_body(response, kind, ceiling, check):
    if response.status != 200:
        raise CaptureRefused("http_non_success")
    headers = response.headers
    media = headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if media not in ({"text/plain"} if kind == "text" else {"application/json", "text/json"}):
        raise CaptureRefused("media_mismatch")
    if headers.get("content-encoding", "identity").lower() != "identity":
        raise CaptureRefused("unsupported_content_encoding")
    length, transfer = headers.get("content-length"), headers.get("transfer-encoding")
    if (length is None) == (transfer is None):
        raise CaptureRefused("ambiguous_response_framing")
    if transfer is not None and transfer.lower() != "chunked":
        raise CaptureRefused("unsupported_response_framing")
    if length is not None:
        if not isinstance(length, str) or not re.fullmatch(r"0|[1-9][0-9]{0,9}", length):
            raise CaptureRefused("invalid_content_length")
        length = int(length)
        if length > ceiling:
            raise CaptureRefused("body_too_large")
    body = bytearray()
    while True:
        remaining = check()
        chunk = response.read(min(65536, ceiling - len(body) + 1), remaining)
        check()
        if not chunk:
            break
        body.extend(chunk)
        if len(body) > ceiling:
            raise CaptureRefused("body_too_large")
    if length is not None and length != len(body):
        raise CaptureRefused("truncated_body")
    return body


def capture_batch(
    root, plan, *, expected_plan_sha256, open_response=None, clock=time.monotonic, sleep=time.sleep, now=None
):
    """One consumed finite selection; never retries or changes the supplied plan.

    Caller must independently select execution. Validation and tests need no network.
    Journals, lock and Stop live outside managed prices and survive every cleanup.
    """
    root = Path(root).absolute()
    digest = validate_batch_plan(plan, root)
    if digest != expected_plan_sha256:
        raise CaptureRefused("reviewed_plan_digest_mismatch")
    accounting = _accounting(root)
    metadata_ledger = root.parents[1] / ".dex-tcgcsv-metadata" / "attempts.json"
    _private_directory(metadata_ledger.parent)
    with _exclusive(accounting / "execution.lock"), _exclusive(metadata_ledger.with_suffix(".lock")):
        return _capture_batch_locked(
            root, plan, digest, accounting, metadata_ledger, open_response, clock, sleep, now
        )


def _capture_batch_locked(root, plan, digest, accounting, metadata_ledger, open_response, clock, sleep, now):
    limits = plan["limits"]
    timestamp = now or (lambda: datetime.now(timezone.utc).isoformat())
    selected_at = _aware(timestamp())
    group_history, resource_history = {}, {}
    latest, previous_build, metadata_history = _history(
        accounting, metadata_ledger, group_history=group_history, resource_history=resource_history
    )
    purpose = plan.get("purpose", "refresh")
    if selected_at < _aware(plan["not_before"]):
        raise CaptureRefused("capture_not_before")
    if latest and selected_at < latest:
        raise CaptureRefused("capture_clock_rollback")
    # A first fill may extend one cached publication to never-reserved groups.
    # Existing plan digests retain the historical global policy. Explicit new
    # selected-group plans reserve a daily refresh of those resources instead.
    if purpose == "initial_fill":
        if group_history["unknown"]:
            raise CaptureRefused("historical_group_scope_unknown")
        if {row["group_id"] for row in plan["groups"]} & group_history["groups"]:
            raise CaptureRefused("initial_fill_group_already_consumed")
    elif plan.get("refresh_cadence") == "selected_groups":
        if resource_history["unknown"]:
            raise CaptureRefused("historical_group_scope_unknown")
        selected_times = [
            resource_history["latest_by_group"][row["group_id"]]
            for row in plan["groups"]
            if row["group_id"] in resource_history["latest_by_group"]
        ]
        if (
            selected_times
            and (selected_at - max(selected_times)).total_seconds() < limits["publication_spacing_seconds"]
        ):
            raise CaptureRefused("selected_groups_24h_reservation")
    elif latest and (selected_at - latest).total_seconds() < limits["publication_spacing_seconds"]:
        raise CaptureRefused("publisher_24h_reservation")
    retained = root / "price-snapshots/staging/hunt11/capture-v1/groups.json"
    if retained.is_symlink() or not retained.is_file() or retained.resolve(strict=True) != retained:
        raise CaptureRefused("retained_group_metadata_required")
    if retained.stat().st_mode & 0o077 or retained.stat().st_nlink != 1 or retained.stat().st_size > 16 * MIB:
        raise CaptureRefused("unsafe_retained_group_metadata")
    group_body = retained.read_bytes()
    if hashlib.sha256(group_body).hexdigest() != plan["retained_groups_sha256"]:
        raise CaptureRefused("retained_group_metadata_changed")
    _validate(group_body, "groups", groups=plan["groups"])
    # Semantic replay identity excludes the display identifier, preventing renaming
    # a failed/stopped/closed selection to replay its same scope and window.
    scope = dict(plan)
    scope.pop("plan_id")
    scope_digest = hashlib.sha256(_json_bytes(scope)).hexdigest()
    journal = accounting / ("batch-" + scope_digest + ".jsonl")
    if journal.exists():
        raise CaptureRefused("batch_already_consumed")
    stop = accounting / "STOP"
    if stop.exists() or stop.is_symlink():
        raise CaptureRefused("stop_requested")
    staging = root / "price-snapshots/staging"
    _private_directory(staging)
    baseline_size = _staging_size(staging, limits["staging_bytes"])
    if baseline_size >= limits["staging_bytes"]:
        raise CaptureRefused("staging_capacity_exhausted")
    destination = staging / "hunt11-batches" / scope_digest
    _private_directory(destination)
    if any(destination.iterdir()):
        raise CaptureRefused("capture_destination_not_empty")
    descriptor = os.open(journal, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    started, previous_start, total, input_bytes = clock(), None, 0, 0
    created, product_ids, price_ids, group_products = [], set(), set(), {}
    row_totals = {"products": 0, "prices": 0}
    first_build = None
    report = dict(
        schema="dex-tcgcsv-batch-capture-v1",
        plan_sha256=digest,
        selection_sha256=scope_digest,
        plan_id=plan["plan_id"],
        purpose=purpose,
        category_id=3,
        group_ids=[row["group_id"] for row in plan["groups"]],
        provider_operations=0,
        activated=False,
        imported=False,
        status="stopped",
        files=[],
        http_statuses=[],
    )
    selected_urls = {step["url"] for step in plan["steps"]}
    if open_response is None:

        def open_response(url, *, timeout):
            return transport(url, timeout=timeout, selected_urls=selected_urls)

    with os.fdopen(descriptor, "wb") as stream:
        _append(
            stream,
            dict(
                stage="selected",
                at=timestamp(),
                plan_sha256=digest,
                selection_sha256=scope_digest,
                maximum_attempts=plan["request_count"],
                purpose=purpose,
                group_ids=[row["group_id"] for row in plan["groups"]],
            ),
        )
        _sync_directory(accounting)

        def check(request_deadline=None):
            if stop.exists() or stop.is_symlink():
                raise CaptureRefused("stop_requested")
            remaining = started + limits["total_seconds"] - clock()
            if remaining <= 0:
                raise CaptureRefused("total_deadline_exhausted")
            if request_deadline is not None:
                remaining = min(remaining, request_deadline - clock())
                if remaining <= 0:
                    raise CaptureRefused("request_deadline_exhausted")
            return remaining

        active_deadline, terminal = [None], [False]
        try:
            with _batch_watchdog(lambda: None if terminal[0] else check(active_deadline[0])):
                for index, step in enumerate(plan["steps"], 1):
                    check()
                    if previous_start is not None:
                        while clock() - previous_start < limits["spacing_seconds"]:
                            sleep(min(0.05, limits["spacing_seconds"] - (clock() - previous_start)))
                            check()
                    kind, group_id = step["kind"], step["group_id"]
                    ceiling = limits["build_bytes"] if kind == "text" else limits["file_bytes"]
                    if kind in {"products", "prices"}:
                        ceiling = min(ceiling, limits["aggregate_input_bytes"] - input_bytes)
                    ceiling = min(ceiling, limits["staging_bytes"] - baseline_size - total)
                    if ceiling <= 0:
                        raise CaptureRefused("body_capacity_exhausted")
                    previous_start = clock()
                    deadline = min(
                        started + limits["total_seconds"], previous_start + limits["request_seconds"]
                    )
                    # Both publisher reservation and detailed consumption are durable
                    # before any uncertain transport, including DNS/TLS/header failure.
                    reservation = dict(
                        plan="tcgcsv-batch-" + scope_digest,
                        manifest_sha256=digest,
                        reserved_at=timestamp(),
                        status="consumed",
                    )
                    if index == 1:
                        metadata_history["attempts"].append(reservation)
                    else:
                        metadata_history["attempts"][-1] = reservation
                    _replace_metadata(metadata_ledger, metadata_history)
                    _append(
                        stream,
                        dict(
                            stage="consumed",
                            attempt=index,
                            at=timestamp(),
                            endpoint=kind,
                            group_id=group_id,
                            maximum_bytes=ceiling,
                        ),
                    )
                    report["provider_operations"] += 1

                    def request_check():
                        return check(deadline)

                    active_deadline[0] = deadline
                    with open_response(step["url"], timeout=request_check()) as response:
                        report["http_statuses"].append(response.status)
                        _append(
                            stream,
                            dict(
                                stage="response", attempt=index, at=timestamp(), http_status=response.status
                            ),
                        )
                        body = _batch_body(response, kind, ceiling, request_check)
                    active_deadline[0] = None
                    check()
                    details = _validate(body, kind, group_id=group_id, groups=plan["groups"])
                    if kind == "text":
                        built = _aware(details["publisher_built_at"])
                        if built > _aware(timestamp()):
                            raise CaptureRefused("publisher_build_in_future")
                        if first_build is None:
                            first_build = details["publisher_build_text"]
                            if previous_build and (
                                built < previous_build or purpose == "refresh" and built <= previous_build
                            ):
                                raise CaptureRefused("publisher_build_spacing")
                        elif first_build != details["publisher_build_text"]:
                            raise CaptureRefused("publisher_build_changed")
                    else:
                        if details["rows"] > limits["rows_per_file"]:
                            raise CaptureRefused("row_capacity_exhausted")
                        if kind in row_totals:
                            row_totals[kind] += details["rows"]
                            if (
                                row_totals[kind]
                                > limits["product_rows" if kind == "products" else "price_rows"]
                            ):
                                raise CaptureRefused("row_capacity_exhausted")
                            rows = json.loads(body, parse_float=Decimal)["results"]
                            if kind == "products":
                                ids = {row["productId"] for row in rows}
                                if ids & product_ids:
                                    raise CaptureRefused("cross_group_product_identity")
                                product_ids.update(ids)
                                group_products[group_id] = ids
                            else:
                                ids = {(row["productId"], row["subTypeName"]) for row in rows}
                                if ids & price_ids:
                                    raise CaptureRefused("cross_group_price_identity")
                                if any(row["productId"] not in group_products[group_id] for row in rows):
                                    raise CaptureRefused("orphan_price_identity")
                                price_ids.update(ids)
                            input_bytes += len(body)
                    check()
                    path = destination / step["filename"]
                    _private_directory(path.parent)
                    _write_new(path, body)
                    created.append(path)
                    check()
                    total += len(body)
                    item = dict(
                        attempt=index,
                        filename=step["filename"],
                        bytes=len(body),
                        captured_at=timestamp(),
                        group_id=group_id,
                        **details,
                    )
                    report["files"].append(item)
                    _append(stream, dict(stage="received", at=timestamp(), **item))
                check()
                report.update(
                    status="captured",
                    decoded_bytes=total,
                    input_bytes=input_bytes,
                    product_rows=row_totals["products"],
                    price_rows=row_totals["prices"],
                    publisher_built_at=details["publisher_built_at"],
                    provider_valuation_at=None,
                    capture_directory=str(destination.relative_to(root)),
                )
                encoded = _json_bytes(report)
                if (
                    len(encoded) > limits["metadata_bytes"]
                    or baseline_size + total + len(encoded) > limits["staging_bytes"]
                ):
                    raise CaptureRefused("staging_capacity_exhausted")
                _write_new(destination / "capture-metadata.json", encoded)
                created.append(destination / "capture-metadata.json")
                check()
                metadata_history["attempts"][-1]["status"] = "complete"
                _replace_metadata(metadata_ledger, metadata_history)
                check()
                # All selected sends, validation and body/metadata writes passed.
                # Terminal commit has no provider work. A late Stop must not turn
                # one durable captured closure into a second stopped closure.
                terminal[0] = True
                _append(
                    stream,
                    dict(
                        stage="closed",
                        at=timestamp(),
                        status="captured",
                        consumed=report["provider_operations"],
                    ),
                )
        except BaseException as error:
            cleanup_paths = [destination / row["filename"] for row in plan["steps"]]
            cleanup_paths.append(destination / "capture-metadata.json")
            for path in reversed(cleanup_paths):
                path.unlink(missing_ok=True)
            for path in sorted(destination.rglob("*"), reverse=True):
                if path.is_dir() and not path.is_symlink():
                    path.rmdir()
            reason = str(error) if isinstance(error, CaptureRefused) else "transport_or_storage_failure"
            report.update(status="stopped", reason=reason, retained_bodies=0, decoded_bytes=total)
            if report["provider_operations"]:
                metadata_history["attempts"][-1]["status"] = "stopped"
                _replace_metadata(metadata_ledger, metadata_history)
            _append(
                stream,
                dict(
                    stage="closed",
                    at=timestamp(),
                    status="stopped",
                    reason=reason,
                    consumed=report["provider_operations"],
                ),
            )
            if isinstance(error, (KeyboardInterrupt, SystemExit)):
                raise
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Finite private TCGCSV capture; no automatic execution or retry"
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--plan-sha256")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--validate-plan", action="store_true")
    actions.add_argument("--stop", action="store_true")
    actions.add_argument("--clear-stop", action="store_true")
    args = parser.parse_args(argv)
    if args.root.absolute() != ACTUAL_ROOT:
        parser.error("Only the established customer installation is accepted")
    if args.stop or args.clear_stop:
        result = request_stop(args.root) if args.stop else clear_stop(args.root)
        print(json.dumps(result))
        return 0
    if not args.plan or not args.plan_sha256:
        parser.error(
            "A reviewed finite batch plan and exact digest are required; the historical pilot is closed"
        )
    try:
        if args.plan.is_symlink() or args.plan.stat().st_size > 65536:
            raise CaptureRefused("invalid_batch_plan")
        plan = json.loads(args.plan.read_bytes(), object_pairs_hook=_unique_object, parse_constant=_nonfinite)
        digest = validate_batch_plan(plan, args.root)
        if digest != args.plan_sha256:
            raise CaptureRefused("reviewed_plan_digest_mismatch")
        if args.validate_plan:
            print(
                json.dumps(
                    dict(
                        status="valid_unexecuted",
                        plan_sha256=digest,
                        request_count=plan["request_count"],
                        provider_operations=0,
                    )
                )
            )
            return 0
        if args.report is None:
            parser.error("Choose a new metadata-only report outside the customer root")
        path = args.report.absolute()
        if (
            path.exists()
            or path.is_symlink()
            or not path.parent.is_dir()
            or path.resolve().is_relative_to(args.root)
        ):
            parser.error("Choose a new metadata-only report outside the customer root")
        report = capture_batch(args.root, plan, expected_plan_sha256=digest)
        _write_new(path, json.dumps(report, indent=2, sort_keys=True).encode() + b"\n")
    except (OSError, ValueError):
        parser.exit(2, "Capture refused; preserve accounting and do not retry or enlarge the selection.\n")
    print(
        json.dumps({key: report[key] for key in ("status", "provider_operations", "activated", "imported")})
    )
    return 0 if report["status"] == "captured" else 2


if __name__ == "__main__":
    raise SystemExit(main())
