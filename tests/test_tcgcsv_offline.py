"""Synthetic schema qualification only; no source records, rights or acquisition."""

import copy
import json
from datetime import datetime, timezone

import pytest

from pokemon_hunter.beta import price_snapshot_contract as rules
from pokemon_hunter.beta import tcgcsv_offline as adapter

NOW = datetime(2026, 10, 17, 12, tzinfo=timezone.utc)
BUILT = "2026-10-16T20:00:00+00:00"


@pytest.fixture
def case(tmp_path):
    entries = {}
    policy = dict(
        schema="dex-price-contract-v1",
        provider="TCGCSV",
        review_id="synthetic-offline-review",
        policy_url="https://example.test/synthetic-rights",
        policy_version="synthetic-only",
        scope="Synthetic offline qualification only",
        deletion_policy="Synthetic removal boundary",
        acquisition_policy="No acquisition",
        copy_policy="managed_store_and_permitted_history_no_backups_or_exports",
        rights=dict(
            display=True,
            arithmetic=True,
            private_storage=True,
            immutable_save=False,
            noncontent_revocations=True,
        ),
        fields=dict(
            marketPrice=dict(
                grade="raw",
                grader="Synthetic condition-mixed market",
                label="Synthetic market reference",
                currency_evidence="Synthetic USD evidence only",
                valuation_date_field=None,
                reference_date_field="last-updated.txt",
                date_basis="publisher_build",
                identity_scope="conditional_market",
                unit="USD_decimal",
                zero_is_value=False,
            )
        ),
        mappings={},
    )
    products, prices, bindings = [], [], []
    for n, (kind, name, number, species) in enumerate(
        (
            ("Trainer", "Synthetic Professor", "171/182", None),
            ("Energy", "Synthetic Energy", "004/182", None),
            ("Pokémon", "Synthetic Promo", "SVP001", 25),
        ),
        1,
    ):
        pid = "printing-" + str(n)
        p = dict(
            id=pid,
            set_id="synthetic-set",
            set_name="Synthetic Set",
            name=name,
            collector_number=number,
            language="en",
            edition=None,
            finish="normal",
            variant=None,
            catalog_version="synthetic-catalog",
            attributes=dict(supertype=kind, pokemon_dex=species),
        )
        entries[pid] = p
        provider = dict(
            product_id=str(n),
            set=p["set_name"],
            number=number,
            language="en",
            edition="unspecified",
            finish="normal",
            variant="Normal",
            mapping_review="Explicit synthetic mapping, not provider permission",
        )
        policy["mappings"][pid] = dict(
            identity={k: p.get(k) for k in rules.IDENTITY},
            provider_identity=provider,
            source_url="https://example.test/synthetic/" + str(n),
            source_version="tcgcsv-build-" + BUILT,
        )
        products.append(
            dict(
                productId=n,
                categoryId=3,
                groupId=700,
                name=name,
                url="https://example.test/synthetic/" + str(n),
                extendedData=[dict(name="Number", displayName="Number", value=number)],
            )
        )
        prices.append(dict(productId=n, subTypeName="Normal", marketPrice=2.5))
        bindings.append(
            dict(
                printing_id=pid,
                group_id=700,
                product_id=n,
                sub_type_name="Normal",
                product_name=name,
                collector_number=number,
            )
        )
    manifest = dict(
        schema=adapter.SCHEMA,
        publisher_built_at=BUILT,
        captured_at=NOW.isoformat(),
        expires_at="2026-10-18T00:00:00+00:00",
        contract=policy,
        shards=[dict(group_id=700, products="products.json", prices="prices.json")],
        bindings=bindings,
    )
    data = dict(entries=entries, products=products, prices=prices, manifest=manifest, directory=tmp_path)
    save(data)
    return data


def save(case):
    (case["directory"] / "products.json").write_text(
        json.dumps(
            dict(
                totalItems=len(case["products"]),
                success=True,
                errors=[],
                results=case["products"],
            )
        )
    )
    (case["directory"] / "prices.json").write_text(
        json.dumps(
            dict(
                success=True,
                errors=[],
                results=case["prices"],
            )
        )
    )


def prepare(case, **kwargs):
    return adapter.prepare(
        case["entries"], case["manifest"], input_directory=case["directory"], now=NOW, **kwargs
    )


def decision(report, pid="printing-1"):
    return next(d["decision"] for d in report["printings"] if d["printing_id"] == pid)


def test_explicit_trainer_energy_promo_mapping_and_projection_are_nonmutating(case):
    before = copy.deepcopy(case)
    package, report = prepare(case, baseline_eligible={"printing-1"})
    assert package["schema"] == "dex-price-snapshot-v2"
    assert len(package["records"]) == 3
    assert package["contracts"]["synthetic-offline-review"]["contract"] == case["manifest"]["contract"]
    assert all(r["as_of"] is None and r["match_scope"] == "conditional_market" for r in package["records"])
    assert report["eligible_printings"] == report["projected_eligible_printings"] == 3
    assert report["newly_eligible_printings"] == 2
    assert report["projected_unpriced_printings"] == 0
    assert report["decisions"] == {"eligible": 3}
    assert report["input"]["files"] == 2
    assert "2.5" not in json.dumps(report) and "example.test" not in json.dumps(report)
    assert case == before


@pytest.mark.parametrize(
    "change,expected",
    [
        ("no_binding", "unmapped_printing"),
        ("double_binding", "ambiguous_printing_binding"),
        ("shared_source", "ambiguous_source_binding"),
        ("duplicate_product", "ambiguous_product"),
        ("duplicate_price", "ambiguous_price"),
        ("missing_product", "unmapped_product"),
        ("missing_price", "unmapped_price"),
        ("source_number", "collector_number_conflict"),
        ("double_number", "collector_number_conflict"),
        ("source_name", "product_identity_conflict"),
        ("source_url", "product_identity_conflict"),
        ("catalog_version", "catalog_identity_conflict"),
        ("provider_product", "reviewed_source_identity_conflict"),
        ("no_mapping", "missing_reviewed_mapping"),
        ("malformed_provider", "invalid_reviewed_mapping"),
    ],
)
def test_explicit_identity_conflicts_remain_visible(case, change, expected):
    manifest = case["manifest"]
    if change == "no_binding":
        manifest["bindings"].pop(0)
    elif change == "double_binding":
        manifest["bindings"].append(copy.deepcopy(manifest["bindings"][0]))
    elif change == "shared_source":
        manifest["bindings"][1] = dict(manifest["bindings"][0], printing_id="printing-2")
    elif change == "duplicate_product":
        case["products"].append(copy.deepcopy(case["products"][0]))
    elif change == "duplicate_price":
        case["prices"].append(copy.deepcopy(case["prices"][0]))
    elif change == "missing_product":
        case["products"].pop(0)
    elif change == "missing_price":
        case["prices"].pop(0)
    elif change == "source_number":
        case["products"][0]["extendedData"][0]["value"] = "171/999"
    elif change == "double_number":
        case["products"][0]["extendedData"] *= 2
    elif change == "source_name":
        case["products"][0]["name"] += " ex"
    elif change == "source_url":
        case["products"][0]["url"] += "-other"
    elif change == "catalog_version":
        case["entries"]["printing-1"]["catalog_version"] += "-changed"
    elif change == "provider_product":
        manifest["contract"]["mappings"]["printing-1"]["provider_identity"]["product_id"] = "99"
    elif change == "no_mapping":
        manifest["contract"]["mappings"].pop("printing-1")
    else:
        manifest["contract"]["mappings"]["printing-1"]["provider_identity"]["variant"] = []
    save(case)
    package, report = prepare(case)
    assert decision(report) == expected
    assert "printing-1" not in {r["printing_id"] for r in package["records"]}


@pytest.mark.parametrize(
    "change,expected",
    [
        ("language", "language_conflict"),
        ("product_language", "language_conflict"),
        ("price_language", "language_conflict"),
        ("currency", "currency_conflict"),
        ("condition", "unsupported_price_semantics"),
        ("valuation_date", "unsupported_price_semantics"),
        ("price_build", "conflicting_price_dates"),
        ("finish", "rejected_unresolved_or_conflicting_variant"),
        ("known_edition", "rejected_unresolved_or_conflicting_variant"),
        ("special_variant", "rejected_unresolved_or_conflicting_variant"),
    ],
)
def test_variant_language_condition_currency_and_date_conflicts(case, change, expected):
    p = case["entries"]["printing-1"]
    if change == "language":
        p["language"] = "ja"
    elif change == "product_language":
        case["products"][0]["language"] = "ja"
    elif change == "price_language":
        case["prices"][0]["language"] = "ja"
    elif change == "currency":
        case["prices"][0]["currency"] = "EUR"
    elif change == "condition":
        case["prices"][0]["condition"] = "Near Mint"
    elif change == "valuation_date":
        case["prices"][0]["valuation_date"] = "2026-10-17"
    elif change == "price_build":
        case["prices"][0]["publisher_built_at"] = "2026-10-17T00:00:00+00:00"
    elif change == "finish":
        p["finish"] = "holo"
    elif change == "known_edition":
        p["edition"] = "1st-edition"
    else:
        p["variant"] = '{"type":"normal","stamp":["special"]}'
    # Model a reviewed identity that still cannot override known physical fit.
    case["manifest"]["contract"]["mappings"][p["id"]]["identity"] = {k: p.get(k) for k in rules.IDENTITY}
    save(case)
    _, report = prepare(case)
    assert decision(report) == expected


def test_documented_reverse_holofoil_is_conditional_and_unknown_subtypes_remain_visible(case):
    p = case["entries"]["printing-1"]
    p["finish"] = "reverse-holo"
    mapping = case["manifest"]["contract"]["mappings"][p["id"]]
    mapping["identity"] = {k: p.get(k) for k in rules.IDENTITY}
    mapping["provider_identity"].update(finish="reverse-holo", variant="Reverse Holofoil")
    case["prices"][0]["subTypeName"] = "Reverse Holofoil"
    case["manifest"]["bindings"][0]["sub_type_name"] = "Reverse Holofoil"
    save(case)
    package, report = prepare(case)
    assert decision(report) == "eligible"
    assert (
        next(r for r in package["records"] if r["printing_id"] == p["id"])["match_scope"]
        == "conditional_market"
    )
    mapping["provider_identity"]["variant"] = "Special Stamped Holofoil"
    case["prices"][0]["subTypeName"] = "Special Stamped Holofoil"
    case["manifest"]["bindings"][0]["sub_type_name"] = "Special Stamped Holofoil"
    save(case)
    _, report = prepare(case)
    assert decision(report) == "rejected_unresolved_or_conflicting_variant"


@pytest.mark.parametrize(
    "raw", ["null", "0", "-1", '"2.50"', "1e999999999", "1e-999999999", "1.1234567", "1000000000001"]
)
def test_missing_or_invalid_values_and_scientific_expansion_are_bounded(case, raw):
    path = case["directory"] / "prices.json"
    text = path.read_text().replace('"marketPrice": 2.5', '"marketPrice": ' + raw, 1)
    path.write_text(text)
    _, report = prepare(case)
    assert decision(report) in {"missing_market_price", "invalid_market_price"}


@pytest.mark.parametrize(
    "key,value",
    [
        ("publisher_built_at", None),
        ("publisher_built_at", "2026-10-16T20:00:00"),
        ("publisher_built_at", "2026-10-18T00:00:00+00:00"),
        ("captured_at", "2026-10-18T00:00:00+00:00"),
        ("captured_at", "2026-10-17T12:00:00"),
        ("expires_at", None),
        ("expires_at", "2026-10-16T00:00:00+00:00"),
    ],
)
def test_missing_naive_conflicting_or_expired_dates_stop_all_preparation(case, key, value):
    case["manifest"][key] = value
    with pytest.raises(ValueError):
        prepare(case)


def test_timezone_build_uses_utc_date_and_product_modified_time_never_values_price(case):
    case["manifest"]["publisher_built_at"] = "2026-10-16T23:30:00-02:00"
    expected = "2026-10-17T01:30:00+00:00"
    for mapping in case["manifest"]["contract"]["mappings"].values():
        mapping["source_version"] = "tcgcsv-build-" + expected
    case["products"][0]["modifiedOn"] = "2099-01-01T23:23:00"
    save(case)
    package, report = prepare(case)
    assert all(r["reference_as_of"] == "2026-10-17" and r["as_of"] is None for r in package["records"])
    assert report["publisher_built_at"] == expected


def test_source_build_must_match_exact_reviewed_version(case):
    case["manifest"]["publisher_built_at"] = "2026-10-15T00:00:00+00:00"
    package, report = prepare(case)
    assert package is None
    assert report["decisions"] == {"reviewed_source_identity_conflict": 3}


def test_no_bindings_returns_metadata_only_and_orphan_binding_has_separate_denominator(case):
    case["manifest"]["bindings"] = [dict(case["manifest"]["bindings"][0], printing_id="unpublished")]
    package, report = prepare(case)
    assert package is None
    assert report["bindings_absent_from_catalog"] == 1
    assert report["decisions"] == {"unmapped_printing": 3}
    assert sum(report["decisions"].values()) == report["catalog_printings"]
    assert report["unmapped_source_rows"] == 2


def test_adapter_cannot_create_missing_rights_or_accept_unknown_baseline(case):
    case["manifest"]["contract"]["rights"]["arithmetic"] = False
    with pytest.raises(ValueError, match="rights unavailable"):
        prepare(case)
    case["manifest"]["contract"]["rights"]["arithmetic"] = True
    with pytest.raises(ValueError, match="Baseline eligible"):
        prepare(case, baseline_eligible={"absent"})


@pytest.mark.parametrize("raw", [b'{"schema":', b'{"schema":"a","schema":"b"}', b'{"a":NaN}', b"\xff"])
def test_manifest_malformed_truncated_duplicate_key_or_nonfinite_json_is_rejected(tmp_path, raw):
    path = tmp_path / "manifest.json"
    path.write_bytes(raw)
    with pytest.raises(ValueError, match="Malformed"):
        adapter.read_manifest(path)


@pytest.mark.parametrize(
    "mutation", ["failed", "errors", "total", "cross_group", "category", "bool_id", "truncated"]
)
def test_bad_later_shard_or_envelope_is_fatal_before_output(case, mutation):
    path = case["directory"] / "products.json"
    data = json.loads(path.read_text())
    if mutation == "failed":
        data["success"] = False
    elif mutation == "errors":
        data["errors"] = ["Synthetic failure"]
    elif mutation == "total":
        data["totalItems"] += 1
    elif mutation == "cross_group":
        data["results"][0]["groupId"] += 1
    elif mutation == "category":
        data["results"][0]["categoryId"] = 1
    elif mutation == "bool_id":
        data["results"][0]["productId"] = True
    else:
        path.write_text('{"success":')
    if mutation != "truncated":
        path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        prepare(case)


@pytest.mark.parametrize(
    "limit",
    [
        adapter.Limits(file_bytes=20),
        adapter.Limits(total_bytes=30),
        adapter.Limits(rows_per_file=2),
        adapter.Limits(product_rows=2),
        adapter.Limits(price_rows=2),
        adapter.Limits(bindings=2),
        adapter.Limits(output_bytes=50),
    ],
)
def test_every_input_and_output_ceiling_stops_preparation(case, limit):
    with pytest.raises(ValueError):
        prepare(case, limits=limit)


def test_duration_ceiling_is_checked_between_shards_and_rows(case, monkeypatch):
    ticks = iter((0, 31))
    monkeypatch.setattr(adapter.time, "monotonic", lambda: next(ticks))
    with pytest.raises(ValueError, match="duration ceiling"):
        prepare(case)


@pytest.mark.parametrize("kind", ["absolute", "parent", "symlink", "same_file"])
def test_input_paths_cannot_escape_follow_links_or_reuse_files(case, kind):
    shard = case["manifest"]["shards"][0]
    if kind == "absolute":
        shard["products"] = str(case["directory"] / "products.json")
    elif kind == "parent":
        shard["products"] = "../products.json"
    elif kind == "symlink":
        (case["directory"] / "link.json").symlink_to(case["directory"] / "products.json")
        shard["products"] = "link.json"
    else:
        shard["prices"] = shard["products"]
    with pytest.raises(ValueError):
        prepare(case)


def add_empty_group(case, group):
    product_path, price_path = f"products-{group}.json", f"prices-{group}.json"
    (case["directory"] / product_path).write_text(
        json.dumps(dict(totalItems=0, success=True, errors=[], results=[]))
    )
    (case["directory"] / price_path).write_text(json.dumps(dict(success=True, errors=[], results=[])))
    case["manifest"]["shards"].append(dict(group_id=group, products=product_path, prices=price_path))


def test_68_group_boundary_and_duplicate_group_are_finite(case):
    for group in range(701, 768):
        add_empty_group(case, group)
    _, report = prepare(case)
    assert report["input"]["groups"] == 68 and report["input"]["files"] == 136
    add_empty_group(case, 768)
    with pytest.raises(ValueError, match="68"):
        prepare(case)
    case["manifest"]["shards"] = case["manifest"]["shards"][:2]
    case["manifest"]["shards"][1]["group_id"] = 700
    with pytest.raises(ValueError, match="Distinct"):
        prepare(case)


def test_global_product_identity_duplicates_across_shards_cannot_choose_a_group(case):
    add_empty_group(case, 701)
    product = dict(case["products"][0], groupId=701)
    (case["directory"] / "products-701.json").write_text(
        json.dumps(
            dict(
                totalItems=1,
                success=True,
                errors=[],
                results=[product],
            )
        )
    )
    (case["directory"] / "prices-701.json").write_text(
        json.dumps(
            dict(
                success=True,
                errors=[],
                results=[case["prices"][0]],
            )
        )
    )
    _, report = prepare(case)
    assert decision(report) == "cross_group_identity_conflict"
    assert report["cross_group_product_ids"] == report["cross_group_price_keys"] == 1


def test_limits_cannot_be_increased_above_the_qualified_bounds(case):
    with pytest.raises(ValueError, match="qualified ceilings"):
        prepare(case, limits=adapter.Limits(groups=69))
    with pytest.raises(ValueError, match="Positive finite"):
        prepare(case, limits=adapter.Limits(total_bytes=0))


@pytest.mark.parametrize("edition", ["unlimited", "1st-edition", "unsupported-special"])
def test_reverse_subtype_cannot_override_known_edition(case, edition):
    printing = case["entries"]["printing-1"]
    printing.update(edition=edition, finish="reverse-holo", variant="reverse-holo")
    mapping = case["manifest"]["contract"]["mappings"][printing["id"]]
    mapping["identity"] = {key: printing.get(key) for key in rules.IDENTITY}
    mapping["provider_identity"].update(finish="reverse-holo", variant="Reverse Holofoil")
    case["prices"][0]["subTypeName"] = "Reverse Holofoil"
    case["manifest"]["bindings"][0]["sub_type_name"] = "Reverse Holofoil"
    save(case)
    package, report = prepare(case)
    assert decision(report) == "rejected_unresolved_or_conflicting_variant"
    assert printing["id"] not in {row["printing_id"] for row in package["records"]}


@pytest.mark.parametrize("kind", ["products", "prices"])
def test_actual_later_shard_malformed_envelope_aborts_without_partial_package(case, kind):
    add_empty_group(case, 701)
    path = case["directory"] / f"{kind}-701.json"
    path.write_text('{"success":true,"errors":[],"results":[')
    before = {item.name: item.read_bytes() for item in case["directory"].iterdir()}
    with pytest.raises(ValueError, match="Malformed"):
        prepare(case)
    assert {item.name: item.read_bytes() for item in case["directory"].iterdir()} == before


@pytest.mark.parametrize("kind", ["products", "prices"])
def test_aggregate_rows_are_counted_across_distinct_later_shards(case, kind):
    add_empty_group(case, 701)
    row = dict(case[kind][0])
    if kind == "products":
        row.update(productId=900, groupId=701)
        value = dict(success=True, errors=[], results=[row], totalItems=1)
    else:
        row["productId"] = 900
        value = dict(success=True, errors=[], results=[row])
    (case["directory"] / f"{kind}-701.json").write_text(json.dumps(value))
    limit = adapter.Limits(**{"product_rows" if kind == "products" else "price_rows": 3})
    with pytest.raises(ValueError, match="total row ceiling"):
        prepare(case, limits=limit)


def test_aggregate_bytes_include_every_later_shard_and_exact_boundary_passes(case):
    add_empty_group(case, 701)
    total = sum(path.stat().st_size for path in case["directory"].iterdir())
    _, report = prepare(case, limits=adapter.Limits(total_bytes=total))
    assert report["input"]["input_bytes"] == total
    with pytest.raises(ValueError, match="byte ceiling"):
        prepare(case, limits=adapter.Limits(total_bytes=total - 1))
