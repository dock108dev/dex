"""Required-job aggregation, matrix identity and false-green regressions."""

import json

import pytest
from ci_reporting_helpers import fixture_json, junit, report
from ci_reporting_helpers import identity as identity


@pytest.mark.parametrize(
    "needs,expected",
    [
        ({"quality": {"result": "success"}, "tests": {"result": "success"}}, 0),
        ({"quality": {"result": "success"}, "tests": {"result": "failure"}}, 1),
        ({"quality": {"result": "success"}, "tests": {"result": "skipped"}}, 1),
        ({"quality": {"result": "success"}, "tests": {"result": "cancelled"}}, 1),
        ({"quality": {"result": "success"}}, 1),
        ({"quality": {"result": "success"}, "tests": {"result": "unknown"}}, 1),
    ],
)
def test_aggregate_requires_all_actual_child_job_results(identity, needs, expected):
    assert (
        report.main(
            [
                "aggregate",
                "--needs-json",
                json.dumps(needs),
                "--required",
                "quality",
                "--required",
                "tests",
                "--output",
                str(identity / "aggregate.json"),
            ]
        )
        == expected
    )


def test_explicit_intentional_skip_is_allowed_but_missing_report_is_not(identity):
    arguments = [
        "aggregate",
        "--needs-json",
        '{"optional":{"result":"skipped"}}',
        "--required",
        "optional",
        "--allow-skipped",
        "optional",
        "--output",
        str(identity / "aggregate.json"),
    ]
    assert report.main(arguments) == 0
    assert report.main(arguments + ["--report", str(identity / "missing.json")]) == 1


def test_aggregate_rejects_cross_candidate_metrics(identity):
    path = fixture_json(
        identity / "metrics.json",
        {
            "schema_version": 1,
            "kind": "job",
            "name": "tests",
            "result": "PASS",
            "identity": {"tested_sha": "stale-sha"},
        },
    )
    assert (
        report.main(
            [
                "aggregate",
                "--needs-json",
                '{"tests":{"result":"success"}}',
                "--required",
                "tests",
                "--report",
                str(path),
                "--output",
                str(identity / "aggregate.json"),
            ]
        )
        == 1
    )


def retained_job(identity, directory, name="Behavior", runtime="3.12"):
    path = directory / "metrics.json"
    assert (
        report.main(
            [
                "job",
                "--name",
                name,
                "--outcome",
                "tests=success",
                "--junit",
                str(junit(identity / "native.xml")),
                "--output",
                str(path),
            ]
        )
        == 0
    )
    data = json.loads(path.read_text())
    data["environment"]["python"] = runtime
    fixture_json(path, data)
    return path


def aggregate_reports(identity, directory, count=1):
    return report.main(
        [
            "aggregate",
            "--required",
            "behavior",
            "--needs-json",
            '{"behavior":{"result":"success"}}',
            "--report-directory",
            str(directory),
            "--expect-job-reports",
            f"Behavior={count}",
            "--output",
            str(identity / "aggregate.json"),
        ]
    )


def test_aggregate_retains_each_matrix_result_and_rejects_missing_duplicate_or_stale_attempt(
    identity, monkeypatch
):
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    children = identity / "children"
    first = retained_job(identity, children / "one")
    second = retained_job(identity, children / "two", runtime="3.14")
    assert aggregate_reports(identity, children, 2) == 0
    summary = (identity / "summary.md").read_text()
    assert "1 / 0 / 1" in summary and "3\\.14" in summary
    assert aggregate_reports(identity, children, 3) == 1
    data = json.loads(second.read_text())
    data["environment"]["python"] = "3.12"
    fixture_json(second, data)
    assert aggregate_reports(identity, children, 2) == 1
    second.unlink()
    data = json.loads(first.read_text())
    data["identity"]["run_attempt"] = "1"
    fixture_json(first, data)
    assert aggregate_reports(identity, children) == 1
    first.unlink()
    assert aggregate_reports(identity, children) == 1


@pytest.mark.parametrize(
    "tamper",
    ["missing-native", "failed-native", "counts", "environment", "coverage", "outcomes", "empty-required"],
)
def test_successful_child_outcome_cannot_hide_malformed_or_contradictory_retained_report(identity, tamper):
    children = identity / "children"
    path = retained_job(identity, children / "one")
    data = json.loads(path.read_text())
    if tamper == "missing-native":
        data.pop("reports")
    elif tamper == "empty-required":
        data["reports"]["junit"] = None
    elif tamper == "failed-native":
        data["reports"]["junit"]["failed"] = 1
        data["reports"]["junit"]["passed"] = 0
    elif tamper == "counts":
        data["reports"]["junit"]["tests"] = 3
    elif tamper == "environment":
        data["environment"] = {}
    elif tamper == "coverage":
        data["reports"]["coverage"] = {
            "lines": 10,
            "covered_lines": 8,
            "line_percent": 100,
            "branches": 0,
            "covered_branches": 0,
            "branch_percent": None,
        }
    else:
        data["outcomes"]["tests"] = "cancelled"
    fixture_json(path, data)
    assert aggregate_reports(identity, children) == 1
    assert json.loads((identity / "aggregate.json").read_text())["errors"]
