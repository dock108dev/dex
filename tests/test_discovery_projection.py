"""Current/frozen selection, result projection and temporary review contracts; no acquisition."""

import hashlib

import pytest
from django.http import Http404
from test_discovery import discovery as discovery
from test_discovery import ledger, run_for

from pokemon_hunter.beta import discovery as d


def test_deals_include_owned_without_goal_and_query_dedup(discovery):
    rows = d._candidate_data(discovery.actor, d.Choices(), None)
    assert any(r["id"] == "p1" and r["owned"] for r in rows)
    assert len(d.query_plan(rows + rows)) == 6
    assert d.query_plan(rows, "custom singles") == ["custom singles"]
    assert all("Pokemon" in q and "Base Set" in q for q in d.query_plan(rows))


def test_missing_current_printings_species_and_frozen_scope(discovery):
    def ids(choices):
        return {r["id"] for r in d._candidate_data(discovery.actor, d.Choices(**choices), None)}

    assert ids({"intent": "missing", "missing_basis": "printing"}) == {"p2", "p3", "p4", "p5", "p6"}
    assert ids({"intent": "missing"}) == {"p3", "p4", "p5", "p6"}
    assert ids({"intent": "missing", "missing_basis": "species"}) == {"p3", "p4", "p5", "p6"}
    # Broad declaration presence never establishes an exact printing.
    discovery.data["cards"]["p2"]["owned"] = True
    assert "p2" in ids({"intent": "missing", "missing_basis": "printing"})
    scope = dict(name="Frozen", version=2, definition={"policy": "exact"})

    def scoped(who, data, frozen):
        assert frozen is scope
        return {**data, "cards": {"p3": dict(data["cards"]["p3"], owned=False)}}

    discovery.monkeypatch.setattr(d.goal_hunts, "project", scoped)
    result = d._candidate_data(discovery.actor, d.Choices(intent="missing", missing_basis="species"), scope)
    assert [p["id"] for p in result] == ["p3"]


def test_filters_keep_catalog_scope(discovery):
    rows = d._candidate_data(discovery.actor, d.Choices(focus="rares"), None)
    assert [p["id"] for p in rows] == ["p3"]
    assert not d._candidate_data(discovery.actor, d.Choices(set_id="another-set"), None)


def test_region_filters_do_not_include_later_generations(discovery):
    for card, number in zip(discovery.data["cards"].values(), (1, 151, 152, 251, 252, 386), strict=True):
        card["pokemon_dex"] = number
    kanto = d._candidate_data(discovery.actor, d.Choices(focus="kanto"), None)
    johto = d._candidate_data(discovery.actor, d.Choices(focus="johto"), None)
    assert {row["id"] for row in kanto} == {"p1", "p2"}
    assert {row["id"] for row in johto} == {"p3", "p4"}


def test_budget_excludes_known_price_floor_but_keeps_unknown_shipping(discovery):
    from pokemon_hunter.beta import discovery_comparison

    run = run_for(discovery, choices=d.Choices(budget="50", product_type="both"))
    run.state = "complete"
    d._runs[run.id] = run
    rows = [
        dict(item_id="above-budget", listing_price="51", delivered_total=None, shipping=None),
        dict(item_id="incomplete", listing_price="49", delivered_total=None, shipping=None),
        dict(item_id="unknown-price", listing_price=None, delivered_total=None, shipping=None),
    ]
    discovery.monkeypatch.setattr(discovery_comparison, "compare", lambda *args: rows)
    result = d.status(discovery.actor, "session", run.id)
    assert [row["listing_price"] for row in result["results"]] == ["49", None]
    assert result["results"][0]["shipping"] is None


def test_status_rechecks_comparison_and_reveal_without_provider(discovery):
    from pokemon_hunter.beta import discovery_comparison

    run = run_for(discovery)
    run.state = "complete"
    run.raws = [{"itemId": "one"}]
    d._runs[run.id] = run
    calls = []

    def compare(who, raws, candidates):
        calls.append(True)
        return [
            dict(
                item_id="one",
                title="seller title",
                item_url="https://www.ebay.com/itm/1",
                proposed_identity={"printing_id": "p3"},
                classification="conditional",
                delivered_total=None,
                shipping=None,
                save_allowed=False,
            )
        ]

    discovery.monkeypatch.setattr(discovery_comparison, "compare", compare)
    result = d.status(discovery.actor, "session", run.id)
    row = result["results"][0]
    assert row["title"] == "seller title" and row["item_url"].startswith("https://www.ebay.com/")
    assert row["shipping"] is None
    assert row["proposed_identity"] == {"printing_id": "p3"}
    revealed = d.reveal(discovery.actor, "session", run.id, row["id"])
    assert revealed["results"][0]["title"] == "seller title"
    assert len(calls) == 3 and not run.counts["total"]
    # Withdrawal/expiry at the existing admission boundary takes effect locally.
    discovery.monkeypatch.setattr(discovery_comparison, "compare", lambda *args: [])
    assert d.status(discovery.actor, "session", run.id)["results"] == []


def test_status_preserves_comparison_order_through_filtering_and_reveal(discovery):
    from pokemon_hunter.beta import discovery_comparison

    run = run_for(discovery, choices=d.Choices(budget="100", product_type="both"))
    run.state = "complete"
    d._runs[run.id] = run
    rows = [
        dict(
            item_id="high-shipping",
            title="first seller title",
            classification="conditional",
            shipping="90",
            delivered_total="95",
            comparison=dict(
                below_reference=False, difference_percent="-95", reference_minus_delivered_total="-5"
            ),
        ),
        dict(item_id="above-budget", listing_price="101", delivered_total=None, shipping=None),
        dict(
            item_id="free-shipping",
            classification="comparable",
            shipping="0",
            delivered_total="50",
            comparison=dict(
                below_reference=True, difference_percent="50", reference_minus_delivered_total="50"
            ),
        ),
    ]
    discovery.monkeypatch.setattr(discovery_comparison, "compare", lambda *args: rows)
    result = d.status(discovery.actor, "session", run.id)
    # Comparison owns ranking. The adapter only filters and projects its order,
    # even when a substituted comparison supplies another ordering policy.
    assert [row["delivered_total"] for row in result["results"]] == ["95", "50"]
    revealed = d.reveal(discovery.actor, "session", run.id, result["results"][0]["id"])
    assert [row["id"] for row in revealed["results"]] == [row["id"] for row in result["results"]]
    assert revealed["results"][0]["title"] == "first seller title"


def test_status_keeps_equal_comparison_ties_in_original_item_order(discovery):
    from pokemon_hunter.beta import discovery_comparison

    run = run_for(discovery)
    run.state = "complete"
    d._runs[run.id] = run
    item_ids = ["below-small-a", "below-small-b"]
    response_ids = [hashlib.sha256((run.id + "\0" + key).encode()).hexdigest()[:24] for key in item_ids]
    assert response_ids != sorted(response_ids)
    rows = [
        dict(
            item_id=key,
            classification="comparable",
            delivered_total="50",
            comparison=dict(below_reference=True, reference_minus_delivered_total="50"),
        )
        for key in item_ids
    ]
    discovery.monkeypatch.setattr(discovery_comparison, "compare", lambda *args: rows)
    result = d.status(discovery.actor, "session", run.id)
    assert [row["id"] for row in result["results"]] == response_ids
    revealed = d.reveal(discovery.actor, "session", run.id, response_ids[1])
    assert [row["id"] for row in revealed["results"]] == response_ids


def test_current_missing_defaults_kanto_species_but_explicit_goal_remains_unrestricted(discovery):
    current = d.Choices(intent="missing")
    assert current.focus == "kanto" and current.missing_basis == "species"
    frozen = d.Choices(intent="missing", goal_id="saved")
    assert frozen.focus == "all"
    assert d.Choices(intent="deals").focus == "all"


def test_species_and_checked_group_keep_explicit_child_without_picking_sibling(discovery):
    from pokemon_hunter.beta import card_groups

    assert [p["id"] for p in d._candidate_data(discovery.actor, d.Choices(species=1), None)] == ["p1"]
    calls = []

    def detail(actor, group, selected_child=None):
        calls.append((group, selected_child))
        return {"variants": [{"id": "p1", "available": True}, {"id": "p2", "available": True}]}

    discovery.monkeypatch.setattr(card_groups, "detail", detail)
    group = "dg1-" + "a" * 64
    assert len(d._candidate_data(discovery.actor, d.Choices(group_id=group), None)) == 2
    assert [
        p["id"]
        for p in d._candidate_data(
            discovery.actor, d.Choices(group_id=group, printing_id="p2", product_type="both"), None
        )
    ] == ["p2"]
    assert calls == [(group, None), (group, "p2")]
    with pytest.raises(ValueError, match="checked card group"):
        d.Choices(printing_id="p1")


def test_generation_and_goal_version_fail_before_provider_dispatch(discovery):
    from pokemon_hunter.beta import collection

    discovery.monkeypatch.setattr(collection, "generation", lambda who: 7)
    with pytest.raises(collection.Conflict, match="Collection changed"):
        d.start(discovery.actor, "session", {"generation": 6})
    discovery.monkeypatch.setattr(collection, "one", lambda *args: {"version": "a" * 64})
    with pytest.raises(collection.Conflict, match="Saved goal changed"):
        d.start(
            discovery.actor,
            "session",
            {
                "intent": "missing",
                "goal_id": "saved",
                "goal_version": "b" * 64,
            },
        )


def test_review_summary_lease_immediate_and_original_session_expiry(discovery):
    from pokemon_hunter.beta import discovery_comparison

    run = run_for(discovery)
    run.state = "complete"
    run.raws = [{"itemId": "v1|123456789012|0", "title": "PRIVATE SUMMARY"}]
    d._runs[run.id] = run
    discovery.monkeypatch.setattr(
        discovery_comparison,
        "compare",
        lambda *args: [
            {"item_id": run.raws[0]["itemId"], "title": "PRIVATE SUMMARY"},
        ],
    )
    result_id = d.status(discovery.actor, "session", run.id)["results"][0]["id"]
    lease = d.review_candidate(discovery.actor, "session", run.id, result_id)
    assert lease["raw"]["title"] == "PRIVATE SUMMARY" and lease["created"] == run.created
    assert lease["selected_target"] is None
    lease["raw"]["title"] = "modified"
    assert run.raws[0]["title"] == "PRIVATE SUMMARY"
    with pytest.raises(Http404):
        d.review_candidate(discovery.actor, "another-session", run.id, result_id)
    run.created -= d.EPHEMERAL_SECONDS
    with pytest.raises(Http404):
        d.review_candidate(discovery.actor, "session", run.id, result_id)
    assert run.raws == []


def test_review_lease_preserves_checked_exact_target_and_separate_auction_amounts(discovery):
    from pokemon_hunter.beta import card_groups, discovery_comparison, shopping

    group = "dg1-" + "a" * 64
    discovery.monkeypatch.setattr(
        card_groups,
        "detail",
        lambda *args, **kwargs: {
            "variants": [{"id": "p1", "available": True}, {"id": "p2", "available": True}],
        },
    )
    discovery.monkeypatch.setattr(d, "Transport", lambda: pytest.fail("Review must not acquire"))
    run = run_for(discovery, choices=d.Choices(group_id=group, printing_id="p2", product_type="both"))
    run.state = "complete"
    run.raws = [
        {
            "itemId": "v1|123456789012|0",
            "title": "PRIVATE AUCTION SUMMARY",
            "buyingOptions": ["AUCTION", "FIXED_PRICE"],
            "currentBidPrice": {"value": "2.00", "currency": "USD"},
            "price": {"value": "20.00", "currency": "USD"},
        }
    ]
    d._runs[run.id] = run
    discovery.monkeypatch.setattr(
        discovery_comparison,
        "compare",
        lambda *args: [
            {"item_id": run.raws[0]["itemId"], "title": "PRIVATE AUCTION SUMMARY"},
        ],
    )
    result_id = d.status(discovery.actor, "session", run.id)["results"][0]["id"]
    d.reveal(discovery.actor, "session", run.id, result_id)
    lease = d.review_candidate(discovery.actor, "session", run.id, result_id)
    assert lease["selected_target"] == shopping.identity(discovery.data["catalog"][1])
    assert lease["raw"]["currentBidPrice"]["value"] == "2.00"
    assert lease["raw"]["price"]["value"] == "20.00"
    assert "reference" not in lease["result"] and not ledger(discovery).exists()
    d.stop(discovery.actor, "session", run.id)
    with pytest.raises(Http404):
        d.review_candidate(discovery.actor, "session", run.id, result_id)


def test_product_filter_and_ending_soon_order_are_local_and_keep_unpriced(discovery):
    from pokemon_hunter.beta import discovery_comparison

    run = run_for(discovery, choices=d.Choices(product_type="mixed_lots", sort="ending_soonest"))
    run.state = "complete"
    run.raws = [{"itemId": "lot-early"}, {"itemId": "single"}, {"itemId": "lot-late"}]
    d._runs[run.id] = run
    discovery.monkeypatch.setattr(
        discovery_comparison,
        "compare",
        lambda *args: [
            {"item_id": key, "discovery_kind": kind, "classification": "unpriced"}
            for key, kind in (("lot-late", "mixed_lot"), ("single", "single"), ("lot-early", "mixed_lot"))
        ],
    )
    rows = d.status(discovery.actor, "session", run.id)["results"]
    assert len(rows) == 2 and all(row["classification"] == "unpriced" for row in rows)
    early = hashlib.sha256((run.id + "\0lot-early").encode()).hexdigest()[:24]
    assert rows[0]["id"] == early


def test_review_projects_only_selected_offer_and_preserves_lease(discovery, monkeypatch):
    import hashlib

    from pokemon_hunter.beta import discovery_comparison

    run = run_for(discovery, choices=d.Choices(query="Hypno Fossil", product_type="mixed_lots"))
    run.state = "complete"
    run.raws = [{"itemId": str(i), "title": "Engineering lot"} for i in range(80)]
    d._runs[run.id] = run
    batches = []

    def compare(actor, raws, candidates):
        batches.append([raw["itemId"] for raw in raws])
        return [{"item_id": raw["itemId"], "discovery_kind": "mixed_lot"} for raw in raws]

    monkeypatch.setattr(discovery_comparison, "compare", compare)
    handle = hashlib.sha256((run.id + "\0" + "43").encode()).hexdigest()[:24]
    source = d.review_candidate(discovery.actor, "session", run.id, handle)
    assert source["raw"]["itemId"] == "43"
    assert batches == [["43"]]
    assert source["created"] == run.created
    d.stop(discovery.actor, "session", run.id)
    with pytest.raises(Http404):
        d.review_candidate(discovery.actor, "session", run.id, handle)
