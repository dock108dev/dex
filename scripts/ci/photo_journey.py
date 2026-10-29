"""Photo review UI against controlled responses; recognition and writes never dispatch."""

from urllib.parse import urlsplit


def exercise(page, base, output):
    from playwright.sync_api import expect

    checks = []
    read_state = page.request.get(base + "/api/v2/collection-context/").json()
    assert read_state["read_version"] == 2 and read_state["public"] is False
    key = "22222222-2222-4222-8222-222222222222"
    group = dict(
        id="group",
        name="Synthetic card",
        set_name="Synthetic set",
        collector_number="1",
        existing=dict(present=False),
        children=[dict(id="printing")],
    )
    batch = dict(
        id=key,
        revision=1,
        state="editing",
        photos=[],
        stages=[],
        crops=[dict(id=key, state="active", candidates=[dict(id="printing")], row_json={}, proposal={})],
    )
    operation = dict(
        id=key,
        state="confirmed",
        plan=dict(
            photo_report=[
                dict(
                    identity=dict(name="Synthetic card", set_name="Synthetic set", number="1"),
                    status="added",
                    first_edition=False,
                )
            ]
        ),
    )
    calls = []

    def boundary(route):
        path = urlsplit(route.request.url).path
        calls.append((path, route.request.method))
        if path == "/api/v2/selection-groups/":
            value = dict(
                read_state,
                groups=[dict(group, present=False)],
                candidates=[dict(id="printing", group_id="group")],
            )
        elif path == "/api/photo-batches/":
            value = dict(batches=[])
        elif path == f"/api/photo-batches/{key}/":
            value = dict(batch=batch)
        elif path == f"/api/photo-batches/{key}/confirm-cards/":
            assert route.request.post_data_json["choices"] == [
                dict(
                    id=key,
                    included=True,
                    row=dict(printing_id="printing"),
                )
            ]
            value = dict(operation=operation)
        elif path == f"/api/operations/{key}/undo/":
            value = {**operation, "state": "undone"}
        else:
            raise AssertionError("Unexpected photo request; no recognition or write fallback allowed")
        route.fulfill(json=value)

    patterns = (
        "**/api/v2/selection-groups/**",
        "**/api/photo-batches/**",
        f"**/api/operations/{key}/undo/",
    )
    for pattern in patterns:
        page.route(pattern, boundary)
    page.route(
        f"**/scan-photos/{key}/", lambda route: route.fulfill(status=404, body="Synthetic missing image")
    )
    try:
        page.goto(base + "/add-photos/")
        expect(page.get_by_role("button", name="Identify cards", exact=True)).to_have_count(0)
        expect(
            page.get_by_text("AI photo recognition is temporarily unavailable.", exact=False)
        ).to_be_visible()
        assert all(method == "GET" for _, method in calls)
        checks.append(
            dict(name="Photo entry offers manual upload without a recognition control", status="PASS")
        )
        page.goto(base + "/add-photos/?batch=" + key)
        expect(page.locator(".photo-card")).to_have_count(1)
        expect(page.locator(".photo-card")).to_contain_text("No image")
        expect(page.locator("#photo-results-title")).to_be_focused()
        for width, scale in ((1280, 1), (390, 1), (320, 2)):
            page.set_viewport_size(dict(width=width, height=900))
            page.evaluate("scale => document.documentElement.style.fontSize = scale * 100 + '%'", scale)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(output / f"photo-review-{width}-{scale}.png"), full_page=True)
        page.locator(".photo-card summary").focus()
        page.keyboard.press("Enter")
        expect(page.get_by_role("combobox", name="Card match")).to_be_visible()
        page.get_by_role("button", name="Add selected cards", exact=True).click()
        expect(page.locator("#photo-report")).to_be_focused()
        expect(page.locator("#photo-report-body")).to_contain_text("Added")
        page.get_by_role("button", name="Undo these changes", exact=True).click()
        expect(page.locator("#photo-report-body")).to_contain_text("undone")
        assert len([method for _, method in calls if method == "POST"]) == 2
        checks.append(
            dict(
                name="Photo review keyboard, missing image, confirmation/report/Undo and narrow text",
                status="PASS",
            )
        )
    finally:
        for pattern in patterns:
            page.unroute(pattern, boundary)
        page.unroute(f"**/scan-photos/{key}/")
    return checks
