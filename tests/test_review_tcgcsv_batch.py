"""Exact offline mapping regressions; synthetic metadata only, no customer state."""

import copy
import importlib.util
from datetime import datetime, timezone
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "review_tcgcsv_batch", Path(__file__).parents[1] / "scripts/review_tcgcsv_batch.py"
)
review = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(review)


@pytest.fixture
def case():
    target = dict(
        id="printing",
        set_id="set",
        set_name="Synthetic Set",
        name="Nidoran♀",
        collector_number="001",
        language="en",
        edition=None,
        finish="normal",
        variant='{"type":"normal"}',
        catalog_version="v1",
        attributes={"supertype": "Pokémon"},
    )
    product = dict(
        productId=10,
        categoryId=3,
        groupId=11,
        name="Nidoran F (1)",
        url="https://www.tcgplayer.com/product/10/pokemon-synthetic-set-nidoran-f",
        extendedData=[dict(name="Number", value="1/120")],
    )
    price = dict(productId=10, subTypeName="Normal", marketPrice=None)
    evidence = dict(
        category_id=3,
        literal_name="Synthetic Set",
        language="en",
        language_evidence=[{"source": "pinned English canonical set/crosswalk"}],
        denominators={"": ["120"]},
    )
    return target, product, price, evidence


def choose(case, *, products=None, prices=None, targets=None):
    target, product, price, evidence = case
    entries = targets or {target["id"]: target}
    return review.choose(
        entries,
        {key: 11 for key in entries},
        {"11": evidence},
        products or {(11, 10): [product]},
        prices or {(11, (10, "Normal")): [price]},
        {"product_ids": set(), "price_keys": set()},
    )


def test_padding_alias_and_reviewed_denominator_produce_exact_binding(case):
    decisions, bindings = choose(case)
    assert len(bindings) == 1
    assert bindings[0]["collector_number"] == "1/120"
    assert decisions[0]["candidates"][0]["source_language_unstated"]
    assert "Nidoran_gender_alias" in decisions[0]["candidates"][0]["name_relation"]
    assert decisions[0]["candidates"][0]["number_relation"] == "reviewed_English_set_denominator"
    assert "marketPrice" not in str(decisions)


@pytest.mark.parametrize(
    ("local", "source", "evidence", "expected"),
    [
        ("001", "1", {}, "padding_normalization"),
        ("H01", "H1", {}, "padding_normalization"),
        ("H01", "1", {}, None),
        ("28a", "28", {}, None),
        ("28a", "028a", {}, "padding_normalization"),
        ("5/120", "5/121", {"": ["120"]}, None),
        ("5", "5/120", {}, None),
        ("5", "5/0120", {"": ["120"]}, "reviewed_English_set_denominator"),
        ("5/120", "5", {"": ["120"]}, "reviewed_English_set_denominator"),
        ("SL1", "SL1/95", {"": ["95"]}, None),
        ("RC14", "RC14/RC25", {"rc": ["RC25"]}, "reviewed_English_set_denominator"),
    ],
)
def test_number_relations_preserve_full_identity(local, source, evidence, expected):
    assert review.collector_relation(local, source, {"denominators": evidence}) == expected


@pytest.mark.parametrize(
    ("source", "number", "matched"),
    [
        ("Unown (A)", "1/120", True),
        ("Unown", "1/120", False),
        ("Unown (A) (001)", "1/120", True),
        ("Unown (A) (2)", "1/120", False),
        ("Unown (A) (1/120)", "1/120", True),
        ("Unown (A) (Cosmos Holo)", "1/120", False),
    ],
)
def test_only_agreeing_terminal_collector_suffix_can_be_removed(source, number, matched):
    target = {"name": "Unown (A)", "attributes": {}}
    assert bool(review.product_name_relation(target, source, number)) is matched


@pytest.mark.parametrize(
    ("source", "number", "matched"),
    [
        ("Tangela - 178/165", "178/165", True),
        ("Tangela - 0178/0165", "178/165", True),
        ("Tangela - 178/165", "0178/0165", True),
        ("Tangela - 178", "178", True),
        ("Tangela - 178", "178/165", False),
        ("Tangela - 178/166", "178/165", False),
        ("Tangela - H178/165", "178/165", False),
        ("Tangela - 178a/165", "178/165", False),
        ("Tangela - 178/165 Special", "178/165", False),
        ("Tangela - Reverse Holo", "178/165", False),
    ],
)
def test_terminal_dash_suffix_requires_complete_captured_number(source, number, matched):
    target = {"name": "Tangela", "attributes": {}}
    assert bool(review.product_name_relation(target, source, number)) is matched


def test_dash_suffix_preserves_named_forms_and_ownership():
    target = {"name": "Team Rocket's Houndoom", "attributes": {}}
    assert review.product_name_relation(target, "Team Rocket's Houndoom - 191/182", "191/182")
    assert not review.product_name_relation(
        {"name": "Houndoom", "attributes": {}}, "Team Rocket's Houndoom - 191/182", "191/182"
    )
    target = {"name": "Unown (A)", "attributes": {}}
    assert review.product_name_relation(target, "Unown (A) - 001/120", "1/120")
    assert not review.product_name_relation(
        {"name": "Unown", "attributes": {}}, "Unown (A) - 001/120", "1/120"
    )


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("language", "ja", "known_source_language_conflict"),
        ("language", None, "known_source_language_conflict"),
        ("isSelectable", True, "selectable_distribution_conflict"),
        ("isSpecialProduct", True, "selectable_distribution_conflict"),
        ("condition", "Near Mint", "unsupported_source_condition_or_grade"),
        ("edition", "first_edition", "source_edition_conflict"),
        ("finish", "holo", "source_finish_conflict"),
        ("url", "https://www.tcgplayer.com/product/99/pokemon-synthetic", "invalid_source_identity_url"),
    ],
)
def test_explicit_product_conflicts_block_binding(case, field, value, reason):
    case[1][field] = value
    decisions, bindings = choose(case)
    assert not bindings
    assert decisions[0]["decision"] == reason


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("language", "fr"),
        ("condition", "Near Mint"),
        ("grade", "10"),
        ("valuation_date", "2026-10-17"),
        ("captured_at", "2026-10-17T00:00:00Z"),
        ("currency", "EUR"),
    ],
)
def test_price_semantic_claims_cannot_override_reference_contract(case, field, value):
    case[2][field] = value
    assert not choose(case)[1]


def test_unknown_finish_does_not_choose_first_subtype(case):
    case[0]["finish"] = case[0]["variant"] = None
    price2 = dict(productId=10, subTypeName="Holofoil", marketPrice=None)
    decisions, bindings = choose(
        case, prices={(11, (10, "Normal")): [case[2]], (11, (10, "Holofoil")): [price2]}
    )
    assert not bindings
    assert decisions[0]["decision"] == "ambiguous_supported_subtypes"


def test_duplicate_products_and_shared_source_keys_are_never_first_matches(case):
    extra = copy.deepcopy(case[1])
    extra.update(productId=20, url="https://www.tcgplayer.com/product/20/pokemon-synthetic-set-nidoran-f")
    decisions, bindings = choose(case, products={(11, 10): [case[1]], (11, 20): [extra]})
    assert not bindings
    assert decisions[0]["decision"] == "ambiguous_literal_products"
    other = dict(case[0], id="other")
    decisions, bindings = choose(case, targets={"printing": case[0], "other": other})
    assert not bindings
    assert {row["decision"] for row in decisions} == {"shared_source_binding_ambiguous"}


def test_cross_group_or_duplicate_identity_aborts_instead_of_selecting(case):
    with pytest.raises(ValueError, match="Duplicate"):
        choose(case, products={(11, 10): [case[1], case[1]]})
    case[1]["categoryId"] = 1
    with pytest.raises(ValueError, match="non-Pokemon"):
        choose(case)


def test_missing_denominator_and_language_evidence_remain_explicit(case):
    case[3]["denominators"] = {}
    decisions, bindings = choose(case)
    assert not bindings
    assert decisions[0]["decision"] == "collector_denominator_conflict_or_missing_evidence"
    case[1]["extendedData"][0]["value"] = "1"
    case[3]["language_evidence"] = []
    assert choose(case)[0][0]["decision"] == "missing_English_scope_evidence"


def test_unsupported_special_variant_stays_unsupported(case):
    case[0]["variant"] = '{"type":"normal","stamp":["set-logo"]}'
    decisions, bindings = choose(case)
    assert not bindings
    assert decisions[0]["decision"] == "unsupported_catalog_variant"


def test_contract_keeps_valuation_null_and_references_compact_scope_evidence(case):
    decisions, bindings = choose(case)
    built = datetime(2026, 10, 17, tzinfo=timezone.utc)
    contract = review.contract_for(
        {"printing": case[0]}, decisions, bindings, built, "review-v1", {"groups": [11]}
    )
    field = contract["fields"]["marketPrice"]
    assert field["valuation_date_field"] is None
    assert field["identity_scope"] == "conditional_market"
    assert contract["rights"]["immutable_save"] is False
    mapping = contract["mappings"]["printing"]
    assert mapping["provider_identity"]["number"] == "001"
    assert len(mapping["provider_identity"]["mapping_review"]) < 450
    assert "scope:" in mapping["provider_identity"]["mapping_review"]


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/product/10/pokemon-synthetic",
        "http://www.tcgplayer.com/product/10",
        "https://www.tcgplayer.com/product/100/pokemon-synthetic",
        "https://www.tcgplayer.com/product/10/magic-card",
        "https://u:p@www.tcgplayer.com/product/10",
        "https://www.tcgplayer.com:443/product/10",
    ],
)
def test_product_url_preserves_exact_source_identity(url):
    assert not review.product_url(url, 10)


@pytest.fixture
def rc_scope_inputs(monkeypatch, tmp_path):
    entries = {
        "ordinary": dict(id="ordinary", set_id="set", collector_number="1"),
        "radiant": dict(id="radiant", set_id="set", collector_number="RC14"),
    }
    groups = [
        dict(
            group_id=1409,
            category_id=3,
            literal_name="Legendary Treasures",
            selector="collector_number_does_not_start_RC",
        ),
        dict(
            group_id=1465,
            category_id=3,
            literal_name="Legendary Treasures: Radiant Collection",
            selector="collector_number_starts_RC",
        ),
    ]
    inventory = dict(
        catalog_identity_sha256=review.rules.digest(entries),
        set_bindings=[
            dict(
                set_id="set",
                name="Legendary Treasures",
                language="en",
                source_groups=groups,
                external_set_identity_evidence=[dict(external_id="bw11", provider="tcgdex:en")],
            )
        ],
    )
    base = dict(
        id="tcgdex:en:bw11",
        provider_set_id="bw11",
        name="Legendary Treasures",
        language="en",
        medium="physical",
        official_numbered_count=113,
        source_url="https://example.org/bw11",
        source_sha256="a" * 64,
    )
    rc = dict(
        id="tcgdex:en:rc",
        provider_set_id="rc",
        name="Radiant Collection",
        language="en",
        medium="physical",
        release_date="2013-11-06",
        official_numbered_count=25,
        source_url="https://example.org/rc",
        source_sha256="b" * 64,
    )
    universe = dict(sets=[base, rc])
    monkeypatch.setattr(review.audit, "catalog_metadata", lambda _root: entries)
    monkeypatch.setattr(
        review.audit, "read_json", lambda path: inventory if path.name == "inventory.json" else universe
    )
    selected = [
        dict(printing_id="ordinary", source_group_id=1409),
        dict(printing_id="radiant", source_group_id=1465),
    ]
    return tmp_path, inventory, universe, selected


def test_radiant_supplement_supports_only_reviewed_rc_group(rc_scope_inputs):
    root, _inventory, _universe, selected = rc_scope_inputs
    scope = review.build_scope(root, selected, root / "inventory.json", root / "universe.json")
    ordinary, radiant = scope["group_evidence"]["1409"], scope["group_evidence"]["1465"]
    assert ordinary["denominators"] == {"": ["113"]}
    assert radiant["denominators"] == {"rc": ["rc25"]}
    assert radiant["denominator_evidence"][0]["official_numbered_count"] == 25
    assert radiant["denominator_evidence"][0]["source_sha256"] == "b" * 64
    assert review.collector_relation("RC14", "RC14/RC25", radiant)
    assert review.collector_relation("RC14", "RC14/rc025", radiant)
    assert not review.collector_relation("RC14", "RC14/25", radiant)
    assert not review.collector_relation("RC14", "RC14/113", radiant)
    assert not review.collector_relation("14", "14/RC25", radiant)
    assert not review.collector_relation("RC14", "RC14/RC25", ordinary)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("language", "ja"),
        ("official_numbered_count", 113),
        ("release_date", "2016-02-22"),
        ("name", "Another Collection"),
        ("id", "tcgdex:en:another"),
        ("medium", "digital"),
    ],
)
def test_radiant_supplement_requires_exact_retained_identity(rc_scope_inputs, field, value):
    root, _inventory, universe, selected = rc_scope_inputs
    universe["sets"][1][field] = value
    with pytest.raises(ValueError, match="Radiant Collection"):
        review.build_scope(root, selected, root / "inventory.json", root / "universe.json")
