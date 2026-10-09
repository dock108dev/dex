#!/usr/bin/env python3
"""Run local security CLIs without retaining source snippets or secret values."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import re
import shutil
import subprocess
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

SEVERITIES = {"LOW", "MEDIUM", "HIGH"}


class ScanError(ValueError):
    """A scanner failed to produce usable evidence."""


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ScanError("required report missing or malformed") from exc


def sanitize_bandit(data: object) -> tuple[dict, int]:
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        raise ScanError("invalid Bandit report schema")
    if not isinstance(data.get("errors"), list) or data["errors"]:
        raise ScanError("Bandit source analysis was incomplete")
    metrics = data.get("metrics", {})
    if not isinstance(metrics, dict) or metrics.get("_totals", {}).get("loc", 0) <= 0:
        raise ScanError("Bandit did not analyze source")
    findings = []
    blocking = 0
    fields = ("filename", "line_number", "line_range", "test_id", "test_name", "more_info")
    for result in data["results"]:
        if not isinstance(result, dict):
            raise ScanError("invalid Bandit finding")
        severity, confidence = result.get("issue_severity"), result.get("issue_confidence")
        if severity not in SEVERITIES or confidence not in SEVERITIES or not result.get("test_id"):
            raise ScanError("invalid Bandit finding severity or confidence")
        finding = {key: result[key] for key in fields if key in result}
        finding.update(issue_severity=severity, issue_confidence=confidence)
        findings.append(finding)
        blocking += severity in {"MEDIUM", "HIGH"} and confidence == "HIGH"
    # Bandit's code and issue_text can contain source/password literals; neither is uploaded.
    return {"results": findings, "errors": [], "metrics": metrics}, blocking


def validate_audit(data: object) -> tuple[dict, int]:
    if not isinstance(data, dict) or not isinstance(data.get("dependencies"), list):
        raise ScanError("invalid pip-audit report schema")
    if not data["dependencies"]:
        raise ScanError("pip-audit did not audit dependencies")
    dependencies = []
    count = 0
    for dependency in data["dependencies"]:
        if not isinstance(dependency, dict) or not dependency.get("name") or not dependency.get("version"):
            raise ScanError("invalid dependency identity")
        if dependency.get("skip_reason") or not isinstance(dependency.get("vulns"), list):
            raise ScanError("dependency audit was incomplete")
        vulnerabilities = []
        for vulnerability in dependency["vulns"]:
            if not isinstance(vulnerability, dict) or not vulnerability.get("id"):
                raise ScanError("invalid dependency vulnerability")
            vulnerabilities.append(
                {
                    key: vulnerability[key]
                    for key in ("id", "fix_versions", "aliases", "description")
                    if key in vulnerability
                }
            )
        dependencies.append(
            {"name": dependency["name"], "version": dependency["version"], "vulns": vulnerabilities}
        )
        count += len(vulnerabilities)
    # PyPI's audit response has no universal severity field; unknown stays unknown.
    return {"dependencies": dependencies, "fixes": []}, count


def sanitize_gitleaks(data: object, scope: str) -> list[dict]:
    if not isinstance(data, list):
        raise ScanError("invalid Gitleaks report schema")
    findings = []
    for finding in data:
        if not isinstance(finding, dict) or not finding.get("RuleID") or not finding.get("File"):
            raise ScanError("invalid Gitleaks finding identity")
        if not isinstance(finding.get("StartLine"), int) or finding["StartLine"] < 1:
            raise ScanError("invalid Gitleaks finding location")
        # Allowlist fields: Match, Secret, author, email, and commit messages are discarded.
        clean = {
            key: finding[key]
            for key in ("RuleID", "File", "StartLine", "EndLine", "Commit", "Fingerprint")
            if key in finding
        }
        clean["ScanScope"] = scope
        findings.append(clean)
    return findings


def verify_exit(returncode: int, count: int, finding_exit: int = 1) -> None:
    expected = finding_exit if count else 0
    if returncode != expected:
        raise ScanError("scanner exit status does not match complete report")


def run(command: list[str], root: Path, timeout: int = 300) -> int:
    try:
        return subprocess.run(
            command,
            cwd=root,
            timeout=timeout,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
    except (OSError, subprocess.TimeoutExpired) as exc:
        # Never retain raw command output: a scanner may echo a credential or source.
        raise ScanError("scanner unavailable or exceeded finite timeout") from exc


def tracked_snapshot(root: Path, destination: Path) -> int:
    try:
        listed = subprocess.check_output(["git", "ls-files", "-z"], cwd=root, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ScanError("cannot enumerate repository files") from exc
    names = {name for name in listed.decode().split("\0") if name}
    # Include authored source before commit, restricted to known code/fixture trees and formats.
    # No enumeration of profiles, reports, evidence, photos, or other owner-state trees.
    extensions = {".py", ".html", ".js", ".css", ".yml", ".yaml", ".toml", ".json", ".txt"}
    for directory in ("src", "web", "scripts/ci", ".github", "tests"):
        names.update(
            str(path.relative_to(root))
            for path in (root / directory).glob("**/*")
            if path.is_file() and path.suffix in extensions
        )
    candidates = "\0".join(sorted(names)) + "\0"
    ignored = subprocess.run(
        ["git", "check-ignore", "--no-index", "-z", "--stdin"],
        cwd=root,
        input=candidates.encode(),
        capture_output=True,
        timeout=30,
        check=False,
    )
    if ignored.returncode not in (0, 1):
        raise ScanError("cannot enforce ignored-state exclusion")
    excluded = set(ignored.stdout.decode().split("\0"))
    count = 0
    for name in sorted(names - excluded):
        path = root / name
        if path.is_symlink() or not path.is_file():
            continue
        if not path.resolve().is_relative_to(root):
            raise ScanError("repository path escaped scan root")
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        count += 1
    if not count:
        raise ScanError("tracked worktree scan scope is empty")
    return count


def inventory() -> list[dict]:
    """Retain installed dependency identity/license metadata; no package code."""
    records = []
    for package in importlib.metadata.distributions():
        metadata = package.metadata
        records.append(
            {
                "name": metadata.get("Name"),
                "version": package.version,
                "license_expression": metadata.get("License-Expression"),
                "license_classifiers": [
                    value for value in metadata.get_all("Classifier", []) if value.startswith("License ::")
                ],
            }
        )
    return sorted(records, key=lambda record: (record["name"] or "").lower())


def version(tool: str, executable: str) -> str:
    if tool != "gitleaks":
        try:
            return importlib.metadata.version(tool)
        except importlib.metadata.PackageNotFoundError as exc:
            raise ScanError("cannot verify scanner version") from exc
    try:
        result = subprocess.run(
            [executable, "version"], capture_output=True, text=True, timeout=10, check=True
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ScanError("cannot verify scanner version") from exc
    value = result.stdout.strip()
    if not re.fullmatch(r"v?\d+\.\d+\.\d+", value):
        raise ScanError("cannot verify scanner version")
    return value


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def scan(root: Path, output: Path, gitleaks: str) -> int:
    output.mkdir(parents=True, exist_ok=True)
    status = {"schema_version": 1, "started_at": datetime.now(UTC).isoformat(), "tools": {}}
    with tempfile.TemporaryDirectory(prefix="dex-ci-security-") as temporary:
        scratch = Path(temporary)
        for tool in ("bandit", "pip-audit", "gitleaks"):
            start = time.monotonic()
            report = output / f"{tool}.json"
            report.unlink(missing_ok=True)  # A stale report cannot qualify this invocation.
            try:
                tool_version = version(tool, gitleaks)
                if tool == "bandit":
                    raw = scratch / "bandit.json"
                    code = run(["bandit", "-r", "src", "-f", "json", "-o", str(raw)], root)
                    clean, blocking = sanitize_bandit(read_json(raw))
                    verify_exit(code, len(clean["results"]))
                    finding_count = len(clean["results"])
                elif tool == "pip-audit":
                    requirements = scratch / "requirements.txt"
                    if (
                        run(
                            [
                                "uv",
                                "export",
                                "--locked",
                                "--all-extras",
                                "--no-emit-project",
                                "--format",
                                "requirements-txt",
                                "--output-file",
                                str(requirements),
                            ],
                            root,
                        )
                        != 0
                    ):
                        raise ScanError("locked dependency export failed")
                    raw = scratch / "pip-audit.json"
                    code = run(
                        [
                            "pip-audit",
                            "--no-deps",
                            "--disable-pip",
                            "--strict",
                            "--progress-spinner",
                            "off",
                            "--timeout",
                            "15",
                            "--cache-dir",
                            str(scratch / "audit-cache"),
                            "--vulnerability-service",
                            "pypi",
                            "-f",
                            "json",
                            "-o",
                            str(raw),
                            "-r",
                            str(requirements),
                        ],
                        root,
                    )
                    clean, blocking = validate_audit(read_json(raw))
                    verify_exit(code, blocking)
                    finding_count = blocking
                else:
                    shallow = (
                        subprocess.check_output(
                            ["git", "rev-parse", "--is-shallow-repository"], cwd=root, timeout=30
                        )
                        .decode()
                        .strip()
                    )
                    if shallow != "false":
                        raise ScanError("full-history secret scan requires a nonshallow checkout")
                    snapshot = scratch / "worktree"
                    snapshot.mkdir()
                    file_count = tracked_snapshot(root, snapshot)
                    config = scratch / "gitleaks.toml"
                    config.write_text("[extend]\nuseDefault = true\n", encoding="utf-8")
                    clean = []
                    for scope, mode, target in (
                        ("tracked-worktree", "dir", snapshot),
                        ("git-history", "git", root),
                    ):
                        raw = scratch / f"gitleaks-{mode}.json"
                        command = [
                            gitleaks,
                            mode,
                            str(target),
                            "--redact=100",
                            "--config",
                            str(config),
                            "--gitleaks-ignore-path",
                            str(scratch),
                            "--ignore-gitleaks-allow",
                            "--no-banner",
                            "--no-color",
                            "--log-level",
                            "error",
                            "--timeout",
                            "240",
                            "--exit-code",
                            "10",
                            "--report-format",
                            "json",
                            "--report-path",
                            str(raw),
                        ]
                        if mode == "git":
                            command.append("--log-opts=--all")
                        code = run(command, root)
                        findings = sanitize_gitleaks(read_json(raw), scope)
                        verify_exit(code, len(findings), finding_exit=10)
                        clean.extend(findings)
                    finding_count = blocking = len(clean)
                    status["tracked_files_scanned"] = file_count
                write_json(report, clean)
                status["tools"][tool] = {
                    "outcome": "FAIL" if blocking else "PASS",
                    "findings": finding_count,
                    "blocking_findings": blocking,
                    "report": report.name,
                    "version": tool_version,
                }
            except (ScanError, OSError, ValueError, subprocess.SubprocessError) as exc:
                # Exception text from our own ScanError is safe; other errors can contain raw paths/data.
                reason = str(exc) if isinstance(exc, ScanError) else "security scan or report unavailable"
                status["tools"][tool] = {
                    "outcome": "FAIL",
                    "findings": None,
                    "blocking_findings": None,
                    "reason": reason,
                    "report": None,
                }
            status["tools"][tool]["duration_seconds"] = round(time.monotonic() - start, 3)
    status["finished_at"] = datetime.now(UTC).isoformat()
    status["vulnerability_data"] = "PyPI advisory responses fetched during this run; no response-cache reuse"
    status["baseline"] = None
    status["outcome"] = (
        "PASS" if all(value["outcome"] == "PASS" for value in status["tools"].values()) else "FAIL"
    )
    write_json(output / "security-status.json", status)
    write_json(output / "dependency-license-inventory.json", inventory())
    print(f"Security scans: {status['outcome']}. Sanitized reports: {output}")
    return 0 if status["outcome"] == "PASS" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("reports/ci/security"))
    parser.add_argument("--gitleaks-bin", default="gitleaks")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    return scan(root, args.output_dir.resolve(), args.gitleaks_bin)


if __name__ == "__main__":
    raise SystemExit(main())
