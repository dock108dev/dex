"""Rolling local authentication using simulated time and disposable accounts only."""

from datetime import timedelta
from unittest.mock import patch

from test_b1 import env as env
from test_migration import snapshot as snapshot


def test_local_persistent_rolling_cookie_and_idle_expiry(env):
    from django.conf import settings
    from django.contrib.sessions.models import Session
    from django.utils import timezone

    a = env["a"]
    cookie = a.cookies[settings.SESSION_COOKIE_NAME]
    assert settings.SESSION_COOKIE_AGE == 30 * 86400
    assert not settings.SESSION_SAVE_EVERY_REQUEST
    assert not settings.SESSION_EXPIRE_AT_BROWSER_CLOSE
    assert cookie["max-age"] == 30 * 86400 and cookie["expires"]
    assert cookie["httponly"] and cookie["samesite"] == "Strict"
    key = cookie.value
    initial = Session.objects.get(session_key=key).expire_date
    future = timezone.now() + timedelta(days=29, hours=23)
    with patch("django.utils.timezone.now", return_value=future):
        assert a.get("/api/export/").status_code == 200
        assert a.cookies[settings.SESSION_COOKIE_NAME].value == key
        renewed = Session.objects.get(session_key=key).expire_date
        assert renewed == future + timedelta(days=30)
        assert renewed > initial
    with patch("django.utils.timezone.now", return_value=renewed + timedelta(seconds=1)):
        assert a.get("/api/export/").status_code == 302


def test_reconstructed_client_and_database_connection_keep_session(env):
    from django.conf import settings
    from django.db import connection

    key = env["a"].cookies[settings.SESSION_COOKIE_NAME].value
    connection.close()  # A new server connection/process reads the same persistent row.
    reopened = env["client"]()
    reopened.cookies[settings.SESSION_COOKIE_NAME] = key
    assert reopened.get("/api/export/").status_code == 200
    assert reopened.cookies[settings.SESSION_COOKIE_NAME].value == key
    a = env["a"]
    assert a.post("/logout/", {"csrfmiddlewaretoken": a.cookies["dex_b1_csrf"].value}).status_code == 302
    assert reopened.get("/api/export/").status_code == 302


def test_password_change_revokes_rolling_session_without_other_account_effect(env):
    user = env["owner"]
    user.set_unusable_password()
    user.save(update_fields=["password"])
    assert env["a"].get("/api/export/").status_code == 302
    assert env["b"].get("/api/export/").status_code == 200


def test_staging_retains_original_short_browser_session_policy():
    from pokemon_hunter.beta.staging_config import configuration

    configured = configuration(
        dict(
            DATABASE_URL="postgresql://example.invalid/dex",
            DEX_SECRET_KEY="x" * 60,
            DEX_PUBLIC_ORIGIN="https://dex.example",
            DEX_PROXY_NETWORKS="127.0.0.1/32",
        )
    )
    assert configured["SESSION_COOKIE_AGE"] == 3600
    assert configured["SESSION_EXPIRE_AT_BROWSER_CLOSE"] is True
    assert configured["SESSION_SAVE_EVERY_REQUEST"] is False
    assert configured["SESSION_COOKIE_SECURE"] is True


def test_ordinary_reads_do_not_write_until_hourly_renewal(env):
    from django.conf import settings
    from django.contrib.sessions.models import Session
    from django.utils import timezone

    a = env["a"]
    key = a.cookies[settings.SESSION_COOKIE_NAME].value
    row = Session.objects.get(session_key=key)
    original = row.session_data, row.expire_date
    with patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(minutes=30)):
        assert a.get("/api/export/").status_code == 200
    row.refresh_from_db()
    assert (row.session_data, row.expire_date) == original
    with patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(hours=2)):
        assert a.get("/api/export/").status_code == 200
    row.refresh_from_db()
    assert row.expire_date > original[1]
    assert row.session_key == key


def test_ordinary_login_cycles_untrusted_session_key(env):
    from django.conf import settings
    from django.contrib.sessions.models import Session

    client = env["client"]()
    session = client.session
    session["untrusted"] = "engineering-only"
    session.save()
    prior = session.session_key
    client.cookies[settings.SESSION_COOKIE_NAME] = prior
    assert env["login"](client, "admin", env["password"]).status_code == 302
    assert client.cookies[settings.SESSION_COOKIE_NAME].value != prior
    assert not Session.objects.filter(session_key=prior).exists()
