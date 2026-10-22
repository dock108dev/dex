"""Independent adversarial checks; disposable engineering accounts only."""

import importlib
import sqlite3
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest
from django.conf import settings
from django.urls import clear_url_caches, resolve
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_broad_goals import special
from test_collection_goals import create
from test_cx03_review import clone, find
from test_effective_collection import add, apply, select
from test_effective_collection import cx as cx
from test_migration import snapshot as snapshot
from test_sealed_catalog import e1 as e1

from pokemon_hunter.beta import collection as inv
from pokemon_hunter.beta import image_mappings


def dump(cx):
    with sqlite3.connect(cx["root"] / "inventory.db") as db:
        return list(db.iterdump())


def test_review_species_owned_groups_are_compact_distinct_and_readonly(cx):
    clone(cx, edition="first", finish="holo")
    base = clone(cx, collector_number="30")
    inv.execute("UPDATE printings SET set_id=%s WHERE id=%s", [cx["by_legacy"]["b"]["set_id"], base])
    select(cx, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon); Ivysaur #30 (Uncommon)"}})
    before = dump(cx)
    with (
        patch("requests.sessions.Session.request", side_effect=AssertionError("provider request")),
        patch("httpx.post", side_effect=AssertionError("provider request")),
    ):
        response = cx["a"].get("/api/species/2/card-groups/")
        assert response.status_code == 200, response.content
        data = response.json()
        assert data["account_id"] == cx["actor"].user_id
        assert data["generation"] == data["owned"]["generation"] == data["catalog"]["generation"]
        assert data["owned"]["total"] == 2
        assert {row["collector_number"] for row in data["owned"]["groups"]} == {"30", "44"}
        assert len({row["id"] for row in data["owned"]["groups"]}) == 2
        assert all(row["established_total_quantity"] is None for row in data["owned"]["groups"])
        for row in data["owned"]["groups"]:
            detail = cx["a"].get(f"/api/card-groups/{row['id']}/").json()
            assert detail["selected_child"] is None
    assert dump(cx) == before


@pytest.mark.parametrize("field", ["return", "scroll", "select", "focus", "account", "scope", "species"])
def test_review_species_ui_context_never_becomes_group_filter(cx, field):
    before = dump(cx)
    assert cx["a"].get("/api/species/2/card-groups/", {field: "2"}).status_code == 400
    assert dump(cx) == before


def test_review_species_group_generation_conflict_is_readonly(cx):
    first = cx["a"].get("/api/species/3/card-groups/").json()
    add(cx)
    before = dump(cx)
    result = cx["a"].get("/api/species/3/card-groups/", {"generation": first["generation"]})
    assert result.status_code == 409
    assert "reload" in result.json()["error"].lower()
    assert dump(cx) == before


def test_review_species_only_declaration_is_not_a_counterfeit_card(cx):
    select(cx, {8: {"Base Set": "✓"}, 134: {"Team Rocket": "✓D Dark Vaporeon"}})
    for dex in (8, 134):
        response = cx["a"].get(f"/api/species/{dex}/card-groups/").json()
        assert response["owned"]["groups"] == []
        assert response["unresolved"]
    state = cx["a"].get("/api/collection/").json()["effective_collection"]
    assert state["species"]["8"]["present"] and state["species"]["134"]["present"]
    assert state["species"]["8"]["established_total_quantity"] is None


@pytest.mark.parametrize("parity,staging", [(False, False), (True, False), (False, True), (True, True)])
def test_review_canonical_species_has_one_private_handler_in_all_b2_profiles(b2, parity, staging):
    from pokemon_hunter.beta import urls

    old = settings.PARITY_ENABLED, settings.STAGING
    settings.PARITY_ENABLED, settings.STAGING = parity, staging
    importlib.reload(urls)
    clear_url_caches()
    try:
        before = dump(b2)
        for path in ("/pokedex/", "/pokedex/2/"):
            response = b2["a"].get(path)
            assert response.status_code == 200, response.content
            assert b"collection.js" in response.content
            assert sum(pattern.resolve(path.lstrip("/")) is not None for pattern in urls.urlpatterns) == 1
        assert resolve("/pokedex/2/").func is resolve("/pokedex/").func
        assert dump(b2) == before
    finally:
        settings.PARITY_ENABLED, settings.STAGING = old
        importlib.reload(urls)
        clear_url_caches()


@pytest.mark.parametrize(
    "path",
    [
        "/pokedex/?species=2&species=3",
        "/pokedex/?species=0",
        "/pokedex/?species=252",
        "/pokedex/?species=two",
        "/pokedex/?region=kanto&region=johto",
        "/pokedex/?q=one&q=two",
        "/pokedex/?account=other",
        "/pokedex/2/?species=3",
        "/pokedex/2/?return=https://example.com/",
    ],
)
def test_review_species_routes_reject_ambiguous_or_unsafe_queries(cx, path):
    before = dump(cx)
    assert cx["a"].get(path).status_code == 400
    assert dump(cx) == before


def test_review_legacy_species_direct_navigation_canonicalizes(cx):
    response = cx["a"].get("/pokedex/?species=2&q=Ivy&region=kanto")
    assert response.status_code in {301, 302, 307, 308}
    assert response.url.startswith("/pokedex/2/")
    assert "species=" not in response.url
    assert cx["a"].get(response.url).status_code == 200


@pytest.mark.parametrize("legacy,region", [("all", ""), ("1", "kanto"), ("2", "johto")])
def test_review_legacy_species_and_region_combination_retains_canonical_scope(cx, legacy, region):
    response = cx["a"].get("/pokedex/", {"species": "152" if region == "johto" else "2", "region": legacy})
    assert response.status_code in {301, 302, 307, 308}
    context = parse_qs(urlsplit(response.url).query)["return"][0]
    assert parse_qs(urlsplit(context).query).get("region", [""]) == [region]
    assert cx["a"].get(response.url).status_code == 200


def test_review_species_guest_never_infers_not_collected_or_private_evidence(cx):
    select(cx, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}})
    before = dump(cx)
    guest = cx["client"]()
    for path in ("/pokedex/", "/pokedex/2/"):
        response = guest.get(path)
        assert response.status_code == 200
        text = response.content.decode()
        for private in (
            "Not collected",
            "Collected",
            "recorded_copy_count",
            "photo_references",
            "operation_ids",
        ):
            assert private not in text
        assert "collection.js" not in text
    assert guest.get("/api/species/2/card-groups/").status_code in {302, 403}
    assert dump(cx) == before


def test_review_owned_archived_group_remains_private_and_canonical_species_art_separate(cx):
    group = find(cx)
    inv.execute("UPDATE printings SET publication_state='archived'")
    before = dump(cx)
    data = cx["a"].get("/api/species/2/card-groups/").json()
    assert data["owned"]["groups"][0]["id"] == group["id"]
    assert data["catalog"]["groups"] == []
    assert cx["client"]().get(f"/api/public/card-groups/{group['id']}/").status_code == 404
    species = image_mappings.species_artwork(2)
    assert species["role"] == "species_artwork" and species["alt"] == "Ivysaur"
    assert species["bound_identity"]["pokemon_dex"] == 2
    assert species["image_url"] != data["owned"]["groups"][0].get("reference_image", {}).get("image_url")
    assert dump(cx) == before


def test_review_pokedex_preserves_all_canonical_species_and_completion_denominator(cx):
    from pokemon_hunter.beta.canonical_species import registry

    select(cx, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}, 251: {"Neo Destiny": "✓"}})
    before = dump(cx)
    with patch("pokemon_hunter.beta.parity.projection", side_effect=AssertionError("parity valuation")):
        data = cx["a"].get("/api/pokedex-species/").json()
        assert data["account_id"] == cx["actor"].user_id
        assert data["generation"] == cx["a"].get("/api/species/2/card-groups/").json()["generation"]
        assert len(data["species"]) == 251 and data["filtered_count"] == 251
        for row in data["species"]:
            assert row["name"] == registry()[row["dex"]]["name"]
            assert row["species_artwork"]["role"] == "species_artwork"
            assert row["species_artwork"]["bound_identity"]["pokemon_dex"] == row["dex"]
        assert {row["dex"] for row in data["species"] if row["current_present"]} == {2, 251}
        search = cx["a"].get("/api/pokedex-species/?q=Ivysaur").json()
        assert [row["dex"] for row in search["species"]] == [2]
        assert search["progress"] == data["progress"]
        assert search["progress"]["total"] == 251
        assert cx["a"].get("/api/pokedex-species/?region=kanto").json()["progress"]["total"] == 151
        assert cx["a"].get("/api/pokedex-species/?region=johto").json()["progress"]["total"] == 100
    assert dump(cx) == before


def test_review_saved_declaration_and_current_cards_remain_independent(cx):
    _, source = select(cx, {3: {"Base Set 2": "✓ Venusaur #18 (Rare Holo)"}})
    frozen = create(cx, source)
    definition = frozen["definition"]
    select(cx)
    before = dump(cx)
    response = cx["a"].get("/api/pokedex-species/", {"goal": frozen["id"]})
    assert response.status_code == 200, response.content
    data = response.json()
    row = next(row for row in data["species"] if row["dex"] == 3)
    assert not row["current_present"] and row["goal_present"]
    assert data["scope"]["kind"] == "saved_declaration"
    assert data["scope"]["goal_id"] == frozen["id"]
    assert data["progress"]["satisfied"] == 1
    assert cx["a"].get("/api/species/3/card-groups/").json()["owned"]["groups"] == []
    assert inv.goals(cx["actor"], goal_id=frozen["id"])[0]["definition"] == definition
    assert dump(cx) == before
    assert cx["b"].get("/api/pokedex-species/", {"goal": frozen["id"]}).status_code == 400


def test_review_printing_goal_retains_printing_units_without_invented_species_progress(cx):
    p = cx["by_legacy"]["c"]
    goal = apply(
        cx["actor"],
        "goal",
        {"name": "Exact Venusaur", "goal_kind": "custom", "policy": "exact", "printing_ids": [p["id"]]},
    )["changes"][0]["after"]
    before = dump(cx)
    data = cx["a"].get("/api/pokedex-species/", {"goal": goal["id"]}).json()
    assert data["scope"]["kind"] == "printing_goal"
    assert data["scope"]["units"] == "printings"
    assert not data["scope"]["supported"]
    assert len(data["species"]) == 251
    assert all(row["goal_present"] is None for row in data["species"])
    assert data["current_progress"]["units"] == "species"
    assert data["current_progress"]["total"] == 251
    assert data["progress"]["total"] == 1
    assert dump(cx) == before


def test_review_qualified_species_goal_does_not_count_broad_card_ownership(cx):
    p = next(row for row in special(cx) if row["name"] == "Ivysaur")
    goal = apply(cx["actor"], "goal", {"name": "Qualified species", "goal_kind": "original151"})["changes"][
        0
    ]["after"]
    definition = inv.goals(cx["actor"], goal_id=goal["id"])[0]["definition"]
    apply(
        cx["actor"],
        "mark_owned",
        {"set_name": p["set_name"], "name": p["name"], "number": p["collector_number"], "language": "en"},
    )
    data = cx["a"].get("/api/pokedex-species/", {"goal": goal["id"]}).json()
    row = next(row for row in data["species"] if row["dex"] == 2)
    assert data["scope"]["kind"] == "qualified_species" and data["scope"]["units"] == "species"
    assert row["current_present"] and not row["goal_present"]
    apply(cx["actor"], "add", {"printing_id": p["id"], "duplicate_policy": "allow"})
    data = cx["a"].get("/api/pokedex-species/", {"goal": goal["id"]}).json()
    assert next(row for row in data["species"] if row["dex"] == 2)["goal_present"]
    assert inv.goals(cx["actor"], goal_id=goal["id"])[0]["definition"] == definition


def test_review_legacy_species_goal_cannot_be_relabelled_as_printing_units(cx):
    goal = apply(cx["actor"], "goal", {"name": "Retained vintage", "goal_kind": "vintage"})["changes"][0][
        "after"
    ]
    source = inv.goals(cx["actor"], goal_id=goal["id"])[0]
    assert source["definition"]["policy"] == "species"
    response = cx["a"].get("/api/pokedex-species/", {"goal": goal["id"]})
    assert response.status_code == 200, response.content
    data = response.json()
    assert data["scope"]["units"] == "species"
    assert data["progress"]["units"] == "species"
    assert data["progress"]["total"] == source["total"]


def test_review_projection_generation_account_revocation_and_logout_boundaries(cx):
    data = cx["a"].get("/api/pokedex-species/").json()
    member = cx["b"].get("/api/pokedex-species/").json()
    assert member["account_id"] != data["account_id"]
    assert not any(row["current_present"] for row in member["species"])
    add(cx)
    before = dump(cx)
    assert cx["a"].get("/api/pokedex-species/", {"generation": data["generation"]}).status_code == 409
    assert dump(cx) == before
    cx["accounts"].revoke(cx["second"])
    assert cx["b"].get("/api/pokedex-species/").status_code in {302, 403}
    assert cx["client"]().get("/api/pokedex-species/").status_code in {302, 403}


def test_review_true_interleaved_commit_cannot_publish_mixed_species_snapshot(cx):
    from pokemon_hunter.beta import effective_collection

    original = effective_collection.project
    committed = False

    def interleaved(actor, **kwargs):
        nonlocal committed
        state = original(actor, **kwargs)
        if not committed:
            committed = True
            add(cx)
        return state

    with patch.object(effective_collection, "project", side_effect=interleaved):
        result = cx["a"].get("/api/pokedex-species/")
    assert committed and result.status_code == 409
    assert "reload" in result.json()["error"].lower()
    fresh = cx["a"].get("/api/pokedex-species/").json()
    assert next(row for row in fresh["species"] if row["dex"] == 3)["current_present"]
    assert fresh["generation"] == cx["a"].get("/api/species/3/card-groups/").json()["generation"]


@pytest.mark.parametrize(
    "query",
    [
        "q=a&q=b",
        "goal=missing",
        "region=mars",
        "generation=-1",
        "generation=١",
        "scroll=1",
        "return=/pokedex/",
        "account_id=someone",
        "goal=a&goal=b",
    ],
)
def test_review_projection_invalid_or_foreign_scope_never_silently_falls_back(cx, query):
    before = dump(cx)
    response = cx["a"].get("/api/pokedex-species/?" + query)
    assert response.status_code == 400, response.content
    assert "error" in response.json()
    assert dump(cx) == before


def test_review_two_level_species_card_return_preserves_list_context_without_selecting_child(cx):
    group = find(cx)
    list_context = "/pokedex/?q=Ivy&region=kanto&scroll=340&focus=2"
    species_context = "/pokedex/2/?" + urlencode({"return": list_context, "scroll": "45"})
    before = dump(cx)
    result = cx["a"].get(group["url"], {"return": species_context})
    assert result.status_code == 200, result.content
    assert cx["a"].get(species_context).status_code == 200
    assert cx["a"].get(list_context).status_code == 200
    assert cx["a"].get(f"/api/card-groups/{group['id']}/").json()["selected_child"] is None
    assert dump(cx) == before


@pytest.mark.parametrize(
    "destination",
    [
        "/pokedex/0/",
        "/pokedex/252/",
        "/pokedex/2/?scroll=-1",
        "/pokedex/2/?scroll=10000001",
        "/pokedex/?focus=252",
        "/pokedex/?scroll=١",
        "/pokedex/?q=a&q=b",
        "/pokedex/2/?goal=a&goal=b",
        "/pokedex/2/?child=foreign",
        "/pokedex/2/?return=%2Fpokedex%2F3%2F",
        "/pokedex/2/?return=%2Fpokedex%2F%3Freturn%3D%2Fpokedex%2F",
        "/pokedex/2/?return=%2Fcards%2F",
        "/pokedex/2/?return=https%3A%2F%2Fexample.com%2F",
        "/pokedex/2/#secret",
        "/pokedex/?q=%0A",
        "/pokedex/?q=%00",
        "/pokedex/2/?goal=%7F",
    ],
)
def test_review_species_card_returns_reject_unsafe_nested_or_malformed_context(cx, destination):
    before = dump(cx)
    assert cx["a"].get(find(cx)["url"], {"return": destination}).status_code == 400
    assert dump(cx) == before
