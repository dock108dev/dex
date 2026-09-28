"""Catalog expansion qualification with synthetic private accounts; no live recognition."""

import copy
import importlib
import json
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b2 import post
from test_b3 import b3 as b3
from test_b3 import image
from test_migration import snapshot as snapshot

from pokemon_hunter.beta import catalog_imports as cat
from pokemon_hunter.beta import catalog_requests as req
from pokemon_hunter.beta import collection as inv
from pokemon_hunter.beta import scans, store
from pokemon_hunter.inventory import connect


@pytest.fixture
def b4(b3):
    from django.conf import settings
    from django.db import connection
    from django.urls import clear_url_caches

    from pokemon_hunter.beta import urls

    connection.close()
    with connect(b3["root"] / "inventory.db") as db:
        cat.initialize(db)
    settings.B4_ENABLED = True
    importlib.reload(urls)
    clear_url_caches()
    yield b3
    settings.B4_ENABLED = False
    importlib.reload(urls)
    clear_url_caches()


def package(name="synthetic-orbits"):
    return json.loads((Path(__file__).parents[1] / "config/catalog-imports" / (name + ".json")).read_text())


def provisional(b4, member=False):
    actor = b4["member"] if member else b4["actor"]
    j = scans.create(actor, str(uuid.uuid4()), [image()], "unsupported")
    scans.process_one()
    j = scans.action(actor, j["id"], "confirm", {"notes": "Private notes retained <not HTML>"})
    return actor, j


def request(b4, member=False, share=False, **hints):
    actor, j = provisional(b4, member)
    s = req.create(
        actor,
        {
            "origin": "copy",
            "origin_id": j["copy_id"],
            "share_photos": share,
            "hints": {
                "game": "synthetic-orbits",
                "set": "Demo One",
                "language": "en",
                "name": "Synthetic Navigator",
                "number": "AX-007/A",
                **hints,
            },
        },
    )
    return actor, j, s


def review(b4, s, **kwargs):
    r = store.rows("SELECT * FROM catalog_requests WHERE id=%s", [s["request_id"]])[0]
    return req.review(
        b4["actor"],
        r["id"],
        {
            "revision": r["revision"],
            "action": "review",
            "state": "ready",
            "game": "synthetic-orbits",
            "set_key": "demo-one",
            "language": "en",
            "aliases": ["Demo One"],
            **kwargs,
        },
    )


def publish(b4, p=None):
    op = cat.preview(b4["actor"], p or package())
    cat.transition(b4["actor"], op["id"], "verify")
    return cat.transition(b4["actor"], op["id"], "publish")


def test_versioned_import_repeat_partial_conflict_and_rollback(b4):
    p = package()
    op = publish(b4, p)
    assert cat.preview(b4["actor"], p)["id"] == op["id"]
    assert cat.transition(b4["actor"], op["id"], "publish")["id"] == op["id"]
    rows = inv.catalog(b4["actor"], set_id=op["set_id"])
    assert len(rows) == 2 and {r["collector_number"] for r in rows} == {"AX-007/A"}
    assert all(r["attributes"]["synthetic"] and not r["attributes"].get("pokemon_dex") for r in rows)
    add = inv.preview(
        b4["actor"],
        "add",
        {"printing_id": rows[0]["id"], "duplicate_policy": "allow", "attributes": {}},
        str(uuid.uuid4()),
    )
    owned = inv.confirm(b4["actor"], add["id"])["changes"][0]["after"]
    bad = copy.deepcopy(p)
    bad["cards"][0]["number"] = "AX-008/A"
    bad["version"] = "v2"
    with pytest.raises(ValueError, match="Identity conflict"):
        cat.preview(b4["actor"], bad)
    changed = copy.deepcopy(p)
    changed["cards"][0]["name"] = "Altered"
    with pytest.raises(ValueError, match="different content"):
        cat.preview(b4["actor"], changed)
    cat.transition(b4["actor"], op["id"], "rollback")
    assert inv.catalog(b4["actor"], set_id=op["set_id"]) == []
    assert inv.one(b4["actor"], "copy", owned["id"]) == owned
    assert store.rows("SELECT * FROM printings WHERE id=%s", [owned["printing_id"]])
    cat.transition(b4["actor"], op["id"], "publish")
    assert len(inv.catalog(b4["actor"], set_id=op["set_id"])) == 2
    partial = copy.deepcopy(p)
    partial["version"] = "v2-partial"
    partial["coverage"] = "partial"
    partial["cards"] = partial["cards"][:1]
    second = publish(b4, partial)
    assert len(inv.catalog(b4["actor"], set_id=op["set_id"])) == 1
    assert second["preview"]["archived"]
    cat.transition(b4["actor"], second["id"], "rollback")
    assert len(inv.catalog(b4["actor"], set_id=op["set_id"])) == 2


def test_invalid_coverage_string_number_variant_and_stale_preview(b4):
    p = package()
    p["cards"][0]["number"] = 7
    with pytest.raises(ValueError):
        cat.preview(b4["actor"], p)
    p = package()
    p["cards"] = p["cards"][:1]
    with pytest.raises(ValueError, match="coverage"):
        cat.preview(b4["actor"], p)
    p = package()
    p["cards"][0]["variant"] = "made-up"
    with pytest.raises(ValueError, match="Orbits"):
        cat.preview(b4["actor"], p)
    a = cat.preview(b4["actor"], package())
    p = package()
    p["version"] = "v2"
    b = publish(b4, p)
    with pytest.raises(inv.Conflict):
        cat.transition(b4["actor"], a["id"], "verify")
    assert b["state"] == "published"


def test_interrupted_publication_is_atomic(b4):
    op = cat.preview(b4["actor"], package())
    cat.transition(b4["actor"], op["id"], "verify")
    original = cat.write

    def fail(table, row):
        original(table, row)
        if table == "printings":
            raise RuntimeError("simulated interrupted publication")

    with patch.object(cat, "write", fail), pytest.raises(RuntimeError):
        cat.transition(b4["actor"], op["id"], "publish")
    assert cat.get(b4["actor"], op["id"])["state"] == "verified"
    assert not store.rows("SELECT * FROM catalog_sets WHERE id=%s", [op["set_id"]])
    assert not store.rows("SELECT * FROM catalog_aliases")
    assert cat.transition(b4["actor"], op["id"], "publish")["state"] == "published"


def test_requests_merge_distinct_requesters_aliases_and_privacy(b4):
    a, ja, sa = request(b4)
    b, jb, sb = request(b4, True)
    _, jc, sc = request(b4)
    review(b4, sa)
    for s in (sb, sc):
        r = store.rows("SELECT * FROM catalog_requests WHERE id=%s", [s["request_id"]])[0]
        req.review(a, r["id"], {"action": "merge", "target": sa["request_id"], "revision": r["revision"]})
    target = next(r for r in req.review_list(a) if r["id"] == sa["request_id"])
    assert target["requesters"] == 2 and len(target["submissions"]) == 3
    assert req.detail(b, sb["id"])["request"]["id"] == sa["request_id"]
    _, jd, sd = request(b4, True, set="  demo ONE ")
    assert sd["request_id"] == sa["request_id"]
    assert req.create(b, {"origin": "copy", "origin_id": jd["copy_id"], "hints": {}})["id"] == sd["id"]
    assert not target["submissions"][0]["photos"]
    assert "Private notes" not in json.dumps(req.review_list(a))
    for s in (sa, sb, sc, sd):
        assert store.rows("SELECT * FROM owned_copies WHERE id=%s", [s["origin_id"]])


def test_consent_scope_revocation_cross_account_and_admin(b4):
    a, ja, sa = request(b4)
    b, jb, sb = request(b4, True, True)
    shared = jb["photos"][0]
    assert b4["a"].get(f"/api/catalog-evidence/{sb['id']}/{shared}/").status_code == 200
    assert b4["a"].get(f"/scan-photos/{shared}/").status_code == 404
    assert b4["a"].get(f"/api/inventory/{jb['copy_id']}/").status_code == 404
    assert b4["b"].get("/api/catalog-review/").status_code == 403
    assert b4["b"].get("/catalog-review/").status_code == 403
    assert b4["b"].get("/api/catalog-imports/").status_code == 403
    assert b4["client"]().get("/requests/").status_code == 302
    assert (
        post(b4["a"], f"/api/catalog-requests/{sb['id']}/update/", {"share_photos": True}).status_code == 404
    )
    assert b4["a"].get(f"/api/catalog-evidence/{sa['id']}/{shared}/").status_code == 404
    req.update(b, sb["id"], {"share_photos": False})
    assert b4["a"].get(f"/api/catalog-evidence/{sb['id']}/{shared}/").status_code == 404
    req.update(b, sb["id"], {"share_photos": True})
    b4["accounts"].revoke(b4["second"])
    assert b4["a"].get(f"/api/catalog-evidence/{sb['id']}/{shared}/").status_code == 403


def test_resolution_same_copy_retry_undo_photos_and_frozen_goals(b4):
    a, j, s = request(b4, variant="orbit:nebula")
    review(b4, s)
    old = inv.one(a, "copy", j["copy_id"])
    count = len(inv.copies(a))
    op = publish(b4)
    goal = inv.preview(
        a,
        "goal",
        {"name": "Frozen", "goal_kind": "set", "set_id": op["set_id"], "policy": "catalog"},
        str(uuid.uuid4()),
    )
    inv.confirm(a, goal["id"])
    goals = inv.goals(a)
    proposed = req.detail(a, s["id"])["candidates"]
    assert len(proposed) == 1
    data = {"printing_id": proposed[0]["id"], "revision": old["revision"]}
    result = req.resolve(a, s["id"], data)
    assert req.resolve(a, s["id"], data) == result
    assert len(inv.copies(a)) == count
    current = inv.one(a, "copy", j["copy_id"])
    assert current["id"] == old["id"] and current["notes"] == old["notes"]
    assert json.loads(current["provisional_identity"])["scan_job"] == j["id"]
    assert scans.job(a, j["id"])["photos"] == j["photos"]
    assert b4["a"].get("/scan-photos/" + j["photos"][0] + "/").status_code == 200
    cat.transition(a, op["id"], "rollback")
    assert inv.goals(a)[0]["definition"] == goals[0]["definition"]
    inv.undo(a, result["resolution_op"])
    assert inv.one(a, "copy", j["copy_id"])["printing_id"] is None
    assert len(inv.copies(a)) == count


def test_rejected_request_keeps_copy_and_stale_proposal_blocked(b4):
    a, j, s = request(b4)
    review(b4, s, state="rejected", decision="Need better identity evidence")
    assert inv.one(a, "copy", j["copy_id"])["state"] == "active"
    review(b4, s)
    op = publish(b4)
    candidate = req.detail(a, s["id"])["candidates"][0]
    cat.transition(a, op["id"], "rollback")
    with pytest.raises(inv.Conflict):
        req.resolve(a, s["id"], {"printing_id": candidate["id"], "revision": 0})
    assert not inv.one(a, "copy", j["copy_id"])["printing_id"]


def test_gym_heroes_actual_package_ordinary_import(b4):
    op = publish(b4, package("gym-heroes"))
    entries = inv.catalog(b4["actor"], set_id=op["set_id"])
    assert len(entries) == 132 and any(
        p["name"] == "Blaine's Moltres" and p["collector_number"] == "1" for p in entries
    )
    assert all(p["edition"] is None and p["finish"] is None and p["variant"] is None for p in entries)
    assert all("image" not in p["attributes"] for p in entries)
    cat.transition(b4["actor"], op["id"], "rollback")
    assert not inv.catalog(b4["actor"], set_id=op["set_id"])
    cat.transition(b4["actor"], op["id"], "publish")
    assert len(inv.catalog(b4["actor"], set_id=op["set_id"])) == 132


def test_cross_account_resolution_admin_posts_and_source_mapping_conflict(b4):
    a, j, s = request(b4)
    review(b4, s)
    op = publish(b4)
    candidate = req.detail(a, s["id"])["candidates"][0]
    assert (
        post(
            b4["b"],
            f"/api/catalog-requests/{s['id']}/resolve/",
            {"printing_id": candidate["id"], "revision": 0},
        ).status_code
        == 404
    )
    assert post(b4["b"], "/api/catalog-imports/", package()).status_code == 403
    assert post(b4["b"], f"/api/catalog-imports/{op['id']}/rollback/", {}).status_code == 403
    assert (
        post(
            b4["b"],
            f"/api/catalog-review/{s['request_id']}/",
            {"revision": 1, "action": "review", "state": "rejected"},
        ).status_code
        == 403
    )
    p = package("gym-heroes")
    inv.execute("INSERT INTO external_mappings VALUES('tcgdex:en','printing','gym1-1','conflicting-id')")
    with pytest.raises(ValueError, match="already mapped"):
        cat.preview(a, p)


def test_leading_zero_pokemon_number_and_missing_evidence(b4):
    p = package("gym-heroes")
    p["set_key"] = "synthetic-number-test"
    p["set_name"] = "Synthetic number test"
    p["version"] = "numbers-v1"
    p["provider"] = "synthetic-number-test"
    p["cards"] = [{"external_id": "test-001", "number": "001/A", "name": "Synthetic numbered entry"}]
    p["expected_count"] = 1
    p["aliases"] = []
    op = publish(b4, p)
    assert inv.catalog(b4["actor"], set_id=op["set_id"])[0]["collector_number"] == "001/A"
    actor, j, s = request(b4, True, True)
    scans.action(actor, j["id"], "delete-photos", {})
    assert b4["a"].get(f"/api/catalog-evidence/{s['id']}/{j['photos'][0]}/").status_code == 404


def test_stale_review_alias_collision_and_merge_cycles(b4):
    a, j, s = request(b4)
    review(b4, s)
    with pytest.raises(inv.Conflict):
        req.review(a, s["request_id"], {"revision": 0, "action": "review", "state": "ready"})
    b, k, t = request(b4, True, set="Unknown alias")
    with pytest.raises(inv.Conflict):
        review(b4, t, set_key="other-set", aliases=["Demo One"])
    r = store.rows("SELECT * FROM catalog_requests WHERE id=%s", [t["request_id"]])[0]
    req.review(a, t["request_id"], {"revision": r["revision"], "action": "merge", "target": s["request_id"]})
    source = store.rows("SELECT * FROM catalog_requests WHERE id=%s", [s["request_id"]])[0]
    with pytest.raises(ValueError):
        req.review(
            a, s["request_id"], {"revision": source["revision"], "action": "merge", "target": t["request_id"]}
        )


def test_concurrent_resolution_keeps_one_identity(b4):
    from concurrent.futures import ThreadPoolExecutor

    from django.db import close_old_connections

    a, j, s = request(b4)
    review(b4, s)
    publish(b4)
    candidate = req.detail(a, s["id"])["candidates"][0]
    count = len(inv.copies(a))

    def accept(_):
        close_old_connections()
        try:
            return req.resolve(a, s["id"], {"printing_id": candidate["id"], "revision": 0})["copy"]["id"]
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(accept, range(2)))
    assert ids == [j["copy_id"], j["copy_id"]]
    assert len(inv.copies(a)) == count


def test_second_provider_cannot_duplicate_same_identity(b4):
    publish(b4)
    p = package()
    p["provider"] = "another-provider"
    p["version"] = "different-source"
    with pytest.raises(ValueError, match="different source mapping"):
        cat.preview(b4["actor"], p)


def test_edit_after_proposal_and_resolution_undo_protects_edits(b4):
    a, j, s = request(b4)
    review(b4, s)
    publish(b4)
    p = req.detail(a, s["id"])["candidates"][0]
    edit = inv.preview(
        a,
        "edit",
        {"id": j["copy_id"], "revision": 0, "attributes": {"notes": "Later private edit"}},
        str(uuid.uuid4()),
    )
    inv.confirm(a, edit["id"])
    with pytest.raises(inv.Conflict):
        req.resolve(a, s["id"], {"printing_id": p["id"], "revision": 0})
    resolved = req.resolve(a, s["id"], {"printing_id": p["id"], "revision": 1})
    edit = inv.preview(
        a,
        "edit",
        {"id": j["copy_id"], "revision": 2, "attributes": {"notes": "Even later edit"}},
        str(uuid.uuid4()),
    )
    inv.confirm(a, edit["id"])
    with pytest.raises(inv.Conflict):
        inv.undo(a, resolved["resolution_op"])
    assert inv.one(a, "copy", j["copy_id"])["notes"] == "Even later edit"


def test_request_after_publication_and_alias_normalization(b4):
    op = publish(b4)
    a, j, s = request(b4, set="  demo ONE ")
    assert s["request"]["state"] == "published"
    assert len(s["candidates"]) == 2
    assert s["request"]["identity_key"] == "synthetic-orbits:en:demo-one"
    assert op["state"] == "published"
