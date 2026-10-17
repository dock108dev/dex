"""Engineering-only all-era references over real admission/lifecycle services."""

import copy
import json
import sqlite3
from datetime import timedelta
from uuid import uuid4

import pytest
from django.conf import settings
from price_snapshot_helpers import NOW, build_reference_package, package, stage
from price_snapshot_helpers import b2 as b2
from price_snapshot_helpers import env as env
from price_snapshot_helpers import setup as setup
from price_snapshot_helpers import shop as shop
from price_snapshot_helpers import snapshot as snapshot

from pokemon_hunter.beta import catalog_imports, collection, hunter_catalog, lot_calculator, lot_guides
from pokemon_hunter.beta import price_snapshot_contract as rules
from pokemon_hunter.beta import price_snapshots as prices

REAL_ENTRIES = prices.entries


@pytest.fixture
def modern(setup, monkeypatch):
    # Disposable database only; retain the production published-entry selector.
    with sqlite3.connect(settings.ROOT / "inventory.db") as db:
        catalog_imports.initialize(db)
    monkeypatch.setattr(settings, "B4_ENABLED", True)
    collection.execute("UPDATE catalog_sets SET name='Paradox Rift'")
    collection.execute(
        "UPDATE printings SET collector_number='252/182' WHERE id=%s", [next(iter(setup["entries"]))]
    )
    setup["entries"] = {p["id"]: p for p in collection.catalog(setup["actor"])}
    monkeypatch.setattr(prices, "entries", REAL_ENTRIES)
    monkeypatch.setattr(lot_calculator, "legacy_records", lambda: [])
    return setup


def listing(printing, **changes):
    result = dict(
        itemId="engineering-reference-offer",
        title=(
            f"{printing['set_name']} {printing['name']} {printing['collector_number']} "
            "English Unlimited Non Holo"
        ),
        condition="Near Mint",
        buyingOptions=["FIXED_PRICE"],
        price=dict(value="1.00", currency="USD"),
        shippingOptions=[dict(shippingCostType="FIXED", shippingCost=dict(value="0.50", currency="USD"))],
        itemWebUrl="https://www.ebay.com/itm/123",
    )
    result.update(changes)
    return result


def compare(setup, printing, **changes):
    return hunter_catalog.compare(setup["actor"], [listing(printing, **changes)], now=NOW)[0]


def test_all_era_selector_uses_published_pokemon_without_changing_calculator_scope(modern):
    value = package(modern)
    pid = value["records"][0]["printing_id"]
    assert pid in prices.entries()
    assert lot_calculator.catalog(modern["actor"]) == []
    prices.activate(stage(value), None, now=NOW)
    p = modern["entries"][pid]
    row = compare(modern, p)
    assert row["reference"]["amount"] == "2.550001"
    assert row["reference"]["as_of"] == "2026-10-09"
    assert row["reference"]["captured_at"] == NOW.isoformat()
    assert row["hunt_status"] == "conditional"
    assert row["delivered_total"] is None and row["tax"] is None


@pytest.mark.parametrize("mutation", ["archived_printing", "archived_set", "other_game"])
def test_all_era_selector_never_admits_unavailable_or_other_game(modern, mutation):
    value = package(modern)
    pid = value["records"][0]["printing_id"]
    if mutation == "archived_printing":
        collection.execute("UPDATE printings SET publication_state='archived' WHERE id=%s", [pid])
    elif mutation == "archived_set":
        collection.execute("UPDATE catalog_sets SET publication_state='archived'")
    else:
        collection.execute("UPDATE games SET game_key='another-game'")
    assert pid not in prices.entries()
    with pytest.raises(ValueError, match="absent from the installed"):
        prices.activate(stage(value), None, now=NOW)


def test_all_era_selector_cannot_grant_a_source_or_product_mapping(modern):
    value = package(modern)
    path = stage(value)
    (settings.ROOT / "SYNTHETIC_ONLY").unlink()
    value["contract"]["provider"] = "engineering-publisher"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="admission disabled"):
        prices.preview(path, now=NOW)
    prices.atomic(settings.ROOT / "price-contracts.json", {"fixture": rules.digest(value["contract"])})
    assert prices.preview(path, now=NOW)["version"] == value["version"]
    value["records"][0]["provider_identity"] = dict(
        value["records"][0]["provider_identity"], product_id="unmapped-product"
    )
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="reviewed source mapping"):
        prices.preview(path, now=NOW)


def test_all_era_null_value_cannot_replace_an_admitted_release(modern):
    first = package(modern)
    prices.activate(stage(first), None, now=NOW)
    invalid = package(modern)
    invalid["records"][0].update(value=None, original_money=None)
    with pytest.raises(ValueError, match="invalid_decimal"):
        prices.activate(stage(invalid), first["version"], now=NOW)
    assert prices.state()["current"] == first["version"]


@pytest.mark.parametrize("subtype", ["Unlimited", "1st Edition", "Reverse Holofoil"])
def test_conditional_market_subtype_applicability_is_not_expanded(modern, subtype):
    value = package(modern)
    value["records"] = value["records"][:1]
    row, policy = value["records"][0], value["contract"]
    row["field"] = "marketPrice"
    row.update(
        as_of=None,
        reference_as_of="2026-10-09",
        publisher_built_at="2026-10-09T00:00:00+00:00",
        match_scope="conditional_market",
    )
    provider = dict(
        row["provider_identity"],
        variant=subtype,
        edition="first_edition" if subtype == "1st Edition" else "unlimited",
        finish="reverse-holo" if subtype == "Reverse Holofoil" else "normal",
    )
    row["provider_identity"] = provider
    policy["provider"] = "TCGCSV"
    policy["fields"] = {
        "marketPrice": dict(
            policy["fields"]["price-raw"],
            date_basis="publisher_build",
            valuation_date_field=None,
            reference_date_field="last-updated.txt",
            identity_scope="conditional_market",
        )
    }
    policy["mappings"][row["printing_id"]]["provider_identity"] = provider
    prices.atomic(settings.ROOT / "price-contracts.json", {"fixture": rules.digest(policy)})
    prices.activate(stage(value), None, now=NOW)
    result = compare(modern, modern["entries"][row["printing_id"]])
    if subtype == "Unlimited":
        assert result["reference"]["variant"] == "Unlimited"
        assert result["reference"]["valuation_as_of"] is None
        assert result["hunt_status"] == "conditional"
    else:
        assert result["reference"] is None and result["hunt_status"] == "unpriced"


@pytest.mark.parametrize("state", ["missing", "null", "stale", "provider_variant", "provider_number"])
def test_all_era_reference_gaps_remain_unpriced(modern, state):
    value = package(modern)
    p = modern["entries"][value["records"][0]["printing_id"]]
    row = value["records"][0]
    if state in {"null", "stale"}:
        row["as_of"] = None if state == "null" else "2026-08-01"
    elif state.startswith("provider_"):
        key = "variant" if state == "provider_variant" else "number"
        provider = dict(row["provider_identity"], **{key: "conflicting-literal"})
        value["contract"]["mappings"][p["id"]]["provider_identity"] = provider
        for observation in value["records"]:
            observation["provider_identity"] = provider
    if state != "missing":
        prices.activate(stage(value), None, now=NOW)
    result = compare(modern, p)
    assert result["reference"] is None and result["hunt_status"] == "unpriced"
    assert result["comparison"]["below_reference"] is None
    if state == "null":
        assert "Reference date missing" in result["reason"]
    elif state == "stale":
        assert "older than 30 days" in result["reason"]
    elif state.startswith("provider_"):
        assert "Rejected" in result["reason"]


@pytest.mark.parametrize("lifecycle", ["expiry", "withdrawal", "admission_removed"])
def test_all_era_reads_recheck_source_lifecycle_and_original_capture(modern, lifecycle):
    value = package(modern, permanent=False)
    value["contract"]["provider"] = "engineering-publisher"
    digest = rules.digest(value["contract"])
    prices.atomic(settings.ROOT / "price-contracts.json", {"fixture": digest})
    # V2 keeps source withdrawal independent of the containing release.
    value = dict(
        schema="dex-price-snapshot-v2",
        version=value["version"],
        release_month=value["release_month"],
        contracts={"fixture": dict(contract=value["contract"], expires_at=value["expires_at"])},
        records=[dict(row, contract_id="fixture") for row in value["records"]],
    )
    prices.activate(stage(value), None, now=NOW)
    p = modern["entries"][value["records"][0]["printing_id"]]
    before = compare(modern, p)
    assert before["reference"]["captured_at"] == NOW.isoformat()
    if lifecycle == "expiry":
        prices.purge_expired(now=NOW + timedelta(days=2))
    elif lifecycle == "withdrawal":
        prices.sources.remove_source(digest)
    else:
        prices.atomic(settings.ROOT / "price-contracts.json", {})
    after = compare(modern, p)
    assert after["reference"] is None and after["hunt_status"] == "unpriced"


def test_literal_raw_conditions_select_applicable_retained_reference_without_borrowing(modern, monkeypatch):
    p = next(iter(modern["entries"].values()))
    legacy_id = json.loads(p["provenance"])["legacy_id"]
    common = dict(
        card_id=legacy_id,
        currency="USD",
        edition="standard",
        grade="raw",
        grader="Guide",
        variant_verified=True,
        source_url="https://example.test/engineering-guide",
    )
    records = [
        dict(common, value="2", as_of="2026-10-08", condition="NM"),
        dict(common, value="9", as_of="2026-10-09", condition="LP"),
    ]
    monkeypatch.setattr(lot_calculator, "legacy_records", lambda: records)
    near_mint = compare(modern, p)
    assert near_mint["reference"]["amount"] == "2"
    assert near_mint["reference"]["condition"] == "NM"
    lightly_played = compare(modern, p, condition="Lightly Played")
    assert lightly_played["reference"]["amount"] == "9"
    damaged = compare(modern, p, condition="Damaged")
    assert damaged["reference"] is None
    assert "condition conflicts" in damaged["reason"]
    unknown = compare(modern, p, condition="Ungraded")
    assert unknown["hunt_status"] == "conditional" and unknown["reference"]["amount"] == "9"


def test_title_condition_claims_narrow_references_with_unknown_raw_condition_in_one_batch(
    modern, monkeypatch
):
    p = next(iter(modern["entries"].values()))
    legacy_id = json.loads(p["provenance"])["legacy_id"]
    common = dict(
        card_id=legacy_id,
        currency="USD",
        edition="standard",
        grade="raw",
        grader="Guide",
        variant_verified=True,
        source_url="https://example.test/engineering-guide",
    )
    records = [
        dict(common, value="2", as_of="2026-10-08", condition="NM"),
        dict(common, value="9", as_of="2026-10-09", condition="LP"),
    ]
    monkeypatch.setattr(lot_calculator, "legacy_records", lambda: records)
    title = listing(p)["title"]
    raw_rows = [
        listing(p, title=title + " " + claim, condition="Used", itemId=claim) for claim in ("NM", "LP", "DMG")
    ]
    rows = {row["item_id"]: row for row in hunter_catalog.compare(modern["actor"], raw_rows, now=NOW)}
    assert rows["NM"]["reference"]["condition"] == "NM" and rows["NM"]["reference"]["amount"] == "2"
    assert rows["LP"]["reference"]["condition"] == "LP" and rows["LP"]["reference"]["amount"] == "9"
    assert rows["NM"]["raw_condition_basis"] == "Used" and rows["NM"]["hunt_status"] == "conditional"
    assert rows["LP"]["hunt_status"] == "conditional"
    assert rows["DMG"]["reference"] is None and "condition conflicts" in rows["DMG"]["reason"]
    # A sole LP observation must not be reused for a title claiming NM.
    records[:] = records[1:]
    unmatched = compare(modern, p, title=title + " NM", condition="Used")
    assert unmatched["reference"] is None and "condition conflicts" in unmatched["reason"]


def graded_competition(setup):
    first = package(setup)
    second = copy.deepcopy(first)
    for value, grader, amount, as_of in (
        (first, "PSA", "7", "2026-10-08"),
        (second, "CGC", "11", "2026-10-09"),
    ):
        value["contract"]["review_id"] = "engineering-" + grader
        value["records"] = [value["records"][1]]
        row = value["records"][0]
        row.update(
            observation_id=str(uuid4()), grader=grader, value=amount, original_money=amount, as_of=as_of
        )
        value["contract"]["fields"][row["field"]]["grader"] = grader
    return dict(
        schema="dex-price-snapshot-v2",
        version=str(uuid4()),
        release_month="2026-10",
        contracts={
            value["contract"]["review_id"]: dict(contract=value["contract"], expires_at=value["expires_at"])
            for value in (first, second)
        },
        records=[
            dict(row, contract_id=value["contract"]["review_id"])
            for value in (first, second)
            for row in value["records"]
        ],
    )


def test_literal_grader_is_selected_before_newest_source_without_equating_grades(modern):
    value = graded_competition(modern)
    prices.activate(stage(value), None, now=NOW)
    p = modern["entries"][value["records"][0]["printing_id"]]
    title = listing(p)["title"]
    raw_rows = [
        listing(p, title=title + " " + claim, itemId=claim) for claim in ("PSA 8", "CGC 8", "BGS 8", "PSA 9")
    ]
    rows = {row["item_id"]: row for row in hunter_catalog.compare(modern["actor"], raw_rows, now=NOW)}
    assert rows["PSA 8"]["reference"]["grader"] == "PSA"
    assert rows["PSA 8"]["reference"]["amount"] == "7"
    assert rows["CGC 8"]["reference"]["grader"] == "CGC"
    assert rows["CGC 8"]["reference"]["amount"] == "11"
    assert rows["BGS 8"]["reference"] is None and "grader conflicts" in rows["BGS 8"]["reason"]
    assert rows["PSA 9"]["reference"] is None
    # Ordinary calculator selection still exposes the competing literal population.
    cell = lot_guides.cells(p, lot_calculator.retained_records(), NOW.date())["8"]
    assert cell["grader"] == "CGC" and cell["conflicts"][0]["grader"] == "PSA"


def test_competing_build_and_valuation_dates_remain_separate_in_hunter(modern):
    value = build_reference_package(modern)
    other = copy.deepcopy(value["records"][0])
    other.update(
        contract_id="engineering-valuation",
        observation_id=str(uuid4()),
        as_of="2026-10-08",
        captured_at=NOW.isoformat(),
    )
    other.pop("reference_as_of")
    other.pop("publisher_built_at")
    policy = copy.deepcopy(value["contracts"]["fixture-raw"]["contract"])
    policy.update(review_id="engineering-valuation", provider="dex-engineering-fixture")
    field = policy["fields"]["price-raw"]
    field.update(date_basis="valuation", valuation_date_field="valued")
    field.pop("reference_date_field")
    value["contracts"]["engineering-valuation"] = dict(contract=policy, expires_at=None)
    value["records"].append(other)
    prices.activate(stage(value), None, now=NOW)
    p = modern["entries"][other["printing_id"]]
    ref = compare(modern, p)["reference"]
    assert ref["date_basis"] == "publisher_build" and ref["valuation_as_of"] is None
    assert ref["publisher_built_at"] == "2026-10-09T00:00:00+00:00"
    conflict = ref["conflicts"][0]
    assert conflict["date_basis"] == "valuation" and conflict["valuation_as_of"] == "2026-10-08"
    assert conflict["publisher_built_at"] is None and conflict["captured_at"] == NOW.isoformat()
