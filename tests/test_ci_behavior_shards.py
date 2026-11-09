"""No omitted modules, lost branch coverage, or false-green shard reports."""

import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest
import yaml
from ci_reporting_helpers import report
from coverage import CoverageData
from coverage.exceptions import DataError
from test_ci_aggregate import retained_job

from scripts.ci import behavior_shards as shards
from scripts.ci import combine_behavior

ROOT = Path(__file__).resolve().parents[1]


def test_partition_includes_every_current_and_new_module_once(tmp_path):
    names = {p.name for p in (ROOT / "tests").glob("test_*.py")}
    names.update({"test_new_domain.py", "test_shop99_future.py"})
    for name in names:
        (tmp_path / name).touch()
    assigned = [p.name for shard in shards.SHARDS for p in shards.modules(shard, tmp_path)]
    assert Counter(assigned) == Counter(names)
    assert shards.shard_for("test_shop99_future") == "shopping-journeys"
    assert shards.shard_for("test_new_domain") == "core"


@pytest.mark.parametrize("exit_code", [0, 1, 5])
def test_shard_runner_passes_every_module_and_preserves_pytest_exit(monkeypatch, exit_code):
    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        return exit_code

    monkeypatch.setattr(shards.subprocess, "call", run)
    assert shards.main(["shopping-decisions", "--", "-vv", "--disable-socket"]) == exit_code
    command, options = calls[0]
    assert command[1:3] == ["-m", "pytest"]
    assert command[3:-2] == [str(p.relative_to(ROOT)) for p in shards.modules("shopping-decisions")]
    assert command[-2:] == ["-vv", "--disable-socket"]
    assert options["cwd"] == ROOT


def test_shard_report_rejects_omitted_new_module(tmp_path, monkeypatch):
    monkeypatch.setattr(report, "modules", lambda shard: [Path("test_one.py"), Path("test_new.py")])
    native = tmp_path / "native.xml"
    native.write_text('<testsuite><testcase classname="tests.test_one"/></testsuite>')
    args = [
        "job",
        "--name",
        "Behavior: core",
        "--outcome",
        "tests=success",
        "--junit",
        str(native),
        "--suite-shard",
        "core",
        "--output",
        str(tmp_path / "metrics.json"),
    ]
    assert report.main(args) == 1
    assert "tests.test_new" in str(json.loads((tmp_path / "metrics.json").read_text())["errors"])


def native_shards(tmp_path, monkeypatch, runtime="3.15.2", *, covered=True):
    monkeypatch.setattr(combine_behavior, "modules", lambda shard: [Path("test_one.py")])
    monkeypatch.setenv("GITHUB_SHA", "candidate")
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    source = tmp_path / "branch_sample.py"
    source.write_text("def choose(flag):\n    if flag:\n        return 1\n    return 0\n")
    native = tmp_path / "native.xml"
    native.write_text('<testsuite><testcase classname="tests.test_one" time="1"/></testsuite>')
    paths = []
    for index, shard in enumerate(shards.SHARDS):
        directory = tmp_path / "children" / f"{runtime}-{shard}" / "ci/behavior"
        path = directory / "metrics.json"
        assert (
            report.main(
                [
                    "job",
                    "--name",
                    "Behavior: " + shard,
                    "--outcome",
                    "tests=success",
                    "--expect-suite",
                    "tests.test_one",
                    "--junit",
                    str(native),
                    "--output",
                    str(path),
                ]
            )
            == 0
        )
        record = json.loads(path.read_text())
        record["environment"].update(os="Linux", python=runtime)
        path.write_text(json.dumps(record))
        data = CoverageData(basename=str(directory / "coverage.data"))
        arcs = [(-1, 2), (2, 3), (3, -1)] if covered and index % 2 else [(-1, 2), (2, 4), (4, -1)]
        data.add_arcs({str(source): arcs})
        data.write()
        paths.append(path)
    return paths, source


def test_combines_branch_union_per_runtime_without_mixing_versions(tmp_path, monkeypatch):
    _, source = native_shards(tmp_path, monkeypatch)
    native_shards(tmp_path, monkeypatch, "3.14.10", covered=False)
    for runtime, expected_arcs in (("3.15", 5), ("3.14", 3)):
        output = tmp_path / "combined" / runtime
        assert combine_behavior.combine(tmp_path / "children", output, runtime)["result"] == "PASS"
        data = CoverageData(basename=str(output / "coverage.data"))
        data.read()
        assert len(data.arcs(str(source))) == expected_arcs
        assert (output / "coverage.xml").is_file()
        assert (output / "coverage.json").is_file()


@pytest.mark.parametrize(
    "damage",
    [
        "missing",
        "duplicate",
        "failed",
        "stale",
        "omitted-module",
        "coverage-missing",
        "coverage-corrupt",
        "coverage-lines",
    ],
)
def test_combination_rejects_incomplete_or_invalid_shards(tmp_path, monkeypatch, damage):
    paths, source = native_shards(tmp_path, monkeypatch)
    path = paths[-1]
    record = json.loads(path.read_text())
    if damage == "missing":
        path.unlink()
    elif damage == "duplicate":
        record["name"] = "Behavior: core"
    elif damage == "failed":
        record["result"] = "FAIL"
        record["outcomes"]["tests"] = "failure"
    elif damage == "stale":
        record["identity"]["run_attempt"] = "1"
    elif damage == "omitted-module":
        record["reports"]["junit"]["expected_suites"] = {}
    else:
        coverage = path.parent / "coverage.data"
        coverage.unlink()
        if damage == "coverage-corrupt":
            coverage.write_bytes(b"broken database")
        elif damage == "coverage-lines":
            data = CoverageData(basename=str(coverage))
            data.add_lines({str(source): [1, 2]})
            data.write()
    if damage != "missing":
        path.write_text(json.dumps(record))
    with pytest.raises((report.ReportError, DataError)):
        combine_behavior.combine(tmp_path / "children", tmp_path / "combined", "3.15")


def test_workflow_matrix_reports_match_each_shard_and_runtime():
    jobs = yaml.safe_load((ROOT / ".github/workflows/validate.yml").read_text())["jobs"]
    matrix = jobs["behavior"]["strategy"]["matrix"]
    assert set(matrix["shard"]) == set(shards.SHARDS)
    assert matrix["python"] == ["3.15"]
    coverage = next(step["run"] for step in jobs["gate"]["steps"] if step.get("id") == "coverage")
    assert coverage.count("--python ") == 1
    assert "--python 3.15" in coverage
    aggregate = next(step["run"] for step in jobs["gate"]["steps"] if step.get("id") == "result")
    for shard in shards.SHARDS:
        assert f'--expect-job-reports "Behavior: {shard}={len(matrix["python"])}"' in aggregate
    assert "--required coverage" in aggregate
    run = next(step for step in jobs["behavior"]["steps"] if step.get("id") == "tests")
    assert "-- -vv" in run["run"]
    assert '--suite-shard "${{ matrix.shard }}"' in str(jobs["behavior"])
    assert run["env"]["COVERAGE_FILE"] == "reports/ci/behavior/coverage.data"


def test_empty_or_unknown_partition_refuses_to_run(tmp_path):
    with pytest.raises(ValueError):
        shards.modules("core", tmp_path)
    with pytest.raises(ValueError):
        shards.modules("typo", tmp_path)


@pytest.mark.parametrize("coverage_status", ["success", "failure", "skipped"])
def test_required_gate_records_coverage_failure_even_when_all_jobs_pass(tmp_path, coverage_status):
    jobs = yaml.safe_load((ROOT / ".github/workflows/validate.yml").read_text())["jobs"]
    command = next(step["run"] for step in jobs["gate"]["steps"] if step.get("id") == "result")
    scripts = tmp_path / "scripts/ci"
    scripts.mkdir(parents=True)
    for name in ("report.py", "report_readers.py", "behavior_shards.py"):
        shutil.copyfile(ROOT / "scripts/ci" / name, scripts / name)
    binary = tmp_path / "bin"
    binary.mkdir()
    (binary / "python3").symlink_to(sys.executable)
    children = tmp_path / "reports/ci/children"
    for shard in shards.SHARDS:
        for runtime in jobs["behavior"]["strategy"]["matrix"]["python"]:
            retained_job(tmp_path, children / f"{shard}-{runtime}", "Behavior: " + shard, runtime)
    for name in (
        "Source quality",
        "Staging PostgreSQL",
        "Fresh distribution",
        "Synthetic browser journeys",
        "Security and dependencies",
    ):
        retained_job(tmp_path, children / name, name)
    needs = {name: {"result": "success"} for name in jobs["gate"]["needs"]}
    result = subprocess.run(
        ["bash", "-e", "-o", "pipefail", "-c", command],
        cwd=tmp_path,
        env={
            **os.environ,
            "PATH": str(binary) + os.pathsep + os.environ["PATH"],
            "NEEDS_JSON": json.dumps(needs),
            "COVERAGE": coverage_status,
            "GITHUB_OUTPUT": str(tmp_path / "output"),
        },
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == (0 if coverage_status == "success" else 1), result.stderr
    record = json.loads((tmp_path / "reports/ci/gate/metrics.json").read_text())
    assert record["result"] == ("PASS" if coverage_status == "success" else "FAIL")
    assert len(record["job_reports"]) == 9
    if coverage_status != "success":
        assert not (tmp_path / "output").exists()
