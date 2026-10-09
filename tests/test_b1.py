"""Synthetic authentication checks. No owner files, passwords or tokens are fixtures."""

import json
import secrets
from datetime import timedelta
from unittest.mock import patch

import pytest
from test_migration import snapshot as snapshot

from pokemon_hunter.beta.cli import initialize, setup
from pokemon_hunter.inventory import OWNER_ID
from pokemon_hunter.migration import import_snapshot


@pytest.fixture
def env(tmp_path, snapshot):
    target = tmp_path / "b0.db"
    batch = import_snapshot(snapshot, target)
    root = tmp_path / "isolated"
    initialize(root, target)
    setup(root)
    from django.conf import settings
    from django.core.management import call_command
    from django.db import connection

    connection.close()
    settings.DATABASES["default"]["NAME"] = root / "inventory.db"
    connection.settings_dict["NAME"] = root / "inventory.db"
    call_command("migrate", verbosity=0)
    from django.test import Client

    from pokemon_hunter.beta import accounts, store

    def client():
        return Client(enforce_csrf_checks=True, HTTP_HOST="127.0.0.1:8011", REMOTE_ADDR="127.0.0.1")

    def login(c, username, password):
        c.get("/login/")
        return c.post(
            "/login/",
            {
                "username": username,
                "password": password,
                "csrfmiddlewaretoken": c.cookies["dex_b1_csrf"].value,
            },
        )

    def redeem(c, link, password):
        first = c.get(link)
        if first.status_code != 302:
            return first
        return c.post(
            first.url,
            {
                "new_password1": password,
                "new_password2": password,
                "csrfmiddlewaretoken": c.get(first.url)
                .cookies.get("dex_b1_csrf", c.cookies.get("dex_b1_csrf"))
                .value,
            },
        )

    password = secrets.token_urlsafe(24)
    owner = accounts.bootstrap(password)
    second = accounts.invite("collector")
    other_password = secrets.token_urlsafe(24)
    link = accounts.issue_link(second, "invite")
    a, b = client(), client()
    assert redeem(b, link, other_password).status_code == 302
    assert login(a, "admin", password).status_code == 302
    assert login(b, "collector", other_password).status_code == 302
    yield dict(
        root=root,
        batch=batch,
        owner=owner,
        second=second,
        a=a,
        b=b,
        client=client,
        login=login,
        redeem=redeem,
        password=password,
        other_password=other_password,
        accounts=accounts,
        store=store,
    )
    connection.close()


def test_two_sessions_preservation_empty_member_and_forged_ids(env):
    a, b = env["a"], env["b"]
    assert a.cookies["dex_b1_session"].value != b.cookies["dex_b1_session"].value
    copies = a.get("/api/inventory/").json()["copies"]
    assert len(copies) == 2
    assert sum(r["first_edition_selected"] for r in copies) == 1
    assert all(json.loads(r["unresolved_fields"]) for r in copies)
    assert a.get("/api/export/").json()["vintage_251"]["total"] == 1
    for route, key in [("inventory", "copies"), ("hunts", "hunts"), ("archives", "archives")]:
        assert b.get(f"/api/{route}/?user_id={OWNER_ID}", HTTP_X_USER_ID=OWNER_ID).json()[key] == []
    assert b.get(f"/api/export/?user_id={OWNER_ID}").json()["copies"] == []
    assert len(a.get("/api/hunts/").json()["hunts"]) == 2
    assert b"Your collection is empty" in b.get("/").content
    assert b"Your collection" in a.get("/").content


@pytest.mark.parametrize(
    "route", ["/api/inventory/", "/api/hunts/", "/api/archives/", "/api/export/", "/api/admin/catalog/"]
)
def test_anonymous_cannot_read(env, route):
    assert env["client"]().get(route).status_code == 302


def test_cross_user_reads_writes_downloads_and_admin(env):
    a, b, store = env["a"], env["b"], env["store"]
    key = a.get("/api/inventory/").json()["copies"][0]["id"]
    route = f"/api/inventory/{key}/"
    assert b.get(route).status_code == 404
    assert (
        b.post(route, {"notes": "tamper", "csrfmiddlewaretoken": b.cookies["dex_b1_csrf"].value}).status_code
        == 404
    )
    assert (
        a.post(
            route, {"notes": "synthetic edit", "csrfmiddlewaretoken": a.cookies["dex_b1_csrf"].value}
        ).status_code
        == 200
    )
    assert (
        a.post(
            route, {"user_id": "forged", "csrfmiddlewaretoken": a.cookies["dex_b1_csrf"].value}
        ).status_code
        == 400
    )
    assert a.get("/api/inventory/guessed/").status_code == 404
    assert b.get(f"/api/hunts/{env['batch']}/1/").status_code == 404
    archive = f"/files/{env['batch']}/config/settings.yaml"
    assert a.get(archive).content == b"synthetic: true\n"
    assert b.get(archive).status_code == 404
    assert env["client"]().get(archive).status_code == 302
    assert a.get(f"/files/{env['batch']}/../../secret.key").status_code == 404
    assert b.get("/api/admin/catalog/").status_code == 403
    assert a.get("/api/admin/catalog/").status_code == 200
    # Even the catalog owner cannot read a member's synthetic copy, hunt or archive.
    from django.db import connection

    member = store.principal(env["second"].pk)
    with connection.cursor() as c:
        c.execute("UPDATE owned_copies SET user_id=%s WHERE id=%s", [member.user_id, key])
        c.execute("UPDATE saved_hunts SET user_id=%s WHERE legacy_id=1", [member.user_id])
        c.execute(
            "UPDATE private_archives SET user_id=%s WHERE path='config/settings.yaml'", [member.user_id]
        )
    assert a.get(route).status_code == 404
    assert b.get(route).status_code == 200
    assert a.get(f"/api/hunts/{env['batch']}/1/").status_code == 404
    assert a.get(archive).status_code == 404
    assert key not in {r["id"] for r in a.get("/api/export/").json()["copies"]}


@pytest.mark.parametrize("kind", ["photos", "scan_jobs", "goals", "request_evidence"])
def test_unimplemented_b1_resource_routes_remain_unavailable(env, kind):
    # Account-only roots do not enable photo, job, goal or evidence services.
    from django.http import Http404

    with pytest.raises(Http404):
        env["store"].resource(env["store"].principal(env["owner"].pk), kind, "unused")
    for method in (env["a"].get, env["a"].post):
        assert (
            method(
                f"/api/{kind}/", {"csrfmiddlewaretoken": env["a"].cookies["dex_b1_csrf"].value}
            ).status_code
            == 404
        )


def test_csrf_origin_host_and_cookie_protections(env):
    a = env["a"]
    assert a.post("/logout/").status_code == 403
    assert (
        a.post(
            "/logout/",
            {"csrfmiddlewaretoken": a.cookies["dex_b1_csrf"].value},
            HTTP_ORIGIN="https://evil.example",
        ).status_code
        == 403
    )
    assert a.get("/", HTTP_HOST="evil.example").status_code == 403
    assert a.get("/", REMOTE_ADDR="192.0.2.1").status_code == 403
    assert a.get("/", HTTP_X_FORWARDED_FOR="127.0.0.1").status_code == 403
    assert a.get("/", HTTP_ORIGIN="http://127.0.0.1:9999").status_code == 403
    assert a.cookies["dex_b1_session"]["httponly"]
    assert a.cookies["dex_b1_session"]["samesite"] == "Strict"
    assert a.get("/")["Cache-Control"] == "no-store"
    assert a.get("/")["Referrer-Policy"] == "same-origin"
    assert a.get("/logout/").status_code == 405


def test_logout_revocation_and_session_expiry(env):
    from django.contrib.sessions.models import Session
    from django.utils import timezone

    a, b = env["a"], env["b"]
    old = a.cookies["dex_b1_session"].value
    assert a.post("/logout/", {"csrfmiddlewaretoken": a.cookies["dex_b1_csrf"].value}).status_code == 302
    replay = env["client"]()
    replay.cookies["dex_b1_session"] = old
    assert replay.get("/api/export/").status_code == 302
    env["accounts"].revoke(env["second"])
    assert b.get("/api/export/").status_code == 302
    assert env["login"](a, "admin", env["password"]).status_code == 302
    Session.objects.filter(session_key=a.cookies["dex_b1_session"].value).update(
        expire_date=timezone.now() - timedelta(seconds=1)
    )
    assert a.get("/api/export/").status_code == 302


@pytest.mark.parametrize("kind", ["invite", "recovery"])
def test_tokens_expire_replay_rotate_and_complete(env, kind):
    from django.conf import settings
    from django.contrib.auth import get_user_model

    accounts = env["accounts"]
    user = accounts.invite("new-collector") if kind == "invite" else env["owner"]
    generator = accounts.invite_token if kind == "invite" else accounts.recovery_token
    link = accounts.issue_link(user, kind)
    token = link.strip("/").split("/")[-1]
    user.refresh_from_db()
    with patch.object(
        generator,
        "_now",
        return_value=generator._now() + timedelta(seconds=settings.PASSWORD_RESET_TIMEOUT + 1),
    ):
        assert not generator.check_token(user, token)
        assert b"invalid, expired" in env["client"]().get(link).content
    newer = accounts.issue_link(user, kind)
    assert b"invalid, expired" in env["client"]().get(link).content
    c = env["client"]()
    password = secrets.token_urlsafe(24)
    assert env["redeem"](c, newer, password).status_code == 302
    assert b"invalid, expired" in env["client"]().get(newer).content
    assert env["login"](c, user.username, password).status_code == 302
    assert c.get("/").status_code == 200
    assert get_user_model().objects.get(pk=user.pk).email == ""
    if kind == "recovery":
        assert env["a"].get("/api/export/").status_code == 302


def test_token_purpose_weak_password_and_concurrent_redemption(env):
    accounts = env["accounts"]
    user = accounts.invite("new-collector")
    link = accounts.issue_link(user, "invite")
    assert b"invalid, expired" in env["client"]().get(link.replace("/invite/", "/recovery/")).content
    a, b = env["client"](), env["client"]()
    first, second = a.get(link), b.get(link)
    a.get(first.url)
    b.get(second.url)
    weak = secrets.token_hex(2)
    assert (
        a.post(
            first.url,
            {
                "new_password1": weak,
                "new_password2": weak,
                "csrfmiddlewaretoken": a.cookies["dex_b1_csrf"].value,
            },
        ).status_code
        == 200
    )
    password = secrets.token_urlsafe(24)
    assert (
        a.post(
            first.url,
            {
                "new_password1": password,
                "new_password2": password,
                "csrfmiddlewaretoken": a.cookies["dex_b1_csrf"].value,
            },
        ).status_code
        == 302
    )
    result = b.post(
        second.url,
        {
            "new_password1": password,
            "new_password2": password,
            "csrfmiddlewaretoken": b.cookies["dex_b1_csrf"].value,
        },
    )
    assert result.status_code in (200, 404) and result.status_code != 302


def test_bootstrap_repeat_and_privilege_does_not_follow_username(env):
    from django.contrib.auth import get_user_model

    owner = env["owner"]
    owner.refresh_from_db()
    before = owner.password
    assert env["accounts"].bootstrap(secrets.token_urlsafe(24)).pk == owner.pk
    assert get_user_model().objects.get(pk=owner.pk).password == before
    owner.username = "renamed-owner"
    owner.save(update_fields=["username"])
    member = env["second"]
    member.username = "admin"
    member.save(update_fields=["username"])
    assert env["store"].principal(owner.pk).user_id == OWNER_ID
    assert env["a"].get("/api/admin/catalog/").status_code == 200
    assert env["b"].get("/api/admin/catalog/").status_code == 403


def test_login_failure_limit_and_no_public_signup(env):
    c = env["client"]()
    for _ in range(5):
        result = env["login"](c, "admin", secrets.token_urlsafe(24))
    assert result.status_code == 429
    assert env["login"](c, "admin", env["password"]).status_code == 429
    assert c.get("/signup/").status_code == 404
    assert c.post("/login/", {"username": "admin"}).status_code == 403


def test_owner_first_and_identity_adoption_refused(env):
    from django.contrib.auth import get_user_model
    from django.db import connection

    # Disposable synthetic database only: simulate a preexisting unbound account.
    with connection.cursor() as c:
        c.execute("UPDATE users SET auth_subject=NULL,state='unprovisioned' WHERE id=%s", [OWNER_ID])
    with pytest.raises(ValueError):
        env["accounts"].invite("too-early")
    with pytest.raises(ValueError):
        env["accounts"].bootstrap(secrets.token_urlsafe(24))
    assert get_user_model().objects.count() == 2


def test_invitation_reissue_and_revoked_links(env):
    accounts = env["accounts"]
    user = accounts.invite("pending-collector")
    old = accounts.issue_link(user, "invite")
    assert accounts.invite("pending-collector").pk == user.pk
    new = accounts.issue_link(user, "invite")
    assert b"invalid, expired" in env["client"]().get(old).content
    accounts.revoke(user)
    assert b"invalid, expired" in env["client"]().get(new).content
    with pytest.raises(ValueError):
        accounts.invite("pending-collector")
    with pytest.raises(ValueError):
        accounts.issue_link(user, "recovery")
    with pytest.raises(ValueError):
        accounts.issue_link(env["owner"], "other")


def test_initialization_refuses_existing_or_checkout_paths(env):
    from pathlib import Path

    with pytest.raises(FileExistsError):
        initialize(env["root"])
    with pytest.raises(ValueError):
        initialize(Path(__file__).resolve().parents[1] / "b1-unsafe")
