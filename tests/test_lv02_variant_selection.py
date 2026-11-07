"""Authored physical families, scoped seller assertions and quantity conservation."""

import copy
import json
from datetime import date

import pytest
from test_hunter_lots import printing

from pokemon_hunter.beta import catalog_variants as variants
from pokemon_hunter.beta import hunter_lot_parser as parser
from pokemon_hunter.beta import lot_guides


def family():
    parent = dict(
        printing("parent"),
        edition=None,
        finish=None,
        variant=None,
        catalog_version="authored-v1",
        publication_state="published",
    )
    children = []
    for kind in ["normal", "holo"]:
        descriptor = dict(type=kind, stamp=["1st-edition"])
        edition, finish, variant = variants.physical(descriptor)
        evidence = dict(
            source_url="https://example.test/authored",
            revision="authored-v1",
            archive_sha256="a" * 64,
            member="authored.ts",
            member_sha256="b" * 64,
            lineage="authored-test-only",
            source_identity="parent",
            source_descriptor=descriptor,
            descriptor=descriptor,
            parent_id="parent",
        )
        children.append(
            dict(
                parent,
                id=kind,
                edition=edition,
                finish=finish,
                variant=variant,
                attributes=dict(parent_printing_id="parent", physical_variant=descriptor),
                provenance=json.dumps(dict(variant_evidence=evidence)),
            )
        )
    return [parent, *children]


def parse(text, title="Pokemon lot of 2 cards", entries=None):
    return parser.parse(dict(title=title, shortDescription=text), entries or family())


def test_unknown_edition_retains_alternatives_without_multiplying_cards():
    result = parse("2x Charizard Base Set 4/102 English")
    line = result["proposals"][0]
    assert line["quantity"] == 2 and line["included_quantity"] == 0
    assert line["printing_id"] is None
    binding = line["variant_selection"]
    assert binding["selected_child_id"] is None and binding["membership"] == "non_exhaustive"
    assert len(binding["alternatives"]) == 2
    assert result["unknown_remainder"] == 2
    assert lot_guides.family_alternatives(result, family(), [], date(2026, 11, 4))[0]["quantity"] == 2


def test_explicit_variant_and_evidence_scope():
    result = parse("2x Charizard Base Set 4/102 English First Edition Non Holo")
    line = result["proposals"][0]
    assert line["printing_id"] == "normal" and line["included_quantity"] == 2
    binding = line["variant_selection"]
    assert binding["selected_child_id"] == "normal"
    assert binding["allocations"] == [dict(child_id="normal", quantity=2)]
    assert binding["seller_evidence"]["scope"] == "this content line only"
    assert len(binding["alternatives"]) == 2


@pytest.mark.parametrize(
    "text",
    [
        "2x Charizard Base Set 4/102 First Edition Non Holo",
        "2x Charizard Base Set 4/102 English Non Holo",
        "2x Charizard Base Set 4/102 English First Edition Unlimited Non Holo",
    ],
)
def test_missing_or_conflicting_traits_never_select(text):
    result = parse(text)
    assert all(not p["included_quantity"] for p in result["proposals"])
    assert all(
        not p["variant_selection"]["selected_child_id"] for p in result["proposals"] if p["variant_selection"]
    )


def test_unrelated_edition_mention_does_not_apply_to_line():
    result = parse("2x Charizard Base Set 4/102 English Non Holo; first edition collection")
    assert result["included_quantity"] == 0


def test_explicit_mixed_finish_allocation_and_repetition():
    text = "1x Charizard Base Set 4/102 English First Edition Non Holo; 1x Charizard Base Set 4/102 English First Edition Holo"
    result = parse(text)
    assert result["included_quantity"] == 2 and result["unknown_remainder"] == 0
    assert {p["printing_id"] for p in result["proposals"]} == {"normal", "holo"}
    result = parse(
        "2x Charizard Base Set 4/102 English First Edition Non Holo; 2x Charizard Base Set 4/102 English First Edition Non Holo"
    )
    assert result["included_quantity"] == 2 and len(result["proposals"]) == 1


def test_contradictory_title_clears_selection():
    result = parse(
        "2x Charizard Base Set 4/102 English First Edition Non Holo",
        title="2 cards Charizard Base Set 4/102 English First Edition Holo",
    )
    assert result["included_quantity"] == 0
    assert result["proposals"][0]["variant_selection"]["selected_child_id"] is None


def test_family_revalidation_stale_identity_cross_parent_and_unsupported_foil():
    rows = family()
    original = variants.family_projection(rows[0], rows[1:])
    changed = copy.deepcopy(rows)
    changed[0]["catalog_version"] = "new"
    with pytest.raises(ValueError, match="changed"):
        variants.family_projection(changed[0], changed[1:], expected=original)
    changed = copy.deepcopy(rows)
    changed[1]["provenance"] = changed[1]["provenance"].replace(
        '"parent_id": "parent"', '"parent_id": "other"'
    )
    assert (
        variants.family_projection(changed[0], changed[1:])["alternatives"][1]["status"]
        == "catalog_relation_requires_review"
    )
    changed = copy.deepcopy(rows)
    changed[1]["attributes"]["physical_variant"]["foil"] = "galaxy"
    result = variants.family_projection(changed[0], changed[1:])
    assert (
        next(a for a in result["alternatives"] if a["child_id"] == "normal")["status"]
        == "catalog_relation_requires_review"
    )
    assert changed[1]["attributes"]["physical_variant"]["foil"] == "galaxy"


def test_distinct_numbered_families_never_join_and_single_child_does_not_choose():
    rows = family()
    rows[1]["collector_number"] = "25/62"
    result = variants.family_projection(rows[0], rows[1:])
    assert (
        next(a for a in result["alternatives"] if a["child_id"] == "normal")["status"]
        == "catalog_relation_requires_review"
    )
    result = parse("2x Charizard Base Set 4/102 English", entries=family()[:2])
    assert result["included_quantity"] == 0


def test_original_numbered_finish_is_catalog_evidence_not_a_seller_claim():
    result = parse("2x Charizard Base Set 4/102 English First Edition")
    line = result["proposals"][0]
    assert line["printing_id"] == "holo" and line["included_quantity"] == 2
    evidence = line["variant_selection"]["seller_evidence"]
    assert evidence["catalog_finish_inference"]
    assert result["unknown_remainder"] == 0
