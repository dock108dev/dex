"""Authored engineering evidence only; no market calibration or customer data."""

import copy
from dataclasses import asdict
from datetime import datetime, timedelta, timezone

import pytest

from pokemon_hunter.beta import price_snapshot_contract as rules
from pokemon_hunter.beta import sold_estimates as sold
from pokemon_hunter.beta import valuation_evidence as evidence

NOW = datetime(2026, 11, 4, 20, tzinfo=timezone.utc)
IDENTITY = dict(
    set_id="fossil",
    collector_number="10",
    language="en",
    edition="unlimited",
    finish="holo",
    variant="holo",
    catalog_version="authored-v1",
)


def sales(count=12):
    return [
        dict(
            origin="authored-marketplace",
            sale_id=f"authored-{i}",
            identity=dict(IDENTITY),
            grade="raw",
            condition=None,
            sold_at=(NOW - timedelta(days=i + 1)).isoformat(),
            captured_at=NOW.isoformat(),
            amount=str(10 + i % 3),
            shipping="4",
            currency="USD",
            quantity=1,
            amount_basis="item_excluding_shipping_tax",
            price_semantics="transaction_amount",
            accepted_offer=False,
            accepted_amount_known=False,
            source_url="https://example.test/sale",
        )
        for i in range(count)
    ]


def test_predeclared_candidates_and_simple_median():
    assert len(sold.policies()) == 12
    result = sold.estimate(sales(), IDENTITY, now=NOW)
    assert result["value"] == "11.000000"
    assert result["unique_sales"] == 12
    assert result["effective_sample_size"] == "12"
    assert result["condition_strata"] == {"unknown": 12}
    assert not result["strict_ceiling_ready"]
    assert result["spread"]["meaning"] == "observed_order_statistics_not_confidence_bounds"


@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("identity", dict(IDENTITY, edition="first_edition"), "wrong_or_unresolved_identity"),
        ("identity", dict(IDENTITY, finish="normal"), "wrong_or_unresolved_identity"),
        ("identity", dict(IDENTITY, language="ja"), "wrong_or_unresolved_identity"),
        ("grade", "10", "graded"),
        ("quantity", 2, "unsupported_quantity"),
        ("quantity", True, "unsupported_quantity"),
        ("amount_basis", "delivered", "incompatible_money_basis"),
        ("currency", "EUR", "incompatible_money_basis"),
        ("price_semantics", "asking_price", "not_sold_amount"),
        ("accepted_offer", True, "unknown_accepted_amount"),
        ("accepted_offer", None, "unknown_offer_semantics"),
        ("sold_at", (NOW - timedelta(days=31)).isoformat(), "outside_lookback"),
        ("sold_at", (NOW + timedelta(days=1)).isoformat(), "future_sale_or_capture"),
        ("amount", "NaN", "invalid_sale"),
        ("shipping", "unknown", "invalid_sale"),
    ],
)
def test_authored_negative_cases(field, value, reason):
    rows = sales()
    rows[0][field] = value
    result = sold.estimate(rows, IDENTITY, now=NOW)
    assert result["excluded"] == {reason: 1}
    assert result["unique_sales"] == 11


def test_duplicates_cross_provider_conflicts_and_extreme():
    rows = sales()
    baseline = sold.estimate(rows, IDENTITY, now=NOW)
    duplicate = dict(rows[0], source_url="https://another.test/same-sale")
    result = sold.estimate(rows + [duplicate] * 50, IDENTITY, now=NOW)
    assert result["value"] == baseline["value"]
    assert result["unique_sales"] == 12
    assert result["excluded"] == {"duplicate": 50}
    conflict = dict(duplicate, amount="90000")
    result = sold.estimate(rows + [conflict], IDENTITY, now=NOW)
    assert result["excluded"] == {"conflicting_duplicate": 2}
    assert result["unique_sales"] == 11
    rows[0]["amount"] = "90000"
    assert sold.estimate(rows, IDENTITY, now=NOW)["value"] == "11.000000"


def test_sparse_condition_and_missing_identity_never_become_nm():
    assert sold.estimate(sales(4), IDENTITY, now=NOW)["value"] is None
    assert sold.estimate(sales(), IDENTITY, now=NOW, condition="NM")["unique_sales"] == 0
    assert sold.estimate(sales(), dict(IDENTITY, finish=None), now=NOW)["unique_sales"] == 0
    rows = sales()
    rows[0]["accepted_offer"] = rows[0]["accepted_amount_known"] = True
    assert sold.estimate(rows, IDENTITY, now=NOW)["unique_sales"] == 12
    for row in rows:
        row["shipping"] = None
    assert sold.estimate(rows, IDENTITY, now=NOW)["value"] == "11.000000"


def test_weighting_age_strata_and_effective_sample_gate():
    rows = sales()
    for i, row in enumerate(rows):
        row["amount"] = "10" if i < 6 else "20"
        row["sold_at"] = (NOW - timedelta(days=1 if i < 6 else 25)).isoformat()
    result = sold.estimate(rows, IDENTITY, now=NOW, policy=sold.Policy("recency_weighted_median", 30, 14, 10))
    assert result["value"] == "10.000000"
    assert 5 < float(result["effective_sample_size"]) < 12
    rows = sales(10)
    for i, row in enumerate(rows):
        row["sold_at"] = (NOW - timedelta(days=1 if i == 0 else 89)).isoformat()
    result = sold.estimate(rows, IDENTITY, now=NOW, policy=sold.Policy("recency_weighted_median", 90, 14, 10))
    assert result["value"] is None and float(result["effective_sample_size"]) < 5


def test_future_naive_dates_and_bounds():
    with pytest.raises(ValueError):
        sold.estimate(sales(), IDENTITY, now=NOW.replace(tzinfo=None))
    with pytest.raises(ValueError):
        sold.estimate(sales() * 200, IDENTITY, now=NOW)
    with pytest.raises(ValueError):
        sold.Policy("median", 31, None, 5)


def v2_package(value, *, basis="guide", qualified=True):
    value = copy.deepcopy(value)
    value["records"] = value["records"][:1]
    policy = value["contract"]
    policy["schema"] = "dex-price-contract-v2"
    policy["fields"] = {value["records"][0]["field"]: policy["fields"][value["records"][0]["field"]]}
    policy["valuation"] = dict(
        basis=basis,
        condition=None,
        amount_basis="item_excluding_shipping_tax",
        ceiling_applicable=False,
        qualification="reviewed" if qualified else "engineering_only",
        qualification_review="authored-isolated-policy-not-real-calibration",
        estimator=asdict(sold.Policy()) if basis == "sold_estimate" else None,
        sale_origins=["authored-marketplace"] if basis == "sold_estimate" else [],
    )
    row = value["records"][0]
    row.update(
        condition=None,
        ceiling_applicable=False,
        valuation_qualification=policy["valuation"]["qualification"],
        evidence=dict(
            schema=evidence.SCHEMA,
            basis=basis,
            condition=None,
            amount_basis="item_excluding_shipping_tax",
            sales=[],
            estimate=None,
        ),
    )
    if basis == "sold_estimate":
        clock = rules.timestamp(row["captured_at"])
        samples = sales()
        for i, sample in enumerate(samples):
            sample.update(
                identity=dict(row["identity"]),
                sold_at=(clock - timedelta(days=i + 1)).isoformat(),
                captured_at=clock.isoformat(),
            )
        result = sold.estimate(samples, row["identity"], now=clock)
        row.update(
            estimate_kind="dex_sold_estimate",
            value=result["value"],
            original_money=None,
            as_of=(clock - timedelta(days=1)).date().isoformat(),
        )
        row["evidence"].update(sales=samples, estimate=result)
        value["expires_at"] = (clock + timedelta(hours=12)).isoformat()
    return value
