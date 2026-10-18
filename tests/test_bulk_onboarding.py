"""Bulk-entry mutations use disposable test accounts exclusively."""

import json
from datetime import timedelta

import pytest
from django.http import Http404
from django.utils import timezone
from test_collection_intents import identity
from test_effective_collection import add, apply, b2, b3, b4, card, cx, e1, env, select, snapshot

from pokemon_hunter.beta import bulk_input as adapter
from pokemon_hunter.beta import collection as inv
from pokemon_hunter.beta import collection_drafts as drafts
from pokemon_hunter.beta import effective_collection, store

__all__ = ["b2", "b3", "b4", "cx", "e1", "env", "snapshot"]


@pytest.fixture
def bulk(cx):
    drafts.initialize()
    drafts.initialize()
    return cx


def row(cx, key="c", **extra):
    p = cx["by_legacy"][key]
    return dict(row_id=key, printing_id=p["id"], **extra)


def save(cx, rows, defaults=None, **kw):
    return drafts.save(cx["actor"], dict(rows=rows, defaults=defaults or {}), **kw)


def commit(cx, rows, defaults=None):
    draft = save(cx, rows, defaults, new_batch=True)
    preview = drafts.review(cx["actor"], draft["id"], draft["revision"])
    assert not preview["operation"]["plan"]["errors"]
    return drafts.confirm(cx["actor"], draft["id"], draft["revision"])


def test_bulk_single_transaction_projection_and_replay(bulk):
    cx = bulk
    select(cx)
    before = inv.generation(cx["actor"])
    draft = save(cx, [row(cx, quantity=2)])
    op = drafts.review(cx["actor"], draft["id"], 1)["operation"]
    assert not op["plan"]["errors"]
    assert not card(effective_collection.project(cx["actor"]), "Venusaur", "18")["present"]
    done = drafts.confirm(cx["actor"], draft["id"], 1)
    projected = card(effective_collection.project(cx["actor"]), "Venusaur", "18")
    assert projected["present"] and len(projected["current_copy_ids"]) == 2
    assert done["plan"]["reviewed_effects"]["added_species"] == [3]
    assert inv.generation(cx["actor"]) == before + 1
    assert drafts.confirm(cx["actor"], draft["id"], 1) == done
    assert save(cx, [row(cx, quantity=2)])["confirmed_operation_id"] == done["id"]
    inv.undo(cx["actor"], done["id"])
    assert not card(effective_collection.project(cx["actor"]), "Venusaur", "18")["present"]


def test_provisional_binding_resolution_removal_and_untrusted_import(bulk):
    cx = bulk
    select(cx)
    op = commit(cx, [dict(row_id="p", set="Base Set 2", number="18", keep_unknown=True)])
    copy = op["changes"][0]["after"]
    assert copy["printing_id"] is None
    current = card(effective_collection.project(cx["actor"]), "Venusaur", "18")
    assert current["present"] and current["current_copy_ids"] == [copy["id"]]
    assert current["exact_printing_owned_ids"] == []
    total = apply(cx["actor"], "card_quantity", {**identity(cx, "c"), "established_total_quantity": 2})
    apply(cx["actor"], "remove_card", identity(cx, "c"))
    assert inv.one(cx["actor"], "copy", copy["id"])["state"] == "removed"
    assert not card(effective_collection.project(cx["actor"]), "Venusaur", "18")["present"]
    with pytest.raises(inv.Conflict):
        inv.undo(cx["actor"], total["id"])


def test_provisional_preserves_original_admission_after_source_boundary(bulk):
    cx = bulk
    op = commit(cx, [dict(row_id="p", set="Base Set 2", number="18", keep_unknown=True)])
    copy = op["changes"][0]["after"]
    select(cx)
    apply(cx["actor"], "resolve", dict(id=copy["id"], revision=0, printing_id=cx["by_legacy"]["c"]["id"]))
    current = card(effective_collection.project(cx["actor"]), "Venusaur", "18")
    assert not current["present"] and current["recorded_copy_count"] == 1


def test_broad_noop_total_and_copy_invalidation(bulk):
    cx = bulk
    select(cx)
    commit(cx, [row(cx, action="mark_owned")])
    commit(cx, [row(cx, action="set_total", total="5")])
    noop = save(cx, [row(cx, action="mark_owned")])
    assert noop["state"] == "confirmed"  # Exact reupload recovers the first receipt.
    op = commit(cx, [row(cx, quantity=2)])
    assert (
        card(effective_collection.project(cx["actor"]), "Venusaur", "18")["established_total_quantity"]
        is None
    )
    inv.undo(cx["actor"], op["id"])
    assert (
        card(effective_collection.project(cx["actor"]), "Venusaur", "18")["established_total_quantity"]
        is None
    )


@pytest.mark.parametrize("number,expected", [("018", "18"), ("18", "18")])
def test_adapters_equivalent_and_padding(bulk, number, expected):
    cx = bulk
    p = cx["by_legacy"]["c"]
    defaults = dict(set="Base Set 2", language="en")
    a = adapter.envelope(dict(rows=[dict(row_id="r", number=number)], defaults=defaults))
    b = adapter.envelope(dict(source="paste", text=number, defaults=defaults))
    c = adapter.envelope(
        dict(
            source="csv",
            defaults=defaults,
            text=adapter.export_rows(
                [dict(row_id="r", action="add_copies", set="Base Set 2", number=number, language="en")]
            ),
        )
    )
    norms = [adapter.normalize(cx["actor"], data)["rows"][0] for data in (a, b, c)]
    assert all(r["printing_id"] == p["id"] and r["quantity"] == 1 and not r["errors"] for r in norms)
    assert norms[0]["matched_number"] == expected


@pytest.mark.parametrize("text", ["3-1", "RC1-RC3", "1 x0", "1 x1.5", "1 X2", "1,,2", "1-2001", "-1"])
def test_bad_paste(text):
    with pytest.raises(ValueError):
        adapter.parse_paste(text, {})


def test_grammar_modes_and_quoted_literals():
    assert [r["number"] for r in adapter.parse_paste("001-003 x2; 8", {})] == ["001", "002", "003", "8"]
    assert adapter.parse_paste('"RC1-RC3"', {})[0]["number"] == "RC1-RC3"
    assert adapter.parse_paste("1 xunknown", {"action": "set_total"})[0]["total"] == "unknown"
    for text, defaults in [("1 x2", {"action": "mark_owned"}), ("1", {"action": "set_total"})]:
        with pytest.raises(ValueError):
            adapter.parse_paste(text, defaults)


@pytest.mark.parametrize(
    "extra",
    [
        dict(quantity=0),
        dict(quantity=True),
        dict(quantity="1.5"),
        dict(certificate="one", quantity=2),
        dict(grading_company="PSA"),
        dict(purchase_amount="2"),
        dict(binder_id="foreign"),
        dict(edition="shadowless"),
        dict(action="mark_owned", condition="NM"),
        dict(action="set_total", total="2"),
        dict(notes="x" * 2001),
    ],
)
def test_malformed_rows_not_hidden_by_skip(bulk, extra):
    cx = bulk
    select(cx)
    raw = row(cx, **extra, duplicate_decision="skip")
    draft = save(cx, [raw])
    preview = drafts.review(cx["actor"], draft["id"], 1)
    assert preview["operation"]["plan"]["errors"]
    with pytest.raises(inv.Conflict):
        drafts.confirm(cx["actor"], draft["id"], 1)


def test_stale_review_cancel_and_cas(bulk):
    cx = bulk
    draft = save(cx, [row(cx)])
    drafts.review(cx["actor"], draft["id"], 1)
    add(cx, "a")
    with pytest.raises(inv.Conflict):
        drafts.confirm(cx["actor"], draft["id"], 1)
    drafts.review(cx["actor"], draft["id"], 1)
    revised = save(cx, [row(cx, quantity=2)], key=draft["id"], revision=1)
    with pytest.raises(inv.Conflict):
        drafts.confirm(cx["actor"], draft["id"], 1)
    with pytest.raises(inv.Conflict):
        save(cx, [row(cx)], key=draft["id"], revision=1)
    preview = drafts.review(cx["actor"], draft["id"], revised["revision"])["operation"]
    drafts.cancel(cx["actor"], draft["id"], revised["revision"])
    with pytest.raises(inv.Conflict):
        inv.confirm(cx["actor"], preview["id"])


def test_expiry_receipt_reupload_reorder_and_new_batch(bulk):
    cx = bulk
    rows = [row(cx), row(cx, "a")]
    draft = save(cx, rows)
    assert save(cx, list(reversed(rows)))["id"] == draft["id"]
    drafts.review(cx["actor"], draft["id"], 1)
    op = drafts.confirm(cx["actor"], draft["id"], 1)
    inv.execute(
        "UPDATE collection_drafts SET expires_at=%s WHERE id=%s",
        [(timezone.now() - timedelta(days=8)).isoformat(), draft["id"]],
    )
    drafts.purge_expired()
    assert save(cx, rows)["confirmed_operation_id"] == op["id"]
    another = save(cx, rows, new_batch=True)
    assert another["id"] != draft["id"]
    inv.execute(
        "UPDATE collection_drafts SET expires_at=%s WHERE id=%s",
        [(timezone.now() - timedelta(days=8)).isoformat(), another["id"]],
    )
    with pytest.raises(inv.Conflict):
        drafts.review(cx["actor"], another["id"], 1)


def test_multi_action_conflicts_and_overlap(bulk):
    cx = bulk
    data = adapter.envelope(dict(source="paste", text="18,18", defaults={"set": "Base Set 2"}))
    assert adapter.normalize(cx["actor"], data)["rows"][1]["errors"]
    data = adapter.envelope(dict(rows=[row(cx), dict(row(cx, action="mark_owned"), row_id="other")]))
    assert all(r["errors"] for r in adapter.normalize(cx["actor"], data)["rows"])


def test_no_foreign_account_and_atomic_rollback(bulk, monkeypatch):
    cx = bulk
    draft = save(cx, [row(cx)])
    with pytest.raises(Http404):
        drafts.get(cx["member"], draft["id"])
    op = drafts.review(cx["actor"], draft["id"], 1)["operation"]
    original = inv.write_row

    def fail(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("engineering fault")

    monkeypatch.setattr(inv, "write_row", fail)
    before = inv.copies(cx["actor"])
    with pytest.raises(RuntimeError):
        drafts.confirm(cx["actor"], draft["id"], 1)
    assert inv.copies(cx["actor"]) == before
    assert inv.operation(cx["actor"], op["id"])["state"] == "preview"


def test_reused_row_identity_different_content_needs_explicit_batch(bulk):
    cx = bulk
    draft = save(cx, [row(cx, quantity=1)])
    for rows, defaults in [([row(cx, quantity=2)], {}), ([row(cx, quantity=1)], {"condition": "NM"})]:
        with pytest.raises(inv.Conflict):
            save(cx, rows, defaults)
    assert save(cx, [row(cx, quantity=1)])["id"] == draft["id"]
    assert save(cx, [row(cx, quantity=2)], new_batch=True)["id"] != draft["id"]


def test_stale_catalog_and_binder_require_explicit_review(bulk):
    cx = bulk
    binder = apply(cx["actor"], "binder", {"name": "Engineering binder"})["changes"][0]["after"]
    draft = save(cx, [row(cx, binder_id=binder["id"])])
    drafts.review(cx["actor"], draft["id"], 1)
    inv.execute("UPDATE binders SET revision=revision+1 WHERE id=%s", [binder["id"]])
    with pytest.raises(inv.Conflict):
        drafts.confirm(cx["actor"], draft["id"], 1)
    drafts.review(cx["actor"], draft["id"], 1)
    p = cx["by_legacy"]["c"]
    inv.execute(
        "UPDATE catalog_sets SET catalog_version=%s WHERE id=%s", ["new-reviewed-version", p["set_id"]]
    )
    with pytest.raises(inv.Conflict):
        drafts.confirm(cx["actor"], draft["id"], 1)


def test_frozen_goals_unchanged_and_conflict_undo_is_atomic(bulk):
    cx = bulk
    before = inv.goals(cx["actor"])
    op = commit(cx, [row(cx), row(cx, "a")])
    assert [(g["id"], g["definition"], g["version"]) for g in inv.goals(cx["actor"])] == [
        (g["id"], g["definition"], g["version"]) for g in before
    ]
    copy = op["changes"][-1]["after"]
    apply(
        cx["actor"], "edit", dict(id=copy["id"], revision=0, attributes={"notes": "later engineering work"})
    )
    snapshot = inv.copies(cx["actor"])
    with pytest.raises(inv.Conflict):
        inv.undo(cx["actor"], op["id"])
    assert inv.copies(cx["actor"]) == snapshot


def test_2000_limit_and_no_splitting(bulk):
    cx = bulk
    data = adapter.envelope(dict(rows=[row(cx, quantity=2000)]))
    assert adapter.normalize(cx["actor"], data)["expanded"] == 2000
    with pytest.raises(ValueError):
        adapter.envelope(dict(rows=[dict(row(cx), row_id=str(n)) for n in range(2001)]))
    data = adapter.envelope(dict(rows=[row(cx, quantity=2000), row(cx, "a", quantity=1)]))
    with pytest.raises(ValueError, match="Expanded"):
        adapter.normalize(cx["actor"], data)
    with pytest.raises(ValueError):
        adapter.parse_csv("x" * 1500001)


def test_100_open_drafts_and_expiry_does_not_renew(bulk):
    cx = bulk
    first = save(cx, [], new_batch=True)
    lease = first["expires_at"]
    assert drafts.get(cx["actor"], first["id"])["expires_at"] == lease
    for _ in range(99):
        save(cx, [], new_batch=True)
    with pytest.raises(ValueError, match="100 open"):
        save(cx, [], new_batch=True)
    inv.execute(
        "UPDATE collection_drafts SET expires_at=%s WHERE id=%s",
        [(timezone.now() - timedelta(days=8)).isoformat(), first["id"]],
    )
    assert drafts.get(cx["actor"], first["id"])["state"] == "expired"
    assert save(cx, [], new_batch=True)


def test_csv_bad_headers_repeated_ids_encoding_and_slash_alias():
    for text in [
        "schema,row_id,action,quantity,quantity\n",
        "schema,row_id,action,secret\n",
        "schema,row_id,action\nwrong,r,add_copies\n",
        "schema,row_id,action\ndex-onboarding-v1,r,mark_owned,extra\n",
        "schema,row_id,action,notes\ndex-onboarding-v1,r,add_copies,=FORMULA()\n",
    ]:
        with pytest.raises(ValueError):
            adapter.parse_csv(text)
    for number, expected in [("001", ["001/165"]), ("1", ["001/165"]), ("001/999", [])]:
        assert [
            g["collector_number"] for g in adapter.number_matches(number, [{"collector_number": "001/165"}])
        ] == expected
    encoded = adapter.export_rows([dict(row_id="r", action="add_copies", notes="=literal text")])
    assert adapter.parse_csv(encoded)[0]["notes"] == "=literal text"


def test_http_auth_logout_revocation_and_safe_errors(bulk):
    from test_b2 import post

    cx = bulk
    client = cx["a"]
    assert client.get("/add-many/").status_code == 200
    response = post(client, "/api/bulk/save/", {"input": dict(rows=[row(cx)])})
    assert response.status_code == 200
    draft = response.json()["draft"]
    assert cx["b"].get(f"/api/bulk/drafts/{draft['id']}/").status_code == 404
    assert client.get("/api/bulk/save/").status_code == 405
    assert (
        client.post("/api/bulk/save/", json.dumps({"input": {}}), content_type="application/json").status_code
        == 403
    )
    client.logout()
    assert client.get(f"/api/bulk/drafts/{draft['id']}/").status_code == 302
    cx["second"].is_active = False
    cx["second"].save()
    from django.core.exceptions import PermissionDenied

    with pytest.raises(PermissionDenied):
        drafts.get(cx["member"], draft["id"])


def test_same_identity_exclusion_is_not_a_conflict(bulk):
    cx = bulk
    data = adapter.envelope(
        dict(rows=[row(cx), dict(row(cx, action="mark_owned", included=False), row_id="excluded")])
    )
    assert not adapter.normalize(cx["actor"], data)["rows"][0]["errors"]


def test_untrusted_provisional_json_never_grants_group_presence(bulk):
    cx = bulk
    select(cx)
    op = commit(cx, [dict(row_id="p", set="Base Set 2", number="18", keep_unknown=True)])
    original = op["changes"][0]["after"]
    inv.undo(cx["actor"], op["id"])
    unbound = apply(cx["actor"], "photo", dict(provisional_identity=original["provisional_identity"]))
    assert not card(effective_collection.project(cx["actor"]), "Venusaur", "18")["present"]
    # Untrusted JSON stays free text: it cannot restrict ordinary unidentified-copy resolution either.
    select(cx)
    unbound_copy = unbound["changes"][0]["after"]
    apply(
        cx["actor"],
        "resolve",
        dict(id=unbound_copy["id"], revision=0, printing_id=cx["by_legacy"]["a"]["id"]),
    )
    assert not card(effective_collection.project(cx["actor"]), "Ivysaur", "44")["present"]


def test_confirm_cancel_race_and_parallel_confirmation(bulk):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from django.db import connections

    cx = bulk
    draft = save(cx, [row(cx)])
    op = drafts.review(cx["actor"], draft["id"], 1)["operation"]
    gate = Barrier(2)

    def race(action):
        connections.close_all()
        try:
            gate.wait(timeout=5)
            return getattr(drafts, action)(cx["actor"], draft["id"], 1)["state"]
        except inv.Conflict:
            return "conflict"
        finally:
            connections.close_all()

    before = inv.generation(cx["actor"])
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(race, ["confirm", "cancel"]))
    result = drafts.get(cx["actor"], draft["id"])
    if result["state"] == "confirmed":
        assert inv.generation(cx["actor"]) == before + 1
        assert outcomes == ["confirmed", "confirmed"]
    else:
        assert result["state"] == "cancelled" and "conflict" in outcomes
        assert inv.generation(cx["actor"]) == before
        with pytest.raises(inv.Conflict):
            inv.confirm(cx["actor"], op["id"])
    second = save(cx, [row(cx)], new_batch=True)
    drafts.review(cx["actor"], second["id"], 1)

    def confirm(_):
        connections.close_all()
        try:
            return drafts.confirm(cx["actor"], second["id"], 1)
        finally:
            connections.close_all()

    before = inv.generation(cx["actor"])
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(confirm, range(2)))
    assert results[0] == results[1] and inv.generation(cx["actor"]) == before + 1


def test_literal_unknown_notes_from_safe_csv_and_drawer(bulk):
    cx = bulk
    for raw in [
        dict(row(cx, notes="unknown"), literal_text=["notes"]),
        adapter.parse_csv(adapter.export_rows([dict(row(cx, notes="unknown"), action="add_copies")]))[0],
    ]:
        norm = adapter.normalize(cx["actor"], adapter.envelope(dict(rows=[raw])))
        assert not norm["rows"][0]["errors"]
        assert norm["rows"][0]["attributes"]["notes"] == "unknown"


def test_upload_alias_survives_corrections_and_confirmed_expiry(bulk):
    cx = bulk
    original = [row(cx)]
    draft = save(cx, original)
    updated = save(cx, [row(cx, notes="reviewed correction")], key=draft["id"], revision=1)
    drafts.review(cx["actor"], draft["id"], updated["revision"])
    op = drafts.confirm(cx["actor"], draft["id"], updated["revision"])
    inv.execute(
        "UPDATE collection_drafts SET expires_at=%s WHERE id=%s",
        [(timezone.now() - timedelta(days=8)).isoformat(), draft["id"]],
    )
    drafts.purge_expired()
    assert save(cx, original)["confirmed_operation_id"] == op["id"]


def test_intentional_batch_retry_uses_same_identity(bulk):
    cx = bulk
    identity = str(__import__("uuid").uuid4())
    first = save(cx, [row(cx)], new_batch=True, batch_identity=identity)
    assert save(cx, [row(cx)], new_batch=True, batch_identity=identity)["id"] == first["id"]
    with pytest.raises(inv.Conflict):
        save(cx, [row(cx, quantity=2)], new_batch=True, batch_identity=identity)


def test_provisional_group_detail_editor_and_trainer_boundary(bulk):
    from pokemon_hunter.beta import card_groups

    cx = bulk
    select(cx)
    op = commit(cx, [dict(row_id="p", set="Base Set 2", number="18", keep_unknown=True)])
    copy = op["changes"][0]["after"]
    group = op["plan"]["bulk"]["rows"][0]["group_id"]
    detail = card_groups.detail(cx["actor"], group)
    assert detail["group"]["recorded_copy_count"] == 1
    assert detail["copies"][0]["id"] == copy["id"]
    assert detail["copies"][0]["display_identity"]["name"] == "Venusaur"
    dashboard = cx["a"].get("/api/collection/").json()
    assert (
        next(c for c in dashboard["copies"] if c["id"] == copy["id"])["display_identity"]["name"]
        == "Venusaur"
    )
    adapted = card_groups.mutation_request(
        cx["actor"], group, "resolve", dict(id=copy["id"], revision=0, printing_id=cx["by_legacy"]["c"]["id"])
    )
    apply(cx["actor"], "resolve", adapted)
    assert card(effective_collection.project(cx["actor"]), "Venusaur", "18")["present"]
    trainer = cx["by_legacy"]["b"]
    inv.execute(
        "UPDATE printings SET attributes=%s WHERE id=%s",
        [json.dumps(dict(name="Engineering Trainer", supertype="Trainer", pokemon_dex=1)), trainer["id"]],
    )
    commit(cx, [row(cx, "b", keep_unknown=True)])
    projected = effective_collection.project(cx["actor"])
    assert not projected["species"]["1"]["present"]
    assert card(projected, "Engineering Trainer", "67")["present"]


def test_mixed_set_rows_override_default_set_context(bulk):
    cx = bulk
    p = cx["by_legacy"]["c"]
    data = adapter.envelope(dict(rows=[row(cx)], defaults={"set_id": "some-other-default-set"}))
    assert not adapter.normalize(cx["actor"], data)["rows"][0]["errors"]
    data = adapter.envelope(
        dict(
            rows=[dict(row_id="set", set=p["set_name"], number=p["collector_number"])],
            defaults={"set_id": "some-other-default-set"},
        )
    )
    assert not adapter.normalize(cx["actor"], data)["rows"][0]["errors"]


def test_preview_rows_match_effective_result_including_existing_counts(bulk):
    cx = bulk
    select(cx)
    draft = save(cx, [row(cx, quantity=2)])
    preview = drafts.review(cx["actor"], draft["id"], 1)["operation"]
    expected = preview["plan"]["bulk"]["rows"][0]["resulting"]
    drafts.confirm(cx["actor"], draft["id"], 1)
    actual = card(effective_collection.project(cx["actor"]), "Venusaur", "18")
    assert expected == dict(
        present=actual["present"],
        established_total_quantity=actual["established_total_quantity"],
        recorded_copy_count=actual["recorded_copy_count"],
        current_copy_count=len(actual["current_copy_ids"]),
        exact_variant_count=len(actual["exact_printing_owned_ids"]),
    )


def test_revocation_cleans_draft_inputs_preserves_receipt_mapping(bulk):
    from django.core.exceptions import PermissionDenied

    cx = bulk
    draft = save(cx, [row(cx, notes="private engineering draft")])
    cx["accounts"].revoke(cx["owner"])
    with pytest.raises(PermissionDenied):
        drafts.get(cx["actor"], draft["id"])
    result = store.rows("SELECT state,input_json FROM collection_drafts WHERE id=%s", [draft["id"]])[0]
    assert result["state"] == "cancelled" and "private engineering draft" not in result["input_json"]
    assert store.rows("SELECT draft_id FROM collection_replays WHERE draft_id=%s", [draft["id"]])


def test_parse_endpoint_is_read_only_and_appendable(bulk):
    from test_b2 import post

    cx = bulk
    before = inv.generation(cx["actor"])
    parsed = post(
        cx["a"],
        "/api/bulk/parse/",
        {"input": dict(source="paste", text="018 x2", defaults={"set": "Base Set 2"})},
    )
    assert parsed.status_code == 200
    assert parsed.json()["normalized"]["rows"][0]["matched_number"] == "18"
    assert inv.generation(cx["actor"]) == before
    assert not drafts.listed(cx["actor"])


def test_reordered_paste_expansions_have_one_replay_identity(bulk):
    cx = bulk
    defaults = {"set": "Base Set 2"}
    a = adapter.envelope(dict(source="paste", text="18,44 x2,67", defaults=defaults))
    b = adapter.envelope(dict(source="paste", text=" 67 ; 18 ; 44 x2 ", defaults=defaults))
    assert adapter.fingerprint(a) == adapter.fingerprint(b)
    first = drafts.save(cx["actor"], dict(source="paste", text="18,44 x2,67", defaults=defaults))
    assert (
        drafts.save(cx["actor"], dict(source="paste", text="67,18,44 x2", defaults=defaults))["id"]
        == first["id"]
    )


def test_valid_large_manual_draft_is_not_limited_by_ordinary_small_requests(bulk):
    from test_b2 import post

    cx = bulk
    rows = [
        dict(row(cx, notes="n" * 1000, duplicate_decision="different"), row_id="large-" + str(n))
        for n in range(2000)
    ]
    response = post(cx["a"], "/api/bulk/save/", {"input": dict(rows=rows)})
    assert response.status_code == 200, response.content[:200]
    assert len(response.json()["draft"]["input_json"]["rows"]) == 2000


def test_large_transport_allowance_is_manual_only(bulk):
    import asyncio

    from pokemon_hunter.beta.asgi import BULK_BODY_LIMIT, SCAN_BODY_LIMIT, BoundedBodyApplication

    async def exercise(path, size):
        sent = []

        async def app(scope, receive, send):
            await send({"type": "http.response.start", "status": 204, "headers": []})

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(message):
            sent.append(message)

        await BoundedBodyApplication(app)(
            {
                "type": "http",
                "path": path,
                "method": "POST",
                "client": ("127.0.0.1", 12345),
                "headers": [(b"host", b"127.0.0.1:8011"), (b"content-length", str(size).encode())],
            },
            receive,
            send,
        )
        return sent[0]["status"]

    assert asyncio.run(exercise("/api/bulk/save/", 2_100_000)) == 204
    assert asyncio.run(exercise("/api/bulk/parse/", BULK_BODY_LIMIT + 1)) == 413
    assert asyncio.run(exercise("/api/operations/preview/", 2_100_000)) == 413
    assert asyncio.run(exercise("/api/scans/", SCAN_BODY_LIMIT + 1)) == 413


def test_provisional_resolution_cannot_cross_game_or_set_identity(bulk):
    import uuid

    cx = bulk
    op = commit(cx, [dict(row_id="p", set="Base Set 2", number="18", keep_unknown=True)])
    copy = op["changes"][0]["after"]
    p = cx["by_legacy"]["c"]
    game = store.rows("SELECT * FROM games WHERE id=%s", [p["game_id"]])[0]
    game.update(id=str(uuid.uuid4()), game_key="engineering-other-game", name="Engineering other game")
    set_row = store.rows("SELECT * FROM catalog_sets WHERE id=%s", [p["set_id"]])[0]
    set_row.update(id=str(uuid.uuid4()), game_id=game["id"])
    printing = store.rows("SELECT * FROM printings WHERE id=%s", [p["id"]])[0]
    printing.update(id=str(uuid.uuid4()), set_id=set_row["id"])
    for table, data in [("games", game), ("catalog_sets", set_row), ("printings", printing)]:
        inv.execute(
            "INSERT INTO "
            + table
            + " ("
            + ",".join(data)
            + ") VALUES ("
            + ",".join(["%s"] * len(data))
            + ")",
            list(data.values()),
        )
    with pytest.raises(ValueError, match="original game"):
        inv.preview(
            cx["actor"],
            "resolve",
            dict(id=copy["id"], revision=0, printing_id=printing["id"]),
            str(uuid.uuid4()),
        )
    assert inv.one(cx["actor"], "copy", copy["id"])["printing_id"] is None
