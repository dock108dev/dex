"""Disposable ownership projection equivalence for the Shopping performance repair."""

from test_b1 import env as env
from test_b2 import b2 as b2
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_effective_collection import cx as cx
from test_effective_collection import select
from test_migration import snapshot as snapshot
from test_sealed_catalog import e1 as e1

from pokemon_hunter.beta import parity


def test_candidate_projection_retains_current_ownership_without_presentation(cx, monkeypatch):
    select(cx, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}})
    full = parity.projection(cx["actor"])

    def denied(*args, **kwargs):
        raise AssertionError("Candidate reads must not bind overview images or values")

    monkeypatch.setattr(parity, "estimates", denied)
    from pokemon_hunter.beta import image_bindings, owned_artwork

    monkeypatch.setattr(image_bindings, "catalog_images", denied)
    monkeypatch.setattr(owned_artwork, "reference_images", denied)
    lean = parity.projection(cx["actor"], include_presentation=False)
    assert lean["catalog"] == full["catalog"]
    assert lean["effective_collection"] == full["effective_collection"]
    assert {
        key: {k: v for k, v in card.items() if k != "reference_image"} for key, card in full["cards"].items()
    } == lean["cards"]
    assert {n: s["dex_owned"] for n, s in lean["pokedex"].items()} == {
        n: s["dex_owned"] for n, s in full["pokedex"].items()
    }
