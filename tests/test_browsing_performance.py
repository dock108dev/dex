"""Bounded reads keep large inventories and off-page artwork out of browsing."""

from unittest.mock import patch

from django.test import Client
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_cx03_review import dump
from test_effective_collection import cx as cx
from test_migration import snapshot as snapshot
from test_sealed_catalog import e1 as e1

from pokemon_hunter.beta import card_groups, collection, image_mappings


def test_context_does_not_export_inventory_or_project_collection(cx):
    before = dump(cx)
    with (
        patch.object(collection, "export_data", side_effect=AssertionError("full inventory export")),
        patch("pokemon_hunter.beta.effective_collection.project", side_effect=AssertionError("projection")),
    ):
        response = cx["a"].get("/api/collection-context/")
    assert response.status_code == 200
    result = response.json()
    assert result["context_only"] is True
    assert result["effective_collection"] == {
        "user_id": cx["actor"].user_id,
        "generation": collection.generation(cx["actor"]),
        "cards": [],
    }
    assert all(set(row) == {"id", "printing_id"} for row in result["copies"])
    assert all(set(row) == {"id", "name", "version"} for row in result["goals"])
    assert set(result) == {"context_only", "effective_collection", "binders", "copies", "goals"}
    assert "private" in response["Cache-Control"] and "no-store" in response["Cache-Control"]
    assert dump(cx) == before


def test_context_rejects_foreign_selectors_and_changed_generation(cx):
    assert cx["a"].get("/api/collection-context/?user=other").status_code == 400
    member = cx["b"].get("/api/collection-context/")
    assert member.status_code == 200
    assert member.json()["effective_collection"]["user_id"] == cx["member"].user_id
    assert not (
        {r["id"] for r in member.json()["copies"]} & {c["id"] for c in collection.copies(cx["actor"])}
    )
    generation = collection.generation(cx["actor"])
    with patch.object(collection, "generation", side_effect=[generation, generation + 1]):
        assert cx["a"].get("/api/collection-context/").status_code == 409
    assert (
        Client(HTTP_HOST="127.0.0.1:8011", REMOTE_ADDR="127.0.0.1")
        .get("/api/collection-context/")
        .status_code
        == 302
    )


def test_only_visible_page_and_detail_bind_artwork(cx):
    real = image_mappings.card_group_reference
    with patch.object(image_mappings, "card_group_reference", wraps=real) as reference:
        page = card_groups.list_groups(cx["actor"], {"page_size": "1"})
        assert page["total"] > 1 and len(page["groups"]) == 1
        assert reference.call_count == 1
        assert "reference_image" in page["groups"][0]
        reference.reset_mock()
        card_groups.filter_options(cx["actor"])
        assert reference.call_count == 0
        card_groups.detail(cx["actor"], page["groups"][0]["id"])
        assert reference.call_count == 1
        reference.reset_mock()
        empty = card_groups.list_groups(cx["actor"], {"q": "no-such-card"})
        assert empty["total"] == 0 and reference.call_count == 0
