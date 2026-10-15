"""group/filter/edit contracts on disposable engineering accounts only."""

import importlib
import uuid
from unittest.mock import patch
from urllib.parse import urlencode

import pytest
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.urls import clear_url_caches
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_card_groups import clone, find
from test_cx03_review import dump
from test_effective_collection import apply, remove, select
from test_effective_collection import cx as cx
from test_migration import snapshot as snapshot
from test_sealed_catalog import e1 as e1

from pokemon_hunter.beta import card_groups, collection, effective_collection, parity, store


def adapt(cx, key, kind, request=None, child=None):
    group = find(cx, key)
    literal = card_groups.mutation_request(
        cx["actor"], group["id"], kind, request or {}, selected_child=child
    )
    return apply(cx["actor"], kind, literal)


def new_set(cx, name):
    row = store.rows("SELECT * FROM catalog_sets WHERE id=%s", [cx["by_legacy"]["a"]["set_id"]])[0]
    row.update(id=str(uuid.uuid4()), name=name)
    keys = list(row)
    collection.execute(
        "INSERT INTO catalog_sets (" + ",".join(keys) + ") VALUES (" + ",".join(["%s"] * len(keys)) + ")",
        [row[key] for key in keys],
    )
    return row["id"]


def test_effective_generation_binds_dashboard_parity_and_groups_before_and_after_mutation(cx):
    def assert_generation(expected):
        projected = effective_collection.project(cx["actor"])
        dashboard = cx["a"].get("/api/collection/").json()["effective_collection"]
        legacy = parity.projection(cx["actor"])["effective_collection"]
        grouped = cx["a"].get("/api/my-card-groups/").json()
        assert (
            projected["generation"]
            == dashboard["generation"]
            == legacy["generation"]
            == grouped["generation"]
            == expected
        )
        assert projected["user_id"] == dashboard["user_id"] == legacy["user_id"] == grouped["account_id"]

    old = collection.generation(cx["actor"])
    before = dump(cx)
    assert_generation(old)
    assert dump(cx) == before
    adapt(cx, "c", "mark_owned")
    current = collection.generation(cx["actor"])
    assert current > old
    assert_generation(current)
    assert cx["a"].get("/api/my-card-groups/", {"generation": old}).status_code == 409


def test_effective_generation_changes_during_projection_reject_before_publication(cx):
    generation = collection.generation(cx["actor"])
    read_catalog = collection.catalog
    changed = False

    def concurrent_collection_change(*args, **kwargs):
        nonlocal changed
        rows = read_catalog(*args, **kwargs)
        if not changed:
            changed = True
            apply(
                cx["actor"],
                "mark_owned",
                dict(set_name="Base Set 2", name="Venusaur", number="18", language="en"),
            )
        return rows

    with (
        patch.object(collection, "catalog", side_effect=concurrent_collection_change),
        pytest.raises(collection.Conflict, match="changed during projection"),
    ):
        effective_collection.project(cx["actor"])
    assert changed and collection.generation(cx["actor"]) > generation
    current = effective_collection.project(cx["actor"])
    assert current["generation"] == collection.generation(cx["actor"])
    assert next(row for row in current["cards"] if row["name"] == "Venusaur")["present"]


def test_complete_scoped_filters_include_owned_archived_sets_beyond_first_page(cx):
    archived_set = new_set(cx, "Z retained owned set")
    collection.execute(
        "UPDATE printings SET set_id=%s,publication_state='archived',edition='first',finish='holo',variant='stamped' WHERE id=%s",
        [archived_set, cx["by_legacy"]["a"]["id"]],
    )
    collection.execute("UPDATE catalog_sets SET publication_state='archived' WHERE id=%s", [archived_set])
    before = dump(cx)
    first = card_groups.list_groups(cx["actor"], {"scope": "owned", "page_size": "1"})
    owned = card_groups.filter_options(cx["actor"], {"scope": "owned"})
    catalog = card_groups.filter_options(cx["actor"], {"scope": "catalog"})
    assert first["total"] == 2 and len(first["groups"]) == 1
    assert first["groups"][0]["set_id"] != archived_set
    assert {row["id"] for row in owned["sets"]} == {archived_set, cx["by_legacy"]["b"]["set_id"]}
    assert archived_set not in {row["id"] for row in catalog["sets"]}
    assert owned["editions"] == ["first"] and owned["finishes"] == ["holo"]
    assert owned["variants"] == ["stamped"] and owned["languages"] == ["en"]
    assert "first" not in catalog["editions"]
    assert dump(cx) == before


def test_filter_endpoint_is_private_complete_strict_and_generation_bound(cx):
    generation = collection.generation(cx["actor"])
    before = dump(cx)
    response = cx["a"].get("/api/card-group-filters/", {"scope": "owned", "generation": generation})
    assert response.status_code == 200, response.content
    data = response.json()
    assert data["account_id"] == cx["actor"].user_id and not data["public"]
    assert data["scope"] == "owned" and data["generation"] == generation
    assert data["sets"] and "no-store" in response["Cache-Control"]
    assert cx["b"].get("/api/card-group-filters/?scope=owned").json()["sets"] == []
    for query in (
        "scope=owned&scope=catalog",
        "page=1",
        "q=Ivysaur",
        "scroll=7",
        "return=%2Fcards%2F",
        "scope=foreign",
        "generation=-1",
        "generation=1.0",
    ):
        assert cx["a"].get("/api/card-group-filters/?" + query).status_code == 400
    assert cx["client"]().get("/api/card-group-filters/").status_code in {302, 403}
    assert dump(cx) == before
    adapt(cx, "c", "mark_owned")
    assert cx["a"].get("/api/card-group-filters/", {"generation": generation}).status_code == 409
    collection.execute("UPDATE users SET state='revoked' WHERE id=%s", [cx["actor"].user_id])
    with pytest.raises(PermissionDenied):
        card_groups.filter_options(cx["actor"])


def test_all_private_group_http_reads_bind_account_without_public_leak(cx):
    group = find(cx)
    for path in (
        "/api/card-groups/",
        "/api/my-card-groups/",
        "/api/card-group-filters/",
        f"/api/card-groups/{group['id']}/",
        "/api/species/2/card-groups/",
    ):
        response = cx["a"].get(path)
        assert response.status_code == 200
        assert response.json()["account_id"] == cx["actor"].user_id
    assert "account_id" not in cx["client"]().get("/api/public/card-groups/").json()


@pytest.mark.parametrize("path", ["/cards/", "/card-library/"])
def test_return_context_preserves_list_state_and_canonical_null_child(cx, path):
    from pokemon_hunter.beta import card_group_views

    group = find(cx)
    context = path + "?" + urlencode({"q": "Ivysaur", "page": "2", "sort": "name", "scroll": "840"})
    before = dump(cx)
    response = cx["a"].get(group["url"], {"return": context})
    assert response.status_code == 200
    assert card_group_views.return_context(context) == context
    assert card_groups.detail(cx["actor"], group["id"])["selected_child"] is None
    assert cx["a"].get(f"/api/card-groups/{group['id']}/", {"return": context}).status_code == 400
    assert dump(cx) == before


@pytest.mark.parametrize(
    "context",
    [
        "https://elsewhere.test/cards/",
        "//elsewhere.test/cards/",
        " /cards/",
        "/cards/#other",
        "/collection/",
        "/cards/?q=a&q=b",
        "/cards/?scope=owned",
        "/cards/?return=/cards/",
        "/cards/?scroll=-1",
        "/cards/?scroll=10000001",
        "/cards/?page=0",
        "/cards/?sort=unknown",
        "/cards/?q=hello\n",
    ],
)
def test_unsafe_or_unsupported_return_context_rejects(env, context):
    from pokemon_hunter.beta import card_group_views

    with pytest.raises(ValueError):
        card_group_views.return_context(context)


def test_variant_filter_keeps_complete_group_and_explicit_archived_child(cx):
    base = cx["by_legacy"]["a"]["id"]
    clone(cx, finish="holo", edition="first", provenance="{}")
    adapt(cx, "a", "card_quantity", {"established_total_quantity": 7})
    collection.execute("UPDATE printings SET publication_state='archived' WHERE id=%s", [base])
    selected = card_groups.list_groups(cx["actor"], {"scope": "owned", "finish": "holo"})
    assert selected["total"] == 1
    group = selected["groups"][0]
    assert group["matching_child_ids"] == ["extra-variant"] and group["established_total_quantity"] == 7
    canonical = card_groups.detail(cx["actor"], group["id"])
    assert canonical["selected_child"] is None
    explicit = card_groups.detail(cx["actor"], group["id"], base)
    assert explicit["selected_child"]["available"] is False
    assert all(row["established_total_quantity"] is None for row in explicit["variants"])
    assert cx["a"].get(group["url"], {"child": base, "return": "/cards/"}).status_code == 200


def test_ordinary_group_mark_quantity_clear_and_explicit_child_addition(cx):
    select(cx)
    before_copies = collection.copies(cx["actor"])
    owned = adapt(cx, "c", "mark_owned")
    assert find(cx, "c")["present"] and find(cx, "c")["established_total_quantity"] is None
    assert collection.copies(cx["actor"]) == before_copies
    adapt(cx, "c", "card_quantity", {"established_total_quantity": 3})
    assert find(cx, "c")["established_total_quantity"] == 3
    adapt(cx, "c", "card_quantity", {"established_total_quantity": None})
    assert find(cx, "c")["established_total_quantity"] is None
    with pytest.raises(ValueError, match="Select an exact child"):
        adapt(cx, "c", "add", {"duplicate_policy": "allow"})
    adapt(cx, "c", "add", {"duplicate_policy": "allow"}, child=cx["by_legacy"]["c"]["id"])
    assert find(cx, "c")["recorded_copy_count"] == 1
    with pytest.raises(collection.Conflict):
        collection.undo(cx["actor"], owned["id"])


def test_copy_edit_preserves_omitted_purchase_grading_certificate_and_card_total(cx):
    added = adapt(
        cx,
        "c",
        "add",
        {
            "duplicate_policy": "allow",
            "attributes": {
                "purchase_amount": "12.50",
                "purchase_currency": "USD",
                "purchase_date": "2026-10-01",
                "grading_company": "PSA",
                "grade": "9",
                "certificate": "retained-test-certificate",
            },
        },
        child=cx["by_legacy"]["c"]["id"],
    )
    copy = added["changes"][0]["after"]
    adapt(cx, "c", "card_quantity", {"established_total_quantity": 2})
    adapt(
        cx, "c", "edit", {"id": copy["id"], "revision": copy["revision"], "attributes": {"condition": "LP"}}
    )
    edited = collection.one(cx["actor"], "copy", copy["id"])
    for field in (
        "purchase_amount",
        "purchase_currency",
        "purchase_date",
        "grading_company",
        "grade",
        "certificate",
    ):
        assert edited[field] == copy[field]
    assert edited["condition"] == "LP" and find(cx, "c")["established_total_quantity"] == 2
    second = adapt(cx, "c", "add", {"duplicate_policy": "allow"}, child=cx["by_legacy"]["c"]["id"])
    assert find(cx, "c")["established_total_quantity"] is None
    collection.undo(cx["actor"], second["id"])
    assert find(cx, "c")["established_total_quantity"] is None


def test_copy_removal_declaration_correction_and_whole_card_removal_stay_distinct(cx):
    select(cx, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}})
    copy = next(
        row for row in collection.copies(cx["actor"]) if row["printing_id"] == cx["by_legacy"]["a"]["id"]
    )
    remove(cx, copy)
    assert find(cx)["present"] and find(cx)["recorded_copy_count"] == 0
    adapt(cx, "a", "add", {"duplicate_policy": "allow"}, child=cx["by_legacy"]["a"]["id"])
    copies = collection.copies(cx["actor"])
    adapt(cx, "a", "declaration_correction")
    assert collection.copies(cx["actor"]) == copies and find(cx)["present"]
    removed = adapt(cx, "a", "remove_card")
    assert not find(cx)["present"] and find(cx)["recorded_copy_count"] == 0
    assert card_groups.detail(cx["actor"], find(cx)["id"])["history"]
    adapt(cx, "a", "add", {"duplicate_policy": "allow"}, child=cx["by_legacy"]["a"]["id"])
    assert find(cx)["present"]
    with pytest.raises(collection.Conflict):
        collection.undo(cx["actor"], removed["id"])


@pytest.mark.parametrize("parity,staging", [(False, False), (True, False), (False, True), (True, True)])
def test_cards_and_filters_routes_have_one_handler_across_supported_b2_profiles(b2, parity, staging):
    from pokemon_hunter.beta import urls

    old = settings.PARITY_ENABLED, settings.STAGING
    settings.PARITY_ENABLED, settings.STAGING = parity, staging
    importlib.reload(urls)
    clear_url_caches()
    try:
        before = dump(b2)
        assert b2["a"].get("/cards/").status_code == 200
        assert b2["a"].get("/card-library/").status_code == 200
        response = b2["a"].get("/api/card-group-filters/")
        assert response.status_code == 200 and response.json()["scope"] == "catalog"
        assert dump(b2) == before
    finally:
        settings.PARITY_ENABLED, settings.STAGING = old
        importlib.reload(urls)
        clear_url_caches()
