"""Offline subprocess contract tests; never require a login or API key."""

import fcntl
import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b3 import action, upload
from test_b3 import b3 as b3
from test_migration import snapshot as snapshot

from pokemon_hunter.beta import codex_recognition as cli
from pokemon_hunter.beta import collection as inv
from pokemon_hunter.beta import scans

CLUES = dict(
    status="readable",
    name="Pikachu",
    set_name=None,
    number="58",
    language=None,
    edition=None,
    finish=None,
    variant=None,
)


def fake_cli(tmp_path, monkeypatch, body):
    script = tmp_path / "fake-codex"
    script.write_text(
        f"#!{sys.executable}\nimport sys,os,json,time,stat,subprocess\nfrom pathlib import Path\n"
        "args=sys.argv[1:]\n" + body
    )
    script.chmod(0o700)
    monkeypatch.setattr(cli.shutil, "which", lambda _: str(script))
    return script


def successful(payload=CLUES, usage=None):
    usage = usage or {"input_tokens": 20, "output_tokens": 4}
    return (
        f"Path(args[args.index('-o')+1]).write_text({json.dumps(json.dumps(payload))})\n"
        f"print({json.dumps(json.dumps({'type': 'turn.completed', 'usage': usage}))})\n"
    )


def records(root):
    return [json.loads(line) for line in (root / "codex-usage.jsonl").read_text().splitlines()]


def test_cli_contract_private_cleanup_and_separate_usage(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-leave-dex")
    monkeypatch.setenv("DEX_SECRET", "must-not-leave-dex")
    marker = tmp_path / "cwd.txt"
    fake_cli(
        tmp_path,
        monkeypatch,
        f"""
assert 'OPENAI_API_KEY' not in os.environ and 'DEX_SECRET' not in os.environ
assert stat.S_IMODE(Path.cwd().stat().st_mode) == 0o700
for p in Path.cwd().iterdir():
 assert stat.S_IMODE(p.stat().st_mode) == 0o600
assert '--ignore-user-config' in args and '--ignore-rules' in args and '--ephemeral' in args
assert '--output-schema' in args and '--image' in args and '--' in args
assert args[-2] == '--'
assert 'forced_login_method="chatgpt"' in args
assert 'features.shell_tool=false' in args and 'features.hooks=false' in args
assert 'features.plugins=false' in args and 'features.apps=false' in args
assert 'project_doc_max_bytes=0' in args and 'skills.include_instructions=false' in args
assert any('"/"="deny"' in a and 'network={{enabled=false}}' in a for a in args)
assert 'model_providers.dex_subscription.request_max_retries=0' in args
schema=json.loads(Path(args[args.index('--output-schema')+1]).read_text())
assert schema['additionalProperties'] is False
assert Path(args[args.index('--image')+1]).read_bytes() == b'normalized-image'
Path({str(marker)!r}).write_text(str(Path.cwd()))
"""
        + successful(),
    )
    clue, usage = cli.recognize([b"normalized-image"], tmp_path, job_id="test")
    assert clue.name == "Pikachu" and usage["input_tokens"] == 20
    assert not Path(marker.read_text()).exists()
    row = records(tmp_path)[0]
    assert row["outcome"] == "completed" and row["latency"] >= 0
    assert row["available_usage"] is None and "cost_usd" not in row
    assert (tmp_path / "codex-usage.jsonl").stat().st_mode & 0o077 == 0


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {**CLUES, "name": 12},
        {**CLUES, "inventory_action": "add"},
        {**CLUES, "status": "certain"},
        {**CLUES, "number": "1" * 41},
    ],
)
def test_validated_model_output(tmp_path, monkeypatch, payload):
    fake_cli(tmp_path, monkeypatch, successful(payload))
    with pytest.raises(cli.RecognitionError, match="invalid card details"):
        cli.recognize([b"image"], tmp_path)
    assert records(tmp_path)[0]["outcome"] == "failed"
    assert records(tmp_path)[0]["usage"]["output_tokens"] == 4


@pytest.mark.parametrize(
    "error,expected",
    [
        ("401 authentication expired", "login unavailable"),
        ("429 usage limit reached", "usage limit"),
        ("unexpected argument --image", "incompatible"),
        ("connection refused", "recognition failed"),
    ],
)
def test_redacted_failures(tmp_path, monkeypatch, error, expected):
    fake_cli(tmp_path, monkeypatch, f"print({error!r},file=sys.stderr)\nsys.exit(1)\n")
    with pytest.raises(cli.RecognitionError, match=expected):
        cli.recognize([b"image"], tmp_path)
    assert error not in (tmp_path / "codex-usage.jsonl").read_text()


def test_missing_cli_and_busy(tmp_path, monkeypatch):
    monkeypatch.setattr(cli.shutil, "which", lambda _: None)
    with pytest.raises(cli.RecognitionError, match="missing"):
        cli.recognize([b"image"], tmp_path)
    with (tmp_path / "codex-recognition.lock").open("r+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with pytest.raises(cli.RecognitionError, match="already recognizing"):
            cli.recognize([b"image"], tmp_path)
    assert all(not r["submitted"] for r in records(tmp_path))


@pytest.mark.parametrize("kind", ["cancel", "timeout", "shutdown"])
def test_termination_and_cleanup(tmp_path, monkeypatch, kind):
    marker = tmp_path / "process.json"
    fake_cli(
        tmp_path,
        monkeypatch,
        f"""
child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])
Path({str(marker)!r}).write_text(json.dumps([os.getpid(),child.pid,str(Path.cwd())]))
time.sleep(60)
""",
    )
    monkeypatch.setattr(cli, "TIMEOUT", 0.3 if kind == "timeout" else 3)
    start = time.monotonic()
    with pytest.raises(cli.RecognitionError, match="timed out" if kind == "timeout" else "cancelled"):
        cli.recognize([b"image"], tmp_path, lambda: kind != "timeout" and marker.exists())
    assert time.monotonic() - start < 3
    pid, child, folder = json.loads(marker.read_text())
    assert not Path(folder).exists()
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
    # A dead child can briefly be a zombie until reaped by init on CI.
    import subprocess

    status = subprocess.run(
        ["ps", "-o", "stat=", "-p", str(child)], capture_output=True, text=True
    ).stdout.strip()
    assert not status or status.startswith("Z")
    assert records(tmp_path)[0]["outcome"] == ("timeout" if kind == "timeout" else "cancelled")


def test_output_bound_and_tool_action_rejection(tmp_path, monkeypatch):
    fake_cli(tmp_path, monkeypatch, "print('x'*300000)\n")
    with pytest.raises(cli.RecognitionError, match="exceeded"):
        cli.recognize([b"image"], tmp_path)
    fake_cli(
        tmp_path,
        monkeypatch,
        "print(json.dumps({'type':'item.completed','item':{'type':'command_execution'}}))\n" + successful(),
    )
    with pytest.raises(cli.RecognitionError, match="unsupported action"):
        cli.recognize([b"image"], tmp_path)


def test_cli_shared_confirmation_undo_and_no_api_spend(b3):
    (b3["root"] / "scan-config.json").write_text('{"mode":"codex_cli","ceiling_usd":0,"user_ceiling_usd":0}')
    p = b3["catalog"][0]
    clues = scans.Clues(
        **{**CLUES, "name": p["name"], "number": p["collector_number"], "set_name": p["set_name"]}
    )
    before = len(inv.copies(b3["actor"]))
    with (
        patch.object(cli, "recognize", return_value=(clues, {"input_tokens": 20})),
        patch.object(scans, "recognize") as api,
    ):
        j = upload(b3)
        scans.process_one()
        result = scans.job(b3["actor"], j["id"])
        assert result["mode"] == "codex_cli" and result["model"] == cli.MODEL
        assert result["state"] == "needs-confirmation" and result["result"]["candidates"][0]["id"] == p["id"]
        assert result["reserved_usd"] == 0 and result["cost_usd"] is None
        assert len(inv.copies(b3["actor"])) == before
        first = action(b3, j, "confirm", {"printing_id": p["id"], "notes": "manual correction"}).json()
        assert action(b3, j, "confirm", {"printing_id": p["id"]}).json()["copy_id"] == first["copy_id"]
        assert len(inv.copies(b3["actor"])) == before + 1
        assert action(b3, j, "undo").status_code == 200
        assert len(inv.copies(b3["actor"])) == before
        api.assert_not_called()


def test_cli_failure_retry_cancel_and_provider_switch(b3):
    (b3["root"] / "scan-config.json").write_text('{"mode":"codex_cli"}')
    with (
        patch.object(
            cli, "recognize", side_effect=cli.RecognitionError("Codex usage limit reached. Choose manually.")
        ),
        patch.object(scans, "recognize") as api,
    ):
        j = upload(b3)
        scans.process_one()
        assert "usage limit" in scans.job(b3["actor"], j["id"])["error"]
        action(b3, j, "retry")
        scans.process_one()
        assert action(b3, j, "retry").status_code == 400
        assert action(b3, j, "confirm", {"notes": "manual unidentified"}).status_code == 200
        api.assert_not_called()
    j = upload(b3)

    def cancel(images, root, cancelled, job_id):
        action(b3, j, "cancel")
        assert cancelled()
        raise cli.RecognitionError("Recognition cancelled.")

    with patch.object(cli, "recognize", side_effect=cancel):
        scans.process_one()
    result = scans.job(b3["actor"], j["id"])
    assert result["state"] == "cancelled" and not result["photos"] and result["latency"] is not None
    j = upload(b3)
    (b3["root"] / "scan-config.json").write_text('{"mode":"openai"}')
    with patch.object(cli, "recognize") as codex, patch.object(scans, "recognize") as api:
        scans.process_one()
        assert "provider changed" in scans.job(b3["actor"], j["id"])["error"]
        codex.assert_not_called()
        api.assert_not_called()


def test_unknown_provider_and_global_cli_concurrency(b3):
    (b3["root"] / "scan-config.json").write_text('{"mode":"codex_cli"}')
    first = upload(b3)
    inv.execute("UPDATE scan_jobs SET state='processing',started=%s WHERE id=%s", [time.time(), first["id"]])
    second = upload(b3)
    with patch.object(cli, "recognize") as codex:
        assert not scans.process_one()
        assert scans.job(b3["actor"], second["id"])["state"] == "queued"
        codex.assert_not_called()
    (b3["root"] / "scan-config.json").write_text('{"mode":"typo"}')
    with pytest.raises(ValueError, match="Invalid scan configuration"):
        scans.create(b3["actor"], "12345678-1234-1234-1234-123456789012", [])
