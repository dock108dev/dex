"""Bounded historical Actions health and runner-resource evidence."""

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from test_ci_reporting import identity as identity
from test_ci_reporting import load_script

health = load_script("health")

NOW = datetime(2026, 10, 8, 12, tzinfo=UTC)


def run_fixture(
    index, *, event="pull_request", branch="topic", conclusion="success", attempt=1, seconds=None
):
    start = NOW - timedelta(hours=index + 1)
    run = {
        "id": index,
        "workflow_id": 10,
        "name": "checks",
        "status": "completed",
        "conclusion": conclusion,
        "event": event,
        "head_branch": branch,
        "head_sha": f"sha-{index}",
        "run_attempt": attempt,
        "created_at": (start - timedelta(seconds=30)).isoformat(),
        "run_started_at": start.isoformat(),
    }
    if seconds is not None:
        run["completed_at"] = (start + timedelta(seconds=seconds)).isoformat()
    return run


def test_health_separates_events_cancellations_and_first_attempt_recovery():
    first = run_fixture(1, attempt=2)
    first["first_attempt"] = {"conclusion": "failure"}
    missing = run_fixture(2, attempt=2)
    runs = [
        first,
        missing,
        run_fixture(3, conclusion="cancelled"),
        run_fixture(4, event="push", branch="main"),
        run_fixture(5, event="schedule", branch="main"),
    ]
    metrics = health.analyze({"workflow_runs": runs}, NOW, "main", 30)
    pr = metrics["groups"]["pull_request"]["aggregate"]
    assert pr["sample_size"] == 3
    assert pr["first_attempt_pass_percent"] == 0
    assert pr["first_attempt_eligible"] == 1 and pr["first_attempt_missing"] == 1
    assert pr["first_attempt_cancelled"] == 1 and pr["latest_conclusions"]["cancelled"] == 1
    assert pr["rerun_runs"] == 2 and pr["recovered_after_failure"] == 1
    assert pr["suspected_flakes"] is None
    assert metrics["groups"]["primary_branch"]["aggregate"]["sample_size"] == 1
    assert metrics["groups"]["other"]["aggregate"]["sample_size"] == 1


def test_health_is_bounded_by_window_and_count_and_p95_has_minimum_sample():
    runs = [run_fixture(index, seconds=index + 1) for index in range(35)]
    runs += [
        {**run_fixture(2000), "created_at": (NOW - timedelta(days=31)).isoformat()},
        {**run_fixture(2), "status": "in_progress"},
    ]
    record = health.analyze({"workflow_runs": runs}, NOW, "main", 30)
    assert record["sample_size"] == 30
    assert record["excluded_incomplete_or_outside_window"] == 2
    speed = record["groups"]["pull_request"]["aggregate"]["observed_duration"][0]
    assert speed["median"] == 15.5 and speed["p95"] == 29
    smaller = health.analyze({"workflow_runs": runs[:4]}, NOW, "main", 30)
    speed = smaller["groups"]["pull_request"]["aggregate"]["observed_duration"][0]
    assert speed["median"] is None and speed["p95"] is None


def test_health_updated_at_does_not_invent_duration_and_jobs_require_complete_snapshot():
    run = run_fixture(1)
    run["updated_at"] = NOW.isoformat()
    assert health.duration(run) == (None, None)
    end = NOW.isoformat()
    run["jobs_snapshot"] = {"total_count": 2, "jobs": [{"completed_at": end}]}
    assert health.duration(run) == (None, None)
    run["jobs_snapshot"] = {"total_count": 1, "jobs": [{"completed_at": end}]}
    value, method = health.duration(run)
    assert value == 7200 and "observed span" in method
    assert health.timestamp("2026-10-08T12:00:00") is None


def test_observed_runner_minutes_sum_parallel_execution_and_include_started_cancellation():
    start = NOW - timedelta(minutes=5)
    jobs = [
        {
            "conclusion": "success",
            "started_at": start.isoformat(),
            "completed_at": (start + timedelta(minutes=1)).isoformat(),
        },
        {
            "conclusion": "failure",
            "started_at": start.isoformat(),
            "completed_at": (start + timedelta(minutes=2)).isoformat(),
        },
        {
            "conclusion": "cancelled",
            "started_at": start.isoformat(),
            "completed_at": (start + timedelta(seconds=30)).isoformat(),
        },
        {"conclusion": "skipped", "started_at": None, "completed_at": None},
        {"conclusion": "cancelled", "started_at": None, "completed_at": None},
    ]
    run = {"jobs_snapshot": {"total_count": len(jobs), "jobs": jobs}}
    assert health.resource_observation(run) == (3.5, 3, None)
    assert health.resource_observation({"jobs_snapshot": {"total_count": 0, "jobs": []}}) == (0, 0, None)


@pytest.mark.parametrize(
    "snapshot",
    [
        None,
        {"total_count": 2, "jobs": [{"conclusion": "skipped"}]},
        {"total_count": True, "jobs": [{"conclusion": "skipped"}]},
        {"total_count": 1, "jobs": [{"conclusion": "success", "started_at": None, "completed_at": None}]},
        {
            "total_count": 1,
            "jobs": [{"conclusion": "cancelled", "started_at": NOW.isoformat(), "completed_at": None}],
        },
        {
            "total_count": 1,
            "jobs": [
                {
                    "conclusion": "success",
                    "started_at": NOW.isoformat(),
                    "completed_at": (NOW - timedelta(seconds=1)).isoformat(),
                }
            ],
        },
        {
            "total_count": 1,
            "jobs": [
                {
                    "conclusion": "success",
                    "status": "in_progress",
                    "started_at": NOW.isoformat(),
                    "completed_at": NOW.isoformat(),
                }
            ],
        },
    ],
)
def test_missing_partial_or_invalid_job_resources_remain_null(snapshot):
    value, count, reason = health.resource_observation({"jobs_snapshot": snapshot})
    assert value is None and count is None and reason


def test_creation_to_run_start_is_first_attempt_proxy_with_nulls_for_reruns_or_bad_timestamps():
    run = run_fixture(1)
    assert health.start_delay(run) == 30
    for changed in (
        {"run_attempt": 2},
        {"run_started_at": None},
        {"run_started_at": (NOW - timedelta(days=20)).isoformat()},
    ):
        assert health.start_delay({**run, **changed}) is None


def test_resource_metrics_show_incomplete_samples_and_never_mix_workflow_identity():
    runs = [run_fixture(index) for index in range(5)]
    for run in runs[:4]:
        start = health.timestamp(run["run_started_at"])
        run["jobs_snapshot"] = {
            "total_count": 1,
            "jobs": [
                {
                    "conclusion": "success",
                    "started_at": start.isoformat(),
                    "completed_at": (start + timedelta(minutes=1)).isoformat(),
                }
            ],
        }
    grouped = health.analyze({"workflow_runs": runs}, NOW, "main", 30)["groups"]["pull_request"]
    metrics = grouped["by_workflow"]["10"]
    assert metrics["runner_minutes"] is None
    assert metrics["observed_runner_minutes"]["measured_subtotal"] == 4
    assert metrics["observed_runner_minutes"]["sample_size"] == 4
    assert metrics["observed_runner_minutes"]["unavailable_runs"] == 1
    assert metrics["creation_to_run_start_delay"]["median"] == 30
    assert metrics["queue_seconds"] is None and metrics["billing_cost"] is None
    runs[0]["workflow_id"] = 20
    grouped = health.analyze({"workflow_runs": runs}, NOW, "main", 30)["groups"]["pull_request"]
    assert grouped["aggregate"]["observed_runner_minutes"] is None
    assert grouped["aggregate"]["creation_to_run_start_delay"] is None
    assert set(grouped["by_workflow"]) == {"10", "20"}


def test_cancelled_run_retains_observed_resources_and_delay_without_duration_statistics():
    run = run_fixture(1, conclusion="cancelled", seconds=60)
    start = health.timestamp(run["run_started_at"])
    run["jobs_snapshot"] = {
        "total_count": 1,
        "jobs": [
            {
                "conclusion": "cancelled",
                "started_at": start.isoformat(),
                "completed_at": (start + timedelta(seconds=60)).isoformat(),
            }
        ],
    }
    record = health.analyze({"workflow_runs": [run]}, NOW, "main", 30)
    retained = record["runs"][0]
    assert retained["observed_runner_minutes"] == 1
    assert retained["creation_to_run_start_seconds"] == 30
    metrics = record["groups"]["pull_request"]["by_workflow"]["10"]
    assert metrics["observed_duration"] == []
    assert metrics["runner_minutes"] == 1


def test_health_cli_missing_snapshot_and_invalid_limits_fail(identity):
    output = identity / "health.json"
    assert health.main(["--snapshot", str(identity / "missing.json"), "--output", str(output)]) == 1
    assert json.loads(output.read_text())["status"] == "UNAVAILABLE"
    with pytest.raises(SystemExit):
        health.main(["--limit", "31", "--output", str(output)])


def test_live_sampling_read_only_bounded_and_first_attempt_fetches(monkeypatch):
    runs = [run_fixture(index, attempt=2 if index == 1 else 1) for index in range(30)]
    calls = []

    def api(repository, suffix, fields=None):
        calls.append((repository, suffix, fields))
        if suffix == "actions/runs":
            return {"workflow_runs": runs}
        if suffix.endswith("/jobs"):
            return {"total_count": 0, "jobs": []}
        return {"conclusion": "failure"}

    monkeypatch.setattr(health, "gh_api", api)
    payload, errors = health.load_live("owner/repo", NOW, 30)
    assert len(calls) == 32 and not errors
    assert calls[0][2]["per_page"] == "30" and calls[0][2]["status"] == "completed"
    assert calls[0][2]["created"].startswith(">=")
    assert payload["workflow_runs"][1]["first_attempt"]["conclusion"] == "failure"


def test_gh_command_uses_argument_vector_get_and_finite_timeout(monkeypatch):
    observed = []

    def process(command, **kwargs):
        observed.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout='{"workflow_runs":[]}', stderr="")

    monkeypatch.setattr(health.subprocess, "run", process)
    assert health.gh_api("owner/repo", "actions/runs", {"created": ">=timestamp"}) == {"workflow_runs": []}
    command, kwargs = observed[0]
    assert command[:4] == ["gh", "api", "--method", "GET"]
    assert kwargs["timeout"] == 25 and "shell" not in kwargs
