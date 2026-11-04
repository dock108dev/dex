"""Controlled Shopping browser failures; engineering fixtures, never product acceptance."""

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


def test_missing_picker_edits_options_failure_and_keyboard(browser_app, monkeypatch):
    from playwright.sync_api import expect

    from pokemon_hunter.beta import discovery

    state, page, base, requests, errors = browser_app
    monkeypatch.setattr(discovery.ebay_hunts, "status", lambda: dict(enabled=True, configured=True))
    options, methods = [], []
    page.on("request", lambda r: methods.append((r.method, r.url)))

    def hold(route):
        if not urlsplit(route.request.url).query:
            options.append(route)
        else:
            route.continue_()

    page.route("**/api/shopping/discovery/", hold)
    page.goto(base + "/shopping/?missing=species&budget=73.50")
    expect(page.locator("#discovery-target")).to_be_enabled()
    value = page.locator("#discovery-target option").nth(1).get_attribute("value")
    page.locator("#discovery-target").select_option(value)
    page.locator("#discovery-budget").fill("86.75")
    page.locator("#discovery-prefer-vintage").check()
    assert len(options) == 1
    options[0].fulfill(status=503, json=dict(error="runtime_busy"))
    expect(page.locator("#discovery-options-reload")).to_be_visible()
    assert page.locator("#discovery-target").input_value() == value
    assert page.locator("#discovery-budget").input_value() == "86.75"
    for width in (320, 390, 1280):
        page.set_viewport_size(dict(width=width, height=900))
        page.add_style_tag(content="html {font-size:200% !important}")
        for selector in ("#discovery-target", "#discovery-budget", "#find-missing"):
            control = page.locator(selector)
            control.scroll_into_view_if_needed()
            box = control.bounding_box()
            assert box and box["x"] >= 0 and box["x"] + box["width"] <= width + 1
    page.locator("#discovery-target").focus()
    page.locator("#discovery-target").press("ArrowDown")
    page.locator("#discovery-target").press("Enter")
    page.locator("#find-deals").click()
    expect(page.locator("#discovery-query")).to_be_editable()
    assert page.locator("#discovery-budget").input_value() == "86.75"
    assert not any(method == "POST" and "/discovery/" in url for method, url in methods)
    assert not errors


def test_collection_lost_response_keeps_later_edits_and_never_reposts(browser_app, monkeypatch):
    import uuid

    from playwright.sync_api import expect
    from test_shop12_browser import received

    from pokemon_hunter.beta import discovery

    state, page, base, requests, errors = browser_app
    monkeypatch.setattr(discovery.ebay_hunts, "status", lambda: dict(enabled=True, configured=True))
    posted = []
    run_id = str(uuid.uuid4())

    def intercept(route):
        request = route.request
        if request.method == "POST":
            posted.append(request.post_data_json)
            route.abort()
        elif "request_id=" in request.url:
            result = received(run_id, state["actor"].user_id, request.header_value("X-Dex-Shopping-Binding"))
            result["choices"] = posted[0]
            route.fulfill(json=result)
        else:
            route.continue_()

    page.route("**/api/shopping/discovery/**", intercept)
    page.goto(base + "/shopping/?missing=species")
    expect(page.locator("#discovery-target")).to_be_enabled()
    species = page.locator("#discovery-target option").nth(1).get_attribute("value")
    page.locator("#discovery-target").select_option(species)
    page.locator("#discovery-budget").fill("64.25")
    page.locator("#discovery-prefer-vintage").check()
    page.locator("#discovery-search").evaluate("e=>{e.click();e.click()}")
    expect(page.locator("#discovery-reload")).to_be_visible()
    assert len(posted) == 1
    assert posted[0]["species"] == int(species) and posted[0]["collection_intent"]
    assert posted[0]["budget"] == "64.25" and posted[0]["prefer_vintage"]
    page.locator("#discovery-budget").fill("72.50")
    page.locator("#discovery-reload").click()
    expect(page.get_by_text("Engineering received lot", exact=True)).to_be_visible()
    assert page.locator("#discovery-target").input_value() == species
    assert page.locator("#discovery-budget").input_value() == "72.50"
    assert page.locator("#discovery-prefer-vintage").is_checked()
    assert len(posted) == 1
    assert not errors


def test_no_targets_does_not_acquire(browser_app, monkeypatch):
    from playwright.sync_api import expect

    from pokemon_hunter.beta import discovery

    state, page, base, requests, errors = browser_app
    monkeypatch.setattr(discovery.ebay_hunts, "status", lambda: dict(enabled=True, configured=True))
    methods = []
    page.on("request", lambda r: methods.append((r.method, r.url)))

    def empty(route):
        route.fulfill(
            json=dict(
                targets=[],
                authority=dict(
                    account_id=state["actor"].user_id,
                    binding=route.request.header_value("X-Dex-Shopping-Binding"),
                ),
            )
        )

    page.route("**/api/shopping/discovery/targets/**", empty)
    page.goto(base + "/shopping/?missing=species")
    expect(page.locator("#discovery-target-status")).to_have_text("No missing Pokémon in this scope.")
    expect(page.locator("#discovery-search")).to_be_disabled()
    assert not any(method == "POST" for method, url in methods)
    assert not errors


def test_account_change_clears_private_targets_and_goal_output(browser_app):
    from playwright.sync_api import expect

    state, page, base, requests, errors = browser_app
    page.goto(base + "/shopping/?missing=species")
    expect(page.locator("#discovery-target")).to_be_enabled()
    assert page.locator("#discovery-target option").count() > 1
    page.evaluate("window.dispatchEvent(new Event('dex:authority-revoked'))")
    assert page.locator("#discovery-target option").count() == 0
    assert page.locator("#discovery-goal option").count() == 0
    assert page.locator("#discovery-query").input_value() == ""
    expect(page.locator("#discovery-search")).to_be_disabled()
    assert not errors
