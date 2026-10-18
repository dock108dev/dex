"""Numbered extension lifecycle, exact preservation and dependency boundaries."""

import copy
import json
import uuid

import pytest
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_catalog_pipeline import batch, synthetic
from test_migration import snapshot as snapshot

from pokemon_hunter.beta import catalog_additions as additions
from pokemon_hunter.beta import catalog_imports as cat
from pokemon_hunter.beta import catalog_pipeline as pipeline
from pokemon_hunter.beta import collection as inv
from pokemon_hunter.beta import store


def setup(actor, code="extension-test"):
    a = synthetic(code, (495,))
    a["catalog_policy"] = "english-physical-all"
    c = a["package"]["cards"][0]
    c.update(edition=None, finish=None, variant=None)
    c["metadata"]["dex_eligible"] = True
    op = cat.preview(actor, a["package"])
    cat.transition(actor, op["id"], "verify")
    op = cat.transition(actor, op["id"], "publish")
    s = cat.snapshot(op["set_id"])["sets"][0]
    p = copy.deepcopy(a["package"])
    new = dict(copy.deepcopy(c), external_id=code + "-2", number="2", name="Synthetic extension Snivy")
    p.update(
        schema_version=additions.SCHEMA,
        source_time=a["source_time"],
        source_members={
            r["external_id"]: dict(path="synthetic/" + r["number"] + ".ts", sha256="a" * 64) for r in [c, new]
        },
        set_id=s["id"],
        source_set_key=code,
        set_sha256=cat.fingerprint(s),
        version="extension-v1",
        cards=[new],
        enumeration=[c, new],
        represented={c["external_id"]: {c["external_id"]: op["preview"]["added"][0]["id"]}},
        expected_count=2,
    )
    a.update(package=p, enumerated_ids=[c["external_id"], new["external_id"]], expected_target_count=2)
    return a


def publish(actor, p):
    op = cat.preview(actor, p)
    if op["state"] == "preview":
        cat.transition(actor, op["id"], "verify")
    return cat.transition(actor, op["id"], "publish")


def test_full_enumeration_preserves_rows_mapping_versions_and_replay(b4):
    actor = b4["actor"]
    a = setup(actor)
    p = a["package"]
    before = cat.snapshot(p["set_id"])
    maps = store.rows("SELECT * FROM external_mappings")
    r = pipeline.assess(a)
    assert r["enumeration_complete"] and r["expected_target_count"] == 2
    assert pipeline.prepared(a, r) == p
    op = publish(actor, p)
    after = cat.snapshot(p["set_id"])
    assert after["sets"] == before["sets"]
    assert all(r in after["cards"] for r in before["cards"])
    assert all(r in store.rows("SELECT * FROM external_mappings") for r in maps)
    assert len(op["preview"]["added"]) == 1 and not op["preview"]["updated"] and not op["preview"]["archived"]
    assert cat.preview(actor, p) == op and cat.transition(actor, op["id"], "publish") == op
    assert all(json.loads(r["attributes"]).get("parent_printing_id") is None for r in op["preview"]["added"])
    cat.transition(actor, op["id"], "rollback")
    republished = cat.transition(actor, op["id"], "publish")
    assert republished["state"] == "published" and cat.snapshot(p["set_id"]) == after


@pytest.mark.parametrize("kind", ["mapping", "version", "partition", "metadata", "physical"])
def test_conflicts(b4, kind):
    actor = b4["actor"]
    a = setup(actor)
    p = a["package"]
    if kind == "mapping":
        inv.execute(
            "INSERT INTO external_mappings VALUES(%s,'printing',%s,%s)",
            [
                p["provider"] + ":en",
                p["cards"][0]["external_id"],
                next(iter(next(iter(p["represented"].values())).values())),
            ],
        )
    elif kind == "version":
        cat.preview(actor, p)
        p["cards"][0]["name"] = "Changed"
        p["enumeration"][1]["name"] = "Changed"
    elif kind == "partition":
        p["enumeration"].pop()
    elif kind == "metadata":
        p["enumeration"][0]["metadata"]["pokemon_dex"] = 496
    elif kind == "physical":
        p["cards"][0]["finish"] = "normal"
    with pytest.raises(ValueError):
        cat.preview(actor, p)


@pytest.mark.parametrize("dependency", ["copy", "goal", "mapping", "descendant", "publication"])
def test_numbered_parent_rollback_dependencies(b4, dependency):
    actor = b4["actor"]
    p = setup(actor)["package"]
    op = publish(actor, p)
    row = op["preview"]["added"][0]
    pid = row["id"]
    if dependency == "copy":
        entry = inv.preview(
            actor, "add", dict(printing_id=pid, attributes={}, duplicate_policy="allow"), str(uuid.uuid4())
        )
        inv.confirm(actor, entry["id"])
    elif dependency == "goal":
        entry = inv.preview(
            actor,
            "goal",
            dict(name="Frozen extension", goal_kind="custom", printing_ids=[pid], policy="catalog"),
            str(uuid.uuid4()),
        )
        inv.confirm(actor, entry["id"])
    elif dependency == "mapping":
        inv.execute("INSERT INTO external_mappings VALUES('later','printing','later',%s)", [pid])
    elif dependency == "descendant":
        child = dict(
            row,
            id=str(uuid.uuid4()),
            attributes=json.dumps(dict(json.loads(row["attributes"]), parent_printing_id=pid)),
            publication_state="archived",
        )
        cat.write("printings", child)
    else:
        inv.execute(
            "INSERT INTO catalog_imports(id,user_id,package,package_hash,set_id,state,baseline,preview) VALUES(%s,%s,%s,%s,%s,'published','{}','{}')",
            [str(uuid.uuid4()), actor.user_id, json.dumps({"depends": pid}), str(uuid.uuid4()), "other-set"],
        )
    with pytest.raises(inv.Conflict):
        cat.transition(actor, op["id"], "rollback")
    assert cat.get(actor, op["id"])["state"] == "published"


def test_stale_preview_and_cross_package_conflict(b4):
    actor = b4["actor"]
    p = setup(actor)["package"]
    op = cat.preview(actor, p)
    inv.execute("UPDATE catalog_sets SET catalog_version='intervening' WHERE id=%s", [p["set_id"]])
    with pytest.raises((ValueError, inv.Conflict)):
        cat.transition(actor, op["id"], "verify")


def test_checkpoint_resume_and_frozen_read_membership(b4):
    from pokemon_hunter.beta import broad_goals

    actor = b4["actor"]
    a = setup(actor, "extension-one")
    b = setup(actor, "extension-two")
    raw = batch(a, b, mode="checkpoint", version="extension-batch")
    op = pipeline.preview(actor, raw)
    assert op["state"] == "preview"
    pipeline.transition(actor, op["id"], "verify")
    op = pipeline.transition(actor, op["id"], "publish", limit=1, expected_completed=0)
    assert op["completed_sets"] == 1 and op["state"] == "partial"
    assert pipeline.transition(actor, op["id"], "publish", limit=1, expected_completed=0) == op
    op = pipeline.transition(actor, op["id"], "publish", limit=1, expected_completed=1)
    assert op["state"] == "published" and op["completed_sets"] == 2
    selected, refs = broad_goals.reviewed(inv.catalog(actor), upper=1025)
    assert {r["id"] for r in selected} >= {
        r["id"] for outcome in op["outcomes"] for r in outcome["publication"]["impact"]["added"]
    }


def test_cross_version_numbered_evidence_conflict(b4):
    actor = b4["actor"]
    p = setup(actor)["package"]
    publish(actor, p)
    later = copy.deepcopy(p)
    later["version"] = "conflicting-extension-v2"
    with pytest.raises(ValueError, match="different extension evidence"):
        cat.preview(actor, later)


def test_stale_archived_identity_rejected(b4):
    actor = b4["actor"]
    p = setup(actor)["package"]
    old = cat.snapshot(p["set_id"])["cards"][0]
    inv.execute("UPDATE printings SET publication_state='archived' WHERE id=%s", [old["id"]])
    op = cat.preview(actor, p)
    cat.transition(actor, op["id"], "verify")
    inv.execute(
        "UPDATE printings SET attributes=%s WHERE id=%s",
        [json.dumps(dict(json.loads(old["attributes"]), later_note="changed")), old["id"]],
    )
    with pytest.raises(inv.Conflict, match="original identity"):
        cat.transition(actor, op["id"], "publish")


def test_later_sealed_bridge_prevents_numbered_rollback(b4):
    from django.db import connection

    actor = b4["actor"]
    p = setup(actor)["package"]
    op = publish(actor, p)
    with connection.cursor() as cursor:
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS sealed_bridges(printing_id TEXT PRIMARY KEY,catalog_id TEXT NOT NULL,import_id TEXT NOT NULL)"
        )
    inv.execute(
        "INSERT INTO sealed_bridges VALUES('later-sealed',%s,'later-publication')",
        [op["preview"]["added"][0]["id"]],
    )
    with pytest.raises(inv.Conflict, match="Later publication"):
        cat.transition(actor, op["id"], "rollback")


def test_new_archived_identity_stales_verified_extension(b4):
    actor = b4["actor"]
    p = setup(actor)["package"]
    op = cat.preview(actor, p)
    cat.transition(actor, op["id"], "verify")
    extra = dict(
        cat.snapshot(p["set_id"])["cards"][0],
        id=str(uuid.uuid4()),
        collector_number="later",
        publication_state="archived",
    )
    cat.write("printings", extra)
    with pytest.raises(inv.Conflict, match="archived additions"):
        cat.transition(actor, op["id"], "publish")
