"""Fake official-client searches, private saved scopes and spoiler-safe replay."""

import json
from copy import deepcopy

import pytest
from test_b1 import env as env
from test_b2 import apply, post
from test_b2 import b2 as b2
from test_b2_parity import restored as restored
from test_migration import snapshot as snapshot

from pokemon_hunter.beta import collection as service
from pokemon_hunter.beta import ebay_hunts, goal_hunts, parity


@pytest.fixture
def live(restored, monkeypatch):
    root = restored["root"] / "ebay-config"
    (root / ".env").write_text(
        "EBAY_CLIENT_ID=fixture-key\nEBAY_CLIENT_SECRET=fixture-secret\n"
        "EBAY_DELIVERY_POSTAL_CODE=07740\nOPENAI_API_KEY=never-loaded\n"
    )
    (root / "config").mkdir()
    (root / "config/settings.yaml").write_text(
        "environment: sandbox\nsearch:\n  max_pages: 5\n  page_size: 20\n"
    )
    calls, clients = [], []
    raw = parity.evidence("demo_hunts.json", [])[0]
    raw["title"] = "Test Missing 3/100 lot of 30 Pokemon cards"
    raw["condition"] = "Lightly Played"

    class FakeClient:
        def __init__(self, provider, credentials=None, extended=False):
            from django.db import connection

            assert not connection.in_atomic_block
            self.settings = provider
            assert credentials == ("fixture-key", "fixture-secret")
            assert extended is True
            self.warnings = ["SECRET provider warning"]
            self.closed = False
            clients.append(self)

        def search(self, query, option):
            calls.append((query, option))
            return iter([deepcopy(raw)])

        def close(self):
            self.closed = True

    monkeypatch.setattr(ebay_hunts.ebay, "EbayClient", FakeClient)
    return {**restored, "calls": calls, "clients": clients, "raw": raw, "provider_root": root}


def test_config_status_is_read_only_and_uses_ebay_values_only(live, monkeypatch):
    monkeypatch.setenv("EBAY_CLIENT_ID", "environment-wins")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    provider, values = ebay_hunts.configuration()
    assert values["EBAY_CLIENT_ID"] == "environment-wins"
    assert provider.delivery_postal_code == "07740" and provider.search.max_pages == 2
    before = live["a"].get("/api/hunts/").json()
    assert before["search_status"]["configured"] is True
    assert before["search_status"]["environment"] == "sandbox"
    assert not live["clients"]
    import os

    assert "OPENAI_API_KEY" not in os.environ
    assert "EBAY_CLIENT_SECRET" not in os.environ
    assert "fixture-secret" not in json.dumps(before)


def test_live_search_bounds_spoilers_isolation_replay_and_rescore(live):
    found = post(live["a"], "/api/hunts/", {"demo": False, "budget": "100"})
    assert found.status_code == 200, found.content
    found = found.json()
    assert found["demo"] is False and found["coverage"] == {
        "queries_run": 8,
        "queries_total": 11,
        "offset": 0,
        "next_offset": 8,
        "limited": True,
        "environment": "sandbox",
    }
    assert len(live["calls"]) == 16
    assert live["clients"][0].closed
    assert "SECRET" not in json.dumps(found)
    result = found["results"][0]
    assert not {"title", "url", "cards", "components", "image", "condition"} & result.keys()
    route = f"/api/hunts/{found['batch']}/{found['id']}/"
    assert live["b"].get(route).status_code == 404
    reveal = route + "reveal/" + result["id"] + "/"
    assert post(live["b"], reveal, {}).status_code == 404
    shown = post(live["a"], reveal, {}).json()
    assert shown["cards"] == ["c"] and shown["url"] == "https://www.ebay.com/SECRET"
    call_count = len(live["calls"])
    assert live["a"].get(route).json()["results"][0]["dex_hits"] == 1
    assert len(live["calls"]) == call_count
    printing = next(p for p in live["catalog"] if json.loads(p["provenance"])["legacy_id"] == "c")
    apply(live, "add", {"printing_id": printing["id"], "attributes": {}, "duplicate_policy": "allow"})
    assert live["a"].get(route).json()["results"][0]["dex_hits"] == 0
    assert len(live["calls"]) == call_count
    history = next(h for h in live["a"].get("/api/hunts/").json()["hunts"] if h["batch"] == found["batch"])
    assert history["environment"] == "sandbox" and "SECRET" not in json.dumps(history)


def test_continuation_uses_saved_plan_and_rejects_cross_account_or_changed_settings(live):
    first = post(live["a"], "/api/hunts/", {"demo": False}).json()
    next_request = {**first["settings"], "offset": 8, "continuation_batch": first["batch"]}
    before = len(live["calls"])
    assert post(live["b"], "/api/hunts/", next_request).status_code == 404
    assert post(live["a"], "/api/hunts/", {**next_request, "focus": "johto"}).status_code == 400
    assert post(live["a"], "/api/hunts/", {"demo": False, "offset": 8}).status_code == 400
    assert len(live["calls"]) == before
    evidence = live["root"] / "parity-evidence/hunt.json"
    config = json.loads(evidence.read_text())
    config["pools"]["known_lots"] = ["SHOULD NOT REPLACE SAVED PLAN"]
    evidence.write_text(json.dumps(config))
    second = post(live["a"], "/api/hunts/", next_request)
    assert second.status_code == 200, second.content
    assert second.json()["coverage"]["next_offset"] is None
    assert second.json()["coverage"]["queries_run"] == 3
    assert len(live["calls"]) == before + 6
    assert all("SHOULD NOT" not in query for query, _ in live["calls"])


def test_failed_provider_is_sanitized_and_does_not_save(live, monkeypatch, caplog):
    def failed(*args):
        raise RuntimeError("SECRET credential and seller payload")

    monkeypatch.setattr(ebay_hunts.ebay, "discover", failed)
    before = len(parity.hunt_rows(live["actor"]))
    response = post(live["a"], "/api/hunts/", {"demo": False})
    assert response.status_code == 502
    assert "SECRET" not in response.content.decode() + caplog.text
    assert len(parity.hunt_rows(live["actor"])) == before
    assert live["clients"][0].closed


def test_provider_http_failure_is_actionable_and_does_not_save(live, monkeypatch, caplog):
    import httpx

    def failed(*args):
        response = httpx.Response(401, json={"error": "invalid_client", "error_description": "SECRET"})
        raise ebay_hunts.ebay.EbayHTTPError("OAuth", 401, response)

    monkeypatch.setattr(ebay_hunts.ebay, "discover", failed)
    before = len(parity.hunt_rows(live["actor"]))
    response = post(live["a"], "/api/hunts/", {"demo": False})
    assert response.status_code == 502
    assert "OAuth returned HTTP 401 (invalid_client)" in response.content.decode()
    assert "SECRET" not in response.content.decode() + caplog.text
    assert len(parity.hunt_rows(live["actor"])) == before
    assert live["clients"][0].closed


def test_missing_credentials_staging_and_samples_make_no_provider_call(restored, monkeypatch):
    monkeypatch.setattr(ebay_hunts.ebay, "EbayClient", lambda *a: pytest.fail("Unexpected provider call"))
    assert post(restored["a"], "/api/hunts/", {"demo": False}).status_code == 400
    assert post(restored["a"], "/api/hunts/", {"demo": True}).status_code == 200
    from django.conf import settings

    monkeypatch.setattr(settings, "STAGING", True)
    assert ebay_hunts.status()["enabled"] is False
    with pytest.raises(ebay_hunts.LiveHuntError):
        ebay_hunts.search(["query"])


def test_goal_target_owns_only_allowed_printings_and_frozen_replay(live):
    printing = next(p for p in live["catalog"] if json.loads(p["provenance"])["legacy_id"] == "c")
    op = apply(
        live,
        "goal",
        {
            "name": "Missing target",
            "goal_kind": "custom",
            "policy": "catalog",
            "printing_ids": [printing["id"]],
        },
    )
    goal_id = op["changes"][0]["after"]["id"]
    live["raw"]["title"] = "Test Missing 3/100"
    live["raw"]["shortDescription"] = ""
    first = post(
        live["a"], "/api/hunts/", {"pool": "singles", "demo": False, "goal_id": goal_id, "intent": "missing"}
    )
    assert first.status_code == 200, first.content
    first = first.json()
    assert first["goal"]["name"] == "Missing target"
    assert live["calls"] == [
        ("Pokemon Test Missing 3/100", "AUCTION"),
        ("Pokemon Test Missing 3/100", "FIXED_PRICE"),
    ]
    assert first["results"][0]["exact_hits"] == 1
    assert post(live["b"], "/api/hunts/", {"demo": False, "goal_id": goal_id}).status_code == 404
    route = f"/api/hunts/{first['batch']}/1/"
    # Deleting a goal does not remove its saved scope or trigger a provider call.
    current = service.one(live["actor"], "goal", goal_id)
    apply(live, "goal_remove", {"id": goal_id, "revision": current["revision"]})
    assert live["a"].get(route).json()["goal"] == first["goal"]
    apply(live, "add", {"printing_id": printing["id"], "attributes": {}, "duplicate_policy": "allow"})
    assert live["a"].get(route).json()["results"] == []
    assert len(live["calls"]) == 2


def test_goal_printing_queries_include_owned_species_missing_printing(live):
    data = parity.projection(live["actor"])
    target = deepcopy(data["catalog"][0])
    target["id"] = "other-printing"
    data["catalog"].append(target)
    card = deepcopy(data["cards"]["a"])
    card.update(printing_id=target["id"], card_id="other", owned=False, number="99")
    data["cards"]["other"] = card
    scope = {
        "id": "target",
        "name": "Other printing",
        "definition": {"policy": "catalog", "items": [{"printing_ids": [target["id"]]}]},
    }
    projected = goal_hunts.project(live["actor"], data, scope)
    assert parity.query_plan(projected, parity.evidence("hunt.json", {}), "singles", "all") == [
        "Pokemon Test Normal 99"
    ]
    assert projected["pokedex"]["1"]["dex_owned"] is True
    raw = deepcopy(live["raw"])
    raw.update(title="Test Normal 99", shortDescription="")
    from pokemon_hunter import hunt

    results = hunt.project_results(
        [raw],
        parity.hunt_settings({"pool": "singles", "focus": "kanto"}),
        False,
        projected,
        parity.evidence("hunt.json", {}),
        {},
    )
    assert len(results) == 1 and results[0]["exact_hits"] == 1 and results[0]["dex_hits"] == 0


def test_goal_species_does_not_count_owned_species_outside_allowed_printings(live):
    data = parity.projection(live["actor"])
    target = deepcopy(data["catalog"][0])
    target["id"] = "other-printing"
    data["catalog"].append(target)
    card = deepcopy(data["cards"]["a"])
    card.update(printing_id=target["id"], card_id="other", owned=False, number="99")
    data["cards"]["other"] = card
    scope = {
        "id": "target",
        "name": "Restricted species",
        "definition": {"policy": "species", "items": [{"printing_ids": [target["id"]], "pokemon_dex": 1}]},
    }
    assert data["pokedex"]["1"]["dex_owned"] is True
    projected = goal_hunts.project(live["actor"], data, scope)
    assert projected["pokedex"]["1"]["dex_owned"] is False
    assert parity.query_plan(projected, parity.evidence("hunt.json", {}), "singles", "all") == [
        "Pokemon Test Normal 99"
    ]


def test_goal_trainer_printing_can_match_without_becoming_a_species(live):
    data = parity.projection(live["actor"])
    target = deepcopy(data["catalog"][0])
    target["id"] = "trainer-printing"
    data["catalog"].append(target)
    card = deepcopy(data["cards"]["a"])
    card.update(
        printing_id=target["id"],
        card_id="trainer",
        owned=False,
        name="Professor Oak",
        number="88",
        dex_eligible=False,
        pokemon_dex=None,
        supertype="Trainer",
    )
    data["cards"]["trainer"] = card
    scope = {
        "id": "target",
        "name": "Trainer goal",
        "definition": {"policy": "catalog", "items": [{"printing_ids": [target["id"]]}]},
    }
    projected = goal_hunts.project(live["actor"], data, scope)
    raw = deepcopy(live["raw"])
    raw.update(title="Test Professor Oak 88", shortDescription="")
    from pokemon_hunter import hunt

    results = hunt.project_results(
        [raw],
        parity.hunt_settings({"pool": "singles"}),
        False,
        projected,
        parity.evidence("hunt.json", {}),
        {},
    )
    assert len(results) == 1
    assert (
        results[0]["cards"] == ["trainer"] and results[0]["dex_hits"] == 0 and results[0]["exact_hits"] == 1
    )


def test_invalid_provider_data_rolls_back_saved_hunt(live, caplog):
    live["raw"]["title"] = {"SECRET": "invalid seller payload"}
    before = len(parity.hunt_rows(live["actor"]))
    response = post(live["a"], "/api/hunts/", {"demo": False})
    assert response.status_code == 502
    assert "SECRET" not in response.content.decode() + caplog.text
    assert len(parity.hunt_rows(live["actor"])) == before


def test_custom_query_and_value_intent_include_owned_card(live):
    live["raw"].update(title="Test Normal 001/A", shortDescription="")
    response = post(
        live["a"],
        "/api/hunts/",
        {"demo": False, "pool": "singles", "intent": "value", "query": "  Pokemon Test Normal 001/A  "},
    )
    assert response.status_code == 200, response.content
    found = response.json()
    assert found["settings"]["query"] == "Pokemon Test Normal 001/A"
    assert found["coverage"]["queries_total"] == 1
    assert found["results"][0]["exact_hits"] == 0
    assert len(live["calls"]) == 2
    missing = post(
        live["a"],
        "/api/hunts/",
        {"demo": False, "pool": "singles", "intent": "missing", "query": "Pokemon Test Normal 001/A"},
    ).json()
    assert missing["results"] == []


def test_official_client_extended_description_and_explicit_credentials(monkeypatch):
    import httpx

    from pokemon_hunter.ebay import EbayClient
    from pokemon_hunter.models import Settings

    for key in ebay_hunts.ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    calls = []

    def respond(request):
        calls.append(request)
        if request.url.path == "/identity/v1/oauth2/token":
            assert request.headers["Authorization"].startswith("Basic ")
            return httpx.Response(200, json={"access_token": "fixture-token", "expires_in": 3600})
        assert request.url.params["fieldgroups"] == "EXTENDED"
        return httpx.Response(
            200,
            json={"itemSummaries": [{"itemId": "fixture", "shortDescription": "visible seller description"}]},
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        client = EbayClient(
            Settings(), client=http, credentials=("fixture-key", "fixture-secret"), extended=True
        )
        rows = list(client.search("fixture", "FIXED_PRICE"))
    assert rows[0]["shortDescription"] == "visible seller description"
    assert len(calls) == 2


def test_value_results_rank_discount_and_reveal_price_evidence_only_on_request(live, monkeypatch):
    first = deepcopy(live["raw"])
    first.update(
        itemId="SECRET-first",
        title="Test Missing 3/100 unlimited",
        shortDescription="",
        price={"currency": "USD", "value": "10"},
    )
    second = deepcopy(first)
    second.update(
        itemId="SECRET-second", title="Test Normal 001/A unlimited", price={"currency": "USD", "value": "3"}
    )
    monkeypatch.setattr(ebay_hunts.ebay, "discover", lambda client, queries: [first, second])
    found = post(live["a"], "/api/hunts/", {"demo": False, "pool": "singles", "intent": "value"})
    assert found.status_code == 200, found.content
    found = found.json()
    assert len(found["results"]) == 2
    best = found["results"][0]
    assert best["pricing"]["reference_total"] == "10.00"
    assert best["pricing"]["discount_percent"] == "70.00"
    assert "evidence" not in best["pricing"] and "SECRET" not in json.dumps(found)
    route = f"/api/hunts/{found['batch']}/1/reveal/{best['id']}/"
    shown = post(live["a"], route, {}).json()
    assert shown["pricing"]["evidence"][0]["card_id"] == "a"


@pytest.mark.parametrize("provider_failed", [False, True])
def test_client_cleanup_failure_never_saves_or_masks_provider_failure(
    live, monkeypatch, caplog, provider_failed
):
    import httpx

    def failed_close(client):
        client.closed = True
        raise OSError("SECRET cleanup content")

    monkeypatch.setattr(ebay_hunts.ebay.EbayClient, "close", failed_close)
    if provider_failed:

        def failed(*args):
            raise ebay_hunts.ebay.EbayHTTPError("OAuth", 401, httpx.Response(401))

        monkeypatch.setattr(ebay_hunts.ebay, "discover", failed)
    before = len(parity.hunt_rows(live["actor"]))
    response = post(live["a"], "/api/hunts/", {"demo": False})
    assert response.status_code == 502
    if provider_failed:
        assert "OAuth returned HTTP 401" in response.content.decode()
    assert len(parity.hunt_rows(live["actor"])) == before
    assert "ebay_client_close_failed" in caplog.text
    assert "SECRET" not in response.content.decode() + caplog.text


@pytest.mark.parametrize(
    "fields",
    [
        {"demo": 0},
        {"demo": 1},
        {"demo": "false"},
        {"demo": "true"},
        {"demo": None},
        {"offset": "0"},
        {"offset": 0.0},
        {"offset": True},
    ],
)
def test_search_controls_are_not_coerced_before_provider_access(live, monkeypatch, fields):
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid search controls must not construct a provider client")

    monkeypatch.setattr(ebay_hunts.ebay, "EbayClient", forbidden)
    before = len(parity.hunt_rows(live["actor"]))
    response = post(live["a"], "/api/hunts/", fields)
    assert response.status_code == 400
    assert len(parity.hunt_rows(live["actor"])) == before
    assert not live["calls"]


@pytest.mark.parametrize("content_type", ["text/plain", "application/x-www-form-urlencoded"])
def test_authenticated_search_rejects_non_json_before_provider_access(live, monkeypatch, content_type):
    def forbidden(*args, **kwargs):
        pytest.fail("Non-JSON search must not construct a provider client")

    monkeypatch.setattr(ebay_hunts.ebay, "EbayClient", forbidden)
    before = len(parity.hunt_rows(live["actor"]))
    response = live["a"].post(
        "/api/hunts/",
        '{"demo":false}',
        content_type=content_type,
        HTTP_X_CSRFTOKEN=live["a"].cookies["dex_b1_csrf"].value,
    )
    assert response.status_code == 400
    assert len(parity.hunt_rows(live["actor"])) == before
    assert not live["calls"]
