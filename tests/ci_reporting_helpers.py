"""Native CI fixtures shared by job, aggregate and historical-health tests."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / "ci" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


report = load_script("report")
sys.modules.setdefault("report", report)


@pytest.fixture
def identity(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary.md"))
    monkeypatch.setenv("GITHUB_SHA", "tested-merge-sha")
    monkeypatch.setenv("CI_PR_HEAD_SHA", "pr-head-sha")
    monkeypatch.setenv("GITHUB_REF", "refs/pull/4/merge")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_RUN_ID", "42")
    return tmp_path


def fixture_json(path, data):
    path.write_text(json.dumps(data))
    return path


def junit(path, failure=False):
    path.write_text(
        '<testsuites><testsuite tests="2" failures="%d" errors="0" skipped="1" time="0.5">'
        '<testcase classname="suite" name="alpha" time="0.2">%s</testcase>'
        '<testcase name="beta" time="0.1"><skipped/></testcase></testsuite></testsuites>'
        % (int(failure), '<failure message="raw log never rendered">details</failure>' if failure else "")
    )
    return path
