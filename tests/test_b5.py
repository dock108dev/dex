"""B5 privacy and configuration checks; PostgreSQL rehearsal is a separate script."""

import json
import time
from unittest.mock import patch

import pytest
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_b4 import provisional, request
from test_migration import snapshot as snapshot

from pokemon_hunter.beta import collection as inv
from pokemon_hunter.beta import deployment, scans, store
from pokemon_hunter.beta.staging_config import configuration


def test_staging_fails_closed():
    with pytest.raises(RuntimeError):
        configuration({})
    cfg = {
        "DATABASE_URL": "postgresql://localhost/disposable",
        "DEX_SECRET_KEY": "s" * 64,
        "DEX_PUBLIC_ORIGIN": "https://dex.example",
        "DEX_PROXY_NETWORKS": "127.0.0.1/32",
    }
    assert configuration(cfg)["SESSION_COOKIE_SECURE"]
    for key, value in [
        ("DEX_PUBLIC_ORIGIN", "http://dex.example"),
        ("DEX_PROXY_NETWORKS", "0.0.0.0/0"),
        ("DEX_SECRET_KEY", "short"),
        ("DATABASE_URL", "sqlite:///tmp/a"),
    ]:
        with pytest.raises(RuntimeError):
            configuration({**cfg, key: value})


def test_account_erasure_preserves_others_catalog_and_spend(b4):
    from pokemon_hunter.beta import support

    deployment.initialize()
    owner_before = inv.export_data(b4["actor"])
    who, j, s = request(b4, member=True, share=True)
    inv.execute("UPDATE scan_jobs SET reserved_usd=0.05 WHERE id=%s", [j["id"]])
    before = store.rows("SELECT * FROM printings ORDER BY id")
    support.delete_account(who)
    assert inv.export_data(b4["actor"]) == owner_before
    assert store.rows("SELECT * FROM printings ORDER BY id") == before
    for table in (
        "owned_copies",
        "scan_photos",
        "catalog_submissions",
        "collection_operations",
        "private_archives",
    ):
        assert not store.rows(f"SELECT * FROM {table} WHERE user_id=%s", [who.user_id])
    tombstone = store.rows("SELECT * FROM scan_jobs WHERE id=%s", [j["id"]])[0]
    assert (
        tombstone["reserved_usd"] == 0.05 and tombstone["result"] == "{}" and tombstone["selection"] is None
    )
    assert b4["b"].get("/api/export/").status_code == 302


def test_cleanup_and_redacted_diagnostics(b4):
    from pokemon_hunter.beta import support

    deployment.initialize()
    who, j = provisional(b4, member=True)
    inv.execute(
        "INSERT INTO beta_feedback VALUES(%s,%s,%s,%s)",
        ["old", who.user_id, "SECRET", time.time() - 31 * 86400],
    )
    support.cleanup()
    assert not store.rows("SELECT * FROM beta_feedback")
    assert "SECRET" not in json.dumps(support.diagnostics())
    assert scans.job(who, j["id"])["photos"]  # confirmed photos retained


def test_worker_stop_does_not_claim(b4):
    import threading

    from pokemon_hunter.beta.scan_worker import run

    stop = threading.Event()
    stop.set()
    with patch.object(scans, "process_one") as claim:
        run(stop)
        claim.assert_not_called()


def test_backup_expiration_only_removes_own_expired_packages(tmp_path):
    old = tmp_path / "old"
    old.mkdir()
    for name in ("database.dump", "manifest.json", "sha256"):
        (old / name).write_text("synthetic")
    (old / "expires.json").write_text(json.dumps({"expires": 1}))
    untouched = tmp_path / "unrelated"
    untouched.mkdir()
    (untouched / "important").write_text("keep")
    deployment.expire_backups(tmp_path, now=2)
    assert not old.exists() and (untouched / "important").read_text() == "keep"
