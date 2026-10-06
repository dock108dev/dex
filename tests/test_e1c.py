"""Full-registry support is distinct from physical certainty and frozen goal policy."""

import copy
import json
import uuid
from pathlib import Path

import pytest
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_migration import snapshot as snapshot
from test_sealed_catalog import e1 as e1
from test_sealed_catalog import publish

from pokemon_hunter.beta import broad_goals, canonical_species, catalog_imports, packs, parity, store
from pokemon_hunter.beta import collection as inv
from pokemon_hunter.beta import sealed_catalog as sealed

ROOT = Path(__file__).parents[1]


def package():
    return json.loads((ROOT / "config/sealed/2026-10-05-det1-e1c/package.json").read_text())


def apply(actor, kind, data):
    op = inv.preview(actor, kind, data, str(uuid.uuid4()))
    assert not op["plan"]["errors"]
    inv.confirm(actor, op["id"])
    return op


@pytest.mark.parametrize("n", [272, 755, 658, 289, 1025])
def test_supported_species(n):
    m = catalog_imports.Metadata(pokemon_dex=n, dex_eligible=False, supertype="Pokémon", rarity="Unknown")
    assert canonical_species.require(m.pokemon_dex) == f"ndex:{n:04}"


@pytest.mark.parametrize("n", [0, 1026, 9999, True, "272", 272.0])
def test_unsupported_species(n):
    with pytest.raises(ValueError):
        catalog_imports.Metadata(pokemon_dex=n, dex_eligible=False, supertype="Pokémon", rarity="Unknown")


@pytest.mark.parametrize("fault", ["category", "eligible-unresolved", "mapping", "species-format", "finish"])
def test_consistency(fault):
    p = package()
    c = p["bridges"][0]["package"]["cards"][0]
    if fault == "category":
        c["metadata"]["supertype"] = "Trainer"
    elif fault == "eligible-unresolved":
        c["metadata"]["pokemon_dex"] = None
    elif fault == "mapping":
        p["bridges"][0]["links"][0]["external_id"] = "wrong"
    elif fault == "species-format":
        p["printings"][0]["species_id"] = "ndex:1"
    else:
        c["finish"] = "nonfoil"
    with pytest.raises(ValueError):
        sealed.validate(p)


def test_publication_rollback_successor_and_unknown_roundtrip(e1):
    actor = e1["actor"]
    apply(actor, "goal", dict(name="Frozen Original 151", goal_kind="original151"))
    apply(actor, "goal", dict(name="Frozen Vintage 251", goal_kind="vintage"))
    goals = store.rows("SELECT * FROM collection_goals ORDER BY id")
    original = next(g for g in inv.goals(actor) if g["kind"] == "original151")
    before = inv.copies(actor)
    p = package()
    op = sealed.preview(actor, p)
    assert len(op["baseline"]["bridges"][0]["impact"]["added"]) == 18
    assert sealed.preview(actor, p)["id"] == op["id"]
    with pytest.raises(ValueError):
        sealed.transition(actor, op["id"], "publish")
    sealed.transition(actor, op["id"], "verify")
    sealed.transition(actor, op["id"], "publish")
    assert sealed.transition(actor, op["id"], "publish")["state"] == "published"
    assert store.rows("SELECT * FROM collection_goals ORDER BY id") == goals
    assert inv.copies(actor) == before
    entries = inv.catalog(actor, set_id=op["baseline"]["bridges"][0]["impact"]["added"][0]["set_id"])
    projection = parity.projection(actor)
    assert len(projection["pokedex"]) == 251
    later = [c for c in projection["cards"].values() if c.get("pokemon_dex", 0) and c["pokemon_dex"] > 251]
    assert len(later) == 4 and all(not c["dex_eligible"] for c in later)
    assert len(entries) == 18
    assert all(p["edition"] is None and p["finish"] is None for p in entries)
    assert all(p["unresolved_fields"] == ["edition", "finish"] for p in entries)
    bad = copy.deepcopy(p)
    bad["version"] += "-conflict"
    bad["bridges"][0]["package"]["version"] += "-conflict"
    bad["bridges"][0]["package"]["cards"][0]["edition"] = "unlimited"
    with pytest.raises(ValueError, match="Identity conflict"):
        sealed.preview(actor, bad)
    sealed.transition(actor, op["id"], "rollback")
    assert not inv.catalog(actor, set_id=entries[0]["set_id"])
    assert store.rows("SELECT * FROM collection_goals ORDER BY id") == goals
    # Reviewed new sealed version restores the archived exact identities.
    p["version"] += "-restore"
    p["bridges"][0]["package"]["version"] += "-restore"
    publish(e1, p)
    req = dict(
        id=original["id"], revision=original["revision"], name=original["name"], goal_kind="original151"
    )
    successor = inv.preview(actor, "goal_edit", req, str(uuid.uuid4()))
    assert len(successor["plan"]["goal_difference"]["added"]) == 13
    assert successor["plan"]["goal_difference"]["progress_after"] == original["satisfied"]
    assert store.rows("SELECT * FROM collection_goals ORDER BY id") == goals
    inv.confirm(actor, successor["id"])
    current = next(g for g in inv.goals(actor) if g["kind"] == "original151" and g["id"] != original["id"])
    assert current["total"] == 151
    members = {pid for i in current["definition"]["items"] for pid in i["printing_ids"]}
    assert sum(p["id"] in members for p in entries) == 13
    assert all(p["id"] not in members for p in entries if p["attributes"]["pokemon_dex"] > 151)
    broad_goals.validate(current["definition"])
    context = packs.project(actor, current["id"])
    assert len(context["expansions"]) == 1
    assert context["expansions"][0]["count"] == 0
    assert len(context["expansions"][0]["uncertain"]) == 13
    response = e1["a"].get("/packs/", {"goal": current["id"]})
    assert response.status_code == 200
    assert b"Unknown finish" in response.content
    assert b"0 possible missing species" in response.content
    vintage_before = inv.export_data(actor)["vintage_251"]
    higher = next(p for p in entries if p["attributes"]["pokemon_dex"] == 755)
    apply(actor, "add", dict(printing_id=higher["id"], duplicate_policy="allow"))
    assert inv.export_data(actor)["vintage_251"] == vintage_before
    apply(actor, "add", dict(printing_id=entries[0]["id"], duplicate_policy="allow"))
    exported = inv.export_data(actor)
    row = next(p for p in exported["copies"] if p["printing_id"] == entries[0]["id"])
    assert row["edition"] is None
    assert json.loads(row["unresolved_fields"]) == ["edition", "finish"]
    assert (
        sealed.validate(json.loads(json.dumps(package())))["bridges"][0]["package"]["cards"][0]["finish"]
        is None
    )
    # Unknown physical identity stays unresolved and cannot manufacture completion.
    assert next(g for g in inv.goals(actor) if g["id"] == current["id"])["satisfied"] == original["satisfied"]
    apply(e1["member"], "import", dict(text=json.dumps(exported), format="json", duplicate_policy="allow"))
    reexported = inv.export_data(e1["member"])
    assert next(p for p in reexported["copies"] if p["printing_id"] == row["printing_id"])["edition"] is None
