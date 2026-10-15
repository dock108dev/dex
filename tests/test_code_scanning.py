"""Redirect and error-disclosure boundaries on disposable engineering state."""

import json
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from test_b1 import env as env
from test_migration import snapshot as snapshot


def test_review_conflicts_return_fixed_guidance_without_exception_details(env, caplog):
    from django.test import RequestFactory

    from pokemon_hunter.beta import collection, collection_views

    request = RequestFactory().get("/api/collection/")
    request.user = SimpleNamespace(is_authenticated=True)

    @collection_views.endpoint
    def failing(request):
        raise error from ValueError("SECRET chained exception /private/owner.db")

    cases = {**collection.REVIEW_CONFLICT_MESSAGES, "SECRET unknown code": collection.REVIEW_CONFLICT_DEFAULT}
    for code, expected in cases.items():
        error = collection.ReviewConflict(code)
        # Even a known code must not forward subsequently attached exception details.
        error.args = ("SECRET exception payload /private/owner.db",)
        response = failing(request)
        assert response.status_code == 409
        assert json.loads(response.content) == {"error": expected}
        assert b"SECRET" not in response.content
    assert "request_review_conflict" in caplog.text
    assert "SECRET" not in caplog.text
    assert "/private/owner.db" not in caplog.text


def test_pokedex_redirect_boundary_rejects_remote_and_non_pokedex_destinations(env):
    from pokemon_hunter.beta.species_views import _redirect

    for target in (
        "https://evil.example/pokedex/",
        "http://evil.example/pokedex/",
        "//evil.example/pokedex/",
        "///evil.example/pokedex/",
        "\\\\evil.example/pokedex/",
        "/\\evil.example/pokedex/",
        "https:/evil.example/pokedex/",
        "javascript:alert(1)",
        "/cards/",
    ):
        with pytest.raises(ValueError):
            _redirect(target)


def test_legacy_pokedex_redirects_keep_url_like_search_text_in_query_only(env):
    guest = env["client"]()
    for search in ("https://evil.example/?x=1&y=2", "//evil.example/", "\\\\evil.example/", "a#fragment"):
        for extra, path in (({"region": "1"}, "/pokedex/"), ({"species": "2"}, "/pokedex/2/")):
            response = guest.get("/pokedex/", {"q": search, **extra})
            assert response.status_code == 302, response.content
            target = urlsplit(response.url)
            assert target.path == path
            assert not target.scheme and not target.netloc and not target.fragment
            fields = parse_qs(target.query)
            if "return" in fields:
                returned = urlsplit(fields["return"][0])
                assert returned.path == "/pokedex/" and not returned.scheme and not returned.netloc
                fields = parse_qs(returned.query)
            assert fields["q"] == [search]
            assert response["Cache-Control"] == "no-store"
