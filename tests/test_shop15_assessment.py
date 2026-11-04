"""Conditional bid policy and authority tests on disposable engineering data."""

import uuid
from decimal import ROUND_CEILING, Decimal
from types import SimpleNamespace

import pytest
from price_snapshot_helpers import NOW, package, stage
from test_listing_check import b2 as b2
from test_listing_check import env as env
from test_listing_check import review_value
from test_listing_check import setup as setup
from test_listing_check import shop as shop
from test_listing_check import snapshot as snapshot

from pokemon_hunter.beta import discovery, listing_check, lot_assessment, price_snapshots


@pytest.mark.parametrize(
    "limit,after_costs,shipping,rate,expected",
    [
        ("90", "11", "5", "0", "79"),
        ("100", "11", "5", "0", "89"),
        ("80", "5", "5", "10", "67.72"),
        ("8", "11", "5", "0", None),
        ("0", "0", "0", "0", "0"),
        ("1.00999", "0", "0", "0", "1.00"),
    ],
)
def test_ceiling_matches_incremental_affordability(limit, after_costs, shipping, rate, expected):
    limit, fixed, ship, pct = map(Decimal, (limit, after_costs, shipping, rate))
    answer = lot_assessment.ceiling(limit, fixed, ship, pct)
    assert answer == (Decimal(expected) if expected is not None else None)
    # Independent forward oracle enumerates even unaffordable bids one cent at a time.
    feasible = []
    for cent in range(int(limit * 100) + 2):
        bid = Decimal(cent) / 100
        tax_cents = ((bid + ship) * pct).to_integral_value(rounding=ROUND_CEILING)
        if bid + fixed + tax_cents / 100 <= limit:
            feasible.append(bid)
    assert answer == max(feasible, default=None)


@pytest.fixture
def auction(setup, monkeypatch):
    actor = setup["actor"]
    monkeypatch.setitem(listing_check._reviews, discovery._owner(actor, "session"), None)
    source = package(setup, permanent=False)
    record = source["records"][1]
    source["contract"]["fields"][record["field"]]["grader"] = "PSA"
    record.update(grader="PSA", value="45.00001", original_money="45.00001")
    price_snapshots.activate(stage(source), None, now=NOW)
    p = setup["entries"][record["printing_id"]]
    monkeypatch.setattr(listing_check, "datetime", SimpleNamespace(now=lambda tz: NOW))
    run = discovery.Run(
        str(uuid.uuid4()),
        discovery._owner(actor, "session"),
        discovery.Choices(),
        None,
        [],
        operation="detail",
        state="complete",
        raws=[
            listing_check.details(
                "123456789012",
                dict(
                    itemId="v1|123456789012|0",
                    title=p["name"],
                    buyingOptions=["AUCTION"],
                    currentBidPrice=dict(value="80", currency="USD"),
                ),
            )
        ],
    )
    monkeypatch.setitem(discovery._runs, run.id, run)
    value = review_value(
        p,
        detail_run=run.id,
        price_kind="current_bid",
        price="80",
        unknown_contents=0,
        planned_bid="78",
        budget="100",
        shipping="5",
        tax="6",
        other_costs="0",
        stock_quantity=77,
        lot_units=1,
    )
    value["cards"][0].update(grade="8", grader="PSA")
    lease = listing_check.review(actor, "session")["lease"]

    def save():
        return listing_check.review(actor, "session", value, lease)["revision"]

    def compare(revision=None):
        return listing_check.saved_comparison(actor, "session", revision or save(), lease)["assessment"]

    return value, compare, save, run, source, setup


def test_auction_review_corrections_costs_and_scope(auction):
    v, compare, save, run, source, state = auction
    result = compare()
    assert not result["issues"], result["issues"]
    assert (result["maximum"], result["value_limit"], result["budget_limit"], result["binding"]) == (
        "79.00",
        "79.00",
        "89.00",
        "reference value",
    )
    assert result["price_above"] and not result["planned_bid_above"]
    assert result["evidence"][0]["grader"] == "PSA"
    assert result["costs"]["listing_observation"]["reference_difference"] == "-1.00"
    v.update(budget="70", price="50")
    result = compare()
    assert result["maximum"] == "59.00" and result["binding"] == "budget"
    assert not result["price_above"] and result["planned_bid_above"]
    v.update(tax="", tax_rate="10", budget="80")
    result = compare()
    assert result["maximum"] == "67.72" and result["costs"]["planned_bid"]["full_delivered_cost"] == "91.30"
    v.update(tax_rate="", tax="", planned_bid="12")
    result = compare()
    assert result["costs"]["planned_bid"]["before_tax"] == "17.00"
    assert result["costs"]["planned_bid"]["full_delivered_cost"] is None and result["maximum"] is None
    v.update(tax="0", shipping="")
    assert any("shipping" in issue for issue in compare()["issues"])
    v.update(shipping="0", currency="GBP")
    assert compare()["maximum"] is None
    v.update(currency="USD", unknown_contents=None)
    result = compare()
    assert result["subtotal"] == "90.00" and result["value"] is result["maximum"] is None
    v.update(unknown_contents=0)
    other = next(p for p in state["entries"].values() if p["id"] != v["cards"][0]["printing_id"])
    v["cards"].append(dict(printing_id=other["id"], grade="raw", condition="LP", quantity=1))
    result = compare()
    assert result["subtotal"] == "90.00" and result["priced"] == 2 and result["units"] == 3
    assert any(other["name"] in issue and "LP" in issue for issue in result["issues"])
    v["cards"][0].update(grader="BGS")
    assert compare()["subtotal"] is None
    v["cards"].pop()
    v["cards"][0].update(grader="PSA")
    v.update(price_kind="current_asking_price")
    with pytest.raises(ValueError, match="Offer type"):
        compare()
    run.raws[0]["price_kind"] = "current_asking_price"
    fixed = compare()
    assert not fixed["auction"] and fixed["maximum"] is None and fixed["value"] == "90.00"


def test_source_withdrawal_and_lease_revalidation(auction, monkeypatch):
    v, compare, save, run, source, _ = auction
    old = save()
    v["budget"] = "10"
    revision = save()
    with pytest.raises(ValueError, match="Review changed"):
        compare(old)
    assert compare(revision)["maximum"] is None  # fixed charges exceed budget even at zero
    v.update(budget="100")
    assert compare()["maximum"] == "79.00"
    price_snapshots.remove(source["version"])
    assert compare()["maximum"] is None
    revision = save()
    run.cancel.set()
    with pytest.raises(ValueError, match="stopped"):
        compare(revision)
    run.cancel.clear()
    revision = save()
    monkeypatch.setattr(
        listing_check.time, "monotonic", lambda: run.created + discovery.EPHEMERAL_SECONDS + 1
    )
    with pytest.raises(ValueError, match="expired"):
        compare(revision)


def test_offer_contradiction_and_reference_age(auction, monkeypatch):
    from datetime import timedelta

    value, compare, _, run, _, _ = auction
    run.raws[0]["clues"].update(graded=True, grader="BGS", grade="8")
    result = compare()
    assert result["maximum"] is result["subtotal"] is None
    assert any("conflicts with the seller evidence" in reason for reason in result["issues"])
    run.raws[0]["clues"].update(graded=True, grader="PSA", grade="8")
    assert compare()["maximum"] == "79.00"
    monkeypatch.setattr(listing_check, "datetime", SimpleNamespace(now=lambda tz: NOW + timedelta(days=32)))
    result = compare()
    assert result["maximum"] is None and result["priced"] == 0
    assert any("PSA 8" in reason for reason in result["issues"])


def test_return_reads_snapshot_without_cleanup_or_lease_renewal(auction, monkeypatch):
    from datetime import timedelta

    value, compare, save, run, source, state = auction
    before = listing_check.review(state["actor"], "session")
    revision = save()
    monkeypatch.setattr(price_snapshots, "purge_expired", lambda **_: pytest.fail("return ran cleanup"))
    with price_snapshots.read_only():
        assert compare(revision)["maximum"] == "79.00"
        assert price_snapshots.display_current(now=NOW + timedelta(days=3))[0] == []
    after = listing_check.review(state["actor"], "session", lease=before["lease"])
    assert before["lease"] == after["lease"] and after["expires_in_seconds"] <= before["expires_in_seconds"]
    assert (price_snapshots.directory() / (source["version"] + ".json")).is_file()


@pytest.mark.parametrize(
    "change",
    [
        "withdraw_primary",
        "withdraw_competing",
        "expiry",
        "printing",
        "condition",
        "superseded",
        "index",
        "stop",
    ],
)
def test_prepared_evidence_rechecked_after_calculation(auction, monkeypatch, change):
    """Interleave the change after calculation but before the final decision check."""
    from copy import deepcopy
    from datetime import timedelta

    from pokemon_hunter.beta import price_snapshot_contract as rules

    value, compare, save, run, old, state = auction
    parts, records = {}, []
    for key in ("first", "second"):
        policy = deepcopy(old["contract"])
        policy["review_id"] = key
        parts[key] = dict(contract=policy, expires_at=old["expires_at"])
        row = dict(old["records"][1], contract_id=key, observation_id=str(uuid.uuid4()))
        records.append(row)
    version = str(uuid.uuid4())
    release = dict(
        schema="dex-price-snapshot-v2",
        version=version,
        release_month=old["release_month"],
        contracts=parts,
        records=records,
    )
    price_snapshots.activate(stage(release), old["version"], now=NOW)
    ref = compare()["evidence"][0]
    assert ref["conflicts"] and compare()["maximum"] == "79.00"
    revision = save()
    original = listing_check.compare

    def interleave(*args, **kwargs):
        result = original(*args, **kwargs)
        assert result["assessment"]["maximum"] == "79.00"
        if change.startswith("withdraw"):
            digest = (
                ref["source_contract"]
                if change == "withdraw_primary"
                else ref["conflicts"][0]["source_contract"]
            )
            price_snapshots.sources.remove_source(digest)
        elif change == "expiry":
            current = price_snapshots.current
            monkeypatch.setattr(price_snapshots, "current", lambda **kw: current(now=NOW + timedelta(days=3)))
        elif change == "printing":
            monkeypatch.setitem(state["entries"][records[0]["printing_id"]], "finish", "holo")
        elif change in ("condition", "superseded"):
            if change == "condition":
                value["cards"][0].update(grade="raw", grader="", condition="LP")
            else:
                value["budget"] = "20"
            save()
        elif change == "index":
            path = price_snapshots.sources.shard(
                version, rules.digest(parts["first"]["contract"])
            ).with_suffix(".idx")
            path.write_text("{}")
        else:
            run.cancel.set()
        return result

    monkeypatch.setattr(listing_check, "compare", interleave)
    with pytest.raises(ValueError, match="reference expired|Review changed|stopped"):
        compare(revision)
