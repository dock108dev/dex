"""grouping contracts on isolated engineering accounts and retained metadata."""

import copy
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.test.utils import CaptureQueriesContext
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_effective_collection import cx as cx
from test_effective_collection import remove, select
from test_migration import snapshot as snapshot
from test_sealed_catalog import e1 as e1

from pokemon_hunter.beta import card_groups as groups
from pokemon_hunter.beta import collection, store


def metadata(key="a", **changes):
    row = dict(
        id=key,
        game_id="pokemon",
        set_id="base2",
        set_name="Base Set 2",
        language="en",
        collector_number="44",
        name="Ivysaur",
        edition=None,
        finish=None,
        variant=None,
        attributes=dict(name="Ivysaur", pokemon_dex=2, supertype="Pokémon"),
        unresolved_fields=[],
        provenance="{}",
    )
    row.update(changes)
    return row


def find(cx, legacy="a"):
    child = cx["by_legacy"][legacy]["id"]
    return next(
        row for row in groups.project(cx["actor"])["groups"] if child in {p["id"] for p in row["_children"]}
    )


def clone(cx, **changes):
    row = store.rows("SELECT * FROM printings WHERE id=%s", [cx["by_legacy"]["a"]["id"]])[0]
    row.update(id="extra-variant", **changes)
    keys = list(row)
    collection.execute(
        "INSERT INTO printings (" + ",".join(keys) + ") VALUES (" + ",".join(["%s"] * len(keys)) + ")",
        [row[key] for key in keys],
    )
    return row


def test_retained_ivysaur_metadata_revalidated_twenty_variants_thirteen_groups():
    root = Path(__file__).parents[1] / "config/catalog-pipeline"
    retained = json.loads((root / "retained-20261004.json").read_text())
    packages = [row["package"] for row in retained["sets"]]
    packages.append(json.loads((root / "d6-20261005/gym2.json").read_text()))
    fixture = Path(__file__).parent / "fixtures/retained-catalog/ivysaur-packages.json"
    packages.extend(row["package"] for row in json.loads(fixture.read_text()))
    rows = []
    for package in packages:
        for card in package.get("cards", []):
            if card.get("metadata", {}).get("pokemon_dex") == 2:
                rows.append(
                    metadata(
                        package["provider"] + ":" + card["external_id"],
                        game_id=package["game"],
                        set_id=package["provider"] + ":" + package["language"] + ":" + package["set_key"],
                        set_name=package["set_name"],
                        name=card["name"],
                        language=package["language"],
                        collector_number=card["number"],
                        attributes={**card["metadata"], "name": card["name"]},
                        finish=card.get("finish"),
                        edition=card.get("edition"),
                        variant=card.get("variant"),
                    )
                )
    result = groups.build_groups(rows, pokemon_game_ids={"pokemon"})
    assert len(rows) == 20 and len(result["groups"]) == 13
    assert not result["unresolved"]
    assert any(row["name"] == "Erika's Ivysaur" for row in result["groups"])
    assert {(row["set_name"], row["collector_number"]) for row in result["groups"]}.issuperset(
        {("Base Set", "30"), ("Base Set 2", "44")}
    )


def test_species_eligibility_is_game_and_type_bound():
    rows = [
        metadata(),
        metadata(
            "trainer",
            collector_number="45",
            attributes={"name": "Ivysaur", "supertype": "Trainer", "pokemon_dex": 2},
        ),
        metadata("foreign", game_id="other", collector_number="46"),
    ]
    result = groups.build_groups(rows, pokemon_game_ids={"pokemon"})
    assert [row["pokemon_dex"] for row in result["groups"]] == [2, None, None]


def test_same_number_contradictory_catalog_names_stop_slot():
    result = groups.build_groups(
        [metadata(), metadata("wrong", name="Venusaur"), metadata("other", collector_number="45")]
    )
    assert len(result["groups"]) == 1
    assert result["unresolved"][0]["printing_ids"] == ["a", "wrong"]


def test_artwork_fields_and_identity_reorder_do_not_rekey():
    base = metadata()
    original = groups.build_groups([base])["groups"][0]["id"]
    changed = copy.deepcopy(base)
    changed["attributes"].update(image_url="blocked", quantity=900)
    other = metadata("other", finish="holo", edition="first")
    for rows in ([changed, other], [other, changed], [dict(changed, publication_state="archived")]):
        assert groups.build_groups(rows)["groups"][0]["id"] == original


def test_declaration_only_unknown_total_zero_copy_and_detail(cx):
    old = next(
        copy for copy in collection.copies(cx["actor"]) if copy["printing_id"] == cx["by_legacy"]["a"]["id"]
    )
    remove(cx, old)
    select(cx, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}})
    row = find(cx)
    owned = groups.list_groups(cx["actor"], {"scope": "owned"})
    assert owned["total"] == 1
    assert owned["groups"][0]["present"] and owned["groups"][0]["recorded_copy_count"] == 0
    assert owned["groups"][0]["established_total_quantity"] is None
    assert "recorded_copy_ids" not in owned["groups"][0]
    detail = groups.detail(cx["actor"], row["id"])
    assert detail["selected_child"] is None
    assert detail["group"]["exact_printing_owned_ids"] == []
    assert not detail["variants"][0]["exact_printing_owned"]
    assert len(detail["history"]) == 1


def test_reads_are_fresh_one_effective_projection_and_bounded_queries(cx):
    from pokemon_hunter.beta import effective_collection

    clone(cx, finish="holo")
    row = find(cx)
    with patch.object(effective_collection, "project", wraps=effective_collection.project) as effective:
        with CaptureQueriesContext(connection) as queries:
            detail = groups.detail(cx["actor"], row["id"])
        assert effective.call_count == 1
    count = len(queries)
    collection.execute("DELETE FROM printings WHERE id='extra-variant'")
    with CaptureQueriesContext(connection) as fewer:
        groups.detail(cx["actor"], row["id"])
    assert count == len(fewer)
    assert len(detail["variants"]) == 2


def test_cached_private_snapshot_rejects_foreign_and_revoked_actor(cx):
    snapshot = groups.project(cx["actor"])
    with pytest.raises(ValueError):
        groups._finish_read(snapshot, cx["member"])
    collection.execute("UPDATE users SET state='revoked' WHERE id=%s", [cx["actor"].user_id])
    with pytest.raises(PermissionDenied):
        groups._finish_read(snapshot, cx["actor"])


def test_adapter_rejects_set_checklist_and_canonical_alias_conflict(cx):
    row = find(cx)
    with pytest.raises(ValueError):
        groups.mutation_request(
            cx["actor"],
            row["id"],
            "set",
            dict(set_id=row["set_id"], duplicate_policy="allow"),
            selected_child=cx["by_legacy"]["a"]["id"],
        )
    collection.execute(
        "UPDATE printings SET provenance=%s WHERE id=%s",
        [json.dumps(dict(legacy_id=row["id"])), cx["by_legacy"]["b"]["id"]],
    )
    with pytest.raises(collection.Conflict):
        groups.resolve_destination(cx["actor"], row["id"])
