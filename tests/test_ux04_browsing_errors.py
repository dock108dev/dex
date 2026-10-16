"""Bounded browsing guidance without changing private mutation/import contracts."""

from unittest.mock import patch
from urllib.parse import urlencode

import pytest
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b2 import post
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_card_groups import find
from test_cx03_review import dump
from test_effective_collection import cx as cx
from test_migration import snapshot as snapshot
from test_sealed_catalog import e1 as e1


@pytest.mark.parametrize(
    "path",
    [
        "/api/my-card-groups/?species=252",
        "/api/my-card-groups/?q=private-one&q=private-two",
        "/api/card-groups/?scope=unsafe",
        "/api/card-group-filters/?scope=owned&scope=all",
        "/api/species/2/card-groups/?page=-1",
        "/api/collection-context/?private=secret",
        "/api/navigation/home/?destination=/cards/&destination=/pokedex/",
        "/api/navigation/home/?" + urlencode({"destination": "https://example.invalid/private"}),
        "/api/navigation/home/?" + urlencode({"destination": "/cards/?q=one&q=two"}),
    ],
)
def test_browsing_bad_filters_are_safe_json_with_supported_recovery(cx, path):
    from pokemon_hunter.beta.collection_views import BROWSING_ERROR

    before = dump(cx)
    response = cx["a"].get(path)
    assert response.status_code == 400
    assert response["Content-Type"] == "application/json"
    assert response["Cache-Control"] == "private, no-store"
    assert response.json() == {"error": BROWSING_ERROR, "recovery_url": "/cards/"}
    assert "import" not in response.content.decode().lower()
    assert cx["a"].get(response.json()["recovery_url"]).status_code == 200
    assert dump(cx) == before


@pytest.mark.parametrize(
    "back",
    [
        "https://example.invalid/private?secret=hidden",
        "//example.invalid/cards/",
        "/cards/?q=private-one&q=private-two",
        "/cards/?scroll=bad",
        "/cards/?q=%00private",
        "/cards/?q",
        "/pokedex/?region=kanto&region=johto",
    ],
)
def test_card_page_malformed_return_original_failure_and_no_echo(cx, back):
    from pokemon_hunter.beta.collection_views import BROWSING_ERROR

    group = find(cx, "a")
    before = dump(cx)
    response = cx["a"].get(f"/card-groups/{group['id']}/?" + urlencode({"return": back}))
    assert response.status_code == 400
    assert response.json() == {"error": BROWSING_ERROR, "recovery_url": "/cards/"}
    assert "private" not in response.content.decode()
    assert "example.invalid" not in response.content.decode()
    assert dump(cx) == before


def test_auth_methods_generation_and_account_guards_survive(cx):
    from pokemon_hunter.beta import collection

    assert cx["client"]().get("/api/my-card-groups/?species=252").status_code == 302
    assert post(cx["a"], "/api/my-card-groups/", {}).status_code == 405
    group = find(cx, "a")
    stale = collection.generation(cx["actor"]) + 1
    assert cx["a"].get(f"/api/card-groups/{group['id']}/?generation={stale}").status_code == 409
    a = cx["a"].get("/api/my-card-groups/").json()
    b = cx["b"].get("/api/my-card-groups/").json()
    assert a["account_id"] != b["account_id"]


@pytest.mark.parametrize("kind", ["import", "add", "card_quantity"])
def test_genuine_mutation_value_errors_keep_original_contract(cx, kind):
    from pokemon_hunter.beta import collection

    before = dump(cx)
    with patch.object(collection, "preview", side_effect=ValueError("private submitted data")):
        response = post(
            cx["a"], "/api/operations/preview/", {"kind": kind, "request": {}, "operation_id": "invalid"}
        )
    assert response.status_code == 400
    assert response.json() == {"error": "Invalid request. Check the fields and import format."}
    assert dump(cx) == before


def test_card_mutation_is_not_opted_into_browsing_guidance(cx):
    group = find(cx, "a")
    before = dump(cx)
    response = post(cx["a"], f"/api/card-groups/{group['id']}/preview/", [])
    assert response.status_code == 400
    assert response.json() == {"error": "Invalid request. Check the fields and import format."}
    assert dump(cx) == before
