"""Local wire fixtures and real isolated workers; external transport is prohibited."""

import gzip
import hashlib
import http.client
import io
import json
import multiprocessing
import socket
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from pokemon_hunter import metadata_collector as collector


def envelope(count=2):
    return dict(
        totalItems=count,
        success=True,
        errors=[],
        results=[
            dict(
                groupId=1000000 + i,
                name=("Base Set" if i == 0 else "Jungle" if i == 1 else f"Synthetic {i}"),
                abbreviation="SYN",
                isSupplemental=False,
                publishedOn="2000-01-01T00:00:00",
                modifiedOn="2000-01-02T00:00:00",
                categoryId=3,
            )
            for i in range(count)
        ],
    )


def fixture_worker(store, pipe, seconds):
    """Production transport/decoder/parser with an in-memory HTTP socket only."""
    store = Path(store)
    fixture = json.loads((store.parent / "fixture.json").read_text())

    def prohibited(*args, **kwargs):
        raise AssertionError("External sockets and DNS forbidden by fixture worker")

    socket.socket = socket.getaddrinfo = prohibited

    def mark(phase):
        (store.parent / "phase.json").write_text(json.dumps({"phase": phase}))
        if fixture.get("stall") == phase:
            time.sleep(60)

    class FakeSocket:
        def makefile(self, *args, **kwargs):
            return io.BytesIO(wire)

    value = fixture.get("value", envelope())
    body = json.dumps(value, separators=(",", ":")).encode()
    if "body" in fixture:
        body = fixture["body"].encode()
    if fixture.get("gzip"):
        body = gzip.compress(body)
    status = fixture.get("status", 200)
    headers = fixture.get("headers", {"Content-Type": "application/json"})
    if fixture.get("gzip"):
        headers["Content-Encoding"] = "gzip"
    if not fixture.get("unframed"):
        headers["Content-Length"] = str(fixture.get("declared_length", len(body)))
    if fixture.get("truncated"):
        body = body[:-5]
    if fixture.get("partial_gzip"):
        body = body[:-5]
        headers["Content-Length"] = str(len(body))
    wire = (
        f"HTTP/1.1 {status} Synthetic\r\n" + "".join(f"{k}: {v}\r\n" for k, v in headers.items()) + "\r\n"
    ).encode() + body

    class Connection:
        def __init__(self, host, timeout):
            assert host == "tcgcsv.com" and 0 < timeout <= 30
            mark("dns")

        def request(self, method, path, headers):
            assert method == "GET" and path == "/tcgplayer/3/groups"
            assert headers == {
                "User-Agent": collector.REQUEST["user_agent"],
                "Accept": "application/json",
                "Accept-Encoding": "identity",
            }
            (store.parent / "requests.json").write_text(json.dumps({"count": 1, "no_credentials": True}))
            if fixture.get("exception"):
                raise RuntimeError("SECRET_PROVIDER_BODY_AND_KEY")
            mark("connect")

        def getresponse(self):
            mark("headers")
            response = http.client.HTTPResponse(FakeSocket())
            response.begin()
            original = response.read1

            def read(amount):
                mark("read")
                return original(amount)

            response.read1 = read
            return response

        def close(self):
            pass

    collector.worker(store, pipe, seconds, connection_factory=Connection)


@pytest.fixture
def case(tmp_path):
    manifest = tmp_path / "manifest.json"
    # Test-only contract with the fixed request/limits; no private approval file
    # is shipped or read, and fixture_worker prohibits all external transport.
    manifest.write_text(
        json.dumps(
            {
                "schema": "dex-metadata-proposal-v1",
                "source": "TCGCSV",
                "request_type": "Pokemon group metadata only",
                "dispatch_enabled": False,
                "evidence_class": "synthetic offline test manifest",
                "requests": [
                    {
                        "method": "GET",
                        "url": "https://tcgcsv.com/tcgplayer/3/groups",
                        "evidence_locator": "https://tcgcsv.com/docs, Pokemon categoryId=3 and documented groups route",
                        "credentials": "none",
                        "user_agent": "DexPrivateMetadataReview/1.0 (bounded personal local review)",
                        "accept": "application/json",
                        "accept_encoding": "identity",
                    }
                ],
                "ceilings": {
                    "attempts": 1,
                    "files": 1,
                    "rows": 500,
                    "encoded_bytes": 1048576,
                    "decoded_bytes": 1048576,
                    "wall_seconds": 30,
                    "redirects": 0,
                    "retries": 0,
                    "paging": 0,
                    "product_files": 0,
                    "price_files": 0,
                    "price_endpoint_requests": 0,
                    "price_cells": 0,
                    "spending_usd": 0,
                },
            }
        )
    )
    return dict(
        root=tmp_path,
        store=tmp_path / "request",
        ledger=tmp_path / "control" / "attempts.json",
        manifest=manifest,
        sha=hashlib.sha256(manifest.read_bytes()).hexdigest(),
    )


def run(case, fixture=None, *, seconds=5):
    (case["root"] / "fixture.json").write_text(json.dumps(fixture or {}))
    return collector.collect(
        case["store"],
        case["ledger"],
        case["manifest"],
        case["sha"],
        _worker=fixture_worker,
        _wall_seconds=seconds,
    )


def assert_no_body(case):
    assert not (case["store"] / "groups.json").exists()
    assert not (case["store"] / "groups.pending.json").exists()
    assert not list(case["store"].glob("body-*.tmp"))
    assert not multiprocessing.active_children()


def test_complete_private_single_file_no_retry_and_unchanged_manifest(case):
    before = case["manifest"].read_bytes()
    result = run(case)
    assert result["status"] == "complete" and result["rows"] == 2
    assert result["encoded_bytes"] == result["decoded_bytes"] <= 1048576
    assert json.loads((case["store"] / "groups.json").read_text()) == envelope()
    assert case["store"].stat().st_mode & 0o077 == 0
    assert (case["store"] / "groups.json").stat().st_mode & 0o077 == 0
    assert case["ledger"].stat().st_mode & 0o077 == 0
    assert case["manifest"].read_bytes() == before
    assert json.loads((case["root"] / "requests.json").read_text()) == {"count": 1, "no_credentials": True}
    with pytest.raises(collector.Rejected):
        run(case)
    case["store"] = case["root"] / "another-store"
    with pytest.raises(collector.Rejected, match="attempt_already_consumed"):
        run(case)


def test_gzip_is_bounded_and_not_preserved_as_second_copy(case):
    result = run(case, {"gzip": True})
    assert result["status"] == "complete"
    assert result["encoded_bytes"] < result["decoded_bytes"]
    assert [p.name for p in case["store"].iterdir()] == ["groups.json"]


def test_inclusive_file_and_row_boundaries(case):
    body = json.dumps(envelope(500))
    body += " " * (1048576 - len(body.encode()))
    result = run(case, {"body": body})
    assert result["status"] == "complete" and result["rows"] == 500
    assert result["encoded_bytes"] == result["decoded_bytes"] == 1048576
    assert (case["store"] / "groups.json").stat().st_size < 1048576


def test_unicode_metadata_serialization_stays_within_file_byte_limit(case):
    value = envelope(500)
    for row in value["results"]:
        row["name"] = "🦋" * 256
        row["abbreviation"] = "🦋" * 64
    result = run(case, {"body": json.dumps(value, ensure_ascii=False)})
    assert result["status"] == "complete"
    assert (case["store"] / "groups.json").stat().st_size <= 1048576
    assert json.loads((case["store"] / "groups.json").read_text()) == value


def test_price_payload_is_removed_and_failure_summary_never_contains_price(case):
    value = envelope()
    value["results"][0]["marketPrice"] = "98765.4321"
    result = run(case, {"value": value})
    assert result["status"] == "failed" and result["reason"] == "group_fields"
    assert "98765" not in str(result) + case["ledger"].read_text()
    assert_no_body(case)


@pytest.mark.parametrize(
    "fixture,reason",
    [
        ({"declared_length": 1048577}, "encoded_limit"),
        ({"body": "A" * 1048580, "unframed": True}, "encoded_limit"),
        ({"body": "A" * 1048577, "gzip": True}, "decoded_limit"),
        ({"gzip": True, "truncated": True}, "partial_body"),
        ({"gzip": True, "partial_gzip": True}, "partial_gzip"),
        ({"truncated": True}, "partial_body"),
        ({"body": '{"success":true'}, "invalid_json"),
        ({"value": envelope(501)}, "row_limit"),
        (
            {
                "status": 302,
                "headers": {"Content-Type": "application/json", "Location": "https://evil.test/prices"},
            },
            "http_status",
        ),
        ({"status": 500, "body": "SECRET_PROVIDER_ERROR"}, "http_status"),
        ({"headers": {"Content-Type": "text/html"}, "body": "SECRET_PRICE_PAGE"}, "http_content_type"),
        ({"headers": {"Content-Type": "application/json", "Content-Encoding": "br"}}, "http_encoding"),
        ({"exception": True}, "transport_or_parse_failure"),
    ],
)
def test_failed_transport_parse_limits_consume_attempt_and_remove_all_content(case, fixture, reason, capsys):
    result = run(case, fixture)
    assert result == {"status": "failed", "reason": reason, "attempted_requests": 1, "price_requests": 0}
    assert_no_body(case)
    journal = case["ledger"].read_text()
    assert json.loads(journal)["attempts"][0]["status"] == "failed"
    assert "SECRET" not in journal + str(result) + capsys.readouterr().out
    case["store"] = case["root"] / "reopened"
    with pytest.raises(collector.Rejected, match="attempt_already_consumed"):
        run(case)


@pytest.mark.parametrize(
    "mutation",
    [
        "price_field",
        "product",
        "nested_price",
        "wrong_category",
        "boolean_id",
        "duplicate_id",
        "partial",
        "unknown_envelope",
        "duplicate_json",
        "nan",
    ],
)
def test_group_allowlist_rejects_price_product_and_ambiguous_payloads(mutation):
    value = envelope()
    if mutation == "price_field":
        value["results"][0]["marketPrice"] = "123.45"
    elif mutation == "product":
        value["results"][0]["productId"] = 11
    elif mutation == "nested_price":
        value["results"][0]["name"] = {"marketPrice": "123.45"}
    elif mutation == "wrong_category":
        value["results"][0]["categoryId"] = 1
    elif mutation == "boolean_id":
        value["results"][0]["groupId"] = True
    elif mutation == "duplicate_id":
        value["results"][1]["groupId"] = value["results"][0]["groupId"]
    elif mutation == "partial":
        value["totalItems"] = 3
    elif mutation == "unknown_envelope":
        value["prices"] = []
    body = json.dumps(value).encode()
    if mutation == "duplicate_json":
        body = b'{"totalItems":2,"totalItems":1}'
    elif mutation == "nan":
        body = b'{"totalItems":NaN}'
    with pytest.raises(collector.Rejected):
        collector.groups(body)


@pytest.mark.parametrize("phase", ["dns", "connect", "headers", "read"])
def test_wall_deadline_interrupts_stalled_request_at_every_phase(case, phase):
    started = time.monotonic()
    result = run(case, {"stall": phase}, seconds=1)
    assert result["status"] == "timeout"
    assert time.monotonic() - started < 2.5
    assert_no_body(case)
    assert collector.journal(case["ledger"])["attempts"][0]["status"] == "timeout"


@pytest.mark.parametrize("phase", ["headers", "read"])
def test_independent_stop_closes_worker_and_consumes_attempt(case, phase):
    result = []
    thread = threading.Thread(target=lambda: result.append(run(case, {"stall": phase}, seconds=8)))
    thread.start()
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        marker = case["root"] / "phase.json"
        try:
            if marker.exists() and json.loads(marker.read_text())["phase"] == phase:
                break
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        time.sleep(0.01)
    else:
        pytest.fail("Fixture did not reach requested transport phase")
    stopped = time.monotonic()
    stop_client = multiprocessing.get_context("spawn").Process(
        target=collector.stop, args=(case["store"], case["ledger"])
    )
    stop_client.start()
    stop_client.join(timeout=2)
    assert stop_client.exitcode == 0
    thread.join(timeout=2)
    assert not thread.is_alive() and time.monotonic() - stopped < 2
    assert result[0]["status"] == "stopped"
    assert_no_body(case)
    assert collector.journal(case["ledger"])["attempts"][0]["status"] == "stopped"


def test_stop_between_durable_reservation_and_dispatch(case, monkeypatch):
    original = collector.reserve

    def stop_after_reserve(ledger, digest, now):
        original(ledger, digest, now)
        collector.stop(case["store"], ledger)

    monkeypatch.setattr(collector, "reserve", stop_after_reserve)
    assert run(case)["status"] == "stopped"
    assert not (case["root"] / "requests.json").exists()
    assert_no_body(case)


def test_preflight_time_cannot_dispatch_after_the_wall_deadline(case, monkeypatch):
    original = collector.reserve

    def delayed_reserve(ledger, digest, now):
        original(ledger, digest, now)
        time.sleep(0.05)

    monkeypatch.setattr(collector, "reserve", delayed_reserve)
    assert run(case, seconds=0.02)["status"] == "timeout"
    assert not (case["root"] / "requests.json").exists()
    assert_no_body(case)


def test_consumed_reservation_survives_crash_reopening_and_clock_rollback(case):
    collector.location(case["store"], case["ledger"])
    now = datetime.now(timezone.utc)
    collector.reserve(case["ledger"], case["sha"], now)
    assert collector.journal(case["ledger"])["attempts"][0]["status"] == "consumed"
    with pytest.raises(collector.Rejected, match="attempt_already_consumed"):
        run(case)
    value = collector.journal(case["ledger"])
    value["attempts"][0]["plan"] = "other-tcgcsv-sync"
    collector.atomic(case["ledger"], value)
    for timestamp in (now - timedelta(seconds=1), now + timedelta(hours=23, minutes=59)):
        with pytest.raises(collector.Rejected, match="publisher_24h_reservation"):
            collector.reserve(case["ledger"], case["sha"], timestamp)
    collector.reserve(case["ledger"], case["sha"], now + timedelta(hours=24))


@pytest.mark.parametrize("mutation", ["url", "headers", "ceiling", "approval", "dispatch"])
def test_fixed_manifest_and_execution_digest_gate_before_transport(case, mutation):
    value = json.loads(case["manifest"].read_text())
    if mutation == "url":
        value["requests"][0]["url"] = "https://tcgcsv.com/tcgplayer/3/1/prices"
    elif mutation == "headers":
        value["requests"][0]["credentials"] = "api-key"
    elif mutation == "ceiling":
        value["ceilings"]["attempts"] = 2
    elif mutation == "dispatch":
        value["dispatch_enabled"] = True
    else:
        case["sha"] = "0" * 64
    if mutation != "approval":
        case["manifest"].write_text(json.dumps(value))
        case["sha"] = hashlib.sha256(case["manifest"].read_bytes()).hexdigest()
    with pytest.raises(collector.Rejected):
        run(case)
    assert not case["ledger"].exists()
    assert not (case["root"] / "requests.json").exists()


def test_private_path_and_no_installation_repository_side_effects(case, monkeypatch):
    monkeypatch.setattr(collector, "OWNER_ROOT", case["root"] / "owner")
    with pytest.raises(collector.Rejected, match="outside_installation"):
        collector.location(case["root"] / "owner" / "anything", case["ledger"])
    repository = case["root"] / "repository"
    (repository / ".git").mkdir(parents=True)
    with pytest.raises(collector.Rejected, match="outside_installation"):
        collector.location(repository / "evidence" / "bad", case["ledger"])
    assert not (repository / "evidence").exists()
    linked = case["root"] / "linked"
    linked.symlink_to(case["root"])
    with pytest.raises(collector.Rejected, match="linked_path"):
        collector.location(linked / "request", case["ledger"])


def test_publication_failure_and_stop_publication_race_do_not_leave_content(case, monkeypatch):
    original = collector.os.replace

    def stopped_publication(source, destination):
        if str(source).endswith("groups.pending.json"):
            collector.stop(case["store"], case["ledger"])
        original(source, destination)

    monkeypatch.setattr(collector.os, "replace", stopped_publication)
    assert run(case)["status"] == "stopped"
    assert_no_body(case)


def test_cli_cannot_select_a_second_cadence_journal(case, monkeypatch, capsys):
    seen = []
    monkeypatch.setattr(
        collector,
        "collect",
        lambda store, ledger, manifest, approved: seen.append(ledger) or {"status": "complete"},
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "metadata",
            "--store",
            str(case["store"]),
            "collect",
            "--manifest",
            str(case["manifest"]),
            "--approved-manifest-sha256",
            case["sha"],
        ],
    )
    assert collector.main() == 0
    assert seen == [collector.LEDGER]
    assert json.loads(capsys.readouterr().out)["status"] == "complete"
