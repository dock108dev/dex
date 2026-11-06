"""Read-only v2 dimension tests, with fixtures kept separate from actual coverage."""

import json

import pytest
from test_hunter_coverage_audit import NOW, file_bytes, install
from test_hunter_coverage_audit import audit_module as audit_module
from test_hunter_coverage_audit import audit_root as audit_root
from test_lot_value_readiness import prepare_schema
from test_lv02_valuation import v2_package

from pokemon_hunter.beta import lot_value_readiness as readiness


def test_readiness_guide_without_condition_and_fixture_labels(audit_root):
    root, _, value = audit_root
    prepare_schema(root)
    install(root, value)
    before = file_bytes(root.parent)
    result = readiness.project(root, now=NOW, version=2)
    assert file_bytes(root.parent) == before
    assert result["schema"] == "dex-lot-value-readiness-v2"
    assert result["coverage"]["eligible_raw_guide_printings"] == 1
    assert result["coverage"]["eligible_sold_printings"] == 0
    assert result["coverage"]["condition_applicable_raw_printings"] == 0
    assert result["state"] == "isolated_engineering"
    assert not result["ready"] and not result["readiness"]["guide_available"]
    assert "raw_condition_capability_missing" not in {r["code"] for r in result["reasons"]}
    assert sum(r["catalog_printings"] for r in result["variant_coverage"]) == 3
    for forbidden in ("876.543", "original_money", "source_url", "sensitive-test-review"):
        assert forbidden not in json.dumps(result)


def test_sold_and_engineering_only_coverage(audit_root):
    root, _, value = audit_root
    prepare_schema(root)
    for row in value["records"]:
        row["captured_at"] = NOW.isoformat()
    value = v2_package(value, basis="sold_estimate")
    install(root, value)
    result = readiness.project(root, now=NOW, version=2)
    assert result["coverage"]["eligible_sold_printings"] == 1
    assert result["coverage"]["eligible_raw_guide_printings"] == 0
    assert result["coverage"]["condition_applicable_raw_printings"] == 0


@pytest.mark.parametrize("state", ["expired", "withdrawn", "unadmitted", "stale"])
def test_v2_coverage_lifecycle(audit_root, state):
    from datetime import timedelta

    root, _, value = audit_root
    prepare_schema(root)
    if state == "expired":
        value["expires_at"] = NOW.isoformat()
    if state == "stale":
        for row in value["records"]:
            row["as_of"] = (NOW - timedelta(days=31)).date().isoformat()
    registry = install(root, value)
    if state == "withdrawn":
        registry.write_text(json.dumps([value["version"]]))
    if state == "unadmitted":
        (root / "SYNTHETIC_ONLY").unlink()
        (root / "price-contracts.json").write_text("{}")
    before = file_bytes(root.parent)
    result = readiness.project(root, now=NOW, version=2)
    assert result["coverage"]["eligible_benchmark_printings"] == 0
    assert not result["ready"]
    assert file_bytes(root.parent) == before


def test_pilot_reproducibility_and_frozen_failure_denominator(monkeypatch):
    import importlib
    from pathlib import Path

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    manifest = importlib.import_module("lv02_pricing_pilot").manifest
    entries = {}
    for name in ("Base Set", "Jungle", "Fossil"):
        for number in range(1, 31):
            pid = f"authored-{name}-{number}"
            entries[pid] = dict(
                id=pid,
                name="Lapras" if name == "Fossil" and number in (10, 25) else "Authored card",
                set_name=name,
                set_id=name,
                collector_number=str(number),
                language="en",
                edition=None,
                finish=None,
                variant=None,
                catalog_version="authored-v1",
                attributes=dict(
                    supertype="Trainer" if number % 5 == 0 else "Pokémon",
                    rarity="Rare" if number % 2 else "Common",
                ),
            )
    frozen = manifest(entries)
    assert frozen == manifest(dict(reversed(list(entries.items()))))
    assert len(frozen["rows"]) == 60
    assert len({r["printing_id"] for r in frozen["rows"]}) == 60
    lapras = [r for r in frozen["rows"] if r["set_name"] == "Fossil" and r["name"] == "Lapras"]
    assert {r["identity"]["collector_number"] for r in lapras} == {"10", "25"}
    assert all(r["unresolved_identity"] for r in lapras)
    assert len(frozen["authored_engineering_baskets"]) == 6
    assert all(
        b["value"] is None and b["priced_quantity"] == 0 for b in frozen["authored_engineering_baskets"]
    )
    with pytest.raises(ValueError):
        manifest({})


def test_condition_scoped_reference_does_not_claim_general_benchmark(audit_root):
    root, _, value = audit_root
    prepare_schema(root)
    value = v2_package(value)
    value["contract"]["valuation"].update(condition="LP", ceiling_applicable=True)
    value["records"][0].update(condition="LP", ceiling_applicable=True)
    value["records"][0]["evidence"]["condition"] = "LP"
    install(root, value)
    result = readiness.project(root, now=NOW, version=2)
    assert result["coverage"]["condition_scoped_guide_printings"] == 1
    assert result["coverage"]["eligible_raw_guide_printings"] == 0
    assert result["coverage"]["condition_applicable_raw_printings"] == 1
