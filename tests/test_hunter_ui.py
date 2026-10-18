"""Guard the disposable browser harness and its protected-state evidence."""

import importlib.util
import sqlite3
from pathlib import Path

import pytest


def harness():
    path = Path(__file__).resolve().parents[1] / "scripts/qualify_hunter_ui.py"
    spec = importlib.util.spec_from_file_location("hunter_browser_qualification", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("existing", ["root", "source"])
def test_browser_preparation_refuses_existing_paths_before_initialization(tmp_path, existing):
    root, source = tmp_path / "root", tmp_path / "source"
    (root if existing == "root" else source).mkdir()
    with pytest.raises(ValueError, match="Fresh disposable"):
        harness().prepare(root, source)
    assert sorted(path.name for path in tmp_path.iterdir()) == [existing]


def test_browser_server_refuses_customer_port_and_unmarked_roots(tmp_path):
    script = harness()
    with pytest.raises(ValueError, match="Disposable fixture"):
        script.serve(tmp_path, tmp_path, 18999)
    (tmp_path / "SYNTHETIC_ONLY").write_text("Engineering fixture\n")
    with pytest.raises(ValueError, match="Disposable fixture"):
        script.serve(tmp_path, tmp_path, 8011)


def test_protected_state_detects_collection_goal_and_source_right_changes(tmp_path):
    with sqlite3.connect(tmp_path / "inventory.db") as db:
        db.execute("CREATE TABLE owned_copies (id TEXT PRIMARY KEY, quantity INTEGER)")
        db.execute("INSERT INTO owned_copies VALUES ('fixture',2)")
        db.execute("CREATE TABLE collection_goals (id TEXT PRIMARY KEY, version INTEGER)")
        db.execute("INSERT INTO collection_goals VALUES ('fixture-goal',1)")
    script = harness()
    before = script.protected_state(tmp_path)
    assert before == script.protected_state(tmp_path)
    with sqlite3.connect(tmp_path / "inventory.db") as db:
        db.execute("UPDATE owned_copies SET quantity=3")
    after = script.protected_state(tmp_path)
    assert before["owned_copies"] != after["owned_copies"]
    assert before["collection_goals"] == after["collection_goals"]
    (tmp_path / "price-contracts.json").write_text('{"engineering-fixture":"withdrawn"}')
    assert script.protected_state(tmp_path)["price-contracts.json"] != after["price-contracts.json"]


def test_computed_color_contrast_gate_detects_invisible_navigation():
    script = harness()
    assert script.contrast_ratio("rgb(0, 0, 0)", "rgb(255, 255, 255)") == pytest.approx(21)
    assert script.contrast_ratio("rgb(255, 255, 255)", "rgb(245, 246, 248)") < 1.1
    assert script.contrast_ratio("rgb(156, 28, 48)", "rgb(245, 246, 248)") >= 4.5
