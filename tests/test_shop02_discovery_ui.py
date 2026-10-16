"""The shipped singles client keeps acquisition explicit and local actions private."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest


def test_discovery_client_explicit_acquisition_and_private_ui_boundaries():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required for the shipped browser adapter checks")
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            node,
            str(root / "tests/shop02_discovery_ui_cases.cjs"),
            str(root / "src/pokemon_hunter/beta/static/discovery.js"),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    report = json.loads(result.stdout)
    assert report["passed"] == len(report["cases"]) >= 11
    assert report["provider_calls"] == 0
    assert report["customer_data"] is False
