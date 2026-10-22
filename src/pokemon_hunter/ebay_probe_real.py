"""Explicit eBay transport and canonical authority; the default probe stays offline.

No customer configuration or environment credentials are read. Only the bounded
worker constructs the client, reads hidden input and holds response content.
"""

import argparse
import base64
import hashlib
import json
import os
import pwd
import re
import resource
import signal
import stat
import termios
import time
import zlib
from dataclasses import dataclass
from pathlib import Path

import httpx

from . import ebay_probe as probe

RUN_ID = "shop-01d-20261015"
# OS account home, never HOME/XDG/config or a caller-supplied directory.
PRIVATE = Path(pwd.getpwuid(os.getuid()).pw_dir) / ".local/share/dex/ebay-connection-test"
CANONICAL = PRIVATE / RUN_ID
ENROLLMENT = PRIVATE / (RUN_ID + ".enrollment.json")
ISSUED = PRIVATE / (RUN_ID + ".issued")
STOP = PRIVATE / (RUN_ID + ".stop")
APPLICATION = {"developer_account": "mikefusc", "application": "dex", "keyset": "existing-production"}
WIRE_EXTRA = 64 * 1024
MAX_CHUNKS = 8192


def candidate_digest():
    return hashlib.sha256(Path(__file__).read_bytes() + Path(probe.__file__).read_bytes()).hexdigest()


@dataclass(frozen=True)
class RealEnvelope(probe.Envelope):
    def binding(self):
        return dict(
            super().binding(),
            mode="real-production-shop01d-v1",
            application=APPLICATION,
            environment="production",
            selected_run=RUN_ID,
            candidate_sha256=candidate_digest(),
        )


ENV = RealEnvelope("EBAY_US", "US")


def _read_private_json(path, limit=16384):
    fd = probe._open_private(path, os.O_RDONLY)
    with os.fdopen(fd, "rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise probe.ProbeError("invalid_preflight")
    return probe.decode_json(raw)


def validate_preflight(record, now=None):
    """A sanitized decision receipt, not a substitute for reviewing real evidence.

    Only noncontent decisions/reference labels belong here. Never copy contracts,
    key identifiers/values, responses or private correspondence into this receipt.
    """
    now = time.time() if now is None else now
    if not isinstance(record, dict) or set(record) != {
        "binding",
        "owner_selected",
        "access_evidence_reviewed",
        "allowance_evidence_reviewed",
        "temporary_processing_permitted",
        "oauth_remaining_at_least_one",
        "browse_remaining_at_least_one",
        "destination_approved",
        "stop_verified",
        "reviewed_at",
        "valid_until",
    }:
        raise probe.ProbeError("incomplete_preflight")
    if record["binding"] != ENV.binding():
        raise probe.ProbeError("preflight_binding_mismatch")
    for key in set(record) - {"binding", "reviewed_at", "valid_until"}:
        if record[key] is not True:
            raise probe.ProbeError("unmet_preflight")
    start, end = record["reviewed_at"], record["valid_until"]
    if (
        type(start) not in (int, float)
        or type(end) not in (int, float)
        or not start <= now < end <= start + 900
    ):
        raise probe.ProbeError("expired_preflight")
    return record


class RealJournal(probe.Journal):
    envelope_type = RealEnvelope
    network_enabled = True

    def __init__(self, directory=None):
        if directory is not None and Path(directory) != CANONICAL:
            raise probe.ProbeError("canonical_path_required")
        super().__init__(CANONICAL)

    def _check_parent(self):
        for path in (PRIVATE, *PRIVATE.parents):
            if path.is_symlink():
                raise probe.ProbeError("unsafe_state")
        info = PRIVATE.stat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise probe.ProbeError("unsafe_state")

    def prepare(self, run_id, envelope):
        # The generic/offline API can never mint real authority.
        raise probe.ProbeError("reviewed_real_selection_required")

    def issue(self, preflight):
        validate_preflight(preflight)
        self._check_parent()
        # Enrollment is installed ONCE during engineering preparation, grants no
        # dispatch, and has no create/reset/restore command in this package.
        # Missing, consumed or corrupt enrollment is never reconstructed.
        fd = probe._open_private(ENROLLMENT, os.O_RDWR)
        try:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with os.fdopen(os.dup(fd), "rb") as stream:
                raw = stream.read(16385)
            enrollment = probe.decode_json(raw)
            if enrollment != {"state": "unissued", "binding": ENV.binding()}:
                raise probe.ProbeError("authority_consumed")
            if os.path.lexists(ISSUED) or os.path.lexists(CANONICAL) or self.revoked():
                raise probe.ProbeError("authority_consumed")
            # Burn enrollment before any directory/authority creation. A torn
            # write, crash or missing later state fails closed forever.
            os.lseek(fd, 0, os.SEEK_SET)
            os.ftruncate(fd, 0)
            os.write(fd, b'{"state":"consumed"}\n')
            os.fsync(fd)
            marker = probe._open_private(ISSUED, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
            os.fsync(marker)
            os.close(marker)
            probe._sync_dir(PRIVATE)
            return super().prepare(RUN_ID, ENV)
        finally:
            os.close(fd)

    def _read(self):
        self._check_parent()
        if _read_private_json(ENROLLMENT) != {"state": "consumed"}:
            raise probe.ProbeError("corrupt_state")
        fd = probe._open_private(ISSUED, os.O_RDONLY)
        try:
            if os.fstat(fd).st_size != 0:
                raise probe.ProbeError("corrupt_state")
        finally:
            os.close(fd)
        state = super()._read()
        if state["run_id"] != RUN_ID:
            raise probe.ProbeError("authority_mismatch")
        return state

    def claim(self, run_id, envelope):
        if run_id != RUN_ID or envelope.binding() != ENV.binding():
            raise probe.ProbeError("authority_mismatch")
        return super().claim(run_id, envelope)

    def revoked(self):
        return os.path.lexists(STOP) or super().revoked()

    def stop(self):
        # Works before issuance too. Missing/corrupt journal cannot prevent this
        # independent permanent revocation marker, and never triggers issuance.
        self._check_parent()
        try:
            fd = probe._open_private(STOP, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
            os.fsync(fd)
            os.close(fd)
            probe._sync_dir(PRIVATE)
        except FileExistsError:
            pass
        if os.path.lexists(CANONICAL):
            return super().stop()
        return {"outcome": "stopped", "revoked": True, "authority_issued": False}

    def worker_cleanup(self):
        # Guardian captures terminal settings, never credentials. Reaping a
        # stalled/terminated input worker must also restore terminal echo.
        try:
            fd = os.open("/dev/tty", os.O_RDWR | os.O_NOCTTY)
        except OSError:
            return super().worker_cleanup()  # fake transport qualification has no TTY
        previous = termios.tcgetattr(fd)

        def restore():
            try:
                termios.tcsetattr(fd, termios.TCSAFLUSH, previous)
            finally:
                os.close(fd)

        return restore


def hidden_credentials():
    """Explicit controlling-TTY input only; no getpass echo/stdin fallback."""
    values = []
    fd = os.open("/dev/tty", os.O_RDWR | os.O_NOCTTY)
    try:
        if not os.isatty(fd):
            raise probe.ProbeError("private_tty_required")
        previous = termios.tcgetattr(fd)
        handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGALRM)}

        def interrupted(sig, frame):
            # Also restore if the guardian dies and the kernel timer fires.
            termios.tcsetattr(fd, termios.TCSAFLUSH, previous)
            signal.signal(sig, signal.SIG_DFL)
            os.kill(os.getpid(), sig)

        for sig in handlers:
            signal.signal(sig, interrupted)
        hidden = list(previous)
        hidden[3] &= ~(termios.ECHO | termios.ECHONL)
        termios.tcsetattr(fd, termios.TCSAFLUSH, hidden)
        try:
            for prompt in (b"Existing dex Production App ID (hidden): ", b"Matching Cert ID (hidden): "):
                os.write(fd, prompt)
                raw = bytearray()
                while True:
                    char = os.read(fd, 1)
                    if char in (b"\n", b"\r"):
                        break
                    if not char or len(raw) >= 2048:
                        raise probe.ProbeError("invalid_private_input")
                    raw.extend(char)
                values.append(raw.decode("ascii"))
                raw.clear()
                os.write(fd, b"\n")
        finally:
            termios.tcsetattr(fd, termios.TCSAFLUSH, previous)
            for sig, handler in handlers.items():
                signal.signal(sig, handler)
    finally:
        os.close(fd)
    _validate_credentials(tuple(values))
    return tuple(values)


def check_private_context():
    """No input: reject a missing/unsafe controlling terminal before issuance."""
    fd = os.open("/dev/tty", os.O_RDWR | os.O_NOCTTY)
    try:
        if not os.isatty(fd):
            raise probe.ProbeError("private_tty_required")
        termios.tcgetattr(fd)
    finally:
        os.close(fd)
    RealJournal()._check_parent()


def _validate_credentials(pair):
    if (
        not isinstance(pair, tuple)
        or len(pair) != 2
        or any(
            not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,2048}", value) for value in pair
        )
    ):
        raise probe.ProbeError("invalid_private_input")


class StreamedResponse:
    """Read raw HTTP stream; never invoke httpx's unbounded auto-decompressor."""

    def __init__(self, response, limit):
        self.response, self.status_code, self.limit = response, response.status_code, limit

    def iter_decoded(self, chunk_size):
        if chunk_size != probe.CHUNK_LIMIT:
            raise probe.BodyError("body_limit")
        encoding = self.response.headers.get("content-encoding", "identity").strip().lower()
        if encoding not in {"identity", "gzip", "deflate"}:
            raise probe.BodyError("invalid_schema")
        length = self.response.headers.get("content-length")
        if length is not None and (
            not re.fullmatch(r"[0-9]{1,12}", length) or int(length) > self.limit + WIRE_EXTRA
        ):
            raise probe.BodyError("body_limit")
        decoder = None if encoding == "identity" else zlib.decompressobj(31 if encoding == "gzip" else 15)
        wire = decoded = chunks = 0
        try:
            # HTTP/1 core reads at most 64KiB. Iterate without a chunker so even
            # empty/tiny chunks are counted; no accumulated raw buffering.
            for raw in self.response.iter_raw():
                chunks += 1
                if not isinstance(raw, bytes) or len(raw) > chunk_size or chunks > MAX_CHUNKS:
                    raise probe.BodyError("body_limit")
                wire += len(raw)
                if wire > self.limit + WIRE_EXTRA:
                    raise probe.BodyError("body_limit")
                pending = raw
                while pending:
                    if decoder is None:
                        output, pending = pending, b""
                    else:
                        if decoder.eof:
                            raise probe.BodyError("malformed_json")
                        # At most one extra byte is decoded to detect overflow;
                        # unrestricted decompress/flush is never used.
                        output = decoder.decompress(pending, min(chunk_size, self.limit - decoded + 1))
                        pending = decoder.unconsumed_tail
                        if decoder.unused_data:
                            raise probe.BodyError("malformed_json")
                    decoded += len(output)
                    if decoded > self.limit:
                        raise probe.BodyError("body_limit")
                    if output:
                        yield output
            if decoder is not None and not decoder.eof:
                raise probe.BodyError("malformed_json")
        except zlib.error:
            raise probe.BodyError("malformed_json") from None

    def close(self):
        self.response.close()


class RealTransport:
    """Single HTTP send per dispatch, credentials read within the worker only.

    Inject HTTP transport/private input in offline tests. Production CLI exposes
    neither injection nor endpoint, directory, run-ID or credential arguments.
    """

    def __init__(self, *, transport=None, credential_reader=hidden_credentials):
        self.reader = credential_reader
        self.next_stage = "oauth"
        self.client = httpx.Client(
            transport=transport
            if transport is not None
            else httpx.HTTPTransport(
                retries=0,
                trust_env=False,
                http1=True,
                http2=False,
                limits=httpx.Limits(max_connections=1, max_keepalive_connections=0),
            ),
            auth=None,
            trust_env=False,
            follow_redirects=False,
        )

    def dispatch(self, request, *, credentials, token):
        probe.validate_request(request, ENV)
        if request.stage != self.next_stage:
            raise probe.ProbeError("attempt_budget")
        self.next_stage = "browse" if request.stage == "oauth" else None
        deadline = time.monotonic() + request.timeout
        headers = dict(request.headers)
        headers.update(
            {"Accept": "application/json", "Accept-Encoding": "gzip, deflate", "Connection": "close"}
        )
        if request.stage == "oauth":
            if credentials != probe.DUMMY or token is not None:
                raise probe.ProbeError("invalid_private_input")
            pair = self.reader()
            _validate_credentials(pair)
            headers["Authorization"] = (
                "Basic " + base64.b64encode((pair[0] + ":" + pair[1]).encode()).decode()
            )
            pair = None
        else:
            if (
                credentials is not None
                or not isinstance(token, str)
                or not re.fullmatch(r"[\x21-\x7e]{1,8192}", token)
            ):
                raise probe.ProbeError("invalid_token")
            headers["Authorization"] = "Bearer " + token
        # Direct Request avoids client cookie/default-header merging. send has no
        # auth flow and no redirects; transport retries are explicitly zero.
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError
        wire = httpx.Request(
            request.method,
            request.url,
            headers=headers,
            params=request.params or None,
            data=dict(request.data) or None,
            extensions={"timeout": {key: remaining for key in ("connect", "read", "write", "pool")}},
        )
        if wire.url.scheme != "https" or wire.url.host != "api.ebay.com" or wire.url.port not in (None, 443):
            raise probe.ProbeError("unexpected_request")
        response = self.client.send(wire, stream=True, auth=None, follow_redirects=False)
        return StreamedResponse(
            response,
            probe.AUTHORIZATION_RESPONSE_LIMIT_BYTES if request.stage == "oauth" else probe.BODY_LIMIT,
        )

    def close(self):
        self.reader = None
        self.client.close()


def execute_real(preflight):
    validate_preflight(preflight)
    # Verify the independent revocation path/permissions before private input.
    journal = RealJournal()
    journal.status()
    return probe.execute(
        CANONICAL,
        RUN_ID,
        ENV,
        transport_factory=RealTransport,
        journal_type=RealJournal,
    )


def main(argv=None):
    cli = argparse.ArgumentParser(description="Explicit real eBay probe; offline remains the default module.")
    commands = cli.add_subparsers(dest="command", required=True)
    run = commands.add_parser(
        "execute", help="requires reviewed facts and explicit owner selection; no retries"
    )
    run.add_argument("--preflight", type=Path, required=True)
    run.add_argument("--owner-selected-this-run", action="store_true", required=True)
    commands.add_parser("status")
    commands.add_parser("stop")
    commands.add_parser("binding", help="print fixed nonsecret binding; issues no authority")
    args = cli.parse_args(argv)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    try:
        if args.command == "binding":
            result = ENV.binding()
        elif args.command == "stop":
            result = RealJournal().stop()
        elif args.command == "status":
            result = RealJournal().status()
        else:
            preflight = validate_preflight(_read_private_json(args.preflight))
            check_private_context()
            # One invocation issues and consumes a single authority. Prepared or
            # interrupted authority is not resumable via another invocation.
            RealJournal().issue(preflight)
            result = execute_real(preflight)
        print(json.dumps(result, sort_keys=True))
        return 0 if result.get("outcome") in (None, "ok", "empty", "stopped", "prepared", "running") else 1
    except (probe.ProbeError, OSError, ValueError, TypeError, EOFError):
        # Cannot assert zero requests from a failed command: reservations may be
        # consumed/uncertain. Preserve state; use status/Stop, never replacement.
        print(json.dumps({"outcome": "refused", "consumption": "inspect canonical status; never retry"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
