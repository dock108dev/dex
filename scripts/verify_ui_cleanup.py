"""Synthetic presentation preview. Intercepts every browser request; no app or owner data.

Run with: uv run --with playwright python scripts/verify_ui_cleanup.py --output DIR --phase before
Repeat with --phase after to capture matched states from the edited source.
"""

import argparse
import io
import json
import subprocess
from pathlib import Path

from django.conf import settings
from django.template import Context, Engine
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--phase", choices=["before", "after"], required=True)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
settings.configure(USE_I18N=False)
base = ROOT / "src/pokemon_hunter/beta"
printing = dict(
    id="p1",
    name="Pikachu",
    set_name="Base Set",
    collector_number="58",
    set_id="s1",
    unresolved_fields=["edition"],
    edition=None,
)
copies = [
    dict(
        id=f"c{i}",
        printing_id="p1",
        attributes='{"name":"Pikachu"}',
        collector_number="58",
        condition=None,
        first_edition_selected=False,
        binder_id=None,
        notes="Synthetic preview card" if i == 0 else "",
        purchase_amount=None,
        purchase_currency=None,
        grading_company=None,
        grade=None,
    )
    for i in range(3)
]
collection = dict(
    copies=copies,
    binders=[],
    sets=[dict(id="s1", name="Base Set")],
    printing_details={"p1": printing},
    vintage_251=dict(total=1),
    operations=[],
)
scenario = dict(priced=0, owned=3, subtotal=None, total=None, estimated=0)
parity = dict(
    totals=dict(kanto=1, johto=0, total=1, physical_copies=3, exact_cards=1, unavailable_species=0),
    cards={
        f"p{i}": dict(
            printing_id=f"p{i}",
            card_id=f"p{i}",
            owned=i == 1,
            supertype="Pokémon",
            rarity=rarity,
            name=name,
            number=str(i),
            set="Base Set",
            copy_ids=["c0", "c1", "c2"] if i == 1 else [],
            dex_eligible=True,
        )
        for i, name, rarity in [
            (1, "Pikachu", "Common"),
            (2, "Bulbasaur", "Uncommon"),
            (3, "Charizard", "Rare"),
        ]
    },
    catalog=[dict(printing, id=f"p{i}") for i in range(1, 4)],
    valuation=dict(
        confirmed={"raw": scenario},
        conditional={g: scenario for g in ["raw", "7", "8", "9", "10"]},
        source_dates=[],
        max_age_days=30,
        purchase_subtotals={},
        purchase_known=0,
    ),
)
job = dict(
    id="00000000-0000-4000-8000-000000000001",
    state="needs-confirmation",
    mode="codex_cli",
    attempts=1,
    latency=1.5,
    created=1790596800,
    operation_id=None,
    photos=["synthetic-photo"],
    error="",
    result=dict(
        candidates=[printing],
        clues=dict(
            name="Pikachu",
            set_name="Base Set",
            number="58",
            language=None,
            edition=None,
            finish=None,
            variant=None,
        ),
        usage={"input_tokens": 20},
    ),
)


def source(path):
    if args.phase == "before":
        return subprocess.check_output(["git", "show", "HEAD:" + str(path.relative_to(ROOT))], cwd=ROOT)
    return path.read_bytes()


if args.phase == "before":
    template_paths = (
        subprocess.check_output(
            ["git", "ls-tree", "-r", "--name-only", "HEAD", "src/pokemon_hunter/beta/templates"], cwd=ROOT
        )
        .decode()
        .splitlines()
    )
    templates = {
        str((ROOT / path).relative_to(base / "templates")): source(ROOT / path).decode()
        for path in template_paths
        if path.endswith(".html")
    }
    engine = Engine(loaders=[("django.template.loaders.locmem.Loader", templates)])
else:
    engine = Engine(dirs=[base / "templates"])


photo = Image.new("RGB", (400, 560), "#f4d96d")
ImageDraw.Draw(photo).text((40, 220), "SYNTHETIC CARD\nPreview only", fill="black")
photo_bytes = io.BytesIO()
photo.save(photo_bytes, format="JPEG")
metrics = []
with sync_playwright() as pw:
    browser = pw.chromium.launch()
    for viewport in [dict(width=1280, height=900), dict(width=390, height=844)]:
        for state in [
            "overview",
            "cards",
            "cards-empty",
            "collection",
            "empty",
            "scan",
            "ready",
            "failed",
            "saved",
            "processing",
            "load-error",
        ]:
            context = browser.new_context(viewport=viewport)
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))

            def route(request):
                path = __import__("urllib.parse", fromlist=["urlsplit"]).urlsplit(request.request.url).path
                if path.startswith("/collection-assets/"):
                    asset = base / "static" / path.rsplit("/", 1)[-1]
                    return request.fulfill(
                        body=source(asset),
                        content_type="text/css" if asset.suffix == ".css" else "text/javascript",
                    )
                if path.startswith("/scan-photos/"):
                    return request.fulfill(body=photo_bytes.getvalue(), content_type="image/jpeg")
                if path.startswith("/api/"):
                    if path == "/api/collection/" and state == "load-error":
                        return request.fulfill(
                            status=503, json={"error": "Collection unavailable. Reload to try again."}
                        )
                    if path == "/api/collection/":
                        value = {**collection, "copies": [] if state == "empty" else copies}
                    elif path == "/api/parity/":
                        value = parity
                    elif path == "/api/catalog/":
                        value = {"printings": [printing]}
                    elif path == "/api/scans/":
                        value = {"jobs": [] if state == "scan" else [job], "mode": "codex_cli"}
                    elif path.startswith("/api/scans/"):
                        value = {
                            **job,
                            "state": {
                                "failed": "failed",
                                "saved": "confirmed",
                                "processing": "processing",
                            }.get(state, job["state"]),
                            "operation_id": "synthetic-operation" if state == "saved" else None,
                            "operation": {"state": "confirmed"},
                            "error": "Recognition failed. Retry or choose a card manually."
                            if state == "failed"
                            else "",
                        }
                    else:
                        raise AssertionError(path)
                    return request.fulfill(json=value)
                template = (
                    "scans.html" if state in {"scan", "ready", "failed", "saved", "processing"} else "b2.html"
                )
                html = engine.from_string(source(base / "templates/beta" / template).decode()).render(
                    Context(
                        dict(
                            parity=True,
                            scans=True,
                            expansion=True,
                            staging=False,
                            mode="codex_cli",
                            csrf_token="synthetic",
                        )
                    )
                )
                request.fulfill(body=html, content_type="text/html")

            page.route("**/*", route)
            path = (
                "/overview/"
                if state == "overview"
                else "/cards/"
                if state in {"cards", "cards-empty"}
                else "/scan/"
                if state in {"scan", "ready", "failed", "saved", "processing"}
                else "/collection/"
            )
            if state in {"ready", "failed", "saved", "processing"}:
                path += "#" + job["id"]
            page.goto("http://localhost:8769" + path)
            page.wait_for_load_state("networkidle")
            if state in {"ready", "failed"}:
                page.locator("#add-copy").wait_for()
            elif state == "saved":
                page.locator('[data-action="undo"]').wait_for()
            elif state == "load-error":
                page.get_by_role("heading", name="Collection unavailable").wait_for()
            elif state == "processing":
                page.locator('[data-action="cancel"]').wait_for()
            elif state in {"collection", "empty"}:
                page.locator("#copies").wait_for()
            elif state in {"cards", "cards-empty"}:
                page.locator("#parity-cards").wait_for()
                if state == "cards-empty":
                    page.locator("#cards-query").fill("No synthetic match")
                    assert "No matching printings" in page.locator("#parity-cards").inner_text()
                assert page.locator("#cards-prev").is_disabled()
                assert page.locator("#cards-next").is_disabled()
            elif state == "overview":
                page.get_by_role("heading", name="Overview", exact=True).wait_for()
            assert not errors, errors
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), state
            measures = page.evaluate(
                """() => ({height:document.documentElement.scrollHeight, mainTop:document.querySelector('main').getBoundingClientRect().top, cardTop:document.querySelector('#parity-cards .card')?.getBoundingClientRect().top ?? null, huntLinkTop:document.querySelector('main a[href="/hunt/"]')?.getBoundingClientRect().top ?? null, actionTop:(document.querySelector('#add-copy')||document.querySelector('#upload button:last-child')||document.querySelector('#show-add'))?.getBoundingClientRect().top ?? null})"""
            )
            metrics.append(dict(phase=args.phase, width=viewport["width"], state=state, **measures))
            page.screenshot(
                path=str(args.output / f"{args.phase}-{viewport['width']}-{state}.png"), full_page=True
            )
            if args.phase == "after":
                if state in {"ready", "failed"}:
                    assert page.locator("#add-copy").is_disabled()
                    page.locator("#reviewed").check()
                    assert page.locator("#add-copy").is_enabled()
                    page.locator("#selection").select_option("p1")
                    assert page.locator("#add-copy").is_disabled()
                    assert "Check the review box" in page.locator("#confirm-help").inner_text()
                    page.locator('[data-action="cancel"]').focus()
                    assert page.locator('[data-action="cancel"]').evaluate("e=>e===document.activeElement")
                for summary in page.locator("details > summary").all():
                    was_open = summary.evaluate("e => e.parentElement.open")
                    summary.focus()
                    summary.press("Enter")
                    assert summary.evaluate("e => e.parentElement.open") != was_open
                    summary.press("Enter")
                buttons = page.locator("button:visible").all()
                assert all(b.bounding_box()["height"] >= 44 for b in buttons)
                page.evaluate("document.documentElement.style.fontSize='32px'")
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
                    f"200% text: {state}"
                )
                if state in {"overview", "cards"}:
                    page.screenshot(
                        path=str(args.output / f"{args.phase}-{viewport['width']}-{state}-text200.png"),
                        full_page=True,
                    )
            context.close()
    browser.close()
(args.output / f"{args.phase}-metrics.json").write_text(json.dumps(metrics, indent=2))
print(json.dumps(metrics, indent=2))
