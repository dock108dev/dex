"""Frozen literal parsing and explicit unresolved variant policy, without acquisition."""

import importlib.util
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "retained_parser", Path(__file__).resolve().parents[1] / "scripts/prepare_d6.py"
)
parser = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(parser)


def test_literals_preserve_multiple_species_literal_number_and_name():
    result = parser.parse(
        "const card: Card = {name: {en: 'Mewtwo & Mew-GX'}, number: 'SM191', dexId: [150, 151], variants: [{type: 'holo', stamp: ['promo']}]}\nexport default card"
    )
    assert result["dexId"] == [150, 151]
    assert result["number"] == "SM191"
    assert result["name"]["en"] == "Mewtwo & Mew-GX"


@pytest.mark.parametrize(
    "value",
    [
        "{name: 'a', name: 'b'}",
        "{name: dangerous()}",
        "{dexId: [1 + dangerous()]}",
        "{name: process.env.SECRET}",
    ],
)
def test_executable_or_conflicting_literals_are_refused(value):
    with pytest.raises((ValueError, IndexError)):
        parser.parse("const card: Card = " + value)


def test_only_literal_english_variant_combinations_are_eligible():
    accepted, excluded = parser.english_variants(
        [{"type": "normal", "languages": ["en"]}, {"type": "holo", "languages": ["ja"]}]
    )
    assert accepted == [{"type": "normal", "languages": ["en"]}]
    assert len(excluded) == 1
    assert parser.english_variants({"normal": True})[0] == []


def test_inventory_role_partition_is_explicit_and_unresolved_names_stay_unresolved():
    import sys

    scripts = Path(__file__).resolve().parents[1] / "scripts"
    sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location(
        "broad_inventory_test", scripts / "prepare_broad_catalog.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for code, name, expected in [
        ("bw1", "Black & White", "main"),
        ("dv1", "Dragon Vault", "special"),
        ("tk-bw-e", "BW trainer Kit (Excadrill)", "supplemental"),
        ("sv03.5", "151", "special"),
        ("bwp", "BW Black Star Promos", "promo"),
        ("unknown", "Unknown", "unresolved"),
    ]:
        assert module.coverage_role(code, name) == expected
