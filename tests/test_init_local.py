"""Original-app initializer privacy, import safety and missing-input recovery."""

import os
import runpy
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_original_initializer_creates_private_files_without_overwriting(tmp_path):
    scripts = tmp_path / "scripts"
    config = tmp_path / "config"
    scripts.mkdir()
    config.mkdir()
    script = scripts / "init_local.py"
    shutil.copy2(ROOT / "scripts/init_local.py", script)
    for name in ("pokedex_251.example.json", "settings.example.yaml"):
        (config / name).write_text("synthetic initial state")
    previous_mask = os.umask(0)
    try:
        runpy.run_path(str(script), run_name="__main__")
    finally:
        os.umask(previous_mask)
    files = [config / name for name in ("pokedex_251.json", "settings.yaml", "market_values.json")]
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in files)
    files[0].write_text("preserved synthetic collection")
    runpy.run_path(str(script), run_name="__main__")
    assert files[0].read_text() == "preserved synthetic collection"


def test_original_initializer_import_has_no_file_side_effects(tmp_path):
    scripts = tmp_path / "scripts"
    config = tmp_path / "config"
    scripts.mkdir()
    config.mkdir()
    script = scripts / "init_local.py"
    shutil.copy2(ROOT / "scripts/init_local.py", script)
    for name in ("pokedex_251.example.json", "settings.example.yaml"):
        (config / name).write_text("synthetic example")
    before = {p.name: p.read_bytes() for p in config.iterdir()}
    module = runpy.run_path(str(script))
    assert callable(module["initialize"])
    assert {p.name: p.read_bytes() for p in config.iterdir()} == before


def test_original_initializer_missing_example_does_not_create_empty_state(tmp_path):
    scripts = tmp_path / "scripts"
    config = tmp_path / "config"
    scripts.mkdir()
    config.mkdir()
    script = scripts / "init_local.py"
    shutil.copy2(ROOT / "scripts/init_local.py", script)
    with pytest.raises(FileNotFoundError):
        runpy.run_path(str(script), run_name="__main__")
    assert not list(config.iterdir())
    # A repaired fixture can be initialized normally, without deleting an empty placeholder.
    for name in ("pokedex_251.example.json", "settings.example.yaml"):
        (config / name).write_text("synthetic example")
    runpy.run_path(str(script), run_name="__main__")
    assert (config / "pokedex_251.json").read_text() == "synthetic example"
