"""E1 service qualification on synthetic private state; retained real package is input data."""

import copy
import json
import sqlite3
from datetime import timedelta
from pathlib import Path

import pytest
from django.core.exceptions import PermissionDenied
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_migration import snapshot as snapshot

from pokemon_hunter.beta import collection as inv
from pokemon_hunter.beta import sealed_catalog as cat
from pokemon_hunter.beta import store

DATA = Path(__file__).parents[1] / "config/sealed/2026-10-04/package.json"


def package():
    return json.loads(DATA.read_text())


@pytest.fixture
def e1(b4):
    cat.initialize()
    return b4


def publish(e1, p=None):
    op = cat.preview(e1["actor"], p or package())
    cat.transition(e1["actor"], op["id"], "verify")
    return cat.transition(e1["actor"], op["id"], "publish")


def test_real_package_and_offline_identity_validation():
    p = cat.validate(package())
    assert len(p["species"]) == 1025
    assert p["species"][-1]["name"] == "Pecharunt"
    assert p["printings"][0]["species_id"] == "ndex:0123"
    assert p["printings"][0]["language"] == "en"
    assert len(p["coverage"][0]["intended_expansions"]) == 205
    assert sum(r["medium"] == "digital" for r in p["expansions"]) == 15
    assert p["packs"][0]["quantity"] is None
    assert p["observations"][0]["stock"] == "unknown"


@pytest.mark.parametrize(
    "mutation,match",
    [
        (lambda p: p["species"][0].update(id="ndex:0002"), "Repeated identity"),
        (lambda p: p["species"][-1].update(sources=["sets"]), "official evidence"),
        (lambda p: p["printings"][0].update(species_id="ndex:9999"), "Broken reference"),
        (lambda p: p["printings"][0].update(language="fr"), "language/category"),
        (lambda p: p["printings"][0].update(category="trainer"), "language/category"),
        (lambda p: p["memberships"][0].update(sources=["scyther"]), "official card"),
        (lambda p: p["memberships"][0].update(expansion_id="tcgdex:en:base1"), "expansion mismatch"),
        (lambda p: p["packs"][0].update(quantity=6), "official contents"),
        (lambda p: p["products"][0].update(total_packs=6), "official contents"),
        (lambda p: p["offers"][0].update(seller_kind="direct"), "market/seller"),
        (lambda p: p["offers"][0].update(market="UK"), "market/seller"),
        (lambda p: p["observations"][0].update(checked_at="2026-10-04T12:00:00"), "timezone-aware"),
        (lambda p: p["observations"][0].update(checked_at="2026-10-05T12:00:00+00:00"), "cannot follow"),
        (lambda p: p["mappings"][0].update(internal_id="ndex:9999"), "Broken reference"),
        (lambda p: p["mappings"][1025].update(language="fr"), "Mapping language"),
        (lambda p: p["products"][0].update(contents="complete"), "Known contents"),
        (lambda p: p["coverage"][0]["intended_expansions"].append("tcgdex:en:A1"), "universe"),
    ],
)
def test_unsupported_assumptions_and_broken_references(mutation, match):
    p = package()
    mutation(p)
    with pytest.raises(ValueError, match=match):
        cat.validate(p)


def test_unknown_and_malformed_values():
    for kind, field, value in [
        ("packs", "quantity", 0),
        ("packs", "quantity", True),
        ("observations", "price_minor", -1),
        ("observations", "stock", "sold-out"),
        ("sources", "sha256", "bad"),
    ]:
        p = package()
        p[kind][0][field] = value
        with pytest.raises(ValueError):
            cat.validate(p)
    p = package()
    p["private_copies"] = []
    with pytest.raises(ValueError):
        cat.validate(p)


def test_idempotency_publication_preservation_and_copied_recovery(b4, tmp_path):
    # Rehearse feature migration and native SQLite backup/restore on copied state.
    from django.db import connection
    from test_b2 import apply

    e1 = b4
    apply(e1, "goal", {"name": "Frozen vintage", "goal_kind": "vintage"})
    apply(e1, "goal", {"name": "Private member vintage", "goal_kind": "vintage"}, e1["b"])
    copies = store.rows("SELECT * FROM owned_copies ORDER BY id")
    goals = store.rows("SELECT * FROM collection_goals ORDER BY id")
    printings = store.rows("SELECT * FROM printings ORDER BY id")
    exports = [inv.export_data(e1[a]) for a in ("actor", "member")]
    with sqlite3.connect(e1["root"] / "inventory.db") as original:
        with sqlite3.connect(tmp_path / "before.copied.sqlite3") as backup:
            original.backup(backup)
            before = {
                t: backup.execute(f"SELECT * FROM {t} ORDER BY id").fetchall()
                for t in ("owned_copies", "collection_goals", "printings")
            }
            cat.initialize(backup)
            cat.initialize(backup)
            assert all(
                backup.execute(f"SELECT * FROM {t} ORDER BY id").fetchall() == rows
                for t, rows in before.items()
            )
    cat.initialize()
    op = publish(e1)
    assert cat.preview(e1["actor"], package())["id"] == op["id"]
    assert cat.transition(e1["actor"], op["id"], "publish")["id"] == op["id"]
    report = cat.report(e1["actor"], cat.instant(package()["observations"][0]["checked_at"]))
    assert report["counts"]["species"] == 1025 and report["counts"]["printings"] == 1
    assert report["coverage"][0]["sets_with_printings"] == 1
    assert len(report["coverage"][0]["missing_sets"]) == 204
    assert report["observations"][0]["fresh"] and not report["observations"][0]["buy_now"]
    assert store.rows("SELECT * FROM owned_copies ORDER BY id") == copies
    assert store.rows("SELECT * FROM collection_goals ORDER BY id") == goals
    assert store.rows("SELECT * FROM printings ORDER BY id") == printings
    assert [inv.export_data(e1[a]) for a in ("actor", "member")] == exports
    cat.transition(e1["actor"], op["id"], "rollback")
    assert cat.report(e1["actor"])["counts"]["species"] == 0
    assert [inv.export_data(e1[a]) for a in ("actor", "member")] == exports
    connection.close()
    with (
        sqlite3.connect(tmp_path / "before.copied.sqlite3") as backup,
        sqlite3.connect(tmp_path / "restored.sqlite3") as restored,
    ):
        backup.backup(restored)
        assert all(
            restored.execute(f"SELECT * FROM {t} ORDER BY id").fetchall() == rows
            for t, rows in before.items()
        )


def delta(p, version="observation-v2"):
    return {
        **{k: [] for k in cat.KINDS},
        "mappings": [],
        "schema_version": "dex-sealed-v1",
        "provider": p["provider"],
        "version": version,
    }


def test_changed_observations_retain_dates_sources_and_conflicts(e1):
    p = package()
    op = publish(e1, p)
    q = delta(p)
    src = copy.deepcopy(next(s for s in p["sources"] if s["id"] == "target"))
    source_time = cat.instant(src["retrieved_at"]) + timedelta(hours=1)
    obs = copy.deepcopy(p["observations"][0])
    obs.update(
        id="target:88897904:second-check",
        checked_at=source_time.isoformat(),
        sources=["target-check-2"],
        stock="out-of-stock",
        price_minor=2799,
    )
    src.update(
        id="target-check-2",
        retrieved_at=source_time.isoformat(),
        sha256="1" * 64,
        subjects=[obs["id"]],
        note="Synthetic observation for behavior test; not real retailer evidence",
    )
    q.update(sources=[src], observations=[obs])
    newest = publish(e1, q)
    observed = cat.report(e1["actor"], source_time)["observations"]
    assert len(observed) == 2
    assert observed[0]["checked_at"] == p["observations"][0]["checked_at"]
    assert observed[1]["price_minor"] == 2799
    assert cat.preview(e1["actor"], q)["id"] == newest["id"]
    with pytest.raises(inv.Conflict):
        cat.transition(e1["actor"], op["id"], "rollback")
    altered = copy.deepcopy(q)
    altered["observations"][0]["price_minor"] = 2800
    with pytest.raises(ValueError, match="Immutable record conflict"):
        cat.preview(e1["actor"], altered)
    other = copy.deepcopy(q)
    other["observations"][0].update(id="other-observation")
    other["sources"][0]["subjects"].append("other-observation")
    with pytest.raises(ValueError, match="Immutable record conflict|Conflicting dated observation"):
        cat.preview(e1["actor"], other)
    mapping = delta(p, "mapping-conflict")
    mapping["mappings"] = [{**p["mappings"][0], "internal_id": "ndex:0002"}]
    with pytest.raises(ValueError, match="mapping conflict"):
        cat.preview(e1["actor"], mapping)
    changed_version = delta(p)
    with pytest.raises(ValueError, match="Source version"):
        cat.preview(e1["actor"], changed_version)
    cat.transition(e1["actor"], newest["id"], "rollback")
    assert len(cat.report(e1["actor"])["observations"]) == 1
    # Archived source IDs and observations also cannot be repurposed.
    altered["version"] = "later"
    with pytest.raises(ValueError, match="Archived identity"):
        cat.preview(e1["actor"], altered)
    cat.transition(e1["actor"], op["id"], "rollback")
    assert cat.report(e1["actor"])["counts"]["species"] == 0


def test_owner_authorization_and_preview_publication_order(e1):
    for operation in [lambda: cat.preview(e1["member"], package()), lambda: cat.report(e1["member"])]:
        with pytest.raises(PermissionDenied):
            operation()
    op = cat.preview(e1["actor"], package())
    with pytest.raises(ValueError, match="in order"):
        cat.transition(e1["actor"], op["id"], "publish")
    with pytest.raises(PermissionDenied):
        cat.get(e1["member"], op["id"])
    second = cat.preview(e1["actor"], {**package(), "version": "same-data-v2"})
    cat.transition(e1["actor"], op["id"], "verify")
    cat.transition(e1["actor"], op["id"], "publish")
    with pytest.raises(inv.Conflict, match="changed"):
        cat.transition(e1["actor"], second["id"], "verify")


def test_freshness_never_uses_import_or_report_time(e1):
    p = package()
    publish(e1, p)
    checked = cat.instant(p["observations"][0]["checked_at"])
    assert cat.report(e1["actor"], checked + timedelta(hours=24))["observations"][0]["fresh"]
    for now in (checked - timedelta(seconds=1), checked + timedelta(hours=24, seconds=1)):
        row = cat.report(e1["actor"], now)["observations"][0]
        assert row["availability"] == "stale" and row["checked_at"] == p["observations"][0]["checked_at"]


def test_promo_deck_guaranteed_and_mixed_contents_are_separate():
    p = package()
    # Clearly synthetic official-content source for schema behavior only.
    content = copy.deepcopy(p["sources"][0])
    product = p["products"][0]
    pack = p["packs"][0]
    content.update(
        id="fixture-content",
        authority="official-product",
        market="US",
        subjects=[product["id"], pack["id"], "fixture-guaranteed", "fixture-second-pack"],
        supports=["product-contents"],
        note="Synthetic test evidence",
    )
    p["sources"].append(content)
    product.update(
        sources=["fixture-content"], contents="mixed-known", total_packs=8, guaranteed_cards_known=True
    )
    pack.update(sources=["fixture-content"], quantity=6)
    p["packs"].append({**pack, "id": "fixture-second-pack", "expansion_id": "tcgdex:en:base1", "quantity": 2})
    p["guaranteed"].append(
        dict(
            id="fixture-guaranteed",
            sources=["fixture-content"],
            product_id=product["id"],
            printing_id=p["printings"][0]["id"],
            quantity=1,
        )
    )
    for status in ("promo", "deck-only", "unknown", "booster"):
        p["memberships"][0]["status"] = status
        result = cat.validate(p)
        assert result["guaranteed"][0]["quantity"] == 1
        assert result["memberships"][0]["status"] == status
    p["packs"][1]["quantity"] = None
    with pytest.raises(ValueError, match="Known contents"):
        cat.validate(p)
    p["packs"][1]["quantity"] = 2
    p["products"][0]["total_packs"] = 9
    with pytest.raises(ValueError, match="Known contents"):
        cat.validate(p)


def test_latest_observation_prevents_historical_buy_now(e1):
    p = package()
    p["offers"][0].update(seller="Synthetic Target", seller_kind="direct")
    p["sources"][-1]["note"] = "Synthetic stock/seller/price override for behavior test only"
    p["observations"][0].update(stock="in-stock", price_minor=2799)
    publish(e1, p)
    checked = cat.instant(p["observations"][0]["checked_at"])
    assert cat.report(e1["actor"], checked)["observations"][0]["buy_now"]
    q = delta(p, "latest-check")
    source = copy.deepcopy(p["sources"][-1])
    observation = copy.deepcopy(p["observations"][0])
    observation.update(
        id="fixture-latest",
        checked_at=(checked + timedelta(hours=1)).isoformat(),
        stock="out-of-stock",
        sources=["fixture-latest-source"],
    )
    source.update(
        id="fixture-latest-source",
        retrieved_at=observation["checked_at"],
        subjects=[observation["id"]],
        sha256="2" * 64,
    )
    q.update(sources=[source], observations=[observation])
    publish(e1, q)
    rows = cat.report(e1["actor"], checked + timedelta(hours=2))["observations"]
    assert all(not row["buy_now"] for row in rows)
    assert sum(row["latest"] for row in rows) == 1
