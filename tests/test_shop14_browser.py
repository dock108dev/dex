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


def test_open_survives_same_run_refresh_while_waiting_for_status(browser_app):
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
            dict(itemId="v1|123456789012|0", title="Ivysaur lot of 2 cards", buyingOptions=["FIXED_PRICE"])
        ],
    )
    discovery._runs[run.id] = run
    handle = discovery_listing.result_handle(run.id, run.raws[0]["itemId"])
    page.goto(base + f"/shopping/?run_id={run.id}&q=Ivysaur")
    expect(page.locator(f'[data-review-id="{handle}"]').first).to_be_attached()
    pending = []
    page.route("**/api/shopping/discovery/**", lambda route: pending.append(route))
    page.wait_for_timeout(6500)
    assert pending
    page.locator(f'[data-review-id="{handle}"]').first.evaluate("e=>e.click()")
    expect(page.locator("#discovery-status")).to_contain_text("Opening your review")
    pending.pop(0).continue_()
    page.wait_for_url("**/shopping/check/**", timeout=15000)
    expect(page.locator("#listing-preview")).to_be_visible()
    assert not errors


def test_finished_search_waits_before_compare_without_replaying(browser_app):
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
            dict(itemId="v1|123456789012|0", title="Ivysaur lot of 2 cards", buyingOptions=["FIXED_PRICE"])
        ],
    )
    discovery._runs[run.id] = run
    handle = discovery_listing.result_handle(run.id, run.raws[0]["itemId"])
    page.goto(base + f"/shopping/check/?discovery_run={run.id}&item_id={handle}")
    page.locator("#use-listing").click()
    page.locator("#review-price").fill("17.25")
    expect(page.locator("#review-save-status")).to_contain_text("saved")
    other = page.context.new_page()
    pending = []
    sent = []
    page.on("request", lambda req: sent.append((req.method, req.url)))

    def hold(route):
        if "run_id=" in route.request.url:
            pending.append(route)
        else:
            route.continue_()

    other.route("**/api/shopping/discovery/**", hold)
    other.goto(base + f"/shopping/?run_id={run.id}&q=Ivysaur", wait_until="domcontentloaded")
    expect(other.locator("#discovery-form")).to_be_visible()
    page.wait_for_timeout(500)
    assert pending
    page.locator("#check-compare").click()
    page.wait_for_timeout(600)
    assert not any(method == "POST" and "/listing/compare/" in url for method, url in sent)
    pending.pop(0).continue_()
    expect(page.locator("#check-results")).to_be_visible(timeout=15000)
    assert sum(method == "POST" and "/listing/compare/" in url for method, url in sent) == 1
    assert not any(method == "POST" and "/discovery/" in url for method, url in sent)
    assert not errors
    other.close()


def test_comparison_recovers_from_temporary_background_failure(browser_app):
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
            dict(itemId="v1|123456789012|0", title="Ivysaur lot of 2 cards", buyingOptions=["FIXED_PRICE"])
        ],
    )
    discovery._runs[run.id] = run
    handle = discovery_listing.result_handle(run.id, run.raws[0]["itemId"])
    page.goto(base + f"/shopping/check/?discovery_run={run.id}&item_id={handle}")
    page.locator("#use-listing").click()
    page.locator("#review-price").fill("17.25")
    page.locator("#check-compare").click()
    expect(page.locator("#check-results")).to_be_visible()
    page.route(
        "**/api/shopping/price-source-status/",
        lambda route: route.fulfill(status=503, json={"error": "runtime_busy"}),
    )
    expect(page.locator("#check-results")).to_be_hidden(timeout=12000)
    expect(page.locator("#check-status")).to_contain_text("Verification is pending")
    assert page.locator("#review-price").input_value() == "17.25"
    page.unroute("**/api/shopping/price-source-status/")
    page.locator("#check-reload").click()
    expect(page.locator("#check-results")).to_be_visible(timeout=12000)
    assert page.locator("#review-price").input_value() == "17.25"
    assert not errors


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
    assert '{"edition"' not in page.locator("#review-cards").inner_text()
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


def test_family_split_survives_compare_and_reload(browser_app):
    import json
    from concurrent.futures import ThreadPoolExecutor

    from playwright.sync_api import expect

    from pokemon_hunter.beta import (
        account_read_build,
        catalog_read_build,
        collection,
        discovery,
        discovery_listing,
    )

    state, page, base, requests, errors = browser_app
    first, second = state["by_legacy"]["a"]["id"], state["by_legacy"]["b"]["id"]

    def prepare_family():
        collection.execute(
            "UPDATE printings SET attributes=%s WHERE id=%s",
            [json.dumps(dict(name="Ivysaur", pokemon_dex=2, dex_eligible=True, supertype="Pokémon")), second],
        )
        catalog_read_build.activate(catalog_read_build.prepare())
        account_read_build.prepare(state["actor"])

    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(prepare_family).result()
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
                title="Lot of 4 cards",
                shortDescription="4x Ivysaur",
                buyingOptions=["FIXED_PRICE"],
            )
        ],
    )
    discovery._runs[run.id] = run
    handle = discovery_listing.result_handle(run.id, run.raws[0]["itemId"])
    page.goto(base + f"/shopping/check/?discovery_run={run.id}&item_id={handle}")
    page.locator("#use-listing").click()
    page.locator("#review-cards summary").filter(has_text="Correct identity").first.click()
    picker = page.locator("#review-cards select").first
    for key in (first, second):
        picker.select_option(key)
        page.locator(f'input[data-printing="{key}"]').check()
    page.locator(f'input[data-quantity="{second}"]').fill("2")
    expect(page.locator("#review-count")).to_contain_text(
        "3 individually identified cards · unrecognized contents: 1"
    )
    expect(page.locator("#review-save-status")).to_contain_text("saved")
    page.locator("#check-compare").click()
    expect(page.locator("#check-results")).to_contain_text("Identified copies: 3")
    expect(page.locator("#check-results")).to_contain_text("Unresolved remainder: 1")
    page.reload()
    expect(page.locator("#review-count")).to_contain_text(
        "3 individually identified cards · unrecognized contents: 1"
    )
    assert run.counts["total"] == 0 and not errors


def test_opening_another_offer_preserves_review_until_user_applies_it(browser_app):
    from playwright.sync_api import expect

    from pokemon_hunter.beta import discovery, discovery_listing

    state, page, base, requests, errors = browser_app
    page.goto(base + "/shopping/check/")
    binding = page.locator("#check-binding").evaluate("e=>JSON.parse(e.textContent)")
    runs = []
    for number, name in (("123456789012", "Ivysaur"), ("123456789013", "Venusaur")):
        run = discovery.Run(
            str(uuid.uuid4()),
            (str(state["root"]), state["actor"].user_id, binding),
            discovery.Choices(query=name, product_type="mixed_lots"),
            None,
            [name],
            state="complete",
            raws=[
                dict(itemId=f"v1|{number}|0", title=f"{name} lot of 2 cards", buyingOptions=["FIXED_PRICE"])
            ],
        )
        discovery._runs[run.id] = run
        runs.append((run, discovery_listing.result_handle(run.id, run.raws[0]["itemId"])))
    first, second = runs
    page.goto(base + f"/shopping/check/?discovery_run={first[0].id}&item_id={first[1]}")
    page.locator("#use-listing").click()
    page.locator("#review-price").fill("12.34")
    expect(page.locator("#review-save-status")).to_contain_text("saved")
    page.goto(base + f"/shopping/check/?discovery_run={second[0].id}&item_id={second[1]}")
    expect(page.locator("#listing-preview")).to_be_visible()
    expect(page.locator("#review-price")).to_have_value("12.34")
    page.locator("#use-listing").click()
    expect(page.locator("#offer-summary")).to_contain_text("Venusaur")
    assert all(run.counts["total"] == 0 for run, _ in runs) and not errors
