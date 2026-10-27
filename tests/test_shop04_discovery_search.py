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
    assert submitted_query("Hypno", english_vintage=True) == "Hypno English vintage"
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


def test_selected_set_is_a_provider_facet_and_survives_more():
    from pokemon_hunter.beta.discovery_paging import checked_params, first_pages, following

    pages = first_pages("Venusaur Base Set", "both", "ending_soonest", set_name="Base Set")
    for page in pages:
        wire = checked_params(page)
        assert wire["q"] == "Venusaur"
        assert wire["aspect_filter"] == f"categoryId:{page.category},Set:{{Base Set}}"
        assert wire["sort"] == "endingSoonest"
        assert "itemLocationCountry:US" in wire["filter"]
        more = checked_params(following(page, {"total": 80}, [{}] * 20))
        assert more == {**wire, "offset": 20}


def test_unselected_set_does_not_invent_a_facet():
    from pokemon_hunter.beta.discovery_paging import checked_params, first_pages

    wire = checked_params(first_pages("Venusaur", "mixed_lots", "best_match")[0])
    assert wire["q"] == "Venusaur"
    assert "aspect_filter" not in wire


@pytest.mark.parametrize("set_name", ["Base Set},Game:{Other", "Base|Jungle", "Base\nSet"])
def test_set_cannot_inject_provider_filters(set_name):
    from pokemon_hunter.beta.discovery_paging import first_pages

    with pytest.raises(ValueError):
        first_pages("Venusaur", "mixed_lots", "best_match", set_name=set_name)
