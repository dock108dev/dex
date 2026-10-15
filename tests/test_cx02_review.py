"""Independent adversarial checks on isolated engineering accounts."""

import json
import sqlite3
import uuid
from unittest.mock import patch

import pytest
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.http import Http404
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b2 import post
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_collection_goals import create
from test_effective_collection import add, apply, card, select
from test_effective_collection import cx as cx
from test_migration import snapshot as snapshot
from test_sealed_catalog import e1 as e1

from pokemon_hunter.beta import collection as inv
from pokemon_hunter.beta import effective_collection, lookup, parity, store


def identity(cx, key="c"):
    p = cx["by_legacy"][key]
    return dict(set_name=p["set_name"], name=p["name"], number=p["collector_number"])


def row(cx, key="c"):
    p = cx["by_legacy"][key]
    return card(effective_collection.project(cx["actor"]), p["name"], p["collector_number"])


def attest(cx, total, key="c"):
    return apply(cx["actor"], "card_quantity", {**identity(cx, key), "established_total_quantity": total})


def dump(cx):
    with sqlite3.connect(cx["root"] / "inventory.db") as db:
        return list(db.iterdump())


def test_independent_ordinary_intent_is_pending_then_converges_and_is_retry_safe(cx):
    select(cx)
    before_copies = inv.copies(cx["actor"])
    operation_id = str(uuid.uuid4())
    request = identity(cx)
    pending = inv.preview(cx["actor"], "mark_owned", request, operation_id)
    assert not row(cx)["present"]
    confirmed = inv.confirm(cx["actor"], pending["id"])
    assert inv.confirm(cx["actor"], pending["id"]) == confirmed
    assert inv.copies(cx["actor"]) == before_copies
    assert row(cx)["present"] and row(cx)["established_total_quantity"] is None
    current = parity.projection(cx["actor"])
    assert current["cards"]["c"]["effective_card_present"]
    assert current["pokedex"]["3"]["collection_owned"]
    assert not lookup.project(cx["actor"], dict(targets="3", scope="missing"))["missing"]
    assert cx["a"].get("/api/collection/").json()["effective_collection"]["species"]["3"]["present"]
    with pytest.raises(inv.Conflict, match="different input"):
        inv.preview(cx["actor"], "mark_owned", identity(cx, "a"), operation_id)


def test_independent_card_removal_preserves_raw_history_and_later_addition(cx):
    _, source = select(cx, {3: {"Base Set 2": "✓ Venusaur #18 (Rare Holo)"}})
    addition = add(cx)
    copy = addition["changes"][0]["after"]
    before_sources = store.rows("SELECT * FROM ownership_declarations")
    removal = apply(cx["actor"], "remove_card", identity(cx))
    retained = inv.one(cx["actor"], "copy", copy["id"])
    assert retained["state"] == "removed" and retained["id"] == copy["id"]
    assert retained["batch_id"] == copy["batch_id"]
    assert not row(cx)["present"] and not row(cx)["current_copy_ids"]
    assert store.rows("SELECT * FROM ownership_declarations") == before_sources
    assert any(c["before"]["id"] == copy["id"] for c in removal["changes"])
    with pytest.raises(inv.Conflict, match="removed"):
        apply(
            cx["actor"],
            "edit",
            dict(id=retained["id"], revision=retained["revision"], attributes={"notes": "retained history"}),
        )
    assert not row(cx)["present"]
    add(cx)
    assert row(cx)["present"] and row(cx)["established_total_quantity"] is None
    assert source["source_text"] == before_sources[0]["source_text"]


@pytest.mark.parametrize("value", [True, False, 1.0, 1.5, -1, 0, "1", "01", "", [], {}])
def test_independent_quantity_strict_types_and_zero_fail_without_mutation(cx, value):
    select(cx)
    apply(cx["actor"], "mark_owned", identity(cx))
    before = dump(cx)
    with pytest.raises(ValueError):
        inv.preview(
            cx["actor"],
            "card_quantity",
            {**identity(cx), "established_total_quantity": value},
            str(uuid.uuid4()),
        )
    assert dump(cx) == before


def test_independent_undo_copy_addition_never_restores_stale_total(cx):
    select(cx)
    apply(cx["actor"], "mark_owned", identity(cx))
    attest(cx, 4)
    addition = add(cx)
    assert row(cx)["established_total_quantity"] is None
    inv.undo(cx["actor"], addition["id"])
    assert row(cx)["present"]
    assert row(cx)["established_total_quantity"] is None


def test_independent_resolved_copy_evidence_cannot_contradict_existing_total(cx):
    select(cx)
    provisional = []
    for _ in range(2):
        op = apply(cx["actor"], "photo", dict(provisional_identity=json.dumps({"name": "Unreviewed card"})))
        provisional.append(op["changes"][0]["after"])
    apply(cx["actor"], "mark_owned", identity(cx))
    attest(cx, 1)
    printing_id = cx["by_legacy"]["c"]["id"]
    apply(cx["actor"], "resolve", dict(id=provisional[0]["id"], revision=0, printing_id=printing_id))
    assert row(cx)["established_total_quantity"] == 1
    try:
        pending = inv.preview(
            cx["actor"],
            "resolve",
            dict(id=provisional[1]["id"], revision=0, printing_id=printing_id),
            str(uuid.uuid4()),
        )
    except inv.Conflict:
        return
    if pending["plan"]["errors"]:
        return
    inv.confirm(cx["actor"], pending["id"])
    current = row(cx)
    assert current["established_total_quantity"] is None and current["conflicts"]


def test_independent_total_undo_dependency_and_source_boundary(cx):
    select(cx)
    owned = apply(cx["actor"], "mark_owned", identity(cx))
    quantity = attest(cx, 3)
    with pytest.raises(inv.Conflict):
        inv.undo(cx["actor"], owned["id"])
    cleared = attest(cx, None)
    with pytest.raises(inv.Conflict):
        inv.undo(cx["actor"], quantity["id"])
    assert row(cx)["present"] and row(cx)["established_total_quantity"] is None
    select(cx)
    with pytest.raises(inv.Conflict):
        inv.undo(cx["actor"], cleared["id"])
    assert not row(cx)["present"]


def test_independent_scoped_replacement_preserves_outside_quantity_and_copies(cx):
    printing_id = cx["by_legacy"]["c"]["id"]
    inv.execute(
        "UPDATE printings SET attributes=%s WHERE id=%s",
        [
            json.dumps(dict(name="Chikorita", pokemon_dex=152, dex_eligible=True, supertype="Pokémon")),
            printing_id,
        ],
    )
    cx["by_legacy"]["c"] = next(p for p in inv.catalog(cx["actor"]) if p["id"] == printing_id)
    _, source = select(cx)
    apply(cx["actor"], "mark_owned", identity(cx, "a"))
    attest(cx, 5, "a")
    add(cx)
    attest(cx, 8)
    outside = row(cx)
    raw_copies = inv.copies(cx["actor"])
    request = dict(source_id=source["id"], scope="kanto", replacement="replace")
    pending = inv.preview(cx["actor"], "source_select", request, str(uuid.uuid4()))
    assert row(cx, "a")["present"] and row(cx) == outside
    effects = pending["plan"]["reviewed_effects"]
    assert effects["replacement_scope"] == "kanto"
    assert effects["removed_species"] == [2]
    assert not effects["added_species"]
    assert all(q["name"] != "Chikorita" for q in effects["quantity_changes"])
    confirmed = inv.confirm(cx["actor"], pending["id"])
    assert not row(cx, "a")["present"]
    assert row(cx) == outside
    assert inv.copies(cx["actor"]) == raw_copies
    inv.undo(cx["actor"], confirmed["id"])
    assert row(cx, "a")["established_total_quantity"] == 5
    assert row(cx) == outside
    full = apply(
        cx["actor"], "source_select", dict(source_id=source["id"], scope="full251", replacement="replace")
    )
    assert not full["changes"]
    assert not row(cx, "a")["present"] and not row(cx)["present"]
    assert row(cx)["established_total_quantity"] is None


def test_independent_complete_mutation_sequence_and_saved_goal_policies(cx):
    _, source = select(cx, {3: {"Base Set 2": "✓ Venusaur #18 (Rare Holo)"}})
    frozen = create(cx, source)
    printing_id = cx["by_legacy"]["c"]["id"]
    inv.execute(
        "UPDATE printings SET unresolved_fields='[]',edition='unlimited',finish='nonholo',variant='standard' WHERE id=%s",
        [printing_id],
    )
    exact = apply(
        cx["actor"],
        "goal",
        dict(name="Retained exact", goal_kind="custom", policy="exact", printing_ids=[printing_id]),
    )
    exact_id = exact["changes"][0]["after"]["id"]
    definitions = {g["id"]: g["definition"] for g in inv.goals(cx["actor"])}
    apply(cx["actor"], "mark_owned", identity(cx))
    attest(cx, 3)
    assert row(cx)["present"] and row(cx)["established_total_quantity"] == 3
    assert inv.goals(cx["actor"], goal_id=exact_id)[0]["satisfied"] == 0
    add(cx)
    assert row(cx)["established_total_quantity"] is None
    assert inv.goals(cx["actor"], goal_id=exact_id)[0]["satisfied"] == 1
    apply(cx["actor"], "remove_card", identity(cx))
    assert not row(cx)["present"]
    assert inv.goals(cx["actor"], goal_id=exact_id)[0]["satisfied"] == 0
    assert inv.goals(cx["actor"], goal_id=frozen["id"])[0]["satisfied"] == 1
    assert lookup.project(cx["actor"], dict(targets="3", scope="missing"))["missing"]
    add(cx)
    assert row(cx)["present"]
    _, empty = select(cx)
    assert not row(cx)["present"]
    assert inv.goals(cx["actor"], goal_id=exact_id)[0]["satisfied"] == 1
    assert not lookup.project(cx["actor"], dict(targets="3", scope="missing", goal=exact_id))["missing"]
    assert not lookup.project(cx["actor"], dict(targets="3", scope="missing", goal=frozen["id"]))["missing"]
    selection = inv.operation(
        cx["actor"], effective_collection.project(cx["actor"])["source_boundary"]["operation_id"]
    )
    inv.undo(cx["actor"], selection["id"])
    assert row(cx)["present"] and row(cx)["established_total_quantity"] is None
    assert {g["id"]: g["definition"] for g in inv.goals(cx["actor"])} == definitions
    assert empty["source_text"] != source["source_text"]


def test_independent_atomic_failure_and_stale_preview(cx):
    select(cx)
    add(cx)
    pending = inv.preview(cx["actor"], "remove_card", identity(cx), str(uuid.uuid4()))
    before = dump(cx)
    with patch.object(inv, "bump", side_effect=RuntimeError("injected final write failure")):
        with pytest.raises(RuntimeError, match="injected"):
            inv.confirm(cx["actor"], pending["id"])
    assert dump(cx) == before
    apply(cx["actor"], "mark_owned", identity(cx, "a"))
    with pytest.raises(inv.Conflict, match="changed after preview"):
        inv.confirm(cx["actor"], pending["id"])
    assert row(cx)["present"]


def test_independent_unsupported_journal_order_blocks_preview_and_undo(cx):
    selected, _ = select(cx)
    owned = apply(cx["actor"], "mark_owned", identity(cx))
    inv.execute(
        "UPDATE collection_operations SET generation=%s WHERE id=%s",
        [selected["generation"], owned["id"]],
    )
    before = dump(cx)
    for invoke in (
        lambda: inv.preview(cx["actor"], "mark_owned", identity(cx, "a"), str(uuid.uuid4())),
        lambda: inv.undo(cx["actor"], owned["id"]),
    ):
        with pytest.raises(inv.Conflict, match="order"):
            invoke()
        assert dump(cx) == before


def test_independent_restart_retains_current_intent_without_writes(cx):
    select(cx)
    apply(cx["actor"], "mark_owned", identity(cx))
    attest(cx, 7)
    projection = effective_collection.project(cx["actor"])
    before = dump(cx)
    connection.close()
    assert effective_collection.project(cx["actor"]) == projection
    assert dump(cx) == before
    exported = inv.export_data(cx["actor"])
    assert row(cx)["established_total_quantity"] == 7
    assert "collection_intents" not in exported


def test_independent_historical_export_import_compatibility(b2):
    exported = inv.export_data(b2["actor"])
    imported = apply(
        b2["member"], "import", dict(format="json", text=json.dumps(exported), duplicate_policy="allow")
    )
    assert imported["state"] == "confirmed"
    other = effective_collection.project(b2["member"])
    assert all(r["established_total_quantity"] is None for r in other["cards"])
    assert len(inv.copies(b2["member"])) == len(exported["copies"])
    assert "collection_intents" not in exported


def test_independent_direct_endpoints_and_revocation_cannot_cross_accounts(cx):
    select(cx)
    request = identity(cx)
    pending = inv.preview(cx["actor"], "mark_owned", request, str(uuid.uuid4()))
    for action in ("confirm", "undo"):
        assert post(cx["b"], f"/api/operations/{pending['id']}/{action}/", {}).status_code == 404
    assert cx["b"].get(f"/api/operations/{pending['id']}/").status_code == 404
    assert post(cx["a"], f"/api/operations/{pending['id']}/confirm/", {"request": {}}).status_code == 400
    assert inv.operation(cx["actor"], pending["id"])["state"] == "preview"
    with pytest.raises(Http404):
        inv.confirm(cx["member"], pending["id"])
    forged = store.Principal(cx["member"].subject, cx["actor"].user_id, "owner")
    with pytest.raises(PermissionDenied):
        inv.preview(forged, "mark_owned", request, str(uuid.uuid4()))
    with pytest.raises(ValueError, match="fields"):
        inv.preview(
            cx["actor"], "mark_owned", {**request, "user_id": cx["member"].user_id}, str(uuid.uuid4())
        )
    own_member_preview = inv.preview(cx["member"], "mark_owned", request, str(uuid.uuid4()))
    cx["accounts"].revoke(cx["second"])
    for function in (inv.confirm, inv.undo, inv.operation):
        with pytest.raises(PermissionDenied):
            function(cx["member"], own_member_preview["id"])
    assert not row(cx)["present"]
