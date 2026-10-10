"""Offline v1 snapshot lifecycle, validation, integrity and save boundaries."""

import copy
import json
from datetime import timedelta

import pytest
from django.conf import settings
from price_snapshot_helpers import (
    NOW,
    inputs,
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


def test_atomic_activation_rollback_and_intervening_write(setup):
    first, second = package(setup), package(setup)
    first_path = stage(first)
    assert prices.summary(prices.preview(first_path, now=NOW))["records"] == 4
    assert prices.state()["current"] is None
    prices.activate(first_path, None, now=NOW)
    assert not first_path.exists()
    with pytest.raises(ValueError, match="changed"):
        prices.activate(stage(second), None, now=NOW)
    prices.activate(stage(second), first["version"], now=NOW)
    prices.rollback(second["version"], now=NOW)
    assert prices.current()[0][0]["_snapshot_version"] == first["version"]
    with pytest.raises(ValueError, match="changed"):
        prices.rollback(second["version"], now=NOW)


def test_failure_before_pointer_write_retains_old_active(setup, monkeypatch):
    first, second = package(setup), package(setup)
    prices.activate(stage(first), None, now=NOW)
    original = prices.atomic

    def failure(path, value):
        if path.name == "active.json":
            raise OSError("Synthetic interrupted activation")
        return original(path, value)

    monkeypatch.setattr(prices, "atomic", failure)
    with pytest.raises(OSError):
        prices.activate(stage(second), first["version"], now=NOW)
    assert prices.state()["current"] == first["version"]
    assert prices.current()[0][0]["_snapshot_version"] == first["version"]


@pytest.mark.parametrize("mutation", ["unknown_date", "capture_only", "identity", "stale"])
def test_ineligible_records_remain_unpriced_with_separate_reasons(setup, mutation):
    value = package(setup)
    row = value["records"][1]
    if mutation in {"unknown_date", "capture_only"}:
        row["as_of"] = None
    elif mutation == "identity":
        row["identity"] = dict(row["identity"], edition="first_edition")
        value["contract"]["mappings"][row["printing_id"]]["identity"] = row["identity"]
        for other in value["records"]:
            other["identity"] = row["identity"]
    else:
        row["as_of"] = "2026-08-01"
    prices.activate(stage(value), None, now=NOW)
    p = setup["entries"][row["printing_id"]]
    cells, reasons = lot.cell_details(p, lot.retained_records(), NOW.date())
    assert cells["8"] is None
    assert reasons["8"] != "Missing observation for this exact printing and grade"
    assert value["records"][1]["captured_at"] == NOW.isoformat()


@pytest.mark.parametrize(
    "mutation",
    [
        "band",
        "grader",
        "duplicate",
        "currency",
        "interpolated",
        "float",
        "future_capture",
        "url",
        "mapping",
        "empty",
        "no_expiry",
        "copy_reach",
    ],
)
def test_structure_and_semantic_conflicts_stop_activation(setup, mutation):
    value = package(setup, permanent=False)
    row = value["records"][1]
    if mutation == "band":
        value["contract"]["fields"][row["field"]]["grade"] = "8/8.5"
    elif mutation == "grader":
        row["grader"] = "PSA"
    elif mutation == "duplicate":
        value["records"].append(copy.deepcopy(row))
    elif mutation == "currency":
        row["currency"] = "EUR"
    elif mutation == "interpolated":
        row["estimate_kind"] = "interpolated"
    elif mutation == "float":
        row["value"] = 7.0
    elif mutation == "future_capture":
        row["captured_at"] = (NOW + timedelta(days=1)).isoformat()
    elif mutation == "url":
        row["source_url"] = "javascript:alert(1)"
    elif mutation == "mapping":
        row["provider_identity"] = dict(row["provider_identity"], product_id="another-printing")
    elif mutation == "empty":
        value["records"] = []
    elif mutation == "no_expiry":
        value["expires_at"] = None
    else:
        value["contract"]["copy_policy"] = "unknown_backups"
    with pytest.raises((ValueError, TypeError)):
        prices.activate(stage(value), None, now=NOW)
    assert prices.state()["current"] is None


def test_source_cannot_authorize_itself_or_use_fixture_on_ordinary_root(setup):
    value = package(setup)
    path = stage(value)
    (settings.ROOT / "SYNTHETIC_ONLY").unlink()
    with pytest.raises(ValueError, match="ordinary"):
        prices.preview(path, now=NOW)
    value["contract"]["provider"] = "unreviewed-provider"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="admission disabled"):
        prices.preview(path, now=NOW)
    prices.atomic(settings.ROOT / "price-contracts.json", {"fixture": rules.digest(value["contract"])})
    assert prices.preview(path, now=NOW)["version"] == value["version"]
    value["contract"]["policy_version"] = "changed-unreviewed-contract"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="admission disabled"):
        prices.preview(path, now=NOW)


def test_expiry_deletion_and_independent_restore_exclusion(setup):
    value = package(setup, permanent=False)
    original_bytes = json.dumps(value)
    prices.activate(stage(value), None, now=NOW)
    prices.purge_expired(now=NOW + timedelta(days=2))
    assert not (prices.directory() / (value["version"] + ".json")).exists()
    assert value["version"] in prices.denied()
    # Simulate restoring a captured store with both values and its pointer.
    restored = prices.directory() / (value["version"] + ".json")
    restored.write_text(original_bytes)
    prices.atomic(prices.directory() / "active.json", dict(current=value["version"], previous=None))
    assert prices.current(now=NOW)[0] == []
    assert not restored.exists()
    with pytest.raises(ValueError, match="Revoked"):
        prices.preview(stage(value), now=NOW)


def test_remove_before_expiry_prevents_rollback_and_restore(setup):
    first, second = package(setup, permanent=False), package(setup)
    prices.activate(stage(first), None, now=NOW)
    prices.activate(stage(second), first["version"], now=NOW)
    prices.remove(first["version"])
    assert prices.state()["previous"] is None
    with pytest.raises(ValueError, match="Revoked"):
        prices.activate(stage(first), second["version"], now=NOW)


def test_restricted_display_arithmetic_refuses_saves_and_preserves_history(setup):
    old_key = shopping.save(setup["actor"], inputs(setup), "Old independent inputs", now=NOW)
    old = shopping.one(setup["actor"], old_key)
    value = package(setup, permanent=False)
    prices.activate(stage(value), None, now=NOW)
    p = setup["entries"][value["records"][0]["printing_id"]]
    raw = request(setup)
    raw["cards"] = [
        dict(printing_id=p["id"], quantity=2, values={g: dict(mode="guide") for g in rules.COLUMNS})
    ]
    payload = lot.prepare(setup["actor"], raw, NOW)
    assert [payload["scenarios"][g]["result"]["full_selected_total"] for g in rules.COLUMNS] == [
        "5.10",
        "14.00",
        "22.00",
        "38.00",
    ]
    assert lot.browse(setup["actor"])[0]["cells"]["8"]["grader"] == "Generic guide population"
    with pytest.raises(ValueError, match="permanent comparison"):
        shopping.store_payload(setup["actor"], payload, "Forbidden price derivatives")
    assert shopping.one(setup["actor"], old_key) == old
    assert len(shopping.listing(setup["actor"])) == 1
    assert not shopping.listing(setup["member"])


def test_new_permitted_history_integrity_isolation_and_no_owner_mutations(setup):
    before = collection.export_data(setup["actor"])
    value = package(setup)
    prices.activate(stage(value), None, now=NOW)
    raw = request(setup)
    pid = value["records"][0]["printing_id"]
    raw["cards"] = [dict(printing_id=pid, quantity=3, values={g: dict(mode="guide") for g in rules.COLUMNS})]
    payload = lot.prepare(setup["actor"], raw, NOW)
    forged = copy.deepcopy(payload)
    forged["scenarios"]["8"]["references"][0]["amount"] = "999"
    with pytest.raises(ValueError, match="differs"):
        shopping.store_payload(setup["actor"], forged, "Forged amount")
    key = shopping.store_payload(setup["actor"], payload, "Permitted fabricated history")
    original = shopping.one(setup["actor"], key)
    assert setup["b"].get(f"/shopping/saved/{key}/").status_code == 404
    prices.remove(value["version"])
    assert shopping.reopen(setup["actor"], key)["scenarios"]["8"]["result"]["full_selected_total"] == "21.00"
    assert shopping.one(setup["actor"], key) == original
    assert collection.export_data(setup["actor"]) == before


def test_symlink_and_path_traversal_are_refused(setup, tmp_path):
    value = package(setup)
    path = stage(value)
    link = tmp_path / "linked.json"
    link.symlink_to(path)
    with pytest.raises(ValueError, match="linked"):
        prices.preview(link, now=NOW)
    prices.atomic(prices.directory() / "active.json", dict(current="../../outside", previous=None))
    with pytest.raises(ValueError):
        prices.state()


def test_version_seal_rejects_modified_prices_and_is_removed_at_expiry(setup):
    value = package(setup, permanent=False)
    prices.activate(stage(value), None, now=NOW)
    path = prices.directory() / (value["version"] + ".json")
    changed = copy.deepcopy(value)
    changed["records"][0]["value"] = changed["records"][0]["original_money"] = "123"
    path.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="bytes changed"):
        prices.current()
    prices.purge_expired(now=NOW + timedelta(days=2))
    assert value["version"] not in prices.seals()
    assert not path.exists()


def test_expiry_worker_removes_expired_orphan_seal_without_provider_io(setup, monkeypatch):
    value = package(setup, permanent=False)
    prices.activate(stage(value), None, now=NOW)
    (prices.directory() / (value["version"] + ".json")).unlink()
    purge = prices.purge_expired
    monkeypatch.setattr(prices, "purge_expired", lambda: purge(now=NOW + timedelta(days=2)))

    class Stop:
        iterations = 0

        def wait(self, seconds):
            self.iterations += 1
            return self.iterations > 1

    prices.expiry_worker(Stop())
    assert value["version"] not in prices.seals()
    assert value["version"] in prices.denied()
    assert prices.state()["current"] is None
