"""Current collection-to-Shopping browser checks over the CI wrapper's disposable root."""

import json
import time

from scripts.ci.discovery_journey import exercise as discovery_journey
from scripts.ci.listing_journey import exercise as listing_journey


def exercise(url, root, output):
    if not (root / "SYNTHETIC_ONLY").is_file():
        raise ValueError("Disposable synthetic collection journey required")
    from playwright.sync_api import expect, sync_playwright

    credentials = json.loads((root / "credentials.json").read_text())
    checks = []
    report = {"status": "FAIL", "checks": checks}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(type(error).__name__))
        context.route(
            "**/*",
            lambda route: (
                route.continue_()
                if route.request.url.startswith(url + "/")
                else route.fulfill(status=404, body="Controlled CI image unavailability")
            ),
        )

        def passed(name, started):
            checks.append(
                {"name": name, "status": "PASS", "duration_seconds": round(time.monotonic() - started, 3)}
            )

        def capture(name):
            if page.evaluate("() => document.documentElement.scrollWidth > innerWidth"):
                raise AssertionError("Current collection journey has horizontal overflow")
            page.screenshot(path=str(output / (name + ".png")))

        try:
            started = time.monotonic()
            page.goto(url + "/login/?next=/cards/")
            page.get_by_label("Username:", exact=True).fill("admin")
            page.get_by_label("Password:", exact=True).fill(credentials["admin"])
            page.get_by_role("button", name="Sign in", exact=True).click()
            expect(page.locator("#card-group-list .owned-card-tile").first).to_be_visible()
            if page.locator(".card-tabs").count():
                raise AssertionError("Superseded duplicate card navigation returned")
            capture("consumer-my-cards")
            passed("ordinary sign-in and current owned cards", started)

            started = time.monotonic()
            page.locator(".owned-card-tile").first.click()
            expect(page.locator("#canonical-card")).to_be_visible()
            page.locator("#edit-group-card").click()
            expect(page.locator("#editor")).to_be_visible()
            page.keyboard.press("Escape")
            expect(page.locator("#editor")).not_to_be_visible()
            expect(page.locator("#edit-group-card")).to_be_focused()
            passed("canonical card opens directly; editing cancellation restores focus", started)

            started = time.monotonic()
            page.goto(url + "/pokedex/")
            expect(page.locator("[data-dex-species]")).to_have_count(251)
            page.locator("[data-dex-species]").first.click()
            expect(page.locator("#your-cards-heading")).to_be_visible()
            expect(page.locator(".species-detail-heading #species-shopping")).to_be_visible()
            capture("consumer-species")
            passed("all 251 Pokémon and normal species page with contextual Find", started)

            started = time.monotonic()
            page.locator("#species-shopping").click()
            expect(page.locator("#context-label")).to_contain_text("Finding cards")
            expect(page.locator("#cards")).not_to_have_attribute("aria-busy", "true")
            if page.locator("#show-all").count():
                page.locator("#show-all").click()
            expect(page.get_by_role("button", name="Add to lot", exact=True)).to_be_visible()
            page.get_by_role("button", name="Add to lot", exact=True).click()
            expect(page.locator("#selections .selection")).to_have_count(1)
            page.locator("#lot-price").fill("18")
            page.locator("#comparison button[value=compare]").click()
            expect(page.locator("#results")).to_be_visible()
            capture("consumer-shopping")
            passed("contextual Shopping entry, local picker and explicit comparison", started)

            started = time.monotonic()
            for width in (390, 320):
                page.set_viewport_size({"width": width, "height": 900})
                capture("consumer-shopping-" + str(width))
                if (
                    page.locator(".lot-items").bounding_box()["y"]
                    >= page.locator("#search-matches").bounding_box()["y"]
                ):
                    raise AssertionError("Narrow Shopping hides the lot behind the picker")
            page.evaluate("""() => {
              const rows=[...document.querySelectorAll('body,body *')].map(e=>[e,parseFloat(getComputedStyle(e).fontSize)]);
              rows.forEach(([e,n])=>{e.style.fontSize=(2*n)+'px';});
            }""")
            capture("consumer-shopping-text200")
            passed("narrow and actual doubled-text collection Shopping layout", started)

            checks.extend(discovery_journey(page, url, output))
            checks.extend(listing_journey(page, url, output))

            started = time.monotonic()
            page.goto(url + "/cards/?species=252")
            expect(page.locator("#card-retry")).to_be_visible()
            page.get_by_role("link", name="Back to cards", exact=True).click()
            expect(page.locator("#card-group-list")).to_be_visible()
            page.locator('.app-header [data-navigation-tab="/card-library/"]').click()
            expect(page.locator('.app-header [data-navigation-tab="/card-library/"]')).to_have_attribute(
                "aria-current", "page"
            )
            if page.locator('.app-header [aria-current="page"]').count() != 1 or errors:
                raise AssertionError("Current navigation or renderer boundary failed")
            passed("invalid filter recovery and one active Library navigation target", started)
            report["status"] = "PASS"
        except Exception as error:
            report["failure"] = type(error).__name__
            raise
        finally:
            (output / "consumer-report.json").write_text(json.dumps(report, indent=2) + "\n")
            context.close()
            browser.close()
    return checks
