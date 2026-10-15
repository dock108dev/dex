"""Independent adversarial checks, disposable engineering accounts only."""

import importlib
import sqlite3
from html.parser import HTMLParser
from unittest.mock import patch
from urllib.parse import urlencode

import pytest
from django.conf import settings
from django.urls import clear_url_caches
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_collection_goals import create
from test_cx03_review import find
from test_effective_collection import add, select
from test_effective_collection import cx as cx
from test_migration import snapshot as snapshot
from test_sealed_catalog import e1 as e1

from pokemon_hunter.beta import collection as inv


def dump(cx):
    with sqlite3.connect(cx["root"] / "inventory.db") as db:
        return list(db.iterdump())


def home(cx, destination, client=None):
    return (client or cx["a"]).get("/api/navigation/home/", {"destination": destination})


@pytest.mark.parametrize(
    "destination",
    [
        "/cards/",
        "/cards/?q=Ivy&sort=name&page=1&scroll=245",
        "/card-library/?species=2&edition=standard&page_size=24",
        "/pokedex/?q=Ivy&region=kanto&owned=missing&scroll=901&focus=2",
        "/pokedex/2/",
        "/pokedex/251/?scroll=0",
    ],
)
def test_review_home_finite_success_is_authorized_and_readonly(cx, destination):
    before = dump(cx)
    with patch("requests.sessions.Session.request", side_effect=AssertionError("provider call")):
        response = home(cx, destination)
    assert response.status_code == 200, response.content
    assert response.json()["destination"] == destination
    assert response.json()["navigation_account_id"] == cx["actor"].user_id
    assert "private" in response["Cache-Control"] and "no-store" in response["Cache-Control"]
    assert dump(cx) == before


@pytest.mark.parametrize(
    "destination",
    [
        "/",
        "/login/",
        "/settings/",
        "/collection/",
        "/scan/",
        "/shopping/",
        "/goals/",
        "/api/export/",
        "/cards/../settings/",
        "//example.com/cards/",
        "https://example.com/cards/",
        "/cards/#private",
        "/cards/?account_id=other",
        "/cards/?q=one&q=two",
        "/cards/?scroll=-1",
        "/cards/?scroll=10000001",
        "/cards/?scroll=١",
        "/cards/?page=0",
        "/pokedex/0/",
        "/pokedex/252/",
        "/pokedex/?q=%00",
        "/pokedex/?region=mars",
        "/pokedex/?focus=252",
        "/pokedex/?selecting=2",
        "/pokedex/2/?child=foreign",
        "/pokedex/2/?return=%2Fshopping%2F",
    ],
)
def test_review_home_never_remembers_unsafe_or_mutable_destination(cx, destination):
    before = dump(cx)
    response = home(cx, destination)
    assert response.status_code == 400, response.content
    assert dump(cx) == before


def test_review_home_endpoint_rejects_forged_or_duplicate_authority(cx):
    before = dump(cx)
    for query in (
        "destination=%2Fcards%2F&destination=%2Fpokedex%2F",
        "destination=%2Fcards%2F&account_id=foreign",
        "destination=%2Fcards%2F&generation=1",
    ):
        assert cx["a"].get("/api/navigation/home/?" + query).status_code == 400
    assert dump(cx) == before


def test_review_home_group_child_reauthorization_has_no_default_printing(cx):
    group = find(cx)
    child = cx["by_legacy"]["a"]["id"]
    before = dump(cx)
    for destination in (group["url"], group["url"] + "?" + urlencode({"child": child})):
        assert home(cx, destination).status_code == 200
    assert home(cx, group["url"] + "?" + urlencode({"child": cx["by_legacy"]["c"]["id"]})).status_code in {
        400,
        404,
    }
    assert cx["a"].get(f"/api/card-groups/{group['id']}/").json()["selected_child"] is None
    assert dump(cx) == before


def test_review_home_goal_does_not_substitute_foreign_or_deleted_saved_goal(cx):
    _, source = select(cx, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}})
    goal = create(cx, source)
    destination = "/pokedex/?" + urlencode({"goal": goal["id"], "region": "kanto"})
    before = dump(cx)
    assert home(cx, destination).status_code == 200
    assert home(cx, destination, cx["b"]).status_code in {400, 404}
    assert dump(cx) == before
    inv.execute("DELETE FROM collection_goals WHERE id=%s", [goal["id"]])
    before = dump(cx)
    assert home(cx, destination).status_code in {400, 404}
    assert dump(cx) == before


def test_review_home_private_archived_group_cannot_cross_account(cx):
    group = find(cx)
    inv.execute("UPDATE printings SET publication_state='archived' WHERE id=%s", [cx["by_legacy"]["a"]["id"]])
    before = dump(cx)
    assert home(cx, group["url"]).status_code == 200
    assert home(cx, group["url"], cx["b"]).status_code in {400, 404}
    assert dump(cx) == before


def test_review_home_account_logout_and_revocation_discard_authority(cx):
    assert (
        home(cx, "/cards/").json()["navigation_account_id"]
        != home(cx, "/cards/", cx["b"]).json()["navigation_account_id"]
    )
    cx["accounts"].revoke(cx["second"])
    assert home(cx, "/cards/", cx["b"]).status_code in {302, 403}
    assert home(cx, "/cards/", cx["client"]()).status_code in {302, 403}
    assert (
        cx["a"].post("/logout/", {"csrfmiddlewaretoken": cx["a"].cookies["dex_b1_csrf"].value}).status_code
        == 302
    )
    assert home(cx, "/cards/").status_code in {302, 403}


@pytest.mark.parametrize("parity,staging", [(False, False), (True, False), (False, True), (True, True)])
def test_review_b2_primary_and_home_routes_have_single_handlers(b2, parity, staging):
    from pokemon_hunter.beta import urls

    previous = settings.PARITY_ENABLED, settings.STAGING
    settings.PARITY_ENABLED, settings.STAGING = parity, staging
    importlib.reload(urls)
    clear_url_caches()
    try:
        for path in ("/", "/cards/", "/card-library/", "/pokedex/", "/shopping/", "/api/navigation/home/"):
            assert sum(pattern.resolve(path.lstrip("/")) is not None for pattern in urls.urlpatterns) == 1
    finally:
        settings.PARITY_ENABLED, settings.STAGING = previous
        importlib.reload(urls)
        clear_url_caches()


def test_review_add_card_entry_cannot_create_copy_preview_or_provider_work(cx):
    before = dump(cx)
    with patch("requests.sessions.Session.request", side_effect=AssertionError("provider call")):
        response = cx["a"].get("/card-library/")
    assert response.status_code == 200
    assert dump(cx) == before


@pytest.mark.parametrize(
    "query",
    [
        "species=0",
        "species=252",
        "species=١",
        "species=2&species=3",
        "species=2&group=bad",
        "child=anything",
        "species=2&account_id=other",
        "species=2&quantity=7",
        "species=2&owned=missing",
        "species=2&generation=-1",
        "species=2&generation=١",
        "species=2&return=/settings/",
        "species=2&return=https://example.com/",
        "species=2&return=%2Fpokedex%2F%3Fq%3Da%26q%3Db",
        "group=bad",
        "goal=missing",
        "version=" + "0" * 64,
        "species=",
        "group=",
        "goal=",
        "return=",
        "species=2&goal=missing&version=wrong",
    ],
)
def test_review_shopping_invalid_context_rejected_without_side_effects(cx, query):
    before = dump(cx)
    assert cx["a"].get("/shopping/?" + query).status_code == 400
    assert dump(cx) == before


def test_review_context_empty_explicit_child_is_not_null_child(cx):
    before = dump(cx)
    group = find(cx)
    assert cx["a"].get("/shopping/", {"group": group["id"], "child": ""}).status_code == 400
    assert dump(cx) == before


def test_review_shopping_species_context_never_inherits_first_saved_goal(cx):
    _, source = select(cx, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}})
    frozen = create(cx, source)
    select(cx)
    before = dump(cx)
    response = cx["a"].get("/api/shopping/lot-catalog/", {"species": "2"})
    assert response.status_code == 200, response.content
    context = response.json()["context"]
    assert context["kind"] == "species" and context["species"] == 2
    assert context["current_present"] is False
    assert context["query"].get("goal") is None
    assert context["goal_version"] is None
    assert "Ivysaur" in context["label"]
    assert frozen["id"] != context["query"].get("goal")
    assert dump(cx) == before


def test_review_shopping_group_without_child_is_selection_only(cx):
    from pokemon_hunter.beta import lot_calculator

    group = find(cx)
    before = dump(cx)
    with patch.object(
        lot_calculator, "priced_cards", side_effect=AssertionError("default printing valuation")
    ):
        response = cx["a"].get("/api/shopping/lot-catalog/", {"group": group["id"]})
    assert response.status_code == 200, response.content
    result = response.json()
    assert result["context"]["kind"] == "group" and result["context"]["child"] is None
    assert result["context"]["needs_selection"]
    assert result["cards"] and all(not row["cells"] for row in result["cards"])
    assert not any(key in row for row in result["cards"] for key in ("quantity", "wanted", "locked"))
    assert dump(cx) == before


def test_review_shopping_exact_child_does_not_substitute_another_group(cx):
    group = find(cx)
    child = cx["by_legacy"]["a"]["id"]
    before = dump(cx)
    response = cx["a"].get("/api/shopping/lot-catalog/", {"group": group["id"], "child": child})
    assert response.status_code == 200, response.content
    assert {row["id"] for row in response.json()["cards"]} == {child}
    assert response.json()["context"]["kind"] == "printing"
    assert not response.json()["context"]["needs_selection"]
    assert (
        cx["a"].get("/shopping/", {"group": group["id"], "child": cx["by_legacy"]["c"]["id"]}).status_code
        == 404
    )
    assert dump(cx) == before


def test_review_shopping_archived_exact_target_is_unavailable_without_sibling(cx):
    group = find(cx)
    child = cx["by_legacy"]["a"]["id"]
    inv.execute("UPDATE printings SET publication_state='archived' WHERE id=%s", [child])
    before = dump(cx)
    response = cx["a"].get("/api/shopping/lot-catalog/", {"group": group["id"], "child": child})
    assert response.status_code == 200, response.content
    assert response.json()["cards"] == []
    assert not response.json()["context"]["available"]
    assert response.json()["context"]["child"] == child
    assert dump(cx) == before


def test_review_shopping_foreign_goal_and_stale_version_are_not_usable_authority(cx):
    _, source = select(cx)
    goal = create(cx, source)
    context = {"species": "2", "goal": goal["id"], "version": goal["version"]}
    before = dump(cx)
    assert cx["a"].get("/shopping/", context).status_code == 200
    assert cx["b"].get("/shopping/", context).status_code == 404
    assert cx["a"].get("/shopping/", {**context, "version": "0" * 64}).status_code == 409
    assert dump(cx) == before


def test_review_shopping_stale_generation_rejected_readonly(cx):
    generation = cx["a"].get("/api/pokedex-species/").json()["generation"]
    add(cx)
    before = dump(cx)
    for route in ("/shopping/", "/api/shopping/lot-catalog/"):
        assert cx["a"].get(route, {"species": "2", "generation": str(generation)}).status_code == 409
    assert dump(cx) == before


def test_review_shopping_interleaved_generation_cannot_publish_context(cx):
    from pokemon_hunter.beta import effective_collection

    original = effective_collection.project
    changed = False

    def interleaved(actor, **kwargs):
        nonlocal changed
        result = original(actor, **kwargs)
        if not changed:
            changed = True
            add(cx)
        return result

    with patch.object(effective_collection, "project", side_effect=interleaved):
        result = cx["a"].get("/api/shopping/lot-catalog/", {"species": "2"})
    assert changed and result.status_code == 409


@pytest.mark.parametrize(
    "query", ["restore=a&restore=a", "restore=", "restore=a&species=2", "restore=a&generation=1&generation=2"]
)
def test_review_draft_resolution_rejects_ambiguous_identity_request(cx, query):
    before = dump(cx)
    assert cx["a"].get("/api/shopping/lot-catalog/?" + query).status_code == 400
    assert dump(cx) == before


def test_review_draft_resolution_keeps_missing_id_and_no_new_wants(cx):
    child = cx["by_legacy"]["a"]["id"]
    before = dump(cx)
    old_session = dict(cx["a"].session)
    response = cx["a"].get("/api/shopping/lot-catalog/", {"restore": [child, "removed-printing"]})
    assert response.status_code == 200, response.content
    assert response.json()["missing_ids"] == ["removed-printing"]
    assert {row["id"] for row in response.json()["cards"]} == {child}
    assert response.json()["context"]["account_id"] == cx["actor"].user_id
    assert dict(cx["a"].session) == old_session
    assert dump(cx) == before


def test_review_home_auth_session_binding_changes_at_same_account_relogin(cx):
    first = home(cx, "/cards/").json()
    assert first["navigation_binding"]
    cx["a"].post("/logout/", {"csrfmiddlewaretoken": cx["a"].cookies["dex_b1_csrf"].value})
    assert cx["login"](cx["a"], "admin", cx["password"]).status_code == 302
    second = home(cx, "/cards/").json()
    assert second["navigation_account_id"] == first["navigation_account_id"]
    assert second["navigation_binding"] != first["navigation_binding"]


def test_review_shopping_goal_version_rechecked_after_catalog_projection(cx):
    from pokemon_hunter.beta import lot_calculator

    _, source = select(cx)
    goal = create(cx, source)
    original = lot_calculator.catalog
    changed = False

    def interleaved(actor, *args, **kwargs):
        nonlocal changed
        result = original(actor, *args, **kwargs)
        if not changed:
            changed = True
            inv.execute("UPDATE collection_goals SET version=%s WHERE id=%s", ["0" * 64, goal["id"]])
        return result

    with patch.object(lot_calculator, "catalog", side_effect=interleaved):
        response = cx["a"].get(
            "/api/shopping/lot-catalog/", {"species": "2", "goal": goal["id"], "version": goal["version"]}
        )
    assert changed and response.status_code == 409


def test_review_populated_wants_are_not_changed_by_context_navigation_or_draft_get(cx):
    from test_b2 import post

    cx["a"].get("/shopping/")
    child = cx["by_legacy"]["a"]["id"]
    assert (
        post(cx["a"], "/api/shopping/wants/", {"wants": [{"printing_id": child, "quantity": 7}]}).status_code
        == 200
    )
    before = dump(cx)
    session = dict(cx["a"].session)
    for route, query in (
        ("/shopping/", {"species": "3"}),
        ("/api/shopping/lot-catalog/", {"species": "3"}),
        ("/api/shopping/lot-catalog/", {"restore": [child]}),
        ("/api/navigation/home/", {"destination": "/pokedex/3/"}),
    ):
        assert cx["a"].get(route, query).status_code == 200
    assert dict(cx["a"].session) == session
    assert dump(cx) == before
    assert not any(key.startswith("shopping_wants_") for key in cx["b"].session.keys())


def test_review_ordinary_signin_my_cards_and_explicit_deep_link_precedence(cx):
    client = cx["client"]()
    default = cx["login"](client, "admin", cx["password"])
    assert default.status_code == 302 and default.url == "/"
    assert b"navigation.js" in client.get(default.url).content
    fresh = cx["client"]()
    deep = "/pokedex/2/?return=" + urlencode({"": "/pokedex/?q=Ivy&region=kanto"})[1:]
    fresh.get("/login/", {"next": deep})
    response = fresh.post(
        "/login/",
        {
            "username": "admin",
            "password": cx["password"],
            "next": deep,
            "csrfmiddlewaretoken": fresh.cookies["dex_b1_csrf"].value,
        },
    )
    assert response.status_code == 302 and response.url == deep
    assert fresh.get(response.url).status_code == 200


def test_review_unsafe_signin_return_uses_collection_default(cx):
    for destination in (
        "https://evil.example/cards/",
        "//evil.example/cards/",
        "http://127.0.0.1:9999/cards/",
    ):
        client = cx["client"]()
        client.get("/login/")
        response = client.post(
            "/login/",
            {
                "username": "admin",
                "password": cx["password"],
                "next": destination,
                "csrfmiddlewaretoken": client.cookies["dex_b1_csrf"].value,
            },
        )
        assert response.status_code == 302 and response.url == "/"
        assert b"navigation.js" in client.get(response.url).content


class HeaderLinks(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.in_header = False
        self.links = []
        self.active = None
        self.feed(html.decode())

    def handle_starttag(self, tag, attrs):
        if tag == "header":
            self.in_header = True
        if self.in_header and tag == "a":
            self.active = dict(attrs)
            self.active["text"] = ""
            self.links.append(self.active)

    def handle_endtag(self, tag):
        if tag == "a":
            self.active = None
        if tag == "header":
            self.in_header = False

    def handle_data(self, data):
        if self.active is not None:
            self.active["text"] += data


def test_review_primary_section_has_one_active_header_link(cx):
    group = find(cx)
    for path, expected in (
        ("/cards/", "My Cards"),
        ("/card-library/", "Card Library"),
        ("/pokedex/2/", "Pokédex"),
        ("/shopping/?species=2", "Shopping"),
        (group["url"], "My Cards"),
        (group["url"] + "?" + urlencode({"return": "/pokedex/2/"}), "Pokédex"),
    ):
        response = cx["a"].get(path)
        assert response.status_code == 200, response.content
        links = HeaderLinks(response.content).links
        active = [link for link in links if link.get("aria-current") == "page"]
        assert len(active) == 1 and active[0]["text"].strip() == expected
        assert next(link for link in links if "data-add-card" in link)["href"] == "/card-library/"
    owner = {link["href"] for link in HeaderLinks(cx["a"].get("/cards/").content).links}
    member = {link["href"] for link in HeaderLinks(cx["b"].get("/cards/").content).links}
    assert {
        "/collection/",
        "/goals/",
        "/settings/",
        "/lookup/",
        "/packs/saved/",
        "/scan/",
        "/catalog-review/",
        "/catalog-pipeline/",
        "/product-review/",
    } <= owner
    assert "/catalog-review/" not in member


def test_review_home_and_shopping_reauthorize_bounded_nested_return_chain(cx):
    group = find(cx)
    listing = "/pokedex/?q=Ivy&region=kanto&scroll=850&focus=2"
    species = "/pokedex/2/?" + urlencode({"return": listing, "scroll": "25"})
    destination = group["url"] + "?" + urlencode({"return": species})
    before = dump(cx)
    assert home(cx, destination).status_code == 200
    assert cx["a"].get("/shopping/", {"group": group["id"], "return": destination}).status_code == 200
    nested_group = group["url"] + "?" + urlencode({"return": destination})
    for invalid in (
        nested_group,
        "/pokedex/2/?" + urlencode({"return": species}),
        "/pokedex/?" + urlencode({"return": listing}),
    ):
        assert home(cx, invalid).status_code == 400
        assert cx["a"].get("/shopping/", {"species": "2", "return": invalid}).status_code == 400
    assert dump(cx) == before


@pytest.mark.parametrize(
    "header,value,expected",
    [
        ("HTTP_X_DEX_SHOPPING_BINDING", "old-session", 403),
        ("HTTP_X_DEX_SHOPPING_GENERATION", "0", 409),
        ("HTTP_X_DEX_SHOPPING_GOAL", "foreign", 400),
    ],
)
def test_review_shopping_old_page_authority_rejected_before_wants_write(cx, header, value, expected):
    import json

    cx["a"].get("/shopping/")
    if header == "HTTP_X_DEX_SHOPPING_GENERATION":
        value = str(cx["a"].get("/api/pokedex-species/").json()["generation"] + 1)
    before = dump(cx)
    session = dict(cx["a"].session)
    response = cx["a"].post(
        "/api/shopping/wants/",
        json.dumps({"wants": [{"printing_id": cx["by_legacy"]["a"]["id"], "quantity": 9}]}),
        content_type="application/json",
        HTTP_X_CSRFTOKEN=cx["a"].cookies["dex_b1_csrf"].value,
        **{header: value},
    )
    assert response.status_code == expected, response.content
    assert dict(cx["a"].session) == session
    assert dump(cx) == before


def test_review_b2_only_header_hides_disabled_specialist_routes(b2):
    from pokemon_hunter.beta import urls

    old = settings.B3_ENABLED, settings.B4_ENABLED
    settings.B3_ENABLED, settings.B4_ENABLED = False, False
    importlib.reload(urls)
    clear_url_caches()
    try:
        response = b2["a"].get("/cards/")
        assert response.status_code == 200
        links = {link["href"] for link in HeaderLinks(response.content).links}
        assert not links & {
            "/scan/",
            "/requests/",
            "/catalog-coverage/",
            "/catalog-review/",
            "/catalog-pipeline/",
        }
        assert "/product-review/" in links
        for path in links - {"/", "#main"}:
            assert any(pattern.resolve(path.lstrip("/")) is not None for pattern in urls.urlpatterns), path
    finally:
        settings.B3_ENABLED, settings.B4_ENABLED = old
        importlib.reload(urls)
        clear_url_caches()
