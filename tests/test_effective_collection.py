"""Effective ownership boundaries on disposable engineering accounts only."""

import csv
import io
import json
import sqlite3
import uuid
from unittest.mock import patch

import pytest
from django.core.exceptions import PermissionDenied
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_collection_goals import create, seed
from test_migration import snapshot as snapshot
from test_ownership_declarations import migrate
from test_sealed_catalog import e1 as e1

from pokemon_hunter.beta import collection as inv
from pokemon_hunter.beta import (
    collection_goals,
    effective_collection,
    goal_hunts,
    lookup,
    owned_artwork,
    parity,
    store,
)
from pokemon_hunter.beta import ownership_declarations as declarations
from pokemon_hunter.beta.canonical_species import registry
from pokemon_hunter.migration import digest


@pytest.fixture
def cx(e1):
    """Retained imported copies plus an unowned card, all in an isolated catalog."""
    names = {"a": ("Ivysaur", "44", 2), "b": ("Bulbasaur", "67", 1), "c": ("Venusaur", "18", 3)}
    for p in inv.catalog(e1["actor"]):
        key = json.loads(p["provenance"])["legacy_id"]
        name, number, dex = names[key]
        inv.execute("UPDATE catalog_sets SET name='Base Set 2' WHERE id=%s", [p["set_id"]])
        inv.execute(
            "UPDATE printings SET collector_number=%s,language='en',attributes=%s WHERE id=%s",
            [
                number,
                json.dumps(dict(name=name, pokemon_dex=dex, dex_eligible=True, supertype="Pokémon")),
                p["id"],
            ],
        )
    e1["by_legacy"] = {json.loads(p["provenance"])["legacy_id"]: p for p in inv.catalog(e1["actor"])}
    return e1


def apply(actor, kind, data):
    pending = inv.preview(actor, kind, data, str(uuid.uuid4()))
    assert not pending["plan"]["errors"]
    return inv.confirm(actor, pending["id"])


def source_text(marks=None):
    marks = marks or {}
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=declarations.FULL_HEADERS)
    writer.writeheader()
    for n in range(1, 252):
        row = dict.fromkeys(declarations.FULL_HEADERS, "")
        row.update(Dex=n, Pokemon=registry()[n]["name"], Status="Owned" if n in marks else "Missing")
        row.update(marks.get(n, {}))
        writer.writerow(row)
    return stream.getvalue()


def select(cx, marks=None):
    return seed(cx, source_text(marks))


def add(cx, key="c", actor=None):
    return apply(
        actor or cx["actor"],
        "add",
        dict(printing_id=cx["by_legacy"][key]["id"], duplicate_policy="allow"),
    )


def remove(cx, copy):
    return apply(cx["actor"], "remove", dict(id=copy["id"], revision=copy["revision"]))


def card(projected, name, number):
    return next(r for r in projected["cards"] if r["name"] == name and r["number"] == number)


def present(cx, n):
    return effective_collection.project(cx["actor"])["species"][str(n)]["present"]


def test_exact_declared_ivysaur_zero_and_partial_records_never_invent_quantity(cx):
    old = next(c for c in inv.copies(cx["actor"]) if c["printing_id"] == cx["by_legacy"]["a"]["id"])
    remove(cx, old)
    _, source = select(cx, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}})
    p = effective_collection.project(cx["actor"])
    row = card(p, "Ivysaur", "44")
    assert p["selected_source"]["id"] == source["id"]
    assert row["present"] and row["declared"]
    assert row["established_total_quantity"] is None
    assert row["recorded_copy_count"] == 0
    assert row["exact_printing_owned_ids"] == []
    op = add(cx, "a")
    row = card(effective_collection.project(cx["actor"]), "Ivysaur", "44")
    assert row["present"] and row["recorded_copy_count"] == 1
    assert row["established_total_quantity"] is None
    assert op["id"] in row["operation_ids"]


def test_selected_empty_source_suppresses_imports_and_metadata_edits_do_not_revive(cx):
    before = inv.copies(cx["actor"])
    op, _ = select(cx)
    p = effective_collection.project(cx["actor"])
    assert p["has_selected_source"]
    assert p["source_boundary"]["operation_id"] == op["id"]
    assert not any(s["present"] for s in p["species"].values())
    assert inv.copies(cx["actor"]) == before
    copy = before[0]
    for kind, data in (
        ("edit", dict(attributes={"condition": "NM"})),
        ("edition", dict(selection="unresolved")),
    ):
        current = inv.one(cx["actor"], "copy", copy["id"])
        apply(cx["actor"], kind, dict(id=current["id"], revision=current["revision"], **data))
        assert not any(s["present"] for s in effective_collection.project(cx["actor"])["species"].values())


def test_confirmed_addition_agrees_with_current_adapters_and_missing_selector(cx):
    select(cx)
    op = add(cx)
    p = effective_collection.project(cx["actor"])
    assert p["species"]["3"]["present"]
    assert op["id"] in p["species"]["3"]["operation_ids"]
    assert card(p, "Venusaur", "18")["present"]
    view = parity.projection(cx["actor"])
    assert view["cards"]["c"]["effective_card_present"]
    assert view["pokedex"]["3"]["collection_owned"]
    assert view["pokedex"]["3"]["effective_species_present"]
    missing = lookup.project(cx["actor"], dict(targets="1,2,3", scope="missing"))
    assert {i["pokemon_dex"] for i in missing["missing"]} == {1, 2}
    response = cx["a"].get("/api/collection/")
    assert response.status_code == 200
    assert response.json()["effective_collection"]["species"]["3"]["present"]


def test_pending_and_undone_additions_and_removal_without_declaration(cx):
    select(cx)
    pending = inv.preview(
        cx["actor"],
        "add",
        dict(printing_id=cx["by_legacy"]["c"]["id"], duplicate_policy="allow"),
        str(uuid.uuid4()),
    )
    assert not present(cx, 3)
    inv.confirm(cx["actor"], pending["id"])
    assert present(cx, 3)
    inv.undo(cx["actor"], pending["id"])
    assert not present(cx, 3)
    op = add(cx)
    remove(cx, op["changes"][0]["after"])
    assert not present(cx, 3)


def test_last_record_removal_keeps_surviving_declaration(cx):
    select(cx, {3: {"Base Set 2": "✓ Venusaur #18 (Rare Holo)"}})
    op = add(cx)
    removed = remove(cx, op["changes"][0]["after"])
    row = card(effective_collection.project(cx["actor"]), "Venusaur", "18")
    assert row["present"] and row["recorded_copy_count"] == 0
    assert row["established_total_quantity"] is None
    inv.undo(cx["actor"], removed["id"])
    assert card(effective_collection.project(cx["actor"]), "Venusaur", "18")["recorded_copy_count"] == 1


def test_source_add_remove_reselection_edit_undo_preserves_new_boundary(cx):
    first, _ = select(cx)
    addition = add(cx)
    removal = remove(cx, addition["changes"][0]["after"])
    newer, _ = select(cx, {1: {"Base Set 2": "✓ Bulbasaur #67 (Common)"}})
    assert present(cx, 1) and not present(cx, 3)
    inv.undo(cx["actor"], removal["id"])
    assert inv.one(cx["actor"], "copy", addition["changes"][0]["after"]["id"])["state"] == "active"
    assert not present(cx, 3)  # Restoring an old record cannot overwrite the selected source.
    # Reimporting identical source bytes is still an explicit new boundary.
    reselected, _ = select(cx)
    assert reselected["plan"]["creates"] == []
    assert effective_collection.project(cx["actor"])["source_boundary"]["operation_id"] == reselected["id"]
    assert not present(cx, 1)
    later = add(cx)
    copy = later["changes"][0]["after"]
    edit = apply(cx["actor"], "edit", dict(id=copy["id"], revision=0, attributes={"condition": "LP"}))
    before = effective_collection.project(cx["actor"])
    inv.undo(cx["actor"], edit["id"])
    after = effective_collection.project(cx["actor"])
    assert before["species"]["3"]["present"] and after["species"]["3"]["present"]
    assert (
        before["species"]["3"]["established_total_quantity"]
        == after["species"]["3"]["established_total_quantity"]
    )
    with pytest.raises(inv.Conflict):
        inv.undo(cx["actor"], later["id"])
    assert first["id"] != newer["id"] != reselected["id"]


def test_metadata_edit_and_undo_cannot_admit_suppressed_copy(cx):
    old = inv.copies(cx["actor"])[0]
    select(cx)
    edit = apply(
        cx["actor"], "edit", dict(id=old["id"], revision=old["revision"], attributes={"notes": "review"})
    )
    assert not any(s["present"] for s in effective_collection.project(cx["actor"])["species"].values())
    inv.undo(cx["actor"], edit["id"])
    assert not any(s["present"] for s in effective_collection.project(cx["actor"])["species"].values())


def test_no_selected_source_retains_copy_fallback(cx):
    p = effective_collection.project(cx["actor"])
    assert not p["has_selected_source"] and p["selected_source"] is None
    assert p["species"]["1"]["present"] and p["species"]["2"]["present"]
    assert not p["species"]["3"]["present"]
    op = add(cx)
    assert present(cx, 3)
    inv.undo(cx["actor"], op["id"])
    assert not present(cx, 3)


def test_multi_cards_and_unresolved_special_marks_never_choose_variant(cx):
    select(
        cx,
        {
            2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon); Ivysaur #99 (Rare)"},
            8: {"Base Set": "✓"},
            134: {"Team Rocket": "✓D Dark Vaporeon (card number and rarity unconfirmed)"},
            249: {"Plasma Storm": "✓EX (card number and rarity unconfirmed)"},
        },
    )
    p = effective_collection.project(cx["actor"])
    assert {n for n, s in p["species"].items() if s["present"]} == {"2", "8", "134", "249"}
    assert {r["number"] for r in p["cards"] if r["pokemon_dex"] == 2 and r["present"]} == {"44", "99"}
    assert all(r["number"] is None for r in p["cards"] if r["pokemon_dex"] in {8, 134, 249})
    assert all(r["established_total_quantity"] is None for r in p["cards"] if r["present"])
    assert not any(r["exact_printing_owned"] for r in p["printings"].values())
    assert all(p["species"][str(n)]["unresolved"] for n in (8, 134, 249))


def test_missing_blocked_and_unsupported_artwork_cannot_change_ownership(cx, monkeypatch):
    select(cx, {3: {"Base Set 2": "✓ Venusaur #18 (Rare Holo)"}, 249: {"Plasma Storm": "✓EX"}})
    expected = effective_collection.project(cx["actor"])
    from pokemon_hunter.beta import image_mappings

    reference = image_mappings.card_group_reference

    def unavailable(*args, **kwargs):
        return dict(reference(*args, **kwargs), image_url=None, availability="unavailable")

    with patch.object(image_mappings, "card_group_reference", side_effect=unavailable):
        assert effective_collection.project(cx["actor"]) == expected
        view = parity.projection(cx["actor"])
        assert view["cards"]["c"]["effective_card_present"]
        assert view["cards"]["c"]["reference_image"]["availability"] == "unavailable"
        assert view["cards"]["c"]["reference_image"]["image_url"] is None
        assert view["effective_collection"] == expected
    from django.conf import settings

    monkeypatch.setattr(settings, "STAGING", True)
    blocked = effective_collection.project(cx["actor"])
    assert {n: s["present"] for n, s in blocked["species"].items()} == {
        n: s["present"] for n, s in expected["species"].items()
    }
    assert card(blocked, "Venusaur", "18")["present"]
    assert parity.projection(cx["actor"])["pokedex"]["249"]["collection_owned"]


def test_current_frozen_declaration_and_qualified_copy_goals_keep_distinct_policies(cx):
    _, src = select(cx, {3: {"Base Set 2": "✓ Venusaur #18 (Rare Holo)"}})
    frozen = create(cx, src)
    p = cx["by_legacy"]["c"]
    inv.execute(
        "UPDATE printings SET unresolved_fields='[]',edition='unlimited',finish='nonholo',variant='standard' WHERE id=%s",
        [p["id"]],
    )
    exact = apply(
        cx["actor"],
        "goal",
        dict(name="Qualified", goal_kind="custom", policy="exact", printing_ids=[p["id"]]),
    )
    exact_id = exact["changes"][0]["after"]["id"]
    assert inv.goals(cx["actor"], goal_id=exact_id)[0]["satisfied"] == 0
    select(cx)
    assert not present(cx, 3)
    assert inv.goals(cx["actor"], goal_id=frozen["id"])[0]["satisfied"] == 1
    op = add(cx)
    assert present(cx, 3)
    assert inv.goals(cx["actor"], goal_id=exact_id)[0]["satisfied"] == 1
    inv.undo(cx["actor"], op["id"])
    assert not present(cx, 3)
    assert inv.goals(cx["actor"], goal_id=exact_id)[0]["satisfied"] == 0
    assert inv.goals(cx["actor"], goal_id=frozen["id"])[0]["definition"] == frozen["definition"]


def test_account_isolation_forged_and_revoked_direct_projection(cx):
    select(cx, {3: {"Base Set 2": "✓ Venusaur #18 (Rare Holo)"}})
    assert not any(s["present"] for s in effective_collection.project(cx["member"])["species"].values())
    with pytest.raises(ValueError, match="current account"):
        effective_collection.project(cx["member"], active=inv.copies(cx["actor"]))
    forged = store.Principal(cx["member"].subject, cx["actor"].user_id, "owner")
    with pytest.raises(PermissionDenied):
        effective_collection.project(forged)
    cx["accounts"].revoke(cx["second"])
    with pytest.raises(PermissionDenied):
        effective_collection.project(cx["member"])
    assert present(cx, 3)


def test_repeated_reads_leave_all_persisted_evidence_unchanged(cx):
    _, source = select(cx, {3: {"Base Set 2": "✓ Venusaur #18 (Rare Holo)"}})
    create(cx, source)
    add(cx)

    def persisted():
        with sqlite3.connect(cx["root"] / "inventory.db") as db:
            return list(db.iterdump())

    before = persisted()
    first = effective_collection.project(cx["actor"])
    for _ in range(3):
        assert effective_collection.project(cx["actor"]) == first
        parity.projection(cx["actor"])
        inv.goals(cx["actor"])
        lookup.project(cx["actor"], dict(targets="1,2,3", scope="missing"))
    assert persisted() == before
    assert digest(collection_goals.latest(cx["actor"])["source_text"].encode()) == source["source_sha256"]


def test_scoped_source_reselection_replaces_scope_and_keeps_other_scope_fallback(cx):
    p = cx["by_legacy"]["c"]
    inv.execute(
        "UPDATE printings SET attributes=%s WHERE id=%s",
        [json.dumps(dict(name="Chikorita", pokemon_dex=152, dex_eligible=True)), p["id"]],
    )
    add(cx)

    def scoped(n):
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=declarations.HEADERS)
        writer.writeheader()
        row = dict.fromkeys(declarations.HEADERS, "")
        row.update(Dex=n, Pokemon=registry()[n]["name"], Base="✓")
        writer.writerow(row)
        return stream.getvalue()

    migrate(cx)
    text = scoped(2)
    apply(cx["actor"], "owner_declaration", dict(text=text, sha256=digest(text.encode())))
    assert present(cx, 2) and present(cx, 152)
    assert not present(cx, 1)
    text = scoped(8)
    apply(cx["actor"], "owner_declaration", dict(text=text, sha256=digest(text.encode())))
    p = effective_collection.project(cx["actor"])
    assert p["scoped_sources"]["kanto"]["boundary"]
    assert p["species"]["8"]["present"] and p["species"]["152"]["present"]
    assert not p["species"]["2"]["present"]


def test_ambiguous_operation_order_retains_conflict_without_admitting_source(cx):
    selected, _ = select(cx, {3: {"Base Set 2": "✓ Venusaur #18 (Rare Holo)"}})
    added = add(cx)
    inv.execute(
        "UPDATE collection_operations SET generation=%s WHERE id=%s",
        [selected["generation"], added["id"]],
    )
    p = effective_collection.project(cx["actor"])
    assert any(c["kind"] == "ambiguous-operation-order" for c in p["conflicts"])
    assert not p["species"]["3"]["present"]
    assert not card(p, "Venusaur", "18")["present"]


def test_literal_catalog_identity_collision_keeps_declaration_without_variant_mapping(cx):
    other = cx["by_legacy"]["b"]
    inv.execute(
        "UPDATE printings SET collector_number='44',attributes=%s WHERE id=%s",
        [json.dumps(dict(name="Ivysaur", pokemon_dex=3, dex_eligible=True)), other["id"]],
    )
    select(cx, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}})
    p = effective_collection.project(cx["actor"])
    row = card(p, "Ivysaur", "44")
    assert row["present"] and row["declared"]
    assert row["identity_status"] == "conflict"
    assert not row["printing_ids"]
    assert any(c["kind"] == "catalog-identity-collision" for c in row["conflicts"])
    assert not any(r["present"] for r in p["printings"].values())
    assert not p["species"]["3"]["present"]


def test_undo_cannot_delete_a_source_reselected_by_a_newer_operation(cx):
    marks = {3: {"Base Set 2": "✓ Venusaur #18 (Rare Holo)"}}
    original, src = select(cx, marks)
    select(cx)
    newer, _ = select(cx, marks)
    assert newer["plan"]["creates"] == []
    before = effective_collection.project(cx["actor"])
    with pytest.raises(inv.Conflict):
        inv.undo(cx["actor"], original["id"])
    after = effective_collection.project(cx["actor"])
    assert after == before
    assert after["selected_source"]["id"] == src["id"]
    assert after["source_boundary"]["operation_id"] == newer["id"]


def test_malformed_source_boundary_reports_conflict_and_never_guesses_order(cx):
    selected, _ = select(cx, {3: {"Base Set 2": "✓ Venusaur #18 (Rare Holo)"}})
    add(cx)
    inv.execute("UPDATE collection_operations SET generation='unresolved' WHERE id=%s", [selected["id"]])
    p = effective_collection.project(cx["actor"])
    assert any(c["kind"] == "ambiguous-operation-order" for c in p["conflicts"])
    assert not p["species"]["3"]["present"]


def test_artwork_preloaded_projection_cannot_cross_accounts(cx):
    owner = effective_collection.project(cx["actor"])
    with pytest.raises(ValueError, match="account"):
        owned_artwork.owned_cards(cx["member"], effective=owner)


@pytest.mark.parametrize("supertype", ["Trainer", "Energy"])
def test_non_pokemon_card_never_owns_incidental_species(cx, supertype):
    p = cx["by_legacy"]["c"]
    inv.execute(
        "UPDATE printings SET attributes=%s WHERE id=%s",
        [json.dumps(dict(name="Incidental species text", pokemon_dex=3, supertype=supertype)), p["id"]],
    )
    select(cx)
    add(cx)
    projected = effective_collection.project(cx["actor"])
    assert projected["printings"][p["id"]]["present"]
    assert not projected["species"]["3"]["present"]
    missing = lookup.project(cx["actor"], dict(targets="3", scope="missing"))
    assert {i["pokemon_dex"] for i in missing["missing"]} == {3}


def test_multiple_variant_candidates_remain_broad_declared_presence_without_exact_completion(cx):
    for key in ("a", "b"):
        p = cx["by_legacy"][key]
        for copy in inv.copies(cx["actor"]):
            if copy["printing_id"] == p["id"]:
                remove(cx, copy)
    other = cx["by_legacy"]["b"]
    inv.execute(
        "UPDATE printings SET collector_number='44',attributes=%s WHERE id=%s",
        [json.dumps(dict(name="Ivysaur", pokemon_dex=2, supertype="Pokémon")), other["id"]],
    )
    select(cx, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}})
    projected = effective_collection.project(cx["actor"])
    row = card(projected, "Ivysaur", "44")
    assert set(row["printing_ids"]) == {cx["by_legacy"][key]["id"] for key in ("a", "b")}
    assert row["present"] and row["recorded_copy_count"] == 0
    assert row["established_total_quantity"] is None
    assert row["exact_printing_owned_ids"] == []
    assert not any(p["exact_printing_owned"] for p in projected["printings"].values())


def test_no_goal_and_saved_hunt_lookup_policies_do_not_converge_on_one_counter(cx):
    _, src = select(cx, {3: {"Base Set 2": "✓ Venusaur #18 (Rare Holo)"}})
    frozen = create(cx, src)
    p = cx["by_legacy"]["c"]
    inv.execute(
        "UPDATE printings SET unresolved_fields='[]',edition='unlimited',finish='nonholo',variant='standard' WHERE id=%s",
        [p["id"]],
    )
    exact = apply(
        cx["actor"],
        "goal",
        dict(name="Saved qualified copy", goal_kind="custom", policy="exact", printing_ids=[p["id"]]),
    )
    exact_id = exact["changes"][0]["after"]["id"]
    add(cx)
    select(cx)
    base = parity.projection(cx["actor"])
    current = goal_hunts.project(cx["actor"], base, None)
    declaration = goal_hunts.project(cx["actor"], base, goal_hunts.snapshot(cx["actor"], frozen["id"]))
    qualified = goal_hunts.project(cx["actor"], base, goal_hunts.snapshot(cx["actor"], exact_id))
    assert not current["pokedex"]["3"]["dex_owned"] and not current["cards"]["c"]["owned"]
    assert declaration["pokedex"]["3"]["dex_owned"]
    assert not any(c["owned"] for c in declaration["cards"].values())
    assert qualified["cards"]["c"]["owned"]
    missing = lookup.project(cx["actor"], dict(targets="3", scope="missing"))
    assert {i["pokemon_dex"] for i in missing["missing"]} == {3}
    for goal_id in (frozen["id"], exact_id):
        saved = lookup.project(cx["actor"], dict(targets="3", scope="missing", goal=goal_id))
        assert saved["missing"] == [] and saved["ownership_basis"] == "saved-goal-policy"
