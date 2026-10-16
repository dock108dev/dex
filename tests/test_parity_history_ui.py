"""Historical hunt pages retain local reads and direct new acquisition to Shopping."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest


def test_historical_renderer_has_no_retired_acquisition_controls():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is required for the historical renderer checks")
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            node,
            str(root / "tests/parity_history_ui_cases.cjs"),
            str(root / "src/pokemon_hunter/beta/static/parity.js"),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    report = json.loads(result.stdout)
    assert report["passed"] == len(report["cases"]) == 5
    assert report["provider_calls"] == 0
    assert report["customer_data"] is False
