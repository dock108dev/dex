"""Owner default attestations preserve history, account isolation and explicit edits."""

import uuid

import pytest
from test_collection_intents import current, intent
from test_effective_collection import add, apply, b2, b3, b4, cx, e1, env, remove, select, snapshot

from pokemon_hunter.beta import card_groups, collection

__all__ = ["b2", "b3", "b4", "cx", "e1", "env", "snapshot"]


def request(cx):
    return dict(card_ids=[current(cx)["id"]], quantity=1, variant="normal")


def test_owner_attestation_no_copies_catalog_or_goal_changes_and_undo(cx):
    copy = next(
        row for row in collection.copies(cx["actor"]) if row["printing_id"] == cx["by_legacy"]["a"]["id"]
    )
    remove(cx, copy)
    select(cx, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}})
    before = (collection.copies(cx["actor"]), collection.catalog(cx["actor"]), collection.goals(cx["actor"]))
    pending = collection.preview(cx["actor"], "card_defaults", request(cx), str(uuid.uuid4()))
    assert current(cx)["established_total_quantity"] is None
    assert pending["plan"]["reviewed_effects"]["quantity_changes"][0]["after"] == 1
    done = collection.confirm(cx["actor"], pending["id"])
    assert current(cx)["established_total_quantity"] == 1
    assert current(cx)["owned_variant"] == "normal"
    assert before == (
        collection.copies(cx["actor"]),
        collection.catalog(cx["actor"]),
        collection.goals(cx["actor"]),
    )
    grouped = card_groups.list_groups(cx["actor"], {"scope": "owned"})["groups"][0]
    assert grouped["established_total_quantity"] == 1 and grouped["owned_variant"] == "normal"
    assert grouped["exact_variant_count"] == 0
    collection.undo(cx["actor"], done["id"])
    assert current(cx)["established_total_quantity"] is None
    assert not current(cx).get("owned_variant")


def test_explicit_quantity_preserved_later_edit_and_undo_dependency(cx):
    select(cx)
    intent(cx, "mark_owned")
    intent(cx, "card_quantity", established_total_quantity=3)
    done = apply(cx["actor"], "card_defaults", request(cx))
    assert current(cx)["established_total_quantity"] == 3
    intent(cx, "card_quantity", established_total_quantity=4)
    assert current(cx)["established_total_quantity"] == 4
    with pytest.raises(collection.Conflict, match="Newer card intent"):
        collection.undo(cx["actor"], done["id"])


def test_explicit_copy_note_preserved_as_variant_exception(cx):
    select(cx)
    added = add(cx, "a")
    copy = added["changes"][0]["after"]
    apply(
        cx["actor"],
        "edit",
        dict(id=copy["id"], revision=copy["revision"], attributes={"notes": "reverse holo"}),
    )
    apply(cx["actor"], "card_defaults", request(cx))
    assert current(cx)["established_total_quantity"] == 1
    assert not current(cx).get("owned_variant")


def test_multiple_copies_without_total_fail_before_any_write(cx):
    select(cx)
    add(cx, "a")
    add(cx, "a")
    generation = collection.generation(cx["actor"])
    with pytest.raises(collection.Conflict, match="Multiple recorded copies"):
        apply(cx["actor"], "card_defaults", request(cx))
    assert collection.generation(cx["actor"]) == generation


def test_new_source_and_removal_replace_default_attestation(cx):
    select(cx)
    intent(cx, "mark_owned")
    apply(cx["actor"], "card_defaults", request(cx))
    intent(cx, "remove_card")
    intent(cx, "mark_owned")
    assert current(cx)["established_total_quantity"] is None
    assert not current(cx).get("owned_variant")
    apply(cx["actor"], "card_defaults", request(cx))
    select(cx, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}})
    assert current(cx)["established_total_quantity"] is None
    assert not current(cx).get("owned_variant")


def test_foreign_account_or_stale_generation_cannot_apply_defaults(cx):
    select(cx)
    intent(cx, "mark_owned")
    with pytest.raises(ValueError, match="Only the owner"):
        apply(cx["member"], "card_defaults", request(cx))
    pending = collection.preview(cx["actor"], "card_defaults", request(cx), str(uuid.uuid4()))
    intent(cx, "card_quantity", established_total_quantity=2)
    with pytest.raises(collection.Conflict, match="changed after preview"):
        collection.confirm(cx["actor"], pending["id"])
    assert current(cx)["established_total_quantity"] == 2


def test_known_normal_child_is_declared_owned_without_inventing_edition(cx):
    copy = next(
        row for row in collection.copies(cx["actor"]) if row["printing_id"] == cx["by_legacy"]["a"]["id"]
    )
    remove(cx, copy)
    collection.execute(
        "UPDATE printings SET edition=NULL,finish='normal',variant=%s,unresolved_fields=%s WHERE id=%s",
        ['{"type":"normal"}', '["edition"]', cx["by_legacy"]["a"]["id"]],
    )
    select(cx, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}})
    apply(cx["actor"], "card_defaults", request(cx))
    group = card_groups.list_groups(cx["actor"], {"scope": "owned"})["groups"][0]
    detail = card_groups.detail(cx["actor"], group["id"])
    variant = next(v for v in detail["variants"] if v["id"] == cx["by_legacy"]["a"]["id"])
    assert variant["declared_variant_owned"]
    assert not variant["exact_printing_owned"]
    assert detail["group"]["owned_variant"] == "normal"
    assert detail["group"]["established_total_quantity"] == 1


def test_later_variant_note_overrides_default_without_changing_total(cx):
    select(cx)
    added = add(cx, "a")
    copy = added["changes"][0]["after"]
    collection.execute(
        'UPDATE printings SET edition=NULL,finish=NULL,variant=NULL,unresolved_fields=\'["edition","finish","variant"]\' WHERE id=%s',
        [copy["printing_id"]],
    )
    collection.execute("UPDATE owned_copies SET first_edition_selected=0 WHERE id=%s", [copy["id"]])
    apply(cx["actor"], "card_defaults", request(cx))
    assert current(cx)["owned_variant"] == "normal"
    apply(
        cx["actor"],
        "edit",
        dict(id=copy["id"], revision=copy["revision"], attributes={"notes": "reverse holo"}),
    )
    assert not current(cx).get("owned_variant")
    assert current(cx)["established_total_quantity"] == 1
