"""Authored nested seller lists; no captured provider content or prices."""

import json

from test_hunter_lots import printing

from pokemon_hunter.beta import catalog_variants as variants
from pokemon_hunter.beta import hunter_lot_parser as parser


def catalog():
    result = []
    for number, kind in [("10", "holo"), ("25", "normal")]:
        parent = dict(
            printing("parent-" + number, "Lapras", number=number),
            set_id="fossil",
            set_name="Fossil",
            edition=None,
            finish=None,
            variant=None,
        )
        desc = dict(type=kind, edition="unlimited")
        edition, finish, variant = variants.physical(desc)
        child = dict(
            parent,
            id="child-" + number,
            edition=edition,
            finish=finish,
            variant=variant,
            attributes=dict(parent_printing_id=parent["id"], physical_variant=desc),
            provenance=json.dumps(
                dict(
                    variant_evidence=dict(
                        parent_id=parent["id"],
                        descriptor=desc,
                        source_descriptor=desc,
                        source_url="https://example.test/catalog",
                        revision="authored-v1",
                        archive_sha256="a" * 64,
                        member="authored.ts",
                        member_sha256="b" * 64,
                        lineage="authored-test-only",
                        source_identity=parent["id"],
                    )
                )
            ),
        )
        result.extend([parent, child])
    return result


def sample():
    return dict(
        itemId="v1|123456789012|0",
        title="Lapras Fossil Unlimited holo and non-holo card group",
        shortDescription="Includes two 1999 Fossil Lapras Holo Unlimited cards and one 1999 Fossil Lapras Non-Holo Unlimited card.",
        description="Authored list:\n- 1999 Fossil Lapras Holo Unlimited (x2):\n  - Set: Fossil\n  - Card Number: 10/62\n\n- 1999 Fossil Lapras Non-Holo Unlimited:\n  - Set: Fossil\n  - Card Number: 25/62\n",
        buyingOptions=["FIXED_PRICE"],
        localizedAspects=[
            dict(name=k, value=v)
            for k, v in [
                ("Set", "Fossil"),
                ("Language", "English"),
                ("Edition", "Unlimited"),
                ("Finish", "Holo, Regular"),
                ("Card Name", "Lapras"),
                ("Card Number", "10/62, 25/62"),
                ("Number of Cards", "3"),
            ]
        ],
    )


def test_nested_numbered_sections_keep_two_physical_allocations():
    raw = sample()
    value = parser.parse(raw, catalog(), detail=raw, complete_candidates=True)
    assert {
        p["printing_id"]: p["included_quantity"] for p in value["proposals"] if p["included_quantity"]
    } == {"child-10": 2, "child-25": 1}
    assert value["included_quantity"] == 3
    for row in value["proposals"]:
        for m in row["mentions"] + row["scope_mentions"]:
            assert value["source_fields"][m["source_field"]][m["start"] : m["end"]] == m["text"]


def test_nested_sections_reject_global_language_and_edition_conflicts():
    for field, value in [("Language", "English, Japanese"), ("Edition", "Unlimited, First Edition")]:
        raw = sample()
        for row in raw["localizedAspects"]:
            if row["name"] == field:
                row["value"] = value
        result = parser.parse(raw, catalog(), detail=raw)
        assert result["included_quantity"] == 0


def test_nested_number_or_quantity_disagreement_is_not_silently_selected():
    raw = sample()
    raw["description"] = raw["description"].replace("Card Number: 10/62", "Card Number: 999/62")
    result = parser.parse(raw, catalog(), detail=raw)
    assert not any(p["printing_id"] == "child-10" and p["included_quantity"] for p in result["proposals"])
    raw = sample()
    raw["shortDescription"] = raw["shortDescription"].replace("two 1999", "three 1999")
    result = parser.parse(raw, catalog(), detail=raw)
    assert not any(p["printing_id"] == "child-10" and p["included_quantity"] for p in result["proposals"])


def test_sections_do_not_join_unindented_attributes_or_photo_only_headings():
    raw = sample()
    raw["description"] = raw["description"].replace("  - Card Number:", "- Card Number:")
    result = parser.parse(raw, catalog(), detail=raw)
    assert result["included_quantity"] == 0
    raw = sample()
    raw["description"] = raw["description"].replace(
        "- 1999 Fossil Lapras Holo", "- Photo example 1999 Fossil Lapras Holo"
    )
    result = parser.parse(raw, catalog(), detail=raw)
    assert not any(p["printing_id"] == "child-10" and p["included_quantity"] for p in result["proposals"])


def test_unrelated_descriptive_mentions_do_not_add_copies_to_sections():
    raw = sample()
    raw["description"] = "Lapras Fossil Unlimited holo and non-holo card group\n" + raw["description"]
    raw["description"] += "\nHighlights:\n- Favorite character: Lapras\n- For Lapras collectors\n"
    result = parser.parse(raw, catalog(), detail=raw)
    assert result["included_quantity"] == 3
    assert len(result["proposals"]) == 2


def test_official_detail_quantities_use_the_existing_selected_contents_projection():
    from pokemon_hunter.beta import listing_check

    raw = sample()
    value = dict(seller_contents=parser.parse(raw, catalog(), detail=raw, complete_candidates=True))
    listing_check._selected_contents(value)
    assert {p["id"]: p["quantity"] for p in value["proposals"]} == {"child-10": 2, "child-25": 1}
    assert value["unknown_contents"] == 0


def descriptive_sample():
    raw = sample()
    raw["title"] = "Pokemon 1999 Fossil Lapras Holo and Non-Holo Unlimited group"
    raw["shortDescription"] = (
        "A collectible Lapras Fossil card group. Featuring two 1999 Fossil Lapras Holo Unlimited cards and one 1999 Fossil Lapras Non-Holo Unlimited card."
    )
    raw["description"] = (
        raw["title"]
        + "\n"
        + raw["shortDescription"]
        + "\n"
        + raw["description"].replace("  - ", "\u00a0 - ")
        + "\n- Special Feature: Shiny holographic finish featuring Lapras\n- Special Feature: Plain non-holo version of Lapras\n- Character: Lapras\n- Collectors: Add these Lapras cards\n"
    )
    return raw


def test_descriptive_and_aggregate_claims_do_not_poison_numbered_sections():
    raw = descriptive_sample()
    value = parser.parse(raw, catalog(), detail=raw, complete_candidates=True)
    assert {
        p["printing_id"]: p["included_quantity"] for p in value["proposals"] if p["included_quantity"]
    } == {"child-10": 2, "child-25": 1}
    assert value["unknown_remainder"] == 0


def test_descriptive_context_does_not_hide_actual_identity_or_quantity_conflicts():
    for before, after in [
        ("Featuring two", "Featuring three"),
        ("10/62, 25/62", "99/62, 25/62"),
        ("10/62, 25/62", "10/99, 25/62"),
        ("Unlimited group", "First Edition group"),
    ]:
        raw = descriptive_sample()
        raw = json.loads(json.dumps(raw).replace(before, after))
        value = parser.parse(raw, catalog(), detail=raw, complete_candidates=True)
        assert value["included_quantity"] < 3, (before, after)


def test_projected_complete_mixed_finish_lot_has_no_false_global_conflict():
    from pokemon_hunter.beta import discovery_comparison as dc
    from pokemon_hunter.beta import shopping_contents

    raw = descriptive_sample()
    raw["description"] += "\nComplete collection of the listed cards. Photos show the cards.\n"
    value = dict(
        title=raw["title"], clues=dc._clues(raw), _contents_source=raw, _contents_kind="official_detail"
    )
    groups = shopping_contents.project(value, catalog())
    assert value["seller_contents"]["included_quantity"] == 3
    assert value["clues"]["conflicts"] == []
    assert not any("Conflicting seller finish claims" in g["reasons"] for g in groups)


def test_review_comparison_keeps_parent_context_for_selected_physical_children(monkeypatch):
    from pokemon_hunter.beta import listing_details, lot_assessment

    raw = descriptive_sample()
    offer = listing_details.details(raw["itemId"], raw)
    cards = [dict(printing_id="child-10", quantity=2), dict(printing_id="child-25", quantity=1)]
    issues, disputed = lot_assessment.seller_constraints(
        [offer], {p["id"]: p for p in catalog()}, {p["printing_id"]: p for p in cards}, 3
    )
    assert not disputed
    assert not any("conflict" in issue.casefold() for issue in issues)


def test_unknown_review_condition_is_unavailable_not_a_claimed_contradiction():
    from pokemon_hunter.beta import listing_details, lot_assessment

    raw = descriptive_sample()
    raw["localizedAspects"].extend(
        [dict(name="Graded", value="No"), dict(name="Card Condition", value="Lightly Played")]
    )
    offer = listing_details.details(raw["itemId"], raw)
    cards = [
        dict(printing_id="child-10", quantity=2, grade="raw", condition="Used"),
        dict(printing_id="child-25", quantity=1, grade="raw", condition="Used"),
    ]
    issues, disputed = lot_assessment.seller_constraints(
        [offer], {p["id"]: p for p in catalog()}, {p["printing_id"]: p for p in cards}, 3
    )
    assert disputed == {"child-10", "child-25"}
    assert any("condition claim has not been matched" in issue for issue in issues)
    assert not any("conflicts with" in issue or "literal grader" in issue for issue in issues)


def test_structured_regular_finish_selects_one_supported_card_without_inventing_lot_quantity():
    entries = [p for p in catalog() if p["collector_number"] == "25"]
    raw = dict(
        itemId="v1|123456789012|0",
        title="Authored Lapras card group",
        shortDescription="Includes Lapras 25/62.",
        localizedAspects=[
            dict(name=k, value=v)
            for k, v in [
                ("Set", "Fossil"),
                ("Language", "English"),
                ("Edition", "Unlimited"),
                ("Finish", "Regular"),
                ("Number of Cards", "3"),
            ]
        ],
    )
    value = parser.parse(raw, entries)
    assert value["included_quantity"] == 1
    assert value["unknown_remainder"] == 2
    chosen = next(p for p in value["proposals"] if p["included_quantity"])
    assert chosen["printing_id"] == "child-25" and chosen["clues"]["finish"] == "normal"
    raw["localizedAspects"] = [a for a in raw["localizedAspects"] if a["name"] != "Finish"]
    raw["shortDescription"] += " Regular customer service."
    inferred = parser.parse(raw, entries)
    assert inferred["included_quantity"] == 1 and inferred["unknown_remainder"] == 2
    selected = next(p for p in inferred["proposals"] if p["included_quantity"])
    assert selected["printing_id"] == "child-25"
    assert selected["variant_selection"]["seller_evidence"]["catalog_finish_inference"]
    # Generic customer-service prose cannot supply missing edition evidence.
    raw["localizedAspects"] = [a for a in raw["localizedAspects"] if a["name"] != "Edition"]
    assert parser.parse(raw, entries)["included_quantity"] == 0


def test_named_family_total_and_subgroup_prose_do_not_invent_cards():
    raw = sample()
    raw["title"] = "Lapras card bundle"
    raw["shortDescription"] = "Four Lapras cards. Two are moderately played. Ships in 2 business days."
    raw["description"] = raw["shortDescription"]
    raw["localizedAspects"] = []
    value = parser.parse(raw, catalog(), detail=raw, complete_candidates=True)
    assert value["seller_stated_totals"] == [4]
    assert value["unresolved_contents"] == []
    assert value["included_quantity"] == 0


def test_named_subtotals_do_not_override_whole_lot_total():
    assert parser._totals(
        "Lot of 6. Includes two Lapras cards and four Moltres cards.", {"Lapras", "Moltres"}
    ) == {6}


def test_scoped_condition_is_retained_without_authenticating_it():
    raw = sample()
    raw["description"] = raw["description"].replace(
        "Card Number: 10/62", "Card Number: 10/62\n  - Condition: Moderately Played"
    )
    raw["conditionDescription"] = "See individual condition claims in the contents list."
    value = parser.parse(raw, catalog(), detail=raw, complete_candidates=True)
    selected = [p for p in value["proposals"] if p["printing_id"] == "child-10"]
    assert selected and selected[0]["clues"]["condition"] == "MP"
    assert value["source_fields"]["official_condition"] == raw["conditionDescription"]
