"""Qualify the shipped singles-only Hunter; finite lot hunts live on Shopping."""

import json


def exercise(page, root, output, report, capture, passed, protected_state):
    from playwright.sync_api import expect

    before = protected_state(root)
    start = page.get_by_role("button", name="Find cards", exact=True)
    enable = page.locator("#hunter-poc-enable")
    expect(enable).to_be_visible()
    expect(start).to_be_disabled()
    expect(page.locator("#hunter-scope")).to_be_hidden()
    expect(page.locator("#hunter-usage-settings")).to_be_hidden()
    assert not (output / "fake-transport.json").exists()
    capture("singles-disabled-320", 320)
    capture("singles-disabled-320-text2x", 320, doubled=True)
    enable.focus()
    enable.press("Enter")
    expect(start).to_be_enabled()
    expect(page.locator("#hunter-usage")).to_be_hidden()
    assert not (output / "fake-transport.json").exists()
    passed("keyboard enable configures three one-time requests without acquiring any listings")
    start.focus()
    start.press("Enter")
    expect(page.locator("#hunter-results")).to_be_visible(timeout=30000)
    cards = page.locator("#hunter-cards article")
    expect(cards.first).to_be_visible(timeout=30000)
    expect(cards.first).to_contain_text("Shipping to you")
    expect(cards.first).to_contain_text("Ungraded reference")
    expect(cards.first).to_contain_text("net", ignore_case=True)
    calls = json.loads((output / "fake-transport.json").read_text())
    assert [item["stage"] for item in calls] == ["oauth", "browse", "browse"]
    passed("Find cards performs one fabricated OAuth and two fabricated singles browse requests")
    for width in (1280, 390, 320):
        capture(f"results-singles-{width}", width)
    page.locator(".hunter-cost-settings summary").click()
    postage = page.get_by_label("Resale postage $", exact=True)
    postage.fill("6")
    expect(postage).to_have_value("6")
    capture("results-singles-320-text2x", 320, doubled=True)
    assert json.loads((output / "fake-transport.json").read_text()) == calls
    assert protected_state(root) == before
    passed(
        "cost changes and responsive result reads preserve collection and source rights and acquire nothing"
    )
    report["route_contract"] = "singles-only Hunter; finite auction/BIN lot journey qualified on Shopping"
