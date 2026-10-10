"""Offline multi-source release, revocation, competition and private history."""

import copy
import json
from datetime import timedelta
from uuid import uuid4

import pytest
from django.conf import settings
from price_snapshot_helpers import (
    NOW,
    inputs,
    multi_package,
    package,
    request,
    stage,
)
from price_snapshot_helpers import b2 as b2
from price_snapshot_helpers import env as env
from price_snapshot_helpers import setup as setup
from price_snapshot_helpers import shop as shop
from price_snapshot_helpers import snapshot as snapshot

from pokemon_hunter.beta import collection, shopping
from pokemon_hunter.beta import lot_calculator as lot
from pokemon_hunter.beta import price_snapshot_contract as rules
from pokemon_hunter.beta import price_snapshots as prices


def test_multisource_grades_and_independent_expiry_restore_exclusion(setup):
    value = multi_package(setup)
    prices.activate(stage(value), None, now=NOW)
    before = prices.current()[0]
    assert {r["_review_id"] for r in before} == {"fixture-raw", "fixture-graded"}
    permanent_hash = rules.digest(value["contracts"]["fixture-raw"]["contract"])
    limited_hash = rules.digest(value["contracts"]["fixture-graded"]["contract"])
    stable_path = prices.sources.shard(value["version"], permanent_hash)
    limited_path = prices.sources.shard(value["version"], limited_hash)
    stable_bytes, restore_bytes = stable_path.read_bytes(), limited_path.read_bytes()
    prices.purge_expired(now=NOW + timedelta(days=2))
    assert stable_path.read_bytes() == stable_bytes
    assert not limited_path.exists()
    assert limited_hash not in prices.seals()[value["version"]]["sources"]
    assert [r["grade"] for r in prices.current(now=NOW)[0]] == ["raw"]
    # Even restoring a valid old source file cannot overcome the independent tombstone.
    limited_path.write_bytes(restore_bytes)
    assert [r["grade"] for r in prices.current(now=NOW)[0]] == ["raw"]
    assert not limited_path.exists()
    p = setup["entries"][value["records"][0]["printing_id"]]
    cells = lot.cells(p, lot.retained_records(), NOW.date())
    assert cells["raw"]["source_review"] == "fixture-raw"
    assert cells["8"] is None


def test_multisource_removal_across_releases_and_rollback(setup):
    first, second = multi_package(setup, restricted=False), multi_package(setup, restricted=False)
    prices.activate(stage(first), None, now=NOW)
    prices.activate(stage(second), first["version"], now=NOW)
    digest = rules.digest(first["contracts"]["fixture-graded"]["contract"])
    stable = prices.sources.shard(
        first["version"], rules.digest(first["contracts"]["fixture-raw"]["contract"])
    )
    old_bytes = stable.read_bytes()
    prices.sources.remove_source(digest)
    prices.rollback(second["version"], now=NOW)
    assert [r["grade"] for r in prices.current()[0]] == ["raw"]
    assert stable.read_bytes() == old_bytes
    for v in (first, second):
        assert not prices.sources.shard(v["version"], digest).exists()
    with pytest.raises(ValueError, match="Revoked source"):
        prices.preview(stage(first), now=NOW)


def test_multisource_competing_cells_deterministic_and_not_averaged(setup):
    value = multi_package(setup, restricted=False, competing=True)
    prices.activate(stage(value), None, now=NOW)
    pid = value["records"][0]["printing_id"]
    p = setup["entries"][pid]
    rows = prices.current()[0]
    forward = lot.cells(p, rows, NOW.date())["raw"]
    reverse = lot.cells(p, list(reversed(rows)), NOW.date())["raw"]
    assert forward == reverse
    assert forward["amount"] == "99"
    assert forward["grader"] == "PSA"
    assert forward["conflicts"][0]["grader"] == "Generic guide population"
    raw = request(setup)
    raw["cards"] = [dict(printing_id=pid, quantity=2, values={g: dict(mode="guide") for g in rules.COLUMNS})]
    prepared = lot.prepare(setup["actor"], raw, NOW)
    assert prepared["scenarios"]["raw"]["references"][0]["source_contract"] == forward["source_contract"]
    assert prepared["scenarios"]["raw"]["result"]["full_selected_total"] == "198.00"


def test_multisource_save_rights_history_and_account_isolation(setup):
    old_key = shopping.save(setup["actor"], inputs(setup), "Old history", now=NOW)
    old = shopping.one(setup["actor"], old_key)
    state_before = collection.export_data(setup["actor"])
    value = multi_package(setup)
    prices.activate(stage(value), None, now=NOW)
    pid = value["records"][0]["printing_id"]
    raw = request(setup)
    raw["cards"] = [dict(printing_id=pid, quantity=2, values={g: dict(mode="guide") for g in rules.COLUMNS})]
    with pytest.raises(ValueError, match="permanent comparison"):
        shopping.store_payload(setup["actor"], lot.prepare(setup["actor"], raw, NOW), "No rights borrowing")
    for grade in ("8", "9", "10"):
        raw["cards"][0]["values"][grade] = dict(mode="none")
    key = shopping.store_payload(
        setup["actor"], lot.prepare(setup["actor"], raw, NOW), "Independent raw only"
    )
    assert setup["b"].get(f"/shopping/saved/{key}/").status_code == 404
    prices.sources.remove_source(rules.digest(value["contracts"]["fixture-raw"]["contract"]))
    assert shopping.reopen(setup["actor"], key)["scenarios"]["raw"]["result"]["full_selected_total"] == "5.10"
    assert shopping.one(setup["actor"], old_key) == old
    assert collection.export_data(setup["actor"]) == state_before


@pytest.mark.parametrize("mutation", ["missing_source", "rights_borrow", "duplicate", "unknown_field"])
def test_multisource_contract_links_are_independently_validated(setup, mutation):
    value = multi_package(setup)
    if mutation == "missing_source":
        value["records"][0]["contract_id"] = "unknown"
    elif mutation == "rights_borrow":
        value["records"][1]["contract_id"] = "fixture-raw"
        value["contracts"]["fixture-raw"]["contract"]["fields"].pop("price-8")
    elif mutation == "duplicate":
        value["records"][1]["observation_id"] = value["records"][0]["observation_id"]
    else:
        value["records"][1]["field"] = "guessed-grade8-price"
    with pytest.raises(ValueError):
        prices.activate(stage(value), None, now=NOW)
    assert prices.state()["current"] is None


def test_multisource_ordinary_admission_revokes_only_changed_contract(setup):
    value = multi_package(setup, restricted=False)
    for source in value["contracts"].values():
        source["contract"]["provider"] = "synthetic-publisher"
    registry = {key: rules.digest(p["contract"]) for key, p in value["contracts"].items()}
    (settings.ROOT / "SYNTHETIC_ONLY").unlink()
    path = stage(value)
    prices.atomic(settings.ROOT / "price-contracts.json", {"fixture-raw": registry["fixture-raw"]})
    with pytest.raises(ValueError, match="admission disabled"):
        prices.preview(path, now=NOW)
    prices.atomic(settings.ROOT / "price-contracts.json", registry)
    prices.activate(path, None, now=NOW)
    staged = copy.deepcopy(value)
    staged["version"] = str(uuid4())
    staged_path = stage(staged)
    prices.atomic(settings.ROOT / "price-contracts.json", {"fixture-raw": registry["fixture-raw"]})
    assert [row["grade"] for row in prices.current()[0]] == ["raw"]
    assert not prices.sources.shard(value["version"], registry["fixture-graded"]).exists()
    assert set(json.loads(staged_path.read_text())["contracts"]) == {"fixture-raw"}


def test_multisource_integrity_and_interrupted_activation_preserve_current(setup, monkeypatch):
    first, second = multi_package(setup), multi_package(setup)
    prices.activate(stage(first), None, now=NOW)
    original = prices.atomic

    def failure(path, value):
        if path.name == "active.json":
            raise OSError("Interrupted v2 pointer update")
        original(path, value)

    monkeypatch.setattr(prices, "atomic", failure)
    with pytest.raises(OSError):
        prices.activate(stage(second), first["version"], now=NOW)
    assert prices.state()["current"] == first["version"]
    digest = rules.digest(first["contracts"]["fixture-raw"]["contract"])
    path = prices.sources.shard(first["version"], digest)
    corrupt = json.loads(path.read_text())
    corrupt["records"][0]["value"] = corrupt["records"][0]["original_money"] = "999"
    path.write_text(json.dumps(corrupt))
    with pytest.raises(ValueError, match="bytes changed"):
        prices.current()


def test_source_status_is_authenticated_nonprice_and_tracks_independent_removal(setup):
    value = multi_package(setup, restricted=False)
    prices.activate(stage(value), None, now=NOW)
    url = "/api/shopping/price-source-status/"
    response = setup["a"].get(url)
    assert response.status_code == 200
    assert "no-store" in response["Cache-Control"]
    data = response.json()
    assert set(data) == {"sources", "versions", "status"}
    assert len(data["sources"]) == 2
    digest = rules.digest(value["contracts"]["fixture-graded"]["contract"])
    prices.sources.remove_source(digest)
    assert len(setup["a"].get(url).json()["sources"]) == 1
    setup["a"].logout()
    assert setup["a"].get(url).status_code == 302


def test_current_page_callers_share_snapshot_error_policy(setup, monkeypatch):
    calls = []

    def unavailable(**kwargs):
        calls.append(kwargs)
        return [], "invalid_snapshot"

    monkeypatch.setattr(prices, "display_current", unavailable)
    records = lot.retained_records()
    assert records.status == "invalid_snapshot"
    response = setup["a"].get("/api/shopping/price-source-status/")
    assert response.status_code == 200
    assert response.json() == dict(sources=[], versions=[], status="invalid_snapshot")
    assert len(calls) == 2


def test_source_restriction_in_competing_observation_cannot_borrow_save_rights(setup):
    value = multi_package(setup, competing=True)
    # Choose a newer unrestricted raw observation while retaining a restricted conflict.
    for row in value["records"]:
        if row["contract_id"] == "fixture-graded" and row["grade"] == "raw":
            row["as_of"] = "2026-10-08"
    prices.activate(stage(value), None, now=NOW)
    pid = value["records"][0]["printing_id"]
    raw = request(setup)
    raw["cards"] = [
        dict(
            printing_id=pid,
            quantity=1,
            values={g: dict(mode="guide" if g == "raw" else "none") for g in rules.COLUMNS},
        )
    ]
    payload = lot.prepare(setup["actor"], raw, NOW)
    assert payload["scenarios"]["raw"]["references"][0]["save_allowed"] is True
    with pytest.raises(ValueError, match="permanent comparison"):
        shopping.store_payload(setup["actor"], payload, "Restricted conflict cannot be embedded")


def test_multisource_partial_coverage_and_old_new_format_rollback(setup):
    old = package(setup)
    prices.activate(stage(old), None, now=NOW)
    value = multi_package(setup, restricted=False)
    value["records"] = [r for r in value["records"] if r["grade"] in {"raw", "10"}]
    prices.activate(stage(value), old["version"], now=NOW)
    assert {r["grade"] for r in prices.current()[0]} == {"raw", "10"}

    pid = value["records"][0]["printing_id"]
    raw = request(setup)
    raw["cards"] = [
        dict(
            printing_id=pid,
            quantity=3,
            values={g: dict(mode="guide" if g in {"raw", "10"} else "none") for g in rules.COLUMNS},
        )
    ]
    payload = lot.prepare(setup["actor"], raw, NOW)
    assert payload["scenarios"]["8"]["result"]["full_selected_total"] is None
    prices.rollback(value["version"], now=NOW)
    assert len(prices.current()[0]) == 4
    prices.rollback(old["version"], now=NOW)
    assert {r["grade"] for r in prices.current()[0]} == {"raw", "10"}
