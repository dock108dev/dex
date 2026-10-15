"""read-only targets, request authority and bounded draft re-resolution."""

import json

import pytest
from test_b1 import env as env
from test_b2 import apply
from test_b2 import b2 as b2
from test_lot_calculator import post
from test_lot_calculator import workspace as workspace
from test_migration import snapshot as snapshot
from test_shopping import shop as shop

from pokemon_hunter.beta import card_groups, collection, shopping_context


def target(workspace):
    return card_groups.list_groups(workspace["actor"], {"scope": "catalog"})["groups"][0]


def test_null_group_never_prices_or_chooses_child(workspace, monkeypatch):
    group = target(workspace)
    before = collection.export_data(workspace["actor"])
    from pokemon_hunter.beta import lot_calculator

    monkeypatch.setattr(
        lot_calculator,
        "priced_cards",
        lambda *args: pytest.fail("Null-child navigation cannot obtain prices"),
    )
    response = workspace["a"].get("/api/shopping/lot-catalog/", {"group": group["id"]})
    assert response.status_code == 200
    data = response.json()
    assert data["context"]["child"] is None
    assert data["context"]["needs_selection"]
    assert data["cards"] and all(not row["cells"] for row in data["cards"])
    assert collection.export_data(workspace["actor"]) == before
    assert not workspace["a"].session.get("shopping_wants_" + workspace["actor"].user_id)


def test_explicit_printing_revalidates_group_and_admitted_catalog(workspace):
    group = target(workspace)
    detail = card_groups.detail(workspace["actor"], group["id"])
    child = detail["variants"][0]["id"]
    response = workspace["a"].get("/api/shopping/lot-catalog/", {"group": group["id"], "child": child})
    assert response.status_code == 200
    assert [row["id"] for row in response.json()["cards"]] == [child]
    assert response.json()["context"]["child"] == child
    assert workspace["a"].get("/shopping/", {"group": group["id"], "child": "missing"}).status_code == 404
    assert (
        workspace["a"]
        .get("/api/shopping/lot-catalog/", {"group": group["id"], "printing": "missing"})
        .status_code
        == 404
    )


def test_restore_is_read_only_bounded_and_preserves_missing_identity_inputs(workspace):
    ids = [row["id"] for row in workspace["catalog"]]
    before = collection.export_data(workspace["actor"])
    response = workspace["a"].get(
        "/api/shopping/lot-catalog/",
        {"restore": [*ids, "absent"], "generation": collection.generation(workspace["actor"])},
    )
    assert response.status_code == 200
    assert {row["id"] for row in response.json()["cards"]} == set(ids)
    assert response.json()["missing_ids"] == ["absent"]
    assert response.json()["authority"]["account_id"] == workspace["actor"].user_id
    for bad in (
        {"restore": [ids[0], ids[0]]},
        {"restore": ids, "account_id": "other"},
        {"restore": ["a"] * 201},
    ):
        assert workspace["a"].get("/api/shopping/lot-catalog/", bad).status_code == 400
    assert (
        workspace["a"].get("/api/shopping/lot-catalog/", {"restore": ids, "generation": "999"}).status_code
        == 409
    )
    assert collection.export_data(workspace["actor"]) == before


def test_context_goal_version_current_status_and_no_default_goal(workspace):
    goal = apply(
        workspace,
        "goal",
        dict(
            name="Exact printings",
            goal_kind="custom",
            printing_ids=[row["id"] for row in workspace["catalog"]],
        ),
    )["changes"][0]["after"]
    context = shopping_context.resolve(workspace["actor"], {"species": "2"})
    assert context["kind"] == "species"
    assert context["goal_kind"] is None and context["query"] == {"species": "2"}
    exact = shopping_context.resolve(workspace["actor"], {"goal": goal["id"], "version": goal["version"]})
    assert exact["goal_kind"] == "custom"
    assert exact["goal_version"] == goal["version"]
    assert workspace["a"].get("/shopping/", {"goal": goal["id"]}).status_code == 400
    assert workspace["a"].get("/shopping/", {"goal": goal["id"], "version": "0" * 64}).status_code == 409
    assert (
        workspace["b"].get("/shopping/", {"goal": goal["id"], "version": goal["version"]}).status_code == 404
    )


def test_stale_authority_stops_lock_write_before_effect(workspace):
    page = workspace["a"].get("/shopping/")
    assert page.status_code == 200
    before = dict(workspace["a"].session)
    response = workspace["a"].post(
        "/api/shopping/wants/",
        json.dumps({"wants": [{"printing_id": workspace["catalog"][0]["id"], "quantity": 4}]}),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=workspace["a"].cookies["dex_b1_csrf"].value,
        HTTP_X_DEX_SHOPPING_BINDING="foreign",
    )
    assert response.status_code == 403
    assert dict(workspace["a"].session) == before
    response = post(workspace, "/api/shopping/wants/", dict(wants=[]))
    assert response.status_code == 200
    assert response.json()["authority"]["binding"]


def test_species_choices_use_authoritative_nested_catalog_metadata(workspace):
    p = workspace["catalog"][0]
    attributes = dict(p["attributes"], pokemon_dex=2, supertype="Pokémon")
    collection.execute("UPDATE printings SET attributes=%s WHERE id=%s", [json.dumps(attributes), p["id"]])
    response = workspace["a"].get("/api/shopping/lot-catalog/", {"species": "2"})
    assert response.status_code == 200
    assert p["id"] in {row["id"] for row in response.json()["cards"]}
    assert all(not row["cells"] for row in response.json()["cards"])
