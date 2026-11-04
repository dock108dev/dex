"""Failure and recovery on the ordinary assessment screen and an intercepted seller tab."""

import json
import subprocess
import sys
from contextlib import ExitStack
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from browser_measurements import isolated_network
from runtime_process import close_pipes, read_port
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_effective_collection import cx as cx
from test_migration import snapshot as snapshot
from test_sealed_catalog import e1 as e1
from test_shop15_performance import prepare_auction, prepare_review

pytestmark = pytest.mark.allow_hosts(["127.0.0.1"])


def test_original_assessment_across_return_failures(cx):
    from playwright.sync_api import expect, sync_playwright

    root = cx["root"]
    pid, run_id, handle, client = prepare_auction(cx, 120, 20, "return")
    config_path = root / "engineering-shopping.json"
    settings = json.loads(config_path.read_text())
    config_path.write_text(json.dumps(dict(settings, exercise_expiry=True)))
    with ExitStack() as stack:

        def serve(port=0):
            proc = subprocess.Popen(
                [sys.executable, "tests/shop12_server.py", str(root), str(port)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            def stop():
                if proc.poll() is None:
                    proc.terminate()
                    proc.wait(timeout=15)
                    close_pipes(proc)

            stack.callback(stop)
            return read_port(proc), stop

        port, stop = serve()
        base = f"http://127.0.0.1:{port}"
        pw = stack.enter_context(sync_playwright())
        browser = pw.chromium.launch()
        stack.callback(browser.close)
        context = browser.new_context(viewport=dict(width=390, height=900), timezone_id="UTC")
        cookies = [dict(name=k, value=v.value, url=base) for k, v in client.cookies.items()]
        context.add_cookies(cookies)
        destination = "https://www.ebay.com/itm/123456789012"
        context.route(
            destination, lambda r: r.fulfill(content_type="text/html", body="<title>Intercept</title>")
        )
        page = context.new_page()
        isolated_network(page, base)
        writes = []
        page.on("request", lambda r: writes.append(r.url) if r.method != "GET" else None)
        page.goto(base + "/shopping/?q=Venusaur")
        page.goto(base + "/shopping/check/")

        def seed():
            page.reload()
            page.locator("#check-compare:enabled").wait_for()
            prepare_review(page, pid, run_id, handle, "NM")

        seed()
        button = page.locator("#check-compare")
        result = page.locator("#check-results")
        status = page.locator("#check-status")
        bid = page.locator("#review-planned_bid")
        budget = page.locator("#review-budget")

        def leave():
            expect(button).to_be_enabled()
            with page.expect_response(lambda r: "/listing/compare/" in r.url) as decision:
                button.press("Enter")
            assert decision.value.ok, decision.value.text()
            expect(status).to_contain_text("Comparison updated")
            result.locator("a").focus()
            with context.expect_page() as opened:
                result.locator("a").press("Enter")
            seller = opened.value
            seller.wait_for_url(destination)
            assert seller.title() == "Intercept"
            return seller

        def back(seller):
            before = len(writes)
            with page.expect_response(lambda r: "/listing/return/" in r.url):
                seller.close()
                page.bring_to_front()
                page.evaluate("window.dispatchEvent(new FocusEvent('focus'))")
            assert len(writes) == before

        path = root / "parity-evidence/market_values.json"
        original = path.read_text()
        now = datetime.now(ZoneInfo("America/New_York"))
        before_midnight = now.replace(hour=23, minute=59, second=50, microsecond=0)
        for issue in ("withdrawn", "aged", "midnight"):
            if issue == "midnight":
                record = dict(json.loads(original)[0], as_of=(now.date() - timedelta(days=30)).isoformat())
                path.write_text(json.dumps([record]))
                page.clock.install(time=before_midnight)
                page.reload()
                expect(budget).to_have_value("12")
            seller = leave()
            clock = root / "engineering-next-month"
            if issue == "withdrawn":
                path.write_text("[]")
            else:
                clock.touch()
            if issue == "midnight":
                page.clock.set_system_time(before_midnight + timedelta(seconds=11))
                expect(result).to_be_empty()
                expect(status).to_contain_text("Reference expired")
            back(seller)
            expect(status).to_contain_text("Venusaur")
            expect(status).to_contain_text("NM")
            expect(result).to_be_empty()
            expect(budget).to_have_value("12")
            button.press("Enter")
            expect(result).to_contain_text("Recommendation unavailable")
            path.write_text(original)
            clock.unlink(missing_ok=True)
            if issue == "midnight":
                page.clock.set_system_time(datetime.now(ZoneInfo("America/New_York")))
                page.reload()
                expect(budget).to_have_value("12")

        seller = leave()
        other = context.new_page()
        isolated_network(other, base)
        other.goto(page.url)
        expect(other.locator("#review-budget")).to_have_value("12")
        other.get_by_text("Bid, budget and purchase costs", exact=True).click()
        other.locator("#review-budget").fill("8")
        other.locator("#review-planned_bid").fill("10")
        other.locator("#check-compare").click()
        expect(other.locator("#check-results")).to_contain_text("Your planned bid exceeds the ceiling")
        other.close()
        back(seller)
        expect(status).to_contain_text("saved review changed")
        expect(budget).to_have_value("8")
        expect(bid).to_have_value("10")
        expect(result).to_be_empty()
        button.press("Enter")
        expect(result).to_contain_text("Budget bid limit $7.00")

        # Leave via browser Back before the autosave debounce.
        page.get_by_text("Bid, budget and purchase costs", exact=True).click()
        bid.fill("6")
        page.go_back()
        assert "q=Venusaur" in page.url
        page.go_forward()
        expect(bid).to_have_value("6")

        seller = leave()
        stop()
        _, stop = serve(port)
        back(seller)
        expect(status).to_contain_text("original offer or review")
        expect(result).to_be_empty()
        expect(bid).to_have_value("6")
        expect(page.locator("#review-price")).to_have_value("")

        seed()
        seller = leave()
        context.clear_cookies()
        back(seller)
        expect(status).to_contain_text("Sign in again")
        expect(button).to_be_disabled()
        expect(result).to_be_empty()
        expect(bid).to_have_value("")

        context.add_cookies(cookies)
        seed()
        seller = leave()
        response = context.request.post(
            base + f"/api/shopping/discovery/{run_id}/stop/",
            data={},
            headers={
                "X-CSRFToken": page.locator("#listing-load [name=csrfmiddlewaretoken]").input_value(),
                "X-Dex-Shopping-Binding": json.loads(page.locator("#check-binding").text_content()),
            },
        )
        assert response.ok, response.text()
        back(seller)
        expect(result).to_be_empty()
        expect(status).to_contain_text("original offer or review")
        expect(budget).to_have_value("12")

        stop()
        config_path.write_text(json.dumps(dict(settings, lease_seconds=5)))
        _, stop = serve(port)
        seed()
        seller = leave()
        expect(result).to_be_empty(timeout=8000)
        seller.close()
        page.bring_to_front()
        page.evaluate("window.dispatchEvent(new FocusEvent('focus'))")
        expect(status).to_contain_text("Temporary review expired")
        expect(budget).to_have_value("12")
        expect(page.locator("#review-price")).to_have_value("")

        # The browser retains its cookie, but the server revokes the session.
        # Start a new engineering run so the previous expiry stays final.
        stop()
        config_path.write_text(json.dumps(settings))
        serve(port)
        seed()
        seller = leave()
        logout = context.request.post(
            base + "/logout/",
            headers={"X-CSRFToken": page.locator("#listing-load [name=csrfmiddlewaretoken]").input_value()},
            max_redirects=0,
        )
        assert logout.status in (200, 302)
        context.add_cookies(cookies)
        back(seller)
        expect(status).to_contain_text("Sign in again")
        expect(result).to_be_empty()
        expect(button).to_be_disabled()
        expect(budget).to_have_value("")
