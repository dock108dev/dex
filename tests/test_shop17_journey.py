"""Ordinary screen to screen decisions on controlled auction evidence."""

import json
import math
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from browser_measurements import isolated_network
from perf04_helpers import prepare_reads
from price_snapshot_helpers import package, stage
from runtime_process import close_pipes, read_port
from shop_action_measure import take
from test_account_read_performance import ownership
from test_b1 import env as env
from test_b2 import apply
from test_b2 import b2 as b2
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_catalog_read_performance import seed
from test_effective_collection import cx as cx
from test_migration import snapshot as snapshot
from test_perf04_interactions import candidate
from test_sealed_catalog import e1 as e1

pytestmark = pytest.mark.allow_hosts(["127.0.0.1"])
SELLER = "https://www.ebay.com/itm/123456789012"


def prepare(cx, count, copies):
    from django.conf import settings

    from pokemon_hunter.beta import collection, hunter_policy, price_snapshots, shopping

    root = cx["root"]
    for marker in ("SYNTHETIC_ONLY", "B2_ISOLATED", "B3_ISOLATED", "B4_ISOLATED"):
        (root / marker).touch()
    (root / "secret.key").write_text(settings.SECRET_KEY)
    collection.execute("UPDATE printings SET edition='standard',finish='normal',variant='normal'")
    venus = cx["by_legacy"]["c"]
    collection.execute(
        "UPDATE printings SET set_id=%s, attributes=%s,collector_number='18',finish='holo' WHERE id=%s",
        [venus["set_id"], json.dumps(venus["attributes"]), cx["by_legacy"]["b"]["id"]],
    )
    now = datetime.now(UTC)
    records, contracts = [], {}
    for key, price in (("c", "10"), ("a", "7")):
        pid = cx["by_legacy"][key]["id"]
        source = package({"entries": {pid: price_snapshots.entries()[pid]}}, permanent=False)
        row = source["records"][1]
        row.update(
            grader="PSA",
            value=price,
            original_money=price,
            as_of=str(now.astimezone(shopping.TZ).date()),
            captured_at=now.isoformat(),
        )
        policy = source["contract"]
        policy["fields"][row["field"]]["grader"] = "PSA"
        policy["review_id"] += key
        records.append(dict(row, contract_id=policy["review_id"]))
        contracts[policy["review_id"]] = dict(
            contract=policy, expires_at=(now + timedelta(days=1)).isoformat()
        )
    value = dict(
        schema="dex-price-snapshot-v2",
        version=source["version"],
        release_month=now.strftime("%Y-%m"),
        records=records,
        contracts=contracts,
    )
    seed(cx, count)
    # Same reviewed lot and two source contracts; fill the rest of each release
    # with published unrelated printings, up to the dedicated volume gate size.
    total = 7653 if count == 33083 else 15306
    catalog = price_snapshots.entries()
    source_keys = list(contracts)
    excluded = {p["id"] for p in cx["by_legacy"].values()}
    for printing in catalog.values():
        if printing["id"] in excluded or not all(
            printing.get(k) for k in ("language", "edition", "finish", "variant")
        ):
            continue
        source = package({"entries": {printing["id"]: printing}}, permanent=False)
        source_key = source_keys[((len(records) - 2) // 4) % 2]
        policy = contracts[source_key]["contract"]
        policy["mappings"].update(source["contract"]["mappings"])
        for row in source["records"][: total - len(records)]:
            row.update(
                contract_id=source_key,
                grader=policy["fields"][row["field"]]["grader"],
                as_of=str(now.astimezone(shopping.TZ).date()),
                captured_at=now.isoformat(),
            )
            records.append(row)
        if len(records) == total:
            break
    assert len(records) == total
    price_snapshots.activate(stage(value), None, now=now)
    ownership(cx, copies)
    # Leave species 3 missing in the account with the scaled inventory.
    collection.execute(
        "UPDATE owned_copies SET printing_id=%s WHERE printing_id IN (SELECT id FROM printings WHERE json_extract(attributes,'$.pokemon_dex')=3)",
        [cx["by_legacy"]["a"]["id"]],
    )
    goal = (
        apply(cx, "goal", dict(name="Frozen Kanto", goal_kind="original151"))["changes"][0]["after"]
        if count == 66166
        else None
    )
    prepare_reads(cx)
    hunter_policy.select(
        cx["actor"],
        dict(
            enabled=True,
            per_hunt_limit=5,
            daily_limit=100,
            timezone="America/New_York",
            recurring=False,
            expires_at=(datetime.now(UTC) + timedelta(days=1)).isoformat(),
            revision=0,
        ),
    )
    (root / "engineering-offer.json").write_text(
        json.dumps(
            dict(
                itemId="v1|123456789012|0",
                title="Venusaur and Ivysaur lot of 3 cards",
                shortDescription="1x Venusaur Base Set 2 #18; 2x Ivysaur Base Set 2 #44",
                buyingOptions=["AUCTION"],
                currentBidPrice=dict(value="8", currency="USD"),
                itemEndDate=(datetime.now(UTC) + timedelta(hours=6)).isoformat(),
                itemWebUrl=SELLER,
                categoryId="183455",
            )
        )
    )
    return goal


def open_controlled_seller(page, link):
    # Intercept the new tab's first navigation only while the seller handoff
    # is exercised. Keeping a context route installed intercepts even local
    # requests at Chromium's protocol layer, despite the exact URL matcher.
    def intercept(route):
        route.fulfill(content_type="text/html", body="Intercepted seller")

    page.context.route(SELLER, intercept)
    try:
        with page.context.expect_page() as opened:
            link.press("Enter")
        seller = opened.value
        seller.get_by_text("Intercepted seller", exact=True).wait_for()
        return seller
    finally:
        page.context.unroute(SELLER, intercept)


def changed_evidence(page, root, frozen):
    """Explicitly compare an unsupported grade, a quantity conflict and expired sources."""
    from playwright.sync_api import expect

    out = page.locator("#check-results")

    def compare():
        page.locator("#check-compare").press("Enter")
        expect(out).to_contain_text("Recommendation unavailable")
        out.locator(":scope > details > summary").press("Enter")
        return out.inner_text()

    group = page.locator("#review-cards .contents-entry").filter(
        has=page.locator("h3").filter(has_text="Ivysaur")
    )
    group.get_by_label("Literal grader").select_option("BGS")
    partial = compare()
    assert "1 of 3" in partial and "BGS 8" in partial and "Whole-lot reference Unavailable" in partial, (
        partial
    )
    group.get_by_label("Literal grader").select_option("PSA")
    group.get_by_label("Cards inside this one lot").fill("3")
    conflict = compare()
    assert "Reconcile the printing and quantity for" in conflict and "ivysaur" in conflict.casefold(), (
        conflict
    )
    group.get_by_label("Cards inside this one lot").fill("2")
    (root / "advance-snapshot-clock").touch()
    try:
        expired = compare()
        assert "0 of 3" in expired and "matching this printing and PSA 8" in expired, expired
    finally:
        (root / "advance-snapshot-clock").unlink()
    from pokemon_hunter.beta import price_snapshots

    page.locator("#check-compare").press("Enter")
    expect(out).to_contain_text("Binding limit: budget")
    out.locator(":scope > details > summary").press("Enter")
    link = out.locator("a")
    assert link.get_attribute("href") == SELLER
    seller = open_controlled_seller(page, link)
    version = price_snapshots.state()["current"]
    descriptor = price_snapshots.read(price_snapshots.directory() / (version + ".json"))
    key = "fixturea" if frozen else "fixturec"
    digest = next(d for d, m in descriptor["sources"].items() if m["review_id"] == key)
    price_snapshots.sources.remove_source(digest)
    seller.close()
    page.bring_to_front()
    page.evaluate("window.dispatchEvent(new FocusEvent('focus'))")
    expect(out).to_be_hidden()
    withdrawn = compare()
    assert ("1 of 3" if frozen else "2 of 3") in withdrawn
    subtotal = "Condition-specific subtotal $10.00" if frozen else "Condition-specific subtotal $14.00"
    assert subtotal in withdrawn
    assert "matching this printing and PSA 8" in withdrawn
    return dict(partial=partial, conflicting=conflict, expired=expired, withdrawn=withdrawn)


def journey(page, base, goal, cx, report, width, zoom, exercise_changes):
    from playwright.sync_api import expect

    samples = report["samples"]
    probes = {
        "missing picker": (
            '#discovery-target:enabled:has(option[value="3"])',
            "/api/shopping/discovery/targets/",
        ),
        "controlled search": (".compact-lot", "/api/shopping/discovery/"),
        "candidate": (None, "/api/shopping/listing/candidate/"),
        "use offer": ("#review-cards .contents-entry", "/api/shopping/listing/review/"),
        "compare": ("#check-results:not([hidden]) a", "/api/shopping/listing/compare/"),
        "return": ("#check-results:not([hidden]):not([data-pending]) a", "/api/shopping/listing/return/"),
        "back": (None, "/api/shopping/discovery/"),
    }

    def measure(label, action, ready):
        if label in probes:
            css, path = probes[label]
            destination = None
            if label == "back":
                destination = 'body:has(#discovery-target:enabled option[value="3"]:checked) .compact-lot'
            # Keyboard actions start in the browser before product event handlers,
            # excluding the driver's round trip between arming and key delivery.
            # Seller return is a close/focus sequence with its own explicit boundary.
            marker = "shopMark" if label == "return" else "shopArm"
            page.evaluate(
                "([marker,kind,css,dest])=>window[marker](kind,css,dest)",
                [marker, label, css, destination],
            )
            action()
            take(page, report["browser"], [], label, path)
            datum = report["browser"]["samples"][label][-1]
            datum.update(width=width, text_percent=zoom)
            if label in ("compare", "return"):
                assert len(datum["parses"]) == 1
            ready()
            samples.setdefault(label, []).append(datum["elapsed"])
            return
        start = time.perf_counter()
        action()
        ready()
        page.evaluate("()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))")
        samples.setdefault(label, []).append(round((time.perf_counter() - start) * 1000, 2))

    start = time.perf_counter()
    loc = page.locator

    def edit(label, control, action, expected):
        def ready():
            assert control.input_value() == expected

        measure(label, action, ready)

    def enter():
        page.goto(base + "/shopping/", wait_until="commit")
        # LV-06 puts the established scoped search behind an explicit disclosure.
        # Include its keyboard opening in the same Shopping timing and budget.
        page.get_by_text("Search options", exact=True).press("Enter")

    measure("Shopping", enter, lambda: loc("#find-missing:enabled").wait_for())
    measure(
        "missing picker",
        lambda: loc("#find-missing").press("Enter"),
        lambda: loc('#discovery-target:enabled option[value="3"]').wait_for(state="attached"),
    )
    assert page.evaluate("parseFloat(getComputedStyle(document.documentElement).fontSize)") == 16 * zoom / 100
    if goal:
        goal_start = time.perf_counter()
        with page.expect_response(lambda r: "/discovery/targets/" in r.url and goal["id"] in r.url):
            loc("#discovery-goal").select_option(goal["id"])
        loc('#discovery-target:enabled option[value="3"]').wait_for(state="attached")
        page.evaluate("()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))")
        samples.setdefault("goal picker", []).append((time.perf_counter() - goal_start) * 1000)
    target = loc("#discovery-target")
    edit("choose target", target, lambda: target.select_option("3"), "3")
    budget = loc("#discovery-budget")
    edit("budget", budget, lambda: budget.fill("20"), "20")
    vintage = loc("#discovery-prefer-vintage")
    measure("vintage preference", vintage.check, lambda: expect(vintage).to_be_checked())

    def hunt_ready():
        loc(".compact-lot").first.wait_for()
        expect(loc("#discovery-stop")).to_be_hidden()
        expect(loc("#discovery-status")).to_contain_text("1 listings found · 1 checked in detail")

    measure(
        "controlled search",
        lambda: loc("#discovery-search").press("Enter"),
        hunt_ready,
    )
    result = loc("#discovery-cards").inner_text()
    loc(".lot-more > summary").first.press("Enter")
    measure(
        "candidate",
        lambda: loc(".review-offer").first.press("Enter"),
        lambda: loc("#use-listing:enabled").wait_for(),
    )
    resources = report["browser"]["samples"]["candidate"][-1]["resources"]
    assert [r["path"] for r in resources if r["path"].endswith(".css")] == [
        "/collection-assets/listing-shell.css"
    ]
    # This retained review uses the selected offer's admitted printing identities.
    assert not any(r["path"] == "/api/shopping/listing/catalog/" for r in resources)
    loc("#listing-preview > details > summary").first.press("Enter")
    preview = loc("#contents-preview").inner_text()
    assert "2 printing alternatives" in preview and "Seller quantity: 2" in preview, preview
    measure(
        "use offer",
        lambda: loc("#use-listing").press("Enter"),
        lambda: loc("#review-cards .contents-entry").nth(1).wait_for(),
    )
    for key, name in (("c", "Venusaur"), ("a", "Ivysaur")):
        group = loc("#review-cards .contents-entry").filter(has=loc("h3").filter(has_text=name))
        pid = cx["by_legacy"][key]["id"]
        measure(
            "open alternatives " + name,
            lambda: group.locator("summary").filter(has_text="Correct identity").press("Enter"),
            lambda: group.get_by_label("Printing to review").wait_for(),
        )

        # Selecting an alternative adds a second heading inside this group.
        # Address the actual selected printing, including after a DOM redraw.
        checkbox = loc(f'#review-cards .review-include input[data-printing="{pid}"]')

        def include():
            group.get_by_label("Printing to review").select_option(pid)
            checkbox.press("Space")

        measure("include " + name, include, lambda: expect(checkbox).to_be_checked())
        # Inclusion starts with one physical card; group multiplicity is an
        # explicit allocation after checking the itemized seller evidence.
        quantity = group.get_by_label("Cards inside this one lot")
        expect(quantity).to_have_value("1")
        quantity.fill("2" if name == "Ivysaur" else "1")
        group.locator("summary").filter(has_text="optional card details").press("Enter")
        grade = group.get_by_label("Value basis")
        grader = group.get_by_label("Literal grader")
        edit("grade " + name, grade, lambda: grade.select_option("8"), "8")
        edit("grader " + name, grader, lambda: grader.select_option("PSA"), "PSA")
    shipping = loc("#review-shipping")
    edit("shipping", shipping, lambda: shipping.fill("2"), "2")
    page.get_by_text("Bid, budget and listing details", exact=True).press("Enter")
    for field, value in (("tax", "1"), ("other_costs", "0"), ("planned_bid", "12")):
        control = loc("#review-" + field)
        edit(field, control, lambda: control.fill(value), value)
    expect(loc("#review-budget")).to_have_value("20")
    out = loc("#check-results")

    def compare():
        loc("#check-compare").press("Enter")

    measure("compare", compare, lambda: out.locator("a").wait_for())
    out.locator(":scope > details > summary").press("Enter")
    content = out.inner_text()
    assert all(
        s in content
        for s in (
            "3 of 3",
            "$24.00",
            "All-in $15.00",
            "$17.00",
            "PSA 8",
            "https://example.test/product",
            "Binding limit: budget",
        )
    ), content
    assert out.evaluate("e=>e.scrollWidth<=e.clientWidth+1 && e.getBoundingClientRect().right<=innerWidth+1")
    scope = loc("#check-context").inner_text()
    if goal:
        # These reviewed printings are outside the frozen goal. The compact
        # context must not advertise them as additions to that goal.
        assert scope == ""
        expect(loc("#check-context")).to_be_hidden()
    else:
        assert "Potential collection additions: Venusaur" in scope
    link = out.locator("a")
    assert link.get_attribute("href") == SELLER
    link.focus()
    scroll = page.evaluate("scrollY")
    seller_start = time.perf_counter()
    seller = open_controlled_seller(page, link)
    assert seller.url == SELLER and seller.evaluate("window.opener===null")
    samples.setdefault("seller tab", []).append((time.perf_counter() - seller_start) * 1000)

    def close():
        seller.close()
        page.bring_to_front()
        page.evaluate("window.dispatchEvent(new FocusEvent('focus'))")

    expect(out).to_have_attribute("data-pending", "true")
    measure("return", close, lambda: loc("#check-results:not([hidden]):not([data-pending]) a").wait_for())
    assert (
        out.inner_text() == content
        and page.evaluate("scrollY") == scroll
        and link.evaluate("e=>e===document.activeElement")
    )
    assert loc("#check-context").inner_text() == scope
    excluded = time.perf_counter()
    if exercise_changes:
        report["changed_evidence"] = changed_evidence(page, cx["root"], bool(goal))
    start += time.perf_counter() - excluded
    measure("back", lambda: loc("#check-back").press("Enter"), lambda: loc(".compact-lot").first.wait_for())
    assert loc("#discovery-target").input_value() == "3" and loc("#discovery-budget").input_value() == "20"
    assert loc("#discovery-prefer-vintage").is_checked() and loc("#discovery-goal").input_value() == (
        goal["id"] if goal else ""
    )
    samples.setdefault("complete journey", []).append((time.perf_counter() - start) * 1000)
    return dict(scope=scope, result=result, contents=preview, comparison=content)


@pytest.mark.no_cover
@pytest.mark.parametrize("count,copies", [(33083, 5000), (66166, 10000)])
def test_integrated_journey(cx, count, copies):
    from playwright.sync_api import sync_playwright

    goal = prepare(cx, count, copies)
    root = cx["root"]
    digest = candidate()
    report = dict(
        source_sha256=digest,
        printings=count,
        observations=7653 if count == 33083 else 15306,
        added_copies=copies,
        scope="frozen" if goal else "current",
        samples={},
        browser={"samples": {}},
        failures=[],
    )
    proc = subprocess.Popen(
        [sys.executable, "tests/shop17_server.py", str(root), "0"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    try:
        base = f"http://127.0.0.1:{read_port(proc)}"
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            for i in range(20):
                width = (320, 390, 1280)[i % 3]
                zoom = (100, 200)[i % 2]
                with browser.new_context(viewport=dict(width=width, height=940)) as context:
                    context.add_cookies(
                        [dict(name=k, value=v.value, url=base) for k, v in cx["a"].cookies.items()]
                    )
                    context.add_init_script(
                        f"document.addEventListener('DOMContentLoaded',()=>document.documentElement.style.setProperty('font-size','{zoom}%','important'))"
                    )
                    context.add_init_script(path="tests/shop12_browser_probe.js")
                    page = context.new_page()
                    page.set_default_timeout(6000)
                    blocked = isolated_network(page, base)
                    errors = []
                    page.on("pageerror", lambda e: errors.append(str(e)))
                    try:
                        report["answers"] = journey(page, base, goal, cx, report, width, zoom, i == 19)
                    except Exception:
                        report["last_screen"] = page.locator("body").inner_text(timeout=1000)[:9000]
                        raise
                    assert not errors and not blocked
            browser.close()
    finally:
        proc.terminate()
        proc.wait(timeout=15)
        close_pipes(proc)
        assert candidate() == digest
        report["controlled_calls"] = (
            (root / "controlled-calls").read_text().splitlines()
            if (root / "controlled-calls").exists()
            else []
        )
        report["requests"] = [
            json.loads(line) for line in (root / "journey-requests.jsonl").read_text().splitlines()
        ]
        diagnostics = root / "guard-failures.jsonl"
        report["guard_failures"] = (
            [json.loads(line) for line in diagnostics.read_text().splitlines()]
            if diagnostics.exists()
            else []
        )
        admissions = root / "assessment-admissions.jsonl"
        report["assessment_admissions"] = (
            [json.loads(line) for line in admissions.read_text().splitlines()] if admissions.exists() else []
        )
        for request in report["requests"]:
            if request["route"] == "api/shopping/listing/candidate/" and request["status"] == 200:
                observed = [r["kind"] for r in report["assessment_admissions"] if r["id"] == request["id"]]
                if observed != ["admission", "lease"]:
                    report["failures"].append(f"candidate admission and final lease: {observed}")
        for name, values in report["samples"].items():
            p95 = sorted(values)[math.ceil(0.95 * len(values)) - 1]
            report.setdefault("metrics", {})[name] = dict(n=len(values), p95=p95, worst=max(values))
            if len(values) != 20 or (
                name not in ("complete journey", "controlled search", "seller tab") and p95 > 300
            ):
                report["failures"].append(name)

        def summarize(values):
            return dict(
                n=len(values), p95=sorted(values)[math.ceil(0.95 * len(values)) - 1], worst=max(values)
            )

        for label, rows in report["browser"]["samples"].items():
            for field, limit in (("scheduling_transfer_ms", 50), ("parse_dom_paint_ms", 70)):
                metric = summarize([r[field] for r in rows])
                report.setdefault("metrics", {}).setdefault(label, {})[field] = metric
                if label != "controlled search" and metric["p95"] > limit:
                    report["failures"].append(f"{label}: {field} > {limit}")
        routes = {}
        for r in report["requests"]:
            if not r["route"].startswith("api/shopping/"):
                continue
            name = r["route"] + " " + r["operation"]
            r["sql_ms"] = r["sql_execute_ms"] + r["sql_fetch_ms"]
            r["other_ms"] = (
                r["elapsed_ms"] - r["sql_ms"] - (r["composition_ms"] or 0) - (r["serialization_ms"] or 0)
            )
            routes.setdefault(name, []).append(r)
        for name, rows in routes.items():
            metrics = {}
            for field, limit in (
                ("elapsed_ms", 180),
                ("sql_ms", 40),
                ("query_count", 20),
                ("composition_ms", 80),
                ("serialization_ms", 60),
                ("other_ms", 60),
                ("payload_bytes", 131072),
            ):
                values = [r[field] for r in rows if r[field] is not None]
                if not values:
                    continue
                metrics[field] = summarize(values)
                if len(values) >= 20 and metrics[field]["p95"] > limit:
                    report["failures"].append(f"{name} {field} > {limit}")
            report.setdefault("server_metrics", {})[name] = metrics
        path = Path(f"reports/shop-17-prepared/journey-{count}.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        trace = root / "engineering-query-timings.json"
        if trace.exists():
            (path.parent / f"statements-{count}.json").write_bytes(trace.read_bytes())
        path.write_text(json.dumps(report, indent=2))
    assert report["controlled_calls"].count("browse") == 40
    assert report["controlled_calls"].count("detail") == 20
    assert len(report["controlled_calls"]) <= 100
    assert not report["failures"], report["failures"]
