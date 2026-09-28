import pytest

from pokemon_hunter.classifier import detect_sets, lot_rejection


@pytest.mark.parametrize(
    "text,purity",
    [
        ("Base Jungle Fossil", "pure"),
        ("Neo Genesis Neo Discovery", "pure"),
        ("250 cards Base Jungle Neo Ruby Sapphire", "mixed"),
        ("wotc bulk", "probably_pure"),
        ("1999-2024 vintage collection", "mixed"),
        ("rocket bulk", "unknown"),
        ("Team Rocket Returns Neo", "mixed"),
        ("Neo Genesis Japanese", "mixed"),
        ("Sword & Shield", "unknown"),
        ("Jungle Evolutions lot", "mixed"),
    ],
)
def test_classification(catalog, text, purity):
    assert detect_sets(text, catalog)[2] == purity


def test_base_set_2(catalog):
    assert detect_sets("Base Set 2 lot", catalog)[0] == {"base_set_2"}


@pytest.mark.parametrize(
    "text",
    [
        "Neo Genesis complete set minus 3 cards",
        "wotc mystery pack",
        "Neo bulk guaranteed holo",
        "lot of energy only",
        "Neo sealed booster lot",
        "custom pack lot",
    ],
)
def test_not_bulk(text):
    assert lot_rejection(text)


def test_played_unsorted():
    assert lot_rejection("Damaged Neo childhood collection unsorted lot") is None
