"""Isolated LV readiness cases; never customer or provider evidence."""

import hashlib
import json
import sqlite3
from datetime import timedelta

import pytest
from test_hunter_coverage_audit import NOW, file_bytes, install
from test_hunter_coverage_audit import audit_module as audit_module
from test_hunter_coverage_audit import audit_root as audit_root

from pokemon_hunter.beta import lot_value_readiness as readiness
from pokemon_hunter.beta import price_snapshot_contract as rules
from pokemon_hunter.beta import reference_inventory as inventory


def prepare_schema(root):
    with sqlite3.connect(root / "inventory.db") as db:
        db.executescript("""
          CREATE TABLE catalog_read_schema(version INTEGER);
          CREATE TABLE account_read_schema(version INTEGER);
          CREATE TABLE catalog_read_revision(id INTEGER,value INTEGER);
          CREATE TABLE catalog_read_active(id INTEGER,build INTEGER);
          CREATE TABLE catalog_read_builds(id INTEGER,policy TEXT,status TEXT,revision INTEGER);
          INSERT INTO catalog_read_revision VALUES(1,7);
          INSERT INTO catalog_read_active VALUES(1,1);
        """)
        db.execute("INSERT INTO catalog_read_schema VALUES(?)", (readiness.VERSION,))
        db.execute("INSERT INTO account_read_schema VALUES(?)", (readiness.ACCOUNT_VERSION,))
        db.execute("INSERT INTO catalog_read_builds VALUES(1,?,'ready',7)", (readiness.POLICY,))


def assert_private(report):
    rendered = json.dumps(report)
    for forbidden in (
        "876.543",
        "sensitive-test-review",
        "fabricated-product",
        "example.test",
        "Synthetic private source",
        "original_money",
        "source_url",
        "api_key",
    ):
        assert forbidden not in rendered


def codes(report):
    return {row["code"] for row in report["reasons"]}


def test_absence_approvals_and_no_setup_or_pruning(audit_root, monkeypatch):
    root, _, _ = audit_root
    prepare_schema(root)
    (root / "price-contracts.json").write_text(json.dumps({"private-review": "a" * 64}))
    from pokemon_hunter.beta import cli, price_snapshots

    def forbidden(*args, **kwargs):
        raise AssertionError("Readiness must never initialize, acquire, prune or activate")

    for name in ("current", "display_current", "purge_expired", "activate", "atomic", "locked"):
        monkeypatch.setattr(price_snapshots, name, forbidden)
    monkeypatch.setattr(cli, "setup", forbidden)
    before = file_bytes(root.parent)
    report = readiness.project(root, now=NOW)
    assert file_bytes(root.parent) == before
    assert report["runtime"]["compatible_with_checkout"]
    assert report["catalog"]["printings"] == 3
    assert report["contract_approvals"] == 1
    assert report["coverage"]["eligible_raw_guide_printings"] == 0
    assert "missing_snapshot" in codes(report)
    assert not report["ready"]
    assert_private(report)


def test_admitted_guide_is_not_condition_applicable_or_real_fixture_evidence(audit_root):
    root, _, value = audit_root
    prepare_schema(root)
    install(root, value)
    before = file_bytes(root.parent)
    report = readiness.project(root, now=NOW)
    assert file_bytes(root.parent) == before
    assert report["coverage"]["eligible_raw_guide_printings"] == 1
    assert report["coverage"]["condition_applicable_raw_printings"] == 0
    assert report["snapshots"]["eligible_raw_condition_unspecified"] == 1
    assert "raw_condition_capability_missing" in codes(report)
    assert "fixture_evidence_only" in codes(report)
    assert report["evidence_class"] == "isolated_engineering"
    assert_private(report)


@pytest.mark.parametrize("state", ["stale", "expired", "withdrawn", "unadmitted", "invalid"])
def test_source_lifecycle_withholds_values_without_cleanup(audit_root, state):
    root, _, value = audit_root
    prepare_schema(root)
    if state == "stale":
        for row in value["records"]:
            row["as_of"] = (NOW - timedelta(days=31)).date().isoformat()
    elif state == "expired":
        value["expires_at"] = NOW.isoformat()
    elif state == "invalid":
        value["records"][0]["currency"] = "GBP"
    registry = install(root, value)
    if state == "withdrawn":
        registry.write_text(json.dumps([value["version"]]))
    elif state == "unadmitted":
        (root / "price-contracts.json").write_text("{}")
    before = file_bytes(root.parent)
    report = readiness.project(root, now=NOW)
    assert file_bytes(root.parent) == before
    assert report["coverage"]["eligible_raw_guide_printings"] == 0
    assert report["snapshots"]["records_" + state] == 4
    if state != "stale":
        assert "sources_" + state in codes(report)
    assert_private(report)


@pytest.mark.parametrize("change", ["schema", "duplicate_schema", "policy", "stale", "missing"])
def test_incompatible_catalog_is_not_runtime_ready(audit_root, change):
    root, _, _ = audit_root
    prepare_schema(root)
    with sqlite3.connect(root / "inventory.db") as db:
        if change == "schema":
            db.execute("UPDATE account_read_schema SET version=2")
        elif change == "duplicate_schema":
            db.execute("INSERT INTO catalog_read_schema VALUES(99)")
        elif change == "policy":
            db.execute("UPDATE catalog_read_builds SET policy='previous'")
        elif change == "stale":
            db.execute("UPDATE catalog_read_revision SET value=8")
        else:
            db.execute("DROP TABLE catalog_read_active")
    before = file_bytes(root.parent)
    report = readiness.project(root, now=NOW)
    assert file_bytes(root.parent) == before
    assert not report["runtime"]["compatible_with_checkout"]
    assert "runtime_incompatible" in codes(report)
    assert report["catalog"]["printings"] == 3


def test_pinned_legacy_has_separate_age_and_condition_metadata(audit_root, monkeypatch):
    root, _, _ = audit_root
    rows = [
        dict(
            card_id="vintage",
            grade="raw",
            as_of="2026-09-01",
            value="876.543",
            edition="standard",
            currency="USD",
            grader="Guide",
            source_url="https://example.test/x",
        )
    ]
    parent = root / "parity-evidence"
    parent.mkdir()
    path = parent / "market_values.json"
    path.write_text(json.dumps(rows))
    original = inventory.legacy_metadata
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    monkeypatch.setattr(
        inventory, "legacy_metadata", lambda *a, **kw: original(*a, expected_sha256=digest, **kw)
    )
    before = file_bytes(root.parent)
    report = readiness.project(root, now=NOW)
    assert file_bytes(root.parent) == before
    assert report["retained_guides"]["raw_condition_unavailable"] == 1
    assert report["retained_guides"]["records_stale"] == 1
    assert report["coverage"]["condition_applicable_raw_printings"] == 0
    assert_private(report)


def split_install(root, value):
    registry = install(root, value)
    base = root / "price-snapshots"
    digest = rules.digest(value["contract"])
    descriptor = dict(
        schema="dex-price-release-v2",
        version=value["version"],
        release_month=value["release_month"],
        sources={
            digest: dict(
                review_id=value["contract"]["review_id"], expires_at=value["expires_at"], fixture=False
            )
        },
    )
    directory = base / value["version"]
    directory.mkdir()
    (directory / (digest + ".json")).write_text(json.dumps(value))
    (base / (value["version"] + ".json")).write_text(json.dumps(descriptor))
    (base / "versions.json").write_text(
        json.dumps(
            {value["version"]: dict(sha256=rules.digest(descriptor), sources={digest: rules.digest(value)})}
        )
    )
    source_registry = registry.with_name(registry.stem + "-sources.json")
    source_registry.write_text(json.dumps(dict(contracts=[], releases=[])))
    return directory / (digest + ".json"), source_registry, digest


@pytest.mark.parametrize("state", ["expired", "withdrawn", "unadmitted"])
def test_removed_split_shards_keep_lifecycle_reason_not_invented_row_counts(audit_root, state):
    root, _, value = audit_root
    if state == "expired":
        value["expires_at"] = NOW.isoformat()
    shard, registry, digest = split_install(root, value)
    shard.unlink()
    if state == "withdrawn":
        registry.write_text(json.dumps(dict(contracts=[digest], releases=[])))
    elif state == "unadmitted":
        (root / "price-contracts.json").write_text("{}")
    before = file_bytes(root.parent)
    report = readiness.project(root, now=NOW)
    assert file_bytes(root.parent) == before
    assert report["snapshots"]["sources_" + state] == 1
    assert report["snapshots"].get("records", 0) == 0
    assert "sources_" + state in codes(report)


def test_fixture_provider_cannot_be_admitted_into_ordinary_root(audit_root):
    root, _, value = audit_root
    (root / "SYNTHETIC_ONLY").unlink()
    value["contract"]["provider"] = "dex-engineering-fixture"
    install(root, value)
    report = readiness.project(root, now=NOW)
    assert report["coverage"]["eligible_raw_guide_printings"] == 0
    assert report["snapshots"]["sources_fixture_rejected"] == 1


@pytest.mark.parametrize(
    "problem", ["missing_registry", "malformed", "link", "row_bound", "report_bound", "changed"]
)
def test_fail_closed_sanitized_and_non_mutating(audit_root, monkeypatch, problem):
    root, _, value = audit_root
    registry = install(root, value)
    if problem == "missing_registry":
        registry.unlink()
    elif problem == "malformed":
        (root / "price-contracts.json").write_text('"876.543 private data"')
    elif problem == "link":
        path = root / "price-contracts.json"
        path.rename(root / "private.json")
        path.symlink_to(root / "private.json")
    elif problem == "report_bound":
        monkeypatch.setattr(readiness, "MAX_REPORT_BYTES", 64)
    elif problem == "row_bound":
        monkeypatch.setattr(inventory, "MAX_CATALOG_ROWS", 2)
    else:
        original = inventory.ReadBudget.finish

        def changed(self):
            self.paths[root / "inventory.db"] = None
            return original(self)

        monkeypatch.setattr(inventory.ReadBudget, "finish", changed)
    before = file_bytes(root.parent)
    report = readiness.project(root, now=NOW)
    assert file_bytes(root.parent) == before
    assert report["state"] == "unavailable"
    assert codes(report) == {"inspection_failed"}
    assert_private(report)


def test_identity_changed_cannot_count_as_eligible(audit_root):
    root, _, value = audit_root
    install(root, value)
    with sqlite3.connect(root / "inventory.db") as db:
        db.execute("UPDATE printings SET edition='first_edition'")
    report = readiness.project(root, now=NOW)
    assert report["coverage"]["eligible_raw_guide_printings"] == 0
    assert report["snapshots"]["records_inapplicable"] == 4


def test_priority_does_not_narrow_catalog(audit_root):
    root, _, _ = audit_root
    with sqlite3.connect(root / "inventory.db") as db:
        for i, name in enumerate(("Fossil", "Base Set", "Jungle")):
            db.execute(
                "INSERT INTO catalog_sets VALUES(?, 'pokemon',?,'v1','indexed','published')", (str(i), name)
            )
            db.execute(
                "INSERT INTO printings SELECT ?,?,collector_number,language,edition,finish,variant,attributes,provenance,publication_state FROM printings LIMIT 1",
                (str(i), str(i)),
            )
    report = readiness.project(root, now=NOW)
    assert [s["set_name"] for s in report["supported_scope"]] == [
        "Base Set",
        "Jungle",
        "Fossil",
        "Synthetic Set",
    ]
    assert sum(s["catalog_printings"] for s in report["supported_scope"]) == 6


def test_split_release_requires_existing_prepared_index(audit_root):
    root, _, value = audit_root
    shard, _, digest = split_install(root, value)
    before = file_bytes(root.parent)
    report = readiness.project(root, now=NOW)
    assert file_bytes(root.parent) == before
    assert report["coverage"]["eligible_raw_guide_printings"] == 0
    assert "sources_preparation_missing" in codes(report)
    # Build an isolated canonical index using the existing operator writer, then
    # prove readiness uses it without invoking preparation on a read.
    from pokemon_hunter.beta import price_snapshot_index as index
    from pokemon_hunter.beta import price_snapshots as storage

    shard.parent.chmod(0o700)
    shard.parent.parent.chmod(0o700)
    storage.atomic(shard, value)
    idx = index.prepare(shard, value, rules.digest(value))
    seals = root / "price-snapshots/versions.json"
    data = json.loads(seals.read_text())
    data[value["version"]]["indexes"] = {digest: idx}
    seals.write_text(json.dumps(data))
    before = file_bytes(root.parent)
    report = readiness.project(root, now=NOW)
    assert file_bytes(root.parent) == before
    assert report["coverage"]["eligible_raw_guide_printings"] == 1
    assert "sources_preparation_missing" not in codes(report)


@pytest.mark.parametrize("days,expected", [(30, 1), (31, 0)])
def test_publisher_build_is_conditional_not_raw_condition_or_new_valuation(audit_root, days, expected):
    root, _, value = audit_root
    row = value["records"][0]
    value["records"] = [row]
    row.update(
        field="marketPrice",
        grader="Guide",
        as_of=None,
        match_scope="conditional_market",
        reference_as_of=(NOW - timedelta(days=days)).date().isoformat(),
        publisher_built_at=(NOW - timedelta(days=days)).isoformat(),
    )
    policy = value["contract"]
    policy["provider"] = "TCGCSV"
    field = dict(
        policy["fields"]["price-raw"],
        grader="Guide",
        identity_scope="conditional_market",
        date_basis="publisher_build",
        valuation_date_field=None,
        reference_date_field="last-updated.txt",
    )
    policy["fields"] = {"marketPrice": field}
    row["provider_identity"].update(edition="unlimited", finish="normal", variant="Unlimited")
    install(root, value)
    report = readiness.project(root, now=NOW)
    assert report["coverage"]["eligible_raw_guide_printings"] == expected
    assert report["coverage"]["condition_applicable_raw_printings"] == 0
    assert report["snapshots"]["date_basis_publisher_build"] == 1
    assert "date_basis_valuation" not in report["snapshots"]
    assert_private(report)


def test_expired_deadline_never_reports_partial_success(audit_root, monkeypatch):
    root, _, _ = audit_root
    original = inventory.ReadBudget.__init__

    def expired(self):
        original(self)
        self.deadline = 0

    monkeypatch.setattr(inventory.ReadBudget, "__init__", expired)
    before = file_bytes(root.parent)
    assert readiness.project(root, now=NOW)["state"] == "unavailable"
    assert file_bytes(root.parent) == before


def test_wal_layout_is_refused_without_creating_sqlite_sidecars(audit_root):
    root, _, _ = audit_root
    from contextlib import closing

    with closing(sqlite3.connect(root / "inventory.db")) as db:
        assert db.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
    before = file_bytes(root.parent)
    report = readiness.project(root, now=NOW)
    assert report["state"] == "unavailable"
    assert file_bytes(root.parent) == before
