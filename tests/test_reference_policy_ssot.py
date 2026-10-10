"""Offline regression checks for shared reference policy and retired entry points."""

from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from pokemon_hunter import reference_policy as policy
from pokemon_hunter import valuation
from pokemon_hunter.beta import (
    hunt_values,
    lot_calculator,
    price_snapshot_contract,
    price_snapshots,
    shopping_math,
)

TODAY = date(2026, 10, 10)


@pytest.mark.parametrize(
    "url",
    [
        "https://EXAMPLE.test:443/guide?q=1#source",
        "https://sub-domain.example.test/guide",
        "https://xn--bcher-kva.example/guide",
    ],
)
def test_source_url_preserves_supported_ascii_hosts(url):
    assert policy.source_url(url) == url


@pytest.mark.parametrize(
    "host",
    ["example", ".example.test", "example..test", "example.test.", "under_score.test", "é.test"],
)
def test_source_url_rejects_invalid_host_labels(host):
    assert policy.source_url(f"https://{host}/guide") is None


def test_source_url_rejects_long_adversarial_hosts_and_keeps_length_limit():
    assert policy.source_url("https://" + "-" * 1900 + ".test!") is None
    assert policy.source_url("https://" + "a." * 950 + "test!") is None
    assert policy.source_url("https://example.test/" + "a" * 2000) is None


def guide(**changes):
    return dict(
        card_id="synthetic",
        grade="raw",
        edition="standard",
        grader="Guide",
        currency="USD",
        value="12.50",
        as_of=TODAY.isoformat(),
        source_url="https://example.test/guide",
        variant_verified=True,
        **changes,
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_url", "https://example.test@evil.test/guide"),
        ("source_url", "https://127.0.0.1/guide"),
        ("source_url", "https://example.test:444/guide"),
        ("source_url", "https://example.test\\@evil.test/guide"),
        ("source_url", "https://example.test/guide\n"),
        ("currency", "EUR"),
        ("value", "NaN"),
        ("value", "Infinity"),
        ("value", "-1"),
        ("value", "1000000000001"),
        ("variant_verified", "true"),
        ("as_of", "2026-09-09"),
        ("as_of", "2026-10-11"),
        ("as_of", None),
    ],
)
def test_collection_and_hunts_refuse_the_same_invalid_evidence(field, value):
    row = guide()
    row[field] = value
    data = dict(cards={"synthetic": dict(owned=True, first_edition=False)})
    result = valuation.valuation_records(data, [row], TODAY)
    assert result["scenarios"]["raw"]["priced"] == 0
    assert hunt_values._guide("synthetic", "standard", None, [row], TODAY) is None


@pytest.mark.parametrize("age,status", [(0, "eligible"), (30, "eligible"), (31, "stale"), (-1, "future")])
def test_shared_age_boundary_preserves_supported_valuation(age, status):
    row = guide()
    row["as_of"] = (TODAY - timedelta(days=age)).isoformat()
    assert policy.fresh(row["as_of"], TODAY.isoformat()) == status
    assert (policy.valid_record(row, TODAY, guide=True) is not None) == (status == "eligible")
    assert shopping_math.fresh is policy.fresh


def test_collection_valuation_and_legacy_lot_cells_delegate_to_admission():
    row = guide()
    data = dict(cards={"synthetic": dict(owned=True, first_edition=False)})
    printing = dict(id="p", provenance='{"legacy_id":"synthetic"}', edition="standard")
    with patch.object(policy, "valid_record", return_value=None) as admit:
        assert valuation.valuation_records(data, [row], TODAY)["scenarios"]["raw"]["priced"] == 0
        assert lot_calculator.legacy_cells(printing, [row], TODAY)["raw"] is None
        assert admit.call_count == 2
    assert lot_calculator.COLUMNS is price_snapshot_contract.COLUMNS


@pytest.mark.parametrize("error", [ValueError, OSError, KeyError])
def test_current_page_snapshot_failure_is_explicit_but_operator_read_is_strict(error):
    with patch.object(price_snapshots, "current", side_effect=error("synthetic failure")):
        assert price_snapshots.display_current() == ([], "invalid_snapshot")
        with pytest.raises(error):
            price_snapshots.current()
        with patch.object(lot_calculator, "legacy_records", return_value=[]):
            records = lot_calculator.retained_records()
            assert records == [] and records.status == "invalid_snapshot"


def test_no_unreviewed_scraper_or_duplicate_hunt_admission():
    assert not (Path(__file__).resolve().parents[1] / "scripts/refresh_values.py").exists()
    for symbol in ("_source", "_valid", "_amount", "MAX_VALUE"):
        assert not hasattr(hunt_values, symbol)
