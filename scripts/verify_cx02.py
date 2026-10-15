"""Exercise collection editing forms forms against a disposable engineering database and real server.

No customer installation is read or changed. Browser/API requests are never mocked;
external requests are blocked and retained as failures. This qualifies only the
bounded collection editor, review, source selector, keyboard and narrow paths.
"""

import argparse
import csv
import hashlib
import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import traceback
import uuid
from pathlib import Path
from urllib.request import urlopen

PROJECT = Path(__file__).resolve().parents[1]


def prepare(root, source, output):
    from qualify_shopping import prepare as initialize_fixture

    initialize_fixture(root, source)
    from django.db import connection

    from pokemon_hunter.beta import collection, ownership_declarations, store
    from pokemon_hunter.beta.canonical_species import registry
    from pokemon_hunter.inventory import connect
    from pokemon_hunter.migration import digest

    with connect(root / "inventory.db") as db:
        ownership_declarations.initialize(db)
    actor = store.principal(1)
    collection.execute("UPDATE catalog_sets SET name='Base Set 2'")
    names = {
        "synthetic-bulbasaur": ("Ivysaur", "44", 2),
        "synthetic-chansey": ("Bulbasaur", "67", 1),
        "synthetic-scyther": ("Venusaur", "18", 3),
        "synthetic-scyther-alt": ("Chikorita", "54", 152),
    }
    for printing in collection.catalog(actor):
        legacy = json.loads(printing["provenance"])["legacy_id"]
        name, number, dex = names[legacy]
        collection.execute(
            "UPDATE printings SET collector_number=%s,language='en',attributes=%s WHERE id=%s",
            [
                number,
                json.dumps(dict(name=name, pokemon_dex=dex, dex_eligible=True, supertype="Pokémon")),
                printing["id"],
            ],
        )

    def apply(kind, request):
        op = collection.preview(actor, kind, request, str(uuid.uuid4()))
        assert not op["plan"]["errors"], op["plan"]
        return collection.confirm(actor, op["id"])

    for copy in collection.copies(actor):
        apply("remove", dict(id=copy["id"], revision=copy["revision"]))

    def source_request(marks):
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=ownership_declarations.FULL_HEADERS)
        writer.writeheader()
        for dex in range(1, 252):
            row = dict.fromkeys(ownership_declarations.FULL_HEADERS, "")
            row.update(
                Dex=dex, Pokemon=registry()[dex]["name"], Status="Owned" if dex in marks else "Missing"
            )
            row.update(marks.get(dex, {}))
            writer.writerow(row)
        text = stream.getvalue()
        return dict(text=text, sha256=digest(text.encode()))

    first = source_request({2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}})
    second = source_request({3: {"Base Set 2": "✓ Venusaur #18 (Rare)"}})
    selected_second = apply("owner_declaration", second)
    selected_first = apply("owner_declaration", first)
    fixture = dict(
        evidence_class="isolated engineering fixture; never customer demonstration",
        sources=dict(
            first=selected_first["plan"]["selected_source_id"],
            second=selected_second["plan"]["selected_source_id"],
        ),
        initial_copies=collection.copies(actor),
        initial_goals=collection.goals(actor),
    )
    output.write_text(json.dumps(fixture, indent=2, sort_keys=True) + "\n")
    connection.close()


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


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
        evidence_class="isolated engineering browser; real loopback server and database",
        customer_installation_accessed=False,
        deferred_consumer_journeys_qualified=False,
        checks=[],
    )
    result = args.output / "verification.json"
    source_files = [
        "src/pokemon_hunter/beta/static/collection.js",
        "src/pokemon_hunter/beta/static/parity.js",
        "src/pokemon_hunter/beta/static/collection.css",
        "src/pokemon_hunter/beta/collection.py",
        "src/pokemon_hunter/beta/collection_views.py",
        "src/pokemon_hunter/beta/collection_intents.py",
        "src/pokemon_hunter/beta/effective_collection.py",
        "src/pokemon_hunter/beta/ownership_declarations.py",
        "src/pokemon_hunter/beta/parity.py",
        "scripts/verify_cx02.py",
    ]
    report["source_hashes"] = {
        name: hashlib.sha256((PROJECT / name).read_bytes()).hexdigest() for name in source_files
    }
    try:
        with tempfile.TemporaryDirectory(prefix="dex-cx02-browser-") as temporary:
            base = Path(temporary)
            root = base / "engineering-root"
            fixture_path = args.output / "fixture.json"
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
                    str(fixture_path),
                ],
                check=True,
                cwd=PROJECT,
            )
            fixture = json.loads(fixture_path.read_text())
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
                    exercise(url, args.output, fixture, report)
                finally:
                    server.terminate()
                    try:
                        server.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        server.kill()
                        server.wait(timeout=10)
            calls = json.loads((args.output / "provider-calls.json").read_text())
            assert calls["calls"] == 0, calls
            report["provider_calls"] = calls["calls"]
            after_hashes = {
                name: hashlib.sha256((PROJECT / name).read_bytes()).hexdigest() for name in source_files
            }
            assert after_hashes == report["source_hashes"], "Browser source changed during verification"
            report["source_stable_during_verification"] = True
        report["passed"] = True
    except Exception:
        report["passed"] = False
        report["failure"] = traceback.format_exc()
        raise
    finally:
        result.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


def exercise(url, output, fixture, report):
    from playwright.sync_api import expect, sync_playwright
    from qualify_shopping import PASSWORD

    external_requests = []
    page_errors = []
    operations = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        report["browser_version"] = browser.version
        context = browser.new_context(viewport=dict(width=1280, height=900))
        context.tracing.start(screenshots=True, snapshots=True, sources=False)

        def restrict(route):
            if route.request.url.startswith(url + "/"):
                route.continue_()
            else:
                external_requests.append(
                    dict(url=route.request.url, resource_type=route.request.resource_type, blocked=True)
                )
                route.abort()

        context.route("**/*", restrict)
        page = context.new_page()
        page.on("pageerror", lambda error: page_errors.append(str(error)))

        def state():
            response = context.request.get(url + "/api/collection/")
            assert response.status == 200, response.status
            return response.json()

        def card(name):
            rows = [r for r in state()["effective_collection"]["cards"] if r["name"] == name]
            assert len(rows) <= 1, rows
            return (
                rows[0]
                if rows
                else dict(present=False, established_total_quantity=None, recorded_copy_count=0)
            )

        def check(name, present, quantity, copies):
            row = card(name)
            assert (row["present"], row["established_total_quantity"], row["recorded_copy_count"]) == (
                present,
                quantity,
                copies,
            ), row
            heading = page.locator(".card-detail-layout h1")
            if heading.count() and heading.inner_text() == name:
                expect(page.locator(".card-detail-layout")).to_contain_text(
                    "Owned" if present else "Not owned"
                )
                expect(page.locator(".card-detail-layout")).to_contain_text(
                    "Quantity not recorded." if quantity is None else "Quantity " + str(quantity)
                )

        def close_review():
            if page.locator("#review").is_visible():
                page.get_by_role("button", name="Close review", exact=True).click()

        def visit(legacy):
            close_review()
            page.goto(url + "/cards/" + legacy + "/")
            expect(page.locator("#edit-group-card")).to_be_visible()

        def preview_click(click, label):
            before = state()["effective_collection"]
            with page.expect_response(lambda response: response.url.endswith("/preview/")) as pending:
                click()
            response = pending.value
            assert response.status == 200, response.text()
            op = response.json()
            expect(page.locator("#review")).to_be_visible()
            assert not op["plan"]["errors"], op["plan"]
            assert state()["effective_collection"] == before, "Pending preview changed effective ownership"
            operations.append(
                dict(label=label, operation=op, review=page.locator("#review-body").inner_text())
            )
            return op

        def intent(legacy, kind, quantity=None):
            visit(legacy)
            page.locator("#edit-group-card").click()
            page.get_by_label("Change", exact=True).select_option(kind)
            if kind == "card_quantity":
                page.get_by_label("Total quantity", exact=True).fill(str(quantity))
            return preview_click(
                lambda: page.get_by_role("button", name="Preview collection change", exact=True).click(), kind
            )

        def mutate(action):
            with page.expect_response(lambda response: response.url.endswith("/" + action + "/")) as pending:
                page.locator("#" + action).click()
            response = pending.value
            assert response.status == 200, response.text()
            expect(page.locator("#review-body")).to_contain_text(
                "Changes saved." if action == "confirm" else "This operation has been undone"
            )
            expect(page.locator("#review-error")).to_be_empty()

        def passed(label):
            report["checks"].append(dict(check=label, passed=True))

        def keyboard_path(dialog):
            path = []
            for _ in range(12):
                page.keyboard.press("Tab")
                focused = page.evaluate(
                    """selector => { const active=document.activeElement; return {
                        tag:active.tagName, id:active.id, text:active.textContent,
                        inside:Boolean(active.closest(selector))}; }""",
                    dialog,
                )
                # Native Chromium dialogs can transfer focus to browser chrome.
                # BODY then represents document focus, never a background control.
                assert focused["inside"] or focused["tag"] == "BODY", focused
                path.append({key: focused[key] for key in ("tag", "id", "inside")})
            assert any(item["inside"] for item in path)
            report.setdefault("keyboard_paths", []).append(dict(dialog=dialog, path=path))
            return path

        def fits(label, dialog=None):
            layout = page.evaluate(
                "() => ({width:innerWidth,scrollWidth:document.documentElement.scrollWidth})"
            )
            if dialog:
                layout["dialog"] = page.locator(dialog).evaluate(
                    "element => ({width:element.clientWidth,scrollWidth:element.scrollWidth})"
                )
                assert layout["dialog"]["scrollWidth"] <= layout["dialog"]["width"], layout
            report.setdefault("layouts", []).append(dict(label=label, **layout))
            assert layout["scrollWidth"] <= layout["width"], layout

        try:
            page.goto(url + "/login/?next=/collection/")
            page.get_by_label("Username:", exact=True).fill("admin")
            page.get_by_label("Password:", exact=True).fill(PASSWORD)
            page.get_by_role("button", name="Sign in", exact=True).click()
            expect(page.locator("#content")).not_to_contain_text("Loading your collection")
            check("Ivysaur", True, None, 0)
            passed("ordinary sign-in; declared Ivysaur owned with unknown total and zero copies")

            visit("synthetic-chansey")
            edit = page.get_by_role("button", name="Edit collection", exact=True)
            edit.focus()
            page.keyboard.press("Enter")
            expect(page.locator("#editor")).to_be_visible()
            path = keyboard_path("#editor")
            assert any(item["id"] == "collection-intent" for item in path), path
            page.keyboard.press("Escape")
            expect(page.locator("#editor")).not_to_be_visible()
            passed("keyboard Enter opens editor, Tab reaches intent and no background control, Escape closes")

            intent("synthetic-chansey", "mark_owned")
            mutate("confirm")
            check("Bulbasaur", True, None, 0)
            mutate("undo")
            check("Bulbasaur", False, None, 0)
            intent("synthetic-chansey", "mark_owned")
            mutate("confirm")
            check("Bulbasaur", True, None, 0)
            passed("mark owned preview/confirm/undo creates no copy or physical attributes")

            intent("synthetic-bulbasaur", "card_quantity", 3)
            mutate("confirm")
            check("Ivysaur", True, 3, 0)
            intent("synthetic-bulbasaur", "quantity_unknown")
            mutate("confirm")
            check("Ivysaur", True, None, 0)
            intent("synthetic-bulbasaur", "card_quantity", 2)
            mutate("confirm")
            check("Ivysaur", True, 2, 0)
            passed("explicit exhaustive integer total and clear-to-unknown through ordinary forms")

            visit("synthetic-bulbasaur")
            page.get_by_role("button", name="Add a physical copy", exact=True).click()
            preview_click(
                lambda: page.get_by_role("button", name="Preview addition", exact=True).click(),
                "add physical copy",
            )
            mutate("confirm")
            check("Ivysaur", True, None, 1)
            close_review()
            preview_click(
                lambda: page.get_by_role("button", name="Remove this copy", exact=True).click(),
                "remove this copy",
            )
            mutate("confirm")
            check("Ivysaur", True, None, 0)
            mutate("undo")
            check("Ivysaur", True, None, 1)
            passed(
                "copy addition invalidates total; removing a copy preserves declared card presence; undo restores record"
            )

            copy_id = card("Ivysaur")["recorded_copy_ids"][0]
            intent("synthetic-bulbasaur", "remove_card")
            expect(page.locator("#review-body")).to_contain_text(copy_id)
            page.screenshot(path=str(output / "desktop-remove-card-review.png"), full_page=True)
            mutate("confirm")
            check("Ivysaur", False, None, 0)
            mutate("undo")
            check("Ivysaur", True, None, 1)
            passed(
                "remove-card preview exposes affected copy ID; confirmation removes possession and record support; undo restores"
            )

            intent("synthetic-bulbasaur", "declaration_correction")
            mutate("confirm")
            check("Ivysaur", True, None, 1)
            mutate("undo")
            check("Ivysaur", True, None, 1)
            passed("declaration-only correction preserves supported physical copy possession and undo")

            intent("synthetic-scyther-alt", "mark_owned")
            mutate("confirm")
            intent("synthetic-scyther-alt", "card_quantity", 3)
            mutate("confirm")
            check("Chikorita", True, 3, 0)
            for scope in ("full251", "kanto"):
                close_review()
                page.goto(url + "/settings/")
                page.get_by_label("Source", exact=True).select_option(fixture["sources"]["second"])
                page.get_by_label("Replacement scope", exact=True).select_option(scope)
                preview_click(
                    lambda: page.get_by_role("button", name="Preview source replacement", exact=True).click(),
                    "source replacement " + scope,
                )
                mutate("confirm")
                check("Ivysaur", False, None, 1)
                check("Bulbasaur", False, None, 0)
                check("Venusaur", True, None, 0)
                check("Chikorita", scope == "kanto", 3 if scope == "kanto" else None, 0)
                mutate("undo")
                check("Ivysaur", True, None, 1)
                check("Bulbasaur", True, None, 0)
                check("Chikorita", True, 3, 0)
            passed(
                "full and explicitly scoped source preview/confirm/undo; Kanto replacement preserves Johto ownership and total"
            )

            page.set_viewport_size(dict(width=320, height=740))
            visit("synthetic-bulbasaur")
            page.locator("#edit-group-card").click()
            page.get_by_label("Change", exact=True).select_option("card_quantity")
            for invalid in ("0", "1.5", "-1"):
                page.get_by_label("Total quantity", exact=True).fill(invalid)
                page.get_by_role("button", name="Preview collection change", exact=True).click()
                expect(page.locator("#review")).not_to_be_visible()
                assert not page.locator("#total-quantity").evaluate("input => input.checkValidity()")
            page.get_by_label("Total quantity", exact=True).fill("2")
            fits("320px card editor", "#editor")
            page.screenshot(path=str(output / "narrow-collection-editor.png"), full_page=True)
            preview_click(
                lambda: page.get_by_role("button", name="Preview collection change", exact=True).press(
                    "Enter"
                ),
                "320px keyboard total preview",
            )
            path = keyboard_path("#review")
            assert any(item["id"] == "confirm" for item in path), path
            fits("320px quantity review", "#review")
            page.screenshot(path=str(output / "narrow-quantity-review.png"), full_page=True)
            mutate("confirm")
            check("Ivysaur", True, 2, 1)
            mutate("undo")
            check("Ivysaur", True, None, 1)
            passed(
                "320px editor/review fit; invalid total blocked; keyboard preview and modal focus; confirmation/undo"
            )

            close_review()
            page.goto(url + "/settings/")
            expect(page.locator("#select-source")).to_be_visible()
            fits("320px Settings source form")
            page.get_by_label("Source", exact=True).select_option(fixture["sources"]["second"])
            page.get_by_label("Replacement scope", exact=True).select_option("kanto")
            preview_click(
                lambda: page.get_by_role("button", name="Preview source replacement", exact=True).press(
                    "Enter"
                ),
                "320px source replacement",
            )
            fits("320px source review", "#review")
            page.screenshot(path=str(output / "narrow-source-review.png"), full_page=True)
            mutate("confirm")
            check("Chikorita", True, 3, 0)
            mutate("undo")
            check("Ivysaur", True, None, 1)
            close_review()
            page.goto(url + "/collection/")
            expect(page.locator("#edit-owned-card")).to_be_visible()
            fits("320px collection ownership adapter")
            page.locator("#edit-group-card").click()
            fits("320px owned-card editor", "#editor")
            page.keyboard.press("Escape")
            page.get_by_role("button", name="Add a physical copy", exact=True).click()
            page.get_by_label("Name or collector number", exact=True).fill("Bulbasaur")
            page.get_by_role("button", name="Search catalog", exact=True).click()
            expect(page.locator("[data-card-intent]")).to_have_count(1)
            fits("320px catalog ownership adapter")
            page.locator("[data-card-intent]").press("Enter")
            fits("320px catalog-card editor", "#editor")
            expect(page.locator("#editor-body")).to_contain_text("Bulbasaur #67")
            page.keyboard.press("Escape")
            passed(
                "320px Settings source preview/confirm/undo, current-owned and catalog editor adapters fit and work by keyboard"
            )

            stable_goal_fields = ("id", "user_id", "name", "kind", "definition", "revision", "version")

            def frozen_goals(goals):
                return [{key: goal.get(key) for key in stable_goal_fields} for goal in goals]

            assert frozen_goals(state()["goals"]) == frozen_goals(fixture["initial_goals"]), (
                "Editor changed frozen goal definitions"
            )
            assert not page_errors, page_errors
            assert all(
                request["blocked"] and request["resource_type"] == "image" for request in external_requests
            ), external_requests
            passed(
                "frozen goals unchanged; zero browser script errors; all external image attempts blocked before network acquisition"
            )
        except Exception:
            page.screenshot(path=str(output / "failure.png"), full_page=True)
            (output / "failure.html").write_text(page.content())
            report["failure_layout"] = page.evaluate(
                """() => ({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,
                    overflowing:[...document.querySelectorAll('body *')].filter(e=>{
                        const rect=e.getBoundingClientRect();return rect.width>0&&rect.right>innerWidth;
                    }).map(e=>({tag:e.tagName,id:e.id,class:e.className,
                        right:e.getBoundingClientRect().right,width:e.getBoundingClientRect().width}))})"""
            )
            raise
        finally:
            report["page_errors"] = page_errors
            report["blocked_external_requests"] = external_requests
            (output / "operations.json").write_text(json.dumps(operations, indent=2, sort_keys=True) + "\n")
            context.tracing.stop(path=str(output / "trace.zip"))
            browser.close()


if __name__ == "__main__":
    main()
