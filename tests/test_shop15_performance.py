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


def prepare_auction(cx, count, copies, action):
    from datetime import datetime

    from django.conf import settings

    from pokemon_hunter.beta import collection, discovery_listing, navigation, shopping

    pid = cx["by_legacy"]["c"]["id"]
    collection.execute(
        "UPDATE printings SET edition='standard',finish='normal',variant='normal' WHERE id=%s", [pid]
    )
    (cx["root"] / "SYNTHETIC_ONLY").touch()
    evidence = cx["root"] / "parity-evidence"
    evidence.mkdir(exist_ok=True)
    (evidence / "market_values.json").write_text(
        json.dumps(
            [
                dict(
                    card_id="c",
                    edition="standard",
                    finish="normal",
                    variant="normal",
                    language="en",
                    grade="raw",
                    grader="Guide",
                    condition="NM",
                    value="10",
                    currency="USD",
                    variant_verified=True,
                    as_of=datetime.now(shopping.TZ).date().isoformat(),
                    source_url="https://example.test/engineering",
                )
            ]
        )
    )
    seed(cx, count)
    ownership(cx, copies)
    choices = dict(query="Venusaur", product_type="mixed_lots")
    user, client = cx["owner"], cx["a"]
    if action == "return":
        user, client = cx["second"], cx["b"]
        choices.update(collection_intent=True, intent="missing", species=3, prefer_vintage=True, budget="12")
        if count == 66166:
            from test_b2 import apply

            goal = apply(cx, "goal", dict(name="Engineering frozen", goal_kind="original151"), client=client)[
                "changes"
            ][0]["after"]
            choices.update(goal_id=goal["id"], goal_version=goal["version"])
        choices["generation"] = collection.generation(cx["member"])
    prepare_reads(cx)
    run_id = str(uuid.uuid4())
    handle = discovery_listing.result_handle(run_id, "v1|123456789012|0")
    binding = navigation.binding(SimpleNamespace(user=user, session=client.session))["navigation_binding"]
    for marker in ("B2_ISOLATED", "B3_ISOLATED", "B4_ISOLATED"):
        (cx["root"] / marker).write_text("Engineering capability\n")
    (cx["root"] / "secret.key").write_text(settings.SECRET_KEY)
    (cx["root"] / "engineering-shopping.json").write_text(
        json.dumps(
            dict(
                run_id=run_id,
                binding=binding,
                subject=user.pk,
                choices=choices,
                measure_compare=True,
                measure_route=f"api/shopping/listing/{action}/",
                raw=dict(
                    itemId="v1|123456789012|0",
                    title="Card lot of 1: Venusaur Base Set 2 #18",
                    shortDescription="1x Venusaur Base Set 2 #18",
                    buyingOptions=["AUCTION"],
                    itemEndDate="2031-01-10T18:40:00Z",
                    currentBidPrice={"value": "11", "currency": "USD"},
                ),
            )
        )
    )
    return pid, run_id, handle, client


def prepare_review(page, pid, run_id, handle, condition):
    review = dict(
        lease=None,
        review=dict(
            currency="USD",
            unknown_contents=0,
            price_kind="current_bid",
            discovery_origin={"run_id": run_id, "result_id": handle},
            price="11",
            shipping="1",
            tax="0",
            other_costs="0",
            budget="12",
            authored_fields=["budget", "planned_bid"],
            planned_bid="9",
            cards=[dict(printing_id=pid, quantity=1, grade="raw", condition=condition)],
        ),
    )
    page.evaluate(
        """async payload=>{
        const headers={'Content-Type':'application/json','X-CSRFToken':document.querySelector('[name=csrfmiddlewaretoken]').value,'X-Dex-Shopping-Binding':JSON.parse(document.querySelector('#check-binding').textContent)};
        const url='/api/shopping/listing/review/';
        payload.lease=(await (await fetch(url,{headers})).json()).lease;
        const r=await fetch(url,{headers,method:'POST',body:JSON.stringify(payload)});
        if(!r.ok) throw Error(await r.text());
    }""",
        review,
    )
    page.reload()
    from playwright.sync_api import expect

    expect(page.locator("#review-price")).to_have_value("11")
    expect(page.locator("#check-compare")).to_be_enabled()


@pytest.mark.no_cover
@pytest.mark.parametrize("count,copies", [(33083, 5000), (66166, 10000)])
@pytest.mark.parametrize("action", ["compare", "return"])
def test_assessment_action_to_usable(cx, count, copies, action):
    route = f"/api/shopping/listing/{action}/"
    from playwright.sync_api import sync_playwright

    pid, run_id, handle, client = prepare_auction(cx, count, copies, action)
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
            context = browser.new_context(timezone_id="UTC")
            seller_url = "https://www.ebay.com/itm/123456789012"
            context.route(
                seller_url,
                lambda r: r.fulfill(content_type="text/html", body="<title>Intercepted seller</title>"),
            )
            context.add_cookies([dict(name=k, value=v.value, url=base) for k, v in client.cookies.items()])
            context.add_init_script(path="tests/shop12_browser_probe.js")
            page = context.new_page()
            isolated_network(page, base)
            errors = []
            requests = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("request", lambda r: requests.append((r.method, r.url)))

            from shop_action_measure import take

            page.goto(base + "/shopping/check/")
            page.locator("#check-compare:enabled").wait_for()
            for scenario, condition in (("supported", "NM"), ("withheld", "LP")):
                prepare_review(page, pid, run_id, handle, condition)
                if action == "return":
                    page.locator("#check-compare").press("Enter")
                    page.locator("#check-results a").wait_for()
                for i in range(20):
                    width = (320, 390, 1280)[i % 3]
                    page.set_viewport_size(dict(width=width, height=950))
                    zoom = 200 if i % 2 else 100
                    size = page.evaluate(
                        """zoom=>{
                        document.documentElement.style.setProperty('font-size',zoom+'%','important');
                        return parseFloat(getComputedStyle(document.documentElement).fontSize);
                    }""",
                        zoom,
                    )
                    assert size == 16 * zoom / 100
                    button = page.locator("#check-compare")
                    if action == "return":
                        link = page.locator("#check-results a")
                        assert link.get_attribute("href") == seller_url
                        end = link.locator("..").inner_text()
                        assert "2031" in end and "UTC" in end
                        scope = page.locator("#check-context").inner_text()
                        assert "Venusaur" in scope and "12 USD" in scope and "Vintage preferred" in scope
                        link.focus()
                        scroll = page.evaluate("scrollY")
                        with context.expect_page() as opened:
                            link.press("Enter")
                        seller = opened.value
                        seller.wait_for_url(seller_url)
                        assert seller.title() == "Intercepted seller" and seller.evaluate(
                            "window.opener===null"
                        )
                        assert page.locator("#check-results").get_attribute("data-pending")
                        page.evaluate(
                            """() => shopMark('return','#check-results:not([hidden]):not([data-pending]) p')"""
                        )
                        start = len(requests)
                        seller.close()
                        page.bring_to_front()
                        # Headless Chromium does not reliably deliver OS window focus.
                        page.evaluate("window.dispatchEvent(new FocusEvent('focus'))")
                    else:
                        button.focus()
                        button.evaluate(
                            """e=>e.addEventListener('click',()=>{
                                for (const old of document.querySelectorAll('#check-results p')) old.dataset.previous='true';
                                window.shopMark('compare','#check-results:not([hidden]) p:not([data-previous])');
                            },{capture:true,once:true})"""
                        )
                        button.press("Enter")
                    take(page, report, errors, scenario, route)
                    if action == "return":
                        assert all(
                            method == "GET" and url.startswith(base) for method, url in requests[start:]
                        )
                        assert (
                            link.evaluate("e=>document.activeElement===e")
                            and page.evaluate("scrollY") == scroll
                        )
                        assert page.locator("#check-context").inner_text() == scope
                        assert page.locator("#review-budget").input_value() == "12"
                        assert page.locator("#review-planned_bid").input_value() == "9"
                    sample = report["samples"][scenario][-1]
                    assert any(r["path"] == route for r in sample["resources"])
                    assert len(sample["parses"]) == 1 and sample["parses"][0]["end"] <= sample["ready"]
                    out = page.locator("#check-results")
                    report["samples"][scenario][-1].update(width=width, text_percent=zoom)
                    content = out.inner_text()
                    assert (
                        "$9.00" in content and "Observed bid already exceeds ceiling" in content
                        if scenario == "supported"
                        else "matching this printing and LP" in content
                    ), content
                    assert out.evaluate(
                        "e=>e.getBoundingClientRect().right<=innerWidth+1 && e.scrollWidth<=e.clientWidth+1"
                    )
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
            budget = 300
            if len(values) != 20 or report["metrics"][kind]["p95_ms"] > budget:
                report["failures"].append(f"{kind}: incomplete samples or exceeds {budget} ms")
            for phase, limit in (("scheduling_transfer_ms", 50), ("parse_dom_paint_ms", 70)):
                timings = sorted(s[phase] for s in samples)
                report["metrics"][kind][phase] = dict(
                    p95=timings[18] if len(timings) == 20 else max(timings), worst=max(timings)
                )
                if report["metrics"][kind][phase]["p95"] > limit:
                    report["failures"].append(f"{kind}: {phase} exceeds {limit} ms")
        diagnostics = cx["root"] / "engineering-compare.jsonl"
        rows = (
            [json.loads(line) for line in diagnostics.read_text().splitlines()]
            if diagnostics.exists()
            else []
        )
        for i, kind in enumerate(("supported", "withheld")):
            samples = rows[20 * i : 20 * (i + 1)]
            report.setdefault("server_samples", {})[kind] = samples
            if len(samples) != 20:
                report["failures"].append(f"{kind}: incomplete server samples")
                continue
            for row in samples:
                row["sql_ms"] = row["sql_execute_ms"] + row["sql_fetch_ms"]
                row["other_ms"] = (
                    row["elapsed_ms"] - row["sql_ms"] - row["composition_ms"] - row["serialization_ms"]
                )
            for field, limit in dict(
                elapsed_ms=180,
                sql_ms=40,
                other_ms=60,
                composition_ms=80,
                serialization_ms=60,
                query_count=20,
                payload_bytes=131072,
            ).items():
                if any(row[field] is None or row["status"] != 200 for row in samples):
                    report["failures"].append(f"{kind}: failed request or missing {field}")
                    continue
                values = sorted(row[field] for row in samples)
                report["metrics"][kind][field] = dict(p95=values[18], worst=max(values))
                if values[18] > limit:
                    report["failures"].append(f"{kind}: {field} exceeds {limit}")
        out = Path("reports/shop-16" if action == "return" else "reports/shop-15")
        out.mkdir(parents=True, exist_ok=True)
        (out / f"browser-{count}.json").write_text(json.dumps(report, indent=2))
    assert len(report["samples"]) == 2
    assert not report["failures"], report["failures"]
