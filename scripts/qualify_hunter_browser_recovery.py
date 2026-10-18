"""Offline retained-tab qualification, with explicit browser evidence classes.

The existing UI harness supplies disposable state, a finite fake provider and
guarded loopback server. This extension disconnects and reconnects a real
Chromium controller while preserving its original process, tab and history. It
does not impersonate a Codex turn or claim to exercise CUA's turn-end cleanup.
"""

import argparse
import hashlib
import json
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit

import qualify_hunter_ui as baseline

baseline_exercise = baseline.exercise


class TurnRetentionModel:
    """Document-derived model only; never counted as observed CUA behavior."""

    def __init__(self):
        self.turn = 0
        self.marked = {}
        self.tabs = {"original"}

    def mark(self, tab, kind="handoff"):
        self.marked[tab] = kind

    def end_turn(self):
        self.tabs &= self.marked.keys()
        self.marked = {}
        self.turn += 1


def qualify_mark_model(report):
    renewed = TurnRetentionModel()
    renewed.mark("original")
    renewed.end_turn()
    renewed.mark("original")
    renewed.end_turn()
    assert renewed.tabs == {"original"}
    omitted = TurnRetentionModel()
    omitted.mark("original")
    omitted.end_turn()
    omitted.end_turn()
    assert omitted.tabs == set()
    replacement = TurnRetentionModel()
    replacement.tabs.add("other")
    replacement.mark("original")
    replacement.mark("original", "deliverable")
    replacement.mark("other")
    assert replacement.marked["original"] == "deliverable"
    replacement.end_turn()
    assert replacement.tabs == {"original", "other"}
    report["turn_retention_model"] = dict(
        evidence_class="simulated document-derived turn model; not actual CUA turn cleanup",
        renewed_each_turn_retains_original=True,
        one_time_mark_does_not_survive_second_unmarked_turn=True,
        latest_kind_for_same_tab_wins=True,
        marks_for_distinct_tabs_are_independent=True,
        actual_owner_turn_transition_exercised=False,
    )


def exercise_retained_tab(base, root, output, report):
    from playwright.sync_api import expect, sync_playwright
    from qualify_shopping import PASSWORD

    checks = report["checks"]
    requests, external, errors = [], [], []
    latest = {}
    controller = None
    browser = None
    context = None
    page = None
    process = None
    target = None
    handoffs = []

    def passed(name):
        checks.append(
            dict(check=name, passed=True, evidence_class="real Chromium CDP reconnect; fabricated provider")
        )

    def calls():
        path = output / "fake-transport.json"
        return json.loads(path.read_text()) if path.exists() else []

    def intercept(route):
        request = route.request
        if not request.url.startswith(base + "/"):
            external.append(dict(resource_type=request.resource_type, sent=False))
            route.abort()
            return
        path = urlsplit(request.url).path
        if path.startswith("/api/shopping/hunter/"):
            response = route.fetch()
            if "application/json" not in response.headers.get("content-type", ""):
                requests.append(dict(path=path, method=request.method, status=response.status, non_json=True))
                route.fulfill(response=response)
                return
            value = response.json()
            if response.ok and value.get("run_id"):
                latest.update(value)
            requests.append(dict(path=path, method=request.method, status=response.status))
            route.fulfill(response=response)
            return
        route.continue_()

    def connect(endpoint, expected=None):
        nonlocal controller, browser, context, page, target
        controller = sync_playwright().start()
        browser = controller.chromium.connect_over_cdp(endpoint)
        context = browser.contexts[0]
        assert len(context.pages) == 1, "Reuse the original tab; do not create a replacement"
        page = context.pages[0]
        context.route("**/*", intercept)
        page.on("pageerror", lambda error: errors.append(str(error)))
        session = context.new_cdp_session(page)
        current = session.send("Target.getTargetInfo")["targetInfo"]["targetId"]
        session.detach()
        if expected is not None:
            assert current == expected, "The reconnect must retain the original Chromium target"
        target = current
        return page

    def handoff(endpoint, phase):
        saved_target = target
        saved_history = page.evaluate("() => JSON.stringify(history.state)")
        saved_url = page.url
        # This disconnect is an actual controller boundary; it is not a CUA turn.
        context.unroute_all(behavior="ignoreErrors")
        controller.stop()
        time.sleep(0.15)
        assert process.poll() is None
        connect(endpoint, saved_target)
        assert page.url == saved_url
        assert page.evaluate("() => JSON.stringify(history.state)") == saved_history
        handoffs.append(dict(phase=phase, same_target=True, same_url=True, same_history=True))

    with tempfile.TemporaryDirectory(prefix="dex-h07-chromium-engineering-") as directory:
        directory = Path(directory)
        probe = sync_playwright().start()
        executable = probe.chromium.executable_path
        probe.stop()
        command = [
            executable,
            "--headless=new",
            "--no-sandbox",
            "--disable-background-networking",
            "--disable-component-update",
            "--no-first-run",
            "--no-default-browser-check",
            "--remote-debugging-address=127.0.0.1",
            "--remote-debugging-port=0",
            "--proxy-server=http://127.0.0.1:9",
            "--proxy-bypass-list=127.0.0.1",
            "--user-data-dir=" + str(directory),
            "about:blank",
        ]
        with (output / "chromium-controller.log").open("w") as log:
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
            try:
                endpoint_file = directory / "DevToolsActivePort"
                for _ in range(100):
                    if endpoint_file.exists():
                        break
                    assert process.poll() is None, "Disposable Chromium exited before readiness"
                    time.sleep(0.05)
                else:
                    raise TimeoutError("Disposable Chromium controller did not become ready")
                endpoint = "http://127.0.0.1:" + endpoint_file.read_text().splitlines()[0]
                connect(endpoint)
                report["recovery_browser_version"] = browser.version
                page.goto(base + "/login/")
                handoff(endpoint, "ordinary-sign-in-page-awaiting-controlled-reply")
                page.get_by_label("Username:", exact=True).fill("admin")
                page.get_by_label("Password:", exact=True).fill(PASSWORD)
                page.get_by_role("button", name="Sign in", exact=True).click()
                expect(page).to_have_url(base + "/cards/")
                assert calls() == []
                passed("ordinary sign-in survives controller reconnect without any acquisition")

                page.goto(base + "/shopping/hunter/")
                expect(page.locator("#hunter-start")).to_be_enabled()
                page.locator("#hunter-scope").select_option("lots")
                page.locator("#hunter-start").click()
                expect(page.locator("#hunter-local-next")).to_be_enabled(timeout=30000)
                expect(page.locator("#hunter-continue")).to_be_enabled(timeout=30000)
                assert [item["stage"] for item in calls()] == ["oauth", "browse", "browse"]
                first_window = latest["window"]
                first_run = latest["run_id"]
                first_expiry = latest["expires_in_seconds"]
                first_plan = latest["plan"]
                first_history = page.evaluate("() => history.state")
                assert first_history["run"] == first_run
                passed("first received lot results require exactly one OAuth and two fake Browse operations")

                handoff(endpoint, "signed-in-first-results")
                expect(page.locator("#hunter-results")).to_be_visible()
                assert page.evaluate("() => history.state.run") == first_run
                assert len(calls()) == 3
                passed(
                    "original tab, opaque run and navigation history survive a second real controller reconnect"
                )

                local_start = len(calls())
                page.locator("#hunter-filter").select_option("mixed_lot")
                page.locator("[data-reveal]").first.click()
                page.locator("#hunter-local-next").click()
                expect(page.locator("#hunter-local-next")).to_be_enabled()
                page.locator("#hunter-filter").select_option("all")
                assert page.locator("#hunter-cards > article").count() == 260
                assert len(calls()) == local_start
                passed("local filtering, seller reveal and received-result paging acquire no provider data")

                page.reload()
                expect(page.locator("#hunter-local-next")).to_be_hidden(timeout=30000)
                expect(page.locator("#hunter-cards > article")).to_have_count(260)
                assert latest["run_id"] == first_run and latest["window"] == first_window
                assert latest["expires_in_seconds"] <= first_expiry
                assert len(calls()) == local_start
                passed(
                    "same-tab reload restores only its authorized opaque handle without renewing the original lease"
                )

                page.locator("#hunter-continue").click()
                expect(page.locator("#hunter-continue")).to_be_enabled(timeout=30000)
                assert [item["stage"] for item in calls()] == ["oauth"] + ["browse"] * 4
                assert latest["run_id"] == first_run
                assert latest["window"] == first_window and latest["plan"] == first_plan
                assert latest["expires_in_seconds"] <= first_expiry
                passed(
                    "explicit Continue alone acquires the next two fake pages in the same captured run, window and plan"
                )

                analyze = page.get_by_role("button", name="Analyze lot", exact=True).first
                analyze_id = analyze.get_attribute("id")
                analyze.focus()
                analyze.click()
                expect(page.locator("#hunter-review")).to_be_visible()
                expect(page.locator("#hunter-review")).to_contain_text("Ungraded")
                quantity = page.get_by_label("Included cards inside this one lot", exact=True).first
                quantity.fill("3")
                page.locator("#hunter-review-compare").click()
                expect(page.locator("#hunter-review-compare")).to_be_enabled()
                review_history = page.evaluate("() => history.state")
                assert review_history["review"] and review_history["run"] == first_run
                handoff(endpoint, "corrected-temporary-lot-review")
                expect(
                    page.get_by_label("Included cards inside this one lot", exact=True).first
                ).to_have_value("3")
                page.go_back()
                expect(page.locator("#" + analyze_id)).to_be_focused()
                assert page.evaluate("() => history.state.run") == first_run
                assert len(calls()) == 5
                passed(
                    "lot proposal, quantity correction, retained review and browser Back restore originating focus without acquisition"
                )

                fresh = context.new_page()
                fresh.goto(base + "/shopping/hunter/")
                expect(fresh.locator("#hunter-app")).to_be_visible()
                expect(fresh.locator("#hunter-results")).to_be_hidden()
                expect(fresh.locator("#hunter-continue")).to_be_hidden()
                assert fresh.evaluate("() => history.state?.run || null") is None
                assert len(calls()) == 5
                fresh.close()
                passed(
                    "fresh authenticated tab has no original run and does not automatically resume or replace its Hunt"
                )

                stale_history = dict(page.evaluate("() => history.state"))
                stale_history["run"] = "00000000-0000-4000-8000-000000000000"
                stale_history.update(view="results", review=None, inspect=None, pages=1)
                page.evaluate("state => history.replaceState(state, '', location.pathname)", stale_history)
                page.reload()
                expect(page.locator("#hunter-results")).to_be_hidden()
                expect(page.locator("#hunter-status")).to_contain_text("unavailable", timeout=30000)
                expect(page.locator("#hunter-continue")).to_be_hidden()
                assert len(calls()) == 5
                assert page.evaluate("() => history.state.run") is None
                passed(
                    "missing temporary run returns honest unavailable state and clears the stale handle without acquisition"
                )

                # Retain the actual authorized handle only in this same tab for
                # the final independent Stop; no response body is reconstructed.
                page.evaluate("state => history.replaceState(state, '', location.pathname)", first_history)
                page.reload()
                expect(page.locator("#hunter-results")).to_be_visible(timeout=30000)
                page.locator("#hunter-stop").click()
                expect(page.locator("#hunter-results")).to_be_hidden()
                expect(page.locator("#hunter-status")).to_contain_text("stopped", ignore_case=True)
                assert len(calls()) == 5
                passed("explicit parent Stop clears the retained run and uses no acquisition capacity")

                stores = page.evaluate("() => ({local:{...localStorage},session:{...sessionStorage}})")
                serialized = json.dumps(stores)
                assert all(
                    text not in serialized
                    for text in ("Engineering Pokémon lot", "reference_amount", "12.00")
                )
                assert not errors, errors
                report["retained_tab"] = dict(
                    evidence_class="real persistent Chromium process and CDP controller reconnects; not actual CUA turns",
                    handoffs=handoffs,
                    target_identity_sha256=hashlib.sha256(target.encode()).hexdigest(),
                    same_captured_run_window_and_plan=True,
                    engineering_captured_scope="lots; independent of genuine Both plan ordering",
                    original_lease_not_renewed=True,
                    fake_operations=[item["stage"] for item in calls()],
                    local_operations_additional_fake_calls=0,
                    missing_context_additional_fake_calls=0,
                    external_requests_sent=0,
                    blocked_external_resources=len(external),
                    browser_errors=errors,
                    hunter_requests=requests,
                )
            finally:
                report["retained_tab_attempt"] = dict(
                    handoffs=handoffs,
                    fake_operations=[item["stage"] for item in calls()],
                    hunter_requests=requests,
                    browser_errors=errors,
                    external_requests_sent=0,
                )
                if controller is not None:
                    try:
                        if page is not None and not page.is_closed():
                            page.screenshot(path=str(output / "engineering-recovery-final.png"))
                        controller.stop()
                    except Exception:
                        pass
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


def exercise(base, root, output, report):
    qualify_mark_model(report)
    exercise_retained_tab(base, root, output, report)
    baseline_exercise(base, root, output, report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--installed", action="store_true")
    args = parser.parse_args()
    baseline.INSTALLED = args.installed
    baseline.SOURCE_FILES += ("scripts/qualify_hunter_browser_recovery.py",)
    baseline.exercise = exercise
    baseline.run(args.output.resolve())


if __name__ == "__main__":
    main()
