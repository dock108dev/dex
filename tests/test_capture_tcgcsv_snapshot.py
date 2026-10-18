"""Bounded synthetic transport tests; no external sockets or customer state."""

import importlib.util
import io
import json
from contextlib import contextmanager
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "capture_tcgcsv_snapshot", Path(__file__).parents[1] / "scripts" / "capture_tcgcsv_snapshot.py"
)
capture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(capture)
BUILD = b"2026-10-17T12:30:00Z\n"


class Clock:
    def __init__(self):
        self.seconds = 0.0

    def __call__(self):
        return self.seconds

    def sleep(self, seconds):
        self.seconds += seconds


def envelope(rows, *, total=True):
    result = {"success": True, "errors": [], "results": rows}
    if total:
        result["totalItems"] = len(rows)
    return json.dumps(result).encode()


@pytest.fixture
def pilot(tmp_path):
    root = tmp_path / "customer"
    root.mkdir(mode=0o700)
    bodies = [
        BUILD,
        envelope([{"groupId": 3170, "categoryId": 3, "name": "SWSH12: Silver Tempest"}]),
        envelope(
            [{"productId": 1, "categoryId": 3, "groupId": 3170, "name": "Synthetic Card", "extendedData": []}]
        ),
        envelope([{"productId": 1, "subTypeName": "Normal", "marketPrice": 1.25}], total=False),
        BUILD,
    ]
    clock, calls, headers, statuses = Clock(), [], {}, {}

    @contextmanager
    def transport(url, *, timeout):
        index = len(calls)
        # The consumed record must already be durable and visible before dispatch.
        journal = next((root.parent / ".dex-tcgcsv-snapshots").rglob("*.jsonl"))
        events = [json.loads(line) for line in journal.read_text().splitlines()]
        assert events[-1]["stage"] == "consumed"
        assert events[-1]["attempt"] == index + 1
        assert 0 < timeout <= 15
        calls.append((url, clock()))
        body = bodies[index]
        stream = io.BytesIO(body)

        response_headers = {
            "content-type": "text/plain" if index in {0, 4} else "application/json",
            "content-length": str(len(body)),
        }
        response_headers.update(headers.get(index, {}))

        class Response:
            status = statuses.get(index, 200)
            headers = response_headers

            def read(self, size, remaining):
                assert 0 < remaining <= 15
                return stream.read(size)

        yield Response()

    def run(**extra):
        return capture.capture(
            root,
            open_response=transport,
            clock=clock,
            sleep=clock.sleep,
            now=lambda: "2026-10-17T13:00:00+00:00",
            **extra,
        )

    return dict(
        root=root, bodies=bodies, calls=calls, headers=headers, statuses=statuses, run=run, clock=clock
    )


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


# Finite scaled selection tests use only these fabricated envelopes and private
# disposable roots. No source transport or customer installation is accessed.
@pytest.fixture
def batch(tmp_path):
    import hashlib

    owner = tmp_path / "owner"
    owner.mkdir(mode=0o700)
    root = owner / "customer"
    root.mkdir(mode=0o700)
    groups = [{"group_id": 1397, "name": "Aquapolis"}, {"group_id": 1375, "name": "Expedition"}]
    group_body = envelope([dict(groupId=g["group_id"], categoryId=3, name=g["name"]) for g in groups])
    retained = root / "price-snapshots/staging/hunt11/capture-v1/groups.json"
    capture._private_directory(retained.parent)
    capture._write_new(retained, group_body)
    plan = capture.make_batch_plan(
        root, groups, "2026-10-19T00:00:00Z", hashlib.sha256(group_body).hexdigest()
    )
    accounting = capture._accounting(root)
    legacy = [dict(stage="selected", maximum_attempts=5, at="2026-10-17T13:00:00Z")]
    for attempt in range(1, 6):
        legacy.append(dict(stage="consumed", attempt=attempt, at="2026-10-17T13:00:00Z"))
        if attempt in {1, 5}:
            legacy.append(dict(stage="received", attempt=attempt, publisher_built_at="2026-10-16T12:30:00Z"))
    legacy.append(dict(stage="closed", status="captured", consumed=5))
    capture._write_new(
        accounting / "hunt11-five-request-v1.jsonl", b"".join(capture._json_bytes(row) for row in legacy)
    )
    metadata = root.parents[1] / ".dex-tcgcsv-metadata/attempts.json"
    capture._private_directory(metadata.parent)
    capture._write_new(
        metadata,
        capture._json_bytes(
            dict(
                schema="dex-tcgcsv-metadata-attempts-v1",
                attempts=[
                    dict(
                        plan="historical-metadata",
                        manifest_sha256="a" * 64,
                        reserved_at="2026-10-17T12:00:00Z",
                        status="complete",
                    )
                ],
            )
        ),
    )
    build = b"2026-10-18T12:30:00Z\n"
    bodies = [build]
    for index, group in enumerate(groups):
        product_id = index + 1
        bodies.extend(
            [
                envelope(
                    [
                        dict(
                            productId=product_id,
                            categoryId=3,
                            groupId=group["group_id"],
                            name="Synthetic",
                            extendedData=[],
                        )
                    ]
                ),
                envelope([dict(productId=product_id, subTypeName="Normal", marketPrice=1.25)], total=False),
            ]
        )
    bodies.append(build)
    clock, calls, statuses, headers = Clock(), [], {}, {}

    @contextmanager
    def response(url, *, timeout):
        index = len(calls)
        journal = next(accounting.glob("batch-*.jsonl"))
        rows = [json.loads(line) for line in journal.read_text().splitlines()]
        assert rows[-1]["stage"] == "consumed" and rows[-1]["attempt"] == index + 1
        history = json.loads(metadata.read_bytes())
        assert history["attempts"][-1]["status"] == "consumed"
        assert history["attempts"][0]["plan"] in {"historical-metadata", "tcgcsv-pokemon-groups-first-v1"}
        assert 0 < timeout <= plan["limits"]["request_seconds"]
        calls.append((url, clock()))
        body = bodies[index]
        stream = io.BytesIO(body)
        response_headers = {
            "content-type": "text/plain" if index in {0, len(bodies) - 1} else "application/json",
            "content-length": str(len(body)),
        }
        response_headers.update(headers.get(index, {}))

        class Response:
            status = statuses.get(index, 200)
            headers = response_headers

            def read(self, size, remaining):
                return stream.read(size)

        yield Response()

    def run(**extra):
        return capture.capture_batch(
            root,
            plan,
            expected_plan_sha256=capture.validate_batch_plan(plan, root),
            open_response=extra.pop("open_response", response),
            clock=clock,
            sleep=clock.sleep,
            now=extra.pop("now", lambda: "2026-10-19T13:00:00Z"),
            **extra,
        )

    return dict(
        root=root,
        plan=plan,
        accounting=accounting,
        metadata=metadata,
        retained=retained,
        bodies=bodies,
        calls=calls,
        statuses=statuses,
        headers=headers,
        clock=clock,
        run=run,
    )


def test_finite_batch_exact_order_caps_and_private_metadata_accounting(batch):
    report = batch["run"]()
    assert report["status"] == "captured"
    assert report["provider_operations"] == 6 == batch["plan"]["request_count"]
    assert report["group_ids"] == [1397, 1375]
    assert [row[0] for row in batch["calls"]] == [step["url"] for step in batch["plan"]["steps"]]
    assert all(b[1] - a[1] >= 1 for a, b in zip(batch["calls"], batch["calls"][1:]))
    assert report["product_rows"] == report["price_rows"] == 2
    assert report["provider_valuation_at"] is None
    assert report["imported"] is report["activated"] is False
    destination = batch["root"] / report["capture_directory"]
    assert len(list(destination.rglob("*.json"))) == 5
    assert all(path.stat().st_mode & 0o077 == 0 for path in destination.rglob("*") if path.is_file())
    accounting = next(batch["accounting"].glob("batch-*.jsonl")).read_text()
    assert accounting.count('"stage":"consumed"') == 6
    assert "marketPrice" not in accounting and "1.25" not in accounting
    assert not any("sha256" in row for row in report["files"])
    assert batch["retained"].exists()


def test_renaming_consumed_batch_or_pilot_cannot_replay(batch, monkeypatch):
    assert batch["run"]()["status"] == "captured"
    batch["plan"]["plan_id"] = "renamed-plan"
    with pytest.raises(capture.CaptureRefused, match="batch_already_consumed"):
        batch["run"](now=lambda: "2026-10-21T13:00:00Z")
    monkeypatch.setattr(capture, "PILOT", "renamed-pilot")
    with pytest.raises(FileExistsError):
        capture.capture(batch["root"])
    assert len(batch["calls"]) == 6


@pytest.mark.parametrize(
    "mutation,reason",
    [
        ("request_count", "batch_step_mismatch"),
        ("url", "batch_step_mismatch"),
        ("duplicate_group", "invalid_batch_groups"),
        ("extra_key", "invalid_batch_plan"),
        ("file_expansion", "batch_limit_expansion"),
        ("pace_expansion", "batch_limit_expansion"),
        ("naive_date", "aware_timestamp_required"),
        ("bad_digest", "invalid_batch_identity"),
        ("bool_count", "batch_step_mismatch"),
        ("bool_limit", "invalid_batch_limits"),
    ],
)
def test_batch_plan_is_exact_and_limits_cannot_expand(batch, mutation, reason):
    plan = batch["plan"]
    if mutation == "request_count":
        plan["request_count"] += 1
    elif mutation == "url":
        plan["steps"][1]["url"] += "?fallback=1"
    elif mutation == "duplicate_group":
        plan["groups"][1] = plan["groups"][0]
    elif mutation == "extra_key":
        plan["retry"] = True
    elif mutation == "file_expansion":
        plan["limits"]["file_bytes"] += 1
    elif mutation == "pace_expansion":
        plan["limits"]["spacing_seconds"] = 0.25
    elif mutation == "naive_date":
        plan["not_before"] = "2026-10-19T00:00:00"
    elif mutation == "bad_digest":
        plan["retained_groups_sha256"] = "wrong"
    elif mutation == "bool_count":
        plan["request_count"] = True
    else:
        plan["limits"]["file_bytes"] = True
    with pytest.raises(capture.CaptureRefused, match=reason):
        batch["run"]()
    assert batch["calls"] == []


@pytest.mark.parametrize("source", ["snapshot", "metadata"])
def test_publication_spacing_reads_all_durable_histories(batch, source):
    if source == "snapshot":
        capture._write_new(
            batch["accounting"] / "uncertain-old-plan.jsonl",
            b"".join(
                [
                    capture._json_bytes(
                        dict(stage="selected", maximum_attempts=6, at="2026-10-19T12:59:00Z")
                    ),
                    capture._json_bytes(dict(stage="consumed", at="2026-10-19T12:59:00Z", attempt=1)),
                ]
            ),
        )
    else:
        value = json.loads(batch["metadata"].read_bytes())
        value["attempts"][0].update(reserved_at="2026-10-19T12:59:00Z", status="failed")
        capture._replace_metadata(batch["metadata"], value)
    with pytest.raises(capture.CaptureRefused, match="publisher_24h_reservation"):
        batch["run"]()
    assert not batch["calls"]


@pytest.mark.parametrize("source", ["snapshot", "metadata"])
def test_absent_or_corrupt_history_fails_before_dispatch(batch, source):
    path = (
        (batch["accounting"] / "hunt11-five-request-v1.jsonl") if source == "snapshot" else batch["metadata"]
    )
    path.unlink()
    with pytest.raises(capture.CaptureRefused, match="historical_accounting_required"):
        batch["run"]()
    capture._write_new(path, b"corrupt\n")
    with pytest.raises(capture.CaptureRefused, match="invalid_accounting"):
        batch["run"]()
    assert not batch["calls"]


def test_not_before_and_retained_group_change_refuse_without_consuming(batch):
    with pytest.raises(capture.CaptureRefused, match="capture_not_before"):
        batch["run"](now=lambda: "2026-10-18T13:00:00Z")
    batch["retained"].write_bytes(b"changed")
    with pytest.raises(capture.CaptureRefused, match="retained_group_metadata_changed"):
        batch["run"]()
    assert not batch["calls"] and not list(batch["accounting"].glob("batch-*.jsonl"))


@pytest.mark.parametrize(
    "mutation,reason,attempts",
    [
        ("changed_build", "publisher_build_changed", 6),
        ("old_build", "publisher_build_spacing", 1),
        ("naive_build", "aware_timestamp_required", 1),
        ("future_build", "publisher_build_in_future", 1),
        ("later_malformed", "invalid_json", 4),
        ("later_group", "product_binding_conflict", 4),
        ("cross_group_product", "cross_group_product_identity", 4),
        ("orphan_price", "orphan_price_identity", 5),
    ],
)
def test_later_shard_failures_consume_once_and_clean_only_batch_bodies(batch, mutation, reason, attempts):
    if mutation == "changed_build":
        batch["bodies"][5] = b"2026-10-18T12:30:01Z"
    elif mutation == "old_build":
        batch["bodies"][0] = b"2026-10-16T12:30:00Z"
    elif mutation == "naive_build":
        batch["bodies"][0] = b"2026-10-18T12:30:00"
    elif mutation == "future_build":
        batch["bodies"][0] = b"2026-10-20T12:30:00Z"
    elif mutation == "later_malformed":
        batch["bodies"][3] = b"{malformed later shard"
    else:
        index = 4 if mutation == "orphan_price" else 3
        value = json.loads(batch["bodies"][index])
        if mutation == "later_group":
            value["results"][0]["groupId"] = 1397
        else:
            value["results"][0]["productId"] = 999 if mutation == "orphan_price" else 1
        batch["bodies"][index] = json.dumps(value).encode()
    report = batch["run"]()
    assert report["status"] == "stopped" and report["reason"] == reason
    assert report["provider_operations"] == attempts == len(batch["calls"])
    assert not list((batch["root"] / "price-snapshots/staging/hunt11-batches").rglob("*.json"))
    assert batch["retained"].exists()
    assert json.loads(batch["metadata"].read_bytes())["attempts"][-1]["status"] == "stopped"
    with pytest.raises(capture.CaptureRefused, match="publisher_24h_reservation"):
        batch["run"]()


@pytest.mark.parametrize("status", [301, 302, 429, 500])
def test_batch_never_retries_redirects_or_falls_back(batch, status):
    batch["statuses"][1] = status
    report = batch["run"]()
    assert report["reason"] == "http_non_success" and report["provider_operations"] == 2


@pytest.mark.parametrize("kind", ["aggregate", "products", "prices", "per_file_rows", "metadata", "staging"])
def test_batch_explicit_aggregate_row_and_storage_limits(batch, kind):
    limits = batch["plan"]["limits"]
    if kind == "aggregate":
        limits["aggregate_input_bytes"] = len(batch["bodies"][1]) + 4
    elif kind in {"products", "prices"}:
        limits[kind[:-1] + "_rows"] = 1
    elif kind == "per_file_rows":
        value = json.loads(batch["bodies"][4])
        value["results"].append(dict(productId=2, subTypeName="Holofoil"))
        batch["bodies"][4] = json.dumps(value).encode()
        limits["rows_per_file"] = 1
    elif kind == "metadata":
        limits["metadata_bytes"] = 1
    else:
        limits["staging_bytes"] = batch["retained"].stat().st_size + len(batch["bodies"][0]) + 4
    report = batch["run"]()
    assert report["status"] == "stopped"
    assert report["reason"] in {"body_too_large", "row_capacity_exhausted", "staging_capacity_exhausted"}
    assert not list((batch["root"] / "price-snapshots/staging/hunt11-batches").rglob("*.json"))


def test_batch_request_deadline_consumes_uncertainty_and_sanitizes_failure(batch):
    @contextmanager
    def uncertain(url, *, timeout):
        raise TimeoutError("secret raw content must never appear")
        yield

    report = batch["run"](open_response=uncertain)
    assert report["provider_operations"] == 1 and report["reason"] == "transport_or_storage_failure"
    assert "secret" not in json.dumps(report)
    assert json.loads(batch["metadata"].read_bytes())["attempts"][-1]["status"] == "stopped"


@pytest.mark.parametrize("which", ["request", "total"])
def test_batch_wall_watchdog_bounds_blocked_headers_and_total_deadline(batch, which):
    import time

    batch["plan"]["limits"][which + "_seconds"] = 0.02

    @contextmanager
    def blocked(url, *, timeout):
        time.sleep(2)
        yield

    started = time.monotonic()
    report = capture.capture_batch(
        batch["root"],
        batch["plan"],
        expected_plan_sha256=capture.validate_batch_plan(batch["plan"], batch["root"]),
        open_response=blocked,
        now=lambda: "2026-10-19T13:00:00Z",
    )
    assert time.monotonic() - started < 0.5
    assert report["reason"] == which + "_deadline_exhausted" and report["provider_operations"] == 1


def test_batch_stop_before_start_is_independent_and_never_consumes(batch):
    assert capture.request_stop(batch["root"])["provider_operations"] == 0
    with pytest.raises(capture.CaptureRefused, match="stop_requested"):
        batch["run"]()
    assert not batch["calls"] and not list(batch["accounting"].glob("batch-*.jsonl"))
    capture.clear_stop(batch["root"])
    assert batch["run"]()["status"] == "captured"


def _blocked_batch_child(root, plan, pipe):
    import time

    @contextmanager
    def blocked(url, *, timeout):
        pipe.send("in_flight")
        time.sleep(5)
        yield

    report = capture.capture_batch(
        root,
        plan,
        expected_plan_sha256=capture.validate_batch_plan(plan, root),
        open_response=blocked,
        now=lambda: "2026-10-19T13:00:00Z",
    )
    pipe.send(report)
    pipe.close()


def test_concurrent_start_and_independent_stop_interrupt_inflight_headers(batch):
    import multiprocessing
    import time

    context = multiprocessing.get_context("fork")
    parent, child = context.Pipe()
    process = context.Process(target=_blocked_batch_child, args=(batch["root"], batch["plan"], child))
    process.start()
    try:
        assert parent.poll(3) and parent.recv() == "in_flight"
        with pytest.raises(capture.CaptureRefused, match="execution_already_active"):
            batch["run"]()
        with pytest.raises(capture.CaptureRefused, match="execution_already_active"):
            capture.clear_stop(batch["root"])
        started = time.monotonic()
        assert capture.request_stop(batch["root"])["provider_operations"] == 0
        assert parent.poll(1)
        report = parent.recv()
        assert time.monotonic() - started < 0.5
        assert report["reason"] == "stop_requested" and report["provider_operations"] == 1
        process.join(2)
        assert process.exitcode == 0
        assert not list((batch["root"] / "price-snapshots/staging/hunt11-batches").rglob("*.json"))
    finally:
        if process.is_alive():
            process.terminate()
        process.join(2)
        parent.close()
        child.close()


@pytest.mark.parametrize(
    "headers,reason",
    [
        ({"content-length": None}, "ambiguous_response_framing"),
        ({"transfer-encoding": "chunked"}, "ambiguous_response_framing"),
        ({"content-length": "+20"}, "invalid_content_length"),
        ({"content-length": " 20"}, "invalid_content_length"),
        ({"content-encoding": "gzip"}, "unsupported_content_encoding"),
    ],
)
def test_batch_strict_framing_before_body(batch, headers, reason):
    batch["headers"][0] = headers
    report = batch["run"]()
    assert report["reason"] == reason and report["provider_operations"] == 1


def test_batch_explicitly_selected_groups_metadata_request_is_counted(batch):
    plan = batch["plan"]
    plan["include_groups"] = True
    plan["steps"] = capture.batch_steps(plan["groups"], True)
    plan["request_count"] = 7
    batch["bodies"].insert(1, batch["retained"].read_bytes())
    report = batch["run"]()
    assert report["status"] == "captured" and report["provider_operations"] == 7
    assert [row[0] for row in batch["calls"]] == [step["url"] for step in plan["steps"]]


def test_batch_dangling_stop_link_cannot_bypass_stop(batch, tmp_path):
    (batch["accounting"] / "STOP").symlink_to(tmp_path / "missing")
    capture.request_stop(batch["root"])
    with pytest.raises(capture.CaptureRefused, match="stop_requested"):
        batch["run"]()
    assert not batch["calls"]


def test_batch_stop_between_shards_and_during_body_keeps_consumed_attempt(batch):
    @contextmanager
    def response(url, *, timeout):
        class Response:
            status = 200
            headers = {"content-type": "text/plain", "content-length": str(len(batch["bodies"][0]))}

            def read(self, size, remaining):
                capture.request_stop(batch["root"])
                return batch["bodies"][0]

        yield Response()

    report = batch["run"](open_response=response)
    assert report["reason"] == "stop_requested" and report["provider_operations"] == 1
    assert json.loads(batch["metadata"].read_bytes())["attempts"][-1]["status"] == "stopped"


def test_batch_reduces_no_transport_limit_after_failure(batch):
    original = json.dumps(batch["plan"], sort_keys=True)
    batch["statuses"][2] = 500
    assert batch["run"]()["reason"] == "http_non_success"
    assert json.dumps(batch["plan"], sort_keys=True) == original


@pytest.mark.parametrize("point", ["validation", "body_write", "metadata_write"])
def test_total_deadline_covers_final_processing_and_storage(batch, monkeypatch, point):
    if point == "validation":
        original = capture._validate
        calls = []

        def validate(body, kind, **kwargs):
            result = original(body, kind, **kwargs)
            calls.append(kind)
            if calls.count("text") == 2:
                batch["clock"].seconds += 181
            return result

        monkeypatch.setattr(capture, "_validate", validate)
    else:
        original = capture._write_new

        def write(path, body):
            original(path, body)
            target = "build-after.txt" if point == "body_write" else "capture-metadata.json"
            if path.name == target:
                batch["clock"].seconds += 181

        monkeypatch.setattr(capture, "_write_new", write)
    report = batch["run"]()
    assert report["reason"] == "total_deadline_exhausted"
    assert report["provider_operations"] == 6
    assert not list((batch["root"] / "price-snapshots/staging/hunt11-batches").rglob("*.json"))


def test_stop_during_pacing_prevents_next_dispatch(batch):
    original = batch["clock"].sleep

    def sleep(seconds):
        capture.request_stop(batch["root"])
        original(seconds)

    batch["clock"].sleep = sleep
    report = batch["run"]()
    assert report["reason"] == "stop_requested" and report["provider_operations"] == 1
    assert len(batch["calls"]) == 1


@pytest.mark.parametrize(
    "mutation", ["empty", "missing_consumption", "bad_closure", "after_closed", "naive_build"]
)
def test_corrupt_original_pilot_cannot_erase_consumed_history(batch, mutation):
    path = batch["accounting"] / "hunt11-five-request-v1.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    if mutation == "empty":
        rows = []
    elif mutation == "missing_consumption":
        rows = [row for row in rows if not (row["stage"] == "consumed" and row["attempt"] == 3)]
    elif mutation == "bad_closure":
        rows[-1]["consumed"] = 4
    elif mutation == "after_closed":
        rows.append(dict(stage="consumed", attempt=6, at="2026-10-17T13:00:00Z"))
    else:
        next(row for row in rows if row["stage"] == "received")["publisher_built_at"] = "2026-10-16T12:30:00"
    path.write_bytes(b"".join(capture._json_bytes(row) for row in rows))
    with pytest.raises(capture.CaptureRefused, match="invalid_accounting"):
        batch["run"]()
    assert not batch["calls"]


def test_existing_pending_reservation_is_preserved_without_dispatch(batch):
    pending = batch["metadata"].with_suffix(".pending")
    capture._write_new(pending, b"independent interrupted durable reservation")
    report = batch["run"]()
    assert report["reason"] == "transport_or_storage_failure" and report["provider_operations"] == 0
    assert pending.read_bytes() == b"independent interrupted durable reservation"
    assert not batch["calls"]


def test_stop_after_terminal_commit_preserves_single_coherent_captured_closure(batch, monkeypatch):
    original = capture._append

    def append(stream, row):
        original(stream, row)
        if row.get("stage") == "closed" and row.get("status") == "captured":
            capture.request_stop(batch["root"])

    monkeypatch.setattr(capture, "_append", append)
    report = batch["run"]()
    assert report["status"] == "captured" and report["provider_operations"] == 6
    rows = [
        json.loads(line) for line in next(batch["accounting"].glob("batch-*.jsonl")).read_text().splitlines()
    ]
    assert sum(row["stage"] == "closed" for row in rows) == 1
    latest, _, _ = capture._history(batch["accounting"], batch["metadata"])
    assert latest == capture._aware("2026-10-19T13:00:00Z")
    assert (batch["root"] / report["capture_directory"] / "capture-metadata.json").exists()


def test_watchdog_after_body_write_before_bookkeeping_cleans_that_body(batch, monkeypatch):
    original = capture._write_new

    def write(path, body):
        original(path, body)
        if path.name == "build-after.txt":
            raise capture.CaptureRefused("total_deadline_exhausted")

    monkeypatch.setattr(capture, "_write_new", write)
    report = batch["run"]()
    assert report["reason"] == "total_deadline_exhausted" and report["provider_operations"] == 6
    assert not list((batch["root"] / "price-snapshots/staging/hunt11-batches").rglob("*.txt"))
    assert not list((batch["root"] / "price-snapshots/staging/hunt11-batches").rglob("*.json"))


def _initial_fill(batch):
    batch["plan"]["purpose"] = "initial_fill"
    batch["plan"]["not_before"] = "2026-10-17T13:30:00Z"
    history = json.loads(batch["metadata"].read_bytes())
    history["attempts"][0]["plan"] = "tcgcsv-pokemon-groups-first-v1"
    capture._replace_metadata(batch["metadata"], history)
    batch["bodies"][0] = batch["bodies"][-1] = b"2026-10-16T12:30:00Z"


def test_initial_fill_new_groups_can_share_build_without_waiting_refresh_period(batch):
    _initial_fill(batch)
    report = batch["run"](now=lambda: "2026-10-17T14:00:00Z")
    assert report["status"] == "captured" and report["provider_operations"] == 6
    assert report["purpose"] == "initial_fill"
    rows = [
        json.loads(line) for line in next(batch["accounting"].glob("batch-*.jsonl")).read_text().splitlines()
    ]
    assert rows[0]["purpose"] == "initial_fill"
    assert rows[0]["group_ids"] == [1397, 1375]
    assert rows[1]["stage"] == "consumed" and rows[1]["endpoint"] == "text"
    groups = {}
    capture._history(batch["accounting"], batch["metadata"], group_history=groups)
    assert groups == {"groups": {3170, 1397, 1375}, "unknown": False}
    assert batch["plan"]["limits"]["publication_spacing_seconds"] == 86400


def test_initial_fill_still_honors_not_before(batch):
    _initial_fill(batch)
    with pytest.raises(capture.CaptureRefused, match="capture_not_before"):
        batch["run"](now=lambda: "2026-10-17T13:00:00Z")
    assert not batch["calls"]


@pytest.mark.parametrize("change", ["plan_id", "not_before", "both", "subset"])
def test_initial_fill_full_selection_stays_consumed_after_failed_first_build(batch, change):
    _initial_fill(batch)
    batch["statuses"][0] = 500
    report = batch["run"](now=lambda: "2026-10-17T14:00:00Z")
    assert report["provider_operations"] == 1 and report["reason"] == "http_non_success"
    if change in {"plan_id", "both"}:
        batch["plan"]["plan_id"] = "renamed-initial-fill"
    if change in {"not_before", "both"}:
        batch["plan"]["not_before"] = "2026-10-18T14:00:00Z"
    if change == "subset":
        batch["plan"]["groups"] = batch["plan"]["groups"][1:]
        batch["plan"]["steps"] = capture.batch_steps(batch["plan"]["groups"])
        batch["plan"]["request_count"] = 4
    with pytest.raises(capture.CaptureRefused, match="initial_fill_group_already_consumed"):
        batch["run"](now=lambda: "2026-10-20T14:00:00Z")
    assert len(batch["calls"]) == 1


def test_initial_fill_cannot_repeat_fixed_historical_pilot_group(batch):
    _initial_fill(batch)
    batch["plan"]["groups"] = [{"group_id": 3170, "name": "SWSH12: Silver Tempest"}]
    batch["plan"]["steps"] = capture.batch_steps(batch["plan"]["groups"])
    batch["plan"]["request_count"] = 4
    with pytest.raises(capture.CaptureRefused, match="initial_fill_group_already_consumed"):
        batch["run"](now=lambda: "2026-10-17T14:00:00Z")
    assert not batch["calls"]


@pytest.mark.parametrize("source", ["unknown_snapshot", "unknown_metadata", "old_build_only"])
def test_initial_fill_unknown_prior_scope_fails_conservatively(batch, source):
    _initial_fill(batch)
    if source == "unknown_metadata":
        history = json.loads(batch["metadata"].read_bytes())
        history["attempts"][0]["plan"] = "unknown-prior-data-plan"
        capture._replace_metadata(batch["metadata"], history)
    else:
        consumed = dict(stage="consumed", attempt=1, at="2026-10-17T13:00:00Z")
        if source == "old_build_only":
            consumed.update(endpoint="text", group_id=None)
        capture._write_new(
            batch["accounting"] / "old-uncertain.jsonl",
            b"".join(
                capture._json_bytes(row) for row in [dict(stage="selected", maximum_attempts=6), consumed]
            ),
        )
    with pytest.raises(capture.CaptureRefused, match="historical_group_scope_unknown"):
        batch["run"](now=lambda: "2026-10-17T14:00:00Z")
    assert not batch["calls"]


def test_initial_fill_declared_scope_blocks_retry_even_before_first_send(batch, monkeypatch):
    _initial_fill(batch)
    original = capture._replace_metadata

    def refused(*_):
        raise OSError("synthetic reservation failure")

    monkeypatch.setattr(capture, "_replace_metadata", refused)
    report = batch["run"](now=lambda: "2026-10-17T14:00:00Z")
    assert report["provider_operations"] == 0
    monkeypatch.setattr(capture, "_replace_metadata", original)
    batch["plan"].update(plan_id="new-zero-send-selection", not_before="2026-10-18T00:00:00Z")
    with pytest.raises(capture.CaptureRefused, match="initial_fill_group_already_consumed"):
        batch["run"](now=lambda: "2026-10-20T14:00:00Z")
    assert not batch["calls"]


def test_refresh_build_only_needs_to_be_strictly_newer_not_day_newer(batch):
    batch["bodies"][0] = batch["bodies"][-1] = b"2026-10-16T12:30:01Z"
    report = batch["run"]()
    assert report["status"] == "captured" and report["purpose"] == "refresh"
    assert "purpose" not in batch["plan"]


def test_explicit_refresh_keeps_daily_reservation_guard(batch):
    batch["plan"]["purpose"] = "refresh"
    batch["plan"]["not_before"] = "2026-10-17T13:30:00Z"
    with pytest.raises(capture.CaptureRefused, match="publisher_24h_reservation"):
        batch["run"](now=lambda: "2026-10-17T14:00:00Z")
    assert not batch["calls"]


def test_initial_fill_does_not_accept_older_build(batch):
    _initial_fill(batch)
    batch["bodies"][0] = b"2026-10-16T12:29:59Z"
    report = batch["run"](now=lambda: "2026-10-17T14:00:00Z")
    assert report["reason"] == "publisher_build_spacing" and report["provider_operations"] == 1


@pytest.mark.parametrize("purpose", ["background", "", None, [], True])
def test_optional_purpose_remains_strict(batch, purpose):
    batch["plan"]["purpose"] = purpose
    with pytest.raises(capture.CaptureRefused, match="invalid_batch_plan"):
        batch["run"]()
    assert not batch["calls"]


@pytest.mark.parametrize("purpose", ["initial_fill", "refresh"])
def test_any_mode_refuses_clock_rollback_against_consumed_history(batch, purpose):
    _initial_fill(batch)
    batch["plan"]["purpose"] = purpose
    path = batch["accounting"] / "hunt11-five-request-v1.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    for row in rows:
        if row["stage"] == "consumed":
            row["at"] = "2026-10-17T15:00:00Z"
    path.write_bytes(b"".join(capture._json_bytes(row) for row in rows))
    with pytest.raises(capture.CaptureRefused, match="capture_clock_rollback"):
        batch["run"](now=lambda: "2026-10-17T14:00:00Z")
    assert not batch["calls"]


def _selected_group_refresh(batch):
    batch["plan"].update(purpose="refresh", refresh_cadence="selected_groups")
    history = json.loads(batch["metadata"].read_bytes())
    history["attempts"][0]["plan"] = "tcgcsv-pokemon-groups-first-v1"
    capture._replace_metadata(batch["metadata"], history)


def _reserve_group(batch, gid, at, *, endpoint="text", consumed=True):
    rows = [dict(stage="selected", maximum_attempts=4, at=at, group_ids=[gid], purpose="refresh")]
    if consumed:
        rows.append(
            dict(
                stage="consumed",
                attempt=1,
                at=at,
                endpoint=endpoint,
                group_id=gid if endpoint in {"products", "prices"} else None,
            )
        )
    capture._write_new(
        batch["accounting"] / "other-reservation.jsonl", b"".join(capture._json_bytes(row) for row in rows)
    )


def test_selected_group_refresh_ignores_unrelated_recent_data_consumption(batch):
    _selected_group_refresh(batch)
    _reserve_group(batch, 9999, "2026-10-19T12:59:00Z", endpoint="prices")
    assert batch["run"]()["status"] == "captured"
    assert len(batch["calls"]) == 6


@pytest.mark.parametrize("consumed,endpoint", [(False, "text"), (True, "text"), (True, "prices")])
def test_selected_group_refresh_keeps_failed_uncertain_and_zero_send_reservations(batch, consumed, endpoint):
    _selected_group_refresh(batch)
    _reserve_group(batch, 1397, "2026-10-19T12:59:00Z", endpoint=endpoint, consumed=consumed)
    with pytest.raises(capture.CaptureRefused, match="selected_groups_24h_reservation"):
        batch["run"]()
    assert not batch["calls"]


def test_selected_group_refresh_uses_latest_matching_attempt_not_selection_start(batch):
    _selected_group_refresh(batch)
    _reserve_group(batch, 1397, "2026-10-18T12:59:00Z", endpoint="prices")
    path = batch["accounting"] / "other-reservation.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    rows[-1]["at"] = "2026-10-18T13:00:01Z"
    path.write_bytes(b"".join(capture._json_bytes(row) for row in rows))
    with pytest.raises(capture.CaptureRefused, match="selected_groups_24h_reservation"):
        batch["run"]()
    assert not batch["calls"]


def test_selected_group_refresh_accepts_exact_daily_boundary(batch):
    _selected_group_refresh(batch)
    _reserve_group(batch, 1397, "2026-10-18T13:00:00Z", endpoint="prices")
    assert batch["run"]()["status"] == "captured"


def test_selected_group_refresh_refuses_unknown_historical_scope(batch):
    batch["plan"]["refresh_cadence"] = "selected_groups"
    with pytest.raises(capture.CaptureRefused, match="historical_group_scope_unknown"):
        batch["run"]()
    assert not batch["calls"]


def test_selected_group_refresh_failed_build_reserves_scope_across_renaming(batch):
    _selected_group_refresh(batch)
    batch["statuses"][0] = 500
    assert batch["run"]()["provider_operations"] == 1
    batch["plan"].update(plan_id="renamed-refresh", not_before="2026-10-19T13:01:00Z")
    with pytest.raises(capture.CaptureRefused, match="selected_groups_24h_reservation"):
        batch["run"](now=lambda: "2026-10-19T14:00:00Z")
    assert len(batch["calls"]) == 1


@pytest.mark.parametrize("mutation", ["initial_fill", "metadata", "invalid", "null"])
def test_selected_group_refresh_policy_is_strict_and_digest_bound(batch, mutation):
    _selected_group_refresh(batch)
    before = capture.validate_batch_plan(batch["plan"], batch["root"])
    legacy = dict(batch["plan"])
    legacy.pop("refresh_cadence")
    assert capture.validate_batch_plan(legacy, batch["root"]) != before
    if mutation == "initial_fill":
        batch["plan"]["purpose"] = "initial_fill"
    elif mutation == "metadata":
        batch["plan"]["include_groups"] = True
    else:
        batch["plan"]["refresh_cadence"] = None if mutation == "null" else "unlimited"
    with pytest.raises(capture.CaptureRefused, match="invalid_refresh_cadence"):
        batch["run"]()
    assert not batch["calls"]
