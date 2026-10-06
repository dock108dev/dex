"""M1 independent targets, ordinary maintenance, frozen research and isolation."""

import importlib
import json
import uuid
from unittest.mock import patch

import pytest
from django.db import connection
from django.http import Http404
from test_b2 import apply
from test_collection_goals import CSV, MISSING, create, seed
from test_collection_goals import b2 as b2
from test_collection_goals import b3 as b3
from test_collection_goals import b4 as b4
from test_collection_goals import e1 as e1
from test_collection_goals import env as env
from test_collection_goals import snapshot as snapshot
from test_sealed_catalog import publish
from test_sealed_expansion import expanded

from pokemon_hunter.beta import collection as inv
from pokemon_hunter.beta import collection_goals as cg
from pokemon_hunter.beta import lookup, pack_research, packs, parity


@pytest.fixture(autouse=True)
def ordinary_routes(e1):
    from django.conf import settings
    from django.urls import clear_url_caches

    from pokemon_hunter.beta import urls

    previous = settings.PARITY_ENABLED
    settings.PARITY_ENABLED = True
    importlib.reload(urls)
    clear_url_caches()
    yield
    settings.PARITY_ENABLED = previous
    importlib.reload(urls)
    clear_url_caches()


def goal(e1, src, numbers):
    op = apply(
        e1,
        "goal",
        dict(name="M1 collecting", goal_kind=cg.TARGET_KIND, collection_source_id=src["id"], targets=numbers),
    )
    return next(g for g in inv.goals(e1["actor"]) if g["id"] == op["changes"][0]["after"]["id"])


def test_251_subsets_owned_lookup_and_species_gaps(e1):
    _, src = seed(e1)
    original = inv.copies(e1["actor"])
    with patch("httpx.Client.send", side_effect=AssertionError("No provider calls")):
        g = goal(e1, src, list(range(1, 252)))
        assert (g["satisfied"], g["missing"], g["total"]) == (161, 90, 251)
        cg.validate(g["definition"], src)
        assert packs.project(e1["actor"], g["id"])["progress"]["missing"] == 90
        all_missing = lookup.project(e1["actor"], dict(scope="missing"))
        assert (all_missing["progress"]["satisfied"], len(all_missing["missing"])) == (161, 90)
        assert {i["pokemon_dex"] for i in all_missing["missing"] if i["pokemon_dex"] <= 151} == MISSING
        subset = goal(e1, src, [134, 136, 230, 251])
        assert (subset["satisfied"], subset["missing"]) == (3, 1)
        for n in (134, 136, 230):
            result = lookup.project(e1["actor"], dict(targets=str(n)))
            assert result["progress"]["satisfied"] == 1
            assert result["missing"][0]["status"] == "owned"
            assert not result["expansions"]
        with pytest.raises(ValueError):
            lookup.project(e1["actor"], dict(targets="252"))
        with pytest.raises(Http404):
            lookup.project(e1["member"], dict(goal=g["id"]))
    assert inv.copies(e1["actor"]) == original


def test_correction_preview_undo_conflict_successor_and_raw_identity(e1):
    _, src = seed(e1)
    original = inv.copies(e1["actor"])
    old = goal(e1, src, list(range(1, 252)))
    request = dict(source_id=src["id"], pokemon_dex=134, owned=False)
    op = inv.preview(e1["actor"], "collection_correct", request, str(uuid.uuid4()))
    assert op["plan"]["source_preview"]["owned"] == 160
    assert op["plan"]["source_preview"]["removed"] == [134]
    inv.confirm(e1["actor"], op["id"])
    assert parity.projection(e1["actor"])["owner_collection"]["total"] == 160
    assert next(g for g in inv.goals(e1["actor"]) if g["id"] == old["id"])["satisfied"] == 161
    with pytest.raises(inv.Conflict):
        inv.preview(e1["actor"], "collection_correct", request, str(uuid.uuid4()))
    inv.undo(e1["actor"], op["id"])
    assert parity.projection(e1["actor"])["owner_collection"]["total"] == 161
    assert inv.copies(e1["actor"]) == original
    source = inv.export_data(e1["actor"])["collection_sources"][0]
    assert source["source_text"].encode() == CSV.read_bytes()
    for label in (
        "Clefable #98 (Rare)",
        "Articuno-EX #25 (Rare Holo EX)",
        "Dark Vaporeon #45 (Uncommon)",
        "Dark Flareon #35 (Uncommon)",
    ):
        assert label in source["source_text"]
    req = dict(
        name=old["name"],
        goal_kind=cg.TARGET_KIND,
        collection_source_id=src["id"],
        targets=[134, 136, 230],
        id=old["id"],
        revision=old["revision"],
    )
    successor = apply(e1, "goal_edit", req)
    assert successor["plan"]["goal_progress"]["total"] == 3
    assert len([g for g in inv.goals(e1["actor"]) if g["kind"] == cg.TARGET_KIND]) == 2


def test_general_export_import_tampering_idempotency_and_lookup_restart(e1):
    publish(e1, expanded())
    _, src = seed(e1)
    first = create(e1, src)
    johto = lookup.project(e1["actor"], dict(targets="230"))
    assert [i["pokemon_dex"] for i in johto["uncovered_targets"]] == [230]
    g = goal(e1, src, list(range(1, 252)))
    pack_research.initialize()
    old = pack_research.save(e1["actor"], first["id"], goal_version=first["version"])
    result = lookup.project(e1["actor"], dict(targets="123,134", scope="all"))
    assert result["progress"]["total"] == 2 and result["progress"]["satisfied"] == 1
    key = pack_research.store_context(e1["actor"], result, "M1 lookup")
    raw = pack_research.one(e1["actor"], key)["snapshot"]
    connection.close()
    assert pack_research.reopen(e1["actor"], key)["progress"]["satisfied"] == 1
    assert pack_research.reopen(e1["actor"], old)["progress"]["satisfied"] == 137
    assert pack_research.one(e1["actor"], key)["snapshot"] == raw
    data = inv.export_data(e1["actor"])
    op = apply(
        e1, "import", dict(format="json", text=json.dumps(data), duplicate_policy="allow"), client=e1["b"]
    )
    inv.confirm(e1["member"], op["id"])
    assert len([g for g in inv.goals(e1["member"]) if g["kind"] == cg.TARGET_KIND]) == 1
    imported = next(g for g in inv.goals(e1["member"]) if g["kind"] == cg.TARGET_KIND)
    assert imported["satisfied"] == 161
    with pytest.raises(Http404):
        pack_research.reopen(e1["member"], key)
    data["collection_sources"][0]["source_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        inv.preview(
            e1["member"],
            "import",
            dict(format="json", text=json.dumps(data), duplicate_policy="allow"),
            str(uuid.uuid4()),
        )
    assert g["satisfied"] == 161


def test_ordinary_routes_and_lookup_save_scope_validation(e1):
    publish(e1, expanded())
    _, src = seed(e1)
    goal(e1, src, [123, 134, 230])
    pack_research.initialize()
    page = e1["a"].get("/lookup/?targets=134")
    assert page.status_code == 200
    assert b"Pack lookup" in page.content and b"1 owned" in page.content
    result = lookup.project(e1["actor"], dict(targets="134"))
    req = {**result["lookup_request"], "scope_version": result["goal"]["version"], "name": "Owned Vaporeon"}
    token = e1["a"].cookies["dex_b1_csrf"].value
    saved = e1["a"].post("/lookup/save/", {**req, "csrfmiddlewaretoken": token})
    assert saved.status_code == 302, saved.content
    assert e1["a"].get(saved["Location"]).status_code == 200
    assert e1["b"].get(saved["Location"]).status_code == 404
    req["scope_version"] = "0" * 64
    assert e1["a"].post("/lookup/save/", {**req, "csrfmiddlewaretoken": token}).status_code == 400
    assert e1["a"].get("/api/collection-sources/" + src["id"] + "/").status_code == 200
    assert e1["b"].get("/api/collection-sources/" + src["id"] + "/").status_code == 400
    body = e1["a"].get("/pokedex/").content
    assert b"pokedex.js" in body and b"Pack lookup" in body


def test_reselecting_original_source_retains_changed_successor_and_undo(e1):
    _, src = seed(e1)
    predecessor = goal(e1, src, list(range(1, 252)))
    op = apply(e1, "collection_correct", dict(source_id=src["id"], pokemon_dex=134, owned=False))
    changed = cg.latest(e1["actor"])
    successor = apply(
        e1,
        "goal_edit",
        dict(
            id=predecessor["id"],
            revision=predecessor["revision"],
            name=predecessor["name"],
            goal_kind=cg.TARGET_KIND,
            collection_source_id=changed["id"],
            targets=list(range(1, 252)),
        ),
    )
    assert successor["plan"]["goal_progress"]["satisfied"] == 160
    with pytest.raises(inv.Conflict):
        inv.undo(e1["actor"], op["id"])
    replay = apply(e1, "owner_declaration", dict(text=src["source_text"], sha256=src["source_sha256"]))
    assert not replay["changes"]
    assert cg.latest(e1["actor"])["id"] == src["id"]
    assert parity.projection(e1["actor"])["owner_collection"]["total"] == 161
    retained = [g for g in inv.goals(e1["actor"]) if g["kind"] == cg.TARGET_KIND]
    assert sorted(g["satisfied"] for g in retained) == [160, 161]
    inv.undo(e1["actor"], replay["id"])
    assert cg.latest(e1["actor"])["id"] == changed["id"]
    assert parity.projection(e1["actor"])["owner_collection"]["total"] == 160


def test_physical_card_criteria_lookup_does_not_use_declarations(e1):
    from test_filtered_goals import request

    seed(e1)
    for p in e1["catalog"]:
        inv.execute(
            "UPDATE printings SET attributes=%s WHERE id=%s",
            [json.dumps({**p["attributes"], "supertype": "Pokémon"}), p["id"]],
        )
    req = request(e1, completion="printings")
    apply(e1, "goal", {**req, "name": "Resolved physical cards", "policy": "exact"})
    g = next(g for g in inv.goals(e1["actor"]) if g["name"] == "Resolved physical cards")
    result = lookup.project(e1["actor"], dict(goal=g["id"]))
    assert g["satisfied"] == 0
    assert result["progress"]["satisfied"] == 0
    assert "collection_source" not in result["goal"]["definition"]
