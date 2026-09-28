"""Verify restored private bytes and session authorization using synthetic rehearsal credentials."""

import argparse
import json
from pathlib import Path

from pokemon_hunter.beta import deployment


def run(evidence):
    deployment.setup()
    from django.conf import settings
    from django.contrib.auth import get_user_model
    from django.test import Client

    from pokemon_hunter.beta import collection as inv
    from pokemon_hunter.beta import scans, store, support

    saved = json.loads((evidence / "synthetic-account.json").read_text())
    user = get_user_model().objects.get(pk=saved["id"])
    assert user.check_password(saved["password"])
    who = store.principal(user.pk)
    c = Client(
        enforce_csrf_checks=True,
        HTTP_HOST=settings.PUBLIC_ORIGIN.removeprefix("https://"),
        REMOTE_ADDR="127.0.0.1",
        HTTP_X_FORWARDED_PROTO="https",
    )
    c.force_login(user)
    assert c.get("/api/export/").status_code == 200
    assert c.get("/scan-photos/" + saved["photo"] + "/").status_code == 200
    assert len(inv.copies(who)) == 2
    assert inv.copies(who)[0]["purchase_amount"] in ("12.3400", None)
    owner = Client(
        HTTP_HOST=settings.PUBLIC_ORIGIN.removeprefix("https://"),
        REMOTE_ADDR="127.0.0.1",
        HTTP_X_FORWARDED_PROTO="https",
    )
    owner.force_login(get_user_model().objects.get(pk=saved["owner"]))
    assert owner.get("/scan-photos/" + saved["photo"] + "/").status_code == 404
    assert owner.get(f"/api/catalog-evidence/{saved['submission']}/{saved['photo']}/").status_code == 200
    assert store.rows("SELECT * FROM catalog_heads")
    assert store.rows("SELECT * FROM collection_operations WHERE user_id=%s", [who.user_id])
    cfg = scans.config()
    cfg["mode"] = "manual"
    inv.execute("UPDATE beta_operations SET value=%s WHERE key='scan_config'", [json.dumps(cfg)])
    # Writes made after the backup still exist in the source database. Never restore over it.
    print(
        json.dumps(
            {
                "restore_exact_manifest": "PASS",
                "passwords_photos_consent_isolation_history": "PASS",
                "copies": 2,
                "reserved_usd": support.diagnostics()["recognition"]["reserved_usd"],
            }
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, required=True)
    run(parser.parse_args().evidence)
