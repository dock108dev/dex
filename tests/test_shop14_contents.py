"""Fabricated seller evidence only; contents never establish ownership or value."""

import pytest
from test_hunter_lots import entries as entries
from test_hunter_lots import raw

from pokemon_hunter.beta import hunter_lot_parser, listing_details, shopping_contents


def project(entries, **changes):
    value = listing_details.details("v1|123456789012|0", raw(**changes))
    return shopping_contents.project(value, entries)


def test_two_entries_and_duplicate_evidence_keep_physical_quantity(entries):
    contents = project(entries)
    assert len(contents) == 2
    assert [e["quantity"] for e in contents] == [2, 1]
    assert all(e["evidence"] and "seller claim" in e["evidence"][0]["provenance"] for e in contents)
    shopping_contents.validate(contents)
    repeated = project(entries, shortDescription=raw()["shortDescription"] + ";" + raw()["shortDescription"])
    assert [e["quantity"] for e in repeated] == [2, 1]
    assert all(len(e["evidence"]) == 2 for e in repeated)


def test_complete_family_is_not_flattened_or_clipped(entries):
    family = [dict(entries[0], id=f"sibling-{i}", edition=f"edition-{i}") for i in range(65)]
    contents = project(family, shortDescription="1x Charizard Base Set 4/102")
    assert len(contents) == 1
    assert {p["id"] for p in contents[0]["candidates"]} == {p["id"] for p in family}
    assert contents[0]["reasons"]


@pytest.mark.parametrize(
    "text,quantity,reason",
    [
        ("1x Charizard Base Set #999", 1, "collector-number evidence is incomplete"),
        ("1x Charizard Base Set 4/102 holo non holo", 1, "Conflicting seller finish claims"),
        ("Charizard", None, "title mention does not establish per-card multiplicity"),
        ("random mystery Charizard", None, "contents valuation unavailable"),
        ("custom proxy Charizard", None, "contents valuation unavailable"),
    ],
)
def test_uncertain_claims_do_not_establish_contents(entries, text, quantity, reason):
    result = project(entries, title=text, shortDescription="")
    assert len(result) == 1 and result[0]["quantity"] == quantity
    # Explicit quantities remain seller claims when identity or finish conflicts;
    # a name alone must not acquire a default quantity.
    assert any(reason in issue for issue in result[0]["reasons"])


def test_stock_units_remainder_and_included_quantity_remain_distinct(entries):
    result = hunter_lot_parser.parse(
        raw(
            lotSize="12",
            estimatedAvailabilities=[dict(estimatedAvailableQuantity=27)],
            title="lot of 5 cards",
        ),
        entries,
        complete_candidates=True,
    )
    assert (
        result["stock_quantity"],
        result["lot_units"],
        result["seller_stated_total"],
        result["included_quantity"],
        result["unknown_remainder"],
    ) == (27, 12, 5, 3, 2)


def test_contents_annotations_are_bounded_and_never_authoritative(entries):
    content = project(entries)
    content[0]["quantity"] = -1
    with pytest.raises(ValueError):
        shopping_contents.validate(content)
    content = project(entries)
    content[0]["evidence"][0]["text"] = "x" * 100001
    with pytest.raises(ValueError):
        shopping_contents.validate(content)


def test_two_named_title_mentions_are_two_unconfirmed_entries(entries):
    result = project(entries, title="Charizard and Blastoise lot of 2 cards", shortDescription="")
    assert {g["name"] for g in result} == {"charizard", "blastoise"}
    assert all(g["quantity"] is None and g["reasons"] for g in result)
    explicit = project(entries, title="Charizard and Blastoise lot of 3 cards")
    assert len(explicit) == 2 and [g["quantity"] for g in explicit] == [2, 1]
    assert all(any(e["source_field"] == "title" for e in g["evidence"]) for g in explicit)


def test_structured_identity_does_not_hide_other_title_mentions(entries):
    summary = raw(title="Charizard Blastoise Pokemon lot of 3 cards", shortDescription="")
    detail = dict(summary, localizedAspects=[dict(name="Card Name", value="Charizard")])
    value = listing_details.details(summary["itemId"], detail, source_kind="official_detail")
    result = shopping_contents.project(value, entries, summary=summary)
    other = next(g for g in result if g["name"] == "blastoise")
    assert other["quantity"] is None
    assert any(e["source_field"].endswith("title") for e in other["evidence"])
    assert not any(p["included_quantity"] for p in value["seller_contents"]["proposals"])


def test_conflicting_repetitions_remain_one_unresolved_group(entries):
    result = project(entries, shortDescription="2x Charizard Base Set #4; 3x Charizard Base Set #4")
    assert len(result) == 1 and result[0]["quantity"] is None
    assert len(result[0]["evidence"]) == 2 and result[0]["reasons"]


def test_conflicting_structured_count_does_not_reappear_from_title(entries):
    data = raw(title="lot of 3 cards", localizedAspects=[dict(name="Number of Cards", value="5")])
    value = listing_details.details(data["itemId"], data)
    assert value["seller_lot_size"] is None
    contents = shopping_contents.project(value, entries)
    assert value["seller_lot_size"] is None and value["unknown_contents"] is None
    assert all("Conflicting seller-stated card counts" in group["reasons"] for group in contents)


def test_conditional_description_is_not_a_stated_quantity(entries):
    result = project(entries, title="Mixed lot", shortDescription="May contain Charizard Base Set #4")
    assert len(result) == 1 and result[0]["quantity"] is None and result[0]["reasons"]


def test_unrecognized_detail_line_keeps_its_source(entries):
    result = project(entries, shortDescription="1x Unknownmon")
    assert result[0]["quantity"] == 1 and result[0]["candidates"] == []
    assert result[0]["evidence"][0]["provenance"] == "Official detail · seller claim"


def test_operation_local_literal_reuse_keeps_aliases_sets_and_fraction_conflicts(entries):
    from pokemon_hunter.beta import discovery_matching as match

    a = dict(entries[0], attributes={"name_aliases": ["Flame"]}, set_aliases=["First Set"])
    sibling = dict(a, collector_number="4/99", edition="first")
    other = dict(a, attributes={}, set_aliases=[])

    def read():
        return [
            (
                match.name_spans(p, t),
                match.set_spans(p, t),
                match.number_claims(p, t),
                match.evidence(p, {"text": t}),
            )
            for p in (a, sibling, other)
            for t in ("Flame First Set #4/102", "Charizard Base Set #4/99")
        ]

    expected = read()
    with match.local_evidence():
        assert read() == expected
        match.number_claims(a, "Flame First Set #4/102").clear()
        assert read() == expected
    assert match._local.get() is None
