"""Finite batch transport, Stop and durable storage contracts."""

import json
from contextlib import contextmanager

import pytest
from tcgcsv_capture_helpers import batch as batch
from tcgcsv_capture_helpers import capture
from tcgcsv_capture_helpers import pilot as pilot


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
