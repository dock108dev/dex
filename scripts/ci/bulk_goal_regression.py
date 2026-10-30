"""Retain an original/repaired focused comparison, never full acceptance."""

import ast
import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

BASE = "2778b844bf0a3d8d87c20f96fd06c8fbc30bd3bf"
OUT = Path("reports/ci/bulk-goal-regression")
TEST = Path("tests/test_perf04_workflows.py")
REGRESSION = "test_custom_goal_waits_for_confirmation_before_reload"


def git(*args):
    return subprocess.check_output(["git", *args], text=True)


def prepare():
    OUT.mkdir(parents=True, exist_ok=True)
    current = TEST.read_text()
    original = git("show", f"{BASE}:{TEST}")
    node = next(n for n in ast.parse(current).body if getattr(n, "name", "") == REGRESSION)
    first = min([node.lineno, *(n.lineno for n in node.decorator_list)])
    regression = "\n".join(current.splitlines()[first - 1 : node.end_lineno]) + "\n"
    baseline = original + "\n\n" + regression
    (OUT / "test_original_regression.py").write_text(baseline)
    # Keep the same conftest fixtures as the repaired workflow.
    Path("tests/test_bulk_goal_original_diagnostic.py").write_text(baseline)
    unchanged = git("diff", BASE, "HEAD", "--", "src", "pyproject.toml", "uv.lock")
    assert not unchanged, "Application, dependencies or pytest configuration changed"
    (OUT / "identities.json").write_text(
        json.dumps(
            {
                "focused_only": True,
                "original_sha": BASE,
                "candidate_sha": git("rev-parse", "HEAD").strip(),
                "candidate_tree": git("rev-parse", "HEAD^{tree}").strip(),
                "application_dependencies_and_pytest_configuration_unchanged": True,
                "original_test_sha256": hashlib.sha256(original.encode()).hexdigest(),
                "candidate_test_sha256": hashlib.sha256(current.encode()).hexdigest(),
                "shared_regression_sha256": hashlib.sha256(regression.encode()).hexdigest(),
                "baseline_module_sha256": hashlib.sha256(baseline.encode()).hexdigest(),
                "python": sys.version,
            },
            indent=2,
        )
    )


def verify():
    result = {}
    for name, count, failures in [("original", 1, 1), ("workflows", 22, 0), ("related", 66, 0)]:
        root = ET.parse(OUT / f"{name}.xml").getroot()
        cases = list(root.iter("testcase"))
        assert len(cases) == count, (name, len(cases))
        assert not list(root.iter("error")) and not list(root.iter("skipped")), name
        assert len(list(root.iter("failure"))) == failures, name
        result[name] = {"tests": count, "failures": failures, "errors": 0, "skips": 0}
        if name == "original":
            assert cases[0].attrib["name"] == REGRESSION + "[bulk]"
            message = cases[0].find("failure").attrib["message"]
            assert "Timeout 30000ms exceeded" in message
            assert "View frozen checklist and progress" in message
            assert "Conflict: /api/v2/goals/" in (OUT / "original.log").read_text()
    (OUT / "comparison.json").write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    {"prepare": prepare, "verify": verify}[sys.argv[1]]()
