"""Synthetic collection workflow, isolation, transaction, retry and preservation checks."""

import importlib
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest
from test_b1 import env as env
from test_migration import snapshot as snapshot

from pokemon_hunter.beta import collection as service
from pokemon_hunter.inventory import connect


@pytest.fixture
def b2(env):
    from django.conf import settings
    from django.db import connection
    from django.urls import clear_url_caches

    from pokemon_hunter.beta import urls

    connection.close()
    with connect(env["root"] / "inventory.db") as db:
        service.initialize(db)
    original_limit = settings.DATA_UPLOAD_MAX_MEMORY_SIZE
    settings.DATA_UPLOAD_MAX_MEMORY_SIZE = 2_000_000
    settings.B2_ENABLED = True
    importlib.reload(urls)
    clear_url_caches()
    env["actor"] = env["store"].principal(env["owner"].pk)
    env["member"] = env["store"].principal(env["second"].pk)
    env["catalog"] = service.catalog(env["actor"])
    yield env
    settings.DATA_UPLOAD_MAX_MEMORY_SIZE = original_limit
    settings.B2_ENABLED = False
    importlib.reload(urls)
    clear_url_caches()


def post(c, url, data):
    return c.post(
        url,
        json.dumps(data),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=c.cookies["dex_b1_csrf"].value,
    )


def preview(b2, kind, request, client=None, id=None):
    return post(
        client or b2["a"],
        "/api/operations/preview/",
        {"kind": kind, "request": request, "operation_id": id or str(uuid.uuid4())},
    )


def apply(b2, kind, request, client=None):
    c = client or b2["a"]
    r = preview(b2, kind, request, c)
    assert r.status_code == 200, r.content
    assert not r.json()["plan"]["errors"], r.json()["plan"]["errors"]
    op = r.json()
    result = post(c, f"/api/operations/{op['id']}/confirm/", {})
    assert result.status_code == 200, result.content
    return result.json()


def add(b2, client=None, **attrs):
    return apply(
        b2,
        "add",
        {"printing_id": b2["catalog"][0]["id"], "attributes": attrs, "duplicate_policy": "allow"},
        client,
    )


def test_manual_duplicate_retry_and_exact_unknown_attributes(b2):
    a = b2["a"]
    before = a.get("/api/inventory/").json()["copies"]
    request = {
        "printing_id": b2["catalog"][0]["id"],
        "duplicate_policy": "allow",
        "attributes": {
            "purchase_amount": "0.100001",
            "purchase_currency": "USD",
            "purchase_date": "2026-09-27",
            "notes": "<script>not markup</script>",
        },
    }
    id = str(uuid.uuid4())
    first = preview(b2, "add", request, id=id).json()
    assert preview(b2, "add", request, id=id).json() == first
    assert len(a.get("/api/inventory/").json()["copies"]) == len(before)
    op = post(a, f"/api/operations/{first['id']}/confirm/", {}).json()
    assert post(a, f"/api/operations/{first['id']}/confirm/", {}).json() == op
    created = op["changes"][0]["after"]
    assert created["purchase_amount"] == "0.100001" and created["condition"] is None
    assert json.loads(created["provisional_identity"])["unresolved_fields"]
    assert len(service.copies(b2["actor"])) == len(before) + 1
    add(b2)
    assert len(service.copies(b2["actor"])) == len(before) + 2
    assert preview(b2, "add", {**request, "duplicate_policy": "reject"}).json()["plan"]["errors"]
    skipped = apply(b2, "add", {**request, "duplicate_policy": "skip"})
    assert not skipped["changes"]
    assert preview(b2, "add", {**request, "attributes": {"notes": "different"}}, id=id).status_code == 409


def test_undo_edit_remove_and_stale_updates(b2):
    created = add(b2)
    c = created["changes"][0]["after"]
    edit = apply(b2, "edit", {"id": c["id"], "revision": 0, "attributes": {"notes": "new note"}})
    assert (
        preview(b2, "edit", {"id": c["id"], "revision": 0, "attributes": {"notes": "stale"}}).status_code
        == 409
    )
    assert post(b2["a"], f"/api/operations/{created['id']}/undo/", {}).status_code == 409
    removed = apply(b2, "remove", {"id": c["id"], "revision": 1})
    assert c["id"] not in {r["id"] for r in service.copies(b2["actor"])}
    url = f"/api/operations/{removed['id']}/undo/"
    first = post(b2["a"], url, {}).json()
    assert post(b2["a"], url, {}).json() == first
    restored = service.one(b2["actor"], "copy", c["id"])
    assert restored["notes"] == "new note" and restored["revision"] == 3
    # Even changing back to earlier text must not permit an older undo (ABA).
    assert post(b2["a"], f"/api/operations/{edit['id']}/undo/", {}).status_code == 409
    second = add(b2)
    before = {r["id"] for r in service.copies(b2["actor"])}
    assert post(b2["a"], f"/api/operations/{second['id']}/undo/", {}).status_code == 200
    assert {r["id"] for r in service.copies(b2["actor"])} == before - {second["changes"][0]["after"]["id"]}
    assert post(b2["a"], f"/api/operations/{second['id']}/confirm/", {}).json()["state"] == "undone"


def test_binders_dependency_undo_rename_and_empty_removal(b2):
    binder = apply(b2, "binder", {"name": "Private binder"})
    b = binder["changes"][0]["after"]
    op = add(b2, binder_id=b["id"])
    assert post(b2["a"], f"/api/operations/{binder['id']}/undo/", {}).status_code == 409
    assert preview(b2, "binder_remove", {"id": b["id"], "revision": 0}).status_code == 409
    rename = apply(b2, "binder_edit", {"id": b["id"], "revision": 0, "name": "Renamed"})
    assert post(b2["a"], f"/api/operations/{rename['id']}/undo/", {}).status_code == 200
    assert service.binders(b2["actor"])[0]["name"] == "Private binder"
    assert post(b2["a"], f"/api/operations/{op['id']}/undo/", {}).status_code == 200
    removal = apply(b2, "binder_remove", {"id": b["id"], "revision": 2})
    assert service.binders(b2["actor"]) == []
    assert post(b2["a"], f"/api/operations/{removal['id']}/undo/", {}).status_code == 200


def test_goals_never_clone_inventory_and_frozen_membership(b2):
    before = service.copies(b2["actor"])
    sid = b2["catalog"][0]["set_id"]
    for kind, policy in [("set", "catalog"), ("set", "exact"), ("vintage", "catalog"), ("custom", "catalog")]:
        apply(
            b2,
            "goal",
            {
                "name": kind + policy,
                "goal_kind": kind,
                "set_id": sid,
                "policy": policy,
                "printing_ids": [p["id"] for p in b2["catalog"]],
            },
        )
    assert service.copies(b2["actor"]) == before
    goals = {g["name"]: g for g in service.goals(b2["actor"])}
    assert goals["setcatalog"]["total"] == 3 and goals["setcatalog"]["satisfied"] == 2
    assert goals["setexact"]["satisfied"] == 0
    assert goals["vintagecatalog"]["total"] == 251 and goals["vintagecatalog"]["satisfied"] == 1
    assert goals["customcatalog"]["satisfied"] == 2  # Dark card not excluded globally.
    service.execute("UPDATE printings SET attributes='{}'")
    assert service.goals(b2["actor"]) == list(sorted(goals.values(), key=lambda g: (g["name"], g["id"])))
    g = goals["setcatalog"]
    removal = apply(b2, "goal_remove", {"id": g["id"], "revision": 0})
    assert post(b2["a"], f"/api/operations/{removal['id']}/undo/", {}).status_code == 200


def test_set_review_atomic_undo_preserves_preexisting(b2):
    before = service.copies(b2["actor"])
    req = {"set_id": b2["catalog"][0]["set_id"], "duplicate_policy": "skip"}
    p = preview(b2, "set", req).json()
    assert len(p["plan"]["checklist"]) == 3
    assert sum(r["existing_copies"] for r in p["plan"]["checklist"]) == 2
    assert sum(r["proposed_copies"] for r in p["plan"]["checklist"]) == 1
    assert all(r["unresolved"] for r in p["plan"]["checklist"])
    op = post(b2["a"], f"/api/operations/{p['id']}/confirm/", {}).json()
    assert len(service.copies(b2["actor"])) == 3
    assert post(b2["a"], f"/api/operations/{op['id']}/undo/", {}).status_code == 200
    assert service.copies(b2["actor"]) == before


def test_stale_preview_and_catalog_changes_require_review(b2):
    req = {"printing_id": b2["catalog"][0]["id"], "duplicate_policy": "allow"}
    p = preview(b2, "add", req).json()
    add(b2)
    assert post(b2["a"], f"/api/operations/{p['id']}/confirm/", {}).status_code == 409
    q = preview(b2, "add", req).json()
    service.execute("UPDATE printings SET edition='changed' WHERE id=%s", [req["printing_id"]])
    assert post(b2["a"], f"/api/operations/{q['id']}/confirm/", {}).status_code == 409


def test_interrupted_transaction_rolls_back_and_retries(b2):
    req = {"set_id": b2["catalog"][0]["set_id"], "duplicate_policy": "allow"}
    p = service.preview(b2["actor"], "set", req, str(uuid.uuid4()))
    before = service.copies(b2["actor"])
    original = service.write_row
    calls = []

    def interrupt(*args, **kwargs):
        original(*args, **kwargs)
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError("synthetic interrupted transaction")

    with patch.object(service, "write_row", side_effect=interrupt), pytest.raises(RuntimeError):
        service.confirm(b2["actor"], p["id"])
    assert service.copies(b2["actor"]) == before
    assert service.operation(b2["actor"], p["id"])["state"] == "preview"
    op = service.confirm(b2["actor"], p["id"])
    assert len(service.copies(b2["actor"])) == len(before) + 3
    with patch.object(service, "write_row", side_effect=RuntimeError("undo interrupted")):
        # Add undo uses DELETE, so exercise rollback after the first deletion instead.
        original_execute = service.execute

        def fail(sql, params=()):
            original_execute(sql, params)
            if sql.startswith("DELETE FROM owned_copies"):
                raise RuntimeError("interrupted undo")

        with patch.object(service, "execute", side_effect=fail), pytest.raises(RuntimeError):
            service.undo(b2["actor"], op["id"])
    assert len(service.copies(b2["actor"])) == len(before) + 3
    service.undo(b2["actor"], op["id"])
    assert service.copies(b2["actor"]) == before


def test_parallel_confirmation_and_edit_conflicts(b2):
    from django.db import connections

    p = service.preview(
        b2["actor"],
        "add",
        {"printing_id": b2["catalog"][0]["id"], "duplicate_policy": "allow"},
        str(uuid.uuid4()),
    )

    def confirm():
        try:
            return service.confirm(b2["actor"], p["id"])
        finally:
            connections.close_all()

    before = len(service.copies(b2["actor"]))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: confirm(), range(2)))
    assert results[0] == results[1]
    assert len(service.copies(b2["actor"])) == before + 1
    c = results[0]["changes"][0]["after"]
    p1 = service.preview(
        b2["actor"],
        "edit",
        {"id": c["id"], "revision": 0, "attributes": {"notes": "first"}},
        str(uuid.uuid4()),
    )
    p2 = service.preview(
        b2["actor"],
        "edit",
        {"id": c["id"], "revision": 0, "attributes": {"notes": "second"}},
        str(uuid.uuid4()),
    )
    service.confirm(b2["actor"], p1["id"])
    with pytest.raises(service.Conflict):
        service.confirm(b2["actor"], p2["id"])


def test_export_import_round_trip_and_undo_in_empty_account(b2):
    binder = apply(b2, "binder", {"name": "Roundtrip"})["changes"][0]["after"]
    add(
        b2,
        binder_id=binder["id"],
        condition="LP",
        purchase_amount="123.450",
        purchase_currency="USD",
        notes="roundtrip",
        grading_company="Synthetic",
        grade="7",
        certificate="test-only",
    )
    apply(b2, "goal", {"name": "Vintage", "goal_kind": "vintage"})
    apply(
        b2,
        "goal",
        {"name": "Exact", "goal_kind": "set", "set_id": b2["catalog"][0]["set_id"], "policy": "exact"},
    )
    exported = b2["a"].get("/api/export/").json()
    req = {"format": "json", "text": json.dumps(exported), "duplicate_policy": "allow"}
    result = apply(b2, "import", req, b2["b"])
    imported = b2["b"].get("/api/export/").json()
    assert imported["schema"] == service.SCHEMA
    assert len(imported["copies"]) == len(exported["copies"])
    by_source = {c["source_copy_id"]: c for c in imported["copies"]}
    for original in exported["copies"]:
        new = by_source[original["id"]]
        for key in (
            "printing_id",
            "provisional_identity",
            "first_edition_selected",
            "condition",
            "purchase_amount",
            "purchase_currency",
            "purchase_date",
            "notes",
            "grade",
            "certificate",
            "grading_company",
            "unresolved_fields",
            "attributes",
        ):
            assert new[key] == original[key], key
        assert new["id"] != original["id"] and new["user_id"] != original["user_id"]
    assert [g["definition"] for g in imported["goals"]] == [g["definition"] for g in exported["goals"]]
    assert imported["vintage_251"] == exported["vintage_251"]
    assert preview(b2, "import", req, b2["b"]).json()["id"] == result["id"]
    assert post(b2["b"], f"/api/operations/{result['id']}/confirm/", {}).json() == result
    assert post(b2["b"], f"/api/operations/{result['id']}/undo/", {}).status_code == 200
    empty = b2["b"].get("/api/export/").json()
    assert empty["copies"] == empty["binders"] == empty["goals"] == []
    assert b2["a"].get("/api/export/").json() == exported


@pytest.mark.parametrize("amount", ["-1", "NaN", "Infinity", "1e3", "1.1234567", 1.1])
def test_bad_money_stays_visible_and_atomic(b2, amount):
    req = {
        "format": "json",
        "text": json.dumps(
            [{"printing_id": b2["catalog"][0]["id"], "purchase_amount": amount, "purchase_currency": "USD"}]
        ),
        "duplicate_policy": "allow",
    }
    # JSON non-string numbers must not be silently converted to binary-derived decimal.
    p = preview(b2, "import", req)
    assert p.status_code == 200
    assert p.json()["plan"]["errors"]
    assert post(b2["a"], f"/api/operations/{p.json()['id']}/confirm/", {}).status_code == 400


def test_csv_errors_duplicate_policy_and_import_stable_id(b2):
    pid = b2["catalog"][0]["id"]
    req = {
        "format": "csv",
        "text": f"printing_id,notes,purchase_amount,purchase_currency\n{pid},valid,1.23,USD\nunknown,bad,1.23,USD\n",
        "duplicate_policy": "allow",
    }
    p = preview(b2, "import", req, b2["b"]).json()
    assert len(p["plan"]["errors"]) == 1 and p["plan"]["errors"][0].startswith("Row 2")
    assert post(b2["b"], f"/api/operations/{p['id']}/confirm/", {}).status_code == 400
    assert service.copies(b2["member"]) == []
    req["text"] = f"printing_id,notes\n{pid},one\n{pid},two\n"
    p = preview(b2, "import", {**req, "duplicate_policy": "reject"}, b2["b"]).json()
    assert p["plan"]["errors"]
    op = apply(b2, "import", req, b2["b"])
    assert len(service.copies(b2["member"])) == 2
    assert preview(b2, "import", req, b2["b"]).json()["id"] == op["id"]


def test_every_new_feature_is_session_scoped_and_rechecked(b2):
    for own, other in [(b2["a"], b2["b"]), (b2["b"], b2["a"])]:
        binder = apply(b2, "binder", {"name": "Private"}, own)["changes"][0]["after"]
        goal = apply(b2, "goal", {"name": "Private", "goal_kind": "vintage"}, own)["changes"][0]["after"]
        copy = add(b2, own)["changes"][0]["after"]
        for resource, row in [("binders", binder), ("goals", goal), ("inventory", copy)]:
            assert other.get(f"/api/{resource}/{row['id']}/").status_code == 404
        for kind, request in [
            ("binder_edit", {"id": binder["id"], "revision": 0, "name": "stolen"}),
            ("binder_remove", {"id": binder["id"], "revision": 0}),
            ("goal_remove", {"id": goal["id"], "revision": 0}),
            ("edit", {"id": copy["id"], "revision": 0, "attributes": {"notes": "stolen"}}),
            ("remove", {"id": copy["id"], "revision": 0}),
            (
                "add",
                {
                    "printing_id": copy["printing_id"],
                    "duplicate_policy": "allow",
                    "attributes": {"binder_id": binder["id"]},
                },
            ),
        ]:
            assert preview(b2, kind, request, other).status_code == 404
        for kind, request in [
            ("add", {"printing_id": copy["printing_id"], "duplicate_policy": "allow"}),
            ("set", {"set_id": b2["catalog"][0]["set_id"], "duplicate_policy": "allow"}),
            (
                "import",
                {"format": "csv", "text": "printing_id\n" + copy["printing_id"], "duplicate_policy": "allow"},
            ),
        ]:
            op = preview(b2, kind, request, own).json()
            path = f"/api/operations/{op['id']}/"
            assert other.get(path).status_code == 404
            assert post(other, path + "confirm/", {}).status_code == 404
            assert post(other, path + "undo/", {}).status_code == 404
        for path in ("/api/collection/", "/api/binders/", "/api/goals/", "/api/export/"):
            response = other.get(path + "?user_id=" + copy["user_id"], HTTP_X_USER_ID=copy["user_id"])
            assert copy["id"] not in response.content.decode()
            assert binder["id"] not in response.content.decode()
            assert goal["id"] not in response.content.decode()
    op = preview(b2, "binder", {"name": "queued"}).json()
    b2["accounts"].revoke(b2["owner"])
    assert post(b2["a"], f"/api/operations/{op['id']}/confirm/", {}).status_code == 302
    from django.core.exceptions import PermissionDenied

    with pytest.raises(PermissionDenied):
        service.confirm(b2["actor"], op["id"])


def test_new_route_auth_csrf_and_no_legacy_write_bypass(b2):
    for path in [
        "/goals/",
        "/settings/",
        "/api/collection/",
        "/api/catalog/",
        "/api/binders/",
        "/api/goals/",
        "/api/export/",
        "/api/operations/guessed/",
    ]:
        assert b2["client"]().get(path).status_code == 302
    assert b2["a"].post("/api/operations/preview/", "{}", content_type="application/json").status_code == 403
    copy = service.copies(b2["actor"])[0]
    assert post(b2["a"], f"/api/inventory/{copy['id']}/", {"notes": "bypass"}).status_code == 405
    assert preview(b2, "binder", {"name": "bad", "user_id": "forged"}).status_code == 400
    home = b2["a"].get("/")
    assert home.status_code == 200
    assert b'<script src="/collection-assets/collection.js" defer></script>' in home.content


def test_stale_import_can_be_reviewed_again_and_goal_rules_are_validated(b2):
    request = {"format": "csv", "text": "printing_id\n" + b2["catalog"][0]["id"], "duplicate_policy": "allow"}
    first = preview(b2, "import", request).json()
    add(b2)
    assert post(b2["a"], f"/api/operations/{first['id']}/confirm/", {}).status_code == 409
    refreshed = preview(b2, "import", request).json()
    assert refreshed["id"] == first["id"]
    assert post(b2["a"], f"/api/operations/{first['id']}/confirm/", {}).status_code == 200
    apply(b2, "goal", {"name": "Vintage", "goal_kind": "vintage"})
    document = b2["a"].get("/api/export/").json()
    goal = document["goals"][0]
    # A file must not quietly redefine the named Vintage exclusion policy.
    from pokemon_hunter.migration import digest, encode

    dark = next(p for p in b2["catalog"] if not p["attributes"]["dex_eligible"])
    goal["definition"]["items"][0]["printing_ids"].append(dark["id"])
    goal["version"] = digest(encode(goal["definition"]).encode())
    response = preview(
        b2, "import", {"format": "json", "text": json.dumps(document), "duplicate_policy": "allow"}, b2["b"]
    )
    assert response.status_code == 400
    assert response.json()["error"] == "Invalid request. Check the fields and import format."
    assert service.copies(b2["member"]) == []


def test_isolated_initialization_marker_and_no_owner_environment_upgrade(tmp_path):
    from pokemon_hunter.beta.cli import initialize

    root = tmp_path / "new-b2-root"
    initialize(root, b2=True)
    assert (root / "B2_ISOLATED").is_file()
    with connect(root / "inventory.db") as db:
        assert db.execute("SELECT version FROM schema_versions ORDER BY version").fetchall()[-1][0] == 2
    before = (root / "inventory.db").read_bytes()
    with pytest.raises(FileExistsError):
        initialize(root, b2=True)
    assert (root / "inventory.db").read_bytes() == before


def test_copy_level_unresolved_fields_cannot_satisfy_exact_goal(b2):
    copy = service.copies(b2["actor"])[0]
    service.execute(
        "UPDATE printings SET unresolved_fields='[]',edition='unlimited',finish='nonholo',variant='standard' WHERE id=%s",
        [copy["printing_id"]],
    )
    apply(
        b2,
        "goal",
        {
            "name": "Known variant",
            "goal_kind": "custom",
            "policy": "exact",
            "printing_ids": [copy["printing_id"]],
        },
    )
    assert service.goals(b2["actor"])[0]["satisfied"] == 0
    op = apply(b2, "add", {"printing_id": copy["printing_id"], "duplicate_policy": "allow"})
    assert service.goals(b2["actor"])[0]["satisfied"] == 1
    assert post(b2["a"], f"/api/operations/{op['id']}/undo/", {}).status_code == 200
    assert service.goals(b2["actor"])[0]["satisfied"] == 0


def test_invalid_provisional_flag_is_a_row_error(b2):
    response = preview(
        b2,
        "import",
        {
            "format": "json",
            "text": json.dumps([{"provisional_identity": "{}", "first_edition_selected": 3}]),
            "duplicate_policy": "allow",
        },
    )
    assert response.status_code == 200
    assert "first_edition_selected" in response.json()["plan"]["errors"][0]
