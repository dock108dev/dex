"""New B5 catalog reconciliation, provider configuration and private recovery transport."""

import copy
import importlib
import json
from urllib.parse import urlsplit

import pytest
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_b4 import publish
from test_migration import snapshot as base_snapshot

from pokemon_hunter.beta import catalog_imports as cat
from pokemon_hunter.beta import collection as inv
from pokemon_hunter.beta import store
from pokemon_hunter.beta.catalog_reconcile import PACKAGES, request_set_id
from pokemon_hunter.beta.staging_config import configuration


@pytest.fixture
def snapshot(tmp_path):
    root = base_snapshot.__wrapped__(tmp_path)
    project = PACKAGES.parents[2]
    data = json.loads((project / "config/pokedex_251.example.json").read_text())
    data["cards"]["base_set-1"]["owned"] = True
    data["cards"]["base_set-1"]["first_edition"] = True
    (root / "config/pokedex_251.json").write_text(json.dumps(data))
    (root / "config/catalog/sources.json").write_bytes((project / "config/catalog/sources.json").read_bytes())
    return root


def test_ten_sets_reconcile_without_changing_inventory_or_frozen_goals(b4):
    import uuid

    from test_b4 import provisional

    op = inv.preview(
        b4["actor"],
        "goal",
        {"goal_kind": "vintage", "name": "Frozen before reconciliation"},
        str(uuid.uuid4()),
    )
    inv.confirm(b4["actor"], op["id"])
    _, job = provisional(b4)
    inv.execute("UPDATE scan_jobs SET reserved_usd=0.05 WHERE id=%s", [job["id"]])
    before = {
        t: store.rows("SELECT * FROM " + t + " ORDER BY 1")
        for t in ("owned_copies", "collection_goals", "scan_jobs", "import_records")
    }
    old = store.rows("SELECT * FROM printings ORDER BY id")
    operations = []
    for path in sorted(PACKAGES.glob("*.json")):
        if path.name not in {"source-manifest.json", "species.json"}:
            package = json.loads(path.read_text())
            op = publish(b4, package)
            operations.append(op)
            assert request_set_id(cat.identity("pokemon", package["set_key"], "en")) == op["set_id"]
    after = store.rows("SELECT * FROM printings ORDER BY id")
    assert len(after) == len(old) == 859
    for a, b in zip(old, after, strict=True):
        for field in (
            "id",
            "set_id",
            "collector_number",
            "edition",
            "finish",
            "variant",
            "unresolved_fields",
        ):
            assert a[field] == b[field]
        original = json.loads(a["provenance"])
        current = json.loads(b["provenance"])
        assert all(current[k] == v for k, v in original.items())
    assert all(before[t] == store.rows("SELECT * FROM " + t + " ORDER BY 1") for t in before)
    from django.test import override_settings

    from pokemon_hunter.beta import deployment, parity

    deployment.initialize()
    with override_settings(STAGING=True):
        assert len(inv.catalog(b4["actor"])) == 859
        assert len(parity.projection(b4["actor"])["pokedex"]) == 251
    # Rollback / republish preserves every identity and original baseline evidence.
    for op in operations:
        cat.transition(b4["actor"], op["id"], "rollback")
    assert store.rows("SELECT * FROM printings ORDER BY id") == old
    for op in operations:
        cat.transition(b4["actor"], op["id"], "publish")
    assert store.rows("SELECT * FROM printings ORDER BY id") == after


def test_reconciliation_rejects_unreviewed_mapping_and_ambiguous_variants(b4):
    package = json.loads((PACKAGES / "base_set.json").read_text())
    bad = copy.deepcopy(package)
    bad["cards"][0]["legacy_id"] = "base_set-2"
    with pytest.raises(ValueError, match="pinned"):
        cat.preview(b4["actor"], bad)
    original = store.rows("SELECT * FROM printings WHERE collector_number='1'")[0]
    duplicate = {**original, "id": "synthetic-ambiguous-printing", "edition": "other"}
    cat.write("printings", duplicate)
    with pytest.raises(ValueError, match="Ambiguous"):
        cat.preview(b4["actor"], package)


def test_render_environment_requires_explicit_provider_identity():
    cfg = {
        "DATABASE_URL": "postgresql://localhost/disposable",
        "DEX_SECRET_KEY": "s" * 64,
        "DEX_PUBLIC_ORIGIN": "https://dex-test.onrender.com",
        "DEX_INGRESS": "render",
        "RENDER": "true",
        "RENDER_SERVICE_ID": "srv-synthetic",
        "RENDER_SERVICE_TYPE": "web",
        "RENDER_EXTERNAL_HOSTNAME": "dex-test.onrender.com",
    }
    assert configuration(cfg)["PROXY_NETWORKS"] == []
    for key, value in [
        ("RENDER", "false"),
        ("RENDER_EXTERNAL_HOSTNAME", "foreign.onrender.com"),
        ("DEX_PROXY_NETWORKS", "10.0.0.0/8"),
    ]:
        with pytest.raises(RuntimeError):
            configuration({**cfg, key: value})


def test_render_guard_health_and_exact_https(b4):
    from django.http import HttpResponse
    from django.test import RequestFactory, override_settings

    from pokemon_hunter.beta.security import StagingMiddleware

    guard = StagingMiddleware(lambda r: HttpResponse("ok"))
    factory = RequestFactory()
    with override_settings(
        INGRESS="render",
        PROXY_NETWORKS=[],
        PUBLIC_ORIGIN="https://dex-test.onrender.com",
        ALLOWED_HOSTS=["dex-test.onrender.com"],
    ):

        def request(path="/", **meta):
            return guard(
                factory.get(path, HTTP_HOST="dex-test.onrender.com", REMOTE_ADDR="10.23.45.67", **meta)
            )

        assert request().status_code == 403
        assert request(HTTP_X_FORWARDED_PROTO="https,http").status_code == 403
        assert request(HTTP_X_FORWARDED_PROTO="https", HTTP_ORIGIN="https://evil.invalid").status_code == 403
        assert request(HTTP_X_FORWARDED_PROTO="https").status_code == 200
        assert request("/healthz/").status_code == 200


def test_staging_recovery_token_never_enters_request_url(b4):
    from django.test import Client, override_settings
    from django.urls import clear_url_caches

    from pokemon_hunter.beta import accounts, urls

    with override_settings(STAGING=True):
        importlib.reload(urls)
        clear_url_caches()
        try:
            link = accounts.issue_link(b4["owner"], "recovery")
            assert urlsplit(link).path == "/access/"
            kind, uid, token = urlsplit(link).fragment.split("/")
            c = Client(enforce_csrf_checks=True, HTTP_HOST="127.0.0.1:8011", REMOTE_ADDR="127.0.0.1")
            assert c.get("/access/").status_code == 200
            data = {"kind": kind, "uid": uid, "token": token}
            assert c.post("/access/start/", data).status_code == 403
            data["csrfmiddlewaretoken"] = c.cookies["dex_b1_csrf"].value
            result = c.post("/access/start/", data)
            assert result.url == "/access/reset/" and token not in result.url
            assert c.get(result.url).status_code == 200
            password = "Synthetic-new-passphrase-84715"
            result = c.post(
                "/access/reset/",
                {
                    "new_password1": password,
                    "new_password2": password,
                    "csrfmiddlewaretoken": c.cookies["dex_b1_csrf"].value,
                },
            )
            assert result.status_code == 302 and result.url == "/login/"
            assert c.post("/access/start/", data).status_code == 400
            assert c.get(f"/recovery/{uid}/{token}/").status_code == 404
        finally:
            # Restore URL configuration after leaving the override below.
            pass
    importlib.reload(urls)
    clear_url_caches()
