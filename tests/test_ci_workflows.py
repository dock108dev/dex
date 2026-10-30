"""Workflow regressions for clean runners and diagnostic failure propagation."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def job(workflow, name):
    return yaml.safe_load((ROOT / ".github/workflows" / workflow).read_text())["jobs"][name]


@pytest.mark.parametrize(
    "workflow,name", [("validate.yml", "behavior"), ("assurance.yml", "native-diagnostic")]
)
def test_full_suites_install_locked_renderer_dependencies(workflow, name):
    steps = job(workflow, name)["steps"]
    install = next(i for i, step in enumerate(steps) if step.get("id") == "javascript")
    assert any("actions/setup-node@" in step.get("uses", "") for step in steps[:install])
    assert steps[install]["run"] == "npm ci --ignore-scripts --no-audit --no-fund"
    assert any("pytest" in step.get("run", "") for step in steps[install + 1 :])
    assert any("javascript=$JAVASCRIPT" in step.get("run", "") for step in steps[install + 1 :])


@pytest.mark.parametrize("probe_exit", [0, 139])
def test_native_probe_preserves_all_trials_and_propagates_failure(tmp_path, probe_exit):
    steps = job("assurance.yml", "native-diagnostic")["steps"]
    command = next(step["run"] for step in steps if step.get("id") == "probes")
    output = tmp_path / "reports/ci/native-diagnostic"
    output.mkdir(parents=True)
    result = subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", f"timeout() {{ return {probe_exit}; }}\n" + command],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == (1 if probe_exit else 0), result.stderr
    records = (output / "probe-exits.txt").read_text().splitlines()
    assert len(records) == 18
    assert all(line.endswith(f" {probe_exit}") for line in records)


def test_performance_summary_retains_every_missing_suite_and_fails(tmp_path):
    steps = job("assurance.yml", "performance-diagnostic")["steps"]
    command = next(step["run"] for step in steps if step.get("name") == "Performance diagnostic summaries")
    scripts = tmp_path / "scripts/ci"
    scripts.mkdir(parents=True)
    for name in ("report.py", "report_readers.py"):
        shutil.copyfile(ROOT / "scripts/ci" / name, scripts / name)
    result = subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", command],
        cwd=tmp_path,
        env={
            **os.environ,
            "SETUP": "success",
            "CHROMIUM": "success",
            "PROBES": "success",
            "BUDGETS": "success",
            "BROWSER": "success",
        },
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 1, result.stderr
    records = list((tmp_path / "reports/ci/perf-diagnostic").glob("*-metrics.json"))
    assert len(records) == 3
    assert all(json.loads(path.read_text())["result"] == "FAIL" for path in records)
