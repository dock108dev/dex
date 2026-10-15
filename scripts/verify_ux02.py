"""Grouped-navigation/layout checks on the caller's isolated engineering server only."""

from urllib.parse import urlsplit


def exercise(url, root, output, report):
    from playwright.sync_api import expect, sync_playwright
    from qualify_shopping import PASSWORD
    from verify_cx05 import persisted_snapshot

    assert root.name == "engineering-root" and "review-local" not in str(root)
    checks, errors, posts = [], [], []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        context.route(
            "**/*",
            lambda route: route.continue_() if route.request.url.startswith(url + "/") else route.abort(),
        )
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(url + "/login/?next=/cards/")
        page.get_by_label("Username:", exact=True).fill("admin")
        page.get_by_label("Password:", exact=True).fill(PASSWORD)
        page.get_by_role("button", name="Sign in", exact=True).click()
        expect(page.locator("#cards-count")).to_be_visible()
        before = persisted_snapshot(root)
        page.on("request", lambda request: posts.append(request.url) if request.method != "GET" else None)

        def load(path, marker):
            response = page.goto(url + path)
            assert response.status == 200, (path, response.status)
            expect(page.locator(marker)).to_be_visible()
            page.evaluate(
                "() => new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))"
            )

        def primary(label):
            expect(page.locator('.app-header nav > a[aria-current="page"]')).to_have_count(1)
            expect(page.locator('.app-header nav > a[aria-current="page"]')).to_have_text(label)

        parity = page.locator("body").get_attribute("data-parity") == "true"
        for path in (["/hunt/", "/missing/", "/finds/"] if parity else []) + [
            "/lookup/",
            "/packs/",
            "/packs/saved/",
        ]:
            load(path, ".task-navigation")
            primary("Shopping")
            expect(page.get_by_role("navigation", name="Shopping tasks")).to_be_visible()
        checks.append("legacy Shopping destinations retain one primary destination and visible task group")
        load("/add-card/", "main h1")
        expect(page.locator('main a[href="/card-library/"]')).to_be_visible()
        if page.locator('main a[href="/scan/"]').count():
            expect(page.locator('main a[href="/scan/"]')).to_be_visible()
        else:
            expect(page.locator("main")).to_contain_text("Photo entry is unavailable")
        load("/collection-tools/", "main h1")
        expect(page.locator('main a[href="/goals/"]')).to_be_visible()
        expect(page.locator('main a[href="/collection/"]')).to_be_visible()
        load("/administration/", "main h1")
        expect(page.locator('main a[href="/product-review/"]')).to_be_visible()
        assert not posts, posts
        checks.append(
            "task entry opens read-only; catalog/photo and authorized maintenance reuse existing screens"
        )

        for path, label in [
            ("/cards/?sort=number&page_size=3", "My Cards"),
            ("/card-library/?sort=number&page_size=3", "Card Library"),
        ]:
            load(path, "#cards-count")
            primary(label)
            tile = page.locator(".owned-card-tile").first
            target = urlsplit(tile.get_attribute("href")).path
            tile.focus()
            tile.press("Enter")
            expect(page.locator("#canonical-card")).to_be_visible()
            primary(label)
            page.locator("#card-back").click()
            expect(page.locator("#cards-sort")).to_have_value("number")
            expect(page.locator(".owned-card-tile").first).to_be_focused()
            assert urlsplit(page.locator(".owned-card-tile").first.get_attribute("href")).path == target
        checks.append(
            "My Cards and Card Library retain page size, sorting, card destination and keyboard focus on Back"
        )
        load("/pokedex/?region=kanto&owned=owned", "#species-grid")
        page.locator('[data-dex-species="2"]').click()
        expect(page.locator("#species-owned-cards .owned-card-tile").first).to_be_visible()
        tile = page.locator("#species-owned-cards .owned-card-tile").first
        tile.click()
        expect(page.locator("#canonical-card")).to_be_visible()
        primary("Pokédex")
        page.locator("#card-back").click()
        expect(page.locator("#species-owned-cards .owned-card-tile").first).to_be_focused()
        page.locator(".browse-return").click()
        expect(page.locator("#dex-region")).to_have_value("kanto")
        expect(page.locator('[data-dex-species="2"]')).to_be_focused()
        checks.append("Pokédex species/card Back retains region, ownership scope and focused species/card")

        measurements = []
        for width, doubled in [(1280, False), (390, False), (320, True)]:
            page.set_viewport_size({"width": width, "height": 900})
            for path, marker in [
                ("/cards/?q=Ivy&sort=number", "#cards-count"),
                ("/card-library/?q=Ivy", "#cards-count"),
                ("/pokedex/?region=kanto&owned=owned", "#species-grid"),
                ("/pokedex/2/", "#species-owned-cards"),
                ("/shopping/", "#lot-price"),
                ("/collection-tools/", "main h1"),
                ("/add-card/", "main h1"),
            ]:
                load(path, marker)
                # A finite, already-supported long label tests wrapping without changing identifiers.
                if page.locator("#cards-set").count():
                    page.locator("#cards-set").evaluate(
                        "e=>{e.options[0].text='All supported sets and expansions with a deliberately long complete label';}"
                    )
                if doubled:
                    sample = page.evaluate("""() => {
                        const rows=[...document.querySelectorAll('body,body *')].map(e=>[e,parseFloat(getComputedStyle(e).fontSize)]);
                        const before=parseFloat(getComputedStyle(document.querySelector('h1')).fontSize);
                        rows.forEach(([e,n])=>e.style.fontSize=(n*2)+'px');
                        return {before,after:parseFloat(getComputedStyle(document.querySelector('h1')).fontSize)};
                    }""")
                    assert sample["after"] == sample["before"] * 2
                for input_id, select_id in [("cards-query", "cards-set"), ("dex-search", "dex-region")]:
                    if page.locator("#" + input_id).count():
                        sizes = page.evaluate(
                            """([input,select]) => {
                            const a=document.getElementById(input),b=document.getElementById(select);
                            return {input:a.getBoundingClientRect().height,select:b.getBoundingClientRect().height,appearance:getComputedStyle(b).appearance};
                        }""",
                            [input_id, select_id],
                        )
                        assert abs(sizes["input"] - sizes["select"]) <= 1, sizes
                        assert sizes["appearance"] == "none", sizes
                page.locator(".app-tools summary").focus()
                page.keyboard.press("Enter")
                expect(page.locator(".tools-menu")).to_be_visible()
                page.evaluate("scrollTo(0,0)")
                dims = page.evaluate("""() => ({width:innerWidth, document:document.documentElement.scrollWidth,
                    overflow:[...document.querySelectorAll('main *')].filter(e=>e.getBoundingClientRect().right>innerWidth+1).slice(0,15).map(e=>({tag:e.tagName,id:e.id,cls:e.className,text:e.textContent.slice(0,80),right:e.getBoundingClientRect().right})),
                    menu:document.querySelector('.tools-menu').getBoundingClientRect().toJSON(),
                    main:document.querySelector('main').getBoundingClientRect().toJSON(),
                    header:document.querySelector('.app-header').getBoundingClientRect().toJSON()})""")
                assert dims["document"] <= width + 1, (path, width, dims)
                assert dims["menu"]["right"] <= width + 1 and dims["menu"]["left"] >= 0, dims
                if width <= 650:
                    assert dims["menu"]["bottom"] <= dims["main"]["top"], (path, dims)
                else:
                    assert dims["header"]["bottom"] <= dims["main"]["top"], dims
                page.screenshot(
                    path=str(
                        output
                        / (
                            "engineering-ux02-"
                            + path.split("?")[0].strip("/").replace("/", "-")
                            + "-"
                            + str(width)
                            + ("-text200" if doubled else "")
                            + ".png"
                        )
                    ),
                    full_page=True,
                )
                measurements.append(
                    {
                        "path": path,
                        "width": width,
                        "text_percent": 200 if doubled else 100,
                        "document_width": dims["document"],
                    }
                )
                page.keyboard.press("Enter")
                expect(page.locator(".app-tools summary")).to_be_focused()
        checks.append(
            "21 browse/task layouts: desktop, phone and measured actual doubled text; menu keyboard and no document overflow"
        )
        assert not posts, posts
        assert not errors, errors
        assert persisted_snapshot(root) == before, "Read-only UX-02 journey changed protected state"
        report["ux02"] = {
            "checks": checks,
            "passed": True,
            "layouts": measurements,
            "provider_requests": 0,
            "private_state_equal": True,
            "page_errors": errors,
        }
        browser.close()
