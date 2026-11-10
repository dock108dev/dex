"""Controlled Shopping browser failures; engineering fixtures, never product acceptance."""

import uuid
from urllib.parse import urlsplit

import pytest
from test_account_reads import prepared as prepared
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_effective_collection import cx as cx
from test_migration import snapshot as snapshot
from test_perf04_workflows import browser_app as browser_app
from test_sealed_catalog import e1 as e1

pytestmark = pytest.mark.allow_hosts(["127.0.0.1"])


def received(run_id, account, binding):
    from datetime import UTC, datetime, timedelta

    return dict(
        run_id=run_id,
        state="complete",
        running=False,
        expires_in_seconds=1800,
        choices=dict(query="Venusaur", intent="deals", product_type="mixed_lots"),
        counts=dict(summary_count=1),
        has_next=False,
        results=[
            dict(
                id="engineering-result",
                title="Engineering received lot",
                listing_price="10.00",
                shipping=None,
                delivered_total=None,
                price_kind="current_bid",
                ends_at=(datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                currency="USD",
                classification="unpriced",
                reference=None,
                comparison={},
                reason="Contents unassessed",
                item_url="https://www.ebay.com/itm/123456789012",
            )
        ],
        authority=dict(account_id=account, binding=binding),
    )


@pytest.mark.parametrize("dual", [False, True])
def test_received_lot_shows_costs_and_review_action_at_narrow_width(browser_app, monkeypatch, dual):
    from playwright.sync_api import expect

    from pokemon_hunter.beta import discovery

    state, page, base, requests, errors = browser_app
    monkeypatch.setattr(discovery.ebay_hunts, "status", lambda: dict(enabled=True, configured=True))
    run_id = str(uuid.uuid4())
    calls = []

    def route(request):
        calls.append(request.request.method)
        binding = request.request.header_value("X-Dex-Shopping-Binding")
        if urlsplit(request.request.url).query:
            value = received(run_id, state["actor"].user_id, binding)
            value["results"][0].update(
                buying_options=["FIXED_PRICE"],
                price_kind="fixed_price",
                buy_now_price="10.00",
                shipping="2.00",
                delivered_total="12.00",
                buy_now_delivered_total="12.00",
            )
            if dual:
                value["results"][0].update(
                    buying_options=["FIXED_PRICE", "AUCTION"],
                    price_kind="current_bid",
                    current_bid="7.00",
                    listing_price="7.00",
                    delivered_total="9.00",
                )
            request.fulfill(json=value)
        else:
            request.continue_()

    page.route("**/api/shopping/discovery/**", route)
    page.goto(base + f"/shopping/?run_id={run_id}&q=Venusaur")
    row = page.locator(".compact-lot").first
    expect(row).to_contain_text("Buy It Now · delivered")
    expect(row).to_contain_text("Asking price: $10.00 · Shipping: $2.00")
    if dual:
        expect(row).to_contain_text("Auction current bid: $7.00 · Bid + shipping before tax: $9.00")
        page.locator(".result-settings > summary").click()
        page.locator("#lot-buying-mode").select_option("auction")
        expect(row).to_contain_text("Auction · bid + shipping")
        expect(row).to_contain_text("$9.00")
        expect(row).to_contain_text("Current bid: $7.00 · Shipping: $2.00")
        page.locator("#lot-buying-mode").select_option("buy_now")
        expect(row).to_contain_text("Buy It Now · delivered")
        expect(row).to_contain_text("$12.00")
        page.locator("#lot-buying-mode").select_option("both")
    expect(row.get_by_role("link", name="Assess lot")).to_be_visible()
    expect(row.get_by_role("link", name="Open seller listing on eBay")).to_be_visible()
    for width in (320, 390, 1280):
        page.set_viewport_size(dict(width=width, height=900))
        page.add_style_tag(content="html { font-size: 200% !important; }")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
    assert all(method == "GET" for method in calls)
    assert not errors


def test_options_failure_and_keyboard_recovery_preserve_results_at_narrow_sizes(browser_app, monkeypatch):
    from playwright.sync_api import expect

    from pokemon_hunter.beta import discovery

    state, page, base, requests, errors = browser_app
    monkeypatch.setattr(discovery.ebay_hunts, "status", lambda: dict(enabled=True, configured=True))
    run_id = str(uuid.uuid4())
    pending, calls = [], []

    def route(request):
        calls.append((request.request.method, request.request.url))
        binding = request.request.header_value("X-Dex-Shopping-Binding")
        if urlsplit(request.request.url).query:
            request.fulfill(json=received(run_id, state["actor"].user_id, binding))
        elif not pending:
            pending.append(request)
        else:
            request.fulfill(
                json=dict(
                    provider=dict(enabled=True, configured=True),
                    goals=[],
                    sets=[],
                    authority=dict(account_id=state["actor"].user_id, binding=binding),
                )
            )

    page.route("**/api/shopping/discovery/**", route)
    page.goto(base + f"/shopping/?run_id={run_id}&q=Venusaur&budget=100")
    expect(page.get_by_text("Engineering received lot", exact=True)).to_be_visible()
    assert len(pending) == 1
    expect(page.get_by_role("button", name="Find lots", exact=True)).to_be_enabled()
    pending[0].fulfill(status=503, json=dict(error="runtime_busy"))
    recover = page.get_by_role("button", name="Reload search options", exact=True)
    expect(recover).to_be_visible()
    for width in (320, 390, 1280):
        page.set_viewport_size(dict(width=width, height=900))
        page.add_style_tag(content="html { font-size: 200% !important; }")
        recover.scroll_into_view_if_needed()
        box = recover.bounding_box()
        assert box and box["x"] >= 0 and box["x"] + box["width"] <= width + 1
        expect(page.get_by_text("Engineering received lot", exact=True)).to_be_visible()
    recover.focus()
    recover.press("Enter")
    expect(recover).to_be_hidden()
    assert page.locator("#discovery-query").input_value() == "Venusaur"
    assert not any("/discovery/catalog/" in url for _, url in calls)
    assert all(method == "GET" for method, _ in calls)
    assert not errors


def test_lost_search_response_reconciles_locally_without_reacquisition(browser_app, monkeypatch):
    from playwright.sync_api import expect

    from pokemon_hunter.beta import discovery

    state, page, base, requests, errors = browser_app
    monkeypatch.setattr(discovery.ebay_hunts, "status", lambda: dict(enabled=True, configured=True))
    posts, reads = [], []
    run_id = str(uuid.uuid4())

    def route(request):
        binding = request.request.header_value("X-Dex-Shopping-Binding")
        if request.request.method == "POST":
            posts.append(request.request.header_value("X-Dex-Shopping-Action"))
            request.abort("failed")
        elif "request_id=" in request.request.url:
            reads.append(request.request.url)
            request.fulfill(json=received(run_id, state["actor"].user_id, binding))
        else:
            request.fulfill(
                json=dict(
                    provider=dict(enabled=True, configured=True),
                    goals=[],
                    sets=[],
                    authority=dict(account_id=state["actor"].user_id, binding=binding),
                )
            )

    page.route("**/api/shopping/discovery/**", route)
    page.goto(base + "/shopping/?q=Venusaur")
    search = page.get_by_role("button", name="Find lots", exact=True)
    search.click()
    expect(search).to_be_disabled()
    expect(page.get_by_text("Its outcome is unknown.", exact=False)).to_be_visible()
    reload = page.get_by_role("button", name="Reload search status", exact=True)
    reload.focus()
    reload.press("Enter")
    expect(page.get_by_text("Engineering received lot", exact=True)).to_be_visible()
    assert len(posts) == 1 and uuid.UUID(posts[0])
    assert len(reads) == 1 and posts[0] in reads[0]
    assert not errors


def test_lot_values_arrive_automatically_and_controls_stay_local(browser_app):
    import copy
    import uuid
    from datetime import UTC, datetime, timedelta

    from playwright.sync_api import expect

    state, page, base, requests, errors = browser_app
    run_id, calls = str(uuid.uuid4()), []

    def route(handler):
        request = handler.request
        calls.append((request.method, request.url))
        binding = request.header_value("X-Dex-Shopping-Binding")
        if "run_id=" not in request.url:
            handler.fulfill(
                json=dict(
                    provider=dict(enabled=True, configured=True),
                    goals=[],
                    sets=[],
                    authority=dict(account_id=state["actor"].user_id, binding=binding),
                )
            )
            return
        result = received(run_id, state["actor"].user_id, binding)
        first = result["results"][0]
        first.update(
            title="Engineering complete lot",
            shipping="5.00",
            delivered_total="15.00",
            buy_now_price="40.00",
            buy_now_delivered_total="45.00",
        )
        second = copy.deepcopy(first)
        second.update(
            id="later",
            title="Engineering later lot",
            buy_now_price=None,
            ends_at=(datetime.now(UTC) + timedelta(hours=60)).isoformat(),
        )
        result["results"].append(second)
        if "view=values" in request.url:
            result["values_checked"] = True
            first["lot_value"] = dict(
                total="100.00",
                subtotal="100.00",
                priced_quantity=3,
                identified_quantity=3,
                stated_quantity=3,
                bid_difference="85.00",
                buy_now_difference="55.00",
                reason="Dated ungraded references",
                references=[],
                cards=[],
            )
        handler.fulfill(json=result)

    page.route("**/api/shopping/discovery/**", route)
    page.goto(base + f"/shopping/?run_id={run_id}&q=Lapras")
    page.locator("#offer-engineering-result .lot-more > summary").click()
    expect(page.get_by_text("$100.00 ungraded lot value", exact=True)).to_be_visible()
    expect(
        page.get_by_text("Buy It Now + shipping: $55.00 below reference · before tax", exact=True)
    ).to_be_visible()
    page.locator(".result-settings > summary").click()
    page.locator("#lot-time-window").select_option("48")
    expect(page.get_by_text("Engineering later lot", exact=True)).to_have_count(0)
    count = len(calls)
    page.locator("#lot-time-window").select_option("72")
    expect(page.get_by_text("Engineering later lot", exact=True)).to_be_visible()
    page.locator("#lot-buying-mode").select_option("buy_now")
    expect(page.get_by_text("Engineering later lot", exact=True)).to_have_count(0)
    page.locator("#lot-value-sort").select_option("value")
    assert len(calls) == count
    assert all(method == "GET" for method, _ in calls)
    for width in (320, 390, 1280):
        page.set_viewport_size(dict(width=width, height=900))
        for name in ("lot-time-window", "lot-buying-mode", "lot-value-sort"):
            control = page.locator("#" + name)
            control.scroll_into_view_if_needed()
            box = control.bounding_box()
            assert box and box["x"] >= 0 and box["x"] + box["width"] <= width + 1
    assert not errors


def test_singles_filter_review_back_reload_and_expired_receipt_are_local(browser_app):
    from playwright.sync_api import expect

    state, page, base, _, errors = browser_app
    run_id, calls = str(uuid.uuid4()), []
    expired = False

    def route(handler):
        request = handler.request
        calls.append(request.method)
        binding = request.header_value("X-Dex-Shopping-Binding")
        result = received(run_id, state["actor"].user_id, binding)
        if not urlsplit(request.url).query:
            handler.fulfill(
                json=dict(
                    provider={"enabled": True, "configured": True},
                    goals=[],
                    sets=[],
                    authority=result["authority"],
                )
            )
            return
        if expired:
            handler.fulfill(status=404, body="Expired")
            return
        result["choices"].update(
            query="Lapras", product_type="singles", single_buying="auction", sort="best_match"
        )
        result["scope_label"] = "Singles · Lapras"
        result["counts"]["summary_count"] = 2
        first = result["results"][0]
        first.update(
            title="Controlled Fossil Lapras",
            buying_options=["AUCTION"],
            release=dict(
                status="eligible", name="Lapras", set_name="Fossil", collector_number="25", finish="normal"
            ),
        )
        result["results"].append(
            dict(first, id="later", title="Controlled later Lapras", release={"status": "later"})
        )
        handler.fulfill(json=result)

    page.route("**/api/shopping/discovery/**", route)
    page.goto(
        base
        + f"/shopping/?run_id={run_id}&q=Lapras&product_type=singles&single_buying=auction&single_release=through2000"
    )
    expect(page.get_by_text("2 received · 1 eligible in this view")).to_be_visible()
    assert not page.get_by_text("Controlled later Lapras").count()
    page.locator("#single-release").select_option("all")
    expect(page.get_by_text("Controlled later Lapras")).to_be_visible()
    page.locator("#single-release").select_option("through2000")
    page.get_by_role("link", name="Review listing").click()
    page.get_by_role("link", name="Back to search").click()
    offer = page.locator("#offer-engineering-result")
    expect(offer).to_be_focused()
    page.reload()
    expect(offer).to_be_focused()
    expect(page.locator("#discovery-query")).to_have_value("Lapras")
    expect(page.locator("#single-buying")).to_have_value("auction")
    expect(page.locator("#single-release")).to_have_value("through2000")
    expired = True
    page.reload()
    expect(page.get_by_text("Your inputs are ready for a new search.", exact=False)).to_be_visible()
    expect(page.get_by_role("button", name="Find singles")).to_be_enabled()
    expect(page.locator("#discovery-query")).to_have_value("Lapras")
    assert calls and set(calls) == {"GET"}
    assert not errors
