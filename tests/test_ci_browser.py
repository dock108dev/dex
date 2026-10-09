"""The CI journey must prepare its own product/goal/save prerequisites."""

import importlib.util
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("dex_ci_browser", ROOT / "scripts/ci/browser.py")
browser_ci = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(browser_ci)


def test_browser_preparation_refuses_unmarked_state_without_creating_files(tmp_path):
    root = tmp_path / "not-synthetic"
    root.mkdir()
    with pytest.raises(ValueError, match="generated synthetic"):
        browser_ci.prepare_journey(root)
    assert list(root.iterdir()) == []


def test_fresh_demo_gets_complete_journey_and_repeat_refuses_duplicate_mutations(tmp_path):
    root = tmp_path / "synthetic"
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("DEX_", "OPENAI_", "EBAY_", "POKEMON_HUNTER_")) and key != "DATABASE_URL"
    }
    env.update(DEX_PROFILE="local", HOME=str(tmp_path))
    subprocess.run(
        [sys.executable, "-m", "pokemon_hunter.beta.synthetic", "--output", str(root)],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        timeout=60,
    )
    command = [sys.executable, str(ROOT / "scripts/ci/browser.py"), "--prepare-root", str(root)]
    subprocess.run(command, cwd=ROOT, env=env, check=True, capture_output=True, timeout=60)
    with sqlite3.connect(root / "inventory.db") as db:
        before = {
            table: db.execute(f'SELECT * FROM "{table}" ORDER BY id').fetchall()
            for table in ("collection_goals", "owned_copies", "saved_pack_research")
        }
        assert len(before["collection_goals"]) == len(before["owned_copies"]) == 6
        assert (
            db.execute(
                "SELECT COUNT(*) FROM collection_goals WHERE name='Synthetic all-era Original 151'"
            ).fetchone()[0]
            == 2
        )
        assert (
            db.execute(
                "SELECT COUNT(*) FROM saved_pack_research WHERE name='Synthetic saved baseline'"
            ).fetchone()[0]
            == 2
        )
        assert (
            db.execute("SELECT COUNT(*) FROM sealed_products WHERE publication_state='published'").fetchone()[
                0
            ]
            > 0
        )
    repeat = subprocess.run(command, cwd=ROOT, env=env, check=False, capture_output=True, timeout=60)
    assert repeat.returncode != 0
    with sqlite3.connect(root / "inventory.db") as db:
        assert all(
            db.execute(f'SELECT * FROM "{table}" ORDER BY id').fetchall() == rows
            for table, rows in before.items()
        )
