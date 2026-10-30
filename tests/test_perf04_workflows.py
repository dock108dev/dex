"""Isolated interactive workflows against real views and mutation authority."""

import threading
from wsgiref.simple_server import make_server

import pytest
from django.core.handlers.wsgi import WSGIHandler
from test_account_reads import prepared as prepared
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_effective_collection import cx as cx
from test_migration import snapshot as snapshot
from test_perf04_browser import Quiet, Server
from test_sealed_catalog import e1 as e1

pytestmark = pytest.mark.allow_hosts(["127.0.0.1"])


@pytest.fixture
def browser_app(prepared, request):
    from playwright.sync_api import sync_playwright

    from pokemon_hunter.beta import collection_drafts

    collection_drafts.initialize()
    mode = getattr(request, "param", None)
    if mode == "bulk":
        from test_catalog_read_performance import seed

        from pokemon_hunter.beta import account_read_build as accounts
        from pokemon_hunter.beta import catalog_read_build as catalogs
        from pokemon_hunter.beta.collection import execute

        seed(prepared, 200)
        execute(
            "UPDATE printings SET set_id='perf-set-1',collector_number=CAST(CAST(substr(id,6) AS INTEGER)%115 AS TEXT) WHERE id LIKE 'perf-%'"
        )
        catalogs.activate(catalogs.prepare())
        accounts.prepare(prepared["actor"])
    if mode == "photo":
        from photo_batch_helpers import cropped

        from pokemon_hunter.beta import photo_batches

        photo_batches.initialize()
        prepared["photo_batch"] = cropped(prepared)
    if mode == "frozen":
        from test_collection_goals import create
        from test_effective_collection import select

        _, source = select(prepared, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}})
        prepared["frozen_goal"] = create(prepared, source)
        select(prepared)
    if mode == "labels":
        from test_catalog_read_performance import seed
        from test_effective_collection import apply

        from pokemon_hunter.beta import account_read_build, catalog_read_build, collection, store

        seed(prepared, 400)
        catalog_read_build.activate(catalog_read_build.prepare())
        account_read_build.prepare(prepared["actor"])
        binder = apply(prepared["actor"], "binder", {"name": "Retained private binder"})["changes"][0][
            "after"
        ]
        copy = collection.copies(prepared["actor"])[0]
        apply(
            prepared["actor"],
            "edit",
            {"id": copy["id"], "revision": copy["revision"], "attributes": {"binder_id": binder["id"]}},
        )
        prepared["binder_group"] = store.rows(
            "SELECT group_id FROM ar_copies WHERE user_id=%s AND id=%s",
            [prepared["actor"].user_id, copy["id"]],
        )[0]["group_id"]
        prepared["binder_id"] = binder["id"]
    if mode == "records":
        import json

        from pokemon_hunter.beta import account_read_build, catalog_read_build, collection

        collection.execute(
            "UPDATE printings SET publication_state='archived' WHERE id=%s",
            [prepared["by_legacy"]["a"]["id"]],
        )
        collection.execute(
            "UPDATE printings SET attributes=%s WHERE id=%s",
            [
                json.dumps(
                    dict(
                        name="Retained long name " + "x" * 5000,
                        pokemon_dex=1,
                        dex_eligible=True,
                        supertype="Pokémon",
                    )
                ),
                prepared["by_legacy"]["b"]["id"],
            ],
        )
        catalog_read_build.activate(catalog_read_build.prepare())
        account_read_build.prepare(prepared["actor"])
        rows = prepared["a"].get("/api/v2/my-card-groups/").json()["groups"]
        prepared["archived_group"] = next(r["id"] for r in rows if r.get("name") == "Ivysaur")
    application = WSGIHandler()

    def app(environ, start):
        # Map only this isolated loopback origin alongside Host; CSRF remains enforced.
        if environ.get("HTTP_ORIGIN") == base:
            environ["HTTP_ORIGIN"] = "http://127.0.0.1:8011"
        environ["HTTP_HOST"] = "127.0.0.1:8011"
        return application(environ, start)

    server = make_server("127.0.0.1", 0, app, Server, Quiet)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            context = browser.new_context()
            context.add_cookies(
                [{"name": k, "value": v.value, "url": base} for k, v in prepared["a"].cookies.items()]
            )
            page = context.new_page()
            page.route("**/*", lambda r: r.continue_() if r.request.url.startswith(base) else r.abort())
            errors, requests = [], []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("request", lambda request: requests.append(request.url.removeprefix(base)))
            yield prepared, page, base, requests, errors
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_goals_create_progress_rename_and_undo(browser_app):
    from playwright.sync_api import expect

    cx, page, base, requests, errors = browser_app
    page.goto(base + "/goals/")
    expect(page.locator("#goal-name")).to_be_visible()
    page.locator("#goal-name").fill("Frozen test goal")
    page.locator("#goal-kind").select_option("custom")
    page.locator("#bounded-set").get_by_role("button", name="Load records").click()
    page.locator("#bounded-set [data-choice]").first.click()
    expect(page.locator("#goal-members input[type=checkbox]").first).to_be_visible()
    page.locator("#goal-members input[type=checkbox]").first.check()
    page.get_by_role("button", name="Preview tracking goal").click()
    expect(page.locator("#confirm")).to_be_visible()
    page.locator("#confirm").click()
    expect(page.locator("#saved-goals")).to_contain_text("Frozen test goal")
    page.locator('[data-close="review"]').click()
    page.get_by_role("button", name="View frozen checklist and progress").click()
    expect(page.locator("#goal-target-list article")).to_have_count(1)
    page.locator('[data-close="editor"]').click()
    page.get_by_role("button", name="Edit goal", exact=True).click()
    page.locator("#retained-goal-name").fill("Preserved test goal")
    page.get_by_role("button", name="Preview name change").click()
    page.locator("#confirm").click()
    expect(page.locator("#saved-goals")).to_contain_text("Preserved test goal")
    page.locator("#undo").click()
    expect(page.locator("#saved-goals")).to_contain_text("Frozen test goal")
    assert not errors, errors
    assert "/api/collection/" not in requests
    assert "/api/catalog/" not in requests


@pytest.mark.parametrize("browser_app", ["bulk"], indirect=True)
def test_bulk_cross_page_selection_save_confirm_recover_undo(browser_app):
    from playwright.sync_api import expect

    cx, page, base, requests, errors = browser_app
    page.goto(base + "/add-many/")
    expect(page.locator("#bulk-catalog-rows .bulk-card").first).to_be_visible()
    page.locator("#bulk-action").select_option("mark_owned")
    page.locator("#bulk-set").select_option("perf-set-1")
    expect(page.locator("#bulk-next")).to_be_enabled()
    page.locator("#bulk-catalog-rows input[type=checkbox]").first.check()
    page.locator("#bulk-next").click()
    expect(page.locator("#bulk-page")).to_contain_text("Page 2")
    page.locator("#bulk-catalog-rows input[type=checkbox]").first.check()
    page.locator("#bulk-range").click()
    expect(page.locator("#bulk-count")).to_contain_text("51 draft rows")
    page.locator("#bulk-all-matches").click()
    expect(page.locator("#bulk-status")).to_contain_text("matching cards selected across pages")
    page.locator("#bulk-save").click()
    expect(page.locator("#bulk-draft-record")).to_be_visible()
    saved_url = page.url
    page.reload()
    expect(page.locator("#bulk-count")).not_to_contain_text("No cards selected")
    expect(page.locator("#bulk-tray")).not_to_contain_text("Loading saved identity")
    page.locator("#bulk-review").click()
    expect(page.locator("#bulk-confirm")).to_be_enabled()
    page.locator("#bulk-confirm").click()
    expect(page.locator("#bulk-receipt")).to_be_visible()
    count = sum("/confirm/" in r for r in requests)
    page.goto(saved_url)
    expect(page.locator("#bulk-receipt")).to_be_visible()
    assert sum("/confirm/" in r for r in requests) == count == 1
    page.locator("#bulk-undo").click()
    expect(page.locator("#bulk-status")).to_contain_text("Whole batch undone")
    assert not errors, errors
    assert "/api/bulk/catalog/" not in requests


@pytest.mark.parametrize("browser_app", ["photo"], indirect=True)
def test_manual_photo_correction_confirmation_and_undo(browser_app):
    from playwright.sync_api import expect

    cx, page, base, requests, errors = browser_app
    batch = cx["photo_batch"]
    page.goto(base + "/add-photos/?batch=" + batch["id"])
    expect(page.locator("#photo-cards .photo-card")).to_have_count(1)
    if not page.locator(".photo-card details").first.evaluate("e=>e.open"):
        page.locator(".photo-card details").first.locator("summary").click()
    page.get_by_role("button", name="Search choices", exact=True).click()
    select = page.get_by_role("combobox", name="Card match")
    expect(select.locator("option")).not_to_have_count(1)
    select.select_option(index=1)
    selected_value = select.input_value()
    selected_label = select.locator("option:checked").inner_text()
    page.get_by_role("searchbox", name="Find another card").fill("No matching engineering card")
    expect(page.locator(".photo-card [role=status]")).to_contain_text("0 choices")
    expect(select).to_have_value(selected_value)
    expect(select.locator("option:checked")).to_have_text(selected_label)
    page.locator("#photo-confirm").click()
    expect(page.locator("#photo-report")).to_be_visible()
    count = sum("confirm-cards" in r for r in requests)
    assert count == 1
    page.locator("#photo-undo").click()
    expect(page.locator("#photo-report-body")).to_contain_text("These changes were undone")
    assert not errors, errors
    assert not any("analyze" in r or "recognize" in r or "detect" in r for r in requests)


@pytest.mark.parametrize(
    "status,code,visible",
    [
        (400, "invalid_request", "Invalid test selection"),
        (403, "forbidden", "Sign in again"),
        (404, "not_found", "unavailable to the current account"),
        (409, "stale_read_state", "records changed"),
        (503, "read_state_unavailable", "Browsing is unavailable"),
    ],
)
def test_primary_error_visible_retry_preserves_route(browser_app, status, code, visible):
    from playwright.sync_api import expect

    _, page, base, requests, errors = browser_app
    pattern = "**/api/v2/my-card-groups/**"
    page.route(
        pattern,
        lambda route: route.fulfill(status=status, json={"code": code, "error": "Invalid test selection"}),
    )
    page.goto(base + "/cards/?q=pikachu")
    expect(page.locator("#content")).to_contain_text(visible)
    expect(page.locator(".owned-card-tile")).to_have_count(0)
    page.unroute(pattern)
    page.locator("#card-retry").click()
    expect(page.locator("#cards-query")).to_have_value("pikachu")
    expect(page.locator("#card-retry")).to_have_count(0)
    assert "/api/collection/" not in requests
    assert not errors, errors


def test_secondary_failure_preserves_primary_and_retries(browser_app):
    from playwright.sync_api import expect

    _, page, base, _, errors = browser_app
    page.goto(base + "/card-library/")
    expect(page.locator(".owned-card-tile").first).to_be_visible()
    count = page.locator(".owned-card-tile").count()
    pattern = "**/api/v2/card-group-filters/**"
    page.route(pattern, lambda route: route.fulfill(status=503, json={"code": "read_state_unavailable"}))
    page.get_by_role("button", name="Browse set choices", exact=True).click()
    expect(page.get_by_text("Browsing is unavailable.", exact=False)).to_be_visible()
    expect(page.locator(".owned-card-tile")).to_have_count(count)
    page.unroute(pattern)
    page.get_by_role("button", name="Retry this page", exact=True).click()
    expect(page.get_by_text("Browsing is unavailable.", exact=False)).to_have_count(0)
    assert not errors, errors


def test_cookie_account_switch_revokes_open_subresource(browser_app):
    from playwright.sync_api import expect

    cx, page, base, _, errors = browser_app
    page.goto(base + "/cards/")
    expect(page.locator(".owned-card-tile").first).to_be_visible()
    page.context.add_cookies([{"name": k, "value": v.value, "url": base} for k, v in cx["b"].cookies.items()])
    page.get_by_role("button", name="Browse set choices", exact=True).click()
    expect(page.locator("#content")).to_contain_text("Sign in again")
    expect(page.locator(".owned-card-tile")).to_have_count(0)
    assert not errors, errors


def test_keyboard_card_return_restores_focus_and_scroll(browser_app):
    from playwright.sync_api import expect

    _, page, base, _, errors = browser_app
    page.goto(base + "/card-library/")
    tile = page.locator(".owned-card-tile").last
    expect(tile).to_be_visible()
    identity = tile.get_attribute("data-group-id")
    tile.focus()
    before = page.evaluate("scrollY")
    tile.press("Enter")
    expect(page.locator("#card-back")).to_be_visible()
    page.locator("#card-back").focus()
    page.keyboard.press("Enter")
    expect(page.locator(f'[data-group-id="{identity}"]')).to_be_focused()
    assert abs(page.evaluate("scrollY") - before) < 3
    for width in [390, 320]:
        page.set_viewport_size({"width": width, "height": 900})
        page.evaluate("document.documentElement.style.fontSize='200%'")
        assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
    assert not errors, errors


def test_progressive_artwork_visible_and_bounded_fanout(browser_app):
    import base64

    from playwright.sync_api import expect

    _, page, base, requests, errors = browser_app
    held = []
    # Pixels are an engineering response to the existing authorized descriptor URL.
    # No source server is contacted; the fixture is never a customer demonstration.
    pixel = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a2ioAAAAASUVORK5CYII="
    )
    page.route("**/*", lambda r: r.fallback() if r.request.url.startswith(base) else held.append(r))
    page.goto(base + "/pokedex/", wait_until="domcontentloaded")
    expect(page.locator("#species-grid [data-dex-species]").first).to_be_visible()
    page.wait_for_timeout(150)
    assert len(held) == 4, len(held)
    assert sum("/species-artwork/" in r for r in requests) == 1
    # First results remain usable while every image is still pending.
    expect(page.locator("#dex-search")).to_be_enabled()
    for _ in range(4):
        held.pop(0).fulfill(status=200, content_type="image/png", body=pixel)
    page.wait_for_timeout(100)
    assert len(held) <= 4
    assert page.locator("#species-grid img").first.evaluate("e=>e.complete&&e.naturalWidth>0")
    for route in held:
        route.abort()
    assert not errors, errors


@pytest.mark.parametrize("browser_app", ["bulk"], indirect=True)
def test_bulk_duplicate_review_requires_explicit_decision(browser_app):
    from playwright.sync_api import expect

    _, page, base, requests, errors = browser_app
    page.goto(base + "/add-many/")
    expect(page.locator("#bulk-catalog-rows .bulk-card").first).to_be_visible()
    page.locator("#bulk-set").select_option("perf-set-1")
    page.locator('[data-input="paste"]').click()
    page.locator("#bulk-paste-text").fill("113, 113")
    page.locator("#bulk-parse-paste").click()
    expect(page.locator("#bulk-count")).to_contain_text("2 draft rows")
    page.locator("#bulk-check-all").click()
    page.locator("#bulk-unknown").click()
    page.locator("#bulk-review").click()
    expect(page.locator("#bulk-review-panel")).to_be_visible()
    expect(page.locator("#bulk-confirm")).to_be_disabled()
    page.locator("#bulk-back-edit").click()
    for index, decision in [(0, "different"), (1, "skip")]:
        page.locator("#bulk-tray button").nth(index).click()
        page.locator("#bulk-row-duplicate_decision").select_option(decision)
        page.locator("#bulk-row-save").click()
    page.locator("#bulk-review").click()
    expect(page.locator("#bulk-confirm")).to_be_enabled()
    page.locator("#bulk-confirm").click()
    expect(page.locator("#bulk-receipt")).to_contain_text("1 added copy records")
    expect(page.locator("#bulk-receipt")).to_contain_text("1 excluded/skipped rows")
    page.locator("#bulk-undo").click()
    expect(page.locator("#bulk-status")).to_contain_text("Whole batch undone")
    assert sum("/confirm/" in r for r in requests) == 1
    assert not errors, errors


@pytest.mark.parametrize("browser_app", ["frozen"], indirect=True)
def test_saved_goal_labels_and_frozen_progress_survive_reload(browser_app):
    from playwright.sync_api import expect

    cx, page, base, requests, errors = browser_app
    goal = cx["frozen_goal"]
    page.goto(base + "/pokedex/?q=Ivysaur&goal=" + goal["id"])
    expect(page.locator("#species-grid")).to_contain_text("Counted in saved goal")
    expect(page.locator("#species-grid")).to_contain_text("Not collected")
    expect(page.locator("#dex-goal-summary")).to_contain_text("in the saved declaration")
    expect(page.locator("#dex-goal option:checked")).to_have_text(goal["name"])
    page.reload()
    expect(page.locator("#dex-goal option:checked")).to_have_text(goal["name"])
    page.locator('[data-dex-species="2"]').click()
    expect(page.locator("#content")).to_contain_text("Your Cards is current possession")
    page.get_by_role("link", name="Back to Pokédex", exact=True).click()
    expect(page.locator("#dex-goal option:checked")).to_have_text(goal["name"])
    assert "/api/collection/" not in requests
    assert not errors, errors


@pytest.mark.parametrize("browser_app", ["records"], indirect=True)
def test_archived_child_and_oversized_record_visible(browser_app):
    from playwright.sync_api import expect

    cx, page, base, requests, errors = browser_app
    page.goto(base + "/card-groups/" + cx["archived_group"] + "/?child=" + cx["by_legacy"]["a"]["id"])
    expect(page.locator("#content")).to_contain_text(
        "New copy addition is unavailable for this archived variant"
    )
    expect(page.locator("#group-add-copy")).to_have_count(0)
    expect(page.locator("#content")).to_contain_text("Your owned evidence is retained")
    page.goto(base + "/cards/")
    link = page.get_by_role("link", name="Open complete record", exact=False).first
    expect(link).to_be_visible()
    with page.expect_download() as downloaded:
        link.click()
    import json
    from pathlib import Path

    record = json.loads(Path(downloaded.value.path()).read_text())
    assert record["record"]["name"].startswith("Retained long name ")
    expect(page.locator("#cards-count")).to_contain_text("2 owned cards")
    assert "/api/collection/" not in requests
    assert not errors, errors


def test_selected_child_preview_uses_exact_printing(browser_app):
    from playwright.sync_api import expect

    cx, page, base, _, errors = browser_app
    page.goto(base + "/card-library/")
    page.locator(".owned-card-tile").first.click()
    page.locator("#group-variants summary").click()
    link = page.locator("#group-variants a").first
    expect(link).to_be_visible()
    from urllib.parse import parse_qs, urlparse

    child = parse_qs(urlparse(link.get_attribute("href")).query)["child"][0]
    link.click()
    page.locator("#group-add-copy").click()
    captured = []
    page.on(
        "request",
        lambda r: captured.append(r.post_data_json) if r.url.endswith("/preview/") else None,
    )
    page.get_by_role("button", name="Preview addition", exact=True).click()
    expect(page.locator("#review")).to_be_visible()
    assert captured[-1]["request"]["printing_id"] == child
    expect(page.locator("#review-body")).to_contain_text(child)
    assert not errors, errors


@pytest.mark.parametrize("browser_app", ["labels"], indirect=True)
def test_off_page_set_and_binder_labels(browser_app):
    from playwright.sync_api import expect

    cx, page, base, requests, errors = browser_app
    page.goto(base + "/card-library/")
    page.get_by_role("button", name="Browse set choices", exact=True).click()
    options = page.locator("[data-option-value]")
    expect(options).to_have_count(40)
    page.get_by_role("button", name="Load next page", exact=True).click()
    expect(options).to_have_count(80)
    value = options.last.get_attribute("data-option-value")
    # Pin identity after pagination finishes; a live .last locator may otherwise
    # read the previous page's label and click the newly appended page's value.
    choice = page.locator(f'[data-option-value="{value}"]')
    label = choice.inner_text()
    choice.click()
    page.get_by_role("button", name="Search cards", exact=True).click()
    expect(page.locator("#cards-set option:checked")).to_have_text(label)
    page.reload()
    expect(page.locator("#cards-set")).to_have_value(value)
    expect(page.locator("#cards-set option:checked")).to_have_text(label)
    page.locator(".owned-card-tile").first.click()
    page.locator("#card-back").click()
    expect(page.locator("#cards-set option:checked")).to_have_text(label)
    page.goto(base + "/card-groups/" + cx["binder_group"] + "/")
    page.locator("#group-copy-records summary").click()
    page.locator("[data-group-copy]").first.click()
    expect(page.locator("#binder_id")).to_have_value(cx["binder_id"])
    expect(page.locator("#binder_id option:checked")).to_have_text("Retained private binder")
    page.locator('[data-close="editor"]').click()
    page.locator("[data-group-copy]").first.click()
    expect(page.locator("#binder_id option:checked")).to_have_text("Retained private binder")
    assert "/api/collection/" not in requests
    assert not errors, errors


@pytest.mark.parametrize(
    "route,ready",
    [
        ("/goals/", "#goal-name"),
        ("/add-many/", "#bulk-catalog-rows .bulk-card"),
        ("/add-photos/", "#photo-entry"),
    ],
)
def test_changed_workspaces_narrow_and_enlarged(browser_app, route, ready):
    from playwright.sync_api import expect

    _, page, base, _, errors = browser_app
    for width in [390, 320]:
        page.set_viewport_size({"width": width, "height": 900})
        page.goto(base + route)
        expect(page.locator(ready).first).to_be_visible()
        page.evaluate(
            '[...document.querySelectorAll("body,body *")].map(e=>[e,parseFloat(getComputedStyle(e).fontSize)]).forEach(([e,n])=>e.style.fontSize=(n*2)+"px")'
        )
        assert page.evaluate("document.documentElement.scrollWidth<=innerWidth"), route
    assert not errors, errors


@pytest.mark.parametrize("browser_app", ["bulk"], indirect=True)
def test_custom_goal_keeps_members_and_labels_across_search_and_pages(browser_app):
    from playwright.sync_api import expect

    cx, page, base, _, errors = browser_app
    page.goto(base + "/goals/")
    page.locator("#goal-name").fill("Cross-page frozen members")
    page.locator("#goal-kind").select_option("custom")
    page.locator("#bounded-set").get_by_role("button", name="Load records", exact=True).click()
    page.locator('#bounded-set [data-choice="perf-set-1"]').click()
    first = page.locator("#goal-members input[type=checkbox]").first
    expect(first).to_be_visible()
    value = first.get_attribute("value")
    label = first.locator("..").inner_text()
    first.check()
    page.locator("#goal-search").fill("No matching engineering card")
    page.locator("#goal-search").press("Tab")
    expect(page.locator("#goal-members")).to_contain_text("0 records")
    expect(page.locator("#goal-members")).to_contain_text("1 selected across all pages")
    page.locator("#goal-search").fill("")
    page.locator("#goal-search").press("Tab")
    expect(page.locator(f'#goal-members input[value="{value}"]')).to_be_checked()
    expect(page.locator(f'#goal-members input[value="{value}"]').locator("..")).to_have_text(label)
    page.locator("#goal-members").get_by_role("button", name="Load next page", exact=True).click()
    expect(page.locator("#goal-members")).to_contain_text("page 2 of")
    second = page.locator("#goal-members input[type=checkbox]").last
    second.check()
    second_value = second.get_attribute("value")
    captured = []
    page.on("request", lambda r: captured.append(r.post_data_json) if r.url.endswith("/preview/") else None)
    with page.expect_response(
        lambda r: r.request.method == "POST" and r.url.endswith("/preview/")
    ) as previewed:
        page.get_by_role("button", name="Preview tracking goal", exact=True).click()
    assert previewed.value.status == 200
    preview = previewed.value.json()
    expect(page.locator("#confirm")).to_be_visible()
    assert set(captured[-1]["request"]["printing_ids"]) == {value, second_value}
    # A click starts confirmation; only its receipt establishes committed authority.
    with page.expect_response(
        lambda r: r.request.method == "POST" and r.url.endswith("/confirm/")
    ) as confirmed:
        page.locator("#confirm").click()
    assert confirmed.value.status == 200
    receipt = confirmed.value.json()
    assert receipt["state"] == "confirmed"
    assert receipt["id"] == preview["id"]
    assert receipt["user_id"] == cx["actor"].user_id
    page.locator('[data-close="review"]').click()
    page.reload()
    page.get_by_role("button", name="View frozen checklist and progress", exact=True).click()
    expect(page.locator("#goal-target-list article")).to_have_count(2)
    assert not errors, errors


@pytest.mark.parametrize("browser_app", ["bulk"], indirect=True)
def test_custom_goal_waits_for_confirmation_before_reload(browser_app, monkeypatch):
    from pokemon_hunter.beta import collection

    _, page, base, requests, _ = browser_app
    entered, release, completed = (threading.Event() for _ in range(3))
    original = collection.confirm
    stale_reads = []

    def held_confirm(*args, **kwargs):
        entered.set()
        # The broken workflow reloads during this interval. A receipt-aware
        # workflow waits, then reads the committed revision on its new page.
        release.wait(2)
        result = original(*args, **kwargs)
        completed.set()
        return result

    def commit_before_stale_read(route):
        if entered.is_set() and not completed.is_set():
            stale_reads.append(route.request.url)
            release.set()
            assert completed.wait(10), "Confirmation did not complete"
        route.continue_()

    monkeypatch.setattr(collection, "confirm", held_confirm)
    page.route(base + "/api/v2/goals/**", commit_before_stale_read)
    test_custom_goal_keeps_members_and_labels_across_search_and_pages(browser_app)
    assert completed.is_set()
    assert not stale_reads
    assert sum("/confirm/" in path for path in requests) == 1
