"""Real form/page interactions and restarted-process navigation in isolated state."""

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest
from browser_measurements import isolated_network
from perf04_helpers import prepare_reads
from runtime_process import close_pipes, read_port
from test_account_read_performance import ownership
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_catalog_read_performance import seed
from test_effective_collection import cx as cx
from test_migration import snapshot as snapshot
from test_sealed_catalog import e1 as e1

pytestmark = pytest.mark.allow_hosts(["127.0.0.1"])


def candidate():
    return hashlib.sha256(
        b"".join(
            p.read_bytes()
            for p in sorted(Path("src/pokemon_hunter/beta").rglob("*"))
            if p.is_file() and p.suffix in {".py", ".js", ".html", ".css"}
        )
    ).hexdigest()


@pytest.mark.no_cover
@pytest.mark.parametrize("scale,copies", [(33083, 5000), (66166, 10000)])
def test_real_interaction_phases_and_restart(cx, scale, copies):
    from playwright.sync_api import sync_playwright

    seed(cx, scale)
    ownership(cx, copies)
    prepare_reads(cx)
    # In-process fixtures toggle capability settings; persist those same capabilities
    # only in this disposable root so a fresh process sees the same application.
    from django.conf import settings

    for marker in ["B2_ISOLATED", "B3_ISOLATED", "B4_ISOLATED"]:
        (cx["root"] / marker).write_text("Engineering fixture capability\n")
    (cx["root"] / "secret.key").write_text(settings.SECRET_KEY)
    digest = candidate()
    report = dict(
        source_sha256=digest,
        scale=scale,
        copies=copies,
        passed=False,
        customer_data=False,
        provider_calls=0,
        connection="Ordinary CLI workers and HTTP/1.1 ASGI/uvicorn; keep-alive enabled, browser resource cache explicitly disabled; external-only interception; Server-Timing connection descriptions identify reused TCP peers",
        os_cache="warm from preparation; OS cache not evicted",
        observation_window_ms=300,
        samples={},
        restart=[],
    )
    process = None

    def start(port=0):
        nonlocal process
        before = time.perf_counter()
        process = subprocess.Popen(
            [sys.executable, "tests/ops_server.py", str(cx["root"]), str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        port = read_port(process)
        return port, (time.perf_counter() - before) * 1000

    port, startup = start()
    report["startup_to_listening_ms"] = startup
    base = f"http://127.0.0.1:{port}"
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            for private in [False, True]:
                context = browser.new_context()
                if private:
                    context.add_cookies(
                        [{"name": k, "value": v.value, "url": base} for k, v in cx["a"].cookies.items()]
                    )
                context.add_init_script(path="tests/perf04_browser_probe.js")
                page = context.new_page()
                isolated_network(page, base)
                page.goto(base + "/card-library/")
                try:
                    page.locator("html[data-perf-ready]").wait_for(state="attached", timeout=5000)
                except Exception:
                    print(page.locator("body").inner_text(), page.evaluate("window.probe"))
                    raise
                for mode in ["search", "filter", "page"]:
                    values = []
                    for i in range(20):
                        # Preparation is outside the measured user action; the destination is reached by real controls.
                        page.goto(base + "/card-library/")
                        page.locator("html[data-perf-ready]").wait_for(state="attached")
                        search = page.locator("#cards-query" if private else "#browse-search")
                        if mode == "search":
                            search.fill("pikachu" if i % 2 else "bulbasaur")
                            search.press("Enter")
                        elif mode == "filter":
                            page.get_by_role("button", name="Browse set choices", exact=True).click()
                            choices = page.locator('[data-option-value="perf-set-1"]')
                            choices.click()
                            page.get_by_role(
                                "button", name="Search cards" if private else "Search", exact=True
                            ).click()
                        else:
                            page.get_by_role(
                                "link", name="Next cards" if private else "Next", exact=True
                            ).click()
                        page.locator("html[data-perf-ready]").wait_for(state="attached")
                        # Fixed post-readiness window includes optional labels/artwork and their failures.
                        page.wait_for_timeout(300)
                        value = page.evaluate("""() => {
                         const p=window.probe,nav=performance.getEntriesByType('navigation')[0],resources=performance.getEntriesByType('resource');
                         const primary=resources.find(r=>new URL(r.name).pathname.endsWith('/card-groups/'));
                         const parse=p.parses.find(r=>r.path.endsWith('/card-groups/'));
                         const end=primary.responseEnd;
                         const intervals=[nav,...resources].filter(r=>r.responseEnd<=end).flatMap(r=>r.serverTiming.filter(t=>t.name==='application').map(t=>[Math.max(0,r.responseStart-t.duration),r.responseStart])).sort((a,b)=>a[0]-b[0]);
                         let server=0,right=0;for(const [left,stop] of intervals){server+=Math.max(0,stop-Math.max(left,right));right=Math.max(right,stop);}
                         return {ms:performance.timeOrigin+p.ready-p.action,parse_dom_paint_ms:p.ready-parse.start,
                           scheduling_transfer_ms:Math.max(0,performance.timeOrigin+end-p.action-server),
                           bytes:nav.decodedBodySize+resources.reduce((n,r)=>n+r.decodedBodySize,0),
                           resources:resources.map(r=>({path:new URL(r.name).pathname,bytes:r.decodedBodySize,ms:r.duration,connection_ms:r.connectEnd-r.connectStart,server:r.serverTiming})),
                           navigation_server:nav.serverTiming,primary_bytes:primary.decodedBodySize,action:p.action,origin:performance.timeOrigin,ready:p.ready};
                        }""")
                        values.append(value)
                    report["samples"][("private" if private else "guest") + "-" + mode] = dict(
                        samples=values,
                        p95_ms=sorted(v["ms"] for v in values)[18],
                        worst_ms=max(v["ms"] for v in values),
                    )
                # Restart the process with the exact prepared DB; no rebuilding or warm-up request.
                process.terminate()
                process.wait(timeout=10)
                close_pipes(process)
                _, startup = start(port)
                page.evaluate("sessionStorage.removeItem('perf04-action')")
                begin = time.perf_counter()
                page.goto(base + "/card-library/")
                try:
                    page.locator("html[data-perf-ready]").wait_for(state="attached", timeout=5000)
                except Exception:
                    print(page.locator("body").inner_text(), page.evaluate("window.probe"))
                    raise
                report["restart"].append(
                    dict(
                        private=private,
                        startup_to_listening_ms=startup,
                        first_navigation_ms=(time.perf_counter() - begin) * 1000,
                    )
                )
                context.close()
            browser.close()
        assert candidate() == digest, "Source changed during measurement"
        failures = []
        for name, group in report["samples"].items():
            if group["p95_ms"] > 300:
                failures.append(f"{name}: p95 {group['p95_ms']:.2f} ms >300")
            for phase, budget in [("scheduling_transfer_ms", 50), ("parse_dom_paint_ms", 70)]:
                group["p95_" + phase] = sorted(v[phase] for v in group["samples"])[18]
                if group["p95_" + phase] > budget:
                    failures.append(f"{name}: {phase} p95 {group['p95_' + phase]:.2f} >{budget}")
            for v in group["samples"]:
                if v["bytes"] > 512 * 1024 or v["primary_bytes"] > 128 * 1024:
                    failures.append(name + ": payload")
                for r in v["resources"]:
                    if ("filter" in r["path"] or r["path"].endswith("/context/")) and r["bytes"] > 32 * 1024:
                        failures.append(name + ": context payload")
                    assert r["path"] not in ["/api/collection/", "/api/catalog/", "/api/collection-context/"]
        for r in report["restart"]:
            if r["first_navigation_ms"] > 1000:
                failures.append("restart first navigation >1000")
        report["failures"] = failures
        report["passed"] = not failures
        assert not failures, failures
    finally:
        if process and process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
        if process:
            close_pipes(process)
        output = Path("reports/perf04")
        output.mkdir(parents=True, exist_ok=True)
        (output / f"interactions-{scale}.json").write_text(json.dumps(report, indent=2))
