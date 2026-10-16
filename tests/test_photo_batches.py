"""Photo-batch controls with fake subprocesses and synthetic images."""

import io
import json
import os
import sys
import time
import uuid

import pytest
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import Http404
from PIL import Image
from test_b3 import image
from test_bulk_onboarding import b2, b3, b4, bulk, cx, e1, env, snapshot
from test_effective_collection import apply

from pokemon_hunter.beta import batch_recognition as protocol
from pokemon_hunter.beta import codex_recognition as cli
from pokemon_hunter.beta import collection as inv
from pokemon_hunter.beta import collection_drafts as drafts
from pokemon_hunter.beta import photo_batches as batches
from pokemon_hunter.beta import scans, store

__all__ = ["b2", "b3", "b4", "bulk", "cx", "e1", "env", "snapshot"]
BOX = dict(x=0.05, y=0.05, width=0.8, height=0.8, rotation=0, issues=[])
DETECTION = dict(schema_version="dex-detection-v1", status="proposed", boxes=[BOX])


@pytest.fixture
def photos(bulk):
    batches.initialize()
    batches.initialize()
    (settings.ROOT / "scan-config.json").write_text('{"mode":"codex_cli"}')
    bulk["session"] = bulk["a"].session.session_key
    return bulk


def staged(cx):
    a = cx["actor"]
    b = batches.create(a, str(uuid.uuid4()))
    return batches.admit(
        a, b["id"], b["revision"], image((400 + len(store.rows("SELECT id FROM scan_batches")), 600))
    )


def cropped(cx, b=None, n=1):
    b = b or staged(cx)
    return batches.layout(
        cx["actor"], b["id"], b["revision"], b["photos"][-1]["id"], [dict(id=None, box=BOX) for _ in range(n)]
    )


def selected(cx, b=None, n=1, retain=True):
    b = cropped(cx, b, n)
    for c in b["crops"]:
        if c["state"] == "active":
            b = batches.select_crop(
                cx["actor"],
                b["id"],
                b["revision"],
                c["id"],
                dict(printing_id=cx["by_legacy"]["c"]["id"]),
                True,
                retain,
                "different",
            )
    return b


def fake(tmp_path, monkeypatch, body):
    p = tmp_path / "fake-codex"
    p.write_text(
        f"#!{sys.executable}\nimport sys,os,json,time,stat,subprocess\nfrom pathlib import Path\nargs=sys.argv[1:]\n"
        + body
    )
    p.chmod(0o700)
    monkeypatch.setattr(cli.shutil, "which", lambda _: str(p))
    return p


def success(payload=DETECTION, usage=True):
    return f"Path(args[args.index('-o')+1]).write_text({json.dumps(json.dumps(payload))})\nprint({json.dumps(json.dumps(dict(type='turn.completed', **({'usage': {'input_tokens': 20, 'output_tokens': 3}} if usage else {}))))})\n"


def run(tmp_path, stage="detection", crop_ids=(), cancelled=lambda: False, timeout=1):
    im = io.BytesIO()
    Image.new("RGB", (400, 600), "blue").save(im, "JPEG")
    return cli.recognize_batch(
        stage, [im.getvalue()] * (len(crop_ids) or 1), tmp_path, cancelled, timeout, crop_ids
    )


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
        run(tmp_path, timeout=0.3)
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


def test_migration_additive_metadata_and_replay(photos):
    cx = photos
    a = cx["actor"]
    before = inv.copies(a)
    b = staged(cx)
    p = batches.photo(a, b["id"], b["photos"][0]["id"])
    im = Image.open(io.BytesIO(bytes(p["content"])))
    assert im.size == (600, 401) and not im.getexif()
    same = batches.admit(a, b["id"], b["revision"], image((401, 600)))
    assert same["revision"] == b["revision"] and len(same["photos"]) == 1
    assert inv.copies(a) == before
    cols = store.rows("SELECT * FROM scan_jobs")
    batches.initialize()
    assert store.rows("SELECT * FROM scan_jobs") == cols


def test_manual_path_handoff_atomic_confirm_receipt_undo_crop_retention(photos):
    cx = photos
    a = cx["actor"]
    b = selected(cx, n=2)
    before = len(inv.copies(a))
    hand = batches.handoff(a, b["id"], b["revision"], True, [])
    d = hand["draft"]
    assert len(inv.copies(a)) == before
    op = drafts.review(a, d["id"], d["revision"])["operation"]
    assert op["plan"]["photo_review"]["physical_duplicates_reviewed"]
    assert not op["plan"]["errors"]
    done = drafts.confirm(a, d["id"], d["revision"])
    assert len(inv.copies(a)) == before + 2
    assert drafts.confirm(a, d["id"], d["revision"]) == done
    retained = scans.authorized_photo_rows(a)
    assert len(retained) == 2 and all(p["copy_id"] for p in retained)
    assert all(not p["content"] for p in store.rows("SELECT content FROM scan_batch_photos"))
    inv.undo(a, done["id"])
    assert len(inv.copies(a)) == before and not scans.authorized_photo_rows(a)
    assert all(not c["content"] for c in store.rows("SELECT content FROM scan_batch_crops"))
    assert batches.reservations(b["id"]) == {}


def test_exclusion_same_printing_is_not_physical_duplicate(photos):
    cx = photos
    a = cx["actor"]
    b = cropped(cx, n=2)
    first, second = b["crops"]
    b = batches.select_crop(
        a,
        b["id"],
        b["revision"],
        first["id"],
        dict(printing_id=cx["by_legacy"]["c"]["id"]),
        True,
        False,
        "different",
    )
    with pytest.raises(ValueError, match="distinct"):
        batches.select_crop(a, b["id"], b["revision"], second["id"], {}, True, False, "same")
    b = batches.select_crop(a, b["id"], b["revision"], second["id"], {}, False, False, "same")
    with pytest.raises(ValueError, match="duplicates"):
        batches.handoff(a, b["id"], b["revision"], False, [])
    d = batches.handoff(a, b["id"], b["revision"], True, [])["draft"]
    op = drafts.review(a, d["id"], d["revision"])["operation"]
    assert op["plan"]["photo_review"]["excluded_crops"] == [second["id"]]
    assert len(op["plan"]["creates"]) == 1


def test_attempts_shared_serialization_and_no_retries(photos, tmp_path, monkeypatch):
    cx = photos
    a = cx["actor"]
    b = staged(cx)
    pid = b["photos"][0]["id"]
    fake(tmp_path, monkeypatch, success())
    b = batches.analyze(a, b["id"], b["revision"], pid, "detection", cx["session"], protocol.CONSENT)
    assert b["attempts"] == 1
    with pytest.raises(inv.Conflict):
        batches.analyze(a, b["id"], b["revision"], pid, "detection", cx["session"], protocol.CONSENT)
    assert batches.process_one()
    b = batches.detail(a, b["id"])
    assert b["photos"][0]["proposal"] == DETECTION and b["remaining_active_seconds"] > 179, b["stages"]
    assert not batches.process_one()  # Read/reopen/worker never retries.
    b = batches.analyze(a, b["id"], b["revision"], pid, "detection", cx["session"], protocol.CONSENT)
    assert batches.process_one()
    b = batches.detail(a, b["id"])
    with pytest.raises(ValueError, match="Attempt"):
        batches.analyze(a, b["id"], b["revision"], pid, "detection", cx["session"], protocol.CONSENT)
    records = batches.journal()
    assert len([r for r in records if r["event"] == "reserve"]) == 2
    assert all(r["cost_usd"] is None for r in records if r["event"] == "settle")
    assert store.rows("SELECT sum(reserved_usd) AS n FROM scan_jobs")[0]["n"] is None


def test_stop_before_dispatch_keeps_consumed_and_recovery_no_resend(photos):
    cx = photos
    a = cx["actor"]
    b = staged(cx)
    pid = b["photos"][0]["id"]
    b = batches.analyze(a, b["id"], b["revision"], pid, "detection", cx["session"], protocol.CONSENT)
    batches.stop_analysis(a, b["id"])
    assert not batches.process_one()
    assert batches.detail(a, b["id"])["attempts"] == 1
    assert batches.reservations(b["id"])[b["stages"][0]["id"]]["charged"] == 75
    with pytest.raises(ValueError, match="exhausted"):
        batches.analyze(a, b["id"], b["revision"], pid, "detection", cx["session"], protocol.CONSENT)


def test_cross_account_revocation_and_generic_cancel_immediate(photos):
    cx = photos
    a = cx["actor"]
    b = selected(cx)
    cid = b["crops"][0]["id"]
    pid = b["photos"][0]["id"]
    other = store.principal(cx["second"].pk)
    with pytest.raises(Http404):
        batches.get(other, b["id"])
    assert not scans.authorized_photo_rows(other, cid)
    hand = batches.handoff(a, b["id"], b["revision"], True, [])
    d = hand["draft"]
    drafts.cancel(a, d["id"], d["revision"])
    with pytest.raises(Http404):
        batches.photo(a, b["id"], pid)
    assert not scans.authorized_photo_rows(a, cid)
    batches.cleanup()
    assert all(not c["content"] for c in store.rows("SELECT content FROM scan_batch_crops"))
    assert cid in batches.tombstones()


def test_expiry_stale_revision_and_restored_tombstone(photos):
    cx = photos
    a = cx["actor"]
    b = cropped(cx)
    pid = b["photos"][0]["id"]
    cid = b["crops"][0]["id"]
    with pytest.raises(inv.Conflict):
        batches.layout(a, b["id"], 1, pid, [])
    old = store.rows("SELECT content FROM scan_batch_crops WHERE id=%s", [cid])[0]["content"]
    batches.cancel(a, b["id"])
    inv.execute("UPDATE scan_batch_crops SET state='active',content=%s WHERE id=%s", [old, cid])
    inv.execute("UPDATE scan_batches SET state='editing' WHERE id=%s", [b["id"]])
    assert not scans.authorized_photo_rows(a, cid)
    batches.cleanup()
    assert not store.rows("SELECT content FROM scan_batch_crops WHERE id=%s", [cid])[0]["content"]
    b = cropped(cx)
    pid = b["photos"][0]["id"]
    inv.execute("UPDATE scan_batch_photos SET created=%s WHERE id=%s", [time.time() - 8 * 86400, pid])
    with pytest.raises(Http404):
        batches.photo(a, b["id"], pid)
    assert not scans.authorized_photo_rows(a)


def test_session_expiry_pre_dispatch_and_late_publication(photos, tmp_path, monkeypatch):
    cx = photos
    a = cx["actor"]
    b = staged(cx)
    pid = b["photos"][0]["id"]
    b = batches.analyze(a, b["id"], b["revision"], pid, "detection", cx["session"], protocol.CONSENT)
    cx["a"].logout()
    assert batches.process_one()
    assert batches.detail(a, b["id"])["stages"][0]["state"] == "cancelled"
    assert not batches.detail(a, b["id"])["photos"][0]["proposal"]


def test_admission_limits_shared_with_single_cards(photos):
    cx = photos
    a = cx["actor"]
    b = staged(cx)
    for n in range(4):
        b = batches.admit(a, b["id"], b["revision"], image((402 + n, 600)))
    batches.remove_photo(a, b["id"], b["revision"], b["photos"][0]["id"])
    b = batches.detail(a, b["id"])
    with pytest.raises(ValueError, match="Five"):
        batches.admit(a, b["id"], b["revision"], image((440, 600)))
    for n in range(15):
        batches.append("single_admit", job_id=str(uuid.uuid4()), user_id=a.user_id, count=1)
    with pytest.raises(ValueError, match="20"):
        scans.create(a, str(uuid.uuid4()), [image()])


def test_retake_preserves_crop_ids_and_consumes_admission(photos):
    cx = photos
    a = cx["actor"]
    b = selected(cx)
    pid, cid = b["photos"][0]["id"], b["crops"][0]["id"]
    b = batches.retake(a, b["id"], b["revision"], pid, image((450, 650)), True)
    assert len(b["photos"]) == 2
    assert b["photos"][0]["state"] == "deleted"
    c = next(c for c in b["crops"] if c["id"] == cid)
    assert c["state"] == "active" and c["revision"] == 2 and not c["proposal"] and not c["included"]
    assert c["photo_id"] != pid
    assert not next(p for p in b["photos"] if p["id"] == c["photo_id"])["reviewed"]
    assert batches.recent_admissions(a) == 2


def test_identity_stage_actual_subprocess_exact_ids_and_bounded_crops(photos, tmp_path, monkeypatch):
    cx = photos
    b = cropped(cx, n=15)
    cid = [c["id"] for c in b["crops"]]
    clue = dict(
        status="unreadable",
        name=None,
        set_name=None,
        number=None,
        language=None,
        edition=None,
        finish=None,
        variant=None,
        reason="fixture: no readable text",
    )
    payload = dict(schema_version="dex-identities-v1", crops=[dict(crop_id=k, **clue) for k in cid])
    fake(tmp_path, monkeypatch, "assert args.count('--image')==15\n" + success(payload, usage=False))
    pid = b["photos"][0]["id"]
    b = batches.analyze(cx["actor"], b["id"], b["revision"], pid, "identity", cx["session"], protocol.CONSENT)
    assert batches.process_one()
    b = batches.detail(cx["actor"], b["id"])
    assert b["stages"][0]["state"] == "completed"
    assert all(c["proposal"]["status"] == "unreadable" and not c["candidates"] for c in b["crops"])
    assert b["stages"][0]["usage"] == "null"
    assert b["remaining_capacity"] is None and b["cost_usd"] is None


def test_identity_edit_invalidates_and_flags_abstain(photos):
    cx = photos
    a = cx["actor"]
    b = cropped(cx)
    c = b["crops"][0]
    inv.execute(
        "UPDATE scan_batch_crops SET proposal=%s WHERE id=%s",
        [json.dumps(dict(status="readable", name="Venusaur", number="18")), c["id"]],
    )
    b = batches.layout(
        a,
        b["id"],
        b["revision"],
        c["photo_id"],
        [dict(id=c["id"], box={**BOX, "rotation": 90, "issues": ["glare"]})],
    )
    assert not b["crops"][0]["proposal"] and b["crops"][0]["revision"] == 2
    assert not b["crops"][0]["included"]


def test_limits_ten_attempts_two_stages_and_deadline_remainders(photos):
    cx = photos
    a = cx["actor"]
    b = cropped(cx)
    pid = b["photos"][0]["id"]
    # A recovered invocation with no settlement consumes its entire deadline.
    aid = str(uuid.uuid4())
    batches.append("reserve", id=aid, batch_id=b["id"], photo_id=pid, stage="detection", allowance=60)
    b = batches.analyze(a, b["id"], b["revision"], pid, "identity", cx["session"], protocol.CONSENT)
    assert b["stages"][-1]["allowance"] == 15
    batches.stop_analysis(a, b["id"])
    with pytest.raises(ValueError, match="exhausted"):
        batches.analyze(a, b["id"], b["revision"], pid, "detection", cx["session"], protocol.CONSENT)
    b = cropped(cx)
    pid = b["photos"][0]["id"]
    for i in range(9):
        aid = str(uuid.uuid4())
        batches.append(
            "reserve",
            id=aid,
            batch_id=b["id"],
            photo_id="historical-" + str(i),
            stage="detection",
            allowance=20,
        )
        batches.append("settle", id=aid, elapsed=19.5)
    b = batches.analyze(a, b["id"], b["revision"], pid, "detection", cx["session"], protocol.CONSENT)
    assert b["attempts"] == 10 and b["stages"][-1]["allowance"] == 4.5
    batches.stop_analysis(a, b["id"])
    with pytest.raises(ValueError, match="Attempt"):
        batches.analyze(a, b["id"], b["revision"], pid, "identity", cx["session"], protocol.CONSENT)


def test_crash_uncertainty_and_restored_database_do_not_replenish_attempts(photos):
    cx = photos
    a = cx["actor"]
    b = staged(cx)
    pid = b["photos"][0]["id"]
    b = batches.analyze(a, b["id"], b["revision"], pid, "detection", cx["session"], protocol.CONSENT)
    inv.execute("UPDATE scan_batch_stages SET state='processing',started=%s", [time.time() - 100])
    batches.cleanup()
    assert batches.detail(a, b["id"])["stages"][0]["state"] == "failed"
    assert not batches.process_one()
    inv.execute("DELETE FROM scan_batch_stages")  # Simulate a database predating its external reservation.
    assert batches.detail(a, b["id"])["attempts"] == 1
    with pytest.raises(ValueError, match="exhausted"):
        batches.analyze(a, b["id"], b["revision"], pid, "detection", cx["session"], protocol.CONSENT)


def test_revision_and_stop_guard_publication(photos, tmp_path, monkeypatch):
    cx = photos
    a = cx["actor"]
    b = staged(cx)
    pid = b["photos"][0]["id"]
    fake(tmp_path, monkeypatch, success())
    real = cli.recognize_batch

    def late(*args, **kwargs):
        result = real(*args, **kwargs)
        batches.stop_analysis(a, b["id"])
        return result

    monkeypatch.setattr(cli, "recognize_batch", late)
    batches.analyze(a, b["id"], b["revision"], pid, "detection", cx["session"], protocol.CONSENT)
    batches.process_one()
    b = batches.detail(a, b["id"])
    assert b["stages"][0]["state"] == "cancelled" and not b["photos"][0]["proposal"]


def test_single_card_and_batch_claims_serialize(photos):
    cx = photos
    a = cx["actor"]
    b = staged(cx)
    j = scans.create(a, str(uuid.uuid4()), [image()])
    b = batches.analyze(
        a, b["id"], b["revision"], b["photos"][0]["id"], "detection", cx["session"], protocol.CONSENT
    )
    inv.execute("UPDATE scan_batch_stages SET state='processing',started=%s", [time.time()])
    assert not scans.process_one()
    batches.stop_analysis(a, b["id"])
    inv.execute("UPDATE scan_jobs SET state='processing',started=%s WHERE id=%s", [time.time(), j["id"]])
    with pytest.raises(ValueError, match="One CLI"):
        batches.analyze(
            a, b["id"], b["revision"], b["photos"][0]["id"], "detection", cx["session"], protocol.CONSENT
        )


def test_removed_copy_revokes_retained_crop_before_cleanup(photos):
    cx = photos
    a = cx["actor"]
    b = selected(cx)
    d = batches.handoff(a, b["id"], b["revision"], True, [])["draft"]
    drafts.review(a, d["id"], d["revision"])
    op = drafts.confirm(a, d["id"], d["revision"])
    cid = op["changes"][0]["after"]["id"]
    assert scans.authorized_photo_rows(a)
    apply(a, "remove", dict(id=cid, revision=0))
    assert not scans.authorized_photo_rows(a)
    assert not store.rows("SELECT content FROM scan_batch_crops")[0]["content"]


def test_account_revocation_immediate_bytes_and_cleanup(photos):
    cx = photos
    a = cx["actor"]
    b = cropped(cx)
    inv.execute("UPDATE users SET state='revoked' WHERE id=%s", [a.user_id])
    with pytest.raises(PermissionDenied):
        scans.authorized_photo_rows(a)
    batches.cleanup()
    assert all(not c["content"] for c in store.rows("SELECT content FROM scan_batch_crops"))
    assert b["id"] in batches.tombstones()


def test_manual_duplicate_rows_and_generic_plan_guard(photos):
    cx = photos
    a = cx["actor"]
    b = selected(cx)
    manual = dict(row_id="manual-object", printing_id=cx["by_legacy"]["c"]["id"])
    with pytest.raises(ValueError, match="manual-row"):
        batches.handoff(a, b["id"], b["revision"], True, [manual])
    d = batches.handoff(a, b["id"], b["revision"], True, [dict(manual, duplicate_decision="different")])[
        "draft"
    ]
    review = drafts.review(a, d["id"], d["revision"])["operation"]
    assert len(review["plan"]["creates"]) == 2
    changed = d["input_json"]
    changed["rows"][0]["quantity"] = 2
    d = drafts.save(a, changed, d["id"], d["revision"])
    with pytest.raises(inv.Conflict):
        drafts.review(a, d["id"], d["revision"])
    assert not store.rows("SELECT id FROM owned_copies WHERE batch_id=%s", [review["id"]])


def test_http_flow_csrf_binding_and_other_account(photos):
    import re

    cx = photos
    c = cx["a"]
    page = c.get("/add-photos/")
    assert page.status_code == 200
    binding = re.search(r'data-navigation-binding="([a-f0-9]+)"', page.content.decode())[1]
    headers = dict(HTTP_X_CSRFTOKEN=c.cookies["dex_b1_csrf"].value, HTTP_X_DEX_BINDING=binding)
    assert (
        c.post(
            "/api/photo-batches/create/",
            json.dumps(dict(id=str(uuid.uuid4()))),
            content_type="application/json",
        ).status_code
        == 403
    )
    response = c.post(
        "/api/photo-batches/create/",
        json.dumps(dict(id=str(uuid.uuid4()))),
        content_type="application/json",
        **headers,
    )
    assert response.status_code == 200
    b = response.json()["batch"]
    uploaded = c.post(
        f"/api/photo-batches/{b['id']}/upload/", dict(photo=image(), revision=b["revision"]), **headers
    )
    assert uploaded.status_code == 200
    assert cx["b"].get(f"/api/photo-batches/{b['id']}/").status_code == 404
    pid = uploaded.json()["batch"]["photos"][0]["id"]
    served = c.get(f"/api/photo-batches/{b['id']}/photos/{pid}/")
    assert served.status_code == 200 and "no-store" in served["Cache-Control"]
    assert c.get("/collection-assets/photo_batches.js").status_code == 200
    assert c.get("/collection-assets/photo_batches.css").status_code == 200


@pytest.mark.parametrize("kind", ["animated", "pixels", "small", "bytes", "format"])
def test_source_limits(photos, kind):
    from django.core.files.uploadedfile import SimpleUploadedFile

    if kind == "bytes":
        upload = SimpleUploadedFile("x", b"x" * 8_000_001)
    elif kind == "format":
        upload = SimpleUploadedFile("x", b"<svg>no</svg>")
    else:
        out = io.BytesIO()
        size = (5000, 5000) if kind == "pixels" else (199, 300) if kind == "small" else (300, 300)
        im = Image.new("RGB", size, "blue")
        if kind == "animated":
            im.save(out, "PNG", save_all=True, append_images=[Image.new("RGB", size, "red")])
        else:
            im.save(out, "PNG")
        upload = SimpleUploadedFile("x", out.getvalue())
    with pytest.raises(ValueError):
        batches.source(upload)


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


def test_duplicate_hints_do_not_merge_and_delete_photos_keeps_collection(photos):
    cx = photos
    a = cx["actor"]
    b = selected(cx, n=2)
    assert len(b["possible_duplicates"]) == 1 and b["possible_duplicates"][0]["same_printing"]
    assert len([c for c in b["crops"] if c["included"]]) == 2
    d = batches.handoff(a, b["id"], b["revision"], True, [])["draft"]
    drafts.review(a, d["id"], d["revision"])
    op = drafts.confirm(a, d["id"], d["revision"])
    before = inv.copies(a)
    batches.delete_images(a, b["id"])
    assert inv.copies(a) == before and inv.operation(a, op["id"])["state"] == "confirmed"
    assert not scans.authorized_photo_rows(a)


def test_cross_batch_same_photo_resumes_original_without_new_admission(photos):
    cx = photos
    a = cx["actor"]
    first = staged(cx)
    second = batches.create(a, str(uuid.uuid4()))
    replay = batches.admit(a, second["id"], second["revision"], image((401, 600)))
    assert replay["id"] == first["id"] and batches.recent_admissions(a) == 1


def test_glare_never_publishes_readable_model_identity(photos, tmp_path, monkeypatch):
    cx = photos
    a = cx["actor"]
    b = cropped(cx)
    c = b["crops"][0]
    b = batches.layout(
        a, b["id"], b["revision"], c["photo_id"], [dict(id=c["id"], box={**BOX, "issues": ["glare"]})]
    )
    clue = dict(
        crop_id=c["id"],
        status="readable",
        name="Venusaur",
        set_name="Base Set 2",
        number="18",
        language="en",
        edition=None,
        finish=None,
        variant=None,
        reason=None,
    )
    fake(tmp_path, monkeypatch, success(dict(schema_version="dex-identities-v1", crops=[clue])))
    batches.analyze(a, b["id"], b["revision"], c["photo_id"], "identity", cx["session"], protocol.CONSENT)
    batches.process_one()
    b = batches.detail(a, b["id"])
    assert b["crops"][0]["proposal"]["status"] == "unreadable"
    assert not b["crops"][0]["candidates"]
