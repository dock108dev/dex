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
from scripts.ci.report_readers import read_json as read_json
from scripts.ci.report_readers import read_junit as read_junit
from scripts.ci.report_readers import read_measurement as read_measurement
from scripts.ci.report_readers import read_security as read_security
from scripts.ci.report_readers import status as status
from scripts.ci.report_readers import xml_number as xml_number

NAME = re.compile(r"[A-Za-z0-9_.-]{1,100}\Z")


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
    for path in args.report:
        try:
            report = read_json(Path(path))
            if (
                not isinstance(report, dict)
                or report.get("schema_version") != 1
                or report.get("kind") != "job"
            ):
                raise ReportError("Invalid job metrics record")
            if status(report.get("result")) != "PASS":
                raise ReportError(f"Retained job report failed: {report.get('name')}")
            candidate = identity()["tested_sha"]
            if not isinstance(report.get("identity"), dict):
                raise ReportError("Invalid retained job candidate identity")
            if candidate and report["identity"].get("tested_sha") != candidate:
                raise ReportError("Job metrics candidate differs from aggregate candidate")
            records.append(report)
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
    aggregate_parser.add_argument("--output", required=True)
    aggregate_parser.set_defaults(handler=aggregate)
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    sys.exit(main())
