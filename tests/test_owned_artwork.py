"""Synthetic engineering checks; no owner state or remote image requests."""

import csv
import io
import json
from urllib.parse import parse_qs, urlsplit

import pytest
from test_b1 import env as env
from test_b2 import apply
from test_b2 import b2 as b2
from test_b2_parity import restored as restored
from test_migration import snapshot as snapshot
from test_ownership_declarations import migrate

from pokemon_hunter.beta import collection as inv
from pokemon_hunter.beta import owned_artwork as art
from pokemon_hunter.beta import ownership_declarations as declarations
from pokemon_hunter.beta.canonical_species import registry
from pokemon_hunter.migration import digest


def select_marks(b2, marks):
    migrate(b2)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=declarations.FULL_HEADERS)
    writer.writeheader()
    for n, species in registry().items():
        if n > 251:
            continue
        cells = marks.get(n, {})
        writer.writerow(
            dict.fromkeys(declarations.FULL_HEADERS, "")
            | dict(Dex=str(n), Pokemon=species["name"], Status="Owned" if cells else "Missing")
            | cells
        )
    text = stream.getvalue()
    return apply(b2, "owner_declaration", dict(text=text, sha256=digest(text.encode())))


def printing(**overrides):
    return dict(set_name="Base Set", name="Bulbasaur", collector_number="44", language="en") | overrides


@pytest.mark.parametrize(
    "set_name,name,number",
    [
        ("Neo Genesis", "Bulbasaur", "44"),
        ("Base Set", "Ivysaur", "44"),
        ("Base Set", "Bulbasaur", None),
        ("Base Set", "Bulbasaur", "44/102"),
        ("Base Set", "Bulbasaur", "../44"),
    ],
)
def test_unresolved_or_mismatched_identity_has_no_image(set_name, name, number):
    assert art.thumbnail(set_name, name, number, [printing()]) is None


def test_english_reference_only_and_low_resolution():
    assert art.thumbnail("Base Set", "Bulbasaur", "44", [printing()]) == (
        "https://assets.tcgdex.net/en/base/base1/44/low.webp"
    )
    assert art.thumbnail("Base Set", "Bulbasaur", "44", [printing(language="ja")]) is None
    assert (
        art.thumbnail(
            "Wizards Black Star Promos",
            "Mew",
            "8",
            [printing(set_name="Wizards Black Star Promos", name="Mew", collector_number="8")],
        )
        == "https://assets.tcgdex.net/en/base/basep/8/low.webp"
    )


def test_card_detail_is_a_normal_private_page(restored):
    before = inv.export_data(restored["actor"])
    response = restored["a"].get("/cards/a/")
    assert response.status_code == 302
    destination = urlsplit(response.url)
    assert destination.path.startswith("/card-groups/dg1-")
    printing = next(
        p for p in inv.catalog(restored["actor"]) if json.loads(p["provenance"]).get("legacy_id") == "a"
    )
    assert parse_qs(destination.query) == {"child": [printing["id"]]}
    for _ in range(2):
        canonical = restored["a"].get(response.url)
        assert canonical.status_code == 200
        assert "img-src 'self' https://assets.tcgdex.net" in canonical["Content-Security-Policy"]
        assert canonical["Cache-Control"] == "private, no-store"
        selected = restored["a"].get("/api" + destination.path, {"child": printing["id"]})
        assert selected.status_code == 200
        assert selected.json()["selected_child"]["id"] == printing["id"]
    assert restored["client"]().get("/cards/a/").status_code == 302
    assert restored["client"]().get(response.url).status_code == 302
    assert restored["a"].get("/owned-cards/").status_code == 404
    assert inv.export_data(restored["actor"]) == before


def test_images_integrate_with_private_collection_and_parity_without_changing_export(b2):
    from pokemon_hunter.beta import parity

    p = b2["catalog"][0]
    inv.execute("UPDATE catalog_sets SET name='Base Set' WHERE id=%s", [p["set_id"]])
    inv.execute(
        "UPDATE printings SET collector_number='44',language='en',attributes=%s WHERE id=%s",
        [json.dumps(dict(name="Bulbasaur", game_key="pokemon", supertype="Pokémon", pokemon_dex=1)), p["id"]],
    )
    before = inv.export_data(b2["actor"])
    response = b2["a"].get("/api/collection/")
    assert response.status_code == 200
    assert response.json()["printing_details"][p["id"]]["reference_image"]["image_url"].endswith(
        "/base/base1/44/low.webp"
    )
    projected = parity.projection(b2["actor"])
    assert projected["cards"]["a"]["reference_image"]["name"] == "Bulbasaur"
    assert projected["pokedex"]["1"]["reference_images"][0]["number"] == "44"
    assert not parity.projection(b2["member"])["pokedex"]["1"]["reference_images"]
    assert not b2["b"].get("/api/collection/").json()["printing_details"]
    assert b2["client"]().get("/api/collection/").status_code == 302
    private_page = b2["a"].get("/collection/")
    assert "img-src 'self' https://assets.tcgdex.net" in private_page["Content-Security-Policy"]
    assert private_page["Cache-Control"] == "no-store"
    assert b2["a"].get("/owned-cards/").status_code == 404
    assert "assets.tcgdex.net" not in b2["client"]().get("/pokedex/")["Content-Security-Policy"]
    assert b"reference_image" not in b2["client"]().get("/api/public/catalog/").content
    assert inv.export_data(b2["actor"]) == before


def test_staging_images_are_unavailable(b2, monkeypatch):
    from django.conf import settings

    monkeypatch.setattr(settings, "STAGING", True)
    assert art.reference_images(b2["actor"]) == []
    response = b2["a"].get("/collection/")
    assert "assets.tcgdex.net" not in response["Content-Security-Policy"]


def test_declarations_never_infer_number_or_create_copy(b2):
    # The imported card name/number is sufficient for a reference scan even when
    # the historical marker requires physical-identity review (Dark cards).
    p = b2["catalog"][0]
    inv.execute("UPDATE catalog_sets SET name='Team Rocket' WHERE id=%s", [p["set_id"]])
    inv.execute(
        "UPDATE printings SET collector_number='45',language='en',attributes=%s WHERE id=%s",
        [
            json.dumps(dict(name="Dark Vaporeon", game_key="pokemon", supertype="Pokémon", pokemon_dex=134)),
            p["id"],
        ],
    )
    select_marks(
        b2,
        {
            134: {"Team Rocket": "✓D Dark Vaporeon #45 (Uncommon)"},
            133: {"Team Rocket": "✓"},
        },
    )
    before = inv.export_data(b2["actor"])
    rows = art.owned_cards(b2["actor"])
    dark = next(r for r in rows if r["name"] == "Dark Vaporeon")
    assert dark["declared"] and dark["image_url"].endswith("/base/base5/45/low.webp")
    assert not any(r["name"] == "Eevee" for r in rows)  # Species mark has no card identity.
    from pokemon_hunter.beta.effective_collection import project

    assert project(b2["actor"])["species"]["133"]["present"]
    assert inv.export_data(b2["actor"]) == before


def test_current_source_overrides_old_copies_and_splits_explicit_cards(b2):
    p = b2["catalog"][0]
    inv.execute("UPDATE catalog_sets SET name='Jungle' WHERE id=%s", [p["set_id"]])
    inv.execute(
        "UPDATE printings SET collector_number='16',language='en',attributes=%s WHERE id=%s",
        [
            json.dumps(dict(name="Wigglytuff", game_key="pokemon", supertype="Pokémon", pokemon_dex=40)),
            p["id"],
        ],
    )
    select_marks(b2, {40: {"Jungle": "✓ Wigglytuff #16 (Rare Holo); Wigglytuff #32 (Rare)"}})
    rows = art.owned_cards(b2["actor"])
    assert [(r["name"], r["number"]) for r in rows] == [("Wigglytuff", "16"), ("Wigglytuff", "32")]
    assert rows[0]["image_url"].endswith("/base/base2/16/low.webp")
    assert rows[1]["image_url"] is None  # Not silently mapped without catalog support.
    # Even an empty selected collection must not revive older physical imports.
    select_marks(b2, {})
    assert art.owned_cards(b2["actor"]) == []
