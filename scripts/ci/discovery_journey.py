"""Discovery layout checks using generated browser responses in isolated tests."""

import json
import time

GOAL_NAME = "Engineering frozen goal with a deliberately long title covering exact edition and finish choices"
RUN_ID = "11111111-1111-4111-8111-111111111111"


def exercise(page, base, output):
    from playwright.sync_api import expect

    page.goto(base + "/shopping/")
    expect(page.locator("#discovery-form")).to_be_visible()
    authority = page.locator("body").evaluate(
        "e => ({account_id:e.dataset.navigationAccount,binding:e.dataset.navigationBinding})"
    )
    if not all(authority.values()):
        raise AssertionError("Authenticated engineering page authority required")
    calls = []
    checks = []
    captured_choices = {}
    results = [
        {
            "id": "engineering-conditional",
            "proposed_identity": {
                "name": "Engineering identity with a long card name and printing annotation",
                "set_name": "Engineering expansion with a long set title",
                "collector_number": "123/456",
                "language": "English",
                "edition": "First edition conditional",
                "finish": "Holographic",
                "artwork_url": None,
            },
            "revealed": True,
            "listing_price": "19.50",
            "shipping": None,
            "delivered_total": None,
            "price_kind": "fixed_price",
            "classification": "conditional",
            "reason": "Engineering condition and edition remain unconfirmed; shipping is unknown.",
            "basis": "Conditional raw-condition comparison; seller text is proposed identity only.",
            "reference": {
                "amount": "25.00",
                "currency": "USD",
                "as_of": "2020-01-01",
                "valuation_as_of": None,
                "captured_at": "2021-02-03T04:05:06+00:00",
                "publisher_built_at": "2020-12-31T23:59:59+00:00",
                "source_url": None,
                "language": "English",
                "edition": "First edition",
                "finish": "Holographic",
                "condition": "NM scenario",
                "grade": "raw",
                "source_version": "engineering-only",
            },
            "comparison": {"reference_minus_delivered_total": None},
            "save_reason": "Engineering temporary comparison; restricted references cannot be saved.",
        },
        {
            "id": "engineering-ambiguous",
            "proposed_identity": None,
            "revealed": True,
            "listing_price": "8.00",
            "shipping": "0.00",
            "delivered_total": "8.00",
            "price_kind": "current_bid",
            "classification": "unpriced",
            "reference": None,
            "reason": "Engineering conflicting edition evidence; no applicable reference.",
            "basis": "No verified identity or compatible guide reference.",
            "save_reason": "Engineering temporary comparison.",
        },
    ]

    def boundary(route):
        nonlocal captured_choices
        request = route.request
        calls.append({"method": request.method, "path": request.url.split(base, 1)[-1]})
        if request.method == "POST":
            captured_choices = request.post_data_json
            value = {
                "run_id": RUN_ID,
                "expires_in_seconds": 1800,
                "state": "complete",
                "running": False,
                "choices": captured_choices,
                "scope_label": "Frozen goal: " + GOAL_NAME + " · missing exact printings",
                "results": results,
                "counts": {"summary_count": 2},
                "has_next": False,
                "note": "Engineering fixture only. Temporary comparisons retain historical source dates.",
            }
        else:
            value = {
                "provider": {"enabled": True, "configured": True},
                "goals": [
                    {
                        "id": "engineering-goal",
                        "name": GOAL_NAME,
                        "policy": "exact",
                        "version": "retained-engineering-version",
                    }
                ],
                "sets": [{"id": "engineering-set", "name": "Engineering supported set"}],
            }
        route.fulfill(
            status=200, content_type="application/json", body=json.dumps({**value, "authority": authority})
        )

    page.route("**/api/shopping/discovery/**", boundary)
    try:
        for width in (1280, 390, 320):
            for enlarged in (False, True):
                started = time.monotonic()
                page.set_viewport_size({"width": width, "height": 900})
                page.goto(base + "/shopping/")
                expect(page.locator("#discovery-search")).to_be_enabled()
                expect(page.get_by_text("Search options", exact=True)).to_be_hidden()
                page.locator("#discovery-query").fill("Engineering Pokémon with a long card name")
                page.locator("#discovery-set").select_option("Engineering supported set")
                page.locator("#discovery-search").click()
                expect(page.locator(".discovery-card")).to_have_count(2)
                expect(page.locator(".discovery-card").first).to_contain_text("Unknown")
                expect(page.locator(".discovery-card").nth(1)).to_contain_text("Current bid")
                # Lots never present a per-card reference as a lot valuation.
                expect(page.locator(".discovery-card .reference").first).to_be_hidden()
                if enlarged:
                    page.evaluate("""() => {
                        const sizes=[...document.querySelectorAll('body,body *')].map(e=>[e,parseFloat(getComputedStyle(e).fontSize)]);
                        sizes.forEach(([e,n])=>{e.style.fontSize=(2*n)+'px';});
                    }""")
                    if page.locator("body").evaluate("e => parseFloat(getComputedStyle(e).fontSize)") < 32:
                        raise AssertionError("Actual doubled text was not applied")
                metrics = page.evaluate("""() => ({
                    horizontal_overflow: document.documentElement.scrollWidth > innerWidth,
                    card_overflow: [...document.querySelectorAll('.discovery-card')].some(e=>e.scrollWidth>e.clientWidth+1),
                    font_size: getComputedStyle(document.body).fontSize,
                    unknown_shipping: document.querySelector('.discovery-amounts').innerText.includes('Unknown')
                })""")
                if (
                    metrics["horizontal_overflow"]
                    or metrics["card_overflow"]
                    or not metrics["unknown_shipping"]
                ):
                    raise AssertionError("Engineering discovery layout overflow or missing unknown shipping")
                name = f"engineering-discovery-{width}" + ("-text200" if enlarged else "")
                page.screenshot(path=str(output / (name + ".png")), full_page=True)
                checks.append(
                    {
                        "name": name,
                        "status": "PASS",
                        "evidence_class": "engineering fixtures only",
                        "provider_calls": 0,
                        "duration_seconds": round(time.monotonic() - started, 3),
                        **metrics,
                    }
                )
        if len([call for call in calls if call["method"] == "POST"]) != 6:
            raise AssertionError("Unexpected automatic discovery acquisition action")
        if (
            captured_choices.get("set_id") != "Engineering supported set"
            or captured_choices.get("intent") != "deals"
            or captured_choices.get("product_type") != "mixed_lots"
            or captured_choices.get("sort") != "ending_soonest"
        ):
            raise AssertionError("Explicit lot search choices were not captured")
    finally:
        page.unroute("**/api/shopping/discovery/**", boundary)
    return checks
