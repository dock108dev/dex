"""M3 service/UI behavior on isolated synthetic SQLite; no real purchasability."""

import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from test_migration import snapshot as snapshot
from test_packs import b2 as b2
from test_packs import b3 as b3
from test_packs import b4 as b4
from test_packs import e1 as e1
from test_packs import env as env
from test_packs import ready
from test_sealed_catalog import delta, publish

from pokemon_hunter.beta import catalog_imports, collection, lookup, pack_research, product_lookup
from pokemon_hunter.beta import offer_filters as filters
from pokemon_hunter.beta import sealed_catalog as cat

NOW = datetime(2026, 10, 6, 3, tzinfo=timezone.utc)
DATA = Path(__file__).parents[1] / "config/sealed/m3-synthetic/package.json"


def fixture():
    return json.loads(DATA.read_text())


def test_mixed_distinct_guaranteed_only_and_unknown_products(e1):
    ready(e1)
    copies = collection.copies(e1["actor"])
    publish(e1, fixture())
    context = lookup.project(e1["actor"], dict(targets="134,135,230"))
    products = {p["id"]: p for g in context["expansions"] for p in g["products"]}
    assert products["m3:product:mixed"]["possible_count"] == 3
    assert products["m3:product:mixed"]["guaranteed_count"] == 1
    assert products["m3:product:mixed"]["distinct_target_count"] == 3
    assert products["m3:product:guaranteed"]["possible_count"] == 0
    assert products["m3:product:guaranteed"]["guaranteed_count"] == 1
    assert products["m3:product:assortment"]["possible_count"] == 0
    assert not products["m3:product:assortment"]["verified"]
    assert collection.copies(e1["actor"]) == copies
    page = e1["a"].get("/lookup/", dict(targets="230"))
    assert page.status_code == 200 and b"Synthetic guaranteed product" in page.content


def correction(records, status="promo", version="m3-correction"):
    old = next(m for m in records["memberships"].values() if m["printing_id"] == "m3:en:kingdra:normal")
    p = delta(dict(provider="m3-synthetic"), version)
    src = copy.deepcopy(records["sources"]["m3-card"])
    src.update(id=version + ":source", sha256="8" * 64)
    p["sources"] = [src]
    p["memberships"] = [dict(old, status=status, sources=old["sources"] + [src["id"]])]
    p["corrections"] = [
        dict(
            kind="memberships",
            id=old["id"],
            before_sha256=catalog_imports.fingerprint(old),
            reason="Synthetic reviewed distribution correction",
        )
    ]
    return p


def test_distribution_correction_conflict_rollback_and_frozen_save(e1):
    ready(e1)
    publish(e1, fixture())
    pack_research.initialize()
    ctx = lookup.project(e1["actor"], dict(targets="230"))
    key = pack_research.store_context(e1["actor"], ctx, "Before correction")
    raw = pack_research.one(e1["actor"], key)["snapshot"]
    p = correction(cat.records())
    op = cat.preview(e1["actor"], p)
    review = cat.review(op)
    assert review["corrections"][0]["before"]["status"] == "booster"
    assert review["corrections"][0]["after"]["status"] == "promo"
    cat.transition(e1["actor"], op["id"], "verify")
    cat.transition(e1["actor"], op["id"], "publish")
    assert cat.transition(e1["actor"], op["id"], "publish")["state"] == "published"
    ctx = lookup.project(e1["actor"], dict(targets="230"))
    assert all(g["count"] == 0 for g in ctx["expansions"])
    assert any(p["guaranteed_count"] == 1 for g in ctx["expansions"] for p in g["products"])
    assert pack_research.reopen(e1["actor"], key)["reference_gaps"]
    assert pack_research.one(e1["actor"], key)["snapshot"] == raw
    stale = copy.deepcopy(p)
    stale["version"] = "stale-correction"
    with pytest.raises(collection.Conflict):
        cat.preview(e1["actor"], stale)
    cat.transition(e1["actor"], op["id"], "rollback")
    assert lookup.project(e1["actor"], dict(targets="230"))["expansions"][0]["count"] == 1
    assert e1["b"].get("/packs/saved/" + key + "/").status_code == 404
    assert e1["b"].get("/product-review/").status_code == 403


def test_source_applicability_price_stock_and_synthetic_eligibility(e1):
    ready(e1)
    publish(e1, fixture())
    r = cat.records()
    product = r["products"]["m3:product:mixed"]
    decisions = {}
    for code in ("fresh", "market", "stale", "unavailable", "unknown"):
        offer = r["offers"]["m3:offer:" + code]
        obs = r["observations"][offer["id"] + ":observation"]
        decisions[code] = filters.eligibility(offer, obs, product, r["sources"], NOW)
    assert decisions["fresh"]["behavior_eligible"] and decisions["market"]["behavior_eligible"]
    indexed = product_lookup.coverage(r, NOW, collection.catalog(e1["actor"]))
    assert indexed[229]["catalog_printing_ids"]
    assert all("printing-unresearched" not in t["gaps"] for t in indexed if t["catalog_printing_ids"])
    assert all(not d["recommendation_eligible"] and not d["purchase_ready"] for d in decisions.values())
    assert all(not decisions[c]["behavior_eligible"] for c in ("stale", "unavailable", "unknown"))
    offer = r["offers"]["m3:offer:fresh"]
    obs = r["observations"][offer["id"] + ":observation"]
    assert not filters.eligibility(offer, obs, dict(product, distinct_target_count=0), r["sources"], NOW)[
        "behavior_eligible"
    ]
    assert not filters.eligibility(offer, dict(obs, price_minor=None), product, r["sources"], NOW)[
        "behavior_eligible"
    ]
    assert not filters.eligibility(offer, dict(obs, sources=[]), product, r["sources"], NOW)[
        "behavior_eligible"
    ]
    assert not filters.eligibility(offer, obs, product, r["sources"], NOW + timedelta(hours=24, seconds=1))[
        "behavior_eligible"
    ]
    report = product_lookup.coverage(r, NOW)
    assert len(report) == 251 and all(not t["researched_absence"] for t in report)
    assert report[229]["products"]["m3:product:guaranteed"]["guaranteed_count"] == 1


@pytest.mark.parametrize("status", ["promo", "deck-only"])
def test_nonbooster_claims_need_official_distribution_evidence(e1, status):
    ready(e1)
    publish(e1, fixture())
    p = correction(cat.records(), status)
    unsupported = copy.deepcopy(p)
    unsupported["sources"][0]["supports"] = ["booster-membership"]
    # A booster checklist is not evidence of promo/deck applicability.
    with pytest.raises(ValueError, match="official card"):
        cat.preview(e1["actor"], unsupported)
    p["sources"][0].update(authority="provider")
    p["memberships"][0]["sources"] = [p["sources"][0]["id"]]
    # Correction first requires retaining prior provenance; both gates refuse unsupported promotion.
    with pytest.raises(ValueError):
        cat.preview(e1["actor"], p)


def test_owner_browser_review_publication_and_immutable_observation(e1):
    ready(e1)

    def post(url, data=None):
        return e1["a"].post(url, data or {}, HTTP_X_CSRFTOKEN=e1["a"].cookies["dex_b1_csrf"].value)

    assert e1["a"].post("/product-review/preview/", {}).status_code == 403
    response = post("/product-review/preview/", dict(package=json.dumps(fixture())))
    assert response.status_code == 302
    url = response["Location"]
    assert e1["a"].get(url).status_code == 200
    assert b"Publication refused" in post(url + "publish/").content
    assert post(url + "verify/").status_code == 302
    assert post(url + "publish/").status_code == 302
    assert post(url + "publish/").status_code == 302
    assert e1["a"].get("/api/product-coverage/").status_code == 200
    p = fixture()
    p["version"] = "mutated-observation"
    p["observations"][0]["price_minor"] = 1
    with pytest.raises(ValueError, match="Immutable record conflict"):
        cat.preview(e1["actor"], p)
    assert post(url + "rollback/").status_code == 302


def test_m2_coverage_tracks_published_distribution_corrections(e1):
    from pokemon_hunter.beta import catalog_pipeline as pipeline

    pipeline.initialize()
    raw = pipeline.retained_batch()
    raw["mode"] = "atomic"
    batch = pipeline.preview(e1["actor"], raw)
    pipeline.transition(e1["actor"], batch["id"], "verify")
    pipeline.transition(e1["actor"], batch["id"], "publish")
    before = pipeline.coverage(e1["actor"])
    before_set = next(r for r in before["sets"] if r["set_id"] == "tcgdex:en:sv03.5")
    assert before_set["distribution"]["booster"] == 185
    records = cat.records()
    old = next(
        m for m in records["memberships"].values() if m["printing_id"] == "tcgdex:en:sv03.5-123:normal"
    )
    p = delta(dict(provider="m3-synthetic"), "m3-retained-membership-correction")
    src = copy.deepcopy(records["sources"][old["sources"][0]])
    src.update(
        id="m3-retained-correction-source",
        sha256="9" * 64,
        note="Synthetic correction qualification only; does not change retained source truth",
        supports=["distribution-membership"],
    )
    p["sources"] = [src]
    p["memberships"] = [dict(old, status="deck-only", sources=old["sources"] + [src["id"]])]
    p["corrections"] = [
        dict(
            kind="memberships",
            id=old["id"],
            before_sha256=catalog_imports.fingerprint(old),
            reason="Synthetic distribution correction",
        )
    ]
    op = publish(e1, p)
    after = pipeline.coverage(e1["actor"])
    after_set = next(r for r in after["sets"] if r["set_id"] == "tcgdex:en:sv03.5")
    assert after_set["distribution"]["booster"] == 184 and after_set["distribution"]["deck-only"] == 1
    assert after["species"][122]["distribution"]["deck-only"] == 1
    cat.transition(e1["actor"], op["id"], "rollback")
    restored = next(r for r in pipeline.coverage(e1["actor"])["sets"] if r["set_id"] == "tcgdex:en:sv03.5")
    assert restored["distribution"] == before_set["distribution"]


def test_unknown_original_time_is_retained_and_never_recommended(e1):
    ready(e1)
    p = fixture()
    p["observations"][0]["checked_at"] = None
    publish(e1, p)
    observed = cat.report(e1["actor"], NOW)["observations"]
    row = next(o for o in observed if o["id"] == "m3:offer:fresh:observation")
    assert row["checked_at"] is None and not row["fresh"] and not row["buy_now"]
    assert "Original checked time" in " ".join(
        product_lookup.coverage(cat.records(), NOW)[229]["offers"][0]["eligibility"]["recommendation_reasons"]
    )
