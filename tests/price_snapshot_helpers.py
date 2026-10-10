"""Synthetic snapshot setup/builders shared outside collected test modules."""

import copy
import json
from datetime import timedelta
from uuid import uuid4

import pytest
from django.conf import settings
from test_b1 import env as env
from test_b2 import b2 as b2
from test_lot_calculator import request as request
from test_migration import snapshot as snapshot
from test_shopping import NOW as NOW
from test_shopping import inputs as inputs
from test_shopping import shop as shop

from pokemon_hunter.beta import collection
from pokemon_hunter.beta import lot_calculator as lot
from pokemon_hunter.beta import price_snapshot_contract as rules
from pokemon_hunter.beta import price_snapshots as prices

# Capture the production loader before the inherited Shopping fixture patches it.
RETAINED_RECORDS = lot.retained_records


@pytest.fixture
def setup(shop, monkeypatch):
    monkeypatch.setattr(settings, "ROOT", shop["root"])
    (settings.ROOT / "SYNTHETIC_ONLY").touch()
    collection.execute("UPDATE catalog_sets SET name='Base Set'")
    collection.execute("UPDATE printings SET edition='standard',finish='normal',variant='normal'")
    entries = {p["id"]: p for p in collection.catalog(shop["actor"])}
    monkeypatch.setattr(prices, "entries", lambda: entries)
    # These old fixtures patch the guide loader. Restore the production loader for new-path checks.
    monkeypatch.setattr(lot, "retained_records", RETAINED_RECORDS)
    monkeypatch.setattr(lot, "legacy_records", lambda: shop["guides"])
    original = prices.current
    monkeypatch.setattr(prices, "current", lambda **kw: original(now=kw.get("now", NOW)))
    shop["entries"] = entries
    return shop


def package(setup, *, permanent=True):
    p = next(iter(setup["entries"].values()))
    identity = {k: p.get(k) for k in rules.IDENTITY}
    provider = dict(
        product_id="fabricated-product",
        set=p["set_name"],
        number=p["collector_number"],
        language=p["language"],
        edition=p["edition"],
        finish=p["finish"],
        variant=p["variant"],
        mapping_review="fabricated-independent-review",
    )
    rows = [
        dict(
            observation_id=str(uuid4()),
            printing_id=p["id"],
            identity=identity,
            provider_identity=provider,
            field="price-" + g,
            grade=g,
            grader="Generic guide population",
            original_money=v,
            value=v,
            currency="USD",
            as_of="2026-10-09",
            captured_at=NOW.isoformat(),
            estimated=True,
            estimate_kind="provider_guide",
            source_url="https://example.test/product",
            source_version="synthetic-v1",
        )
        for g, v in zip(rules.COLUMNS, ("2.550001", "7", "11", "19"), strict=True)
    ]
    policy = dict(
        schema="dex-price-contract-v1",
        provider="dex-engineering-fixture",
        review_id="fixture",
        policy_url="https://example.test/policy",
        policy_version="fabricated-v1",
        scope="Test only",
        deletion_policy="Fabricated managed-copy expiry",
        acquisition_policy="No network",
        copy_policy="managed_store_and_permitted_history_no_backups_or_exports",
        rights=dict(
            display=True,
            arithmetic=True,
            private_storage=True,
            immutable_save=permanent,
            noncontent_revocations=True,
        ),
        fields={
            "price-" + g: dict(
                grade=g,
                grader="Generic guide population",
                label="Literal " + g,
                currency_evidence="Fabricated USD",
                valuation_date_field="valued",
                unit="USD_decimal",
                zero_is_value=True,
            )
            for g in rules.COLUMNS
        },
        mappings={
            p["id"]: {
                k: rows[0][k] for k in ("identity", "provider_identity", "source_url", "source_version")
            }
        },
    )
    return dict(
        schema="dex-price-snapshot-v1",
        version=str(uuid4()),
        release_month="2026-10",
        contract=policy,
        expires_at=(NOW + timedelta(days=1)).isoformat() if not permanent else None,
        records=rows,
    )


def stage(value):
    base = prices.directory() / "staging"
    prices.private_mkdir(base)
    path = base / (value["version"] + ".json")
    path.write_text(json.dumps(value))
    path.chmod(0o600)
    return path


def multi_package(setup, *, restricted=True, competing=False):
    first, second = package(setup), package(setup, permanent=not restricted)
    first["contract"]["review_id"] = "fixture-raw"
    second["contract"]["review_id"] = "fixture-graded"
    first["records"] = first["records"][:1]
    second["records"] = second["records"][1:]
    if competing:
        alternate = copy.deepcopy(first["records"][0])
        alternate["observation_id"] = str(uuid4())
        alternate["value"] = alternate["original_money"] = "99"
        alternate["grader"] = "PSA"
        second["contract"]["fields"][alternate["field"]]["grader"] = "PSA"
        second["records"].append(alternate)
    return dict(
        schema="dex-price-snapshot-v2",
        version=str(uuid4()),
        release_month="2026-10",
        contracts={
            p["contract"]["review_id"]: dict(contract=p["contract"], expires_at=p["expires_at"])
            for p in (first, second)
        },
        records=[
            dict(row, contract_id=p["contract"]["review_id"]) for p in (first, second) for row in p["records"]
        ],
    )


def build_reference_package(setup):
    """Fabricated amounts/identity, with the owner-approved source-specific date shape."""
    value = multi_package(setup, restricted=False)
    policy = value["contracts"]["fixture-raw"]["contract"]
    policy["provider"] = "TCGCSV"
    policy["fields"] = {
        "price-raw": dict(
            policy["fields"]["price-raw"],
            date_basis="publisher_build",
            valuation_date_field=None,
            reference_date_field="last-updated.txt",
        )
    }
    row = value["records"][0]
    row.update(as_of=None, reference_as_of="2026-10-09", publisher_built_at="2026-10-09T00:00:00+00:00")
    prices.atomic(settings.ROOT / "price-contracts.json", {"fixture-raw": rules.digest(policy)})
    return value
