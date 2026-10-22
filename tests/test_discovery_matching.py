"""Explicitly fabricated local matching cases; no provider or customer data."""

import json
from types import SimpleNamespace

import pytest
from test_hunter_catalog import OBSERVED, listing, printing, reference
from test_hunter_catalog import local as local

from pokemon_hunter.beta import (
    collection,
    discovery_comparison,
    hunter_catalog,
    lot_calculator,
    market_identity,
)


def project(local, monkeypatch, cards, raw):
    monkeypatch.setattr(collection, "catalog", lambda *a, **kw: cards)
    monkeypatch.setattr(lot_calculator, "retained_records", lambda: [])
    monkeypatch.setattr(
        discovery_comparison.lot_guides,
        "cell_details",
        lambda p, *a: ({"raw": reference(p)}, {}),
    )
    return hunter_catalog.compare(local, [raw], now=OBSERVED)[0]


@pytest.mark.parametrize("alias", ["Neo Gen", "neo GEN", "neo1"])
def test_published_aliases_and_padded_fraction_keep_literal_identity(local, monkeypatch, alias):
    p = printing("pichu", "Pichu", set_name="Neo Genesis", number="001/111", set_aliases=["Neo Gen", "neo1"])
    raw = listing(p, title=f"{alias} Pichu #1/0111 English Unlimited Non Holo")
    row = project(local, monkeypatch, [p], raw)
    assert row["hunt_status"] == "priced" and row["identity_status"] == "matched"
    assert row["proposed_identity"]["name"] == "Pichu"
    assert row["proposed_identity"]["set_name"] == "Neo Genesis"
    assert row["proposed_identity"]["collector_number"] == "001/111"
    assert row["seller_collector_numbers"] == ["1/0111"]


@pytest.mark.parametrize("alias", ["base2", "base 2", "Base Set 2"])
def test_base_and_base_two_aliases_never_cross_even_with_same_name_number(local, monkeypatch, alias):
    base = printing("base", "Pikachu", set_name="Base Set", number="058")
    two = printing("two", "Pikachu", set_name="Base Set 2", number="058")
    raw = listing(two, title=f"{alias} Pikachu 58 English Unlimited Non Holo")
    row = project(local, monkeypatch, [base, two], raw)
    assert row["proposed_identity"]["printing_id"] == "two"
    base_only = project(local, monkeypatch, [base], raw)
    assert base_only["proposed_identity"] is None and base_only["reference"] is None


@pytest.mark.parametrize("observed", ["252/198", "252/182 #252/198", "252/182 #248/182"])
def test_explicit_collector_conflicts_never_receive_reference(local, monkeypatch, observed):
    p = printing("modern")
    raw = listing(p, title=f"Paradox Rift Gholdengo ex #{observed} English Unlimited Non Holo")
    row = project(local, monkeypatch, [p], raw)
    assert row["identity_status"] == "conflicting"
    assert row["proposed_identity"] is None and row["reference"] is None
    assert "collector-number" in row["reason"]
    assert row["identity_candidates"][0]["seller_collector_numbers"]


def test_conflicting_explicit_opaque_collector_claim_is_not_discarded(local, monkeypatch):
    p = printing("opaque", "Literal Trainer", number="PROMO-A")
    row = project(local, monkeypatch, [p], listing(p, title=listing(p)["title"] + " #PROMO-B"))
    assert row["identity_status"] == "conflicting" and row["reference"] is None
    assert row["identity_candidates"][0]["seller_collector_numbers"] == ["PROMO-A", "PROMO-B"]


def test_explicit_hash_year_is_a_collector_conflict_and_cannot_be_discarded(local, monkeypatch):
    p = printing("explicit-year", "Pikachu", set_name="Base Set", number="58/102")
    row = project(local, monkeypatch, [p], listing(p, title=listing(p)["title"] + " #2025"))
    assert row["identity_status"] == "conflicting" and row["reference"] is None


@pytest.mark.parametrize("number", ["001/A", "X-02", "PROMO-A", "TG023/TG030"])
def test_literal_published_numbers_outside_simple_integer_grammar(local, monkeypatch, number):
    p = printing("literal", "Literal Trainer", number=number, pokemon_dex=None)
    row = project(local, monkeypatch, [p], listing(p))
    assert row["proposed_identity"]["collector_number"] == number
    assert row["identity_status"] == "matched" and row["reference"]
    reordered = listing(p, title=f"Paradox Rift #{number} Literal Trainer English Unlimited Non Holo")
    assert project(local, monkeypatch, [p], reordered)["proposed_identity"]["collector_number"] == number


@pytest.mark.parametrize("catalog,seller", [("252", "252/182"), ("252/182", "252")])
def test_missing_denominator_stays_conditional_and_retains_seller_claim(local, monkeypatch, catalog, seller):
    p = printing("number", number=catalog)
    row = project(
        local,
        monkeypatch,
        [p],
        listing(p, title=f"Paradox Rift Gholdengo ex #{seller} English Unlimited Non Holo"),
    )
    assert row["hunt_status"] == "conditional" and row["reference"]
    assert row["identity_uncertainties"] and "denominator" in row["reason"]
    assert row["seller_collector_numbers"] == [seller]


@pytest.mark.parametrize("name", ["Galarian Slowking", "Radiant Slowking", "Slowking ex", "Mega Slowking EX"])
def test_longer_published_names_cannot_collapse_to_plain_printing(local, monkeypatch, name):
    plain = printing("plain", "Slowking", number="1/165")
    named = printing("named", name, number="1/165")
    row = project(local, monkeypatch, [plain, named], listing(named))
    assert row["proposed_identity"]["printing_id"] == "named"
    assert {item["printing_id"] for item in row["identity_candidates"]} == {"named"}


def test_set_index_cannot_hide_a_retained_longer_name(local, monkeypatch):
    plain = printing("plain", "Alakazam", set_name="Base Set", number="1")
    named = printing("named", "Mega Alakazam", set_name="Another Set", number="1")
    raw = listing(plain, title="Base Set Mega Alakazam 1 English Unlimited Non Holo")
    row = project(local, monkeypatch, [plain, named], raw)
    assert row["proposed_identity"] is None and row["reference"] is None
    assert {item["printing_id"] for item in row["identity_candidates"]} == {"named"}


def test_typographic_apostrophe_preserves_literal_owned_trainer_name(local, monkeypatch):
    p = printing("trainer", "Professor Turo's Scenario", number="171/182", pokemon_dex=None, owned=True)
    raw = listing(p, title="Paradox Rift Professor Turo’s Scenario 0171/182 English Unlimited Non Holo")
    row = project(local, monkeypatch, [p], raw)
    assert row["proposed_identity"]["name"] == p["name"] and row["reference"]


def test_retained_name_alias_only_matches_when_explicitly_published(local, monkeypatch):
    p = printing(
        "alias",
        "Published Trainer",
        number="171/182",
        attributes={"name_aliases": ["Retained Trainer Alias"]},
    )
    raw = listing(p, title="Paradox Rift Retained Trainer Alias 171/182 English Unlimited Non Holo")
    assert project(local, monkeypatch, [p], raw)["proposed_identity"]["printing_id"] == "alias"
    assert project(local, monkeypatch, [dict(p, attributes={})], raw)["proposed_identity"] is None


@pytest.mark.parametrize("field", ["publication_state", "set_publication_state"])
def test_archived_identity_is_visible_unavailable_without_sibling_substitution(local, monkeypatch, field):
    p = printing("archived", **{field: "archived"})
    row = project(local, monkeypatch, [p], listing(p))
    assert row["proposed_identity"]["printing_id"] == "archived"
    assert row["identity_status"] == "unavailable" and row["reference"] is None
    assert "archived/unavailable" in row["reason"]
    sibling = printing("published")
    ambiguous = project(local, monkeypatch, [p, sibling], listing(p))
    assert ambiguous["proposed_identity"] is None and ambiguous["identity_candidates_total"] == 2


@pytest.mark.parametrize("claim", ["Japanese", "1st Edition", "Holo", "Near Mint PSA 8 CGC 9"])
def test_conflicting_literal_claims_stay_explicit(local, monkeypatch, claim):
    p = printing("conflicting")
    row = project(local, monkeypatch, [p], listing(p, title=listing(p)["title"] + " " + claim))
    assert row["identity_status"] == "conflicting"
    assert row["reference"] is None and row["identity_diagnostics"]


def test_title_and_provider_raw_condition_conflict_cannot_select_favorable_condition(local, monkeypatch):
    p = printing("condition")
    raw = listing(p, title=listing(p)["title"] + " NM", condition="Lightly Played")
    row = project(local, monkeypatch, [p], raw)
    assert row["identity_status"] == "conflicting" and row["reference"] is None
    assert row["raw_condition_basis"] == "Lightly Played"
    assert "raw-condition claims" in row["reason"]
    unknown = discovery_comparison._clues(dict(raw, condition="Ungraded"))
    assert unknown["condition"] == "Ungraded" and unknown["condition_claims"] == ["NM"]


@pytest.mark.parametrize("stat", ["60 HP", "HP: 60"])
def test_pokemon_hp_stat_is_not_a_heavily_played_condition_claim(local, monkeypatch, stat):
    p = printing("stat")
    row = project(local, monkeypatch, [p], listing(p, title=listing(p)["title"] + " " + stat))
    assert row["identity_status"] == "matched" and row["reference"]


@pytest.mark.parametrize(
    "name", ["Computer Error", "Ancient Booster Energy Capsule", "Future Booster Energy Capsule"]
)
def test_published_trainer_names_are_not_seller_product_or_error_claims(local, monkeypatch, name):
    p = printing("trainer", name, number="171/182", pokemon_dex=None)
    row = project(local, monkeypatch, [p], listing(p))
    assert row["discovery_kind"] == "single" and row["reference"]
    assert row["identity_status"] == "matched"
    for claim in ("sealed booster", "misprint error"):
        altered = project(local, monkeypatch, [p], listing(p, title=listing(p)["title"] + " " + claim))
        assert altered["reference"] is None


def test_explicit_number_before_name_and_adjacent_year_use_the_retained_number(local, monkeypatch):
    p = printing("year", "Pikachu", set_name="Base Set", number="58/102")
    raw = listing(p, title="Base Set #58/102 Pikachu 1999 English Unlimited Non Holo")
    row = project(local, monkeypatch, [p], raw)
    assert row["identity_status"] == "matched" and row["reference"]
    assert row["seller_collector_numbers"] == ["58/102"]


def test_name_only_single_stays_ambiguous_and_index_fallback_explains_bad_number(local, monkeypatch):
    p = printing("modern")
    raw = listing(p, title="Paradox Rift Gholdengo ex English Unlimited Non Holo")
    row = project(local, monkeypatch, [p], raw)
    assert row["identity_status"] == "ambiguous" and row["proposed_identity"] is None
    bad = listing(p, title="Paradox Rift Gholdengo ex #99/182 English Unlimited Non Holo")
    conflict = project(local, monkeypatch, [p], bad)
    assert conflict["identity_status"] == "conflicting" and conflict["reference"] is None


def test_reverse_finish_is_literal_and_source_fit_preserves_known_edition_conflicts(local, monkeypatch):
    normal = printing("normal")
    reverse = printing("reverse", finish="reverse", variant="reverse-holo")
    raw = listing(reverse, title="Paradox Rift Gholdengo ex 252/182 English Unlimited Reverse Holo")
    clues = discovery_comparison._clues(raw)
    assert clues["finish"] == "reverse-holo" and clues["conflicts"] == []
    assert discovery_comparison._matches([normal, reverse], clues) == [reverse]
    assert market_identity.FINISH["reverse"] == "reverse-holo"
    source_edition, source_finish = market_identity.SUBTYPES["Reverse Holofoil"]
    assert (source_edition, source_finish) == ("unspecified", "reverse-holo")
    assert not market_identity.compatible(reverse, source_edition, source_finish)
    assert market_identity.compatible(dict(reverse, edition=None), source_edition, source_finish)


def test_index_uses_alias_set_and_number_without_dropping_conflict_candidates():
    cards = [printing(str(i), "Shared Trainer", number=str(i)) for i in range(1, 1001)]
    cards += [printing("other-set", "Shared Trainer", set_name="Unrelated Set", number="42")]
    index = hunter_catalog.IdentityIndex(cards)
    clues = discovery_comparison._clues({"title": "Paradox Rift Shared Trainer #42 English"})
    assert [p["id"] for p in index.candidates(clues)] == ["42"]
    assert (
        len(index.candidates(discovery_comparison._clues({"title": "Paradox Rift Shared Trainer #1002"})))
        == 1000
    )


def test_shared_catalog_retains_set_alias_and_set_availability_in_one_query(monkeypatch):
    from pokemon_hunter.beta import collection_catalog

    p = printing(
        "metadata",
        attributes=json.dumps({"name": "Published Trainer"}),
        unresolved_fields="[]",
        set_aliases='["Published Alias"]',
    )
    reads = []

    def rows(query, params):
        assert params == []
        reads.append(query)
        return [p]

    monkeypatch.setattr(collection_catalog.store, "rows", rows)
    monkeypatch.setattr(collection_catalog, "settings", SimpleNamespace(B4_ENABLED=False, STAGING=False))
    result = collection_catalog.catalog_entries(include_archived=True)
    assert result[0]["set_aliases"] == ["Published Alias"]
    assert len(reads) == 1 and "s.aliases AS set_aliases" in reads[0]
    assert "AS set_publication_state" in reads[0]
