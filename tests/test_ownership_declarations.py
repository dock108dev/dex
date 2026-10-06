"""Synthetic presence imports never become copy quantities or exact completion."""

import csv
import io
import uuid

import pytest
from test_b1 import env as env
from test_b2 import b2 as b2
from test_migration import snapshot as snapshot

from pokemon_hunter.beta import collection as inv
from pokemon_hunter.beta import ownership_declarations as decl
from pokemon_hunter.beta import store
from pokemon_hunter.inventory import connect
from pokemon_hunter.migration import digest


def request():
    text = io.StringIO(newline="")
    w = csv.writer(text)
    w.writerow(decl.HEADERS)
    w.writerow(["008", "Wartortle", "", "", "", "", "✓D", "", "", "", "", "", "✓"])
    raw = text.getvalue()
    return dict(text=raw, sha256=digest(raw.encode()))


def migrate(b2):
    with connect(b2["root"] / "inventory.db") as db:
        decl.initialize(db)
        decl.initialize(db)


def test_presence_account_isolation_idempotency_undo_and_preservation(b2):
    before = inv.export_data(b2["actor"])
    migrate(b2)
    assert inv.export_data(b2["actor"]) == before
    op = inv.preview(b2["actor"], "owner_declaration", request(), str(uuid.uuid4()))
    assert inv.export_data(b2["actor"]) == before
    result = inv.confirm(b2["actor"], op["id"])
    assert inv.confirm(b2["actor"], op["id"]) == result
    assert inv.export_data(b2["actor"]) == before
    s = decl.summary(b2["actor"])
    assert s["species"] == 1 and s["marked_cells"] == 2
    assert s["rows"][0]["status"] == "marker-review"
    assert s["rows"][1]["set_name"] == "Boundaries Crossed"
    assert all(r["quantity"] is None and not r["exact_printing_verified"] for r in s["rows"])
    assert not decl.summary(b2["member"])["rows"]
    again = inv.preview(b2["actor"], "owner_declaration", request(), str(uuid.uuid4()))
    assert not again["plan"]["creates"]
    inv.confirm(b2["actor"], again["id"])
    assert decl.summary(b2["actor"]) == s
    inv.undo(b2["actor"], op["id"])
    assert not decl.summary(b2["actor"])["rows"]
    assert inv.export_data(b2["actor"]) == before
    with pytest.raises(ValueError, match="Only the owner"):
        inv.preview(b2["member"], "owner_declaration", request(), str(uuid.uuid4()))


def test_source_identity_and_stale_preview(b2):
    migrate(b2)
    bad = request() | {"sha256": "0" * 64}
    with pytest.raises(ValueError, match="hash mismatch"):
        inv.preview(b2["actor"], "owner_declaration", bad, str(uuid.uuid4()))
    op = inv.preview(b2["actor"], "owner_declaration", request(), str(uuid.uuid4()))
    inv.bump(b2["actor"])
    with pytest.raises(inv.Conflict, match="changed after preview"):
        inv.confirm(b2["actor"], op["id"])
    assert not decl.summary(b2["actor"])["rows"]
    raw = request()["text"].replace("Wartortle", "Charizard")
    with pytest.raises(ValueError, match="name/number"):
        decl.parse(raw, digest(raw.encode()))


def test_declaration_does_not_change_frozen_goal_or_export_and_dashboard(b2):
    migrate(b2)
    op = inv.preview(
        b2["actor"], "goal", dict(name="Original 151", goal_kind="original151"), str(uuid.uuid4())
    )
    inv.confirm(b2["actor"], op["id"])
    before = inv.goals(b2["actor"])
    op = inv.preview(b2["actor"], "owner_declaration", request(), str(uuid.uuid4()))
    inv.confirm(b2["actor"], op["id"])
    assert inv.goals(b2["actor"]) == before
    response = b2["a"].get("/api/collection/")
    assert response.status_code == 200
    assert response.json()["ownership_declaration"]["species"] == 1
    assert store.rows(
        "SELECT source_sha256 FROM ownership_declarations WHERE user_id=%s", [b2["actor"].user_id]
    ) == [{"source_sha256": request()["sha256"]}]
    # Rollback refuses a later alteration rather than overwriting it.
    inv.execute("UPDATE ownership_declarations SET revision=1 WHERE user_id=%s", [b2["actor"].user_id])
    with pytest.raises(inv.Conflict, match="record changed"):
        inv.undo(b2["actor"], op["id"])


def test_gen2_bom_scope_and_original_declaration_coexist(b2):
    migrate(b2)
    first = inv.preview(b2["actor"], "owner_declaration", request(), str(uuid.uuid4()))
    inv.confirm(b2["actor"], first["id"])
    before = inv.export_data(b2["actor"])
    original = decl.summary(b2["actor"])
    text = "\ufeffDex,Pokemon,Neo Genesis,Neo Discovery,Plasma Storm,Dark Explorers\n152,Chikorita,✓,,,\n249,Lugia,,,✓EX,\n251,Celebi,,,,\n"
    source = dict(text=text, sha256=digest(text.encode()))
    op = inv.preview(b2["actor"], "owner_declaration", source, str(uuid.uuid4()))
    inv.confirm(b2["actor"], op["id"])
    result = decl.summary(b2["actor"])
    assert {k: v for k, v in result.items() if k != "gen2"} == {
        k: v for k, v in original.items() if k != "gen2"
    }
    assert result["gen2"]["species"] == 2
    assert result["gen2"]["total"] == 100
    assert len(result["gen2"]["missing"]) == 98
    assert result["gen2"]["rows"][1]["status"] == "marker-review"
    assert result["gen2"]["reviewed_printing_species"] is None
    assert inv.export_data(b2["actor"]) == before
    assert not decl.summary(b2["member"])["gen2"]["rows"]
    inv.undo(b2["actor"], op["id"])
    assert decl.summary(b2["actor"]) == original
    bad = text.replace("152,Chikorita", "001,Bulbasaur")
    with pytest.raises(ValueError, match="out-of-scope"):
        decl.parse(bad, digest(bad.encode()))


def full_request():
    from pokemon_hunter.beta.canonical_species import registry

    text = io.StringIO(newline="")
    writer = csv.writer(text)
    writer.writerow(decl.FULL_HEADERS)
    for n in range(1, 252):
        cells = [""] * (len(decl.FULL_HEADERS) - 3)
        if n == 1:
            cells[0] = "✓ Bulbasaur #44 (Common)"
        if n == 249:
            cells[-2] = "✓EX (card number and rarity unconfirmed)"
        writer.writerow([n, registry()[n]["name"], "Owned" if any(cells) else "Missing", *cells])
    raw = "\ufeff" + text.getvalue()
    return dict(text=raw, sha256=digest(raw.encode()))


def test_full_source_replaces_display_scope_and_drives_pokedex_without_copy_changes(b2):
    from pokemon_hunter.beta import parity

    migrate(b2)
    older = inv.preview(b2["actor"], "owner_declaration", request(), str(uuid.uuid4()))
    inv.confirm(b2["actor"], older["id"])
    original = decl.summary(b2["actor"])
    before = inv.export_data(b2["actor"])
    legacy = parity.projection(b2["actor"])
    op = inv.preview(b2["actor"], "owner_declaration", full_request(), str(uuid.uuid4()))
    inv.confirm(b2["actor"], op["id"])
    assert inv.export_data(b2["actor"]) == before
    summary = decl.summary(b2["actor"])
    assert summary["species"] == 1 and summary["marked_cells"] == 1
    assert summary["gen2"]["species"] == 1
    projection = parity.projection(b2["actor"])
    assert projection["owner_collection"]["total"] == 2
    assert projection["pokedex"]["249"]["collection_owned"]
    assert projection["pokedex"]["249"]["declared_cards"][0]["source_cell"].startswith("✓EX")
    assert not projection["pokedex"]["8"]["collection_owned"]
    assert projection["pokedex"]["1"]["declared_cards"][0]["declared_card_number"] == "44"
    assert projection["totals"] == legacy["totals"]
    assert not parity.projection(b2["member"])["owner_collection"]["active"]
    again = inv.preview(b2["actor"], "owner_declaration", full_request(), str(uuid.uuid4()))
    assert not again["plan"]["creates"]
    inv.undo(b2["actor"], op["id"])
    assert decl.summary(b2["actor"]) == original


def test_full_source_requires_consistent_status_and_all_rows():
    source = full_request()
    raw = source["text"].replace("1,Bulbasaur,Owned", "1,Bulbasaur,Missing")
    with pytest.raises(ValueError, match="status"):
        decl.parse(raw, digest(raw.encode()))
    raw = source["text"].replace("251,Celebi,Missing", "252,Celebi,Missing")
    with pytest.raises(ValueError, match="out-of-scope"):
        decl.parse(raw, digest(raw.encode()))


def test_dark_species_presence_counts_without_inventing_copy_identity(b2):
    migrate(b2)
    source = full_request()
    rows = list(csv.DictReader(io.StringIO(source["text"].lstrip("\ufeff"))))
    for row in rows:
        if int(row["Dex"]) in {134, 136}:
            row["Status"] = "Owned"
            row["Team Rocket"] = "✓D Dark " + row["Pokemon"] + " (card number and rarity unconfirmed)"
    text = io.StringIO(newline="")
    writer = csv.DictWriter(text, fieldnames=decl.FULL_HEADERS)
    writer.writeheader()
    writer.writerows(rows)
    raw = text.getvalue()
    before = inv.export_data(b2["actor"])
    op = inv.preview(
        b2["actor"], "owner_declaration", dict(text=raw, sha256=digest(raw.encode())), str(uuid.uuid4())
    )
    inv.confirm(b2["actor"], op["id"])
    result = decl.summary(b2["actor"])
    assert result["species"] == 3
    assert not {134, 136} & {r["pokemon_dex"] for r in result["missing"]}
    assert all(r["edition"] is None and r["finish"] is None for r in result["rows"])
    assert inv.export_data(b2["actor"]) == before


def test_photo_reconciled_source_retains_new_sets_and_special_card_details(b2):
    from pathlib import Path

    from pokemon_hunter.beta import parity

    migrate(b2)
    raw = (Path(__file__).resolve().parents[1] / "tests/fixtures/synthetic-collection.csv").read_bytes()
    before = inv.export_data(b2["actor"])
    op = inv.preview(
        b2["actor"], "owner_declaration", dict(text=raw.decode(), sha256=digest(raw)), str(uuid.uuid4())
    )
    inv.confirm(b2["actor"], op["id"])
    result = decl.summary(b2["actor"])
    assert (result["species"], result["marked_cells"], result["gen2"]["species"]) == (137, 262, 24)
    projected = parity.projection(b2["actor"])
    assert projected["owner_collection"]["total"] == 161
    for number, card_name, card_number in [
        (134, "Dark Vaporeon", "45"),
        (136, "Dark Flareon", "35"),
        (144, "Articuno-EX", "25"),
        (36, "Clefable", "98"),
    ]:
        cards = projected["pokedex"][str(number)]["declared_cards"]
        assert projected["pokedex"][str(number)]["collection_owned"]
        assert any(
            r["declared_card_name"] == card_name and r["declared_card_number"] == card_number for r in cards
        )
    assert "Call of Legends" in {r["set_name"] for r in result["rows"]}
    assert all(r["edition"] is None and r["finish"] is None for r in result["rows"])
    assert inv.export_data(b2["actor"]) == before
    inv.undo(b2["actor"], op["id"])
    assert inv.export_data(b2["actor"]) == before
