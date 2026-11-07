"""Native coverage is separate from normalized readiness and actual source proof."""

import json

import pytest
from test_hunter_coverage_audit import NOW, file_bytes, install
from test_hunter_coverage_audit import audit_module as audit_module
from test_hunter_coverage_audit import audit_root as audit_root
from test_lot_value_readiness import prepare_schema
from test_lv02_native_guides import native_package

from pokemon_hunter.beta import lot_value_readiness as readiness


def test_native_readiness_keeps_denominator_and_normalized_counts(audit_root):
    root, _, value = audit_root
    prepare_schema(root)
    value = native_package(value)
    install(root, value)
    before = file_bytes(root.parent)
    result = readiness.project(root, now=NOW, version=3)
    assert file_bytes(root.parent) == before
    assert result["schema"] == "dex-lot-value-readiness-v3"
    assert result["coverage"]["eligible_native_guide_printings"] == 1
    assert result["coverage"]["eligible_raw_guide_printings"] == 0
    assert result["coverage"]["eligible_benchmark_printings"] == 0
    assert result["coverage"]["catalog_denominator"] == 3
    assert result["coverage"]["parents_with_eligible_priced_alternatives"] == 0
    assert result["coverage"]["source_absence"] == "not_established_by_active_inventory"
    assert result["state"] == "isolated_engineering" and not result["ready"]
    assert not result["readiness"]["native_guide_available"]
    assert "876.543" not in json.dumps(result)
    old = readiness.project(root, now=NOW, version=2)
    assert old["coverage"]["eligible_raw_guide_printings"] == 0


@pytest.mark.parametrize("state", ["expired", "withdrawn", "unadmitted", "engineering_only"])
def test_native_readiness_lifecycle_does_not_claim_source_absence(audit_root, state):
    root, _, value = audit_root
    prepare_schema(root)
    value = native_package(value)
    if state == "expired":
        value["expires_at"] = NOW.isoformat()
    if state == "engineering_only":
        value["contract"]["valuation"]["qualification"] = "engineering_only"
        value["records"][0]["valuation_qualification"] = "engineering_only"
    registry = install(root, value)
    if state == "withdrawn":
        registry.write_text(json.dumps([value["version"]]))
    if state == "unadmitted":
        (root / "SYNTHETIC_ONLY").unlink()
        (root / "price-contracts.json").write_text("{}")
    result = readiness.project(root, now=NOW, version=3)
    assert result["coverage"]["eligible_native_guide_printings"] == 0
    assert result["coverage"]["source_absence"] == "not_established_by_active_inventory"
    assert not result["readiness"]["native_guide_available"]


def test_one_priced_child_counts_one_parent_separately_from_exact_entries(audit_root, monkeypatch):
    from test_lv02_variant_selection import family

    from pokemon_hunter.beta import price_snapshot_contract as rules

    root, _, value = audit_root
    prepare_schema(root)
    entries = {p["id"]: p for p in family()}
    p = entries["normal"]
    value = native_package(value)
    row = value["records"][0]
    row["printing_id"] = p["id"]
    row["identity"] = {k: p.get(k) for k in rules.IDENTITY}
    row["provider_identity"].update(
        set=p["set_name"],
        number=p["collector_number"],
        language=p["language"],
        edition=p["edition"],
        finish=p["finish"],
        variant=p["variant"],
    )
    value["contract"]["mappings"] = {
        p["id"]: {k: row[k] for k in ["identity", "provider_identity", "source_url", "source_version"]}
    }
    monkeypatch.setattr(readiness.inventory, "catalog_metadata", lambda root: entries)
    install(root, value)
    result = readiness.project(root, now=NOW, version=3)
    assert result["coverage"]["eligible_native_guide_printings"] == 1
    assert result["coverage"]["parents_with_eligible_priced_alternatives"] == 1
    assert result["coverage"]["linked_parent_entries"] == 1
    assert result["coverage"]["catalog_denominator"] == 3
    assert result["coverage"]["eligible_raw_guide_printings"] == 0
