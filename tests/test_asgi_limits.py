"""Real Django abort/cleanup and finite ingress checks; no sockets or owner state."""

import asyncio
from types import SimpleNamespace

import pytest
from test_b1 import env as env
from test_migration import snapshot as snapshot

from pokemon_hunter.beta import asgi
from pokemon_hunter.security import BROWSER_HEADERS


def exchange(
    application,
    chunks=(),
    headers=(),
    path="/login/",
    method="POST",
    host=b"127.0.0.1:8011",
    peer=("127.0.0.1", 54321),
):
    async def run():
        messages = iter(chunks)
        reads, sent = [], []

        async def receive():
            try:
                message = next(messages)
            except StopIteration:
                await asyncio.Future()  # Django's disconnect listener waits until cancelled.
            reads.append(message)
            return message

        async def send(message):
            sent.append(message)

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method,
            "path": path,
            "query_string": b"",
            "scheme": "http",
            "headers": ([(b"host", host)] if host is not None else []) + list(headers),
            "client": peer,
            "server": ("127.0.0.1", 8011),
        }
        await asyncio.wait_for(application(scope, receive, send), timeout=5)
        return reads, sent

    return asyncio.run(run())


def chunk(body, more=False):
    return {"type": "http.request", "body": body, "more_body": more}


@pytest.fixture
def ingress(monkeypatch):
    monkeypatch.setattr(asgi, "settings", SimpleNamespace(DATA_UPLOAD_MAX_MEMORY_SIZE=8, B3_ENABLED=True))
    forwarded, dispatched = [], []

    async def downstream(scope, receive, send):
        # Django consumes the full stream before dispatching any middleware/view.
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            forwarded.append(message["body"])
            if not message.get("more_body", False):
                break
        dispatched.append(scope["path"])
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"accepted"})

    return asgi.BoundedBodyApplication(downstream), forwarded, dispatched


@pytest.mark.parametrize("headers", [[], [(b"content-length", b"1")]])
def test_actual_stream_limit_does_not_trust_declared_length(ingress, headers):
    app, forwarded, dispatched = ingress
    reads, sent = exchange(app, [chunk(b"1234", True), chunk(b"56789", True), chunk(b"unread")], headers)
    assert len(reads) == 2
    assert forwarded == [b"1234"] and not dispatched
    assert sent[0]["status"] == 413
    response_headers = dict(sent[0]["headers"])
    for key, value in BROWSER_HEADERS.items():
        assert response_headers[key.lower().encode()] == value.encode()
    assert b"1234" not in sent[1]["body"]


@pytest.mark.parametrize(
    "headers,status",
    [
        ([(b"content-length", b"9")], 413),
        ([(b"content-length", b"-1")], 400),
        ([(b"content-length", b"+1")], 400),
        ([(b"content-length", b"")], 400),
        ([(b"content-length", b"1,1")], 400),
        ([(b"content-length", b"1"), (b"content-length", b"1")], 400),
        ([(b"content-length", b"9" * 1000)], 400),
    ],
)
def test_invalid_or_oversized_length_refused_without_body_read(ingress, headers, status):
    app, forwarded, dispatched = ingress
    reads, sent = exchange(app, [chunk(b"never consumed")], headers)
    assert not reads and not forwarded and not dispatched
    assert sent[0]["status"] == status


@pytest.mark.parametrize("size", [0, 7, 8])
def test_supported_body_at_or_below_limit(ingress, size):
    app, forwarded, dispatched = ingress
    _, sent = exchange(app, [chunk(b"x" * size)], [(b"content-length", str(size).encode())])
    assert sent[0]["status"] == 200
    assert forwarded == [b"x" * size] and dispatched == ["/login/"]


@pytest.mark.parametrize(
    "enabled,path,method,status",
    [
        (True, "/api/scans/", "POST", 200),
        (False, "/api/scans/", "POST", 413),
        (True, "/api/scans/", "PUT", 413),
        (True, "/api/operations/preview/", "POST", 413),
    ],
)
def test_two_photo_allowance_only_on_enabled_upload_route(ingress, enabled, path, method, status):
    app, _, _ = ingress
    asgi.settings.B3_ENABLED = enabled
    _, sent = exchange(app, [chunk(b"x" * 9)], path=path, method=method)
    assert sent[0]["status"] == status


def test_photo_limit_exact_boundary_and_overflow(ingress):
    app, _, dispatched = ingress
    _, accepted = exchange(app, [chunk(b"x" * asgi.SCAN_BODY_LIMIT)], path="/api/scans/")
    assert accepted[0]["status"] == 200
    dispatched.clear()
    _, refused = exchange(app, [chunk(b"x" * (asgi.SCAN_BODY_LIMIT + 1))], path="/api/scans/")
    assert refused[0]["status"] == 413 and not dispatched


def test_disconnect_is_not_reported_as_oversize(ingress):
    app, _, dispatched = ingress
    _, sent = exchange(app, [{"type": "http.disconnect"}])
    assert not sent and not dispatched


def test_non_http_scope_passed_through():
    seen = []

    async def downstream(scope, receive, send):
        seen.append(scope)

    scope = {"type": "lifespan"}
    asyncio.run(asgi.BoundedBodyApplication(downstream)(scope, None, None))
    assert seen == [scope]


def test_real_django_closes_spool_before_dispatch_on_chunk_overflow(env, monkeypatch):
    from django.core.handlers import asgi as django_asgi
    from django.core.signals import request_started
    from django.test import override_settings

    spools, dispatched = [], []
    factory = django_asgi.tempfile.SpooledTemporaryFile

    def spool(*args, **kwargs):
        result = factory(*args, **kwargs)
        spools.append(result)
        return result

    def started(sender, **kwargs):
        dispatched.append(True)

    monkeypatch.setattr(django_asgi.tempfile, "SpooledTemporaryFile", spool)
    request_started.connect(started)
    try:
        with override_settings(DATA_UPLOAD_MAX_MEMORY_SIZE=8, FILE_UPLOAD_MAX_MEMORY_SIZE=2):
            _, sent = exchange(asgi.get_asgi_application(), [chunk(b"1234", True), chunk(b"56789")])
        assert sent[0]["status"] == 413
        assert len(spools) == 1 and spools[0].closed
        assert not dispatched
    finally:
        request_started.disconnect(started)


def test_real_django_ordinary_public_request_keeps_security_headers(env):
    _, sent = exchange(asgi.get_asgi_application(), [chunk(b"")], method="GET")
    assert sent[0]["status"] == 200
    headers = {key.lower(): value for key, value in sent[0]["headers"]}
    assert b"no-store" in {value.strip() for value in headers[b"cache-control"].split(b",")}
    assert b"Content-Security-Policy".lower() in headers


@pytest.mark.parametrize("suffix", ["upload", "retake"])
def test_batch_photo_ingress_exact_independent_bound(ingress, suffix):
    app, _, dispatched = ingress
    path = f"/api/photo-batches/00000000-0000-0000-0000-000000000001/{suffix}/"
    _, accepted = exchange(app, [chunk(b"x" * 8_100_000)], path=path)
    assert accepted[0]["status"] == 200
    dispatched.clear()
    _, refused = exchange(app, [chunk(b"x" * 8_100_001)], path=path)
    assert refused[0]["status"] == 413 and not dispatched
    _, ordinary = exchange(app, [chunk(b"x" * 9)], path=path, method="PUT")
    assert ordinary[0]["status"] == 413


@pytest.mark.parametrize(
    "options",
    [
        {"host": None},
        {"host": b"evil.example"},
        {"host": b"localhost:8011"},
        {"host": b"127.0.0.1:8012"},
        {"headers": [(b"Host", b"127.0.0.1:8011")]},
        {"headers": [(b"Origin", b"https://evil.example")]},
        {"headers": [(b"origin", b"null")]},
        {"headers": [(b"origin", b"")]},
        {"headers": [(b"origin", b"http://127.0.0.1:8011"), (b"Origin", b"http://127.0.0.1:8011")]},
        {"headers": [(b"Forwarded", b"for=127.0.0.1")]},
        {"headers": [(b"X-Forwarded-Port", b"8011")]},
        {"peer": ("192.0.2.1", 54321)},
        {"peer": None},
    ],
)
def test_local_boundary_rejects_before_reading_or_spooling(ingress, options):
    app, forwarded, dispatched = ingress
    reads, sent = exchange(app, [chunk(b"untrusted upload")], path="/api/scans/", **options)
    assert not reads and not forwarded and not dispatched
    assert sent[0]["status"] == 403
    assert b"untrusted" not in sent[1]["body"]
    headers = dict(sent[0]["headers"])
    for key, value in BROWSER_HEADERS.items():
        assert headers[key.lower().encode()] == value.encode()


@pytest.mark.parametrize("peer", [("127.0.0.1", 1234), ("::1", 1234)])
@pytest.mark.parametrize("headers", [[], [(b"origin", b"http://127.0.0.1:8011")]])
def test_local_boundary_accepts_canonical_requests(ingress, peer, headers):
    app, _, dispatched = ingress
    _, sent = exchange(app, [chunk(b"valid")], peer=peer, headers=headers)
    assert sent[0]["status"] == 200 and dispatched == ["/login/"]


def test_staging_retains_separate_ingress_policy(ingress):
    app, _, dispatched = ingress
    asgi.settings.STAGING = True
    _, sent = exchange(
        app,
        [chunk(b"valid")],
        host=b"dex.example",
        peer=("192.0.2.1", 1234),
        headers=[(b"x-forwarded-proto", b"https"), (b"origin", b"https://dex.example")],
    )
    # The wrapper leaves staging ingress to its existing trusted-proxy middleware.
    assert sent[0]["status"] == 200 and dispatched == ["/login/"]


def test_foreign_origin_never_creates_a_real_django_spool(env, monkeypatch):
    from django.core.handlers import asgi as django_asgi

    def forbidden_spool(*args, **kwargs):
        pytest.fail("Disallowed local ingress reached Django body buffering")

    monkeypatch.setattr(django_asgi.tempfile, "SpooledTemporaryFile", forbidden_spool)
    reads, sent = exchange(
        asgi.get_asgi_application(),
        [chunk(b"untrusted upload")],
        headers=[(b"origin", b"https://evil.example")],
        path="/api/scans/",
    )
    assert not reads
    assert sent[0]["status"] == 403
