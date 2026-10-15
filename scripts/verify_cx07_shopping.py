"""navigation and contextual Shopping isolated Shopping drafts, request races and controlled lifecycle journeys.

Real loopback sign-in/server/SQLite; controlled response cells are engineering
replays only and never qualify source admission or customer installation behavior.
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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import urlopen

from verify_cx07 import PROJECT, free_port, persisted_snapshot, prepare

SOURCE_FILES = [
    "scripts/verify_cx07_shopping.py",
    "src/pokemon_hunter/beta/shopping_views.py",
    "src/pokemon_hunter/beta/shopping_context.py",
    "src/pokemon_hunter/beta/static/lot_calculator.js",
    "src/pokemon_hunter/beta/static/navigation.js",
    "src/pokemon_hunter/beta/templates/beta/lot_calculator.html",
    "src/pokemon_hunter/beta/lot_calculator.py",
    "src/pokemon_hunter/beta/lot_guides.py",
]


def exercise(url, root, output, fixture, report):
    from playwright.sync_api import Error, expect, sync_playwright
    from qualify_shopping import PASSWORD

    errors, posts, external, held = [], [], [], []
    mode = "ordinary"
    expires_at = None
    controlled_source = "a" * 64
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        report["browser_version"] = browser.version
        context = browser.new_context(viewport=dict(width=1280, height=900))
        context.tracing.start(screenshots=True, snapshots=True, sources=False)

        def restrict(route):
            request = route.request
            if not request.url.startswith(url + "/"):
                assert request.resource_type == "image", request.url
                external.append(dict(url=request.url, sent=False))
                route.fulfill(status=404, body="Controlled engineering asset failure")
                return
            if request.method == "POST":
                posts.append(dict(url=request.url, body=request.post_data))
            path = urlsplit(request.url).path
            query = parse_qs(urlsplit(request.url).query)
            if path == "/api/shopping/lot-compare/" and mode == "delay-comparison":
                response = route.fetch()
                assert response.ok, response.text()
                held.append((route, response.json(), path))
                return
            if path == "/api/shopping/lot-catalog/":
                if mode == "delay-catalog" and query.get("q") == ["Old intent"]:
                    response = route.fetch()
                    data = response.json()
                    data["cards"] = [
                        dict(
                            id="old-engineering-response",
                            name="OLD STALE CATALOG RESPONSE",
                            set_name="Base Set",
                            collector_number="99",
                            cells={},
                            price_reasons={},
                        )
                    ]
                    data["total"] = 1
                    held.append((route, data, path))
                    return
                if mode in {
                    "available",
                    "expiry",
                    "withdrawal",
                    "stale-status",
                    "wrong-authority",
                    "missing-authority",
                }:
                    response = route.fetch()
                    assert response.ok, response.text()
                    data = response.json()
                    if mode == "missing-authority":
                        data.pop("authority", None)
                    elif mode == "wrong-authority":
                        data["authority"]["binding"] = "foreign-auth-session"
                    else:
                        for row in data["cards"]:
                            if row["id"] == fixture["base_printing"]:
                                row["cells"] = dict(
                                    raw=dict(
                                        kind="guide",
                                        amount="17.25",
                                        as_of="2026-10-14",
                                        grader=None,
                                        match_status="conditional",
                                        assumptions=[
                                            "Fabricated engineering response; no source admission claim"
                                        ],
                                        source_url="https://example.test/engineering-reference",
                                        snapshot_version="cx07-engineering-lifecycle-v1",
                                        source_contract=controlled_source,
                                        expires_at=expires_at,
                                        raw_record=dict(engineering_only=True),
                                    )
                                )
                    route.fulfill(
                        status=response.status, content_type="application/json", body=json.dumps(data)
                    )
                    return
            if path == "/api/shopping/price-source-status/" and mode in {
                "available",
                "expiry",
                "withdrawal",
                "stale-status",
            }:
                response = route.fetch()
                assert response.ok, response.text()
                data = response.json()
                if mode == "stale-status":
                    route.fulfill(
                        status=409,
                        content_type="application/json",
                        body=json.dumps(dict(error="Controlled changed-generation response")),
                    )
                else:
                    data.update(
                        sources=[] if mode == "withdrawal" else [controlled_source],
                        versions=[] if mode == "withdrawal" else ["cx07-engineering-lifecycle-v1"],
                    )
                    route.fulfill(status=200, content_type="application/json", body=json.dumps(data))
                return
            route.continue_()

        context.route("**/*", restrict)
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))

        def passed(name, evidence="ordinary isolated loopback browser"):
            report["checks"].append(dict(check=name, passed=True, evidence_class=evidence))

        def load(path="/shopping/?species=2"):
            page.goto(url + path)
            expect(page.locator("#clear-lot")).to_be_enabled()

        def row(identity=None):
            return page.locator(
                "#selections .selection" + (f'[data-printing="{identity}"]' if identity else "")
            ).first

        def draft():
            data = page.evaluate("""() => {
              const key=Object.keys(sessionStorage).find(k=>k.startsWith('dex-shopping-draft-v1:'));
              return {key, value:key?JSON.parse(sessionStorage.getItem(key)):null};
            }""")
            assert data["key"] and data["value"]
            return data

        def store(data):
            page.evaluate(
                "data => {window.dispatchEvent(new Event('pagehide'));sessionStorage.setItem(data.key, typeof data.value==='string'?data.value:JSON.stringify(data.value));}",
                data,
            )

        def no_restricted_fields(value):
            forbidden = {
                "cells",
                "sources",
                "source_url",
                "source_contract",
                "snapshot_version",
                "raw_record",
                "price_reasons",
                "scenarios",
                "references",
                "results",
                "total",
                "full_selected_total",
                "known_selected_subtotal",
                "reference_sum",
                "evaluations",
                "derivatives",
            }
            if isinstance(value, dict):
                assert not forbidden.intersection(value), sorted(forbidden.intersection(value))
                for item in value.values():
                    no_restricted_fields(item)
            elif isinstance(value, list):
                for item in value:
                    no_restricted_fields(item)

        def open_costs():
            page.locator(".lot-options").filter(has=page.locator("#costs")).evaluate(
                "element => element.open=true"
            )

        def assert_inputs(included="2", wanted="5", locked=True, amount="12.00"):
            selected = row(fixture["base_printing"])
            expect(selected.get_by_label("In this lot", exact=True)).to_have_value(included)
            expect(selected.get_by_label("Wanted quantity", exact=True)).to_have_value(wanted)
            if locked:
                expect(selected.get_by_label("Lock wanted card", exact=True)).to_be_checked()
            else:
                expect(selected.get_by_label("Lock wanted card", exact=True)).not_to_be_checked()
            expect(page.locator("#lot-price")).to_have_value(amount)

        def screenshot(name):
            page.screenshot(path=str(output / ("engineering-shopping-" + name + ".png")), full_page=True)

        try:
            page.goto(url + "/login/?" + urlencode({"next": "/shopping/?species=2&return=/pokedex/2/"}))
            page.get_by_label("Username:", exact=True).fill("admin")
            page.get_by_label("Password:", exact=True).fill(PASSWORD)
            page.get_by_role("button", name="Sign in", exact=True).click()
            expect(page.locator("#clear-lot")).to_be_enabled()
            before = persisted_snapshot(root)
            count = len(posts)
            expect(page.locator("#printing-choice")).to_have_value("")
            expect(page.locator("#selections .selection")).to_have_count(0)
            expect(page.locator("#context-label")).to_contain_text("Ivysaur")
            assert len(posts) == count and persisted_snapshot(root) == before
            page.locator("#printing-choice").select_option(fixture["base_printing"])
            expect(page.locator("#cards button").filter(has_text="Add to lot")).to_be_visible()
            page.reload()
            expect(page.locator("#clear-lot")).to_be_enabled()
            expect(page.locator("#printing-choice")).to_have_value(fixture["base_printing"])
            expect(page.locator("#selections .selection")).to_have_count(0)
            assert len(posts) == count and persisted_snapshot(root) == before
            passed("context printing choice survives same-target reload without lot or session mutation")

            # Explicit picker scope changes must replace every active scope label,
            # while the original return target remains a separate entry context.
            count = len(posts)
            before = persisted_snapshot(root)
            page.get_by_role("button", name="All cards", exact=True).click()
            expect(page.locator("#context-label")).to_contain_text("Vintage cards")
            expect(page.locator("#context-current-status")).to_be_hidden()
            expect(page.locator("#context-goal-progress")).to_be_hidden()
            expect(page.locator("#context-entry-origin")).to_contain_text(
                "Opened from: Finding cards for Ivysaur"
            )
            expect(page.locator("#catalog-scope")).to_be_visible()
            expect(page.locator("#catalog-scope")).to_contain_text("Owned cards remain selectable")
            page.locator("#show-missing").click()
            selected_goal_name = page.locator("#missing-goal option:checked").inner_text()
            expect(page.locator("#context-label")).to_contain_text("Saved goal: " + selected_goal_name)
            page.locator("details.goal-choice").evaluate("element => element.open=true")
            exact_goal = next(
                goal for goal in fixture["initial_goals"] if goal["definition"]["policy"] == "exact"
            )
            page.locator("#missing-goal").select_option(exact_goal["id"])
            expect(page.locator("#context-label")).to_contain_text("Saved goal: " + exact_goal["name"])
            expect(page.locator("#context-goal-progress")).to_contain_text(
                "printings · Frozen printing membership"
            )
            expect(page.locator("#context-current-status")).to_be_hidden()
            expect(page.locator("#catalog-scope")).to_contain_text(exact_goal["name"])
            species_goal = next(
                goal for goal in fixture["initial_goals"] if goal["definition"]["policy"] == "species"
            )
            page.locator("#missing-goal").select_option(species_goal["id"])
            expect(page.locator("#context-label")).to_contain_text("Saved goal: " + species_goal["name"])
            expect(page.locator("#context-goal-progress")).to_contain_text(
                "species · Frozen species membership"
            )
            expect(page.locator("#shopping-return")).to_have_attribute("href", "/pokedex/2/")
            assert len(posts) == count and persisted_snapshot(root) == before
            passed(
                "species to All cards, Missing and changed printing/species goals update active labels and policy units; original Back context retained without POST"
            )
            load()
            page.locator("#printing-choice").select_option(fixture["base_printing"])
            expect(page.locator("#cards button").filter(has_text="Add to lot")).to_be_visible()
            page.locator("#cards button").filter(has_text="Add to lot").click()
            selected = row(fixture["base_printing"])
            selected.get_by_label("In this lot", exact=True).fill("2")
            selected.get_by_label("Wanted quantity", exact=True).fill("5")
            with page.expect_response(
                lambda response: (
                    response.url.endswith("/api/shopping/wants/") and response.request.method == "POST"
                )
            ) as lock_response:
                selected.get_by_label("Lock wanted card", exact=True).check()
            assert lock_response.value.ok
            expect(selected.get_by_label("Lock wanted card", exact=True)).to_be_enabled()
            page.locator("#lot-price").fill("12.00")
            open_costs()
            page.locator("#listing-url").fill("https://www.ebay.com/itm/987654321")
            page.get_by_label("Lot delivery costs: Shipping, USD", exact=True).fill("1.25")
            page.get_by_label("Lot delivery costs: Other costs, USD", exact=True).fill("0")
            page.get_by_label("Planned bid, USD", exact=True).fill("8.00")
            page.locator("#lot-price").focus()
            page.reload()
            expect(page.locator("#clear-lot")).to_be_enabled()
            assert_inputs()
            expect(page.get_by_label("Lot delivery costs: Shipping, USD", exact=True)).to_have_value("1.25")
            expect(page.get_by_label("Lot delivery costs: Tax, USD", exact=True)).to_have_value("")
            expect(page.get_by_label("Lot delivery costs: Other costs, USD", exact=True)).to_have_value("0")
            expect(page.get_by_label("Planned bid, USD", exact=True)).to_have_value("8.00")
            no_restricted_fields(draft()["value"])
            passed(
                "explicit Add and Lock keep included quantity, independent wanted quantity, costs and unknown tax through reload"
            )

            before = persisted_snapshot(root)
            count = len(posts)
            saved = draft()
            saved["value"]["rows"].append(
                dict(id="cx07-missing-printing", included="4", wanted="6", locked=False)
            )
            store(saved)
            page.reload()
            expect(page.locator("#clear-lot")).to_be_enabled()
            absent = row("cx07-missing-printing")
            expect(absent).to_contain_text("Unavailable printing")
            expect(absent.get_by_label("In this lot", exact=True)).to_have_value("4")
            expect(absent.get_by_label("Wanted quantity", exact=True)).to_have_value("6")
            assert_inputs()
            assert "17.25" not in absent.inner_text()
            assert len(posts) == count and persisted_snapshot(root) == before
            no_restricted_fields(draft()["value"])
            screenshot("missing-printing-inputs")
            passed(
                "missing draft reference remains unavailable with authored included/wanted inputs; fresh GET restore produces no POST"
            )

            saved = draft()
            saved["value"]["rows"] = [
                item for item in saved["value"]["rows"] if item["id"] != "cx07-missing-printing"
            ]
            saved["value"]["rows"][0]["wanted"] = "9"
            store(saved)
            page.reload()
            expect(page.locator("#clear-lot")).to_be_enabled()
            assert_inputs(wanted="9")
            expect(page.locator("#draft-wants-note")).to_contain_text("differ from this session")
            assert len(posts) == count and persisted_snapshot(root) == before
            with page.expect_response(
                lambda response: response.url.endswith("/api/shopping/wants/")
            ) as confirm_response:
                page.get_by_role("button", name="Confirm wanted targets", exact=True).click()
            assert confirm_response.value.ok
            expect(page.locator("#draft-wants-note")).to_be_hidden()
            session = context.request.get(url + "/api/shopping/lot-catalog/?wanted=1")
            assert session.ok
            page.reload()
            expect(page.locator("#clear-lot")).to_be_enabled()
            assert_inputs(wanted="9")
            expect(page.locator("#draft-wants-note")).to_be_hidden()
            passed(
                "divergent wanted draft restores independent local choice without POST; explicit confirmation applies session target"
            )

            before = persisted_snapshot(root)
            count = len(posts)
            saved = draft()
            saved["value"]["rows"][0].update(locked=False, wanted="11")
            store(saved)
            page.reload()
            expect(page.locator("#clear-lot")).to_be_enabled()
            assert_inputs(wanted="11", locked=False)
            expect(page.locator("#draft-wants-note")).to_be_visible()
            assert len(posts) == count and persisted_snapshot(root) == before
            with page.expect_response(
                lambda response: response.url.endswith("/api/shopping/wants/")
            ) as unlock_response:
                page.get_by_role("button", name="Confirm wanted targets", exact=True).click()
            assert unlock_response.value.ok
            assert unlock_response.value.json()["wants"] == []
            expect(page.locator("#draft-wants-note")).to_be_hidden()
            # Only this explicit existing Lock action restores the session target.
            selected = row(fixture["base_printing"])
            selected.get_by_label("Wanted quantity", exact=True).fill("9")
            with page.expect_response(
                lambda response: response.url.endswith("/api/shopping/wants/")
            ) as relock_response:
                selected.get_by_label("Lock wanted card", exact=True).check()
            assert relock_response.value.ok
            expect(selected.get_by_label("Lock wanted card", exact=True)).to_be_enabled()
            assert_inputs(wanted="9")
            passed(
                "divergent draft lock checkbox and wanted quantity remain independent; explicit confirmation and relock alone alter session wants"
            )

            saved = draft()
            for corrupt in ("{broken", dict(saved["value"], cells={"raw": {"amount": "999"}})):
                store(dict(key=saved["key"], value=corrupt))
                count = len(posts)
                page.reload()
                expect(page.locator("#clear-lot")).to_be_enabled()
                assert_inputs(included="0", wanted="9", amount="")
                assert len(posts) == count
                no_restricted_fields(draft()["value"])
            passed(
                "corrupt or out-of-allowlist draft rejected safely; confirmed session wants remain with zero lot inclusion"
            )

            selected = row(fixture["base_printing"])
            selected.get_by_label("In this lot", exact=True).fill("2")
            page.locator("#lot-price").fill("12.00")
            count = len(posts)
            before = persisted_snapshot(root)
            load("/shopping/?species=1")
            assert_inputs(wanted="9")
            expect(page.locator("#context-label")).to_contain_text("Bulbasaur")
            if page.locator("#printing-choice").count():
                expect(page.locator("#printing-choice")).to_have_value("")
            expect(page.locator("#results")).to_be_hidden()
            assert len(posts) == count and persisted_snapshot(root) == before
            passed(
                "different incoming species replaces retained picker intent while preserving independent lot rows and costs"
            )

            load()
            mode = "delay-catalog"
            page.locator("#query").fill("Old intent")
            page.locator("#lookup button").click()
            page.wait_for_timeout(100)
            assert held
            expect(page.locator("#cards button")).to_have_count(0)
            expect(page.locator("#catalog-scope")).to_contain_text("Loading cards")
            page.locator("#query").fill("Ivysaur")
            page.locator("#lookup button").click()
            expect(page.locator("#printing-choice")).to_be_visible()
            pending, data, _ = held.pop()
            pending.fulfill(status=200, content_type="application/json", body=json.dumps(data))
            page.wait_for_timeout(100)
            expect(page.locator("#query")).to_have_value("Ivysaur")
            expect(page.locator("body")).not_to_contain_text("OLD STALE CATALOG RESPONSE")
            mode = "ordinary"
            passed("delayed catalog reply cannot replace newer picker inputs or result")

            with page.expect_response(
                lambda response: response.url.endswith("/api/shopping/lot-compare/")
            ) as compare_response:
                page.get_by_role("button", name="Compare", exact=True).click()
            assert compare_response.value.ok, compare_response.value.text()
            expect(page.locator("#results")).to_be_visible()
            result = compare_response.value.json()
            assert all(
                value["result"]["coverage"]["selected_units"] == 2 for value in result["scenarios"].values()
            )
            assert result["request"]["cards"][0]["quantity"] == 2
            passed("explicit Compare retains four independent server scenarios and included-unit arithmetic")
            mode = "delay-comparison"
            page.get_by_role("button", name="Compare", exact=True).click()
            page.wait_for_timeout(100)
            assert held
            page.get_by_role("link", name="My Cards", exact=True).click()
            expect(page.locator("#content h1")).to_contain_text("My Cards")
            pending, data, _ = held.pop()
            try:
                pending.fulfill(status=200, content_type="application/json", body=json.dumps(data))
            except Error as error:
                report.setdefault("cancelled_route_results", []).append(str(error))
            page.wait_for_timeout(100)
            expect(page.locator("#content h1")).to_contain_text("My Cards")
            assert not page.locator("#summary").count()
            mode = "ordinary"
            load()
            assert_inputs(wanted="9")
            expect(page.locator("#results")).to_be_hidden()
            passed(
                "late non-saving comparison after route departure cannot update another screen or discard retained input draft"
            )

            mode = "available"
            expires_at = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
            page.reload()
            expect(page.locator("#clear-lot")).to_be_enabled()
            expect(row(fixture["base_printing"])).to_contain_text("$17.25")
            no_restricted_fields(draft()["value"])
            mode = "withdrawal"
            expect(row(fixture["base_printing"])).not_to_contain_text("$17.25", timeout=5000)
            expect(row(fixture["base_printing"])).to_contain_text("Source removed")
            assert_inputs(wanted="9")
            expect(page.locator("#results")).to_be_hidden()
            no_restricted_fields(draft()["value"])
            passed(
                "local source withdrawal removes controlled current references without changing draft inputs",
                "controlled engineering response replay; source policy qualified separately by native tests",
            )

            mode = "available"
            page.reload()
            expect(row(fixture["base_printing"])).to_contain_text("$17.25")
            mode = "stale-status"
            expect(row(fixture["base_printing"])).not_to_contain_text("$17.25", timeout=5000)
            expect(page.locator("#context-label")).to_contain_text("Collection or saved goal changed")
            assert_inputs(wanted="9")
            no_restricted_fields(draft()["value"])
            screenshot("stale-context-reference-erasure")
            passed(
                "changed-generation status conflict scrubs current references and derivatives rather than blocking lifecycle cleanup",
                "controlled engineering 409 response replay",
            )

            mode = "expiry"
            expires_at = (datetime.now(timezone.utc) + timedelta(seconds=2)).isoformat()
            page.reload()
            expect(row(fixture["base_printing"])).to_contain_text("$17.25")
            expect(row(fixture["base_printing"])).not_to_contain_text("$17.25", timeout=6000)
            expect(row(fixture["base_printing"])).to_contain_text("Snapshot expired")
            assert_inputs(wanted="9")
            no_restricted_fields(draft()["value"])
            passed(
                "controlled reference expiry timer removes price/source derivatives while preserving user costs and independent quantities",
                "controlled engineering expiring-reference response replay",
            )

            mode = "ordinary"
            page.reload()
            expect(page.locator("#clear-lot")).to_be_enabled()
            with page.expect_response(
                lambda response: response.url.endswith("/api/shopping/wants/")
            ) as clear_response:
                page.get_by_role("button", name="Clear lot", exact=True).click()
            assert clear_response.value.ok
            expect(page.locator("#clear-lot")).to_be_enabled()
            assert_inputs(included="0", wanted="9", amount="")
            expect(page.locator("#listing-url")).to_have_value("")
            expect(page.locator("#results")).to_be_hidden()
            passed(
                "explicit Clear resets included units and costs while retaining confirmed wanted quantity and lock"
            )

            mode = "missing-authority"
            page.locator("#query").fill("Ivysaur")
            page.locator("#lookup button").click()
            expect(page.locator("#status")).to_contain_text("Sign in again")
            expect(page.locator("#selections .selection")).to_have_count(0)
            assert not page.evaluate(
                "() => Object.keys(sessionStorage).some(key=>key.startsWith('dex-shopping-draft-v1:'))"
            )
            passed(
                "missing authority metadata fails closed and discards private UI rather than relying on optional account fields"
            )
            mode = "ordinary"
            page.reload()
            expect(page.locator("#clear-lot")).to_be_enabled()
            assert_inputs(included="0", wanted="9", amount="")
            mode = "wrong-authority"
            page.locator("#query").fill("Ivysaur")
            page.locator("#lookup button").click()
            expect(page.locator("#status")).to_contain_text("Sign in again")
            expect(page.locator("#selections .selection")).to_have_count(0)
            expect(page.locator("#lot-price")).to_have_value("")
            assert not page.evaluate(
                "() => Object.keys(sessionStorage).some(key=>key.startsWith('dex-shopping-draft-v1:'))"
            )
            passed(
                "wrong session authority response discards private lot display and input draft rather than rendering another account/session"
            )
            assert not errors, errors
            report.update(
                external_requests_sent=0,
                controlled_external_assets=external,
                captured_history_evidence="Native Shopping history suite; this replay does not fabricate save rights or current child source observations",
            )
        finally:
            context.tracing.stop(path=str(output / "shopping-trace.zip"))
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
        evidence_class="isolated engineering Shopping browser; ordinary sign-in and real SQLite; controlled response replays labelled individually",
        customer_installation_accessed=False,
        checks=[],
    )
    report["source_hashes"] = {
        name: hashlib.sha256((PROJECT / name).read_bytes()).hexdigest() for name in SOURCE_FILES
    }
    try:
        with tempfile.TemporaryDirectory(prefix="dex-cx07-shopping-") as temporary:
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
            assert json.loads((args.output / "provider-calls.json").read_text())["calls"] == 0
            report["provider_calls"] = 0
            assert report["source_hashes"] == {
                name: hashlib.sha256((PROJECT / name).read_bytes()).hexdigest() for name in SOURCE_FILES
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
