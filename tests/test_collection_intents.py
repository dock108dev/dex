"""broad card mutation contracts on disposable engineering accounts."""

import json
import uuid

import pytest
from test_effective_collection import add, apply, b2, b3, b4, card, cx, e1, env, select, snapshot

from pokemon_hunter.beta import collection as inv
from pokemon_hunter.beta import effective_collection, store

# Imported fixtures keep the existing locked engineering setup.
__all__ = ["b2", "b3", "b4", "cx", "e1", "env", "snapshot"]


def identity(cx, key="a"):
    p = cx["by_legacy"][key]
    return dict(set_name=p["set_name"], name=p["name"], number=p["collector_number"], language=p["language"])


def current(cx, key="a"):
    i = identity(cx, key)
    return card(effective_collection.project(cx["actor"]), i["name"], i["number"])


def intent(cx, kind, key="a", **extra):
    return apply(cx["actor"], kind, {**identity(cx, key), **extra})


def test_mark_owned_preview_confirm_retry_no_copy(cx):
    select(cx)
    before = inv.copies(cx["actor"])
    opid = str(uuid.uuid4())
    pending = inv.preview(cx["actor"], "mark_owned", identity(cx), opid)
    assert not current(cx)["present"]
    assert [r["name"] for r in pending["plan"]["reviewed_effects"]["added_cards"]] == ["Ivysaur"]
    done = inv.confirm(cx["actor"], pending["id"])
    assert current(cx)["present"] and current(cx)["established_total_quantity"] is None
    assert inv.copies(cx["actor"]) == before
    assert inv.confirm(cx["actor"], pending["id"]) == done
    assert inv.preview(cx["actor"], "mark_owned", identity(cx), opid) == done
    with pytest.raises(inv.Conflict):
        inv.preview(cx["actor"], "mark_owned", identity(cx, "b"), opid)
    inv.undo(cx["actor"], done["id"])
    assert not current(cx)["present"]


def test_quantity_attest_clear_and_metadata_preserve(cx):
    select(cx)
    intent(cx, "mark_owned")
    intent(cx, "card_quantity", established_total_quantity=3)
    assert current(cx)["established_total_quantity"] == 3
    # Metadata on excluded inherited records never changes broad total.
    copy = next(c for c in inv.copies(cx["actor"]) if c["printing_id"] == cx["by_legacy"]["a"]["id"])
    apply(
        cx["actor"], "edit", dict(id=copy["id"], revision=copy["revision"], attributes={"notes": "retained"})
    )
    assert current(cx)["established_total_quantity"] == 3
    intent(cx, "card_quantity", established_total_quantity=None)
    assert current(cx)["present"] and current(cx)["established_total_quantity"] is None
    assert all(
        p["established_total_quantity"] is None
        for p in effective_collection.project(cx["actor"])["printings"].values()
    )
    assert effective_collection.project(cx["actor"])["species"]["2"]["established_total_quantity"] is None


@pytest.mark.parametrize("value", [True, False, 0, -1, 1.2, "3", "", [], {}])
def test_strict_total_and_explicit_zero(cx, value):
    select(cx)
    intent(cx, "mark_owned")
    before = inv.generation(cx["actor"])
    with pytest.raises(ValueError, match="positive integer"):
        intent(cx, "card_quantity", established_total_quantity=value)
    assert inv.generation(cx["actor"]) == before


def test_total_requires_presence_and_conflicting_copy_count(cx):
    select(cx)
    with pytest.raises(inv.Conflict, match="Mark this card owned"):
        intent(cx, "card_quantity", established_total_quantity=1)
    add(cx, "a")
    add(cx, "a")
    with pytest.raises(inv.Conflict, match="conflicts"):
        intent(cx, "card_quantity", established_total_quantity=1)
    assert current(cx)["established_total_quantity"] is None


def test_copy_change_and_undo_do_not_restore_stale_total(cx):
    select(cx, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}})
    intent(cx, "card_quantity", established_total_quantity=2)
    added = add(cx, "a")
    assert current(cx)["established_total_quantity"] is None
    inv.undo(cx["actor"], added["id"])
    assert current(cx)["established_total_quantity"] is None
    intent(cx, "card_quantity", established_total_quantity=2)
    copy = next(c for c in inv.copies(cx["actor"]) if c["printing_id"] == cx["by_legacy"]["a"]["id"])
    removed = apply(cx["actor"], "remove", dict(id=copy["id"], revision=copy["revision"]))
    assert current(cx)["present"] and current(cx)["established_total_quantity"] is None
    inv.undo(cx["actor"], removed["id"])
    assert current(cx)["present"] and current(cx)["established_total_quantity"] is None


def test_remove_card_disposes_all_matching_records_and_retains_history(cx):
    select(cx, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}})
    add(cx, "a")
    records = [
        inv.one(cx["actor"], "copy", c["id"])
        for c in inv.copies(cx["actor"])
        if c["printing_id"] == cx["by_legacy"]["a"]["id"]
    ]
    op = intent(cx, "remove_card")
    assert not current(cx)["present"]
    assert not effective_collection.project(cx["actor"])["species"]["2"]["present"]
    assert op["plan"]["reviewed_effects"]["affected_copy_ids"] == sorted(c["id"] for c in records)
    for before in records:
        after = inv.one(cx["actor"], "copy", before["id"])
        assert after == {**before, "state": "removed", "revision": before["revision"] + 1}
    sources = store.rows(
        "SELECT source_text,source_sha256 FROM ownership_declarations WHERE user_id=%s", [cx["actor"].user_id]
    )
    inv.undo(cx["actor"], op["id"])
    assert current(cx)["present"]
    assert (
        store.rows(
            "SELECT source_text,source_sha256 FROM ownership_declarations WHERE user_id=%s",
            [cx["actor"].user_id],
        )
        == sources
    )


def test_correction_preserves_copy_and_later_add_reestablishes_removal(cx):
    select(cx, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}})
    copies = inv.copies(cx["actor"])
    intent(cx, "declaration_correction")
    assert inv.copies(cx["actor"]) == copies
    assert current(cx)["present"] and not current(cx)["declared"]
    intent(cx, "remove_card")
    assert not current(cx)["present"]
    add(cx, "a")
    assert current(cx)["present"] and current(cx)["recorded_copy_count"] == 1


def test_intent_undo_dependencies_and_stale_preview(cx):
    select(cx)
    owned = intent(cx, "mark_owned")
    total = intent(cx, "card_quantity", established_total_quantity=2)
    with pytest.raises(inv.Conflict, match="Newer"):
        inv.undo(cx["actor"], owned["id"])
    pending = inv.preview(cx["actor"], "remove_card", identity(cx), str(uuid.uuid4()))
    intent(cx, "card_quantity", established_total_quantity=None)
    with pytest.raises(inv.Conflict, match="changed after preview"):
        inv.confirm(cx["actor"], pending["id"])
    with pytest.raises(inv.Conflict, match="Newer"):
        inv.undo(cx["actor"], total["id"])


def test_full_reselection_resets_presence_quantity_and_source_undo_guard(cx):
    _, source = select(cx)
    owned = intent(cx, "mark_owned")
    intent(cx, "card_quantity", established_total_quantity=4)
    selected = apply(
        cx["actor"], "source_select", dict(source_id=source["id"], scope="full251", replacement="replace")
    )
    assert not current(cx)["present"] and current(cx)["established_total_quantity"] is None
    assert selected["plan"]["creates"] == []
    with pytest.raises(inv.Conflict, match="Newer"):
        inv.undo(cx["actor"], owned["id"])
    inv.undo(cx["actor"], selected["id"])
    assert current(cx)["present"] and current(cx)["established_total_quantity"] == 4


def test_card_identity_literal_and_no_variant_promise(cx):
    select(cx)
    for fields in ({"name": "Missing"}, {"language": "jp"}, {"number": 44}):
        with pytest.raises(ValueError):
            apply(cx["actor"], "mark_owned", {**identity(cx), **fields})
    op = intent(cx, "mark_owned")
    assert op["plan"]["card_intent"]["identity"]["candidate_printing_ids"] == [cx["by_legacy"]["a"]["id"]]
    assert current(cx)["exact_printing_owned_ids"] == []
    assert json.dumps(op["plan"])


def test_journal_only_physical_removal_undo_does_not_restore_old_total(cx):
    select(cx)
    intent(cx, "mark_owned", "c")
    intent(cx, "card_quantity", "c", established_total_quantity=4)
    assert current(cx, "c")["current_copy_ids"] == []
    removed = intent(cx, "remove_card", "c")
    assert removed["changes"] == []
    inv.undo(cx["actor"], removed["id"])
    assert current(cx, "c")["present"]
    assert current(cx, "c")["established_total_quantity"] is None


def test_scoped_replacement_preserves_outside_intent_total_copies_and_history(cx):
    p = cx["by_legacy"]["c"]
    inv.execute("UPDATE catalog_sets SET name='Neo Genesis' WHERE id=%s", [p["set_id"]])
    inv.execute(
        "UPDATE printings SET collector_number='54',attributes=%s WHERE id=%s",
        [
            json.dumps(dict(name="Chikorita", pokemon_dex=152, dex_eligible=True, supertype="Pokémon")),
            p["id"],
        ],
    )
    cx["by_legacy"] = {json.loads(p["provenance"])["legacy_id"]: p for p in inv.catalog(cx["actor"])}
    _, source = select(cx)
    intent(cx, "mark_owned", "c")
    add(cx, "c")
    total = intent(cx, "card_quantity", "c", established_total_quantity=7)
    outside_before = current(cx, "c")
    copies_before = inv.copies(cx["actor"])
    intent(cx, "mark_owned", "a")
    intent(cx, "card_quantity", "a", established_total_quantity=3)
    replaced = apply(
        cx["actor"], "source_select", dict(source_id=source["id"], scope="kanto", replacement="replace")
    )
    assert not current(cx, "a")["present"]
    assert current(cx, "a")["established_total_quantity"] is None
    assert current(cx, "c") == outside_before
    assert inv.copies(cx["actor"]) == copies_before
    assert replaced["plan"]["reviewed_effects"]["removed_species"] == [2]
    # Outside-scope undo does not cross the independent Kanto boundary.
    inv.undo(cx["actor"], total["id"])
    assert current(cx, "c")["present"] and current(cx, "c")["established_total_quantity"] is None
    inv.undo(cx["actor"], replaced["id"])
    assert current(cx, "a")["present"] and current(cx, "a")["established_total_quantity"] == 3


def test_scoped_selection_before_full_only_applies_declared_scope(cx):
    _, source = select(
        cx, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}, 152: {"Neo Genesis": "✓ Chikorita #54 (Common)"}}
    )
    # Clear source selection without deleting preserved evidence.
    inv.execute("UPDATE collection_operations SET state='undone' WHERE user_id=%s", [cx["actor"].user_id])
    apply(cx["actor"], "source_select", dict(source_id=source["id"], scope="kanto", replacement="replace"))
    projected = effective_collection.project(cx["actor"])
    assert projected["species"]["2"]["present"]
    assert not projected["species"]["152"]["present"]
    assert projected["selected_source"] is None
    assert all(row["pokemon_dex"] <= 151 for row in projected["declaration_rows"])


def test_declaration_correction_does_not_erase_independent_mark_owned(cx):
    select(cx)
    intent(cx, "mark_owned", "c")
    intent(cx, "card_quantity", "c", established_total_quantity=3)
    intent(cx, "declaration_correction", "c")
    assert current(cx, "c")["present"]
    assert current(cx, "c")["established_total_quantity"] == 3
    assert not current(cx, "c")["declared"]
