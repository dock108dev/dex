"""Local search on disposable engineering accounts, without provider I/O."""

import json

import pytest
from test_b1 import env as env
from test_b2 import apply
from test_b2 import b2 as b2
from test_migration import snapshot as snapshot

from pokemon_hunter.beta import (
    card_groups,
    collection,
    discovery_catalog,
    effective_collection,
    image_bindings,
    store,
)


@pytest.fixture
def visual(b2, monkeypatch):
    monkeypatch.setattr(image_bindings, "enabled", lambda: True)
    names = [("Hypno", "23", 97), ("Alakazam", "1", 65), ("Gengar", "5", 94)]
    for printing, (name, number, dex) in zip(b2["catalog"], names, strict=True):
        collection.execute("UPDATE catalog_sets SET name='Base Set 2' WHERE id=%s", [printing["set_id"]])
        collection.execute(
            "UPDATE printings SET collector_number=%s,language='en',attributes=%s WHERE id=%s",
            [
                number,
                json.dumps(dict(name=name, pokemon_dex=dex, dex_eligible=True, supertype="Pokémon")),
                printing["id"],
            ],
        )
    base = store.rows("SELECT * FROM catalog_sets")[0]
    base.update(id="shop04-base-set", name="Base Set")
    keys = list(base)
    collection.execute(
        "INSERT INTO catalog_sets (" + ",".join(keys) + ") VALUES (" + ",".join(["%s"] * len(keys)) + ")",
        [base[key] for key in keys],
    )
    first = store.rows("SELECT * FROM printings WHERE id=%s", [b2["catalog"][1]["id"]])[0]
    for key, set_id, edition, finish in (
        ("shop04-base-alakazam", base["id"], "standard", "holo"),
        ("shop04-base2-variant", b2["catalog"][1]["set_id"], "first", "holo"),
    ):
        row = dict(first, id=key, set_id=set_id, edition=edition, finish=finish)
        keys = list(row)
        collection.execute(
            "INSERT INTO printings (" + ",".join(keys) + ") VALUES (" + ",".join(["%s"] * len(keys)) + ")",
            [row[field] for field in keys],
        )
    return b2


@pytest.mark.parametrize("name,dex", [("Hypno", 97), ("Alakazam", 65), ("Gengar", 94)])
def test_broad_species_art_then_explicit_card_references(visual, name, dex):
    result = discovery_catalog.search(visual["actor"], {"q": name})
    assert result["mode"] == "species"
    assert result["results"][0]["dex"] == dex
    assert result["results"][0]["species_artwork"]["role"] == "species_artwork"
    cards = discovery_catalog.search(visual["actor"], {"q": name, "species": str(dex)})
    assert cards["mode"] == "cards" and cards["results"]
    assert all(row["selected_child"] is None for row in cards["results"])
    assert all(row["reference_image"]["role"] == "card_group_reference" for row in cards["results"])


def test_base_and_base_two_are_independent_with_multiple_printing_choices(visual):
    who = visual["actor"]
    one = discovery_catalog.search(who, {"q": "Alakazam base"})
    two = discovery_catalog.search(who, {"q": "Alakazam base 2"})
    assert one["mode"] == two["mode"] == "cards"
    assert {row["set_name"] for row in one["results"]} == {"Base Set"}
    assert {row["set_name"] for row in two["results"]} == {"Base Set 2"}
    assert two["results"][0]["variant_count"] == 2
    chosen = discovery_catalog.search(who, {"q": "Alakazam", "group": two["results"][0]["id"]})
    assert len(chosen["variants"]) == 2
    assert chosen["results"][0]["selected_child"] is None
    assert {
        row["set_name"]
        for row in discovery_catalog.search(who, {"q": "Alakazam base 2", "set_id": "Base Set"})["results"]
    } == {"Base Set"}
    numbered = discovery_catalog.search(who, {"q": "Base 2 #1"})
    assert {row["name"] for row in numbered["results"]} == {"Alakazam"}
    fraction = discovery_catalog.search(who, {"q": "Base 2 1/130"})
    assert {row["name"] for row in fraction["results"]} == {"Alakazam"}
    assert all(row["selected_child"] is None for row in fraction["results"])
    assert "number before /" in fraction["number_note"]


def test_contextual_entry_merged_and_explicit_child_preserved(visual):
    group = next(
        row
        for row in card_groups.project(visual["actor"])["groups"]
        if row["name"] == "Alakazam" and row["set_name"] == "Base Set 2"
    )
    child = group["_children"][0]["id"]
    response = visual["a"].get(
        "/shopping/",
        {
            "group": group["id"],
            "child": child,
            "return": "/card-library/?set=" + group["set_id"] + "&scroll=250&q=Alakazam",
        },
    )
    assert response.status_code == 200
    assert b'id="discovery-query"' in response.content and b'id="lot-form"' not in response.content
    result = (
        visual["a"].get("/api/shopping/discovery/catalog/", {"group": group["id"], "child": child}).json()
    )
    assert result["context"]["child"] == child and result["results"][0]["selected_child"] == child
    assert visual["a"].get("/shopping/", {"group": group["id"], "child": "wrong"}).status_code == 404


def test_current_missing_and_frozen_goal_delegate_existing_policy_without_mutation(visual):
    who = visual["actor"]
    before = collection.export_data(who)
    current = effective_collection.project(who)
    result = discovery_catalog.search(who, {"intent": "missing", "missing_basis": "species"})
    assert all(
        1 <= row["pokemon_dex"] <= 151 and not current["species"][str(row["pokemon_dex"])]["present"]
        for row in result["results"]
    )
    assert discovery_catalog.search(who, {"q": "Alakazam"})["results"]
    assert collection.export_data(who) == before
    goal = apply(
        visual,
        "goal",
        dict(
            name="Frozen synthetic",
            goal_kind="custom",
            printing_ids=[row["id"] for row in collection.catalog(who)],
        ),
    )["changes"][0]["after"]
    raw = {"goal": goal["id"], "version": goal["version"], "intent": "missing"}
    result = discovery_catalog.search(who, raw)
    assert result["context"]["goal_version"] == goal["version"]
    assert visual["a"].get("/shopping/", dict(raw, version="0" * 64)).status_code == 409
    assert visual["b"].get("/shopping/", raw).status_code == 404


def test_missing_unindexed_species_and_image_failure_remain_visible(visual, monkeypatch):
    missing = next(
        number
        for number in range(1, 152)
        if not effective_collection.project(visual["actor"])["species"][str(number)]["present"]
        and number not in {65, 94, 97}
    )
    from pokemon_hunter.beta import canonical_species

    result = discovery_catalog.search(
        visual["actor"], {"q": canonical_species.registry()[missing]["name"], "intent": "missing"}
    )
    assert result["results"][0]["matching_cards"] == 0
    monkeypatch.setattr(image_bindings, "enabled", lambda: False)
    assert discovery_catalog.search(visual["actor"], {"q": "Gengar"})["results"][0]["species_artwork"] is None
    assert discovery_catalog.search(visual["actor"], {"q": "not a catalog name"})["results"] == []


def test_safe_return_and_authority_filters_are_bounded(visual):
    from pokemon_hunter.beta import navigation

    target = "/shopping/?q=Alakazam&set_id=Base+Set+2&intent=deals&scope=all&result_filter=unpriced&focus=offer-abc123&scroll=340"
    assert navigation.authorize_destination(visual["actor"], target) == target
    for bad in (
        "/shopping/?item_title=Restricted",
        "/shopping/?focus=javascript:bad",
        "/shopping/?scroll=-1",
        "/shopping/?run_id=wrong",
        "https://example.test/shopping/",
    ):
        with pytest.raises(ValueError):
            navigation.authorize_destination(visual["actor"], bad)
    assert visual["a"].get("/api/shopping/discovery/catalog/", {"generation": "999"}).status_code == 409
    assert visual["a"].get("/api/shopping/discovery/catalog/", {"account_id": "other"}).status_code == 400
