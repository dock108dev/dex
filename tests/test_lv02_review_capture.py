"""Authored evidence tests; no network, real source amounts or customer root."""

import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pokemon_hunter.beta import catalog_variants  # noqa: E402
from scripts.lv02_review_capture import basket_review, exact_candidate  # noqa: E402


def printing(descriptor, product=123):
    ed, finish, variant = catalog_variants.physical(descriptor)
    literal = dict(descriptor, thirdParty={} if product is None else {"tcgplayer": product})
    entry = dict(
        set_id="set",
        collector_number="1",
        language="en",
        edition=ed,
        finish=finish,
        variant=variant,
        catalog_version="v1",
        provenance=json.dumps(dict(variant_evidence=dict(descriptor=descriptor, source_descriptor=literal))),
    )
    return entry, [literal]


def test_exact_ordinary_descriptor_and_literal_product_propose_one_subtype():
    assert exact_candidate(*printing({"type": "holo", "stamp": ["1st-edition"]})) == (
        (123, "1st Edition Holofoil"),
        None,
    )


def test_missing_cross_reference_is_not_invented_physical_ambiguity():
    assert exact_candidate(*printing({"type": "normal", "stamp": ["1st-edition"]}, None)) == (
        (None, "1st Edition"),
        None,
    )


def test_unresolved_parent_stays_unresolved_even_with_one_source_option():
    entry, english = printing({"type": "normal", "stamp": ["1st-edition"]})
    entry["edition"] = None
    assert exact_candidate(entry, english) == (None, "unresolved_catalog_identity")


def test_explicit_galaxy_descriptor_cannot_be_erased_into_normal():
    assert (
        exact_candidate(*printing({"type": "normal", "foil": "galaxy", "stamp": ["1st-edition"]}))[0] is None
    )


def test_changed_physical_identity_is_refused():
    entry, english = printing({"type": "normal", "stamp": ["1st-edition"]})
    entry["finish"] = "holo"
    with pytest.raises(ValueError, match="physical identity conflict"):
        exact_candidate(entry, english)


def test_partial_native_basket_keeps_unknown_item_basis_and_no_public_values():
    basket = dict(
        basket_id="B1",
        stated_quantity=7,
        contents=[dict(pilot_id="P1", quantity=3), dict(pilot_id="P2", quantity=4)],
    )
    public, private = basket_review(
        [basket],
        [dict(pilot_id="P1", printing_id="a"), dict(pilot_id="P2", printing_id="b")],
        {"a": Decimal("1.25")},
    )
    assert public[0]["source_guide_supported_quantity"] == 3
    assert public[0]["source_native_scope"] == "partial_subtotal"
    assert public[0]["eligible_item_total"] is None and public[0]["eligible_item_value_quantity"] == 0
    assert "source_native_subtotal" not in public[0]
    assert private[0]["source_native_subtotal"] == "3.75" and private[0]["normalized_item_total"] is None


def test_empty_basket_evidence_is_unavailable_not_zero_value():
    basket = dict(basket_id="B1", stated_quantity=1, contents=[dict(pilot_id="P1", quantity=1)])
    public, private = basket_review([basket], [dict(pilot_id="P1", printing_id="a")], {})
    assert public[0]["source_native_scope"] == "unavailable"
    assert private[0]["source_native_subtotal"] is None


def test_full_native_sum_does_not_prove_item_only_semantics():
    basket = dict(basket_id="B1", stated_quantity=2, contents=[dict(pilot_id="P1", quantity=2)])
    public, private = basket_review([basket], [dict(pilot_id="P1", printing_id="a")], {"a": Decimal("1.25")})
    assert public[0]["source_native_scope"] == "complete_source_native_sum"
    assert public[0]["eligible_item_total"] is None
    assert private[0]["amount_basis"] == "unknown_shipping_and_tax"
