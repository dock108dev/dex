"""Bounded seller text, quantity and printing-identity parsing; synthetic inputs only."""

import pytest
from test_hunter_lots import entries as entries
from test_hunter_lots import raw

from pokemon_hunter.beta import (
    hunter_lots as lots,
)


def test_clear_lists_quantities_totals_stock_units_are_separate(entries):
    value = lots.parse(
        raw(lotSize="2", estimatedAvailabilities=[dict(estimatedAvailableQuantity=8)]), entries
    )
    assert [r["quantity"] for r in value["proposals"]] == [2, 1]
    assert [r["included_quantity"] for r in value["proposals"]] == [2, 1]
    assert value["seller_stated_total"] == 3 and value["included_quantity"] == 3
    assert value["stock_quantity"] == 8 and value["lot_units"] == 2
    assert value["unknown_remainder"] == 0 and value["quantity_issues"] == []
    assert value["proposals"][0]["candidates"][0]["image_binding"]["printing_id"] == "charizard"


def test_repeated_descriptions_and_title_mentions_never_multiply_cards(entries):
    text = "2x Charizard Base Set 4/102 English Unlimited Non Holo"
    value = lots.parse(raw(title=text + " lot of 2 cards", shortDescription=text + ";" + text), entries)
    assert len(value["proposals"]) == 1
    assert value["included_quantity"] == 2 and len(value["proposals"][0]["mentions"]) == 3
    value = lots.parse(raw(title="Charizard Base Set 4/102 lot of 2 cards", shortDescription=text), entries)
    assert value["included_quantity"] == 2 and len(value["proposals"]) == 1


def test_conflicting_multiplicity_partial_unindexed_and_photos_only(entries):
    text = "Charizard Base Set 4/102 English Unlimited Non Holo"
    value = lots.parse(raw(shortDescription="2x " + text + "; 3x " + text), entries)
    assert value["included_quantity"] == 0
    assert any("conflicting quantities" in reason for p in value["proposals"] for reason in p["reasons"])
    value = lots.parse(raw(shortDescription="2x Missingmon Unpublished Set; 1x " + text), entries)
    assert value["included_quantity"] == 1 and value["unknown_remainder"] == 2
    assert value["unresolved_contents"][0]["quantity"] == 2
    value = lots.parse(raw(shortDescription="See photos for cards"), entries)
    assert value["included_quantity"] == 0 and value["unknown_remainder"] == 3
    assert "Vague or photos-only contents remain unresolved" in value["quantity_issues"]


def test_siblings_conflicts_and_number_clues_stay_corrections(entries):
    sibling = dict(entries[0], id="holo", finish="holo")
    value = lots.parse(
        raw(shortDescription="2x Charizard Base Set 4/102 English Unlimited"), entries + [sibling]
    )
    assert value["proposals"][0]["included_quantity"] == 0
    assert value["proposals"][0]["candidates_total"] == 2
    value = lots.parse(
        raw(shortDescription="2x Charizard Base Set 4/102 Japanese Unlimited Non Holo"), entries
    )
    assert value["proposals"][0]["printing_id"] is None and value["included_quantity"] == 0
    value = lots.parse(raw(shortDescription="2x Charizard"), entries)
    assert value["proposals"][0]["printing_id"] is None


def test_html_is_text_only_and_parser_work_is_bounded(entries):
    value = lots.parse(
        raw(
            shortDescription='<script>999x Charizard Base Set 4/102</script><ul><li>2x Charizard Base Set 4/102 English Unlimited Non Holo</li></ul><img src="https://evil.test/x">'
        ),
        entries,
    )
    assert value["included_quantity"] == 2
    assert all("evil.test" not in m["text"] for p in value["proposals"] for m in p["mentions"])
    for text, message in (
        ("a" * 65537, "65536"),
        ("word " * 8193, "8192"),
        ("a;" * 401, "400"),
        ("a" * 2049, "2048"),
    ):
        with pytest.raises(ValueError, match=message):
            lots.parse(raw(shortDescription=text), entries)
    with pytest.raises(ValueError, match="100000"):
        lots.parse(raw(title="Lot of 100001 cards"), entries)


def test_future_detail_input_requires_exact_variation_and_deduplicates(entries):
    summary = raw(itemId="v1|123456789012|223456789012")
    detail = dict(summary, description="<p>" + summary["shortDescription"] + "</p>")
    value = lots.parse(summary, entries, detail=detail)
    assert value["detail_used"] and value["included_quantity"] == 3
    with pytest.raises(ValueError, match="different item"):
        lots.parse(summary, entries, detail=dict(detail, itemId="v1|123456789012|323456789012"))


def test_thousands_total_and_quantity_suffix_and_structured_detail(entries):
    value = lots.parse(raw(title="Pokemon lot of 100,000 cards"), entries)
    assert value["seller_stated_total"] == 100000 and value["unknown_remainder"] == 99997
    value = lots.parse(
        raw(
            title="Lot of 2 cards", shortDescription="Charizard 4/102 Base Set English Unlimited Non Holo x2"
        ),
        entries,
    )
    assert value["included_quantity"] == 2
    summary = raw(title="Pokemon collection")
    detail = dict(summary, description="", localizedAspects=[dict(name="Number of cards", value="3")])
    value = lots.parse(summary, entries, detail=detail)
    assert value["seller_stated_total"] == 3


@pytest.mark.parametrize("quantity", ["0x", "1000000x", "1.5x", "qty 0", "x1000001", "-1x", "2xx"])
def test_explicit_invalid_multiplicity_never_falls_back_to_one(entries, quantity):
    value = lots.parse(
        raw(
            title="Lot of 1 cards",
            shortDescription=quantity + " Charizard Base Set 4/102 English Unlimited Non Holo",
        ),
        entries,
    )
    assert value["included_quantity"] == 0
    assert value["quantity_issues"] and value["proposals"][0]["quantity"] is None
