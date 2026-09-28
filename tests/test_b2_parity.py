"""Synthetic parity, uncertain prices, safe edition operations and hostile spoiler checks."""

import importlib
import json
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from test_b1 import env as env
from test_b2 import apply, post, preview
from test_b2 import b2 as b2
from test_migration import snapshot as snapshot

from pokemon_hunter.beta import collection as service
from pokemon_hunter.beta import parity
from pokemon_hunter.collection import derive, totals


@pytest.fixture
def restored(b2):
    from django.conf import settings
    from django.urls import clear_url_caches

    from pokemon_hunter.beta import urls

    original_root = settings.ROOT
    settings.ROOT = b2["root"]
    settings.PARITY_ENABLED = True
    importlib.reload(urls)
    clear_url_caches()
    evidence = b2["root"] / "parity-evidence"
    evidence.mkdir()
    config = json.loads((Path(__file__).parents[1] / "config/hunt.json").read_text())
    (evidence / "hunt.json").write_text(json.dumps(config))
    raw = [
        {
            "itemId": "SECRET seller item identity",
            "title": "SECRET Normal Missing seller title",
            "shortDescription": "lot of 30 Pokemon cards",
            "price": {"value": "10", "currency": "USD"},
            "shippingOptions": [
                {"shippingCostType": "FIXED", "shippingCost": {"value": "0", "currency": "USD"}}
            ],
            "condition": "SECRET card condition",
            "buyingOptions": ["FIXED_PRICE"],
            "itemWebUrl": "https://www.ebay.com/SECRET",
            "image": {"imageUrl": "https://example.test/SECRET"},
            "_demo_cards": ["a", "c"],
        }
    ]
    (evidence / "demo_hunts.json").write_text(json.dumps(raw))
    (evidence / "raw_values.json").write_text("{}")
    rows = []
    for key in ["a", "b", "c"]:
        for edition in ["standard", "first_edition"]:
            for grade in ["raw", "7", "8", "9", "10"]:
                rows.append(
                    dict(
                        card_id=key,
                        grade=grade,
                        edition=edition,
                        grader="PSA",
                        currency="USD",
                        source_url="https://example.test/guide",
                        variant_verified=True,
                        as_of=date.today().isoformat(),
                        value="20" if edition == "first_edition" else "10",
                        estimated=grade in ("7", "8"),
                        basis="Geometric interpolation" if grade in ("7", "8") else "Guide",
                    )
                )
    (evidence / "market_values.json").write_text(json.dumps(rows))
    yield b2
    settings.ROOT = original_root
    settings.PARITY_ENABLED = False
    importlib.reload(urls)
    clear_url_caches()


def test_projection_matches_same_snapshot_and_scope(restored, snapshot):
    a, b = restored["a"], restored["b"]
    projected = a.get("/api/parity/").json()
    original = json.loads((snapshot / "config/pokedex_251.json").read_text())
    original["pokedex"] = {
        str(n): dict(dex_number=n, name=f"Species {n}", generation=1 if n <= 151 else 2)
        for n in range(1, 252)
    }
    original = derive(original)
    assert {k: projected["totals"][k] for k in totals(original)} == totals(original)
    assert all(projected["cards"][k]["owned"] == v["owned"] for k, v in original["cards"].items())
    assert b.get("/api/parity/?user_id=owner").json()["totals"]["physical_copies"] == 0
    assert projected["pokedex"]["2"]["dex_owned"] is False  # Named card outside Vintage
    assert projected["pokedex"]["152"]["eligible_cards"] == ["c"]
    assert projected["valuation"]["conditional"]["raw"]["subtotal"] == "30.00"
    assert projected["valuation"]["confirmed"]["raw"]["subtotal"] is None
    assert projected["valuation"]["conditional"]["7"]["estimated"] == 2


def test_edition_duplicate_undo_and_export_roundtrip(restored):
    a, b = restored["a"], restored["b"]
    copy = next(c for c in service.copies(restored["actor"]) if c["first_edition_selected"])
    baseline = a.get("/api/parity/").json()
    op = apply(restored, "edition", dict(id=copy["id"], revision=copy["revision"], selection="unresolved"))
    current = service.one(restored["actor"], "copy", copy["id"])
    assert not current["first_edition_selected"]
    assert {"edition", "finish", "variant"} <= set(
        json.loads(current["provisional_identity"])["unresolved_fields"]
    )
    changed = a.get("/api/parity/").json()
    assert changed["totals"] == baseline["totals"]
    assert changed["valuation"]["conditional"]["raw"]["subtotal"] == "20.00"
    assert changed["valuation"]["confirmed"]["raw"]["total"] is None
    assert (
        preview(restored, "edition", dict(id=copy["id"], revision=0, selection="first_edition")).status_code
        == 409
    )
    exported = a.get("/api/export/").json()
    apply(restored, "import", dict(text=json.dumps(exported), format="json", duplicate_policy="allow"), b)
    imported = service.copies(restored["member"])
    match = next(c for c in imported if c["source_copy_id"] == copy["id"])
    assert (
        match["first_edition_selected"] == 0
        and match["provisional_identity"] == current["provisional_identity"]
    )
    assert post(a, f"/api/operations/{op['id']}/undo/", {}).status_code == 200
    assert a.get("/api/parity/").json()["valuation"] == baseline["valuation"]
    added = apply(
        restored, "add", dict(printing_id=copy["printing_id"], attributes={}, duplicate_policy="allow")
    )
    duplicate = a.get("/api/parity/").json()
    assert duplicate["totals"]["physical_copies"] == 3 and duplicate["totals"]["exact_cards"] == 2
    assert duplicate["valuation"]["conditional"]["raw"]["subtotal"] == "50.00"
    assert post(a, f"/api/operations/{added['id']}/undo/", {}).status_code == 200
    assert a.get("/api/parity/").json()["totals"] == baseline["totals"]


def test_value_freshness_unknowns_and_no_variant_fallback(restored):
    path = restored["root"] / "parity-evidence/market_values.json"
    rows = json.loads(path.read_text())
    for r in rows:
        if r["edition"] == "first_edition":
            r["as_of"] = (date.today() - timedelta(days=31)).isoformat()
    path.write_text(json.dumps(rows))
    result = restored["a"].get("/api/parity/").json()["valuation"]
    assert result["conditional"]["raw"]["priced"] == 1
    assert result["conditional"]["raw"]["total"] is None
    assert result["conditional"]["raw"]["subtotal"] == "10.00"
    assert result["purchase_subtotals"] == {"USD": "12.30"}
    path.write_text("[]")
    assert restored["a"].get("/api/parity/").json()["valuation"]["conditional"]["raw"]["subtotal"] is None


def test_hunts_reveal_reopen_rescore_and_cross_account(restored):
    a, b = restored["a"], restored["b"]
    with patch("pokemon_hunter.ebay.EbayClient", side_effect=AssertionError("NO LIVE CALL")):
        assert post(a, "/api/hunts/", {"demo": False}).status_code == 400
        found = post(a, "/api/hunts/", dict(pool="known_lots", focus="all", budget="100", demo=True)).json()
    route = f"/api/hunts/{found['batch']}/{found['id']}/"
    assert len(found["results"]) == 1
    result = found["results"][0]
    assert result["dex_hits"] == 1
    assert "SECRET" not in json.dumps(found)
    assert not {"title", "url", "cards", "components", "condition", "image"} & set(result)
    reveal = route + "reveal/" + result["id"] + "/"
    assert a.get(reveal).status_code == 405
    shown = post(a, reveal, {}).json()
    assert "SECRET" in shown["title"] and shown["url"] is None
    assert "SECRET" not in a.get(route).content.decode()
    assert "SECRET" not in a.get("/api/hunts/").content.decode()
    assert b.get(route).status_code == 404
    assert post(b, reveal, {}).status_code == 404
    assert b.get("/api/hunts/").json()["hunts"] == []
    c = next(p for p in restored["catalog"] if json.loads(p["provenance"])["legacy_id"] == "c")
    added = apply(restored, "add", dict(printing_id=c["id"], attributes={}, duplicate_policy="allow"))
    assert a.get(route).json()["results"][0]["dex_hits"] == 0
    assert a.get("/api/parity/").json()["totals"]["johto"] == 1
    created = added["changes"][0]["after"]
    removed = apply(restored, "remove", {"id": created["id"], "revision": 0})
    assert a.get(route).json()["results"][0]["dex_hits"] == 1
    assert a.get("/api/parity/").json()["totals"]["johto"] == 0
    assert post(a, f"/api/operations/{removed['id']}/undo/", {}).status_code == 200
    assert a.get(route).json()["results"][0]["dex_hits"] == 0
    # Removal/restore changes revision, so older addition undo correctly conflicts.
    assert post(a, f"/api/operations/{added['id']}/undo/", {}).status_code == 409
    current = service.one(restored["actor"], "copy", created["id"])
    apply(restored, "remove", {"id": current["id"], "revision": current["revision"]})
    assert a.get(route).json()["results"][0]["dex_hits"] == 1
    for path in [
        "/overview/",
        "/pokedex/",
        "/cards/",
        "/hunt/",
        "/missing/",
        "/finds/",
        "/api/parity/",
        "/api/hunts/",
        route,
    ]:
        assert restored["client"]().get(path).status_code == 302
    anon = restored["client"]()
    anon.get("/login/")
    assert post(anon, reveal, {}).status_code == 302
    assert a.post(reveal, "{}", content_type="application/json").status_code == 403
    # Both directions: an owner role never bypasses the member's private boundary.
    other = post(b, "/api/hunts/", dict(pool="known_lots", focus="all", budget="100", demo=True)).json()
    other_route = f"/api/hunts/{other['batch']}/{other['id']}/"
    assert a.get(other_route).status_code == 404
    assert post(a, other_route + "reveal/" + other["results"][0]["id"] + "/", {}).status_code == 404


@pytest.mark.parametrize(
    "pool,focus,budget",
    [
        ("known_lots", "all", "100"),
        ("known_lots", "bulk", "100"),
        ("known_lots", "kanto", "100"),
        ("known_lots", "johto", "100"),
        ("known_lots", "rares", "100"),
        ("known_lots", "all", "1"),
        ("mystery", "all", "100"),
        ("singles", "all", "100"),
    ],
)
def test_sample_filters_and_query_plan(restored, pool, focus, budget):
    result = post(restored["a"], "/api/hunts/", dict(pool=pool, focus=focus, budget=budget, demo=True))
    assert result.status_code == 200, result.content
    for row in result.json()["results"]:
        assert row["pool"] == pool and float(row["delivered"]) <= float(budget)


def test_saved_live_replay_has_no_provider_calls(restored):
    from pokemon_hunter.migration import encode

    a = restored["a"]
    sample = post(a, "/api/hunts/", {"pool": "known_lots", "demo": True}).json()
    raw = parity.evidence("demo_hunts.json", [])
    raw[0]["title"] = "Test Missing 3/100 lot of 30 Pokemon cards"
    raw[0]["condition"] = "Lightly Played"
    service.execute(
        "UPDATE saved_hunts SET demo=0,raw=%s,coverage=%s WHERE batch_id=%s",
        [
            encode(raw),
            encode({"note": "SECRET coverage", "warnings": ["SECRET"], "queries_run": 2}),
            sample["batch"],
        ],
    )
    route = f"/api/hunts/{sample['batch']}/1/"
    with patch("pokemon_hunter.ebay.EbayClient", side_effect=AssertionError("NO LIVE CALL")):
        result = a.get(route).json()
    assert result["demo"] is False
    assert result["results"][0]["dex_hits"] == 1
    assert "SECRET" not in json.dumps(result)
    revealed = post(a, route + "reveal/" + result["results"][0]["id"] + "/", {}).json()
    assert revealed["url"] == "https://www.ebay.com/SECRET"
    assert revealed["cards"] == ["c"]
    assert "SECRET" not in a.get(route).content.decode()


def test_edition_ownership_and_invalid_selection(restored):
    copy = service.copies(restored["actor"])[0]
    request = dict(id=copy["id"], revision=copy["revision"], selection="first_edition")
    assert preview(restored, "edition", request, restored["b"]).status_code == 404
    assert preview(restored, "edition", {**request, "selection": "unlimited"}).status_code == 400
    op = apply(restored, "edition", request)
    assert post(restored["b"], f"/api/operations/{op['id']}/undo/", {}).status_code == 404
    assert post(restored["b"], f"/api/operations/{op['id']}/confirm/", {}).status_code == 404
