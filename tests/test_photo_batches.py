"""Photo batches contracts over synthetic state and controlled processes."""

import io
import json
import time
import uuid

import pytest
from django.core.exceptions import PermissionDenied
from django.http import Http404
from photo_batch_helpers import BOX, cropped, photos, selected, staged
from PIL import Image
from test_b3 import image
from test_bulk_onboarding import b2, b3, b4, bulk, cx, e1, env, snapshot
from test_effective_collection import apply

from pokemon_hunter.beta import collection as inv
from pokemon_hunter.beta import collection_drafts as drafts
from pokemon_hunter.beta import photo_batches as batches
from pokemon_hunter.beta import scans, store

__all__ = ["b2", "b3", "b4", "bulk", "cx", "e1", "env", "snapshot", "photos"]


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
    assert len(inv.copies(a)) == before + 1
    assert drafts.confirm(a, d["id"], d["revision"]) == done
    retained = scans.authorized_photo_rows(a)
    assert len(retained) == 1 and all(p["copy_id"] for p in retained)
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
    assert len(review["plan"]["creates"]) == 1
    assert sorted(r["status"] for r in review["plan"]["photo_report"]) == ["added", "duplicate"]
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


@pytest.mark.parametrize(
    ("exception_type", "status", "message"),
    [
        (ValueError, 400, "Check the photo review fields"),
        (TypeError, 400, "Check the photo review fields"),
        (inv.Conflict, 409, "Photo batch changed or is unavailable. Reload before editing."),
    ],
)
def test_http_errors_never_expose_exception_text(photos, monkeypatch, exception_type, status, message):
    import re

    c = photos["a"]
    page = c.get("/add-photos/")
    binding = re.search(r'data-navigation-binding="([a-f0-9]+)"', page.content.decode())[1]
    provider_calls = []
    private_detail = "synthetic-private-photo-path-and-provider-credential"

    def fail_create(*args, **kwargs):
        raise exception_type(private_detail)

    def recognize(*args, **kwargs):
        provider_calls.append(1)
        raise AssertionError("Error handling must not dispatch recognition")

    monkeypatch.setattr(batches, "create", fail_create)
    monkeypatch.setattr("httpx.post", recognize)
    response = c.post(
        "/api/photo-batches/create/",
        json.dumps(dict(id=str(uuid.uuid4()))),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=c.cookies["dex_b1_csrf"].value,
        HTTP_X_DEX_BINDING=binding,
    )
    assert response.status_code == status
    assert response.json() == {"error": message}
    assert private_detail.encode() not in response.content
    assert response["Cache-Control"] == "private, no-store"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert provider_calls == []


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


def test_add_card_links_to_enabled_photo_batches(photos):
    page = photos["a"].get("/add-card/")
    assert page.status_code == 200
    assert 'href="/add-photos/"' in page.content.decode()
