"""Evidence, exact selection, exclusions and conservation on authored inputs."""

import pytest
from lv04_cases import CASES, B, C, case, catalog

from pokemon_hunter.beta import hunter_lot_parser as parser


def selected(value):
    result = {}
    for row in value["proposals"]:
        if row["included_quantity"]:
            result[row["printing_id"]] = result.get(row["printing_id"], 0) + row["included_quantity"]
    return result


@pytest.mark.parametrize("sample", CASES, ids=lambda c: c["key"])
def test_authored_identity_quantity_and_provenance(sample):
    value = parser.parse(sample["raw"], catalog(), detail=sample["detail"])
    assert selected(value) == sample["expected"]
    assert value["seller_stated_total"] == sample["total"]
    known = sum(sample["expected"].values())
    assert value["included_quantity"] == value["physically_selected_quantity"] == known
    assert value["parent_identified_quantity"] >= known
    if sample["key"] == "quantity_conflict":
        assert value["unknown_remainder"] is None
    elif sample["total"] is not None:
        assert value["unknown_remainder"] + known == sample["total"]
    else:
        assert value["unknown_remainder"] is None
    for row in value["proposals"]:
        assert row["included_quantity"] <= (row["quantity"] or 0)
        for m in row["mentions"] + row["scope_mentions"]:
            assert value["source_fields"][m["source_field"]][m["start"] : m["end"]] == m["text"]
    for m in value["total_mentions"]:
        assert value["source_fields"][m["source_field"]][m["start"] : m["end"]] == m["text"]
    if sample["category"] == "clear":
        assert value["contents_state"] == "resolved"
    else:
        assert value["contents_state"] == "unresolved"


def test_correct_total_is_not_complete_contents_and_no_invented_set_list():
    value = parser.parse(case("set", "Complete Base Set", {}, total=102)["raw"], catalog())
    assert value["seller_stated_total"] == 102
    assert value["included_quantity"] == 0 and value["unknown_remainder"] == 102


def test_total_conflict_and_overallocation_never_reconcile():
    sample = case("conflict", f"2x {C}; 1x {B}; total cards: 4", {}, total=3)
    value = parser.parse(sample["raw"], catalog(), detail=sample["detail"])
    assert value["seller_stated_total"] is None and value["unknown_remainder"] is None
    sample = case("over", f"2x {C}; 1x {B}", {}, total=2)
    value = parser.parse(sample["raw"], catalog(), detail=sample["detail"])
    assert value["unknown_remainder"] is None and value["quantity_issues"]


def test_alternatives_have_one_parent_quantity_and_no_price_or_model_inputs():
    sample = next(c for c in CASES if c["key"] == "missing_finish")
    value = parser.parse(sample["raw"], catalog(), detail=sample["detail"])
    assert value["parent_identified_quantity"] == 3
    assert value["included_quantity"] == 0
    assert len(value["proposals"]) == 1 and value["proposals"][0]["quantity"] == 3
    assert value["proposals"][0]["candidates_total"] >= 2
    assert not {"price", "range", "subtotal"} & value.keys()


def test_stock_lots_offered_and_physical_cards_per_lot():
    sample = case(
        "stock",
        f"2x {C}; 1x {B}; Stock quantity: 8",
        {},
        title="Lot of 3 lots of 3 cards",
        lotSize="12",
        estimatedAvailabilities=[dict(estimatedAvailableQuantity=8)],
    )
    value = parser.parse(sample["raw"], catalog(), detail=sample["detail"])
    assert value["seller_stated_total"] == value["seller_lots_offered"] == 3
    assert value["stock_quantity"] == 8 and value["lot_units"] == 12
    assert value["included_quantity"] == 3 and not value["unresolved_contents"]


def test_structured_identity_aspects_and_span_provenance():
    sample = case(
        "aspects",
        "",
        {},
        total=1,
        aspects=[
            dict(name=k, value=v)
            for k, v in [
                ("Card Name", "Blastoise"),
                ("Card Number", "2/102"),
                ("Set", "Base Set"),
                ("Language", "English"),
                ("Edition", "Unlimited"),
                ("Finish", "Non Holo"),
            ]
        ],
    )
    value = parser.parse(sample["raw"], catalog(), detail=sample["detail"])
    assert selected(value) == {"b": 1}
    row = value["proposals"][0]
    for m in row["mentions"] + row["scope_mentions"]:
        assert value["source_fields"][m["source_field"]][m["start"] : m["end"]] == m["text"]


def test_structured_grade_and_conflicting_global_traits_withhold_selection():
    for aspects in ([dict(name="Graded", value="Yes")], [dict(name="Language", value="Japanese")]):
        sample = case("conflict", f"3x {C}", {}, aspects=aspects)
        value = parser.parse(sample["raw"], catalog(), detail=sample["detail"])
        assert selected(value) == {}
    sample = case("raw", f"3x {C}", {}, aspects=[dict(name="Graded", value="No")])
    assert selected(parser.parse(sample["raw"], catalog(), detail=sample["detail"])) == {"c": 3}


def test_bounded_aspects_and_no_identity_from_photo_caption():
    sample = case("large", "", {}, aspects=[dict(name="Contents", value="x" * 501)])
    with pytest.raises(ValueError, match="limit"):
        parser.parse(sample["raw"], catalog(), detail=sample["detail"])


def test_scope_name_cannot_turn_unrelated_prose_into_cards():
    sample = case(
        "scope",
        "All cards are Charizard Base Set 4/102 English Unlimited Non Holo. Ships tomorrow. Thanks for looking.",
        {},
        total=3,
    )
    value = parser.parse(sample["raw"], catalog(), detail=sample["detail"])
    assert selected(value) == {} and value["unknown_remainder"] == 3


def test_broader_repetition_cannot_hide_wrong_number_or_condition_conflict():
    for title in ("3x Charizard #999", "3x Charizard Base Set #999 English Unlimited Non Holo"):
        sample = case("conflict", f"3x {C}", {}, title=title)
        value = parser.parse(sample["raw"], catalog(), detail=sample["detail"])
        assert selected(value) == {}


def test_catalog_punctuation_and_conjunctions_are_not_list_delimiters():
    from test_hunter_lots import printing

    cards = [
        printing("mime", "Mr. Mime", number="6/64"),
        printing("tag", "Reshiram and Zekrom", number="157/236"),
    ]
    sample = case(
        "names",
        "1x Mr. Mime Base Set 6/64 English Unlimited Non Holo and 1x Reshiram and Zekrom Base Set 157/236 English Unlimited Non Holo",
        {},
        total=2,
    )
    value = parser.parse(sample["raw"], cards, detail=sample["detail"])
    assert selected(value) == {"mime": 1, "tag": 1}


@pytest.mark.parametrize("count", ["0", "zero", "-2", "1.5", "1000001"])
def test_invalid_natural_quantities_never_default_to_one(count):
    sample = case("invalid", f"{count} {C}", {}, total=3)
    assert selected(parser.parse(sample["raw"], catalog(), detail=sample["detail"])) == {}


@pytest.mark.parametrize("text,count", [(f"a pair of {C}", 2), (f"twenty-one {C}", 21), (f"{C} (2)", 2)])
def test_natural_count_variants(text, count):
    sample = case("natural", text, {}, total=count)
    assert selected(parser.parse(sample["raw"], catalog(), detail=sample["detail"])) == {"c": count}


def test_incidental_without_does_not_exclude_a_card_but_named_negation_does():
    sample = case("packaging", f"3x {C} without sleeves", {}, total=3)
    assert selected(parser.parse(sample["raw"], catalog(), detail=sample["detail"])) == {"c": 3}
    for prefix in ("No", "Without", "Not"):
        sample = case("negative", f"{prefix} {C}", {}, total=3)
        assert selected(parser.parse(sample["raw"], catalog(), detail=sample["detail"])) == {}
