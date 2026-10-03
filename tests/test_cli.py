import sqlite3
from pathlib import Path

import pytest
from conftest import synthetic_project

from pokemon_hunter.main import main

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def project(tmp_path):
    synthetic_project(tmp_path)
    return tmp_path


def test_offline_never_network_and_second_run_silent(project, monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        pytest.fail("Offline mode must not call the network")

    monkeypatch.setattr("httpx.Client.request", forbidden)
    monkeypatch.setattr("httpx.post", forbidden)
    monkeypatch.setenv("POKEMON_HUNTER_WEBHOOK_URL", "https://example.invalid/never")
    args = ["--root", str(project), "run", "--fixture", str(ROOT / "tests/fixtures/demo.json")]
    assert main(args) == 0
    assert "OFFLINE DEMO" in capsys.readouterr().out
    report = (project / "reports/demo/latest.txt").read_text()
    assert report.startswith("OFFLINE DEMO")
    assert "19h 42m" in report
    assert "Max bid under card-price and spend limits: $111.00" in report
    assert not (project / "data/pokemon.db").exists()
    assert main(args) == 0
    assert capsys.readouterr().out == ""
    with sqlite3.connect(project / "data/demo.db") as conn:
        assert conn.execute("SELECT count(*) FROM listings").fetchone()[0] == 5


def test_no_credentials_doctor(project, monkeypatch, capsys):
    monkeypatch.delenv("EBAY_CLIENT_ID", raising=False)
    monkeypatch.delenv("EBAY_CLIENT_SECRET", raising=False)
    assert main(["--root", str(project), "doctor"]) == 1
    assert "MISSING: eBay client ID" in capsys.readouterr().out


def test_species_updates_redirect_to_exact_cards(project, capsys):
    before = (project / "config/pokedex_251.json").read_text()
    assert main(["--root", str(project), "pokedex", "--owned", "3", "154"]) == 1
    assert "exact card quantities" in capsys.readouterr().err
    assert (project / "config/pokedex_251.json").read_text() == before
    assert main(["--root", str(project), "pokedex", "--owned", "252"]) == 1


@pytest.mark.parametrize("kind", [ValueError, RuntimeError, FileNotFoundError])
def test_cli_redacts_arbitrary_error_messages(project, monkeypatch, capsys, caplog, kind):
    def broken(*args):
        raise kind("SECRET /private/owner.db https://example.invalid/token")

    monkeypatch.setattr("pokemon_hunter.main.load_config", broken)
    assert main(["--root", str(project), "doctor"]) == 1
    output = capsys.readouterr()
    assert "Watcher failed" in output.err
    assert "watcher_command_failed" in caplog.text
    assert "SECRET" not in output.err + caplog.text
    assert "/private/owner.db" not in output.err + caplog.text


def test_cli_redacts_pydantic_configuration_values(project, capsys, caplog):
    (project / "config/settings.yaml").write_text("environment: SECRET\n")
    assert main(["--root", str(project), "doctor"]) == 1
    assert "ValidationError" in caplog.text
    assert "SECRET" not in capsys.readouterr().err + caplog.text
