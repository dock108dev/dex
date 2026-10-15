"""navigation and contextual Shopping isolated engineering navigation and populated Shopping journeys."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path
from urllib.request import urlopen

from verify_cx02 import free_port
from verify_cx05 import persisted_snapshot, prepare

PROJECT = Path(__file__).resolve().parents[1]


def exercise(url, root, output, fixture, report, preserve_cards=True):
    navigation_exercise(url, root, output, fixture, report)
    from verify_cx06 import exercise as previous

    previous(url, root, output, fixture, report, preserve_cards=preserve_cards)


def navigation_exercise(url, root, output, fixture, report):
    from playwright.sync_api import expect, sync_playwright
    from qualify_shopping import PASSWORD

    errors, posts, external = [], [], []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport=dict(width=1280, height=900))
        context.tracing.start(screenshots=True, snapshots=True, sources=False)

        def restrict(route):
            if route.request.url.startswith(url + "/"):
                if route.request.method == "POST":
                    posts.append(route.request.url)
                route.continue_()
            else:
                assert route.request.resource_type == "image", route.request.url
                external.append(route.request.url)
                route.fulfill(status=404, body="Controlled engineering asset failure")

        context.route("**/*", restrict)
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))

        def passed(name):
            report["checks"].append(dict(check=name, passed=True))

        def load(path):
            page.goto(url + path)
            if page.locator("#content").count():
                expect(page.locator("#content h1")).not_to_contain_text("Loading")

        def capture(name, doubled=False):
            if page.locator("#clear-lot").count():
                expect(page.locator("#clear-lot")).to_be_enabled()
                expect(page.locator("#selections .selection").first).to_be_visible()
            if doubled:
                measures = page.evaluate("""() => {
                  const rows=[...document.querySelectorAll('body,body *')].map(e=>[e,parseFloat(getComputedStyle(e).fontSize)]);
                  rows.forEach(([e,n])=>e.style.fontSize=(n*2)+'px');
                  return rows.filter(([e])=>e.matches('h1,button,label,summary,.app-header a')).map(([e,n])=>({text:e.textContent.slice(0,60),before:n,after:parseFloat(getComputedStyle(e).fontSize)}));
                }""")
                assert measures and all(r["after"] == r["before"] * 2 for r in measures), measures
                if "context-shopping" in name:
                    for label in ["In this lot", "Wanted quantity", "Compare"]:
                        assert any(label in row["text"] for row in measures), (name, label, measures)
                report.setdefault("navigation_text_measurements", []).append(
                    dict(name=name, measures=measures)
                )
            assert page.evaluate("document.documentElement.scrollWidth<=innerWidth"), name
            page.screenshot(path=str(output / ("engineering-cx07-" + name + ".png")), full_page=True)

        try:
            page.goto(url + "/login/")
            page.get_by_label("Username:", exact=True).fill("admin")
            page.get_by_label("Password:", exact=True).fill(PASSWORD)
            page.get_by_role("button", name="Sign in", exact=True).click()
            expect(page).to_have_url(url + "/cards/")
            expect(page.locator("#content h1")).to_contain_text("My Cards")
            passed("initial ordinary sign-in opens My Cards")
            for invalid in [
                "{broken",
                json.dumps(dict(v=1, account="foreign", binding="foreign", destination="/pokedex/2/")),
            ]:
                load("/settings/")
                page.evaluate(
                    "value => {const key=Object.keys(sessionStorage).find(k=>k.startsWith('dex-navigation-home:'));sessionStorage.setItem(key,value);}",
                    invalid,
                )
                page.locator(".brand").click()
                expect(page).to_have_url(url + "/cards/")
                expect(page.locator("#content h1")).to_contain_text("My Cards")
            load("/settings/")
            page.evaluate(
                "() => {const key=Object.keys(sessionStorage).find(k=>k.startsWith('dex-navigation-home:')&&!k.endsWith(':tab:pokedex'));const value=JSON.parse(sessionStorage.getItem(key));value.destination='/settings/';sessionStorage.setItem(key,JSON.stringify(value));}"
            )
            page.locator(".brand").click()
            expect(page).to_have_url(url + "/cards/")
            load("/pokedex/2/")
            expect(page.locator("#content h1")).to_contain_text("Ivysaur")
            passed(
                "corrupt foreign-account and invalid remembered home fall back safely; explicit deep link wins"
            )
            load("/pokedex/?q=Ivysaur")
            expect(page.locator("[data-dex-species]")).to_have_count(1)
            page.locator(".brand").click()
            expect(page).to_have_url(__import__("re").compile(r"/pokedex/\?q=Ivysaur(?:&scroll=0)?$"))
            passed("successful collection destination remembered by brand home")
            load("/card-library/?q=Ivysaur")
            expect(page.locator("#content h1")).to_contain_text("Card Library")
            before = persisted_snapshot(root)
            n = len(posts)
            page.get_by_role("link", name="Add Card", exact=True).click()
            expect(page.locator("#content h1")).to_contain_text("Card Library")
            assert page.locator("dialog[open]").count() == 0
            assert len(posts) == n
            assert persisted_snapshot(root) == before
            passed("Add Card opens catalog without preview/copy/provider work")
            load("/pokedex/2/")
            expect(page.locator("#content h1")).to_contain_text("Ivysaur")
            find = page.locator('a[href^="/shopping/?"]').first
            expect(find).to_be_visible()
            find.click()
            expect(page.locator("h1")).to_contain_text("Lot calculator")
            expect(page.locator("body")).to_contain_text("Finding cards for Ivysaur")
            assert page.locator("#selections .selection").count() == 0
            passed("species context Shopping keeps current intent and does not add rows")
            page.locator("#printing-choice").select_option(fixture["base_printing"])
            # Explicit Add is the sole navigation-related lot population action.
            add = page.locator("#cards [data-add-printing]").first
            if not add.count():
                add = page.locator("#cards button").filter(has_text="Add").first
            expect(add).to_be_visible()
            add.click()
            row = page.locator("#selections .selection").first
            expect(row).to_be_visible()
            row.get_by_label("In this lot", exact=True).fill("3")
            row.get_by_label("Wanted quantity", exact=True).fill("7")
            row.get_by_label("Lock wanted card", exact=True).check()
            page.locator("#lot-price").fill("22.75")
            page.locator(".lot-options").filter(has=page.locator("#costs")).locator("summary").click()
            page.locator("#listing-url").fill("https://www.ebay.com/itm/123456789")
            shipping = (
                page.locator("#costs").get_by_label("Lot delivery costs: Shipping, USD", exact=True).first
            )
            shipping.fill("4.50")
            page.locator("#lot-price").focus()
            # Await explicit session-lock write, then read-only round trips must preserve it.
            expect(row.get_by_label("Lock wanted card", exact=True)).to_be_enabled()
            page.wait_for_function(
                "() => [...document.querySelectorAll('#selections input')].every(e=>!e.disabled)"
            )
            before = persisted_snapshot(root)
            n = len(posts)
            page.get_by_role("link", name="My Cards", exact=True).click()
            expect(page.locator("#content h1")).to_contain_text("My Cards")
            load("/shopping/")
            row = page.locator("#selections .selection").first
            expect(row.get_by_label("In this lot", exact=True)).to_have_value("3")
            expect(row.get_by_label("Wanted quantity", exact=True)).to_have_value("7")
            expect(row.get_by_label("Lock wanted card", exact=True)).to_be_checked()
            expect(page.locator("#lot-price")).to_have_value("22.75")
            expect(page.locator("#listing-url")).to_have_value("https://www.ebay.com/itm/123456789")
            page.reload()
            expect(
                page.locator("#selections .selection").first.get_by_label("In this lot", exact=True)
            ).to_have_value("3")
            expect(page.locator("#lot-price")).to_have_value("22.75")
            assert page.locator("#results").is_hidden()
            assert len(posts) == n
            assert persisted_snapshot(root) == before
            storage = page.evaluate("() => Object.fromEntries(Object.entries(sessionStorage))")
            draft_values = [v for k, v in storage.items() if "draft" in k]
            assert draft_values
            for value in draft_values:
                for forbidden in [
                    "cells",
                    "sources",
                    "source_url",
                    "snapshot_version",
                    "evaluations",
                    "reference_sum",
                    "scenarios",
                ]:
                    assert '"' + forbidden + '"' not in value, (forbidden, value)
            passed(
                "populated lot quantities/wants/locks/costs round trip and reload without POST or retained prices/results"
            )
            for width in (1280, 320):
                page.set_viewport_size(dict(width=width, height=900))
                load("/shopping/")
                expect(page.locator("#selections .selection").first).to_be_visible()
                capture("restored-lot-" + str(width))
                capture("navigation-default-" + str(width))
                page.locator(".app-tools summary").click()
                capture("expanded-navigation-" + str(width))
                load("/shopping/")
                capture("restored-lot-text200-" + str(width), True)
                capture("navigation-default-text200-" + str(width))
                page.locator(".app-tools summary").click()
                capture("navigation-expanded-text200-" + str(width))
                signout = page.get_by_role("button", name="Sign out", exact=True)
                signout.focus()
                expect(signout).to_be_focused()
                signout.scroll_into_view_if_needed()
                capture("navigation-expanded-bottom-text200-" + str(width))
                load("/pokedex/2/")
                page.locator('a[href^="/shopping/?"]').first.click()
                expect(page.get_by_role("heading", name="Lot calculator", exact=True)).to_be_visible()
                expect(page.locator("#context-label")).to_contain_text("Finding cards for Ivysaur")
                expect(
                    page.locator("#selections .selection").first.get_by_label("In this lot", exact=True)
                ).to_have_value("3")
                expect(
                    page.locator("#selections .selection").first.get_by_label("Wanted quantity", exact=True)
                ).to_have_value("7")
                capture("context-shopping-" + str(width))
                load("/pokedex/2/")
                page.locator('a[href^="/shopping/?"]').first.click()
                expect(page.get_by_role("heading", name="Lot calculator", exact=True)).to_be_visible()
                expect(page.locator("#context-label")).to_contain_text("Finding cards for Ivysaur")
                expect(
                    page.locator("#selections .selection").first.get_by_label("In this lot", exact=True)
                ).to_have_value("3")
                expect(
                    page.locator("#selections .selection").first.get_by_label("Wanted quantity", exact=True)
                ).to_have_value("7")
                expect(
                    page.locator("#selections .selection").first.get_by_label("Lock wanted card", exact=True)
                ).to_be_checked()
                capture("context-shopping-text200-" + str(width), True)
                load("/pokedex/2/")
                page.locator(".owned-card-tile").first.click()
                page.locator("#edit-group-card").click()
                expect(page.locator("#editor[open]")).to_be_visible()
                capture("active-dialog-" + str(width))
                capture("active-dialog-text200-" + str(width), True)
                preview = page.locator("#collection-card-form button")
                preview.focus()
                expect(preview).to_be_focused()
                preview.scroll_into_view_if_needed()
                assert page.locator("#editor").evaluate("e=>e.scrollWidth<=e.clientWidth")
                capture("active-dialog-bottom-text200-" + str(width))
                page.keyboard.press("Escape")
            passed(
                "navigation/context/restored populated lot/active dialog wide 320 and measured doubled text"
            )
            isolated = context.new_page()
            isolated.add_init_script(
                "Object.defineProperty(window,'sessionStorage',{get(){throw new Error('Engineering storage unavailable');}})"
            )
            isolated.goto(url + "/")
            expect(isolated).to_have_url(url + "/cards/")
            expect(isolated.locator("#content h1")).to_contain_text("My Cards")
            isolated.close()
            passed("unavailable browser storage preserves ordinary My Cards entry")
            load("/settings/")
            late_body = page.evaluate("""async () => {
              const id=data.operations[0].id,original=window.fetch;
              let captured;
              window.fetch=async (...args)=>{const response=await original(...args);const parse=response.json.bind(response);response.json=async()=>{captured=await parse();window.discardNavigationAuthority();return captured;};return response;};
              let blocked=false;
              try{showReview(await api('/api/operations/'+id+'/'));}catch{blocked=true;}
              finally{window.fetch=original;}
              showReview(captured);
              return {blocked,open:document.querySelectorAll('dialog[open]').length,privateRows:document.querySelectorAll('#review-body article').length};
            }""")
            assert late_body == dict(blocked=True, open=0, privateRows=0), late_body
            passed(
                "revocation during delayed JSON body blocks operation history/recovery review and clears private dialogs"
            )
            page.reload()
            expect(page.locator("#content h1")).to_contain_text("Settings & data")
            load("/shopping/")
            expect(page.locator("#selections .selection").first).to_be_visible()
            private_tab = context.new_page()
            private_tab.goto(url + "/pokedex/2/")
            private_tab.locator(".owned-card-tile").first.click()
            private_tab.locator("#edit-group-card").click()
            expect(private_tab.locator("#editor[open]")).to_be_visible()
            page.locator(".app-tools summary").click()
            page.get_by_role("button", name="Sign out", exact=True).click()
            expect(private_tab).to_have_url(__import__("re").compile(r"/login/\?next="))
            expect(private_tab.locator("dialog[open]")).to_have_count(0)
            private_tab.close()
            passed(
                "same-session logout invalidates another tab's open private dialog and safe sign-in return"
            )
            expect(page).to_have_url(url + "/pokedex/")
            assert not page.evaluate(
                "() => Object.keys(sessionStorage).some(k=>k.startsWith('dex-shopping-draft-v1:'))"
            )
            page.goto(url + "/login/")
            page.get_by_label("Username:", exact=True).fill("synthetic-member")
            page.get_by_label("Password:", exact=True).fill(PASSWORD)
            page.get_by_role("button", name="Sign in", exact=True).click()
            expect(page).to_have_url(url + "/cards/")
            load("/shopping/")
            expect(page.locator("#selections .selection")).to_have_count(0)
            expect(page.locator("#lot-price")).to_have_value("")
            assert not page.locator('.app-header a[href="/catalog-review/"]').count()
            passed(
                "logout discards private browser authority; second account cannot restore lot or owner tools"
            )
            assert not errors, errors
            report.update(
                navigation_external_requests_sent=0,
                navigation_controlled_assets=external,
                navigation_read_preservation=True,
            )
        finally:
            context.tracing.stop(path=str(output / "navigation-trace.zip"))
            browser.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--root", type=Path)
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()
    os.environ["DEX_PROFILE"] = "local"
    if args.prepare:
        prepare(args.root, args.source, args.output)
        return
    args.output.mkdir(parents=True, exist_ok=False)
    report = dict(
        evidence_class="isolated engineering browser; real loopback server and SQLite",
        customer_installation_accessed=False,
        CX08_complete=False,
        checks=[],
    )
    files = [
        "src/pokemon_hunter/beta/species_views.py",
        "src/pokemon_hunter/beta/species_projection.py",
        "src/pokemon_hunter/beta/static/species-screens.js",
        "src/pokemon_hunter/beta/card_groups.py",
        "src/pokemon_hunter/beta/card_group_views.py",
        "src/pokemon_hunter/beta/urls.py",
        "src/pokemon_hunter/beta/parity.py",
        "src/pokemon_hunter/beta/collection_views.py",
        "src/pokemon_hunter/beta/static/collection.js",
        "src/pokemon_hunter/beta/static/card-screens.js",
        "src/pokemon_hunter/beta/templates/beta/b2.html",
        "src/pokemon_hunter/beta/templates/beta/header.html",
        "src/pokemon_hunter/beta/templates/beta/base.html",
        "src/pokemon_hunter/beta/static/parity.js",
        "src/pokemon_hunter/beta/image_mappings.py",
        "src/pokemon_hunter/beta/image_bindings.py",
        "src/pokemon_hunter/beta/data/cx04_image_mappings.json",
        "src/pokemon_hunter/beta/owned_artwork.py",
        "src/pokemon_hunter/beta/scans.py",
        "src/pokemon_hunter/beta/scan_views.py",
        "src/pokemon_hunter/beta/security.py",
        "src/pokemon_hunter/beta/static/pokedex.js",
        "src/pokemon_hunter/beta/static/collection.css",
        "scripts/verify_cx07.py",
        "src/pokemon_hunter/beta/navigation.py",
        "src/pokemon_hunter/beta/shopping_context.py",
        "src/pokemon_hunter/beta/static/navigation.js",
        "src/pokemon_hunter/beta/static/lot_calculator.js",
        "src/pokemon_hunter/beta/static/lot_calculator.css",
        "src/pokemon_hunter/beta/shopping_views.py",
        "src/pokemon_hunter/beta/templates/beta/lot_calculator.html",
        "src/pokemon_hunter/beta/settings.py",
    ]
    report["source_hashes"] = {
        name: hashlib.sha256((PROJECT / name).read_bytes()).hexdigest() for name in files
    }
    try:
        with tempfile.TemporaryDirectory(prefix="dex-cx07-browser-") as temporary:
            base = Path(temporary)
            root = base / "engineering-root"
            fixture = args.output / "fixture.json"
            subprocess.run(
                [
                    sys.executable,
                    __file__,
                    "--prepare",
                    "--root",
                    str(root),
                    "--source",
                    str(base / "source"),
                    "--output",
                    str(fixture),
                ],
                check=True,
                cwd=PROJECT,
            )
            port = free_port()
            url = f"http://127.0.0.1:{port}"
            with (args.output / "server.log").open("w") as log:
                server = subprocess.Popen(
                    [
                        sys.executable,
                        str(PROJECT / "scripts/serve_e4a.py"),
                        "--root",
                        str(root),
                        "--output",
                        str(args.output),
                        "--port",
                        str(port),
                    ],
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    cwd=PROJECT,
                )
                try:
                    for _ in range(100):
                        if server.poll() is not None:
                            raise RuntimeError("Engineering server exited before becoming ready")
                        try:
                            with urlopen(url + "/login/", timeout=1) as response:
                                if response.status == 200:
                                    break
                        except OSError:
                            time.sleep(0.1)
                    else:
                        raise RuntimeError("Engineering server did not become ready")
                    exercise(url, root, args.output, json.loads(fixture.read_text()), report)
                finally:
                    server.terminate()
                    try:
                        server.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        server.kill()
                        server.wait(timeout=10)
            calls = json.loads((args.output / "provider-calls.json").read_text())
            assert calls["calls"] == 0, calls
            report["provider_calls"] = 0
            assert report["source_hashes"] == {
                name: hashlib.sha256((PROJECT / name).read_bytes()).hexdigest() for name in files
            }, "Source changed during browser verification"
            report["source_stable_during_verification"] = True
        report["passed"] = True
    except Exception:
        report["passed"] = False
        report["failure"] = traceback.format_exc()
        raise
    finally:
        (args.output / "verification.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
