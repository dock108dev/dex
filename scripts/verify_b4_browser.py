"""Invoked by the existing two-account browser harness on fresh catalog-enabled fixture roots."""

import json

from playwright.sync_api import expect


def catalog_flow(admin_page, admin_context, member_page, member_context, root):
    base = "http://127.0.0.1:8011"
    fixture = root / "synthetic-card.jpg"
    before = member_context.request.get(base + "/api/export/").json()["copies"]
    # Start through the actual B3 upload -> unsupported -> provisional confirmation UI.
    member_page.goto(base + "/scan/")
    member_page.locator("input[name=front]").set_input_files(fixture)
    member_page.locator("select[name=fixture]").select_option("unsupported")
    member_page.get_by_role("button", name="Upload and review", exact=True).click()
    member_page.get_by_text("No supported match", exact=True).wait_for()
    member_page.get_by_label("Notes / identity corrections").fill(
        "Private collector note retained through B4"
    )
    member_page.get_by_label("I reviewed the photo", exact=False).check()
    member_page.get_by_role("button", name="Confirm one copy", exact=True).click()
    member_page.get_by_text("One copy added to your collection.", exact=False).wait_for()
    jid = member_page.url.split("#")[1]
    job = member_context.request.get(base + f"/api/scans/{jid}/").json()
    cid = job["copy_id"]
    member_page.get_by_role("link", name="Request catalog support", exact=True).click()
    member_page.locator("#new-set").fill("Gym Heroes")
    member_page.locator("#new-name").fill("Blaine's Moltres")
    member_page.locator("#new-number").fill("1")
    member_page.get_by_role("button", name="Submit catalog request", exact=True).click()
    member_page.get_by_text("Request submitted. Your inventory is unchanged.", exact=True).wait_for()
    submission = member_context.request.get(base + "/api/catalog-requests/").json()["submissions"][0]
    sid = submission["id"]
    rid = submission["request_id"]
    member_page.screenshot(path=str(root / "narrow-b4-request.png"), full_page=True)
    # Admin sees submitted hints, not private notes/photos or raw inventory access.
    admin_page.goto(base + "/catalog-review/")
    admin_page.get_by_text("Photos private — no reviewer access.", exact=True).wait_for()
    assert "Private collector note" not in admin_page.locator("body").inner_text()
    assert admin_context.request.get(base + f"/api/inventory/{cid}/").status == 404
    assert admin_context.request.get(base + f"/scan-photos/{job['photos'][0]}/").status == 404
    form = admin_page.locator(f'form[data-review="{rid}"]')
    form.locator("[name=set_key]").fill("gym1")
    form.locator("[name=aliases]").fill("Gym Heroes, G1")
    form.locator("[name=state]").select_option("ready")
    form.get_by_role("button", name="Save review", exact=True).click()
    admin_page.get_by_role("heading", name="pokemon:en:gym1 · ready", exact=True).wait_for()
    admin_page.screenshot(path=str(root / "desktop-b4-triage.png"), full_page=True)
    # Explicit consent grants only this evidence endpoint and is immediately revocable.
    member_page.get_by_text("Edit hints or photo consent", exact=True).click()
    member_page.locator(f"#share-{sid}").check()
    member_page.get_by_role("button", name="Save hints and consent", exact=True).click()
    member_page.get_by_text("Photos shared with reviewers.", exact=False).wait_for()
    admin_page.reload()
    admin_page.get_by_alt_text("Explicitly shared request photo").wait_for()
    assert admin_context.request.get(base + f"/api/catalog-evidence/{sid}/{job['photos'][0]}/").status == 200
    admin_page.get_by_role("button", name="Load Gym Heroes package", exact=True).click()
    expect(admin_page.locator("#package")).not_to_have_value("")
    admin_page.get_by_role("button", name="Preview catalog import", exact=True).click()
    admin_page.get_by_role("button", name="Verify preview", exact=True).wait_for()
    admin_page.screenshot(path=str(root / "desktop-b4-preview.png"), full_page=True)
    admin_page.get_by_role("button", name="Verify preview", exact=True).click()
    admin_page.get_by_role("button", name="Publish coverage", exact=True).click()
    admin_page.get_by_role("button", name="Roll back publication", exact=True).wait_for()
    member_page.reload()
    member_page.get_by_role("button", name="Accept for this existing copy", exact=True).wait_for()
    member_page.screenshot(path=str(root / "narrow-b4-proposal.png"), full_page=True)
    member_page.get_by_role("button", name="Accept for this existing copy", exact=True).click()
    member_page.get_by_text("Existing copy resolved. No additional copy was created.", exact=True).wait_for()
    after = member_context.request.get(base + "/api/export/").json()["copies"]
    assert len(after) == len(before) + 1
    c = next(c for c in after if c["id"] == cid)
    assert c["printing_id"] and c["notes"] == "Private collector note retained through B4"
    token = next(c["value"] for c in member_context.cookies() if c["name"] == "dex_b1_csrf")
    assert member_context.request.post(
        base + f"/api/catalog-requests/{sid}/resolve/",
        data={"printing_id": c["printing_id"], "revision": 0},
        headers={"X-CSRFToken": token},
    ).ok
    assert len(member_context.request.get(base + "/api/export/").json()["copies"]) == len(after)
    assert member_context.request.get(base + f"/scan-photos/{job['photos'][0]}/").status == 200
    assert member_context.request.get(base + "/api/catalog-review/").status == 403
    admin_page.get_by_role("button", name="Roll back publication", exact=True).click()
    admin_page.get_by_role("button", name="Publish coverage", exact=True).wait_for()
    assert (
        next(c for c in member_context.request.get(base + "/api/export/").json()["copies"] if c["id"] == cid)[
            "printing_id"
        ]
        == c["printing_id"]
    )
    admin_page.get_by_role("button", name="Publish coverage", exact=True).click()
    admin_page.get_by_role("button", name="Roll back publication", exact=True).wait_for()
    # New set appears in the restored My Cards view too.
    member_page.goto(base + "/cards/")
    member_page.get_by_label("Set", exact=True).select_option(label="Gym Heroes")
    expect(member_page.locator("#cards-count")).to_have_text("132 printings · 1 owned · 131 missing")
    assert member_page.locator("[data-card]").count() == 48
    member_page.get_by_role("button", name="Next printings", exact=True).click()
    member_page.get_by_role("button", name="Next printings", exact=True).click()
    assert member_page.locator("[data-card]").count() == 36
    member_page.screenshot(path=str(root / "narrow-b4-gym-heroes.png"), full_page=True)
    for page in (admin_page, member_page):
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    (root / "b4-browser-report.json").write_text(
        json.dumps(
            {
                "result": "PASS",
                "set": "Gym Heroes",
                "entries": 132,
                "request_consent_admin_publish_resolve_rollback_republish": True,
                "copy_id_preserved": True,
                "private_photos_isolated": True,
                "real_devices": False,
            },
            indent=2,
        )
    )
