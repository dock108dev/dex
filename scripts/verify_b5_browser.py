"""Desktop/narrow Chromium checks against LOCAL HTTPS staging, never real devices."""

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--evidence", type=Path, required=True)
args = parser.parse_args()
saved = json.loads((args.evidence / "synthetic-account.json").read_text())
base = "https://127.0.0.1:8443"
with sync_playwright() as p:
    browser = p.chromium.launch()
    for width in (1280, 390):
        ctx = browser.new_context(ignore_https_errors=True, viewport={"width": width, "height": 900})
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(base + "/login/")
        page.get_by_label("Username:", exact=True).fill(saved["username"])
        page.get_by_label("Password:", exact=True).fill(saved["password"])
        page.get_by_role("button", name="Sign in", exact=True).click()
        page.get_by_role("heading", name="Your collection", exact=True).wait_for()
        cookies = ctx.cookies()
        session = next(c for c in cookies if c["name"] == "__Host-dex_session")
        assert session["secure"] and session["httpOnly"] and session["sameSite"] == "Strict"
        for path in ("/overview/", "/cards/", "/goals/", "/settings/", "/requests/"):
            page.goto(base + path)
            page.wait_for_load_state("networkidle")
            assert page.locator("main").is_visible()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.goto(base + "/scan/")
        fixture = args.evidence / "synthetic.jpg"
        from PIL import Image

        Image.new("RGB", (300, 400), "blue").save(fixture)
        page.locator("input[name=front]").set_input_files(fixture)
        page.get_by_role("button", name="Upload and review", exact=True).click()
        page.get_by_label("I reviewed the photo", exact=False).wait_for()
        page.get_by_label("Notes / identity corrections").fill("Synthetic HTTPS B5")
        page.get_by_label("I reviewed the photo", exact=False).check()
        page.get_by_role("button", name="Confirm one copy", exact=True).click()
        page.get_by_text("One copy added to your collection.", exact=False).wait_for()
        page.get_by_role("link", name="Request catalog support", exact=True).click()
        page.locator("#new-set").fill("Synthetic HTTPS request")
        page.get_by_role("button", name="Submit catalog request", exact=True).click()
        page.get_by_text("Request submitted. Your inventory is unchanged.", exact=True).wait_for()
        page.screenshot(path=str(args.evidence / f"https-{width}-request.png"), full_page=True)
        page.goto(base + "/support/")
        page.get_by_label("Feedback", exact=True).fill("Synthetic HTTPS feedback")
        page.get_by_role("button", name="Save feedback", exact=True).click()
        page.get_by_text("Feedback saved privately. Thank you.").wait_for()
        page.screenshot(path=str(args.evidence / f"https-{width}-support.png"), full_page=True)
        assert not errors, errors
        ctx.close()
    browser.close()
(args.evidence / "https-browser.json").write_text(
    json.dumps(
        {
            "desktop": True,
            "narrow": True,
            "secure_login": True,
            "b2_pages_b3_confirmation_b4_request_feedback": True,
            "hosted": False,
            "real_devices": False,
        },
        indent=2,
    )
)
print("Local HTTPS desktop/narrow browser checks passed")
