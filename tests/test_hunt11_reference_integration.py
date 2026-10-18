"""Synthetic HUNT-11 adapter output through existing reference lifecycle.

No customer state, acquired source records, source permission or live prices are
fixtures. The normal pytest command blocks external sockets for every case.
"""

import copy
import importlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.conf import settings
from price_snapshot_helpers import NOW, package, stage
from price_snapshot_helpers import b2 as b2
from price_snapshot_helpers import env as env
from price_snapshot_helpers import setup as setup
from price_snapshot_helpers import shop as shop
from price_snapshot_helpers import snapshot as snapshot

from pokemon_hunter.beta import collection, hunter_catalog, hunter_lots, lot_calculator
from pokemon_hunter.beta import price_snapshot_contract as rules
from pokemon_hunter.beta import price_snapshots as prices
from pokemon_hunter.beta import tcgcsv_offline as adapter


@pytest.fixture
def reference_case(setup, monkeypatch):
    """Explicitly fabricated broad-set Trainer, Energy and promo identities."""
    template = copy.deepcopy(next(iter(setup["entries"].values())))
    entries = {}
    definitions = (
        ("trainer", "Professor Turo's Scenario", "171/182", "Trainer", None),
        ("energy", "Basic Lightning Energy", "004/182", "Energy", None),
        ("promo", "Pikachu", "SVP001", "Pokémon", 25),
        ("unpriced", "Raichu", "050/182", "Pokémon", 26),
    )
    for key, name, number, supertype, species in definitions:
        attrs = dict(name=name, supertype=supertype)
        if species is not None:
            attrs["pokemon_dex"] = species
        entries[key] = dict(
            template,
            id=key,
            name=name,
            set_id="synthetic-modern",
            set_name="Synthetic Modern Set",
            collector_number=number,
            language="en",
            edition="unlimited",
            finish="normal",
            variant="normal",
            attributes=attrs,
            provenance=json.dumps({"legacy_id": "hunt11-" + key}),
        )
    setup["entries"] = entries
    monkeypatch.setattr(prices, "entries", lambda: entries)
    monkeypatch.setattr(collection, "catalog", lambda *args, **kwargs: list(entries.values()))
    monkeypatch.setattr(lot_calculator, "legacy_records", lambda: [])
    directory = prices.directory() / "staging" / "synthetic-input"
    prices.private_mkdir(directory)
    policy = package(setup)["contract"]
    policy.update(
        provider="TCGCSV",
        review_id="hunt11-synthetic-independent-review",
        scope="Fabricated schema integration evidence only",
    )
    policy["rights"]["immutable_save"] = False
    policy["fields"] = {
        "marketPrice": dict(
            grade="raw",
            grader="TCGplayer ungraded market",
            label="Synthetic ungraded market reference across conditions",
            currency_evidence="Fabricated USD schema evidence",
            valuation_date_field=None,
            reference_date_field="last-updated.txt",
            date_basis="publisher_build",
            identity_scope="conditional_market",
            unit="USD_decimal",
            zero_is_value=False,
        )
    }
    policy["mappings"] = {}
    built_at = "2026-10-09T00:00:00+00:00"
    products, source_prices, bindings = [], [], []
    for product_id, key in enumerate(("trainer", "energy", "promo"), 100):
        printing = entries[key]
        url = "https://example.test/synthetic-product/" + str(product_id)
        policy["mappings"][key] = dict(
            identity={k: printing.get(k) for k in rules.IDENTITY},
            provider_identity=dict(
                product_id=str(product_id),
                set=printing["set_name"],
                number=printing["collector_number"],
                language="en",
                edition="unlimited",
                finish="normal",
                variant="Unlimited",
                mapping_review="Explicit fabricated product and subtype binding",
            ),
            source_url=url,
            source_version="tcgcsv-build-" + built_at,
        )
        products.append(
            dict(
                productId=product_id,
                categoryId=3,
                groupId=700,
                name=printing["name"],
                url=url,
                extendedData=[dict(name="Number", value=printing["collector_number"])],
            )
        )
        source_prices.append(dict(productId=product_id, subTypeName="Unlimited", marketPrice=2.5))
        bindings.append(
            dict(
                printing_id=key,
                group_id=700,
                product_id=product_id,
                sub_type_name="Unlimited",
                product_name=printing["name"],
                collector_number=printing["collector_number"],
            )
        )
    products_path, prices_path = directory / "products.json", directory / "prices.json"
    prices.atomic(products_path, dict(totalItems=len(products), success=True, errors=[], results=products))
    prices.atomic(prices_path, dict(success=True, errors=[], results=source_prices))
    manifest = dict(
        schema="dex-tcgcsv-offline-v1",
        publisher_built_at=built_at,
        captured_at=NOW.isoformat(),
        expires_at=(NOW + timedelta(days=1)).isoformat(),
        contract=policy,
        shards=[dict(group_id=700, products=products_path.name, prices=prices_path.name)],
        bindings=bindings,
    )
    return dict(setup=setup, entries=entries, directory=directory, manifest=manifest)


def prepare(case, *, baseline=()):
    return adapter.prepare(
        case["entries"],
        case["manifest"],
        input_directory=case["directory"],
        now=NOW,
        baseline_eligible=baseline,
    )


def admit(value):
    registry = {key: rules.digest(part["contract"]) for key, part in value["contracts"].items()}
    prices.atomic(settings.ROOT / "price-contracts.json", registry)


def test_preparation_is_nonactivating_and_coverage_counts_reconcile(reference_case):
    case = reference_case
    before = {p: p.read_bytes() for p in case["directory"].iterdir()}
    value, report = prepare(case, baseline={"unpriced", "trainer"})
    assert value["schema"] == "dex-price-snapshot-v2"
    assert {r["printing_id"] for r in value["records"]} == {"trainer", "energy", "promo"}
    assert prices.state()["current"] is None
    assert not (settings.ROOT / "price-contracts.json").exists()
    assert {p: p.read_bytes() for p in case["directory"].iterdir()} == before
    assert report["catalog_printings"] == 4
    assert report["eligible_printings"] == 3
    assert report["baseline_eligible_printings"] == 2
    assert report["newly_eligible_printings"] == 2
    assert report["projected_eligible_printings"] == 4
    assert sum(report["decisions"].values()) == report["catalog_printings"]
    rendered = json.dumps(report)
    assert "2.5" not in rendered and "example.test" not in rendered
    assert "source_version" not in rendered and "source_contract" not in rendered


def test_prepared_source_requires_independent_admission_before_activation(reference_case):
    value, _ = prepare(reference_case)
    path = stage(value)
    with pytest.raises(ValueError, match="admission disabled"):
        prices.activate(path, None, now=NOW)
    assert path.is_file() and prices.state()["current"] is None
    admit(value)
    prices.activate(path, None, now=NOW)
    assert not path.exists()
    records, status = prices.current(now=NOW)
    assert status == "active_snapshot" and len(records) == 3
    assert all(r["as_of"] is None for r in records)
    assert all(r["reference_as_of"] == "2026-10-09" for r in records)


@pytest.mark.parametrize("failure", ["source_shard", "active_pointer"])
def test_prepared_release_failure_preserves_previous_atomic_activation(reference_case, monkeypatch, failure):
    case = reference_case
    first = package(case["setup"])
    prices.activate(stage(first), None, now=NOW)
    old_pointer = (prices.directory() / "active.json").read_bytes()
    old_file = (prices.directory() / (first["version"] + ".json")).read_bytes()
    value, _ = prepare(case)
    admit(value)
    original = prices.atomic

    def interrupted(path, data):
        if failure == "active_pointer" and path.name == "active.json":
            raise OSError("Synthetic interrupted pointer update")
        if failure == "source_shard" and path.parent.name == value["version"]:
            raise OSError("Synthetic interrupted source shard write")
        return original(path, data)

    monkeypatch.setattr(prices, "atomic", interrupted)
    with pytest.raises(OSError, match="Synthetic interrupted"):
        prices.activate(stage(value), first["version"], now=NOW)
    assert (prices.directory() / "active.json").read_bytes() == old_pointer
    assert (prices.directory() / (first["version"] + ".json")).read_bytes() == old_file
    assert prices.state()["current"] == first["version"]


@pytest.mark.parametrize("lifecycle", ["expiry", "withdrawal"])
def test_prepared_source_lifecycle_keeps_independent_source_bytes(reference_case, lifecycle):
    case = reference_case
    value, _ = prepare(case)
    source_id = next(iter(value["contracts"]))
    digest = rules.digest(value["contracts"][source_id]["contract"])
    other = package(case["setup"])
    other["contract"]["review_id"] = "independent-synthetic-source"
    value["contracts"]["independent-synthetic-source"] = dict(
        contract=other["contract"], expires_at=other["expires_at"]
    )
    value["records"].extend(dict(row, contract_id="independent-synthetic-source") for row in other["records"])
    admit(value)
    prices.activate(stage(value), None, now=NOW)
    other_digest = rules.digest(other["contract"])
    stable = prices.sources.shard(value["version"], other_digest)
    removable = prices.sources.shard(value["version"], digest)
    old_bytes, removed_bytes = stable.read_bytes(), removable.read_bytes()
    if lifecycle == "withdrawal":
        prices.sources.remove_source(digest)
    else:
        prices.purge_expired(now=NOW + timedelta(days=2))
    assert stable.read_bytes() == old_bytes
    assert not removable.exists()
    assert {r["_review_id"] for r in prices.current(now=NOW)[0]} == {"independent-synthetic-source"}
    removable.write_bytes(removed_bytes)
    assert {r["_review_id"] for r in prices.current(now=NOW)[0]} == {"independent-synthetic-source"}
    assert not removable.exists()


def listing(printing, **changes):
    raw = dict(
        itemId="synthetic-hunt11-single",
        title=(
            f"{printing['name']} {printing['set_name']} {printing['collector_number']} "
            "English Unlimited Non Holo"
        ),
        condition="Near Mint",
        buyingOptions=["FIXED_PRICE"],
        price=dict(value="1.00", currency="USD"),
        shippingOptions=[dict(shippingCost=dict(value="0.50", currency="USD"))],
    )
    return dict(raw, **changes)


def test_prepared_trainer_energy_references_flow_to_hunter_with_unknown_costs(reference_case):
    case = reference_case
    value, _ = prepare(case)
    admit(value)
    prices.activate(stage(value), None, now=NOW)
    rows = hunter_catalog.compare(
        case["setup"]["actor"],
        [listing(case["entries"][key], itemId=key) for key in ("trainer", "energy")],
        now=NOW,
    )
    assert len(rows) == 2
    for row in rows:
        assert row["reference"]["amount"] == "2.5"
        assert row["reference"]["valuation_as_of"] is None
        assert row["reference"]["date_basis"] == "publisher_build"
        assert row["hunt_status"] == "conditional"
        assert row["tax"] is None and row["delivered_total"] is None


def test_prepared_lot_values_only_included_applicable_units(reference_case, monkeypatch):
    case = reference_case
    value, _ = prepare(case)
    admit(value)
    prices.activate(stage(value), None, now=NOW)

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW.astimezone(tz or timezone.utc)

    monkeypatch.setattr(hunter_lots, "datetime", FixedDatetime)
    raw = listing(
        case["entries"]["trainer"],
        title="Pokemon lot of 4 cards",
        shortDescription=(
            "2x Professor Turo's Scenario Synthetic Modern Set 171/182 English Unlimited Non Holo; "
            "1x Basic Lightning Energy Synthetic Modern Set 004/182 English Unlimited Non Holo; "
            "1x Raichu Synthetic Modern Set 050/182 English Unlimited Non Holo"
        ),
    )
    entries = list(case["entries"].values())
    proposal = hunter_lots.parse(raw, entries)
    _, comparison = hunter_lots._compare(case["setup"]["actor"], raw, proposal, None, entries)
    assert comparison["priced_card_quantity"] == 3
    assert comparison["unpriced_card_quantity"] == 1
    assert comparison["result"]["known_selected_subtotal"] == "7.50"
    assert comparison["result"]["full_selected_total"] is None
    assert comparison["whole_lot_price_count"] == 1
    assert not comparison["complete_delivered_comparison"]
    assert {r["printing_id"] for r in comparison["unpriced_matches"]} == {"unpriced"}


def test_failed_later_input_shard_cannot_change_existing_release(reference_case):
    case = reference_case
    first = package(case["setup"])
    prices.activate(stage(first), None, now=NOW)
    before = (prices.directory() / "active.json").read_bytes()
    second = case["directory"] / "truncated-products.json"
    second.write_text('{"success":true,"results":[')
    case["manifest"]["shards"].append(dict(group_id=701, products=second.name, prices="prices.json"))
    with pytest.raises(ValueError):
        prepare(case)
    assert (prices.directory() / "active.json").read_bytes() == before
    assert prices.state()["current"] == first["version"]


@pytest.fixture
def prepare_script(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    return importlib.import_module("prepare_tcgcsv_offline")


def script_args(case, tmp_path, *, staged=False, expected_current="none"):
    manifest = case["directory"] / "manifest.json"
    prices.atomic(manifest, case["manifest"])
    return SimpleNamespace(
        root=settings.ROOT,
        manifest=manifest,
        report=tmp_path / "synthetic-projection.json",
        stage=prices.directory() / "staging" / "synthetic-prepared.json" if staged else None,
        expected_current=expected_current if staged else None,
        expected_contract_sha256=rules.digest(case["manifest"]["contract"]) if staged else None,
    )


def bytes_under(path):
    return {str(p.relative_to(path)): p.read_bytes() for p in path.rglob("*") if p.is_file()}


def catalog_for_script(script, case, monkeypatch):
    monkeypatch.setattr(script.audit, "catalog_metadata", lambda root: case["entries"])

    def prohibited(*args, **kwargs):
        raise AssertionError("Preparation must not invoke a pruning lifecycle reader")

    monkeypatch.setattr(prices, "current", prohibited)
    monkeypatch.setattr(prices, "display_current", prohibited)
    monkeypatch.setattr(prices, "purge_expired", prohibited)


def test_operator_dry_run_writes_only_nonprice_report(reference_case, prepare_script, monkeypatch, tmp_path):
    case, script = reference_case, prepare_script
    args = script_args(case, tmp_path)
    catalog_for_script(script, case, monkeypatch)
    before = bytes_under(settings.ROOT)
    result = script.run(args, now=NOW)
    assert bytes_under(settings.ROOT) == before
    assert not result["staged"] and not result["activated"]
    assert result["customer_writes"] == result["provider_operations"] == 0
    assert result["actual_acquired_coverage_increase"] == 0
    assert json.loads(args.report.read_text()) == result
    assert args.report.stat().st_mode & 0o077 == 0
    rendered = args.report.read_text()
    assert "2.5" not in rendered and "example.test" not in rendered
    assert "Fabricated USD" not in rendered and "provider_identity" not in rendered
    assert not (prices.directory() / "active.json").exists()


@pytest.mark.parametrize("rejection", ["unadmitted", "contract_changed", "current_changed", "bad_report"])
def test_operator_staging_refuses_before_writing_candidate(
    reference_case, prepare_script, monkeypatch, tmp_path, rejection
):
    case, script = reference_case, prepare_script
    args = script_args(case, tmp_path, staged=True)
    if rejection != "unadmitted":
        prices.atomic(
            settings.ROOT / "price-contracts.json",
            {case["manifest"]["contract"]["review_id"]: args.expected_contract_sha256},
        )
    if rejection == "contract_changed":
        args.expected_contract_sha256 = "0" * 64
    elif rejection == "current_changed":
        args.expected_current = "11111111-1111-4111-8111-111111111111"
    elif rejection == "bad_report":
        args.report.write_text("Preserve this existing report")
    catalog_for_script(script, case, monkeypatch)
    before = bytes_under(settings.ROOT)
    with pytest.raises((ValueError, script.audit.AuditFailure)):
        script.run(args, now=NOW)
    assert bytes_under(settings.ROOT) == before
    assert not args.stage.exists()
    if rejection == "bad_report":
        assert args.report.read_text() == "Preserve this existing report"
    else:
        assert not args.report.exists()


def test_operator_staging_carries_current_source_without_activation(
    reference_case, prepare_script, monkeypatch, tmp_path
):
    case, script = reference_case, prepare_script
    first = package(case["setup"])
    prices.activate(stage(first), None, now=NOW)
    args = script_args(case, tmp_path, staged=True, expected_current=first["version"])
    prices.atomic(
        settings.ROOT / "price-contracts.json",
        {case["manifest"]["contract"]["review_id"]: args.expected_contract_sha256},
    )
    catalog_for_script(script, case, monkeypatch)
    before = bytes_under(settings.ROOT)
    result = script.run(args, now=NOW)
    candidate = prices.read(args.stage)
    assert result["staged"] and not result["activated"]
    assert result["preserved_source_count"] == 1
    assert result["provider_operations"] == result["actual_acquired_coverage_increase"] == 0
    assert candidate["contracts"]["fixture"]["contract"] == first["contract"]
    assert [
        {k: v for k, v in row.items() if k != "contract_id"}
        for row in candidate["records"]
        if row["contract_id"] == "fixture"
    ] == first["records"]
    relative_candidate = str(args.stage.relative_to(settings.ROOT))
    after = bytes_under(settings.ROOT)
    assert set(after) - set(before) == {relative_candidate}
    assert {k: v for k, v in after.items() if k != relative_candidate} == before
    assert args.stage.stat().st_mode & 0o077 == 0
    assert prices.state()["current"] == first["version"]


def test_operator_malformed_retained_shard_leaves_no_stage_or_report(
    reference_case, prepare_script, monkeypatch, tmp_path
):
    case, script = reference_case, prepare_script
    args = script_args(case, tmp_path, staged=True)
    source = case["directory"] / "prices.json"
    source.write_text('{"success":true,"results":[')
    catalog_for_script(script, case, monkeypatch)
    before = bytes_under(settings.ROOT)
    with pytest.raises(ValueError):
        script.run(args, now=NOW)
    assert bytes_under(settings.ROOT) == before
    assert not args.stage.exists() and not args.report.exists()


def test_operator_refuses_partial_same_source_replacement_projection(
    reference_case, prepare_script, monkeypatch, tmp_path
):
    case, script = reference_case, prepare_script
    first, _ = prepare(case)
    admit(first)
    prices.activate(stage(first), None, now=NOW)
    args = script_args(case, tmp_path, staged=True, expected_current=first["version"])
    source = case["directory"] / "prices.json"
    partial = prices.read(source)
    partial["results"] = partial["results"][:1]
    prices.atomic(source, partial)
    # The unchanged contract still maps all three old rows, but only one new
    # row survives this partial input. A baseline union would overstate the
    # eventual replacement's eligible identities, so staging must refuse.
    catalog_for_script(script, case, monkeypatch)
    before = bytes_under(settings.ROOT)
    with pytest.raises(ValueError, match="replacement"):
        script.run(args, now=NOW)
    assert bytes_under(settings.ROOT) == before
    assert prices.state()["current"] == first["version"]
    assert not args.stage.exists() and not args.report.exists()


def test_operator_catalog_change_after_projection_refuses_staging(
    reference_case, prepare_script, monkeypatch, tmp_path
):
    case, script = reference_case, prepare_script
    args = script_args(case, tmp_path, staged=True)
    prices.atomic(
        settings.ROOT / "price-contracts.json",
        {case["manifest"]["contract"]["review_id"]: args.expected_contract_sha256},
    )
    catalog_for_script(script, case, monkeypatch)
    reads = []

    def changing_catalog(root):
        entries = copy.deepcopy(case["entries"])
        if reads:
            entries["trainer"]["collector_number"] = "172/182"
        reads.append(root)
        return entries

    monkeypatch.setattr(script.audit, "catalog_metadata", changing_catalog)
    before = bytes_under(settings.ROOT)
    with pytest.raises(ValueError, match="[Cc]atalog"):
        script.run(args, now=NOW)
    assert len(reads) == 2
    assert bytes_under(settings.ROOT) == before
    assert not args.stage.exists() and not args.report.exists()


@pytest.mark.parametrize(
    "input_issue", ["shared_file", "shared_directory", "symlink", "hardlink", "traversal"]
)
def test_operator_rejects_nonprivate_linked_or_escaping_inputs(
    reference_case, prepare_script, monkeypatch, tmp_path, input_issue
):
    case, script = reference_case, prepare_script
    source = case["directory"] / "prices.json"
    if input_issue == "shared_file":
        source.chmod(0o644)
    elif input_issue == "symlink":
        source.unlink()
        source.symlink_to(case["directory"] / "products.json")
    elif input_issue == "hardlink":
        os.link(source, tmp_path / "outside-managed-source.json")
    elif input_issue == "traversal":
        case["manifest"]["shards"][0]["prices"] = "../prices.json"
    args = script_args(case, tmp_path, staged=True)
    if input_issue == "shared_directory":
        case["directory"].chmod(0o755)
    catalog_for_script(script, case, monkeypatch)
    before = bytes_under(settings.ROOT)
    with pytest.raises(ValueError):
        script.run(args, now=NOW)
    assert bytes_under(settings.ROOT) == before
    assert not args.stage.exists() and not args.report.exists()


def test_new_reviewed_capture_preserves_competing_same_provider_source_and_lifecycle(
    reference_case, prepare_script, monkeypatch, tmp_path
):
    case, script = reference_case, prepare_script
    first, _ = prepare(case)
    admit(first)
    prices.activate(stage(first), None, now=NOW)
    old_key = case["manifest"]["contract"]["review_id"]
    old_source = copy.deepcopy(rules.source_packages(first)[old_key])
    old_digest = rules.digest(old_source["contract"])
    old_shard = prices.sources.shard(first["version"], old_digest)
    old_bytes = old_shard.read_bytes()
    # A distinct actually reviewed capture is additive. It neither replaces the
    # old review nor manufactures a new date or expiry for its observations.
    new_key = old_key + "-next-capture"
    case["manifest"]["contract"]["review_id"] = new_key
    case["manifest"]["expires_at"] = (NOW + timedelta(days=3)).isoformat()
    case["manifest"]["captured_at"] = (NOW + timedelta(hours=1)).isoformat()
    args = script_args(case, tmp_path, staged=True, expected_current=first["version"])
    prices.atomic(
        settings.ROOT / "price-contracts.json",
        {old_key: old_digest, new_key: args.expected_contract_sha256},
    )
    purge_expired = prices.purge_expired
    catalog_for_script(script, case, monkeypatch)
    before = bytes_under(settings.ROOT)
    result = script.run(args, now=NOW + timedelta(hours=1))
    combined = prices.read(args.stage)
    assert result["preserved_source_count"] == 1
    assert rules.source_packages(combined)[old_key]["records"] == old_source["records"]
    assert combined["contracts"][old_key]["expires_at"] == old_source["expires_at"]
    assert combined["contracts"][old_key]["contract"] == old_source["contract"]
    assert old_shard.read_bytes() == old_bytes
    relative_stage = str(args.stage.relative_to(settings.ROOT))
    assert {
        key: value for key, value in bytes_under(settings.ROOT).items() if key != relative_stage
    } == before
    prices.activate(args.stage, first["version"], now=NOW + timedelta(hours=1))
    release = prices.preview(
        prices.directory() / (combined["version"] + ".json"), now=NOW + timedelta(hours=1)
    )
    assert set(release["contracts"]) == {old_key, new_key}
    assert len(release["records"]) == len(first["records"]) * 2
    # Withdrawing the fresh capture leaves the prior admitted evidence intact;
    # neither the old source bytes nor its observation timestamps are renewed.
    monkeypatch.setattr(prices, "purge_expired", lambda: purge_expired(now=NOW + timedelta(hours=1)))
    prices.sources.remove_source(args.expected_contract_sha256)
    surviving = prices.preview(
        prices.directory() / (combined["version"] + ".json"), now=NOW + timedelta(hours=1)
    )
    assert set(surviving["contracts"]) == {old_key}
    assert rules.source_packages(surviving)[old_key]["records"] == old_source["records"]
    assert old_shard.read_bytes() == old_bytes


def test_cross_month_composition_refuses_without_discarding_surviving_source(
    reference_case, prepare_script, monkeypatch, tmp_path
):
    case, script = reference_case, prepare_script
    first = package(case["setup"])
    prices.activate(stage(first), None, now=NOW)
    next_month = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)
    built = "2026-10-31T20:00:00+00:00"
    case["manifest"].update(
        publisher_built_at=built,
        captured_at=next_month.isoformat(),
        expires_at=(next_month + timedelta(days=1)).isoformat(),
    )
    for mapping in case["manifest"]["contract"]["mappings"].values():
        mapping["source_version"] = "tcgcsv-build-" + built
    args = script_args(case, tmp_path, staged=True, expected_current=first["version"])
    prices.atomic(
        settings.ROOT / "price-contracts.json",
        {case["manifest"]["contract"]["review_id"]: args.expected_contract_sha256},
    )
    catalog_for_script(script, case, monkeypatch)
    before = bytes_under(settings.ROOT)
    with pytest.raises(ValueError, match="Cross-month"):
        script.run(args, now=next_month)
    assert bytes_under(settings.ROOT) == before
    assert not args.stage.exists() and not args.report.exists()
    assert prices.state()["current"] == first["version"]
