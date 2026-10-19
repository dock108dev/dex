"""One explicitly approved Pokémon group-metadata request; never a price collector.

This standalone operator does not load Django, an installation or credentials.
Qualification injects local worker fixtures; the CLI always uses the fixed HTTPS route.
"""

import argparse
import fcntl
import hashlib
import http.client
import json
import multiprocessing
import os
import signal
import time
import zlib
from contextlib import contextmanager, suppress
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

URL = "https://tcgcsv.com/tcgplayer/3/groups"
REQUEST = {
    "method": "GET",
    "url": URL,
    "evidence_locator": "https://tcgcsv.com/docs, Pokemon categoryId=3 and documented groups route",
    "credentials": "none",
    "user_agent": "DexPrivateMetadataReview/1.0 (bounded personal local review)",
    "accept": "application/json",
    "accept_encoding": "identity",
}
CEILINGS = dict(
    attempts=1,
    files=1,
    rows=500,
    encoded_bytes=1048576,
    decoded_bytes=1048576,
    wall_seconds=30,
    redirects=0,
    retries=0,
    paging=0,
    product_files=0,
    price_files=0,
    price_endpoint_requests=0,
    price_cells=0,
    spending_usd=0,
)
PLAN = "tcgcsv-pokemon-groups-first-v1"
# Keep the compatibility location: the independent journal is durable request accounting.
OWNER_ROOT = Path.home() / "Desktop" / "dex" / ".local" / "customer"
LEDGER = OWNER_ROOT.parent / ".dex-tcgcsv-metadata" / "attempts.json"


class Rejected(ValueError):
    """Safe finite reason codes only: never provider body, exception or header text."""


def reject(code):
    raise Rejected(code)


def no_links(path):
    if any(p.is_symlink() for p in (path, *path.parents)):
        reject("linked_path")


def private_directory(path):
    no_links(path)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.stat().st_mode & 0o077:
        reject("private_directory_required")


def atomic(path, value, *, prefix="journal"):
    no_links(path)
    if path.exists() and (path.stat().st_mode & 0o077 or path.stat().st_nlink != 1):
        reject("private_file_required")
    body = json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if len(body) > CEILINGS["decoded_bytes"]:
        reject("decoded_limit" if prefix == "body" else "journal_limit")
    temporary = path.parent / (prefix + "-" + str(uuid4()) + ".tmp")
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as output:
            output.write(body)
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


def strict_json(body):
    def object_(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                reject("duplicate_json_key")
            value[key] = item
        return value

    try:
        return json.loads(
            body.decode("utf-8"), object_pairs_hook=object_, parse_constant=lambda _: reject("nonfinite_json")
        )
    except (UnicodeError, json.JSONDecodeError):
        reject("invalid_json")


def groups(body):
    """Strict allowlist from held publisher docs, Groups Collection lines 159–206.

    Schema drift consumes the attempt and fails closed; timestamps remain unzoned
    metadata strings and never become build, capture or valuation dates.
    """
    value = strict_json(body)
    if not isinstance(value, dict) or set(value) != {"totalItems", "success", "errors", "results"}:
        reject("group_envelope")
    rows = value["results"]
    if value["success"] is not True or value["errors"] != [] or not isinstance(rows, list):
        reject("group_envelope")
    if not 1 <= len(rows) <= CEILINGS["rows"]:
        reject("row_limit")
    if type(value["totalItems"]) is not int or value["totalItems"] != len(rows):
        reject("partial_or_paged_groups")
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {
            "groupId",
            "name",
            "abbreviation",
            "isSupplemental",
            "publishedOn",
            "modifiedOn",
            "categoryId",
        }:
            reject("group_fields")
        gid = row["groupId"]
        if type(gid) is not int or not 0 < gid < 2**31 or gid in seen:
            reject("group_identity")
        seen.add(gid)
        if (
            type(row["categoryId"]) is not int
            or row["categoryId"] != 3
            or type(row["isSupplemental"]) is not bool
        ):
            reject("group_identity")
        for key, maximum in (("name", 256), ("abbreviation", 64), ("publishedOn", 64), ("modifiedOn", 64)):
            text = row[key]
            if not isinstance(text, str) or len(text) > maximum or any(ord(c) < 32 for c in text):
                reject("group_text")
        if not row["name"].strip():
            reject("group_text")
        try:
            for key in ("publishedOn", "modifiedOn"):
                datetime.fromisoformat(row[key])
        except ValueError:
            reject("group_timestamp")
    return value


def manifest(path, approved):
    no_links(path)
    with path.open("rb") as stream:
        body = stream.read(65537)
    if len(body) > 65536:
        reject("manifest_limit")
    digest = hashlib.sha256(body).hexdigest()
    if approved != digest:
        reject("exact_execution_approval_required")
    value = strict_json(body)
    if not isinstance(value, dict) or any(
        value.get(k) != v
        for k, v in {
            "schema": "dex-metadata-proposal-v1",
            "source": "TCGCSV",
            "request_type": "Pokemon group metadata only",
            "dispatch_enabled": False,
            "requests": [REQUEST],
            "ceilings": CEILINGS,
        }.items()
    ):
        reject("fixed_request_manifest_required")
    return digest


def location(store, ledger):
    store, ledger = Path(store).absolute(), Path(ledger).absolute()
    for path in (store, ledger):
        no_links(path)
        if (
            path == OWNER_ROOT
            or OWNER_ROOT in path.parents
            or any((p / ".git").exists() for p in path.parents)
        ):
            reject("outside_installation_and_repository_required")
    if store == ledger or store in ledger.parents:
        reject("independent_journal_required")
    private_directory(store)
    private_directory(ledger.parent)
    return store, ledger


@contextmanager
def locked(ledger):
    path = ledger.with_suffix(".lock")
    no_links(path)
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as handle:
        if os.fstat(handle.fileno()).st_mode & 0o077 or os.fstat(handle.fileno()).st_nlink != 1:
            reject("private_file_required")
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def journal(ledger):
    if not ledger.exists():
        return {"schema": "dex-tcgcsv-metadata-attempts-v1", "attempts": []}
    no_links(ledger)
    if ledger.stat().st_mode & 0o077 or ledger.stat().st_nlink != 1:
        reject("private_file_required")
    with ledger.open("rb") as stream:
        body = stream.read(1048577)
    if len(body) > 1048576:
        reject("journal_limit")
    value = strict_json(body)
    if (
        not isinstance(value, dict)
        or set(value) != {"schema", "attempts"}
        or value["schema"] != "dex-tcgcsv-metadata-attempts-v1"
        or not isinstance(value["attempts"], list)
    ):
        reject("invalid_journal")
    for row in value["attempts"]:
        if not isinstance(row, dict) or set(row) != {"plan", "manifest_sha256", "reserved_at", "status"}:
            reject("invalid_journal")
        if row["status"] not in {"consumed", "complete", "stopped", "timeout", "failed"}:
            reject("invalid_journal")
        try:
            timestamp = datetime.fromisoformat(row["reserved_at"])
            if timestamp.tzinfo is None:
                reject("invalid_journal")
        except (TypeError, ValueError):
            reject("invalid_journal")
    return value


def reserve(ledger, digest, now):
    with locked(ledger):
        value = journal(ledger)
        if any(row["plan"] == PLAN for row in value["attempts"]):
            reject("attempt_already_consumed")
        if any(
            (now - datetime.fromisoformat(row["reserved_at"])).total_seconds() < 86400
            for row in value["attempts"]
        ):
            reject("publisher_24h_reservation")
        if len(value["attempts"]) >= 1000:
            reject("journal_limit")
        value["attempts"].append(
            dict(plan=PLAN, manifest_sha256=digest, reserved_at=now.isoformat(), status="consumed")
        )
        atomic(ledger, value)


def finish(ledger, status):
    with locked(ledger):
        value = journal(ledger)
        next(row for row in value["attempts"] if row["plan"] == PLAN)["status"] = status
        atomic(ledger, value)


def cleanup(store):
    for path in [store / "groups.pending.json", store / "groups.json", *store.glob("body-*.tmp")]:
        no_links(path)
        path.unlink(missing_ok=True)


def stop(store, ledger):
    store, _ = location(store, ledger)
    # Does not take the request/journal lock; the parent watchdog closes the worker.
    atomic(store / "STOP.json", {"stop": True})
    cleanup(store)
    return {"status": "stop_requested", "external_requests": 0}


def worker(store, pipe, wall_seconds, connection_factory=http.client.HTTPSConnection):
    """Only the child can perform transport. All failure reports are noncontent codes."""
    signal.setitimer(signal.ITIMER_REAL, wall_seconds)
    connection = response = None
    try:
        if (Path(store) / "STOP.json").exists():
            reject("stop_requested")
        connection = connection_factory("tcgcsv.com", timeout=wall_seconds)
        connection.request(
            "GET",
            "/tcgplayer/3/groups",
            headers={
                "User-Agent": REQUEST["user_agent"],
                "Accept": "application/json",
                "Accept-Encoding": "identity",
            },
        )
        response = connection.getresponse()
        if response.status != 200:
            reject("http_status")  # No redirects or retries; never inspect the error body.
        headers = response.getheaders()
        lengths = [v for k, v in headers if k.lower() == "content-length"]
        encodings = [v for k, v in headers if k.lower() == "content-encoding"]
        types = [v for k, v in headers if k.lower() == "content-type"]
        transfers = [v for k, v in headers if k.lower() == "transfer-encoding"]
        if len(lengths) > 1 or len(encodings) > 1 or len(types) != 1:
            reject("http_headers")
        if transfers and (len(transfers) != 1 or transfers[0].lower() != "chunked" or lengths):
            reject("http_headers")
        if types[0].lower().replace(" ", "") not in {"application/json", "application/json;charset=utf-8"}:
            reject("http_content_type")
        if lengths and (
            not lengths[0].isascii()
            or not lengths[0].isdigit()
            or int(lengths[0]) > CEILINGS["encoded_bytes"]
        ):
            reject("encoded_limit")
        encoding = encodings[0].lower().strip() if encodings else "identity"
        if encoding not in {"identity", "gzip"}:
            reject("http_encoding")
        inflater = zlib.decompressobj(16 + zlib.MAX_WBITS) if encoding == "gzip" else None
        body, encoded = bytearray(), 0
        while True:
            if (Path(store) / "STOP.json").exists():
                reject("stop_requested")
            remaining = CEILINGS["encoded_bytes"] - encoded
            if remaining == 0:
                if response.length == 0:
                    break
                reject("encoded_limit")  # Unframed exact-limit responses fail closed, no excess read.
            chunk = response.read1(min(4096, remaining))
            if not chunk:
                break
            encoded += len(chunk)
            decoded = (
                inflater.decompress(chunk, CEILINGS["decoded_bytes"] - len(body) + 1) if inflater else chunk
            )
            if len(body) + len(decoded) > CEILINGS["decoded_bytes"]:
                reject("decoded_limit")
            body.extend(decoded)
            if inflater and inflater.unused_data:
                reject("gzip_trailing_data")
        if lengths and encoded != int(lengths[0]):
            reject("partial_body")
        if inflater and not inflater.eof:
            reject("partial_gzip")
        value = groups(bytes(body))
        if (Path(store) / "STOP.json").exists():
            reject("stop_requested")
        atomic(Path(store) / "groups.pending.json", value, prefix="body")
        if (Path(store) / "STOP.json").exists():
            cleanup(Path(store))
            reject("stop_requested")
        pipe.send(
            {
                "status": "complete",
                "rows": len(value["results"]),
                "encoded_bytes": encoded,
                "decoded_bytes": len(body),
            }
        )
    except Rejected as exc:
        pipe.send({"status": "failed", "reason": str(exc)})
    except Exception:
        pipe.send({"status": "failed", "reason": "transport_or_parse_failure"})
    finally:
        if response is not None:
            with suppress(Exception):
                response.close()
        if connection is not None:
            with suppress(Exception):
                connection.close()
        pipe.close()


def collect(store, ledger, manifest_path, approved_sha256, *, _worker=worker, _wall_seconds=30):
    started = time.monotonic()
    if not 0 < _wall_seconds <= CEILINGS["wall_seconds"]:
        reject("wall_limit")
    digest = manifest(Path(manifest_path), approved_sha256)
    store, ledger = location(store, ledger)
    if any(store.iterdir()):
        reject("empty_request_store_required")
    reserve(ledger, digest, datetime.now(timezone.utc))
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    process = context.Process(target=_worker, args=(store, child, _wall_seconds), daemon=True)
    result = {"status": "failed", "reason": "worker_failed"}
    try:
        if (store / "STOP.json").exists():
            result = {"status": "stopped"}
        elif time.monotonic() - started >= _wall_seconds:
            result = {"status": "timeout"}
        else:
            process.start()
            child.close()
            while True:
                if (store / "STOP.json").exists():
                    result = {"status": "stopped"}
                    break
                if time.monotonic() - started >= _wall_seconds:
                    result = {"status": "timeout"}
                    break
                if parent.poll(0.02):
                    try:
                        result = parent.recv()  # Worker sends only a small noncontent result.
                    except EOFError:
                        pass
                    break
                if not process.is_alive():
                    break
    except Exception:
        result = {"status": "failed", "reason": "local_worker_failure"}
    finally:
        if process.pid is not None:
            if process.is_alive():
                process.kill()
            process.join(timeout=1)
        parent.close()
        child.close()
    if (store / "STOP.json").exists():
        result = {"status": "stopped"}
    if result["status"] == "complete":
        try:
            os.replace(store / "groups.pending.json", store / "groups.json")
        except OSError:
            result = {"status": "failed", "reason": "local_publication_failure"}
        if (store / "STOP.json").exists():
            result = {"status": "stopped"}
    if result["status"] != "complete":
        cleanup(store)
    finish(ledger, result["status"])
    return dict(result, attempted_requests=1, price_requests=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, required=True)
    commands = parser.add_subparsers(dest="action", required=True)
    acquire = commands.add_parser("collect")
    acquire.add_argument("--manifest", type=Path, required=True)
    acquire.add_argument("--approved-manifest-sha256", required=True)
    commands.add_parser("stop")
    args = parser.parse_args()
    try:
        result = (
            stop(args.store, LEDGER)
            if args.action == "stop"
            else collect(args.store, LEDGER, args.manifest, args.approved_manifest_sha256)
        )
    except Rejected as exc:
        result = {"status": "refused", "reason": str(exc)}
    except Exception:
        result = {"status": "failed", "reason": "local_operator_failure"}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] in {"complete", "stop_requested"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
