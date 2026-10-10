"""Exercise guest and member UI against a generated disposable local root.

The server must be scripts/serve_e4a.py on an unused alternate loopback port.
No owner root, credentials, provider call or external browser request is permitted.
Run with uv run --no-sync --with playwright python scripts/verify_public_ui.py
  --root PRIVATE_SYNTHETIC_ROOT --base-url http://127.0.0.1:PORT --output OUTPUT
"""

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

PROJECT = Path(__file__).resolve().parents[1]


def source_hashes():
    return {
        str(path.relative_to(PROJECT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((PROJECT / "src/pokemon_hunter/beta").rglob("*"))
        if path.is_file() and path.suffix in {".py", ".html", ".css", ".js"}
    }


def preserved(root):
    tables = (
        "owned_copies",
        "collection_goals",
        "saved_hunts",
        "scan_jobs",
        "scan_photos",
        "binders",
        "sealed_observations",
        "saved_pack_research",
        "collection_operations",
        "private_archives",
        "collection_sources",
    )
    with sqlite3.connect(root / "inventory.db") as db:
        available = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        snapshots = {}
        for table in tables:
            if table in available:
                snapshots[table] = sorted(db.execute(f'SELECT * FROM "{table}"').fetchall(), key=repr)
    photos = {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    }
    return snapshots, photos


def run(root, base, output):
    if not (root / "SYNTHETIC_ONLY").is_file():
        raise ValueError("Generated disposable synthetic root required")
    origin = urlsplit(base)
    if origin.hostname != "127.0.0.1" or origin.port == 8011:
        raise ValueError("Unused alternate loopback port required")
    output.mkdir(parents=True, exist_ok=True)
    credentials = json.loads((root / "credentials.json").read_text())
    candidate = source_hashes()
    before, photos_before = preserved(root)
    metrics = []
    denied = []
    errors = []
    external = []

    def capture(page, width, state, full=False):
        overflow = page.evaluate("document.documentElement.scrollWidth > innerWidth")
        layout = page.evaluate("""() => {
            const records = [...document.querySelectorAll(
                '.public-species-row, .public-card, .product-card')];
            const boxes = records.map(item => item.getBoundingClientRect());
            return {
                working_content_top: boxes.length ? Math.round(boxes[0].top + scrollY) : null,
                fully_visible_records: boxes.filter(box => box.top >= 0 && box.bottom <= innerHeight).length
            };
        }""")
        metrics.append(
            dict(
                width=width,
                state=state,
                horizontal_overflow=overflow,
                document_height=page.evaluate("document.documentElement.scrollHeight"),
                **layout,
            )
        )
        page.screenshot(path=str(output / f"{width}-{state}.png"), full_page=full)
        assert not overflow, (width, state, "Horizontal overflow")
        assert not errors, errors

    def details_keyboard(page):
        for summary in page.locator("details > summary:visible").all():
            opened = summary.evaluate("e => e.parentElement.open")
            summary.focus()
            summary.press("Enter")
            assert summary.evaluate("e => e.parentElement.open") != opened
            summary.press("Enter")

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for width, height in ((1280, 900), (390, 844)):
            context = browser.new_context(viewport=dict(width=width, height=height))

            def boundary(route):
                parsed = urlsplit(route.request.url)
                if parsed.scheme in {"http", "https"} and parsed.netloc != origin.netloc:
                    external.append(route.request.url)
                    route.abort()
                else:
                    route.continue_()

            context.route("**/*", boundary)
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            response = page.goto(base + "/")
            assert response.status == 200
            expect(page.locator(".public-species-row")).to_have_count(251)
            expect(page.get_by_role("link", name="Track my collection", exact=True)).to_be_visible()
            expect(page.locator("header")).not_to_contain_text("My collection")
            capture(page, width, "guest-pokedex")
            gap = page.locator(".public-species-row").evaluate_all("""rows => {
                const row = rows.find(row => row.textContent.includes('No indexed cards'));
                return row ? row.querySelector('.public-species-link').getAttribute('href') : null;
            }""")
            if gap:
                page.goto(base + gap)
                expect(page.get_by_role("heading", name="No cards indexed yet", exact=True)).to_be_visible()
                capture(page, width, "guest-catalog-gap")
                page.goto(base + "/pokedex/")
            page.locator(".public-species-link strong").first.evaluate(
                "element => element.textContent = 'Synthetic long Pokémon name for a narrow-layout check'"
            )
            capture(page, width, "guest-pokedex-long")
            page.goto(base + "/pokedex/")
            page.locator("#browse-query").fill("#123")
            page.locator("#browse-query").press("Enter")
            expect(page.locator(".public-species-row")).to_have_count(1)
            expect(page.locator(".public-species-link")).to_contain_text("Scyther")
            capture(page, width, "guest-filtered", full=True)
            page.locator(".public-species-link").focus()
            page.keyboard.press("Enter")
            expect(page.get_by_role("heading", name="#123 Scyther", exact=True)).to_be_visible()
            details_keyboard(page)
            capture(page, width, "guest-species", full=True)
            page.locator(".public-card h2").first.evaluate(
                "element => element.textContent = 'Synthetic long card title with an extended printing description'"
            )
            capture(page, width, "guest-species-long")
            page.get_by_role("link", name="Look up packs", exact=True).click()
            expect(page.get_by_role("heading", name="Pack lookup", exact=True)).to_be_visible()
            expect(page.locator("#lookup-goal")).to_have_count(0)
            expect(page.locator("#lookup-scope option[value='missing']")).to_have_count(0)
            expect(page.locator("form[action='/lookup/save/']")).to_have_count(0)
            expect(page.locator("main")).not_to_contain_text("Current account resolved ownership")
            capture(page, width, "guest-pack", full=True)
            page.locator("#lookup-targets").fill("123,134,230")
            page.locator("#lookup-targets").press("Enter")
            expect(page.locator(".product-card")).not_to_have_count(0)
            page.locator(".offer-filter-panel > summary").press("Enter")
            page.locator("#stock").select_option("out-of-stock")
            page.get_by_role("button", name="Apply filters", exact=True).click()
            assert "goal=" not in page.url
            expect(page.locator("main")).not_to_contain_text("Sign in to use saved goals or collection tools")
            capture(page, width, "guest-pack-filtered", full=True)
            if not page.locator(".offer-filter-panel").evaluate("e => e.open"):
                page.locator(".offer-filter-panel > summary").press("Enter")
            page.get_by_role("link", name="Reset offer filters", exact=True).click()
            assert "goal=" not in page.url
            expect(page.locator(".product-card")).not_to_have_count(0)
            details_keyboard(page)
            if width == 1280:
                page.add_style_tag(content="body { zoom: 2; }")
                capture(page, width, "guest-pack-zoom200")
                page.goto(base + "/pokedex/")
                page.add_style_tag(content="body { zoom: 2; }")
                capture(page, width, "guest-pokedex-zoom200")
            response = page.goto(base + "/lookup/?targets=123&scope=missing")
            assert response.status == 400
            expect(page.get_by_role("alert")).to_contain_text("Sign in")
            capture(page, width, "guest-scope-error", full=True)
            response = page.goto(base + "/lookup/?targets=not-a-number")
            assert response.status == 400
            expect(page.get_by_role("alert")).to_be_visible()
            capture(page, width, "guest-input-error", full=True)
            response = page.goto(base + "/pokedex/?q=NoMatchingPokemon")
            assert response.status == 200
            expect(page.get_by_role("heading", name="No matching Pokémon", exact=True)).to_be_visible()
            capture(page, width, "guest-empty", full=True)
            page.goto(base + "/hunt/")
            expect(page.get_by_role("heading", name="eBay research", exact=True)).to_be_visible()
            capture(page, width, "guest-ebay-guide", full=True)
            for path in (
                "/api/collection/",
                "/api/catalog/",
                "/api/parity/",
                "/api/export/",
                "/api/goals/",
                "/api/hunts/",
                "/goals/",
                "/packs/saved/",
                "/settings/",
                "/collection/",
            ):
                denied_response = context.request.get(base + path, max_redirects=0)
                denied.append(dict(width=width, path=path, status=denied_response.status))
                assert denied_response.status == 302, (path, denied_response.status)
                assert denied_response.headers["location"].startswith("/login/?next=")
            page.goto(base + "/goals/")
            expect(page.get_by_role("heading", name="Sign in to your collection", exact=True)).to_be_visible()
            assert "next=%2Fgoals%2F" in page.url or "next=/goals/" in page.url
            capture(page, width, "sign-in", full=True)
            page.get_by_label("Username").fill("synthetic-member")
            page.locator("#id_password").fill(credentials["synthetic-member"])
            page.get_by_role("button", name="Sign in", exact=True).click()
            expect(page.get_by_role("heading", name="Goals", exact=True)).to_be_visible()
            expect(page.locator("main")).to_contain_text("Synthetic all-era Original 151")
            capture(page, width, "member-goals")
            page.locator(".app-tools > summary").press("Enter")
            page.get_by_role("link", name="Physical copies", exact=True).click()
            expect(page.get_by_role("heading", name="Your collection", exact=True)).to_be_visible()
            expect(page.get_by_role("button", name="Add a physical copy", exact=True)).to_be_visible()
            expect(page.locator("#copies > .card")).to_have_count(3)
            edit_button = page.locator("[data-edit]").first
            edit_button.focus()
            page.keyboard.press("Enter")
            expect(page.locator("#editor")).to_be_visible()
            page.keyboard.press("Escape")
            expect(edit_button).to_be_focused()
            capture(page, width, "member-physical-copies")
            page.goto(base + "/pokedex/123/")
            expect(page.get_by_role("heading", name="#123 Scyther", exact=True)).to_be_visible()
            copy_link = page.get_by_role("link", name="Add or edit a copy", exact=True).first
            expect(copy_link).to_have_attribute("href", "/collection/")
            expect(page.locator("main")).not_to_contain_text("Sign in to add a copy")
            capture(page, width, "member-public-species", full=True)
            data = context.request.get(base + "/api/collection/").json()
            assert len(data["copies"]) == 3 and len(data["goals"]) == 3
            page.goto(base + "/pokedex/")
            expect(page.locator("[data-dex-species]")).to_have_count(251)
            capture(page, width, "member-pokedex")
            first_select = page.locator("[data-select-species]").first
            first_select.focus()
            page.keyboard.press("Space")
            expect(page.locator("#dex-lookup-selection")).to_be_enabled()
            first_species = page.locator("[data-dex-species]").first
            first_species.focus()
            page.keyboard.press("Enter")
            expect(page.locator("#editor")).to_be_visible()
            page.keyboard.press("Escape")
            expect(first_species).to_be_focused()
            page.goto(base + "/settings/")
            expect(page.get_by_role("heading", name="Settings & data", exact=True)).to_be_visible()
            capture(page, width, "member-settings")
            page.goto(base + "/shopping/")
            expect(page.get_by_role("heading", name="Lot calculator", exact=True)).to_be_visible()
            expect(page.locator("#cards .card").first).to_be_visible()
            capture(page, width, "member-shopping-empty")
            card = page.locator("#cards .card").first
            card.get_by_label("Quantity to add").fill("2")
            card.get_by_role("button", name="Add card", exact=True).click()
            row = page.locator("#selections .selection").first
            expect(row.get_by_label("In this lot", exact=True)).to_have_value("2")
            expect(row.locator(".value-cell")).to_have_count(4)
            row.get_by_label("Wanted quantity", exact=True).fill("3")
            with page.expect_response(lambda response: "/api/shopping/wants/" in response.url) as lock_write:
                row.get_by_label("Lock wanted card", exact=True).check()
            assert lock_write.value.status == 200
            page.locator("#lot-price").fill("12")
            with page.expect_response(
                lambda response: "/api/shopping/lot-compare/" in response.url
            ) as compared:
                page.get_by_role("button", name="Total and compare", exact=True).click()
            payload = compared.value.json()
            assert compared.value.status == 200 and payload["schema"] == "dex-lot-v2"
            assert set(payload["scenarios"]) == {"raw", "8", "9", "10"}
            assert all(
                scenario["result"]["coverage"]["selected_units"] == 2
                for scenario in payload["scenarios"].values()
            )
            expect(page.locator("#summary .scenario")).to_have_count(4)
            capture(page, width, "member-shopping-compared")
            if width == 1280:
                page.add_style_tag(content="body { zoom: 2; }")
                capture(page, width, "member-shopping-zoom200")
                page.add_style_tag(content="body { zoom: 1; }")
            # A semantically invalid URL reaches the server; HTML validity alone cannot cover this path.
            page.get_by_text("Listing, planned bid and delivery costs", exact=True).click()
            page.locator("#listing-url").fill("javascript:invalid")
            with page.expect_response(
                lambda response: "/api/shopping/lot-compare/" in response.url
            ) as invalid:
                page.get_by_role("button", name="Total and compare", exact=True).click()
            assert invalid.value.status == 400
            expect(page.locator("#status")).to_be_focused()
            expect(row.get_by_label("In this lot", exact=True)).to_have_value("2")
            capture(page, width, "member-shopping-error")
            page.locator("#listing-url").fill("")
            page.locator("#clear-lot").click()
            expect(row.get_by_label("In this lot", exact=True)).to_have_value("0")
            expect(row.get_by_label("Wanted quantity", exact=True)).to_have_value("3")
            expect(row.get_by_label("Lock wanted card", exact=True)).to_be_checked()
            expect(page.locator("#results")).to_be_hidden()
            page.reload()
            expect(page.locator("#selections .selection")).to_have_count(1)
            expect(page.get_by_label("In this lot", exact=True)).to_have_value("0")
            expect(page.get_by_label("Wanted quantity", exact=True)).to_have_value("3")
            capture(page, width, "member-shopping-next-lot")
            page.goto(base + "/packs/saved/")
            expect(page.get_by_role("heading", name="Saved Packs research", exact=True)).to_be_visible()
            page.get_by_role("link", name="Synthetic saved baseline", exact=True).click()
            expect(page.get_by_role("heading", name="Synthetic saved baseline", exact=True)).to_be_visible()
            details_keyboard(page)
            capture(page, width, "member-saved-pack", full=True)
            page.goto(base + "/lookup/?targets=123,134,230")
            expect(page.get_by_role("button", name="Save lookup", exact=True)).to_be_visible()
            capture(page, width, "member-lookup", full=True)
            if width == 1280:
                page.add_style_tag(content="body { zoom: 2; }")
                capture(page, width, "member-lookup-zoom200")
                page.goto(base + "/pokedex/")
                expect(page.locator("[data-dex-species]")).to_have_count(251)
                page.add_style_tag(content="body { zoom: 2; }")
                capture(page, width, "member-pokedex-zoom200")
            page.locator(".app-tools > summary").press("Enter")
            page.get_by_role("button", name="Sign out", exact=True).click()
            expect(page.locator(".public-species-row")).to_have_count(251)
            assert urlsplit(page.url).path == "/pokedex/"
            context.close()
        browser.close()
    after, photos_after = preserved(root)
    assert before == after, (
        "Private collection, goals, saves or historical observations changed during read-only checks"
    )
    assert photos_before == photos_after
    assert not external, external
    calls = json.loads((output.parent / "provider-calls.json").read_text())
    assert calls["calls"] == 0
    assert candidate == source_hashes(), (
        "Application source changed during browser checks; repeat at the final candidate"
    )
    report = dict(
        result="PASS",
        evidence_class="Generated synthetic local SQLite and Chromium; desktop/narrow/200% scale",
        viewports=[1280, 390],
        keyboard=True,
        private_rows_preserved=True,
        photos_preserved=True,
        provider_calls=0,
        external_browser_requests=0,
        console_errors=errors,
        protected_tables=list(before),
        source_sha256=candidate,
        denied_guest_routes=denied,
        states=metrics,
    )
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(dict(result="PASS", states=len(metrics), provider_calls=0, private_rows_preserved=True)))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--output", type=Path, required=True)
    options = parser.parse_args()
    run(options.root.resolve(), options.base_url.rstrip("/"), options.output.resolve())
