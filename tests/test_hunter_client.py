"""Private Hunter client contract races with a controlled transport and DOM."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_hunter_main_client_contracts():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is required for isolated Hunter client contracts")
    result = subprocess.run(
        [node, str(ROOT / "scripts/verify_hunter_client.js")],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    evidence = json.loads(result.stdout)
    assert evidence["kind"] == "hunter-main-client-contracts"
    assert evidence["engineering_fixtures_only"] is True
    assert evidence["customer_root_access"] is False
    assert evidence["provider_operations"] == 0
    assert evidence["passed"] >= 20
    assert all(case["status"] == "passed" for case in evidence["cases"])
