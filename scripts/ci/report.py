#!/usr/bin/env python3
"""Small, strict native Actions summaries; inputs are data, never executable templates."""

from __future__ import annotations

import argparse
import html
import importlib.metadata
import json
import os
import platform
import re
import sys
import unicodedata
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

# Support the executable script and imports using the same reader module identity.
if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.ci.report_readers import MAX_REPORT_BYTES as MAX_REPORT_BYTES
from scripts.ci.report_readers import STATUSES as STATUSES
from scripts.ci.report_readers import SUITE_NAME as SUITE_NAME
from scripts.ci.report_readers import ReportError as ReportError
from scripts.ci.report_readers import number as number
from scripts.ci.report_readers import read_bytes as read_bytes
from scripts.ci.report_readers import read_coverage as read_coverage
from scripts.ci.report_readers import read_job_metrics as read_job_metrics
from scripts.ci.report_readers import read_json as read_json
from scripts.ci.report_readers import read_junit as read_junit
from scripts.ci.report_readers import read_measurement as read_measurement
from scripts.ci.report_readers import read_security as read_security
from scripts.ci.report_readers import status as status
from scripts.ci.report_readers import xml_number as xml_number

NAME = re.compile(r"[A-Za-z0-9_.-]{1,100}\Z")


def discovered_suites(root: Path | None = None) -> list[str]:
    """Every test module in the candidate must execute; a stale hand-written list cannot omit new domains."""
    root = root or Path(__file__).resolve().parents[2] / "tests"
    suites = ["tests." + path.stem for path in sorted(root.glob("test_*.py")) if path.is_file()]
    if not suites or any(not SUITE_NAME.fullmatch(suite) for suite in suites):
        raise ReportError("Candidate test modules are missing or malformed")
    return suites


def markdown(value: Any) -> str:
    """Keep contributor-controlled strings on one line and inert in Markdown/HTML."""
    clean = "".join(" " if unicodedata.category(char) in {"Cc", "Cf"} else char for char in str(value))
    clean = html.escape(clean, quote=True)
    return re.sub(r"([\\`*_{}\[\]()#+.!|>~-])", r"\\\1", clean)[:500]


def installed_versions() -> dict[str, str]:
    versions = {}
    for package in (
        "pytest",
        "pytest-cov",
        "coverage",
        "ruff",
        "mypy",
        "build",
        "bandit",
        "pip-audit",
        "django",
        "playwright",
    ):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            pass
    return versions


def link(label: str, url: str) -> str:
    """Only same-server HTTPS Actions URLs become active report links."""
    try:
        parsed = urlsplit(url)
        server = urlsplit(os.getenv("GITHUB_SERVER_URL", "https://github.com"))
    except ValueError:
        return markdown(url)
    if (
        parsed.scheme == "https"
        and parsed.netloc == server.netloc
        and not parsed.username
        and re.fullmatch(
            r"/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/actions/runs/[0-9]+(?:/artifacts/[0-9]+)?", parsed.path
        )
        and not parsed.query
        and not parsed.fragment
    ):
        return f"[{markdown(label)}]({quote(url, safe='/:')})"
    return markdown(url)


def pairs(values: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for value in values:
        name, separator, content = value.partition("=")
        if not separator or not NAME.fullmatch(name) or not content or name in parsed:
            raise ReportError("Arguments require unique NAME=VALUE pairs")
        parsed[name] = content
    return parsed


def identity() -> dict[str, Any]:
    repository, run_id = os.getenv("GITHUB_REPOSITORY"), os.getenv("GITHUB_RUN_ID")
    server = os.getenv("GITHUB_SERVER_URL", "https://github.com")
    return {
        "tested_sha": os.getenv("GITHUB_SHA") or None,
        "pr_head_sha": os.getenv("CI_PR_HEAD_SHA") or None,
        "ref": os.getenv("GITHUB_REF") or None,
        "event": os.getenv("GITHUB_EVENT_NAME") or None,
        "run_id": run_id or None,
        "run_attempt": os.getenv("GITHUB_RUN_ATTEMPT") or None,
        "run_url": f"{server}/{repository}/actions/runs/{run_id}" if repository and run_id else None,
        "repository": repository or None,
    }


def write_result(output: Path, data: dict[str, Any], summary: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_path:
        with Path(summary_path).open("a") as destination:
            destination.write(summary + "\n")
    else:
        print(summary)


def job(args: argparse.Namespace) -> int:
    errors: list[str] = []
    reports: dict[str, Any] = {"junit": None, "coverage": None, "security": [], "measurements": []}
    if args.expect_discovered_suites:
        try:
            args.expect_suite = sorted(set(args.expect_suite) | set(discovered_suites()))
        except ReportError as exc:
            errors.append(str(exc))
    if args.expect_suite and not args.junit:
        errors.append("Expected suites require a JUnit report")
    try:
        outcomes = {name: status(value) for name, value in pairs(args.outcome).items()}
        if not outcomes:
            raise ReportError("A job report requires actual check outcomes")
    except ReportError as exc:
        outcomes = {}
        errors.append(str(exc))
    for kind, path, parser in (("junit", args.junit, read_junit), ("coverage", args.coverage, read_coverage)):
        if path:
            try:
                reports[kind] = (
                    parser(Path(path), args.expect_suite) if kind == "junit" else parser(Path(path))
                )
            except ReportError as exc:
                errors.append(str(exc))
    try:
        security = pairs(args.security)
        artifacts = pairs(args.artifact)
        versions = pairs(args.tool_version)
    except ReportError as exc:
        security, artifacts, versions = {}, {}, {}
        errors.append(str(exc))
    for tool, path in security.items():
        try:
            reports["security"].append(read_security(tool, Path(path)))
        except ReportError as exc:
            errors.append(str(exc))
    for path in args.measurement:
        try:
            reports["measurements"].append(read_measurement(Path(path)))
        except ReportError as exc:
            errors.append(str(exc))
    if reports["junit"] and reports["junit"]["failed"]:
        errors.append("Required test report contains failing tests")
    if reports["junit"]:
        errors.extend(reports["junit"]["validation_errors"])
    if any(report["blocking_findings"] for report in reports["security"]):
        errors.append("Required security report contains blocking findings")
    if any(report["status"] != "PASS" for report in reports["measurements"]):
        errors.append("Required measurement contains a failed or unrun check")
    blocking = {name: outcome for name, outcome in outcomes.items() if outcome != "PASS"}
    result = "FAIL" if errors or blocking else "PASS"
    record = {
        "schema_version": 1,
        "kind": "job",
        "name": args.name,
        "result": result,
        "identity": identity(),
        "recorded_at": datetime.now(UTC).isoformat(),
        "environment": {
            "os": platform.system(),
            "architecture": platform.machine(),
            "python": platform.python_version(),
        },
        "tool_versions": {**installed_versions(), **versions},
        "outcomes": outcomes,
        "expected_suites": args.expect_suite,
        "required_reports": {
            "junit": bool(args.junit),
            "coverage": bool(args.coverage),
            "security": len(args.security),
            "measurements": len(args.measurement),
        },
        "reports": reports,
        "errors": errors,
        "baseline": None,
        "artifacts": artifacts,
    }
    lines = [f"### {markdown(args.name)}: {result}", "", "| Check | Actual outcome |", "|---|---|"]
    lines += [f"| {markdown(name)} | {value} |" for name, value in outcomes.items()]
    info = record["identity"]
    lines += [
        "",
        f"Tested SHA: {markdown(info['tested_sha'] or 'unavailable')}; "
        f"PR head: {markdown(info['pr_head_sha'] or 'unavailable')}; "
        f"ref: {markdown(info['ref'] or 'unavailable')}; event: {markdown(info['event'] or 'unavailable')}.",
        f"Runtime: Python {markdown(record['environment']['python'])}, "
        f"{markdown(record['environment']['os'])}/{markdown(record['environment']['architecture'])}.",
    ]
    if record["tool_versions"]:
        lines += [
            "Tool versions: "
            + "; ".join(
                f"{markdown(key)} {markdown(value)}" for key, value in record["tool_versions"].items()
            )
            + "."
        ]
    if info["run_url"]:
        lines += [f"Run: {link('Actions run', info['run_url'])}"]
    if reports["junit"]:
        tests = reports["junit"]
        duration = tests["duration_seconds"]
        lines += [
            f"Tests: {tests['passed']} passed, {tests['failed']} failed, {tests['skipped']} skipped; "
            f"suite duration {round(duration, 3) if duration is not None else 'unavailable'} seconds."
        ]
        lines += [f"- Failing test: {markdown(name)}" for name in tests["failures"]]
        lines += [
            f"- Required suite {markdown(name)}: {counts['executed']} executed, {counts['skipped']} skipped "
            f"of {counts['tests']} collected."
            for name, counts in tests["expected_suites"].items()
        ]
    if reports["coverage"]:
        coverage = reports["coverage"]
        lines += [
            f"Coverage: lines {coverage['line_percent']}%; branches "
            f"{str(coverage['branch_percent']) + '%' if coverage['branch_percent'] is not None else 'unavailable'}. "
            "Comparable baseline/delta: unavailable."
        ]
    for scan in reports["security"]:
        lines += [
            f"Security {markdown(scan['tool'])}: {scan['findings']} findings "
            f"({', '.join(f'{key}: {value}' for key, value in scan['by_severity'].items())})."
        ]
    for measurement in reports["measurements"]:
        values = [
            f"{markdown(key)}: {value}"
            for key, value in measurement.items()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        ]
        lines += [
            f"Measurement {markdown(measurement['source'])}: {measurement['status']}; "
            + "; ".join(values)
            + "."
        ]
    if errors or blocking:
        main_blocker = errors[0] if errors else f"{next(iter(blocking))}: {next(iter(blocking.values()))}"
        lines += [
            "",
            f"Main blocker: {markdown(main_blocker)}.",
            "Next action: inspect retained diagnostics and repair the failing check.",
        ]
        lines += [f"- Report error: {markdown(error)}" for error in errors[:10]]
    else:
        lines += [
            "",
            "Main blocker: none observed. Next action: review retained reports and the remaining required jobs.",
        ]
    lines += [
        "",
        "Retained diagnostics: "
        + (
            "; ".join(f"{markdown(name)}: {link(name, url)}" for name, url in artifacts.items())
            or "see this run's Actions artifacts"
        )
        + ".",
    ]
    write_result(Path(args.output), record, "\n".join(lines))
    return int(result != "PASS")


def aggregate(args: argparse.Namespace) -> int:
    errors: list[str] = []
    try:
        needs = json.loads(args.needs_json)
        if not isinstance(needs, dict):
            raise ReportError("Job outcomes must be a JSON object")
    except (json.JSONDecodeError, ReportError) as exc:
        needs = {}
        errors.append(f"Invalid required job outcomes: {exc}")
    outcomes = {}
    allowed = set(args.allow_skipped)
    required = set(args.required)
    if not required:
        errors.append("Aggregate requires an explicit nonempty required-job list")
    if allowed - required:
        errors.append("Allowed skips must name required jobs")
    for name in args.required:
        value = needs.get(name)
        try:
            outcomes[name] = status(value.get("result") if isinstance(value, dict) else value)
        except ReportError:
            outcomes[name] = "NOT RUN"
            errors.append(f"Required job outcome missing or malformed: {name}")
        if outcomes[name] != "PASS" and not (outcomes[name] == "SKIPPED" and name in allowed):
            errors.append(f"Required job {name}: {outcomes[name]}")
    records = []
    paths = list(args.report)
    if args.report_directory:
        discovered = sorted(Path(args.report_directory).glob("*/metrics.json"))
        if not discovered or len(discovered) > 20:
            errors.append("Required job metrics absent or exceed the 20-report bound")
        else:
            paths.extend(str(path) for path in discovered)
    seen = set()
    for path in paths:
        try:
            report = read_job_metrics(Path(path))
            for field in ("tested_sha", "run_id", "run_attempt", "repository", "event", "ref"):
                expected = identity()[field]
                if expected and report["identity"].get(field) != expected:
                    raise ReportError(f"Job metrics {field} differs from aggregate identity")
            environment = report["environment"]
            key = (report["name"], environment["os"], environment["python"])
            if key in seen:
                raise ReportError("Duplicate retained job environment")
            seen.add(key)
            records.append(report)
            if status(report.get("result")) != "PASS":
                errors.append(f"Retained job report failed: {report['name']}")
        except ReportError as exc:
            errors.append(str(exc))
    try:
        expected_counts = {}
        for value in args.expect_job_reports:
            name, separator, count = value.rpartition("=")
            if (
                not separator
                or not name
                or name in expected_counts
                or not re.fullmatch(r"[1-9][0-9]?", count)
            ):
                raise ReportError("Expected job reports require unique NAME=COUNT pairs")
            expected_counts[name] = int(count)
        actual_counts = dict(Counter(record["name"] for record in records))
        if expected_counts and actual_counts != expected_counts:
            errors.append("Required job report counts do not match the selected matrix")
    except ReportError as exc:
        errors.append(str(exc))
    result = "FAIL" if errors else "PASS"
    record = {
        "schema_version": 1,
        "kind": "aggregate",
        "result": result,
        "identity": identity(),
        "recorded_at": datetime.now(UTC).isoformat(),
        "outcomes": outcomes,
        "allowed_skips": sorted(allowed),
        "errors": errors,
        "job_reports": records,
    }
    summary = [f"### Required CI gates: {result}", "", "| Required job | Actual outcome |", "|---|---|"]
    summary += [
        f"| {markdown(name)} | {outcome}"
        + (" (intentional N/A)" if name in allowed and outcome == "SKIPPED" else "")
        + " |"
        for name, outcome in outcomes.items()
    ]
    summary += ["", f"Tested SHA: {markdown(record['identity']['tested_sha'] or 'unavailable')}."]
    summary += [
        "",
        "| Retained job | Runtime | Result | Tests passed / failed / skipped | Line / branch coverage |",
        "|---|---|---|---|---|",
    ]
    for retained in records:
        environment = retained.get("environment", {})
        native = retained.get("reports", {})
        native = native if isinstance(native, dict) else {}
        tests, coverage = native.get("junit"), native.get("coverage")
        counts = "unavailable"
        coverage_text = "unavailable"
        if isinstance(tests, dict):
            counts = " / ".join(
                markdown(tests.get(key, "unavailable")) for key in ("passed", "failed", "skipped")
            )
        if isinstance(coverage, dict):
            coverage_text = " / ".join(
                markdown(coverage.get(key) if coverage.get(key) is not None else "unavailable")
                for key in ("line_percent", "branch_percent")
            )
        summary.append(
            f"| {markdown(retained['name'])} | {markdown(environment.get('os', 'unavailable'))} "
            f"Python {markdown(environment.get('python', 'unavailable'))} | {markdown(retained['result'])} "
            f"| {counts} | {coverage_text} |"
        )
    summary += [f"- {markdown(error)}" for error in errors[:10]]
    summary += [
        "",
        "Next action: "
        + (
            "inspect the failed or missing required job and its retained reports."
            if errors
            else "review this exact candidate's retained job reports."
        ),
    ]
    write_result(Path(args.output), record, "\n".join(summary))
    return int(result != "PASS")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    job_parser = commands.add_parser("job")
    job_parser.add_argument("--name", required=True)
    job_parser.add_argument("--output", required=True)
    job_parser.add_argument("--outcome", action="append", default=[])
    job_parser.add_argument("--junit")
    job_parser.add_argument("--expect-suite", action="append", default=[])
    job_parser.add_argument("--expect-discovered-suites", action="store_true")
    job_parser.add_argument("--coverage")
    job_parser.add_argument("--security", action="append", default=[])
    job_parser.add_argument("--measurement", action="append", default=[])
    job_parser.add_argument("--artifact", action="append", default=[])
    job_parser.add_argument("--tool-version", action="append", default=[])
    job_parser.set_defaults(handler=job)
    aggregate_parser = commands.add_parser("aggregate")
    aggregate_parser.add_argument("--needs-json", required=True)
    aggregate_parser.add_argument("--required", action="append", default=[])
    aggregate_parser.add_argument("--allow-skipped", action="append", default=[])
    aggregate_parser.add_argument("--report", action="append", default=[])
    aggregate_parser.add_argument("--report-directory")
    aggregate_parser.add_argument("--expect-job-reports", action="append", default=[])
    aggregate_parser.add_argument("--output", required=True)
    aggregate_parser.set_defaults(handler=aggregate)
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
