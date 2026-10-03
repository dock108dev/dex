import httpx
import pytest

from pokemon_hunter.ebay import EbayClient, EbayError, EbayHTTPError, discover


@pytest.fixture(autouse=True)
def credentials(monkeypatch):
    monkeypatch.setenv("EBAY_CLIENT_ID", "test-id")
    monkeypatch.setenv("EBAY_CLIENT_SECRET", "test-secret")


def test_oauth_filters_pagination_and_dedup(settings):
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path.endswith("/token"):
            assert b"grant_type=client_credentials" in request.content
            assert b"scope=https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope" in request.content
            assert request.headers["authorization"].startswith("Basic ")
            return httpx.Response(200, json={"access_token": "test-token", "expires_in": 7200})
        assert request.headers["X-EBAY-C-MARKETPLACE-ID"] == "EBAY_US"
        assert "zip%3D08803" in request.headers["X-EBAY-C-ENDUSERCTX"]
        params = request.url.params
        assert "deliveryPostalCode:08803" in params["filter"]
        assert any(f"buyingOptions:{{{x}}}" in params["filter"] for x in ["AUCTION", "FIXED_PRICE"])
        payload = {"itemSummaries": [{"itemId": "123", "buyingOptions": ["AUCTION"]}], "total": 150}
        if params["offset"] == "0":
            payload["next"] = "https://api.ebay.com/next"
        return httpx.Response(200, json=payload)

    client = EbayClient(settings, httpx.Client(transport=httpx.MockTransport(handler)))
    items = discover(client, ["pokemon neo lot", "pokemon wotc lot"])
    assert len(items) == 1
    assert items[0]["_queries"] == ["pokemon neo lot", "pokemon wotc lot"]
    assert len(requests) == 9  # 1 token + 2 options × 2 queries × 2 pages


def test_retry_and_token_refresh(settings):
    counts = {"token": 0, "get": 0}
    sleeps = []

    def handler(request):
        if request.url.path.endswith("/token"):
            counts["token"] += 1
            return httpx.Response(200, json={"access_token": str(counts["token"]), "expires_in": 1000})
        counts["get"] += 1
        if counts["get"] == 1:
            return httpx.Response(401)
        if counts["get"] == 2:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json={"itemSummaries": []})

    client = EbayClient(settings, httpx.Client(transport=httpx.MockTransport(handler)), sleep=sleeps.append)
    assert list(client.search("test", "AUCTION")) == []
    assert counts == {"token": 2, "get": 3}
    assert sleeps == [0]


def test_error_does_not_leak_response(settings):
    def handler(request):
        return httpx.Response(403, json={"secret": "never-print-me"})

    client = EbayClient(settings, httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(EbayError, match="HTTP 403") as error:
        client.access_token()
    assert "never-print-me" not in str(error.value)


@pytest.mark.parametrize("code, expected", [("invalid_client", "invalid_client"), ("SECRET", None), ([], None)])
def test_http_error_retains_only_safe_oauth_fields(code, expected):
    response = httpx.Response(401, json={"error": code, "error_description": "SECRET", "token": "SECRET"})
    error = EbayHTTPError("OAuth", 401, response)
    assert (error.stage, error.status, error.code) == ("OAuth", 401, expected)
    assert "SECRET" not in str(error) + repr(vars(error))
    browse = EbayHTTPError("Browse", 403, response)
    assert browse.code is None


def test_page_cap_recorded(settings):
    settings.search.max_pages = 1
    client = EbayClient(settings)
    client.get = lambda *a, **kw: {"itemSummaries": [], "next": "more"}
    assert list(client.search("test", "FIXED_PRICE")) == []
    assert "page cap" in client.warnings[0]
    client.close()
