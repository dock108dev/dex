"""Photo recognition contracts over synthetic state and controlled processes."""

import io
import json
import os
import time
import uuid

import pytest
from photo_batch_helpers import BOX, DETECTION, fake, run, success
from PIL import Image

from pokemon_hunter.beta import batch_recognition as protocol
from pokemon_hunter.beta import codex_recognition as cli


def test_subprocess_isolation_attachments_and_cleanup(tmp_path, monkeypatch):
    marker = tmp_path / "directory"
    monkeypatch.setenv("OPENAI_API_KEY", "secret-must-not-leave")
    fake(
        tmp_path,
        monkeypatch,
        f"""
assert set(os.environ)<= {{'HOME','PATH','CODEX_HOME','TMPDIR','LC_CTYPE','__CF_USER_TEXT_ENCODING'}}, sorted(os.environ)
assert 'OPENAI_API_KEY' not in os.environ
assert stat.S_IMODE(Path.cwd().stat().st_mode)==0o700
assert all(stat.S_IMODE(p.stat().st_mode)==0o600 for p in Path.cwd().iterdir())
assert '--ignore-user-config' in args and '--ignore-rules' in args and '--ephemeral' in args
assert 'forced_login_method="chatgpt"' in args
assert 'features.shell_tool=false' in args and 'features.hooks=false' in args
assert 'features.memories=false' in args and 'features.plugins=false' in args
assert 'mcp_servers={{}}' in args and 'plugins={{}}' in args
assert any('"/"="deny"' in a for a in args)
assert 'model_providers.dex_subscription.request_max_retries=0' in args
assert args[args.index('--model')+1]=='gpt-5.6-sol'
assert len([a for a in args if a=='--image'])==1
schema=json.loads(Path(args[args.index('--output-schema')+1]).read_text())
assert schema['additionalProperties'] is False
Path({str(marker)!r}).write_text(str(Path.cwd()))
"""
        + success(),
    )
    result, usage = run(tmp_path)
    assert result == DETECTION and usage == dict(input_tokens=20, output_tokens=3)
    assert not os.path.exists(marker.read_text())


@pytest.mark.parametrize(
    "body,match",
    [
        (
            "print(json.dumps({'type':'item.started','item':{'type':'command_execution'}}))\n" + success(),
            "unsupported",
        ),
        ("print('non-json')\n" + success(), "unsupported"),
        ("print(json.dumps({'type':'tool.call'}))\n" + success(), "unsupported"),
        (
            "Path(args[args.index('-o')+1]).write_text('{}')\nprint(json.dumps({'type':'turn.completed'}))",
            "invalid",
        ),
        ("print('x'*256001)", "stream"),
        ("sys.stderr.write('x'*256001)", "stream"),
        ("Path(args[args.index('-o')+1]).write_text('x'*256001)", "result"),
        ("sys.stderr.write('login expired SECRET');sys.exit(1)", "login"),
        ("sys.stderr.write('usage_limit SECRET');sys.exit(1)", "usage"),
        ("sys.stderr.write('unexpected argument SECRET');sys.exit(1)", "incompatible"),
        ("time.sleep(2)", "deadline"),
        ("Path(args[args.index('-o')+1]).write_text('{}')", "failed"),
    ],
)
def test_real_subprocess_failures(tmp_path, monkeypatch, body, match):
    fake(tmp_path, monkeypatch, body)
    with pytest.raises(cli.RecognitionError, match=match) as exc:
        # Protocol/error cases must reach their output before the separate deadline
        # contract fires, including a cold Python 3.12 interpreter on a busy runner.
        run(tmp_path, timeout=0.3 if match == "deadline" else 3)
    assert "SECRET" not in str(exc.value)


def test_missing_cli_and_shared_lock(tmp_path, monkeypatch):
    import fcntl

    monkeypatch.setattr(cli.shutil, "which", lambda _: None)
    with pytest.raises(cli.RecognitionError, match="missing"):
        run(tmp_path)
    with (tmp_path / "codex-recognition.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(cli.RecognitionError, match="busy"):
            run(tmp_path)


def test_descendant_cleanup_and_independent_stop(tmp_path, monkeypatch):
    pid = tmp_path / "child"
    fake(
        tmp_path,
        monkeypatch,
        f"p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(20)']);Path({str(pid)!r}).write_text(str(p.pid));time.sleep(20)",
    )
    start = time.monotonic()
    with pytest.raises(cli.RecognitionError, match="stopped"):
        run(tmp_path, timeout=2, cancelled=lambda: time.monotonic() - start > 0.15)
    child = int(pid.read_text())
    # Child may briefly be a zombie; it must no longer be executing.
    import subprocess

    state = subprocess.run(
        ["ps", "-o", "stat=", "-p", str(child)], capture_output=True, text=True
    ).stdout.strip()
    assert not state or state.startswith("Z")


@pytest.mark.parametrize(
    "box",
    [
        {**BOX, "width": 1},
        {**BOX, "x": float("nan")},
        {**BOX, "height": 0},
        {**BOX, "rotation": 45},
        {**BOX, "x": True},
        {**BOX, "issues": ["glare", "glare"]},
    ],
)
def test_geometry_rejected(box):
    with pytest.raises(ValueError):
        protocol.Box.model_validate(box)


def test_schema_crop_ids_and_abstention():
    cid = str(uuid.uuid4())
    clue = dict(
        crop_id=cid,
        status="unreadable",
        name=None,
        set_name=None,
        number=None,
        language=None,
        edition=None,
        finish=None,
        variant=None,
        reason="glare",
    )
    payload = dict(schema_version="dex-identities-v1", crops=[clue])
    assert protocol.validate("identity", json.dumps(payload), [cid]) == payload
    for bad in [
        {**payload, "crops": [clue, clue]},
        {**payload, "crops": [{**clue, "name": "guess"}]},
        {**payload, "catalog_id": "made-up"},
    ]:
        with pytest.raises(ValueError):
            protocol.validate("identity", json.dumps(bad), [cid])
    with pytest.raises(ValueError):
        protocol.validate("identity", json.dumps(payload), [str(uuid.uuid4())])
    assert (
        protocol.validate(
            "detection", json.dumps(dict(schema_version="dex-detection-v1", status="refused", boxes=[]))
        )["status"]
        == "refused"
    )
    with pytest.raises(ValueError):
        protocol.validate("detection", json.dumps({**DETECTION, "boxes": [BOX] * 16}))


def test_attachment_dimensions_and_limits():
    out = io.BytesIO()
    Image.new("RGB", (4096, 3000), "green").save(out, "JPEG")
    for edge, ceiling in [(1600, 2_000_000), (1024, 500_000)]:
        content = protocol.attachment(out.getvalue(), edge, ceiling)
        assert len(content) <= ceiling
        with Image.open(io.BytesIO(content)) as im:
            assert max(im.size) <= edge


def test_output_deadline_independent_of_slow_authority(tmp_path, monkeypatch):
    fake(tmp_path, monkeypatch, "time.sleep(5)")
    checks = []

    def authority():
        checks.append(1)
        if len(checks) > 1:
            time.sleep(0.7)
        return False

    start = time.monotonic()
    with pytest.raises(cli.RecognitionError, match="deadline"):
        run(tmp_path, timeout=0.15, cancelled=authority)
    assert time.monotonic() - start < 0.55


def test_registered_crash_payload_cleanup_never_sweeps_unowned(tmp_path):
    home = protocol.payload_home(tmp_path, create=True)
    owned = home / "dex-batch-owned"
    owned.mkdir(mode=0o700)
    unrelated = home / "dex-batch-unregistered"
    unrelated.mkdir(mode=0o700)
    (owned / "selected.jpg").write_bytes(b"engineering pixels")
    registry = home / "owned.jsonl"
    registry.write_text(json.dumps(dict(name=owned.name, created=time.time() - 100)) + "\n")
    protocol.cleanup_payloads(tmp_path)
    assert not owned.exists() and unrelated.exists()
