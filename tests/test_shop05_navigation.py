"""SHOP-05 controlled engineering contracts. No customer state or external requests."""

import json
import re
from urllib.parse import urlencode

import pytest
from test_b1 import env as env
from test_b2 import apply
from test_b2 import b2 as b2
from test_cx03_review import dump
from test_discovery_catalog import visual as visual
from test_migration import snapshot as snapshot

from pokemon_hunter.beta import card_groups, collection, discovery, discovery_catalog
from pokemon_hunter.beta.discovery_transport import Transport


def url(path, **fields):
    return path + "?" + urlencode(fields)


def payload(response, name):
    assert response.status_code == 200, response.content[:300]
    return json.loads(
        re.search(
            r'<script id="' + name + r'" type="application/json">(.*?)</script>', response.content.decode()
        ).group(1)
    )


@pytest.fixture
def no_acquisition(visual, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Navigation/local inspection cannot acquire provider data")

    monkeypatch.setattr(discovery, "start", forbidden)
    monkeypatch.setattr(Transport, "request", forbidden)
    return visual


@pytest.mark.parametrize("dex,name", [(97, "Hypno"), (94, "Gengar"), (2, "Ivysaur")])
def test_species_prefill_and_library_are_read_only(no_acquisition, dex, name):
    state = no_acquisition
    before = dump(state)
    generation = collection.generation(state["actor"])
    species = url(
        f"/pokedex/{dex}/",
        generation=generation,
        scroll=91,
        **{"return": "/pokedex/?owned=missing&focus=" + str(dex)},
    )
    assert state["a"].get(species).status_code == 200
    library = url("/card-library/", species=dex, generation=generation, **{"return": species})
    assert state["a"].get(library).status_code == 200
    catalog = state["a"].get("/api/card-groups/", {"species": dex, "generation": generation})
    assert catalog.status_code == 200
    shopping = state["a"].get(
        "/shopping/",
        {"species": dex, "generation": generation, "product_type": "mixed_lots", "return": species},
    )
    assert payload(shopping, "discovery-initial")["q"] == name
    assert payload(shopping, "discovery-initial")["product_type"] == "mixed_lots"
    assert dump(state) == before
    assert not any(key.startswith("shopping_wants_") for key in state["a"].session.keys())


@pytest.mark.parametrize("set_name", ["Base Set", "Base Set 2"])
def test_single_inherited_set_and_authoritative_card_identity(no_acquisition, set_name):
    state = no_acquisition
    row = next(
        row
        for row in card_groups.project(state["actor"])["groups"]
        if row["set_name"] == set_name and row["name"] == "Alakazam"
    )
    species = url("/pokedex/65/", **{"return": url("/pokedex/", set=row["set_id"], focus=65)})
    response = state["a"].get("/shopping/", {"species": "65", "return": species})
    assert payload(response, "discovery-initial")["set_id"] == set_name
    library = url("/card-library/", species=65, set=row["set_id"], **{"return": species})
    detail = url(f"/card-groups/{row['id']}/", **{"return": library})
    assert state["a"].get(detail).status_code == 200
    shopping = state["a"].get("/shopping/", {"group": row["id"], "return": detail})
    initial = payload(shopping, "discovery-initial")
    assert initial["set_id"] == set_name and initial["q"] == "Alakazam 1"
    assert "child" not in initial
    assert "shopping-scope-note" not in shopping.content.decode()


@pytest.mark.parametrize(
    "scope",
    [
        {"set": '["Base Set","Base Set 2"]'},
        {"set": "Unavailable"},
        {"set": "Base Set", "finish": "holo", "year": "1999"},
    ],
)
def test_unrepresentable_filters_explained_and_original_return_preserved(no_acquisition, scope):
    state = no_acquisition
    back = url("/pokedex/", **scope, owned="missing", focus=97, scroll=312)
    species = url("/pokedex/97/", **{"return": back})
    response = state["a"].get("/shopping/", {"species": "97", "return": species})
    initial = payload(response, "discovery-initial")
    assert initial["return"] == species
    assert b'id="shopping-scope-note"' in response.content
    assert b"Back retains your original collection filters" in response.content
    if scope.get("set") == "Base Set":
        assert initial["set_id"] == "Base Set"
    else:
        assert not initial.get("set_id")


def test_card_choice_replaces_incompatible_original_set_visibly(no_acquisition):
    state = no_acquisition
    row = next(
        row
        for row in card_groups.project(state["actor"])["groups"]
        if row["name"] == "Alakazam" and row["set_name"] == "Base Set 2"
    )
    back = url("/card-library/", set="Base Set")
    response = state["a"].get("/shopping/", {"group": row["id"], "return": back})
    assert payload(response, "discovery-initial")["set_id"] == "Base Set 2"
    assert b"replaces the original collection set" in response.content


@pytest.mark.parametrize("exact", [False, True])
def test_card_details_shopping_return_chain_preserves_target_and_page_choices(no_acquisition, exact):
    state = no_acquisition
    who = state["actor"]
    row = discovery_catalog.search(who, {"q": "Alakazam base 2"})["results"][0]
    variant = card_groups.detail(who, row["id"])["variants"][0]["id"]
    before = dump(state)
    species = url("/pokedex/65/", **{"return": "/pokedex/?owned=missing&scroll=100&focus=65"})
    library = url("/card-library/", species="65", set="Base Set 2", **{"return": species})
    origin = url(f"/card-groups/{row['id']}/", **{"return": library})
    fields = dict(
        group=row["id"],
        generation=collection.generation(who),
        q="Alakazam 1",
        set_id="Base Set 2",
        product_type="mixed_lots",
        sort="best_match",
        budget="10",
        result_filter="unpriced",
        scroll="305",
        focus="catalog-details-" + row["id"],
        run_id="11111111-1111-4111-8111-111111111111",
        **{"return": origin},
    )
    if exact:
        fields["child"] = variant
    shopping = url("/shopping/", **fields)
    details = url(
        f"/card-groups/{row['id']}/",
        generation=collection.generation(who),
        **({"child": variant} if exact else {}),
        **{"return": shopping},
    )
    from pokemon_hunter.beta import navigation

    assert navigation.authorize_destination(who, details) == details
    assert state["a"].get(details).status_code == 200
    response = state["a"].get(shopping)
    initial = payload(response, "discovery-initial")
    assert all(str(initial[key]) == str(value) for key, value in fields.items())
    local = discovery_catalog.search(who, {"group": row["id"], **({"child": variant} if exact else {})})
    assert local["context"]["child"] == (variant if exact else None)
    assert local["results"][0]["selected_child"] == (variant if exact else None)
    assert dump(state) == before


def test_goal_version_generation_and_other_account_rechecked_through_returns(no_acquisition):
    state = no_acquisition
    goal = apply(
        state,
        "goal",
        dict(
            name="Frozen engineering target",
            goal_kind="custom",
            printing_ids=[row["id"] for row in collection.catalog(state["actor"])],
        ),
    )["changes"][0]["after"]
    generation = collection.generation(state["actor"])
    fields = dict(goal=goal["id"], version=goal["version"], generation=generation)
    species = url("/pokedex/97/", **fields)
    library = url("/card-library/", species=97, **fields, **{"return": species})
    row = discovery_catalog.search(state["actor"], {"q": "Hypno", "species": "97"})["results"][0]
    details = url(f"/card-groups/{row['id']}/", **{"return": library})
    before = dump(state)
    for destination in (species, library, details):
        assert state["a"].get(destination).status_code == 200
        assert state["b"].get(destination).status_code in {400, 404}
    shopping = state["a"].get("/shopping/", dict(fields, group=row["id"], **{"return": details}))
    context = payload(shopping, "discovery-context")
    assert context["goal_version"] == goal["version"] and "Frozen" in context["goal_policy"]
    assert payload(shopping, "discovery-initial")["intent"] == "missing"
    for path in ("/pokedex/97/", "/card-library/"):
        assert state["a"].get(path, dict(fields, generation=generation + 1)).status_code == 409
        assert state["a"].get(path, dict(fields, version="0" * 64)).status_code == 409
    stale = url("/card-library/", **dict(fields, version="0" * 64))
    assert state["a"].get(f"/card-groups/{row['id']}/", {"return": stale}).status_code == 409
    assert dump(state) == before
    state["a"].logout()
    assert state["a"].get(details).status_code == 302


@pytest.mark.parametrize(
    "bad",
    [
        "https://evil.test/",
        "//evil.test/shopping/",
        "/shopping/?q=a&q=b",
        "/shopping/?price=1",
        "/shopping/?title=secret",
        "/shopping/?focus=unsafe",
        "/shopping/?run_id=wrong",
        "/shopping/?q=%00",
        "/settings/",
    ],
)
def test_card_details_rejects_unchecked_return(no_acquisition, bad):
    state = no_acquisition
    row = discovery_catalog.search(state["actor"], {"q": "Hypno", "species": "97"})["results"][0]
    assert state["a"].get(f"/card-groups/{row['id']}/", {"return": bad}).status_code == 400
