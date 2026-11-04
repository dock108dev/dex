"""Expiry clears the leased seller evidence, keeping only explicit local edits."""

import uuid
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect
from test_shop13_browser import (
    b2 as b2,
)
from test_shop13_browser import (
    b3 as b3,
)
from test_shop13_browser import (
    b4 as b4,
)
from test_shop13_browser import (
    browser_app as browser_app,
)
from test_shop13_browser import (
    cx as cx,
)
from test_shop13_browser import (
    e1 as e1,
)
from test_shop13_browser import (
    env as env,
)
from test_shop13_browser import (
    prepared as prepared,
)
from test_shop13_browser import (
    snapshot as snapshot,
)

from pokemon_hunter.beta import discovery, discovery_listing

pytestmark = pytest.mark.allow_hosts(["127.0.0.1"])


def test_restored_authored_edits_outlive_only_the_visible_seller_evidence(browser_app):
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
                shortDescription="2x Ivysaur Base Set 2 #44",
                buyingOptions=["FIXED_PRICE"],
            )
        ],
    )
    discovery._runs[run.id] = run
    handle = discovery_listing.result_handle(run.id, run.raws[0]["itemId"])
    page.goto(base + f"/shopping/check/?discovery_run={run.id}&item_id={handle}")
    page.locator("#use-listing").click()
    page.locator("#review-cards summary").filter(has_text="Correct identity").first.click()
    page.locator("#review-cards .review-include input").first.check()
    page.locator("#review-price").fill("14.25")
    page.locator("#check-back").click()
    page.wait_for_url(lambda url: urlsplit(url).path == "/shopping/")
    page.goto(base + "/shopping/check/")
    expect(page.locator("#review-price")).to_have_value("14.25")
    expect(page.locator("#review-title")).to_have_value("Ivysaur lot of 2 cards")
    expect(page.locator("#check-status")).to_contain_text("Temporary review restored")
    seen = []
    page.on("request", lambda r: seen.append((r.method, r.url)))
    page.evaluate("Date.now = ((clock)=>()=>clock()+31*60000)(Date.now)")
    expect(page.locator("#check-status")).to_contain_text("Temporary review expired")
    expect(page.locator("#review-title")).to_have_value("")
    expect(page.locator("#review-price")).to_have_value("14.25")
    expect(page.locator("#review-count")).to_contain_text("2 individually identified cards")
    assert page.locator("#review-cards .contents-entry").count() == 0
    assert not any(method == "POST" for method, _ in seen)
    page.evaluate("window.dispatchEvent(new Event('dex:authority-revoked'))")
    expect(page.locator("#review-price")).to_have_value("")
    assert page.locator("#review-cards").inner_text() == "" and not errors
