"""Managed lifecycle integration against disposable state and authored evidence."""

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

from pokemon_hunter.beta import lot_guides
from pokemon_hunter.beta import price_snapshot_contract as rules
from pokemon_hunter.beta import price_snapshots as storage
from pokemon_hunter.beta import reference_preparation as prep
from pokemon_hunter.beta import valuation_evidence as evidence


def test_v2_sold_contract_and_tampered_derivative(setup):
    value = v2_package(package(setup), basis="sold_estimate")
    rules.validate(value, setup["entries"], now=NOW)
    assert value["records"][0]["original_money"] is None
    value["records"][0]["value"] = "123"
    with pytest.raises(ValueError, match="reproducible"):
        rules.validate(value, setup["entries"], now=NOW)


def test_guide_and_sold_choice_with_independent_strict_ceiling(setup):
    guide = v2_package(package(setup))
    sale = v2_package(package(setup), basis="sold_estimate")
    refs = guide["records"] + sale["records"]
    p = next(iter(setup["entries"].values()))
    result = evidence.select(p, refs, today=NOW.date())
    assert result["basis"] == "sold_estimate"
    assert not result["strict_ceiling_ready"]
    refs[1]["valuation_qualification"] = "engineering_only"
    assert evidence.select(p, refs, today=NOW.date())["basis"] == "guide"
    refs[0]["as_of"] = "2025-01-01"
    assert evidence.select(p, refs, today=NOW.date())["coverage"] == "unavailable"
    assert evidence.lot_basis(["sold_estimate", "guide"]) == "mixed"


def test_no_sold_median_in_legacy_guide_cells(setup):
    value = v2_package(package(setup), basis="sold_estimate")
    storage.activate(stage(value), None, now=NOW)
    rows, _ = storage.current(now=NOW)
    p = next(iter(setup["entries"].values()))
    assert lot_guides.cells(p, rows, NOW.date())["raw"] is None


def test_prepare_activate_stop_failed_refresh_and_replay(setup):
    value = v2_package(package(setup))
    result = prep.prepare(value, expected_current=None, now=NOW)
    assert result["state"] == "staged" and storage.state()["current"] is None
    prep.stop()
    with pytest.raises(ValueError, match="stopped"):
        prep.activate(value["version"], expected_current=None, now=NOW)
    prep.resume()
    prep.activate(value["version"], expected_current=None, now=NOW)
    assert storage.state()["current"] == value["version"]
    changed = copy.deepcopy(value)
    changed["version"] = str(uuid4())
    changed["records"][0]["observation_id"] = str(uuid4())
    with pytest.raises(ValueError, match="reserved previously"):
        prep.prepare(changed, expected_current=value["version"], now=NOW)
    changed["records"][0]["value"] = "not money"
    with pytest.raises(ValueError):
        prep.prepare(changed, expected_current=value["version"], now=NOW)
    assert storage.current(now=NOW)[0]
    storage.remove(value["version"])
    with pytest.raises(ValueError):
        prep.prepare(value, expected_current=None, now=NOW)
    assert prep._history(prep._base())[result["reservation"]]["state"] == "activated"


def test_mid_prepare_failure_still_consumes_and_preserves_old(setup, monkeypatch):
    old = package(setup)
    storage.activate(stage(old), None, now=NOW)
    value = v2_package(package(setup))

    def fail(*args, **kwargs):
        raise ValueError("authored interruption")

    monkeypatch.setattr(storage, "preview", fail)
    with pytest.raises(ValueError, match="interruption"):
        prep.prepare(value, expected_current=old["version"], now=NOW)
    assert storage.state()["current"] == old["version"]
    assert list(prep._history(prep._base()).values())[0]["state"] == "failed"
    with pytest.raises(ValueError, match="reserved previously"):
        prep.prepare(value, expected_current=old["version"], now=NOW)


def test_overlap_deadline_corrupt_or_missing_accounting(setup):
    value = v2_package(package(setup))
    with prep._lock():
        with pytest.raises(ValueError, match="already active"):
            prep.prepare(value, expected_current=None, now=NOW)
    ticks = iter((0, 31))
    with pytest.raises(ValueError, match="deadline"):
        prep.prepare(value, expected_current=None, now=NOW, clock=lambda: next(ticks))
    prep.prepare(value, expected_current=None, now=NOW)
    (prep._base() / "reservations.json").unlink()
    with pytest.raises(ValueError, match="accounting missing"):
        prep.prepare(value, expected_current=None, now=NOW)


def test_expiry_and_source_withdrawal_no_revival(setup):
    value = v2_package(package(setup), basis="sold_estimate")
    prep.prepare(value, expected_current=None, now=NOW)
    prep.activate(value["version"], expected_current=None, now=NOW)
    assert storage.current(now=NOW)[0]
    assert not storage.display_current(now=NOW + timedelta(days=1))[0]


def test_engineering_qualification_cannot_enter_ordinary_root(setup):
    value = v2_package(package(setup), basis="sold_estimate", qualified=False)
    value["contract"]["provider"] = "authored-unqualified-provider"
    storage.atomic(settings.ROOT / "price-contracts.json", {"fixture": rules.digest(value["contract"])})
    with pytest.raises(ValueError, match="Uncalibrated"):
        prep.prepare(value, expected_current=None, now=NOW)


@pytest.mark.parametrize(
    "change", ["identity", "calculated", "sale_amount", "expiry", "condition", "guide_sales"]
)
def test_invalid_evidence_release(setup, change):
    value = v2_package(package(setup), basis="guide" if change == "guide_sales" else "sold_estimate")
    row = value["records"][0]
    if change == "identity":
        row["evidence"]["sales"][0]["identity"]["finish"] = "wrong"
    elif change == "calculated":
        row["evidence"]["estimate"]["calculated_at"] = (NOW + timedelta(days=1)).isoformat()
    elif change == "sale_amount":
        row["evidence"]["sales"][0]["accepted_offer"] = True
    elif change == "expiry":
        value["expires_at"] = (NOW + timedelta(days=31)).isoformat()
    elif change == "condition":
        row["condition"] = "NM"
    else:
        row["evidence"]["sales"] = [{"fabricated": True}]
    with pytest.raises(ValueError):
        rules.validate(value, setup["entries"], now=NOW)


def test_existing_staging_is_preserved_and_activation_cas(setup):
    value = v2_package(package(setup))
    path = stage(value)
    before = path.read_bytes()
    with pytest.raises(ValueError, match="already exists"):
        prep.prepare(value, expected_current=None, now=NOW)
    assert path.read_bytes() == before
    other = v2_package(package(setup))
    other["records"][0]["source_version"] = "authored-second-publication"
    other["contract"]["mappings"][other["records"][0]["printing_id"]]["source_version"] = (
        "authored-second-publication"
    )
    prep.prepare(other, expected_current=None, now=NOW)
    storage.activate(path, None, now=NOW)
    with pytest.raises(ValueError, match="changed"):
        prep.activate(other["version"], expected_current=None, now=NOW)
    assert storage.state()["current"] == value["version"]


def test_split_v2_source_index_withdrawal_and_admission_removal(setup):
    first = v2_package(package(setup))
    second = v2_package(package(setup), basis="sold_estimate")
    second["contract"]["review_id"] = "authored-sold"
    combined = dict(
        schema="dex-price-snapshot-v2",
        version=str(uuid4()),
        release_month=first["release_month"],
        contracts={
            v["contract"]["review_id"]: dict(contract=v["contract"], expires_at=v["expires_at"])
            for v in (first, second)
        },
        records=[
            dict(row, contract_id=v["contract"]["review_id"]) for v in (first, second) for row in v["records"]
        ],
    )
    prep.prepare(combined, expected_current=None, now=NOW)
    prep.activate(combined["version"], expected_current=None, now=NOW)
    rows, _ = storage.current(now=NOW)
    p = next(iter(setup["entries"].values()))
    assert evidence.select(p, rows, today=NOW.date())["basis"] == "sold_estimate"
    storage.sources.remove_source(rules.digest(second["contract"]))
    rows, _ = storage.current(now=NOW)
    assert evidence.select(p, rows, today=NOW.date())["basis"] == "guide"
    assert len(rows) == 1
    assert not storage.sources.shard(combined["version"], rules.digest(second["contract"])).exists()


def test_strict_condition_guide_is_separate_from_generic_benchmark(setup):
    value = v2_package(package(setup))
    policy, row = value["contract"], value["records"][0]
    policy["valuation"].update(condition="LP", ceiling_applicable=True)
    row.update(condition="LP", ceiling_applicable=True)
    row["evidence"]["condition"] = "LP"
    rules.validate(value, setup["entries"], now=NOW)
    p = next(iter(setup["entries"].values()))
    assert evidence.select(p, [row], today=NOW.date())["reference"] is None
    assert evidence.select(p, [row], today=NOW.date(), condition="NM")["reference"] is None
    assert evidence.select(p, [row], today=NOW.date(), condition="LP")["strict_ceiling_ready"]


def test_stop_guard_inside_atomic_activation(setup, monkeypatch):
    value = v2_package(package(setup))
    prep.prepare(value, expected_current=None, now=NOW)
    original = storage.activate

    def stopped_before_lock(*args, **kwargs):
        prep.stop()
        return original(*args, **kwargs)

    monkeypatch.setattr(storage, "activate", stopped_before_lock)
    with pytest.raises(ValueError, match="stopped"):
        prep.activate(value["version"], expected_current=None, now=NOW)
    assert storage.state()["current"] is None


def test_process_restart_reservation_and_clock_rollback(setup):
    value = v2_package(package(setup))
    prep.prepare(value, expected_current=None, now=NOW)
    # Reimporting the orchestrator has no in-memory budget to replenish.
    import importlib

    importlib.reload(prep)
    with pytest.raises(ValueError, match="reserved previously"):
        prep.prepare(value, expected_current=None, now=NOW)
    other = v2_package(package(setup))
    other["records"][0]["as_of"] = "2026-10-08"
    other["records"][0]["captured_at"] = (NOW - timedelta(hours=2)).isoformat()
    with pytest.raises(ValueError, match="clock rollback"):
        prep.prepare(other, expected_current=None, now=NOW - timedelta(hours=1))


def test_legacy_missing_source_reason_survives_evidence_filter(setup):
    class Missing(list):
        status = "missing_snapshot"

    p = next(iter(setup["entries"].values()))
    _, reasons = lot_guides.cell_details(p, Missing(), NOW.date())
    assert "No active private snapshot" in reasons["raw"]
