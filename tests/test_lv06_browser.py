"""Authored UI envelopes on the ordinary page; external traffic is blocked."""

import copy
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

import pytest
from test_shop12_browser import (  # noqa: F401
    b2,
    b3,
    b4,
    cx,
    e1,
    env,
    prepared,
    snapshot,
)
from test_shop12_browser import browser_app as browser_app

pytestmark = pytest.mark.allow_hosts(["127.0.0.1"])


def offer(key="complete", group="complete", basis="mixed", rank=1):
    now = datetime.now(UTC)
    ref = dict(
        printing_id="authored-lapras",
        basis="sold_estimate" if basis == "mixed" else basis,
        amount="30.00",
        as_of=now.date().isoformat(),
        date_basis="valuation_as_of",
        condition=None,
        source_url="https://example.test/reference",
        source_contract="authored-source",
        expires_at=(now + timedelta(hours=1)).isoformat(),
        method=dict(method="recency_weighted_median", version="v1"),
        sample=dict(
            unique_sales=7,
            effective_sample_size="6.5",
            sold_from="2026-10-01",
            sold_through="2026-11-03",
            excluded={"duplicate": 2},
        ),
    )
    costs = dict(
        auction=dict(
            base="1.00",
            shipping="5.00",
            delivered_before_tax="6.00",
            difference="34.00",
            subtotal_difference=None,
        ),
        buy_it_now=dict(
            base="50.00",
            shipping="5.00",
            delivered_before_tax="55.00",
            difference="-15.00",
            subtotal_difference=None,
        ),
    )
    val = dict(
        assessment_version="dex-lot-value-v3",
        basis=basis,
        basis_label={"mixed": "Mixed", "guide": "Guide", "sold_estimate": "Sold estimate"}[basis],
        total="40.00",
        subtotal="40.00",
        priced_quantity=2,
        normalized_priced_quantity=2,
        identified_quantity=2,
        physically_selected_quantity=2,
        parent_identified_quantity=2,
        native_priced_quantity=0,
        stated_quantity=2,
        identified_unpriced_quantity=0,
        unidentified_quantity=0,
        contents_state="resolved",
        benchmark_costs=costs,
        bid_difference="34.00",
        buy_now_difference="-15.00",
        native_guides=[],
        alternatives=[],
        reason="Seller-stated contents; condition unspecified.",
        references=[ref],
        cards=[
            dict(
                printing_id="authored-lapras",
                name="Lapras",
                set_name="Fossil",
                collector_number="10",
                quantity=1,
                reference=ref,
                reference_subtotal="30.00",
            ),
            dict(
                printing_id="authored-venusaur",
                name="Venusaur",
                set_name="Base Set",
                collector_number="15",
                quantity=1,
                reference={**ref, "printing_id": "authored-venusaur", "basis": "guide", "sample": None},
                reference_subtotal="10.00",
            ),
        ],
        source_fields={
            "detail_description": "Authored 2-card lot: Lapras and Venusaur. <script>unsafe</script>"
        },
        contents=[],
        quantity_issues=[],
        gaps=[],
    )
    if group in {"partial", "unknown_cost"}:
        val.update(
            total=None,
            stated_quantity=37,
            unidentified_quantity=35,
            contents_state="unresolved",
            bid_difference=None,
            buy_now_difference=None,
        )
        for c in costs.values():
            c["subtotal_difference"], c["difference"] = c["difference"], None
    if group == "unknown_cost":
        for c in costs.values():
            c.update(shipping=None, delivered_before_tax=None, subtotal_difference=None)
    if group == "unpriced":
        val.update(
            total=None,
            subtotal=None,
            priced_quantity=0,
            normalized_priced_quantity=0,
            references=[],
            identified_unpriced_quantity=2,
            bid_difference=None,
            buy_now_difference=None,
        )
        for c in costs.values():
            c.update(difference=None, subtotal_difference=None)
        for card in val["cards"]:
            card.update(reference=None, reference_subtotal=None)
    order = dict(rank=rank, combined_rank=rank, group=group)
    return dict(
        id=key,
        title=f"Authored {key} lot",
        price_kind="current_bid",
        listing_price="1.00",
        shipping="5.00",
        buy_now_price="50.00",
        delivered_total="6.00",
        buy_now_delivered_total="55.00",
        item_url="https://www.ebay.com/itm/123456789012?var=123456789013",
        ends_at=(now + timedelta(hours=12)).isoformat(),
        observed_at=now.isoformat(),
        evidence_kind="seller_details",
        assessment_state="partial" if group != "complete" else "ready",
        lot_value=val,
        value_order=dict(
            schema="dex-lot-order-v1",
            lanes={"auction": order.copy(), "buy_it_now": order.copy()},
            combined=order.copy(),
            native=[],
        ),
    )


@pytest.fixture
def ui(browser_app):
    state, page, base, requests, errors = browser_app
    run_id = str(uuid.uuid4())
    model = dict(
        run_id=run_id,
        contract="dex-lot-hunt-v2",
        state="partial",
        running=False,
        expires_in_seconds=1800,
        values_checked=True,
        has_next=False,
        choices=dict(query="Lapras", intent="deals", product_type="mixed_lots"),
        progress=dict(searched=2, received=40, enriched=2, assessed=2, unprocessed=38),
        reasons={"candidate_limit": 1},
        coverage=dict(received=40),
        results=[offer()],
    )
    calls, pending = [], []
    control = dict(hold=False, sources=["authored-source"])

    def route(handler):
        req = handler.request
        calls.append((req.method, req.url, req.post_data_json if req.method == "POST" else None))
        authority = dict(
            account_id=state["actor"].user_id, binding=req.header_value("X-Dex-Shopping-Binding")
        )
        if "/price-source-status/" in req.url:
            if control.get("source_busy"):
                handler.fulfill(status=503, json=dict(error="runtime_busy"))
                return
            handler.fulfill(json=dict(versions=[], sources=control["sources"], authority=authority))
        elif req.method == "POST" and "/stop/" in req.url:
            model.update(state="stopped", running=False, results=[])
            handler.fulfill(json=dict(copy.deepcopy(model), authority=authority))
        elif req.method == "POST" or urlsplit(req.url).query:
            if control["hold"] and req.method == "GET":
                pending.append((handler, dict(copy.deepcopy(model), authority=authority)))
            else:
                handler.fulfill(json=dict(copy.deepcopy(model), authority=authority))
        else:
            handler.fulfill(
                json=dict(
                    provider=dict(enabled=True, configured=True), goals=[], sets=[], authority=authority
                )
            )

    page.route("**/api/shopping/discovery/**", route)
    page.route("**/api/shopping/price-source-status/", route)
    return page, base, model, calls, control, pending, errors


def open_results(ui, *, advanced=False):
    page, base, model, *_ = ui
    page.goto(base + f"/shopping/?run_id={model['run_id']}&q=Lapras")
    page.locator("#discovery-results:not([hidden])").wait_for()
    if advanced:
        page.locator(".result-settings > summary").click()
        page.locator("#lot-value-sort").select_option("value")


def open_details(page, key="complete"):
    panel = page.locator(f"#offer-{key} .lot-more")
    if not panel.evaluate("e=>e.open"):
        panel.locator(":scope > summary").click()


def test_glance_groups_dual_costs_evidence_keyboard_and_layout(ui):
    from playwright.sync_api import expect

    page, base, model, calls, control, pending, errors = ui
    model["results"] = [
        offer(),
        offer("partial", "partial", "guide", 2),
        offer("unknown", "unknown_cost", "sold_estimate", 3),
        offer("unpriced", "unpriced", rank=4),
    ]
    open_results(ui, advanced=True)
    for label in (
        "Complete assessments",
        "Partially assessed",
        "Unknown delivered cost",
        "Assessed without a normalized value",
    ):
        expect(page.locator(".lot-group-heading").filter(has_text=label)).to_be_visible()
    open_details(page)
    open_details(page, "partial")
    first = page.locator("#offer-complete")
    expect(first.get_by_text("$40.00 ungraded lot value", exact=True)).to_be_visible()
    expect(
        first.get_by_text("Buy It Now + shipping: $15.00 above reference · before tax", exact=True)
    ).to_be_visible()
    expect(first.locator(".lot-value")).to_contain_text("Bid + shipping: $34.00 below reference")
    expect(first.locator(".lot-buy")).to_contain_text("$55.00")
    expect(page.locator("#offer-partial .partial-difference").first).to_contain_text(
        "not a whole-lot bargain score"
    )
    expect(page.locator("#discovery-status")).to_contain_text("40 listings found · 2 checked in detail")
    from pathlib import Path

    out = Path("reports/lv-06-20261104")
    out.mkdir(exist_ok=True)
    first.screenshot(path=str(out / "authored-result-desktop.png"))
    summary = first.locator(".lot-evidence > summary")
    summary.focus()
    summary.press("Enter")
    expect(first.locator(".lot-evidence")).to_have_attribute("open", "")
    expect(first.locator(".lot-evidence")).to_contain_text("Venusaur")
    expect(first.locator(".lot-evidence")).to_contain_text("7 comparable sales")
    expect(first.locator(".lot-evidence")).to_contain_text("duplicate: 2")
    expect(first.locator(".lot-evidence")).to_contain_text("<script>unsafe</script>")
    assert page.locator(".lot-evidence script").count() == 0
    for width in (320, 390, 1280):
        page.set_viewport_size(dict(width=width, height=1000))
        page.add_style_tag(content="html {font-size:200% !important}")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth+1")
        for element in page.locator(".lot-result-controls select").all():
            box = element.bounding_box()
            assert box and box["width"] > 0 and box["x"] >= 0 and box["x"] + box["width"] <= width + 1
    summary.press("Enter") if summary.evaluate("e=>e.parentElement.open") else None
    page.set_viewport_size(dict(width=320, height=900))
    first.screenshot(path=str(out / "authored-result-narrow-enlarged.png"))
    page.locator("#lot-value-basis").select_option("guide")
    expect(page.locator(".discovery-card")).to_have_count(1)
    expect(page.locator(".discovery-card")).to_contain_text("Authored partial lot")
    assert all(method == "GET" for method, _, _ in calls)
    assert not errors


def test_independent_bin_rank_and_native_cohorts(ui):
    from playwright.sync_api import expect

    page, base, model, calls, control, pending, errors = ui
    a, b = offer("a", rank=1), offer("b", rank=2)
    a["value_order"]["lanes"]["buy_it_now"]["rank"] = 2
    b["value_order"]["lanes"]["buy_it_now"]["rank"] = 1
    for row, cohort, total in ((a, "cohort-a", "5.00"), (b, "cohort-b", "999.00")):
        row["lot_value"]["native_guides"] = [
            dict(
                cohort=cohort,
                provider=cohort,
                reference_date="2026-11-04",
                date_basis="publisher_build",
                total=total,
                subtotal=total,
                complete=True,
                priced_quantity=2,
                references=[],
            )
        ]
        row["value_order"]["native"] = [
            dict(lane=lane, cohort=cohort, rank=1) for lane in ("auction", "buy_it_now")
        ]
    model["results"] = [a, b]
    open_results(ui, advanced=True)
    page.locator("#lot-buying-mode").select_option("buy_now")
    expect(page.locator(".discovery-card").first).to_have_id("offer-b")
    page.locator("#lot-buying-mode").select_option("auction")
    expect(page.locator(".discovery-card").first).to_have_id("offer-a")
    page.locator("#lot-value-sort").select_option("native")
    expect(page.locator(".lot-group-heading").first).to_contain_text("cohort-a")
    expect(page.locator(".lot-group-heading")).to_have_count(2)
    open_details(page, "a")
    expect(page.locator(".native-guide").first).to_contain_text("Shipping/tax basis unknown")
    assert not errors


@pytest.mark.parametrize(
    "state, message",
    [
        ("queued", "Hunt queued"),
        ("discovering", "Discovering offers"),
        ("fetching_details", "Fetching selected seller details"),
        ("assessing", "Assessing supplied contents"),
        ("busy", "Dex is busy"),
        ("exhausted", "capacity is exhausted"),
        ("failed", "ended after a failure"),
        ("restart_uncertain", "no requests were replayed"),
        ("expired", "Temporary results expired"),
    ],
)
def test_progress_and_terminal_recovery_without_replay(ui, state, message):
    from playwright.sync_api import expect

    page, base, model, calls, control, pending, errors = ui
    model.update(
        state=state, running=state in {"queued", "discovering", "fetching_details", "assessing"}, results=[]
    )
    open_results(ui)
    expect(page.locator("#discovery-status")).to_contain_text(message)
    assert page.locator("#discovery-status").get_attribute("role") == "status"
    if not model["running"]:
        expect(page.locator("#discovery-search")).to_be_enabled()
        expect(page.locator("#discovery-stop")).to_be_hidden()
    assert not any(method == "POST" for method, _, _ in calls)
    assert not errors


def test_all_unavailable_distinguishes_unfetched_from_unresolved(ui):
    from playwright.sync_api import expect

    page, base, model, calls, control, pending, errors = ui
    first, second = offer("unresolved", "unpriced"), offer("unfetched", "unpriced", rank=2)
    first["lot_value"].update(
        contents_state="unresolved",
        total=None,
        subtotal=None,
        references=[],
        reason="Supplied contents could not be resolved.",
    )
    second.pop("lot_value")
    second.update(evidence_kind="seller_summary", assessment_state="unprocessed")
    model["results"] = [first, second]
    open_results(ui)
    expect(page.locator(".discovery-card")).to_have_count(2)
    open_details(page, "unresolved")
    expect(page.locator("#offer-unresolved")).to_contain_text("Supplied contents could not be resolved")
    expect(page.locator("#offer-unfetched")).to_contain_text("Contents need checking")
    expect(page.locator("#lot-values-status")).to_contain_text("No supported value comparisons yet")
    assert not errors


def test_withdrawal_late_response_stop_and_expiry(ui):
    from playwright.sync_api import expect

    page, base, model, calls, control, pending, errors = ui
    model.update(state="assessing", running=True)
    open_results(ui)
    open_details(page)
    expect(page.get_by_text("$40.00 ungraded lot value", exact=True)).to_be_visible()
    control["hold"] = True
    page.wait_for_timeout(750)
    assert pending
    control["sources"] = []
    expect(page.get_by_text("$40.00 ungraded lot value", exact=True)).to_have_count(0)
    handler, stale = pending.pop(0)
    handler.fulfill(json=stale)
    page.wait_for_timeout(100)
    expect(page.get_by_text("$40.00 ungraded lot value", exact=True)).to_have_count(0)
    page.locator("#discovery-stop").click()
    expect(page.locator(".discovery-card")).to_have_count(0)
    for handler, stale in pending:
        handler.fulfill(json=stale)
    expect(page.locator("#discovery-status")).to_contain_text("Hunt stopped")
    assert len([c for c in calls if c[0] == "POST"]) == 1
    control.update(hold=False, sources=["authored-source"])
    model.update(state="partial", running=False, results=[offer()], expires_in_seconds=1)
    open_results(ui)
    expect(page.locator(".discovery-card")).to_have_count(1)
    expect(page.locator(".discovery-card")).to_have_count(0, timeout=4000)
    assert not errors


def test_one_action_automatic_assessment_and_local_back(ui):
    from playwright.sync_api import expect

    page, base, model, calls, control, pending, errors = ui
    page.goto(base + "/shopping/?q=Lapras")
    page.locator("#discovery-search").click()
    open_details(page)
    expect(page.get_by_text("$40.00 ungraded lot value", exact=True)).to_be_visible()
    posts = [c for c in calls if c[0] == "POST"]
    assert len(posts) == 1 and posts[0][2]["acquisition_contract"] == "dex-lot-hunt-v2"
    seller = page.locator("#offer-complete .lot-buy a").first
    assert seller.get_attribute("target") == "_blank"
    assert seller.get_attribute("href") == "https://www.ebay.com/itm/123456789012?var=123456789013"
    page.locator(".result-settings > summary").click()
    page.locator("#lot-buying-mode").select_option("buy_now")
    # Ordinary Back restores only the handle and filters; it must read values again.
    page.goto(base + "/shopping/check/")
    page.go_back()
    open_details(page)
    expect(page.get_by_text("$40.00 ungraded lot value", exact=True)).to_be_visible()
    expect(page.locator("#lot-buying-mode")).to_have_value("buy_now")
    assert len([c for c in calls if c[0] == "POST"]) == 1
    assert not errors


def test_local_refresh_preserves_expansion_focus_and_clears_changed_authority(ui):
    from playwright.sync_api import expect

    page, base, model, calls, control, pending, errors = ui
    open_results(ui)
    open_details(page)
    summary = page.locator("#offer-complete .lot-evidence > summary")
    summary.focus()
    summary.press("Enter")
    model["results"][0]["lot_value"]["reason"] = "Changed current source condition; still a dated benchmark."
    page.wait_for_timeout(5500)
    expect(summary).to_be_focused()
    expect(page.locator("#offer-complete .lot-evidence")).to_have_attribute("open", "")
    expect(page.locator("#offer-complete")).to_contain_text("Changed current source condition")
    model.update(state="conflict", running=False, results=[])
    # Returning from a seller tab must withhold old values before the read finishes.
    control["hold"] = True
    page.evaluate("window.dispatchEvent(new Event('focus'))")
    expect(page.get_by_text("$40.00 ungraded lot value", exact=True)).to_have_count(0)
    for _ in range(40):
        if pending:
            break
        page.wait_for_timeout(50)
    assert pending
    handler, value = pending.pop()
    handler.fulfill(json=value)
    expect(page.locator(".discovery-card")).to_have_count(0)
    assert all(method == "GET" for method, _, _ in calls)
    assert not errors


def test_corrected_benchmark_is_visible_when_strict_ceiling_is_unavailable(browser_app):
    from playwright.sync_api import expect

    state, page, base, requests, errors = browser_app
    model = offer()["lot_value"]
    cost = dict(
        base_price="1.00",
        base_plus_shipping="6.00",
        before_tax="6.00",
        full_delivered_cost=None,
        reference_difference=None,
        unknown_or_ineligible_components=["tax"],
    )
    comparison = dict(
        assessment=dict(
            ends_at=None,
            auction=True,
            evidence=[],
            costs=dict(listing_observation=cost, planned_bid=cost),
            priced=0,
            units=2,
            subtotal=None,
            value=None,
            maximum=None,
            issues=["Condition-specific ceiling unavailable"],
            seller_url=None,
        ),
        benchmark=dict(
            assessment_version="dex-lot-value-v3",
            basis_label="Mixed",
            priced_card_quantity=2,
            unpriced_card_quantity=0,
            result=dict(full_lot_total="40.00", known_selected_subtotal="40.00"),
            benchmark_costs=model["benchmark_costs"],
            references=[],
            native_guides=[],
            gaps=[],
        ),
    )

    def compare(route):
        route.fulfill(
            json=dict(
                comparison,
                authority=dict(
                    account_id=state["actor"].user_id,
                    binding=route.request.header_value("X-Dex-Shopping-Binding"),
                    generation=1,
                ),
            )
        )

    page.route("**/api/shopping/listing/compare/", compare)
    page.goto(base + "/shopping/check/")
    page.locator("#manual-entry").click()
    page.locator("#check-compare").click()
    expect(page.locator(".review-benchmark")).to_contain_text("$40.00 comparable lot reference")
    expect(page.locator(".review-benchmark")).to_contain_text("$-15.00 before tax")
    expect(page.locator("#check-results")).to_contain_text("Recommendation unavailable")
    page.locator("#review-price").fill("7")
    expect(page.locator("#check-results")).to_be_hidden()
    assert not errors


@pytest.mark.no_cover
def test_forty_summary_two_assessment_local_filter_budget(ui):
    import json
    import math
    from pathlib import Path

    from playwright.sync_api import expect

    page, base, model, calls, control, pending, errors = ui
    model["results"] = [offer(), offer("partial", "partial", "guide", 2)]
    for index in range(38):
        row = offer(f"unprocessed-{index}", "unpriced", rank=index + 3)
        row.pop("lot_value")
        row.update(evidence_kind="seller_summary", assessment_state="unprocessed")
        model["results"].append(row)
    open_results(ui)
    expect(page.locator(".discovery-card")).to_have_count(40)
    samples = []
    for index in range(20):
        samples.append(
            page.evaluate(
                """async basis=>{
          const select=document.querySelector('#lot-value-basis');
          const start=performance.now();select.value=basis;select.dispatchEvent(new Event('change'));
          await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
          return {elapsed_ms:performance.now()-start,shown:document.querySelectorAll('.discovery-card').length};
        }""",
                "guide" if index % 2 == 0 else "all",
            )
        )
    times = sorted(s["elapsed_ms"] for s in samples)
    report = dict(
        samples=samples,
        p95_ms=times[math.ceil(0.95 * len(times)) - 1],
        worst_ms=max(times),
        limit_ms=300,
        parse_dom_paint_limit_ms=70,
        summaries=40,
        enriched=2,
        provider_wait="None: pre-received authored batch; network discovery latency is not measured",
        customer_data=False,
    )
    out = Path("reports/lv-06-20261104")
    out.mkdir(exist_ok=True)
    import sys

    (out / f"local-filter-{sys.version_info.minor}.json").write_text(json.dumps(report, indent=2))
    assert all(s["shown"] == (1 if i % 2 == 0 else 40) for i, s in enumerate(samples))
    assert report["p95_ms"] <= 70, report
    assert all(method == "GET" for method, _, _ in calls)
    assert not errors


@pytest.mark.parametrize("guide", [None, "normalized", "native"])
def test_find_lots_forty_rows_worker_and_local_evidence(browser_app, monkeypatch, guide):
    """Use the ordinary page/server/worker; substitute only local configuration and the provider."""
    import json
    from types import SimpleNamespace

    import httpx
    from playwright.sync_api import expect
    from test_lv03_hunt import Stream
    from test_lv03_hunt import offer as listing

    from pokemon_hunter.beta import discovery as discovery
    from pokemon_hunter.beta import hunter_policy, lot_hunt
    from pokemon_hunter.beta.discovery_transport import Transport

    state, page, base, requests, errors = browser_app
    from concurrent.futures import ThreadPoolExecutor

    from perf04_helpers import prepare_reads
    from price_snapshot_helpers import package, stage
    from test_lv02_native_guides import native_package
    from test_lv02_valuation import v2_package

    from pokemon_hunter.beta import collection, price_snapshots

    def admit():
        (state["root"] / "SYNTHETIC_ONLY").touch()
        pid = state["by_legacy"]["a"]["id"]
        collection.execute(
            "UPDATE printings SET edition='unlimited',finish='normal',variant='normal',unresolved_fields='[]' WHERE id=%s",
            [pid],
        )
        prepare_reads(state)
        data = package(dict(entries={pid: price_snapshots.entries()[pid]}), permanent=False)
        data = (native_package if guide == "native" else v2_package)(data)
        now = datetime.now(UTC)
        data.update(expires_at=(now + timedelta(days=1)).isoformat(), release_month=now.strftime("%Y-%m"))
        from pokemon_hunter.beta import shopping

        day = now.date() if guide == "native" else now.astimezone(shopping.TZ).date()
        data["records"][0].update(as_of=day.isoformat(), captured_at=now.isoformat())
        price_snapshots.activate(stage(data), None, now=now)
        return data["version"]

    with ThreadPoolExecutor(max_workers=1) as executor:
        if guide:
            source_version = executor.submit(admit).result()
        executor.submit(
            hunter_policy.select,
            state["actor"],
            dict(
                enabled=True,
                per_hunt_limit=5,
                daily_limit=5,
                timezone="UTC",
                recurring=False,
                expires_at=None,
                revision=0,
            ),
        ).result()
    monkeypatch.setattr(discovery, "_tokens", {})
    monkeypatch.setattr(discovery.ebay_hunts, "status", lambda: dict(enabled=True, configured=True))
    monkeypatch.setattr(
        discovery.ebay_hunts,
        "configuration",
        lambda: (
            SimpleNamespace(environment="production"),
            dict(EBAY_CLIENT_ID="authored", EBAY_CLIENT_SECRET="authored"),
        ),
    )
    calls = []
    offers = [listing(i, lane="buy_it_now" if i < 20 else "auction", title="37-card lot") for i in range(40)]
    for i in (7, 35):
        offers[i]["title"] = "37-card mixed lot · Lapras Fossil · cards included: Lapras 10/62"
    offers[7]["shippingOptions"][0]["shippingCostType"] = "FIXED"

    async def respond(req):
        calls.append(req.url.path)
        if "oauth2" in req.url.path:
            body = dict(access_token="authored", expires_in=3600, token_type="Bearer")
        elif "item_summary" in req.url.path:
            body = dict(
                itemSummaries=offers[:20] if "FIXED_PRICE" in req.url.params["filter"] else offers[20:]
            )
        else:
            source = next(row for row in offers if req.url.path.endswith(row["itemId"]))
            body = dict(
                source,
                description="<p>Seller lists 1x Lapras, printing unspecified.</p>"
                + "<p>Shipping "
                + "a" * 1200
                + "</p>",
            )
            if guide:
                body["description"] += "<p>2x Ivysaur Base Set 2 #44 English Unlimited Non Holo</p>"
        return httpx.Response(200, stream=Stream(json.dumps(body).encode()))

    monkeypatch.setattr(lot_hunt, "Transport", lambda: Transport(transport=httpx.MockTransport(respond)))
    page.goto(base + "/shopping/?q=Lapras")
    page.get_by_role("button", name="Find lots", exact=True).click()
    expect(page.locator("#discovery-status")).to_contain_text(
        "40 listings found · 2 checked in detail", timeout=30000
    )
    page.locator(".result-settings > summary").click()
    page.locator("#lot-value-sort").select_option("value")
    heads = page.locator(".lot-group-heading h3")
    groups = (
        ["Partially assessed · 1", "Unknown delivered cost · 1", "Unprocessed · 38"]
        if guide == "normalized"
        else ["Assessed without a normalized value · 2", "Unprocessed · 38"]
    )
    expect(heads).to_have_text(groups)
    expect(page.locator(".discovery-card")).to_have_count(40)
    row = page.locator(".discovery-card").filter(has=page.locator(".lot-evidence")).first
    row.locator(".lot-more > summary").click()
    if guide:
        expect(row.locator(".lot-value")).to_contain_text("$5.10")
        if guide == "native":
            page.locator("#lot-value-sort").select_option("native")
            expect(heads.first).to_contain_text("Publisher guide contents")
            expect(heads.first).to_contain_text(" · 2")
            expect(heads.last).to_contain_text("No compatible publisher guide · 38")
            page.locator("#lot-value-sort").select_option("value")
    if not row.locator(".lot-more").evaluate("e=>e.open"):
        row.locator(".lot-more > summary").click()
    with page.expect_response(lambda r: "/evidence/" in r.url) as response:
        row.locator(".lot-evidence > summary").click()
    assert response.value.ok
    expect(row.locator(".lot-evidence")).to_contain_text("Seller lists 1x Lapras")
    assert len(calls) == 5
    result_sizes = []
    page.on("response", lambda r: result_sizes.append(r) if "/discovery/?" in r.url else None)
    row.locator(".review-offer").click()
    page.wait_for_url("**/shopping/check/**")
    page.go_back()
    expect(heads).to_have_text(groups)
    sized = [len(r.body()) for r in result_sizes if r.ok and len(r.json().get("results", [])) == 40]
    assert sized and max(sized) <= 120 * 1024
    print("Find lots authenticated JSON bytes", max(sized), "groups", heads.all_text_contents())
    assert len(calls) == 5 and not errors
    if guide:
        with ThreadPoolExecutor(max_workers=1) as executor:
            executor.submit(price_snapshots.remove, source_version).result()
        expect(page.locator(".lot-value").filter(has_text="$5.10")).to_have_count(0, timeout=10000)
        expect(heads).to_have_text(["Assessed without a normalized value · 2", "Unprocessed · 38"])
        assert len(calls) == 5


def test_changed_evidence_closes_disclosure_without_refresh_loop(ui):
    from playwright.sync_api import expect

    page, base, model, calls, control, pending, errors = ui
    model["results"][0].update(evidence_version="original", content_revision=4)
    evidence_calls = []

    def mismatch(route):
        evidence_calls.append(route.request.url)
        binding = route.request.header_value("X-Dex-Shopping-Binding")
        # Reuse the account binding from the ordinary intercepted status reply.
        account = page.locator("body").get_attribute("data-navigation-account")
        route.fulfill(
            json=dict(
                run_id=model["run_id"],
                id="complete",
                content_revision=4,
                evidence_version="changed",
                lot_value={},
                authority=dict(account_id=account, binding=binding),
            )
        )

    page.route("**/api/shopping/discovery/*/evidence/**", mismatch)
    open_results(ui)
    open_details(page)
    panel = page.locator("#offer-complete .lot-evidence")
    panel.locator("summary").click()
    expect(panel).not_to_have_attribute("open", "")
    expect(page.locator("#offer-complete .lot-value")).to_contain_text("$40.00")
    # Exercise the next ordinary local status check; no second disclosure request.
    page.wait_for_timeout(5500)
    assert len(evidence_calls) == 1 and not errors


def test_local_source_busy_recovers_values_without_repeating_hunt(ui):
    from playwright.sync_api import expect

    page, base, model, calls, control, pending, errors = ui
    row = model["results"][0]
    row["buying_order"] = {
        "combined": dict(
            rank=1,
            reason="Current authored guide estimate",
            contents="Lapras",
            estimate_amount="100",
            estimate_complete=True,
            price_to_estimate=".87",
            all_pre_2000=True,
        )
    }
    control["source_busy"] = True
    open_results(ui)
    expect(page.locator("#lot-values-reload")).to_be_visible()
    expect(page.locator(".lot-value-badge")).not_to_contain_text("87% of value")
    control["source_busy"] = False
    expect(page.locator(".lot-value-badge")).to_contain_text("87% of value", timeout=10000)
    assert any("view=values" in url for method, url, _ in calls if method == "GET")
    assert not any(method == "POST" for method, _, _ in calls)
    assert not errors


def test_quick_value_filter_and_background_checks_do_not_overlap(ui):
    from playwright.sync_api import expect

    page, base, model, calls, control, pending, errors = ui
    model["results"][0]["buying_order"] = {
        "combined": dict(
            rank=1,
            contents="Lapras",
            estimate_amount="100",
            estimate_complete=True,
            price_to_estimate=".87",
        )
    }
    unknown = offer("unknown")
    unknown["buying_order"] = {"combined": dict(rank=2, contents="Unknown")}
    model["results"].append(unknown)
    open_results(ui)
    expect(page.locator("#discovery-shown")).to_have_text("2 options")
    page.get_by_role("combobox", name="Value", exact=True).select_option("below")
    expect(page.locator("#discovery-shown")).to_have_text("1 option")
    expect(page.locator(".lot-value-badge")).to_have_class("lot-value-badge tone-good")
    control["hold"] = True
    page.wait_for_timeout(7500)
    assert len(pending) == 1, calls
    before = len([url for _, url, _ in calls if "/price-source-status/" in url])
    page.wait_for_timeout(1200)
    assert len(pending) == 1
    assert len([url for _, url, _ in calls if "/price-source-status/" in url]) == before
    control["hold"] = False
    handler, value = pending.pop()
    handler.fulfill(json=value)
    expect(page.locator("#discovery-shown")).to_have_text("1 option")
    assert not any(method == "POST" for method, _, _ in calls)
    assert not errors
