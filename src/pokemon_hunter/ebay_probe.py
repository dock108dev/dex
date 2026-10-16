"""One-shot eBay operator; CLI and default APIs remain offline only.

The worker alone handles dummy credentials, bounded decoded bodies and tokens. A
separate guardian owns its process handle and durably arbitrates every dispatch.
Do not replace this boundary with EbayClient (which retries, pages and reauths).
"""

import argparse
import fcntl
import json
import logging
import math
import multiprocessing
import os
import re
import resource
import signal
import socket
import stat
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import httpx

from .ebay import EbayError

QUERY = "Pokemon Base Set Chansey 3"
BASE = "https://api.ebay.com"
# Public endpoint and response-size metadata, never credential/token values.
AUTHORIZATION_ENDPOINT_URL = BASE + "/identity/v1/oauth2/token"
BROWSE = BASE + "/buy/browse/v1/item_summary/search"
SCOPE = "https://api.ebay.com/oauth/api_scope"
DUMMY = ("offline-client", "offline-secret")
BODY_LIMIT = 2 * 1024 * 1024
AUTHORIZATION_RESPONSE_LIMIT_BYTES = 64 * 1024
CHUNK_LIMIT = 64 * 1024
POLL = 0.02
CLEANUP_SECONDS = 1.0
OUTCOMES = {
    "ok",
    "empty",
    "http_error",
    "redirect",
    "timeout",
    "stopped",
    "transport_error",
    "body_limit",
    "malformed_json",
    "invalid_schema",
    "worker_lost",
    "abandoned",
    "control_error",
    "running",
    "prepared",
}


class ProbeError(EbayError):
    """Only static allowlisted messages may cross the operator boundary."""


@dataclass(frozen=True)
class Envelope:
    marketplace: str
    country: str

    # Country-only US delivery is supported explicitly. Postal destinations
    # require a separately qualified extension, never an inferred environment value.
    def validate(self):
        if self.marketplace != "EBAY_US" or self.country != "US":
            raise ProbeError("unsupported_destination")

    def binding(self):
        self.validate()
        return {
            "mode": "offline-fixture-v1",
            "marketplace": self.marketplace,
            "country": self.country,
            "postal_code": None,
            "query": QUERY,
            "oauth_url": AUTHORIZATION_ENDPOINT_URL,
            "browse_url": BROWSE,
            "buying_option": "FIXED_PRICE",
            "limit": 5,
            "offset": 0,
            "request_seconds": 30,
            "overall_seconds": 75,
            "browse_bytes": BODY_LIMIT,
            "oauth_bytes": AUTHORIZATION_RESPONSE_LIMIT_BYTES,
            "max_attempts": 2,
            "redirects": False,
            "retries": 0,
        }


@dataclass(frozen=True)
class Request:
    stage: str
    method: str
    url: str
    headers: tuple = ()
    params: tuple = ()
    data: tuple = ()
    timeout: float = 30
    follow_redirects: bool = False


def request_for(stage, envelope, timeout):
    envelope.validate()
    if not math.isfinite(timeout) or not 0 < timeout <= 30:
        raise ProbeError("invalid_timeout")
    if stage == "oauth":
        return Request(
            stage,
            "POST",
            AUTHORIZATION_ENDPOINT_URL,
            headers=(("Content-Type", "application/x-www-form-urlencoded"),),
            data=(("grant_type", "client_credentials"), ("scope", SCOPE)),
            timeout=timeout,
        )
    if stage == "browse":
        return Request(
            stage,
            "GET",
            BROWSE,
            headers=(("X-EBAY-C-MARKETPLACE-ID", envelope.marketplace),),
            params=(
                ("q", QUERY),
                ("filter", "buyingOptions:{FIXED_PRICE},deliveryCountry:US"),
                ("limit", "5"),
                ("offset", "0"),
                ("fieldgroups", "EXTENDED"),
            ),
            timeout=timeout,
        )
    raise ProbeError("unexpected_operation")


def validate_request(request, envelope):
    if request != request_for(request.stage, envelope, request.timeout):
        raise ProbeError("unexpected_request")


def _sync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _open_private(path, flags):
    fd = os.open(path, (flags & ~os.O_TRUNC) | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    info = os.fstat(fd)
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.getuid()
        or info.st_mode & 0o077
        or info.st_nlink != 1
    ):
        os.close(fd)
        raise ProbeError("unsafe_state")
    if flags & os.O_TRUNC:
        os.ftruncate(fd, 0)
    return fd


class Journal:
    """One fixed authority slot per offline directory; no run-ID-based filenames.

    An exclusive issued tombstone precedes initial state. Missing/corrupt state is
    never recreated. Lock inode is stable; replacement state is fsynced + renamed.
    """

    envelope_type = Envelope
    network_enabled = False

    def __init__(self, directory):
        self.path = Path(directory).absolute()

    def worker_cleanup(self):
        return lambda: None

    def _check_directory(self):
        # Refuse symlinks in every existing path component, including the leaf.
        for path in (self.path, *self.path.parents):
            if path.is_symlink():
                raise ProbeError("unsafe_state")
        info = self.path.stat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ProbeError("unsafe_state")

    @contextmanager
    def locked(self):
        self._check_directory()
        fd = _open_private(self.path / "lock", os.O_RDWR)
        end = time.monotonic() + 0.25
        try:
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= end:
                        raise ProbeError("state_busy") from None
                    time.sleep(0.005)
            yield
        finally:
            os.close(fd)

    def revoked(self):
        # Any marker, including an unexpected file type, revokes authority.
        return os.path.lexists(self.path / "stop")

    def _read(self):
        for name in ("issued",):
            fd = _open_private(self.path / name, os.O_RDONLY)
            if os.fstat(fd).st_size != 0:
                os.close(fd)
                raise ProbeError("corrupt_state")
            os.close(fd)
        fd = _open_private(self.path / "authority.json", os.O_RDONLY)
        with os.fdopen(fd, "rb") as stream:
            raw = stream.read(8193)
        try:
            state = decode_json(raw) if len(raw) <= 8192 else None
            if not isinstance(state, dict) or set(state) != {
                "version",
                "run_id",
                "envelope",
                "attempts",
                "phase",
                "outcome",
                "http_status",
                "count",
            }:
                raise ValueError
            binding = state["envelope"]
            if binding != self.envelope_type(binding["marketplace"], binding["country"]).binding():
                raise ValueError
            if (
                type(state["version"]) is not int
                or state["version"] != 1
                or not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", state["run_id"])
            ):
                raise ValueError
            if state["attempts"] not in ([], ["oauth"], ["oauth", "browse"]):
                raise ValueError
            if state["phase"] not in {"prepared", "running", "complete", "failed"}:
                raise ValueError
            if state["outcome"] not in OUTCOMES:
                raise ValueError
            code, count = state["http_status"], state["count"]
            if code is not None and (type(code) is not int or not 100 <= code <= 599):
                raise ValueError
            if count is not None and (type(count) is not int or not 0 <= count <= 5):
                raise ValueError
            phase, outcome, attempts = state["phase"], state["outcome"], state["attempts"]
            if phase == "prepared" and (outcome != "prepared" or attempts):
                raise ValueError
            if phase == "running" and outcome != "running":
                raise ValueError
            if phase == "complete" and (
                outcome not in {"ok", "empty"} or len(attempts) != 2 or count is None
            ):
                raise ValueError
            if phase == "failed" and outcome in {"ok", "empty", "running", "prepared"}:
                raise ValueError
            if phase != "complete" and count is not None:
                raise ValueError
            if phase in {"prepared", "running"} and code is not None:
                raise ValueError
            if phase == "complete" and (code != 200 or (outcome == "empty") != (count == 0)):
                raise ValueError
        except (ValueError, TypeError, KeyError, ProbeError):
            raise ProbeError("corrupt_state") from None
        return state

    def _write(self, state):
        # No body/credential inputs reach this method. Orphaned staging files are
        # noncontent only; they never become authority after an interrupted write.
        temp = self.path / "pending.json"
        fd = _open_private(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC)
        with os.fdopen(fd, "w") as stream:
            json.dump(state, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, self.path / "authority.json")
        _sync_dir(self.path)

    def prepare(self, run_id, envelope):
        binding = envelope.binding()
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", run_id):
            raise ProbeError("invalid_run_id")
        # Directory creation itself is an irreversible authority tombstone. Even
        # an interrupted/empty initialization must never be prepared again.
        self.path.mkdir(mode=0o700, parents=False)
        self._check_directory()
        _sync_dir(self.path.parent)
        fd = _open_private(self.path / "lock", os.O_CREAT | os.O_EXCL | os.O_RDWR)
        os.close(fd)
        _sync_dir(self.path)
        with self.locked():
            fd = _open_private(self.path / "issued", os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.fsync(fd)
            os.close(fd)
            _sync_dir(self.path)
            self._write(
                {
                    "version": 1,
                    "run_id": run_id,
                    "envelope": binding,
                    "attempts": [],
                    "phase": "prepared",
                    "outcome": "prepared",
                    "http_status": None,
                    "count": None,
                }
            )
        return self.status()

    def status(self):
        with self.locked():
            state = self._read()
            if self.network_enabled:
                state["consumed_operations"] = len(state["attempts"])
                state["wire_attempts"] = "unverified; reservations include uncertain or unsent work"
            else:
                state["simulated_consumed"] = len(state["attempts"])
                state["real_provider_requests"] = 0
            state["revoked"] = self.revoked()
            state["authority_reusable"] = state["phase"] == "prepared" and not state["revoked"]
            state["process_liveness"] = "unverified"
            if state["revoked"]:
                state.update(outcome="stopped", count=None)
            return state

    def stop(self):
        self._check_directory()
        try:
            fd = _open_private(self.path / "stop", os.O_WRONLY | os.O_CREAT | os.O_EXCL)
            os.fsync(fd)
            os.close(fd)
            _sync_dir(self.path)
        except FileExistsError:
            pass
        # Serialize with a finishing guardian, after immediate durable revocation.
        # Corrupt/busy state never prevents the marker from revoking dispatch.
        try:
            with self.locked():
                state = self._read()
                state.update(phase="failed", outcome="stopped", count=None)
                self._write(state)
        except (OSError, ProbeError):
            pass
        # No PID is read or signalled. Revocation works even with corrupt state.
        result = {"outcome": "stopped", "revoked": True}
        if not self.network_enabled:
            result["real_provider_requests"] = 0
        return result

    def claim(self, run_id, envelope):
        with self.locked():
            state = self._read()
            if self.revoked() or state["phase"] != "prepared":
                raise ProbeError("authority_consumed")
            if state["run_id"] != run_id or state["envelope"] != envelope.binding():
                raise ProbeError("authority_mismatch")
            state.update(phase="running", outcome="running")
            self._write(state)

    def reserve(self, stage):
        with self.locked():
            state = self._read()
            if self.revoked() or state["phase"] != "running":
                raise ProbeError("authority_consumed")
            expected = (
                "oauth" if not state["attempts"] else "browse" if state["attempts"] == ["oauth"] else None
            )
            if stage != expected:
                raise ProbeError("attempt_budget")
            state["attempts"].append(stage)
            self._write(state)
            # Final gate after durable reservation. A revoked reservation is still
            # consumed; a granted operation is already admitted/possibly in flight.
            if self.revoked():
                raise ProbeError("authority_consumed")

    def finish(self, outcome, code=None, count=None):
        with self.locked():
            state = self._read()
            if self.revoked() and state["phase"] == "failed" and state["outcome"] == "stopped":
                return
            if state["phase"] != "running":
                raise ProbeError("authority_consumed")
            if self.revoked():
                outcome, count = "stopped", None
            if outcome not in OUTCOMES - {"prepared", "running"}:
                raise ProbeError("invalid_outcome")
            success = outcome in {"ok", "empty"}
            if success and (
                state["attempts"] != ["oauth", "browse"] or type(count) is not int or not 0 <= count <= 5
            ):
                raise ProbeError("invalid_outcome")
            if code is not None and (type(code) is not int or not 100 <= code <= 599):
                raise ProbeError("invalid_outcome")
            state.update(
                phase="complete" if success else "failed",
                outcome=outcome,
                http_status=code,
                count=count if success else None,
            )
            self._write(state)


class BodyError(Exception):
    pass


def decode_json(body):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError("duplicate_json_key")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError("invalid_json_constant")

    def finite_float(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError("invalid_json_number")
        return result

    if isinstance(body, (bytes, bytearray)):
        body = body.decode("utf-8")
    return json.loads(
        body, object_pairs_hook=pairs, parse_constant=invalid_constant, parse_float=finite_float
    )


def bounded_json(response, limit, parser=decode_json):
    # The real adapter additionally bounds raw reads and incremental decompression.
    body = bytearray()
    try:
        for chunk in response.iter_decoded(CHUNK_LIMIT):
            if not isinstance(chunk, bytes) or len(chunk) > CHUNK_LIMIT or len(body) + len(chunk) > limit:
                raise BodyError("body_limit")
            body.extend(chunk)
        try:
            return parser(body)
        except (ValueError, TypeError, RecursionError, OverflowError):
            raise BodyError("malformed_json") from None
    finally:
        body.clear()


def _deny_network(*args, **kwargs):
    raise OSError("offline_network_disabled")


def _quiet_worker(network=False):
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    logging.disable(logging.CRITICAL)
    with open(os.devnull, "w") as sink:
        os.dup2(sink.fileno(), 1)
        os.dup2(sink.fileno(), 2)
    # Defence in depth. Qualification additionally denies networking at the OS.
    if not network:
        socket.socket = _deny_network
        socket.create_connection = _deny_network
        socket.getaddrinfo = _deny_network


def _worker(
    connection,
    close_connections,
    directory,
    envelope,
    factory,
    parser,
    request_seconds,
    deadline,
    network=False,
):
    for other in close_connections:
        other.close()
    _quiet_worker(network)
    # A kernel timer with the default disposition also bounds the worker if its
    # guardian crashes, including a native parser stall that holds Python's GIL.
    signal.signal(signal.SIGALRM, signal.SIG_DFL)
    signal.setitimer(signal.ITIMER_REAL, max(0.000001, deadline - time.monotonic()))
    transport = response = token = payload = code = None
    try:
        transport = factory()
        for stage in ("oauth", "browse"):
            code = None
            request = request_for(stage, envelope, request_seconds)
            validate_request(request, envelope)
            connection.send(("reserve", stage))
            permit, deadline = connection.recv()
            if permit != "permit" or Journal(directory).revoked() or time.monotonic() >= deadline:
                return
            request = request_for(stage, envelope, min(request_seconds, deadline - time.monotonic()))
            validate_request(request, envelope)
            signal.setitimer(signal.ITIMER_REAL, max(0.000001, deadline - time.monotonic()))
            # RealTransport receives private credentials inside this worker only;
            # the offline transport continues to receive dummy constants.
            response = transport.dispatch(
                request, credentials=DUMMY if stage == "oauth" else None, token=token
            )
            code = response.status_code
            if type(code) is not int or not 100 <= code <= 599:
                raise BodyError("invalid_schema")
            if code != 200:
                connection.send(("result", "redirect" if 300 <= code < 400 else "http_error", code, None))
                return  # Error bodies are never read, even for OAuth.
            payload = bounded_json(
                response, AUTHORIZATION_RESPONSE_LIMIT_BYTES if stage == "oauth" else BODY_LIMIT, parser
            )
            response.close()
            response = None
            if not isinstance(payload, dict) or payload.get("errors"):
                raise BodyError("invalid_schema")
            if stage == "oauth":
                token = payload.get("access_token")
                lifetime = payload.get("expires_in")
                if (
                    not isinstance(token, str)
                    or not 1 <= len(token) <= 8192
                    or not token.strip()
                    or not re.fullmatch(r"[\x21-\x7e]{1,8192}", token)
                    or type(lifetime) is not int
                    or lifetime <= 0
                    or not isinstance(payload.get("token_type", "Bearer"), str)
                    or payload.get("token_type", "Bearer").lower()
                    not in {"bearer", "application access token"}
                ):
                    raise BodyError("invalid_schema")
            else:
                for field in ("total", "limit", "offset"):
                    if field in payload and (type(payload[field]) is not int or payload[field] < 0):
                        raise BodyError("invalid_schema")
                if ("limit" in payload and payload["limit"] != 5) or payload.get("offset", 0) != 0:
                    raise BodyError("invalid_schema")
                items = payload.get("itemSummaries", [] if payload.get("total") == 0 else None)
                if (
                    not isinstance(items, list)
                    or len(items) > 5
                    or any(
                        not isinstance(item, dict)
                        or not isinstance(item.get("itemId"), str)
                        or not item["itemId"].strip()
                        for item in items
                    )
                ):
                    raise BodyError("invalid_schema")
                if "total" in payload and payload["total"] < len(items):
                    raise BodyError("invalid_schema")
                connection.send(("result", "ok" if items else "empty", 200, len(items)))
            payload = None  # Never return listing content or token over IPC.
    except BodyError as exc:
        outcome = (
            str(exc) if str(exc) in {"body_limit", "malformed_json", "invalid_schema"} else "transport_error"
        )
        connection.send(("result", outcome, code, None))
    except (TimeoutError, httpx.TimeoutException):
        connection.send(("result", "timeout", None, None))
    except BaseException:
        # Never format a transport/parser exception: it may contain secrets/body.
        try:
            connection.send(("result", "transport_error", None, None))
        except (OSError, EOFError):
            pass
    finally:
        token = payload = None
        try:
            if response is not None:
                response.close()
            if transport is not None:
                transport.close()
        finally:
            connection.close()


def _wait_owned(process, seconds):
    # A readable multiprocessing sentinel can precede actual OS exit. join(t)
    # then calls blocking waitpid even after its timeout wait succeeded. Poll
    # owned handles with WNOHANG instead, including during terminal teardown.
    end = time.monotonic() + seconds
    while process.is_alive():
        if time.monotonic() >= end:
            return False
        time.sleep(min(POLL, max(0, end - time.monotonic())))
    process.join(0)
    return True


def _reap(process):
    # Only handles created/owned by this process; no journal PID or killpg.
    if process.is_alive():
        process.terminate()
    _wait_owned(process, 0.2)
    if process.is_alive():
        process.kill()
        _wait_owned(process, 0.2)
    return not process.is_alive()


def _guardian(
    parent,
    parent_other,
    directory,
    envelope,
    factory,
    parser,
    request_seconds,
    overall_seconds,
    clock,
    journal_type=Journal,
):
    parent_other.close()
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    journal = journal_type(directory)
    context = multiprocessing.get_context("fork")
    control, worker_end = context.Pipe()
    deadline = time.monotonic() + overall_seconds
    worker = context.Process(
        target=_worker,
        args=(
            worker_end,
            (parent, control),
            directory,
            envelope,
            factory,
            parser,
            request_seconds,
            deadline,
            journal.network_enabled,
        ),
    )
    stage_deadline = deadline
    controlled_deadline = clock() + overall_seconds
    outcome, code, count = "worker_lost", None, None
    cleanup = journal.worker_cleanup()
    worker.start()
    worker_end.close()
    try:
        while True:
            if parent.poll():  # EOF also wakes poll when the operator crashes.
                try:
                    parent.recv()
                except EOFError:
                    outcome = "abandoned"
                    break
            if journal.revoked():
                outcome = "stopped"
                break
            if time.monotonic() >= min(deadline, stage_deadline) or clock() >= controlled_deadline:
                outcome = "timeout"
                break
            if not control.poll(POLL):
                if not worker.is_alive():
                    if worker.exitcode == -signal.SIGALRM:
                        outcome = "timeout"
                    break
                continue
            message = control.recv()
            if message[0] == "reserve":
                # Repeat deadline/Stop gates after receiving queued worker work.
                if (
                    time.monotonic() >= min(deadline, stage_deadline)
                    or clock() >= controlled_deadline
                    or journal.revoked()
                ):
                    outcome = "stopped" if journal.revoked() else "timeout"
                    break
                journal.reserve(message[1])
                if time.monotonic() >= deadline or journal.revoked():
                    outcome = "stopped" if journal.revoked() else "timeout"
                    break
                stage_deadline = min(deadline, time.monotonic() + request_seconds)
                control.send(("permit", stage_deadline))
            elif message[0] == "result":
                if (
                    time.monotonic() >= min(deadline, stage_deadline)
                    or clock() >= controlled_deadline
                    or journal.revoked()
                ):
                    outcome = "stopped" if journal.revoked() else "timeout"
                else:
                    _, outcome, code, count = message
                break
            else:
                raise ProbeError("invalid_worker_message")
    except (OSError, EOFError, ProbeError):
        outcome = "timeout" if time.monotonic() >= min(deadline, stage_deadline) else "control_error"
        code, count = None, None
    finally:
        # Reap BEFORE committing/publication: stalled close/parser/transport cannot
        # delay cleanup, leak content to disk or publish a late result.
        reaped = _reap(worker)
        cleanup()
        control.close()
        if not reaped:
            journal.stop()
            outcome, count = "control_error", None
        if outcome in {"ok", "empty"} and time.monotonic() >= min(deadline, stage_deadline):
            outcome, count = "timeout", None
        try:
            journal.finish(outcome, code, count)
            parent.send({"cleanup_reaped": reaped})
        except (OSError, EOFError, ProbeError):
            pass
        parent.close()


def execute(
    directory,
    run_id,
    envelope,
    *,
    transport_factory=None,
    parser=decode_json,
    request_seconds=30.0,
    overall_seconds=75.0,
    clock=time.monotonic,
    journal_type=Journal,
):
    if transport_factory is None:
        raise ProbeError("offline_transport_required")
    if not callable(transport_factory) or not callable(parser) or not callable(clock):
        raise ProbeError("invalid_prerequisite")
    if (
        not math.isfinite(request_seconds)
        or not 0 < request_seconds <= 30
        or not math.isfinite(overall_seconds)
        or not 0 < overall_seconds <= 75
    ):
        raise ProbeError("invalid_timeout")
    envelope.validate()
    journal = journal_type(directory)
    journal.claim(run_id, envelope)  # Failure/crash consumes execution authority too.
    context = multiprocessing.get_context("fork")
    parent, child = context.Pipe()
    guardian = context.Process(
        target=_guardian,
        args=(
            child,
            parent,
            directory,
            envelope,
            transport_factory,
            parser,
            request_seconds,
            overall_seconds,
            clock,
            journal_type,
        ),
    )
    receipt = {"cleanup_reaped": False}
    guardian.start()
    child.close()
    try:
        if parent.poll(overall_seconds + CLEANUP_SECONDS):
            receipt = parent.recv()
        else:
            journal.stop()
        _wait_owned(guardian, CLEANUP_SECONDS)
        if guardian.is_alive():
            # Guardian only does bounded local control work. Do not release or
            # renew reservations if OS/process cleanup cannot be confirmed.
            raise ProbeError("cleanup_unconfirmed")
        if not receipt.get("cleanup_reaped") or guardian.exitcode != 0:
            raise ProbeError("cleanup_unconfirmed")
        result = journal.status()
        result.update(receipt)
        return result
    except EOFError:
        raise ProbeError("cleanup_unconfirmed") from None
    finally:
        parent.close()


class FixtureResponse:
    def __init__(self, body, status_code=200):
        self.body, self.status_code = body, status_code

    def iter_decoded(self, chunk_size):
        for start in range(0, len(self.body), chunk_size):
            yield self.body[start : start + chunk_size]

    def close(self):
        self.body = b""


class FixtureTransport:
    def __init__(self, scenario="success"):
        self.scenario = scenario

    def dispatch(self, request, *, credentials, token):
        validate_request(request, Envelope("EBAY_US", "US"))
        if self.scenario == "stall-" + request.stage:
            time.sleep(120)
        if request.stage == "oauth":
            return FixtureResponse(b'{"access_token":"offline-token","expires_in":300,"token_type":"Bearer"}')
        return FixtureResponse(
            b'{"itemSummaries":[]}'
            if self.scenario == "empty"
            else b'{"itemSummaries":[{"itemId":"offline-item"}]}'
        )

    def close(self):
        pass


def main(argv=None):
    cli = argparse.ArgumentParser(description="Offline SHOP-01C operator; real execution is unavailable.")
    cli.add_argument(
        "--state-dir", type=Path, required=True, help="private disposable OFFLINE authority directory"
    )
    commands = cli.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare", help="issue one offline authority; never reset an existing slot")
    prepare.add_argument("--run-id", required=True)
    prepare.add_argument("--marketplace", choices=["EBAY_US"], required=True)
    prepare.add_argument("--country", choices=["US"], required=True)
    execute_cli = commands.add_parser(
        "execute", help="dummy credentials and explicitly selected fake transport only"
    )
    execute_cli.add_argument("--run-id", required=True)
    execute_cli.add_argument(
        "--fixture", required=True, choices=["success", "empty", "stall-oauth", "stall-browse"]
    )
    commands.add_parser("status")
    commands.add_parser("stop", help="durably revoke authority; never signals a stored PID")
    args = cli.parse_args(argv)
    journal = Journal(args.state_dir)
    try:
        if args.command == "prepare":
            result = journal.prepare(args.run_id, Envelope(args.marketplace, args.country))
        elif args.command == "execute":
            current = journal.status()["envelope"]
            result = execute(
                args.state_dir,
                args.run_id,
                Envelope(current["marketplace"], current["country"]),
                transport_factory=lambda: FixtureTransport(args.fixture),
            )
        elif args.command == "stop":
            result = journal.stop()
        else:
            result = journal.status()
        print(json.dumps(result, sort_keys=True))
        return 0 if result["outcome"] in {"ok", "empty", "prepared", "running", "stopped"} else 1
    except (ProbeError, OSError, ValueError, TypeError):
        print(json.dumps({"outcome": "refused", "real_provider_requests": 0}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
