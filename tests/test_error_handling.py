"""Owned-resource failure tests; no provider or owner state access."""

import runpy
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from pokemon_hunter.beta.diagnostics import closing


@pytest.mark.parametrize("primary", [None, ValueError("private primary"), KeyboardInterrupt()])
def test_cleanup_is_visible_and_preserves_active_errors(caplog, primary):
    class Resource:
        def close(self):
            raise OSError("SECRET cleanup")

    with pytest.raises(type(primary) if primary is not None else OSError) as caught:
        with closing(Resource(), "synthetic_close_failed"):
            if primary is not None:
                raise primary
    if primary is not None:
        assert caught.value is primary
    assert "synthetic_close_failed" in caplog.text
    assert "SECRET" not in caplog.text
    assert "private primary" not in caplog.text


def test_local_operator_failure_is_redacted(monkeypatch, caplog):
    from pokemon_hunter.beta import cli

    def broken():
        raise OSError("SECRET /private/owner.db")

    monkeypatch.setattr(cli, "main", broken)
    with pytest.raises(SystemExit) as caught:
        cli.entrypoint()
    assert caught.value.code != 0
    assert "local_operation_failed" in caplog.text
    assert "SECRET" not in str(caught.value) + caplog.text
    assert "/private/owner.db" not in str(caught.value) + caplog.text


@pytest.mark.parametrize("exit_code", [0, 1])
def test_scheduler_removal_reports_uncertain_stop(tmp_path, monkeypatch, capsys, exit_code):
    agent = tmp_path / "Library/LaunchAgents/local.pokemon-hunter.daily.plist"
    agent.parent.mkdir(parents=True)
    agent.write_text("synthetic schedule")
    calls = []

    def launchctl(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=exit_code, stderr=b"SECRET subprocess output")

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(subprocess, "run", launchctl)
    monkeypatch.setattr(sys, "argv", ["schedule.py", "--remove"])
    script = Path(__file__).resolve().parents[1] / "scripts/schedule.py"
    with pytest.raises(SystemExit) as caught:
        runpy.run_path(str(script), run_name="__main__")
    assert caught.value.code == 0
    assert not agent.exists()
    assert calls[0][1]["capture_output"] is True
    output = capsys.readouterr()
    assert ("stop was not confirmed" in output.err) is bool(exit_code)
    assert "does not confirm" in output.out
    assert "SECRET" not in output.out + output.err
