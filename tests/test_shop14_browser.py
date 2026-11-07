"""Actual templates/services on disposable engineering state; no provider access."""

import uuid
from urllib.parse import urlsplit

import pytest
from test_shop13_browser import (  # noqa: F401
    b2,
    b3,
    b4,
    cx,
    e1,
    env,
    prepared,
    snapshot,
)
from test_shop13_browser import (
    browser_app as browser_app,
)

pytestmark = pytest.mark.allow_hosts(["127.0.0.1"])


def test_contents_keyboard_layout_correction_and_failed_save(browser_app):
    from playwright.sync_api import expect

    from pokemon_hunter.beta import discovery, discovery_listing

    state, page, base, requests, errors = browser_app
    page.goto(base + "/shopping/check/")
    binding = page.locator("#check-binding").evaluate("e=>JSON.parse(e.textContent)")
    run = discovery.Run(
        str(uuid.uuid4()),
        (str(state["root"]), state["actor"].user_id, binding),
        discovery.Choices(query="Ivysaur", product_type="mixed_lots"),
        None,
        ["Ivysaur"],
        state="complete",
        raws=[
            dict(
                itemId="v1|123456789012|0",
                title="Ivysaur lot of 2 cards",
                shortDescription="1x Ivysaur Base Set 2 #44; 1x Venusaur Base Set 2 #18",
                buyingOptions=["FIXED_PRICE"],
            )
        ],
    )
    discovery._runs[run.id] = run
    handle = discovery_listing.result_handle(run.id, run.raws[0]["itemId"])
    page.goto(base + f"/shopping/check/?discovery_run={run.id}&item_id={handle}")
    expect(page.locator("#contents-preview .contents-entry")).to_have_count(2)
    page.locator("#listing-preview > details > summary").first.click()
    assert page.locator("#contents-preview").inner_text().count("contents unverified") == 2
    layouts = [(width, zoom) for zoom in (100, 200) for width in (320, 390, 1280)]
    for width, zoom in layouts:
        page.set_viewport_size(dict(width=width, height=1000))
        page.add_style_tag(content=f"html {{font-size:{zoom}% !important}}")
        for selector in ("#contents-preview", "#use-listing"):
            box = page.locator(selector).bounding_box()
            assert box and box["x"] >= 0 and box["x"] + box["width"] <= width + 1
    disclosure = page.locator("#contents-preview summary").filter(has_text="Printing alternatives").first
    disclosure.focus()
    disclosure.press("Enter")
    assert disclosure.evaluate("e=>e.parentElement.open")
    page.locator("#use-listing").click()
    expect(page.locator("#review-cards .contents-entry")).to_have_count(2)
    correction = page.locator("#review-cards summary").filter(has_text="Correct identity").first
    correction.focus()
    correction.press("Enter")
    expect(page.locator("#review-cards .review-card").first).to_be_visible()
    for width, zoom in layouts:
        page.set_viewport_size(dict(width=width, height=1000))
        page.add_style_tag(content=f"html {{font-size:{zoom}% !important}}")
        for control in (
            page.locator("#review-cards .contents-entry")
            .first.locator("summary:visible, select:visible, input:visible, button:visible")
            .all()
        ):
            control.scroll_into_view_if_needed()
            box = control.bounding_box()
            assert box and 0 <= box["x"] and box["x"] + box["width"] <= width + 1
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
    include = page.locator("#review-cards .review-include input[data-printing]").first
    include.focus()
    include.press("Space")
    expect(include).to_be_checked()
    expect(include).to_be_focused()
    # Local failure must keep the authored amount and entry alternatives.
    page.route(
        "**/api/shopping/listing/review/",
        lambda route: (
            route.fulfill(status=503, json=dict(error="runtime_busy"))
            if route.request.method == "POST"
            else route.continue_()
        ),
    )
    page.locator("#review-price").fill("17.25")
    expect(page.locator("#check-reload")).to_be_visible()
    assert page.locator("#review-price").input_value() == "17.25"
    assert page.locator("#review-cards .contents-entry").count() == 2
    page.unroute("**/api/shopping/listing/review/")
    page.locator("#check-reload").click()
    expect(page.locator("#check-status")).to_have_text("Your latest edits are retained.")
    page.locator("#check-back").click()
    page.wait_for_url(lambda url: urlsplit(url).path == "/shopping/")
    page.goto(base + "/shopping/check/")
    expect(page.locator("#review-price")).to_have_value("17.25")
    expect(page.locator("#review-cards .contents-entry")).to_have_count(2)
    # Exclude, edit a trait, then navigate away before the save delay. A
    # corrected zero-unit identity must restore while contributing no gain.
    correction = page.locator("#review-cards summary").filter(has_text="Correct identity").first
    correction.click()
    page.locator("#review-cards .review-include input[data-printing]").first.uncheck()
    page.locator("#review-cards summary").filter(has_text="optional card details").first.click()
    page.get_by_label("Condition claim", exact=True).first.fill("User checked corner wear")
    page.locator("#check-back").click()
    page.wait_for_url(lambda url: urlsplit(url).path == "/shopping/")
    page.goto(base + "/shopping/check/")
    page.locator("#review-cards summary").filter(has_text="Correct identity").first.click()
    page.locator("#review-cards summary").filter(has_text="optional card details").first.click()
    expect(page.get_by_label("Condition claim", exact=True).first).to_have_value("User checked corner wear")
    expect(page.locator("#review-cards .review-include input[data-printing]").first).not_to_be_checked()
    page.evaluate("window.dispatchEvent(new Event('dex:authority-revoked'))")
    assert page.locator("#review-cards").inner_text() == ""
    assert not errors
