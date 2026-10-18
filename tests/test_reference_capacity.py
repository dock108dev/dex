"""Finite lookup, selection and composed release capacity; fabricated references only."""

import copy
from uuid import NAMESPACE_URL, uuid5

import pytest
from price_snapshot_helpers import b2 as b2
from price_snapshot_helpers import env as env
from price_snapshot_helpers import setup as setup
from price_snapshot_helpers import shop as shop
from price_snapshot_helpers import snapshot as snapshot
from test_tcgcsv_offline import NOW, prepare
from test_tcgcsv_offline import case as case

from pokemon_hunter.beta import price_snapshot_contract as rules


def test_large_catalog_small_explicit_selection_keeps_full_denominator(case):
    for number in range(3, 10001):
        key = f"lookup-{number}"
        case["entries"][key] = dict(id=key)
    package, report = prepare(case, target_ids=["printing-1", "printing-2", "printing-3"])
    assert report["catalog_printings"] == 10001
    assert report["selected_target_printings"] == 3
    assert report["records"] == 3
    assert report["decisions"] == {"eligible": 3, "unmapped_printing": 9998}
    assert len(package["records"]) == 3


def test_catalog_and_selection_boundary_and_oversized(case):
    for number in range(3, rules.MAX_CATALOG_ROWS):
        key = f"lookup-{number}"
        case["entries"][key] = dict(id=key)
    _, report = prepare(case)
    assert report["catalog_printings"] == rules.MAX_CATALOG_ROWS
    case["entries"]["oversized"] = dict(id="oversized")
    with pytest.raises(ValueError, match="lookup ceiling"):
        prepare(case)
    del case["entries"]["oversized"]
    selected = list(case["entries"])[: rules.MAX_ROWS]
    # Include the actual bindings in the otherwise-unmapped selected boundary.
    for key in ("printing-1", "printing-2", "printing-3"):
        assert key in selected
    prepare(case, target_ids=selected)
    with pytest.raises(ValueError, match="explicit import targets"):
        prepare(case, target_ids=list(case["entries"])[: rules.MAX_ROWS + 1])
    with pytest.raises(ValueError, match="outside the selected"):
        prepare(case, target_ids=[])


def test_lookup_byte_limit_is_independent(case, monkeypatch):
    size = rules.serialized_bytes(case["entries"])
    monkeypatch.setattr(rules, "MAX_CATALOG_BYTES", size)
    prepare(case)
    monkeypatch.setattr(rules, "MAX_CATALOG_BYTES", size - 1)
    with pytest.raises(ValueError, match="lookup byte"):
        prepare(case)


def release(case, count, shard_rows=5000):
    """Build deterministic explicit synthetic rows with independent source shards."""
    original, _ = prepare(case)
    seed = original["records"][0]
    policy = next(iter(original["contracts"].values()))["contract"]
    contracts, rows, entries = {}, [], {}
    for number in range(count):
        pid, key = f"synthetic-capacity-{number:05}", f"synthetic-shard-{number // shard_rows}"
        p = dict(case["entries"]["printing-1"], id=pid, collector_number=str(number))
        entries[pid] = p
        row = copy.deepcopy(seed)
        row.update(observation_id=str(uuid5(NAMESPACE_URL, pid)), printing_id=pid, contract_id=key)
        row["identity"] = {k: p.get(k) for k in rules.IDENTITY}
        row["provider_identity"].update(product_id=str(number), number=str(number))
        if key not in contracts:
            contracts[key] = dict(
                contract=copy.deepcopy(policy),
                expires_at=original["contracts"][policy["review_id"]]["expires_at"],
            )
            contracts[key]["contract"].update(review_id=key, mappings={})
        mapping = {
            k: copy.deepcopy(row[k])
            for k in ("identity", "provider_identity", "source_url", "source_version")
        }
        contracts[key]["contract"]["mappings"][pid] = mapping
        rows.append(row)
    return dict(original, contracts=contracts, records=rows), entries


def test_composed_release_above_old_limit_is_valid_and_source_bounded(case):
    package, entries = release(case, 10001)
    rules.validate(package, entries, now=NOW)
    assert len(package["contracts"]) == 3
    assert all(
        len(p["records"]) <= rules.MAX_ROWS and rules.serialized_bytes(p) <= rules.MAX_BYTES
        for p in rules.source_packages(package).values()
    )


def test_composed_row_mapping_and_byte_limits_fail_independently(case, monkeypatch):
    package, entries = release(case, 12, shard_rows=5)
    monkeypatch.setattr(rules, "MAX_RELEASE_ROWS", 12)
    monkeypatch.setattr(rules, "MAX_RELEASE_MAPPINGS", 12)
    monkeypatch.setattr(rules, "MAX_RELEASE_BYTES", rules.serialized_bytes(package))
    rules.validate(package, entries, now=NOW)
    with monkeypatch.context() as limit:
        limit.setattr(rules, "MAX_RELEASE_ROWS", 11)
        with pytest.raises(ValueError, match="record set"):
            rules.validate(package, entries, now=NOW)
    with monkeypatch.context() as limit:
        limit.setattr(rules, "MAX_RELEASE_MAPPINGS", 11)
        with pytest.raises(ValueError, match="mapping ceiling"):
            rules.validate(package, entries, now=NOW)
    monkeypatch.setattr(rules, "MAX_RELEASE_BYTES", rules.serialized_bytes(package) - 1)
    with pytest.raises(ValueError, match="byte ceiling"):
        rules.validate(package, entries, now=NOW)


def test_source_limits_and_duplicate_observation_refuse_partial_composition(case, monkeypatch):
    package, entries = release(case, 12, shard_rows=5)
    package["records"][1]["observation_id"] = package["records"][0]["observation_id"]
    with pytest.raises(ValueError, match="Duplicate observation"):
        rules.validate(package, entries, now=NOW)
    package, entries = release(case, 12, shard_rows=12)
    monkeypatch.setattr(rules, "MAX_ROWS", 11)
    with pytest.raises(ValueError):
        rules.validate(package, entries, now=NOW)


# Existing lifecycle fixtures use disposable accounts and a separate current root.


def test_large_composition_atomic_activation_admission_and_failed_shard_preserve_old(
    case, setup, monkeypatch
):
    from django.conf import settings
    from price_snapshot_helpers import multi_package, stage

    from pokemon_hunter.beta import price_snapshots as prices

    old = multi_package(setup, restricted=False)
    prices.activate(stage(old), None, now=NOW)
    original_rows = prices.current(now=NOW)[0]
    package, expanded = release(case, 10001)
    setup["entries"].update(expanded)
    for key, value in old["contracts"].items():
        package["contracts"][key] = value
    package["records"].extend(copy.deepcopy(old["records"]))
    staged = stage(package)
    with pytest.raises(ValueError, match="admission disabled"):
        prices.preview(staged, now=NOW)
    prices.atomic(
        settings.ROOT / "price-contracts.json",
        {
            key: rules.digest(value["contract"])
            for key, value in package["contracts"].items()
            if value["contract"]["provider"] == "TCGCSV"
        },
    )
    with pytest.raises(ValueError, match="changed"):
        prices.activate(staged, str(uuid5(NAMESPACE_URL, "stale")), now=NOW)
    original_atomic = prices.atomic
    writes = []

    def interrupted(path, value):
        if path.parent.name == package["version"]:
            writes.append(path)
            if len(writes) == 2:
                raise OSError("Fabricated interrupted source install")
        return original_atomic(path, value)

    with monkeypatch.context() as failure:
        failure.setattr(prices, "atomic", interrupted)
        with pytest.raises(OSError):
            prices.activate(staged, old["version"], now=NOW)
    assert prices.state()["current"] == old["version"]
    assert prices.current(now=NOW)[0] == original_rows
    prices.activate(staged, old["version"], now=NOW)
    loaded, status = prices.current(now=NOW)
    assert status == "active_snapshot" and len(loaded) == len(package["records"])
    assert {r["observation_id"] for r in original_rows} <= {r["observation_id"] for r in loaded}


@pytest.mark.parametrize("raw", ['{"contracts":{},"contracts":{}}', '{"value":NaN}'])
def test_duplicate_json_mapping_keys_and_nonfinite_numbers_refused(tmp_path, raw):
    from pokemon_hunter.beta import price_snapshots

    path = tmp_path / "malformed.json"
    path.write_text(raw)
    with pytest.raises(ValueError):
        price_snapshots.read(path)
