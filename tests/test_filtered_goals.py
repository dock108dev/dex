"""Filtered goals count only scoped copies, retain membership and survive reviewed edits/imports."""

import json

import pytest
from test_b1 import env as env
from test_b2 import apply, post, preview
from test_b2 import b2 as b2
from test_migration import snapshot as snapshot

from pokemon_hunter.beta import collection as service
from pokemon_hunter.inventory import stable_id


def request(b2, **filters):
    return {
        "name": "Filtered collection",
        "goal_kind": "filtered",
        "policy": "catalog",
        "filters": {
            "game_id": stable_id("game", "pokemon"),
            "set_ids": [b2["catalog"][0]["set_id"]],
            "card_type": "all",
            "rarities": [],
            "pokemon_dex_min": 1,
            "pokemon_dex_max": 151,
            "completion": "species",
            **filters,
        },
    }


def test_species_filters_preserve_251_and_no_inventory_changes(b2):
    before = service.export_data(b2["actor"])
    apply(b2, "goal", request(b2))
    goal = service.goals(b2["actor"])[0]
    assert goal["total"] == 151 and goal["satisfied"] == 1
    assert goal["unavailable"] == 150 and goal["missing"] == 0
    assert goal["progress"][0]["status"] == "owned"
    assert goal["progress"][1]["status"] == "unavailable"  # Dark Pokémon never satisfy species.
    assert service.copies(b2["actor"]) == before["copies"]
    assert service.export_data(b2["actor"])["vintage_251"] == before["vintage_251"]
    assert all(i["pokemon_dex"] <= 151 for i in goal["definition"]["items"])


def test_selected_set_only_counts_its_copies_and_freezes_membership(b2):
    game = stable_id("game", "pokemon")
    service.execute(
        "INSERT INTO catalog_sets VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        ["other-set", game, "Other set", "en", None, "[]", "{}", "synthetic", "test"],
    )
    # Same species available in another set, but its existing copy is in the original set.
    service.execute(
        "INSERT INTO printings VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        [
            "other-printing",
            "other-set",
            "1",
            "en",
            None,
            None,
            None,
            "[]",
            json.dumps({"name": "Normal", "pokemon_dex": 1, "dex_eligible": True}),
            "{}",
        ],
    )
    apply(b2, "goal", request(b2, set_ids=["other-set"], pokemon_dex_max=1))
    g = service.goals(b2["actor"])[0]
    assert g["satisfied"] == 0 and g["missing"] == 1
    definition = g["definition"]
    apply(b2, "add", {"printing_id": "other-printing", "duplicate_policy": "allow"})
    assert service.goals(b2["actor"])[0]["satisfied"] == 1
    service.execute(
        "UPDATE printings SET attributes=%s WHERE id=%s",
        [json.dumps({"name": "Changed", "pokemon_dex": 200, "dex_eligible": True}), "other-printing"],
    )
    assert service.goals(b2["actor"])[0]["definition"] == definition
    assert service.goals(b2["actor"])[0]["satisfied"] == 1


def test_printing_rarity_type_range_and_resolved_completion(b2):
    for index, p in enumerate(b2["catalog"]):
        attrs = {**p["attributes"], "supertype": "Pokémon", "rarity": "Rare" if index == 0 else "Common"}
        service.execute("UPDATE printings SET attributes=%s WHERE id=%s", [json.dumps(attrs), p["id"]])
    req = request(b2, completion="printings", card_type="Pokémon", rarities=["Rare"])
    apply(b2, "goal", req)
    g = service.goals(b2["actor"])[0]
    assert g["total"] == 1 and g["satisfied"] == 1
    apply(b2, "goal", {**req, "name": "Exact", "policy": "exact"})
    assert next(g for g in service.goals(b2["actor"]) if g["name"] == "Exact")["satisfied"] == 0


@pytest.mark.parametrize(
    "fields",
    [
        {"set_ids": ["foreign"]},
        {"set_ids": ["duplicate", "duplicate"]},
        {"pokemon_dex_min": 152, "pokemon_dex_max": 151},
        {"pokemon_dex_max": 252},
        {"pokemon_dex_min": True},
        {"rarities": ["invented"]},
        {"card_type": "invented"},
        {"completion": "invented"},
        {"unknown": "field"},
    ],
)
def test_invalid_filters_block_without_writes(b2, fields):
    before = service.copies(b2["actor"])
    assert preview(b2, "goal", request(b2, **fields)).status_code == 400
    assert not service.goals(b2["actor"]) and service.copies(b2["actor"]) == before


def test_edit_undo_stale_and_cross_account(b2):
    apply(b2, "goal", request(b2))
    g = service.goals(b2["actor"])[0]
    edit = {**request(b2, pokemon_dex_max=251), "id": g["id"], "revision": g["revision"]}
    op = apply(b2, "goal_edit", edit)
    assert service.goals(b2["actor"])[0]["total"] == 251
    assert preview(b2, "goal_edit", edit).status_code == 409
    assert preview(b2, "goal_edit", edit, b2["b"]).status_code == 404
    assert b2["b"].get(f"/api/goals/{g['id']}/").status_code == 404
    assert post(b2["a"], f"/api/operations/{op['id']}/undo/", {}).status_code == 200
    restored = service.goals(b2["actor"])[0]
    assert restored["definition"] == g["definition"] and restored["version"] == g["version"]


def test_filtered_export_import_and_membership_validation(b2):
    apply(b2, "goal", request(b2, pokemon_dex_max=251))
    exported = service.export_data(b2["actor"])
    apply(
        b2, "import", {"text": json.dumps(exported), "format": "json", "duplicate_policy": "allow"}, b2["b"]
    )
    original, imported = service.goals(b2["actor"])[0], service.goals(b2["member"])[0]
    assert imported["definition"] == original["definition"]
    assert imported["satisfied"] == original["satisfied"] and imported["id"] != original["id"]
    from pokemon_hunter.migration import digest, encode

    tampered = json.loads(json.dumps(exported))
    goal = tampered["goals"][0]
    goal["definition"]["items"][0]["printing_ids"] = goal["definition"]["items"][151]["printing_ids"]
    goal["version"] = digest(encode(goal["definition"]).encode())
    invalid = preview(
        b2, "import", {"text": json.dumps(tampered), "format": "json", "duplicate_policy": "allow"}
    )
    assert invalid.status_code == 400


def test_new_species_labels_are_canonical_and_historical_labels_import_unchanged(b2):
    from pokemon_hunter.migration import digest, encode

    apply(b2, "goal", request(b2))
    original = service.goals(b2["actor"])[0]
    assert original["definition"]["items"][0]["label"] == "#001 Bulbasaur"
    assert original["definition"]["items"][1]["label"] == "#002 Ivysaur"
    exported = service.export_data(b2["actor"])
    # A retained pre-enforcement definition has catalog-derived or placeholder labels.
    historical = exported["goals"][0]
    historical["definition"]["items"][0]["label"] = "#001 Normal"
    historical["definition"]["items"][1]["label"] = "#002 Species 002"
    historical["version"] = digest(encode(historical["definition"]).encode())
    apply(
        b2, "import", {"text": json.dumps(exported), "format": "json", "duplicate_policy": "allow"}, b2["b"]
    )
    imported = service.goals(b2["member"])[0]
    assert imported["definition"] == historical["definition"]
    assert imported["version"] == historical["version"]
    assert service.goals(b2["actor"])[0]["definition"] == original["definition"]
