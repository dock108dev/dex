"""D6 static-literal parsing rejects execution and preserves canonical source data."""

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "d6_prepare", Path(__file__).parents[1] / "scripts/prepare_d6.py"
)
parser = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parser)


def test_literal_comments_and_escaped_names():
    data = parser.parse("""import { Card } from "ignored"; const card: Card = {
      name: {en: "Blaine's Moltres"}, // a misleading dexId: [1]
      dexId: [146], category: "Pokemon", set: Set,
      variants: [{type: "holo", stamp: ["1st-edition"]}],
    }; export default card""")
    assert data["dexId"] == [146]
    assert data["name"]["en"] == "Blaine's Moltres"
    assert data["variants"][0]["stamp"] == ["1st-edition"]


def test_literal_concatenation():
    assert (
        parser.parse('const card: Card = {name:{en:"Dark " + "Eevee"}, dexId:[133]}')["name"]["en"]
        == "Dark Eevee"
    )


def test_reject_calls_without_running_them():
    with pytest.raises(ValueError, match="Unsupported expression"):
        parser.parse("const card: Card = {dexId: runUntrustedFunction()}")


def test_empty_dex_and_null_remain_distinct():
    result = parser.parse('const card: Card = {dexId: [], category:"Trainer", rarity:null}')
    assert result["dexId"] == [] and result["rarity"] is None


def test_english_variants_exclude_explicit_other_languages():
    english = {"type": "reverse", "languages": ["en", "de"]}
    german = {"type": "normal", "stamp": ["snowflake"], "languages": ["de"]}
    accepted, excluded = parser.english_variants([english, german])
    assert accepted == [english]
    assert excluded == [{"reason": "non-English-or-unresolved-variant-language", "value": german}]


def test_legacy_variant_shape_is_retained_without_guessing():
    legacy = {"normal": True, "holo": False}
    accepted, excluded = parser.english_variants(legacy)
    assert accepted == []
    assert excluded[0]["value"] == legacy
