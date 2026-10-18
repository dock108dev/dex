"""Engineering-only regressions for the independent source identity reviewer."""

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("independent_tcgcsv_audit", SCRIPTS / "audit_tcgcsv_batch.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


@pytest.mark.parametrize(
    "local,source,denominators,expected",
    [
        ("1", "001/165", {"": ["165"]}, True),
        ("H1", "H01/H32", {"h": ["H32"]}, True),
        ("H1", "1/165", {"": ["165"], "h": ["H32"]}, False),
        ("RC1", "RC01/RC25", {"": ["113"]}, False),
        ("SL1", "SL01/11", {"sl": ["11"]}, True),
        ("1a", "001/165", {"": ["165"]}, False),
        ("1/165", "001/999", {"": ["165", "999"]}, False),
        ("1/165", "001", {"": ["165"]}, True),
        ("1/165", "001", {"": ["999"]}, False),
    ],
)
def test_collector_prefix_suffix_denominator_boundaries(local, source, denominators, expected):
    assert audit.collector_matches(local, source, {"denominators": denominators}) is expected


def test_name_suffix_requires_number_and_preserves_form():
    target = {"name": "Nidoran ♀", "attributes": {}}
    assert audit.name_matches(target, "Nidoran F (030)", "30/165")
    assert not audit.name_matches(target, "Nidoran F (031)", "30/165")
    assert not audit.name_matches(target, "Nidoran M (030)", "30/165")
    assert not audit.name_matches({"name": "Castform", "attributes": {}}, "Castform (Rainy Form)", "1/165")


def test_hyphen_number_suffix_requires_whole_agreeing_collector_identity():
    target = {"name": "Houndour", "attributes": {}}
    assert audit.name_matches(target, "Houndour - 060/109", "60/109")
    assert not audit.name_matches(target, "Houndour - 060/110", "60/109")
    assert not audit.name_matches(target, "Houndour - 061/109", "60/109")
    assert not audit.name_matches(target, "Houndour - Dark Form", "60/109")
    assert not audit.name_matches(target, "Houndour (Prime) - 060/109", "60/109")
    assert not audit.name_matches(target, "Houndour - 060a/109", "60/109")
    assert not audit.name_matches(target, "Houndour - 060", "60/109")


def test_supported_variant_does_not_infer_special_distribution():
    target = {"language": "en", "edition": None, "finish": "reverse", "variant": '{"type":"reverse"}'}
    assert audit.compatible(target, "Reverse Holofoil")
    target["variant"] = '{"type":"reverse","stamp":["set-logo"]}'
    assert not audit.compatible(target, "Reverse Holofoil")
    target.update(edition="unlimited", finish="normal", variant=None)
    assert audit.compatible(target, "Unlimited")
    assert not audit.compatible(target, "Normal")


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.tcgplayer.com/product/123/pokemon-set-pikachu", True),
        ("https://www.tcgplayer.com/product/123", True),
        ("https://www.tcgplayer.com/product/1234/pokemon-set-pikachu", False),
        ("https://evil.test/product/123/pokemon-set-pikachu", False),
        ("https://www.tcgplayer.com/product/123/magic-set-pikachu", False),
        ("https://www.tcgplayer.com/product/123/pokemon-set-pikachu?variant=other", False),
    ],
)
def test_product_url_is_exact_identity(url, expected):
    assert audit.source_url_matches(url, 123) is expected


def test_shared_source_keys_and_ambiguous_subtypes_stay_unresolved():
    target = dict(
        name="Pikachu",
        collector_number="1",
        language="en",
        finish="normal",
        edition=None,
        variant=None,
        attributes={},
    )
    product = dict(
        productId=123,
        categoryId=3,
        groupId=7,
        name="Pikachu",
        url="https://www.tcgplayer.com/product/123/pokemon-set-pikachu",
        extendedData=[{"name": "Number", "value": "001/10"}],
    )
    sources, prices = {(7, 123): product}, {(7, 123, "Normal"): [{}]}
    evidence = {"7": {"denominators": {"": ["10"]}}}
    selected, _ = audit.rederive({"a": target}, {"a": 7}, evidence, sources, prices)
    assert set(selected) == {"a"}
    selected, counts = audit.rederive({"a": target, "b": target}, {"a": 7, "b": 7}, evidence, sources, prices)
    assert selected == {} and counts["shared_source_key"] == 2
    prices[(7, 123, "Unlimited")] = [{}]
    selected, counts = audit.rederive({"a": target}, {"a": 7}, evidence, sources, prices)
    assert selected == {} and counts["no_unique_compatible_subtype"] == 1


def test_selectable_product_cannot_be_admitted_as_regular_printing():
    product = dict(
        productId=123,
        name="Pikachu",
        isSelectable=True,
        url="https://www.tcgplayer.com/product/123/pokemon-set-pikachu",
        extendedData=[],
    )
    assert audit.product_conflicts(product, {}) == ["special_distribution"]
