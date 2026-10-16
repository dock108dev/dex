"""Disposable browsing error/recovery and Shopping-client contracts."""

from urllib.parse import urlencode


def exercise(page, base, output):
    from playwright.sync_api import expect

    checks = []
    error = "Invalid browsing filters or return link. Go back or open My Cards at /cards/."
    group = page.request.get(base + "/api/my-card-groups/").json()["groups"][0]["id"]
    path = f"/card-groups/{group}/?" + urlencode({"return": "https://example.invalid/private"})
    response = page.goto(base + path)
    assert response.status == 400
    assert response.json() == {"error": error, "recovery_url": "/cards/"}
    expect(page.locator("body")).not_to_contain_text("import format")
    page.goto(base + response.json()["recovery_url"])
    expect(page.locator("#card-group-list .owned-card-tile").first).to_be_visible()
    checks.append(
        dict(
            name="original malformed card return is safe JSON 400 with working fixed recovery", status="PASS"
        )
    )
    duplicate = page.request.get(base + "/api/my-card-groups/?q=one&q=two")
    assert duplicate.status == 400 and duplicate.json()["error"] == error
    for width in (1280, 390, 320):
        for doubled in (False, True):
            page.set_viewport_size(dict(width=width, height=900))
            page.goto(base + "/cards/?species=252")
            expect(page.locator("#card-retry")).to_be_visible()
            expect(page.locator("#content")).to_contain_text(error)
            expect(page.locator("#content")).not_to_contain_text("import format")
            if doubled:
                sizes = page.evaluate("""() => {
                    const rows=[...document.querySelectorAll('body,body *')].map(e=>[e,parseFloat(getComputedStyle(e).fontSize)]);
                    const sample=document.querySelector('#card-retry'),before=parseFloat(getComputedStyle(sample).fontSize);
                    rows.forEach(([e,n])=>e.style.fontSize=(2*n)+'px');
                    return [before,parseFloat(getComputedStyle(sample).fontSize)];
                }""")
                assert sizes[1] == 2 * sizes[0]
            assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
            page.screenshot(
                path=str(output / f"engineering-browse-error-{width}-{doubled}.png"), full_page=True
            )
            page.get_by_role("link", name="Back to cards", exact=True).click()
            expect(page.locator("#card-group-list .owned-card-tile").first).to_be_visible()
    checks.append(
        dict(
            name="invalid-filter error and visible Back recovery at 1280/390/320, normal and actual 200% text",
            status="PASS",
        )
    )
    page.set_viewport_size(dict(width=1280, height=900))
    generic = "Invalid request. Check the fields and import format."
    page.goto(base + "/shopping/calculator/")
    expect(page.locator("#lot-price")).to_be_visible()
    page.locator("#lot-price").fill("12.34")
    page.route(
        "**/api/shopping/lot-compare/", lambda route: route.fulfill(status=400, json={"error": generic})
    )
    page.locator("#comparison button[value=compare]").click()
    expect(page.locator("#status")).to_contain_text(
        "Check card quantities, USD amounts, dates and the listing URL. Your entries remain here."
    )
    expect(page.locator("#lot-price")).to_have_value("12.34")
    page.unroute("**/api/shopping/lot-compare/")
    page.goto(base + "/shopping/check/")
    expect(page.locator("#review-price")).to_be_enabled()
    page.route(
        "**/api/shopping/listing/review/", lambda route: route.fulfill(status=400, json={"error": generic})
    )
    page.locator("#review-price").fill("23.45")
    expect(page.locator("#check-status")).to_contain_text(
        "Check whole quantities, amounts and the listing URL. Your edits remain."
    )
    expect(page.locator("#review-price")).to_have_value("23.45")
    page.unroute("**/api/shopping/listing/review/")
    checks.append(
        dict(
            name="calculator and assisted checker still translate generic mutation errors and retain entries",
            status="PASS",
        )
    )
    return checks
