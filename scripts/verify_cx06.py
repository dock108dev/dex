"""Pokédex and species pages real-loopback engineering journeys; customer root remains untouched."""

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
    """Ordinary sign-in, normal species/card pages, read preservation and races."""
    from playwright.sync_api import expect, sync_playwright
    from qualify_shopping import PASSWORD

    errors, external, parity_requests = [], [], []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(viewport=dict(width=1280, height=900))
        context.tracing.start(screenshots=True, snapshots=True, sources=False)

        def restrict(route):
            request = route.request
            if request.url.startswith(url + "/"):
                if "/api/parity/" in request.url:
                    parity_requests.append(request.url)
                route.continue_()
            else:
                assert request.resource_type == "image", request.url
                external.append(dict(url=request.url, sent_to_remote=False))
                route.fulfill(status=404, body="Controlled image failure")

        context.route("**/*", restrict)
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))

        def get(path):
            response = context.request.get(url + path)
            assert response.status == 200, (path, response.status, response.text())
            return response.json()

        def passed(name):
            report["checks"].append(dict(check=name, passed=True))

        def load(path):
            page.goto(url + path)
            expect(page.locator("#content h1")).not_to_contain_text("Loading")
            expect(page.locator("#content")).not_to_contain_text("Loading Pokémon")
            expect(page.locator("#content")).not_to_contain_text("Loading Your Cards")

        def capture(name):
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), name
            assert page.evaluate("""() => [...document.querySelectorAll('#content button, #content input, #content select')]
                .filter(e=>e.getBoundingClientRect().width).every(e=>e.getBoundingClientRect().left>=0 && e.getBoundingClientRect().right<=innerWidth)"""), (
                name
            )
            if "text200" in name:
                measured = page.evaluate("""() => {
                  const selectors=['#content h1','#your-cards-heading','.owned-card-tile strong','dialog[open] button','dialog[open] label','#dex-search','#dex-scope-label'];
                  return selectors.flatMap(selector=>[...document.querySelectorAll(selector)].map(e=>({selector,expected:Number(e.dataset.cx06Font),actual:parseFloat(getComputedStyle(e).fontSize)})));
                }""")
                assert measured and all(
                    row["expected"] == row["actual"] and row["expected"] > 0 for row in measured
                ), measured
                report.setdefault("capture_text_measurements", []).append(
                    dict(name=name, measurements=measured)
                )
            page.screenshot(path=str(output / ("engineering-pokemon-" + name + ".png")), full_page=True)
            page.screenshot(path=str(output / ("engineering-pokemon-" + name + "-viewport.png")))

        def double_text():
            measured = page.evaluate("""() => {
              const h=document.querySelector('#content h1'),before=parseFloat(getComputedStyle(h).fontSize);
              const sizes=[...document.querySelectorAll('body,body *')].map(e=>[e,parseFloat(getComputedStyle(e).fontSize)]);
              sizes.forEach(([e,size])=>{e.style.fontSize=(size*2)+'px';e.dataset.cx06Font=String(size*2);});
              return {before,after:parseFloat(getComputedStyle(h).fontSize)};
            }""")
            assert measured["after"] == measured["before"] * 2, measured
            report.setdefault("text_measurements", []).append(measured)

        try:
            page.goto(url + "/login/?next=/pokedex/")
            page.get_by_label("Username:", exact=True).fill("admin")
            page.get_by_label("Password:", exact=True).fill(PASSWORD)
            page.get_by_role("button", name="Sign in", exact=True).click()
            expect(page.locator("[data-dex-species]")).to_have_count(251)
            before = persisted_snapshot(root)
            projection = get("/api/pokedex-species/")
            assert len(projection["species"]) == 251
            assert {row["dex"] for row in projection["species"]} == set(range(1, 252))
            assert page.locator("[data-select-species]").count() == 0
            assert page.locator("dialog[open]").count() == 0
            passed("251 canonical Pokémon, current status, no default selection or browsing dialog")
            page.locator("#dex-search").fill("Ivysaur")
            page.locator("#dex-search").press("Enter")
            expect(page.locator("[data-dex-species]")).to_have_count(1)
            species = page.locator("[data-dex-species]").first
            species.focus()
            species.press("Enter")
            expect(page).to_have_url(__import__("re").compile(r"/pokedex/2/\?"))
            expect(page.locator("#content h1")).to_contain_text("Ivysaur")
            expect(page.get_by_role("heading", name="Your Cards", exact=True)).to_be_visible()
            expect(page.locator(".owned-card-tile")).to_have_count(2)
            assert page.locator("dialog[open]").count() == 0
            owned = get("/api/species/2/card-groups/")["owned"]["groups"]
            assert {(g["set_name"], g["collector_number"]) for g in owned} == {
                ("Base Set", "30"),
                ("Base Set 2", "44"),
            }
            assert all(
                "child=" not in a
                for a in page.locator(".owned-card-tile").evaluate_all(
                    "rows=>rows.map(e=>e.getAttribute('href'))"
                )
            )
            page.locator(".owned-card-tile").first.click()
            expect(page.locator("#canonical-card")).to_be_visible()
            assert (
                get(
                    "/api/card-groups/" + page.locator("#canonical-card").get_attribute("data-group-id") + "/"
                )["selected_child"]
                is None
            )
            page.locator("#card-back").click()
            expect(page.locator("#content h1")).to_contain_text("Ivysaur")
            expect(page.locator(".owned-card-tile")).to_have_count(2)
            page.reload()
            expect(page.locator(".owned-card-tile")).to_have_count(2)
            passed("one-click species, two-click owned card, two Ivysaur groups once, card Back and refresh")
            page.get_by_role("link", name=__import__("re").compile("Back to Pokédex")).first.click()
            expect(page.locator("[data-dex-species]")).to_have_count(1)
            expect(page.locator("#dex-search")).to_have_value("Ivysaur")
            expect(page.locator("[data-dex-species]").first).to_be_focused()
            passed("visible Back restores list search and activated species focus")
            load("/pokedex/?species=2")
            assert "/pokedex/2/" in page.url
            page.go_back()
            expect(page.locator("[data-dex-species]")).to_have_count(1)
            passed("legacy species URL canonicalizes; browser Back restores original list")
            for width in (1280, 320):
                page.set_viewport_size(dict(width=width, height=900))
                load("/pokedex/")
                expect(page.locator("[data-dex-species]")).to_have_count(251)
                capture("list-" + str(width))
                page.get_by_role("button", name="Select", exact=True).click()
                page.locator("#dex-clear-selection").click()
                first = page.locator("[data-select-species]").first
                first.focus()
                first.press("Space")
                expect(page.locator("#dex-lookup-selection")).to_be_enabled()
                capture("list-selection-" + str(width))
                for summary in page.locator("#content details > summary").all():
                    summary.click()
                page.evaluate("scrollTo(0,0)")
                capture("list-expanded-" + str(width))
                page.locator("#content details").last.scroll_into_view_if_needed()
                capture("list-tools-" + str(width))
                load("/pokedex/")
                double_text()
                capture("list-text200-" + str(width))
                load("/pokedex/")
                page.get_by_role("button", name="Select", exact=True).click()
                for summary in page.locator("#content details > summary").all():
                    summary.click()
                page.evaluate("scrollTo(0,0)")
                double_text()
                capture("list-expanded-text200-" + str(width))
                page.locator("#dex-goal").scroll_into_view_if_needed()
                capture("list-goal-controls-text200-" + str(width))
                page.locator("#dex-set").scroll_into_view_if_needed()
                capture("list-card-filters-text200-" + str(width))
                page.locator("#dex-era").scroll_into_view_if_needed()
                capture("list-era-controls-text200-" + str(width))
                page.locator("#dex-rarity").scroll_into_view_if_needed()
                capture("list-rarity-controls-text200-" + str(width))
                select_widths = page.locator("#content select").evaluate_all("""rows=>rows.filter(e=>e.getBoundingClientRect().width && !e.value).map(e=>{
                  const ctx=document.createElement('canvas').getContext('2d');ctx.font=getComputedStyle(e).font;
                  return {id:e.id,text:ctx.measureText(e.selectedOptions[0].text).width,available:e.clientWidth-48};
                })""")
                assert all(row["text"] <= row["available"] for row in select_widths), select_widths
                page.locator("#dex-batch-actions").scroll_into_view_if_needed()
                capture("list-selection-text200-" + str(width))
                page.locator("#content details").last.scroll_into_view_if_needed()
                capture("list-tools-text200-" + str(width))
                load("/pokedex/2/")
                expect(page.locator(".owned-card-tile")).to_have_count(2)
                capture("species-" + str(width))
                for summary in page.locator("#content details > summary").all():
                    summary.click()
                capture("species-expanded-" + str(width))
                load("/pokedex/2/")
                double_text()
                capture("species-text200-" + str(width))
                for summary in page.locator("#content details > summary").all():
                    summary.click()
                page.evaluate("scrollTo(0,0)")
                capture("species-expanded-text200-" + str(width))
                page.locator(".owned-card-tile").first.click()
                expect(page.locator("#edit-group-card")).to_be_visible()
                page.locator("#edit-group-card").click()
                expect(page.locator("#editor[open]")).to_be_visible()
                double_text()
                capture("card-editor-text200-" + str(width))
                page.locator("#collection-intent").select_option("remove_card")
                selected_width = page.locator("#collection-intent").evaluate("""e=>{
                  const ctx=document.createElement('canvas').getContext('2d');ctx.font=getComputedStyle(e).font;
                  return {text:ctx.measureText(e.selectedOptions[0].text).width,available:e.clientWidth-48};
                }""")
                assert selected_width["text"] <= selected_width["available"], selected_width
                page.locator("#collection-card-form button").scroll_into_view_if_needed()
                assert page.locator("#editor").evaluate("e=>e.scrollWidth<=e.clientWidth"), (
                    "Editor inner overflow"
                )
                capture("card-editor-bottom-text200-" + str(width))
                page.keyboard.press("Escape")
                expect(page.locator("#edit-group-card")).to_be_focused()
            passed("wide/320 default, expanded, actual doubled-text and focused editing dialog captures")
            load("/pokedex/250/")
            expect(page.get_by_role("heading", name="Your Cards", exact=True)).to_be_visible()
            expect(page.locator(".owned-card-tile")).to_have_count(0)
            expect(
                page.get_by_role("link", name=__import__("re").compile("Explore Ho-Oh cards"))
            ).to_have_attribute("href", "/card-library/?species=250")
            passed("uncollected catalog gap remains canonical with useful empty Your Cards/catalog link")

            def wrong_generation(route):
                response = route.fetch()
                result = response.json()
                result["generation"] += 1
                route.fulfill(response=response, json=result)

            page.route("**/api/species/2/card-groups/**", wrong_generation, times=1)
            load("/pokedex/2/")
            expect(page.locator("#content")).to_contain_text("Reload")
            expect(page.locator(".owned-card-tile")).to_have_count(0)
            passed("mismatched generation refuses owned tiles and requires visible reload")
            load("/pokedex/2/")
            expect(page.locator(".owned-card-tile")).to_have_count(2)
            for width in (1280, 320):
                page.set_viewport_size(dict(width=width, height=900))
                load("/settings/")
                page.locator("#species-source-tools > summary").click()
                expect(page.locator("#source-correction-species option")).to_have_count(251)
                page.locator("#source-correction-species").select_option("2")
                page.locator("#correct-source-species").click()
                expect(page.locator("#editor-title")).to_contain_text("Ivysaur")
                expect(page.locator("#correct-card")).not_to_have_value("")
                double_text()
                capture("source-correction-text200-" + str(width))
                page.locator("#dex-correction button").scroll_into_view_if_needed()
                capture("source-correction-bottom-text200-" + str(width))
                page.keyboard.press("Escape")
                expect(page.locator("dialog[open]")).to_have_count(0)
            passed(
                "source-specific correction remains in reviewed Settings tools without parity; cancel performs no mutation"
            )
            assert not errors, errors
            assert not parity_requests, parity_requests
            assert persisted_snapshot(root) == before, "Read-only species journeys changed persisted state"
            (output / "species-read-preservation.json").write_text(
                json.dumps(dict(before=before, after=persisted_snapshot(root), equal=True), indent=2) + "\n"
            )
            report.update(
                species_journeys_passed=True,
                species_external_requests_sent=0,
                controlled_species_images=external,
                species_parity_requests=0,
                species_read_preservation=True,
            )
        finally:
            context.tracing.stop(path=str(output / "species-trace.zip"))
            browser.close()
    if preserve_cards:
        from verify_cx05 import exercise as card_exercise

        card_exercise(url, root, output, fixture, report)


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
        "scripts/verify_cx06.py",
    ]
    report["source_hashes"] = {
        name: hashlib.sha256((PROJECT / name).read_bytes()).hexdigest() for name in files
    }
    try:
        with tempfile.TemporaryDirectory(prefix="dex-cx06-browser-") as temporary:
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
