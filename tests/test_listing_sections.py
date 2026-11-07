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
