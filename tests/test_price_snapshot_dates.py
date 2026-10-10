"""Source-specific publisher dates remain distinct from provider valuation."""

from datetime import timedelta

import pytest
from price_snapshot_helpers import NOW, build_reference_package, request, stage
from price_snapshot_helpers import b2 as b2
from price_snapshot_helpers import env as env
from price_snapshot_helpers import setup as setup
from price_snapshot_helpers import shop as shop
from price_snapshot_helpers import snapshot as snapshot

from pokemon_hunter.beta import lot_calculator as lot
from pokemon_hunter.beta import price_snapshot_contract as rules
from pokemon_hunter.beta import price_snapshots as prices
from pokemon_hunter.beta import shopping


def test_tcgcsv_build_reference_keeps_valuation_unknown_in_browse_evaluation_and_save(setup):
    value = build_reference_package(setup)
    prices.activate(stage(value), None, now=NOW)
    pid = value["records"][0]["printing_id"]
    browse = lot.cell_details(setup["entries"][pid], lot.retained_records(), NOW.date())[0]
    assert browse["raw"]["date_basis"] == "publisher_build"
    assert browse["raw"]["as_of"] == "2026-10-09"
    assert browse["raw"]["valuation_as_of"] is None
    assert browse["8"]["date_basis"] == "valuation"
    raw = request(setup)
    raw["cards"] = [dict(printing_id=pid, quantity=2, values={g: dict(mode="guide") for g in rules.COLUMNS})]
    payload = lot.prepare(setup["actor"], raw, NOW)
    ref = payload["scenarios"]["raw"]["references"][0]
    assert ref["raw_record"]["as_of"] is None
    assert ref["publisher_built_at"] == "2026-10-09T00:00:00+00:00"
    prices.admit(ref)
    forged = dict(ref, date_basis="valuation", valuation_as_of="2026-10-09")
    with pytest.raises(ValueError, match="provider valuation"):
        prices.admit(forged)
    key = shopping.store_payload(setup["actor"], payload, "Synthetic dated-reference check")
    assert (
        shopping.reopen(setup["actor"], key)["scenarios"]["raw"]["references"][0]["valuation_as_of"] is None
    )


@pytest.mark.parametrize(
    "mutation", ["other_source", "graded", "future_build", "forged_valuation", "wrong_date"]
)
def test_build_date_exception_cannot_escape_source_grade_or_date_boundary(setup, mutation):
    value = build_reference_package(setup)
    policy = value["contracts"]["fixture-raw"]["contract"]
    row = value["records"][0]
    if mutation == "other_source":
        policy["provider"] = "Other source"
    elif mutation == "graded":
        policy["fields"]["price-raw"]["grade"] = row["grade"] = "8"
    elif mutation == "future_build":
        row["publisher_built_at"] = (NOW + timedelta(seconds=1)).isoformat()
    elif mutation == "forged_valuation":
        row["as_of"] = "2026-10-09"
    else:
        row["reference_as_of"] = "2026-10-08"
    with pytest.raises(ValueError):
        rules.validate(value, setup["entries"], now=NOW)
    assert prices.state()["current"] is None


def test_build_reference_uses_utc_build_date_and_same_thirty_day_limit(setup):
    value = build_reference_package(setup)
    row = value["records"][0]
    row.update(reference_as_of="2026-09-09", publisher_built_at="2026-09-08T23:30:00-01:00")
    # Graded rows still need valuation dates even in a release containing build references.
    value["records"][1]["as_of"] = None
    prices.activate(stage(value), None, now=NOW)
    pid = row["printing_id"]
    cells, _ = lot.cell_details(setup["entries"][pid], lot.retained_records(), NOW.date())
    assert cells["raw"]["as_of"] == "2026-09-09"  # Exactly 30 days remains eligible.
    assert cells["8"] is None
    cells, _ = lot.cell_details(
        setup["entries"][pid], lot.retained_records(), (NOW + timedelta(days=1)).date()
    )
    assert cells["raw"] is None  # New capture does not refresh a 31-day-old build.
