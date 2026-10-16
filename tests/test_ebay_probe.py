"""Exercise the real offline operator, subprocess Stop, durable failure and cleanup.

Run under OS networking denial in addition to pytest-socket. No owner state or
real credentials are used. Local audit files contain stage names only.
"""

import dataclasses
import json
import multiprocessing
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from pokemon_hunter import ebay_probe as probe

ENV = probe.Envelope("EBAY_US", "US")
TOKEN = "CANARY_TOKEN_SHOP01C"
BODY = "CANARY_BODY_SHOP01C"
SECRET = "CANARY_CREDENTIAL_SHOP01C"
OAUTH_BODY = json.dumps({"access_token": TOKEN, "expires_in": 300, "token_type": "Bearer"}).encode()
SEARCH_BODY = json.dumps(
    {"itemSummaries": [{"itemId": "fake-id", "title": BODY}], "next": "https://untrusted.invalid/continue"}
).encode()


class Response(probe.FixtureResponse):
    def __init__(self, body, status_code=200, *, stall=False):
        super().__init__(body, status_code)
        self.stall = stall

    def iter_decoded(self, chunk_size):
        if self.stall:
            time.sleep(10)
        yield from super().iter_decoded(chunk_size)


class Fake:
    def __init__(
        self,
        audit,
        *,
        oauth=OAUTH_BODY,
        browse=SEARCH_BODY,
        oauth_code=200,
        browse_code=200,
        stall=None,
        crash=None,
        stop=None,
        close_stalls=False,
    ):
        self.audit = audit
        self.oauth, self.browse = oauth, browse
        self.oauth_code, self.browse_code = oauth_code, browse_code
        self.stall, self.crash, self.stop = stall, crash, stop
        self.close_stalls = close_stalls

    def dispatch(self, request, *, credentials, token):
        probe.validate_request(request, ENV)
        assert request.timeout <= 30
        if request.stage == "oauth":
            assert credentials == probe.DUMMY and token is None
        else:
            assert credentials is None and token == TOKEN
            assert request.headers == (("X-EBAY-C-MARKETPLACE-ID", "EBAY_US"),)
            assert dict(request.params) == {
                "q": probe.QUERY,
                "filter": "buyingOptions:{FIXED_PRICE},deliveryCountry:US",
                "limit": "5",
                "offset": "0",
                "fieldgroups": "EXTENDED",
            }
        with open(self.audit, "a") as stream:
            stream.write(request.stage + "\n")
        if self.crash == request.stage:
            os._exit(73)
        if self.stop == request.stage:
            probe.Journal(Path(self.audit).parent / "authority").stop()
        if self.stall == request.stage:
            # Ignore SIGTERM to exercise escalation; no saved PID can target us.
            signal.signal(signal.SIGTERM, signal.SIG_IGN)
            time.sleep(10)
        return Response(
            getattr(self, request.stage),
            getattr(self, request.stage + "_code"),
            stall=self.stall == request.stage + "-body",
        )

    def close(self):
        if self.close_stalls:
            time.sleep(10)


@pytest.fixture
def authority(tmp_path):
    directory = tmp_path / "authority"
    journal = probe.Journal(directory)
    journal.prepare("selected-run", ENV)
    return journal


def run(authority, tmp_path, **kwargs):
    fake_args = kwargs.pop("fake_args", {})
    result = probe.execute(
        authority.path,
        "selected-run",
        ENV,
        transport_factory=lambda: Fake(tmp_path / "audit", **fake_args),
        request_seconds=kwargs.pop("request_seconds", 1),
        overall_seconds=kwargs.pop("overall_seconds", 2),
        **kwargs,
    )
    assert result["cleanup_reaped"] is True
    assert result["real_provider_requests"] == 0
    assert not multiprocessing.active_children()
    return result


def stages(tmp_path):
    audit = tmp_path / "audit"
    return audit.read_text().splitlines() if audit.exists() else []


def cli(directory, *args, check=False):
    return subprocess.run(
        [sys.executable, "-m", "pokemon_hunter.ebay_probe", "--state-dir", str(directory), *args],
        capture_output=True,
        text=True,
        timeout=5,
        check=check,
    )


def start_cli(directory, scenario="stall-oauth"):
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "pokemon_hunter.ebay_probe",
            "--state-dir",
            str(directory),
            "execute",
            "--run-id",
            "selected-run",
            "--fixture",
            scenario,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def wait_until(test, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if test():
            return
        time.sleep(0.01)
    raise AssertionError("bounded condition did not arrive")


def assert_noncontent(directory):
    for path in directory.rglob("*"):
        if path.is_file():
            content = path.read_bytes()
            for canary in (TOKEN, BODY, SECRET, *probe.DUMMY):
                assert canary.encode() not in content, str(path)


def test_success_fixed_envelope_no_pagination(authority, tmp_path):
    result = run(authority, tmp_path)
    assert result["outcome"] == "ok" and result["count"] == 1
    assert result["attempts"] == ["oauth", "browse"]
    assert stages(tmp_path) == ["oauth", "browse"]
    assert_noncontent(tmp_path)
    with pytest.raises(probe.ProbeError):
        probe.execute(authority.path, "replacement", ENV, transport_factory=probe.FixtureTransport)


@pytest.mark.parametrize("body", [b'{"itemSummaries":[]}', b'{"total":0}'])
def test_empty_no_retry(authority, tmp_path, body):
    result = run(authority, tmp_path, fake_args={"browse": body})
    assert result["outcome"] == "empty" and result["count"] == 0
    assert stages(tmp_path) == ["oauth", "browse"]


@pytest.mark.parametrize(
    "stage,code",
    [
        (stage, code)
        for stage in ("oauth", "browse")
        for code in (301, 302, 307, 308, 400, 401, 403, 429, 500, 503)
    ],
)
def test_http_and_redirect_no_retry(authority, tmp_path, stage, code):
    result = run(authority, tmp_path, fake_args={stage + "_code": code, stage: BODY.encode()})
    assert result["outcome"] == ("redirect" if code < 400 else "http_error")
    assert result["http_status"] == code
    assert stages(tmp_path) == (["oauth"] if stage == "oauth" else ["oauth", "browse"])
    assert_noncontent(tmp_path)


@pytest.mark.parametrize("stage", ["oauth", "browse"])
@pytest.mark.parametrize(
    "body,expected",
    [
        (b"not-json", "malformed_json"),
        (b"[1,2]", "invalid_schema"),
        (b'{"errors":[{}]}', "invalid_schema"),
        (b'{"x":NaN}', "malformed_json"),
        (b'{"x":1,"x":2}', "malformed_json"),
        (b'{"itemSummaries":{}}', "invalid_schema"),
    ],
)
def test_bad_responses(authority, tmp_path, stage, body, expected):
    result = run(authority, tmp_path, fake_args={stage: body})
    assert result["outcome"] == expected
    assert result["count"] is None
    assert len(stages(tmp_path)) == (1 if stage == "oauth" else 2)


@pytest.mark.parametrize(
    "body",
    [
        b'{"access_token":"x","expires_in":true}',
        b'{"access_token":" ","expires_in":10}',
        b'{"access_token":"x","expires_in":10,"token_type":2}',
        b'{"access_token":"x","expires_in":10,"token_type":"other"}',
        json.dumps({"access_token": "x" * 8193, "expires_in": 300}).encode(),
    ],
)
def test_oauth_schema(authority, tmp_path, body):
    assert run(authority, tmp_path, fake_args={"oauth": body})["outcome"] == "invalid_schema"
    assert stages(tmp_path) == ["oauth"]


@pytest.mark.parametrize("token_type", ["Application Access Token", "application access token"])
def test_ebay_application_token_label(authority, tmp_path, token_type):
    body = json.dumps({"access_token": TOKEN, "expires_in": 7200, "token_type": token_type}).encode()
    result = run(authority, tmp_path, fake_args={"oauth": body})
    assert result["outcome"] == "ok"
    assert stages(tmp_path) == ["oauth", "browse"]
    assert_noncontent(tmp_path)


@pytest.mark.parametrize(
    "body",
    [
        b'{"itemSummaries":[{}]}',
        b'{"itemSummaries":[1]}',
        json.dumps({"itemSummaries": [{"itemId": "fake"}] * 6}).encode(),
    ],
)
def test_browse_schema_and_excess(authority, tmp_path, body):
    assert run(authority, tmp_path, fake_args={"browse": body})["outcome"] == "invalid_schema"


@pytest.mark.parametrize(
    "stage,limit", [("oauth", probe.AUTHORIZATION_RESPONSE_LIMIT_BYTES), ("browse", probe.BODY_LIMIT)]
)
def test_decoded_body_limit_before_parser(authority, tmp_path, stage, limit):
    def parser(body):
        if len(body) > limit:
            raise AssertionError("oversize parsed")
        return probe.decode_json(body)

    result = run(authority, tmp_path, fake_args={stage: b" " * (limit + 1)}, parser=parser)
    assert result["outcome"] == "body_limit"
    assert_noncontent(tmp_path)


def test_body_stops_reading_before_unbounded_stream():
    class Endless:
        reads = 0

        def iter_decoded(self, chunk_size):
            while True:
                self.reads += 1
                yield b" " * chunk_size

    response = Endless()
    with pytest.raises(probe.BodyError, match="body_limit"):
        probe.bounded_json(response, probe.BODY_LIMIT)
    assert response.reads == probe.BODY_LIMIT // probe.CHUNK_LIMIT + 1


@pytest.mark.parametrize("stage", ["oauth", "browse", "oauth-body", "browse-body"])
def test_timeout_during_stage(authority, tmp_path, stage):
    before = time.monotonic()
    result = run(authority, tmp_path, fake_args={"stall": stage}, request_seconds=0.12)
    assert result["outcome"] == "timeout" and result["count"] is None
    assert time.monotonic() - before < 1.5
    assert stages(tmp_path) == (["oauth"] if stage.startswith("oauth") else ["oauth", "browse"])


def test_overall_timeout_stalled_factory(authority, tmp_path):
    def factory():
        time.sleep(10)

    result = probe.execute(
        authority.path, "selected-run", ENV, transport_factory=factory, request_seconds=1, overall_seconds=0.1
    )
    assert result["outcome"] == "timeout" and result["attempts"] == [] and result["cleanup_reaped"]


@pytest.mark.parametrize("stage", ["oauth", "browse"])
def test_parser_stall_independent_deadline(authority, tmp_path, stage):
    def parser(body):
        if (b"access_token" in body) == (stage == "oauth"):
            time.sleep(10)
        return probe.decode_json(body)

    result = run(authority, tmp_path, parser=parser, request_seconds=0.12)
    assert result["outcome"] == "timeout"
    assert len(result["attempts"]) == (1 if stage == "oauth" else 2)


def test_controlled_clock_prevents_dispatch(authority, tmp_path):
    class Clock:
        value = 0

        def __call__(self):
            self.value += 80
            return self.value

    result = run(authority, tmp_path, clock=Clock())
    assert result["outcome"] == "timeout" and stages(tmp_path) == []


def test_stop_before_dispatch_and_restart(authority, tmp_path):
    assert cli(authority.path, "stop").returncode == 0
    with pytest.raises(probe.ProbeError, match="authority_consumed"):
        run(authority, tmp_path)
    assert stages(tmp_path) == []
    assert (
        cli(
            authority.path, "prepare", "--run-id", "new-run", "--marketplace", "EBAY_US", "--country", "US"
        ).returncode
        == 2
    )
    assert authority.status()["attempts"] == []


def test_stop_between_stages(authority, tmp_path):
    result = run(authority, tmp_path, fake_args={"stop": "oauth"})
    assert result["outcome"] == "stopped" and result["count"] is None
    assert stages(tmp_path) == ["oauth"]


@pytest.mark.parametrize("stage", ["oauth", "browse"])
def test_independent_stop_while_busy(authority, stage):
    process = start_cli(authority.path, "stall-" + stage)
    try:
        wait_until(lambda: len(authority.status()["attempts"]) == (1 if stage == "oauth" else 2))
        before = time.monotonic()
        assert cli(authority.path, "stop").returncode == 0
        stdout, stderr = process.communicate(timeout=2)
        assert time.monotonic() - before < 2
        assert process.returncode == 0, stderr
        result = json.loads(stdout)
        assert result["outcome"] == "stopped" and result["count"] is None
        assert result["cleanup_reaped"] is True
        assert (
            cli(authority.path, "execute", "--run-id", "selected-run", "--fixture", "success").returncode == 2
        )
    finally:
        if process.poll() is None:
            cli(authority.path, "stop")
            process.communicate(timeout=2)


@pytest.mark.parametrize("stage", ["oauth", "browse"])
def test_crash_after_reserved_dispatch(authority, tmp_path, stage):
    result = run(authority, tmp_path, fake_args={"crash": stage})
    assert result["outcome"] in {"control_error", "worker_lost"}
    assert result["simulated_consumed"] == (1 if stage == "oauth" else 2)
    with pytest.raises(probe.ProbeError):
        run(authority, tmp_path)


def test_crash_between_reservation_and_dispatch(authority):
    script = "from pokemon_hunter.ebay_probe import *; import os,sys; j=Journal(sys.argv[1]); j.claim('selected-run',Envelope('EBAY_US','US')); j.reserve('oauth'); os._exit(77)"
    process = subprocess.run([sys.executable, "-c", script, str(authority.path)], timeout=3)
    assert process.returncode == 77
    assert authority.status()["attempts"] == ["oauth"]
    with pytest.raises(probe.ProbeError):
        probe.execute(authority.path, "selected-run", ENV, transport_factory=probe.FixtureTransport)


def test_supervisor_crash_guardian_cleans_worker(authority):
    process = start_cli(authority.path)
    wait_until(lambda: authority.status()["attempts"] == ["oauth"])
    process.kill()  # Our owned test process, never a PID read from a journal.
    process.wait(timeout=2)
    # Pipe EOF reaches the independent guardian even if the CLI dies. Its
    # inherited stdout pipe also closes once guardian/worker exit.
    stdout, stderr = process.communicate(timeout=2)
    wait_until(lambda: authority.status()["outcome"] == "abandoned")
    assert not stdout and not stderr
    assert authority.status()["attempts"] == ["oauth"]


def test_competing_processes_cannot_renew_budget(authority):
    first = start_cli(authority.path)
    try:
        wait_until(lambda: authority.status()["attempts"] == ["oauth"])
        other = start_cli(authority.path, "success")
        out, err = other.communicate(timeout=2)
        assert other.returncode == 2 and json.loads(out)["outcome"] == "refused" and not err
        assert authority.status()["attempts"] == ["oauth"]
    finally:
        cli(authority.path, "stop")
        first.communicate(timeout=2)


def test_third_attempt_rejected_durably(authority):
    authority.claim("selected-run", ENV)
    authority.reserve("oauth")
    authority.reserve("browse")
    for stage in ("oauth", "browse", "detail", "legacy-id", "seller", "sold-history"):
        with pytest.raises(probe.ProbeError, match="attempt_budget"):
            authority.reserve(stage)
    assert authority.status()["attempts"] == ["oauth", "browse"]


@pytest.mark.parametrize(
    "mutation", ["truncated", "unknown", "bad_budget", "bad_envelope", "missing", "bad_phase", "pid"]
)
def test_corrupt_or_ambiguous_journal_refuses(authority, mutation):
    path = authority.path / "authority.json"
    value = json.loads(path.read_text())
    if mutation == "truncated":
        path.write_text("{")
    elif mutation == "missing":
        path.unlink()
    else:
        if mutation == "unknown":
            value["unrecognized"] = True
        elif mutation == "bad_budget":
            value["attempts"] = ["browse"]
        elif mutation == "bad_envelope":
            value["envelope"]["limit"] = 10
        elif mutation == "bad_phase":
            value["phase"] = "complete"
        else:
            value["pid"] = os.getpid()  # Never interpreted as a signal target.
        path.write_text(json.dumps(value))
    assert cli(authority.path, "execute", "--run-id", "selected-run", "--fixture", "success").returncode == 2
    assert cli(authority.path, "status").returncode == 2
    assert cli(authority.path, "stop").returncode == 0
    assert (
        cli(
            authority.path, "prepare", "--run-id", "new", "--marketplace", "EBAY_US", "--country", "US"
        ).returncode
        == 2
    )
    assert os.getpid() > 0  # This test process remains alive; Stop never signals it.


def test_stale_pid_file_is_never_used(authority):
    (authority.path / "pid").write_text(str(os.getpid()))
    assert cli(authority.path, "stop").returncode == 0
    assert authority.status()["outcome"] == "stopped"


def test_missing_fake_or_destination_refuses_without_consumption(authority):
    with pytest.raises(probe.ProbeError, match="offline_transport_required"):
        probe.execute(authority.path, "selected-run", ENV)
    assert authority.status()["phase"] == "prepared"
    with pytest.raises(probe.ProbeError):
        probe.execute(
            authority.path,
            "selected-run",
            probe.Envelope("EBAY_GB", "GB"),
            transport_factory=probe.FixtureTransport,
        )
    assert authority.status()["phase"] == "prepared"
    assert cli(authority.path, "execute", "--run-id", "selected-run").returncode == 2
    assert cli(authority.path, "execute", "--run-id", "selected-run", "--fixture", "live").returncode == 2


@pytest.mark.parametrize(
    "change",
    [
        {"method": "DELETE"},
        {"url": "https://evil.invalid/"},
        {"stage": "detail"},
        {"params": (("limit", "6"),)},
        {"follow_redirects": True},
        {"timeout": 31},
        {"timeout": float("nan")},
    ],
)
def test_unexpected_request_rejected(change):
    with pytest.raises(probe.ProbeError):
        probe.validate_request(dataclasses.replace(probe.request_for("browse", ENV, 30), **change), ENV)


def test_cleanup_stalled_close(authority, tmp_path):
    before = time.monotonic()
    assert run(authority, tmp_path, fake_args={"close_stalls": True})["outcome"] == "ok"
    assert time.monotonic() - before < 1
    assert_noncontent(tmp_path)


def test_transport_exception_is_sanitized(authority, tmp_path):
    class Explodes:
        def dispatch(self, *args, **kwargs):
            raise RuntimeError(SECRET + TOKEN + BODY)

        def close(self):
            pass

    result = probe.execute(authority.path, "selected-run", ENV, transport_factory=Explodes)
    assert result["outcome"] == "transport_error" and result["cleanup_reaped"]
    assert_noncontent(tmp_path)


def test_network_missing_transport_cannot_fallback(authority):
    class NetworkAttempt:
        def dispatch(self, *args, **kwargs):
            import socket

            socket.create_connection(("192.0.2.1", 443), timeout=0.1)

        def close(self):
            pass

    result = probe.execute(authority.path, "selected-run", ENV, transport_factory=NetworkAttempt)
    assert result["outcome"] == "transport_error"
    assert result["attempts"] == ["oauth"]


def test_private_permissions_and_symlink_refusal(authority, tmp_path):
    for file in authority.path.iterdir():
        assert file.stat().st_mode & 0o077 == 0
    link = tmp_path / "symlink"
    link.symlink_to(authority.path, target_is_directory=True)
    assert cli(link, "status").returncode == 2
    (authority.path / "authority.json").chmod(0o644)
    assert cli(authority.path, "status").returncode == 2


@pytest.mark.parametrize("stage", ["oauth", "browse"])
def test_late_result_after_stop_cannot_publish(authority, tmp_path, stage):
    result = run(authority, tmp_path, fake_args={"stop": stage})
    assert result["outcome"] == "stopped" and result["count"] is None
    stored = json.loads((authority.path / "authority.json").read_text())
    assert stored["count"] is None and stored["outcome"] == "stopped"
    assert result["attempts"] == (["oauth"] if stage == "oauth" else ["oauth", "browse"])


@pytest.mark.parametrize("stage", ["oauth", "browse"])
def test_controlled_deadline_suppresses_queued_late_result(authority, tmp_path, stage):
    class Clock:
        def __call__(self):
            return 100 if stage in stages(tmp_path) else 0

    result = run(authority, tmp_path, clock=Clock())
    assert result["outcome"] == "timeout" and result["count"] is None
    assert result["attempts"] == (["oauth"] if stage == "oauth" else ["oauth", "browse"])


@pytest.mark.parametrize("stage", ["oauth", "browse"])
def test_explicit_transport_timeout_no_retry(authority, tmp_path, stage):
    class Timeouts(Fake):
        def dispatch(self, request, **kwargs):
            if request.stage == stage:
                with open(self.audit, "a") as stream:
                    stream.write(request.stage + "\n")
                raise probe.httpx.ReadTimeout(SECRET + BODY)
            return super().dispatch(request, **kwargs)

    result = probe.execute(
        authority.path, "selected-run", ENV, transport_factory=lambda: Timeouts(tmp_path / "audit")
    )
    assert result["outcome"] == "timeout" and result["cleanup_reaped"]
    assert stages(tmp_path) == (["oauth"] if stage == "oauth" else ["oauth", "browse"])
    assert_noncontent(tmp_path)


def test_worker_kernel_timer_without_guardian(authority, tmp_path):
    context = multiprocessing.get_context("fork")
    parent, child = context.Pipe()
    worker = context.Process(
        target=probe._worker,
        args=(
            child,
            (parent,),
            authority.path,
            ENV,
            lambda: Fake(tmp_path / "audit", stall="oauth"),
            probe.decode_json,
            0.1,
            time.monotonic() + 1,
        ),
    )
    worker.start()
    child.close()
    try:
        assert parent.poll(1)
        assert parent.recv() == ("reserve", "oauth")
        parent.send(("permit", time.monotonic() + 0.1))
        worker.join(1)
        assert worker.exitcode == -signal.SIGALRM
        assert stages(tmp_path) == ["oauth"]
    finally:
        if worker.is_alive():
            worker.kill()
            worker.join(1)
        parent.close()


def test_exact_body_bound_accepted_and_chunk_overflow_rejected():
    body = b'{"itemSummaries":[]}'
    assert probe.bounded_json(Response(body + b" " * (probe.BODY_LIMIT - len(body))), probe.BODY_LIMIT) == {
        "itemSummaries": []
    }

    class BadDecoder:
        def iter_decoded(self, chunk_size):
            yield b" " * (chunk_size + 1)

    with pytest.raises(probe.BodyError, match="body_limit"):
        probe.bounded_json(BadDecoder(), probe.BODY_LIMIT)


def test_parser_exception_canary_is_not_retained(authority, tmp_path):
    def parser(body):
        raise RuntimeError(SECRET + TOKEN + BODY)

    result = run(authority, tmp_path, parser=parser)
    assert result["outcome"] == "transport_error" and stages(tmp_path) == ["oauth"]
    assert_noncontent(tmp_path)


def test_independent_stop_does_not_signal_unrelated_process(authority):
    innocent = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"])
    try:
        (authority.path / "pid").write_text(str(innocent.pid))
        assert cli(authority.path, "stop").returncode == 0
        assert innocent.poll() is None
    finally:
        innocent.terminate()
        innocent.wait(timeout=2)


def test_claim_mismatch_leaves_selected_authority_unchanged(authority):
    with pytest.raises(probe.ProbeError, match="authority_mismatch"):
        authority.claim("replacement", ENV)
    assert authority.status()["phase"] == "prepared"


def test_ambiguous_initialization_missing_lock_not_recreated(authority):
    (authority.path / "lock").unlink()
    assert (
        cli(
            authority.path, "prepare", "--run-id", "new", "--marketplace", "EBAY_US", "--country", "US"
        ).returncode
        == 2
    )
    assert not (authority.path / "lock").exists()
    assert cli(authority.path, "stop").returncode == 0


@pytest.mark.parametrize("fault", ["missing-issued", "corrupt-issued", "duplicate-json", "empty-directory"])
def test_initialization_corruption_never_renews(authority, fault):
    if fault == "empty-directory":
        for path in authority.path.iterdir():
            path.unlink()
    elif fault == "missing-issued":
        (authority.path / "issued").unlink()
    elif fault == "corrupt-issued":
        (authority.path / "issued").write_text("unexpected")
    else:
        path = authority.path / "authority.json"
        path.write_text(
            path.read_text().replace('"phase": "prepared"', '"phase": "running", "phase": "prepared"')
        )
    assert cli(authority.path, "status").returncode == 2
    assert (
        cli(
            authority.path,
            "prepare",
            "--run-id",
            "replacement",
            "--marketplace",
            "EBAY_US",
            "--country",
            "US",
        ).returncode
        == 2
    )
    assert cli(authority.path, "stop").returncode == 0


def test_existing_unrelated_directory_is_not_modified(tmp_path):
    target = tmp_path / "not-a-journal"
    target.mkdir(mode=0o700)
    file = target / "protected"
    file.write_text("existing data")
    assert (
        cli(
            target, "prepare", "--run-id", "selected-run", "--marketplace", "EBAY_US", "--country", "US"
        ).returncode
        == 2
    )
    assert {path.name for path in target.iterdir()} == {"protected"}
    assert file.read_text() == "existing data"


def test_unconfirmed_cleanup_refuses_publication(authority, tmp_path, monkeypatch):
    original = probe._reap

    def unconfirmed(process):
        original(process)
        return False

    monkeypatch.setattr(probe, "_reap", unconfirmed)
    with pytest.raises(probe.ProbeError, match="cleanup_unconfirmed"):
        run(authority, tmp_path)
    status = authority.status()
    assert status["revoked"] and status["count"] is None and not status["authority_reusable"]
