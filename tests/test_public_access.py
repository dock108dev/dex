"""Guest catalog browsing and account boundaries on disposable synthetic roots."""

import importlib
import json
from unittest.mock import patch

import pytest
from django.db import connection
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_migration import snapshot as snapshot
from test_sealed_catalog import e1 as e1
from test_sealed_catalog import package, publish
from test_sealed_expansion import expanded

from pokemon_hunter.beta import collection as inv
from pokemon_hunter.beta import public_catalog, store

PRIVATE_TABLES = (
    "owned_copies",
    "collection_goals",
    "collection_sources",
    "ownership_declarations",
    "saved_hunts",
    "private_archives",
    "pack_research",
    "collection_operations",
)


def test_early_root_guest_registry_browse_uses_no_private_data_or_network(env):
    queries = []

    def record(execute, sql, params, many, context):
        queries.append(sql.lower())
        return execute(sql, params, many, context)

    guest = env["client"]()
    with (
        connection.execute_wrapper(record),
        patch("httpx.Client.send", side_effect=AssertionError("No network")),
    ):
        for route in ("/", "/pokedex/", "/pokedex/123/", "/hunt/", "/lookup/?targets=123"):
            assert guest.get(route).status_code == 200
        numeric = guest.get("/pokedex/", {"q": "#123"})
        assert b"Scyther" in numeric.content and b"Bulbasaur" not in numeric.content
        assert guest.get("/pokedex/252/").status_code == 404
        assert guest.get("/api/public/catalog/").json()["printings"] == []
    assert not any(table in sql for sql in queries for table in PRIVATE_TABLES)
    assert b"0 indexed cards" in guest.get("/pokedex/123/").content
    for asset in ("glass.css", "collection.css", "public.css"):
        assert guest.get("/collection-assets/" + asset).status_code == 200
    assert guest.get("/collection-assets/secret.key").status_code == 404


def test_public_printings_are_allowlisted_published_and_escaped(b4):
    row = inv.catalog(b4["actor"])[0]
    attributes = dict(
        row["attributes"], name='<script>alert("private")</script>', secret_marker="PRIVATE-ATTR"
    )
    inv.execute(
        "UPDATE printings SET attributes=%s,provenance=%s WHERE id=%s",
        [json.dumps(attributes), json.dumps({"source": "/private/PRIVATE-PROVENANCE"}), row["id"]],
    )
    guest = b4["client"]()
    response = guest.get("/api/public/catalog/")
    assert response.status_code == 200
    printing = next(value for value in response.json()["printings"] if value["id"] == row["id"])
    assert set(printing) == {*public_catalog.CARD_FIELDS, "pokemon_dex", "rarity", "supertype", "era"}
    assert b"PRIVATE-ATTR" not in response.content and b"PRIVATE-PROVENANCE" not in response.content
    number = printing["pokemon_dex"]
    assert number
    page = guest.get(f"/pokedex/{number}/")
    assert b"&lt;script&gt;" in page.content and b'<script>alert("private")</script>' not in page.content
    inv.execute("UPDATE printings SET language='ja' WHERE id=%s", [row["id"]])
    assert row["id"] not in {value["id"] for value in guest.get("/api/public/catalog/").json()["printings"]}
    inv.execute("UPDATE printings SET language='en' WHERE id=%s", [row["id"]])
    inv.execute("INSERT INTO games VALUES('public-other','other','Other game','test','{}','test')")
    inv.execute("UPDATE catalog_sets SET game_id='public-other' WHERE id=%s", [row["set_id"]])
    assert row["set_id"] not in {
        value["set_id"] for value in guest.get("/api/public/catalog/").json()["printings"]
    }
    inv.execute("UPDATE catalog_sets SET game_id=%s WHERE id=%s", [row["game_id"], row["set_id"]])
    inv.execute("UPDATE printings SET publication_state='archived' WHERE id=%s", [row["id"]])
    assert row["id"] not in {value["id"] for value in guest.get("/api/public/catalog/").json()["printings"]}
    inv.execute("UPDATE catalog_sets SET publication_state='archived' WHERE id=%s", [row["set_id"]])
    assert row["set_id"] not in {
        value["set_id"] for value in guest.get("/api/public/catalog/").json()["printings"]
    }


def test_guest_private_routes_and_mutations_stay_account_only(b4):
    guest = b4["client"]()
    before = inv.export_data(b4["actor"])
    for route in (
        "/cards/",
        "/collection/",
        "/goals/",
        "/settings/",
        "/scan/",
        "/requests/",
        "/catalog-review/",
        "/api/collection/",
        "/api/catalog/",
        "/api/inventory/",
        "/api/goals/",
        "/api/binders/",
        "/api/export/",
        "/api/hunts/",
        "/api/archives/",
        "/packs/saved/",
        "/packs/refresh/",
    ):
        # cards is only enabled by parity; other routes always exist in this fixture.
        expected = {302, 404} if route == "/cards/" else {302}
        assert guest.get(route).status_code in expected
    for route in ("/lookup/save/", "/packs/save/", "/api/operations/preview/", "/api/scans/"):
        assert guest.post(route, "{}", content_type="application/json").status_code in {302, 403}
    assert inv.export_data(b4["actor"]) == before
    assert b4["b"].get("/api/inventory/").json()["copies"] == []
    assert b4["a"].get("/").status_code == 200
    assert b4["a"].get("/collection/").status_code == 200
    assert (
        b'<script src="/collection-assets/collection.js" defer></script>'
        in b4["a"].get("/collection/").content
    )
    assert b'<script src="/collection-assets/collection.js" defer></script>' in b4["a"].get("/").content


def test_guest_lookup_reuses_public_evidence_without_account_reads(e1):
    publish(e1, package())
    publish(e1, expanded())
    queries = []

    def record(execute, sql, params, many, context):
        queries.append(sql.lower())
        return execute(sql, params, many, context)

    guest = e1["client"]()
    before = inv.export_data(e1["actor"])
    with (
        connection.execute_wrapper(record),
        patch("httpx.Client.send", side_effect=AssertionError("No network")),
    ):
        result = public_catalog.pack_lookup({"targets": "123"})
        page = guest.get("/lookup/", {"targets": "123"})
    assert page.status_code == 200
    assert result["goal"] == {"name": "Selected Pokémon"}
    assert result["progress"]["total"] == 1 and "satisfied" not in result["progress"]
    assert len(result["expansions"]) == 1 and result["expansions"][0]["count"] == 1
    assert "versions" not in result and "source_goal_id" not in result
    assert not any(table in sql for sql in queries for table in PRIVATE_TABLES)
    checked = {
        observation["checked_at"]
        for group in result["expansions"]
        for product in group["products"]
        for offer in product["offers"]
        for observation in offer["observations"]
    }
    assert checked and checked <= {
        json.loads(row["data"])["checked_at"] for row in store.rows("SELECT data FROM sealed_observations")
    }
    assert inv.export_data(e1["actor"]) == before


@pytest.mark.parametrize(
    "query",
    [
        {"goal": "other-account"},
        {"goal": ""},
        {"scope": "missing"},
        {"user_id": "forged"},
        {"scope_version": "private"},
        {"targets": "252"},
    ],
)
def test_guest_lookup_private_or_invalid_scope_is_a_helpful_error(b4, query):
    response = b4["client"]().get("/lookup/", query)
    assert response.status_code == 400
    assert b'role="alert"' in response.content


def test_guest_pokedex_dispatch_and_signed_in_collection_remain_distinct(b4):
    from django.conf import settings
    from django.urls import clear_url_caches

    from pokemon_hunter.beta import urls

    previous = settings.PARITY_ENABLED
    settings.PARITY_ENABLED = True
    importlib.reload(urls)
    clear_url_caches()
    try:
        guest = b4["client"]()
        assert guest.get("/pokedex/").status_code == 200
        assert b"public-species" in guest.get("/pokedex/").content
        assert guest.get("/hunt/").status_code == 200
        assert guest.get("/cards/").status_code == 302
        assert guest.get("/api/parity/").status_code == 302
        assert b4["a"].get("/pokedex/").status_code == 200
        assert (
            b'<script src="/collection-assets/parity.js" defer></script>' in b4["a"].get("/pokedex/").content
        )
        assert (
            b4["a"].post("/logout/", HTTP_X_CSRFTOKEN=b4["a"].cookies["dex_b1_csrf"].value).url == "/pokedex/"
        )
    finally:
        settings.PARITY_ENABLED = previous
        importlib.reload(urls)
        clear_url_caches()
