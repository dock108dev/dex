"""Check canonical card-group routes on disposable engineering state.

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
    (root / "B4_ISOLATED").write_text("Disposable CX-03 publication fixture only\n")
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


def persisted_snapshot(root):
    """Complete SQLite content plus independent protected file hashes; no writes."""
    databases = {}
    for path in sorted(root.rglob("*.db")):
        with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
            schema = list(db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name"))
            tables = {}
            for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
                quoted = '"' + name.replace('"', '""') + '"'
                rows = list(db.execute("SELECT * FROM " + quoted))
                normalized = [
                    [dict(blob_hex=value.hex()) if isinstance(value, bytes) else value for value in row]
                    for row in rows
                ]
                tables[name] = hashlib.sha256(
                    json.dumps(sorted(normalized, key=repr), sort_keys=True).encode()
                ).hexdigest()
            databases[str(path.relative_to(root))] = dict(
                schema_sha256=hashlib.sha256(json.dumps(schema).encode()).hexdigest(), tables=tables
            )
    files = {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.suffix != ".db" and not path.name.endswith(("-wal", "-shm", "-journal"))
    }
    return dict(databases=databases, protected_files=files)


def exercise(url, root, output, fixture, report):
    from playwright.sync_api import expect, sync_playwright
    from qualify_shopping import PASSWORD

    external, errors = [], []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        report["browser_version"] = browser.version
        context = browser.new_context(viewport=dict(width=1280, height=900))
        context.tracing.start(screenshots=True, snapshots=True, sources=False)

        def restrict(route):
            if route.request.url.startswith(url + "/"):
                route.continue_()
            else:
                external.append(
                    dict(url=route.request.url, resource_type=route.request.resource_type, blocked=True)
                )
                route.abort()

        context.route("**/*", restrict)
        page = context.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))

        def get(path, status=200):
            response = context.request.get(url + path)
            assert response.status == status, (path, response.status, response.text())
            return response.json() if status == 200 else response

        def passed(name):
            report["checks"].append(dict(check=name, passed=True))

        try:
            page.goto(url + "/login/?next=/collection/")
            page.get_by_label("Username:", exact=True).fill("admin")
            page.get_by_label("Password:", exact=True).fill(PASSWORD)
            page.get_by_role("button", name="Sign in", exact=True).click()
            expect(page.locator("#content")).not_to_contain_text("Loading your collection")
            catalog = get("/api/card-groups/")
            group = next(row for row in catalog["groups"] if row["name"] == "Ivysaur")
            group_id = group["id"]
            assert group_id.startswith("dg1-"), group_id
            path = "/card-groups/" + group_id + "/"
            selected = path + "?child=" + fixture["selected_printing"]
            detail = get("/api/card-groups/" + group_id + "/?child=" + fixture["selected_printing"])
            assert detail["selected_child"]["id"] == fixture["selected_printing"], detail
            page.goto(url + selected)
            expect(page.locator("#content h1")).to_have_text("Ivysaur")
            expect(page.locator("#group-selected")).to_have_attribute(
                "data-selected-child", fixture["selected_printing"]
            )
            page.reload()
            expect(page.locator("#group-selected")).to_have_attribute(
                "data-selected-child", fixture["selected_printing"]
            )
            page.screenshot(path=str(output / "canonical-selected-child.png"), full_page=True)
            passed("direct canonical URL and refresh preserve selected variant")

            original_collection = get("/api/collection/")["effective_collection"]
            page.get_by_role("button", name="Edit collection", exact=True).click()
            page.get_by_label("Change", exact=True).select_option("card_quantity")
            page.get_by_label("Total quantity", exact=True).fill("2")
            with page.expect_response(
                lambda response: response.url == url + "/api/card-groups/" + group_id + "/preview/"
            ) as pending:
                page.get_by_role("button", name="Preview collection change", exact=True).click()
            response = pending.value
            assert response.status == 200, response.text()
            operation = response.json()
            assert not operation["plan"]["errors"], operation["plan"]
            assert operation["request"] == dict(
                set_name=group["set_name"],
                name=group["name"],
                number=group["collector_number"],
                language=group["language"],
                established_total_quantity=2,
            ), operation
            assert get("/api/collection/")["effective_collection"] == original_collection
            expect(page.locator("#review")).to_be_visible()
            page.get_by_role("button", name="Close review", exact=True).click()
            passed(
                "selected-child collection editor previews the authoritative literal scope without ownership mutation"
            )

            for key in (fixture["selected_printing"], fixture["selected_alias"]):
                page.goto(url + "/cards/" + key + "/")
                expect(page).to_have_url(url + selected)
                expect(page.locator("#group-selected")).to_have_attribute(
                    "data-selected-child", fixture["selected_printing"]
                )
            passed("legacy printing and alias routes redirect to canonical selected-child destination")

            archived_path = path + "?child=" + fixture["archived_printing"]
            page.goto(url + archived_path)
            expect(page.locator("#group-selected")).to_have_attribute(
                "data-selected-child", fixture["archived_printing"]
            )
            expect(page.locator("#group-selected")).to_contain_text("Archived or unavailable")
            page.reload()
            expect(page.locator("#group-selected")).to_have_attribute(
                "data-selected-child", fixture["archived_printing"]
            )
            get("/api/public/card-groups/" + group_id + "/?child=" + fixture["archived_printing"], 404)
            passed(
                "owned archived selected child remains identified privately and absent from public projection"
            )

            for child in (fixture["foreign_printing"], "unknown-printing"):
                get("/api/card-groups/" + group_id + "/?child=" + child, 404)
                assert page.goto(url + path + "?child=" + child).status == 404
            assert page.goto(url + "/cards/" + fixture["ambiguous_alias"] + "/").status == 409
            assert page.goto(url + "/cards/cx03-browser-unknown/").status == 404
            passed("foreign/unknown children rejected; duplicate aliases conflict; unknown alias absent")

            page.goto(url + "/cards/")
            expect(page.locator("#content")).not_to_contain_text("Loading your collection")
            links = page.locator(".owned-card-tile")
            expect(links.first).to_be_visible()
            assert links.count(), "Ordinary card browsing has no detail destination"
            links.first.click()
            expect(page.locator("#group-variants")).to_be_visible()
            passed("ordinary card browsing reaches canonical group detail through compatible destinations")

            before = persisted_snapshot(root)
            for _ in range(3):
                get("/api/card-groups/")
                get("/api/my-card-groups/")
                get("/api/card-groups/" + group_id + "/")
                get("/api/card-groups/" + group_id + "/?child=" + fixture["selected_printing"])
                get("/api/public/card-groups/")
                get("/api/public/card-groups/" + group_id + "/")
                page.goto(url + selected)
                expect(page.locator("#group-variants")).to_be_visible()
                page.goto(url + "/cards/" + fixture["selected_alias"] + "/")
                expect(page.locator("#group-variants")).to_be_visible()
            after = persisted_snapshot(root)
            (output / "read-preservation.json").write_text(
                json.dumps(dict(before=before, after=after, equal=before == after), indent=2, sort_keys=True)
                + "\n"
            )
            assert before == after, "Repeated read requests changed persisted state or protected evidence"
            passed(
                "repeated APIs and route resolution preserve complete database tables/schema and protected files"
            )
            report["auth_boundary"] = (
                "Snapshots after ordinary sign-in; sign-in session creation excluded from GET audit"
            )
        finally:
            report["external_requests"] = external
            report["page_errors"] = errors
            context.tracing.stop(path=str(output / "trace.zip"))
            browser.close()
        assert all(
            item["blocked"]
            and item["resource_type"] == "image"
            and item["url"].startswith("https://assets.tcgdex.net/")
            for item in external
        ), external
        assert not errors, errors
        report["blocked_inherited_images"] = len(external)
        passed(
            "all external assets blocked before network; no provider or script requests and no browser errors"
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
        "scripts/verify_cx03.py",
    ]
    report["source_hashes"] = {
        name: hashlib.sha256((PROJECT / name).read_bytes()).hexdigest() for name in files
    }
    try:
        with tempfile.TemporaryDirectory(prefix="dex-cx03-browser-") as temporary:
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
