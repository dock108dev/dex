"""Collection intent on disposable engineering accounts; never acquires content."""

import time
import uuid

import pytest
from perf04_helpers import enable_read_fixture
from test_b1 import env as env
from test_b2 import apply
from test_b2 import b2 as b2
from test_discovery_catalog import visual as visual
from test_migration import snapshot as snapshot

from pokemon_hunter.beta import collection, discovery, listing_check, shopping_intent


def selected(actor, **overrides):
    return discovery.Choices(
        collection_intent=True,
        intent="missing",
        species=65,
        generation=collection.generation(actor),
        query="Alakazam",
        budget="87.25",
        prefer_vintage=True,
        focus="kanto",
        **overrides,
    )


def received(actor, choice, title="Alakazam Alakazam Gengar two card lot", scope=None):
    run = discovery.Run(
        str(uuid.uuid4()),
        discovery._owner(actor, "session"),
        choice,
        scope,
        ["Alakazam"],
        state="complete",
        acquired_at=time.monotonic(),
        raws=[
            dict(
                itemId="v1|123456789012|0",
                title=title,
                buyingOptions=["FIXED_PRICE"],
                price=dict(value="10", currency="USD"),
            )
        ],
    )
    discovery._runs[run.id] = run
    return run


def test_targets_are_indexed_authorized_and_no_printings(visual, monkeypatch):
    enable_read_fixture(visual, monkeypatch)
    actor = visual["actor"]
    monkeypatch.setattr(collection, "catalog", lambda *a, **k: pytest.fail("catalog projection"))
    result = shopping_intent.targets(actor, {"scope": "kanto"})
    assert any(r == dict(species=65, name="Alakazam") for r in result["targets"])
    assert all(r["species"] <= 151 for r in result["targets"])
    assert all(r["species"] > 151 for r in shopping_intent.targets(actor, {"scope": "johto"})["targets"])
    with pytest.raises(collection.Conflict):
        shopping_intent.targets(actor, {"generation": str(result["generation"] + 1)})


@pytest.mark.parametrize("title", ["Alakazam Alakazam Gengar two card lot", "Unknown mystery contents", ""])
def test_receipt_is_not_fit_or_value_and_intent_survives(visual, monkeypatch, title):
    enable_read_fixture(visual, monkeypatch)
    actor = visual["actor"]
    run = received(actor, selected(actor), title)
    result = discovery.status(actor, "session", run.id, received=True)
    assert result["choices"]["species"] == 65
    assert result["choices"]["budget"] == "87.25"
    assert result["choices"]["currency"] == "USD"
    assert result["choices"]["prefer_vintage"]
    assert len(result["results"]) == 1
    row = result["results"][0]
    assert row["discovery_kind"] == "unassessed"
    assert not row.get("reference") and not row.get("comparison")
    assert "Any qualifying era" in result["scope_label"] or "any qualifying era" in result["scope_label"]
    assert run.counts["total"] == 0


def test_review_and_original_lease_keep_intent_then_reject_changed_generation(visual, monkeypatch):
    enable_read_fixture(visual, monkeypatch)
    actor = visual["actor"]
    run = received(actor, selected(actor))
    row = discovery.status(actor, "session", run.id, received=True)["results"][0]
    value = listing_check.candidate(actor, "session", run.id, row["id"])
    assert value["context"]["choices"]["species"] == 65
    assert value["context"]["choices"]["budget"] == "87.25"
    created = run.created
    apply(visual, "add", {"printing_id": visual["catalog"][1]["id"], "duplicate_policy": "allow"})
    with pytest.raises(collection.Conflict):
        discovery.status(actor, "session", run.id, received=True)
    with pytest.raises(collection.Conflict):
        listing_check.candidate(actor, "session", run.id, row["id"])
    assert run.created == created


def test_invalid_collection_intent_cannot_dispatch():
    for change in (
        {"species": None},
        {"generation": None},
        {"focus": "rares"},
        {"english_vintage": True},
        {"goal_id": "x"},
        {"intent": "deals"},
    ):
        raw = dict(collection_intent=True, intent="missing", species=65, generation=0)
        with pytest.raises(ValueError):
            discovery.Choices(**dict(raw, **change))


def test_frozen_goal_retains_version_and_rejects_changed_goal(visual, monkeypatch):
    from pokemon_hunter.beta import goal_hunts

    goal = apply(visual, "goal", dict(name="Species goal", goal_kind="original151"))["changes"][0]["after"]
    enable_read_fixture(visual, monkeypatch)
    actor = visual["actor"]
    result = shopping_intent.targets(actor, {"goal": goal["id"], "version": goal["version"]})
    assert any(r["species"] == 65 for r in result["targets"])
    choice = selected(actor, goal_id=goal["id"], goal_version=goal["version"])
    run = received(actor, choice, scope=goal_hunts.snapshot(actor, goal["id"]))
    assert (
        discovery.status(actor, "session", run.id, received=True)["choices"]["goal_version"]
        == goal["version"]
    )
    with pytest.raises(collection.Conflict):
        shopping_intent.targets(actor, {"goal": goal["id"], "version": "0" * 64})
    collection.execute("UPDATE collection_goals SET version=%s WHERE id=%s", ["0" * 64, goal["id"]])
    from pokemon_hunter.beta.catalog_read_build import Unavailable

    with pytest.raises((collection.Conflict, Unavailable)):
        discovery.status(actor, "session", run.id, received=True)


def test_search_admission_uses_one_species_without_catalog_projection(visual, monkeypatch):
    enable_read_fixture(visual, monkeypatch)
    actor = visual["actor"]
    from types import SimpleNamespace

    monkeypatch.setattr(
        discovery.ebay_hunts,
        "configuration",
        lambda: (
            SimpleNamespace(environment="production"),
            {"EBAY_CLIENT_ID": "engineering", "EBAY_CLIENT_SECRET": "engineering"},
        ),
    )
    monkeypatch.setattr(discovery, "_authorize", lambda *a: None)
    monkeypatch.setattr(discovery, "_worker", lambda *a: None)
    monkeypatch.setattr(
        discovery, "_candidate_data", lambda *a, **k: pytest.fail("broad candidate projection")
    )
    raw = selected(actor).model_dump(mode="json")
    raw["query"] = "Gengar arbitrary user words"
    result = discovery.start(actor, "session", raw)
    run = discovery._runs[result["run_id"]]
    assert run.choices.query == "Alakazam"
    assert len(run.queries) == 1 and "vintage" not in run.queries[0].lower()
    assert run.choices.budget == discovery.Decimal("87.25")


def test_intent_query_profile(visual, monkeypatch):
    import json
    from pathlib import Path
    from types import SimpleNamespace

    from django.db import connection

    from pokemon_hunter.beta import goal_hunts, navigation

    goal = apply(visual, "goal", dict(name="Species goal", goal_kind="original151"))["changes"][0]["after"]
    enable_read_fixture(visual, monkeypatch)
    actor = visual["actor"]
    binding = navigation.binding(SimpleNamespace(user=visual["owner"], session=visual["a"].session))[
        "navigation_binding"
    ]
    run = received(
        actor,
        selected(actor, goal_id=goal["id"], goal_version=goal["version"]),
        scope=goal_hunts.snapshot(actor, goal["id"]),
    )
    run.owner = discovery._owner(actor, binding)
    handle = discovery.discovery_listing.result_handle(run.id, run.raws[0]["itemId"])
    profiles = {}
    for route in (
        f"/api/shopping/listing/candidate/?discovery_run={run.id}&item_id={handle}",
        f"/shopping/?species=65&goal={goal['id']}&version={goal['version']}",
    ):
        queries = []

        def capture(execute, sql, params, many, context):
            queries.append(sql)
            return execute(sql, params, many, context)

        with connection.execute_wrapper(capture):
            response = visual["a"].get(route, HTTP_X_DEX_SHOPPING_BINDING=binding)
        assert response.status_code == 200, response.content
        profiles[route.split("?")[0]] = queries
    out = Path("reports/shop-13")
    out.mkdir(exist_ok=True, parents=True)
    (out / "query-profile.json").write_text(json.dumps(profiles, indent=2))


def test_fit_counts_unique_included_species_without_claiming_contents(visual, monkeypatch):
    enable_read_fixture(visual, monkeypatch)
    actor = visual["actor"]
    run = received(actor, selected(actor), "Alakazam Alakazam Eevee Gengar two card lot")
    handle = discovery.discovery_listing.result_handle(run.id, run.raws[0]["itemId"])
    candidate = listing_check.candidate(actor, "session", run.id, handle)
    fit = candidate["context"]["collection_fit"]
    assert fit["mentioned_species"] == [65, 133]
    assert fit["included_species"] is None and fit["unknown_contents"] is None
    opened = listing_check.review(actor, "session")
    value = dict(
        currency="USD",
        unknown_contents=None,
        discovery_origin=dict(run_id=run.id, result_id=handle),
        cards=[
            dict(printing_id=p, quantity=2)
            for p in (visual["catalog"][1]["id"], "shop04-base-alakazam", visual["catalog"][2]["id"])
        ],
    )
    result = listing_check.review(actor, "session", value, opened["lease"])
    fit = result["context"]["collection_fit"]
    assert fit["included_species"] == [65]
    assert "unverified" in fit["included_provenance"]
    assert fit["unknown_contents"] is None
    assert result["context"]["choices"]["budget"] == "87.25"
    assert run.counts["total"] == 0


def test_deals_review_shows_current_collection_fit(visual, monkeypatch):
    enable_read_fixture(visual, monkeypatch)
    actor = visual["actor"]
    listing_check._reviews.pop(discovery._owner(actor, "session"), None)
    choice = discovery.Choices(intent="deals", query="Alakazam", generation=collection.generation(actor))
    run = received(actor, choice, "Alakazam lot")
    handle = discovery.discovery_listing.result_handle(run.id, run.raws[0]["itemId"])
    fit = listing_check.candidate(actor, "session", run.id, handle)["context"]["collection_fit"]
    assert 65 in fit["mentioned_species"] and fit["included_species"] is None
    opened = listing_check.review(actor, "session")
    review = dict(
        currency="USD",
        unknown_contents=None,
        discovery_origin=dict(run_id=run.id, result_id=handle),
        cards=[dict(printing_id="shop04-base-alakazam", quantity=1)],
    )
    fit = listing_check.review(actor, "session", review, opened["lease"])["context"]["collection_fit"]
    assert fit["included_species"] == [65]
    assert run.counts["total"] == 0


def test_empty_and_locally_filtered_receipts_preserve_counts(visual, monkeypatch):
    enable_read_fixture(visual, monkeypatch)
    actor = visual["actor"]
    run = received(actor, selected(actor).model_copy(update={"budget": discovery.Decimal("1")}))
    value = discovery.status(actor, "session", run.id, received=True)
    assert not value["results"]
    assert value["coverage"] == dict(received=1, shown=0, filtered=1)
    assert "budget" in value["limitation"]
    run.raws.clear()
    value = discovery.status(actor, "session", run.id, received=True)
    assert value["coverage"] == dict(received=0, shown=0, filtered=0)
    assert value["choices"]["species"] == 65


@pytest.mark.parametrize("expired", [False, True])
def test_receipt_final_stop_or_original_expiry_clears_output(visual, monkeypatch, expired):
    from pokemon_hunter.beta import store

    enable_read_fixture(visual, monkeypatch)
    actor = visual["actor"]
    run = received(actor, selected(actor))
    rows = store.rows

    def change(sql, params=()):
        value = rows(sql, params)
        if "AS catalog,(SELECT status FROM account_read_state" in sql:
            if expired:
                run.created -= discovery.EPHEMERAL_SECONDS
            else:
                run.cancel.set()
        return value

    monkeypatch.setattr(store, "rows", change)
    result = discovery.status(actor, "session", run.id, received=True)
    assert not result["results"] and not result["running"]
    assert result["state"] == ("expired" if expired else "stopped")


def test_review_correction_outside_frozen_printings_cannot_claim_goal_gain(visual, monkeypatch):
    from pokemon_hunter.beta import goal_hunts, shopping_index

    goal = apply(visual, "goal", dict(name="Frozen coverage", goal_kind="original151"))["changes"][0]["after"]
    enable_read_fixture(visual, monkeypatch)
    actor = visual["actor"]
    run = received(
        actor,
        selected(actor, goal_id=goal["id"], goal_version=goal["version"]),
        scope=goal_hunts.snapshot(actor, goal["id"]),
    )

    # This retained goal has no reviewed printing membership for the later
    # engineering Alakazam metadata, despite retaining species 65 as missing.
    @shopping_index.indexed
    def checked(actor):
        return shopping_intent.fit(
            actor,
            run.choices.model_dump(mode="json"),
            "Alakazam",
            dict(cards=[dict(printing_id="shop04-base-alakazam", quantity=2)], unknown_contents=None),
        )

    fit = checked(actor)
    assert fit["mentioned_species"] == [65]
    assert fit["included_species"] == []
    assert fit["outside_scope_ids"] == ["shop04-base-alakazam"]
    assert fit["unknown_contents"] is None


def test_exact_goal_uses_missing_printing_not_same_species(visual, monkeypatch):
    from pokemon_hunter.beta import goal_hunts, shopping_index

    target = "shop04-base-alakazam"
    other = "shop04-base2-variant"
    collection.execute("UPDATE printings SET unresolved_fields='[]' WHERE id=%s", [target])
    goal = apply(
        visual, "goal", dict(name="Exact", goal_kind="custom", policy="exact", printing_ids=[target])
    )["changes"][0]["after"]
    enable_read_fixture(visual, monkeypatch)
    actor = visual["actor"]
    listing_check._reviews.pop(discovery._owner(actor, "session"), None)
    raw = {"goal": goal["id"], "version": goal["version"], "scope": "all"}
    assert any(row["species"] == 65 for row in shopping_intent.targets(actor, raw)["targets"])

    @shopping_index.indexed
    def check(actor, pid):
        return shopping_intent.fit(
            actor,
            dict(focus="all", goal_id=goal["id"], goal_version=goal["version"]),
            "Alakazam",
            dict(cards=[dict(printing_id=pid, quantity=1)], unknown_contents=2),
        )

    assert check(actor, other)["included_printings"] == []
    assert [p["id"] for p in check(actor, target)["included_printings"]] == [target]
    with pytest.raises(collection.Conflict):
        shopping_intent.targets(actor, dict(raw, version="0" * 64))

    run = received(
        actor,
        selected(actor, goal_id=goal["id"], goal_version=goal["version"]),
        scope=goal_hunts.snapshot(actor, goal["id"]),
    )
    handle = discovery.discovery_listing.result_handle(run.id, run.raws[0]["itemId"])
    assert (
        listing_check.candidate(actor, "session", run.id, handle)["context"]["collection_fit"]["goal_policy"]
        == "exact"
    )
    opened = listing_check.review(actor, "session")
    review = dict(
        currency="USD",
        price_kind="current_asking_price",
        unknown_contents=1,
        discovery_origin=dict(run_id=run.id, result_id=handle),
        cards=[dict(printing_id=target, quantity=1)],
    )
    saved = listing_check.review(actor, "session", review, opened["lease"])
    assert [p["id"] for p in saved["context"]["collection_fit"]["included_printings"]] == [target]
    listing_check.saved_comparison(actor, "session", saved["revision"], opened["lease"])
    listing_check.validate_lease(actor, "session", opened["lease"], run.id, handle)
    other_run = received(actor, run.choices, scope=goal_hunts.snapshot(actor, goal["id"]))
    other_handle = discovery.discovery_listing.result_handle(other_run.id, other_run.raws[0]["itemId"])
    listing_check.validate_lease(actor, "session", opened["lease"], other_run.id, other_handle)
    assert run.counts["total"] == 0
    apply(visual, "add", {"printing_id": other, "duplicate_policy": "allow"})
    with pytest.raises(collection.Conflict):
        listing_check.validate_lease(actor, "session", opened["lease"], run.id, handle)
    with pytest.raises(collection.Conflict):
        listing_check.saved_comparison(actor, "session", saved["revision"], opened["lease"])


@pytest.mark.parametrize("frozen", [False, True])
def test_review_fit_matches_before_and_after_read_preparation(visual, monkeypatch, frozen):
    from pokemon_hunter.beta import shopping_index

    target, other = "shop04-base-alakazam", "shop04-base2-variant"
    collection.execute("UPDATE printings SET unresolved_fields='[]' WHERE id=%s", [target])
    goal = apply(
        visual, "goal", dict(name="Exact", goal_kind="custom", policy="exact", printing_ids=[target])
    )["changes"][0]["after"]
    choices = dict(focus="all", goal_id=goal["id"] if frozen else None, goal_version=goal["version"])
    actor = visual["actor"]

    def fit(pid):
        return shopping_intent.fit(
            actor, choices, "Alakazam", dict(cards=[dict(printing_id=pid, quantity=1)], unknown_contents=2)
        )

    before = [fit(pid) for pid in (target, other)]
    enable_read_fixture(visual, monkeypatch)
    after = [shopping_index.indexed(fit_for_actor)(actor, choices, pid) for pid in (target, other)]
    for result in after:
        for key in (
            "read_version",
            "public",
            "catalog_revision",
            "account_revision",
            "account_id",
            "generation",
        ):
            result.pop(key, None)
    assert after == before


def fit_for_actor(actor, choices, pid):
    return shopping_intent.fit(
        actor, choices, "Alakazam", dict(cards=[dict(printing_id=pid, quantity=1)], unknown_contents=2)
    )


def test_exact_goal_does_not_match_a_now_unresolved_catalog_identity(visual, monkeypatch):
    from pokemon_hunter.beta import shopping_index

    target = "shop04-base-alakazam"
    collection.execute("UPDATE printings SET unresolved_fields='[]' WHERE id=%s", [target])
    goal = apply(
        visual, "goal", dict(name="Exact", goal_kind="custom", policy="exact", printing_ids=[target])
    )["changes"][0]["after"]
    collection.execute("UPDATE printings SET unresolved_fields='[\"edition\"]' WHERE id=%s", [target])
    enable_read_fixture(visual, monkeypatch)

    @shopping_index.indexed
    def check(actor):
        return shopping_intent.fit(
            actor,
            dict(focus="all", goal_id=goal["id"], goal_version=goal["version"]),
            "Alakazam",
            dict(cards=[dict(printing_id=target, quantity=1)], unknown_contents=None),
        )

    assert check(visual["actor"])["included_printings"] == []
