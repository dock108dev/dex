"""Authored native-source preparation; no acquired prices or source permission."""

import copy
from datetime import date

import pytest
from test_tcgcsv_offline import case as case
from test_tcgcsv_offline import prepare, save

from pokemon_hunter.beta import lot_guides
from pokemon_hunter.beta import valuation_evidence as evidence


def native(case):
    policy = case["manifest"]["contract"]
    policy["schema"] = "dex-price-contract-v3"
    policy["valuation"] = dict(
        basis=evidence.NATIVE,
        condition=None,
        amount_basis=evidence.NATIVE_AMOUNT,
        native_money=dict(evidence.NATIVE_MONEY),
        ceiling_applicable=False,
        qualification="reviewed",
        qualification_review="Authored native preparation semantics only",
        estimator=None,
        sale_origins=[],
    )
    for pid, printing in case["entries"].items():
        printing["edition"] = "unlimited"
        policy["mappings"][pid]["identity"]["edition"] = "unlimited"
        policy["mappings"][pid]["provider_identity"]["edition"] = "unlimited"
        policy["mappings"][pid]["provider_identity"]["variant"] = "Unlimited"
    for row in case["prices"]:
        row["subTypeName"] = "Unlimited"
    for binding in case["manifest"]["bindings"]:
        binding["sub_type_name"] = "Unlimited"
    save(case)
    return policy


def test_offline_native_preparation_retains_unknown_basis_and_exact_contract(case):
    policy = native(case)
    before = copy.deepcopy(case)
    package, report = prepare(case)
    assert case == before
    assert report["eligible_printings"] == 3
    assert package["contracts"][policy["review_id"]]["contract"] == policy
    for row in package["records"]:
        assert row["evidence"]["schema"] == evidence.NATIVE_SCHEMA
        assert row["evidence"]["native_money"] == evidence.NATIVE_MONEY
        assert row["condition"] is None and not row["ceiling_applicable"]
        assert row["as_of"] is None
        assert row["reference_as_of"] == "2026-10-16"
        assert row["value"] == row["original_money"] == "2.5"
        printing = case["entries"][row["printing_id"]]
        assert lot_guides.cells(dict(printing, provenance="{}"), [row], date(2026, 10, 17))["raw"] is None


def test_offline_native_preparation_does_not_complete_unknown_edition(case):
    native(case)
    case["entries"]["printing-1"]["edition"] = None
    case["manifest"]["contract"]["mappings"]["printing-1"]["identity"]["edition"] = None
    package, report = prepare(case)
    assert report["eligible_printings"] == 2
    assert all(row["printing_id"] != "printing-1" for row in package["records"])


def test_adapter_cannot_assert_normalized_marketprice_semantics(case):
    policy = native(case)
    policy["schema"] = "dex-price-contract-v2"
    policy["valuation"].update(basis="guide", amount_basis="item_excluding_shipping_tax")
    del policy["valuation"]["native_money"]
    with pytest.raises(ValueError, match="no established normalized"):
        prepare(case)
