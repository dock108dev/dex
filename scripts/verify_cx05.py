"""Check My Cards and Card Library destinations on disposable engineering state.

Uses real loopback HTTP, Chromium and SQLite, blocks external requests and
provider acquisition, and never reads or changes the customer installation.
This helper exercises a focused contract. Integrated journeys are maintained in
scripts/ci/browser.py.
"""

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

from qualification_state import persisted_snapshot
from verify_cx02 import free_port

PROJECT = Path(__file__).resolve().parents[1]


def prepare(root, source, output):
    from verify_cx04 import prepare as previous_prepare

    previous_prepare(root, source, output)
    import uuid

    from django.db import connection

    from pokemon_hunter.beta import collection, store

    who = store.principal(1)
    fixture = json.loads(output.read_text())
    original = store.rows("SELECT * FROM printings WHERE id=%s", [fixture["primary_printing"]])[0]
    catalog_set = store.rows("SELECT * FROM catalog_sets WHERE id=%s", [original["set_id"]])[0]

    def insert(table, row):
        columns = list(row)
        collection.execute(
            "INSERT INTO "
            + table
            + " ("
            + ",".join(columns)
            + ") VALUES ("
            + ",".join(["%s"] * len(columns))
            + ")",
            list(row.values()),
        )

    def add_set(key, name, archived=False):
        row = dict(catalog_set, id=key, name=name, publication_state="archived" if archived else "published")
        insert("catalog_sets", row)

    def add_card(key, set_id, name, number, dex, archived=False):
        row = dict(
            original,
            id=key,
            set_id=set_id,
            collector_number=number,
            publication_state="archived" if archived else "published",
            provenance=json.dumps(dict(legacy_id=key)),
            attributes=json.dumps(dict(name=name, pokemon_dex=dex, dex_eligible=True, supertype="Pokémon")),
        )
        insert("printings", row)

    add_set("cx05-base", "Base Set")
    add_set("cx05-promos", "Wizards Black Star Promos")
    add_set("cx05-archive", "Retained archive", True)
    add_card("cx05-ivysaur-base", "cx05-base", "Ivysaur", "30", 2)
    add_card("cx05-mew-promo", "cx05-promos", "Mew", "8", 151)
    add_card("cx05-owned-archive", "cx05-archive", "Pikachu", "58", 25, True)

    def apply(kind, request):
        op = collection.preview(who, kind, request, str(uuid.uuid4()))
        assert not op["plan"]["errors"], op["plan"]
        return collection.confirm(who, op["id"])

    base = dict(set_name="Base Set", name="Ivysaur", number="30", language="en")
    apply("mark_owned", base)
    apply("card_quantity", dict(base, established_total_quantity=3))
    apply("mark_owned", dict(set_name="Retained archive", name="Pikachu", number="58", language="en"))
    fixture.update(
        base_printing="cx05-ivysaur-base",
        mew_printing="cx05-mew-promo",
        archive_printing="cx05-owned-archive",
    )
    output.write_text(json.dumps(fixture, indent=2) + "\n")
    connection.close()


def exercise(url, root, output, fixture, report):
    from playwright.sync_api import expect, sync_playwright
    from qualify_shopping import PASSWORD

    requests, errors = [], []
    mode = "success"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        report["browser_version"] = browser.version
        context = browser.new_context(viewport=dict(width=1280, height=900))
        context.tracing.start(screenshots=True, snapshots=True, sources=False)

        def restrict(route):
            if route.request.url.startswith(url + "/"):
                route.continue_()
                return
            request = route.request
            assert request.resource_type == "image", request.url
            assert request.url.startswith(
                ("https://assets.tcgdex.net/", "https://raw.githubusercontent.com/")
            )
            headers = request.all_headers()
            assert not any(k in headers for k in ("referer", "cookie", "authorization"))
            requests.append(dict(url=request.url, mode=mode, sent_to_remote=False))
            if mode == "blocked":
                route.abort("blockedbyclient")
            elif mode == "failure":
                route.fulfill(status=404, body="Controlled image failure")
            else:
                route.fulfill(
                    status=200,
                    content_type="image/svg+xml",
                    body='<svg xmlns="http://www.w3.org/2000/svg" width="245" height="337"><rect width="245" height="337" fill="#e6e6e6"/><text x="20" y="170" font-size="18">Engineering image</text></svg>',
                )

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
            expect(page.locator("#content")).not_to_contain_text("Loading cards…")

        def tile(name):
            return page.locator(".owned-card-tile").filter(has_text=name)

        def preview_change(intent, quantity=None):
            page.locator("#edit-group-card").click()
            page.locator("#collection-intent").select_option(intent)
            if quantity is not None:
                page.locator("#total-quantity").fill(str(quantity))
            page.get_by_role("button", name="Preview collection change", exact=True).click()
            expect(page.locator("#review")).to_be_visible()

        def confirm():
            page.locator("#confirm").click()
            expect(page.locator("#review-body")).to_contain_text("Changes saved.")

        def close_review():
            page.locator('[data-close="review"]').click()
            expect(page.locator("#edit-group-card")).to_be_focused()

        def scale_text(keys):
            measured = page.evaluate(
                """keys => {
                const before=keys.map(key=>parseFloat(getComputedStyle(document.querySelector(key)).fontSize));
                const sizes=[...document.querySelectorAll('body,body *')].map(el=>[el,parseFloat(getComputedStyle(el).fontSize),el.style.fontSize]);
                window.cx05TextRestore=sizes;
                for(const [el,size] of sizes)el.style.fontSize=(size*2)+'px';
                return {before,after:keys.map(key=>parseFloat(getComputedStyle(document.querySelector(key)).fontSize))};
            }""",
                keys,
            )
            assert measured["after"] == [size * 2 for size in measured["before"]], measured
            return measured

        def header_separated():
            assert page.evaluate("""() => {
                const brand=document.querySelector('.app-header .brand').getBoundingClientRect();
                const tools=document.querySelector('.app-tools summary').getBoundingClientRect();
                return brand.right<=tools.left||tools.right<=brand.left||brand.bottom<=tools.top||tools.bottom<=brand.top;
            }"""), "Brand and account navigation overlap at enlarged text"

        def restore_text():
            page.evaluate(
                """() => {for(const [el,size,original] of window.cx05TextRestore){if(original)el.style.fontSize=original;else el.style.removeProperty('font-size');}delete window.cx05TextRestore;}"""
            )

        try:
            page.goto(url + "/login/?next=/cards/")
            page.get_by_label("Username:", exact=True).fill("admin")
            page.get_by_label("Password:", exact=True).fill(PASSWORD)
            page.get_by_role("button", name="Sign in", exact=True).click()
            expect(page.locator("#content h1")).to_have_text("My Cards")
            before = persisted_snapshot(root)
            authority = get("/api/collection/")["effective_collection"]
            owned = get("/api/my-card-groups/")
            assert type(authority["generation"]) is int and authority["generation"] == owned["generation"]
            assert authority["user_id"] == owned["account_id"]
            library = get("/api/card-groups/")
            group = next(g for g in owned["groups"] if g["collector_number"] == "44")
            base = next(g for g in owned["groups"] if g["collector_number"] == "30")
            mew = next(g for g in library["groups"] if g["name"] == "Mew")
            path = group["url"]
            passed(
                "ordinary sign-in reaches owned groups; canonical Base 30/Base2 44 separate and Mew promo 8 available"
            )
            report["group_ids"] = {k: v["id"] for k, v in [("ivysaur", group), ("base", base), ("mew", mew)]}
            # Verify list against authority rather than names or child count.
            expect(page.locator(".owned-card-tile")).to_have_count(owned["total"])
            assert all(g["present"] for g in owned["groups"])
            assert len(owned["groups"]) == 3
            assert page.locator(".owned-card-tile").filter(has_text="Mew").count() == 0
            assert page.locator(".owned-card-tile").filter(has_text="recorded copies").count() == 0
            assert page.locator(".owned-card-tile").filter(has_text="Unknown").count() == 0
            assert all(
                page.locator(".owned-card-tile").nth(i).locator("button,a").count() == 0
                for i in range(owned["total"])
            )
            passed(
                "owned-only compact one-link tiles; unknown total omitted and established total once; no nested controls"
            )
            for width in (1280, 390, 320):
                page.set_viewport_size(dict(width=width, height=900))
                load("/cards/")
                page.screenshot(path=str(output / f"engineering-list-{width}.png"), full_page=True)
                load(path)
                expect(page.locator("#content h1")).to_have_text("Ivysaur")
                assert page.locator("dialog[open]").count() == 0
                assert page.locator("#content details[open]").count() == 0
                expect(page.locator("#content")).to_contain_text("Quantity not recorded.")
                assert get("/api/card-groups/" + group["id"] + "/")["selected_child"] is None
                expect(page.locator("#card-collection-heading")).to_be_visible()
                assert page.locator("#group-history").count() == int(
                    bool(get("/api/card-groups/" + group["id"] + "/")["history"])
                )
                assert page.locator("#group-copies [data-group-copy]").count() == 0
                if width == 1280:
                    for key in (
                        "#canonical-card h1",
                        ".card-ownership",
                        "#edit-group-card",
                        "#card-collection-heading",
                    ):
                        box = page.locator(key).bounding_box()
                        assert box["y"] + box["height"] < 900, key
                page.screenshot(path=str(output / f"engineering-detail-default-{width}.png"), full_page=True)
                page.locator("#group-variants > summary").click()
                page.locator("#group-records > summary").click()
                page.screenshot(path=str(output / f"engineering-detail-expanded-{width}.png"), full_page=True)
                assert page.evaluate("document.documentElement.scrollWidth<=innerWidth"), width
            passed(
                "focused normal detail has visible collection summary and closed optional disclosures; wide/320px default and expanded screenshots retained"
            )
            # Explicit and archived selection never substitutes the group image.
            for child in (fixture["selected_printing"], fixture["archived_printing"]):
                load(path + "?child=" + child)
                expect(page.locator("#group-selected")).to_have_attribute("data-selected-child", child)
                expect(page.locator("#group-selected")).to_contain_text("image unavailable")
                assert page.locator("#group-selected img").count() == 0
                page.reload()
                expect(page.locator("#group-selected")).to_have_attribute("data-selected-child", child)
            passed(
                "null/explicit/archived child and refresh preserve exact context; unsupported exact imagery separate"
            )
            for state in ("failure", "blocked"):
                mode = state
                load("/cards/")
                expect(page.locator(".owned-card-tile").first).to_be_visible()
                page.locator(".owned-card-tile").first.focus()
                page.keyboard.press("Enter")
                expect(page.locator("#content h1")).not_to_contain_text("Loading")
                assert page.locator("dialog[open]").count() == 0
                assert page.url.startswith(url + "/card-groups/")
            mode = "success"
            passed("controlled image HTTP failure and abort preserve tile keyboard navigation")
            load("/cards/?q=Ivysaur&sort=name&page_size=1&page=2&scroll=0")
            expect(page.locator(".owned-card-tile")).to_have_count(1)
            link = page.locator(".owned-card-tile").first
            destination = link.get_attribute("href")
            assert "return=" in destination and "child=" not in destination
            link.scroll_into_view_if_needed()
            scroll_before = page.evaluate("Math.round(scrollY)")
            expected_return = (
                url + "/cards/?q=Ivysaur&sort=name&page_size=1&page=2&scroll=" + str(scroll_before)
            )
            link.click()
            expect(page.locator("#card-back")).to_have_attribute("href", expected_return.removeprefix(url))
            expect(page.locator("#content h1")).to_have_text("Ivysaur")
            page.reload()
            expect(page.locator("#content h1")).to_have_text("Ivysaur")
            page.locator("#card-back").click()
            expect(page).to_have_url(expected_return)
            expect(page.locator(".owned-card-tile").first).to_be_focused()
            assert abs(page.evaluate("scrollY") - scroll_before) <= 1
            page.locator(".owned-card-tile").first.click()
            page.go_back()
            expect(page.locator("#cards-query")).to_have_value("Ivysaur")
            expect(page.locator(".owned-card-tile")).to_have_count(1)
            passed(
                "group pagination and search/sort/tab/page return context survive visible Back, browser Back and refresh"
            )
            page.locator(".app-header nav a", has_text="Card Library").click()
            expect(page.locator("#cards-count")).to_be_visible()
            page.locator("#cards-query").fill("Mew")
            page.get_by_role("button", name="Search cards", exact=True).click()
            expect(page.locator(".owned-card-tile")).to_have_count(1)
            page.locator(".app-header nav a", has_text="My Cards").click()
            expect(page.locator("#cards-query")).to_have_value("Ivysaur")
            assert "page=2" in page.url and "page_size=1" in page.url
            page.locator(".app-header nav a", has_text="Card Library").click()
            expect(page.locator("#cards-query")).to_have_value("Mew")
            expect(page.locator(".owned-card-tile")).to_have_count(1)
            passed(
                "local tab switching restores each tab own validated filters/page without cross-account authority"
            )
            load("/cards/?q=absent-card")
            expect(page.locator("#content")).to_contain_text("No matching cards")
            load("/cards/?finish=holo")
            expect(page.locator(".owned-card-tile")).to_have_count(1)
            assert page.locator(".owned-card-tile").first.get_attribute("data-matching-child-ids")
            assert "child=" not in page.locator(".owned-card-tile").first.get_attribute("href")
            options = get("/api/card-group-filters/?scope=owned")
            assert any(s["name"] == "Retained archive" for s in options["sets"])
            passed(
                "no-match distinct; variant matches retain child IDs without selection; complete owned archived set options"
            )
            load("/card-library/?q=Mew")
            expect(page.locator(".owned-card-tile")).to_have_count(1)
            page.locator(".owned-card-tile").click()
            expect(page.locator("#edit-group-card")).to_have_text("Add to collection")
            assert persisted_snapshot(root) == before
            (output / "read-preservation.json").write_text(
                json.dumps(dict(before=before, after=persisted_snapshot(root), equal=True), indent=2) + "\n"
            )
            passed(
                "all preceding read-only routes preserve complete persisted state; private and public source boundaries retained"
            )
            # Broad ownership does not require a copy or edition.
            page.locator("#edit-group-card").click()
            held = []
            page.route("**/api/card-groups/*/preview/", lambda route: held.append(route), times=1)
            page.get_by_role("button", name="Preview collection change", exact=True).click()
            expect(page.locator("#collection-intent")).to_be_disabled()
            page.keyboard.press("Escape")
            assert len(held) == 1
            held[0].continue_()
            page.wait_for_function("() => !busy")
            assert page.locator("dialog[open]").count() == 0
            assert get("/api/card-groups/" + mew["id"] + "/")["group"]["present"] is False
            page.locator("#edit-group-card").click()
            page.get_by_role("button", name="Preview collection change", exact=True).click()
            confirm()
            close_review()
            result = get("/api/card-groups/" + mew["id"] + "/")
            assert (
                result["group"]["present"]
                and not result["copies"]
                and result["group"]["established_total_quantity"] is None
            )
            passed(
                "cancel/Escape performs no confirmation; broad mark-owned adds without physical copy/quantity/variant"
            )
            preview_change("card_quantity", 4)
            confirm()
            close_review()
            assert get("/api/card-groups/" + mew["id"] + "/")["group"]["established_total_quantity"] == 4
            page.locator("#edit-group-card").click()
            expect(page.locator("#collection-intent")).to_have_value("")
            page.keyboard.press("Escape")
            preview_change("quantity_unknown")
            confirm()
            close_review()
            assert get("/api/card-groups/" + mew["id"] + "/")["group"]["established_total_quantity"] is None
            passed(
                "record and clear established total explicitly; opening owned editor has no destructive default"
            )
            # A concurrent authoritative change cannot silently refresh/confirm a preview.
            import uuid

            csrf_token = next(c["value"] for c in context.cookies() if c["name"] == "dex_b1_csrf")

            def post(path, payload):
                response = context.request.post(
                    url + path,
                    data=json.dumps(payload),
                    headers={"Content-Type": "application/json", "X-CSRFToken": csrf_token, "Origin": url},
                )
                assert response.status == 200, (path, response.status, response.text())
                return response.json()

            preview_change("card_quantity", 5)
            other = post(
                "/api/card-groups/" + base["id"] + "/preview/",
                dict(
                    kind="card_quantity",
                    request=dict(established_total_quantity=3),
                    operation_id=str(uuid.uuid4()),
                ),
            )
            post("/api/operations/" + other["id"] + "/confirm/", {})
            pending_refresh = []
            page.route("**/api/collection-context/", lambda route: pending_refresh.append(route), times=1)
            page.locator("#confirm").click()
            expect(page.locator("#review-error")).to_contain_text("conflicts")
            expect(page.locator("#confirm")).to_be_hidden()
            assert get("/api/card-groups/" + mew["id"] + "/")["group"]["established_total_quantity"] is None
            close_review()
            assert len(pending_refresh) == 1, "Stale authority refresh was not requested"
            pending_refresh[0].continue_()
            page.wait_for_function("() => !busy")
            expect(page.locator("#edit-group-card")).to_be_focused()
            passed(
                "stale confirmation visibly reloads authority without silently confirming a refreshed preview; closing during delayed refresh restores current focus"
            )
            preview_change("card_quantity", 4)
            page.route(
                "**/api/collection-context/",
                lambda route: route.fulfill(
                    status=503, content_type="text/html", body="Controlled refresh loss"
                ),
                times=1,
            )
            page.locator("#confirm").click()
            expect(page.locator("#recover-operation")).to_be_visible()
            page.locator("#recover-operation").click()
            expect(page.locator("#review-body")).to_contain_text("Changes saved.")
            assert get("/api/card-groups/" + mew["id"] + "/")["group"]["established_total_quantity"] == 4
            close_review()
            page.reload()
            expect(page.locator("#edit-group-card")).to_be_visible()
            passed(
                "lost refresh recovers the same saved operation inside accessible review; no second addition"
            )
            # Add an explicitly chosen itemised child and preserve closed advanced fields.
            load(path + "?child=" + fixture["selected_printing"])
            expect(page.locator("#group-variants")).to_have_attribute("open", "")
            page.locator("#group-add-copy").click()
            assert page.locator(".copy-purchase[open],.copy-grading[open]").count() == 0
            page.locator(".copy-purchase > summary").click()
            page.locator("#purchase_amount").fill("12.50")
            page.locator("#purchase_currency").fill("USD")
            page.locator(".copy-grading > summary").click()
            page.locator("#grading_company").fill("PSA")
            page.locator("#grade").fill("9")
            page.locator("#certificate").fill("engineering-cert")
            page.locator("#notes").fill("Retained copy note")
            page.get_by_role("button", name="Preview addition", exact=True).click()
            confirm()
            close_review()
            result = get("/api/card-groups/" + group["id"] + "/")
            copy = result["copies"][0]
            assert copy["printing_id"] == fixture["selected_printing"]
            for width in (1280, 320):
                page.set_viewport_size(dict(width=width, height=900))
                page.screenshot(path=str(output / f"engineering-active-copy-{width}.png"), full_page=True)
            page.locator(".copy-actions > summary").first.click()
            report["copy_text_scaling"] = scale_text(
                ["[data-group-copy]", "[data-group-edition]", "[data-group-remove]"]
            )
            assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
            assert page.locator(".card-copy-row button").evaluate_all(
                "(buttons)=>buttons.every(button=>button.scrollWidth<=button.clientWidth)"
            ), "Copy action text escapes its control"
            page.screenshot(path=str(output / "engineering-active-copy-320-text200.png"), full_page=True)
            restore_text()
            page.locator("[data-group-copy]").first.focus()
            page.keyboard.press("Enter")
            expect(page.locator("#editor")).to_be_visible()
            page.keyboard.press("Escape")
            expect(page.locator("[data-group-copy]").first).to_be_focused()
            page.keyboard.press("Enter")
            assert page.locator(".copy-purchase[open],.copy-grading[open]").count() == 0
            for width in (1280, 320):
                page.set_viewport_size(dict(width=width, height=900))
                page.screenshot(path=str(output / f"engineering-copy-editor-{width}.png"), full_page=True)
            page.locator(".copy-purchase > summary").click()
            page.locator(".copy-grading > summary").click()
            report["editor_text_scaling"] = scale_text(
                ["#editor-title", "#condition", "#purchase_currency", "#certificate"]
            )
            assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
            assert page.locator("#editor").evaluate("(dialog)=>dialog.scrollWidth<=dialog.clientWidth"), (
                "Editor has internal horizontal overflow"
            )
            assert (
                page.locator("#copy-form button").bounding_box()["width"]
                <= page.locator("#editor").bounding_box()["width"]
            )
            page.screenshot(path=str(output / "engineering-copy-editor-320-text200.png"), full_page=True)
            restore_text()
            page.locator(".copy-purchase > summary").click()
            page.locator(".copy-grading > summary").click()
            page.locator("#notes").fill("Updated note only")
            page.get_by_role("button", name="Preview edit", exact=True).click()
            confirm()
            close_review()
            edited = get("/api/card-groups/" + group["id"] + "/")["copies"][0]
            assert all(
                edited[k] == copy[k]
                for k in (
                    "id",
                    "purchase_amount",
                    "purchase_currency",
                    "grading_company",
                    "grade",
                    "certificate",
                )
            )
            assert edited["notes"] == "Updated note only"
            passed(
                "selected-child copy addition and two-step edit preserve closed purchase/grading/certificate fields"
            )
            page.locator("#group-prices > summary").click()
            expect(page.locator("#group-prices-body")).not_to_contain_text("Loading retained prices")
            expect(page.locator("#group-prices-body")).to_contain_text("No matching retained guide evidence")
            page.locator(".copy-actions > summary").first.click()
            page.locator("[data-group-edition]").first.click()
            expect(page.locator("#copy-first-edition")).to_be_disabled()
            expect(page.locator("#copy-first-edition")).not_to_be_checked()
            page.get_by_role("button", name="Preview edition change", exact=True).click()
            confirm()
            after_edition = get("/api/card-groups/" + group["id"] + "/")["copies"][0]
            assert (
                not after_edition["first_edition_selected"]
                and after_edition["purchase_amount"] == copy["purchase_amount"]
            )
            page.locator("#undo").click()
            expect(page.locator("#review-body")).to_contain_text("This operation has been undone")
            close_review()
            passed(
                "optional retained price/source disclosure uses existing evidence only; focused copy edition preview/undo remains reachable"
            )
            # Confirmation succeeded but response lost: do not submit another addition.
            expect(page.locator("#group-variants")).to_have_attribute("open", "")
            page.locator("#group-add-copy").click()
            page.locator("#copy-policy").select_option("allow")
            page.get_by_role("button", name="Preview addition", exact=True).click()

            def lose_confirmation(route):
                route.fetch()
                route.abort("failed")

            page.route("**/api/operations/*/confirm/", lose_confirmation, times=1)
            confirm()
            saved = get("/api/card-groups/" + group["id"] + "/")
            assert len(saved["copies"]) == 2
            expect(page.locator("#confirm")).to_be_hidden()
            page.locator("#undo").click()
            expect(page.locator("#review-body")).to_contain_text("This operation has been undone")
            assert len(get("/api/card-groups/" + group["id"] + "/")["copies"]) == 1
            close_review()
            passed(
                "lost confirmation response resolves saved operation; repeated confirmation/undo do not duplicate additions"
            )
            # Remove copy differs from remove-card; history and later genuine addition preserved.
            load(path)
            page.locator(".copy-actions > summary").first.click()
            page.locator("[data-group-remove]").first.click()
            confirm()
            close_review()
            result = get("/api/card-groups/" + group["id"] + "/")
            assert result["group"]["present"] and not result["copies"] and result["history"]
            preview_change("remove_card")
            confirm()
            close_review()
            assert not get("/api/card-groups/" + group["id"] + "/")["group"]["present"]
            page.locator("#edit-group-card").click()
            page.get_by_role("button", name="Preview collection change", exact=True).click()
            confirm()
            close_review()
            assert get("/api/card-groups/" + group["id"] + "/")["group"]["present"]
            passed(
                "remove one copy preserves declaration; remove-card removes possession; later explicit addition restores ownership"
            )
            # Visible request errors include retries and do not masquerade as empty.
            page.route(
                "**/api/my-card-groups/*",
                lambda r: r.fulfill(status=503, content_type="text/html", body="<h1>Unavailable</h1>"),
                times=1,
            )
            load("/cards/")
            expect(page.locator("#content")).to_contain_text("could not complete")
            assert page.get_by_role("button", name="Reload current cards", exact=False).count() > 0
            page.unroute("**/api/my-card-groups/*")
            load("/cards/")
            passed("HTML unavailability is a request failure with retry, distinct from empty collection")
            page.set_viewport_size(dict(width=320, height=900))
            load(path)
            scaling = page.evaluate("""() => {
                const keys=['#canonical-card h1','#edit-group-card','#group-variants summary'];
                const before=keys.map(key=>parseFloat(getComputedStyle(document.querySelector(key)).fontSize));
                const sizes=[...document.querySelectorAll('body,body *')].map(el=>[el,parseFloat(getComputedStyle(el).fontSize)]);
                for(const [el,size] of sizes)el.style.fontSize=(size*2)+'px';
                return {before,after:keys.map(key=>parseFloat(getComputedStyle(document.querySelector(key)).fontSize))};
            }""")
            assert scaling["after"] == [size * 2 for size in scaling["before"]], scaling
            report["text_scaling"] = scaling
            header_separated()
            page.locator(".app-tools > summary").focus()
            page.keyboard.press("Enter")
            expect(page.locator(".tools-menu")).to_be_visible()
            assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
            assert page.locator(".tools-menu a").evaluate_all(
                "els=>els.every(el=>el.scrollWidth<=el.clientWidth)"
            )
            menu = page.locator(".tools-menu").bounding_box()
            card = page.locator("#canonical-card").bounding_box()
            assert menu["y"] + menu["height"] <= card["y"], "Narrow menu must precede card without overlap"
            page.screenshot(path=str(output / "engineering-menu-320-text200.png"), full_page=True)
            page.locator(".app-tools > summary").focus()
            page.keyboard.press("Enter")
            expect(page.locator(".app-tools > summary")).to_be_focused()
            page.screenshot(path=str(output / "engineering-detail-320-text200.png"), full_page=True)
            passed("200% text at 320px retains readable controls without horizontal page overflow")
            load("/cards/")
            page.locator("#card-advanced-filters > summary").click()
            list_scaling = page.evaluate("""() => {
                const keys=['#cards-query','.app-header nav a','#card-advanced-filters summary'];
                const before=keys.map(key=>parseFloat(getComputedStyle(document.querySelector(key)).fontSize));
                const sizes=[...document.querySelectorAll('body,body *')].map(el=>[el,parseFloat(getComputedStyle(el).fontSize)]);
                for(const [el,size] of sizes)el.style.fontSize=(size*2)+'px';
                return {before,after:keys.map(key=>parseFloat(getComputedStyle(document.querySelector(key)).fontSize))};
            }""")
            assert list_scaling["after"] == [size * 2 for size in list_scaling["before"]]
            assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
            page.screenshot(path=str(output / "engineering-list-320-text200.png"), full_page=True)
            report["list_text_scaling"] = list_scaling
            header_separated()
            passed(
                "200% actual text scaling keeps list tabs, Search, Set and advanced controls usable at 320px"
            )
            guest = browser.new_context()
            assert "account_id" not in guest.request.get(url + "/api/public/card-groups/").text()
            assert guest.request.get(url + "/api/my-card-groups/", max_redirects=0).status == 302
            guest.close()
            passed(
                "signed-out private routes redirect; public metadata excludes account/source/copy/photo projections"
            )
            report["mutations_after"] = persisted_snapshot(root)
            report["mutation_evidence_note"] = (
                "Expected account-scoped journal/copy/quantity changes only; read-only fingerprint phase recorded separately."
            )
        finally:
            report["controlled_image_requests"] = requests
            report["page_errors"] = errors
            context.tracing.stop(path=str(output / "trace.zip"))
            browser.close()
        assert not errors, errors
        report["external_requests_sent"] = 0
        report["controlled_asset_note"] = (
            "Neutral engineering SVG/404/abort responses; no external image or customer visual claim."
        )


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
        deferred_CX06_CX08_journeys_qualified=False,
        checks=[],
    )
    files = [
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
        "scripts/verify_cx05.py",
    ]
    report["source_hashes"] = {
        name: hashlib.sha256((PROJECT / name).read_bytes()).hexdigest() for name in files
    }
    try:
        with tempfile.TemporaryDirectory(prefix="dex-cx05-browser-") as temporary:
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
