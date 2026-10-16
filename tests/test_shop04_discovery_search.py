"""Offline search intent controls: no provider or customer data."""

import pytest

from pokemon_hunter.beta.discovery_search import canonical_query, product_kind, submitted_query


@pytest.mark.parametrize("alias", ["Base 2", "Base Set 2", "base2", "BASE SET2"])
def test_base_two_alias_never_becomes_base_one(alias):
    assert canonical_query("Alakazam " + alias) == "Alakazam Base Set 2"
    assert canonical_query(canonical_query(alias)) == "Base Set 2"


def test_base_alias_set_override_and_bounded_suffix_are_distinct():
    assert canonical_query("Alakazam base") == "Alakazam Base Set"
    assert submitted_query("Alakazam base", set_name="Base Set 2") == "Alakazam Base Set 2"
    assert submitted_query("Alakazam base 2", set_name="Base Set") == "Alakazam Base Set"
    assert (
        submitted_query("Hypno", product_type="mixed_lots", english_vintage=True)
        == "Hypno lot English vintage"
    )
    query = submitted_query("x" * 200, set_name="Team Rocket", english_vintage=True)
    assert len(query) <= 200 and query.endswith("Team Rocket English")


@pytest.mark.parametrize(
    "title", ["Hypno mixed lot", "Alakazam 10 cards", "Gengar binder", "Hypno loose collection"]
)
def test_loose_mixed_cards_are_supported_without_mystery_assumption(title):
    assert product_kind(title) == "mixed_lot"


@pytest.mark.parametrize(
    "title", ["Hypno mystery lot", "Gengar curated lot", "Alakazam sealed booster", "Hypno choose your card"]
)
def test_unsupported_product_rules_still_apply(title):
    assert product_kind(title) == "unsupported"
