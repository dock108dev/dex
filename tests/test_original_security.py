"""Original-app ingress validation and private write preservation."""

import os

import pytest
from fastapi.testclient import TestClient
from test_collection_app import local as local

from pokemon_hunter.app import create_app
from pokemon_hunter.collection import read, update_card


def test_original_app_validation_does_not_echo_private_input(local):
    with TestClient(
        create_app(local), base_url="http://127.0.0.1:8765", client=("127.0.0.1", 50000)
    ) as client:
        response = client.put("/api/cards/base_set-15", json={"owned": "SECRET", "private": "SECRET"})
    assert response.status_code == 422
    assert "SECRET" not in response.text


def test_original_app_storage_failure_is_safe_server_error(local, caplog):
    app = create_app(local)
    (local / "config/pokedex_251.json").write_text("SECRET invalid JSON")
    with TestClient(app, base_url="http://127.0.0.1:8765", client=("127.0.0.1", 50000)) as client:
        response = client.put("/api/cards/base_set-15", json={"owned": True})
    assert response.status_code == 500
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "legacy_request_failed" in caplog.text
    assert "SECRET" not in response.text + caplog.text


@pytest.mark.parametrize("provider_error", [True, False])
def test_original_app_distinguishes_provider_and_internal_failure(local, monkeypatch, caplog, provider_error):
    from pokemon_hunter.ebay import EbayError

    class Client:
        warnings = []
        closed = False

        def close(self):
            self.closed = True
            raise OSError("SECRET cleanup")

    owned = Client()

    def broken(*args):
        raise (EbayError if provider_error else RuntimeError)("SECRET provider or internal content")

    monkeypatch.setattr("pokemon_hunter.app.EbayClient", lambda *_: owned)
    monkeypatch.setattr("pokemon_hunter.app.discover", broken)
    with TestClient(
        create_app(local), base_url="http://127.0.0.1:8765", client=("127.0.0.1", 50000)
    ) as client:
        response = client.post("/api/hunts", json={"demo": False})
        assert client.get("/api/hunts").json() == []
    assert response.status_code == (502 if provider_error else 500)
    assert owned.closed
    assert "legacy_ebay_client_close_failed" in caplog.text
    assert "SECRET" not in response.text + caplog.text


@pytest.mark.parametrize(
    "host",
    [
        "testserver:8765",
        "evil.example:8765",
        "127.0.0.1.evil.example:8765",
        "localhost:0",
        "localhost:65536",
        "localhost:80:443",
        "localhost@evil.example",
        "localhost/evil",
        "localhost:bad",
        "localhost:",
    ],
)
def test_original_app_rejects_test_and_malformed_hosts_before_mutation(local, host):
    path = local / "config/pokedex_251.json"
    before = path.read_bytes()
    with TestClient(
        create_app(local), base_url="http://127.0.0.1:8765", client=("127.0.0.1", 50000)
    ) as client:
        response = client.put(
            "/api/cards/base_set-15", json={"owned": True}, headers={"Host": host, "Origin": f"http://{host}"}
        )
    assert response.status_code == 403
    assert response.headers["Cache-Control"] == "no-store"
    assert path.read_bytes() == before


@pytest.mark.parametrize("peer", ["192.0.2.1", "testclient"])
def test_original_app_rejects_non_loopback_peers(local, peer):
    with TestClient(create_app(local), base_url="http://127.0.0.1:8765", client=(peer, 50000)) as client:
        assert client.get("/api/export").status_code == 403


@pytest.mark.parametrize("header", ["Forwarded", "X-Forwarded-Host", "X-Forwarded-For", "X-Forwarded-Port"])
def test_original_app_rejects_forwarded_headers(local, header):
    with TestClient(
        create_app(local), base_url="http://127.0.0.1:8765", client=("127.0.0.1", 50000)
    ) as client:
        assert client.get("/api/export", headers={header: "127.0.0.1"}).status_code == 403


def test_original_app_rejects_duplicate_hosts(local):
    with TestClient(
        create_app(local), base_url="http://127.0.0.1:8765", client=("127.0.0.1", 50000)
    ) as client:
        response = client.get("/api/export", headers=[("Host", "127.0.0.1:8765"), ("Host", "evil.example")])
    assert response.status_code == 403


@pytest.mark.parametrize("host", ["localhost:8765", "127.0.0.1:8765"])
def test_original_app_accepts_supported_local_origin(local, host):
    with TestClient(create_app(local), base_url=f"http://{host}", client=("127.0.0.1", 50000)) as client:
        response = client.put(
            "/api/cards/base_set-15", json={"owned": True}, headers={"Origin": f"http://{host}"}
        )
    assert response.status_code == 200


@pytest.mark.parametrize("content_type", [None, "text/plain", "application/x-www-form-urlencoded"])
def test_original_app_requires_json_before_search_or_ownership_write(local, monkeypatch, content_type):
    def forbidden(*args):
        pytest.fail("Non-JSON request must not construct a provider client")

    monkeypatch.setattr("pokemon_hunter.app.EbayClient", forbidden)
    path = local / "config/pokedex_251.json"
    before = path.read_bytes()
    headers = {"Content-Type": content_type} if content_type else {}
    with TestClient(
        create_app(local), base_url="http://127.0.0.1:8765", client=("127.0.0.1", 50000)
    ) as client:
        assert client.post("/api/hunts", content='{"demo":false}', headers=headers).status_code == 415
        assert (
            client.put("/api/cards/base_set-15", content='{"owned":true}', headers=headers).status_code == 415
        )
        assert client.get("/api/hunts").json() == []
    assert path.read_bytes() == before


@pytest.mark.parametrize("demo", [0, 1, "false", "true", None])
def test_original_app_requires_boolean_search_mode(local, monkeypatch, demo):
    def forbidden(*args):
        pytest.fail("Invalid mode must not construct a provider client")

    monkeypatch.setattr("pokemon_hunter.app.EbayClient", forbidden)
    with TestClient(
        create_app(local), base_url="http://127.0.0.1:8765", client=("127.0.0.1", 50000)
    ) as client:
        assert client.post("/api/hunts", json={"demo": demo}).status_code == 422
        assert client.get("/api/hunts").json() == []


def test_original_app_new_storage_and_replacements_are_private(local):
    path = local / "config/pokedex_251.json"
    path.chmod(0o600)
    victim = local / "unrelated.txt"
    victim.write_text("retain this evidence")
    stale = path.with_suffix(".tmp")
    stale.symlink_to(victim)
    previous_mask = os.umask(0)
    try:
        create_app(local)
        update_card(path, "base_set-15", True)
    finally:
        os.umask(previous_mask)
    assert path.stat().st_mode & 0o777 == 0o600
    assert (local / "data/collection_hunts.db").stat().st_mode & 0o777 == 0o600
    assert read(path)["cards"]["base_set-15"]["owned"] is True
    assert stale.is_symlink() and victim.read_text() == "retain this evidence"


def test_failed_private_replacement_preserves_collection(local, monkeypatch):
    path = local / "config/pokedex_251.json"
    before = path.read_bytes()

    def fail(*args):
        raise OSError("Synthetic replacement failure")

    monkeypatch.setattr("pokemon_hunter.collection.os.replace", fail)
    with pytest.raises(OSError, match="replacement failure"):
        update_card(path, "base_set-15", True)
    assert path.read_bytes() == before
    retained = list(path.parent.glob(".pokedex_251.json.*.tmp"))
    assert len(retained) == 1 and retained[0].stat().st_mode & 0o777 == 0o600


def test_original_app_refuses_symlinked_collection_write(local):
    path = local / "config/pokedex_251.json"
    target = path.with_name("synthetic-original.json")
    path.rename(target)
    path.symlink_to(target)
    before = target.read_bytes()
    with pytest.raises(OSError, match="symlink"):
        update_card(path, "base_set-15", True)
    assert path.is_symlink() and target.read_bytes() == before


def test_original_app_refuses_symlinked_hunt_database(local):
    (local / "data").mkdir()
    target = local / "unrelated.bin"
    target.write_bytes(b"retain this evidence")
    (local / "data/collection_hunts.db").symlink_to(target)
    with pytest.raises(OSError, match="symlink"):
        create_app(local)
    assert target.read_bytes() == b"retain this evidence"
