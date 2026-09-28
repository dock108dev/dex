"""Synthetic B3 images and provider doubles: no live recognition claims."""

import importlib
import io
import json
import time
import uuid
from unittest.mock import patch

import pytest
from PIL import Image
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b2 import post
from test_migration import snapshot as snapshot

from pokemon_hunter.beta import collection as inv
from pokemon_hunter.beta import scans
from pokemon_hunter.inventory import connect


@pytest.fixture
def b3(b2):
    from django.conf import settings
    from django.db import connection
    from django.urls import clear_url_caches

    from pokemon_hunter.beta import urls

    connection.close()
    with connect(b2["root"] / "inventory.db") as db:
        scans.initialize(db)
    old_root = settings.ROOT
    settings.ROOT = b2["root"]
    settings.B3_ENABLED = True
    (settings.ROOT / "scan-config.json").write_text(json.dumps({"mode": "fixture"}))
    importlib.reload(urls)
    clear_url_caches()
    yield b2
    settings.ROOT = old_root
    settings.B3_ENABLED = False
    importlib.reload(urls)
    clear_url_caches()


def image(size=(400, 600)):
    from django.core.files.uploadedfile import SimpleUploadedFile

    output = io.BytesIO()
    photo = Image.new("RGB", size, "red")
    exif = Image.Exif()
    exif[274] = 6
    exif[270] = "private metadata"
    photo.save(output, "JPEG", exif=exif)
    return SimpleUploadedFile("untrusted.jpg", output.getvalue(), content_type="image/jpeg")


def upload(b3, outcome="valid", client=None):
    c = client or b3["a"]
    r = c.post(
        "/api/scans/",
        {"front": image(), "job_id": str(uuid.uuid4()), "fixture": outcome},
        HTTP_X_CSRFTOKEN=c.cookies["dex_b1_csrf"].value,
    )
    assert r.status_code == 200, r.content
    return r.json()


def action(b3, j, a, data=None, client=None):
    return post(client or b3["a"], f"/api/scans/{j['id']}/{a}/", data or {})


@pytest.mark.parametrize(
    "outcome,state",
    [
        ("valid", "needs-confirmation"),
        ("ambiguous", "needs-confirmation"),
        ("unreadable", "needs-better-photo"),
        ("unsupported", "unsupported"),
        ("failed", "failed"),
    ],
)
def test_job_states_refresh_no_ownership(b3, outcome, state):
    before = inv.copies(b3["actor"])
    j = upload(b3, outcome)
    assert j["state"] == "queued"
    assert scans.process_one()
    r = b3["a"].get(f"/api/scans/{j['id']}/").json()
    assert r["state"] == state and r["mode"] == "fixture"
    assert inv.copies(b3["actor"]) == before


def test_validation_normalization_idempotency_and_limits(b3):
    j = upload(b3)
    content = b3["a"].get("/scan-photos/" + j["photos"][0] + "/")
    assert "no-store" in content["Cache-Control"]
    normalized = Image.open(io.BytesIO(content.content))
    assert normalized.size == (600, 400) and not normalized.getexif()
    assert scans.create(b3["actor"], j["id"], [image()])["id"] == j["id"]
    with pytest.raises(ValueError):
        scans.normalized(image((199, 400)))
    from django.core.files.uploadedfile import SimpleUploadedFile

    with pytest.raises(ValueError):
        scans.normalized(SimpleUploadedFile("x.jpg", b"<svg>bad</svg>"))
    with pytest.raises(ValueError):
        scans.normalized(SimpleUploadedFile("x.jpg", b"x" * 8_000_001))
    (b3["root"] / "scan-config.json").write_text('{"enabled":false}')
    with pytest.raises(ValueError):
        scans.create(b3["actor"], str(uuid.uuid4()), [image()])


def test_confirm_once_second_copy_undo_and_provenance(b3):
    before = len(inv.copies(b3["actor"]))
    j = upload(b3)
    scans.process_one()
    data = {"printing_id": b3["catalog"][0]["id"], "notes": "my correction"}
    first = action(b3, j, "confirm", data)
    assert first.status_code == 200, first.content
    result = first.json()
    assert action(b3, j, "confirm", data).json() == result
    c = inv.one(b3["actor"], "copy", result["copy_id"])
    assert c["notes"] == "my correction" and c["condition"] is None and c["grade"] is None
    assert json.loads(c["provisional_identity"])["scan_job"] == j["id"]
    assert len(inv.copies(b3["actor"])) == before + 1
    second = upload(b3)
    scans.process_one()
    assert action(b3, second, "confirm", data).status_code == 200
    assert len(inv.copies(b3["actor"])) == before + 2
    assert action(b3, j, "undo").status_code == 200
    assert len(inv.copies(b3["actor"])) == before + 1
    assert action(b3, j, "confirm", data).json()["operation"]["state"] == "undone"
    assert b3["a"].get("/scan-photos/" + j["photos"][0] + "/").status_code == 404


def test_provisional_export_and_safe_undo_after_edit(b3):
    j = upload(b3, "unsupported")
    scans.process_one()
    r = action(b3, j, "confirm", {"notes": "Unknown game, keep this"}).json()
    c = inv.one(b3["actor"], "copy", r["copy_id"])
    assert c["printing_id"] is None
    assert any(x["id"] == c["id"] for x in inv.export_data(b3["actor"])["copies"])
    op = inv.preview(
        b3["actor"],
        "edit",
        {"id": c["id"], "revision": c["revision"], "attributes": {"notes": "subsequent edit"}},
        str(uuid.uuid4()),
    )
    inv.confirm(b3["actor"], op["id"])
    assert action(b3, j, "undo").status_code == 409
    assert inv.one(b3["actor"], "copy", c["id"])["notes"] == "subsequent edit"


def test_cross_account_csrf_cancel_and_photo_delete(b3):
    j = upload(b3)
    assert b3["b"].get(f"/api/scans/{j['id']}/").status_code == 404
    assert b3["b"].get("/scan-photos/" + j["photos"][0] + "/").status_code == 404
    assert action(b3, j, "confirm", {}, b3["b"]).status_code == 404
    assert (
        b3["a"].post(f"/api/scans/{j['id']}/cancel/", "{}", content_type="application/json").status_code
        == 403
    )
    assert b3["client"]().get("/scan-photos/" + j["photos"][0] + "/").status_code == 302
    assert action(b3, j, "cancel").status_code == 200
    assert action(b3, j, "confirm").status_code == 400
    assert not scans.process_one()


def test_cancel_during_processing_and_revoke(b3):
    j = upload(b3)
    before = inv.copies(b3["actor"])
    original = scans.match

    def cancel(actor, clues):
        scans.action(actor, j["id"], "cancel", {})
        return original(actor, clues)

    with patch.object(scans, "match", cancel):
        scans.process_one()
    assert scans.job(b3["actor"], j["id"])["state"] == "cancelled"
    assert inv.copies(b3["actor"]) == before
    j = upload(b3, client=b3["b"])
    b3["accounts"].revoke(b3["second"])
    scans.process_one()
    assert not b3["store"].rows("SELECT id FROM scan_photos WHERE job_id=%s", [j["id"]])


def test_retries_crash_recovery_retention(b3):
    j = upload(b3, "failed")
    scans.process_one()
    assert action(b3, j, "retry").status_code == 200
    scans.process_one()
    assert action(b3, j, "retry").status_code == 400
    k = upload(b3)
    inv.execute(
        "UPDATE scan_jobs SET state='processing',started=%s WHERE id=%s", [time.time() - 130, k["id"]]
    )
    scans.process_one()
    assert scans.job(b3["actor"], k["id"])["state"] == "failed"
    inv.execute("UPDATE scan_jobs SET created=0 WHERE id=%s", [k["id"]])
    scans.cleanup()
    assert not scans.job(b3["actor"], k["id"])["photos"]


def test_provider_contract_budget_and_missing_key(b3, monkeypatch):
    (b3["root"] / "scan-config.json").write_text(
        '{"mode":"openai","ceiling_usd":0.05,"user_ceiling_usd":0.05}'
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    j = upload(b3)
    scans.process_one()
    assert "OPENAI_API_KEY" in scans.job(b3["actor"], j["id"])["error"]
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-never-real")
    payload = {
        "status": "completed",
        "usage": {"input_tokens": 1000, "output_tokens": 100},
        "output": [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": json.dumps(
                            dict(
                                status="readable",
                                name="Missing",
                                set_name=None,
                                number=None,
                                language=None,
                                edition=None,
                                finish=None,
                                variant=None,
                            )
                        ),
                    }
                ],
            }
        ],
    }

    class Reply:
        def raise_for_status(self):
            pass

        def json(self):
            return payload

    with patch.object(scans.httpx, "post", return_value=Reply()) as request:
        action(b3, j, "retry")
        scans.process_one()
        sent = request.call_args.kwargs["json"]
        assert sent["store"] is False and sent["max_output_tokens"] == 600 and sent["model"] == scans.MODEL
        assert sent["text"]["format"]["strict"] is True
        assert "tools" not in sent
        assert scans.job(b3["actor"], j["id"])["cost_usd"] == pytest.approx(0.00056)
        k = upload(b3)
        scans.process_one()
        assert "ceiling" in scans.job(b3["actor"], k["id"])["error"]
        assert request.call_count == 1


def test_untrusted_model_schema_and_conflicting_clues(b3):
    with pytest.raises(ValueError):
        scans.Clues.model_validate({"status": "readable", "tool": "delete"})
    p = b3["catalog"][0]
    clue = scans.Clues(
        status="readable",
        name=p["name"],
        set_name="Wrong set",
        number=p["collector_number"],
        language=None,
        edition=None,
        finish=None,
        variant=None,
    )
    assert scans.match(b3["actor"], clue)[0] == "unsupported"


def test_simultaneous_confirmation_and_cross_account_copy(b3):
    from concurrent.futures import ThreadPoolExecutor

    from django.db import close_old_connections

    j = upload(b3)
    scans.process_one()
    before = len(inv.copies(b3["actor"]))

    def confirm():
        close_old_connections()
        try:
            return scans.action(b3["actor"], j["id"], "confirm", {"printing_id": b3["catalog"][0]["id"]})[
                "copy_id"
            ]
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(lambda _: confirm(), range(2)))
    assert ids[0] == ids[1]
    assert len(inv.copies(b3["actor"])) == before + 1
    assert b3["b"].get("/api/inventory/" + ids[0] + "/").status_code == 404
    assert action(b3, j, "delete-photos", client=b3["b"]).status_code == 404
    assert action(b3, j, "undo", client=b3["b"]).status_code == 404


def test_manual_mode_and_deleted_copy_photos(b3):
    (b3["root"] / "scan-config.json").write_text('{"mode":"manual"}')
    j = upload(b3)
    scans.process_one()
    assert scans.job(b3["actor"], j["id"])["result"]["candidates"] == []
    saved = action(b3, j, "confirm", {"notes": "keep privately"}).json()
    op = inv.preview(b3["actor"], "remove", {"id": saved["copy_id"], "revision": 0}, str(uuid.uuid4()))
    inv.confirm(b3["actor"], op["id"])
    assert b3["a"].get("/scan-photos/" + j["photos"][0] + "/").status_code == 404
    scans.cleanup()
    assert not scans.job(b3["actor"], j["id"])["photos"]
