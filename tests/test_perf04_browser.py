"""Full-size disposable browser qualification; never uses the customer installation."""

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer

import pytest
from runtime_process import close_pipes, read_port
from test_account_read_performance import ownership
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_catalog_read_performance import seed
from test_effective_collection import cx as cx
from test_migration import snapshot as snapshot
from test_ownership_declarations import migrate as declarations_migrate
from test_sealed_catalog import e1 as e1

from pokemon_hunter.beta import account_read_build as accounts
from pokemon_hunter.beta import account_read_schema as schema
from pokemon_hunter.beta import catalog_read_build as catalogs
from pokemon_hunter.beta.catalog_read_schema import migrate

pytestmark = pytest.mark.allow_hosts(["127.0.0.1"])


class Server(ThreadingMixIn, WSGIServer):
    daemon_threads = True
    request_queue_size = 128


class Quiet(WSGIRequestHandler):
    def log_message(self, *args):
        pass


@pytest.mark.no_cover
@pytest.mark.parametrize("scale,copies", [(33083, 5000), (66166, 10000)])
def test_full_browser(cx, scale, copies):
    from playwright.sync_api import expect, sync_playwright

    from pokemon_hunter.beta import collection_drafts

    collection_drafts.initialize()
    declarations_migrate(cx)
    seed(cx, scale)
    ownership(cx, copies)
    migrate()
    catalogs.activate(catalogs.prepare())
    schema.migrate()
    accounts.prepare(cx["actor"])
    key = cx["a"].get("/api/v2/my-card-groups/").json()["groups"][0]["id"]
    from django.conf import settings

    for marker in ("B2_ISOLATED", "B3_ISOLATED", "B4_ISOLATED"):
        (cx["root"] / marker).write_text("Engineering fixture capability\n")
    (cx["root"] / "secret.key").write_text(settings.SECRET_KEY)
    process = subprocess.Popen(
        [sys.executable, "tests/ops_server.py", str(cx["root"]), "0"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        port = read_port(process)
    except BaseException:
        process.terminate()
        process.wait(timeout=12)
        close_pipes(process)
        raise
    base = f"http://127.0.0.1:{port}"

    def candidate():
        return hashlib.sha256(
            b"".join(
                p.read_bytes()
                for p in sorted(Path("src/pokemon_hunter/beta").rglob("*"))
                if p.is_file() and p.suffix in {".py", ".js", ".css", ".html"}
            )
        ).hexdigest()

    source_hash = candidate()
    report = {
        "source_sha256": source_hash,
        "passed": False,
        "scale": scale,
        "copies": copies,
        "customer_data": False,
        "provider_calls": 0,
        "samples": {},
        "observation_window_ms": 300,
        "serving": "ordinary CLI ASGI/uvicorn with real cleanup workers; engineering port and timing instrumentation",
    }
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            context = browser.new_context()
            context.add_cookies(
                [{"name": k, "value": v.value, "url": base} for k, v in cx["a"].cookies.items()]
            )
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.route(
                "**/*",
                lambda route: route.continue_() if route.request.url.startswith(base) else route.abort(),
            )
            paths = [
                ("/cards/", "#card-group-list .owned-card-tile"),
                ("/card-library/?q=pikachu", "#card-group-list .owned-card-tile"),
                ("/pokedex/", "#species-grid [data-dex-species]"),
                ("/cards/?page=2", "#card-group-list .owned-card-tile"),
                ("/cards/?set=perf-set-1", "#card-group-list .owned-card-tile"),
                ("/card-groups/" + key + "/?return=%2Fcards%2F", "#edit-group-card"),
                ("/pokedex/1/", "#species-explore"),
            ]
            for path, selector in paths:
                values = []
                for i in range(20):
                    start = time.perf_counter()
                    page.goto(base + path, wait_until="domcontentloaded")
                    try:
                        expect(page.locator(selector).first).to_be_visible()
                    except AssertionError:
                        print(page.locator("body").inner_text(), errors)
                        raise
                    page.evaluate("() => new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))")
                    elapsed = (time.perf_counter() - start) * 1000
                    # Observe optional work for a fixed window after primary timing ends.
                    page.wait_for_timeout(300)
                    resources = page.evaluate(
                        'performance.getEntriesByType("resource").map(r=>({name:new URL(r.name).pathname,bytes:r.decodedBodySize,duration:r.duration}))'
                    )
                    assert not any(
                        r["name"]
                        in [
                            "/api/collection/",
                            "/api/collection-context/",
                            "/api/catalog/",
                            "/api/my-card-groups/",
                            "/api/card-groups/",
                            "/api/pokedex-species/",
                        ]
                        for r in resources
                    )
                    values.append(
                        {
                            "ms": elapsed,
                            "requests": len(resources) + 1,
                            "bytes": sum(r["bytes"] for r in resources)
                            + page.evaluate("performance.getEntriesByType('navigation')[0].decodedBodySize"),
                            "resources": resources,
                        }
                    )
                report["samples"][path] = {
                    "p95_ms": sorted(v["ms"] for v in values)[18],
                    "worst_ms": max(v["ms"] for v in values),
                    "samples": values,
                }
            for scenario in report["samples"].values():
                assert scenario["p95_ms"] <= 300, scenario["p95_ms"]
                assert max(v["bytes"] for v in scenario["samples"]) <= 512 * 1024
                assert all(
                    r["bytes"] <= 128 * 1024
                    for v in scenario["samples"]
                    for r in v["resources"]
                    if r["name"].startswith("/api/v2/")
                )
            assert not errors, errors
            page.goto(base + "/cards/")
            expect(page.locator(".owned-card-tile").first).to_be_visible()
            page.locator(".owned-card-tile").first.click()
            expect(page.locator("#edit-group-card")).to_be_visible()
            page.locator("#card-back").click()
            expect(page.locator(".owned-card-tile").first).to_be_visible()
            # Options are secondary. Their failure must preserve usable primary cards.
            page.route(
                "**/api/v2/card-group-filters/**",
                lambda route: route.fulfill(status=503, json={"code": "read_state_unavailable"}),
            )
            page.get_by_role("button", name="Browse set choices", exact=True).click()
            expect(page.locator("#card-group-list .owned-card-tile").first).to_be_visible()
            expect(page.get_by_text("Browsing is unavailable.", exact=False)).to_be_visible()
            page.unroute("**/api/v2/card-group-filters/**")
            page.goto(base + "/pokedex/")
            expect(page.locator("#species-grid [data-dex-species]").first).to_be_visible()
            page.locator("#dex-search").fill("pikachu")
            page.locator("#dex-search").fill("ivysaur")
            expect(page.locator("#species-grid")).to_contain_text("Ivysaur")
            expect(page.locator("#species-grid")).not_to_contain_text("Pikachu")
            for width in [1280, 390, 320]:
                page.set_viewport_size({"width": width, "height": 900})
                page.goto(base + "/cards/")
                expect(page.locator(".owned-card-tile").first).to_be_visible()
                page.evaluate(
                    '[...document.querySelectorAll("body,body *")].map(e=>[e,parseFloat(getComputedStyle(e).fontSize)]).forEach(([e,n])=>e.style.fontSize=(n*2)+"px")'
                )
                assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
            page.set_viewport_size({"width": 1280, "height": 900})
            page.goto(base + "/add-many/")
            expect(page.locator("#bulk-catalog-rows .bulk-card").first).to_be_visible()
            page.locator("#bulk-set").select_option("perf-set-1")
            expect(page.locator("#bulk-catalog-rows .bulk-card").first).to_be_visible()
            page.locator("#bulk-catalog-rows input[type=checkbox]").first.check()
            expect(page.locator("#bulk-count")).to_contain_text("1 draft row")
            page.locator("#bulk-next").click()
            expect(page.locator("#bulk-page")).to_contain_text("Page 2")
            expect(page.locator("#bulk-count")).to_contain_text("1 draft row")
            page.locator("#bulk-catalog-rows button").first.click()
            expect(page.locator("#bulk-drawer")).to_be_visible()
            assert not errors, errors
            guest = browser.new_page()
            guest.route(
                "**/*",
                lambda route: route.continue_() if route.request.url.startswith(base) else route.abort(),
            )
            for path in ["/card-library/", "/pokedex/"]:
                guest.goto(base + path)
                expect(guest.locator("#browse-results")).not_to_contain_text("Loading")
                assert "Owned" not in guest.locator("#content").inner_text()
            assert candidate() == source_hash, "Source changed during measurement"
            report["passed"] = True
            browser.close()
    finally:
        process.terminate()
        process.wait(timeout=12)
        close_pipes(process)
        output = Path("reports/perf04")
        output.mkdir(parents=True, exist_ok=True)
        (output / f"browser-{scale}.json").write_text(json.dumps(report, indent=2))
