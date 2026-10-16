"""eBay transport adapter tests with fake HTTP streams and OS network denial.

All real-namespace slots below are disposable engineering state via monkeypatch;
no test enrolls or issues the canonical owner slot or sees genuine credentials.
"""

import dataclasses
import gzip
import json
import multiprocessing
import os
import signal
import time
import zlib
from pathlib import Path

import httpx
import pytest

from pokemon_hunter import ebay_probe as probe
from pokemon_hunter import ebay_probe_real as real

SECRET = "CANARY_SECRET_SHOP01D"
CLIENT = "CANARY_CLIENT_SHOP01D"
TOKEN = "CANARY_TOKEN_SHOP01D"
BODY = "CANARY_SELLER_PRICE_BODY_SHOP01D"
PAIR = (CLIENT, SECRET)
OAUTH = json.dumps({"access_token": TOKEN, "expires_in": 300, "token_type": "Bearer"}).encode()
BROWSE = json.dumps(
    {"itemSummaries": [{"itemId": "fake", "title": BODY}], "next": "https://bad.invalid"}
).encode()


class Stream(httpx.SyncByteStream):
    def __init__(self, raw, *, split=1024, stall=False, crash=False, stop=None):
        self.raw, self.split, self.stall, self.crash, self.stop = raw, split, stall, crash, stop

    def __iter__(self):
        if self.stop:
            self.stop()
        if self.crash:
            os._exit(71)
        if self.stall:
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            time.sleep(10)
        for start in range(0, len(self.raw), self.split):
            yield self.raw[start : start + self.split]


def receipt():
    now = time.time()
    return dict(
        binding=real.ENV.binding(),
        owner_selected=True,
        access_evidence_reviewed=True,
        allowance_evidence_reviewed=True,
        temporary_processing_permitted=True,
        oauth_remaining_at_least_one=True,
        browse_remaining_at_least_one=True,
        destination_approved=True,
        stop_verified=True,
        reviewed_at=now,
        valid_until=now + 120,
    )


@pytest.fixture
def enrolled(tmp_path, monkeypatch):
    parent = tmp_path / "private"
    parent.mkdir(mode=0o700)
    monkeypatch.setattr(real, "PRIVATE", parent)
    monkeypatch.setattr(real, "CANONICAL", parent / real.RUN_ID)
    monkeypatch.setattr(real, "ENROLLMENT", parent / (real.RUN_ID + ".enrollment.json"))
    monkeypatch.setattr(real, "ISSUED", parent / (real.RUN_ID + ".issued"))
    monkeypatch.setattr(real, "STOP", parent / (real.RUN_ID + ".stop"))
    real.ENROLLMENT.write_text(json.dumps({"state": "unissued", "binding": real.ENV.binding()}))
    real.ENROLLMENT.chmod(0o600)
    return real.RealJournal()


@pytest.fixture
def authority(enrolled):
    enrolled.issue(receipt())
    return enrolled


def canaries_absent(directory):
    for path in directory.rglob("*"):
        if path.is_file():
            for value in (SECRET, CLIENT, TOKEN, BODY):
                assert value.encode() not in path.read_bytes()


def run(
    authority,
    *,
    codes=None,
    bodies=None,
    encoding="gzip",
    split=1024,
    stall=None,
    stop=None,
    crash=None,
    parser=probe.decode_json,
    request_seconds=1,
    overall_seconds=3,
    clock=time.monotonic,
):
    audit = authority.path.parent / "audit"
    codes, bodies = codes or {}, bodies or {}

    def handler(request):
        stage = "oauth" if request.url.path.endswith("token") else "browse"
        with audit.open("a") as stream:
            stream.write(stage + "\n")
        body = bodies.get(stage, OAUTH if stage == "oauth" else BROWSE)
        encoded = (
            gzip.compress(body)
            if encoding == "gzip"
            else zlib.compress(body)
            if encoding == "deflate"
            else body
        )
        headers = {"content-encoding": encoding}
        return httpx.Response(
            codes.get(stage, 200),
            headers=headers,
            stream=Stream(
                encoded,
                split=split,
                stall=stall == stage,
                crash=crash == stage,
                stop=authority.stop if stop == stage else None,
            ),
        )

    result = probe.execute(
        authority.path,
        real.RUN_ID,
        real.ENV,
        journal_type=real.RealJournal,
        transport_factory=lambda: real.RealTransport(
            transport=httpx.MockTransport(handler), credential_reader=lambda: PAIR
        ),
        parser=parser,
        request_seconds=request_seconds,
        overall_seconds=overall_seconds,
        clock=clock,
    )
    assert result["cleanup_reaped"] and not multiprocessing.active_children()
    assert "simulated_consumed" not in result and "real_provider_requests" not in result
    canaries_absent(authority.path.parent)
    return result, audit.read_text().splitlines() if audit.exists() else []


def test_exact_wire_requests_and_no_continuation(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://must-not-be-used.invalid:1")
    seen = []

    def handler(request):
        seen.append(request)
        assert request.url.scheme == "https" and request.url.host == "api.ebay.com"
        assert "cookie" not in request.headers
        assert set(request.extensions["timeout"]) == {"connect", "read", "write", "pool"}
        assert all(0 < value <= 1 for value in request.extensions["timeout"].values())
        if len(seen) == 1:
            assert request.method == "POST" and request.url.path == "/identity/v1/oauth2/token"
            assert not request.url.query
            import base64

            assert (
                request.headers["authorization"]
                == "Basic " + base64.b64encode((CLIENT + ":" + SECRET).encode()).decode()
            )
            assert (
                request.content
                == b"grant_type=client_credentials&scope=https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope"
            )
            return httpx.Response(200, headers={"set-cookie": "unwanted=private"}, stream=Stream(OAUTH))
        assert request.method == "GET" and request.url.path == "/buy/browse/v1/item_summary/search"
        assert request.headers["authorization"] == "Bearer " + TOKEN
        assert request.headers["x-ebay-c-marketplace-id"] == "EBAY_US"
        assert dict(request.url.params) == {
            "q": probe.QUERY,
            "filter": "buyingOptions:{FIXED_PRICE},deliveryCountry:US",
            "limit": "5",
            "offset": "0",
            "fieldgroups": "EXTENDED",
        }
        assert not request.content
        return httpx.Response(200, stream=Stream(BROWSE))

    transport = real.RealTransport(transport=httpx.MockTransport(handler), credential_reader=lambda: PAIR)
    try:
        first = transport.dispatch(
            probe.request_for("oauth", real.ENV, 1), credentials=probe.DUMMY, token=None
        )
        assert probe.bounded_json(first, probe.AUTHORIZATION_RESPONSE_LIMIT_BYTES)["access_token"] == TOKEN
        second = transport.dispatch(probe.request_for("browse", real.ENV, 1), credentials=None, token=TOKEN)
        assert len(probe.bounded_json(second, probe.BODY_LIMIT)["itemSummaries"]) == 1
        with pytest.raises(probe.ProbeError):
            transport.dispatch(probe.request_for("browse", real.ENV, 1), credentials=None, token=TOKEN)
        assert len(seen) == 2
    finally:
        transport.close()


def test_production_transport_options_no_ambient(monkeypatch):
    actual = httpx.HTTPTransport
    seen = []

    def factory(**kwargs):
        seen.append(kwargs)
        return actual(**kwargs)

    monkeypatch.setattr(httpx, "HTTPTransport", factory)
    transport = real.RealTransport(credential_reader=lambda: PAIR)
    assert seen[0]["retries"] == 0 and seen[0]["trust_env"] is False
    assert seen[0]["http1"] is True and seen[0]["http2"] is False
    assert transport.client.trust_env is False and transport.client.follow_redirects is False
    assert transport.client.auth is None
    transport.close()


@pytest.mark.parametrize(
    "change",
    [
        {"method": "PUT"},
        {"url": "https://api.sandbox.ebay.com/identity/v1/oauth2/token"},
        {"url": probe.AUTHORIZATION_ENDPOINT_URL + "?x=1"},
        {"url": probe.AUTHORIZATION_ENDPOINT_URL + "/"},
        {"params": (("q", "other"),)},
        {"follow_redirects": True},
        {"headers": (("Host", "bad.invalid"),)},
        {"timeout": 31},
        {"data": (("grant_type", "refresh_token"),)},
    ],
)
def test_modified_requests_rejected_before_input_or_send(change):
    def forbidden(*args):
        raise AssertionError("input/dispatch occurred")

    transport = real.RealTransport(transport=httpx.MockTransport(forbidden), credential_reader=forbidden)
    try:
        with pytest.raises(probe.ProbeError):
            transport.dispatch(
                dataclasses.replace(probe.request_for("oauth", real.ENV, 1), **change),
                credentials=probe.DUMMY,
                token=None,
            )
    finally:
        transport.close()


@pytest.mark.parametrize("encoding", ["identity", "gzip", "deflate"])
@pytest.mark.parametrize("split", [1, 7, 65536])
def test_chunk_boundaries_success(authority, encoding, split):
    result, stages = run(authority, encoding=encoding, split=split)
    assert result["outcome"] == "ok" and result["count"] == 1
    assert result["consumed_operations"] == 2 and stages == ["oauth", "browse"]


@pytest.mark.parametrize("code", [301, 302, 307, 308, 400, 401, 403, 429, 500, 503])
@pytest.mark.parametrize("stage", ["oauth", "browse"])
def test_failure_no_retries_auth_redirect_or_body_read(authority, code, stage):
    result, stages = run(authority, codes={stage: code}, stall=stage)
    assert result["outcome"] == ("redirect" if code < 400 else "http_error")
    assert result["http_status"] == code and result["count"] is None
    assert stages == (["oauth"] if stage == "oauth" else ["oauth", "browse"])


@pytest.mark.parametrize(
    "stage,limit", [("oauth", probe.AUTHORIZATION_RESPONSE_LIMIT_BYTES), ("browse", probe.BODY_LIMIT)]
)
@pytest.mark.parametrize("encoding", ["identity", "gzip", "deflate"])
def test_overflow_before_parser(authority, stage, limit, encoding):
    def parser(body):
        assert len(body) <= limit
        return probe.decode_json(body)

    result, stages = run(authority, bodies={stage: b" " * (limit + 1)}, encoding=encoding, parser=parser)
    assert result["outcome"] == "body_limit" and len(stages) == (1 if stage == "oauth" else 2)


@pytest.mark.parametrize(
    "raw,encoding",
    [
        (b"not compressed", "gzip"),
        (gzip.compress(b"{}")[:-1], "gzip"),
        (gzip.compress(b"{}") + gzip.compress(b"{}"), "gzip"),
        (gzip.compress(b"{}") + b"junk", "gzip"),
        (zlib.compress(b"{}")[:-1], "deflate"),
        (b"{}", "br"),
        (b"{}", "gzip, deflate"),
        (b"{}", "unknown"),
        (b"{}", "deflate"),
    ],
)
def test_bad_encoding(raw, encoding):
    response = httpx.Response(200, headers={"content-encoding": encoding}, stream=Stream(raw, split=1))
    with pytest.raises(probe.BodyError):
        probe.bounded_json(
            real.StreamedResponse(response, probe.AUTHORIZATION_RESPONSE_LIMIT_BYTES),
            probe.AUTHORIZATION_RESPONSE_LIMIT_BYTES,
        )


@pytest.mark.parametrize("encoding", ["gzip", "deflate"])
def test_exact_decoded_bound(encoding):
    body = b'{"total":0}' + b" " * (probe.BODY_LIMIT - len(b'{"total":0}'))
    raw = gzip.compress(body) if encoding == "gzip" else zlib.compress(body)
    response = httpx.Response(200, headers={"content-encoding": encoding}, stream=Stream(raw, split=17))
    assert probe.bounded_json(real.StreamedResponse(response, probe.BODY_LIMIT), probe.BODY_LIMIT) == {
        "total": 0
    }


@pytest.mark.parametrize("length", ["999999999999", "-1", "bad", "1, 1"])
def test_invalid_or_oversized_content_length(length):
    response = httpx.Response(200, headers={"content-length": length}, stream=Stream(b"{}", stall=True))
    with pytest.raises(probe.BodyError):
        probe.bounded_json(real.StreamedResponse(response, 64), 64)


def test_raw_wire_and_chunk_count_caps():
    class TooMany(httpx.SyncByteStream):
        def __iter__(self):
            yield from [b""] * (real.MAX_CHUNKS + 1)

    # httpx.iter_raw preserves empty chunks with no chunk_size.
    response = httpx.Response(200, stream=TooMany())
    with pytest.raises(probe.BodyError):
        probe.bounded_json(real.StreamedResponse(response, 64), 64)
    response = httpx.Response(200, stream=Stream(b"x" * 65537, split=65537))
    with pytest.raises(probe.BodyError):
        probe.bounded_json(real.StreamedResponse(response, probe.BODY_LIMIT), probe.BODY_LIMIT)


@pytest.mark.parametrize(
    "stage,body,expected",
    [
        ("oauth", b"bad-json", "malformed_json"),
        ("oauth", b'{"access_token":"x\\n","expires_in":1}', "invalid_schema"),
        ("browse", b'{"total":true}', "invalid_schema"),
        ("browse", b'{"total":-1}', "invalid_schema"),
        ("browse", b'{"total":0,"itemSummaries":[{"itemId":"x"}]}', "invalid_schema"),
        ("browse", b'{"itemSummaries":[],"limit":6}', "invalid_schema"),
        ("browse", b'{"itemSummaries":[],"offset":5}', "invalid_schema"),
        ("browse", b'{"itemSummaries":[{},{},{},{},{},{}]}', "invalid_schema"),
        ("browse", b'{"total":0,"total":0}', "malformed_json"),
        ("browse", b'{"itemSummaries":[],"x":NaN}', "malformed_json"),
    ],
)
def test_schema_faults(authority, stage, body, expected):
    result, stages = run(authority, bodies={stage: body})
    assert result["outcome"] == expected and result["count"] is None
    assert len(stages) == (1 if stage == "oauth" else 2)


def test_empty_ends_once(authority):
    result, stages = run(authority, bodies={"browse": b'{"total":0}'})
    assert result["outcome"] == "empty" and result["count"] == 0 and stages == ["oauth", "browse"]


@pytest.mark.parametrize("stage", ["oauth", "browse"])
def test_deadline_during_stream(authority, stage):
    before = time.monotonic()
    result, stages = run(authority, stall=stage, request_seconds=0.12)
    assert result["outcome"] == "timeout" and result["count"] is None
    assert time.monotonic() - before < 1.5 and len(stages) == (1 if stage == "oauth" else 2)


@pytest.mark.parametrize("stage", ["oauth", "browse"])
def test_stop_during_stream_reaps_owned_worker(authority, stage):
    result, stages = run(authority, stop=stage, stall=stage)
    assert result["outcome"] == "stopped" and result["count"] is None
    assert len(stages) == (1 if stage == "oauth" else 2)


def test_stop_between_requests(authority):
    def parser(body):
        value = probe.decode_json(body)
        if "access_token" in value:
            authority.stop()
        return value

    result, stages = run(authority, parser=parser)
    assert result["outcome"] == "stopped" and stages == ["oauth"]


def test_stop_before_start(authority):
    authority.stop()
    with pytest.raises(probe.ProbeError):
        run(authority)
    assert authority.status()["consumed_operations"] == 0


def test_late_parser_result_suppressed(authority):
    def parser(body):
        result = probe.decode_json(body)
        if "itemSummaries" in result:
            time.sleep(0.4)
        return result

    result, _ = run(authority, parser=parser, request_seconds=0.1)
    assert result["outcome"] == "timeout" and result["count"] is None


def test_total_deadline_includes_transport_factory(authority):
    def factory():
        time.sleep(5)

    result = probe.execute(
        authority.path,
        real.RUN_ID,
        real.ENV,
        journal_type=real.RealJournal,
        transport_factory=factory,
        overall_seconds=0.1,
    )
    assert result["outcome"] == "timeout" and result["consumed_operations"] == 0


@pytest.mark.parametrize("stage", ["oauth", "browse"])
def test_crash_consumes_and_cannot_reissue(authority, stage):
    result, _ = run(authority, crash=stage)
    assert result["consumed_operations"] == (1 if stage == "oauth" else 2)
    assert result["count"] is None
    with pytest.raises(probe.ProbeError):
        authority.issue(receipt())
    with pytest.raises(probe.ProbeError):
        run(authority)


def test_canonical_and_namespace_separation(authority, tmp_path):
    with pytest.raises(probe.ProbeError):
        real.RealJournal(tmp_path / "replacement")
    with pytest.raises(probe.ProbeError):
        probe.Journal(authority.path).status()
    with pytest.raises(probe.ProbeError):
        authority.claim("replacement", real.ENV)
    with pytest.raises(probe.ProbeError):
        authority.claim(real.RUN_ID, probe.Envelope("EBAY_US", "US"))
    with pytest.raises(probe.ProbeError):
        authority.prepare("replacement", real.ENV)
    assert authority.status()["consumed_operations"] == 0


@pytest.mark.parametrize(
    "part", ["authority.json", "issued", "lock", "enrollment", "outer-issued", "directory"]
)
def test_deleted_issued_state_never_recreates_budget(authority, part):
    authority.claim(real.RUN_ID, real.ENV)
    authority.reserve("oauth")
    if part == "enrollment":
        real.ENROLLMENT.unlink()
    elif part == "outer-issued":
        real.ISSUED.unlink()
    elif part == "directory":
        import shutil

        shutil.rmtree(authority.path)
    else:
        (authority.path / part).unlink()
    with pytest.raises((probe.ProbeError, OSError)):
        authority.issue(receipt())
    with pytest.raises((probe.ProbeError, OSError)):
        authority.status()


def test_missing_enrollment_cannot_issue(enrolled):
    real.ENROLLMENT.unlink()
    with pytest.raises(OSError):
        enrolled.issue(receipt())
    assert not real.CANONICAL.exists() and not real.ISSUED.exists()


def test_all_consumed_records_deleted_still_no_enrollment_recreation(authority):
    import shutil

    shutil.rmtree(real.PRIVATE)
    real.PRIVATE.mkdir(mode=0o700)
    with pytest.raises(OSError):
        authority.issue(receipt())


def test_torn_enrollment_and_corrupt_state_fail_closed(enrolled):
    real.ENROLLMENT.write_text('{"state":')
    with pytest.raises(ValueError):
        enrolled.issue(receipt())
    assert not real.CANONICAL.exists()


def test_concurrent_issue_once(enrolled):
    ctx = multiprocessing.get_context("fork")
    parent, child = ctx.Pipe()

    def issue():
        try:
            enrolled.issue(receipt())
            child.send("issued")
        except (probe.ProbeError, OSError):
            child.send("refused")

    children = [ctx.Process(target=issue) for _ in range(2)]
    for process in children:
        process.start()
    outcomes = [parent.recv(), parent.recv()]
    for process in children:
        process.join(2)
        assert process.exitcode == 0
    assert sorted(outcomes) == ["issued", "refused"]
    child.close()
    parent.close()


@pytest.mark.parametrize(
    "key",
    [
        "owner_selected",
        "access_evidence_reviewed",
        "allowance_evidence_reviewed",
        "temporary_processing_permitted",
        "oauth_remaining_at_least_one",
        "browse_remaining_at_least_one",
        "destination_approved",
        "stop_verified",
    ],
)
def test_each_preflight_fact_required_before_issue_or_input(enrolled, key):
    current = receipt()
    current[key] = False
    with pytest.raises(probe.ProbeError):
        enrolled.issue(current)
    assert not real.CANONICAL.exists() and not real.ISSUED.exists()


@pytest.mark.parametrize(
    "change",
    [
        {"reviewed_at": 0, "valid_until": 1},
        {"valid_until": float("inf")},
        {"binding": {}},
        {"extra": True},
        {"owner_selected": 1},
    ],
)
def test_preflight_binding_expiry_strict(change):
    current = receipt() | change
    with pytest.raises(probe.ProbeError):
        real.validate_preflight(current)


def test_hidden_input_has_no_environment_fallback(monkeypatch):
    monkeypatch.setenv("EBAY_CLIENT_ID", CLIENT)
    monkeypatch.setenv("EBAY_CLIENT_SECRET", SECRET)

    def no_tty(*args):
        raise OSError("no tty")

    monkeypatch.setattr(real.os, "open", no_tty)
    with pytest.raises(OSError):
        real.hidden_credentials()


def test_cli_cannot_override_path_run_or_credentials():
    for args in (
        ["--state-dir", "/tmp/other", "status"],
        ["execute", "--run-id", "new"],
        ["execute", "--client-secret", SECRET],
        ["prepare"],
    ):
        with pytest.raises(SystemExit):
            real.main(args)


def test_stop_before_issuance_is_permanent(enrolled):
    assert enrolled.stop()["authority_issued"] is False
    with pytest.raises(probe.ProbeError):
        enrolled.issue(receipt())
    assert not real.CANONICAL.exists() and not real.ISSUED.exists()


def test_issue_crash_before_journal_never_reissues(enrolled, monkeypatch):
    def crash(*args):
        raise OSError("simulated torn creation")

    monkeypatch.setattr(probe.Journal, "prepare", crash)
    with pytest.raises(OSError):
        enrolled.issue(receipt())
    assert json.loads(real.ENROLLMENT.read_text()) == {"state": "consumed"}
    with pytest.raises(probe.ProbeError):
        enrolled.issue(receipt())
    assert not real.CANONICAL.exists()


def test_concurrent_execution_admits_one(authority):
    ctx = multiprocessing.get_context("fork")
    parent, child = ctx.Pipe()

    def start():
        try:
            result, stages = run(authority)
            child.send((result["outcome"], len(stages)))
        except probe.ProbeError:
            child.send(("refused", 0))

    children = [ctx.Process(target=start) for _ in range(2)]
    for process in children:
        process.start()
    assert parent.poll(4)
    results = [parent.recv()]
    assert parent.poll(4)
    results.append(parent.recv())
    for process in children:
        process.join(2)
        assert process.exitcode == 0
    assert sorted(results) == [("ok", 2), ("refused", 0)]
    child.close()
    parent.close()


def test_oversized_compressed_wire_even_without_output():
    # A gzip header with a long bounded optional name yields no decoded data.
    raw = (
        b"\x1f\x8b\x08\x08" + b"\0" * 6 + b"a" * (probe.AUTHORIZATION_RESPONSE_LIMIT_BYTES + real.WIRE_EXTRA)
    )
    response = httpx.Response(200, headers={"content-encoding": "gzip"}, stream=Stream(raw))
    with pytest.raises(probe.BodyError, match="body_limit"):
        probe.bounded_json(
            real.StreamedResponse(response, probe.AUTHORIZATION_RESPONSE_LIMIT_BYTES),
            probe.AUTHORIZATION_RESPONSE_LIMIT_BYTES,
        )


def test_private_input_timeout_cannot_send():
    sends = []

    def slow():
        time.sleep(0.02)
        return PAIR

    transport = real.RealTransport(
        transport=httpx.MockTransport(lambda request: sends.append(request)),
        credential_reader=slow,
    )
    try:
        with pytest.raises(TimeoutError):
            transport.dispatch(
                probe.request_for("oauth", real.ENV, 0.001), credentials=probe.DUMMY, token=None
            )
        assert sends == []
    finally:
        transport.close()


@pytest.mark.parametrize("raw", [b"\xff", '{"total":0}'.encode("utf-16"), b'{"x":1e999}'])
def test_json_encoding_and_nonfinite_overflow(authority, raw):
    result, _ = run(authority, bodies={"browse": raw})
    assert result["outcome"] == "malformed_json"
    assert result["http_status"] == 200


def test_transport_exception_sanitized_no_retry(authority):
    audit = authority.path.parent / "transport-error-audit"

    def handler(request):
        audit.write_text("oauth")
        raise httpx.ConnectError(SECRET + TOKEN + BODY)

    result = probe.execute(
        authority.path,
        real.RUN_ID,
        real.ENV,
        journal_type=real.RealJournal,
        transport_factory=lambda: real.RealTransport(
            transport=httpx.MockTransport(handler),
            credential_reader=lambda: PAIR,
        ),
    )
    assert result["outcome"] == "transport_error" and result["consumed_operations"] == 1
    canaries_absent(authority.path.parent)


@pytest.mark.parametrize("interrupt", [None, signal.SIGTERM, signal.SIGALRM])
def test_hidden_tty_input_and_signal_restore(interrupt):
    import pty
    import select
    import subprocess
    import sys
    import termios

    master, slave = pty.openpty()
    code = """
import fcntl,os,sys,termios
fcntl.ioctl(0, termios.TIOCSCTTY, 0)
sys.path.insert(0,sys.argv[1])
from pokemon_hunter import ebay_probe_real as real
original=real.termios.tcsetattr
def record_restore(fd, when, attrs):
 original(fd, when, attrs)
 if attrs[3] & termios.ECHO:
  os.write(1,b'ECHO_RESTORED\\n')
real.termios.tcsetattr=record_restore
pair=real.hidden_credentials()
assert pair == ('CANARY_CLIENT_SHOP01D','CANARY_SECRET_SHOP01D')
os.write(1,b'PRIVATE_INPUT_OK\\n')
"""
    process = subprocess.Popen(
        [sys.executable, "-I", "-c", code, str(Path(real.__file__).parents[1])],
        stdin=slave,
        stdout=slave,
        stderr=slave,
        start_new_session=True,
    )
    output = bytearray()

    def read_prompt(marker):
        deadline = time.monotonic() + 3
        while marker not in output:
            assert time.monotonic() < deadline
            if select.select([master], [], [], 0.1)[0]:
                output.extend(os.read(master, 4096))

    try:
        read_prompt(b"App ID (hidden): ")
        assert not termios.tcgetattr(slave)[3] & termios.ECHO
        if interrupt is not None:
            process.send_signal(interrupt)
        else:
            os.write(master, (CLIENT + "\n").encode())
            read_prompt(b"Cert ID (hidden): ")
            os.write(master, (SECRET + "\n").encode())
            read_prompt(b"PRIVATE_INPUT_OK")
        read_prompt(b"ECHO_RESTORED")
        if interrupt is not None:
            # macOS can defer a PTY session leader exit until master hangup.
            os.close(master)
            os.close(slave)
            master = slave = None
        deadline = time.monotonic() + 2
        while process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert process.poll() in ({0} if interrupt is None else {-interrupt, -signal.SIGHUP})
        assert CLIENT.encode() not in output and SECRET.encode() not in output
    finally:
        if master is not None:
            os.close(master)
            os.close(slave)
        if process.poll() is None:
            process.kill()
        process.wait(timeout=2)


def test_worker_logging_does_not_write_to_inherited_handler(authority):
    import logging

    log = authority.path.parent / "inherited-log"
    logger = logging.getLogger("shop01d-private-test")
    handler = logging.FileHandler(log)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

    def parser(body):
        # Prove the entire inherited logging path is disabled without routing
        # even synthetic credentials to a logger.
        assert not logger.isEnabledFor(logging.CRITICAL)
        logger.critical("worker logging suppression check")
        return probe.decode_json(body)

    try:
        result, _ = run(authority, parser=parser)
        assert result["outcome"] == "ok" and log.read_bytes() == b""
    finally:
        logger.removeHandler(handler)
        handler.close()


def test_binding_cli_never_reads_credentials_or_issues_authority(monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        raise AssertionError("binding read credentials or accessed private authority")

    monkeypatch.setattr(real, "RealJournal", forbidden)
    monkeypatch.setattr(real, "hidden_credentials", forbidden)
    monkeypatch.setattr(real, "check_private_context", forbidden)

    assert real.main(["binding"]) == 0
    output = capsys.readouterr()
    binding = json.loads(output.out)
    assert binding == real.ENV.binding()
    assert binding["oauth_url"] == "https://api.ebay.com/identity/v1/oauth2/token"
    assert binding["oauth_bytes"] == 65536
    assert output.err == ""
    assert all(value not in output.out for value in (SECRET, CLIENT, TOKEN, BODY))


def test_owned_cleanup_never_uses_blocking_join():
    class Process:
        terminated = killed = False

        def is_alive(self):
            return True

        def terminate(self):
            self.terminated = True

        def kill(self):
            self.killed = True

        def join(self, seconds):
            raise AssertionError("blocking join used")

    process = Process()
    before = time.monotonic()
    assert probe._reap(process) is False
    assert process.terminated and process.killed and time.monotonic() - before < 1


def test_guardian_private_input_timeout_restores_echo(authority):
    import pty
    import select
    import subprocess
    import sys

    master, slave = pty.openpty()
    code = """
import fcntl,os,sys,termios
from pathlib import Path
fcntl.ioctl(0, termios.TIOCSCTTY, 0)
sys.path.insert(0,sys.argv[1])
import httpx
from pokemon_hunter import ebay_probe as probe,ebay_probe_real as real
real.PRIVATE=Path(sys.argv[2])
real.CANONICAL=real.PRIVATE/real.RUN_ID
real.ENROLLMENT=real.PRIVATE/(real.RUN_ID+'.enrollment.json')
real.ISSUED=real.PRIVATE/(real.RUN_ID+'.issued')
real.STOP=real.PRIVATE/(real.RUN_ID+'.stop')
result=probe.execute(real.CANONICAL,real.RUN_ID,real.ENV,journal_type=real.RealJournal,
 transport_factory=lambda:real.RealTransport(transport=httpx.MockTransport(lambda request:None)),
 request_seconds=.15,overall_seconds=1)
assert result['outcome']=='timeout' and result['cleanup_reaped'] and result['consumed_operations']==1
assert termios.tcgetattr(0)[3] & termios.ECHO
os.write(1,b'GUARDIAN_CLEANUP_OK\\n')
"""
    process = subprocess.Popen(
        [sys.executable, "-I", "-c", code, str(Path(real.__file__).parents[1]), str(authority.path.parent)],
        stdin=slave,
        stdout=slave,
        stderr=slave,
        start_new_session=True,
    )
    output = bytearray()
    try:
        deadline = time.monotonic() + 3
        while b"GUARDIAN_CLEANUP_OK" not in output and time.monotonic() < deadline:
            if select.select([master], [], [], 0.1)[0]:
                output.extend(os.read(master, 4096))
        assert b"GUARDIAN_CLEANUP_OK" in output
        deadline = time.monotonic() + 2
        while process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert process.poll() == 0
    finally:
        os.close(master)
        os.close(slave)
        if process.poll() is None:
            process.kill()
        process.wait(timeout=2)
    assert authority.status()["consumed_operations"] == 1


def test_private_context_required_before_issuance(enrolled, monkeypatch):
    def no_tty(*args):
        raise OSError("no private terminal")

    monkeypatch.setattr(real.os, "open", no_tty)
    with pytest.raises(OSError):
        real.check_private_context()
    assert not real.CANONICAL.exists()
