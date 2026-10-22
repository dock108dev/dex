"""Offline equivalence and bounded-work checks for the real-catalog delay repair."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from pokemon_hunter.beta import discovery, parity
from pokemon_hunter.beta import discovery_comparison as comparison
from pokemon_hunter.beta import discovery_matching as matching


@pytest.mark.parametrize(
    "text",
    [
        "Fossil Hypno 8/62 holo lot",
        "Dark Hypno Team Rocket 9/82",
        "Blaine's Charizard 2/132",
        "Mr. Mime and Pikachu ex lot",
        "PIKACHU EX",
        "Pikachu  base set 2 58/102",
        "Legendary Collection",
        "Farfetch’d 27/102",
        "Mr.\tMime 6/64",
        "Koffing 51/102",
        "Vaporeon Jolteon Gengar",
        "no recognizable name",
    ],
)
def test_name_index_preserves_full_literal_matching_and_projection(text, monkeypatch):
    names = [
        "Hypno",
        "Dark Hypno",
        "Blaine's Charizard",
        "Charizard",
        "Mr. Mime",
        "Pikachu",
        "Pikachu ex",
        "Farfetch'd",
        "Koffing",
    ]
    cards = [
        dict(
            id=str(i),
            name=name,
            set_name="Fossil",
            collector_number="8/62",
            attributes={},
            set_id="fossil",
            language="en",
            edition="standard",
            finish="normal",
            variant="normal",
        )
        for i, name in enumerate(names)
    ]
    cards.append(dict(cards[0], id="alias", attributes={"name_aliases": ["Sleeper"]}))
    clues = comparison._clues({"title": text})
    index = matching.NameIndex(cards)
    narrowed = index.candidates(clues)
    assert matching.literal_candidates(narrowed, text) == matching.literal_candidates(cards, text)
    assert comparison._matches(narrowed, clues) == comparison._matches(cards, clues)
    monkeypatch.setattr(comparison.store, "verified", lambda actor: actor)
    raw = [{"itemId": "engineering", "title": text, "_discovery_category": "183455"}]
    full = comparison._project(None, deepcopy(raw), cards, [], artwork={})
    indexed = comparison._project(None, deepcopy(raw), cards, [], artwork={}, candidates_for=index.candidates)
    assert indexed == full


def test_repeated_printings_check_each_name_family_once(monkeypatch):
    cards = [dict(id=str(i), name="Hypno", attributes={}) for i in range(33083)]
    index = matching.NameIndex(cards)
    original = matching.name_spans
    calls = []

    def spans(p, text):
        calls.append(p["id"])
        return original(p, text)

    monkeypatch.setattr(matching, "name_spans", spans)
    assert index.candidates({"text": "Hypno Fossil"}) == cards
    assert len(calls) == 1


def test_metadata_needs_no_ownership_or_artwork_projection(monkeypatch):
    monkeypatch.setattr(discovery.store, "verified", lambda actor: actor)
    monkeypatch.setattr(discovery, "_sets", lambda actor: {"fossil": "Fossil"})
    monkeypatch.setattr(discovery.ebay_hunts, "status", lambda: {"configured": True})
    monkeypatch.setattr(
        parity, "projection", lambda *a, **kw: pytest.fail("Metadata must not build the collection overview")
    )
    assert discovery.metadata(SimpleNamespace())["sets"] == [{"id": "fossil", "name": "Fossil"}]
