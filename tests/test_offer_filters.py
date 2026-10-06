"""Offline comparison branches, immutable saved scopes and endpoint validation."""

import copy
import hashlib
import itertools
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from test_migration import snapshot as snapshot
from test_packs import b2 as b2
from test_packs import b3 as b3
from test_packs import b4 as b4
from test_packs import e1 as e1
from test_packs import env as env
from test_packs import ready

from pokemon_hunter.beta import collection, pack_research, packs, store
from pokemon_hunter.beta import offer_filters as f

NOW = datetime(2026, 10, 5, 12, tzinfo=timezone.utc)


def fixture():
    product = dict(id="product", contents="complete", sources=["official"], offers=[])
    sources = {
        "official": dict(
            status="usable", authority="official-product", subjects=["product"], supports=["product-identity"]
        )
    }
    for key, stock, price, currency, checked in (
        ("a", "in-stock", 1500, "USD", NOW),
        ("b", "out-of-stock", 1000, "USD", NOW - timedelta(hours=24)),
        ("c", "unknown", None, "USD", None),
        ("d", "in-stock", 500, "EUR", NOW - timedelta(hours=25)),
        ("e", "preorder", 0, "USD", NOW + timedelta(seconds=1)),
    ):
        sources[key] = dict(
            status="usable", authority="retailer", subjects=[key], supports=["offer-observation"]
        )
        product["offers"].append(
            dict(
                id=key,
                product_id="product",
                sources=[key],
                retailer="Fixture",
                seller="Seller",
                seller_kind="direct",
                currency=currency,
                url="https://example.test/" + key,
                observations=[
                    dict(
                        id=key,
                        sources=[key],
                        checked_at=checked.isoformat() if checked else None,
                        stock=stock,
                        price_minor=price,
                        shipping_minor=None,
                        note="Fixture",
                    )
                ],
            )
        )
    return dict(expansions=[dict(count=151, species=[123], products=[product])]), sources


def offers(context):
    return context["expansions"][0]["products"][0]["offers"]


def test_every_combination_and_unchanged_coverage_history():
    context, sources = fixture()
    before = copy.deepcopy(context)
    for stock, age, maximum, sort in itertools.product(
        ("all", "in-stock", "out-of-stock", "unknown"),
        ("all", "fresh", "older", "unknown"),
        ("", "10"),
        ("checked", "price"),
    ):
        filtered = f.apply(
            copy.deepcopy(context),
            dict(stock=stock, age=age, max_price=maximum, sort=sort, currency="USD"),
            sources,
            NOW,
        )
        expected = []
        for offer in offers(context):
            o = offer["observations"][0]
            if stock != "all" and stock != o["stock"]:
                continue
            if age != "all" and age != f.age(o["checked_at"], NOW):
                continue
            if maximum and (
                offer["currency"] != "USD" or o["price_minor"] is None or o["price_minor"] > 1000
            ):
                continue
            expected.append(offer["id"])
        assert set(expected) == {o["id"] for o in offers(filtered)}
        assert filtered["expansions"][0]["count"] == 151
        assert filtered["expansions"][0]["species"] == [123]
    assert context == before
    assert f.validate({"max_price": "0", "currency": "USD"})["max_price"] == "0"
    assert packs.money(0, "USD") == "USD 0.00"
    assert packs.money(100, None) == "Unknown"
    missing = copy.deepcopy(context)
    offers(missing)[0].pop("currency")
    assert not offers(f.apply(missing, {"sort": "price", "currency": "USD"}, sources, NOW))[-1][
        "price_comparable"
    ]
    frozen = f.apply(copy.deepcopy(context), {"age": "fresh"}, sources, NOW)
    assert len(offers(frozen)) == 2
    aged = f.apply(frozen, {"age": "fresh"}, sources, NOW + timedelta(days=100), frozen=True)
    assert len(offers(aged)) == 2 and all(not o["representative"]["fresh"] for o in offers(aged))
    assert [
        o["id"]
        for o in offers(f.apply(copy.deepcopy(context), {"sort": "price", "currency": "USD"}, sources, NOW))
    ] == ["e", "b", "a", "c", "d"]
    assert [o["id"] for o in offers(f.apply(copy.deepcopy(context), now=NOW))] == ["e", "a", "b", "d", "c"]


def test_selection_ties_unknown_times_and_exact_boundaries():
    context, sources = fixture()
    history = offers(context)[0]["observations"]
    history.extend([dict(history[0], id="0"), dict(history[0], id="unknown", checked_at=None)])
    result = f.apply(context, now=NOW, sources=sources)
    selected = next(o for o in offers(result) if o["id"] == "a")
    assert selected["representative"]["id"] == "0"
    assert [o["id"] for o in selected["observations"]] == ["0", "a", "unknown"]
    assert f.age((NOW - timedelta(hours=24)).isoformat(), NOW) == "fresh"
    assert f.age((NOW - timedelta(hours=24, microseconds=1)).isoformat(), NOW) == "older"
    assert f.age((NOW + timedelta(microseconds=1)).isoformat(), NOW) == "future"
    assert f.age(None, NOW) == f.age("invalid", NOW) == f.age("2026-10-05", NOW) == "unknown"
    # An offer without observations is retained as unknown, not manufactured into an observation.
    offers(context)[0]["observations"] = []
    result = f.apply(context, {"stock": "unknown"}, sources, NOW)
    assert any(o["observations"] == [] and o["representative"] == {} for o in offers(result))


@pytest.mark.parametrize(
    "values",
    [
        dict(stock="preorder"),
        dict(age="future"),
        dict(sort="fake"),
        dict(max_price="1"),
        dict(max_price="NaN", currency="USD"),
        dict(max_price="-1", currency="USD"),
        dict(max_price="1.001", currency="USD"),
        dict(currency="usd"),
        dict(sort="price"),
    ],
)
def test_invalid_filter_values(values):
    with pytest.raises(ValueError):
        f.validate(values)


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "data:text/html,a",
        "https://user:pass@host/",
        "https://host:bad",
        "https:///nohost",
        "https://host/\n",
        "https://host\\evil",
        "https://host/%0afoo",
        "https://@example.test/",
        "https://./",
        "https://host%40other/",
    ],
)
def test_unsafe_urls(url):
    context, sources = fixture()
    offer = offers(context)[0]
    offer["url"] = url
    decision = f.eligibility(
        offer, offer["observations"][0], context["expansions"][0]["products"][0], sources, NOW
    )
    assert not decision["source"] and not decision["offer"] and not decision["purchase_ready"]
    assert decision["source_reasons"]
    assert f.safe_url("http://example.test/path") and f.safe_url("https://[::1]/path")


def test_link_evidence_levels_time_quality_and_replay():
    context, sources = fixture()
    product = context["expansions"][0]["products"][0]
    offer = offers(context)[0]
    obs = offer["observations"][0]
    decision = f.eligibility(offer, obs, product, sources, NOW)
    assert decision["source"] and decision["offer"] and not decision["purchase_ready"]
    # The supported interface cannot accept an unattested backend timestamp.
    with pytest.raises(TypeError, match="backend_checked_at"):
        f.eligibility(offer, obs, product, sources, NOW, backend_checked_at=NOW.isoformat())
    for change in ({"seller": None}, {"seller_kind": "unknown"}, {"product_id": "different"}):
        assert not f.eligibility(offer | change, obs, product, sources, NOW)["offer"]
    for change in ({"stock": "unknown"}, {"stock": "out-of-stock"}, {"checked_at": None}):
        assert not f.eligibility(offer, obs | change, product, sources, NOW)["purchase_ready"]
    sources["a"]["note"] = "Synthetic replay fixture"
    assert not f.eligibility(offer, obs, product, sources, NOW)["offer"]
    sources["a"]["status"] = "access-denied"
    assert not f.eligibility(offer, obs, product, sources, NOW)["offer"]


def test_projection_save_old_new_compatibility_and_no_acquisition(e1):
    g = ready(e1)
    pack_research.initialize()
    observations = store.rows("SELECT * FROM sealed_observations")
    protected = collection.export_data(e1["actor"])
    with (
        patch("httpx.Client.send", side_effect=AssertionError("No acquisition")),
        patch("pokemon_hunter.beta.ebay_hunts.search", side_effect=AssertionError("No acquisition")),
    ):
        filters = dict(stock="out-of-stock", age="all", max_price="28", currency="USD", sort="price")
        context = packs.project(e1["actor"], g["id"], "123", "tcgdex:en:sv03.5", filters=filters)
        assert context["expansions"][0]["count"] == 1
        assert len(offers(context)[0]["observations"]) >= 2
        key = pack_research.save(
            e1["actor"], g["id"], "123", "tcgdex:en:sv03.5", goal_version=g["version"], filters=filters
        )
        raw = pack_research.one(e1["actor"], key)["snapshot"]
        later = pack_research.reopen(e1["actor"], key, now=NOW + timedelta(days=100))
        assert later["offer_filters"] == filters and len(offers(later)) == len(offers(context))
        assert pack_research.one(e1["actor"], key)["snapshot"] == raw
        # Actual v1 payload structure without E4b fields reopens with defaults and unchanged bytes.
        old = json.loads(raw)
        old["context"].pop("offer_filters")
        for o in offers(old["context"]):
            for field in ("eligibility", "representative", "price_comparable"):
                o.pop(field, None)
        oldraw = json.dumps(old)
        collection.execute(
            "UPDATE saved_pack_research SET snapshot=%s,snapshot_sha256=%s WHERE id=%s",
            [oldraw, hashlib.sha256(oldraw.encode()).hexdigest(), key],
        )
        assert pack_research.reopen(e1["actor"], key)["offer_filters"] == f.validate()
        assert pack_research.one(e1["actor"], key)["snapshot"] == oldraw
        assert e1["b"].get(f"/packs/saved/{key}/").status_code == 404
        assert e1["b"].get("/packs/", {"goal": g["id"], **filters}).status_code == 404
        page = e1["a"].get(
            "/packs/", {"goal": g["id"], "species": "123", "expansion": "tcgdex:en:sv03.5", **filters}
        )
        assert page.status_code == 200
        assert b"Reset offer filters" in page.content and b"View source" in page.content
        assert b"Buy now" not in page.content and b">View offer<" not in page.content
        assert e1["a"].get("/packs/", {"goal": g["id"], "max_price": "1"}).status_code == 400
    assert store.rows("SELECT * FROM sealed_observations") == observations
    assert collection.export_data(e1["actor"]) == protected
