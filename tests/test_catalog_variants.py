"""Evidenced additive families, frozen meaning, lifecycle and seller boundaries."""

import copy
import json
import uuid
from datetime import date
from unittest.mock import patch

import pytest
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_migration import snapshot as snapshot

from pokemon_hunter.beta import (
    card_groups,
    discovery_comparison,
    effective_collection,
    hunter_catalog,
    market_identity,
    store,
)
from pokemon_hunter.beta import catalog_imports as cat
from pokemon_hunter.beta import catalog_variants as variants
from pokemon_hunter.beta import collection as inv
from pokemon_hunter.beta import price_snapshot_contract as rules


def package(actor, descriptors=None, version="variant-test-v1"):
    parent = next(
        p for p in inv.catalog(actor) if all(p[k] is None for k in ("edition", "finish", "variant"))
    )
    raw = store.rows("SELECT * FROM printings WHERE id=%s", [parent["id"]])[0]
    cards = []
    for value in descriptors or [{"type": "normal"}, {"type": "normal", "stamp": ["1st-edition"]}]:
        cards.append(
            dict(
                parent_id=parent["id"],
                parent_sha256=cat.fingerprint(raw),
                descriptor=value,
                evidence=dict(
                    source_url="https://example.test/retained",
                    revision="synthetic-v1",
                    archive_sha256="a" * 64,
                    member="synthetic.ts",
                    member_sha256="b" * 64,
                    lineage="synthetic-only",
                    source_identity="synthetic-parent",
                    source_descriptor=dict(value, thirdParty={"tcgplayer": 1}),
                ),
            )
        )
    return dict(
        schema_version=variants.SCHEMA,
        game="pokemon",
        set_id=parent["set_id"],
        set_key="synthetic-family",
        set_name=parent["set_name"],
        language="en",
        provider=variants.PROVIDER,
        version=version,
        source_url="https://example.test/retained",
        source_sha256="a" * 64,
        metadata_permission="Synthetic test metadata only",
        image_permission="not-included",
        coverage="partial",
        expected_count=len(cards),
        cards=cards,
    )


def publish(actor, p):
    op = cat.preview(actor, p)
    cat.transition(actor, op["id"], "verify")
    return cat.transition(actor, op["id"], "publish")


def test_additive_idempotent_parent_mappings_set_and_snapshot_identity(b4):
    actor = b4["actor"]
    p = package(actor)
    before = cat.snapshot(p["set_id"])
    mapping = store.rows("SELECT * FROM external_mappings ORDER BY provider,entity_kind,external_id")
    op = publish(actor, p)
    after = cat.snapshot(p["set_id"])
    assert after["sets"] == before["sets"]
    old = {r["id"]: r for r in before["cards"]}
    assert all(old[r["id"]] == r for r in after["cards"] if r["id"] in old)
    assert all(r in store.rows("SELECT * FROM external_mappings") for r in mapping)
    assert len(after["cards"]) == len(before["cards"]) + 2
    assert not op["preview"]["updated"] and not op["preview"]["archived"]
    assert cat.preview(actor, p)["id"] == op["id"]
    assert cat.transition(actor, op["id"], "publish") == op
    p["version"] = "variant-test-v2"
    repeated = cat.preview(actor, p)
    assert not repeated["preview"]["added"] and not repeated["preview"]["updated"]
    publish(actor, p)
    assert len(cat.snapshot(p["set_id"])["cards"]) == len(after["cards"])
    # Same exact identity preserves applicability. Catalog versions still matter.
    parent = next(r for r in inv.catalog(actor) if r["id"] == p["cards"][0]["parent_id"])
    row = dict(
        identity={k: parent.get(k) for k in rules.IDENTITY},
        match_scope="conditional_market",
        grade="raw",
        reference_as_of="2026-10-17",
        as_of=None,
        provider_identity=dict(
            language="en",
            edition="first_edition",
            finish="normal",
            variant="1st Edition",
            number=parent["collector_number"],
            set=parent["set_name"],
        ),
    )
    assert rules.reason(row, parent, date(2026, 10, 17)) == "eligible"
    assert (
        rules.reason(row, dict(parent, catalog_version="changed"), date(2026, 10, 17))
        == "rejected_installed_identity"
    )
    child = next(r for r in inv.catalog(actor) if r.get("parent_printing_id") == parent["id"])
    assert rules.reason(row, child, date(2026, 10, 17)) != "eligible"
    assert "legacy_id" not in json.loads(child["provenance"])


@pytest.mark.parametrize(
    "value,edition,finish",
    [
        ({"type": "normal"}, None, "normal"),
        ({"type": "holo", "stamp": ["1st-edition"]}, "first_edition", "holo"),
        ({"type": "normal", "foil": "galaxy"}, None, None),
        ({"type": "normal", "foil": "galaxy", "stamp": ["1st-edition"]}, "first_edition", None),
        ({"type": "normal", "subtype": "1999-2000-copyright"}, None, "normal"),
        ({"type": "normal", "size": "jumbo", "stamp": ["25th-celebration"]}, None, "normal"),
    ],
)
def test_literal_specials_unknowns_and_no_market_inheritance(value, edition, finish):
    e, f, literal = variants.physical(value)
    assert (e, f) == (edition, finish) and json.loads(literal) == value
    p = dict(language="en", edition=e, finish=f, variant=literal)
    if set(value) - {"type", "stamp"}:
        assert not any(market_identity.compatible(p, *pair) for pair in market_identity.SUBTYPES.values())
    if edition is None:
        assert "edition not established" in variants.label(value)


@pytest.mark.parametrize(
    "value",
    [
        {"type": "normal", "foil": "galaxy", "stamp": ["no-stamp"]},
        {"type": "holo", "foil": "galaxy"},
        {"type": "unknown"},
        {"type": "normal", "languages": ["ja"]},
        {"type": "normal", "stamp": ["25th-celebration"]},
        {"type": "normal", "subtype": "1999-2000-copyright", "stamp": ["1st-edition"]},
    ],
)
def test_unknown_or_contradictory_physical_claim_refused(value):
    with pytest.raises(ValueError):
        variants.descriptor(value)


def test_stale_review_external_conflict_and_transactional_failure(b4):
    actor = b4["actor"]
    p = package(actor)
    op = cat.preview(actor, p)
    cat.transition(actor, op["id"], "verify")
    before = cat.snapshot(p["set_id"])
    original = cat.write
    calls = []

    def failing(table, row):
        original(table, row)
        calls.append(table)
        if len(calls) == 2:
            raise RuntimeError("Synthetic transactional failure")

    with patch.object(cat, "write", failing), pytest.raises(RuntimeError):
        cat.transition(actor, op["id"], "publish")
    assert cat.snapshot(p["set_id"]) == before
    assert cat.get(actor, op["id"])["state"] == "verified"
    inv.execute(
        "UPDATE catalog_sets SET catalog_version='later-owner-publication' WHERE id=%s", [p["set_id"]]
    )
    with pytest.raises(inv.Conflict):
        cat.transition(actor, op["id"], "publish")
    inv.execute(
        "UPDATE catalog_sets SET catalog_version=%s WHERE id=%s",
        [before["sets"][0]["catalog_version"], p["set_id"]],
    )
    child = next(
        r for r in cat.rows_for(cat.validate(p))[1] if r["id"] not in {c["id"] for c in before["cards"]}
    )
    provenance = json.loads(child["provenance"])
    inv.execute(
        "INSERT INTO external_mappings VALUES(%s,'printing',%s,%s)",
        [provenance["provider"], provenance["external_id"], p["cards"][0]["parent_id"]],
    )
    with pytest.raises(ValueError, match="mapping conflict"):
        cat.rows_for(cat.validate(p))


def test_collection_frozen_goals_search_numbered_counts_and_referenced_rollback(b4):
    actor = b4["actor"]
    p = package(actor)
    parent_id = p["cards"][0]["parent_id"]
    add = inv.preview(
        actor, "add", dict(printing_id=parent_id, attributes={}, duplicate_policy="allow"), str(uuid.uuid4())
    )
    inv.confirm(actor, add["id"])
    goal = inv.preview(
        actor,
        "goal",
        dict(name="Frozen parent goal", goal_kind="custom", printing_ids=[parent_id], policy="catalog"),
        str(uuid.uuid4()),
    )
    inv.confirm(actor, goal["id"])
    copies = inv.copies(actor)
    goals = store.rows("SELECT * FROM collection_goals")
    progress = inv.goals(actor)
    before_groups = card_groups.build_groups(inv.catalog(actor))
    op = publish(actor, p)
    assert inv.copies(actor) == copies
    assert store.rows("SELECT * FROM collection_goals") == goals
    assert inv.goals(actor) == progress
    family = [r for r in inv.catalog(actor) if r.get("parent_printing_id") == parent_id]
    assert len(family) == 2 and all(r["id"] not in {c["printing_id"] for c in copies} for r in family)
    assert len(card_groups.build_groups(inv.catalog(actor))["groups"]) == len(before_groups["groups"])
    assert any(r["id"] == family[0]["id"] for r in inv.catalog(actor, "edition not established"))
    exact = next(r for r in family if r["edition"] == "first_edition")
    entry = inv.preview(
        actor,
        "add",
        dict(printing_id=exact["id"], attributes={}, duplicate_policy="allow"),
        str(uuid.uuid4()),
    )
    inv.confirm(actor, entry["id"])
    assert any(c["printing_id"] == exact["id"] for c in inv.export_data(actor)["copies"])
    with pytest.raises(inv.Conflict, match="collection activity"):
        cat.transition(actor, op["id"], "rollback")
    assert cat.get(actor, op["id"])["state"] == "published"


def test_safe_rollback_and_republication_without_duplicate(b4):
    actor = b4["actor"]
    p = package(actor)
    before = cat.snapshot(p["set_id"])
    op = publish(actor, p)
    cat.transition(actor, op["id"], "rollback")
    assert [r for r in cat.snapshot(p["set_id"])["cards"] if r["publication_state"] == "published"] == before[
        "cards"
    ]
    cat.transition(actor, op["id"], "publish")
    assert len(cat.snapshot(p["set_id"])["cards"]) == len(before["cards"]) + 2


def test_seller_family_ambiguity_exact_choice_and_reference_independence(b4):
    actor = b4["actor"]
    p = package(actor)
    publish(actor, p)
    parent_id = p["cards"][0]["parent_id"]
    family = [
        r for r in inv.catalog(actor) if r["id"] == parent_id or r.get("parent_printing_id") == parent_id
    ]
    parent = next(r for r in family if r["id"] == parent_id)
    title = f"{parent['name']} #{parent['collector_number']} {parent['set_name']}"
    broad = discovery_comparison._clues(dict(title=title))
    detailed = discovery_comparison._clues(dict(title=title + " English 1st Edition Normal"))
    assert len(discovery_comparison._matches(family, broad)) == 3
    exact = discovery_comparison._matches(family, detailed)
    assert len(exact) == 1 and exact[0]["edition"] == "first_edition"
    special = discovery_comparison._clues(dict(title=title + " English 1st Edition Normal galaxy"))
    assert len(discovery_comparison._matches(family, special)) != 1
    refs = hunter_catalog.ReferenceIndex([dict(_snapshot_version="synthetic", printing_id=parent_id)])
    assert not refs.for_printing(exact[0])
    assert len(refs.for_printing(parent)) == 1


def test_identical_existing_variant_reused_and_descriptor_tamper_refused(b4):
    actor = b4["actor"]
    p = package(actor)
    _, rows = cat.rows_for(cat.validate(p))
    parent_ids = {r["id"] for r in cat.snapshot(p["set_id"])["cards"]}
    child = next(r for r in rows if r["id"] not in parent_ids)
    # A separately mapped existing physical identity is reused, never duplicated.
    child["id"] = str(uuid.uuid4())
    cat.write("printings", child)
    op = cat.preview(actor, p)
    assert len(op["preview"]["added"]) == 1
    modified = copy.deepcopy(p)
    modified["cards"][0]["descriptor"]["size"] = "jumbo"
    with pytest.raises(ValueError, match="differs"):
        cat.validate(modified)


def test_old_normal_attestation_cannot_claim_new_children(b4):
    actor = b4["actor"]
    p = package(actor)
    parent_id = p["cards"][0]["parent_id"]

    def apply(kind, request):
        op = inv.preview(actor, kind, request, str(uuid.uuid4()))
        return inv.confirm(actor, op["id"])

    apply("add", dict(printing_id=parent_id, attributes={}, duplicate_policy="allow"))
    current = effective_collection.project(actor)
    row = next(r for r in current["cards"] if parent_id in r["printing_ids"])
    apply("card_defaults", dict(card_ids=[row["id"]], quantity=1, variant="normal"))
    before = effective_collection.project(actor)
    before_owned = {r["id"]: r.get("owned_variant_printing_ids", []) for r in before["cards"]}
    publish(actor, p)
    after = effective_collection.project(actor)
    assert {r["id"]: r.get("owned_variant_printing_ids", []) for r in after["cards"]} == before_owned
    group = next(
        g
        for g in card_groups.list_groups(actor, {"scope": "catalog"})["groups"]
        if g["collector_number"] == row["number"] and g["set_name"] == row["set_name"]
    )
    assert group["evidenced_variant_count"] == 2
    assert group["variant_count"] == 2 and group["catalog_identity_count"] == 3
    detail = card_groups.detail(actor, group["id"])
    assert not any(v.get("declared_variant_owned") for v in detail["variants"] if v["parent_printing_id"])
    detailed = card_groups.list_groups(actor, {"scope": "catalog", "q": row["name"] + " 1st Edition"})
    assert group["id"] in {g["id"] for g in detailed["groups"]}


def test_frozen_review_membership_survives_additive_heads_and_later_growth(b4):
    from test_collection_goals import create, seed

    from pokemon_hunter.beta import catalog_reconcile, collection_goals

    actor = b4["actor"]
    catalog_reconcile.publish_all(actor)
    _, source = seed(b4)
    frozen = create(b4, source)
    original_row = inv.one(actor, "goal", frozen["id"])
    original_progress = inv.goals(actor, goal_id=frozen["id"], include_updates=False)[0]
    p = package(actor)
    publish(actor, p)
    assert inv.one(actor, "goal", frozen["id"]) == original_row
    assert inv.goals(actor, goal_id=frozen["id"], include_updates=False)[0] == original_progress
    successor = create(b4, source, before=frozen)
    successor_definition = copy.deepcopy(successor["definition"])
    successor_progress = inv.goals(actor, goal_id=successor["id"], include_updates=False)[0]
    current_ids = {pid for i in successor_definition["items"] for pid in i["printing_ids"]}
    added = {r["id"] for r in inv.catalog(actor) if r.get("parent_printing_id") == p["cards"][0]["parent_id"]}
    assert added <= current_ids
    later = package(actor, [{"type": "holo", "stamp": ["1st-edition"]}], version="later-variant-v2")
    assert later["cards"][0]["parent_id"] == p["cards"][0]["parent_id"]
    publish(actor, later)
    assert inv.goals(actor, goal_id=successor["id"], include_updates=False)[0] == successor_progress
    collection_goals.validate(successor_definition, source)
    forged = copy.deepcopy(successor_definition)
    new_id = next(
        r["id"]
        for r in inv.catalog(actor)
        if r.get("parent_printing_id") == p["cards"][0]["parent_id"] and r["id"] not in added
    )
    item = next(i for i in forged["items"] if p["cards"][0]["parent_id"] in i["printing_ids"])
    item["printing_ids"].append(new_id)
    with pytest.raises(ValueError, match="Forged"):
        collection_goals.validate(forged, source)
