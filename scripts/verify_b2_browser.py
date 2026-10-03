"""Exercise collection transactions in independent desktop/narrow Chromium contexts, using a fresh copied root.

Run: uv run --with playwright python scripts/verify_b2_browser.py --root DISPOSABLE_APP_ROOT
The server must be running on loopback:8011 against that same root. No owner passwords.
Screenshots and reports are private. Narrow viewport is emulation, not real-device evidence.
"""

import argparse
import json
import os
import secrets

from pokemon_hunter.beta.cli import setup

parser = argparse.ArgumentParser()
parser.add_argument("--root", type=__import__("pathlib").Path, required=True)
parser.add_argument("--parity", action="store_true")
args = parser.parse_args()
os.umask(0o077)
assert (args.root / "B2_ISOLATED").is_file()
setup(args.root)
from django.contrib.auth import get_user_model  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

from pokemon_hunter.beta import accounts  # noqa: E402

assert not get_user_model().objects.exists(), (
    "Use a fresh collection test root; never reset existing accounts"
)
password_a, password_b = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
accounts.bootstrap(password_a)
member = accounts.invite("b2-collector")
invitation = accounts.issue_link(member, "invite")
base = "http://127.0.0.1:8011"


def login(page, username, password):
    page.goto(base + "/login/")
    page.get_by_label("Username:", exact=True).fill(username)
    page.get_by_label("Password:", exact=True).fill(password)
    page.get_by_role("button", name="Sign in", exact=True).click()
    page.wait_for_url(base + "/")
    page.get_by_role("heading", name="Your collection", exact=True).wait_for()


def csrf(context):
    return next(c["value"] for c in context.cookies() if c["name"] == "dex_b1_csrf")


def post(context, path, data):
    return context.request.post(base + path, data=data, headers={"X-CSRFToken": csrf(context)})


def exported(context):
    return context.request.get(base + "/api/export/").json()


def close(page):
    page.get_by_role("button", name="Close review", exact=True).click()


def confirm(page):
    button = page.get_by_role("button", name="Confirm changes", exact=True)
    button.wait_for(state="visible")
    box = button.bounding_box()
    assert box and box["y"] >= 0 and box["y"] + box["height"] <= page.viewport_size["height"], (
        "Confirmation must remain visible without scrolling the review dialog"
    )
    page.get_by_role("button", name="Confirm changes", exact=True).click()
    page.locator("#review-body").get_by_text(
        "Changes saved. Retrying confirmation will not add them again."
    ).wait_for()
    op = page.locator("#review-body code").first.text_content().strip()
    assert op, "Operation reference must remain readable when its disclosure is collapsed"
    close(page)
    return op


def undo(page, op):
    page.goto(base + "/settings/")
    page.locator("[data-operation='" + op + "']").click()
    page.get_by_role("button", name="Undo this operation", exact=True).click()
    page.locator("#review-body").get_by_text(
        "This operation has been undone; retries will not reapply it."
    ).wait_for()
    close(page)


def layout(page):
    return page.evaluate("""() => ({width:innerWidth, scroll:document.documentElement.scrollWidth,
      smallButtons:[...document.querySelectorAll('button')].filter(b=>b.getClientRects().length && !b.closest('dialog:not([open])')).filter(b=>b.getBoundingClientRect().height<43).length})""")


def flow(page, context, label):
    page.goto(base + "/settings/")
    page.get_by_label("New binder name").fill(label + " binder")
    page.get_by_role("button", name="Preview binder", exact=True).click()
    binder_op = confirm(page)
    binder = exported(context)["binders"][-1]
    page.goto(base + "/")
    page.get_by_role("button", name="Add a physical copy", exact=True).click()
    page.get_by_label("Name or collector number").fill("Pikachu")
    page.get_by_role("button", name="Search catalog", exact=True).click()
    page.locator("#catalog-results article").first.get_by_role("button").click()
    page.get_by_label("Condition", exact=True).select_option("LP")
    page.locator("#editor").get_by_label("Binder", exact=True).select_option(binder["id"])
    page.get_by_label("Purchase amount", exact=True).fill("not money")
    page.get_by_role("button", name="Preview addition", exact=True).click()
    page.locator("#copy-error").wait_for(state="visible")
    assert "purchase_amount" in page.locator("#copy-error").inner_text()
    page.get_by_label("Purchase amount", exact=True).fill("12.340001")
    page.get_by_label("Currency (e.g. USD)").fill("USD")
    page.get_by_label("Purchase date", exact=True).fill("2026-09-27")
    page.get_by_label("Notes", exact=True).fill(label + " synthetic copy")
    page.get_by_label("Grading company (optional)").fill("Synthetic company")
    page.get_by_label("Recorded grade (optional)").fill("7")
    page.get_by_label("Certificate (optional)").fill("TEST-ONLY")
    page.locator("#editor").get_by_label("Duplicate policy", exact=True).select_option("allow")
    page.get_by_role("button", name="Preview addition", exact=True).click()
    page.get_by_role("button", name="Confirm changes", exact=True).wait_for(state="visible")
    page.screenshot(path=str(args.root / f"{label}-add-review.png"))
    add_op = confirm(page)
    op = context.request.get(base + f"/api/operations/{add_op}/").json()
    copy = op["changes"][0]["after"]
    count = len(exported(context)["copies"])
    assert post(context, f"/api/operations/{add_op}/confirm/", {}).status == 200
    assert len(exported(context)["copies"]) == count
    page.get_by_label("Find owned copies").fill(label + " synthetic copy")
    page.get_by_role("button", name="Edit copy", exact=True).click()
    page.get_by_label("Notes", exact=True).fill(label + " edited copy")
    page.get_by_role("button", name="Preview edit", exact=True).click()
    edit_op = confirm(page)
    assert post(context, f"/api/operations/{add_op}/undo/", {}).status == 409
    page.get_by_label("Find owned copies").fill(label + " edited copy")
    page.get_by_role("button", name="Remove", exact=True).click()
    remove_op = confirm(page)
    assert len(exported(context)["copies"]) == count - 1
    undo(page, remove_op)
    assert len(exported(context)["copies"]) == count
    page.goto(base + "/goals/")
    page.get_by_label("Goal name", exact=True).fill(label + " Vintage")
    page.get_by_label("Goal type", exact=True).select_option("vintage")
    page.get_by_role("button", name="Preview tracking goal").click()
    vintage_op = confirm(page)
    page.get_by_label("Goal name", exact=True).fill(label + " exact set")
    page.get_by_label("Goal type", exact=True).select_option("set")
    page.get_by_label("Completion policy", exact=True).select_option("exact")
    page.get_by_role("button", name="Preview tracking goal").click()
    set_goal_op = confirm(page)
    page.get_by_label("Goal name", exact=True).fill(label + " custom")
    page.get_by_label("Goal type", exact=True).select_option("custom")
    page.locator("#goal-members input").first.check()
    page.get_by_role("button", name="Preview tracking goal").click()
    custom_op = confirm(page)
    assert len(exported(context)["copies"]) == count
    assert all(
        g["satisfied"] == 0 for g in exported(context)["goals"] if g["definition"]["policy"] == "exact"
    )
    page.evaluate("window.scrollTo(0,0)")
    page.screenshot(path=str(args.root / f"{label}-goals.png"))
    assert layout(page)["scroll"] <= layout(page)["width"]
    assert layout(page)["smallButtons"] == 0
    page.goto(base + "/")
    page.get_by_role("button", name="Add a physical copy", exact=True).click()
    page.get_by_label("Owned set", exact=True).select_option(label="Wizards Black Star Promos")
    page.get_by_label("Duplicate policy", exact=True).select_option("skip")
    page.get_by_role("button", name="Preview owned-set addition", exact=True).click()
    page.locator("#review-body").get_by_text(
        "Only listed catalog entries are proposed.", exact=False
    ).wait_for()
    set_op = confirm(page)
    undo(page, set_op)
    assert len(exported(context)["copies"]) == count
    page.get_by_label("File format", exact=True).select_option("csv")
    page.get_by_label("Import contents", exact=True).fill("printing_id,notes\ninvalid,broken\n")
    page.get_by_label("Duplicate handling", exact=True).select_option("allow")
    page.get_by_role("button", name="Preview import", exact=True).click()
    page.locator("#review-body .error").wait_for()
    assert not page.get_by_role("button", name="Confirm changes", exact=True).is_visible()
    page.screenshot(path=str(args.root / f"{label}-import-errors.png"))
    close(page)
    page.get_by_label("Import contents", exact=True).fill(
        f"printing_id,notes\n{copy['printing_id']},CSV synthetic duplicate\n"
    )
    page.get_by_role("button", name="Preview import", exact=True).click()
    import_op = confirm(page)
    undo(page, import_op)
    assert len(exported(context)["copies"]) == count
    page.evaluate("window.scrollTo(0,0)")
    page.screenshot(path=str(args.root / f"{label}-settings.png"))
    assert layout(page)["scroll"] <= layout(page)["width"]
    page.goto(base + "/")
    page.get_by_label("Find owned copies").fill(label)
    page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement.id") == "binder-filter"
    page.screenshot(path=str(args.root / f"{label}-collection.png"))
    assert layout(page)["scroll"] <= layout(page)["width"]
    assert layout(page)["smallButtons"] == 0
    return {
        "copy": copy["id"],
        "binder": binder["id"],
        "goals": [g["id"] for g in exported(context)["goals"]],
        "operations": [
            binder_op,
            add_op,
            edit_op,
            remove_op,
            vintage_op,
            set_goal_op,
            custom_op,
            set_op,
            import_op,
        ],
    }


with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless=True
    )
    a = browser.new_context(viewport={"width": 1280, "height": 900})
    b = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    pa, pb = a.new_page(), b.new_page()
    errors = []
    pa.on("pageerror", lambda e: errors.append(str(e)))
    pb.on("pageerror", lambda e: errors.append(str(e)))
    login(pa, "admin", password_a)
    baseline = exported(a)
    pb.goto(base + invitation)
    pb.get_by_label("New password:", exact=True).fill(password_b)
    pb.get_by_label("New password confirmation:", exact=True).fill(password_b)
    pb.get_by_role("button", name="Save password").click()
    login(pb, "b2-collector", password_b)
    pb.get_by_role("heading", name="Your collection is empty").wait_for()
    pb.screenshot(path=str(args.root / "member-empty.png"))
    # Complete exported owner snapshot round-trip into the initially empty isolated account.
    pb.goto(base + "/settings/")
    pb.get_by_label("Import contents", exact=True).fill(json.dumps(baseline))
    pb.get_by_label("Duplicate handling", exact=True).select_option("allow")
    pb.get_by_role("button", name="Preview import", exact=True).click()
    roundtrip_op = confirm(pb)
    roundtrip = exported(b)
    assert len(roundtrip["copies"]) == len(baseline["copies"])
    by_source = {c["source_copy_id"]: c for c in roundtrip["copies"]}
    for c in baseline["copies"]:
        assert by_source[c["id"]]["printing_id"] == c["printing_id"]
        assert by_source[c["id"]]["first_edition_selected"] == c["first_edition_selected"]
        assert by_source[c["id"]]["provisional_identity"] == c["provisional_identity"]
    assert roundtrip["vintage_251"] == baseline["vintage_251"]
    undo(pb, roundtrip_op)
    assert exported(b)["copies"] == []
    records_a = flow(pa, a, "desktop")
    records_b = flow(pb, b, "narrow")
    for context, forbidden in [(a, records_b), (b, records_a)]:
        for path in [
            f"/api/inventory/{forbidden['copy']}/",
            f"/api/binders/{forbidden['binder']}/",
            *[f"/api/goals/{g}/" for g in forbidden["goals"]],
        ]:
            assert context.request.get(base + path).status == 404
        for op in forbidden["operations"]:
            assert context.request.get(base + f"/api/operations/{op}/").status == 404
            assert post(context, f"/api/operations/{op}/confirm/", {}).status == 404
            assert post(context, f"/api/operations/{op}/undo/", {}).status == 404
        assert forbidden["copy"] not in {c["id"] for c in exported(context)["copies"]}
    after = {c["id"]: c for c in exported(a)["copies"]}
    assert all(after[c["id"]] == c for c in baseline["copies"])
    if args.parity:
        from verify_parity_browser import parity_flow

        parity_flow(pa, a, args.root, "desktop", records_a)
        parity_flow(pb, b, args.root, "narrow", records_b)
    assert not errors, errors
    if (args.root / "B3_ISOLATED").is_file():
        from verify_b3_browser import scan_flow

        scan_flow(pa, a, args.root, "desktop")
        scan_flow(pb, b, args.root, "narrow")

    if (args.root / "B4_ISOLATED").is_file():
        from verify_b4_browser import catalog_flow

        catalog_flow(pa, a, pb, b, args.root)
        assert not errors, errors

    (args.root / "browser-report.json").write_text(
        json.dumps(
            {
                "result": "PASS",
                "browser_version": browser.version,
                "sessions": 2,
                "viewports": [1280, 390],
                "device_status": "Chromium viewport/touch emulation only; no real iOS/Android testing",
                "flows": "manual add, invalid money, duplicate acknowledgment, retry, edit, remove, undo, binder, Vintage/set/custom goals, reviewed set batch/undo, invalid and valid CSV/undo, JSON export/import/undo, keyboard focus, narrow layout",
                "cross_account": "both directions; copies, binders, goals, exports, all operation reads/confirmation/undo denied",
                "baseline_copies_unchanged": len(baseline["copies"]),
                "baseline_vintage": baseline["vintage_251"],
                "roundtrip_copies": len(roundtrip["copies"]),
                "console_errors": errors,
            },
            indent=2,
        )
        + "\n"
    )
    browser.close()
print("Collection browser flows passed; report and screenshots retained in the private root.")
