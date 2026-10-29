"""Explicit diagnostic subset, never discovered as acceptance or customer evidence."""

import cProfile
import json
import os
import platform
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest
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

OUTPUT = Path("reports/ci/perf-diagnostic")
pytestmark = [pytest.mark.no_cover, pytest.mark.allow_hosts(["127.0.0.1"])]


def identity():
    from django.db import connection

    return {
        "source": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "run": os.environ.get("GITHUB_RUN_ID"),
        "attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "sqlite": connection.Database.sqlite_version,
        "cpu_count": os.cpu_count(),
        "load": os.getloadavg(),
        "trace_active": sys.gettrace() is not None,
        "diagnostic_only": True,
        "customer_data": False,
    }


def test_profile_preparation(cx):
    from test_ownership_declarations import migrate as declarations_migrate

    from pokemon_hunter.beta import catalog_read_build as builds
    from pokemon_hunter.beta.catalog_read_schema import migrate

    OUTPUT.mkdir(parents=True, exist_ok=True)
    declarations_migrate(cx)
    seed(cx, 66166)
    migrate()
    phases = {}
    profiler = cProfile.Profile()
    profiler.enable()
    try:
        build = builds.prepare(timings=phases)
        builds.activate(build)
    finally:
        profiler.disable()
        profiler.dump_stats(str(OUTPUT / "preparation.prof"))
        (OUTPUT / "preparation-profile.json").write_text(
            json.dumps({"identity": identity(), "phases": phases, "profiled_not_acceptance": True}, indent=2)
        )


NAVIGATION_PROBE = r"""(() => {
 const selectors = {'/cards/':'#card-group-list .owned-card-tile',
 '/card-library/':'#card-group-list .owned-card-tile',
 '/pokedex/':'#species-grid [data-dex-species]', '/pokedex/1/':'#species-explore'};
 const selector=selectors[location.pathname];
 window.navigationProbe={ready:null,visible:null,frames:[],longtasks:[],visibility:document.visibilityState};
 let prior=performance.now();
 function frame(t){navigationProbe.frames.push(t-prior);prior=t;
   if(navigationProbe.frames.length<30)requestAnimationFrame(frame);}
 requestAnimationFrame(frame);
 try{new PerformanceObserver(list=>navigationProbe.longtasks.push(...list.getEntries().map(e=>({start:e.startTime,duration:e.duration}))))
 .observe({type:'longtask',buffered:true});}catch(_){}
 function visible(){const e=document.querySelector(selector);return e&&e.getClientRects().length&&getComputedStyle(e).visibility!=='hidden';}
 let scheduled=false;
 function check(){if(scheduled||!visible())return;scheduled=true;navigationProbe.visible=performance.now();
 requestAnimationFrame(()=>requestAnimationFrame(()=>{
  if(!visible()){scheduled=false;check();return;}
  navigationProbe.ready=performance.now();document.documentElement.dataset.navigationProbeReady='true';
 }));}
 new MutationObserver(check).observe(document,{childList:true,subtree:true,attributes:true});
 addEventListener('DOMContentLoaded',check);check();
})();"""


def test_browser_instrumentation(cx):
    from django.conf import settings
    from playwright.sync_api import expect, sync_playwright

    OUTPUT.mkdir(parents=True, exist_ok=True)
    seed(cx, 66166)
    ownership(cx, 10000)
    prepare_reads(cx)
    for marker in ["B2_ISOLATED", "B3_ISOLATED", "B4_ISOLATED"]:
        (cx["root"] / marker).write_text("Isolated engineering capability\n")
    (cx["root"] / "secret.key").write_text(settings.SECRET_KEY)
    process = subprocess.Popen(
        [sys.executable, "tests/ops_server.py", str(cx["root"]), "0"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    report = {"identity": identity(), "scale": 66166, "copies": 10000, "modes": {}}
    try:
        base = f"http://127.0.0.1:{read_port(process)}"
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            report["browser"] = browser.version
            for mode in ["all_requests_python", "external_only", "all_requests_python_repeat"]:
                context = browser.new_context()
                context.add_cookies(
                    [{"name": k, "value": v.value, "url": base} for k, v in cx["a"].cookies.items()]
                )
                context.add_init_script(script=NAVIGATION_PROBE)
                context.add_init_script(path="tests/perf04_browser_probe.js")
                page = context.new_page()
                cdp = context.new_cdp_session(page)
                cdp.send("Network.enable")
                cdp.send("Network.setCacheDisabled", {"cacheDisabled": True})
                routing = []

                def routed(route):
                    start = time.perf_counter()
                    local = route.request.url.startswith(base + "/")
                    if local:
                        route.continue_()
                    else:
                        route.abort()
                    routing.append({"local": local, "callback_ms": (time.perf_counter() - start) * 1000})

                page.route(
                    "**/*"
                    if mode.startswith("all_requests")
                    else re.compile(r"^(?!" + re.escape(base) + r"(?:/|$))"),
                    routed,
                )
                measurements = {"navigation": {}, "filter": [], "routing": routing}
                report["modes"][mode] = measurements
                for path, selector in [
                    ("/cards/", "#card-group-list .owned-card-tile"),
                    ("/pokedex/1/", "#species-explore"),
                ]:
                    samples = []
                    for _ in range(20):
                        start = time.perf_counter()
                        page.goto(base + path, wait_until="domcontentloaded")
                        expect(page.locator(selector).first).to_be_visible()
                        page.evaluate(
                            "() => new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))"
                        )
                        driver_ms = (time.perf_counter() - start) * 1000
                        page.wait_for_timeout(300)
                        value = page.evaluate("""() => ({...navigationProbe,
                        navigation:performance.getEntriesByType('navigation')[0].toJSON(),
                        resources:performance.getEntriesByType('resource').map(r=>r.toJSON())})""")
                        assert value["ready"] is not None
                        value["driver_ms"] = driver_ms
                        samples.append(value)
                    measurements["navigation"][path] = samples
                # Guest filter is the repeated near-threshold Linux case.
                context.clear_cookies()
                for _ in range(20):
                    page.goto(base + "/card-library/")
                    page.locator("html[data-perf-ready]").wait_for(state="attached")
                    page.get_by_role("button", name="Browse set choices", exact=True).click()
                    page.locator('[data-option-value="perf-set-1"]').click()
                    page.get_by_role("button", name="Search", exact=True).click()
                    page.locator("html[data-perf-ready]").wait_for(state="attached")
                    page.wait_for_timeout(300)
                    measurements["filter"].append(
                        page.evaluate("""() => ({probe:window.probe,
                     timeOrigin:performance.timeOrigin, navigationProbe,
                     navigation:performance.getEntriesByType('navigation')[0].toJSON(),
                     resources:performance.getEntriesByType('resource').map(r=>r.toJSON())})""")
                    )
                # Controlled external URL is aborted by the route before transmission.
                assert page.evaluate("fetch('https://example.invalid/diagnostic').then(()=>false,()=>true)")
                context.close()
                (OUTPUT / "browser.json").write_text(json.dumps(report, indent=2))
            browser.close()
    finally:
        process.terminate()
        process.wait(timeout=12)
        close_pipes(process)
        (OUTPUT / "browser.json").write_text(json.dumps(report, indent=2))
