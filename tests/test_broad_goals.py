"""E2a authenticated reviewed goal versions; no acquisition or inferred ownership."""

import copy
import json
from unittest.mock import patch

from test_b1 import env as env
from test_b2 import apply, post, preview
from test_b2 import b2 as b2
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_migration import snapshot as snapshot
from test_sealed_catalog import e1 as e1
from test_sealed_catalog import package, publish
from test_sealed_expansion import expanded

from pokemon_hunter.beta import broad_goals, goal_hunts, parity, store
from pokemon_hunter.beta import catalog_imports as cat
from pokemon_hunter.beta import collection as inv
from pokemon_hunter.migration import digest, encode

REQ = dict(name="Any era Original 151", goal_kind="original151")


def goal(e1):
    return next(g for g in inv.goals(e1["actor"]) if g["kind"] == "original151")


def update(g):
    return dict(REQ, id=g["id"], revision=g["revision"])


def special(e1, version="special-v1", extra=False):
    p = expanded()["bridges"][0]["package"]
    p.update(set_key="e2a-synthetic", set_name="E2a synthetic canonical examples", version=version)
    p.pop("reconcile_legacy_set", None)
    examples = [
        ("Dark Bulbasaur", 1, "Pokémon"),
        ("Erika's Bulbasaur", 1, "Pokémon"),
        ("Alolan Vulpix", 37, "Pokémon"),
        ("Bulbasaur ex V GX", 1, "Pokémon"),
        ("Trainer cameo", None, "Trainer"),
        ("Energy", None, "Energy"),
        ("Unresolved species", None, "Pokémon"),
        ("Ivysaur", 2, "Pokémon"),
    ]
    if extra:
        examples.append(("Charmander", 4, "Pokémon"))
    p["cards"] = [
        dict(
            external_id=f"e2a-{i}",
            name=name,
            number=str(i),
            edition="unlimited",
            finish="normal",
            variant="standard",
            metadata=dict(pokemon_dex=n, dex_eligible=False, supertype=kind, rarity="Common"),
        )
        for i, (name, n, kind) in enumerate(examples)
    ]
    p["expected_count"] = len(p["cards"])
    op = cat.preview(e1["actor"], p)
    cat.transition(e1["actor"], op["id"], "verify")
    cat.transition(e1["actor"], op["id"], "publish")
    return inv.catalog(e1["actor"], set_id=op["set_id"])


def test_old_root_fixed_denominator_cancel_and_unreviewed_exclusion(b2):
    before = inv.export_data(b2["actor"])
    p = preview(b2, "goal", REQ).json()
    assert p["plan"]["goal_progress"]["total"] == 151
    assert p["plan"]["goal_progress"]["unavailable"] == 151
    assert not inv.goals(b2["actor"])  # Closing preview makes no goal writes.
    assert inv.copies(b2["actor"]) == before["copies"]
    result = post(b2["a"], f"/api/operations/{p['id']}/confirm/", {})
    assert result.status_code == 200
    assert goal(b2)["missing"] == 151
    assert post(b2["a"], f"/api/operations/{p['id']}/confirm/", {}).json() == result.json()
    assert len(inv.goals(b2["actor"])) == 1


def test_canonical_forms_copies_duplicates_evolutions_and_isolation(e1):
    entries = special(e1)
    apply(e1, "goal", REQ)
    g = goal(e1)
    members = {p for i in g["definition"]["items"] for p in i["printing_ids"]}
    assert {p["name"] for p in entries if p["id"] in members} == {
        "Dark Bulbasaur",
        "Erika's Bulbasaur",
        "Alolan Vulpix",
        "Bulbasaur ex V GX",
        "Ivysaur",
    }
    before = inv.copies(e1["actor"])
    for name in ("Ivysaur", "Dark Bulbasaur", "Dark Bulbasaur", "Alolan Vulpix"):
        p = next(p for p in entries if p["name"] == name)
        apply(e1, "add", dict(printing_id=p["id"], duplicate_policy="allow"))
        count = next(g for g in inv.goals(e1["actor"]) if g["kind"] == "original151")["satisfied"]
        assert count == {"Ivysaur": 1, "Dark Bulbasaur": 2, "Alolan Vulpix": 3}[name]
    assert len(inv.copies(e1["actor"])) == len(before) + 4
    current = goal(e1)
    assert current["satisfied"] == 3 and current["missing"] == 148 and current["unavailable"] == 148
    apply(e1, "goal", REQ, e1["b"])
    assert inv.goals(e1["member"])[0]["satisfied"] == 0
    assert preview(e1, "goal_edit", update(g), e1["b"]).status_code == 404
    owned = next(
        c
        for c in inv.copies(e1["actor"])
        if c["printing_id"] == next(p["id"] for p in entries if p["name"] == "Alolan Vulpix")
    )
    inv.execute("UPDATE printings SET unresolved_fields='[\"identity\"]' WHERE id=%s", [owned["printing_id"]])
    assert goal(e1)["satisfied"] == 2
    inv.execute("UPDATE printings SET unresolved_fields='[]' WHERE id=%s", [owned["printing_id"]])
    inv.execute(
        'UPDATE owned_copies SET provisional_identity=\'{"unresolved_fields":["species"]}\' WHERE id=%s',
        [owned["id"]],
    )
    assert goal(e1)["satisfied"] == 2


def test_real_reviewed_151_variants_membership_and_legacy_preservation(e1):
    apply(e1, "goal", dict(name="Legacy unchanged", goal_kind="vintage"))
    previous = store.rows("SELECT * FROM collection_goals")
    copies = inv.copies(e1["actor"])
    publish(e1, package())
    publish(e1, expanded())
    apply(e1, "goal", REQ)
    g = goal(e1)
    assert g["total"] == 151 and g["qualifying_printings"] == 346
    assert g["unavailable"] == 0 and g["missing"] == 151
    assert all(i["printing_ids"] for i in g["definition"]["items"])
    assert inv.copies(e1["actor"]) == copies
    assert all(row in store.rows("SELECT * FROM collection_goals") for row in previous)
    broad_goals.validate(g["definition"])


def test_growth_stale_review_successor_cancel_and_retained_hunt_scope(e1):
    entries = special(e1)
    apply(e1, "goal", REQ)
    g = goal(e1)
    frozen = inv.one(e1["actor"], "goal", g["id"])
    scope = goal_hunts.snapshot(e1["actor"], g["id"])
    p = preview(e1, "goal_edit", update(g)).json()
    special(e1, "special-v2", extra=True)
    assert post(e1["a"], f"/api/operations/{p['id']}/confirm/", {}).status_code == 409
    assert inv.one(e1["actor"], "goal", g["id"]) == frozen
    assert goal(e1)["coverage_update_available"]
    fresh = preview(e1, "goal_edit", update(g)).json()
    assert len(fresh["plan"]["goal_difference"]["added"]) == 1
    assert len(inv.goals(e1["actor"])) == 1  # cancellation
    confirmed = post(e1["a"], f"/api/operations/{fresh['id']}/confirm/", {}).json()
    assert post(e1["a"], f"/api/operations/{fresh['id']}/confirm/", {}).json() == confirmed
    versions = inv.goals(e1["actor"])
    assert len(versions) == 2
    assert inv.one(e1["actor"], "goal", g["id"]) == frozen
    successor = next(v for v in versions if v["id"] != g["id"])
    assert successor["definition"]["lineage"]["predecessor_version"] == g["version"]
    assert preview(e1, "goal_edit", update(g)).status_code == 409
    assert preview(e1, "goal_remove", dict(id=g["id"], revision=0)).status_code == 409
    assert post(e1["a"], f"/api/operations/{fresh['id']}/undo/", {}).status_code == 409
    # A saved scope projects current account copies without redirecting to the successor.
    with patch("pokemon_hunter.beta.ebay_hunts.search", side_effect=AssertionError("No provider call")):
        projected = goal_hunts.project(e1["actor"], parity.projection(e1["actor"]), scope)
    allowed = {p for i in scope["definition"]["items"] for p in i["printing_ids"]}
    assert {c["printing_id"] for c in projected["cards"].values()} == allowed
    assert goal_hunts.snapshot(e1["actor"], g["id"]) == scope
    apply(e1, "add", dict(printing_id=entries[0]["id"], duplicate_policy="allow"))
    assert any(
        c["owned"]
        for c in goal_hunts.project(e1["actor"], parity.projection(e1["actor"]), scope)["cards"].values()
    )


def test_export_import_versions_policy_forgery_and_account_refs(e1):
    special(e1)
    apply(e1, "goal", REQ)
    apply(e1, "goal_edit", update(goal(e1)))
    exported = inv.export_data(e1["actor"])
    apply(e1, "import", dict(text=json.dumps(exported), format="json", duplicate_policy="allow"), e1["b"])
    versions = inv.goals(e1["member"])
    root = next(g for g in versions if g["definition"]["lineage"]["number"] == 1)
    newer = next(g for g in versions if g["definition"]["lineage"]["number"] == 2)
    assert newer["definition"]["lineage"]["predecessor_id"] == root["id"]
    assert newer["definition"]["lineage"]["predecessor_version"] == root["version"]
    assert root["id"] not in {g["id"] for g in exported["goals"]}
    for mutation in ("member", "policy", "reference", "cross-account"):
        forged = copy.deepcopy(exported)
        g = forged["goals"][0]
        if mutation == "member":
            g["definition"]["items"][1]["printing_ids"] = g["definition"]["items"][0]["printing_ids"]
        elif mutation == "policy":
            g["definition"]["eligibility_policy"]["id"] = "unsupported"
        elif mutation == "reference":
            g["definition"]["lineage"]["root_id"] = root["id"]
        else:
            g["user_id"] = "another-account"
        g["version"] = digest(encode(g["definition"]).encode())
        assert (
            preview(
                e1, "import", dict(text=json.dumps(forged), format="json", duplicate_policy="allow")
            ).status_code
            == 400
        )


def test_account_ownership_change_invalidates_preview(e1):
    entries = special(e1)
    p = preview(e1, "goal", REQ).json()
    apply(e1, "add", dict(printing_id=entries[0]["id"], duplicate_policy="allow"))
    assert post(e1["a"], f"/api/operations/{p['id']}/confirm/", {}).status_code == 409


def test_explicit_legacy_original151_successor_and_import(e1):
    from test_filtered_goals import request

    original_op = apply(e1, "goal", request(e1))
    legacy = inv.goals(e1["actor"])[0]
    frozen = inv.one(e1["actor"], "goal", legacy["id"])
    op = apply(e1, "goal_edit", update(legacy))
    assert op["plan"]["goal_difference"]["policy_before"] == "species"
    assert op["plan"]["goal_difference"]["progress_before"] == legacy["satisfied"]
    assert inv.one(e1["actor"], "goal", legacy["id"]) == frozen
    assert post(e1["a"], f"/api/operations/{original_op['id']}/undo/", {}).status_code == 409
    assert preview(e1, "goal_edit", dict(request(e1), id=legacy["id"], revision=0)).status_code == 400
    exported = inv.export_data(e1["actor"])
    apply(e1, "import", dict(text=json.dumps(exported), format="json", duplicate_policy="allow"), e1["b"])
    imported = inv.goals(e1["member"])
    root = next(g for g in imported if g["kind"] == "filtered")
    newer = next(g for g in imported if g["kind"] == "original151")
    assert newer["definition"]["lineage"]["root_id"] == root["id"]
    assert newer["definition"]["lineage"]["predecessor_version"] == root["version"]


def test_saved_hunt_reopen_freezes_goal_version_and_no_provider(e1, monkeypatch):
    from django.conf import settings

    monkeypatch.setattr(settings, "ROOT", e1["root"])
    evidence = e1["root"] / "parity-evidence"
    evidence.mkdir()
    from pathlib import Path

    (evidence / "hunt.json").write_bytes((Path(__file__).parents[1] / "config/hunt.json").read_bytes())
    (evidence / "demo_hunts.json").write_text("[]")
    special(e1)
    apply(e1, "goal", REQ)
    first = goal(e1)
    with patch("pokemon_hunter.beta.ebay_hunts.search", side_effect=AssertionError("No provider calls")):
        saved = parity.search(e1["actor"], dict(demo=True, goal_id=first["id"], intent="missing"))
        before = store.resource(e1["actor"], "hunts", (saved["batch"], 1))
        captured = json.loads(before["coverage"])
        assert captured["goal_scope"]["version"] == first["version"]
        assert captured["query_plan"]
        special(e1, "growth", extra=True)
        apply(e1, "goal_edit", update(first))
        reopened = parity.hunt_response(e1["actor"], before, saved["batch"], 1)
        assert reopened["goal"] == saved["goal"]
        assert store.resource(e1["actor"], "hunts", (saved["batch"], 1)) == before
        assert reopened["results"] == []


def test_removals_require_successor_and_keep_frozen_ownership_and_hunts(e1):
    entries = special(e1)
    p = next(p for p in entries if p["name"] == "Ivysaur")
    apply(e1, "add", dict(printing_id=p["id"], duplicate_policy="allow"))
    apply(e1, "goal", REQ)
    old = goal(e1)
    assert old["satisfied"] == 1
    captured = goal_hunts.snapshot(e1["actor"], old["id"])
    head = store.rows(
        "SELECT i.package FROM catalog_heads h JOIN catalog_imports i ON i.id=h.import_id WHERE h.set_id=%s",
        [p["set_id"]],
    )[0]
    package = json.loads(head["package"])
    package.update(version="removed-v2", cards=[c for c in package["cards"] if c["name"] != "Ivysaur"])
    package["expected_count"] = len(package["cards"])
    op = cat.preview(e1["actor"], package)
    cat.transition(e1["actor"], op["id"], "verify")
    cat.transition(e1["actor"], op["id"], "publish")
    assert goal(e1)["satisfied"] == 1
    assert goal(e1)["definition"] == old["definition"]
    previewed = preview(e1, "goal_edit", update(old)).json()
    assert previewed["plan"]["goal_difference"]["removed"] == [p["id"]]
    assert previewed["plan"]["goal_difference"]["progress_before"] == 1
    assert previewed["plan"]["goal_difference"]["progress_after"] == 0
    projected = goal_hunts.project(e1["actor"], parity.projection(e1["actor"]), captured)
    retained = next(c for c in projected["cards"].values() if c["printing_id"] == p["id"])
    assert retained["owned"] and retained["pokemon_dex"] == 2
    assert not any(c["printing_id"] == p["id"] for c in parity.projection(e1["actor"])["cards"].values())

    applied = post(e1["a"], f"/api/operations/{previewed['id']}/confirm/", {})
    assert applied.status_code == 200
    assert goal(e1)["frozen_qualifying_printings"] in {4, 5}
    exported = inv.export_data(e1["actor"])
    apply(e1, "import", dict(text=json.dumps(exported), format="json", duplicate_policy="allow"), e1["b"])
    restored = inv.goals(e1["member"])
    assert sorted(g["satisfied"] for g in restored) == [0, 1]
