"""Real installed UI execution on disposable engineering state; no customer-state access."""

import json
from urllib.parse import urlsplit


def exercise(url, root, output, report):
    from playwright.sync_api import expect, sync_playwright
    from qualify_shopping import PASSWORD
    from verify_cx05 import persisted_snapshot

    assert root.name == "engineering-root" and "review-local" not in str(root)
    checks, measurements, errors, posts = [], [], [], []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport=dict(width=1280, height=900))
        context.route(
            "**/*",
            lambda route: route.continue_() if route.request.url.startswith(url + "/") else route.abort(),
        )
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(url + "/login/?next=/pokedex/")
        page.get_by_label("Username:", exact=True).fill("admin")
        page.get_by_label("Password:", exact=True).fill(PASSWORD)
        page.get_by_role("button", name="Sign in", exact=True).click()
        expect(page.locator("#species-grid")).to_be_visible()
        before = persisted_snapshot(root)
        page.on("request", lambda request: posts.append(request.url) if request.method != "GET" else None)

        def load(path):
            assert page.goto(url + path).status == 200
            expect(page.locator("#species-grid")).to_be_visible()
            page.evaluate("() => new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))")

        def apply():
            with page.expect_response(lambda r: "/api/pokedex-species/" in r.url) as response:
                page.locator("#dex-scope-apply").click()
            assert response.value.status == 200
            expect(page.locator("#scope-pending")).to_contain_text("Selections are applied")
            return response.value.json()

        load("/pokedex/?region=kanto")
        expect(page.locator("[data-dex-species]")).to_have_count(151)
        old = page.locator("#dex-progress").inner_text()
        if not page.locator("#dex-scope-editor").evaluate("(e)=>e.open"):
            page.locator("#dex-scope-editor>summary").click()
        page.locator('[data-scope-key="released"][value="pre-2000"]').check()
        assert page.locator("#dex-progress").inner_text() == old
        assert "released=" not in page.url
        first = apply()
        assert first["scoped_progress"]["total"] == 151
        expect(page.locator("[data-dex-species]")).to_have_count(151)
        expect(page.locator("#dex-active-filters")).to_contain_text("Pre-2000")
        page.reload()
        expect(page.locator("#species-grid")).to_be_visible()
        assert "released=pre-2000" in page.url
        if not page.locator("#dex-scope-editor").evaluate("(e)=>e.open"):
            page.locator("#dex-scope-editor>summary").click()
        page.locator('[data-scope-key="released"][value="pre-2000"]').uncheck()
        page.locator('[data-scope-key="released"][value="2000-onward"]').check()
        second = apply()
        assert second["scoped_progress"]["total"] == 151
        checks.append("draft Apply, exact pre-2000/2000-onward serialization, reload and stable 151 targets")
        page.locator("#dex-scope-clear").click()
        expect(page.locator("#dex-active-filters")).to_contain_text("unrestricted")
        boxes = page.locator('[data-scope-key="set"]')
        selected = [boxes.nth(i).get_attribute("value") for i in range(2)]
        for i in range(2):
            boxes.nth(i).check()
        combined = apply()
        assert set(json.loads(combined["filters"]["set"])) == set(selected)
        assert combined["scoped_progress"]["total"] == 151
        page.locator("#scope-search-set").fill("No such set")
        assert page.locator("#dex-set .scope-options label:visible").count() == 0
        page.locator("#scope-search-set").fill("")
        assert page.locator('[data-scope-key="set"]:checked').count() == 2
        link = page.locator('[data-dex-species="2"]')
        link.focus()
        scroll_before = page.evaluate("scrollY")
        link.press("Enter")
        expect(page.locator("#species-owned-cards .owned-card-tile").first).to_be_visible()
        expect(page.locator("#species-owned-cards h3").first).to_be_visible()
        page.locator("#species-owned-cards .owned-card-tile").first.click()
        expect(page.locator("#canonical-card")).to_be_visible()
        page.locator("#card-back").click()
        expect(page.locator("#species-owned-cards .owned-card-tile").first).to_be_focused()
        page.locator("#species-shopping").click()
        expect(page.locator("#lot-price")).to_be_visible()
        page.locator("#shopping-return").click()
        expect(page.locator("#species-owned-cards")).to_be_visible()
        page.locator(".browse-return").click()
        expect(page.locator('[data-dex-species="2"]')).to_be_focused()
        expect(page.locator("#dex-scope-editor")).to_have_attribute("open", "")
        page.wait_for_function("(value)=>Math.abs(scrollY-value)<=1", arg=scroll_before)
        assert set(
            json.loads(
                __import__("urllib.parse", fromlist=["parse_qs"]).parse_qs(urlsplit(page.url).query)["set"][0]
            )
        ) == set(selected)
        page.locator('.app-header [data-navigation-tab="/card-library/"]').click()
        expect(page.locator("#cards-count")).to_be_visible()
        page.locator('.app-header [data-navigation-section="pokedex"]').click()
        expect(page.locator("#species-grid")).to_be_visible()
        assert "set=" in page.url
        checks.append(
            "two-set OR, searchable checkboxes, species/card/Shopping return and header restoration"
        )
        if not page.locator("#dex-scope-editor").evaluate("(e)=>e.open"):
            page.locator("#dex-scope-editor>summary").click()
        page.locator('[data-scope-key="finish"]').first.check()
        applied = apply()
        assert applied["filters"]["finish"]
        assert applied["scoped_progress"]["total"] == 151
        page.locator('[data-remove-key="finish"]').click()
        expect(page.locator('[data-remove-key="finish"]')).to_have_count(0)
        assert "finish=" not in page.url
        page.locator("#dex-date_from").fill("2000-01-01")
        page.locator("#dex-date_to").fill("2000-01-01")
        exact = apply()
        assert exact["filters"]["date_from"] == exact["filters"]["date_to"] == "2000-01-01"
        checks.append("combined finish, immediate chip removal and inclusive custom range")
        load("/pokedex/?region=kanto&q=Ivysaur&set=cx05-base")
        page.locator('[data-dex-species="2"]').click()
        expect(page.locator('[data-scope-cards="collected"]')).to_contain_text("Base Set · #30")
        expect(page.locator('[data-scope-cards="outside"]')).to_contain_text("Base Set 2 · #44")
        expect(page.locator('[data-scope-cards="unresolved"]')).to_have_count(0)
        page.locator(".browse-return").click()
        expect(page.locator('[data-dex-species="2"]')).to_be_focused()
        checks.append("canonical tile join separates qualifying and outside-scope cards with correct labels")
        for width in (1280, 390, 320):
            for doubled in (False, True):
                load(
                    "/pokedex/?region=kanto&set="
                    + __import__("urllib.parse", fromlist=["quote"]).quote(json.dumps(selected))
                )
                page.set_viewport_size(dict(width=width, height=900))
                if not page.locator("#dex-scope-editor").evaluate("(e)=>e.open"):
                    page.locator("#dex-scope-editor>summary").click()
                # Long supported labels are presentation-only engineering inputs.
                page.locator("#dex-set .scope-options label").first.evaluate(
                    "e=>e.append(' — Complete retained expansion name with a deliberately long readable label')"
                )
                sample = None
                if doubled:
                    sample = page.evaluate(
                        """() => {const rows=[...document.querySelectorAll('body,body *')].map(e=>[e,parseFloat(getComputedStyle(e).fontSize)]);const e=document.querySelector('#dex-progress'),before=parseFloat(getComputedStyle(e).fontSize);rows.forEach(([e,n])=>e.style.fontSize=(n*2)+'px');return {before,after:parseFloat(getComputedStyle(e).fontSize)};}"""
                    )
                    assert sample["after"] == sample["before"] * 2
                assert page.evaluate("document.documentElement.scrollWidth<=innerWidth"), (width, doubled)
                page.locator("#scope-search-set").focus()
                page.keyboard.press("Tab")
                assert page.evaluate("document.activeElement.matches('input[type=checkbox]')")
                page.locator("#dex-scope-apply").scroll_into_view_if_needed()
                assert page.evaluate("document.documentElement.scrollWidth<=innerWidth"), (width, doubled)
                measurements.append(dict(width=width, doubled=doubled, text=sample, no_overflow=True))
                page.screenshot(path=str(output / f"engineering-ux03-{width}-{doubled}.png"))
        assert not posts, posts
        assert not errors, errors
        assert persisted_snapshot(root) == before
        checks.append(
            "six measured layouts, long labels, keyboard focus, zero writes and protected state unchanged"
        )
        context.close()
        browser.close()
    report["ux03"] = dict(checks=checks, layouts=measurements, errors=errors, posts=posts)
