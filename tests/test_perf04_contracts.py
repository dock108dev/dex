"""Bounded frontend gap corrections retain server ownership and goal authority."""

from test_account_reads import prepared as prepared
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_effective_collection import cx as cx
from test_migration import snapshot as snapshot
from test_sealed_catalog import e1 as e1

from pokemon_hunter.beta import species_projection


def test_scope_group_page_matches_policy(prepared):
    client = prepared["a"]
    reference = species_projection.project(prepared["actor"], {"finish": "holo"})
    species = client.get("/api/v2/pokedex-species/?owned=owned").json()["species"]
    for row in species:
        response = client.get(f"/api/v2/species/{row['dex']}/owned-groups/?finish=holo&page_size=1")
        assert response.status_code == 200, response.content
        result = response.json()
        assert len(result["groups"]) <= 1
        for key, value in result["scope_groups"].items():
            assert value == reference["scope_groups"][key]
        assert (
            client.get(f"/api/v2/species/{row['dex']}/owned-groups/?account_revision=stale").status_code
            == 409
        )


def test_goal_options_bounded_and_independently_authorized(prepared):
    response = prepared["a"].get("/api/v2/goal-options/?page_size=1")
    assert response.status_code == 200
    assert len(response.json()["goals"]) <= 1
    assert prepared["client"]().get("/api/v2/goal-options/").status_code == 403
    assert prepared["a"].get("/api/v2/goal-options/?page_size=101").status_code == 400


def test_shell_does_not_build_old_group_projection(prepared):
    from unittest.mock import patch

    key = prepared["a"].get("/api/v2/my-card-groups/").json()["groups"][0]["id"]
    with patch("pokemon_hunter.beta.card_groups.detail", side_effect=AssertionError("V1 projection")):
        assert prepared["a"].get("/card-groups/" + key + "/").status_code == 200
    assert prepared["client"]().get("/card-library/").status_code == 200
    assert prepared["client"]().get("/pokedex/").status_code == 200


def test_candidate_resolution_is_bounded_and_preserves_server_ownership(prepared):
    client = prepared["a"]
    page = client.get("/api/v2/catalog/?page_size=2").json()
    ids = ",".join(p["id"] for p in page["printings"])
    result = client.get("/api/v2/selection-groups/", {"ids": ids})
    assert result.status_code == 200
    assert len(result.json()["groups"]) <= 2
    assert all("present" in g or g.get("oversized") for g in result.json()["groups"])
    assert prepared["client"]().get("/api/v2/selection-groups/", {"ids": ids}).status_code == 403
    assert (
        client.get("/api/v2/selection-groups/", {"ids": ",".join(str(i) for i in range(101))}).status_code
        == 400
    )
    assert client.get("/api/v2/binders/?page_size=1").status_code == 200


def test_unprepared_navigation_is_explicit_and_readonly(cx):
    from test_card_groups import find
    from test_cx03_review import dump

    group = find(cx, "a")
    before = dump(cx)
    response = cx["a"].get("/api/navigation/home/", {"destination": group["url"]})
    assert response.status_code == 503
    assert response.json()["code"] == "read_state_unavailable"
    assert response["Cache-Control"] == "private, no-store"
    assert dump(cx) == before


def test_goal_workspace_and_preserved_legacy_edit(prepared):
    import json
    import uuid
    from unittest.mock import patch

    from pokemon_hunter.beta import account_read_build as accounts
    from pokemon_hunter.beta import collection, store

    actor = prepared["actor"]
    printing = prepared["by_legacy"]["a"]["id"]
    op = collection.preview(
        actor,
        "goal",
        {
            "name": "Retained checklist",
            "goal_kind": "custom",
            "printing_ids": [printing],
            "policy": "catalog",
        },
        str(uuid.uuid4()),
    )
    collection.confirm(actor, op["id"])
    goal = store.rows("SELECT * FROM collection_goals WHERE user_id=%s", [actor.user_id])[0]
    with (
        patch.object(collection, "catalog", side_effect=AssertionError("full catalog")),
        patch.object(collection, "copies", side_effect=AssertionError("all copies")),
    ):
        response = prepared["a"].get("/api/v2/goals/?page_size=1")
        assert response.status_code == 200, response.content
        row = response.json()["goals"][0]
        assert row["name"] == "Retained checklist"
        assert "items" not in row["header"]
        items = prepared["a"].get(row["items_url"]).json()["items"]
        assert len(items) == 1
        assert items[0]["printing_ids"] == [printing]
    op = collection.preview(
        actor,
        "goal_edit",
        {
            "id": goal["id"],
            "revision": goal["revision"],
            "name": "Renamed without widening",
            "goal_kind": "custom",
            "preserve_membership": True,
        },
        str(uuid.uuid4()),
    )
    collection.confirm(actor, op["id"])
    after = store.rows("SELECT * FROM collection_goals WHERE id=%s", [goal["id"]])[0]
    assert json.loads(after["definition"]) == json.loads(goal["definition"])
    assert after["version"] == goal["version"]
    assert after["name"] == "Renamed without widening"
    assert prepared["b"].get(f"/api/v2/goals/{goal['id']}/").status_code in {404, 503}
    accounts.prepare(prepared["member"])
    assert prepared["b"].get(f"/api/v2/goals/{goal['id']}/items/").status_code == 404
    assert prepared["a"].get("/api/v2/goals/?account_revision=stale").status_code == 409


def test_artwork_batch_authorization_and_literal_policy(prepared):
    from unittest.mock import patch

    from test_image_mappings import catalog_card, grouped, reference

    from pokemon_hunter.beta import collection, image_mappings

    card = catalog_card()
    group = grouped([card])
    old = reference(group, [card])
    new = image_mappings.indexed_group_reference(group, pokemon_game_ids={card["game_id"]})
    for field in ["image_url", "source_id", "role", "precision", "bound_identity", "width", "height"]:
        assert new[field] == old[field]
    assert image_mappings.indexed_group_reference(group, pokemon_game_ids=set())["image_url"] is None
    key = prepared["a"].get("/api/v2/card-groups/").json()["groups"][0]["id"]
    with patch.object(collection, "catalog", side_effect=AssertionError("full catalog")):
        response = prepared["a"].get("/api/v2/group-artwork/", {"ids": key})
        assert response.status_code == 200, response.content
        assert len(response.content) < 128 * 1024
        assert prepared["client"]().get("/api/v2/group-artwork/", {"ids": key}).status_code == 403
        assert (
            prepared["a"].get("/api/v2/group-artwork/", {"ids": key, "account_revision": "stale"}).status_code
            == 409
        )
        assert (
            prepared["a"]
            .get("/api/v2/group-artwork/", {"ids": ",".join(str(i) for i in range(101))})
            .status_code
            == 400
        )
        public = prepared["client"]().get("/api/v2/public/group-artwork/", {"ids": key})
        assert public.status_code == 200
        assert all(v["role"] == "card_group_reference" for v in public.json()["artwork"].values())
        assert prepared["client"]().get("/api/v2/public/species-artwork/?ids=1,2").status_code == 200
        assert prepared["client"]().get("/api/v2/public/species-artwork/?ids=252").status_code == 400


def test_expected_account_header_is_consistency_guard_not_authority(prepared):
    client = prepared["a"]
    assert (
        client.get("/api/v2/card-groups/", HTTP_X_DEX_READ_ACCOUNT=prepared["actor"].user_id).status_code
        == 200
    )
    assert (
        client.get("/api/v2/card-groups/", HTTP_X_DEX_READ_ACCOUNT=prepared["member"].user_id).status_code
        == 403
    )
    assert (
        prepared["client"]()
        .get("/api/v2/card-groups/", HTTP_X_DEX_READ_ACCOUNT=prepared["actor"].user_id)
        .status_code
        == 403
    )


def test_large_entry_choice_expands_explicitly(prepared):
    from pokemon_hunter.beta import account_read_build, catalog_read_build, collection

    key = prepared["by_legacy"]["a"]["set_id"]
    collection.execute("UPDATE catalog_sets SET name=%s WHERE id=%s", ["Long set " + ("x" * 5000), key])
    catalog_read_build.activate(catalog_read_build.prepare())
    account_read_build.prepare(prepared["actor"])
    response = prepared["a"].get("/api/v2/entry-options/?field=set")
    assert response.status_code == 200 and len(response.content) < 32 * 1024
    row = next(r for r in response.json()["options"] if r["id"] == key)
    assert row["oversized"] is True
    full = prepared["a"].get(row["url"])
    assert full.status_code == 200 and full.json()["record"]["name"] == "Long set " + ("x" * 5000)
    assert prepared["client"]().get(row["url"]).status_code == 403


def test_previous_goal_representation_requires_explicit_preparation(prepared):
    import uuid

    from pokemon_hunter.beta import account_read_build as builds
    from pokemon_hunter.beta import collection, store

    op = collection.preview(
        prepared["actor"],
        "goal",
        {
            "name": "Retained",
            "goal_kind": "custom",
            "printing_ids": [prepared["by_legacy"]["a"]["id"]],
            "policy": "catalog",
        },
        str(uuid.uuid4()),
    )
    collection.confirm(prepared["actor"], op["id"])
    row = store.rows("SELECT * FROM ar_goals WHERE user_id=%s", [prepared["actor"].user_id])[0]
    value = builds.decode(row)
    value.pop("header")
    builds.put("ar_goals", prepared["actor"], dict(id=row["id"], version=row["version"]), value)
    result = prepared["a"].get("/api/v2/goals/")
    assert result.status_code == 503 and result.json()["code"] == "read_state_unavailable"
    builds.prepare(prepared["actor"])
    assert prepared["a"].get("/api/v2/goals/").status_code == 200
