"""Frozen/account-scoped pack projection and ordinary authenticated page."""

import json
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.http import Http404
from test_b1 import env as env
from test_b2 import apply
from test_b2 import b2 as b2
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_broad_goals import REQ, goal, special, update
from test_migration import snapshot as snapshot
from test_sealed_catalog import e1 as e1
from test_sealed_catalog import package, publish
from test_sealed_expansion import expanded

from pokemon_hunter.beta import collection as inv
from pokemon_hunter.beta import packs, store
from pokemon_hunter.beta import sealed_catalog as cat


def ready(e1):
    publish(e1, package())
    publish(e1, expanded())
    apply(e1, "goal", REQ)
    return goal(e1)


def test_retained_union_identity_offers_and_read_only_ui(e1):
    g = ready(e1)
    before = inv.export_data(e1["actor"])
    observations = store.rows("SELECT * FROM sealed_observations")
    now = cat.instant("2026-10-07T00:00:00+00:00")
    with (
        patch("httpx.Client.send", side_effect=AssertionError("Zero network")),
        patch("pokemon_hunter.beta.ebay_hunts.search", side_effect=AssertionError("Zero provider")),
    ):
        p = packs.project(e1["actor"], g["id"], now=now)
        assert len(p["expansions"]) == 1
        ex = p["expansions"][0]
        assert ex["count"] == 151
        assert len({s["dex"] for s in ex["species"]}) == 151
        assert sum(len(s["printings"]) for s in ex["species"]) == 185
        assert len(ex["uncertain"]) == 161  # Pokémon only, excludes Trainer/Energy.
        scyther = packs.project(e1["actor"], g["id"], "123", now=now)["expansions"][0]
        assert scyther["count"] == 1
        assert all(p["species_id"] == "ndex:0123" for s in scyther["species"] for p in s["printings"])
        product = ex["products"][0]
        assert product["coverage"] is None and product["quantity"] is None and not product["verified"]
        assert not product["guaranteed_cards_known"] and product["guaranteed"] == []
        obs = product["offers"][0]["observations"]
        assert all(not o["fresh"] and o["per_pack"] is None and o["shipping"] == "Unknown" for o in obs)
        assert {o["checked_at"] for o in obs} == {json.loads(r["data"])["checked_at"] for r in observations}
        page = e1["a"].get("/packs/", {"goal": g["id"], "species": "123"})
        assert page.status_code == 200
        text = page.content.decode()
        for phrase in (
            "Packs to open",
            "#123 Scyther",
            "Official contents and quantities remain unverified",
            "Approximate original tool-read time",
            "Shipping: Unknown",
            "out-of-stock",
            g["version"],
        ):
            assert phrase in text
        assert "Buy now" not in text
    assert inv.export_data(e1["actor"]) == before
    assert store.rows("SELECT * FROM sealed_observations") == observations
    assert e1["b"].get("/packs/", {"goal": g["id"]}).status_code == 404
    with pytest.raises(Http404):
        packs.project(e1["member"], g["id"])
    # Current resolved ownership, deduplicated across copies.
    pid = next(i for i in g["definition"]["items"] if i["pokemon_dex"] == 123)["printing_ids"][0]
    for _ in range(2):
        apply(e1, "add", dict(printing_id=pid, duplicate_policy="allow"))
    assert packs.project(e1["actor"], g["id"])["expansions"][0]["count"] == 150
    assert not packs.project(e1["actor"], g["id"], "123")["expansions"]


def test_frozen_no_successor_substitution_and_unavailable_review(e1):
    publish(e1, package())
    apply(e1, "goal", REQ)
    first = goal(e1)
    publish(e1, expanded())
    apply(e1, "goal_edit", update(first))
    second = next(g for g in inv.goals(e1["actor"]) if g["id"] != first["id"])
    assert not packs.project(e1["actor"], first["id"])["expansions"]
    assert packs.project(e1["actor"], second["id"])["expansions"][0]["count"] == 151
    ref = second["definition"]["catalog_references"][0]
    inv.execute("UPDATE catalog_imports SET package_hash='unavailable' WHERE id=%s", [ref["import_id"]])
    p = packs.project(e1["actor"], second["id"])
    assert not p["expansions"] and p["limitations"]
    assert p["goal"]["version"] == second["version"]


def test_empty_unsupported_archive_and_local_filter(e1):
    special(e1)
    apply(e1, "goal", REQ)
    g = goal(e1)
    p = packs.project(e1["actor"], g["id"])
    assert not p["expansions"] and p["progress"]["unavailable"] == 148
    apply(e1, "goal", dict(name="Vintage", goal_kind="vintage"))
    legacy = next(g for g in inv.goals(e1["actor"]) if g["kind"] == "vintage")
    assert not packs.project(e1["actor"], legacy["id"])["supported"]


def test_archived_metadata_and_expansion_filter(e1):
    g = ready(e1)
    assert not packs.project(e1["actor"], g["id"], expansion="unindexed")["expansions"]
    inv.execute("UPDATE sealed_printings SET publication_state='archived'")
    p = packs.project(e1["actor"], g["id"])
    assert not p["expansions"] and p["unmapped_printings"] > 0


def test_membership_promo_separation_and_offer_boundary(e1):
    g = ready(e1)
    row = store.rows("SELECT * FROM sealed_memberships")[0]
    data = json.loads(row["data"])
    data["status"] = "promo"
    inv.execute("UPDATE sealed_memberships SET data=%s WHERE id=%s", [json.dumps(data), row["id"]])
    p = packs.project(e1["actor"], g["id"], "123")
    assert p["expansions"][0]["count"] == 0
    assert any(p["membership"] == "promo" for p in p["expansions"][0]["uncertain"])
    checked = cat.instant(
        json.loads(store.rows("SELECT * FROM sealed_observations")[0]["data"])["checked_at"]
    )
    observations = packs.project(e1["actor"], g["id"], now=checked + timedelta(hours=24))["expansions"][0][
        "products"
    ][0]["offers"][0]["observations"]
    original = next(o for o in observations if cat.instant(o["checked_at"]) == checked)
    assert original["fresh"]
    assert packs.money(None, "USD") == "Unknown"


def test_verified_mixed_and_guaranteed_fixtures_do_not_allocate_cost(e1):
    g = ready(e1)
    records = cat.records()
    product = next(iter(records["products"].values()))
    product.update(contents="mixed-known", total_packs=8, guaranteed_cards_known=True)
    pack = next(iter(records["packs"].values()))
    pack["quantity"] = 6
    records["packs"]["mixed"] = dict(pack, id="mixed", quantity=2, expansion_id="another-expansion")
    printing = next(iter(records["printings"]))
    records["guaranteed"]["fixture"] = dict(
        id="fixture", product_id=product["id"], printing_id=printing, quantity=1, sources=[]
    )
    with patch.object(cat, "records", return_value=records):
        p = packs.project(e1["actor"], g["id"])["expansions"][0]
        assert p["count"] == 151
        pr = p["products"][0]
        assert pr["quantity"] == 6 and pr["coverage"] == 151 and len(pr["guaranteed"]) == 1
        assert all(o["per_pack"] is None for offer in pr["offers"] for o in offer["observations"])
        records["packs"].pop("mixed")
        product.update(contents="complete", total_packs=6)
        pr = packs.project(e1["actor"], g["id"])["expansions"][0]["products"][0]
        assert any(o["per_pack"] == "USD 4.67" for offer in pr["offers"] for o in offer["observations"])
        records["offers"].clear()
        assert not packs.project(e1["actor"], g["id"])["expansions"][0]["products"][0]["offers"]
