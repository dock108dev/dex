"""Reviewed coverage identities and unresolved included-card compatibility."""

import copy
from pathlib import Path

import pytest
from test_m3 import b2 as b2
from test_m3 import b3 as b3
from test_m3 import b4 as b4
from test_m3 import e1 as e1
from test_m3 import env as env
from test_m3 import fixture, ready
from test_migration import snapshot as snapshot
from test_sealed_catalog import publish

from pokemon_hunter.beta import catalog_imports, catalog_pipeline, collection, lookup, pack_research
from pokemon_hunter.beta import sealed_catalog as sealed

ROOT = Path(__file__).parents[1]


def test_reviewed_identity_profile_has_exact_source_denominator():
    manifest, aliases = catalog_pipeline.coverage_profile()
    assert len(manifest["sets"]) == 220
    assert sum(r["medium"] == "physical" for r in manifest["sets"]) == 205
    assert aliases == {"tcgdex:en:sv08-5": "tcgdex:en:sv08.5", "tcgdex:en:swsh12-5": "tcgdex:en:swsh12.5"}
    assert aliases.get("tcgdex:en:unreviewed-5", "tcgdex:en:unreviewed-5") == "tcgdex:en:unreviewed-5"
    assert not catalog_pipeline.coverage_profile("historical")[1]
    with pytest.raises(ValueError):
        catalog_pipeline.coverage_profile("arbitrary")


def test_old_packages_preserve_normalized_fingerprints(e1):
    ready(e1)
    raw = fixture()
    assert sealed.validate(raw, sealed.records())["products"] == raw["products"]


def test_inclusion_atomic_refusal_rollback_and_frozen_bytes(e1):
    ready(e1)
    publish(e1, fixture())
    actor = e1["actor"]
    before = sealed.records()
    old = before["products"]["m3:product:mixed"]
    source = copy.deepcopy(before["sources"][old["sources"][0]])
    source.update(id="m4-test-inclusion", subjects=[old["id"]])
    delta = {k: [] for k in sealed.KINDS}
    delta.update(schema_version="dex-sealed-v1", provider="m4-test", version="inclusion-v1", mappings=[])
    delta["sources"] = [source]
    card = dict(
        name="Lucario VSTAR etched foil promo",
        quantity=1,
        canonical_dex=448,
        exact_printing="unresolved",
        sources=[source["id"]],
    )
    delta["products"] = [dict(old, sources=old["sources"] + [source["id"]], included_cards=[card])]
    delta["corrections"] = [
        dict(
            kind="products",
            id=old["id"],
            before_sha256=catalog_imports.fingerprint(old),
            reason="Reviewed retained inclusion",
        )
    ]
    broken = copy.deepcopy(delta)
    broken["products"][0]["included_cards"][0]["sources"] = ["missing:source"]
    with pytest.raises(ValueError):
        sealed.preview(actor, broken)
    assert sealed.records() == before
    pack_research.initialize()
    context = lookup.project(actor, dict(targets="134,230"))
    key = pack_research.store_context(actor, context, "Frozen before inclusion")
    saved = pack_research.one(actor, key)["snapshot"]
    op = sealed.preview(actor, delta)
    sealed.transition(actor, op["id"], "verify")
    sealed.transition(actor, op["id"], "publish")
    assert sealed.preview(actor, delta)["id"] == op["id"]
    after = lookup.project(actor, dict(targets="134,230"))

    def target_counts(ctx):
        return {
            p["id"]: (p["possible_count"], p["guaranteed_count"])
            for g in ctx["expansions"]
            for p in g["products"]
        }

    assert target_counts(context) == target_counts(after)
    assert pack_research.one(actor, key)["snapshot"] == saved
    page = e1["a"].get("/lookup/", dict(targets="134,230"))
    assert b"Lucario VSTAR" in page.content and b"outside #001" in page.content
    assert b"Exact printing unresolved" in page.content
    stale = copy.deepcopy(delta)
    stale["version"] = "stale-inclusion"
    with pytest.raises(collection.Conflict):
        sealed.preview(actor, stale)
    sealed.transition(actor, op["id"], "rollback")
    assert sealed.records() == before
    assert pack_research.one(actor, key)["snapshot"] == saved
