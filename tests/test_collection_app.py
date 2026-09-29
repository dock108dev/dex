import json
import shutil
from pathlib import Path

import pytest
from conftest import synthetic_collection, synthetic_project
from fastapi.testclient import TestClient

from pokemon_hunter.app import create_app
from pokemon_hunter.collection import derive, read, totals, update_card
from pokemon_hunter.hunt import analyze, exact_text_matches, public_listing, query_plan

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def collection():
    return synthetic_collection()


@pytest.fixture
def local(tmp_path):
    synthetic_project(tmp_path)
    shutil.copytree(ROOT / "web", tmp_path / "web")
    return tmp_path


def test_confirmed_import_and_catalog(collection):
    assert totals(collection) == {
        "kanto": 2,
        "johto": 0,
        "total": 2,
        "exact_cards": 2,
        "unavailable_species": 0,
    }
    assert len(collection["pokedex"]) == 251
    assert len(collection["cards"]) == 859
    assert collection["metadata"]["ownership_import_complete"]
    assert collection["metadata"]["import_issues"] == []
    assert collection["cards"]["team_rocket-50"]["dex_eligible"]
    assert not collection["cards"]["team_rocket-4"]["dex_eligible"]
    assert collection["cards"]["neo_discovery-49"]["dex_eligible"]
    assert not collection["cards"]["wizards_black_star_promos-19"]["dex_eligible"]
    assert len(collection["pokedex"]["123"]["eligible_cards"]) == 6
    assert "neo_revelation-4" in collection["pokedex"]["169"]["eligible_cards"]
    assert all(s["eligible_cards"] for s in collection["pokedex"].values())
    assert not collection["cards"]["neo_destiny-2"]["dex_eligible"]
    assert collection["cards"]["neo_destiny-80"]["dex_eligible"]
    assert all(
        not c["owned"]
        for c in collection["cards"].values()
        if c["set_id"] in ("neo_revelation", "neo_destiny")
    )


def test_quantities_deduplicate_species_and_persist(local):
    path = local / "config/pokedex_251.json"
    update_card(path, "base_set-15", True)
    assert totals(read(path))["total"] == 3
    update_card(path, "base_set_2-18", True)
    assert totals(read(path))["total"] == 3
    update_card(path, "base_set-15", False)
    assert totals(read(path))["total"] == 3
    update_card(path, "base_set_2-18", False)
    assert totals(read(path))["total"] == 2
    for value in (-1, 1, 1.5, 10000):
        with pytest.raises(ValueError):
            update_card(path, "base_set-15", value)


def test_excluded_cards_cannot_fill_slot(collection):
    for c in collection["cards"].values():
        c["owned"] = not c["dex_eligible"]
    assert totals(derive(collection))["total"] == 0


def test_cross_set_missing_query_plan(collection):
    config = json.loads((ROOT / "config/hunt.json").read_text())
    queries = query_plan(collection, config, "singles", "kanto")
    assert any("Neo Discovery Scyther 46" in q for q in queries)
    assert not any("Charmander" in q for q in queries)
    assert not any("Dark" in q for q in queries)


def test_text_matching_requires_exact_printing(collection):
    assert exact_text_matches("Neo Discovery Scyther 46/75", collection) == ["neo_discovery-46"]
    assert exact_text_matches("Team Rocket Dark Charizard 4", collection) == []
    assert exact_text_matches("Base Set 2 Charizard 4", collection) == ["base_set_2-4"]
    assert exact_text_matches("Team Rocket Charmander 50", collection) == ["team_rocket-50"]
    assert exact_text_matches("Base Set Charizard", collection) == []


def test_mystery_unknown_and_spoiler_projection(collection):
    config = json.loads((ROOT / "config/hunt.json").read_text())
    raw = json.loads((ROOT / "config/demo_hunts.json").read_text())[0]
    row = analyze(raw, collection, config, {}, demo=True)
    safe = public_listing(row)
    for key in ("title", "url", "cards", "components"):
        assert key not in safe
    assert "Scyther" not in json.dumps(safe)
    assert public_listing(row, True)["cards"]
    raw["title"] += " mystery"
    row = analyze(raw, collection, config, {}, demo=True)
    assert row["cards"] == [] and row["score"] is None
    assert row["raw_value"] is None and row["max_bid"] is None


def test_raw_value_and_auction_bid_without_psa(collection):
    config = json.loads((ROOT / "config/hunt.json").read_text())
    raw = {
        "itemId": "test",
        "title": "Base Set Venusaur 15 — 1 Pokemon card",
        "currentBidPrice": {"value": "4", "currency": "USD"},
        "shippingOptions": [{"shippingCost": {"value": "2.50", "currency": "USD"}}],
        "buyingOptions": ["AUCTION"],
        "itemEndDate": "2099-01-01T00:00:00Z",
        "condition": "Lightly Played",
    }
    values = {
        "base_set-15": {
            "LP": {"value": "10", "source": "test fixture", "as_of": "2026-09-27"},
            "PSA10": {"value": "10000"},
        }
    }
    row = analyze(raw, collection, config, values)
    assert row["raw_value"] == "10" and row["max_bid"] == "7.50"
    raw["condition"] = "Used"
    assert analyze(raw, collection, config, values)["max_bid"] is None
    raw.pop("shippingOptions")
    assert analyze(raw, collection, config, values)["delivered"] is None


def test_app_sample_never_calls_ebay_and_reveal_is_explicit(local, monkeypatch):
    def forbidden(*a, **kw):
        pytest.fail("Sample mode called eBay")

    monkeypatch.setattr("pokemon_hunter.app.discover", forbidden)
    with TestClient(create_app(local)) as client:
        assert client.get("/").status_code == 200
        assert client.get("/api/collection").json()["totals"]["total"] == 2
        response = client.post("/api/hunts", json={"demo": True, "pool": "known_lots", "budget": "150"})
        assert response.status_code == 200
        body = response.json()
        assert len(body["results"]) == 2
        assert "Scyther" not in response.text
        assert all("title" not in r and "cards" not in r for r in body["results"])
        listing = body["results"][0]
        result = client.post(f"/api/hunts/{body['hunt_id']}/reveal/{listing['id']}")
        assert result.json()["cards"]
        assert len(client.get("/api/hunts").json()) == 1
        assert "title" not in client.get(f"/api/hunts/{body['hunt_id']}").json()["results"][0]
        assert client.post("/api/hunts", json={"budget": 1}).json()["results"] == []
        assert (
            client.post("/api/hunts", json={"pool": "singles"}).json()["results"][0]["label"]
            == "Dex opportunity"
        )
        assert client.post("/api/hunts", json={"pool": "mystery"}).json()["results"][0]["score"] is None
        assert client.put("/api/cards/base_set-15", json={"owned": True}).json()["totals"]["total"] == 3
        assert client.put("/api/cards/base_set-15", json={"owned": -1}).status_code == 422
        assert client.put("/api/cards/base_set-15", json={"owned": 1}).status_code == 422
        assert (
            client.put(
                "/api/cards/base_set-15", json={"owned": False}, headers={"Origin": "https://example.com"}
            ).status_code
            == 403
        )
        assert client.get("/api/export").json()["cards"]["base_set-15"]["owned"] is True
    # Restart creates no second collection and preserves history.
    with TestClient(create_app(local)) as client:
        assert client.get("/api/collection").json()["totals"]["total"] == 3
        assert len(client.get("/api/hunts").json()) == 4


def test_live_warning_cannot_leak_single_identity(local, monkeypatch):
    class FakeEbay:
        def __init__(self, settings):
            self.warnings = ["Search page cap reached: FIXED_PRICE / Base Set Venusaur 15"]

        def close(self):
            pass

    def discover(client, queries):
        assert queries and len(queries) <= 8
        return [
            {
                "itemId": "live-test",
                "title": "Base Set Venusaur 15 1 Pokemon card",
                "price": {"value": "5", "currency": "USD"},
                "buyingOptions": ["FIXED_PRICE"],
                "shippingOptions": [{"shippingCost": {"value": "1", "currency": "USD"}}],
            }
        ]

    monkeypatch.setattr("pokemon_hunter.app.EbayClient", FakeEbay)
    monkeypatch.setattr("pokemon_hunter.app.discover", discover)
    with TestClient(create_app(local)) as client:
        res = client.post("/api/hunts", json={"pool": "singles", "demo": False})
        assert res.status_code == 200
        assert "Venusaur" not in res.text
        assert res.json()["coverage"]["warnings"]
        assert res.json()["coverage"]["next_offset"] == 8
        assert res.json()["results"][0]["dex_hits"] == 1


def test_expanded_neo_searches(collection):
    config = json.loads((ROOT / "config/hunt.json").read_text())
    singles = query_plan(collection, config, "singles", "johto")
    assert any("Neo Revelation Crobat 4" in q for q in singles)
    assert any("Neo Destiny Remoraid 80" in q for q in singles)
    for focus in ("all", "johto"):
        queries = query_plan(collection, config, "known_lots", focus)
        assert "pokemon neo revelation lot" in queries
        assert "pokemon neo destiny lot" in queries


def test_owned_and_first_edition(local):
    path = local / "config/pokedex_251.json"
    update_card(path, "base_set-15", True, True)
    row = read(path)["cards"]["base_set-15"]
    assert row["owned"] and row["first_edition"] and "quantity" not in row
    update_card(path, "base_set-15", False)
    assert not read(path)["cards"]["base_set-15"]["first_edition"]
    with pytest.raises(ValueError):
        update_card(path, "base_set-15", False, True)
    with pytest.raises(ValueError):
        update_card(path, "base_set_2-18", True, True)


def test_estimates_match_edition_and_date(local):
    from datetime import date

    from pokemon_hunter.valuation import valuation

    path = local / "config/market_values.json"
    record = dict(
        card_id="base_set-2",
        grade="7",
        edition="standard",
        grader="Guide",
        currency="USD",
        value="123.45",
        as_of="2026-09-27",
        source_url="https://example.com/guide",
        variant_verified=True,
    )
    path.write_text(
        json.dumps(
            [
                record,
                {**record, "grade": "8", "edition": "first_edition", "value": "999"},
                {**record, "grade": "9", "as_of": "2025-01-01"},
            ]
        )
    )
    data = read(local / "config/pokedex_251.json")
    v = valuation(data, path, date(2026, 9, 27))
    assert v["scenarios"]["7"]["subtotal"] == "123.45"
    assert v["scenarios"]["7"]["total"] is None
    assert v["scenarios"]["8"]["priced"] == 0
    assert v["scenarios"]["9"]["priced"] == 0
    data["cards"]["base_set-2"]["first_edition"] = True
    v = valuation(data, path, date(2026, 9, 27))
    assert v["scenarios"]["7"]["priced"] == 0
    assert v["scenarios"]["8"]["subtotal"] == "999.00"


def test_rough_estimate_is_labeled_and_counted(local):
    from datetime import date

    from pokemon_hunter.valuation import valuation

    root = local
    data = read(root / "config/pokedex_251.json")
    path = root / "config/market_values.json"
    path.write_text(
        json.dumps(
            [
                dict(
                    card_id="base_set-2",
                    edition="standard",
                    grade="7",
                    value="20.00",
                    grader="Guide",
                    currency="USD",
                    source_url="https://example.com/guide",
                    as_of="2026-09-27",
                    variant_verified=True,
                    estimated=True,
                    basis="Interpolated",
                )
            ]
        )
    )
    result = valuation(data, path, date(2026, 9, 27))
    assert result["cards"]["base_set-2"]["7"]["estimated"] is True
    assert result["scenarios"]["7"]["estimated"] == 1
    assert result["scenarios"]["7"]["subtotal"] == "20.00"
    assert result["scenarios"]["7"]["total"] is None


def test_legacy_browser_headers(local):
    from pokemon_hunter.security import BROWSER_HEADERS

    client = TestClient(create_app(local))
    for response in (client.get("/"), client.get("/", headers={"Host": "evil.example"})):
        for key, value in BROWSER_HEADERS.items():
            assert response.headers[key] == value


def test_hunt_routes_use_shared_projection_and_schema(local):
    from unittest.mock import patch

    from pokemon_hunter import hunt

    client = TestClient(create_app(local))
    assert client.post("/api/hunts", json={"unsupported": True}).status_code == 422
    with patch.object(hunt, "project_results", wraps=hunt.project_results) as shared:
        response = client.post("/api/hunts", json={"demo": True, "budget": "10000"})
        assert response.status_code == 200
        saved = response.json()
        assert saved["results"]
        route = f"/api/hunts/{saved['hunt_id']}"
        assert client.get(route).status_code == 200
        assert client.post(route + "/reveal/" + saved["results"][0]["id"]).status_code == 200
        assert shared.call_count == 3
