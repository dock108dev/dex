"""The Shopping clock includes browser work, excluding driver delivery delay."""

from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

PROBE = Path(__file__).with_name("shop12_browser_probe.js")


@pytest.fixture
def probe_page():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context()
        context.add_init_script(path=str(PROBE))

        def document(route):
            body = (
                '<div id="result">Ready</div>'
                if route.request.url.endswith("/destination")
                else '<button id="go" onclick="setTimeout(()=>document.querySelector(\'#result\').hidden=false,120)">Go</button>'
                '<a id="next" href="/destination">Next</a><div id="result" hidden>Ready</div>'
            )
            route.fulfill(content_type="text/html", body=body)

        # All documents are fulfilled locally; no network or customer data.
        context.route("**/*", document)
        page = context.new_page()
        page.goto("http://shopping-probe.test/")
        yield page
        context.close()
        browser.close()


@pytest.mark.parametrize("navigation", [False, True])
def test_keyboard_clock_starts_at_real_input_and_survives_navigation(probe_page, navigation):
    page = probe_page
    page.evaluate("shopArm('action','#result:not([hidden])','#result')")
    # Simulate slow driver delivery. This is deliberately outside the user action.
    page.wait_for_timeout(150)
    before_key = page.evaluate("performance.timeOrigin+performance.now()")
    assert page.evaluate("shopProbe.ready") is None
    page.locator("#next" if navigation else "#go").press("Enter")
    page.locator("html[data-shop-ready=true]").wait_for()
    sample = page.evaluate("shopProbe")
    assert sample["input"]["trusted"] is True
    assert sample["input"]["key"] == "Enter"
    assert sample["input"]["driver_wait_ms"] >= 150
    assert sample["action"] >= before_key
    assert sample["action"] == sample["input"]["action"]
    if not navigation:
        # Genuine browser work after the keypress must still count.
        assert sample["elapsed"] >= 120


def test_rearming_ignores_other_keys_and_direct_marks_clear_old_input(probe_page):
    page = probe_page
    page.evaluate("shopArm('obsolete','#missing');shopArm('current','#result:not([hidden])')")
    page.locator("#go").press("Shift")
    assert page.evaluate("shopProbe.ready") is None
    page.locator("#go").press("Enter")
    page.locator("html[data-shop-ready=true]").wait_for()
    assert page.evaluate("shopProbe.kind") == "current"
    original = page.evaluate("shopProbe.input.action")
    page.locator("#go").press("Enter")
    assert page.evaluate("shopProbe.input.action") == original
    page.evaluate("shopMark('direct','#result')")
    page.locator("html[data-shop-ready=true]").wait_for()
    assert page.evaluate("shopProbe.input") is None
    assert page.evaluate("sessionStorage.getItem('shop12-input')") is None
