"""One ordered Hunter browser journey and its local verification primitives.

The runner owns disposable process setup; these checks receive the loopback URL,
fixture root and report explicitly. No customer installation or credentials.
"""

import hashlib
import json
import re
from urllib.parse import parse_qs, urlsplit


def contrast_ratio(foreground, background):
    def luminance(value):
        channels = [float(channel) / 255 for channel in re.findall(r"[\d.]+", value)[:3]]
        linear = [
            channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
            for channel in channels
        ]
        return sum(channel * weight for channel, weight in zip(linear, (0.2126, 0.7152, 0.0722), strict=True))

    low, high = sorted((luminance(foreground), luminance(background)))
    return (high + 0.05) / (low + 0.05)


def protected_state(root):
    """Protect collection, goals, source rights and historical accounting."""
    import sqlite3

    state = {}
    with sqlite3.connect(root / "inventory.db") as db:
        for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
            quoted = '"' + name.replace('"', '""') + '"'
            rows = sorted(db.execute("SELECT * FROM " + quoted).fetchall(), key=repr)
            state[name] = hashlib.sha256(repr(rows).encode()).hexdigest()
    for name in ("price-contracts.json", "price-snapshots/active.json", "protected.json"):
        path = root / name
        state[name] = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
    return state


def exercise(base, root, output, report):
    from playwright.sync_api import expect, sync_playwright
    from qualify_shopping import PASSWORD

    checks, requests, errors, external, held = report["checks"], [], [], [], []
    state = dict(mode="real", last=None, authority=None, run=None, review=None)

    def passed(name, evidence="real API with in-process fabricated provider transport"):
        checks.append(dict(check=name, passed=True, evidence_class=evidence))

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        report["browser_version"] = browser.version
        context = browser.new_context(viewport=dict(width=1280, height=900))
        context.tracing.start(screenshots=True, snapshots=True, sources=False)

        def respond(route, value, status=200):
            route.fulfill(
                status=status,
                content_type="application/json",
                headers={"Cache-Control": "no-store, private"},
                body=json.dumps(value),
            )

        def intercept(route):
            request = route.request
            if not request.url.startswith(base + "/"):
                external.append(dict(kind=request.resource_type, sent=False))
                if state["mode"] == "controlled-images" and request.resource_type == "image":
                    route.fulfill(
                        status=200,
                        content_type="image/svg+xml",
                        body='<svg xmlns="http://www.w3.org/2000/svg" width="245" height="337"><rect width="245" height="337" fill="#eee"/><text x="20" y="160" font-size="18">Engineering image</text></svg>',
                    )
                    return
                route.fulfill(status=404, body="Controlled missing engineering image")
                return
            path = urlsplit(request.url).path
            query = parse_qs(urlsplit(request.url).query)
            if path.startswith("/api/shopping/hunter/"):
                requests.append(dict(path=path, query=query, method=request.method, body=request.post_data))
                mode = state["mode"]
                is_local = path == "/api/shopping/hunter/" and request.method == "GET" and "run_id" in query
                if mode == "hold-start" and path == "/api/shopping/hunter/" and request.method == "POST":
                    response = route.fetch()
                    held.append((route, response.json()))
                    return
                if mode == "cursor-invalid" and is_local and "cursor" in query:
                    state["mode"] = "changed-rank"
                    respond(route, dict(error="Choose a valid local result cursor"), 400)
                    return
                if mode in {"hold-local", "hold-review"} and (
                    (mode == "hold-local" and is_local) or (mode == "hold-review" and "/lot-review/" in path)
                ):
                    response = route.fetch()
                    held.append((route, response.json()))
                    return
                if mode == "review-conflict" and "/lot-review/" in path and request.method == "POST":
                    state["mode"] = "real"
                    respond(route, dict(error="Lot review changed; reload before correcting"), 409)
                    return
                if mode == "read-error" and is_local:
                    respond(route, dict(error="Controlled local read failed"), 503)
                    return
                if mode == "detail-running" and path.endswith("/lot-detail-intent/"):
                    respond(route, dict(enabled=True, dispatch_allowed=True, authority=state["authority"]))
                    return
                if mode == "detail-running" and path.endswith("/analyze-lot-details/"):
                    respond(
                        route,
                        dict(
                            detail_action_id="11111111-1111-4111-8111-111111111111",
                            state="running",
                            running=True,
                            results=[],
                            reviews=[],
                            expires_in_seconds=1700,
                            authority=state["authority"],
                        ),
                    )
                    return
                if mode == "detail-running" and "/lot-details/" in path:
                    stopped = path.endswith("/stop/")
                    respond(
                        route,
                        dict(
                            detail_action_id="11111111-1111-4111-8111-111111111111",
                            state="stopped" if stopped else "running",
                            running=not stopped,
                            results=[],
                            reviews=[],
                            expires_in_seconds=1700,
                            authority=state["authority"],
                        ),
                    )
                    return
                response = route.fetch()
                if "application/json" not in response.headers.get("content-type", ""):
                    route.fulfill(response=response)
                    return
                value = response.json()
                if value.get("authority"):
                    state["authority"] = value["authority"]
                if value.get("run_id"):
                    state["run"] = value["run_id"]
                if value.get("review_id"):
                    state["review"] = value
                if value.get("reviews"):
                    state["review"] = value["reviews"][0]
                if "configured" in value:
                    state["policy"] = value
                if is_local and response.ok:
                    state["last"] = value
                if mode == "unavailable" and path == "/api/shopping/hunter/" and not query:
                    value["traversal_allowance_enabled"] = False
                    value["acquisition_available"] = False
                    value["acquisition_unavailable_reason"] = (
                        "Hunt is unavailable: controlled engineering disabled acquisition."
                    )
                    value["traversal_remaining"] = {key: 0 for key in value["traversal_remaining"]}
                elif mode == "wrong-authority" and value.get("authority"):
                    value["authority"]["binding"] = "foreign-controlled-session"
                elif mode == "missing-authority":
                    value.pop("authority", None)
                elif (
                    mode
                    in {
                        "empty",
                        "expired",
                        "withdrawn",
                        "changed-rank",
                        "hostile",
                        "short-lease",
                        "broken-images",
                        "controlled-images",
                    }
                    and is_local
                ):
                    if mode in {"empty", "expired"}:
                        value.update(results=[], result_cursor=None, has_next=False, running=False)
                        value["state"] = "expired" if mode == "expired" else "complete"
                    elif mode == "withdrawn":
                        for row in value["results"]:
                            row["hunt_status"] = "unpriced"
                            row["reference"] = None
                            row["reason"] = "Controlled reference withdrawn"
                            row["opportunity"] = dict(classification="unpriced", scenarios=[], rank=None)
                    elif mode == "changed-rank":
                        for row in value["results"]:
                            row["title"] = "CHANGED CURRENT PROJECTION " + row.get("title", "")
                            if row.get("proposed_identity"):
                                row["proposed_identity"]["name"] = "CHANGED CURRENT PROJECTION"
                            row["label"] = "CHANGED CURRENT PROJECTION"
                        value["results"].reverse()
                    elif mode == "hostile":
                        row = value["results"][0]
                        row["title"] = '<img src=x onerror="window.HUNTER_HOSTILE=1"> Engineering seller text'
                    elif mode == "short-lease":
                        value["expires_in_seconds"] = 1
                    elif mode in {"broken-images", "controlled-images"}:
                        first = value["results"][0]
                        if first.get("proposed_identity"):
                            first["proposed_identity"]["artwork"] = dict(
                                role="card_group_reference",
                                precision="card_group",
                                availability="reference",
                                image_url="https://assets.tcgdex.net/en/base/base1/44/high.webp",
                                alt="Controlled engineering reference image",
                            )
                respond(route, value, response.status)
                return
            route.continue_()

        context.route("**/*", intercept)
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))

        def load(mode="real", enabled=True):
            state["mode"] = mode
            page.goto(base + "/shopping/hunter/")
            expect(page.locator("#hunter-app")).to_be_visible()
            if enabled and mode not in {"wrong-authority", "missing-authority", "unavailable"}:
                expect(page.locator("#hunter-start")).to_be_enabled()

        def start(scope="singles"):
            page.locator("#hunter-scope").select_option(scope)
            with page.expect_response(
                lambda response: (
                    response.url == base + "/api/shopping/hunter/" and response.request.method == "POST"
                )
            ):
                page.locator("#hunter-start").focus()
                page.locator("#hunter-start").press("Enter")
            expect(page.locator("#hunter-results").locator("[data-result-id], article").first).to_be_visible(
                timeout=30000
            )
            expect(page.locator("#hunter-local-next")).to_be_enabled(timeout=30000)

        def post_count(suffix):
            return len([r for r in requests if r["method"] == "POST" and r["path"].endswith(suffix)])

        def settle_held():
            while held:
                route, value = held.pop(0)
                try:
                    respond(route, value)
                except Exception:
                    # AbortController cancellation can close a held browser route.
                    pass

        def capture(name, width=1280, doubled=False):
            page.set_viewport_size(dict(width=width, height=900))
            if doubled:
                measured = page.evaluate("""() => {
                  const rows=[...document.querySelectorAll('body,body *')]
                    .map(e=>[e,parseFloat(getComputedStyle(e).fontSize)]);
                  rows.forEach(([e,n])=>e.style.fontSize=(n*2)+'px');
                  return rows.filter(([e])=>e.matches('#hunter-app h1,#hunter-app button,#hunter-app label'))
                    .map(([e,n])=>({text:e.textContent.slice(0,80),before:n,after:parseFloat(getComputedStyle(e).fontSize)}));
                }""")
                assert measured and all(r["after"] == r["before"] * 2 for r in measured)
                report.setdefault("text_measurements", []).append(dict(state=name, measurements=measured))
            overflow = page.evaluate("""() => [...document.querySelectorAll('#hunter-app *')]
              .filter(e=>{const r=e.getBoundingClientRect();return r.width&& (r.right>innerWidth+1||r.left< -1)})
              .map(e=>({tag:e.tagName,text:e.textContent.slice(0,80),right:e.getBoundingClientRect().right}))""")
            assert page.evaluate("document.documentElement.scrollWidth<=innerWidth"), (name, overflow[:10])
            if name == "unavailable":
                colors = page.locator(".hunter-heading h1,.hunter-heading nav a").evaluate_all("""elements=>elements.map(el=>{
                  let parent=el,background='rgb(255,255,255)';
                  while(parent){const paint=getComputedStyle(parent).backgroundColor;
                    if(paint!=='rgba(0, 0, 0, 0)'&&paint!=='transparent'){background=paint;break;}parent=parent.parentElement;}
                  return {text:el.textContent,foreground:getComputedStyle(el).color,background};
                })""")
                for color in colors:
                    color["contrast"] = round(contrast_ratio(color["foreground"], color["background"]), 3)
                    assert color["contrast"] >= 4.5, color
                report["heading_and_navigation_contrast"] = colors
            if name.startswith(("results-", "lot-review-")):
                target = "hunter-review" if name.startswith("lot-review-") else "hunter-results"
                page.evaluate(
                    "id=>scrollTo(0,document.getElementById(id).getBoundingClientRect().top+scrollY-16)",
                    target,
                )
            elif name.startswith("settings-"):
                page.locator("#hunter-usage-enabled").scroll_into_view_if_needed()
            page.screenshot(path=str(output / ("engineering-hunter-" + name + ".png")), full_page=False)
            report.setdefault("layouts", []).append(
                dict(state=name, width=width, doubled=doubled, overflow=False)
            )

        def settings(enabled, per_hunt, daily, timezone, recurring):
            page.locator("#hunter-usage-settings").evaluate("el=>el.open=true")
            page.locator("#hunter-usage-enabled").select_option(str(enabled).lower())
            page.locator("#hunter-usage-per-hunt").fill(str(per_hunt))
            page.locator("#hunter-usage-daily").fill(str(daily))
            page.locator("#hunter-usage-timezone").select_option(timezone)
            page.locator("#hunter-usage-recurring").select_option(str(recurring).lower())
            page.locator("#hunter-usage-expiry-mode").select_option("none")
            with page.expect_response(
                lambda response: (
                    response.url == base + "/api/shopping/hunter/usage/" and response.request.method == "POST"
                )
            ):
                page.locator("#hunter-usage-save").click()
            expect(page.locator("#hunter-usage-feedback")).to_contain_text("Usage settings saved")
            expect(page.locator("#hunter-usage-save")).to_be_enabled()

        try:
            page.goto(base + "/login/")
            page.get_by_label("Username:", exact=True).fill("admin")
            page.get_by_label("Password:", exact=True).fill(PASSWORD)
            page.get_by_role("button", name="Sign in", exact=True).click()
            expect(page).to_have_url(base + "/cards/")
            before = protected_state(root)
            load(enabled=False)
            expect(page.locator("#hunter-start")).to_be_disabled()
            expect(page.locator("#hunter-usage-settings")).to_have_attribute("open", "")
            for key in ("enabled", "per-hunt", "daily", "timezone", "recurring", "expiry-mode"):
                expect(page.locator("#hunter-usage-" + key)).to_have_value("")
            assert not (root / "hunter-policy.json").exists()
            assert not (output / "fake-transport.json").exists()
            capture("settings-unconfigured-320", 320)
            capture("settings-unconfigured-320-text2x", 320, doubled=True)
            passed(
                "unconfigured ordinary owner settings are blank and Hunt stays disabled without any provider dispatch",
                "real settings API on disposable engineering root",
            )
            load(enabled=False)
            settings(True, 6, 20, "America/New_York", False)
            expect(page.locator("#hunter-start")).to_be_enabled()
            expect(page.locator("#hunter-usage-capacity")).to_contain_text("20 of 20")
            expect(page.locator("#hunter-usage-capacity")).to_contain_text("does not renew")
            page.locator("#hunter-usage-pause").click()
            expect(page.locator("#hunter-usage-feedback")).to_contain_text("Acquisition paused")
            expect(page.locator("#hunter-start")).to_be_disabled()
            expect(page.locator("#hunter-usage-pause")).to_be_disabled()
            settings(False, 2, 7, "UTC", True)
            expect(page.locator("#hunter-start")).to_be_disabled()
            expect(page.locator("#hunter-usage-per-hunt")).to_have_value("2")
            expect(page.locator("#hunter-usage-daily")).to_have_value("7")
            expect(page.locator("#hunter-usage-capacity")).to_contain_text("Next daily window")
            settings(True, 2, 7, "UTC", True)
            expect(page.locator("#hunter-start")).to_be_enabled()
            expect(page.locator("#hunter-usage-capacity")).to_contain_text("7 of 7")
            assert state["policy"]["revision"] == 4
            assert state["policy"]["used"] == 0
            assert not (output / "fake-transport.json").exists()
            capture("settings-selected-320", 320)
            capture("settings-selected-320-text2x", 320, doubled=True)
            passed(
                "owner explicitly selects limits, pauses, reduces limits, changes timezone and resumes through actual settings APIs; no acquisition occurs",
                "real policy/accounting on disposable engineering root",
            )
            load()
            settings(True, 15, 1000, "America/New_York", True)
            page.locator("#hunter-usage-settings").evaluate("el=>el.open=false")
            load("unavailable")
            expect(page.locator("#hunter-status")).to_contain_text("unavailable", ignore_case=True)
            capture("unavailable")
            passed(
                "disabled acquisition is explicit unavailable, without completed empty results",
                "controlled disabled metadata",
            )

            load()
            start()
            assert state["last"]["results"] and state["last"]["result_cursor"]
            assert state["last"]["traversal_coverage"]["fetched"] >= 260
            passed("explicit Hunt reaches real capped backend with fake transport and partial coverage")
            capture("results-1280")
            for width in (390, 320):
                capture(f"results-{width}", width)
            capture("results-320-text2x", 320, doubled=True)
            load()
            start()
            count = post_count("/continue/")
            local_before = len([r for r in requests if r["query"].get("cursor")])
            page.locator("#hunter-local-next").click()
            page.wait_for_function("() => !document.querySelector('#hunter-local-next')?.disabled")
            assert len([r for r in requests if r["query"].get("cursor")]) > local_before
            assert post_count("/continue/") == count
            expect(page.locator("#hunter-cards")).to_contain_text("unsupported", ignore_case=True)
            expect(page.locator("#hunter-cards")).to_contain_text("unpriced")
            assert state["last"]["coverage"]["unsupported"] >= 1
            assert state["last"]["coverage"]["ambiguous"] >= 1
            assert state["last"]["coverage"]["unpriced"] >= 1
            passed("received-result paging uses GET cursor and no acquisition Continue")
            passed(
                "unsupported, ambiguous and unpriced received rows remain visible with separate dispositions"
            )
            load()
            start()
            state["mode"] = "cursor-invalid"
            page.locator("#hunter-local-next").click()
            expect(page.locator("#hunter-results")).to_contain_text("CHANGED CURRENT PROJECTION")
            assert post_count("/continue/") == count
            assert page.locator("#hunter-cards > article").count() == 200
            passed(
                "invalid local cursor replaces projection and ranks without acquisition",
                "controlled cursor invalidation",
            )
            state["mode"] = "real"
            page.locator("#hunter-continue").click()
            expect(page.locator("#hunter-continue")).to_be_enabled(timeout=30000)
            assert post_count("/continue/") == count + 1
            continuation = [r for r in requests if r["path"].endswith("/continue/")][-1]
            assert set(json.loads(continuation["body"])) == {"cursor"}
            passed("explicit acquisition Continue sends only captured cursor")

            inspect = page.locator("[data-inspect]").first
            inspect_id = inspect.get_attribute("id")
            inspect.focus()
            inspect.click()
            expect(page.locator("#hunter-review")).to_be_visible()
            page.locator("#hunter-back").click()
            expect(page.locator("#" + inspect_id)).to_be_focused()
            passed("single inspection returns to originating result focus without acquisition")
            page.locator("#" + inspect_id).press("Enter")
            expect(page.locator("#hunter-review")).to_be_visible()
            page.go_back()
            expect(page.locator("#" + inspect_id)).to_be_focused()
            outline = page.locator("#" + inspect_id).evaluate(
                "el=>({style:getComputedStyle(el).outlineStyle,width:parseFloat(getComputedStyle(el).outlineWidth)})"
            )
            assert outline["style"] != "none" and outline["width"] >= 2
            passed("keyboard Hunt/inspection and browser Back retain visible originating focus")

            load()
            start("lots")
            analyze = page.get_by_role("button", name="Analyze lot", exact=True).first
            analyze.focus()
            analyze.click()
            expect(page.locator("#hunter-review")).to_be_visible()
            expect(page.locator("#hunter-review")).to_contain_text("Ungraded")
            expect(page.locator("#hunter-review")).to_contain_text("Bulbasaur")
            passed(
                "Analyze lot uses received text through real proposal/review API; owned duplicates remain included"
            )
            report["review_contract_observed"] = True
            assert state["review"]["proposal"]["stock_quantity"] == 8
            assert state["review"]["proposal"]["lot_units"] == 2
            assert sum(card["quantity"] for card in state["review"]["review"]["cards"]) == 3
            quantity = page.get_by_label("Included cards inside this one lot", exact=True).first
            remainder = page.get_by_label(
                "Unresolved remainder (blank means Unknown; 0 confirms no remaining cards)", exact=True
            )
            quantity.fill("3")
            expect(page.locator(".hunter-review-comparison")).to_contain_text("Inputs changed")
            remainder.fill("")
            revision = state["review"]["revision"]
            page.locator("#hunter-review-compare").click()
            expect(page.locator("#hunter-review-compare")).to_be_enabled()
            expect(page.locator(".hunter-review-comparison")).to_contain_text("Remainder: Unknown")
            correction = [r for r in requests if r["method"] == "POST" and "/lot-review/" in r["path"]][-1]
            payload = json.loads(correction["body"])
            assert payload["revision"] == revision and payload["unknown_contents"] is None
            assert all(set(card) == {"printing_id", "quantity"} for card in payload["cards"])
            passed(
                "changed quantities clear obsolete comparison; Unknown remainder sends null and no inherited attribute confirmation"
            )
            remainder.fill("0")
            page.locator("#hunter-review-compare").click()
            expect(page.locator(".hunter-review-comparison")).to_contain_text("Remainder: 0")
            correction = [r for r in requests if r["method"] == "POST" and "/lot-review/" in r["path"]][-1]
            assert json.loads(correction["body"])["unknown_contents"] == 0
            passed(
                "explicit zero remainder is distinct from Unknown; optimistic corrections use real backend revisions"
            )
            quantity = page.get_by_label("Included cards inside this one lot", exact=True).first
            quantity.fill("4")
            state["mode"] = "review-conflict"
            attempts = len([r for r in requests if r["method"] == "POST" and "/lot-review/" in r["path"]])
            page.locator("#hunter-review-compare").click()
            expect(page.locator(".hunter-review-status")).to_contain_text("Current revision reloaded")
            assert (
                len([r for r in requests if r["method"] == "POST" and "/lot-review/" in r["path"]])
                == attempts + 1
            )
            expect(page.get_by_label("Included cards inside this one lot", exact=True).first).to_have_value(
                "3"
            )
            passed(
                "409 correction conflict reloads current revision without overwrite or automatic POST retry",
                "controlled revision conflict over real review",
            )
            card_rows = page.locator(".hunter-review-cards > article")
            card_rows.nth(1).get_by_label("Included cards inside this one lot", exact=True).fill("0")
            page.get_by_text("Whole-lot amount and optional costs", exact=True).click()
            page.get_by_label("Tax", exact=True).fill("0")
            page.get_by_label("Other costs", exact=True).fill("0")
            page.locator("#hunter-review-compare").click()
            expect(page.locator(".hunter-review-comparison h3")).to_have_text(
                "Complete delivered reference comparison"
            )
            assert state["review"]["comparison"]["complete_delivered_comparison"] is True
            assert state["review"]["comparison"]["whole_lot_price_count"] == 1
            assert state["review"]["comparison"]["priced_card_quantity"] == 3
            passed(
                "reconciled fully priced owned duplicates and known costs enable one whole-lot delivered comparison"
            )
            capture("lot-review-1280")
            capture("lot-review-320", 320)
            capture("lot-review-320-text2x", 320, doubled=True)
            page.locator("#hunter-back").click()
            expect(analyze).to_be_focused()
            passed("temporary lot review Back restores originating result focus")

            page.locator("#hunter-stop").click()
            expect(page.locator("#hunter-results")).not_to_contain_text("Engineering Pokémon lot")
            expect(page.locator("#hunter-review")).to_be_hidden()
            passed("parent Stop clears temporary results and dependent review")

            load()
            start("lots")
            page.get_by_role("button", name="Analyze lot", exact=True).first.click()
            expect(page.locator("#hunter-review")).to_be_visible()
            page.get_by_role("button", name="Additional official details…", exact=True).click()
            expect(page.locator("#hunter-detail-status")).to_contain_text("separate explicit acquisition")
            expect(page.locator("#hunter-detail-load")).to_be_enabled()
            assert post_count("/analyze-lot-details/") == 0
            passed("official detail intent reads selected ordinary capacity and does not execute its plan")
            state["mode"] = "detail-running"
            page.get_by_role("button", name="Additional official details…", exact=True).click()
            expect(page.locator("#hunter-detail-load")).to_be_enabled()
            page.locator("#hunter-detail-load").click()
            expect(page.locator("#hunter-detail-status")).to_contain_text("Stop details remains independent")
            stops = post_count("/stop/")
            page.locator("#hunter-detail-stop").click()
            expect(page.locator("#hunter-detail-status")).to_contain_text("Official details stopped")
            expect(page.locator("#hunter-results")).to_be_visible()
            detail_stops = [
                r for r in requests if "/lot-details/" in r["path"] and r["path"].endswith("/stop/")
            ]
            assert detail_stops and json.loads(detail_stops[-1]["body"]) == {}
            assert post_count("/stop/") == stops + 1
            passed(
                "independent detail Stop clears child view while preserving Hunter results",
                "controlled running detail action; real parent Hunt",
            )
            state["mode"] = "real"
            page.locator("#hunter-stop").click()

            load()
            start()
            expect(page.locator("#hunter-cards > article").first).to_contain_text("$12.00")
            state["mode"] = "broken-images"
            with page.expect_response(lambda response: "?run_id=" in response.url):
                page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
            expect(page.locator("#hunter-start")).to_be_enabled()
            first_image = page.locator("#hunter-cards > article").first.locator(".hunter-image").first
            expect(first_image).to_contain_text("Card reference unavailable")
            expect(first_image.locator("img")).to_have_count(0)
            size = first_image.bounding_box()
            assert size["height"] > size["width"] > 50
            passed(
                "broken authorized reference image preserves neutral fixed space and readable identity",
                "controlled image failure",
            )
            state["mode"] = "controlled-images"
            with page.expect_response(lambda response: "?run_id=" in response.url):
                page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
            expect(page.locator("#hunter-start")).to_be_enabled()
            expect(page.locator("#hunter-cards > article").first.locator("img")).to_be_visible()
            assert (
                page.locator("#hunter-cards > article").first.locator("img").get_attribute("referrerpolicy")
                == "no-referrer"
            )
            passed(
                "reference image uses controlled response and no-referrer rendering without seller-photo claims",
                "controlled reference image response",
            )
            state["mode"] = "withdrawn"
            with page.expect_response(lambda response: "?run_id=" in response.url):
                page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
            expect(page.locator("#hunter-cards")).not_to_contain_text("$12.00")
            expect(page.locator("#hunter-cards")).not_to_contain_text("Reference gap:")
            expect(page.locator("#hunter-cards")).not_to_contain_text("Rank ")
            expect(page.locator("#hunter-start")).to_be_enabled()
            passed(
                "tab resumption revalidates reference lifecycle and removes values, gaps and ranks",
                "controlled reference withdrawal over real results",
            )
            state["mode"] = "hostile"
            with page.expect_response(lambda response: "?run_id=" in response.url):
                page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
            expect(page.locator("#hunter-local-next")).to_be_enabled()
            page.locator("[data-reveal]").first.click()
            expect(page.locator("#hunter-cards")).to_contain_text(
                '<img src=x onerror="window.HUNTER_HOSTILE=1">'
            )
            assert page.evaluate("window.HUNTER_HOSTILE || 0") == 0
            assert page.locator('#hunter-cards img[src="x"]').count() == 0
            passed(
                "hostile seller markup renders as inert text and reveal performs no acquisition",
                "controlled hostile seller text",
            )
            state["mode"] = "empty"
            with page.expect_response(lambda response: "?run_id=" in response.url):
                page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
            expect(page.locator("#hunter-cards")).to_contain_text("No eligible results")
            passed(
                "empty completed batch explains limited coverage separately from unavailable acquisition",
                "controlled empty batch",
            )
            state["mode"] = "expired"
            with page.expect_response(lambda response: "?run_id=" in response.url):
                page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
            expect(page.locator("#hunter-status")).to_contain_text("expired")
            expect(page.locator("#hunter-results")).to_be_hidden()
            passed(
                "original parent expiry clears dependent result and review content",
                "controlled parent expiry",
            )

            load()
            start()
            state["mode"] = "read-error"
            page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
            expect(page.locator("#hunter-status")).to_contain_text("Controlled local read failed")
            expect(page.locator("#hunter-results")).to_be_hidden()
            expect(page.locator("#hunter-review")).to_be_hidden()
            passed(
                "local read failure clears obsolete comparison and offers understandable recovery",
                "controlled local HTTP error",
            )
            load()
            start()
            state["mode"] = "short-lease"
            page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
            expect(page.locator("#hunter-status")).to_contain_text("expired", timeout=5000)
            expect(page.locator("#hunter-results")).to_be_hidden()
            passed(
                "captured lease timer clears content without waiting for another backend response",
                "controlled one-second original lease",
            )

            load()
            start()
            state["mode"] = "hold-local"
            page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
            for _ in range(50):
                if held:
                    break
                page.wait_for_timeout(20)
            assert held, "Expected a controlled delayed lifecycle read"
            page.locator("#hunter-stop").click()
            expect(page.locator("#hunter-results")).to_be_hidden()
            settle_held()
            page.wait_for_timeout(150)
            expect(page.locator("#hunter-results")).to_be_hidden()
            expect(page.locator("#hunter-review")).to_be_hidden()
            passed(
                "late lifecycle response cannot restore results after independent parent Stop",
                "controlled delayed response over real stopped run",
            )

            load()
            state["mode"] = "hold-start"
            starts = post_count("/api/shopping/hunter/")
            page.locator("#hunter-start").click()
            expect(page.locator("#hunter-status")).to_contain_text("Starting your Hunt")
            expect(page.locator("#hunter-stop")).to_be_enabled()
            page.locator("#hunter-form").evaluate(
                "form=>form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}))"
            )
            assert post_count("/api/shopping/hunter/") == starts + 1
            page.locator("#hunter-stop").click()
            settle_held()
            expect(page.locator("#hunter-results")).to_be_hidden()
            passed(
                "repeated Start is suppressed and Stop during start suppresses late run publication",
                "controlled delayed start over real backend",
            )
            state["mode"] = "real"
            load()
            start()
            state["mode"] = "wrong-authority"
            page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
            expect(page.locator("#hunter-status")).to_contain_text("session changed")
            expect(page.locator("#hunter-results")).to_be_hidden()
            expect(page.locator("#hunter-review")).to_be_hidden()
            passed(
                "changed account/session authority clears private results and reviews",
                "controlled foreign session binding",
            )
            assert protected_state(root) == before
            passed("inventory, owned copies, goals and source-right files remain unchanged")
            stores = page.evaluate("""() => ({local:{...localStorage},session:{...sessionStorage}})""")
            serialized = json.dumps(stores)
            assert "Engineering Pokémon lot" not in serialized
            assert "FABRICATED_LOCAL" not in serialized
            assert "reference_amount" not in serialized and "shortDescription" not in serialized
            passed("browser durable storage contains no provider summaries or comparison values")
            assert not errors, errors
            assert all(item["kind"] == "image" for item in external), external
            report.update(
                browser_errors=errors, external_requests_sent=0, controlled_external_images=len(external)
            )
        finally:
            settle_held()
            context.unroute_all(behavior="ignoreErrors")
            context.tracing.stop(path=str(output / "engineering-hunter-trace.zip"))
            browser.close()
            report["hunter_requests"] = requests
