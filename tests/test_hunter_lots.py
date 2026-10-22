"""Socket-disabled LOT-01 parser, temporary review and arithmetic boundaries."""

import time
from copy import deepcopy
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from django.http import Http404

from pokemon_hunter.beta import (
    collection,
    discovery,
    hunter,
    store,
)
from pokemon_hunter.beta import (
    discovery_comparison as dc,
)
from pokemon_hunter.beta import (
    hunter_lots as lots,
)
from pokemon_hunter.beta import (
    lot_calculator as lot,
)

NOW = datetime(2026, 10, 16, 12, tzinfo=UTC)


def printing(key, name="Charizard", *, number="4/102", **changes):
    return dict(
        id=key,
        name=name,
        set_id="base",
        set_name="Base Set",
        collector_number=number,
        language="en",
        edition="unlimited",
        finish="normal",
        variant="normal",
        game_id="pokemon",
        provenance='{"legacy_id":"' + key + '"}',
        owned=True,
        attributes={},
        **changes,
    )


def raw(**changes):
    result = dict(
        itemId="v1|123456789012|0",
        title="Pokemon lot of 3 cards",
        shortDescription="2x Charizard Base Set 4/102 English Unlimited Non Holo; 1x Blastoise Base Set 2/102 English Unlimited Non Holo",
        condition="Near Mint",
        buyingOptions=["FIXED_PRICE"],
        price=dict(value="3.00", currency="USD"),
        shippingOptions=[dict(shippingCost=dict(value="1.00", currency="USD"))],
    )
    return dict(result, **changes)


@pytest.fixture
def entries():
    return [printing("charizard"), printing("blastoise", "Blastoise", number="2/102")]


@pytest.fixture
def local(monkeypatch, entries):
    actor = SimpleNamespace(user_id="a")
    monkeypatch.setattr(discovery, "_owner", lambda a, session: ("test", a.user_id, session))
    state = dict(raw=raw(), active=True, references=True, created=time.monotonic() - 60)
    monkeypatch.setattr(store, "verified", lambda a: a)
    monkeypatch.setattr(store, "rows", lambda *a, **kw: [dict(id="pokemon")])
    monkeypatch.setattr(collection, "catalog", lambda *a, **kw: deepcopy(entries))
    monkeypatch.setattr(collection, "generation", lambda *a: 1)
    monkeypatch.setattr(lot, "retained_records", lambda: [])

    def source(a, session, *args, **origin):
        if a.user_id != "a" or session != "session" or not state["active"]:
            raise Http404
        return dict(raw=deepcopy(state["raw"]), created=state["created"], expires_in_seconds=1740)

    monkeypatch.setattr(hunter, "summary_lease", source)

    def cells(p, records, today, clues):
        if not state["references"]:
            return {}, {"raw": "Withdrawn source"}
        return dict(
            raw=dict(
                amount="10.00" if p["id"] == "charizard" else "5.00",
                currency="USD",
                as_of=today.isoformat(),
                grade="raw",
                grader=None,
                value_scope="per_card",
                match_status="exact",
                provenance="admitted_fixture",
                source_url="https://example.test/guide",
                raw_record=dict(condition="NM", language="en", edition="unlimited", finish="normal"),
            )
        ), {}

    monkeypatch.setattr(dc, "_reference_cells", cells)
    lots._reviews.clear()
    yield actor, state
    lots._reviews.clear()


def test_all_era_trainer_energy_identity_adapter(local, monkeypatch):
    actor, state = local
    cards = [
        dict(
            printing("trainer", "Professor Turo's Scenario", number="171/182"),
            set_id="paradox",
            set_name="Paradox Rift",
        ),
        dict(
            printing("energy", "Basic Lightning Energy", number="004"),
            set_id="sv",
            set_name="Scarlet & Violet",
        ),
    ]
    monkeypatch.setattr(collection, "catalog", lambda *a, **kw: cards)
    state["raw"] = raw(
        shortDescription="2x Professor Turo's Scenario Paradox Rift 171/182 English Unlimited Non Holo; 1x Basic Lightning Energy Scarlet & Violet #004 English Unlimited Non Holo"
    )
    result = lots.analyze(actor, "session", "run", "result")
    assert {c["printing_id"] for c in result["review"]["cards"]} == {"trainer", "energy"}
    assert result["comparison"]["priced_card_quantity"] == 3


def test_temporary_review_values_owned_duplicates_and_whole_price_once(local):
    actor, _ = local
    result = lots.analyze(actor, "session", "run", "result")
    comparison = result["comparison"]
    assert comparison["priced_card_quantity"] == 3 and comparison["whole_lot_price_count"] == 1
    assert comparison["result"]["known_selected_subtotal"] == "25.00"
    basis = comparison["result"]["comparisons"]["listing_observation"]
    assert basis["base_price"] == "3.00" and basis["known_cost_subtotal"] == "4.00"
    assert basis["full_delivered_cost"] is None and not comparison["complete_delivered_comparison"]
    updated = lots.correct(
        actor,
        "session",
        result["review_id"],
        dict(
            revision=1,
            cards=result["review"]["cards"],
            unknown_contents=0,
            costs=dict(tax="0", other_costs="0"),
        ),
    )
    assert updated["comparison"]["complete_delivered_comparison"]
    assert (
        updated["comparison"]["result"]["comparisons"]["listing_observation"][
            "full_selected_reference_minus_delivered_cost"
        ]
        == "21.00"
    )
    assert updated["revision"] == 2 and updated["expires_in_seconds"] == result["expires_in_seconds"]
    with pytest.raises(collection.Conflict):
        lots.correct(actor, "session", result["review_id"], dict(revision=1, cards=[], unknown_contents=0))


def test_source_withdrawal_is_recomputed_and_stop_session_lease_rechecked(local):
    actor, state = local
    result = lots.analyze(actor, "session", "run", "result")
    key = result["review_id"]
    state["references"] = False
    withdrawn = lots.read(actor, "session", key)
    assert withdrawn["comparison"]["priced_card_quantity"] == 0
    assert withdrawn["comparison"]["result"]["known_selected_subtotal"] is None
    assert withdrawn["comparison"]["references"] == []
    with pytest.raises(Http404):
        lots.read(actor, "different", key)
    with pytest.raises(Http404):
        lots.read(SimpleNamespace(user_id="b"), "session", key)
    state["active"] = False
    with pytest.raises(Http404):
        lots.read(actor, "session", key)
    assert key not in lots._reviews


def test_stop_during_local_projection_suppresses_late_publication(local, monkeypatch):
    actor, state = local
    original = lots._compare

    def stopped(*args, **kwargs):
        result = original(*args, **kwargs)
        state["active"] = False
        return result

    monkeypatch.setattr(lots, "_compare", stopped)
    with pytest.raises(Http404):
        lots.analyze(actor, "session", "run", "result")
    assert not lots._reviews


def test_auction_bid_buy_now_planned_bid_and_detail_intent_are_distinct(local):
    actor, state = local
    state["raw"] = raw(
        buyingOptions=["AUCTION", "FIXED_PRICE"],
        price=dict(value="20.00", currency="USD"),
        currentBidPrice=dict(value="2.00", currency="USD"),
    )
    result = lots.analyze(actor, "session", "run", "result")
    assert result["review"]["costs"]["price_kind"] == "current_bid"
    assert result["review"]["costs"]["price"] == "2.00"
    assert result["comparison"]["buy_now_amount"] == "20.00"
    assert result["comparison"]["final_purchase_price"] is None
    intent = lots.detail_intent(actor, "session", "run", ["result"])
    assert not intent["enabled"] and not intent["dispatch_allowed"]
    assert intent["maximum_operations"] == dict(oauth=1, browse=0, detail=1, total=2)
    assert intent["requests"][0]["item_id"] == "v1|123456789012|0"
    assert intent["ledger_identity"] is None and not intent["lease_renews"]


def test_batch_and_correction_limits_reject_before_work(local):
    actor, _ = local
    with pytest.raises(ValueError):
        lots.selected_batch(actor, "session", "run", ["result"] * 2)
    with pytest.raises(ValueError):
        lots.detail_intent(actor, "session", "run", [str(i) for i in range(9)])
    result = lots.analyze(actor, "session", "run", "result")
    with pytest.raises(ValueError):
        lots.correct(
            actor,
            "session",
            result["review_id"],
            dict(revision=1, cards=[dict(printing_id="charizard", quantity=100001)], unknown_contents=0),
        )


@pytest.mark.parametrize("late_stop", [False, True])
def test_explicit_detail_worker_shares_accounting_and_original_lease(local, monkeypatch, tmp_path, late_stop):
    import asyncio
    import threading

    from pokemon_hunter.beta import ebay_hunts, hunter_budget
    from pokemon_hunter.beta import hunter_lot_details as details

    actor, state = local
    allowance = hunter_budget.TraversalAllowance("hunt-04-lot-offline", oauth=1, detail=2, total=3, lots=2)
    owner = (str(tmp_path), actor.user_id, "session")
    monkeypatch.setattr(discovery, "_owner", lambda a, session: (str(tmp_path), a.user_id, session))
    parent = SimpleNamespace(
        id="run",
        owner=owner,
        allowance=allowance,
        choices=discovery.Choices(english_vintage=False),
        auth_session=None,
        created=state["created"],
        cancel=threading.Event(),
        lock=threading.RLock(),
        window=dict(start=datetime(2026, 10, 16, tzinfo=UTC), end=datetime(2026, 10, 17, tzinfo=UTC)),
        traversal=None,
    )
    monkeypatch.setattr(hunter, "_lookup", lambda *a: parent)
    state["raw"]["_hunt_paths"] = [("singles", "buy_it_now")]
    monkeypatch.setattr(
        ebay_hunts,
        "configuration",
        lambda: (
            SimpleNamespace(environment="production"),
            dict(EBAY_CLIENT_ID="offline-id", EBAY_CLIENT_SECRET="offline-secret"),
        ),
    )
    monkeypatch.setattr(details, "_worker", lambda *a: None)
    monkeypatch.setattr(discovery, "_authorize", lambda *a: None)
    monkeypatch.setattr(discovery, "_context_current", lambda *a: None)
    monkeypatch.setattr(discovery, "_journal", lambda *a, **kw: None)
    calls = []

    class OfflineTransport:
        async def request(self, stage, **kwargs):
            calls.append(stage)
            if stage == "oauth":
                return dict(access_token="offline-token", expires_in=3600, token_type="Bearer")
            if late_stop:
                run.cancel.set()
            return dict(state["raw"], description=state["raw"]["shortDescription"])

        async def close(self):
            pass

    monkeypatch.setattr(details, "Transport", OfflineTransport)
    discovery._tokens.clear()
    details._runs.clear()
    start = details.start(actor, "session", "run", ["result"])
    run = details._runs[start["detail_action_id"]]
    assert run.created == parent.created and run.cancel is not parent.cancel and run.lock is parent.lock
    run.state = "running"
    if late_stop:
        with pytest.raises(discovery._Stopped):
            asyncio.run(details._acquire(run, actor, "session", ("offline-id", "offline-secret")))
        assert not run.raws and calls == ["oauth", "detail"]
        assert hunter_budget.remaining_traversal(tmp_path, allowance)["detail"] == 1
        details.erase_parent("run")
        assert not details._runs
        discovery._tokens.clear()
        return
    asyncio.run(details._acquire(run, actor, "session", ("offline-id", "offline-secret")))
    result = details.status(actor, "session", run.id)
    assert result["state"] == "complete" and calls == ["oauth", "detail"]
    assert result["reviews"][0]["provenance"]["detail_fetched"]
    assert (
        details.status(actor, "session", run.id)["reviews"][0]["review_id"]
        == result["reviews"][0]["review_id"]
    )
    assert calls == ["oauth", "detail"]  # Reopen and valuation perform no request.
    remaining = hunter_budget.remaining_traversal(tmp_path, allowance)
    assert remaining["oauth"] == 0 and remaining["detail"] == 1 and remaining["lots"] == 1
    # The same exact detail dispatch cannot be admitted again, even in a new action.
    run.current_item = state["raw"]["itemId"]
    with pytest.raises(details.ProviderFailure):
        run.admit("detail")
    details.stop(actor, "session", run.id)
    assert not parent.cancel.is_set() and run.cancel.is_set() and not run.raws
    with pytest.raises(Http404):
        lots.read(actor, "session", result["reviews"][0]["review_id"])
    details._runs.clear()
    discovery._tokens.clear()


def test_default_detail_allowance_prevents_configuration_and_dispatch(local, monkeypatch):
    from pokemon_hunter.beta import ebay_hunts
    from pokemon_hunter.beta import hunter_lot_details as details

    actor, _ = local
    monkeypatch.setattr(hunter, "_lookup", lambda *a: SimpleNamespace(allowance=None))
    monkeypatch.setattr(
        ebay_hunts,
        "configuration",
        lambda: pytest.fail("Disabled detail action must not configure a provider"),
    )
    with pytest.raises(ValueError, match="No future"):
        details.start(actor, "session", "run", ["result"])


@pytest.mark.parametrize("value", [[{}], [None], [1], [""], ["a" * 161]])
def test_malformed_selected_handles_are_client_errors(local, value):
    from pokemon_hunter.beta import hunter_lot_details

    actor, _ = local
    for operation in (lots.selected_batch, lots.detail_intent, hunter_lot_details.start):
        with pytest.raises(ValueError):
            operation(actor, "session", "run", value)


def test_bounded_response_and_parent_erasure(local, monkeypatch):
    actor, state = local

    result = lots.analyze(actor, "session", "run", "result")
    lots.erase_parent("run")
    assert not lots._reviews
    with pytest.raises(Http404):
        lots.read(actor, "session", result["review_id"])
    monkeypatch.setattr(lots, "MAX_RESPONSE_BYTES", 10)
    with pytest.raises(ValueError, match="2 MiB"):
        lots.analyze(actor, "session", "run", "result")
    assert not lots._reviews


def test_selected_batch_indexes_and_reads_authorities_once(local, monkeypatch):
    actor, _ = local
    reads = dict(catalog=0, records=0, index=0)
    original_catalog, original_index = lots._catalog, lots.hunter_catalog.IdentityIndex

    def catalog(actor):
        reads["catalog"] += 1
        return original_catalog(actor)

    def records():
        reads["records"] += 1
        return []

    def index(entries):
        reads["index"] += 1
        return original_index(entries)

    monkeypatch.setattr(lots, "_catalog", catalog)
    monkeypatch.setattr(lot, "retained_records", records)
    monkeypatch.setattr(lots.hunter_catalog, "IdentityIndex", index)
    result = lots.selected_batch(actor, "session", "run", [str(i) for i in range(8)])
    assert len(result["reviews"]) == 8 and result["provider_operations"] == 0
    assert reads == dict(catalog=1, records=1, index=1)


@pytest.mark.parametrize(
    "changes",
    [
        dict(itemEndDate="2000-01-01T00:00:00Z"),
        dict(estimatedAvailabilities=[dict(estimatedAvailabilityStatus="OUT_OF_STOCK")]),
        dict(buyingOptions=["AUCTION"], itemEndDate="2099-01-01T00:00:00Z"),
    ],
)
def test_latest_official_detail_availability_cannot_borrow_old_summary(local, monkeypatch, changes):
    from pokemon_hunter.beta import hunter_lot_details as details

    actor, state = local
    state["raw"]["_hunt_paths"] = [("singles", "buy_it_now")]
    parent = SimpleNamespace(
        window=dict(start="2026-10-16T00:00:00Z", end="2026-10-17T00:00:00Z"), traversal=None
    )
    monkeypatch.setattr(hunter, "_lookup", lambda *a: parent)
    body = dict(state["raw"], **changes)
    # A provider-supplied internal path cannot change the captured BIN lane.
    body["_hunt_paths"] = [("singles", "auction")]
    with pytest.raises(ValueError):
        details._checked_detail(actor, "session", "run", "result", body)


def test_archived_and_inherited_identity_conflicts_stay_unpriced(local, monkeypatch):
    actor, state = local
    state["raw"] = raw(shortDescription="2x Charizard Base Set 4/102 Japanese Unlimited Non Holo")
    result = lots.analyze(actor, "session", "run", "result")
    corrected = lots.correct(
        actor,
        "session",
        result["review_id"],
        dict(revision=1, cards=[dict(printing_id="charizard", quantity=2)], unknown_contents=0),
    )
    assert corrected["review"]["cards"][0]["language"] == "ja"
    assert corrected["comparison"]["priced_card_quantity"] == 0
    assert corrected["comparison"]["unpriced_matches"][0]["printing_id"] == "charizard"
    original = collection.catalog
    monkeypatch.setattr(
        collection,
        "catalog",
        lambda *a, **kw: [dict(p, publication_state="archived") for p in original(*a, **kw)],
    )
    state["raw"] = raw()
    result = lots.analyze(actor, "session", "run", "other")
    corrected = lots.correct(
        actor,
        "session",
        result["review_id"],
        dict(revision=1, cards=[dict(printing_id="charizard", quantity=2)], unknown_contents=0),
    )
    assert corrected["comparison"]["priced_card_quantity"] == 0
    assert "archived" in corrected["comparison"]["unpriced_matches"][0]["reason"]


@pytest.mark.parametrize(
    "different",
    [
        "Japanese Unlimited Non Holo",
        "English 1st Edition Non Holo",
        "English Unlimited Holo",
        "English Unlimited Non Holo LP",
        "English Unlimited Non Holo PSA 10",
    ],
)
def test_repeated_same_printing_quantity_merges_conflicting_claims(local, different):
    actor, state = local
    state["raw"] = raw(
        title="Lot of 1 cards",
        shortDescription="1x Charizard Base Set 4/102 English Unlimited Non Holo;1x Charizard Base Set 4/102 "
        + different,
    )
    result = lots.analyze(actor, "session", "run", "result")
    assert result["proposal"]["included_quantity"] == 0
    assert result["proposal"]["proposals"][0]["printing_id"] is None
    assert result["proposal"]["quantity_issues"]
    assert result["comparison"]["priced_card_quantity"] == 0
    corrected = lots.correct(
        actor,
        "session",
        result["review_id"],
        dict(revision=1, cards=[dict(printing_id="charizard", quantity=1)], unknown_contents=0),
    )
    assert corrected["comparison"]["priced_card_quantity"] == 0


def test_condition_conflict_requires_explicit_attribute_correction(local):
    actor, state = local
    state["raw"] = raw(
        title="Lot of 1 cards",
        shortDescription="1x Charizard Base Set 4/102 English Unlimited Non Holo HP",
        condition="Near Mint",
    )
    result = lots.analyze(actor, "session", "run", "result")
    corrected = lots.correct(
        actor,
        "session",
        result["review_id"],
        dict(
            revision=1,
            cards=[dict(printing_id="charizard", quantity=1)],
            unknown_contents=0,
            costs=dict(tax="0", other_costs="0"),
        ),
    )
    assert corrected["comparison"]["priced_card_quantity"] == 0
    assert not corrected["comparison"]["complete_delivered_comparison"]
    corrected = lots.correct(
        actor,
        "session",
        result["review_id"],
        dict(
            revision=2,
            cards=[dict(printing_id="charizard", quantity=1, condition="NM")],
            unknown_contents=0,
            costs=dict(tax="0", other_costs="0"),
        ),
    )
    assert corrected["comparison"]["priced_card_quantity"] == 1


def test_minimum_next_bid_never_relabels_non_usd_as_usd(local):
    actor, state = local
    state["raw"] = raw(
        buyingOptions=["AUCTION", "FIXED_PRICE"],
        currentBidPrice=dict(value="2", currency="USD"),
        minimumPriceToBid=dict(value="3", currency="EUR"),
    )
    result = lots.analyze(actor, "session", "run", "result")
    assert result["comparison"]["minimum_next_bid"] is None
    assert result["comparison"]["minimum_next_bid_currency"] == "EUR"


@pytest.mark.parametrize(
    "kind", ["sealed booster", "mystery", "random", "curated", "repacked", "choose your", "complete set"]
)
def test_unsupported_products_never_enter_lot_valuation_or_bypass_corrections(local, kind):
    actor, state = local
    supported = lots.analyze(actor, "session", "run", "result")
    state["raw"]["title"] = kind + " Pokemon lot of 3 cards"
    with pytest.raises(ValueError, match="Unsupported"):
        lots.analyze(actor, "session", "run", "other")
    with pytest.raises(ValueError, match="Unsupported"):
        lots.correct(
            actor,
            "session",
            supported["review_id"],
            dict(
                revision=1,
                cards=[dict(printing_id="charizard", quantity=2, condition="NM")],
                unknown_contents=0,
                costs=dict(tax="0", other_costs="0"),
            ),
        )
    with pytest.raises(ValueError, match="Unsupported"):
        lots.read(actor, "session", supported["review_id"])


def test_literal_trainer_name_is_removed_before_unsupported_product_classification(local, monkeypatch):
    actor, state = local
    card = printing("trainer", "Booster Shake", number="142/203")
    monkeypatch.setattr(collection, "catalog", lambda *a, **kw: [card])
    state["raw"] = raw(
        title="Pokemon lot of 2 cards",
        shortDescription="2x Booster Shake Base Set 142/203 English Unlimited Non Holo",
    )
    result = lots.analyze(actor, "session", "run", "result")
    assert result["comparison"]["priced_card_quantity"] == 2
    state["raw"]["title"] = "Sealed Pokemon lot of 2 cards"
    with pytest.raises(ValueError, match="Unsupported"):
        lots.analyze(actor, "session", "run", "other")
