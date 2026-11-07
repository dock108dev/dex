"""Authored native-guide contracts, money separation and managed lifecycle only."""

import copy
from datetime import timedelta
from uuid import uuid4

import pytest
from django.conf import settings
from price_snapshot_helpers import NOW, package, stage
from price_snapshot_helpers import b2 as b2
from price_snapshot_helpers import env as env
from price_snapshot_helpers import setup as setup
from price_snapshot_helpers import shop as shop
from price_snapshot_helpers import snapshot as snapshot
from test_lv02_valuation import v2_package

from pokemon_hunter.beta import lot_guides, shopping_math
from pokemon_hunter.beta import price_snapshot_contract as rules
from pokemon_hunter.beta import price_snapshots as storage
from pokemon_hunter.beta import reference_preparation as prep
from pokemon_hunter.beta import valuation_evidence as evidence


def native_package(value):
    value = v2_package(value)
    value["contract"]["schema"] = "dex-price-contract-v3"
    value["contract"]["valuation"].update(
        basis=evidence.NATIVE, amount_basis=evidence.NATIVE_AMOUNT, native_money=dict(evidence.NATIVE_MONEY)
    )
    value["records"][0]["evidence"].update(
        schema=evidence.NATIVE_SCHEMA,
        basis=evidence.NATIVE,
        amount_basis=evidence.NATIVE_AMOUNT,
        native_money=dict(evidence.NATIVE_MONEY),
    )
    return value


def current_cell(setup, value=None):
    value = value or native_package(package(setup, permanent=False))
    storage.activate(stage(value), None, now=NOW)
    rows, _ = storage.current(now=NOW)
    printing = setup["entries"][value["records"][0]["printing_id"]]
    return printing, rows, lot_guides.native_cell(printing, rows, NOW.date())


def test_native_admission_never_enters_normalized_selection_or_cells(setup):
    p, rows, ref = current_cell(setup)
    assert ref["amount"] == "2.550001"
    assert ref["capabilities"]["native_arithmetic"]
    assert not ref["capabilities"]["normalized"] and not ref["capabilities"]["strict_ceiling"]
    assert ref["native_money"]["shipping"] == ref["native_money"]["tax"] == "unknown"
    assert evidence.select(p, rows, today=NOW.date())["reference"] is None
    assert evidence.select(p, rows, today=NOW.date(), purpose="native")["basis"] == evidence.NATIVE
    assert lot_guides.cells(p, rows, NOW.date())["raw"] is None
    assert shopping_math.eligibility(ref, NOW.date().isoformat()) == "native_guide_not_normalized"
    assert (
        shopping_math.eligibility(dict(ref, basis="guide", raw_record=rows[0]), NOW.date().isoformat())
        == "native_guide_not_normalized"
    )


@pytest.mark.parametrize(
    "key,value",
    [
        ("basis", "guide"),
        ("amount_basis", "item_excluding_shipping_tax"),
        ("condition", "NM"),
        ("native_money", dict(evidence.NATIVE_MONEY, shipping="excluded")),
        ("ceiling_applicable", True),
        ("estimator", {}),
        ("sale_origins", ["invented-sale"]),
        ("qualification", "pending"),
    ],
)
def test_native_policy_rejects_invented_or_normalized_semantics(setup, key, value):
    data = native_package(package(setup))
    data["contract"]["valuation"][key] = value
    with pytest.raises(ValueError):
        rules.validate(data, setup["entries"], now=NOW)


@pytest.mark.parametrize(
    "key,value",
    [
        ("native_money", dict(evidence.NATIVE_MONEY, tax="excluded")),
        ("schema", evidence.SCHEMA),
        ("basis", "sold_estimate"),
        ("sales", [{}]),
        ("estimate", {}),
        ("amount_basis", "item_excluding_shipping_tax"),
    ],
)
def test_native_row_cannot_disagree_with_policy(setup, key, value):
    data = native_package(package(setup))
    data["records"][0]["evidence"][key] = value
    with pytest.raises(ValueError):
        rules.validate(data, setup["entries"], now=NOW)


def test_v2_unresolved_money_and_unknown_versions_still_fail(setup):
    data = v2_package(package(setup))
    data["contract"]["valuation"]["amount_basis"] = evidence.NATIVE_AMOUNT
    with pytest.raises(ValueError, match="item-only"):
        rules.validate(data, setup["entries"], now=NOW)
    data = native_package(package(setup))
    data["contract"]["schema"] = "dex-price-contract-v4"
    with pytest.raises(ValueError, match="Unsupported price contract"):
        rules.validate(data, setup["entries"], now=NOW)


@pytest.mark.parametrize("key", ["edition", "finish", "language"])
def test_native_exact_identity_cannot_use_conditional_unknowns(setup, key):
    data = native_package(package(setup))
    row = data["records"][0]
    p = copy.deepcopy(setup["entries"][row["printing_id"]])
    p[key] = row["identity"][key] = None
    row["match_scope"] = "conditional_market"
    row["reference_as_of"] = row["as_of"]
    assert rules.reason(row, p, NOW.date()) == "rejected_unresolved_or_conflicting_variant"


def test_no_invented_variant_dimension_and_explicit_na_is_not_null(setup):
    data = native_package(package(setup))
    row = data["records"][0]
    p = copy.deepcopy(setup["entries"][row["printing_id"]])
    p["variant"] = row["identity"]["variant"] = None
    assert rules.reason(row, p, NOW.date()) == "eligible"
    p["edition"] = row["identity"]["edition"] = row["provider_identity"]["edition"] = "not_applicable"
    assert rules.reason(row, p, NOW.date()) == "eligible"
    p["edition"] = row["identity"]["edition"] = None
    assert rules.reason(row, p, NOW.date()).startswith("rejected_")


def test_quantity_sums_complete_partial_and_mixed_cohorts(setup):
    p, _, ref = current_cell(setup)
    lines = [dict(printing_id=p["id"], quantity=2)]
    args = dict(today=NOW.date().isoformat(), unknown_quantity=0, reconciled=True)
    groups = shopping_math.native_subtotals(lines, {p["id"]: ref}, **args)
    assert groups[0]["total"] == "5.10" and groups[0]["priced_quantity"] == 2
    assert not groups[0]["save_allowed"]
    assert not any(k in groups[0] for k in ["savings", "full_lot_total", "bid_difference", "strict_ceiling"])
    assert (
        shopping_math.native_subtotals(lines, {p["id"]: ref}, **dict(args, unknown_quantity=1))[0]["total"]
        is None
    )
    other = dict(ref, printing_id="other", cohort="other-cohort", amount="25")
    groups = shopping_math.native_subtotals(
        lines + [dict(printing_id="other", quantity=1)], {p["id"]: ref, "other": other}, **args
    )
    assert len(groups) == 2 and all(g["total"] is None for g in groups)
    with pytest.raises(ValueError, match="incompatible_native_reference"):
        shopping_math.native_subtotals(lines, {p["id"]: dict(ref, basis="guide")}, **args)
    with pytest.raises(ValueError, match="duplicate_native_selection"):
        shopping_math.native_subtotals(lines * 2, {p["id"]: ref}, **args)


@pytest.mark.parametrize("quantity", [0, -1, True, 100001])
def test_native_quantity_bounds(setup, quantity):
    p, _, ref = current_cell(setup)
    with pytest.raises(ValueError):
        shopping_math.native_subtotals(
            [dict(printing_id=p["id"], quantity=quantity)],
            {p["id"]: ref},
            NOW.date().isoformat(),
            unknown_quantity=0,
            reconciled=True,
        )


def combine(*parts):
    return dict(
        schema="dex-price-snapshot-v2",
        version=str(uuid4()),
        release_month=parts[0]["release_month"],
        contracts={
            p["contract"]["review_id"]: dict(contract=p["contract"], expires_at=p["expires_at"])
            for p in parts
        },
        records=[dict(r, contract_id=p["contract"]["review_id"]) for p in parts for r in p["records"]],
    )


def test_native_prepared_index_and_source_withdrawal_preserve_normalized(setup):
    native = native_package(package(setup, permanent=False))
    native["contract"]["review_id"] = "fixture-native"
    guide = v2_package(package(setup))
    data = combine(native, guide)
    storage.activate(stage(data), None, now=NOW)
    rows, _ = storage.current(now=NOW)
    pid = native["records"][0]["printing_id"]
    p = setup["entries"][pid]
    assert lot_guides.native_cell(p, rows, NOW.date())
    assert lot_guides.cells(p, rows, NOW.date())["raw"]
    digest = rules.digest(native["contract"])
    path = storage.sources.shard(data["version"], digest)
    index = storage.read(path.with_suffix(".idx"))
    assert index["format"] == 2 and index["native_context"]["provider"] == "dex-engineering-fixture"
    storage.sources.remove_source(digest)
    rows, _ = storage.current(now=NOW)
    assert lot_guides.native_cell(p, rows, NOW.date()) is None
    assert lot_guides.cells(p, rows, NOW.date())["raw"]
    with pytest.raises(ValueError, match="Revoked source"):
        storage.preview(stage(data), now=NOW)


def test_native_expiry_and_stop_keep_existing_release(setup):
    native = native_package(package(setup, permanent=False))
    prep.prepare(native, expected_current=None, now=NOW)
    prep.stop()
    with pytest.raises(ValueError, match="stopped"):
        prep.activate(native["version"], expected_current=None, now=NOW)
    assert storage.state()["current"] is None
    prep.resume()
    prep.activate(native["version"], expected_current=None, now=NOW)
    rows, _ = storage.current(now=NOW + timedelta(days=2))
    assert not rows


def test_exact_new_admission_required_and_fixture_cannot_escape(setup):
    value = native_package(package(setup))
    (settings.ROOT / "SYNTHETIC_ONLY").unlink()
    with pytest.raises(ValueError, match="Engineering fixtures"):
        storage.preview(stage(value), now=NOW)
    old = v2_package(package(setup))
    old["contract"]["provider"] = "authored-native-review"
    value["contract"]["provider"] = "authored-native-review"
    storage.atomic(
        settings.ROOT / "price-contracts.json", {old["contract"]["review_id"]: rules.digest(old["contract"])}
    )
    with pytest.raises(ValueError, match="exact supported contract"):
        storage.preview(stage(value), now=NOW)
    storage.atomic(
        settings.ROOT / "price-contracts.json",
        {value["contract"]["review_id"]: rules.digest(value["contract"])},
    )
    assert storage.preview(stage(value), now=NOW)
    value["contract"]["rights"]["arithmetic"] = False
    with pytest.raises(ValueError, match="rights unavailable"):
        storage.preview(stage(value), now=NOW)


def test_unstated_variant_cannot_hide_a_special_provider_subtype(setup):
    data = native_package(package(setup))
    row = data["records"][0]
    p = copy.deepcopy(setup["entries"][row["printing_id"]])
    p["variant"] = row["identity"]["variant"] = None
    row["provider_identity"]["variant"] = "galaxy"
    assert rules.reason(row, p, NOW.date()) == "rejected_unresolved_or_conflicting_variant"


@pytest.mark.parametrize("field,value", [("value", "0"), ("value", "1000000000001"), ("currency", "EUR")])
def test_native_money_amount_and_currency_bounds(setup, field, value):
    data = native_package(package(setup))
    data["records"][0][field] = value
    if field == "value":
        data["records"][0]["original_money"] = value
    with pytest.raises(ValueError):
        rules.validate(data, setup["entries"], now=NOW)


def test_native_cannot_supply_strict_ceiling_even_if_projection_flag_is_tampered(setup):
    from pokemon_hunter.beta import lot_assessment

    p, rows, _ = current_cell(setup)
    rows[0]["ceiling_applicable"] = True
    rows[0]["condition"] = "NM"
    ref, reason = lot_assessment.applicable(p, dict(grade="raw", condition="NM"), rows, NOW.date())
    assert ref is None and "No current admitted reference" in reason


def test_native_quantity_weighted_total_keeps_existing_money_cap(setup):
    p, _, ref = current_cell(setup)
    ref["amount"] = str(shopping_math.CAP)
    with pytest.raises(ValueError, match="native_subtotal_above_cap"):
        shopping_math.native_subtotals(
            [dict(printing_id=p["id"], quantity=2)],
            {p["id"]: ref},
            NOW.date().isoformat(),
            unknown_quantity=0,
            reconciled=True,
        )


def test_saved_comparison_cannot_strip_native_basis_to_retain_amount(setup):
    value = native_package(package(setup, permanent=True))
    _, rows, ref = current_cell(setup, value)
    assert ref["save_allowed"] is False
    forged = dict(raw_record=rows[0])
    with pytest.raises(ValueError, match="Native guides are ephemeral"):
        storage.admit(forged, rows=rows)
