"""Additional browser checks, called by verify_b2_browser --parity on a fresh root."""

import json


def parity_flow(page, context, root, label, records):
    base = "http://127.0.0.1:8011"
    projection = context.request.get(base + "/api/parity/").json()
    for route, heading in [
        ("overview", "Overview"),
        ("pokedex", "Pokédex"),
        ("cards", "My Cards"),
        ("hunt", "Hunts"),
        ("missing", "Missing singles"),
        ("finds", "Saved finds"),
    ]:
        page.goto(base + "/" + route + "/")
        page.get_by_role("heading", name=heading, exact=True).wait_for()
        page.screenshot(path=str(root / f"{label}-parity-{route}.png"), full_page=True)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.goto(base + "/pokedex/")
    page.get_by_label("Species name or number").fill("001")
    page.get_by_label("Region", exact=True).select_option("1")
    page.locator('[data-species="1"]').click()
    page.get_by_text("eligible printings", exact=False).wait_for()
    page.screenshot(path=str(root / f"{label}-parity-species.png"))
    page.get_by_role("button", name="Close copy details", exact=True).click()
    page.get_by_label("Ownership", exact=True).select_option("unavailable")
    assert page.locator("[data-species]").count() == 0
    page.goto(base + "/cards/")
    page.get_by_label("Card type", exact=True).select_option("Trainer")
    page.get_by_label("Rarity", exact=True).select_option("Rare")
    assert page.locator("#parity-cards article").count() > 0
    assert all(
        "Trainer" in t and "Rare" in t for t in page.locator("#parity-cards article").all_inner_texts()
    )
    page.get_by_label("Set", exact=True).select_option(index=1)
    page.screenshot(path=str(root / f"{label}-parity-set-type-rarity.png"), full_page=True)
    page.get_by_label("Card type", exact=True).select_option("")
    page.get_by_label("Rarity", exact=True).select_option("")
    page.get_by_label("Set", exact=True).select_option("")
    # Edit only the harness-created copy, never an original copied owner record.
    export = context.request.get(base + "/api/export/").json()
    copy = next(c for c in export["copies"] if c["id"] == records["copy"])
    card = next(c for c in projection["cards"].values() if c["printing_id"] == copy["printing_id"])
    page.goto(base + "/cards/")
    page.get_by_label("Name or number", exact=True).fill(card["name"])
    page.locator('[data-card="' + card["card_id"] + '"]').click()
    panel = page.locator("#editor-body article").filter(has_text=copy["id"])
    panel.get_by_text("Guide scenarios for this copy", exact=True).click()
    panel.get_by_text("Conditional:", exact=False).wait_for()
    page.screenshot(path=str(root / f"{label}-parity-copy-values.png"))
    panel.get_by_role("button", name="Change first-edition selection").click()
    page.get_by_label("First edition selected", exact=True).check()
    page.get_by_role("button", name="Preview edition change").click()
    page.get_by_role("button", name="Confirm changes", exact=True).click()
    page.get_by_text("Changes saved. Retrying confirmation will not add them again.", exact=True).wait_for()
    page.screenshot(path=str(root / f"{label}-parity-edition-review.png"))
    page.get_by_role("button", name="Undo this operation", exact=True).click()
    page.get_by_text("This operation has been undone; retries will not reapply it.", exact=True).wait_for()
    page.get_by_role("button", name="Close review", exact=True).click()
    # Sample results and API/browser spoiler boundary, explicit reveal, then re-hide.
    page.goto(base + "/hunt/")
    page.get_by_label("Search source", exact=True).select_option("sample")
    page.get_by_label("Search pool", exact=True).select_option("known_lots")
    with page.expect_response(
        lambda r: r.url == base + "/api/hunts/" and r.request.method == "POST"
    ) as response:
        page.get_by_role("button", name="Find sample cards").click()
    found = response.value.json()
    assert found["demo"] and found["results"]
    hidden = response.value.text()
    assert all(
        k not in found["results"][0] for k in ["title", "url", "cards", "components", "condition", "image"]
    )
    for text in ["Sample Jungle & Neo Discovery sorting lot", "sample-lot"]:
        assert text not in hidden and text not in page.content()
    page.screenshot(path=str(root / f"{label}-parity-hidden.png"), full_page=True)
    page.get_by_role("button", name="Reveal contents").first.click()
    page.get_by_role("heading", name="Revealed contents", exact=True).wait_for()
    title = page.locator("#editor-body h3").first.inner_text()
    assert title
    page.screenshot(path=str(root / f"{label}-parity-revealed.png"))
    page.get_by_role("button", name="Close copy details", exact=True).click()
    page.get_by_role("link", name="Saved finds", exact=True).click()
    page.locator("[data-saved]").first.click()
    page.get_by_role("button", name="Reveal contents").first.wait_for()
    assert title not in page.content()
    page.screenshot(path=str(root / f"{label}-parity-reopened.png"), full_page=True)
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    (root / f"{label}-parity-report.json").write_text(
        json.dumps(
            {
                "result": "PASS",
                "spoilers": "API and DOM hidden before reveal and after reopen",
                "edition": "synthetic copy selected and undone",
                "views": ["overview", "pokedex", "cards", "hunt", "missing", "finds"],
                "viewport": page.viewport_size,
            },
            indent=2,
        )
    )
