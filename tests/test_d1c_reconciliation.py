"""Offline reporting rejects drift and quarantines affected identity joins."""

import copy
import hashlib
import importlib.util
import json
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

SPEC = importlib.util.spec_from_file_location(
    "d1c", Path(__file__).resolve().parents[1] / "scripts/reconcile_d1c.py"
)
d1c = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(d1c)


@pytest.fixture(autouse=True)
def synthetic_receipts(monkeypatch):
    """Model source receipts and publication references without private files.

    Public catalog packages are the fixed inputs; generated receipts qualify
    reconciliation behavior, never the historical acquisition or publication.
    """
    root = d1c.ROOT
    rawroot = Path("/synthetic-dex-private/d1-e1-20261004/source-evidence")
    detailroot = Path("/synthetic-dex-private/d1-e1b-20261004/source-evidence")
    monkeypatch.setattr(d1c, "PRIVATE", rawroot.parents[1])
    original_read, original_digest = d1c.read, d1c.digest
    universe = original_read(root / "config/sealed/2026-10-04/universe.json")
    package = original_read(root / "config/sealed/2026-10-04-151/package.json")
    virtual = {rawroot / "sets.raw": [{"id": r["id"].split(":", 2)[2]} for r in universe["sets"]]}
    for entry in universe["sets"]:
        path = rawroot / ("series-" + entry["series"] + ".raw")
        series = virtual.setdefault(path, {"name": "Synthetic series", "sets": []})
        series["sets"].append(
            {"id": entry["id"].split(":", 2)[2], "cardCount": {"total": entry["expected_printings"]}}
        )
    for key in ["series", "set151", "official-checklist", "sg"]:
        virtual[rawroot / (key + ".raw")] = {"synthetic": key}
    index = {
        path.stem: {"sha256": hashlib.sha256(json.dumps(value).encode()).hexdigest()}
        for path, value in virtual.items()
    }
    virtual[root / "config/sealed/2026-10-04/source-index.json"] = index
    virtual[detailroot / "retained-hashes.json"] = {}
    virtual[detailroot / "index.json"] = {}
    virtual[rawroot.parents[1] / "d1-e1b-20261004/rehearsal-evidence-3/report.json"] = {
        "printings_bridged": [{"printing_id": r["id"]} for r in package["printings"]],
        "booster_memberships_evidenced": 207,
    }
    refs = []
    for code, entry in universe["existing_shipped_packages"].items():
        cp = original_read(root / entry["package"])
        identity = (
            "set:pokemon:" + cp["reconcile_legacy_set"]
            if cp.get("reconcile_legacy_set")
            else "catalog-set:pokemon:en:" + code
        )
        refs.append(
            {
                "version": cp["version"],
                "set_id": str(uuid.uuid5(uuid.UUID("c40655cd-2748-49cc-877f-88c05d3a4473"), identity)),
            }
        )
    virtual[root / "evidence/e6a-20261005/rehearsal-final/version-1.json"] = {
        "goal": {"definition": {"catalog_references": refs}}
    }
    pinned = root / "config/sealed/2026-10-04/universe.json"
    virtual[d1c.OUT / "inputs.json"] = {"files": {str(pinned): original_digest(pinned)}}

    def read(path):
        path = Path(path)
        if path in virtual:
            return copy.deepcopy(virtual[path])
        # Fail closed instead of accidentally reading local evidence or owner data.
        assert path.is_relative_to(root / "config"), f"Unmodeled private input: {path}"
        return original_read(path)

    def digest(path):
        path = Path(path)
        if path in virtual:
            return hashlib.sha256(json.dumps(virtual[path]).encode()).hexdigest()
        assert path.is_relative_to(root / "config"), f"Unmodeled private hash: {path}"
        return original_digest(path)

    monkeypatch.setattr(d1c, "read", read)
    monkeypatch.setattr(d1c, "digest", digest)


def collect(mutator=None):
    outputs = {}
    original = d1c.read

    def read(path):
        value = original(path)
        return mutator(Path(path), value) if mutator else value

    with (
        patch.object(d1c, "read", read),
        patch.object(d1c, "write", lambda name, value, check: outputs.update({name: value})),
    ):
        d1c.run()
    return outputs


def test_retained_totals_and_digital_promos():
    result = collect()
    totals = result["per-set.json"]["totals"]
    assert totals["sets"] == 220
    assert totals["reviewed_numbered"] == 1198
    assert totals["reviewed_catalog_records"] == 1375
    assert totals["absent_physical"] == 193
    rows = result["per-set.json"]["rows"]
    assert all(r["classification"] == "digital-only" for r in rows if r["medium"] == "digital")
    assert sum(len(r["unresolved_variant_relationships"]) for r in rows) == 177


def test_source_drift_fails_before_output():
    with patch.object(d1c, "digest", return_value="wrong"), patch.object(d1c, "write") as writer:
        with pytest.raises(AssertionError, match="Source hash mismatch"):
            d1c.run()
        writer.assert_not_called()


@pytest.mark.parametrize("failure", ["series-count", "duplicate-printing", "language"])
def test_conflict_excludes_affected_set_and_continues(failure):
    def mutate(path, value):
        if failure == "series-count" and path.name == "series-base.raw":
            next(r for r in value["sets"] if r["id"] == "base1")["cardCount"]["total"] += 1
        if path == d1c.ROOT / "config/catalog-imports/staging-ten/base_set.json":
            if failure == "duplicate-printing":
                value["cards"].append(value["cards"][0])
            if failure == "language":
                value["language"] = "fr"
        return value

    outputs = collect(mutate)
    rows = {r["set_code"]: r for r in outputs["per-set.json"]["rows"]}
    assert rows["base1"]["numbered_status"] == "identity-conflicted"
    assert rows["base1"]["confirmed_numbered_count"] == 0
    assert rows["base2"]["confirmed_numbered_count"] == 64
    assert rows["sv03.5"]["confirmed_numbered_count"] == 207
    assert len(rows) == 220
    totals = outputs["per-set.json"]["totals"]
    assert totals["reviewed_numbered"] + totals["numbered_count_gap"] == totals["expected_numbered"]
