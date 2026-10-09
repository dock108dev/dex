"""Security findings, outages, and redaction must remain distinguishable."""

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "ci_security", Path(__file__).parents[1] / "scripts/ci/security.py"
)
security = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(security)


def test_secret_report_discards_all_source_and_identity_fields():
    secret = "synthetic-value-never-retained"
    finding = {
        "RuleID": "test-rule",
        "File": "app.py",
        "StartLine": 1,
        "EndLine": 1,
        "Secret": secret,
        "Match": secret,
        "Author": secret,
        "Email": secret,
        "Message": secret,
    }
    result = security.sanitize_gitleaks([finding], "tracked-worktree")
    assert secret not in json.dumps(result)
    assert result == [
        {
            "RuleID": "test-rule",
            "File": "app.py",
            "StartLine": 1,
            "EndLine": 1,
            "ScanScope": "tracked-worktree",
        }
    ]


def test_bandit_keeps_advisory_counts_and_blocks_high_confidence_medium_risk():
    low = {"issue_severity": "LOW", "issue_confidence": "HIGH", "test_id": "B105", "code": "private"}
    medium = {"issue_severity": "MEDIUM", "issue_confidence": "HIGH", "test_id": "B608", "code": "private"}
    clean, blocking = security.sanitize_bandit(
        {"errors": [], "results": [low, medium], "metrics": {"_totals": {"loc": 12}}}
    )
    assert len(clean["results"]) == 2
    assert blocking == 1
    assert "private" not in json.dumps(clean)


def test_bandit_hardcoded_password_message_cannot_leak_literal():
    secret = "synthetic-value-never-retained"
    finding = {
        "issue_severity": "LOW",
        "issue_confidence": "HIGH",
        "test_id": "B105",
        "test_name": "hardcoded_password_string",
        "filename": "src/app.py",
        "line_number": 1,
        "issue_text": f"Possible hardcoded password: '{secret}'",
        "code": f"password = '{secret}'",
    }
    clean, _ = security.sanitize_bandit(
        {"errors": [], "results": [finding], "metrics": {"_totals": {"loc": 1}}}
    )
    assert secret not in json.dumps(clean)
    assert "issue_text" not in clean["results"][0]
    assert clean["results"][0]["test_id"] == "B105"
    assert clean["results"][0]["filename"] == "src/app.py"


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"dependencies": []},
        {"dependencies": [{"name": "example", "version": "1", "skip_reason": "unknown"}]},
    ],
)
def test_dependency_audit_cannot_turn_missing_or_skipped_data_into_zero_findings(data):
    with pytest.raises(security.ScanError):
        security.validate_audit(data)


def test_vulnerability_and_scan_exit_are_preserved():
    data = {"dependencies": [{"name": "example", "version": "1", "vulns": [{"id": "TEST-1"}]}]}
    _, count = security.validate_audit(data)
    assert count == 1
    security.verify_exit(1, count)
    with pytest.raises(security.ScanError):
        security.verify_exit(0, count)
    with pytest.raises(security.ScanError):
        security.verify_exit(1, 0)


def test_required_scan_report_missing_or_malformed(tmp_path):
    path = tmp_path / "scan.json"
    with pytest.raises(security.ScanError):
        security.read_json(path)
    path.write_text("not JSON")
    with pytest.raises(security.ScanError):
        security.read_json(path)


def test_scanner_outage_does_not_reuse_stale_report(tmp_path, monkeypatch):
    output = tmp_path / "reports"
    output.mkdir()
    for tool in ("bandit", "pip-audit", "gitleaks"):
        (output / f"{tool}.json").write_text("[]")

    def unavailable(*args, **kwargs):
        raise security.ScanError("scanner unavailable or exceeded finite timeout")

    monkeypatch.setattr(security, "run", unavailable)
    assert security.scan(tmp_path, output, "absent") == 1
    status = json.loads((output / "security-status.json").read_text())
    assert status["outcome"] == "FAIL"
    assert all(tool["findings"] is None for tool in status["tools"].values())
    assert all(not (output / f"{tool}.json").exists() for tool in status["tools"])


def test_arbitrary_scanner_exception_details_are_not_retained(tmp_path, monkeypatch):
    secret = "synthetic-private-exception-detail"

    def invalid(*args, **kwargs):
        raise ValueError(secret)

    monkeypatch.setattr(security, "run", invalid)
    monkeypatch.setattr(security, "version", lambda *args: "1.0.0")
    output = tmp_path / "reports"
    assert security.scan(tmp_path, output, "absent") == 1
    assert secret not in (output / "security-status.json").read_text()


def test_worktree_scan_excludes_ignored_and_untracked_owner_state(tmp_path):
    root = tmp_path / "repository"
    root.mkdir()
    subprocess.run(["git", "init", "--quiet", str(root)], check=True, capture_output=True)
    (root / ".gitignore").write_text("private.json\n")
    (root / "app.py").write_text("print('synthetic')\n")
    (root / "private.json").write_text('"synthetic owner value"')
    (root / "untracked-owner-note.txt").write_text("synthetic owner value")
    subprocess.run(["git", "add", ".gitignore", "app.py"], cwd=root, check=True, capture_output=True)
    # Even a previously tracked path now covered by privacy rules remains excluded.
    subprocess.run(["git", "add", "--force", "private.json"], cwd=root, check=True, capture_output=True)
    (root / "scripts/ci").mkdir(parents=True)
    (root / "scripts/ci/new.py").write_text("print('new CI source')\n")
    (root / "src").mkdir()
    (root / "src/new.py").write_text("print('new app source')\n")
    (root / "src/.env").write_text("synthetic owner value")
    (root / ".github/actions/test").mkdir(parents=True)
    (root / ".github/actions/test/action.yml").write_text("name: New action\n")
    destination = tmp_path / "snapshot"
    destination.mkdir()
    assert security.tracked_snapshot(root, destination) == 5
    assert (destination / "app.py").exists()
    assert (destination / "scripts/ci/new.py").exists()
    assert (destination / "src/new.py").exists()
    assert (destination / ".github/actions/test/action.yml").exists()
    assert not (destination / "src/.env").exists()
    assert not (destination / "private.json").exists()
    assert not (destination / "untracked-owner-note.txt").exists()
