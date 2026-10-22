"""Listing browser contracts over disposable state and mocked seller details."""

import json
from urllib.parse import urlencode, urlsplit


def exercise(page, base, output):
    from playwright.sync_api import expect

    checks = []
    page.set_viewport_size(dict(width=1280, height=900))
    page.goto(base + "/shopping/check/")
    expect(page.locator("#listing-identifier")).to_be_enabled()
    # Local authorized catalog only; provider responses below are engineering replays.
    catalog = page.request.get(base + "/api/shopping/lot-catalog/").json()
    p = catalog["cards"][0]
    authority = catalog["authority"]
    assert p["id"]
    identifier = "123456789012"
    run_id = "11111111-1111-4111-8111-111111111111"
    listing = dict(
        item_id="v1|123456789012|0",
        item_url="https://www.ebay.com/itm/123456789012",
        title="<script>window.SHOP03_BAD=true</script> Engineering long seller title with card details and unknown lot contents",
        price=dict(amount="3.00", currency="USD"),
        price_kind="current_bid",
        buying_options=["AUCTION", "FIXED_PRICE"],
        current_bid=dict(amount="3.00", currency="USD"),
        buy_now=dict(amount="9.00", currency="USD"),
        shipping=dict(amount=None, currency=None),
        seller_lot_size=12,
        api_lot_size="1",
        stock_quantity=27,
        condition="Seller-stated condition; not verified",
        aspects=[dict(name="Number of Cards", value="12")],
        clues=dict(
            grade="raw", grader=None, condition="", language=None, edition=None, finish=None, conflicts=[]
        ),
        proposals=[dict(p, quantity=0)],
        unknown_contents=12,
    )
    mode = ["success"]
    held = []
    loads = []
    stops = []
    compares = []

    def boundary(route):
        req = route.request
        path = urlsplit(req.url).path
        if path == "/api/shopping/listing/":
            if req.method == "POST":
                loads.append(req.post_data_json)
            if mode[0] == "held" and req.method == "POST":
                held.append(route)
                return
            value = dict(
                run_id=run_id,
                running=False,
                state="failed" if mode[0] == "failure" else "complete",
                expires_in_seconds=1800,
                counts=dict(oauth=0, detail=1, resolution=0, total=1),
                authority=authority,
            )
            if mode[0] == "failure":
                value["error"] = "Engineering unavailable listing; no retry."
            else:
                value["listing"] = listing
            route.fulfill(status=200, json=value)
            return
        if path == "/api/shopping/listing/candidate/":
            route.fulfill(
                status=200,
                json=dict(
                    listing=dict(listing, discovery_origin=dict(run_id=run_id, result_id="a" * 24)),
                    expires_in_seconds=1500,
                    context=dict(choices=dict(intent="deals"), scope=None),
                    authority=authority,
                ),
            )
            return
        if path.endswith("/stop/"):
            stops.append(req.post_data_json)
            route.fulfill(status=200, json=dict(state="stopped", authority=authority))
            return
        if path == "/api/shopping/listing/review/" and req.method == "POST":
            data = req.post_data_json
            # Replay has no provider worker. Strip only its nonexistent origin;
            # actual review validation, retention and comparison stay server-owned.
            data["review"]["detail_run"] = None
            data["review"]["discovery_origin"] = None
            route.continue_(post_data=json.dumps(data))
            return
        if path == "/api/shopping/listing/compare/":
            data = req.post_data_json
            data["review"]["detail_run"] = None
            data["review"]["discovery_origin"] = None
            compares.append(data)
            route.continue_(post_data=json.dumps(data))
            return
        route.continue_()

    page.route("**/api/shopping/listing/**", boundary)

    def passed(name):
        checks.append(
            dict(
                name=name,
                status="PASS",
                evidence_class="engineering replay with actual local review/calculator services",
            )
        )

    try:
        destination = "/shopping/?" + urlencode(dict(q="Abra", focus="offer-" + "a" * 24, scroll="37"))
        page.goto(
            base
            + "/shopping/check/?"
            + urlencode(dict(discovery_run=run_id, item_id="a" * 24, **{"return": destination}))
        )
        expect(page.locator("#listing-preview")).to_be_visible()
        expect(page.locator("#listing-identifier")).to_have_value(listing["item_id"])
        expect(page.locator("#check-back")).to_have_attribute("href", destination)
        assert not loads
        page.get_by_text("Seller details and identity notes", exact=True).click()
        assert "Separate buy-now" in page.locator("#listing-details").inner_text()
        page.locator("#discard-listing").click()
        passed("revealed temporary summary and checked return arrive without an eBay detail request")
        page.locator("#review-editor > summary").click()
        page.get_by_text("Listing reference, tax and other costs", exact=True).click()
        page.locator("#review-title").fill("My reviewed edits")
        page.locator("#review-price").fill("7.25")
        page.locator("#listing-tools > summary").click()
        page.locator("#listing-identifier").fill(identifier)
        page.locator("#load-listing").click()
        expect(page.locator("#listing-preview")).to_be_visible()
        expect(page.locator("#review-title")).to_have_value("My reviewed edits")
        assert not page.evaluate("() => Boolean(window.SHOP03_BAD)")
        assert "27" in page.locator("#listing-details").inner_text()
        page.locator("#discard-listing").click()
        expect(page.locator("#review-price")).to_have_value("7.25")
        passed("loading previews untrusted text and keeps reviewed work until explicit replacement")
        page.locator("#load-listing").click()
        page.locator("#use-listing").click()
        expect(page.locator("#review-price")).to_have_value("3.00")
        expect(page.locator("#review-price-kind")).to_have_value("current_bid")
        expect(page.locator("#review-buy-now")).to_contain_text("9.00")
        assert "Ungraded" in page.locator("#review-cards summary").first.inner_text()
        assert "Reference image unavailable" in page.locator("#review-cards").inner_text()
        expect(page.locator("#review-shipping")).to_have_value("")
        q = page.get_by_label("Cards inside this one lot", exact=True)
        expect(q).to_have_value("0")
        q.fill("2")
        expect(page.locator("#review-unknown")).to_have_value("10")
        page.locator("#review-planned_bid").fill("4")
        page.locator("#review-unknown").fill("10")
        page.locator("#check-compare").click()
        expect(page.locator("#check-results")).to_be_visible()
        assert compares[-1]["review"]["cards"][0]["quantity"] == 2
        assert compares[-1]["review"]["price"] == "3.00"
        assert compares[-1]["review"]["price_kind"] == "current_bid"
        assert compares[-1]["review"]["planned_bid"] == "4"
        assert compares[-1]["review"]["cards"][0]["grade"] == "raw"
        assert compares[-1]["review"]["unknown_contents"] == 10
        assert "incomplete" in page.locator("#check-results").inner_text()
        passed(
            "stock is separate; corrected quantities and whole-lot costs reach existing arithmetic; partial contents stay subtotal"
        )
        for width in (1280, 390, 320):
            page.set_viewport_size(dict(width=width, height=900))
            assert not page.evaluate("() => document.documentElement.scrollWidth>innerWidth")
            page.screenshot(path=str(output / f"engineering-shop03-{width}.png"), full_page=True)
        page.evaluate(
            """() => { const values=[...document.querySelectorAll('body,body *')].map(e=>[e,parseFloat(getComputedStyle(e).fontSize)]); values.forEach(([e,n])=>e.style.fontSize=(n*2)+'px'); }"""
        )
        assert not page.evaluate("() => document.documentElement.scrollWidth>innerWidth")
        page.screenshot(path=str(output / "engineering-shop03-text200.png"), full_page=True)
        passed("1280 390 320 layouts and actual doubled text without horizontal overflow")
        page.locator("#review-title").fill("Corrected retained title")
        mode[0] = "failure"
        page.locator("#load-listing").click()
        expect(page.locator("#check-status")).to_contain_text("unavailable")
        expect(page.locator("#review-title")).to_have_value("Corrected retained title")
        page.locator("#check-query").fill(p["name"])
        page.locator("#check-find button").click()
        expect(page.locator("#check-matches button").first).to_be_visible()
        assert len(loads) == 3
        passed("provider failure preserves review and local card search makes no provider calls")
        page.locator("#check-back").click()
        expect(page.locator("#discovery-form")).to_be_visible()
        page.get_by_role("link", name="Check a listing/lot", exact=True).click()
        expect(page.locator("#review-title")).to_have_value("Corrected retained title")
        expect(page.locator("#check-results")).not_to_be_visible()
        assert len(loads) == 3
        passed("navigation restores temporary inputs without automatic comparison or provider request")
        mode[0] = "held"
        page.locator("#load-listing").click()
        expect(page.locator("#stop-listing")).to_be_enabled()
        page.locator("#stop-listing").click()
        for route in held:
            route.fulfill(
                status=200,
                json=dict(
                    run_id=run_id,
                    state="complete",
                    running=False,
                    listing=listing,
                    expires_in_seconds=1800,
                    authority=authority,
                ),
            )
        expect(page.locator("#listing-preview")).not_to_be_visible()
        expect(page.locator("#review-title")).to_have_value("Corrected retained title")
        page.wait_for_function('() => document.querySelector("#load-listing").disabled === false')
        assert len(loads) == 4
        assert page.evaluate(
            '() => !Object.keys(localStorage).some(k=>k.includes("listing")) && !Object.keys(sessionStorage).some(k=>k.includes("listing"))'
        )
        passed("Stop suppresses late listing publication and no assisted content enters browser storage")
        mode[0] = "success"
        listing["price"] = dict(amount=None, currency=None)
        listing["current_bid"] = dict(amount=None, currency=None)
        listing["shipping"] = dict(amount="0.50", currency="USD")
        page.locator("#load-listing").click()
        expect(page.locator("#listing-preview")).to_be_visible()
        page.locator("#use-listing").click()
        expect(page.locator("#review-price")).to_have_value("")
        expect(page.locator("#review-currency")).to_have_value("USD")
        expect(page.locator("#review-shipping")).to_have_value("0.50")
        expect(page.locator("#review-buy-now")).to_contain_text("9.00")
        assert len(loads) == 5
        passed(
            "unknown auction bid remains blank while known USD shipping carries forward independently of buy-now asking price"
        )
        return checks
    finally:
        page.unroute("**/api/shopping/listing/**", boundary)
        page.set_viewport_size(dict(width=1280, height=900))
