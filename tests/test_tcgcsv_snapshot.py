"""Offline conditional market identity, ambiguity and value-boundary checks."""

from copy import deepcopy
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from pokemon_hunter.beta import price_snapshot_contract as rules
from pokemon_hunter.beta import tcgcsv_snapshot as importer


def inputs():
    p = dict(
        id=str(uuid4()),
        set_id=str(uuid4()),
        set_name="Jungle",
        name="Scyther",
        collector_number="10",
        language="en",
        edition=None,
        finish=None,
        variant=None,
        catalog_version="test-catalog",
        attributes=dict(dex_eligible=True, pokemon_dex=123),
    )
    product = dict(
        productId=1,
        categoryId=3,
        groupId=635,
        name="Scyther (10)",
        url="https://www.tcgplayer.com/product/1",
        extendedData=[dict(name="Number", value="010/64")],
    )
    products = {g: [] for g in importer.GROUPS.values()}
    prices = deepcopy(products)
    products[635] = [product]
    prices[635] = [
        dict(productId=1, subTypeName="Unlimited Holofoil", marketPrice=Decimal("10.75")),
        dict(productId=1, subTypeName="1st Edition Holofoil", marketPrice=Decimal("90.50")),
    ]
    return p, products, prices


def build(p, products, prices):
    return importer.build(
        {p["id"]: p},
        products,
        prices,
        built_at="2026-10-09T20:05:19+00:00",
        captured_at="2026-10-10T16:00:00+00:00",
    )


def test_unknown_edition_uses_labelled_conditional_reference_without_catalog_mutation():
    p, products, prices = inputs()
    before = deepcopy(p)
    package, report = build(p, products, prices)
    row = package["records"][0]
    assert row["provider_identity"]["variant"] == "Unlimited Holofoil"
    assert row["value"] == "10.75" and row["as_of"] is None
    assert row["match_scope"] == "conditional_market"
    assert p == before and report["records"] == 1
    assert rules.reason(row, p, date(2026, 10, 10)) == "eligible"
    assert not package["contract"]["rights"]["immutable_save"]


def test_known_first_edition_selects_its_own_subtype_and_value():
    p, products, prices = inputs()
    p.update(edition="1st-edition", finish="holo", variant='{"type":"holo","stamp":["1st-edition"]}')
    package, _ = build(p, products, prices)
    row = package["records"][0]
    assert row["value"] == "90.50"
    assert row["provider_identity"]["variant"] == "1st Edition Holofoil"
    assert rules.reason(row, p, date(2026, 10, 10)) == "eligible"


@pytest.mark.parametrize(
    "mutation", ["name", "number", "duplicate", "zero", "null", "special_variant", "language", "finish"]
)
def test_conflicts_and_missing_prices_cannot_be_admitted(mutation):
    p, products, prices = inputs()
    if mutation == "name":
        products[635][0]["name"] = "Scyther ex"
    elif mutation == "number":
        products[635][0]["extendedData"][0]["value"] = "26/64"
    elif mutation == "duplicate":
        products[635].append(deepcopy(products[635][0]))
    elif mutation == "zero":
        prices[635][0]["marketPrice"] = Decimal(0)
    elif mutation == "null":
        prices[635][0]["marketPrice"] = None
    elif mutation == "special_variant":
        p["variant"] = '{"type":"holo","stamp":["no-symbol"]}'
    elif mutation == "language":
        p["language"] = "ja"
    else:
        p["finish"] = "reverse"
    with pytest.raises(ValueError, match="nonempty"):
        build(p, products, prices)


def test_conditional_scope_cannot_be_transferred_to_a_graded_field():
    p, products, prices = inputs()
    package, _ = build(p, products, prices)
    package["contract"]["fields"]["marketPrice"]["grade"] = "8"
    with pytest.raises(ValueError, match="Conditional market scope"):
        rules.validate(package, {p["id"]: p})


def test_catalog_change_and_future_build_still_reject():
    p, products, prices = inputs()
    package, _ = build(p, products, prices)
    p["edition"] = "1st-edition"
    assert rules.reason(package["records"][0], p, date(2026, 10, 10)) == "rejected_installed_identity"
    with pytest.raises(ValueError, match="October 2026 publisher build"):
        importer.build(
            {p["id"]: p},
            products,
            prices,
            built_at="2026-10-11T20:05:19+00:00",
            captured_at="2026-10-10T16:00:00+00:00",
        )


def test_species_scope_includes_dark_cards_without_changing_goal_eligibility():
    p, products, prices = inputs()
    p["attributes"]["dex_eligible"] = False
    package, report = build(p, products, prices)
    assert report["priority_printings"] == 1 and len(package["records"]) == 1
    assert p["attributes"]["dex_eligible"] is False


def test_non_pokemon_catalog_entries_are_excluded_from_species_scope():
    p, products, prices = inputs()
    trainer = deepcopy(p)
    trainer["id"] = str(uuid4())
    trainer["attributes"]["pokemon_dex"] = None
    _, report = importer.build(
        {p["id"]: p, trainer["id"]: trainer},
        products,
        prices,
        built_at="2026-10-09T20:05:19+00:00",
        captured_at="2026-10-10T16:00:00+00:00",
    )
    assert report["priority_printings"] == 1
