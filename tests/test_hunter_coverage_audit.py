"""Engineering-only coverage audit protects source content and customer state."""

import importlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from price_snapshot_helpers import package

from pokemon_hunter.beta import price_snapshot_contract as rules

NOW = datetime(2026, 10, 16, 18, tzinfo=timezone.utc)


@pytest.fixture
def audit_module(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    return importlib.import_module("qualify_hunter")


@pytest.fixture
def audit_root(tmp_path, audit_module):
    root = tmp_path / "synthetic-audit"
    root.mkdir()
    (root / "SYNTHETIC_ONLY").touch()
    with sqlite3.connect(root / "inventory.db") as database:
        database.executescript("""
            CREATE TABLE games(id TEXT,game_key TEXT);
            CREATE TABLE catalog_sets(id TEXT,game_id TEXT,name TEXT,catalog_version TEXT,
              coverage_status TEXT,publication_state TEXT);
            CREATE TABLE printings(id TEXT,set_id TEXT,collector_number TEXT,language TEXT,
              edition TEXT,finish TEXT,variant TEXT,attributes TEXT,provenance TEXT,publication_state TEXT);
            INSERT INTO games VALUES('pokemon','pokemon');
            INSERT INTO catalog_sets VALUES('set','pokemon','Synthetic Set','v1','indexed','published');
        """)
        for key, species in (("vintage", 1), ("modern", 1025), ("unpriced", 252)):
            database.execute(
                "INSERT INTO printings VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    key,
                    "set",
                    key,
                    "en",
                    "standard",
                    "normal",
                    "normal",
                    json.dumps({"name": "Synthetic " + key, "pokemon_dex": species, "supertype": "Pokémon"}),
                    json.dumps({"legacy_id": key}),
                    "published",
                ),
            )
    entries = audit_module.catalog_metadata(root)
    value = package({"entries": entries})
    value["contract"]["provider"] = "Synthetic private source"
    value["contract"]["review_id"] = "sensitive-test-review"
    value["records"][0]["value"] = value["records"][0]["original_money"] = "876.543"
    return root, entries, value


def install(root, value):
    base = root / "price-snapshots"
    base.mkdir(exist_ok=True)
    (base / "active.json").write_text(json.dumps({"current": value["version"], "previous": None}))
    (base / (value["version"] + ".json")).write_text(json.dumps(value))
    (base / "versions.json").write_text(json.dumps({value["version"]: {"sha256": rules.digest(value)}}))
    digest = rules.digest(value["contract"])
    (root / "price-contracts.json").write_text(json.dumps({value["contract"]["review_id"]: digest}))
    directory = root.parent / ".dex-price-revocations"
    directory.mkdir(exist_ok=True)
    registry = directory / (rules.digest(str(root.resolve())) + ".json")
    registry.write_text("[]")
    return registry


def file_bytes(root):
    return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def test_read_only_audit_uses_broad_catalog_and_never_exposes_source_content(
    audit_module, audit_root, monkeypatch
):
    root, entries, value = audit_root
    install(root, value)
    from pokemon_hunter.beta import price_snapshots

    def forbidden(*args, **kwargs):
        raise AssertionError("Mutating lifecycle reader must not be used")

    monkeypatch.setattr(price_snapshots, "current", forbidden)
    monkeypatch.setattr(price_snapshots, "display_current", forbidden)
    monkeypatch.setattr(price_snapshots, "purge_expired", forbidden)
    before = file_bytes(root.parent)
    report = audit_module.audit(root, now=NOW)
    assert file_bytes(root.parent) == before
    assert report["catalog"] == {"printings": 3, "sets": 1, "species_above_251_printings": 2}
    assert report["reference_coverage_by_printing"]["eligible"] == 1
    assert report["reference_coverage_by_printing"]["unpriced"] == 2
    assert sum(report["reference_coverage_by_printing"].values()) == len(entries)
    assert report["customer_writes"] == report["provider_operations"] == 0
    rendered = json.dumps(report)
    assert all(
        text not in rendered
        for text in (
            "876.543",
            "sensitive-test-review",
            "fabricated-product",
            "example.test",
            "Synthetic private source",
        )
    )


@pytest.mark.parametrize("state", ["stale", "expired", "withdrawn", "unadmitted", "invalid"])
def test_unavailable_references_never_enter_eligible_coverage(audit_module, audit_root, state):
    root, _, value = audit_root
    if state == "stale":
        for row in value["records"]:
            row["as_of"] = (NOW - timedelta(days=31)).date().isoformat()
    elif state == "expired":
        value["expires_at"] = (NOW - timedelta(seconds=1)).isoformat()
    elif state == "invalid":
        value["records"][0]["currency"] = "GBP"
    registry = install(root, value)
    if state == "withdrawn":
        registry.write_text(json.dumps([value["version"]]))
    elif state == "unadmitted":
        (root / "price-contracts.json").write_text("{}")
    before = file_bytes(root.parent)
    report = audit_module.audit(root, now=NOW)
    assert file_bytes(root.parent) == before
    assert report["reference_coverage_by_printing"]["eligible"] == 0
    assert report["reference_coverage_by_printing"][state] == 1


def test_missing_independent_registry_fails_closed_without_recreating_it(audit_module, audit_root):
    root, _, value = audit_root
    registry = install(root, value)
    registry.unlink()
    before = file_bytes(root.parent)
    with pytest.raises(audit_module.AuditFailure, match="Independent lifecycle registry"):
        audit_module.audit(root, now=NOW)
    assert file_bytes(root.parent) == before


def test_unmapped_reference_count_remains_visible_without_identity_content(audit_module, audit_root):
    root, _, value = audit_root
    value["records"][0]["printing_id"] = "sensitive-unmapped-identity"
    install(root, value)
    report = audit_module.audit(root, now=NOW)
    assert report["unmapped_reference_identities"]["snapshot"] == 1
    assert report["snapshots"]["records_unmapped"] == 1
    assert report["reference_coverage_by_printing"]["eligible"] == 0
    assert "sensitive-unmapped-identity" not in json.dumps(report)


def test_bounded_reader_rejects_links_and_never_echoes_private_parser_errors(audit_module, tmp_path, capsys):
    private = tmp_path / "private.json"
    private.write_text("sensitive-source-content")
    linked = tmp_path / "linked.json"
    linked.symlink_to(private)
    with pytest.raises(audit_module.AuditFailure, match="linked"):
        audit_module.read_json(linked)
    assert audit_module.main(["--root", str(tmp_path), "--output", str(tmp_path / "report.json")]) == 1
    assert "sensitive-source-content" not in capsys.readouterr().err
    assert not (tmp_path / "report.json").exists()
