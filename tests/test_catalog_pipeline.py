"""Target-specific batch atomicity, checkpoint recovery and preserved identities."""

import copy
import uuid

import pytest
from django.core.exceptions import PermissionDenied
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_collection_goals import create, seed
from test_migration import snapshot as snapshot
from test_sealed_catalog import e1 as e1

from pokemon_hunter.beta import catalog_pipeline as pipeline
from pokemon_hunter.beta import collection as inv
from pokemon_hunter.beta import collection_goals, lookup, pack_research, store


def synthetic(code="modern-test", numbers=(134, 196, 252, None)):
    cards = [
        dict(
            external_id=f"{code}-{i}",
            number=str(i),
            name=f"Synthetic named form {i}",
            metadata=dict(pokemon_dex=n, dex_eligible=False, supertype="Pokémon", rarity="Rare"),
            finish="foil",
            variant="alternate",
        )
        for i, n in enumerate(numbers, 1)
    ]
    p = dict(
        schema_version="dex-catalog-v1",
        game="pokemon",
        set_key=code,
        set_name="Synthetic " + code,
        language="en",
        aliases=[],
        provider="m2-synthetic",
        version="v1",
        source_url="https://example.test/retained",
        source_sha256="a" * 64,
        metadata_permission="Synthetic test only",
        image_permission="not-included",
        coverage="catalog-entries",
        expected_count=max(1, len(cards)),
        cards=cards,
    )
    return dict(
        set_id="m2-synthetic:en:" + code,
        language="en",
        era="swsh",
        medium="physical",
        release_status="released",
        source_url=p["source_url"],
        source_time="2026-10-04T12:00:00+00:00",
        source_sha256=p["source_sha256"],
        evidence_class="synthetic",
        enumeration_complete=True,
        enumerated_ids=[c["external_id"] for c in cards],
        package=p,
    )


def batch(*sets, mode="atomic", version="synthetic-v1"):
    return dict(schema_version="dex-target-batch-v1", version=version, mode=mode, sets=list(sets))


def test_mapping_scope_truncation_duplicates_and_empty():
    a = synthetic()
    r = pipeline.assess(a)
    assert r["species"] == [134, 196] and r["expected_target_count"] is None
    assert len(r["excluded_above251"]) == 1
    assert any(e["reason"] == "unresolved-canonical-mapping" for e in r["exceptions"])
    a["package"]["cards"].append(copy.deepcopy(a["package"]["cards"][0]))
    assert not pipeline.assess(a)["fatal"]
    a["package"]["cards"][-1]["metadata"]["pokemon_dex"] = 135
    assert pipeline.assess(a)["fatal"]
    a = synthetic(numbers=(134, 196))
    a["enumerated_ids"].append("not-supplied")
    assert pipeline.assess(a)["status"] == "partially-assessed"
    a = synthetic(numbers=(252,))
    assert pipeline.assess(a)["status"] == "confirmed-zero-target"
    for medium, language, release in [
        ("digital", "en", "released"),
        ("physical", "fr", "released"),
        ("physical", "en", "unreleased"),
    ]:
        a = synthetic(numbers=(134,))
        a.update(medium=medium, language=language, release_status=release)
        a["package"]["language"] = language
        a["set_id"] = f"m2-synthetic:{language}:modern-test"
        assert pipeline.assess(a)["status"] == "out-of-scope"
        assert pipeline.assess(a)["target_numbered_count"] == 0
        assert pipeline.assess(a)["distribution"] == {}


def test_atomic_invalid_checkpoint_idempotency_and_rollback(e1):
    actor = e1["actor"]
    before = inv.copies(actor)
    a, b = synthetic("one", (134,)), synthetic("two", (196,))
    bad = copy.deepcopy(b)
    bad["package"]["cards"].append(dict(bad["package"]["cards"][0], name="conflicting"))
    assert pipeline.preview(actor, batch(a, bad))["state"] == "invalid"
    assert not store.rows("SELECT * FROM catalog_batches")
    op = pipeline.preview(actor, batch(a, b, mode="checkpoint"))
    assert not store.rows("SELECT * FROM catalog_imports WHERE package LIKE '%m2-synthetic%'")
    pipeline.transition(actor, op["id"], "verify")
    first = pipeline.transition(actor, op["id"], "publish", limit=1)
    assert first["state"] == "partial"
    assert pipeline.transition(actor, op["id"], "publish", expected_completed=0) == first
    # A new caller resumes only unfinished work using persisted child IDs.
    second = pipeline.transition(actor, op["id"], "publish", limit=1)
    assert second["state"] == "published"
    assert first["outcomes"][0]["publication"] == second["outcomes"][0]["publication"]
    assert pipeline.transition(actor, op["id"], "publish")["state"] == "published"
    assert pipeline.preview(actor, batch(a, b, mode="checkpoint"))["id"] == op["id"]
    assert pipeline.coverage(actor)["totals"]["assessed"] == 0
    assert len(pipeline.coverage(actor)["synthetic"]) == 2
    assert pipeline.transition(actor, op["id"], "rollback")["state"] == "rolled-back"
    assert inv.copies(actor) == before
    with pytest.raises(PermissionDenied):
        pipeline.get(e1["member"], op["id"])


def test_retained_full_batch_and_target_report(e1):
    actor = e1["actor"]
    p = pipeline.retained_batch()
    p["mode"] = "atomic"
    before = inv.copies(actor)
    op = pipeline.preview(actor, p)
    assert len(op["outcomes"]) == 13
    assert sum(r["enumeration_complete"] for r in op["outcomes"]) == 12
    assert (
        next(r for r in op["outcomes"] if r["set_id"] == "tcgdex:en:gym1")["status"] == "partially-assessed"
    )
    pipeline.transition(actor, op["id"], "verify")
    final = pipeline.transition(actor, op["id"], "publish")
    report = pipeline.coverage(actor)
    assert report["totals"]["assessed"] == 13
    assert report["totals"]["unassessed"] == 207
    sv = next(r for r in final["outcomes"] if r["set_id"] == "tcgdex:en:sv03.5")
    assert sv["target_numbered_count"] < sv["supplied_variant_records"]
    assert sv["distribution"]["booster"] < 207  # Trainers/Energy excluded from target measure.
    assert next(s for s in report["species"] if s["dex"] == 196)["target_numbered_count"] > 0
    assert inv.copies(actor) == before
    pipeline.transition(actor, op["id"], "rollback")
    assert pipeline.coverage(actor)["totals"]["assessed"] == 0
    assert inv.copies(actor) == before


def test_source_correction_conflict_and_frozen_m1(e1):
    actor = e1["actor"]
    _, src = seed(e1)
    before = inv.copies(actor)
    frozen_goal = create(e1, src)
    original_goal = inv.one(actor, "goal", frozen_goal["id"])
    source_hash = collection_goals.latest(actor)["source_sha256"]
    a = synthetic("correction", (134, 135, 196))
    op = pipeline.preview(actor, batch(a))
    pipeline.transition(actor, op["id"], "verify")
    pipeline.transition(actor, op["id"], "publish")
    pack_research.initialize()
    assert inv.one(actor, "goal", frozen_goal["id"]) == original_goal
    successor = inv.preview(
        actor,
        "goal_edit",
        dict(
            name=frozen_goal["name"],
            goal_kind=collection_goals.KIND,
            collection_source_id=src["id"],
            id=frozen_goal["id"],
            revision=frozen_goal["revision"],
        ),
        str(uuid.uuid4()),
    )
    assert successor["plan"]
    assert inv.one(actor, "goal", frozen_goal["id"]) == original_goal
    context = lookup.project(actor, dict(targets="134,135"))
    saved = pack_research.store_context(actor, context, research_name="Frozen M2 test")
    frozen = pack_research.one(actor, saved)["snapshot"]
    b = copy.deepcopy(a)
    b["package"]["version"] = "v2"
    b["source_sha256"] = b["package"]["source_sha256"] = "b" * 64
    b["package"]["cards"][0]["name"] = "Synthetic corrected named form"
    correction = pipeline.preview(actor, batch(b, version="correction-v2"))
    assert correction["outcomes"][0]["impact"]["updated"]
    pipeline.transition(actor, correction["id"], "verify")
    pipeline.transition(actor, correction["id"], "publish")
    with pytest.raises(inv.Conflict):
        pipeline.transition(actor, op["id"], "rollback")
    pipeline.transition(actor, correction["id"], "rollback")
    assert pack_research.one(actor, saved)["snapshot"] == frozen
    assert pack_research.reopen(actor, saved)
    assert collection_goals.latest(actor)["source_sha256"] == source_hash
    assert lookup.project(actor, dict(scope="missing"))["progress"]["satisfied"] == 161
    assert inv.copies(actor) == before


def test_cross_set_conflict_publishes_nothing_and_stale_checkpoint(e1):
    a, b = synthetic("conflict-a", (134,)), synthetic("conflict-b", (135,))
    a["package"]["aliases"] = b["package"]["aliases"] = ["same ambiguous alias"]
    pipeline.initialize()
    before = pipeline.state_hash()
    assert pipeline.preview(e1["actor"], batch(a, b))["state"] == "invalid"
    assert pipeline.state_hash() == before
    assert not store.rows("SELECT * FROM catalog_batches")
    a["package"]["aliases"] = b["package"]["aliases"] = []
    op = pipeline.preview(e1["actor"], batch(a, b, mode="checkpoint"))
    pipeline.transition(e1["actor"], op["id"], "verify")
    pipeline.transition(e1["actor"], op["id"], "publish")
    external = pipeline.preview(e1["actor"], batch(synthetic("external", (151,)), version="external"))
    pipeline.transition(e1["actor"], external["id"], "verify")
    pipeline.transition(e1["actor"], external["id"], "publish")
    with pytest.raises(inv.Conflict):
        pipeline.transition(e1["actor"], op["id"], "publish")
    assert pipeline.get(e1["actor"], op["id"])["state"] == "partial"


def test_routes_csrf_privacy_and_unavailable(e1):
    a = synthetic()
    a.update(source_status="unavailable", package={})
    assert pipeline.assess(a)["status"] == "source-unavailable"
    assert pipeline.assess(a)["expected_target_count"] is None
    assert e1["a"].get("/catalog-pipeline/").status_code == 200
    assert e1["b"].get("/catalog-pipeline/").status_code == 403
    assert e1["b"].get("/catalog-coverage/").status_code == 200
    response = e1["b"].get("/api/catalog-coverage/").json()
    assert "package" not in str(response)
    assert e1["a"].post("/catalog-pipeline/preview/", {"retained": "yes"}).status_code == 403


def test_distribution_metrics_keep_promos_decks_and_variants_separate():
    a = copy.deepcopy(pipeline.retained_batch()["sets"][-2])
    a["evidence_class"] = "synthetic"
    first = next(m for m in a["package"]["memberships"] if m["status"] == "booster")
    first["status"] = "promo"
    second = next(m for m in a["package"]["memberships"] if m["status"] == "booster")
    second["status"] = "deck-only"
    r = pipeline.assess(a)
    assert r["target_numbered_count"] == 185 and r["supplied_variant_records"] == 346
    assert r["distribution"]["promo"] == 1 and r["distribution"]["deck-only"] == 1
    assert r["distribution"]["unknown"] == 161
    assert r["variant_completeness"] == "unknown"
