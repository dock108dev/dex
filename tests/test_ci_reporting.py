"""Native job summaries, report readers and suite-execution regressions."""

import json

import pytest
from ci_reporting_helpers import fixture_json, junit, report
from ci_reporting_helpers import identity as identity


def test_job_records_actual_outcomes_tests_coverage_identity_and_summary(identity):
    suite = junit(identity / "junit.xml")
    coverage = fixture_json(
        identity / "coverage.json",
        {
            "totals": {
                "num_statements": 10,
                "covered_lines": 8,
                "num_branches": 4,
                "covered_branches": 3,
            }
        },
    )
    output = identity / "metrics.json"
    result = report.main(
        [
            "job",
            "--name",
            "behavior",
            "--outcome",
            "tests=success",
            "--junit",
            str(suite),
            "--coverage",
            str(coverage),
            "--output",
            str(output),
        ]
    )
    record = json.loads(output.read_text())
    assert result == 0
    assert record["result"] == "PASS"
    assert record["outcomes"] == {"tests": "PASS"}
    assert record["reports"]["junit"] == {
        "tests": 2,
        "passed": 1,
        "failed": 0,
        "skipped": 1,
        "duration_seconds": 0.5,
        "failures": [],
        "source": "junit.xml",
        "expected_suites": {},
        "validation_errors": [],
    }
    assert record["reports"]["coverage"]["line_percent"] == 80
    assert record["reports"]["coverage"]["branch_percent"] == 75
    assert record["reports"]["coverage"]["delta"] is None
    assert record["identity"]["tested_sha"] == "tested-merge-sha"
    assert record["identity"]["pr_head_sha"] == "pr-head-sha"
    assert record["identity"]["run_url"].endswith("/actions/runs/42")
    assert "1 passed, 0 failed, 1 skipped" in (identity / "summary.md").read_text()


@pytest.mark.parametrize(
    "native,expected",
    [
        ("failure", "FAIL"),
        ("skipped", "SKIPPED"),
        ("cancelled", "CANCELLED"),
        ("not-run", "NOT RUN"),
    ],
)
def test_required_unsuccessful_steps_remain_visible_and_fail(identity, native, expected):
    output = identity / "metrics.json"
    assert (
        report.main(["job", "--name", "check", "--outcome", f"check={native}", "--output", str(output)]) == 1
    )
    record = json.loads(output.read_text())
    assert record["outcomes"]["check"] == expected
    assert record["result"] == "FAIL"


@pytest.mark.parametrize(
    "contents",
    [
        None,
        "bad xml",
        '<testsuite tests="0"/>',
        '<testsuite tests="2"><testcase/></testsuite>',
        '<testsuite failures="1"><testcase/></testsuite>',
        "<!DOCTYPE xml><testsuite><testcase/></testsuite>",
    ],
)
def test_missing_malformed_zero_or_inconsistent_junit_cannot_pass(identity, contents):
    suite = identity / "suite.xml"
    if contents is not None:
        suite.write_text(contents)
    output = identity / "metrics.json"
    assert (
        report.main(
            [
                "job",
                "--name",
                "tests",
                "--outcome",
                "tests=success",
                "--junit",
                str(suite),
                "--output",
                str(output),
            ]
        )
        == 1
    )
    record = json.loads(output.read_text())
    assert record["reports"]["junit"] is None
    assert record["errors"]


def test_failing_junit_contradicting_success_step_fails(identity):
    suite = junit(identity / "suite.xml", failure=True)
    output = identity / "metrics.json"
    assert (
        report.main(
            [
                "job",
                "--name",
                "tests",
                "--outcome",
                "tests=success",
                "--junit",
                str(suite),
                "--output",
                str(output),
            ]
        )
        == 1
    )
    record = json.loads(output.read_text())
    assert record["reports"]["junit"]["failed"] == 1
    assert record["reports"]["junit"]["failures"] == ["suite.alpha"]
    assert "raw log never rendered" not in (identity / "summary.md").read_text()


@pytest.mark.parametrize(
    "cases,expected_suite,error",
    [
        (
            '<testcase classname="tests.test_required"><skipped/></testcase>',
            None,
            "all collected cases skipped",
        ),
        ('<testcase classname="tests.test_other"/>', "tests.test_required", "missing from test report"),
        (
            '<testcase classname="tests.test_required"><skipped/></testcase><testcase classname="tests.test_other"/>',
            "tests.test_required",
            "all cases skipped",
        ),
        ('<testcase classname="tests.test_b10"/>', "tests.test_b1", "missing from test report"),
    ],
)
def test_zero_executed_or_required_family_missing_cannot_pass(identity, cases, expected_suite, error):
    path = identity / "junit.xml"
    path.write_text(f"<testsuite>{cases}</testsuite>")
    output = identity / "metrics.json"
    arguments = [
        "job",
        "--name",
        "tests",
        "--outcome",
        "tests=success",
        "--junit",
        str(path),
        "--output",
        str(output),
    ]
    if expected_suite:
        arguments += ["--expect-suite", expected_suite]
    assert report.main(arguments) == 1
    record = json.loads(output.read_text())
    assert any(error in value for value in record["errors"])
    assert record["reports"]["junit"]["tests"] > 0
    if expected_suite:
        assert record["expected_suites"] == [expected_suite]
        assert record["reports"]["junit"]["expected_suites"][expected_suite]["executed"] == 0
    else:
        assert record["reports"]["junit"]["skipped"] == 1


def test_expected_suite_exact_and_dotted_class_matches_retain_execution_and_skip_counts(identity):
    path = identity / "junit.xml"
    path.write_text(
        '<testsuite><testcase classname="tests.test_b1"/>'
        '<testcase classname="tests.test_b1.TestGroup"><skipped/></testcase>'
        '<testcase classname="tests.test_b10"/><testcase classname="tests.test_second"/></testsuite>'
    )
    output = identity / "metrics.json"
    assert (
        report.main(
            [
                "job",
                "--name",
                "tests",
                "--outcome",
                "tests=success",
                "--junit",
                str(path),
                "--expect-suite",
                "tests.test_b1",
                "--expect-suite",
                "tests.test_second",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    families = json.loads(output.read_text())["reports"]["junit"]["expected_suites"]
    assert families["tests.test_b1"] == {"tests": 2, "skipped": 1, "executed": 1}
    assert families["tests.test_second"] == {"tests": 1, "skipped": 0, "executed": 1}


def test_coverage_xml_and_invalid_required_coverage(identity):
    xml = identity / "coverage.xml"
    xml.write_text('<coverage lines-valid="10" lines-covered="9" branches-valid="0" branches-covered="0"/>')
    assert report.read_coverage(xml)["line_percent"] == 90
    assert report.read_coverage(xml)["branch_percent"] is None
    for totals in [
        {},
        {"num_statements": 0, "covered_lines": 0},
        {"num_statements": 1, "covered_lines": 2},
        {"num_statements": True, "covered_lines": 0},
    ]:
        bad = fixture_json(identity / "bad.json", {"totals": totals})
        with pytest.raises(report.ReportError):
            report.read_coverage(bad)


def test_security_counts_match_policy_and_preserve_unknown_severity(identity):
    bandit = fixture_json(
        identity / "bandit.json",
        {
            "errors": [],
            "results": [
                {"issue_severity": "LOW", "issue_confidence": "HIGH"},
                {"issue_severity": "HIGH", "issue_confidence": "LOW"},
                {"issue_severity": "MEDIUM", "issue_confidence": "HIGH"},
            ],
        },
    )
    scan = report.read_security("bandit", bandit)
    assert scan["findings"] == 3 and scan["blocking_findings"] == 1
    audit = fixture_json(
        identity / "audit.json", {"dependencies": [{"name": "example", "vulns": [{"id": "PYSEC-test"}]}]}
    )
    assert report.read_security("pip-audit", audit)["by_severity"]["unknown"] == 1
    leaks = fixture_json(identity / "leaks.json", [{"RuleID": "example", "Secret": "should-never-be-copied"}])
    scan = report.read_security("gitleaks", leaks)
    assert "should-never-be-copied" not in json.dumps(scan)
    assert scan["blocking_findings"] == 1


@pytest.mark.parametrize(
    "tool,data",
    [
        ("bandit", {"results": [], "errors": [{"reason": "tool unavailable"}]}),
        ("bandit", {}),
        ("pip-audit", {"dependencies": [{}]}),
        ("gitleaks", {}),
    ],
)
def test_security_outages_are_not_zero_findings(identity, tool, data):
    path = fixture_json(identity / "scan.json", data)
    output = identity / "metrics.json"
    assert (
        report.main(
            [
                "job",
                "--name",
                "security",
                "--outcome",
                "scan=success",
                "--security",
                f"{tool}={path}",
                "--output",
                str(output),
            ]
        )
        == 1
    )
    record = json.loads(output.read_text())
    assert record["reports"]["security"] == []
    assert record["errors"]


def test_low_bandit_findings_are_reported_without_weakening_defined_policy(identity):
    path = fixture_json(
        identity / "scan.json",
        {
            "errors": [],
            "results": [
                {"issue_severity": "LOW", "issue_confidence": "HIGH"},
            ],
        },
    )
    assert (
        report.main(
            [
                "job",
                "--name",
                "security",
                "--outcome",
                "scan=success",
                "--security",
                f"bandit={path}",
                "--output",
                str(identity / "metrics.json"),
            ]
        )
        == 0
    )


def test_measurement_child_failure_and_nonfinite_metrics_are_rejected(identity):
    path = fixture_json(
        identity / "smoke.json",
        {"status": "PASS", "wheel_bytes": 300, "checks": [{"name": "import", "status": "FAIL"}]},
    )
    with pytest.raises(report.ReportError, match="failed or unrun"):
        report.read_measurement(path)
    path.write_text('{"status":"PASS","duration_seconds":NaN}')
    with pytest.raises(report.ReportError, match="Malformed JSON"):
        report.read_measurement(path)


def test_optional_measurements_preserve_null_instead_of_zero(identity):
    path = fixture_json(
        identity / "smoke.json", {"status": "PASS", "sdist_bytes": None, "sdist_file_count": None}
    )
    measured = report.read_measurement(path)
    assert measured["sdist_bytes"] is None and measured["sdist_file_count"] is None


def test_summary_escapes_untrusted_markdown_control_and_html(identity):
    name = "[click](javascript:alert(1))|<script>\nnew row\u202e"
    report.main(
        ["job", "--name", name, "--outcome", "tests=success", "--output", str(identity / "metrics.json")]
    )
    summary = (identity / "summary.md").read_text()
    assert "<script>" not in summary and "\u202e" not in summary
    assert "\\[click\\]" in summary and "\\|" in summary
    assert "\nnew row" not in summary


def test_only_validated_actions_urls_become_active_summary_links(identity):
    assert report.link("run", "https://github.com/owner/repo/actions/runs/42").startswith("[run](https:")
    for value in (
        "javascript:alert(1)",
        "https://example.com/owner/repo/actions/runs/42",
        "https://github.com/owner/repo/actions/runs/42?untrusted=1",
        "https://github.com/owner/repo/actions/runs/42)\n[unsafe](javascript:1)",
    ):
        assert not report.link("run", value).startswith("[run](")


def test_browser_and_security_measurement_schemas_and_conflicting_statuses(identity):
    browser = fixture_json(
        identity / "browser.json", {"result": "PASS", "state_count": 2, "states": [{}, {}]}
    )
    assert report.read_measurement(browser)["status"] == "PASS"
    security = fixture_json(
        identity / "security.json", {"outcome": "PASS", "tools": {"bandit": {"outcome": "PASS"}}}
    )
    assert report.read_measurement(security)["status"] == "PASS"
    fixture_json(security, {"outcome": "PASS", "tools": {"bandit": {"outcome": "FAIL"}}})
    with pytest.raises(report.ReportError, match="failed or unrun tool"):
        report.read_measurement(security)
    fixture_json(browser, {"status": "PASS", "result": "FAIL"})
    with pytest.raises(report.ReportError, match="actual status"):
        report.read_measurement(browser)


def test_new_candidate_module_cannot_be_omitted_from_successful_test_report(identity, monkeypatch):
    root = identity / "tests"
    root.mkdir()
    (root / "test_existing.py").touch()
    (root / "test_shopping_new.py").touch()
    discovered = report.discovered_suites(root)
    monkeypatch.setattr(report, "discovered_suites", lambda: discovered)
    native = identity / "native.xml"
    native.write_text('<testsuite><testcase classname="tests.test_existing"/></testsuite>')
    output = identity / "job.json"
    args = [
        "job",
        "--name",
        "Behavior",
        "--outcome",
        "tests=success",
        "--expect-discovered-suites",
        "--junit",
        str(native),
        "--output",
        str(output),
    ]
    assert report.main(args) == 1
    assert "tests.test_shopping_new" in str(json.loads(output.read_text())["errors"])
    native.write_text(
        '<testsuite><testcase classname="tests.test_existing"/><testcase classname="tests.test_shopping_new"/></testsuite>'
    )
    assert report.main(args) == 0
