"""Retained historical hunt compatibility; active acquisition is tested separately."""

import json
import uuid
from copy import deepcopy

import pytest
from django.http import Http404
from hunt_history_helpers import demo_rows, seed_history
from test_b1 import env as env
from test_b2 import apply, post
from test_b2 import b2 as b2
from test_b2_parity import restored as restored
from test_migration import snapshot as snapshot

from pokemon_hunter import hunt
from pokemon_hunter.beta import collection as service
from pokemon_hunter.beta import ebay_hunts, goal_hunts, parity, store
from pokemon_hunter.beta.discovery_transport import Transport


@pytest.fixture
def retained(restored, monkeypatch):
    root = restored["root"] / "ebay-config"
    (root / ".env").write_text(
        "EBAY_CLIENT_ID=fixture-key\nEBAY_CLIENT_SECRET=fixture-secret\n"
        "EBAY_DELIVERY_POSTAL_CODE=07740\nOPENAI_API_KEY=never-loaded\n"
    )
    (root / "config").mkdir()
    (root / "config/settings.yaml").write_text(
        "environment: sandbox\nsearch:\n  max_pages: 5\n  page_size: 20\n"
    )
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(True)
        pytest.fail("Historical reads must not acquire provider data")

    monkeypatch.setattr(Transport, "request", forbidden)
    raw = demo_rows()[0]
    raw["title"] = "Test Missing 3/100 lot of 30 Pokemon cards"
    raw["condition"] = "Lightly Played"
    return {**restored, "calls": calls, "raw": raw, "provider_root": root}


def test_config_status_is_read_only_and_uses_ebay_values_only(retained, monkeypatch):
    monkeypatch.setenv("EBAY_CLIENT_ID", "environment-wins")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    provider, values = ebay_hunts.configuration()
    assert values["EBAY_CLIENT_ID"] == "environment-wins"
    assert provider.delivery_postal_code == "07740" and provider.search.max_pages == 5
    before = retained["a"].get("/api/hunts/").json()
    assert before["search_status"]["configured"] is True
    assert before["search_status"]["environment"] == "sandbox"
    assert not retained["calls"]
    import os

    assert "OPENAI_API_KEY" not in os.environ
    assert "EBAY_CLIENT_SECRET" not in os.environ
    assert "fixture-secret" not in json.dumps(before)


def test_retained_search_spoilers_isolation_replay_and_rescore(retained):
    found = seed_history(
        retained["a"],
        {"demo": False, "budget": "100"},
        rows=[retained["raw"]],
        coverage=dict(
            queries_run=8, queries_total=11, offset=0, next_offset=8, limited=True, environment="sandbox"
        ),
    )
    assert found["demo"] is False and found["coverage"] == {
        "queries_run": 8,
        "queries_total": 11,
        "offset": 0,
        "next_offset": 8,
        "limited": True,
        "environment": "sandbox",
    }
    assert "SECRET" not in json.dumps(found)
    result = found["results"][0]
    assert not {"title", "url", "cards", "components", "image", "condition"} & result.keys()
    route = f"/api/hunts/{found['batch']}/{found['id']}/"
    before = store.resource(retained["actor"], "hunts", (found["batch"], 1))
    assert retained["b"].get(route).status_code == 404
    reveal = route + "reveal/" + result["id"] + "/"
    assert post(retained["b"], reveal, {}).status_code == 404
    shown = post(retained["a"], reveal, {}).json()
    assert shown["cards"] == ["c"] and shown["url"] == "https://www.ebay.com/SECRET"
    assert retained["a"].get(route).json()["results"][0]["dex_hits"] == 1
    printing = next(p for p in retained["catalog"] if json.loads(p["provenance"])["legacy_id"] == "c")
    apply(retained, "add", {"printing_id": printing["id"], "attributes": {}, "duplicate_policy": "allow"})
    assert retained["a"].get(route).json()["results"][0]["dex_hits"] == 0
    history = next(
        h for h in retained["a"].get("/api/hunts/").json()["hunts"] if h["batch"] == found["batch"]
    )
    assert history["environment"] == "sandbox" and "SECRET" not in json.dumps(history)
    assert store.resource(retained["actor"], "hunts", (found["batch"], 1)) == before
    assert not retained["calls"]


def test_saved_continuation_metadata_remains_readable_without_dispatch(retained):
    previous = str(uuid.uuid4())
    found = seed_history(
        retained["a"],
        {"demo": False, "offset": 8, "continuation_batch": previous},
        rows=[retained["raw"]],
        coverage=dict(queries_run=3, queries_total=11, offset=8, next_offset=None),
    )
    before = store.resource(retained["actor"], "hunts", (found["batch"], 1))
    reopened = retained["a"].get(f"/api/hunts/{found['batch']}/1/").json()
    assert reopened["settings"]["continuation_batch"] == previous
    assert reopened["settings"]["offset"] == reopened["coverage"]["offset"] == 8
    assert reopened["coverage"]["queries_run"] == 3 and reopened["coverage"]["next_offset"] is None
    assert store.resource(retained["actor"], "hunts", (found["batch"], 1)) == before
    assert not retained["calls"]


def test_staging_status_and_configuration_do_not_admit_provider_access(retained, monkeypatch):
    from django.conf import settings

    monkeypatch.setattr(settings, "STAGING", True)
    assert ebay_hunts.status()["enabled"] is False
    with pytest.raises(ebay_hunts.LiveHuntError):
        ebay_hunts.configuration()
    assert not retained["calls"]


def test_goal_target_keeps_frozen_history_and_current_owned_progress(retained):
    printing = next(p for p in retained["catalog"] if json.loads(p["provenance"])["legacy_id"] == "c")
    op = apply(
        retained,
        "goal",
        {
            "name": "Missing target",
            "goal_kind": "custom",
            "policy": "catalog",
            "printing_ids": [printing["id"]],
        },
    )
    goal_id = op["changes"][0]["after"]["id"]
    retained["raw"].update(title="Test Missing 3/100", shortDescription="")
    first = seed_history(
        retained["a"],
        {"pool": "singles", "demo": False, "goal_id": goal_id, "intent": "missing"},
        rows=[retained["raw"]],
    )
    assert first["goal"]["name"] == "Missing target" and first["results"][0]["exact_hits"] == 1
    with pytest.raises(Http404):
        seed_history(retained["b"], {"demo": False, "goal_id": goal_id}, rows=[retained["raw"]])
    route = f"/api/hunts/{first['batch']}/1/"
    before = store.resource(retained["actor"], "hunts", (first["batch"], 1))
    current = service.one(retained["actor"], "goal", goal_id)
    apply(retained, "goal_remove", {"id": goal_id, "revision": current["revision"]})
    assert retained["a"].get(route).json()["goal"] == first["goal"]
    apply(retained, "add", {"printing_id": printing["id"], "attributes": {}, "duplicate_policy": "allow"})
    assert retained["a"].get(route).json()["results"] == []
    assert store.resource(retained["actor"], "hunts", (first["batch"], 1)) == before
    assert not retained["calls"]


def test_goal_printing_queries_include_owned_species_missing_printing(retained):
    data = parity.projection(retained["actor"])
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
    projected = goal_hunts.project(retained["actor"], data, scope)
    assert hunt.query_plan(projected, parity.evidence("hunt.json", {}), "singles", "all") == [
        "Pokemon Test Normal 99"
    ]
    assert projected["pokedex"]["1"]["dex_owned"] is True
    raw = deepcopy(retained["raw"])
    raw.update(title="Test Normal 99", shortDescription="")
    results = hunt.project_results(
        [raw],
        parity.hunt_settings({"pool": "singles", "focus": "kanto"}),
        False,
        projected,
        parity.evidence("hunt.json", {}),
        {},
    )
    assert len(results) == 1 and results[0]["exact_hits"] == 1 and results[0]["dex_hits"] == 0


def test_goal_species_does_not_count_owned_species_outside_allowed_printings(retained):
    data = parity.projection(retained["actor"])
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
    projected = goal_hunts.project(retained["actor"], data, scope)
    assert projected["pokedex"]["1"]["dex_owned"] is False
    assert hunt.query_plan(projected, parity.evidence("hunt.json", {}), "singles", "all") == [
        "Pokemon Test Normal 99"
    ]


def test_goal_trainer_printing_can_match_without_becoming_a_species(retained):
    data = parity.projection(retained["actor"])
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
    projected = goal_hunts.project(retained["actor"], data, scope)
    raw = deepcopy(retained["raw"])
    raw.update(title="Test Professor Oak 88", shortDescription="")
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


def test_retained_custom_query_and_value_intent_include_owned_card(retained):
    retained["raw"].update(title="Test Normal 001/A", shortDescription="")
    found = seed_history(
        retained["a"],
        {"demo": False, "pool": "singles", "intent": "value", "query": "  Pokemon Test Normal 001/A  "},
        rows=[retained["raw"]],
    )
    assert found["settings"]["query"] == "Pokemon Test Normal 001/A"
    assert found["coverage"]["queries_total"] == 1 and found["results"][0]["exact_hits"] == 0
    missing = seed_history(
        retained["a"],
        {"demo": False, "pool": "singles", "intent": "missing", "query": "Pokemon Test Normal 001/A"},
        rows=[retained["raw"]],
    )
    assert missing["results"] == [] and not retained["calls"]


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


def test_value_results_rank_discount_and_reveal_price_evidence_only_on_request(retained):
    first = deepcopy(retained["raw"])
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
    found = seed_history(
        retained["a"], {"demo": False, "pool": "singles", "intent": "value"}, rows=[first, second]
    )
    assert len(found["results"]) == 2
    best = found["results"][0]
    assert best["pricing"]["reference_total"] == "10.00"
    assert best["pricing"]["discount_percent"] == "70.00"
    assert "evidence" not in best["pricing"] and "SECRET" not in json.dumps(found)
    route = f"/api/hunts/{found['batch']}/1/reveal/{best['id']}/"
    shown = post(retained["a"], route, {}).json()
    assert shown["pricing"]["evidence"][0]["card_id"] == "a"


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
def test_retained_search_controls_remain_strict(fields):
    with pytest.raises(ValueError):
        parity.saved_settings(fields)


@pytest.mark.parametrize(
    "content_type", ["application/json", "text/plain", "application/x-www-form-urlencoded"]
)
def test_retired_search_returns_410_without_provider_access(retained, content_type):
    before = len(parity.hunt_rows(retained["actor"]))
    response = retained["a"].post(
        "/api/hunts/",
        '{"demo":false}',
        content_type=content_type,
        HTTP_X_CSRFTOKEN=retained["a"].cookies["dex_b1_csrf"].value,
    )
    assert response.status_code == 410 and response.json()["shopping_url"] == "/shopping/"
    assert len(parity.hunt_rows(retained["actor"])) == before and not retained["calls"]
