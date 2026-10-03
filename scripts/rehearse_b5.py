"""Verify a migrated disposable staging database; writes only synthetic test accounts.

Load staging environment securely first. --evidence must be private and outside Git.
Requires a copied catalog-enabled database with an owner binding and Gym Heroes already published.
"""

import argparse
import io
import json
import secrets
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from pokemon_hunter.beta import deployment


def run(evidence):
    deployment.setup()
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.db import close_old_connections
    from django.test import Client
    from PIL import Image

    from pokemon_hunter.beta import accounts, scans, store, support
    from pokemon_hunter.beta import catalog_imports as cat
    from pokemon_hunter.beta import catalog_requests as req
    from pokemon_hunter.beta import collection as inv
    from pokemon_hunter.inventory import OWNER_ID

    report = {}
    owner = store.rows("SELECT auth_subject FROM users WHERE id=%s", [OWNER_ID])[0]
    admin = store.principal(owner["auth_subject"])
    owner_before = inv.export_data(admin)
    # Never reset the copied review password. Independent synthetic accounts only.
    user = accounts.invite("b5-" + uuid.uuid4().hex[:12])
    password = secrets.token_urlsafe(24)
    user.set_password(password)
    user.save()
    inv.execute("UPDATE users SET state='active' WHERE auth_subject=%s", [str(user.pk)])
    actor = store.principal(user.pk)
    cfg = scans.config()
    cfg["mode"] = "fixture"
    inv.execute("UPDATE beta_operations SET value=%s WHERE key='scan_config'", [json.dumps(cfg)])

    def client(user=None):
        c = Client(
            enforce_csrf_checks=True,
            HTTP_HOST=settings.PUBLIC_ORIGIN.removeprefix("https://"),
            REMOTE_ADDR="127.0.0.1",
            HTTP_X_FORWARDED_PROTO="https",
        )
        if user:
            c.force_login(user)
        return c

    c = client(user)
    assert c.get("/").status_code == 200
    assert c.get("/api/export/").json()["copies"] == []
    assert c.get("/api/catalog-review/").status_code == 403
    assert c.get("/api/catalog/", HTTP_X_FORWARDED_PROTO="http").status_code == 403
    assert c.get("/api/catalog/", REMOTE_ADDR="192.0.2.10").status_code == 403
    assert c.post("/api/operations/preview/", data="{}", content_type="application/json").status_code == 403
    report["https_proxy_session_csrf_isolation"] = "PASS"
    printing = inv.catalog(actor)[0]
    op = inv.preview(
        actor,
        "add",
        {
            "printing_id": printing["id"],
            "duplicate_policy": "allow",
            "attributes": {"purchase_amount": "12.3400", "purchase_currency": "USD", "notes": "Synthetic B5"},
        },
        str(uuid.uuid4()),
    )

    def confirm(_):
        close_old_connections()
        try:
            return inv.confirm(actor, op["id"])["id"]
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert len(set(pool.map(confirm, range(2)))) == 1
    assert len(inv.copies(actor)) == 1
    assert inv.copies(actor)[0]["purchase_amount"] == "12.3400"
    for kind, payload in (
        ("binder", {"name": "Synthetic binder"}),
        ("goal", {"name": "Synthetic goal", "goal_kind": "custom", "printing_ids": [printing["id"]]}),
    ):
        draft = inv.preview(actor, kind, payload, str(uuid.uuid4()))
        inv.confirm(actor, draft["id"])
        inv.undo(actor, draft["id"])
    assert not inv.binders(actor) and not inv.goals(actor)
    report["concurrent_confirmation_exact_values"] = "PASS"

    def photo():
        f = io.BytesIO()
        Image.new("RGB", (300, 400), "red").save(f, "JPEG")
        return SimpleUploadedFile("synthetic.jpg", f.getvalue(), content_type="image/jpeg")

    job = scans.create(actor, str(uuid.uuid4()), [photo()], "unsupported")
    scans.process_one()
    job = scans.action(actor, job["id"], "confirm", {"notes": "Synthetic photo"})
    photoid = job["photos"][0]
    assert c.get("/scan-photos/" + photoid + "/").status_code == 200
    other = client(get_user_model().objects.get(pk=admin.subject))
    assert other.get("/scan-photos/" + photoid + "/").status_code == 404
    submission = req.create(
        actor,
        {
            "origin": "copy",
            "origin_id": job["copy_id"],
            "share_photos": True,
            "hints": {
                "game": "pokemon",
                "set": "Gym Heroes",
                "language": "en",
                "name": "Blaine's Moltres",
                "number": "1",
            },
        },
    )
    assert other.get(f"/api/catalog-evidence/{submission['id']}/{photoid}/").status_code == 200
    detail = req.detail(actor, submission["id"])
    candidates = detail.get("proposals", [])
    if not candidates:
        candidates = req.proposed(actor, req.submission(actor, submission["id"]))
    if candidates:
        before_id = job["copy_id"]
        req.resolve(actor, submission["id"], {"printing_id": candidates[0]["id"], "revision": 0})
        req.resolve(actor, submission["id"], {"printing_id": candidates[0]["id"], "revision": 0})
        assert inv.one(actor, "copy", before_id)["printing_id"] == candidates[0]["id"]
    else:
        raise AssertionError("Expected published Gym Heroes proposal")
    package = json.loads(
        (Path(__file__).resolve().parents[1] / "config/catalog-imports/synthetic-orbits.json").read_text()
    )
    operation = cat.preview(admin, package)
    cat.transition(admin, operation["id"], "verify")
    cat.transition(admin, operation["id"], "publish")
    cat.transition(admin, operation["id"], "rollback")
    cat.transition(admin, operation["id"], "publish")
    report["b3_photos_b4_consent_publication_rollback"] = "PASS"
    crash = scans.create(actor, str(uuid.uuid4()), [photo()])
    inv.execute(
        "UPDATE scan_jobs SET state='processing',started=%s,attempts=1,reserved_usd=0.05 WHERE id=%s",
        [time.time() - 130, crash["id"]],
    )
    scans.process_one()
    assert scans.job(actor, crash["id"])["state"] == "failed"
    cfg["mode"] = "openai"
    cfg["ceiling_usd"] = 0.05
    inv.execute("UPDATE beta_operations SET value=%s WHERE key='scan_config'", [json.dumps(cfg)])
    spend = scans.create(actor, str(uuid.uuid4()), [photo()])
    with (
        patch.dict("os.environ", {"OPENAI_API_KEY": "synthetic-never-sent"}),
        patch.object(scans, "recognize") as provider,
    ):
        scans.process_one()
        provider.assert_not_called()
    assert scans.job(actor, spend["id"])["state"] == "failed"
    report["crash_recovery_no_auto_retry_spend_ceiling"] = "PASS"
    cfg["mode"] = "fixture"
    cfg["ceiling_usd"] = 1.0
    inv.execute("UPDATE beta_operations SET value=%s WHERE key='scan_config'", [json.dumps(cfg)])
    inv.execute(
        "INSERT INTO beta_feedback VALUES(%s,%s,%s,%s)",
        [str(uuid.uuid4()), actor.user_id, "Synthetic feedback", time.time()],
    )
    evidence.mkdir(mode=0o700, parents=True, exist_ok=False)
    deployment.backup(evidence / "backup")
    # Preserve synthetic actor/password privately for restored HTTP/browser checks.
    (evidence / "synthetic-account.json").write_text(
        json.dumps(
            {
                "id": user.pk,
                "username": user.username,
                "password": password,
                "photo": photoid,
                "submission": submission["id"],
                "owner": admin.subject,
            }
        )
    )
    before_spend = support.diagnostics()["recognition"]["reserved_usd"]
    support.delete_account(actor)
    assert support.diagnostics()["recognition"]["reserved_usd"] == before_spend
    assert c.get("/api/export/").status_code == 302
    assert other.get(f"/api/catalog-evidence/{submission['id']}/{photoid}/").status_code == 404
    assert inv.export_data(admin) == owner_before
    report["deletion_other_user_preservation_reservations"] = "PASS"
    report["hosted_observation"] = False
    report["real_devices"] = False
    report["real_recognition_calls"] = 0
    (evidence / "report.json").write_text(json.dumps(report, indent=2))
    for p in evidence.iterdir():
        if p.is_file():
            p.chmod(0o600)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    run(parser.parse_args().evidence)
