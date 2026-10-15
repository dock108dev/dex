"""Independent adversarial contracts, on disposable engineering roots only."""

import json
import sqlite3
import uuid
from unittest.mock import patch

import pytest
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b2 import post
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_cx03_review import clone, find
from test_effective_collection import add, apply, select
from test_effective_collection import cx as cx
from test_migration import snapshot as snapshot
from test_sealed_catalog import e1 as e1

from pokemon_hunter.beta import card_groups as groups
from pokemon_hunter.beta import collection as inv
from pokemon_hunter.beta import parity


def dump(cx):
    with sqlite3.connect(cx["root"] / "inventory.db") as db:
        return list(db.iterdump())


def preview(cx, group, kind, request, *, child=None, operation_id=None):
    return post(
        cx["a"],
        f"/api/card-groups/{group['id']}/preview/",
        {
            "kind": kind,
            "request": request,
            "operation_id": operation_id or str(uuid.uuid4()),
            **({"child": child} if child else {}),
        },
    )


def confirm(cx, pending):
    assert pending.status_code == 200, pending.content
    assert not pending.json()["plan"]["errors"], pending.content
    result = post(cx["a"], f"/api/operations/{pending.json()['id']}/confirm/", {})
    assert result.status_code == 200, result.content
    return result.json()


def test_review_owned_scope_does_not_leak_unowned_groups_or_infer_variant_totals(cx):
    select(cx, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}})
    clone(cx, edition="first", finish="holo")
    owned = cx["a"].get("/api/my-card-groups/").json()
    library = cx["a"].get("/api/card-groups/").json()
    assert owned["total"] == 1 < library["total"]
    group = owned["groups"][0]
    assert group["name"] == "Ivysaur" and group["present"]
    assert group["established_total_quantity"] is None
    assert group["recorded_copy_count"] == 1 and group["current_copy_count"] == 1
    assert library["total"] == 3  # The extra finish is not an extra card tile.
    confirm(cx, preview(cx, group, "card_quantity", {"established_total_quantity": 7}))
    detail = cx["a"].get(f"/api/card-groups/{group['id']}/").json()
    assert detail["group"]["established_total_quantity"] == 7
    assert detail["selected_child"] is None
    assert all(v["established_total_quantity"] is None for v in detail["variants"])
    filtered = cx["a"].get("/api/my-card-groups/?edition=first&page_size=1").json()
    assert filtered["total"] == 1 and filtered["pages"] == 1
    assert filtered["groups"][0]["matching_child_ids"]
    assert filtered["groups"][0]["established_total_quantity"] == 7
    assert cx["a"].get("/api/my-card-groups/?scope=owned").status_code == 400


@pytest.mark.parametrize("field", ["tab", "return", "scroll", "child", "account"])
def test_review_ui_state_never_becomes_an_api_filter(cx, field):
    before = dump(cx)
    response = cx["a"].get("/api/my-card-groups/", {field: "/cards/?tab=library"})
    assert response.status_code == 400
    assert dump(cx) == before


def test_review_unresolved_species_evidence_never_creates_a_card_tile(cx):
    select(cx, {2: {"Base Set 2": "✓"}})
    owned = cx["a"].get("/api/my-card-groups/").json()
    assert owned["groups"] == [] and owned["total"] == 0
    assert owned["unresolved"]
    assert any(row.get("evidence", {}).get("pokemon_dex") == 2 for row in owned["unresolved"])
    assert not any("groups" in row for row in owned["unresolved"])


def test_review_mark_owned_requires_no_copy_and_lost_response_retry_is_idempotent(cx):
    select(cx)
    group = find(cx, "c")
    before_copies = inv.copies(cx["actor"])
    operation_id = str(uuid.uuid4())
    first = preview(cx, group, "mark_owned", {}, operation_id=operation_id)
    assert not groups.detail(cx["actor"], group["id"])["group"]["present"]
    pending = first.json()
    assert preview(cx, group, "mark_owned", {}, operation_id=operation_id).json() == pending
    saved = confirm(cx, first)
    assert cx["a"].get(f"/api/operations/{saved['id']}/").json() == saved
    assert confirm(cx, first) == saved
    assert inv.copies(cx["actor"]) == before_copies
    current = groups.detail(cx["actor"], group["id"])
    assert current["group"]["present"]
    assert current["group"]["established_total_quantity"] is None
    assert current["group"]["current_copy_count"] == 0


def test_review_exact_copy_cannot_be_added_without_explicit_supported_child(cx):
    group = find(cx)
    before = dump(cx)
    result = preview(cx, group, "add", {"duplicate_policy": "allow"})
    assert result.status_code == 400
    assert dump(cx) == before
    foreign = cx["by_legacy"]["c"]["id"]
    result = preview(cx, group, "add", {"duplicate_policy": "allow"}, child=foreign)
    assert result.status_code == 404
    assert dump(cx) == before
    child = cx["by_legacy"]["a"]["id"]
    pending = preview(cx, group, "add", {"duplicate_policy": "allow"}, child=child)
    saved = confirm(cx, pending)
    assert saved["changes"][0]["after"]["printing_id"] == child


def test_review_partial_copy_metadata_edit_preserves_closed_advanced_fields_and_total(cx):
    group = find(cx)
    copy_row = groups.detail(cx["actor"], group["id"])["copies"][0]
    advanced = {
        "purchase_amount": "123.4500",
        "purchase_currency": "USD",
        "purchase_date": "2026-10-01",
        "grading_company": "PSA",
        "grade": "9",
        "certificate": "PRIVATE-CERTIFICATE",
    }
    apply(
        cx["actor"],
        "edit",
        {"id": copy_row["id"], "revision": copy_row["revision"], "attributes": advanced},
    )
    confirm(cx, preview(cx, group, "card_quantity", {"established_total_quantity": 2}))
    current = inv.one(cx["actor"], "copy", copy_row["id"])
    saved = confirm(
        cx,
        preview(
            cx,
            group,
            "edit",
            {"id": current["id"], "revision": current["revision"], "attributes": {"condition": "LP"}},
            child=current["printing_id"],
        ),
    )
    assert saved["state"] == "confirmed"
    edited = inv.one(cx["actor"], "copy", current["id"])
    assert edited["condition"] == "LP"
    for field in advanced:
        assert edited[field] == current[field]
    assert groups.detail(cx["actor"], group["id"])["group"]["established_total_quantity"] == 2


def test_review_copy_remove_card_remove_and_new_addition_have_distinct_authority(cx):
    select(cx, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}})
    group = find(cx)
    row = groups.detail(cx["actor"], group["id"])["copies"][0]
    confirm(cx, preview(cx, group, "card_quantity", {"established_total_quantity": 3}))
    removed = confirm(cx, preview(cx, group, "remove", {"id": row["id"], "revision": row["revision"]}))
    after = groups.detail(cx["actor"], group["id"])
    assert after["group"]["present"] and after["group"]["established_total_quantity"] is None
    assert after["copies"] == [] and len(after["history"]) == 1
    assert post(cx["a"], f"/api/operations/{removed['id']}/undo/", {}).status_code == 200
    assert groups.detail(cx["actor"], group["id"])["group"]["established_total_quantity"] is None
    card_removal = confirm(cx, preview(cx, group, "remove_card", {}))
    assert not groups.detail(cx["actor"], group["id"])["group"]["present"]
    add(cx, "a")
    assert groups.detail(cx["actor"], group["id"])["group"]["present"]
    assert post(cx["a"], f"/api/operations/{card_removal['id']}/undo/", {}).status_code == 409


def test_review_stale_preview_does_not_confirm_and_foreign_status_does_not_leak(cx):
    group = find(cx)
    pending = preview(cx, group, "card_quantity", {"established_total_quantity": 5})
    assert pending.status_code == 200 and not pending.json()["plan"]["errors"]
    add(cx, "a")
    before = dump(cx)
    operation_id = pending.json()["id"]
    assert post(cx["a"], f"/api/operations/{operation_id}/confirm/", {}).status_code == 409
    assert groups.detail(cx["actor"], group["id"])["group"]["established_total_quantity"] is None
    assert cx["b"].get(f"/api/operations/{operation_id}/").status_code == 404
    assert post(cx["b"], f"/api/operations/{operation_id}/confirm/", {}).status_code == 404
    assert dump(cx) == before


def test_review_group_read_navigation_remains_readonly_and_never_calls_providers(cx):
    group = find(cx)
    before = dump(cx)
    with (
        patch("requests.sessions.Session.request", side_effect=AssertionError("provider request")),
        patch("httpx.post", side_effect=AssertionError("provider request")),
    ):
        for path in (
            "/cards/",
            "/card-library/",
            "/api/my-card-groups/",
            "/api/card-groups/",
            group["url"],
            f"/api/card-groups/{group['id']}/",
        ):
            assert cx["a"].get(path).status_code == 200, path
    assert dump(cx) == before
    serialized = json.dumps(cx["client"]().get("/api/public/card-groups/").json())
    for private in ("recorded_copy_count", "purchase_amount", "photo_references", "operation_ids"):
        assert private not in serialized


def test_review_filter_options_are_complete_account_bound_readonly_and_archived_aware(cx):
    select(cx, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}})
    group = find(cx)
    child = cx["by_legacy"]["a"]
    inv.execute("UPDATE printings SET publication_state='archived'")
    before = dump(cx)
    owned = cx["a"].get("/api/card-group-filters/?scope=owned").json()
    assert owned["sets"] == [{"id": child["set_id"], "name": "Base Set 2"}]
    assert owned["account_id"] == cx["actor"].user_id
    assert owned["languages"] == ["en"]
    assert cx["a"].get("/api/my-card-groups/?page_size=1&page=100").json()["groups"] == []
    assert cx["a"].get("/api/card-group-filters/?scope=owned").json() == owned
    assert cx["a"].get("/api/card-group-filters/?scope=catalog").json()["sets"] == []
    member = cx["b"].get("/api/card-group-filters/?scope=owned").json()
    assert member["sets"] == [] and member["account_id"] == cx["member"].user_id
    assert "no-store" in cx["a"].get("/api/card-group-filters/")["Cache-Control"]
    assert dump(cx) == before
    assert cx["client"]().get("/api/card-group-filters/").status_code in {302, 403}
    confirm(cx, preview(cx, group, "card_quantity", {"established_total_quantity": 2}))
    assert (
        cx["a"].get(f"/api/card-group-filters/?scope=owned&generation={owned['generation']}").status_code
        == 409
    )


@pytest.mark.parametrize(
    "destination",
    [
        "https://example.com/cards/",
        "//example.com/cards/",
        "/collection/",
        "/cards/#private",
        "/cards/?q=a&q=b",
        "/cards/?scope=owned",
        "/cards/?child=secret",
        "/cards/?return=/cards/",
        "/cards/?page=0",
        "/cards/?scroll=-1",
        "/cards/?scroll=10000001",
        "/cards/?scroll=١",
        "/cards/\n",
    ],
)
def test_review_canonical_return_context_rejects_external_ambiguous_or_invalid_state(cx, destination):
    before = dump(cx)
    assert cx["a"].get(find(cx)["url"], {"return": destination}).status_code == 400
    assert dump(cx) == before


def test_review_canonical_return_is_ui_only_and_does_not_select_a_child(cx):
    group = find(cx)
    destination = "/card-library/?q=Ivysaur&page=2&page_size=1&sort=name&scroll=345"
    before = dump(cx)
    assert cx["a"].get(group["url"], {"return": destination}).status_code == 200
    assert cx["a"].get(f"/api/card-groups/{group['id']}/", {"return": destination}).status_code == 400
    assert cx["a"].get(f"/api/card-groups/{group['id']}/").json()["selected_child"] is None
    assert dump(cx) == before


def test_review_actual_dashboard_group_and_optional_guide_bind_same_authority(cx):
    """Actual HTTP shape, not a frontend mock with assumed generation fields."""
    group = find(cx)
    for _ in range(2):
        before = dump(cx)
        dashboard = cx["a"].get("/api/collection/").json()["effective_collection"]
        detail = cx["a"].get(f"/api/card-groups/{group['id']}/").json()
        prices = parity.projection(cx["actor"])["effective_collection"]
        assert type(dashboard.get("generation")) is int
        assert dashboard["generation"] == detail["generation"] == prices["generation"]
        assert dashboard["user_id"] == detail["account_id"] == prices["user_id"]
        assert dump(cx) == before
        confirm(cx, preview(cx, group, "card_quantity", {"established_total_quantity": 2}))
