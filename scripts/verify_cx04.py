"""Check artwork roles and fallback routes on disposable engineering state.

Uses real loopback HTTP, Chromium and SQLite, blocks external requests and
provider acquisition, and never reads or changes the customer installation.
This helper exercises a focused contract. Integrated journeys are maintained in
scripts/ci/browser.py.
"""

import argparse
import hashlib
import json
import os
import sqlite3
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
    from verify_cx02 import prepare as prepare_collection

    prepare_collection(root, source, output)
    from django.conf import settings
    from django.db import connection

    from pokemon_hunter.beta import catalog_imports

    connection.close()
    with sqlite3.connect(root / "inventory.db") as db:
        catalog_imports.initialize(db)
    (root / "B4_ISOLATED").write_text("Disposable CX-04 publication fixture only\n")
    settings.B4_ENABLED = True
    with sqlite3.connect(root / "inventory.db") as db:
        db.row_factory = sqlite3.Row
        entries = [dict(row) for row in db.execute("SELECT * FROM printings")]
        original = next(
            row for row in entries if json.loads(row["provenance"]).get("legacy_id") == "synthetic-bulbasaur"
        )
        variant = dict(original)
        variant.update(
            id="cx03-browser-ivysaur-first",
            edition="first_edition",
            finish="holo",
            variant="first-edition-holo",
            unresolved_fields="[]",
            provenance=json.dumps(dict(legacy_id="cx03-browser-first")),
        )
        columns = list(variant)
        db.execute(
            "INSERT INTO printings ("
            + ",".join(columns)
            + ") VALUES ("
            + ",".join("?" for _ in columns)
            + ")",
            list(variant.values()),
        )
        archived = dict(variant)
        archived.update(
            id="cx03-browser-ivysaur-archived",
            edition="unlimited",
            finish="reverse-holo",
            variant="archived-reverse-holo",
            provenance=json.dumps(dict(legacy_id="cx03-browser-archived")),
            publication_state="archived",
        )
        db.execute(
            "INSERT INTO printings ("
            + ",".join(archived)
            + ") VALUES ("
            + ",".join("?" for _ in archived)
            + ")",
            list(archived.values()),
        )
        ambiguous = [row for row in entries if row["id"] != original["id"]][:2]
        for row in ambiguous:
            provenance = json.loads(row["provenance"])
            provenance["legacy_id"] = "cx03-browser-ambiguous"
            db.execute("UPDATE printings SET provenance=? WHERE id=?", (json.dumps(provenance), row["id"]))
        foreign = next(row for row in entries if row["id"] != original["id"])
    fixture = json.loads(output.read_text())
    fixture.update(
        primary_printing=original["id"],
        selected_printing=variant["id"],
        selected_alias="cx03-browser-first",
        archived_printing=archived["id"],
        foreign_printing=foreign["id"],
        ambiguous_alias="cx03-browser-ambiguous",
    )
    output.write_text(json.dumps(fixture, indent=2, sort_keys=True) + "\n")


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
            assert request.resource_type == "image"
            assert request.url.startswith(
                ("https://assets.tcgdex.net/", "https://raw.githubusercontent.com/")
            )
            headers = request.all_headers()
            assert "referer" not in headers and "cookie" not in headers and "authorization" not in headers
            requests.append(dict(url=request.url, mode=mode, sent_to_remote=False))
            if mode == "blocked":
                route.abort("blockedbyclient")
            elif mode == "failure":
                route.fulfill(status=404, content_type="text/plain", body="Controlled unavailable image")
            else:
                route.fulfill(
                    status=200,
                    content_type="image/svg+xml",
                    body='<svg xmlns="http://www.w3.org/2000/svg" width="475" height="475"><rect width="475" height="475" fill="#d8e4da"/></svg>',
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

        try:
            page.goto(url + "/login/?next=/collection/")
            page.get_by_label("Username:", exact=True).fill("admin")
            page.get_by_label("Password:", exact=True).fill(PASSWORD)
            page.get_by_role("button", name="Sign in", exact=True).click()
            expect(page.locator("#content")).not_to_contain_text("Loading your collection")
            before = persisted_snapshot(root)
            collection_before = get("/api/collection/")
            group = next(row for row in get("/api/card-groups/")["groups"] if row["name"] == "Ivysaur")
            path = "/card-groups/" + group["id"] + "/"
            detail_before = get("/api/card-groups/" + group["id"] + "/")
            assert detail_before["selected_child"] is None and detail_before["selected_child_image"] is None
            assert group["reference_image"]["role"] == "card_group_reference"
            assert group["reference_image"]["image_url"].endswith("/base/base4/44/low.webp")
            passed("group reference exists without selected child, independent of possession")
            dimensions = {}
            for state in ("success", "failure", "blocked"):
                mode = state
                for width in (1280, 320):
                    page.set_viewport_size(dict(width=width, height=900))
                    page.goto(url + "/pokedex/")
                    rows = page.locator(".species-row")
                    expect(rows.first).to_be_visible()
                    frames = page.locator(".species-detail .species-artwork")
                    expect(frames.first).to_be_visible()
                    if state == "success":
                        expect(frames.first.locator("img")).to_be_visible()
                        page.wait_for_function(
                            "document.querySelector('.species-artwork img').naturalWidth > 0"
                        )
                    else:
                        expect(frames.first.locator("img")).to_be_hidden()
                        expect(frames.first).to_have_class("species-artwork image-frame compact unavailable")
                    assert page.locator(".species-detail .card-artwork").count() == 0
                    target = page.locator('[data-dex-species="2"]')
                    image = target.locator(".species-artwork")
                    box = image.bounding_box()
                    assert box["width"] >= 58 and box["height"] >= 58
                    dimensions[f"{state}-{width}"] = box
                    target.focus()
                    page.keyboard.press("Enter")
                    expect(page).to_have_url(url + "/pokedex/?species=2")
                    expect(page.locator("#content h1")).to_have_text("Ivysaur")
                    expect(page.locator("#content > .species-artwork")).to_be_visible()
                    passed(
                        f"{state} image at {width}px keeps canonical species keyboard destination and neutral space"
                    )
                    for selected in (None, fixture["selected_printing"], fixture["archived_printing"]):
                        suffix = "?child=" + selected if selected else ""
                        page.goto(url + path + suffix)
                        expect(page.locator("#content h1")).to_have_text("Ivysaur")
                        frame = page.locator(".card-detail-image > .card-artwork")
                        expect(frame).to_be_visible()
                        assert frame.bounding_box()["height"] > 200
                        if selected:
                            expect(page.locator("#group-selected")).to_have_attribute(
                                "data-selected-child", selected
                            )
                            expect(page.locator(".selected-image-status")).to_have_text(
                                "Selected variant image unavailable"
                            )
                            assert page.locator("#group-selected img").count() == 0
                        else:
                            expect(page.locator("#group-variants")).to_contain_text("No variant selected")
                        assert page.url == url + path + suffix
                    passed(
                        f"{state} image at {width}px keeps selected, archived and null child context; no sibling substitution"
                    )
                page.screenshot(path=str(output / f"engineering-{state}.png"), full_page=True)
                assert get("/api/collection/") == collection_before
                assert get("/api/card-groups/" + group["id"] + "/") == detail_before
            assert (
                dimensions["success-320"]["width"]
                == dimensions["failure-320"]["width"]
                == dimensions["blocked-320"]["width"]
            )
            assert (
                dimensions["success-320"]["height"]
                == dimensions["failure-320"]["height"]
                == dimensions["blocked-320"]["height"]
            )
            page.goto(url + "/cards/")
            expect(page.locator(".owned-card-tile").first).to_be_visible()
            target_url = page.locator(".owned-card-tile").first.get_attribute("href")
            page.locator(".owned-card-tile").first.focus()
            page.keyboard.press("Enter")
            expect(page.locator("#group-variants")).to_be_visible()
            passed("failed card image retains keyboard-accessible canonical card destination")
            page.reload()
            expect(page.locator("#group-variants")).to_be_visible()
            assert persisted_snapshot(root) == before
            (output / "read-preservation.json").write_text(
                json.dumps(dict(before=before, after=persisted_snapshot(root), equal=True), indent=2) + "\n"
            )
            report["frame_dimensions"] = dimensions
            report["ordinary_card_link"] = target_url
            passed(
                "all image modes preserve identical effective collection, quantities, exact qualification and complete persisted state"
            )
            page.goto(url + "/cards/")
            expect(
                page.locator("img[referrerpolicy='no-referrer'][loading='lazy'][decoding='async']").first
            ).to_be_attached()
            guest = browser.new_context()
            assert "reference_image" not in guest.request.get(url + "/api/public/card-groups/").text()
            guest.close()
            passed("lazy asynchronous images have no referrer; guest projections exclude private references")
            rendered = page.evaluate(
                """reference => {
                    const box=document.createElement('div');
                    const alt='Mew <img src=x onerror=alert(1)> " quoted';
                    box.innerHTML=cardImage({...reference, alt});
                    return {count:box.querySelectorAll('img').length,
                            alt:box.querySelector('img').alt,
                            injected:box.querySelector('[onerror]')!==null,
                            species:speciesImage(reference).includes('<img')};
                }""",
                group["reference_image"],
            )
            assert rendered == dict(
                count=1, alt='Mew <img src=x onerror=alert(1)> " quoted', injected=False, species=False
            )
            response = context.request.get(url + path)
            policy = response.headers["content-security-policy"]
            assert policy.count("img-src ") == 1 and "*" not in policy
            assert response.headers["cache-control"] == "private, no-store"
            passed(
                "escaped malicious alt cannot inject markup; wrong role cannot populate species; single bounded CSP"
            )
        finally:
            report["controlled_image_requests"] = requests
            report["page_errors"] = errors
            context.tracing.stop(path=str(output / "trace.zip"))
            browser.close()
        assert not errors, errors
        report["external_requests_sent"] = 0
        report["controlled_asset_note"] = (
            "Controlled neutral SVG/404/abort engineering responses only, distinct from external visual verification"
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
        deferred_CX05_CX06_journeys_qualified=False,
        checks=[],
    )
    files = [
        "src/pokemon_hunter/beta/card_groups.py",
        "src/pokemon_hunter/beta/card_group_views.py",
        "src/pokemon_hunter/beta/urls.py",
        "src/pokemon_hunter/beta/parity.py",
        "src/pokemon_hunter/beta/collection_views.py",
        "src/pokemon_hunter/beta/static/collection.js",
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
        "scripts/verify_cx04.py",
    ]
    report["source_hashes"] = {
        name: hashlib.sha256((PROJECT / name).read_bytes()).hexdigest() for name in files
    }
    try:
        with tempfile.TemporaryDirectory(prefix="dex-cx04-browser-") as temporary:
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
