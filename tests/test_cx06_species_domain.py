"""thin read projection qualifies canonical scope without inventing card truth."""

from unittest.mock import patch

import pytest
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_collection_goals import create
from test_effective_collection import cx as cx
from test_effective_collection import select
from test_migration import snapshot as snapshot
from test_sealed_catalog import e1 as e1

from pokemon_hunter.beta import collection
from pokemon_hunter.beta import species_projection as species
from pokemon_hunter.beta.canonical_species import registry


def test_canonical_identity_and_read_preservation_without_parity(cx):
    before = collection.export_data(cx["actor"])
    with patch("pokemon_hunter.beta.parity.projection", side_effect=AssertionError("No valuations")):
        with patch("httpx.Client.send", side_effect=AssertionError("No providers")):
            result = species.project(cx["actor"])
    assert [row["dex"] for row in result["species"]] == list(range(1, 252))
    assert [row["name"] for row in result["species"]] == [registry()[n]["name"] for n in range(1, 252)]
    assert all(row["url"] == f"/pokedex/{row['dex']}/" for row in result["species"])
    assert all(row["species_quantity"] is None for row in result["species"])
    assert result["account_id"] == cx["actor"].user_id
    assert result["progress"]["total"] == 251
    assert collection.export_data(cx["actor"]) == before
    searched = species.project(cx["actor"], {"q": "#002"})
    assert [row["dex"] for row in searched["species"]] == [2]
    assert searched["progress"] == result["progress"]
    assert species.project(cx["actor"], {"region": "kanto"})["progress"]["total"] == 151
    assert species.project(cx["actor"], {"region": "johto"})["progress"]["total"] == 100


def test_saved_declaration_filters_use_frozen_source_while_current_presence_changes(cx):
    _, source = select(cx, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}})
    goal = create(cx, source)
    before = collection.one(cx["actor"], "goal", goal["id"])
    select(cx, {3: {"Base Set 2": "✓ Venusaur #18 (Rare)"}})
    result = species.project(cx["actor"], {"goal": goal["id"], "card": "Ivysaur", "gaps": "false"})
    assert len(result["species"]) == 151
    row = next(row for row in result["species"] if row["dex"] == 2)
    assert row["goal_present"] and not row["current_present"]
    assert result["scope"]["kind"] == "saved_declaration"
    assert result["progress"] == dict(satisfied=1, total=151, units="species")
    assert collection.one(cx["actor"], "goal", goal["id"]) == before
    with pytest.raises(ValueError, match="unavailable"):
        species.project(cx["member"], {"goal": goal["id"]})


def test_species_only_evidence_and_explicit_gap_filter(cx):
    select(cx, {2: {"Base Set 2": "✓"}, 251: {"Neo Revelation": "✓"}})
    result = species.project(cx["actor"])
    owned = [row for row in result["species"] if row["current_present"]]
    assert [row["dex"] for row in owned] == [2, 251]
    assert all(row["details_needed"] for row in owned)
    assert all(row["species_quantity"] is None for row in owned)
    assert (
        species.project(cx["actor"], {"q": "#251", "card": "Unknown", "gaps": "true"})["filtered_count"] == 1
    )
    assert (
        species.project(cx["actor"], {"q": "#251", "card": "Unrelated", "gaps": "false"})["filtered_count"]
        == 1
    )
    scoped = species.project(cx["actor"], {"q": "#251", "card": "Unrelated", "gaps": "true"})
    assert scoped["species"][0]["scope_status"] == "unresolved"
    assert scoped["scoped_progress"]["satisfied"] == 0


def test_generation_and_account_mismatch_cannot_publish(cx):
    authoritative = species.effective_collection.project(cx["actor"])
    with patch.object(
        species.effective_collection,
        "project",
        return_value={**authoritative, "user_id": cx["member"].user_id},
    ):
        with pytest.raises(collection.Conflict, match="reload"):
            species.project(cx["actor"])
    with pytest.raises(collection.Conflict, match="reload"):
        species.project(cx["actor"], {"generation": str(authoritative["generation"] + 1)})


def test_species_return_has_exactly_one_nesting_level(env):
    from pokemon_hunter.beta.card_group_views import return_context

    good = (
        "/pokedex/2/?goal=saved&return=%2Fpokedex%2F%3Fq%3DIvysaur%26selecting%3D1%26scroll%3D90%26focus%3D2"
    )
    assert return_context(good) == good
    for value in (
        "/pokedex/?generation=1",
        "/pokedex/?selecting=0",
        "/pokedex/?focus=252",
        "/pokedex/2/?child=one",
        "/pokedex/2/?return=%2Fcards%2F",
        "/pokedex/2/?return=%2Fpokedex%2F3%2F",
        "/pokedex/252/",
        "/pokedex/?return=%2Fpokedex%2F",
        "/pokedex/?region=unbounded",
    ):
        with pytest.raises(ValueError):
            return_context(value)


def test_filtered_explicit_species_policy_uses_existing_frozen_membership_and_progress(b2):
    from test_b2 import apply
    from test_filtered_goals import request

    operation = apply(b2, "goal", request(b2, pokemon_dex_min=1, pokemon_dex_max=3))
    goal_id = operation["changes"][0]["after"]["id"]
    goal = collection.goals(b2["actor"], goal_id=goal_id, include_updates=False)[0]
    result = species.project(b2["actor"], {"goal": goal_id})
    assert result["scope"]["kind"] == "qualified_species" and result["scope"]["supported"]
    assert result["scope"]["membership"] == [1, 2, 3]
    assert result["progress"] == dict(satisfied=goal["satisfied"], total=3, units="species")
    assert {row["dex"] for row in result["species"] if row["goal_present"]} == {
        item["pokemon_dex"] for item in goal["progress"] if item["status"] == "owned"
    }


def test_legacy_species_goal_without_species_references_retains_species_units_in_goals(b2):
    from test_b2 import apply

    operation = apply(b2, "goal", dict(name="Legacy Vintage", goal_kind="vintage"))
    goal_id = operation["changes"][0]["after"]["id"]
    result = species.project(b2["actor"], {"goal": goal_id})
    assert not result["scope"]["supported"]
    assert result["scope"]["units"] == result["progress"]["units"] == "species"
    assert result["scope"]["goals_url"] == "/goals/"
    assert all(row["goal_present"] is None for row in result["species"])


def test_guest_explicit_back_keeps_validated_focus_and_private_errors_are_opaque(cx):
    guest = cx["client"]()
    response = guest.get("/pokedex/?q=Ivysaur")
    assert response.status_code == 200
    # Public identity and Back/focus behavior are now exercised in the V2 browser harness.
    assert b"/collection-assets/public-browse.js" in response.content
    assert guest.get("/collection-assets/public-species.js").status_code == 200
    for old, new in (("all", "/pokedex/"), ("1", "/pokedex/?region=kanto"), ("2", "/pokedex/?region=johto")):
        redirect = guest.get("/pokedex/?region=" + old)
        assert redirect.status_code == 302 and redirect.url == new
    legacy = guest.get("/pokedex/?species=2&region=1")
    assert legacy.status_code == 302 and "region%3Dkanto" in legacy.url
    with patch.object(species, "project", side_effect=ValueError("PRIVATE-ERROR")):
        invalid = cx["a"].get("/api/pokedex-species/")
        assert invalid.status_code == 400 and b"PRIVATE-ERROR" not in invalid.content
    for context in ("/pokedex/?q=%0A", "/pokedex/2/?goal=%00"):
        from pokemon_hunter.beta.card_group_views import return_context

        with pytest.raises(ValueError):
            return_context(context)
