"""Independent adversarial review; disposable engineering roots only."""

import importlib
import json
import sqlite3
import uuid
from unittest.mock import patch

import pytest
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.http import Http404
from django.test.utils import CaptureQueriesContext
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b2 import post
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_collection_goals import create
from test_effective_collection import add, apply, remove, select
from test_effective_collection import cx as cx
from test_migration import snapshot as snapshot
from test_sealed_catalog import e1 as e1

from pokemon_hunter.beta import card_groups as groups
from pokemon_hunter.beta import collection as inv
from pokemon_hunter.beta import lookup, parity, store


def dump(cx):
    with sqlite3.connect(cx["root"] / "inventory.db") as db:
        return list(db.iterdump())


def clone(cx, key="a", **changes):
    original = store.rows("SELECT * FROM printings WHERE id=%s", [cx["by_legacy"][key]["id"]])[0]
    original.update(id=str(uuid.uuid4()), **changes)
    columns = list(original)
    inv.execute(
        "INSERT INTO printings (" + ",".join(columns) + ") VALUES (" + ",".join(["%s"] * len(columns)) + ")",
        [original[c] for c in columns],
    )
    return original["id"]


def find(cx, key="a"):
    p = cx["by_legacy"][key]
    return next(
        g
        for g in groups.list_groups(cx["actor"])["groups"]
        if g["name"] == p["name"] and g["collector_number"] == p["collector_number"]
    )


def adapt(cx, group, kind, request=None, child=None):
    literal = groups.mutation_request(cx["actor"], group["id"], kind, request or {}, selected_child=child)
    return apply(cx["actor"], kind, literal)


@pytest.mark.parametrize(
    "url",
    [
        "/api/card-groups/?q=Ivysaur&q=Venusaur",
        "/api/card-groups/?user_id=foreign",
        "/api/my-card-groups/?scope=catalog",
        "/api/public/card-groups/?user_id=foreign",
        "/api/public/card-groups/?scope=owned",
        "/api/species/2/card-groups/?q=one&q=two",
    ],
)
def test_reviewer_http_strict_queries_make_no_writes(cx, url):
    before = dump(cx)
    result = cx["a"].get(url)
    assert result.status_code == 400, result.content
    assert dump(cx) == before


def test_reviewer_forged_and_revoked_principals_and_alternating_accounts(cx):
    select(cx, {3: {"Base Set 2": "✓ Venusaur #18 (Rare Holo)"}})
    owner = groups.list_groups(cx["actor"], raw={"scope": "owned"})
    for _ in range(3):
        assert groups.list_groups(cx["member"], raw={"scope": "owned"})["total"] == 0
        assert groups.list_groups(cx["actor"], raw={"scope": "owned"}) == owner
    forged = store.Principal(cx["member"].subject, cx["actor"].user_id, "owner")
    with pytest.raises(PermissionDenied):
        groups.project(forged)
    cx["accounts"].revoke(cx["second"])
    for service in (
        lambda: groups.project(cx["member"]),
        lambda: groups.list_groups(cx["member"]),
        lambda: groups.species(cx["member"], 3),
    ):
        with pytest.raises(PermissionDenied):
            service()
    assert cx["b"].get("/api/my-card-groups/").status_code in {302, 403}
    assert groups.list_groups(cx["actor"], raw={"scope": "owned"}) == owner


def test_reviewer_group_adapter_cannot_bypass_literal_scope_or_foreign_child(cx):
    selected = find(cx)
    before = dump(cx)
    foreign = cx["by_legacy"]["c"]["id"]
    for service in (
        lambda: groups.detail(cx["actor"], selected["id"], selected_child=foreign),
        lambda: groups.resolve_destination(cx["actor"], foreign, group_id=selected["id"]),
        lambda: groups.mutation_request(
            cx["actor"], selected["id"], "mark_owned", {}, selected_child=foreign
        ),
        lambda: groups.mutation_request(cx["actor"], selected["id"], "mark_owned", {"name": "Venusaur"}),
        lambda: groups.mutation_request(cx["actor"], selected["id"], "source_select", {"source_id": "x"}),
    ):
        with pytest.raises((ValueError, Http404, inv.Conflict)):
            service()
    assert dump(cx) == before


def metadata(key="p", **changes):
    row = dict(
        id=key,
        game_id="game",
        set_id="set",
        set_name="Reviewed set",
        language="en",
        collector_number="1",
        name="Ivysaur",
        edition="unlimited",
        finish="nonholo",
        variant="standard",
        publication_state="published",
        attributes={"name": "Ivysaur", "pokemon_dex": 2, "supertype": "Pokémon"},
        unresolved_fields=[],
        provenance="{}",
    )
    row.update(changes)
    return row


def test_reviewer_stability_literal_number_set_language_game_and_children():
    base = metadata()
    first = groups.build_groups([base])["groups"][0]["id"]
    children = [base, metadata("finish", finish="holo"), metadata("edition", edition="first")]
    for rows in (
        children,
        list(reversed(children)),
        children[:1],
        [{**p, "publication_state": "archived"} for p in children],
    ):
        result = groups.build_groups(rows)
        assert len(result["groups"]) == 1
        assert result["groups"][0]["id"] == first
        assert set(result["printing_to_group"]) == {p["id"] for p in rows}
    distinct = [
        base,
        metadata("zero", collector_number="001"),
        metadata("suffix", collector_number="1a"),
        metadata("set", set_id="set2"),
        metadata("game", game_id="game2"),
        metadata("language", language="ja"),
        metadata(
            "dark",
            name="Dark Ivysaur",
            collector_number="2",
            attributes={"name": "Dark Ivysaur", "pokemon_dex": 2, "supertype": "Pokémon"},
        ),
        metadata(
            "light",
            name="Light Ivysaur",
            collector_number="3",
            attributes={"name": "Light Ivysaur", "pokemon_dex": 2, "supertype": "Pokémon"},
        ),
    ]
    assert len(groups.build_groups(distinct)["groups"]) == 8


@pytest.mark.parametrize(
    "changes",
    [
        {"attributes": {"name": "Ivysaur", "pokemon_dex": 3, "supertype": "Pokémon"}},
        {"name": "ivysaur", "attributes": {"name": "ivysaur", "pokemon_dex": 2, "supertype": "Pokémon"}},
    ],
)
def test_reviewer_conflict_affects_only_its_group(changes):
    result = groups.build_groups(
        [metadata(), metadata("collision", **changes), metadata("independent", collector_number="2")]
    )
    assert len(result["groups"]) == 1
    assert result["groups"][0]["collector_number"] == "2"
    assert result["unresolved"]
    assert "p" not in result["printing_to_group"]
    assert "collision" not in result["printing_to_group"]


@pytest.mark.parametrize(
    "field,value",
    [("collector_number", ""), ("language", None), ("name", ""), ("set_id", ""), ("game_id", "")],
)
def test_reviewer_missing_identity_is_readable_unresolved(field, value):
    result = groups.build_groups([metadata(**{field: value}), metadata("independent", collector_number="2")])
    assert len(result["groups"]) == 1
    assert result["unresolved"]
    assert "p" not in result["printing_to_group"]


def test_reviewer_declared_unknown_total_exact_child_and_quantity_reference_once(cx):
    for copy in inv.copies(cx["actor"]):
        remove(cx, copy)
    child = clone(cx, finish="holo", provenance="{}")
    select(cx, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}})
    group = find(cx)
    assert group["present"] and group["established_total_quantity"] is None
    assert group["recorded_copy_count"] == group["current_copy_count"] == group["exact_variant_count"] == 0
    assert group["variant_count"] == 2
    detail = groups.detail(cx["actor"], group["id"])
    assert detail["group"]["exact_printing_owned_ids"] == []
    adapt(cx, group, "card_quantity", {"established_total_quantity": 7})
    assert find(cx)["established_total_quantity"] == 7
    assert groups.list_groups(cx["actor"], {"finish": "holo"})["groups"][0]["established_total_quantity"] == 7
    detail = groups.detail(cx["actor"], group["id"], selected_child=child)
    assert detail["group"]["established_total_quantity"] == 7
    assert all(v["established_total_quantity"] is None for v in detail["variants"])
    assert detail["selected_child"]["id"] == child


def test_reviewer_adapter_full_lifecycle_and_saved_goal_policies(cx):
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
        dict(name="Frozen exact", goal_kind="custom", policy="exact", printing_ids=[printing_id]),
    )
    exact_id = exact["changes"][0]["after"]["id"]
    definitions = {g["id"]: g["definition"] for g in inv.goals(cx["actor"])}
    group = find(cx, "c")
    mark = adapt(cx, group, "mark_owned")
    quantity = adapt(cx, group, "card_quantity", {"established_total_quantity": 3})
    with pytest.raises(inv.Conflict):
        inv.undo(cx["actor"], mark["id"])
    addition = adapt(cx, group, "add", {"duplicate_policy": "allow"}, printing_id)
    copy = addition["changes"][0]["after"]
    assert find(cx, "c")["established_total_quantity"] is None
    assert inv.goals(cx["actor"], goal_id=exact_id)[0]["satisfied"] == 1
    adapt(cx, group, "card_quantity", {"established_total_quantity": 4})
    edit = adapt(
        cx,
        group,
        "edit",
        {"id": copy["id"], "revision": copy["revision"], "attributes": {"notes": "retained"}},
    )
    assert find(cx, "c")["established_total_quantity"] == 4
    with pytest.raises(inv.Conflict):
        inv.undo(cx["actor"], quantity["id"])
    removal = adapt(cx, group, "remove_card")
    assert not find(cx, "c")["present"]
    assert not groups.detail(cx["actor"], group["id"])["group"]["current_copy_ids"]
    assert inv.one(cx["actor"], "copy", copy["id"])["state"] == "removed"
    assert inv.goals(cx["actor"], goal_id=frozen["id"])[0]["satisfied"] == 1
    assert inv.goals(cx["actor"], goal_id=exact_id)[0]["satisfied"] == 0
    inv.undo(cx["actor"], removal["id"])
    assert find(cx, "c")["present"] and find(cx, "c")["established_total_quantity"] is None
    selection, _ = select(cx)
    assert not find(cx, "c")["present"]
    assert find(cx, "c")["recorded_copy_count"] == 1 and find(cx, "c")["current_copy_count"] == 0
    assert inv.goals(cx["actor"], goal_id=exact_id)[0]["satisfied"] == 1
    assert lookup.project(cx["actor"], dict(targets="3", scope="missing"))["missing"]
    assert not lookup.project(cx["actor"], dict(targets="3", scope="missing", goal=exact_id))["missing"]
    with pytest.raises(inv.Conflict):
        inv.undo(cx["actor"], edit["id"])
    inv.undo(cx["actor"], selection["id"])
    assert find(cx, "c")["present"]
    assert {g["id"]: g["definition"] for g in inv.goals(cx["actor"])} == definitions


def test_reviewer_complete_multi_card_repeated_and_unmapped_evidence(cx):
    select(
        cx,
        {
            2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon); Ivysaur #99 (Rare); Ivysaur #44 (Uncommon)"},
            8: {"Base Set": "✓"},
            134: {"Team Rocket": "✓D Dark Vaporeon (card number and rarity unconfirmed)"},
        },
    )
    owned = groups.list_groups(cx["actor"], {"scope": "owned"})
    assert len(owned["groups"]) == 1
    assert owned["groups"][0]["collector_number"] == "44"
    assert owned["groups"][0]["established_total_quantity"] is None
    unresolved = json.dumps(owned["unresolved"], ensure_ascii=False)
    assert "99" in unresolved and "Dark Vaporeon" in unresolved
    assert "Base Set" in unresolved
    assert all(g["pokemon_dex"] not in {8, 134} for g in owned["groups"])
    assert len({g["id"] for g in owned["groups"]}) == len(owned["groups"])


def test_reviewer_owned_archived_child_never_substituted_and_public_excluded(cx):
    select(cx, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}})
    group = find(cx)
    archived = cx["by_legacy"]["a"]["id"]
    other = clone(cx, finish="holo", provenance="{}")
    inv.execute("UPDATE printings SET publication_state='archived' WHERE id=%s", [archived])
    assert find(cx)["id"] == group["id"]
    private = groups.detail(cx["actor"], group["id"], selected_child=archived)
    assert private["selected_child"]["id"] == archived
    assert private["selected_child"]["available"] is False
    assert {v["id"] for v in private["variants"]} == {archived, other}
    with pytest.raises((ValueError, Http404)):
        groups.detail(None, group["id"], selected_child=archived)
    assert groups.detail(None, group["id"], selected_child=other)["selected_child"]["id"] == other
    resolved = groups.resolve_destination(cx["actor"], "a")
    assert resolved["url"].endswith("?child=" + archived)


def test_reviewer_public_allowlist_and_private_http_no_store(cx):
    select(cx, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}})
    group = find(cx)
    raw = store.rows("SELECT * FROM printings WHERE id=%s", [cx["by_legacy"]["a"]["id"]])[0]
    attrs = json.loads(raw["attributes"])
    attrs.update(notes="PRIVATE_SENTINEL", purchase_amount="PRIVATE_SENTINEL", source_text="PRIVATE_SENTINEL")
    inv.execute("UPDATE printings SET attributes=%s WHERE id=%s", [json.dumps(attrs), raw["id"]])
    guest = cx["client"]()
    for route in ("/api/public/card-groups/", f"/api/public/card-groups/{group['id']}/"):
        response = guest.get(route)
        assert response.status_code == 200
        assert b"PRIVATE_SENTINEL" not in response.content
        data = response.json()
        serialized = json.dumps(data)
        for forbidden in (
            "recorded_copy",
            "current_copy",
            "exact_printing_owned",
            "established_total_quantity",
            "source_ids",
            "operation_ids",
            "provenance",
            "user_id",
            "copies",
            "history",
            "present",
        ):
            assert '"' + forbidden + '"' not in serialized
    for route in (
        "/api/card-groups/",
        "/api/my-card-groups/",
        f"/api/card-groups/{group['id']}/",
        "/api/species/2/card-groups/",
    ):
        response = cx["a"].get(route)
        assert response.status_code == 200
        assert "no-store" in response["Cache-Control"].split(", ")
    assert guest.get("/api/card-groups/").status_code in {302, 403}


def test_reviewer_direct_refresh_alias_ambiguity_and_no_persistent_get_changes(cx):
    select(cx, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}})
    clone(cx, provenance=json.dumps({"legacy_id": "a"}))
    current = find(cx)
    p = parity.projection(cx["actor"])
    assert "a" not in p["cards"] and "a" in p["ambiguous_card_aliases"]
    for key in ("a", "unknown-card", "dg1-unknown"):
        with pytest.raises((ValueError, Http404, inv.Conflict)):
            groups.resolve_destination(cx["actor"], key)
    before = dump(cx)
    expected = groups.detail(cx["actor"], current["id"])
    with patch(
        "requests.sessions.Session.request", side_effect=AssertionError("provider request during GET")
    ):
        for _ in range(3):
            assert groups.detail(cx["actor"], current["id"]) == expected
            assert cx["a"].get(current["url"]).status_code == 200
            assert cx["a"].get(f"/api/card-groups/{current['id']}/").status_code == 200
            assert cx["a"].get("/api/card-groups/").status_code == 200
            assert cx["a"].get("/api/my-card-groups/").status_code == 200
            assert cx["a"].get("/api/species/2/card-groups/").status_code == 200
        connection.close()
        assert groups.detail(cx["actor"], current["id"]) == expected
    assert dump(cx) == before


def test_reviewer_list_detail_pages_filter_and_checked_generation(cx):
    clone(cx, finish="holo", provenance="{}")
    select(cx, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}})
    all_rows = groups.list_groups(cx["actor"], {"page_size": "100"})
    ids = []
    for page in range(1, all_rows["total"] + 1):
        result = groups.list_groups(
            cx["actor"], {"page_size": "1", "page": str(page), "generation": str(all_rows["generation"])}
        )
        assert len(result["groups"]) == 1
        group = result["groups"][0]
        ids.append(group["id"])
        detail = groups.detail(cx["actor"], group["id"])
        assert detail["generation"] == result["generation"]
        assert all(detail["group"][key] == value for key, value in group.items())
    assert ids == [g["id"] for g in all_rows["groups"]]
    assert len(set(ids)) == all_rows["total"]
    filtered = groups.list_groups(cx["actor"], {"finish": "holo"})
    assert filtered["total"] == 1
    assert filtered["groups"][0]["variant_count"] == 2
    assert filtered["groups"][0]["present"]
    target = filtered["groups"][0]["id"]
    old_generation = all_rows["generation"]
    add(cx)
    for route in (
        f"/api/card-groups/?generation={old_generation}",
        f"/api/card-groups/{target}/?generation={old_generation}",
    ):
        assert cx["a"].get(route).status_code == 409


def test_reviewer_group_read_query_cost_does_not_scale_per_group(cx, record_testsuite_property):
    initial = {}
    for key, principal in (("private", cx["actor"]), ("public", None)):
        with CaptureQueriesContext(connection) as captured:
            groups.list_groups(principal)
        initial[key] = len(captured)
        record_testsuite_property(key + "_3_groups_queries", initial[key])
    for n in range(20):
        clone(cx, collector_number=str(100 + n), provenance="{}")
    for key, principal in (("private", cx["actor"]), ("public", None)):
        with CaptureQueriesContext(connection) as captured:
            groups.list_groups(principal, {"page_size": "100"})
        record_testsuite_property(key + "_23_groups_queries", len(captured))
        assert len(captured) <= initial[key] + 2


@pytest.mark.parametrize("reserved", ["uuid", "catalog"])
def test_reviewer_alias_collision_with_reserved_child_namespace_is_ambiguous(cx, reserved):
    original = cx["by_legacy"]["a"]["id"]
    alias = original if reserved == "uuid" else "catalog-" + original
    collided = clone(cx, key="c", provenance=json.dumps({"legacy_id": alias}))
    before = dump(cx)
    with pytest.raises((ValueError, Http404, inv.Conflict)):
        groups.resolve_destination(cx["actor"], alias)
    projection = parity.projection(cx["actor"])
    assert alias in projection["ambiguous_card_aliases"]
    assert {p["printing_id"] for p in projection["cards"].values()} == {
        p["id"] for p in inv.catalog(cx["actor"])
    }
    assert len(projection["cards"]) == 4
    assert collided in {p["printing_id"] for p in projection["cards"].values()}
    assert dump(cx) == before


def test_reviewer_reserved_group_alias_keeps_each_parity_child_destination(cx):
    from django.conf import settings
    from django.urls import clear_url_caches

    from pokemon_hunter.beta import urls

    reserved = find(cx)["id"]
    printing = cx["by_legacy"]["c"]["id"]
    inv.execute(
        "UPDATE printings SET provenance=%s WHERE id=%s", [json.dumps({"legacy_id": reserved}), printing]
    )
    before = dump(cx)
    with pytest.raises(inv.Conflict):
        groups.resolve_destination(cx["actor"], reserved)
    projection = parity.projection(cx["actor"])
    row = next(card for card in projection["cards"].values() if card["printing_id"] == printing)
    assert row["card_id"] == "catalog-" + printing
    resolved = groups.resolve_destination(cx["actor"], row["card_id"])
    assert resolved["selected_child"] == printing
    old = settings.PARITY_ENABLED
    settings.PARITY_ENABLED = True
    importlib.reload(urls)
    clear_url_caches()
    try:
        conflict = cx["a"].get("/cards/" + reserved + "/")
        assert conflict.status_code == 409, conflict.content
        redirect = cx["a"].get("/cards/" + row["card_id"] + "/")
        assert redirect.status_code == 302 and redirect.url == resolved["url"]
        assert cx["a"].get(redirect.url).status_code == 200
    finally:
        settings.PARITY_ENABLED = old
        importlib.reload(urls)
        clear_url_caches()
    assert {card["printing_id"] for card in projection["cards"].values()} == {
        card["id"] for card in inv.catalog(cx["actor"])
    }
    assert dump(cx) == before


def test_reviewer_same_slot_conflicting_literal_name_blocks_merge():
    result = groups.build_groups(
        [
            metadata(),
            metadata(
                "conflict",
                name="Venusaur",
                attributes={"name": "Venusaur", "pokemon_dex": 3, "supertype": "Pokémon"},
            ),
            metadata("independent", collector_number="2"),
        ]
    )
    assert len(result["groups"]) == 1
    assert result["groups"][0]["collector_number"] == "2"
    assert result["unresolved"]
    assert "p" not in result["printing_to_group"]


def test_reviewer_unsupported_broad_adapters_do_not_reinterpret_mutation(cx):
    kind = "set"
    current = find(cx)
    before = dump(cx)
    with pytest.raises(ValueError):
        groups.mutation_request(
            cx["actor"], current["id"], kind, {}, selected_child=cx["by_legacy"]["a"]["id"]
        )
    assert dump(cx) == before


@pytest.mark.parametrize("supertype", ["Trainer", "Energy"])
def test_reviewer_non_pokemon_card_does_not_acquire_species_group(cx, supertype):
    printing = cx["by_legacy"]["c"]
    attrs = {**printing["attributes"], "supertype": supertype}
    inv.execute("UPDATE printings SET attributes=%s WHERE id=%s", [json.dumps(attrs), printing["id"]])
    select(cx)
    add(cx)
    group = find(cx, "c")
    assert group["present"]
    assert group["pokemon_dex"] is None
    assert groups.species(cx["actor"], 3)["owned"]["total"] == 0
    assert groups.species(cx["actor"], 3)["catalog"]["total"] == 0


def test_reviewer_other_game_does_not_acquire_pokemon_species(cx):
    game = cx["by_legacy"]["c"]["game_id"]
    inv.execute("UPDATE games SET game_key='review-other-game' WHERE id=%s", [game])
    select(cx)
    add(cx)
    group = next(
        g
        for g in groups.list_groups(cx["actor"], {"scope": "owned"})["groups"]
        if g["collector_number"] == "18"
    )
    assert group["present"] and group["pokemon_dex"] is None
    assert groups.species(cx["actor"], 3)["owned"]["total"] == 0


def test_reviewer_http_group_preview_confirm_retry_and_literal_scope(cx):
    select(cx)
    current = find(cx, "c")
    route = f"/api/card-groups/{current['id']}/preview/"
    operation = str(uuid.uuid4())
    request = {
        "kind": "mark_owned",
        "request": {},
        "operation_id": operation,
        "child": cx["by_legacy"]["c"]["id"],
    }
    response = post(cx["a"], route, request)
    assert response.status_code == 200, response.content
    assert not find(cx, "c")["present"]
    preview = response.json()
    assert preview["plan"]["card_intent"]["identity"]["number"] == "18"
    confirmed = post(cx["a"], f"/api/operations/{preview['id']}/confirm/", {})
    assert confirmed.status_code == 200
    assert post(cx["a"], f"/api/operations/{preview['id']}/confirm/", {}).json() == confirmed.json()
    assert find(cx, "c")["present"]
    before = dump(cx)
    for invalid in (
        {**request, "request": {"number": "44"}, "operation_id": str(uuid.uuid4())},
        {**request, "child": cx["by_legacy"]["a"]["id"], "operation_id": str(uuid.uuid4())},
        {**request, "user_id": cx["member"].user_id, "operation_id": str(uuid.uuid4())},
        {**request, "request": {"user_id": cx["member"].user_id}, "operation_id": str(uuid.uuid4())},
    ):
        assert post(cx["a"], route, invalid).status_code in {400, 404}
    assert dump(cx) == before
    assert post(cx["b"], f"/api/operations/{preview['id']}/undo/", {}).status_code == 404
    assert post(cx["a"], f"/api/operations/{preview['id']}/undo/", {}).status_code == 200
    assert not find(cx, "c")["present"]


def test_reviewer_photo_adapter_retains_exact_selected_scope_and_requires_it(cx):
    group = find(cx)
    child = cx["by_legacy"]["a"]["id"]
    foreign = cx["by_legacy"]["c"]["id"]
    before = dump(cx)
    for request, selected in (({}, None), ({"printing_id": foreign}, child)):
        with pytest.raises(ValueError):
            groups.mutation_request(cx["actor"], group["id"], "photo", request, selected_child=selected)
    request = {"attributes": {"notes": "private retained metadata"}}
    adapted = groups.mutation_request(cx["actor"], group["id"], "photo", request, selected_child=child)
    assert adapted == {**request, "printing_id": child}
    assert dump(cx) == before


@pytest.mark.parametrize("generation", ["", "-1", "1.0", "١", "9" * 161])
def test_reviewer_detail_and_list_reject_malformed_generation_consistently(cx, generation):
    group = find(cx)
    before = dump(cx)
    for route in ("/api/card-groups/", f"/api/card-groups/{group['id']}/"):
        result = cx["a"].get(route, {"generation": generation})
        assert result.status_code == 400, result.content
    assert dump(cx) == before


def test_reviewer_detail_and_list_accept_same_zero_padded_generation(cx):
    group = find(cx)
    generation = groups.list_groups(cx["actor"])["generation"]
    before = dump(cx)
    for route in ("/api/card-groups/", f"/api/card-groups/{group['id']}/"):
        result = cx["a"].get(route, {"generation": f"000{generation}"})
        assert result.status_code == 200, result.content
        assert result.json()["generation"] == generation
    assert dump(cx) == before


@pytest.mark.parametrize("query", [{"scope": "owned"}, {"species": "3"}])
def test_reviewer_species_route_does_not_silently_override_query_scope(cx, query):
    before = dump(cx)
    result = cx["a"].get("/api/species/2/card-groups/", query)
    assert result.status_code == 400, result.content
    assert dump(cx) == before


def test_reviewer_ambiguous_legacy_route_has_readable_safe_conflict(cx):
    from django.conf import settings
    from django.urls import clear_url_caches

    from pokemon_hunter.beta import urls

    clone(cx, provenance=json.dumps({"legacy_id": "a"}))
    before = dump(cx)
    old = settings.PARITY_ENABLED
    settings.PARITY_ENABLED = True
    importlib.reload(urls)
    clear_url_caches()
    try:
        result = cx["a"].get("/cards/a/")
        assert result.status_code == 409, result.content
        assert result.json()["error"] == "Card alias is ambiguous; use the exact printing identifier"
    finally:
        settings.PARITY_ENABLED = old
        importlib.reload(urls)
        clear_url_caches()
    assert dump(cx) == before


def test_reviewer_early_private_catalog_keeps_unowned_browsing_and_direct_access(b2):
    inv.execute("UPDATE printings SET language='en'")
    before = dump(b2)
    children = {p["id"] for p in inv.catalog(b2["actor"])}
    listing = groups.list_groups(b2["actor"])
    assert listing["total"] == 3
    assert groups.list_groups(None)["total"] == 0
    seen = set()
    for group in listing["groups"]:
        detail = groups.detail(b2["actor"], group["id"])
        seen.update(v["id"] for v in detail["variants"])
        assert group["catalog_available"]
        assert all(v["available"] for v in detail["variants"])
        assert b2["a"].get(group["url"]).status_code == 200
    assert seen == children
    assert any(not row["present"] for row in listing["groups"])
    assert dump(b2) == before


@pytest.mark.parametrize("kind", ["language", "game"])
def test_reviewer_private_published_catalog_retains_supported_language_and_games(cx, kind):
    printing = cx["by_legacy"]["c"]
    if kind == "language":
        inv.execute("UPDATE printings SET language='ja' WHERE id=%s", [printing["id"]])
    else:
        inv.execute("UPDATE games SET game_key='review-other-game' WHERE id=%s", [printing["game_id"]])
    before = dump(cx)
    private = groups.list_groups(cx["actor"])
    group = next(g for g in private["groups"] if g["collector_number"] == printing["collector_number"])
    assert group["catalog_available"] and not group["present"]
    detail = groups.detail(cx["actor"], group["id"], selected_child=printing["id"])
    assert detail["selected_child"]["available"]
    assert cx["a"].get(group["url"]).status_code == 200
    public = groups.list_groups(None)
    assert group["id"] not in {g["id"] for g in public["groups"]}
    with pytest.raises(Http404):
        groups.detail(None, group["id"])
    assert dump(cx) == before


def test_reviewer_base_and_base_two_ivysaur_owned_entries_each_appear_once(cx):
    original = store.rows("SELECT * FROM catalog_sets WHERE id=%s", [cx["by_legacy"]["a"]["set_id"]])[0]
    original.update(id=str(uuid.uuid4()), name="Base Set")
    columns = list(original)
    inv.execute(
        "INSERT INTO catalog_sets ("
        + ",".join(columns)
        + ") VALUES ("
        + ",".join(["%s"] * len(columns))
        + ")",
        [original[c] for c in columns],
    )
    base = clone(cx, set_id=original["id"], collector_number="30", provenance="{}")
    clone(cx, finish="holo", provenance="{}")
    select(cx, {2: {"Base Set": "✓ Ivysaur #30 (Uncommon)", "Base Set 2": "✓ Ivysaur #44 (Uncommon)"}})
    rows = groups.species(cx["actor"], 2)["owned"]["groups"]
    assert len(rows) == 2
    assert {(r["set_name"], r["collector_number"]) for r in rows} == {
        ("Base Set", "30"),
        ("Base Set 2", "44"),
    }
    assert len({r["id"] for r in rows}) == 2
    group = next(r for r in rows if r["collector_number"] == "30")
    assert groups.detail(cx["actor"], group["id"], selected_child=base)["selected_child"]["id"] == base
