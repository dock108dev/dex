"""Isolated listing parsing, bounded detail transport and temporary reviews."""

import asyncio
import json
import time
from types import SimpleNamespace

import httpx
import pytest
from price_snapshot_helpers import NOW
from price_snapshot_helpers import b2 as b2
from price_snapshot_helpers import env as env
from price_snapshot_helpers import setup as setup
from price_snapshot_helpers import shop as shop
from price_snapshot_helpers import snapshot as snapshot
from test_discovery import discovery as discovery
from test_discovery import ledger
from test_discovery_comparison import active
from test_lot_calculator import post
from test_lot_calculator import workspace as workspace

from pokemon_hunter.beta import collection, listing_details, price_snapshots, shopping
from pokemon_hunter.beta import discovery as d
from pokemon_hunter.beta import listing_check as c
from pokemon_hunter.beta.discovery_transport import ProviderFailure, Transport

ITEM = "123456789012"
VAR = "987654321012"
REST = f"v1|{ITEM}|0"


def test_details_service_imports_share_stateless_authority():
    assert c.parse_identifier is listing_details.parse_identifier
    assert c.validate_response is listing_details.validate_response
    assert c.details is listing_details.details


@pytest.mark.parametrize(
    "value,variation,rest",
    [
        (ITEM, "0", None),
        (REST, "0", REST),
        (f"v1|{ITEM}|{VAR}", VAR, f"v1|{ITEM}|{VAR}"),
        (f"https://www.ebay.com/itm/{ITEM}", "0", None),
        (f"https://ebay.com/itm/Named-card/{ITEM}?var={VAR}", VAR, None),
        (f"https://m.ebay.com/itm/{ITEM}?_trksid=abc", "0", None),
    ],
)
def test_supported_identifiers(value, variation, rest):
    assert c.parse_identifier(value) == dict(legacy=ITEM, variation=variation, rest=rest)


@pytest.mark.parametrize(
    "value",
    [
        f"http://www.ebay.com/itm/{ITEM}",
        f"https://ebay.com.evil.test/itm/{ITEM}",
        f"https://www.ebay.com@evil.test/itm/{ITEM}",
        f"https://evil@www.ebay.com/itm/{ITEM}",
        f"https://www.ebay.com:443/itm/{ITEM}",
        f"https://www.ebay.com./itm/{ITEM}",
        f"https://ebay.us/{ITEM}",
        f"https://ebay.com/itm/{ITEM}?var={VAR}&var={VAR}",
        f"https://ebay.com/itm/{ITEM}?var=%39{VAR[1:]}",
        f"v1%7C{ITEM}%7C0",
        f"v1%257C{ITEM}%257C0",
        f"https://ebay.com/itm/{ITEM}#redirect",
        f"https://ebay.com/itm/{ITEM}?url=https://evil.test",
        f"https://ebay.com/itm/{ITEM}?var=0&var=",
        f"https://ebay.com/itm/{ITEM}/../{ITEM}",
        f"v2|{ITEM}|0",
        f"v1|{ITEM}|01",
        "javascript:alert(1)",
        "file:///etc/passwd",
        "001234567890",
        "１２３４５６７８９０１２",
        "1",
        "123\n456789012",
    ],
)
def test_hostile_identifiers_rejected(value):
    with pytest.raises(ValueError):
        c.parse_identifier(value)


class Bytes(httpx.AsyncByteStream):
    def __init__(self, value):
        self.value = value

    async def __aiter__(self):
        yield self.value


def raw(**changes):
    result = dict(
        itemId=REST,
        legacyItemId=ITEM,
        title="Engineering Base Set Abra 43",
        buyingOptions=["FIXED_PRICE"],
        price=dict(value="3.50", currency="USD"),
        shippingOptions=[],
        estimatedAvailabilities=[dict(estimatedAvailableQuantity=27)],
    )
    result.update(changes)
    return result


@pytest.mark.parametrize(
    "changes",
    [
        dict(itemId=f"v1|{ITEM}|{VAR}"),
        dict(itemId="v1|223456789012|0"),
        dict(itemId=None),
        dict(legacyItemId="223456789012"),
        dict(primaryItemGroup={"itemGroupId": ITEM}),
        dict(itemEndDate="2000-01-01T00:00:00Z"),
        dict(itemEndDate="bad"),
        dict(buyingOptions=["CLASSIFIED_AD"]),
        dict(estimatedAvailabilities=[dict(estimatedAvailabilityStatus="OUT_OF_STOCK")]),
    ],
)
def test_unresolved_unavailable_identity_rejected(changes):
    with pytest.raises(ValueError):
        c.details(ITEM, raw(**changes))


def test_exact_variation_and_stock_lot_meanings():
    r = c.details(
        f"v1|{ITEM}|{VAR}",
        raw(
            itemId=f"v1|{ITEM}|{VAR}",
            primaryItemGroup={"itemGroupId": ITEM},
            lotSize="10",
            title="Lot of 4 cards",
            localizedAspects=[dict(name="Number of Cards", value="4")],
        ),
    )
    assert r["seller_lot_size"] == 4 and r["stock_quantity"] == 27 and r["api_lot_size"] == "10"
    assert r["shipping"] == dict(amount=None, currency=None)
    assert r["item_url"].endswith("?var=" + VAR)
    assert "description" not in r


def test_conflicting_lot_size_foreign_costs_and_html_are_text():
    r = c.details(
        ITEM,
        raw(
            title="<script>evil()</script> lot of 5",
            localizedAspects=[dict(name="Number of Cards", value="4")],
            price=dict(value="4", currency="GBP"),
            shippingOptions=[dict(shippingCost=dict(value="0", currency="GBP"))],
            description="<script>evil()</script>",
        ),
    )
    assert r["seller_lot_size"] is None and r["price"]["currency"] == "GBP"
    assert r["shipping"] == dict(amount="0.00", currency="GBP")
    assert r["title"].startswith("<script>") and "description" not in r


def run(env, identifier=ITEM):
    r = d.Run(
        "engineering-run",
        (str(env.root), env.actor.user_id, "session"),
        d.Choices(),
        None,
        [],
        operation="detail",
        identifier=identifier,
    )
    r.counts = {"oauth": 0, "detail": 0, "resolution": 0, "total": 0}
    d._arm_deadline(r)
    return r


class Fake:
    calls = []

    async def request(self, stage, **kwargs):
        self.calls.append(stage)
        return (
            dict(access_token="fixture-token", expires_in=3600, token_type="Bearer")
            if stage == "oauth"
            else raw()
        )

    async def close(self):
        pass


def test_token_reuse_and_no_browse_fallback(discovery, monkeypatch):
    Fake.calls = []
    monkeypatch.setattr(c, "Transport", Fake)
    first, second = run(discovery), run(discovery, REST)
    asyncio.run(c._acquire(first, ("fixture", "secret")))
    asyncio.run(c._acquire(second, ("fixture", "secret")))
    assert Fake.calls == ["oauth", "resolution", "detail"]
    assert first.counts["total"] == 2 and second.counts["total"] == 1
    body = ledger(discovery).read_text()
    assert "fixture-token" not in body and "Engineering Base Set" not in body
    assert body.count('"state":"admitted"') == 3


def test_explicit_operation_ceilings_and_stop(discovery):
    async def exercise():
        r = run(discovery)
        f = Fake()
        for _ in range(2):
            await d._dispatch(r, f, "resolution", r.deadline, identifier=ITEM)
        for stage in ["resolution", "detail", "browse", "unknown"]:
            with pytest.raises(ProviderFailure):
                await d._dispatch(r, f, stage, r.deadline)
        r.cancel.set()
        with pytest.raises(d._Stopped):
            await d._dispatch(r, f, "oauth", r.deadline)
        assert r.counts["total"] == 2

    asyncio.run(exercise())


def test_stop_inflight_consumed_and_no_publication(discovery, monkeypatch):
    r = run(discovery)

    class Delayed(Fake):
        async def request(self, stage, **kwargs):
            r.cancel.set()
            await asyncio.sleep(0.01)
            return raw()

    async def exercise():
        with pytest.raises(d._Stopped):
            await d._dispatch(r, Delayed(), "detail", r.deadline)

    asyncio.run(exercise())
    assert r.counts["total"] == 1
    assert "uncertain" in ledger(discovery).read_text() and not r.raws


@pytest.mark.parametrize(
    "stage,identifier,path",
    [
        ("detail", REST, "/buy/browse/v1/item/v1|123456789012|0"),
        ("resolution", ITEM, "/buy/browse/v1/item/get_item_by_legacy_id"),
        ("resolution", f"https://ebay.com/itm/{ITEM}?var={VAR}", "/buy/browse/v1/item/get_item_by_legacy_id"),
    ],
)
def test_official_transport_paths(stage, identifier, path):
    seen = []

    def handle(req):
        seen.append(req)
        return httpx.Response(200, stream=Bytes(b"{}"))

    async def exercise():
        t = Transport(transport=httpx.MockTransport(handle))
        await t.request(stage, timeout=3, token="fixture", identifier=identifier)
        await t.close()

    asyncio.run(exercise())
    req = seen[0]
    assert req.url.host == "api.ebay.com" and req.url.path == path
    assert req.headers["X-EBAY-C-ENDUSERCTX"] == "contextualLocation=country%3DUS"
    assert req.url.params["quantity_for_shipping_estimate"] == "1"
    assert "postal" not in str(req.url).lower()
    if stage == "resolution":
        assert req.url.params["legacy_item_id"] == ITEM
    if "var=" in identifier:
        assert req.url.params["legacy_variation_id"] == VAR


@pytest.mark.parametrize("mode", ["redirect", "oversize", "compressed", "malformed", "failure"])
def test_no_retry_redirect_or_unbounded_body(mode):
    seen = []

    def handle(req):
        seen.append(req)
        return (
            httpx.Response(302, headers={"location": "https://evil.test"})
            if mode == "redirect"
            else httpx.Response(
                200,
                stream=Bytes(
                    b"x" * (2 * 1024 * 1024 + 1)
                    if mode == "oversize"
                    else b"no"
                    if mode == "malformed"
                    else b"{}"
                ),
                headers={"content-encoding": "gzip"} if mode == "compressed" else {},
            )
            if mode != "failure"
            else httpx.Response(404)
        )

    async def exercise():
        t = Transport(transport=httpx.MockTransport(handle))
        with pytest.raises(ProviderFailure):
            await t.request("detail", timeout=3, token="fixture", identifier=REST)
        await t.close()

    asyncio.run(exercise())
    assert len(seen) == 1


def review_value(p, **changes):
    value = dict(
        title="Engineering review",
        listing_url="",
        price="3",
        currency="USD",
        shipping="",
        tax="",
        other_costs="",
        unknown_contents=None,
        cards=[
            dict(
                printing_id=p["id"],
                quantity=2,
                grade="raw",
                condition="",
                grader="",
                language="",
                edition="",
                finish="",
            )
        ],
    )
    value.update(changes)
    return value


def test_review_corrections_existing_math_partial_and_foreign(setup, monkeypatch):
    _, p = active(setup, permanent=False)
    monkeypatch.setattr(c, "datetime", SimpleNamespace(now=lambda tz: NOW))
    # Fixture catalog set must be included by the ordinary vintage calculator.
    collection.execute("UPDATE catalog_sets SET name='Base Set'")
    before = collection.export_data(setup["actor"])
    history = shopping.listing(setup["actor"])
    v = review_value(p)
    result = c.compare(setup["actor"], v)
    r = result["scenarios"]["raw"]["result"]
    assert r["coverage"]["selected_units"] == 2 and r["coverage"]["priced_units"] == 2
    assert r["known_selected_subtotal"] == "5.10" and r["full_lot_total"] is None
    assert r["comparisons"]["listing_observation"]["base_price"] == "3.00"
    assert r["comparisons"]["listing_observation"]["full_delivered_cost"] is None
    v.update(unknown_contents=0, shipping="0", tax="0", other_costs="0")
    r = c.compare(setup["actor"], v)["scenarios"]["raw"]["result"]
    assert (
        r["full_lot_total"] == "5.10"
        and r["comparisons"]["listing_observation"]["full_delivered_cost"] == "3.00"
    )
    v["currency"] = "GBP"
    r = c.compare(setup["actor"], v)["scenarios"]["raw"]["result"]
    assert r["comparisons"]["listing_observation"]["full_delivered_cost"] is None
    assert collection.export_data(setup["actor"]) == before and shopping.listing(setup["actor"]) == history
    assert result["save_allowed"] is False and "raw_record" not in json.dumps(result)


@pytest.mark.parametrize(
    "trait,value",
    [("language", "ja"), ("edition", "first_edition"), ("finish", "holo"), ("grade", ""), ("grade", "9")],
)
def test_review_applicability_unknown_or_conflicting_unpriced(setup, monkeypatch, trait, value):
    _, p = active(setup)
    collection.execute("UPDATE catalog_sets SET name='Base Set'")
    monkeypatch.setattr(c, "datetime", SimpleNamespace(now=lambda tz: NOW))
    v = review_value(p)
    v["cards"][0][trait] = value
    result = c.compare(setup["actor"], v)
    assert all(s["result"]["coverage"]["priced_units"] == 0 for s in result["scenarios"].values())


def test_lease_expiry_read_does_not_renew_and_account_isolation(workspace, monkeypatch):
    who = workspace["actor"]
    p = workspace["catalog"][0]
    value = review_value(p)
    c._reviews.clear()
    clock = [100.0]
    monkeypatch.setattr(c.time, "monotonic", lambda: clock[0])
    opened = c.review(who, "session")
    lease = opened["lease"]
    c.review(who, "session", value, lease)
    clock[0] += 100
    assert c.review(who, "session")["expires_in_seconds"] == 1700
    assert c.review(who, "other")["review"] is None
    with pytest.raises(ValueError):
        c.review(who, "other", value, lease)
    clock[0] += 1800
    with pytest.raises(ValueError):
        c.review(who, "session", value, lease)
    assert c.review(who, "session")["review"] is None


def test_http_local_reads_csrf_save_rejection(workspace, monkeypatch):
    client = workspace["a"]
    monkeypatch.setattr(c, "start", lambda *a: pytest.fail("No hidden acquisition"))
    assert client.get("/shopping/check/").status_code == 200
    opened = client.get("/api/shopping/listing/review/").json()
    v = review_value(workspace["catalog"][0])
    payload = dict(review=v, lease=opened["lease"])
    assert (
        client.post(
            "/api/shopping/listing/review/", json.dumps(payload), content_type="application/json"
        ).status_code
        == 403
    )
    assert post(workspace, "/api/shopping/listing/review/", payload).status_code == 200
    assert client.get("/api/shopping/listing/review/").json()["review"] == v
    assert post(workspace, "/api/shopping/listing/compare/", dict(payload, save=True)).status_code == 400
    assert workspace["b"].get("/api/shopping/listing/review/").json()["review"] is None


def test_failure_ends_action_and_identity_mismatch_unpublished(discovery, monkeypatch):
    class Mismatch(Fake):
        calls = []

        async def request(self, stage, **kwargs):
            self.calls.append(stage)
            return (
                dict(access_token="fixture", expires_in=300, token_type="Bearer")
                if stage == "oauth"
                else raw(itemId=f"v1|{ITEM}|{VAR}")
            )

    monkeypatch.setattr(c, "Transport", Mismatch)
    r = run(discovery)
    c._worker(r, discovery.actor, ("fixture", "secret"))
    assert r.state == "failed" and not r.raws and Mismatch.calls == ["oauth", "resolution"]
    assert r.counts["total"] == 2


def test_revoked_authority_stops_later_dispatch(discovery, monkeypatch):
    calls = []

    def revoked(actor):
        calls.append("authority")
        if len(calls) > 1:
            raise ValueError("Session ended")

    monkeypatch.setattr(d, "_authorize", revoked)
    monkeypatch.setattr(c, "Transport", Fake)
    Fake.calls = []
    r = run(discovery)
    c._worker(r, discovery.actor, ("fixture", "secret"))
    assert Fake.calls == ["oauth"] and r.state == "failed" and not r.raws


def test_deadline_before_admission_and_inflight_timeout(discovery, monkeypatch):
    r = run(discovery)
    r.deadline = time.monotonic() - 1

    async def expired():
        with pytest.raises(d._Stopped):
            await d._dispatch(r, Fake(), "detail", r.deadline)

    asyncio.run(expired())
    assert r.counts["total"] == 0 and r.timed_out

    class Slow(Fake):
        async def request(self, *args, **kwargs):
            await asyncio.sleep(1)
            return raw()

    r = run(discovery)
    monkeypatch.setattr(d, "REQUEST_SECONDS", 0.01)

    async def inflight():
        with pytest.raises(ProviderFailure):
            await d._dispatch(r, Slow(), "detail", r.deadline)

    asyncio.run(inflight())
    assert r.counts["total"] == 1 and "uncertain" in ledger(discovery).read_text()


def test_detail_and_review_expiry_do_not_renew_or_cross_sessions(discovery, monkeypatch):
    r = run(discovery)
    r.raws = [c.details(ITEM, raw())]
    r.state = "complete"
    r.acquired_at = time.monotonic()
    d._runs[r.id] = r
    monkeypatch.setattr(c.lot, "catalog", lambda *a, **kw: [])
    assert c.status(discovery.actor, "session", r.id)["listing"]["item_id"] == REST
    from django.http import Http404

    with pytest.raises(Http404):
        c.status(discovery.actor, "other", r.id)
    r.created -= d.EPHEMERAL_SECONDS
    assert "listing" not in c.status(discovery.actor, "session", r.id) and not r.raws


def test_withdrawal_and_expiry_reenter_reference_admission(setup, monkeypatch):
    value, p = active(setup, permanent=False)
    collection.execute("UPDATE catalog_sets SET name='Base Set'")
    monkeypatch.setattr(c, "datetime", SimpleNamespace(now=lambda tz: NOW))
    v = review_value(p)
    assert c.compare(setup["actor"], v)["scenarios"]["raw"]["result"]["coverage"]["priced_units"] == 2
    price_snapshots.remove(value["version"])
    assert c.compare(setup["actor"], v)["scenarios"]["raw"]["result"]["coverage"]["priced_units"] == 0


def test_structured_literal_grade_is_proposed_and_conflicts_remain():
    descriptors = [
        dict(name="Professional Grader", values=[dict(content="Professional Sports Authenticator (PSA)")]),
        dict(name="Grade", values=[dict(content="8")]),
    ]
    value = c.details(ITEM, raw(condition="Graded", conditionDescriptors=descriptors))
    assert value["clues"]["grader"] == "PSA" and value["clues"]["grade"] == "8"
    assert not value["clues"]["conflicts"]
    value = c.details(ITEM, raw(title="Engineering PSA 9", conditionDescriptors=descriptors))
    assert value["clues"]["conflicts"]


def test_start_captures_auth_session_before_worker(discovery, monkeypatch):
    class NoWorker:
        def __init__(self, *a, **kw):
            pass

        def start(self):
            pass

    monkeypatch.setattr(c, "threading", SimpleNamespace(Thread=NoWorker))
    result = c.start(discovery.actor, "session", ITEM, auth_session="engineering-session")
    assert d._runs[result["run_id"]].auth_session == "engineering-session"


def test_signed_out_worker_session_is_rejected(workspace):
    from django.contrib.sessions.models import Session
    from django.core.exceptions import PermissionDenied

    client = workspace["a"]
    key = client.session.session_key
    d._authorize(workspace["actor"], key)
    Session.objects.filter(session_key=key).delete()
    with pytest.raises(PermissionDenied):
        d._authorize(workspace["actor"], key)


@pytest.mark.parametrize("options", [["AUCTION"], ["AUCTION", "FIXED_PRICE"]])
def test_auction_and_mixed_buying_options_keep_amount_meanings(options):
    value = c.details(
        ITEM,
        raw(buyingOptions=options, currentBidPrice=dict(value="4.25", currency="USD")),
    )
    assert value["price_kind"] == "current_bid"
    assert value["current_bid"] == value["price"] == dict(amount="4.25", currency="USD")
    assert value["buy_now"]["amount"] == ("3.50" if "FIXED_PRICE" in options else None)
    assert "final_cost" not in value


def test_missing_bid_does_not_adopt_asking_price_or_zero():
    value = c.details(ITEM, raw(buyingOptions=["AUCTION", "FIXED_PRICE"]))
    assert value["price"] == dict(amount=None, currency=None)
    assert value["buy_now"] == dict(amount="3.50", currency="USD")


def test_review_current_bid_and_planned_bid_are_independent_whole_lot_amounts(setup, monkeypatch):
    _, p = active(setup)
    collection.execute("UPDATE catalog_sets SET name='Base Set'")
    monkeypatch.setattr(c, "datetime", SimpleNamespace(now=lambda tz: NOW))
    value = review_value(
        p,
        price="3",
        planned_bid="4",
        price_kind="current_bid",
        unknown_contents=0,
        shipping="0",
        tax="0",
        other_costs="0",
    )
    result = c.compare(setup["actor"], value)["scenarios"]["raw"]["result"]
    observed, planned = (result["comparisons"][key] for key in ("listing_observation", "planned_bid"))
    assert observed["price_kind"] == "current_bid" and observed["full_delivered_cost"] == "3.00"
    assert planned["price_kind"] == "personal_planned_bid" and planned["full_delivered_cost"] == "4.00"
    assert result["coverage"]["selected_units"] == 2 and result["full_lot_total"] == "5.10"
    value["shipping"] = ""
    result = c.compare(setup["actor"], value)["scenarios"]["raw"]["result"]
    assert all(item["full_delivered_cost"] is None for item in result["comparisons"].values())


def test_listing_catalog_exposes_checked_images_without_reference_values(workspace):
    data = c.catalog(workspace["actor"], workspace["catalog"][0]["name"])
    assert data["cards"] and all("artwork" in row for row in data["cards"])
    assert all(
        not {"cells", "references", "amount", "source_contract"}.intersection(row) for row in data["cards"]
    )
    restored = c.catalog(workspace["actor"], restore={workspace["catalog"][0]["id"]})
    assert len(restored["cards"]) == 1


def test_discovery_handoff_preserves_original_lease_and_local_only_projection(workspace, monkeypatch):
    import uuid

    from django.http import Http404

    actor = workspace["actor"]
    p = workspace["catalog"][0]
    c._reviews.clear()
    origin = dict(run_id=str(uuid.uuid4()), result_id="a" * 24)
    created = time.monotonic() - 200
    available = [True]
    calls = []

    def source(who, session, run_id, result_id):
        calls.append((who, session, run_id, result_id))
        if not available[0] or session != "session":
            raise Http404
        return dict(
            raw=raw(title=f"Lot of 12 {p['name']}"),
            choices=dict(intent="deals"),
            scope=None,
            created=created,
            expires_in_seconds=1600,
            result=dict(identity_candidates=[dict(printing_id=p["id"])]),
        )

    monkeypatch.setattr(d, "review_candidate", source)
    monkeypatch.setattr(c, "start", lambda *args: pytest.fail("No detail operation on handoff"))
    preview = c.candidate(actor, "session", **origin)
    assert preview["listing"]["discovery_origin"] == origin
    assert preview["listing"]["proposals"][0]["quantity"] == 0
    assert "artwork" in preview["listing"]["proposals"][0]
    opened = c.review(actor, "session")
    value = review_value(p, discovery_origin=origin)
    kept = c.review(actor, "session", value, opened["lease"])
    assert 1598 <= kept["expires_in_seconds"] <= 1600
    assert kept["review"]["discovery_origin"] == origin
    available[0] = False
    with pytest.raises(ValueError, match="expired or was stopped"):
        c.review(actor, "session")
    assert c.review(actor, "session")["review"] is None
    assert calls


def test_handoff_catalog_endpoints_are_bound_and_do_not_acquire(workspace, monkeypatch):
    client = workspace["a"]
    monkeypatch.setattr(c, "start", lambda *args: pytest.fail("No hidden provider request"))
    response = client.get("/api/shopping/listing/catalog/?q=" + workspace["catalog"][0]["name"])
    assert response.status_code == 200 and "no-store" in response["Cache-Control"]
    assert response.json()["cards"][0]["id"]
    assert client.get("/api/shopping/listing/catalog/?q=Abra&q=Hypno").status_code == 400
    assert client.get("/api/shopping/listing/candidate/?item_id=unchecked").status_code == 400
    assert client.get("/shopping/check/?discovery_run=unchecked").status_code == 400
    assert client.get("/shopping/check/?return=https://evil.test/").status_code == 400


@pytest.mark.parametrize("suffix", ["2 cards", "x2", "2x", "bundle", "mixed", "bulk"])
def test_multiple_card_seller_claims_never_become_one_confirmed_card(workspace, monkeypatch, suffix):
    p = c.lot.catalog(workspace["actor"], include_current=True)[0]
    monkeypatch.setattr(c.dc, "_matches", lambda entries, clues: [p])
    value = c._proposals(workspace["actor"], c.details(ITEM, raw(title=f"Abra Base Set 43 {suffix}")))
    assert len(value["proposals"]) == 1 and value["proposals"][0]["quantity"] == 0
    assert value["unknown_contents"] is None


def test_structured_card_count_and_checked_mixed_lot_remain_unconfirmed(workspace, monkeypatch):
    import uuid

    actor = workspace["actor"]
    p = c.lot.catalog(actor, include_current=True)[0]
    monkeypatch.setattr(c.dc, "_matches", lambda entries, clues: [p])
    value = c._proposals(
        actor, c.details(ITEM, raw(localizedAspects=[dict(name="Number of Cards", value="2")]))
    )
    assert value["proposals"][0]["quantity"] == 0 and value["unknown_contents"] == 2
    source = dict(
        raw=raw(),
        choices=dict(intent="deals"),
        scope=None,
        created=time.monotonic(),
        expires_in_seconds=1800,
        result=dict(discovery_kind="mixed_lot"),
    )
    monkeypatch.setattr(d, "review_candidate", lambda *args, **kwargs: source)
    candidate = c.candidate(actor, "session", str(uuid.uuid4()), "a" * 24)["listing"]
    assert candidate["proposals"][0]["quantity"] == 0 and candidate["unknown_contents"] is None


def test_checked_exact_target_survives_conflicting_sibling_contents(workspace, monkeypatch):
    import uuid

    actor = workspace["actor"]
    target, sibling = c.lot.catalog(actor, include_current=True)[:2]
    monkeypatch.setattr(c.dc, "_matches", lambda entries, clues: [sibling])
    source = dict(
        raw=raw(),
        choices=dict(intent="deals", printing_id=target["id"]),
        scope=None,
        created=time.monotonic(),
        expires_in_seconds=1800,
        scope_label="Catalog discovery, including cards already owned",
        selected_target=shopping.identity(target),
        result=dict(discovery_kind="single", identity_candidates=[dict(printing_id=target["id"])]),
    )
    monkeypatch.setattr(d, "review_candidate", lambda *args, **kwargs: source)
    candidate = c.candidate(actor, "session", str(uuid.uuid4()), "a" * 24)
    proposals = candidate["listing"]["proposals"]
    assert {row["id"] for row in proposals} == {target["id"], sibling["id"]}
    assert all(row["quantity"] == 0 for row in proposals)
    assert candidate["listing"]["unknown_contents"] is None
    assert candidate["context"]["selected_target"] == shopping.identity(target)
    assert candidate["context"]["choices"]["printing_id"] == target["id"]
