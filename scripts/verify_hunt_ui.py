"""Exercise authenticated hunt controls with intercepted APIs only; no provider calls.

Run: uv run --with playwright python scripts/verify_hunt_ui.py [--output PRIVATE_DIRECTORY]
Desktop and narrow Chromium are browser evidence, not eBay or real-device evidence.
"""

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

from pokemon_hunter.beta.goal_filters import definition as goal_definition

PROJECT = Path(__file__).resolve().parents[1]
ASSETS = PROJECT / "src/pokemon_hunter/beta/static"
GAMES = [
    {"id": "pokemon", "game_key": "pokemon", "name": "Pokémon"},
    {"id": "orbits", "game_key": "orbits", "name": "Synthetic Orbits"},
]
SETS = [
    {"id": "base", "game_id": "pokemon", "name": "Base Set"},
    {"id": "jungle", "game_id": "pokemon", "name": "Jungle"},
    {"id": "neo", "game_id": "pokemon", "name": "Neo"},
    {"id": "orbits-set", "game_id": "orbits", "name": "Synthetic Orbits"},
]


def printing(key, name, set_id, number, rarity="Common", card_type="Pokémon", game="pokemon"):
    return {
        "id": key,
        "name": name,
        "game_id": game,
        "set_id": set_id,
        "set_name": next(s["name"] for s in SETS if s["id"] == set_id),
        "collector_number": str(number or 99),
        "catalog_version": "synthetic-v1",
        "edition": "standard",
        "finish": "non_holo",
        "variant": "standard",
        "unresolved_fields": [],
        "attributes": {
            "name": name,
            "pokemon_dex": number,
            "supertype": card_type,
            "rarity": rarity,
            "dex_eligible": game == "pokemon" and number is not None,
        },
    }


PRINTINGS = [
    printing("p1", "Bulbasaur", "base", 1),
    printing("p25", "Pikachu", "base", 25, "Rare"),
    printing("p25j", "Pikachu", "jungle", 25),
    printing("p152", "Chikorita", "neo", 152),
    printing("trainer", "Trainer example", "base", None, "Rare", "Trainer"),
    printing("orbit", "Nova", "orbits-set", None, "Rare", "Explorer", "orbits"),
]
GOAL_FILTERS = {
    "game_id": "pokemon",
    "set_ids": [],
    "card_type": "Pokémon",
    "rarities": [],
    "pokemon_dex_min": 1,
    "pokemon_dex_max": 151,
    "completion": "species",
}
GOAL = {
    "id": "goal-1",
    "name": "My selected Pokémon",
    "satisfied": 1,
    "total": 151,
    "kind": "filtered",
    "revision": 1,
    "version": "synthetic-v1",
    "unavailable": 149,
    "definition": goal_definition(GOAL_FILTERS, PRINTINGS, GAMES),
    "progress": [
        {"label": "#001 Bulbasaur", "status": "missing", "printing_ids": ["p1"]},
        {"label": "#025 Pikachu", "status": "owned", "printing_ids": ["p25", "p25j"]},
        {"label": "#002 Species 002", "status": "unavailable", "printing_ids": []},
    ],
}
PRIVATE_TITLE = "Private Pikachu <script>window.unsafeTitle = true</script>"
HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="/collection-assets/collection.css">
<script src="/collection-assets/collection.js" defer></script><script src="/collection-assets/parity.js" defer></script>
</head><body data-parity="true"><header><strong class="brand">DEX</strong><nav>
<a href="/hunt/">Hunts</a><a href="/missing/">Missing singles</a><a href="/finds/">Saved finds</a></nav></header>
<main><input type="hidden" name="csrfmiddlewaretoken" value="synthetic-csrf"><div id="status" role="status"></div><div id="content"></div></main>
<dialog id="editor"><div class="dialog-head"><h2 id="editor-title"></h2><button data-close="editor">Close copy details</button></div><div id="editor-body"></div></dialog>
<dialog id="review"><div id="review-body"></div><p id="review-error"></p><button id="confirm">Confirm</button><button id="undo">Undo</button></dialog>
</body></html>"""


class FixtureAPI:
    def __init__(self):
        self.configured = False
        self.environment = "production"
        self.fail_search = False
        self.requests = []
        self.saved = {}
        self.goals = [GOAL]
        self.previews = []
        self.operations = {}
        self.include_unpriced = False
        self.evidence_grade = "raw"

    def route(self, route):
        request = route.request
        parsed = urlsplit(request.url)
        assert parsed.hostname == "dex-ui.test", "Every browser request must stay intercepted"
        path = parsed.path
        if path.startswith("/collection-assets/"):
            asset = ASSETS / path.rsplit("/", 1)[1]
            route.fulfill(
                body=asset.read_text(),
                content_type="text/css" if asset.suffix == ".css" else "text/javascript",
            )
            return
        status = 200
        if path == "/api/collection/":
            body = {
                "goals": self.goals,
                "sets": SETS,
                "copies": [{"printing_id": "p25"}],
                "goal_options": {"games": GAMES},
            }
        elif path == "/api/catalog/":
            body = {"printings": PRINTINGS}
        elif path == "/api/operations/preview/":
            payload = request.post_data_json
            self.previews.append(payload)
            definition = goal_definition(payload["request"]["filters"], PRINTINGS, GAMES)
            body = {
                "id": payload["operation_id"],
                "kind": payload["kind"],
                "state": "preview",
                "plan": {
                    "creates": [
                        {
                            "kind": "goal",
                            "row": {"name": payload["request"]["name"], "definition": json.dumps(definition)},
                        }
                    ],
                    "updates": [],
                    "deletes": [],
                    "checklist": [],
                    "warnings": [],
                    "errors": [],
                },
            }
            self.operations[body["id"]] = body
        elif path.startswith("/api/operations/") and path.endswith("/confirm/"):
            operation = self.operations[path.split("/")[3]]
            operation["state"] = "confirmed"
            row = operation["plan"]["creates"][0]["row"]
            definition = json.loads(row["definition"])
            body = operation
            self.goals.append(
                {
                    **GOAL,
                    "id": "goal-2",
                    "name": row["name"],
                    "definition": definition,
                    "total": len(definition["items"]),
                }
            )
        elif path == "/api/parity/":
            body = {"cards": {"synthetic-pikachu": {"name": "Pikachu", "set": "Synthetic", "number": "25"}}}
        elif path == "/api/hunts/" and request.method == "GET":
            body = {
                "hunts": list(reversed(list(self.saved.values()))),
                "search_status": {
                    "enabled": True,
                    "configured": self.configured,
                    "environment": self.environment if self.configured else None,
                    "note": "eBay search is configured."
                    if self.configured
                    else "eBay credentials are not configured.",
                },
            }
        elif path == "/api/hunts/":
            payload = request.post_data_json
            self.requests.append(payload)
            if self.fail_search:
                body, status = {"error": "eBay search could not complete. Retry explicitly."}, 502
            else:
                batch = f"batch-{len(self.requests)}"
                settings = {k: v for k, v in payload.items() if k != "continuation_batch"}
                settings.setdefault("goal_id", None)
                body = {
                    "batch": batch,
                    "id": "1",
                    "demo": settings["demo"],
                    "settings": settings,
                    "created": "2026-09-30T12:00:00Z",
                    "goal": {
                        "id": settings["goal_id"],
                        "name": next(g["name"] for g in self.goals if g["id"] == settings["goal_id"]),
                        "policy": "species",
                    }
                    if settings["goal_id"]
                    else None,
                    "coverage": {
                        "queries_run": 2,
                        "queries_total": 4,
                        "offset": settings["offset"],
                        "next_offset": 2 if not settings["demo"] and not settings["offset"] else None,
                        "limited": not bool(settings["offset"]),
                        "environment": None if settings["demo"] else self.environment,
                    },
                    "environment": None if settings["demo"] else self.environment,
                    "note": "Synthetic examples; no live offers."
                    if settings["demo"]
                    else "Saved eBay snapshot. Availability may have changed.",
                    "results": [
                        {
                            "id": "opaque-result",
                            "type": "fixed",
                            "label": "Vintage card lot",
                            "count": 2,
                            "confidence": "Seller text only",
                            "delivered": "25",
                            "dex_hits": 1,
                            "exact_hits": 1,
                            "duplicate_ratio": 0.5,
                            "score": 20,
                            "score_coverage": 0.5,
                            "raw_value": None,
                            "pricing": {
                                "status": "conditional",
                                "basis": "ungraded_guide",
                                "reference_total": "50",
                                "delivered": "25",
                                "saving": "25",
                                "discount_percent": "50",
                                "average_per_card": None,
                                "priced_cards": 2,
                                "identified_cards": 2,
                                "lot_count": 2,
                                "coverage": 1,
                                "source_dates": ["2026-09-27"],
                                "note": "Standard-edition guide assumption; edition remains unresolved.",
                            },
                        }
                    ],
                }
                if self.include_unpriced:
                    body["results"].append(
                        {
                            **body["results"][0],
                            "id": "opaque-unpriced",
                            "confidence": "Contents unknown",
                            "pricing": {
                                "status": "unavailable",
                                "basis": "unavailable",
                                "reference_total": None,
                                "discount_percent": None,
                                "note": "No current matching guide evidence.",
                            },
                        }
                    )
                self.saved[f"/api/hunts/{batch}/1/"] = body
        elif "/reveal/" in path:
            saved_path = "/".join(path.split("/")[:5]) + "/"
            body = {
                "title": PRIVATE_TITLE,
                "confidence": "Seller text only",
                "cards": ["synthetic-pikachu"],
                "url": None if self.saved[saved_path]["demo"] else "https://www.ebay.com/itm/123456789012",
                "pricing": {
                    **self.saved[saved_path]["results"][0]["pricing"],
                    "evidence": [
                        {
                            "card_id": "synthetic-pikachu",
                            "grade": self.evidence_grade,
                            "edition": "standard",
                            "guidevalue": "50",
                            "as_of": "2026-09-27",
                            "source_url": "https://www.pricecharting.com/game/pokemon-base-set/pikachu",
                        }
                    ],
                },
            }
        elif path in self.saved:
            body = self.saved[path]
        elif path in ("/hunt/", "/missing/", "/finds/", "/goals/"):
            route.fulfill(body=HTML, content_type="text/html")
            return
        else:
            raise AssertionError(f"Unexpected browser request: {request.method} {path}")
        route.fulfill(status=status, body=json.dumps(body), content_type="application/json")


def run(browser, viewport, output):
    fixture = FixtureAPI()
    context = browser.new_context(viewport=viewport)
    context.route("**/*", fixture.route)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto("https://dex-ui.test/hunt/")
    expect(page.get_by_label("Search source", exact=True)).to_have_value("live")
    expect(page.get_by_role("button", name="Search eBay", exact=True)).to_be_disabled()
    expect(page.locator("#hunt-provider")).to_contain_text("not configured")
    assert not fixture.requests
    page.get_by_label("Search source", exact=True).select_option("sample")
    page.get_by_role("button", name="Find sample cards", exact=True).click()
    expect(page.get_by_role("heading", name="1 sample finds", exact=True)).to_be_visible()
    assert fixture.requests[-1]["demo"] is True
    assert PRIVATE_TITLE not in page.content()
    assert "pricecharting.com" not in page.content()
    page.get_by_role("button", name="Reveal contents", exact=True).click()
    expect(page.locator("#editor-body h3").first).to_have_text(PRIVATE_TITLE)
    expect(page.get_by_role("link", name="$50.00 · View guide")).to_be_visible()
    assert not page.evaluate("Boolean(window.unsafeTitle)")
    expect(page.get_by_role("link", name="Open on eBay")).to_have_count(0)
    page.get_by_role("button", name="Close copy details").click()
    page.get_by_role("link", name="Saved finds", exact=True).click()
    page.locator("[data-saved]").first.click()
    expect(page.get_by_role("button", name="Reveal contents")).to_be_visible()
    assert PRIVATE_TITLE not in page.content()
    assert len(fixture.requests) == 1

    fixture.configured = True
    page.goto("https://dex-ui.test/missing/?goal=goal-1")
    expect(page.get_by_label("Collection goal", exact=True)).to_have_value("goal-1")
    expect(page.get_by_label("Search pool", exact=True)).to_have_value("singles")
    expect(page.get_by_role("button", name="Search eBay", exact=True)).to_be_enabled()
    assert len(fixture.requests) == 1
    page.get_by_label("Focus", exact=True).select_option("rares")
    page.get_by_label("eBay search words (optional)").fill("pokemon vintage pikachu")
    page.get_by_label("Delivered budget (USD)").fill("50")
    page.get_by_role("button", name="Search eBay", exact=True).click()
    expect(page.get_by_role("button", name="Search next eBay batch", exact=True)).to_be_enabled()
    first = fixture.requests[-1]
    assert first == {
        "pool": "singles",
        "focus": "rares",
        "budget": "50",
        "demo": False,
        "offset": 0,
        "goal_id": "goal-1",
        "intent": "missing",
        "query": "pokemon vintage pikachu",
    }
    expect(page.locator("#hunt-results")).to_contain_text("Ungraded guide reference: $50.00")
    expect(page.locator("#hunt-results")).to_contain_text("50% below reference")
    expect(page.locator("#hunt-results")).to_contain_text("Standard-edition guide assumption")
    assert PRIVATE_TITLE not in page.content()
    page.get_by_role("button", name="Reveal contents", exact=True).click()
    expect(page.get_by_role("link", name="Open on eBay")).to_have_attribute("rel", "noopener noreferrer")
    page.get_by_role("button", name="Close copy details").click()
    page.get_by_label("Focus", exact=True).select_option("johto")
    page.get_by_label("eBay search words (optional)").fill("a changed query")
    page.get_by_label("Delivered budget (USD)").fill("1")
    page.get_by_label("Collection goal", exact=True).select_option("")
    page.get_by_role("button", name="Search next eBay batch", exact=True).click()
    expect(page.locator("#hunt-results")).to_contain_text("no further query batches")
    assert fixture.requests[-1] == {**first, "offset": 2, "continuation_batch": "batch-2"}
    expect(page.get_by_label("Focus", exact=True)).to_have_value("johto")
    expect(page.get_by_label("Delivered budget (USD)")).to_have_value("1")
    expect(page.get_by_label("Search source", exact=True)).to_have_value("live")
    assert len(fixture.requests) == 3
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    if output:
        page.screenshot(path=str(output / f"hunt-{viewport['width']}.png"), full_page=True)

    fixture.fail_search = True
    page.get_by_role("button", name="Search eBay", exact=True).click()
    expect(page.locator("#status")).to_contain_text("Retry explicitly")
    expect(page.get_by_role("button", name="Search eBay", exact=True)).to_be_enabled()
    assert len(fixture.requests) == 4
    fixture.environment = "sandbox"
    page.get_by_role("button", name="Refresh eBay status", exact=True).click()
    expect(page.get_by_role("button", name="Search eBay sandbox", exact=True)).to_be_enabled()
    expect(page.locator("#hunt-provider")).to_contain_text("Sandbox results are test listings")
    assert len(fixture.requests) == 4
    assert not errors, errors
    context.close()


def run_goals(browser, viewport, output):
    fixture = FixtureAPI()
    fixture.configured = True
    context = browser.new_context(viewport=viewport)
    context.route("**/*", fixture.route)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto("https://dex-ui.test/goals/")
    page.get_by_label("Goal type", exact=True).select_option("filtered")
    expect(page.locator("#filter-summary")).to_contain_text("251 target species")
    expect(page.locator("#filter-summary")).to_contain_text("1 owned within these filters")
    page.get_by_role("button", name="Original 151", exact=True).click()
    expect(page.locator("#filter-summary")).to_contain_text("151 target species")
    page.locator('#filter-sets input[value="jungle"]').check()
    expect(page.locator("#filter-summary")).to_contain_text("0 owned within these filters")
    page.get_by_label("Rarities", exact=True).select_option(["Common"])
    page.get_by_label("First Pokédex number", exact=True).fill("10")
    page.get_by_label("Last Pokédex number", exact=True).fill("40")
    expect(page.locator("#filter-summary")).to_contain_text("31 target species")
    expect(page.locator("#filter-summary")).to_contain_text("30 unavailable")
    page.get_by_label("Last Pokédex number", exact=True).fill("9")
    expect(page.get_by_role("button", name="Preview tracking goal", exact=True)).to_be_disabled()
    page.get_by_label("Last Pokédex number", exact=True).fill("40")
    expect(page.get_by_role("button", name="Preview tracking goal", exact=True)).to_be_enabled()
    page.get_by_label("Goal name", exact=True).fill("My filtered target")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    if output:
        page.screenshot(path=str(output / f"goals-{viewport['width']}.png"), full_page=True)
    page.get_by_role("button", name="Preview tracking goal", exact=True).click()
    expect(page.locator("#review-body")).to_contain_text("31 species · No inventory added")
    assert fixture.previews[-1]["request"]["filters"] == {
        **GOAL_FILTERS,
        "set_ids": ["jungle"],
        "rarities": ["Common"],
        "pokemon_dex_min": 10,
        "pokemon_dex_max": 40,
    }
    assert len(fixture.goals) == 1
    page.get_by_role("button", name="Confirm", exact=True).click()
    expect(page.locator("#review-body")).to_contain_text("Changes saved")
    assert len(fixture.goals) == 2
    page.evaluate("document.querySelector('#review').close()")
    page.locator("article.card").filter(has_text="My filtered target").get_by_role(
        "link", name="Find missing on eBay"
    ).click()
    expect(page.get_by_label("Collection goal", exact=True)).to_have_value("goal-2")
    expect(page.get_by_label("Search pool", exact=True)).to_have_value("singles")
    assert not fixture.requests
    page.get_by_role("button", name="Search eBay", exact=True).click()
    expect(page.locator("#hunt-results")).to_contain_text("Goal:")
    assert fixture.requests[-1]["goal_id"] == "goal-2"

    page.goto("https://dex-ui.test/goals/")
    page.get_by_label("Goal type", exact=True).select_option("filtered")
    page.get_by_label("Game", exact=True).select_option("orbits")
    expect(page.get_by_label("Count toward completion", exact=True)).to_have_value("printings")
    expect(page.locator("#filter-dex")).to_be_hidden()
    expect(page.locator("#filter-summary")).to_contain_text("1 matching printings")
    page.get_by_label("Game", exact=True).select_option("pokemon")
    page.get_by_label("Limit Pokémon number range", exact=True).uncheck()
    page.get_by_label("Card type", exact=True).select_option("Trainer")
    expect(page.locator("#filter-summary")).to_contain_text("1 matching printings")
    page.get_by_label("Printing completion", exact=True).select_option("exact")
    expect(page.locator("#filter-summary")).to_contain_text("Exact completion requires resolved variants")
    page.get_by_label("Count toward completion", exact=True).select_option("species")
    expect(page.get_by_label("Card type", exact=True)).to_be_disabled()
    expect(page.get_by_label("Card type", exact=True)).to_have_value("all")
    page.get_by_label("Last Pokédex number", exact=True).fill("0")
    page.get_by_label("Goal type", exact=True).select_option("set")
    page.get_by_label("Goal name", exact=True).fill("Classic set")
    assert page.locator("#goal-form").evaluate("form => form.checkValidity()"), (
        "Hidden filtered inputs must not block another goal type"
    )
    assert not errors, errors
    context.close()


def run_pricing(browser, viewport, output):
    fixture = FixtureAPI()
    fixture.configured = True
    fixture.include_unpriced = True
    context = browser.new_context(viewport=viewport)
    context.route("**/*", fixture.route)
    page = context.new_page()
    page.goto("https://dex-ui.test/hunt/")
    expect(page.get_by_label("Search purpose", exact=True)).to_have_value("value")
    page.get_by_role("button", name="Search eBay", exact=True).click()
    expect(page.locator("#hunt-shown")).to_have_text(
        "Showing 2 / 2 saved results · 1 guide comparisons · 1 unavailable."
    )
    assert fixture.requests[-1]["intent"] == "value"
    if output:
        page.screenshot(path=str(output / f"pricing-{viewport['width']}.png"), full_page=True)
    page.get_by_label("Price filter", exact=True).select_option("below")
    expect(page.locator("#hunt-results article.card")).to_have_count(1)
    expect(page.locator("#hunt-shown")).to_contain_text("Showing 1 / 2")
    assert len(fixture.requests) == 1
    page.get_by_label("Price filter", exact=True).select_option("all")
    expect(page.locator("#hunt-results article.card")).to_have_count(2)
    expect(page.locator("#hunt-results")).to_contain_text("Guide comparison unavailable")
    assert "pricecharting.com" not in page.content()

    saved = next(iter(fixture.saved.values()))
    saved["results"][0]["pricing"].update(
        {
            "status": "benchmark",
            "basis": "catalog_average_benchmark",
            "reference_total": "200",
            "saving": "175",
            "discount_percent": "87.5",
            "average_per_card": "10",
            "lot_count": 20,
            "note": "Average benchmark, not an appraisal or expected contents.",
        }
    )
    page.goto("https://dex-ui.test/finds/")
    page.locator("[data-saved]").first.click()
    expect(page.locator("#hunt-results")).to_contain_text("Catalog average benchmark: $200.00")
    expect(page.locator("#hunt-results")).to_contain_text("$10.00 average per card × 20 stated cards")
    expect(page.locator("#hunt-results")).to_contain_text("not an appraisal or expected contents")

    saved["results"][0]["pricing"].update(
        {
            "status": "partial",
            "basis": "identified_subtotal",
            "reference_total": "60",
            "saving": "35",
            "discount_percent": "58.3",
            "priced_cards": 1,
            "identified_cards": 2,
            "lot_count": 10,
            "coverage": 0.1,
            "note": "Subtotal covers identified cards only; unknown contents are not valued.",
        }
    )
    page.goto("https://dex-ui.test/finds/")
    page.locator("[data-saved]").first.click()
    expect(page.locator("#hunt-results")).to_contain_text("Identified-card guide subtotal: $60.00")
    expect(page.locator("#hunt-results")).to_contain_text("1 / 2 identified cards priced · 10 stated cards")
    expect(page.locator("#hunt-results")).to_contain_text("unknown contents are not valued")

    saved["results"][0]["pricing"].update(
        {
            "status": "matched",
            "basis": "graded_guide",
            "reference_total": "100",
            "saving": "75",
            "discount_percent": "75",
            "note": "Matched PSA 10 guide reference.",
        }
    )
    saved["results"][0].update({"type": "auction", "end_time": "2026-10-01T12:00:00Z"})
    fixture.evidence_grade = "10"
    page.goto("https://dex-ui.test/finds/")
    page.locator("[data-saved]").first.click()
    expect(page.locator("#hunt-results")).to_contain_text("Matched graded guide reference: $100.00")
    expect(page.locator("#hunt-results")).to_contain_text("$25.00 current bid + shipping")
    expect(page.locator("#hunt-results")).to_contain_text("Final auction price may rise")
    assert "pricecharting.com" not in page.content()
    page.get_by_role("button", name="Reveal contents", exact=True).first.click()
    expect(page.locator("#editor-body")).to_contain_text("Grade 10 reference")
    expect(page.get_by_role("link", name="$50.00 · View guide")).to_be_visible()
    assert len(fixture.requests) == 1
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    context.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output:
        args.output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for size in ({"width": 1440, "height": 1000}, {"width": 390, "height": 844}):
            run(browser, size, args.output)
            run_goals(browser, size, args.output)
            run_pricing(browser, size, args.output)
        browser.close()
    print(
        "PASS: isolated hunts, pricing/filter/auction labels, filtered goals, confirmed goal-to-search flow, captured intent/query continuation, reveal/reopen, safe failure, two viewports"
    )
