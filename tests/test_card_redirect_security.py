"""Redirect boundary regression checks on isolated engineering accounts."""

import pytest
from test_b1 import env as env
from test_b2 import b2 as b2
from test_migration import snapshot as snapshot

from pokemon_hunter.beta import account_read_queries, card_groups


@pytest.mark.parametrize(
    "target",
    [
        "https://attacker.example/",
        "//attacker.example/",
        "///attacker.example/",
        r"/\attacker.example/",
        r"\\attacker.example/",
        "https:/attacker.example/",
        "javascript:alert(1)",
        "\x01//attacker.example/",
        "",
    ],
)
def test_legacy_redirect_rejects_unsafe_resolver_output(b2, monkeypatch, target):
    monkeypatch.setattr(account_read_queries, "resolve", lambda *args, **kwargs: {"url": target})
    response = b2["a"].get("/cards/engineering-alias/")
    assert response.status_code == 400
    assert "Location" not in response
    assert "no-store" in response["Cache-Control"]


@pytest.mark.parametrize("child", [None, "printing & //attacker.example/"])
def test_legacy_redirect_preserves_local_canonical_destination(b2, monkeypatch, child):
    target = card_groups.canonical_url("dg1-" + "a" * 64, child)
    monkeypatch.setattr(account_read_queries, "resolve", lambda *args, **kwargs: {"url": target})
    response = b2["a"].get("/cards/engineering-alias/")
    assert response.status_code == 302
    assert response["Location"] == target
    assert "no-store" in response["Cache-Control"]
