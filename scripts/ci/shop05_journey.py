"""Connected card/species browser journeys; disposable catalog, blocked external access."""

import json
import re
from urllib.parse import parse_qs, urlencode, urlsplit


def exercise(page, base, output):
    from playwright.sync_api import expect

    checks, mutations = [], []
    page.on("request", lambda req: mutations.append(req.url) if req.method != "GET" else None)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    def capture(name):
        page.evaluate(
            """()=>{let p=document.getElementById('engineering-banner');if(!p){p=document.createElement('p');p.id='engineering-banner';document.body.prepend(p);}p.textContent='ENGINEERING TEST — disposable collection and controlled responses; zero marketplace calls';p.style.cssText='padding:12px;background:#ffe9a8;color:#222;font-weight:bold';}"""
        )
        page.screenshot(path=str(output / f"engineering-{name}.png"), full_page=True)

    def open_species(dex, **fields):
        page.goto(base + f"/pokedex/{dex}/?" + urlencode(fields))
        expect(page.locator("#species-explore")).to_be_visible()
        expect(page.locator("#species-shopping")).to_be_visible()

    for dex, name in ((97, "Hypno"), (94, "Gengar")):
        open_species(dex, **{"return": f"/pokedex/?owned=missing&focus={dex}&scroll=70"})
        expect(page.locator("h1")).to_contain_text(name)
        expect(page.locator(".species-detail-heading .image-frame")).to_have_class(re.compile("unavailable"))
        if dex == 97:
            capture("missing-hypno")
        page.locator("#species-shopping").click()
        expect(page.locator("#discovery-query")).to_have_value(name)
        expect(page.locator("#discovery-product-type")).to_have_value("mixed_lots")
        page.locator("#shopping-back").click()
        expect(page.locator("#species-shopping")).to_be_focused()
        page.locator("#species-explore").click()
        expect(page.locator("#cards-count")).to_contain_text("catalog")
        expect(page.locator("#library-back")).to_be_visible()
        assert page.locator(".owned-card-tile").count() > 0
        if dex == 97:
            capture("hypno-library")
        first = page.locator(".owned-card-tile").first
        group = first.get_attribute("data-group-id")
        first.click()
        expect(page.locator("#canonical-card")).to_have_attribute("data-selected-child", "")
        expect(page.locator("h1")).to_contain_text(name)
        page.locator("#card-shopping").click()
        assert name in page.locator("#discovery-query").input_value()
        page.locator("#shopping-back").click()
        expect(page.locator("#canonical-card")).to_have_attribute("data-selected-child", "")
        page.locator("#card-back").click()
        expect(page.locator(f'[data-group-id="{group}"]')).to_be_focused()
        page.locator("#library-back").click()
        expect(page.locator("#species-explore")).to_be_focused()
    checks.append(
        "Missing Hypno/Gengar: named mixed lots, actual Library choices, group details, Shopping and focused Back; no acquisition"
    )

    # Current ownership is independent of indexed availability.
    page.goto(base + "/cards/")
    expect(page.locator(".owned-card-tile").first).to_be_visible()
    owned = page.locator(".owned-card-tile").first
    owned.click()
    pokemon = page.locator(".card-pokemon-link")
    expect(pokemon).to_be_visible()
    pokemon.click()
    expect(page.locator("#species-explore")).to_be_visible()
    expect(page.locator("#species-shopping")).to_be_visible()
    checks.append("Owned Pokémon retains exploration and Shopping actions")

    # Explicit controlled empty catalog case, isolated to this engineering browser.
    def empty_catalog(route):
        response = route.fetch()
        data = response.json()
        data.update(groups=[], total=0, pages=0, page=1)
        route.fulfill(response=response, json=data)

    page.route("**/api/card-groups/?*", empty_catalog)
    open_species(251)
    page.locator("#species-explore").click()
    expect(page.locator(".empty")).to_contain_text("No indexed cards")
    page.locator("#library-back").click()
    page.locator("#species-shopping").click()
    expect(page.locator("#discovery-query")).to_have_value("Celebi")
    page.unroute("**/api/card-groups/?*", empty_catalog)
    checks.append(
        "Controlled empty Library response: honest no-indexed-cards state and named mixed-lot route"
    )

    # Multiple inherited filters stay visible as a scope change; Back keeps exact context.
    original = "/pokedex/?" + urlencode(
        {
            "set": json.dumps(["Base Set", "Base Set 2"], separators=(",", ":")),
            "finish": "holo",
            "owned": "missing",
            "scroll": "83",
            "focus": "97",
        }
    )
    open_species(97, **{"return": original})
    page.locator("#species-shopping").click()
    expect(page.locator("#shopping-scope-note")).to_contain_text("one supported set")
    expect(page.locator("#shopping-scope-note")).to_contain_text("Other collection card filters")
    page.locator("#shopping-back").click()
    assert parse_qs(urlsplit(page.url).query)["return"] == [original]
    checks.append("Multiple sets and broader filters explained; original return/filter/scroll retained")

    for name in ("Base Set", "Base Set 2"):
        open_species(97, **{"return": "/pokedex/?" + urlencode({"set": name})})
        page.locator("#species-shopping").click()
        expect(page.locator("#discovery-set")).to_have_value(name)
    checks.append("Inherited single set maps independently for Base Set and Base Set 2")

    goals = page.request.get(base + "/api/shopping/discovery/").json()["goals"]
    goal = next(row for row in goals if row["kind"] == "original151")
    open_species(97, goal=goal["id"])
    page.locator("#species-explore").click()
    expect(page.locator(".owned-card-tile").first).to_be_visible()
    page.locator(".owned-card-tile").first.click()
    expect(page.locator("#card-shopping")).to_be_visible()
    page.locator("#card-shopping").click()
    expect(page.locator("#catalog-status")).to_contain_text("local catalog only")
    retained = parse_qs(urlsplit(page.url).query)
    assert retained["goal"] == [goal["id"]] and retained["version"] == [goal["version"]]
    assert retained["intent"] == ["missing"]
    expect(page.locator(".discovery-context")).to_contain_text("Frozen")
    checks.append(
        "Frozen goal retains account-owned goal/version/policy through species, Library, card and Shopping"
    )

    # Select a local card, then an explicit printing; no child is selected by default.
    open_species(97)
    page.locator("#species-shopping").click()
    page.locator(".discovery-local summary").click()
    expect(page.locator("[data-card-details]").first).to_be_visible()
    selection = page.locator("[data-group]").first
    selection.focus()
    page.keyboard.press("Tab")
    assert page.locator("[data-card-details]").first.evaluate("el=>el===document.activeElement")
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("Enter")
    expect(page.locator("#catalog-printing-select")).to_have_value("")
    child = page.locator("#catalog-printing-select option").nth(1).get_attribute("value")
    page.locator("#catalog-printing-select").select_option(child)
    detail = page.locator("[data-card-details]").first
    detail.click()
    expect(page.locator("#canonical-card")).to_have_attribute("data-selected-child", child)
    page.locator("#card-back").click()
    expect(page.locator("#catalog-printing-select")).to_have_value(child)
    expect(page.locator("[data-card-details]").first).to_be_focused()
    assert not mutations
    checks.append(
        "Keyboard selection and separate Card details link; optional exact child survives details round trip without writes"
    )

    # The catalog and context remain real local reads. Only temporary result responses are controlled.
    authority = page.request.get(base + "/api/shopping/discovery/").json()["authority"]
    run_id = "11111111-1111-4111-8111-111111111111"
    state = {"state": "complete", "seconds": 120, "choices": {}}
    actions, polls = [], []

    def boundary(route):
        req = route.request
        if urlsplit(req.url).path != "/api/shopping/discovery/":
            route.continue_()
            return
        if req.method == "POST":
            actions.append(req.post_data_json)
            state["choices"] = req.post_data_json
        elif "run_id=" in req.url:
            polls.append(req.url)
        else:
            route.fulfill(
                json=dict(authority=authority, goals=[], provider=dict(enabled=True, configured=True))
            )
            return
        route.fulfill(
            json=dict(
                authority=authority,
                run_id=run_id,
                state=state["state"],
                running=False,
                expires_in_seconds=state["seconds"],
                choices=state["choices"],
                has_next=state["state"] == "complete",
                results=[
                    dict(
                        id="engineering-offer",
                        title="ENGINEERING temporary result",
                        item_url="https://www.ebay.com/itm/123456789012",
                        shipping=None,
                        listing_price="2.00",
                        delivered_total=None,
                        classification="unpriced",
                    )
                ]
                if state["state"] == "complete"
                else [],
            )
        )

    page.route("**/api/shopping/discovery/**", boundary)
    # Metadata is now controlled as enabled, allowing one simulated explicit Search.
    page.reload()
    expect(page.locator("#discovery-search")).to_be_enabled()
    page.locator("#discovery-sort").select_option("best_match")
    page.locator("#discovery-form").evaluate("form=>form.requestSubmit()")
    expect(page.locator(".discovery-card")).to_have_count(1)
    assert len(actions) == 1
    page.locator("#discovery-filter").select_option("unpriced")
    before_choices = actions[0].copy()
    page.locator("[data-card-details]").first.click()
    expect(page.locator("#canonical-card")).to_have_attribute("data-selected-child", child)
    state["seconds"] = 81
    page.locator("#card-back").click()
    expect(page.locator(".discovery-card")).to_have_count(1)
    expect(page.locator("#discovery-filter")).to_have_value("unpriced")
    expect(page.locator("#discovery-sort")).to_have_value("best_match")
    expect(page.locator("#discovery-next")).to_be_enabled()
    expect(page.locator("[data-card-details]").first).to_be_focused()
    assert len(actions) == 1 and actions[0] == before_choices and len(polls) == 1
    checks.append(
        "Eligible temporary handle restores query/refinements/target/focus and decreasing original lease; no new Search/More"
    )

    for unavailable in ("stopped", "expired"):
        page.locator("[data-card-details]").first.click()
        expect(page.locator("#canonical-card")).to_be_visible()
        state["state"] = unavailable
        page.locator("#card-back").click()
        expect(page.locator("#discovery-status")).to_contain_text(
            "stopped" if unavailable == "stopped" else "expired"
        )
        expect(page.locator(".discovery-card")).to_have_count(0)
        expect(page.locator("#discovery-next")).to_be_disabled()
    assert len(actions) == 1
    checks.append("Stopped and expired handles stay empty through details/Back without acquisition")

    for width, size, name in ((1280, "100%", "desktop"), (390, "100%", "narrow"), (320, "200%", "enlarged")):
        page.set_viewport_size(dict(width=width, height=900))
        page.evaluate("size=>document.documentElement.style.fontSize=size", size)
        expect(page.locator("[data-card-details]").first).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        capture(name)
    checks.append(
        "Desktop, 390px and 320px/200% text: readable identity, stable artwork fallback, separate focus targets, no overflow"
    )
    assert not errors, errors
    assert len(mutations) == 1 and mutations[0] == base + "/api/shopping/discovery/"
    return checks
