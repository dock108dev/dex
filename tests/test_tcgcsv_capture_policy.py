"""Resource cadence and exhausted one-time selection contracts."""

import json

import pytest
from tcgcsv_capture_helpers import batch as batch
from tcgcsv_capture_helpers import capture

from scripts import tcgcsv_capture_contract


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


@pytest.mark.parametrize("gid,expected", [(9999, "captured"), (1397, "publisher_build_spacing")])
def test_selected_build_history_is_resource_scoped(batch, gid, expected):
    _selected_group_refresh(batch)
    _reserve_group(batch, gid, "2026-10-18T12:00:00Z")
    path = batch["accounting"] / "other-reservation.jsonl"
    with path.open("ab") as stream:
        stream.write(
            capture._json_bytes(dict(stage="received", attempt=1, publisher_built_at="2026-10-18T12:30:00Z"))
        )
    result = batch["run"]()
    assert result.get("reason", result["status"]) == expected
    assert result["provider_operations"] == (6 if expected == "captured" else 1)


def test_resource_build_index_preserves_global_legacy_build(batch):
    _reserve_group(batch, 9999, "2026-10-18T12:00:00Z")
    with (batch["accounting"] / "other-reservation.jsonl").open("ab") as stream:
        stream.write(
            capture._json_bytes(dict(stage="received", attempt=1, publisher_built_at="2026-10-18T12:30:00Z"))
        )
    resources = {}
    _, global_build, _ = capture._history(batch["accounting"], batch["metadata"], resource_history=resources)
    assert global_build.isoformat() == "2026-10-18T12:30:00+00:00"
    assert resources["builds_by_group"][3170].isoformat() == "2026-10-16T12:30:00+00:00"
    assert resources["builds_by_group"][9999] == global_build
    assert 1397 not in resources["builds_by_group"]


def _one_time_new_build_refresh(batch):
    _selected_group_refresh(batch)
    batch["plan"].update(refresh_cadence="selected_groups_new_build", timing_override="owner-refresh-once")
    _reserve_group(batch, 1397, "2026-10-19T12:59:00Z", consumed=True)
    with (batch["accounting"] / "other-reservation.jsonl").open("ab") as stream:
        stream.write(
            capture._json_bytes(dict(stage="received", attempt=1, publisher_built_at="2026-10-17T12:30:00Z"))
        )


def test_one_time_new_build_override_retains_real_history_and_consumption(batch):
    _one_time_new_build_refresh(batch)
    old = (batch["accounting"] / "other-reservation.jsonl").read_bytes()
    result = batch["run"]()
    assert result["status"] == "captured" and result["provider_operations"] == 6
    assert (batch["accounting"] / "other-reservation.jsonl").read_bytes() == old
    header = json.loads(next(batch["accounting"].glob("batch-*.jsonl")).read_text().splitlines()[0])
    assert header["timing_override"] == "owner-refresh-once"


def test_one_time_override_still_requires_strictly_newer_build(batch):
    _one_time_new_build_refresh(batch)
    batch["bodies"][0] = b"2026-10-17T12:30:00Z"
    result = batch["run"]()
    assert result["reason"] == "publisher_build_spacing" and result["provider_operations"] == 1
    batch["plan"].update(plan_id="renamed-override", not_before="2026-10-19T13:00:01Z")
    with pytest.raises(capture.CaptureRefused, match="timing_override_already_reserved"):
        batch["run"](now=lambda: "2026-10-19T14:00:00Z")
    assert len(batch["calls"]) == 1


def test_one_time_override_stop_prevents_dispatch(batch):
    _one_time_new_build_refresh(batch)
    capture.request_stop(batch["root"])
    with pytest.raises(capture.CaptureRefused, match="stop_requested"):
        batch["run"]()
    assert not batch["calls"]


@pytest.mark.parametrize("override", [None, [], "", "../unsafe"])
def test_one_time_override_requires_valid_explicit_identity(batch, override):
    _one_time_new_build_refresh(batch)
    batch["plan"]["timing_override"] = override
    with pytest.raises(capture.CaptureRefused, match="invalid_timing_override"):
        batch["run"]()
    assert not batch["calls"]


def test_ordinary_refresh_cannot_accept_timing_override(batch):
    _selected_group_refresh(batch)
    batch["plan"]["timing_override"] = "owner-refresh-once"
    with pytest.raises(capture.CaptureRefused, match="invalid_timing_override"):
        batch["run"]()
    assert not batch["calls"]


def _r3_same_build(batch, monkeypatch):
    _one_time_new_build_refresh(batch)
    # Fabricated transport exercises the finite policy without customer data.
    monkeypatch.setattr(
        tcgcsv_capture_contract,
        "R3_ACQUIRE1_GROUPS",
        (tuple(g["group_id"] for g in batch["plan"]["groups"]),),
    )
    batch["plan"].update(
        refresh_cadence="owner_r3_acquire1_same_build_once",
        timing_override=f"r3-acquire1-{capture.R3_ACQUIRE1_PROPOSAL[:16]}-batch-1",
    )
    batch["bodies"][0] = batch["bodies"][-1] = b"2026-10-17T12:30:00Z"


def test_r3_same_publication_and_consumed_history(batch, monkeypatch):
    _r3_same_build(batch, monkeypatch)
    old = (batch["accounting"] / "other-reservation.jsonl").read_bytes()
    result = batch["run"]()
    assert result["status"] == "captured" and result["provider_operations"] == 6
    assert (batch["accounting"] / "other-reservation.jsonl").read_bytes() == old
    batch["plan"].update(plan_id="renamed", not_before="2026-10-19T14:00:00Z")
    with pytest.raises(capture.CaptureRefused, match="timing_override_already_reserved"):
        batch["run"](now=lambda: "2026-10-19T14:00:01Z")
    assert len(batch["calls"]) == 6


@pytest.mark.parametrize(
    "body,reason",
    [
        (b"2026-10-16T12:30:00Z", "publisher_build_spacing"),
        (b"2026-10-20T12:30:00Z", "publisher_build_in_future"),
        (b"invalid", "invalid_build_timestamp"),
    ],
)
def test_r3_bad_build_consumes_and_cannot_replay(batch, monkeypatch, body, reason):
    _r3_same_build(batch, monkeypatch)
    batch["bodies"][0] = body
    result = batch["run"]()
    assert result["reason"] == reason and result["provider_operations"] == 1
    batch["plan"]["plan_id"] = "renamed-after-failure"
    with pytest.raises(capture.CaptureRefused, match="timing_override_already_reserved"):
        batch["run"]()
    assert len(batch["calls"]) == 1


def test_r3_changed_build_and_stop(batch, monkeypatch):
    _r3_same_build(batch, monkeypatch)
    batch["bodies"][-1] = b"2026-10-18T12:30:00Z"
    result = batch["run"]()
    assert result["reason"] == "publisher_build_changed" and result["provider_operations"] == 6


def test_r3_stop_before_dispatch(batch, monkeypatch):
    _r3_same_build(batch, monkeypatch)
    capture.request_stop(batch["root"])
    with pytest.raises(capture.CaptureRefused, match="stop_requested"):
        batch["run"]()
    assert not batch["calls"]


@pytest.mark.parametrize("change", ["rename_exception", "add_group", "reverse_groups"])
def test_r3_exception_cannot_expand_or_rename(batch, monkeypatch, change):
    _r3_same_build(batch, monkeypatch)
    if change == "rename_exception":
        batch["plan"]["timing_override"] = "r3-new-exception"
    elif change == "add_group":
        batch["plan"]["groups"].append(dict(group_id=9999, name="Other"))
    else:
        batch["plan"]["groups"].reverse()
    with pytest.raises(capture.CaptureRefused, match="r3_exception_exact_selection_required"):
        batch["run"]()
    assert not batch["calls"]
