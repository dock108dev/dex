"""Matched current-source synthetic previews; every browser request is intercepted.

uv run --no-sync --with playwright python scripts/verify_collecting_clarity.py --phase before --output DIR
Repeat --phase after with the same output. No server, owner data or provider calls.
"""

import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.template import Context, Engine
from playwright.sync_api import expect, sync_playwright
from verify_hunt_ui import PRINTINGS, FixtureAPI

from pokemon_hunter.beta.canonical_species import registry

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "src/pokemon_hunter/beta"
FILES = [
    "templates/beta/b2.html",
    "templates/beta/packs.html",
    "static/collection.css",
    "static/collection.js",
    "static/parity.js",
    "static/pokedex.js",
]
OPTIONAL_FILES = ["templates/beta/header.html", "static/glass.css", "static/public.css"]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--phase", choices=["before", "after"], required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
if not settings.configured:
    settings.configure(USE_I18N=False)
if args.phase == "before" and not (args.output / "before-source-hashes.json").exists():
    for name in FILES + [name for name in OPTIONAL_FILES if (BASE / name).is_file()]:
        dest = args.output / "before-source" / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            dest.write_bytes((BASE / name).read_bytes())


SOURCE = args.output / "before-source" if args.phase == "before" else BASE
engine = Engine(dirs=[SOURCE / "templates"])
FILES += [name for name in OPTIONAL_FILES if (SOURCE / name).is_file()]


def template(name, context):
    return engine.from_string((SOURCE / "templates/beta" / name).read_text()).render(Context(context))


shell = template(
    "b2.html", dict(parity=True, scans=True, expansion=True, staging=False, csrf_token="synthetic")
)
items = [
    dict(label=f"#{n:03} {registry()[n]['name']}", pokemon_dex=n, printing_ids=[], status="missing")
    for n in (123, 134, 196)
]
filters = dict(stock="all", age="all", max_price="", currency="", sort="checked")
obs = dict(
    id="synthetic-observation",
    checked_at="2026-10-06T12:00:00Z",
    stock="out-of-stock",
    price="USD 27.99",
    shipping="Unknown",
    fresh=False,
    age="older",
    sources=["synthetic-source"],
    note="Synthetic historical observation; current availability unverified.",
)
decision = dict(
    source=True,
    offer=False,
    recommendation_eligible=False,
    purchase_ready=False,
    synthetic=True,
    behavior_eligible=False,
    recommendation_reasons=["Availability is not observed in stock"],
    source_reasons=["Validated URL for manual review"],
    offer_reasons=["Seller identity unresolved"],
    purchase_reasons=["Verified backend availability unavailable"],
)
product = dict(
    id="synthetic-product",
    name="Synthetic 151 Booster Bundle",
    sku="Synthetic SKU",
    version="Synthetic English version",
    market="US",
    language="en",
    verified=True,
    contents="complete",
    total_packs=6,
    quantity=6,
    possible_count=3,
    guaranteed_count=0,
    distinct_target_count=3,
    guaranteed_cards_known=False,
    packs=[dict(expansion_id="synthetic-expansion", quantity=6)],
    guaranteed=[],
    included_cards=[],
    offers=[
        dict(
            id="synthetic-offer",
            retailer="Synthetic retailer",
            seller=None,
            seller_kind="unknown",
            url="https://example.test/product",
            eligibility=decision,
            representative=obs,
            observations=[obs],
            price_comparable=False,
        )
    ],
    offer_total=1,
)
pack_context = dict(
    lookup=True,
    supported=True,
    research_enabled=True,
    lookup_goals=[],
    lookup_request=dict(goal="", targets="123,134,196", scope="all", printing=""),
    goal=dict(
        id="synthetic-goal",
        version="synthetic-version",
        name="Selected Pokémon",
        definition=dict(
            lineage=dict(number=1), eligibility_policy=dict(id="synthetic-policy"), catalog_references=[]
        ),
    ),
    progress=dict(missing=3, total=3, satisfied=0, unavailable=0),
    missing=items,
    expansions=[
        dict(
            expansion=dict(
                id="synthetic-expansion", name="Synthetic 151", language="en", expected_printings=207
            ),
            count=3,
            species=[dict(label=i["label"], dex=i["pokemon_dex"], printings=[]) for i in items],
            uncertain=[],
            products=[product],
        )
    ],
    options=[dict(expansion=dict(id="synthetic-expansion", name="Synthetic 151"))],
    unmapped_printings=0,
    filters=filters,
    offer_filters=filters,
    species="",
    expansion="",
    limitations=[],
    sources=[],
    coverage=[],
    csrf_token="synthetic",
)


def parity_fixture():
    cards = {}
    for p in PRINTINGS:
        if p["attributes"]["supertype"] != "Pokémon":
            continue
        cards[p["id"]] = dict(
            p["attributes"],
            card_id=p["id"],
            printing_id=p["id"],
            set=p["set_name"],
            number=p["collector_number"],
            copy_ids=["synthetic-copy"] if p["id"] == "p25" else [],
            era="Classic",
            variant="standard",
            owned=p["id"] == "p25",
        )
    species = {
        str(n): dict(
            dex_number=n,
            name=registry()[n]["name"],
            generation=1 if n <= 151 else 2,
            collection_owned=n == 25,
            dex_owned=n == 25,
            declared_cards=[],
            eligible_cards=[],
        )
        for n in range(1, 252)
    }
    return dict(
        cards=cards,
        catalog=PRINTINGS,
        pokedex=species,
        owner_collection=dict(active=True, total=1, kanto=1, johto=0),
        totals=dict(total=1, kanto=1, johto=0, physical_copies=1, exact_cards=1, unavailable_species=247),
    )


metrics = []
with sync_playwright() as pw:
    browser = pw.chromium.launch()
    for width, height in [(1280, 900), (390, 844)]:
        for state in ["pokedex", "empty", "error", "loading", "packs", "saved", "no-products", "unverified"]:
            api = FixtureAPI()
            ctx = deepcopy(pack_context)
            if state == "saved":
                ctx.update(
                    saved=dict(
                        id="synthetic-save", name="My saved pack lookup", created_at="2026-10-05T10:00:00Z"
                    ),
                    reference_gaps=[],
                )
            if state == "unverified":
                uncertain = ctx["expansions"][0]["products"][0]
                uncertain.update(
                    verified=False,
                    contents="unknown",
                    quantity=None,
                    total_packs=None,
                    possible_count=0,
                    guaranteed_count=0,
                    distinct_target_count=0,
                )
            if state == "no-products":
                ctx["expansions"] = []
            html = (
                template("packs.html", ctx)
                if state in {"packs", "saved", "no-products", "unverified"}
                else shell
            )
            context = browser.new_context(viewport=dict(width=width, height=height))

            def intercept(route):
                request = route.request
                path = urlsplit(request.url).path
                if request.is_navigation_request():
                    route.fulfill(body=html, content_type="text/html")
                elif state == "loading" and path.endswith(".js"):
                    # Capture the initial loading markup before scripts execute.
                    route.fulfill(body="", content_type="text/javascript")
                elif path.startswith("/collection-assets/"):
                    asset = SOURCE / "static" / path.rsplit("/", 1)[1]
                    route.fulfill(
                        body=asset.read_text(),
                        content_type="text/css" if asset.suffix == ".css" else "text/javascript",
                    )
                elif path == "/api/collection/":
                    if state == "error":
                        route.fulfill(
                            status=503, json={"error": "Collection could not load. Reload to retry."}
                        )
                    else:
                        route.fulfill(
                            json=dict(
                                goals=[],
                                sets=[],
                                copies=[],
                                binders=[],
                                operations=[],
                                goal_options=dict(games=[]),
                                current_collection_source=None,
                            )
                        )
                elif path == "/api/parity/":
                    route.fulfill(json=parity_fixture())
                else:
                    assert urlsplit(request.url).hostname == "dex-ui.test", "Unexpected external request"
                    api.route(route)

            context.route("**/*", intercept)
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(
                "https://dex-ui.test/lookup/"
                if state in {"packs", "saved", "no-products", "unverified"}
                else "https://dex-ui.test/pokedex/",
                wait_until="domcontentloaded",
            )
            if state in {"pokedex", "empty"}:
                expect(page.locator("[data-dex-species]")).to_have_count(251)
                if state == "empty":
                    page.locator("#dex-search").fill("No matching species")
                    expect(page.locator("#species-grid")).to_contain_text("No species match")
            elif state == "error":
                expect(page.locator("#content")).to_contain_text("Collection unavailable")
            elif state == "loading":
                expect(page.locator("#content")).to_contain_text("Loading your collection")
            elif state in {"packs", "saved", "unverified"}:
                expect(page.get_by_role("heading", name=product["name"], exact=True)).to_be_visible()
            else:
                expect(
                    page.get_by_role("heading", name="No compatible reviewed booster membership")
                ).to_be_visible()
            assert not errors, errors
            overflow = page.evaluate("document.documentElement.scrollWidth > innerWidth")
            top = page.evaluate("""() => {const y=e=>e?Math.round(e.getBoundingClientRect().top+scrollY):null;
              return {height:document.documentElement.scrollHeight, speciesTop:y(document.querySelector('[data-dex-species]')),
              productTop:y([...document.querySelectorAll('h4')].find(e=>e.textContent==='Synthetic 151 Booster Bundle')),
              saveTop:y(document.querySelector('form[action="/lookup/save/"] button')), horizontalOverflow:document.documentElement.scrollWidth>innerWidth};} """)
            metrics.append(dict(width=width, state=state, **top))
            page.screenshot(path=str(args.output / f"{args.phase}-{width}-{state}.png"), full_page=True)
            page.screenshot(path=str(args.output / f"{args.phase}-{width}-{state}-viewport.png"))
            if args.phase == "after":
                assert not overflow, (state, width)
                if state == "pokedex":
                    lookup_button = page.locator("#dex-lookup-selection")
                    expect(lookup_button).to_be_disabled()
                    first = page.locator("[data-select-species]").first
                    first.focus()
                    page.keyboard.press("Space")
                    expect(lookup_button).to_be_enabled()
                    page.locator("[data-dex-species]").first.focus()
                    page.keyboard.press("Enter")
                    expect(page.locator("#editor")).to_be_visible()
                    page.keyboard.press("Escape")
                    expect(page.locator("[data-dex-species]").first).to_be_focused()
                for summary in page.locator("details > summary:visible").all():
                    opened = summary.evaluate("e=>e.parentElement.open")
                    summary.focus()
                    summary.press("Enter")
                    assert summary.evaluate("e=>e.parentElement.open") != opened
                    summary.press("Enter")
                for button in page.locator("button:visible").all():
                    assert button.bounding_box()["height"] >= 44
                if width == 1280 and state in {"pokedex", "packs"}:
                    page.add_style_tag(content="body { zoom: 2; }")
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
                        "200% zoom overflow"
                    )
                    page.screenshot(path=str(args.output / f"after-zoom-{state}.png"), full_page=True)
                    page.screenshot(path=str(args.output / f"after-zoom-{state}-viewport.png"))
            context.close()
    browser.close()
(args.output / f"{args.phase}-metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
(args.output / f"{args.phase}-source-hashes.json").write_text(
    json.dumps({name: hashlib.sha256((SOURCE / name).read_bytes()).hexdigest() for name in FILES}, indent=2)
    + "\n"
)
print(json.dumps(metrics, indent=2))
