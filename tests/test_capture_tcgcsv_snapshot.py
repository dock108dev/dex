"""Fixed historical pilot transport and durable consumption contracts."""

import json
from contextlib import contextmanager

import pytest
from tcgcsv_capture_helpers import BUILD, capture, envelope
from tcgcsv_capture_helpers import pilot as pilot


def test_exact_five_private_managed_capture_and_immutable_consumption(pilot):
    report = pilot["run"]()
    assert report["status"] == "captured"
    assert report["provider_operations"] == 5
    assert not report["activated"] and not report["imported"]
    assert [item[0] for item in pilot["calls"]] == [step[1] for step in capture.STEPS]
    assert all(b[1] - a[1] >= 0.25 for a, b in zip(pilot["calls"], pilot["calls"][1:]))
    managed = pilot["root"] / report["capture_directory"]
    assert len(list(managed.iterdir())) == 6
    assert all(path.stat().st_mode & 0o077 == 0 for path in managed.iterdir())
    journal = next((pilot["root"].parent / ".dex-tcgcsv-snapshots").rglob("*.jsonl"))
    events = [json.loads(line) for line in journal.read_text().splitlines()]
    assert sum(row["stage"] == "consumed" for row in events) == 5
    assert "marketPrice" not in journal.read_text()
    with pytest.raises(FileExistsError):
        pilot["run"]()
    assert len(pilot["calls"]) == 5


def test_naive_build_kept_without_inventing_timezone_or_admission(pilot):
    pilot["bodies"][0] = pilot["bodies"][4] = b"2026-10-17T12:30:00\n"
    report = pilot["run"]()
    assert report["status"] == "captured"
    assert report["publisher_built_at"] is None
    assert report["publisher_timezone_known"] is False
    assert report["activated"] is False


@pytest.mark.parametrize(
    "change,reason,operations",
    [
        ("group", "group_binding_conflict", 2),
        ("category", "group_binding_conflict", 2),
        ("build", "publisher_build_changed", 5),
        ("duplicate_key", "invalid_json", 2),
        ("errors", "invalid_envelope", 2),
        ("count", "inconsistent_row_count", 3),
        ("product", "product_binding_conflict", 3),
        ("duplicate_product", "duplicate_record_identity", 3),
        ("duplicate_price", "duplicate_record_identity", 4),
        ("subtype", "invalid_literal_subtype", 4),
        ("bad_build", "invalid_build_timestamp", 1),
    ],
)
def test_invalid_input_stops_without_retry_and_removes_managed_bodies(pilot, change, reason, operations):
    if change in {"group", "category"}:
        value = json.loads(pilot["bodies"][1])
        value["results"][0]["name" if change == "group" else "categoryId"] = (
            "Wrong" if change == "group" else 4
        )
        pilot["bodies"][1] = json.dumps(value).encode()
    elif change == "build":
        pilot["bodies"][4] = b"2026-10-17T13:30:00Z"
    elif change == "bad_build":
        pilot["bodies"][0] = b"not-a-build"
    elif change == "duplicate_key":
        pilot["bodies"][1] = b'{"success":true,"success":true,"errors":[],"results":[],"totalItems":0}'
    else:
        index = 3 if change in {"duplicate_price", "subtype"} else 2 if change != "errors" else 1
        value = json.loads(pilot["bodies"][index])
        if change == "errors":
            value["errors"] = ["synthetic failure"]
        elif change == "count":
            value["totalItems"] += 1
        elif change == "product":
            value["results"][0]["groupId"] = 9
        elif change == "subtype":
            value["results"][0]["subTypeName"] = ""
        else:
            value["results"].append(value["results"][0])
            if "totalItems" in value:
                value["totalItems"] += 1
        pilot["bodies"][index] = json.dumps(value).encode()
    report = pilot["run"]()
    assert report["reason"] == reason
    assert report["provider_operations"] == operations == len(pilot["calls"])
    assert list((pilot["root"] / "price-snapshots" / "staging" / "hunt11" / "capture-v1").iterdir()) == []
    with pytest.raises(FileExistsError):
        pilot["run"]()


@pytest.mark.parametrize("status", [301, 302, 429, 500])
def test_no_redirects_or_retries(pilot, status):
    pilot["statuses"][0] = status
    report = pilot["run"]()
    assert report["reason"] == "http_non_success"
    assert report["provider_operations"] == 1


@pytest.mark.parametrize(
    "header,value,reason",
    [
        ("content-type", "text/html", "media_mismatch"),
        ("content-length", "1025", "body_too_large"),
        ("content-length", "999", "truncated_body"),
        ("content-length", "no", "invalid_content_length"),
        ("content-encoding", "gzip", "unsupported_content_encoding"),
    ],
)
def test_response_boundary(pilot, header, value, reason):
    pilot["headers"][0] = {header: value}
    assert pilot["run"]()["reason"] == reason
    assert len(pilot["calls"]) == 1


def test_documented_text_json_media_accepted(pilot):
    for index in (1, 2, 3):
        pilot["headers"][index] = {"content-type": "text/json; charset=utf-8"}
    assert pilot["run"]()["status"] == "captured"


def test_streamed_oversized_body_consumed_once(pilot):
    pilot["bodies"][0] = b"x" * 1025
    pilot["headers"][0] = {"content-length": "1024"}
    assert pilot["run"]()["reason"] == "body_too_large"
    assert len(pilot["calls"]) == 1


def test_row_limit(pilot):
    pilot["bodies"][3] = envelope(
        [{"productId": n, "subTypeName": "Normal"} for n in range(1, 10002)], total=False
    )
    report = pilot["run"]()
    assert report["reason"] == "invalid_envelope"
    assert len(pilot["calls"]) == 4


def test_deadline_and_transport_uncertainty_are_consumed(pilot):
    @contextmanager
    def uncertain(url, *, timeout):
        raise TimeoutError("private transport details must be withheld")
        yield

    report = capture.capture(pilot["root"], open_response=uncertain)
    assert report["provider_operations"] == 1
    assert report["reason"] == "transport_or_storage_failure"
    assert "private" not in json.dumps(report)


def test_linked_managed_directory_rejected_before_send(pilot, tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir(mode=0o700)
    (pilot["root"] / "price-snapshots").symlink_to(elsewhere, target_is_directory=True)
    report = pilot["run"]()
    assert report["provider_operations"] == 0
    assert len(pilot["calls"]) == 0


def test_total_byte_ceiling_stops_without_more_calls(pilot, monkeypatch):
    monkeypatch.setattr(capture, "TOTAL_LIMIT", len(BUILD) + 4)
    report = pilot["run"]()
    assert report["reason"] == "body_too_large"
    assert len(pilot["calls"]) == 2


def test_storage_ceiling_stops_before_network(pilot, monkeypatch):
    monkeypatch.setattr(capture, "STAGING_LIMIT", 1)
    stage = pilot["root"] / "price-snapshots" / "staging"
    stage.mkdir(mode=0o700, parents=True)
    (stage / "existing.json").write_bytes(b"existing")
    report = pilot["run"]()
    assert report["reason"] == "staging_capacity_exhausted"
    assert len(pilot["calls"]) == 0
    assert (stage / "existing.json").read_bytes() == b"existing"


def test_request_deadline_stops_and_consumes_current_attempt(pilot):
    @contextmanager
    def slow(url, *, timeout):
        class Response:
            status = 200
            headers = {"content-type": "text/plain"}

            def read(self, size, remaining):
                pilot["clock"].seconds += 16
                return b""

        yield Response()

    report = capture.capture(
        pilot["root"], open_response=slow, clock=pilot["clock"], sleep=pilot["clock"].sleep
    )
    assert report["provider_operations"] == 1
    assert report["reason"] == "request_deadline_exhausted"
    assert report["http_statuses"] == [200]


def test_total_deadline_prevents_dispatch(pilot, monkeypatch):
    monkeypatch.setattr(capture, "TOTAL_SECONDS", 0.1)
    report = pilot["run"]()
    assert report["reason"] == "total_deadline_exhausted"
    assert report["provider_operations"] == 1
    assert len(pilot["calls"]) == 1


def test_non_success_status_retained_in_metadata_only_accounting(pilot):
    pilot["statuses"][0] = 429
    report = pilot["run"]()
    assert report["http_statuses"] == [429]
    journal = next((pilot["root"].parent / ".dex-tcgcsv-snapshots").rglob("*.jsonl"))
    events = [json.loads(line) for line in journal.read_text().splitlines()]
    assert [row["http_status"] for row in events if row["stage"] == "response"] == [429]


@pytest.mark.parametrize(
    "headers,reason",
    [
        ([("Content-Length", "1"), ("content-length", "1")], "duplicate_response_framing"),
        ([("Content-Type", "text/plain"), ("content-type", "text/plain")], "duplicate_response_framing"),
        ([("Content-Length", "1"), ("Transfer-Encoding", "chunked")], "conflicting_response_framing"),
        ([("Transfer-Encoding", "gzip")], "unsupported_response_framing"),
    ],
)
def test_transport_rejects_ambiguous_framing(headers, reason):
    class Response:
        status = 200

        def getheaders(self):
            return headers

    with pytest.raises(capture.CaptureRefused, match=reason):
        capture._Response(None, Response())


def test_wall_clock_watchdog_bounds_open_and_headers(pilot, monkeypatch):
    import time

    monkeypatch.setattr(capture, "REQUEST_SECONDS", 0.02)

    @contextmanager
    def stuck(url, *, timeout):
        time.sleep(0.2)
        yield

    started = time.monotonic()
    report = capture.capture(pilot["root"], open_response=stuck)
    assert time.monotonic() - started < 0.15
    assert report["reason"] == "request_deadline_exhausted"
    assert report["provider_operations"] == 1


def test_partial_write_failure_removes_only_created_file(tmp_path, monkeypatch):
    path = tmp_path / "managed-body.json"
    real_fsync = capture.os.fsync

    def failed(_):
        raise OSError("synthetic fsync failure")

    monkeypatch.setattr(capture.os, "fsync", failed)
    with pytest.raises(OSError):
        capture._write_new(path, b"synthetic body")
    assert not path.exists()
    monkeypatch.setattr(capture.os, "fsync", real_fsync)
    path.write_bytes(b"existing")
    with pytest.raises(FileExistsError):
        capture._write_new(path, b"replacement")
    assert path.read_bytes() == b"existing"


def test_http_adapter_accepts_completed_response_eof_without_live_socket():
    class Response:
        status = 200

        def getheaders(self):
            return [("Content-Type", "text/plain"), ("Content-Length", "0")]

        def isclosed(self):
            return True

    assert capture._Response(None, Response()).read(1024, 1) == b""
