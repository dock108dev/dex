"""Offline browser-boundary regression tests with synthetic inputs only."""

import json

import pytest
from pydantic import BaseModel
from test_b1 import env as env
from test_migration import snapshot as snapshot

from pokemon_hunter.hunt import analyze, public_listing
from pokemon_hunter.normalize import evaluate
from pokemon_hunter.security import BROWSER_HEADERS, ebay_url


@pytest.mark.parametrize(
    "url",
    [
        r"https://evil.example\@www.ebay.com/item",
        "https://www.ebay.com.evil.example/item",
        "https://user:password@www.ebay.com/item",
        "https://www.ebay.com:444/item",
        "https://www.ebay.com:bad/item",
        "https://[broken",
        "https://www.ebay.com/\nitem",
        " javascript:alert(1)",
        "//www.ebay.com/item",
    ],
)
def test_unsafe_listing_links_never_qualify_or_reveal(url, raw, settings, catalog, now):
    from conftest import synthetic_collection

    assert ebay_url(url) is None
    raw["itemWebUrl"] = url
    listing = evaluate(raw, settings, catalog, (1, 1), now)
    assert not listing.qualifying
    assert "Missing or invalid eBay listing link" in listing.rejection_reasons
    # Use the checked-in public search configuration, never owner state.
    from conftest import ROOT

    config = json.loads((ROOT / "config/hunt.json").read_text())
    result = public_listing(analyze(raw, synthetic_collection(), config, {}), reveal=True)
    assert result["url"] is None


@pytest.mark.parametrize("url", ["https://www.ebay.com/itm/123", "https://ebay.com:443/itm/1?x=2"])
def test_normal_listing_links_preserved(url):
    assert ebay_url(url) == url


def test_authenticated_security_headers_include_errors(env):
    for response in [
        env["a"].get("/"),
        env["client"]().get("/"),
        env["a"].get("/", HTTP_HOST="evil.example"),
    ]:
        for key, value in BROWSER_HEADERS.items():
            assert response[key] == value
    assert "camera=(self)" in BROWSER_HEADERS["Permissions-Policy"]


def test_staging_headers_keep_existing_ingress_boundary(env):
    import ipaddress

    from django.http import HttpResponse
    from django.test import RequestFactory, override_settings

    from pokemon_hunter.beta.security import StagingMiddleware

    middleware = StagingMiddleware(lambda request: HttpResponse("synthetic"))
    with override_settings(
        PUBLIC_ORIGIN="https://dex.example",
        PROXY_NETWORKS=[ipaddress.ip_network("127.0.0.1/32")],
        ALLOWED_HOSTS=["dex.example"],
    ):
        request = RequestFactory().get("/", HTTP_HOST="dex.example", HTTP_X_FORWARDED_PROTO="https")
        for key, value in BROWSER_HEADERS.items():
            assert middleware(request)[key] == value
        request.META["HTTP_X_FORWARDED_PROTO"] = "http"
        assert middleware(request).status_code == 403


def test_validation_errors_do_not_echo_values_or_typeerror_details(env, caplog):
    from django.test import RequestFactory

    from pokemon_hunter.beta.collection_views import endpoint

    class Input(BaseModel):
        count: int

    @endpoint
    def invalid(request):
        Input.model_validate({"count": "private-submitted-value"})

    @endpoint
    def broken(request):
        raise TypeError("private-internal-detail")

    request = RequestFactory().get("/")
    request.user = env["owner"]
    for view in (invalid, broken):
        response = view(request)
        assert response.status_code == 400
        assert b"private-" not in response.content
    assert "request_type_error" in caplog.text
    assert "private-internal-detail" not in caplog.text


@pytest.mark.parametrize(
    "kind,status,event", [("value", 400, "request_value_error"), ("conflict", 409, "request_conflict")]
)
def test_collection_exceptions_do_not_expose_details(env, caplog, kind, status, event):
    from django.test import RequestFactory

    from pokemon_hunter.beta.collection import Conflict
    from pokemon_hunter.beta.collection_views import endpoint

    @endpoint
    def broken(request):
        raise (Conflict if kind == "conflict" else ValueError)("private-content /private/database.db")

    request = RequestFactory().get("/")
    request.user = env["owner"]
    response = broken(request)
    assert response.status_code == status
    assert json.loads(response.content)["error"]
    assert event in caplog.text
    assert "private-content" not in caplog.text + response.content.decode()
    assert "/private/database.db" not in caplog.text + response.content.decode()
