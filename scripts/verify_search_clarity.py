"""Matched synthetic captures using the active beta shell; every request is intercepted.

Run before editing and again afterward with --phase before/after --output DIRECTORY.
No owner state, application server, or provider is used.
"""

import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path

from django.conf import settings
from django.template import Context, Engine
from playwright.sync_api import expect, sync_playwright
from verify_hunt_ui import FixtureAPI

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--phase", choices=["before", "after"], required=True)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
if not settings.configured:
    settings.configure(USE_I18N=False)
html = (
    Engine(dirs=[ROOT / "src/pokemon_hunter/beta/templates"])
    .from_string((ROOT / "src/pokemon_hunter/beta/templates/beta/b2.html").read_text())
    .render(Context(dict(parity=True, scans=True, expansion=True, staging=False, csrf_token="synthetic")))
)
metrics = []
with sync_playwright() as pw:
    browser = pw.chromium.launch()
    for viewport in [dict(width=1280, height=900), dict(width=390, height=844)]:
        for state in ["disabled", "populated", "error", "empty", "history", "reopened"]:
            api = FixtureAPI()
            api.configured = state != "disabled"
            api.include_unpriced = True
            context = browser.new_context(viewport=viewport)

            def route(request):
                if request.request.is_navigation_request():
                    request.fulfill(body=html, content_type="text/html")
                else:
                    api.route(request)

            context.route("**/*", route)
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto("https://dex-ui.test/hunt/")
            expect(page.locator("#hunt-provider")).to_contain_text("configured")
            if state != "disabled":
                api.fail_search = state == "error"
                page.locator("#hunt-search").click()
                if state == "error":
                    expect(page.locator("#status")).to_contain_text("Retry explicitly")
                else:
                    expect(page.locator("[data-reveal-result]")).to_have_count(2)
            if state in ["empty", "history", "reopened"]:
                saved = next(iter(api.saved.values()))
                if state == "empty":
                    saved["results"] = []
                else:
                    for i in range(12):
                        other = deepcopy(saved)
                        other["settings"]["query"] = f"Synthetic vintage collection search {i + 1}"
                        api.saved[f"/api/hunts/history-{i}/1/"] = other
                page.goto("https://dex-ui.test/finds/")
                expect(page.locator("[data-saved]")).to_have_count(1 if state == "empty" else 13)
                if state != "history":
                    page.locator("[data-saved]").first.click()
                    expect(page.locator("#hunt-results h2")).to_be_visible()
            assert not errors, errors
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            measures = page.evaluate("""() => ({height:document.documentElement.scrollHeight,
                resultTop:document.querySelector('#hunt-results h2')?.getBoundingClientRect().top + scrollY || null,
                revealTop:document.querySelector('[data-reveal-result]')?.getBoundingClientRect().top + scrollY || null,
                searchTop:document.querySelector('#hunt-search')?.getBoundingClientRect().top + scrollY || null})""")
            metrics.append(dict(width=viewport["width"], state=state, **measures))
            page.screenshot(
                path=str(args.output / f"{args.phase}-{viewport['width']}-{state}.png"), full_page=True
            )
            if args.phase == "after":
                for summary in page.locator("details > summary:visible").all():
                    was_open = summary.evaluate("e => e.parentElement.open")
                    summary.focus()
                    summary.press("Enter")
                    assert summary.evaluate("e => e.parentElement.open") != was_open
                    summary.press("Enter")
                for button in page.locator("button:visible").all():
                    assert button.bounding_box()["height"] >= 44
                if state in ["populated", "reopened"]:
                    page.locator("[data-reveal-result]").first.focus()
                    page.keyboard.press("Enter")
                    expect(page.locator("#editor")).to_be_visible()
                    page.get_by_role("button", name="Close copy details").click()
                    metrics[-1]["revealFocusReturned"] = page.locator("[data-reveal-result]").first.evaluate(
                        "e => e === document.activeElement"
                    )
                    assert metrics[-1]["revealFocusReturned"], (
                        "Reveal opener must receive focus after closing"
                    )
                page.evaluate("document.documentElement.style.fontSize='32px'")
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), state
                page.screenshot(
                    path=str(args.output / f"{args.phase}-{viewport['width']}-{state}-text200.png"),
                    full_page=True,
                )
            context.close()
    browser.close()
(args.output / f"{args.phase}-search-metrics.json").write_text(json.dumps(metrics, indent=2))
paths = [
    ROOT / "src/pokemon_hunter/beta/static" / name
    for name in ["parity.js", "collection.js", "collection.css"]
]
(args.output / f"{args.phase}-source-hashes.json").write_text(
    json.dumps(
        {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}, indent=2
    )
)
print(json.dumps(metrics, indent=2))
