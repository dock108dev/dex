"""Retained result behavior, real CSRF/account boundaries and additive storage."""

import json
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.db import connection
from django.http import Http404
from django.test import RequestFactory
from test_b2 import apply
from test_broad_goals import REQ, goal, update
from test_migration import snapshot as snapshot
from test_packs import b2 as b2
from test_packs import b3 as b3
from test_packs import b4 as b4
from test_packs import e1 as e1
from test_packs import env as env
from test_packs import ready
from test_sealed_catalog import package, publish
from test_sealed_expansion import expanded

from pokemon_hunter.beta import collection as inv
from pokemon_hunter.beta import pack_research as research
from pokemon_hunter.beta import sealed_catalog as cat
from pokemon_hunter.beta import store


def save(e1, g, **kwargs):
    research.initialize()
    return research.save(e1["actor"], g["id"], goal_version=g["version"], **kwargs)


def post(e1, url, data):
    e1["a"].get("/packs/saved/")
    return e1["a"].post(url, {**data, "csrfmiddlewaretoken": e1["a"].cookies["dex_b1_csrf"].value})


def test_frozen_result_retains_identity_times_ownership_and_changed_gaps(e1):
    g = ready(e1)
    protected = inv.export_data(e1["actor"])
    observations = store.rows("SELECT * FROM sealed_observations")
    with patch("httpx.Client.send", side_effect=AssertionError("No acquisition")):
        key = save(e1, g, species="123", expansion="tcgdex:en:sv03.5")
        initial = research.reopen(e1["actor"], key)
        assert initial["species"] == "123" and initial["expansion"] == "tcgdex:en:sv03.5"
        group = initial["expansions"][0]
        assert group["count"] == 1 and len(group["uncertain"]) == 1
        assert group["uncertain"][0]["membership"] == "unknown"
        assert not group["products"][0]["verified"] and not group["products"][0]["guaranteed_cards_known"]
        original_obs = group["products"][0]["offers"][0]["observations"]
        assert {o["checked_at"] for o in original_obs} == {
            json.loads(o["data"])["checked_at"] for o in observations
        }
        raw = research.one(e1["actor"], key)["snapshot"]
        assert inv.export_data(e1["actor"]) == protected
        pid = next(i for i in g["definition"]["items"] if i["pokemon_dex"] == 123)["printing_ids"][0]
        apply(e1, "add", dict(printing_id=pid, duplicate_policy="allow"))
        # Current public changes/new observations cannot rewrite the saved result.
        inv.execute("UPDATE sealed_memberships SET publication_state='archived'")
        inv.execute("UPDATE sealed_products SET publication_state='archived'")
        ref = g["definition"]["catalog_references"][0]
        inv.execute("UPDATE catalog_imports SET package_hash='changed' WHERE id=%s", [ref["import_id"]])
        connection.close()  # Force a fresh database connection; no memory cache.
        later = research.reopen(
            e1["actor"], key, now=cat.instant(original_obs[0]["checked_at"]) + timedelta(days=10)
        )
        assert later["expansions"][0]["count"] == 1 and later["reference_gaps"]
        assert any("Selected catalog review" in gap for gap in later["reference_gaps"])
        assert all(not o["fresh"] for o in later["expansions"][0]["products"][0]["offers"][0]["observations"])
        assert research.one(e1["actor"], key)["snapshot"] == raw
        assert store.rows("SELECT * FROM sealed_observations") == observations
        page = e1["a"].get(f"/packs/saved/{key}/")
        assert page.status_code == 200 and b"Reference gap:" in page.content
        assert b"Ownership and coverage at save time" in page.content


def test_predecessor_and_server_validation(e1):
    publish(e1, package())
    apply(e1, "goal", REQ)
    first = goal(e1)
    key = save(e1, first)
    publish(e1, expanded())
    apply(e1, "goal_edit", update(first))
    assert research.reopen(e1["actor"], key)["goal"]["version"] == first["version"]
    assert not research.reopen(e1["actor"], key)["expansions"]
    second = next(g for g in inv.goals(e1["actor"]) if g["id"] != first["id"])
    for kwargs in ({"species": "9999"}, {"expansion": "unrelated"}, {"goal_version": "wrong"}):
        with pytest.raises(ValueError):
            research.save(e1["actor"], second["id"], **({"goal_version": second["version"]} | kwargs))
    with pytest.raises(Http404):
        research.save(e1["member"], second["id"], goal_version=second["version"])
    response = post(
        e1, "/packs/save/", {"goal": second["id"], "goal_version": second["version"], "observation": "forged"}
    )
    assert response.status_code == 400


def test_authenticated_ordinary_forms_isolation_csrf_and_selected_remove(e1):
    g = ready(e1)
    research.initialize()
    response = post(
        e1, "/packs/save/", {"goal": g["id"], "goal_version": g["version"], "name": "Whole research"}
    )
    assert response.status_code == 302
    key = response.url.split("/")[-2]
    other = save(e1, g, species="123", research_name="Scyther")
    assert b"Whole research" in e1["a"].get("/packs/saved/").content
    assert b"Whole research" not in e1["b"].get("/packs/saved/").content
    assert e1["b"].get(f"/packs/saved/{key}/").status_code == 404
    e1["b"].get("/packs/saved/")
    token = e1["b"].cookies["dex_b1_csrf"].value
    for url, data in (
        (f"/packs/saved/{key}/remove/", {}),
        (f"/packs/saved/{key}/rename/", {"name": "Hijack"}),
        ("/packs/save/", {"goal": g["id"], "goal_version": g["version"]}),
    ):
        assert e1["b"].post(url, {**data, "csrfmiddlewaretoken": token}).status_code == 404
    assert e1["a"].post(f"/packs/saved/{key}/remove/").status_code == 403
    assert e1["a"].get(f"/packs/saved/{key}/remove/").status_code == 405
    snapshot = research.one(e1["actor"], key)["snapshot"]
    renamed = post(
        e1, f"/packs/saved/{key}/rename/", {"name": "<Saved name>", "next": "https://example.org/"}
    )
    assert renamed.status_code == 302
    assert renamed.url == f"/packs/saved/{key}/"
    assert b"&lt;Saved name&gt;" in e1["a"].get(f"/packs/saved/{key}/").content
    assert research.one(e1["actor"], key)["snapshot"] == snapshot
    assert post(e1, f"/packs/saved/{key}/remove/", {}).status_code == 302
    assert [r["id"] for r in research.listing(e1["actor"])] == [other]


def test_additive_repeatable_migration_and_integrity(e1):
    before = inv.export_data(e1["actor"])
    research.initialize()
    research.initialize()
    assert inv.export_data(e1["actor"]) == before
    key = save(e1, ready(e1))
    inv.execute("UPDATE saved_pack_research SET snapshot='{}' WHERE id=%s", [key])
    with pytest.raises(ValueError, match="integrity"):
        research.reopen(e1["actor"], key)


@pytest.mark.parametrize(
    "key", ["//example.org", "https://example.org/", "../elsewhere", "bad\r\nLocation: https://example.org"]
)
def test_rename_rejects_non_uuid_before_mutation(e1, key):
    from pokemon_hunter.beta import packs_views

    request = RequestFactory().post("/packs/saved/rename/", {"name": "Changed"})
    request.user = e1["owner"]
    with patch.object(research, "rename") as rename:
        response = packs_views.rename(request, key)
    assert response.status_code == 400
    assert not response.has_header("Location")
    rename.assert_not_called()
