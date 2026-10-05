"""151 reconciliation and transactional bridge/correction regression checks."""

import copy
import json
from pathlib import Path

import pytest
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_migration import snapshot as snapshot
from test_sealed_catalog import delta, package, publish
from test_sealed_catalog import e1 as e1

from pokemon_hunter.beta import catalog_imports as legacy
from pokemon_hunter.beta import collection as inv
from pokemon_hunter.beta import sealed_catalog as cat
from pokemon_hunter.beta import store

DATA = Path(__file__).parents[1] / "config/sealed/2026-10-04-151"


def expanded():
    return json.loads((DATA / "package.json").read_text())


def correction(p, version="correction-v1", bridge=False):
    q = delta(p, version)
    row = copy.deepcopy(p["printings"][0])
    source = copy.deepcopy(next(s for s in p["sources"] if s["id"] == row["sources"][0]))
    source.update(
        id=version + ":source", subjects=[row["id"]], note="Synthetic descriptive correction evidence"
    )
    row.update(name=row["name"] + " (reviewed label)", sources=row["sources"] + [source["id"]])
    q.update(
        sources=[source],
        printings=[row],
        corrections=[
            dict(
                kind="printings",
                id=row["id"],
                before_sha256=cat.cat.fingerprint(p["printings"][0]),
                reason="Synthetic spelling correction, identity preserved",
            )
        ],
    )
    if bridge:
        q["printings"] = copy.deepcopy(p["printings"])
        q["printings"][0] = row
        q["mappings"] = copy.deepcopy([m for m in p["mappings"] if m["kind"] in {"printings", "expansions"}])
        q["bridges"] = copy.deepcopy(p["bridges"])
        q["bridges"][0]["package"]["version"] = version
        q["bridges"][0]["package"]["cards"][0]["name"] = row["name"]
    return q


def test_207_identities_categories_variants_and_individual_gaps():
    p = cat.validate(expanded())
    report = json.loads((DATA / "reconciliation.json").read_text())
    assert report["reconciled"] == 207
    assert {r["number"] for r in report["rows"]} == {f"{n:03}" for n in range(1, 208)}
    assert len(p["printings"]) == 384
    assert len({r["species_id"] for r in p["printings"] if r["species_id"]}) == 151
    assert sum(r["status"] == "booster" for r in p["memberships"]) == 207
    for r in p["printings"]:
        assert (r["species_id"] is not None) == (r["category"] == "pokemon")
    energy = [r for r in p["printings"] if r["number"] == "207/165"]
    assert energy and all(r["category"] == "energy" and r["species_id"] is None for r in energy)
    assert sum(len(r["gaps"]) for r in report["rows"]) == 177
    assert p["products"][0]["total_packs"] is None
    assert not p["products"][0]["guaranteed_cards_known"]
    assert p["observations"][-1]["stock"] == "out-of-stock"


def test_bridge_preserves_old_printings_copies_frozen_goals_and_dates(e1):
    from test_b2 import apply

    apply(e1, "goal", {"name": "Frozen vintage", "goal_kind": "vintage"})
    preserved = {
        t: store.rows(f"SELECT * FROM {t} ORDER BY id")
        for t in ("owned_copies", "collection_goals", "printings")
    }
    publish(e1, package())
    p = expanded()
    op = cat.preview(e1["actor"], p)
    review = cat.review(op)
    assert len(review["bridges"][0]["mappings"]) == 384
    assert len(review["bridges"][0]["impact"]["added"]) == 384
    assert not review["bridges"][0]["impact"]["archived"]
    cat.transition(e1["actor"], op["id"], "verify")
    cat.transition(e1["actor"], op["id"], "publish")
    assert cat.preview(e1["actor"], p)["id"] == op["id"]
    result = cat.report(e1["actor"])
    assert len(result["printings_bridged"]) == 384
    assert result["numbered_checklist_identities"] == 207
    assert store.rows("SELECT * FROM owned_copies ORDER BY id") == preserved["owned_copies"]
    assert store.rows("SELECT * FROM collection_goals ORDER BY id") == preserved["collection_goals"]
    current = {r["id"]: r for r in store.rows("SELECT * FROM printings")}
    assert all(current[r["id"]] == r for r in preserved["printings"])
    assert result["observations"][-1]["checked_at"] == p["observations"][-1]["checked_at"]
    assert not any(r["buy_now"] for r in result["observations"])
    cat.transition(e1["actor"], op["id"], "rollback")
    assert not cat.report(e1["actor"])["printings_bridged"]
    assert store.rows("SELECT * FROM collection_goals ORDER BY id") == preserved["collection_goals"]


def test_bridge_failure_rolls_back_both_catalogs_and_retries(e1, monkeypatch):
    p = expanded()
    op = cat.preview(e1["actor"], p)
    cat.transition(e1["actor"], op["id"], "verify")
    old = legacy.transition

    def fail_after_publish(actor, key, action):
        result = old(actor, key, action)
        if action == "publish":
            raise RuntimeError("Injected failure after collection publication")
        return result

    monkeypatch.setattr(legacy, "transition", fail_after_publish)
    with pytest.raises(RuntimeError):
        cat.transition(e1["actor"], op["id"], "publish")
    assert cat.get(e1["actor"], op["id"])["state"] == "verified"
    assert not cat.records()["printings"]
    assert not store.rows("SELECT * FROM sealed_bridges")
    assert legacy.get(e1["actor"], op["baseline"]["bridges"][0]["import_id"])["state"] == "verified"
    monkeypatch.setattr(legacy, "transition", old)
    cat.transition(e1["actor"], op["id"], "publish")
    assert len(cat.report(e1["actor"])["printings_bridged"]) == 384


@pytest.mark.parametrize("change", ["category", "species_id", "variant", "number", "finish"])
def test_correction_refuses_identity_repurposing(e1, change):
    p = package()
    publish(e1, p)
    q = correction(p)
    q["printings"][0][change] = {
        "category": "trainer",
        "species_id": "ndex:0001",
        "variant": "reverse",
        "number": "124/165",
        "finish": "holo",
    }[change]
    with pytest.raises(ValueError, match="Canonical identity conflict"):
        cat.preview(e1["actor"], q)


def test_correction_history_stale_review_and_nonconflicting_rollback(e1):
    p = package()
    publish(e1, p)
    q = correction(p)
    op = cat.preview(e1["actor"], q)
    stale = cat.preview(e1["actor"], correction(p, "stale-review"))
    cat.transition(e1["actor"], op["id"], "verify")
    cat.transition(e1["actor"], op["id"], "publish")
    with pytest.raises(inv.Conflict):
        cat.transition(e1["actor"], stale["id"], "verify")
    # An unrelated later observation is retained when reverting descriptive metadata.
    later = delta(p, "later-unrelated")
    source = copy.deepcopy(p["sources"][-1])
    source.update(id="later-src", subjects=["later-observation"])
    obs = copy.deepcopy(p["observations"][0])
    obs.update(id="later-observation", sources=["later-src"])
    later.update(sources=[source], observations=[obs])
    # Same dated observation identities are prohibited: new check gets a new source time.
    source["retrieved_at"] = "2026-10-04T23:57:28+00:00"
    obs["checked_at"] = source["retrieved_at"]
    publish(e1, later)
    cat.transition(e1["actor"], op["id"], "rollback")
    assert cat.records()["printings"][p["printings"][0]["id"]] == p["printings"][0]
    assert "later-observation" in cat.records()["observations"]
    assert cat.get(e1["actor"], op["id"])["package"]["corrections"][0]["reason"]
    assert cat.preview(e1["actor"], q)["id"] == op["id"]


def test_correction_conflicting_reversal_and_bridge_metadata(e1):
    p = expanded()
    publish(e1, p)
    q = correction(p, bridge=True)
    op = publish(e1, q)
    link = op["baseline"]["bridges"][0]["mappings"][0]
    row = store.rows("SELECT * FROM printings WHERE id=%s", [link["catalog_id"]])[0]
    assert json.loads(row["attributes"])["name"] == q["printings"][0]["name"]
    q2 = correction({**p, "printings": q["printings"]}, "correction-v2", bridge=True)
    publish(e1, q2)
    with pytest.raises(inv.Conflict, match="Conflicting reversal"):
        cat.transition(e1["actor"], op["id"], "rollback")


def test_bridge_mapping_and_category_conflict(e1):
    p = expanded()
    p["bridges"][0]["package"]["cards"][0]["metadata"]["pokemon_dex"] = 2
    with pytest.raises(ValueError, match="canonical identity conflict"):
        cat.preview(e1["actor"], p)
    p = expanded()
    p["mappings"][-1]["external_id"] = "changed"
    with pytest.raises(ValueError, match="explicit external identity"):
        cat.preview(e1["actor"], p)


def test_bridged_correction_cannot_leave_collection_metadata_behind(e1):
    p = expanded()
    publish(e1, p)
    with pytest.raises(ValueError, match="requires atomic collection metadata"):
        cat.preview(e1["actor"], correction(p))


def test_collection_change_invalidates_bridge_review(e1):
    p = expanded()
    op = cat.preview(e1["actor"], p)
    cat.transition(e1["actor"], op["id"], "verify")
    # The selected set is new, so seed it through a separate reviewed legacy publication.
    bridged = copy.deepcopy(p["bridges"][0]["package"])
    bridged["version"] = "independent-intervening-publication"
    other = legacy.preview(e1["actor"], bridged)
    legacy.transition(e1["actor"], other["id"], "verify")
    legacy.transition(e1["actor"], other["id"], "publish")
    with pytest.raises(inv.Conflict, match="Catalog changed"):
        cat.transition(e1["actor"], op["id"], "publish")
    assert not cat.records()["printings"]


def test_provider_expansion_mapping_conflict_cannot_duplicate_set(e1):
    inv.execute("INSERT INTO external_mappings VALUES('tcgdex:en','set','sv03.5','existing-other-set')")
    with pytest.raises(ValueError, match="Provider expansion identity"):
        cat.preview(e1["actor"], expanded())
    assert not store.rows("SELECT * FROM sealed_imports")


def test_correction_requires_retained_and_added_provenance(e1):
    p = package()
    publish(e1, p)
    q = correction(p)
    q["printings"][0]["sources"] = ["correction-v1:source"]
    with pytest.raises(ValueError, match="retain prior provenance"):
        cat.preview(e1["actor"], q)
