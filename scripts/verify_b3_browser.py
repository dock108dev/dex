"""Called by B2 browser harness on a fresh B3-enabled fixture root only."""

import json

from PIL import Image, ImageDraw


def scan_flow(page, context, root, label):
    base = "http://127.0.0.1:8011"
    fixture = root / "synthetic-card.jpg"
    image = Image.new("RGB", (500, 700), "#ffe6a0")
    ImageDraw.Draw(image).text(
        (40, 100), "SYNTHETIC WORKFLOW IMAGE\nNot a real recognition sample", fill="black"
    )
    image.save(fixture)
    baseline = context.request.get(base + "/api/export/").json()["copies"]
    page.goto(base + "/scan/")
    page.get_by_role("heading", name="Scan/Add", exact=True).wait_for()
    page.get_by_text("SIMULATED recognition", exact=False).wait_for()
    jobs = []
    for outcome, state in [
        ("valid", "Ready to review"),
        ("ambiguous", "Ready to review"),
        ("unreadable", "A clearer photo would help"),
        ("unsupported", "No supported match"),
        ("failed", "Recognition failed"),
    ]:
        page.locator("input[name=front]").set_input_files(fixture)
        page.locator("select[name=fixture]").select_option(outcome)
        page.get_by_role("button", name="Upload and review", exact=True).click()
        page.locator("#current strong").filter(has_text=state).wait_for()
        key = page.url.split("#")[1]
        jobs.append(key)
        page.reload()
        page.locator("#current strong").filter(has_text=state).wait_for()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=str(root / f"{label}-scan-{outcome}.png"), full_page=True)
        if outcome in ("valid", "ambiguous"):
            page.locator("[data-candidate]").first.click()
            if outcome == "ambiguous":
                page.get_by_text("existing copies.", exact=False).wait_for()
            page.get_by_label("Notes / identity corrections").fill(
                "Synthetic browser check <script>not executable</script>"
            )
            page.get_by_label("I reviewed the photo", exact=False).check()
            page.get_by_role("button", name="Confirm one copy", exact=True).click()
            page.get_by_text("One copy added to your collection.", exact=False).wait_for()
            token = next(c["value"] for c in context.cookies() if c["name"] == "dex_b1_csrf")
            repeated = context.request.post(
                base + f"/api/scans/{key}/confirm/", data={}, headers={"X-CSRFToken": token}
            )
            assert repeated.ok
            assert len(context.request.get(base + "/api/export/").json()["copies"]) == len(baseline) + (
                1 if outcome == "valid" else 2
            )
        elif outcome == "unsupported":
            page.get_by_label("Notes / identity corrections").fill("Unknown card, preserve photo")
            page.get_by_label("I reviewed the photo", exact=False).check()
            page.get_by_role("button", name="Confirm one copy", exact=True).click()
            page.get_by_text("One copy added to your collection.", exact=False).wait_for()
            page.screenshot(path=str(root / f"{label}-scan-provisional.png"), full_page=True)
            page.get_by_role("button", name="Undo this addition", exact=True).click()
            page.get_by_text("Addition undone.", exact=False).wait_for()
        elif outcome == "failed":
            page.get_by_role("button", name="Retry recognition", exact=True).click()
            page.locator("#current strong").filter(has_text="Recognition failed").wait_for()
            page.get_by_role("button", name="Cancel and delete uploads", exact=True).click()
        else:
            page.get_by_role("button", name="Cancel and delete uploads", exact=True).click()
    for key in jobs[:2]:
        page.goto(base + "/scan/#" + key)
        page.reload()
        page.get_by_role("button", name="Undo this addition", exact=True).click()
        page.get_by_text("Addition undone.", exact=False).wait_for()
    assert context.request.get(base + "/api/export/").json()["copies"] == baseline
    (root / f"{label}-scan-report.json").write_text(
        json.dumps(
            {
                "result": "PASS",
                "mode": "fixture",
                "outcomes": 5,
                "real_recognition_samples": 0,
                "cost_usd": 0,
                "device": "Chromium viewport only",
                "baseline_copies_preserved": len(baseline),
            }
        )
    )
