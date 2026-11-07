"""Full/2x real Shopping actions to rendered usable content; no acquisition."""

import json
import math
import subprocess
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

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
from test_perf04_interactions import candidate
from test_sealed_catalog import e1 as e1

pytestmark = pytest.mark.allow_hosts(["127.0.0.1"])


@pytest.mark.no_cover
@pytest.mark.parametrize("frozen", [False, True])
@pytest.mark.parametrize("count,copies", [(33083, 5000), (66166, 10000)])
def test_collection_intent_action_to_usable(cx, count, copies, frozen):
    from django.conf import settings
    from playwright.sync_api import sync_playwright

    from pokemon_hunter.beta import navigation

    seed(cx, count)
    ownership(cx, copies)
    from test_b2 import apply

    goal = (
        apply(cx, "goal", dict(name="Engineering frozen", goal_kind="original151"), client=cx["b"])[
            "changes"
        ][0]["after"]
        if frozen
        else None
    )
    prepare_reads(cx)
    from pokemon_hunter.beta import collection

    choices = dict(
        query="Venusaur",
        product_type="mixed_lots",
        collection_intent=True,
        intent="missing",
        species=3,
        generation=collection.generation(cx["member"]),
        budget="87.25",
        prefer_vintage=True,
    )
    goal_query = ""
    if goal:
        choices.update(goal_id=goal["id"], goal_version=goal["version"])
        goal_query = f"&goal={goal['id']}&version={goal['version']}"
    run_id = str(uuid.uuid4())
    binding = navigation.binding(SimpleNamespace(user=cx["second"], session=cx["b"].session))[
        "navigation_binding"
    ]
    for marker in ("B2_ISOLATED", "B3_ISOLATED", "B4_ISOLATED"):
        (cx["root"] / marker).write_text("Engineering capability\n")
    (cx["root"] / "secret.key").write_text(settings.SECRET_KEY)
    (cx["root"] / "engineering-shopping.json").write_text(
        json.dumps(
            dict(
                run_id=run_id,
                binding=binding,
                subject=cx["second"].pk,
                choices=choices,
                raw=dict(
                    itemId="v1|123456789012|0",
                    title="Two card lot Base Set 2 Venusaur 18",
                    buyingOptions=["FIXED_PRICE"],
                    price={"value": "10", "currency": "USD"},
                ),
            )
        )
    )
    digest = candidate()
    report = dict(
        source_sha256=digest,
        printings=count,
        copies=copies,
        provider_requests=0,
        customer_data=False,
        serving="Ordinary CLI/ASGI and unchanged bounded admission; pre-received engineering run",
        samples={},
        failures=[],
    )
    process = subprocess.Popen(
        [sys.executable, "tests/shop12_server.py", str(cx["root"]), "0"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        port = read_port(process)
        base = f"http://127.0.0.1:{port}"
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            context = browser.new_context()
            context.add_cookies([dict(name=k, value=v.value, url=base) for k, v in cx["b"].cookies.items()])
            context.add_init_script(path="tests/shop12_browser_probe.js")
            page = context.new_page()
            isolated_network(page, base)
            errors = []
            requests = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("request", lambda r: requests.append((r.method, r.url)))

            def take(kind):
                try:
                    page.locator("html[data-shop-ready=true]").wait_for(timeout=10000)
                except Exception:
                    report["last_action"] = kind
                    report["last_screen"] = page.locator("body").inner_text(timeout=1000)[:5000]
                    raise
                value = page.evaluate(
                    """() => {
                    const p=window.shopProbe, origin=performance.timeOrigin;
                    const resources=performance.getEntriesByType('resource').filter(r=>origin+r.responseEnd>=p.action && r.responseEnd<=p.ready);
                    const nav=performance.getEntriesByType('navigation')[0];
                    const entries=[nav,...resources].filter(r=>origin+r.responseEnd>=p.action && r.responseEnd<=p.ready);
                    const end=Math.max(p.action-origin,...entries.map(r=>r.responseEnd));
                    const intervals=entries.flatMap(r=>r.serverTiming.filter(t=>t.name==='application').map(t=>[Math.max(p.action-origin,r.responseStart-t.duration),r.responseStart])).concat(p.previous_server_intervals.filter(r=>r[1]>=p.action).map(r=>[Math.max(p.action,r[0])-origin,r[1]-origin])).sort((a,b)=>a[0]-b[0]);
                    let server=0,right=p.action-origin;for(const [left,stop] of intervals){server+=Math.max(0,stop-Math.max(left,right));right=Math.max(right,stop);}
                    const parses=p.parses.filter(r=>origin+r.start>=p.action && r.end<=p.ready);
                    const last=parses.at(-1);
                    return {...p,parse_dom_paint_ms:p.ready-(last?last.start:end),
                    scheduling_transfer_ms:Math.max(0,origin+end-p.action-server),
                    resources:entries.map(r=>({path:new URL(r.name).pathname,start:r.startTime,end:r.responseEnd,server:r.serverTiming.map(s=>({name:s.name,duration:s.duration}))}))};
                    }"""
                )
                report["samples"].setdefault(kind, []).append(value)
                assert not errors, errors

            for _ in range(20):
                page.goto(
                    base
                    + f"/shopping/?run_id={run_id}&q=Venusaur&species=3&intent=missing&budget=87.25&prefer_vintage=1{goal_query}",
                    wait_until="domcontentloaded",
                )
                # Navigation origin is the entry boundary; previous action marks
                # belong to prior documents and are explicitly cleared.
                page.evaluate("sessionStorage.removeItem('shop12-clock')")
                take("restored_results")
                assert page.locator("#discovery-budget").input_value() == "87.25"
                assert page.locator("#discovery-prefer-vintage").is_checked()
                page.locator("#discovery-target:not(:disabled)").wait_for()
                page.locator("#find-missing").evaluate(
                    "(e)=>{window.shopMark('targets','#discovery-target:not(:disabled)');e.click();}"
                )
                take("targets")
                page.locator(".review-offer").first.evaluate("(e)=>{window.shopMark('candidate');e.click();}")
                take("candidate")
                assert page.locator("#listing-details").text_content().find("contents entries") >= 0
                page.locator("#use-listing").evaluate(
                    "(e)=>{window.shopMark('use_offer','#review-cards .contents-entry');e.click();}"
                )
                take("use_offer")
                assert page.locator("#review-budget").input_value() == "87.25"
                # Edit while the first save may still be pending. Back must drain
                # the latest revision, rather than publish the earlier payload.
                page.locator("#review-price").fill("11")
                page.locator("#check-back").evaluate("(e)=>{window.shopMark('back');e.click();}")
                take("back_results")
                saved = page.evaluate(
                    "async()=> (await (await fetch('/api/shopping/listing/review/')).json()).review"
                )
                assert saved["price"] == "11"
                assert saved["discovery_origin"]["run_id"] == run_id
                page.evaluate(
                    "window.shopMark('explorer','#catalog-cards .catalog-details, #catalog-cards .catalog-empty');document.querySelector('.discovery-local').open=true"
                )
                take("explorer_empty_frozen" if frozen else "explorer")
                if frozen:
                    assert page.locator("#catalog-cards .catalog-empty").count() == 1
                else:
                    assert page.locator("#catalog-cards .catalog-details").count() > 0
                page.evaluate("sessionStorage.removeItem('shop12-clock')")
            assert not any(
                method == "POST"
                and ("/discovery/" in url or "/listing/loads/" in url or "/interpretation/" in url)
                for method, url in requests
            )
            context.close()
            browser.close()
    finally:
        process.terminate()
        process.wait(timeout=15)
        close_pipes(process)
        assert candidate() == digest, "Source changed during browser measurement"
        for kind, samples in report["samples"].items():
            values = sorted(s["elapsed"] for s in samples)
            report.setdefault("metrics", {})[kind] = dict(
                n=len(values), p95_ms=values[math.ceil(0.95 * len(values)) - 1], worst_ms=max(values)
            )
            budget = 1000 if kind == "restored_results" else 300
            if len(values) != 20 or report["metrics"][kind]["p95_ms"] > budget:
                report["failures"].append(f"{kind}: incomplete samples or exceeds {budget} ms")
            for phase, limit in (("scheduling_transfer_ms", 50), ("parse_dom_paint_ms", 70)):
                timings = sorted(s[phase] for s in samples)
                report["metrics"][kind][phase] = dict(
                    p95=timings[18] if len(timings) == 20 else max(timings), worst=max(timings)
                )
                if kind != "restored_results" and report["metrics"][kind][phase]["p95"] > limit:
                    report["failures"].append(f"{kind}: {phase} exceeds {limit} ms")
        out = Path("reports/shop-13")
        out.mkdir(parents=True, exist_ok=True)
        (out / f"browser-{count}-{'frozen' if frozen else 'current'}.json").write_text(
            json.dumps(report, indent=2)
        )
    assert len(report["samples"]) == 6
    assert not report["failures"], report["failures"]
