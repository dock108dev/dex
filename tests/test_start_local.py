"""Startup reuses the configured installation without initializing or replacing it."""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/start_local.py"


@pytest.fixture
def launcher(monkeypatch, tmp_path):
    monkeypatch.setenv("DEX_APP_ROOT", str(tmp_path / "existing"))
    spec = importlib.util.spec_from_file_location("start_local", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.subprocess, "run", Mock(return_value=SimpleNamespace(returncode=1, stdout="")))
    monkeypatch.setattr(module.webbrowser, "open", Mock())
    monkeypatch.setattr(module.os, "execv", Mock())
    monkeypatch.setattr(module.os, "chdir", Mock())
    return module


def test_existing_listener_opens_without_starting_another_process(launcher):
    launcher.subprocess.run.return_value = SimpleNamespace(returncode=0, stdout="1234\n")
    launcher.main()
    launcher.webbrowser.open.assert_called_once_with("http://127.0.0.1:8011/", new=0)
    launcher.os.execv.assert_not_called()
    launcher.os.chdir.assert_not_called()
    assert not launcher.ROOT.exists()


@pytest.mark.parametrize("missing", ["B1_ISOLATED", "inventory.db"])
def test_incomplete_installation_is_never_initialized(launcher, missing):
    launcher.ROOT.mkdir()
    for name in {"B1_ISOLATED", "inventory.db"} - {missing}:
        (launcher.ROOT / name).touch()
    with pytest.raises(SystemExit, match="existing Dex installation is unavailable"):
        launcher.main()
    assert not (launcher.ROOT / missing).exists()
    launcher.os.execv.assert_not_called()
    launcher.webbrowser.open.assert_not_called()


def test_listener_check_failure_refuses_startup(launcher):
    launcher.subprocess.run.return_value = SimpleNamespace(returncode=2, stdout="")
    with pytest.raises(SystemExit, match="Could not check"):
        launcher.main()
    launcher.os.execv.assert_not_called()


def test_start_uses_selected_interpreter_and_existing_root(launcher, monkeypatch):
    launcher.ROOT.mkdir()
    (launcher.ROOT / "B1_ISOLATED").touch()
    (launcher.ROOT / "inventory.db").write_bytes(b"existing data")
    keys = ("EBAY_CLIENT_ID", "EBAY_CLIENT_SECRET", "EBAY_DELIVERY_POSTAL_CODE")
    for key in keys:
        monkeypatch.setenv(key, "stale-override")
    monkeypatch.setenv("DEX_PROFILE", "staging")

    launcher.main()

    interpreter = sys.executable
    launcher.os.execv.assert_called_once_with(
        interpreter,
        [interpreter, "-I", "-m", "pokemon_hunter.beta.cli", "--root", str(launcher.ROOT), "serve"],
    )
    launcher.os.chdir.assert_called_once_with(launcher.ROOT)
    launcher.webbrowser.open.assert_not_called()
    assert launcher.os.environ["DEX_PROFILE"] == "local"
    assert not any(key in launcher.os.environ for key in keys)
    assert (launcher.ROOT / "inventory.db").read_bytes() == b"existing data"


def test_relative_root_override_is_resolved_before_changing_directory(monkeypatch):
    monkeypatch.setenv("DEX_APP_ROOT", "relative-existing-root")
    spec = importlib.util.spec_from_file_location("start_local_relative", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.ROOT == Path.cwd() / "relative-existing-root"
