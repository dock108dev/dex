"""Engineering browser checks: disposable installation, controlled Browse only."""

import base64
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit


def exercise(page, base, output):
    from playwright.sync_api import expect

    checks, actions, held = [], [], []
    page.goto(base + "/shopping/check/")
    catalog = page.request.get(base + "/api/shopping/lot-catalog/").json()
    authority = catalog["authority"]
    state = {"query": "", "rows": [], "hold": False, "stopped": False}
    run_id = "11111111-1111-4111-8111-111111111111"

    def row(index, **changes):
        result = dict(
            id=f"engineering-{index}",
            title=f"Engineering listing {index} · {state['query']}",
            item_url="https://www.ebay.com/itm/123456789012?var=123456789013",
            proposed_identity=None,
            identity_candidates=[],
            discovery_kind="mixed_lot",
            listing_price="3.00",
            shipping=None,
            delivered_total=None,
            classification="unpriced",
            reference=None,
            comparison={},
            price_kind="current_bid",
            buying_options=["AUCTION"],
            ends_at=(datetime.now(UTC) + timedelta(hours=2)).isoformat(),
            seller_image="https://i.ebayimg.com/images/g/Engineering/s-l500.jpg",
            reason="Contents unverified. No applicable reference.",
        )
        result.update(changes)
        return result

    def response():
        return dict(
            run_id=run_id,
            authority=authority,
            choices=dict(query=state["query"]),
            expires_in_seconds=1800,
            state="stopped" if state["stopped"] else "complete",
            running=False,
            results=[] if state["stopped"] else state["rows"],
            has_next=not state["stopped"],
            counts=dict(summary_count=len(state["rows"])),
        )

    def boundary(route):
        req = route.request
        path = urlsplit(req.url).path
        if path == "/api/shopping/discovery/":
            if req.method == "POST":
                body = req.post_data_json
                actions.append(body)
                if state["hold"]:
                    held.append(route)
                    return
                if "continuation_run" in body:
                    state["rows"].append(row(len(state["rows"]) + 1))
                else:
                    state["stopped"] = False
                    state["query"] = body["query"]
                    state["rows"] = [row(1)]
                route.fulfill(json=response())
            elif "run_id=" in req.url:
                route.fulfill(json=response())
            else:
                route.fulfill(
                    json=dict(authority=authority, goals=[], provider=dict(enabled=True, configured=True))
                )
        elif path.endswith("/stop/"):
            state["stopped"] = True
            route.fulfill(json=response())
        else:
            route.continue_()

    page.route("**/api/shopping/discovery/**", boundary)
    page.goto(base + "/shopping/")
    expect(page.locator("#discovery-search")).to_be_enabled()
    assert page.locator("#discovery-product-type").input_value() == "mixed_lots"
    assert not page.locator("#discovery-budget").is_visible()
    assert not page.locator("#catalog-cards").is_visible()
    checks.append("One primary search, mixed lots default, optional controls collapsed")

    for query in ("Hypno Fossil", "Jolteon", "Gengar Fossil", "Pokemon Jungle", "Pokemon Cards"):
        before = len(actions)
        page.locator("#discovery-query").fill(query)
        page.wait_for_timeout(250)
        assert len(actions) == before
        page.locator("#discovery-query").press("Enter")
        expect(page.locator(".discovery-card h3")).to_contain_text(query)
        assert actions[-1]["query"] == query and actions[-1]["product_type"] == "mixed_lots"
        expect(page.get_by_role("link", name="Open seller listing on eBay")).to_have_attribute(
            "href", "https://www.ebay.com/itm/123456789012?var=123456789013"
        )
        expect(page.locator(".offer-image-fallback")).to_be_visible()
        assert page.locator("[data-discovery-reveal]").count() == 0
    checks.append(
        "Five named/broad searches via keyboard; typing remains local; immediate checked seller links"
    )

    for typo, correction in (("Venasaur", "Venusaur"), ("Gyrados", "Gyarados")):
        before = len(actions)
        page.locator("#discovery-query").fill(typo)
        expect(page.get_by_role("button", name=f"Use {correction}", exact=True)).to_be_visible()
        page.get_by_role("button", name=f"Keep {typo} as typed", exact=True).click()
        assert page.locator("#discovery-query").input_value() == typo
        assert len(actions) == before
        page.locator("#discovery-query").press("Enter")
        expect(page.locator(".discovery-card h3")).to_contain_text(typo)
        page.locator("#discovery-query").fill(typo + " Fossil")
        page.get_by_role("button", name=f"Use {correction} Fossil", exact=True).click()
        assert page.locator("#discovery-query").input_value() == correction + " Fossil"
    checks.append(
        "Both spelling suggestions offer correction and deliberate original text; neither auto-searches"
    )

    page.locator("#discovery-query").fill("Jolteon")
    page.get_by_role("button", name="Find lots", exact=True).click()
    expect(page.locator(".discovery-card h3")).to_contain_text("Jolteon")
    page.get_by_role("button", name="More results", exact=True).click()
    expect(page.locator(".discovery-card")).to_have_count(2)
    assert actions[-1] == {"continuation_run": run_id}
    page.locator("#discovery-query").fill("Fossil")
    expect(page.locator("#discovery-next")).to_be_disabled()
    page.locator("#discovery-query").fill("Jolteon")
    expect(page.locator("#discovery-next")).to_be_enabled()
    checks.append("More submits only captured handle; choice edits require a new Search")

    # Keep the actual failed image node during local re-rendering, with its fallback.
    page.locator(".offer-image img").first.evaluate("img => {window.engineeringImage = img;}")
    before = len(actions)
    # Directly exercise the retained renderer hook; this is not a visible user action.
    page.locator("#discovery-filter").evaluate("el => el.dispatchEvent(new Event('change'))")
    assert page.locator(".offer-image img").first.evaluate("img => img === window.engineeringImage")
    assert len(actions) == before
    expect(page.locator(".offer-image-fallback").first).to_be_visible()
    expect(page.locator(".offer-image img").first).to_have_attribute("alt", "Seller photo")
    checks.append(
        "Local updates preserve image node and failed-image layout; seller imagery explicitly labelled"
    )

    # Exercise time rendering through the shared shipped helper.
    for invalid in (
        None,
        "",
        "bad",
        "2026-10-20T10:00:00",
        "2026-02-30T00:00:00Z",
        "2026-10-20T00:00:00+25:00",
    ):
        label = page.evaluate("value => window.DexAuctionTime(value)", invalid)
        assert "unknown" in label and "1970" not in label
    assert "ended" in page.evaluate("() => window.DexAuctionTime('2000-01-01T00:00:00Z')")
    assert "remaining" in page.locator("[data-auction-end]").first.inner_text()
    checks.append("Shared timing: valid/missing/malformed/unzoned/invalid calendar/invalid zone/ended")

    for width, scale, name in ((1280, 1, "desktop"), (390, 1, "narrow"), (320, 2, "narrow-large-text")):
        page.set_viewport_size(dict(width=width, height=1000))
        page.evaluate("scale => document.documentElement.style.fontSize = (scale * 100) + '%'", scale)
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), name
        page.locator("#discovery-query").focus()
        page.keyboard.press("Tab")
        assert page.evaluate("document.activeElement.id") == "discovery-set"
        page.keyboard.press("Tab")
        assert page.evaluate("document.activeElement.id") == "discovery-search"
        page.evaluate("""() => {
            let banner = document.getElementById('engineering-banner');
            if (!banner) {banner = document.createElement('p');banner.id = 'engineering-banner';document.body.prepend(banner);}
            banner.textContent = 'ENGINEERING TEST — fabricated listings, disposable collection, no marketplace calls';
            banner.style.cssText = 'padding:12px;background:#ffe9a8;color:#222;font-weight:bold';
        }""")
        page.screenshot(path=str(output / f"engineering-{name}.png"), full_page=True)
    checks.append(
        "Desktop 1280, narrow 390, 320 with 200% text: no horizontal overflow; keyboard primary action"
    )

    page.evaluate("document.documentElement.style.fontSize = '100%'")
    page.set_viewport_size(dict(width=1280, height=900))
    # Check actual browser navigation with an intercepted, labelled destination.
    page.context.route(
        "https://www.ebay.com/itm/**",
        lambda route: route.fulfill(
            status=200,
            content_type="text/html",
            body="<p>Engineering seller destination; no marketplace access</p>",
        ),
    )
    with page.expect_popup() as popup_info:
        page.get_by_role("link", name="Open seller listing on eBay").first.click()
    popup = popup_info.value
    popup.wait_for_load_state()
    assert popup.url == "https://www.ebay.com/itm/123456789012?var=123456789013"
    expect(popup.locator("body")).to_contain_text("Engineering seller destination")
    popup.close()
    checks.append("Admitted seller destination opens in browser using intercepted engineering navigation")

    # Controlled image success, separately from the retained failure screenshots.
    pixel = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aHHsAAAAASUVORK5CYII="
    )
    page.route(
        "https://i.ebayimg.com/images/**",
        lambda route: route.fulfill(status=200, content_type="image/png", body=pixel),
    )
    page.locator("#discovery-query").fill("Hypno Fossil")
    page.locator("#discovery-query").press("Enter")
    expect(page.locator(".discovery-card h3")).to_contain_text("Hypno Fossil")
    page.wait_for_function("() => document.querySelector('.offer-image img')?.naturalWidth > 0")
    expect(page.locator(".offer-image-fallback")).to_be_hidden()
    page.locator(".offer-image img").evaluate("img => window.engineeringImage = img")
    # Directly exercise the retained renderer hook; this is not a visible user action.
    page.locator("#discovery-filter").evaluate("el => el.dispatchEvent(new Event('change'))")
    assert page.locator(".offer-image img").evaluate("img => img === window.engineeringImage")
    checks.append("Controlled image load succeeds and local updates preserve the loaded node")

    # Stop can use the existing named-run handle even while More admission is held.
    state["hold"] = True
    page.locator("#discovery-next").click()
    page.wait_for_timeout(100)
    assert len(held) == 1
    page.locator("#discovery-stop").click()
    expect(page.locator("#discovery-status")).to_contain_text("Search stopped")
    state["stopped"] = False
    state["rows"] = [row(99, title="LATE ENGINEERING RESPONSE")]
    held.pop().fulfill(json=response())
    page.wait_for_timeout(250)
    assert "LATE ENGINEERING RESPONSE" not in page.locator("#discovery-cards").inner_text()
    checks.append("Stop during held More prevents late publication")
    return checks
