"""Removed provider paths cannot be reactivated; uploads and review survive."""

import importlib.util
import json
import runpy
import time
import uuid
from pathlib import Path

import pytest
from photo_batch_helpers import photos, selected, staged
from test_b3 import action, image, upload
from test_bulk_onboarding import b2, b3, b4, bulk, cx, e1, env, snapshot

from pokemon_hunter.beta import collection, scan_config, scans, store
from pokemon_hunter.beta import photo_batches as batches

__all__ = ["b2", "b3", "b4", "bulk", "cx", "e1", "env", "snapshot", "photos"]


@pytest.mark.parametrize("mode", ["codex_cli", "openai", "fixture", "manual"])
def test_saved_settings_and_credentials_cannot_enable_ai(b3, monkeypatch, mode):
    monkeypatch.setattr(scan_config, "recognition_enabled", lambda: False)
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-never-used")
    monkeypatch.setenv("PHOTO_RECOGNITION_ENABLED", "true")
    path = b3["root"] / "scan-config.json"
    saved = json.dumps(dict(mode=mode))
    path.write_text(saved)
    before = len(collection.copies(b3["actor"]))
    job = upload(b3)
    assert job["mode"] == "manual" and job["model"] == ""
    assert scans.process_one()
    job = scans.job(b3["actor"], job["id"])
    assert job["state"] == "needs-confirmation" and job["photos"]
    printing = collection.catalog(b3["actor"])[0]["id"]
    assert action(b3, job, "confirm", dict(printing_id=printing)).status_code == 200
    assert len(collection.copies(b3["actor"])) == before + 1
    assert path.read_text() == saved
    page = b3["a"].get("/scan/")
    assert scan_config.UNAVAILABLE.encode() in page.content
    assert b"Photos go to OpenAI" not in page.content


@pytest.mark.parametrize("mode", ["codex_cli", "openai"])
@pytest.mark.parametrize("state", ["queued", "processing"])
def test_historical_jobs_stop_without_erasing_photos_results_or_accounting(b3, monkeypatch, mode, state):
    monkeypatch.setattr(scan_config, "recognition_enabled", lambda: False)
    job = upload(b3)
    result = json.dumps(dict(notice="historical evidence"))
    collection.execute(
        "UPDATE scan_jobs SET mode=%s,state=%s,result=%s,started=%s,attempts=1,reserved_usd=0.05 WHERE id=%s",
        [mode, state, result, time.time(), job["id"]],
    )
    before = store.rows("SELECT * FROM scan_photos")
    scans.select_current_process()  # Restart never exempts historical provider work.
    assert scans.process_one() is False
    job = scans.job(b3["actor"], job["id"])
    assert job["state"] == "failed" and job["mode"] == mode
    assert job["attempts"] == 1 and job["reserved_usd"] == 0.05
    assert job["result"] == json.loads(result)
    assert store.rows("SELECT * FROM scan_photos") == before
    response = action(b3, job, "retry")
    assert response.status_code == 409 and response.json()["error"] == scan_config.UNAVAILABLE


def test_no_provider_implementation_or_runtime_enable_flag(monkeypatch):
    # No credentials, settings toggle or monkeypatched transport can reach removed code.
    for name in ("codex_recognition", "batch_recognition"):
        assert importlib.util.find_spec("pokemon_hunter.beta." + name) is None
    assert not hasattr(scans, "recognize")
    root = Path(scans.__file__).parent
    monkeypatch.setenv("PHOTO_RECOGNITION_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-unused")
    policy = runpy.run_path(str(root / "scan_config.py"))
    assert policy["recognition_enabled"]() is False
    assert policy["effective_mode"]({"mode": "codex_cli"}) == "manual"
    with pytest.raises(ValueError, match="temporarily unavailable"):
        policy["require_recognition"]()
    source = (root / "scan_config.py").read_text()
    assert "PHOTO_RECOGNITION_ENABLED" not in source
    assert "PHOTO_RECOGNITION_ENABLED" not in (root / "settings.py").read_text()
    for name in ("scans.py", "photo_batches.py", "photo_contracts.py"):
        text = (root / name).read_text()
        for forbidden in ("api.openai.com", "OPENAI_API_KEY", "subprocess", "recognize_batch"):
            assert forbidden not in text
    for name in ("evaluate_codex_photos.py", "verify_on02.py", "serve_on02_engineering.py"):
        assert not (root.parents[2] / "scripts" / name).exists()
    for template in (root / "templates/beta").glob("*.html"):
        assert "Codex" not in template.read_text()


@pytest.mark.parametrize("state", ["queued", "processing"])
def test_batch_retirement_preserves_manual_photos_reviews_and_consumption(photos, monkeypatch, state):
    monkeypatch.setattr(scan_config, "recognition_enabled", lambda: False)
    actor = photos["actor"]
    b = selected(photos)
    pid, aid = b["photos"][0]["id"], str(uuid.uuid4())
    # Reconstruct an old persisted claim as test data, without admitting new AI work.
    batches.append("reserve", id=aid, batch_id=b["id"], photo_id=pid, stage="photo", allowance=75)
    collection.execute(
        "INSERT INTO scan_batch_stages(id,batch_id,photo_id,user_id,stage,photo_revision,session_key,state,created,allowance) VALUES(%s,%s,%s,%s,'photo',1,%s,%s,%s,75)",
        [aid, b["id"], pid, actor.user_id, photos["session"], state, time.time()],
    )
    reservations = batches.reservations(b["id"])
    crops = store.rows("SELECT * FROM scan_batch_crops")
    images = store.rows("SELECT * FROM scan_batch_photos")
    assert batches.process_one() is False
    assert batches.reservations(b["id"]) == reservations
    assert store.rows("SELECT * FROM scan_batch_crops") == crops
    assert store.rows("SELECT * FROM scan_batch_photos") == images
    assert batches.detail(actor, b["id"])["stages"][0]["state"] == "cancelled"
    assert batches.handoff(actor, b["id"], b["revision"], True, [])["draft"]
    other = batches.create(actor, str(uuid.uuid4()))
    assert batches.admit(actor, other["id"], other["revision"], image())["photos"]


def test_direct_batch_api_rejects_analysis_without_reservation(photos, monkeypatch):
    monkeypatch.setattr(scan_config, "recognition_enabled", lambda: False)
    b = staged(photos)
    client = photos["a"]
    binding = client.get("/api/photo-batches/").json()["binding"]
    before = batches.reservations(b["id"])
    response = client.post(
        f"/api/photo-batches/{b['id']}/analyze/",
        json.dumps(
            dict(
                revision=b["revision"], photo_id=b["photos"][0]["id"], stage="photo", consent="legacy-consent"
            )
        ),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=client.cookies["dex_b1_csrf"].value,
        HTTP_X_DEX_BINDING=binding,
    )
    assert response.status_code == 409
    assert response.json()["error"] == scan_config.UNAVAILABLE
    assert batches.reservations(b["id"]) == before
    assert not batches.detail(photos["actor"], b["id"])["stages"]
