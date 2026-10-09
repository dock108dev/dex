"""Strict, bounded readers of native CI result files; no rendering or process I/O."""

from __future__ import annotations

import json
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

STATUSES = {
    "success": "PASS",
    "pass": "PASS",
    "failure": "FAIL",
    "fail": "FAIL",
    "skipped": "SKIPPED",
    "cancelled": "CANCELLED",
    "not-run": "NOT RUN",
    "not run": "NOT RUN",
}
SUITE_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*\Z")
MAX_REPORT_BYTES = 4 * 1024 * 1024


class ReportError(ValueError):
    """A required result was absent, malformed, or contradicted a successful step."""


def status(value: Any) -> str:
    if not isinstance(value, str) or value.lower() not in STATUSES:
        raise ReportError(f"Unsupported outcome: {value!r}")
    return STATUSES[value.lower()]


def read_bytes(path: Path) -> bytes:
    try:
        if path.stat().st_size > MAX_REPORT_BYTES:
            raise ReportError(f"Report exceeds {MAX_REPORT_BYTES} bytes: {path.name}")
        return path.read_bytes()
    except OSError as exc:
        raise ReportError(f"Required report unavailable: {path.name} ({exc.strerror})") from exc


def read_json(path: Path) -> Any:
    try:
        return json.loads(
            read_bytes(path), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value))
        )
    except (ValueError, UnicodeDecodeError) as exc:
        raise ReportError(f"Malformed JSON report: {path.name}") from exc


def number(value: Any, label: str, *, integer: bool = False) -> int | float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise ReportError(f"Invalid {label}")
    if integer and int(value) != value:
        raise ReportError(f"Invalid integer {label}")
    return int(value) if integer else value


def xml_number(value: str | None, label: str, *, integer: bool = False) -> int | float:
    try:
        return number(float(value), label, integer=integer)
    except (TypeError, ValueError) as exc:
        raise ReportError(f"Invalid {label}") from exc


def read_junit(path: Path, expected_suites: list[str] | None = None) -> dict[str, Any]:
    expected_suites = expected_suites or []
    if any(not SUITE_NAME.fullmatch(name) for name in expected_suites):
        raise ReportError("Expected suite must be a dotted Python classname/module prefix")
    try:
        raw = read_bytes(path)
        if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
            raise ReportError("JUnit document types/entities are unsupported")
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ReportError(f"Malformed JUnit report: {path.name}") from exc
    if root.tag not in {"testsuite", "testsuites"}:
        raise ReportError("JUnit root must be testsuite or testsuites")
    cases = list(root.iter("testcase"))
    if not cases:
        raise ReportError("Required test report collected zero tests")
    if any(
        case.find("skipped") is not None
        and (case.find("failure") is not None or case.find("error") is not None)
        for case in cases
    ):
        raise ReportError("JUnit contains contradictory failure/skipped cases")
    failed = sum(case.find("failure") is not None or case.find("error") is not None for case in cases)
    skipped = sum(case.find("skipped") is not None for case in cases)
    if failed + skipped > len(cases):
        raise ReportError("JUnit contains contradictory failure/skipped cases")
    for suite in ([root] if root.tag == "testsuites" else []) + list(root.iter("testsuite")):
        suite_cases = list(suite.iter("testcase"))
        observed = {
            "tests": len(suite_cases),
            "failures": sum(case.find("failure") is not None for case in suite_cases),
            "errors": sum(case.find("error") is not None for case in suite_cases),
            "skipped": sum(case.find("skipped") is not None for case in suite_cases),
        }
        for attribute in ("tests", "failures", "errors", "skipped"):
            if attribute in suite.attrib:
                count = xml_number(suite.attrib[attribute], f"JUnit {attribute}", integer=True)
                if count != observed[attribute]:
                    raise ReportError("JUnit declared counts differ from recorded test cases")
        if "time" in suite.attrib:
            xml_number(suite.attrib["time"], "JUnit suite duration")
    durations = [
        xml_number(case.attrib["time"], "JUnit test duration") for case in cases if "time" in case.attrib
    ]
    suite_times = [
        xml_number(suite.attrib["time"], "JUnit suite duration")
        for suite in ([root] if root.tag == "testsuite" else root.findall("testsuite"))
        if "time" in suite.attrib
    ]
    duration = sum(suite_times) if suite_times else sum(durations) if len(durations) == len(cases) else None
    validation_errors = []
    if len(cases) == skipped:
        validation_errors.append("Required test report executed zero tests (all collected cases skipped)")
    families = {}
    for name in expected_suites:
        matched = [
            case
            for case in cases
            if case.get("classname") == name or case.get("classname", "").startswith(name + ".")
        ]
        family_skipped = sum(case.find("skipped") is not None for case in matched)
        families[name] = {
            "tests": len(matched),
            "skipped": family_skipped,
            "executed": len(matched) - family_skipped,
        }
        if not matched:
            validation_errors.append(f"Required suite missing from test report: {name}")
        elif len(matched) == family_skipped:
            validation_errors.append(f"Required suite executed zero tests (all cases skipped): {name}")
    return {
        "tests": len(cases),
        "passed": len(cases) - failed - skipped,
        "failed": failed,
        "skipped": skipped,
        "duration_seconds": duration,
        "failures": [
            f"{case.attrib.get('classname', '')}.{case.attrib.get('name', 'unnamed')}".strip(".")[:500]
            for case in cases
            if case.find("failure") is not None or case.find("error") is not None
        ][:10],
        "source": path.name,
        "expected_suites": families,
        "validation_errors": validation_errors,
    }


def read_coverage(path: Path) -> dict[str, Any]:
    if path.suffix.lower() == ".xml":
        try:
            raw = read_bytes(path)
            if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
                raise ReportError("Coverage document types/entities are unsupported")
            root = ET.fromstring(raw)
        except ET.ParseError as exc:
            raise ReportError(f"Malformed coverage XML: {path.name}") from exc
        if root.tag != "coverage":
            raise ReportError("Coverage XML root must be coverage")
        lines = xml_number(root.get("lines-valid"), "coverage lines", integer=True)
        covered = xml_number(root.get("lines-covered"), "covered lines", integer=True)
        branches = xml_number(root.get("branches-valid"), "coverage branches", integer=True)
        covered_branches = xml_number(root.get("branches-covered"), "covered branches", integer=True)
    else:
        data = read_json(path)
        if not isinstance(data, dict) or not isinstance(data.get("totals"), dict):
            raise ReportError("Coverage JSON must contain totals")
        totals = data["totals"]
        lines = number(totals.get("num_statements"), "coverage lines", integer=True)
        covered = number(totals.get("covered_lines"), "covered lines", integer=True)
        branches = number(totals.get("num_branches", 0), "coverage branches", integer=True)
        covered_branches = number(totals.get("covered_branches", 0), "covered branches", integer=True)
    if lines == 0 or covered > lines or covered_branches > branches:
        raise ReportError("Coverage report has zero statements or inconsistent totals")
    return {
        "lines": lines,
        "covered_lines": covered,
        "line_percent": round(100 * covered / lines, 3),
        "branches": branches,
        "covered_branches": covered_branches,
        "branch_percent": round(100 * covered_branches / branches, 3) if branches else None,
        "source": path.name,
        "baseline": None,
        "delta": None,
    }


def read_security(tool: str, path: Path) -> dict[str, Any]:
    data = read_json(path)
    severities: dict[str, int] = {key: 0 for key in ("critical", "high", "medium", "low", "unknown")}
    blocking_findings = 0
    if tool == "bandit":
        if not isinstance(data, dict) or not isinstance(data.get("results"), list):
            raise ReportError("Bandit report must contain results")
        if not isinstance(data.get("errors"), list) or data["errors"]:
            raise ReportError("Bandit scan errors are unavailable security evidence")
        for finding in data["results"]:
            if (
                not isinstance(finding, dict)
                or finding.get("issue_severity") not in {"HIGH", "MEDIUM", "LOW"}
                or finding.get("issue_confidence") not in {"HIGH", "MEDIUM", "LOW"}
            ):
                raise ReportError("Invalid Bandit finding")
            severities[finding["issue_severity"].lower()] += 1
            blocking_findings += (
                finding["issue_severity"] in {"HIGH", "MEDIUM"} and finding["issue_confidence"] == "HIGH"
            )
    elif tool == "pip-audit":
        dependencies = data.get("dependencies") if isinstance(data, dict) else data
        if not isinstance(dependencies, list):
            raise ReportError("pip-audit report must contain dependencies")
        for dependency in dependencies:
            if not isinstance(dependency, dict) or not isinstance(dependency.get("vulns"), list):
                raise ReportError("Invalid pip-audit dependency")
            if dependency.get("skip_reason"):
                raise ReportError("pip-audit skipped a required dependency")
            for vulnerability in dependency["vulns"]:
                if not isinstance(vulnerability, dict) or not isinstance(vulnerability.get("id"), str):
                    raise ReportError("Invalid pip-audit finding")
                severities["unknown"] += 1
                blocking_findings += 1
    elif tool == "gitleaks":
        if not isinstance(data, list):
            raise ReportError("Gitleaks report must be an array")
        for finding in data:
            if not isinstance(finding, dict) or not isinstance(finding.get("RuleID"), str):
                raise ReportError("Invalid Gitleaks finding")
            severities["unknown"] += 1
            blocking_findings += 1
    else:
        raise ReportError(f"Unsupported security tool: {tool}")
    return {
        "tool": tool,
        "findings": sum(severities.values()),
        "blocking_findings": blocking_findings,
        "by_severity": severities,
        "source": path.name,
    }


def read_measurement(path: Path) -> dict[str, Any]:
    data = read_json(path)
    if not isinstance(data, dict):
        raise ReportError("Measurement report must be an object with an actual status")
    actual_statuses = [status(data[key]) for key in ("status", "result", "outcome") if key in data]
    if not actual_statuses or len(set(actual_statuses)) != 1:
        raise ReportError("Measurement report must be an object with an actual status")
    data["status"] = actual_statuses[0]
    for key, value in data.items():
        if key.endswith(("_seconds", "_bytes", "_count")) or key in {"tests", "states"}:
            if value is None:
                continue  # Optional measurements remain unavailable, never a synthetic zero.
            if isinstance(value, list) and key == "states":
                continue
            number(value, f"measurement {key}", integer=not key.endswith("_seconds"))
            if key in {"tests", "state_count"} and value == 0:
                raise ReportError("Required measurement collected zero tests/states")
    checks = data.get("checks", [])
    if not isinstance(checks, list):
        raise ReportError("Measurement checks must be an array")
    for check in checks:
        if not isinstance(check, dict) or "name" not in check or "status" not in check:
            raise ReportError("Invalid measurement check")
        check["status"] = status(check["status"])
        if check["status"] != "PASS" and data["status"] == "PASS":
            raise ReportError("Passing measurement report contains a failed or unrun check")
        if "duration_seconds" in check:
            number(check["duration_seconds"], "check duration")
    tools = data.get("tools", {})
    if not isinstance(tools, dict):
        raise ReportError("Measurement tools must be an object")
    for name, tool in tools.items():
        if not isinstance(tool, dict) or "outcome" not in tool:
            raise ReportError("Measurement tool requires an actual outcome")
        if status(tool["outcome"]) != "PASS" and data["status"] == "PASS":
            raise ReportError(f"Passing measurement contains a failed or unrun tool: {name}")
    return {**data, "source": path.name}
