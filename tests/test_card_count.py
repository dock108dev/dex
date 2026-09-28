import pytest

from pokemon_hunter.parser import extract_count


@pytest.mark.parametrize(
    "text,expected",
    [
        ("40 Pokemon cards", 40),
        ("100+ vintage Pokemon cards", 100),
        ("Lot of 72", 72),
        ("Approx 200 cards", 200),
        ("36 card lot", 36),
        ("50 common/uncommon cards", 50),
        ("100-150 cards", 100),
        ("90–100 Pokemon cards", 90),
        ("1,000 Pokemon cards", 1000),
        ("100 sleeves included", None),
        ("10 packs of 20 cards", None),
        ("Neo Genesis complete set minus 10 cards", None),
        ("100 cards + 25 energy + 10 trainers", 100),
        ("50 Pokémon cards + 50 energy", 50),
        ("100 cards including 25 energy and 10 trainers", 65),
        ("100 Pokemon, no trainers or energy", 100),
        ("100 random Pokémon TCG cards", 100),
        ("up to 100 cards", None),
        ("choose 50 cards", None),
        ("1999 Pokemon cards lot", None),
        ("lot of 100 sleeves", None),
        ("10 x 20 cards", None),
    ],
)
def test_counts(text, expected):
    assert extract_count(text).denominator == expected


def test_conflicts_lower_confidence():
    result = extract_count("100 Pokemon cards lot. Includes 50 cards.")
    assert result.denominator == 50
    assert result.confidence < 0.6


def test_no_false_precision():
    assert extract_count("100 random Pokemon TCG cards").pokemon is None
    assert extract_count("100 Pokemon, no trainers or energy").pokemon == 100


def test_html():
    assert extract_count("<p>100 <b>Pokemon</b> cards</p><script>900 cards</script>").denominator == 100


@pytest.mark.parametrize("text", ["100 Pokemon card sleeves", "100 card binder", "100 card sleeves included"])
def test_accessory_counts_not_cards(text):
    assert extract_count(text).denominator is None


@pytest.mark.parametrize(
    "text,expected",
    [
        ("100 Pokemon cards including 25 energy and 10 trainers", 65),
        ("100+ Pokemon cards including 25 energy", 75),
        ("100 Pokemon cards with 25 energy", 75),
        ("100 Pokemon cards plus 25 energy", 100),
    ],
)
def test_brand_name_not_species_count(text, expected):
    assert extract_count(text).denominator == expected
