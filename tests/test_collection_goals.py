"""Synthetic ledger regression checks on disposable accounts, without acquisition."""

import copy
import csv
import io
import json
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from django.db import connection
from django.http import Http404
from test_b1 import env as env
from test_b2 import apply
from test_b2 import b2 as b2
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_migration import snapshot as snapshot
from test_ownership_declarations import migrate
from test_sealed_catalog import e1 as e1
from test_sealed_catalog import publish
from test_sealed_expansion import expanded

from pokemon_hunter.beta import collection as inv
from pokemon_hunter.beta import collection_goals as cg
from pokemon_hunter.beta import goal_hunts, pack_research, packs
from pokemon_hunter.migration import digest, encode

CSV = Path(__file__).parents[1] / "tests/fixtures/synthetic-collection.csv"
MISSING = {3, 17, 18, 65, 94, 97, 113, 115, 122, 123, 130, 131, 135, 146}


def seed(e1, text=None):
    migrate(e1)
    text = text if text is not None else CSV.read_bytes().decode()
    op = apply(e1, "owner_declaration", dict(text=text, sha256=digest(text.encode())))
    return op, next(r for r in cg.sources(e1["actor"]) if r["source_sha256"] == digest(text.encode()))


def create(e1, source, before=None):
    req = dict(name="Collection Original 151", goal_kind=cg.KIND, collection_source_id=source["id"])
    if before:
        req.update(id=before["id"], revision=before["revision"])
    op = apply(e1, "goal_edit" if before else "goal", req)
    return next(g for g in inv.goals(e1["actor"]) if g["id"] == op["changes"][0]["after"]["id"])


def successor_text():
    rows = list(csv.reader(io.StringIO(CSV.read_bytes().decode())))
    for row in rows[1:]:
        if int(row[0]) == 3:
            row[2], row[3] = "Owned", "✓ Venusaur #15 (Rare Holo)"
    stream = io.StringIO(newline="")
    csv.writer(stream).writerows(rows)
    return stream.getvalue()


def test_supplied_source_catalog_gaps_dark_ex_and_preserved_copies(e1):
    original = inv.export_data(e1["actor"])
    assert digest(CSV.read_bytes()) == "6c7584b9f4ac5a0e419d8103646454d552d0afdb14e96c4d7b4fce35e4ef1fd7"
    op, src = seed(e1)
    assert any(r["marker"] == "✓D" for r in op["plan"]["checklist"])
    assert any(r["marker"] == "✓EX" for r in op["plan"]["checklist"])
    with patch("httpx.Client.send", side_effect=AssertionError("Acquisition prohibited")):
        g = create(e1, src)
        assert (g["satisfied"], g["missing"], g["total"]) == (137, 14, 151)
        assert {i["pokemon_dex"] for i in g["progress"] if i["status"] != "owned"} == MISSING
        assert g["unavailable"] == 151
        p = packs.project(e1["actor"], g["id"])
        assert {i["pokemon_dex"] for i in p["missing"]} == MISSING
        assert p["progress"]["satisfied"] == 137 and not p["expansions"]
        assert not packs.project(e1["actor"], g["id"], "144")["expansions"]
    assert inv.copies(e1["actor"]) == original["copies"]
    assert not cg.sources(e1["member"])
    with pytest.raises(ValueError, match="account-local"):
        inv.preview(
            e1["member"],
            "goal",
            dict(name="Foreign", goal_kind=cg.KIND, collection_source_id=src["id"]),
            str(uuid.uuid4()),
        )
    with pytest.raises(Http404):
        packs.project(e1["member"], g["id"])
    with pytest.raises(inv.Conflict, match="depends"):
        inv.undo(e1["actor"], op["id"])


def test_successor_filters_saved_reopen_retention_and_import(e1):
    publish(e1, expanded())
    _, src = seed(e1)
    first = create(e1, src)
    pack_research.initialize()
    filtered = packs.project(e1["actor"], first["id"], "123", filters={"stock": "unknown"})
    assert filtered["progress"]["missing"] == 14 and filtered["expansions"][0]["count"] == 1
    saved = pack_research.save(
        e1["actor"], first["id"], species="123", goal_version=first["version"], filters={"stock": "unknown"}
    )
    scope = goal_hunts.snapshot(e1["actor"], first["id"])
    hunting = goal_hunts.project(
        e1["actor"], {"cards": {}, "catalog": [], "pokedex": {str(i): {} for i in range(1, 252)}}, scope
    )
    assert sum(s["dex_owned"] for s in hunting["pokedex"].values()) == 137
    assert not any(c["owned"] for c in hunting["cards"].values())
    raw = pack_research.one(e1["actor"], saved)["snapshot"]
    before = inv.one(e1["actor"], "goal", first["id"])
    _, new_src = seed(e1, successor_text())
    assert packs.project(e1["actor"], first["id"])["progress"]["missing"] == 14
    second = create(e1, new_src, first)
    assert (second["satisfied"], second["missing"]) == (138, 13)
    assert inv.one(e1["actor"], "goal", first["id"]) == before
    connection.close()
    reopened = pack_research.reopen(e1["actor"], saved)
    assert reopened["progress"]["missing"] == 14
    assert pack_research.one(e1["actor"], saved)["snapshot"] == raw
    exported = inv.export_data(e1["actor"])
    op = apply(
        e1,
        "import",
        dict(format="json", text=json.dumps(exported), duplicate_policy="allow"),
        client=e1["b"],
    )
    inv.confirm(e1["member"], op["id"])
    imported = [g for g in inv.goals(e1["member"]) if g["kind"] == cg.KIND]
    assert len(imported) == 2 and {g["missing"] for g in imported} == {13, 14}
    assert all(g["definition"]["collection_source"]["user_id"] == e1["member"].user_id for g in imported)
    with pytest.raises(Http404):
        pack_research.reopen(e1["member"], saved)
    for mutate in (
        lambda d: d["collection_sources"][0].update(source_sha256="0" * 64),
        lambda d: d["collection_sources"][0].update(user_id=e1["member"].user_id),
        lambda d: next(g for g in d["goals"] if g["kind"] == cg.KIND)["definition"].update(
            owned_species=list(range(1, 152))
        ),
    ):
        bad = copy.deepcopy(exported)
        mutate(bad)
        for g in bad["goals"]:
            g["version"] = digest(encode(g["definition"]).encode())
        state = inv.export_data(e1["member"])
        with pytest.raises(ValueError):
            inv.preview(
                e1["member"],
                "import",
                dict(format="json", text=json.dumps(bad), duplicate_policy="allow"),
                str(uuid.uuid4()),
            )
        assert inv.export_data(e1["member"]) == state


def test_declaration_rollback_and_stale_goal_preview(e1):
    op, src = seed(e1)
    inv.undo(e1["actor"], op["id"])
    assert not cg.sources(e1["actor"])
    _, src = seed(e1)
    req = dict(name="Preview", goal_kind=cg.KIND, collection_source_id=src["id"])
    pending = inv.preview(e1["actor"], "goal", req, str(uuid.uuid4()))
    seed(e1, successor_text())
    with pytest.raises(inv.Conflict):
        inv.confirm(e1["actor"], pending["id"])
    assert not any(g["kind"] == cg.KIND for g in inv.goals(e1["actor"]))


def test_atomic_import_failure_rolls_back_sources_and_goals(e1):
    _, src = seed(e1)
    create(e1, src)
    data = inv.export_data(e1["actor"])
    pending = inv.preview(
        e1["member"],
        "import",
        dict(format="json", text=json.dumps(data), duplicate_policy="allow"),
        str(uuid.uuid4()),
    )
    before = inv.export_data(e1["member"])
    write = inv.write_row

    def fail_goal(kind, row, insert=False):
        if kind == "goal" and row["kind"] == cg.KIND:
            raise RuntimeError("Synthetic failure after source insertion")
        return write(kind, row, insert=insert)

    with patch.object(inv, "write_row", side_effect=fail_goal), pytest.raises(RuntimeError):
        inv.confirm(e1["member"], pending["id"])
    assert inv.export_data(e1["member"]) == before
    assert not cg.sources(e1["member"])
    assert inv.operation(e1["member"], pending["id"])["state"] == "preview"
    inv.confirm(e1["member"], pending["id"])
    assert next(g for g in inv.goals(e1["member"]) if g["kind"] == cg.KIND)["missing"] == 14
