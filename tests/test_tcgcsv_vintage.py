"""Retained-source matching never conflates physical variants or missing values."""

from pokemon_hunter.beta import tcgcsv_vintage as vintage


def parent(key="a", **overrides):
    return dict(
        id=key, name="Charizard", collector_number="4", set_name="Base Set", language="en", **overrides
    )


def product(**overrides):
    return dict(
        categoryId=3,
        groupId=604,
        name="Charizard (004)",
        extendedData=[dict(name="Number", value="004/102")],
        **overrides,
    )


def test_exact_numbered_match_and_zero_padding():
    p, source = parent(), product()
    assert vintage.match_products({"a": p}, [source]) == [(p, source)]


def test_ambiguous_product_or_parent_is_not_first_match():
    assert vintage.match_products({"a": parent()}, [product(), product()]) == []
    assert vintage.match_products({"a": parent(), "b": parent("b")}, [product()]) == []


def test_number_alone_does_not_select_product_or_relabel_variant():
    p = product()
    p["name"] = "Charizard (Shadowless)"
    assert vintage.match_products({"a": parent()}, [p]) == []
    assert vintage.match_products({"a": parent(edition="unlimited")}, [product()]) == []


def test_missing_and_duplicate_numbers_are_excluded():
    p = product()
    p["extendedData"].append(dict(name="Number", value="004/102"))
    assert vintage.product_number(p) is None
    assert vintage.number("PROMO") is None


def test_only_explicit_ordinary_physical_subtypes_make_variants():
    assert vintage.descriptor("Unlimited Holofoil") == dict(type="holo", edition="unlimited")
    assert vintage.descriptor("1st Edition") == dict(type="normal", stamp=["1st-edition"])
    assert vintage.descriptor("Normal") is None
    assert vintage.descriptor("Reverse Holofoil") is None


def test_base_and_shadowless_remain_distinct_source_groups():
    from pokemon_hunter.beta import catalog_variants
    from pokemon_hunter.beta import market_identity as identity

    assert vintage.descriptor("Normal", 604) == dict(type="normal", edition="unlimited")
    shadow = vintage.descriptor("Unlimited Holofoil", 1663)
    assert shadow == dict(type="holo", edition="unlimited", other=["shadowless"])
    edition, finish, variant = catalog_variants.physical(shadow)
    printing = dict(language="en", edition=edition, finish=finish, variant=variant)
    provider = dict(
        language="en", edition=edition, finish=finish, variant="Unlimited Holofoil", source_group="1663"
    )
    assert identity.applicable(dict(provider_identity=provider), printing)
    assert not identity.compatible(printing, edition, finish)
    assert not identity.compatible(dict(printing, variant=None), edition, finish, shadowless=True)
    assert not identity.applicable(dict(provider_identity=dict(provider, source_group="635")), printing)
    base = dict(printing, variant=None)
    assert identity.applicable(
        dict(provider_identity=dict(provider, source_group="604", variant="Holofoil")), base
    )
    assert not identity.applicable(
        dict(provider_identity=dict(provider, source_group="635", variant="Holofoil")), base
    )
    p, first, second = parent(), product(), product()
    second["groupId"] = 1663
    assert len(vintage.match_products({"a": p}, [first, second])) == 2


def test_printed_name_accents_and_reviewed_spelling_do_not_hide_products():
    assert vintage.name("Pokémon Trader", "77") == vintage.name("Pokemon Trader", "77")
    assert vintage.name("Imposter Professor Oak", "73") == vintage.name("Impostor Professor Oak", "73")
    assert vintage.name("Charizard (Black Dot Error)", "4") != vintage.name("Charizard", "4")


def test_finish_comes_from_closed_original_set_numbering_not_price_availability():
    assert vintage.numbered_finish(parent()) == "holo"
    assert vintage.numbered_finish(dict(parent(), collector_number="25", set_name="Fossil")) == "normal"
    assert vintage.numbered_finish(dict(parent(), collector_number="16", set_name="Fossil")) == "normal"
    assert vintage.numbered_finish(dict(parent(), collector_number="16", set_name="Jungle")) == "holo"
    assert vintage.numbered_finish(dict(parent(), collector_number="0")) is None
    assert vintage.numbered_finish(dict(parent(), set_name="Base Set 2")) is None
