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


def open_results(ui):
    page, base, model, *_ = ui
    page.goto(base + f"/shopping/?run_id={model['run_id']}&q=Lapras")
    page.locator("#discovery-results:not([hidden])").wait_for()


def test_glance_groups_dual_costs_evidence_keyboard_and_layout(ui):
    from playwright.sync_api import expect

    page, base, model, calls, control, pending, errors = ui
    model["results"] = [
        offer(),
        offer("partial", "partial", "guide", 2),
        offer("unknown", "unknown_cost", "sold_estimate", 3),
        offer("unpriced", "unpriced", rank=4),
    ]
    open_results(ui)
    for label in (
        "Complete assessments",
        "Partially assessed",
        "Unknown delivered cost",
        "Unpriced / unprocessed",
    ):
        expect(page.locator(".lot-group-heading").filter(has_text=label)).to_be_visible()
    first = page.locator("#offer-complete")
    expect(first.get_by_text("$40.00 ungraded lot value", exact=True)).to_be_visible()
    expect(
        first.get_by_text("Buy It Now + shipping: $15.00 above reference · before tax", exact=True)
    ).to_be_visible()
    expect(first.locator(".discovery-amounts")).to_contain_text("$6.00")
    expect(first.locator(".discovery-amounts")).to_contain_text("$55.00")
    expect(page.locator("#offer-partial .partial-difference").first).to_contain_text(
        "not a whole-lot bargain score"
    )
    expect(page.locator("#discovery-status")).to_contain_text("2/2 enriched · 2 assessed · 38 unprocessed")
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
    open_results(ui)
    page.locator("#lot-buying-mode").select_option("buy_now")
    expect(page.locator(".discovery-card").first).to_have_id("offer-b")
    page.locator("#lot-buying-mode").select_option("auction")
    expect(page.locator(".discovery-card").first).to_have_id("offer-a")
    page.locator("#lot-value-sort").select_option("native")
    expect(page.locator(".lot-group-heading").first).to_contain_text("cohort-a")
    expect(page.locator(".lot-group-heading")).to_have_count(2)
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
    first["lot_value"].update(contents_state="unresolved", reason="Supplied contents could not be resolved.")
    second.pop("lot_value")
    second.update(evidence_kind="seller_summary", assessment_state="unprocessed")
    model["results"] = [first, second]
    open_results(ui)
    expect(page.locator(".discovery-card")).to_have_count(2)
    expect(page.locator("#offer-unresolved")).to_contain_text("Supplied contents could not be resolved")
    expect(page.locator("#offer-unfetched")).to_contain_text("Full details have not been assessed")
    expect(page.locator("#lot-values-status")).to_contain_text("No usable prices in this batch")
    assert not errors


def test_withdrawal_late_response_stop_and_expiry(ui):
    from playwright.sync_api import expect

    page, base, model, calls, control, pending, errors = ui
    model.update(state="assessing", running=True)
    open_results(ui)
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
    expect(page.get_by_text("$40.00 ungraded lot value", exact=True)).to_be_visible()
    posts = [c for c in calls if c[0] == "POST"]
    assert len(posts) == 1 and posts[0][2]["acquisition_contract"] == "dex-lot-hunt-v2"
    seller = page.locator("#offer-complete .seller a").first
    assert seller.get_attribute("target") == "_blank"
    assert seller.get_attribute("href") == "https://www.ebay.com/itm/123456789012?var=123456789013"
    page.locator("#lot-buying-mode").select_option("buy_now")
    # Ordinary Back restores only the handle and filters; it must read values again.
    page.goto(base + "/shopping/check/")
    page.go_back()
    expect(page.get_by_text("$40.00 ungraded lot value", exact=True)).to_be_visible()
    expect(page.locator("#lot-buying-mode")).to_have_value("buy_now")
    assert len([c for c in calls if c[0] == "POST"]) == 1
    assert not errors


def test_local_refresh_preserves_expansion_focus_and_clears_changed_authority(ui):
    from playwright.sync_api import expect

    page, base, model, calls, control, pending, errors = ui
    open_results(ui)
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
    expect(page.locator(".review-benchmark")).to_contain_text("$40.00 ungraded lot value")
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
