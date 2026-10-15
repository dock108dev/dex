"""Synthetic engineering checks; no owner state or remote image requests."""

import csv
import io
import json
from pathlib import Path
from unittest.mock import patch
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


def test_retired_image_construction_and_normalized_lookup_are_absent():
    assert not hasattr(art, "thumbnail")
    assert not hasattr(art, "reference_for")
    assert not hasattr(art, "SETS")
    source = Path(art.__file__).read_text()
    assert "assets.tcgdex.net" not in source
    assert "normalized_name" not in source


@pytest.mark.parametrize("allowed", [False, True])
def test_owned_references_and_page_share_image_availability_policy(b2, allowed):
    from pokemon_hunter.beta import image_bindings

    with (
        patch.object(image_bindings, "enabled", return_value=allowed) as policy,
        patch.object(image_bindings, "catalog_images", wraps=image_bindings.catalog_images) as bind,
    ):
        rows = art.owned_cards(b2["actor"])
        response = b2["a"].get("/collection/")
        assert response.status_code == 200
        directives = [directive.split() for directive in response["Content-Security-Policy"].split(";")]
        image_sources = next((values[1:] for values in directives if values and values[0] == "img-src"), [])
        assert ("https://assets.tcgdex.net" in image_sources) is allowed
        assert bool(rows) is allowed
        if allowed:
            bind.assert_called_once()
        else:
            bind.assert_not_called()
        assert policy.call_count >= 2


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
    before = inv.export_data(b2["actor"])
    rows = art.owned_cards(b2["actor"])
    assert [(r["name"], r["number"]) for r in rows] == [("Wigglytuff", "16"), ("Wigglytuff", "32")]
    assert rows[0]["image_url"].endswith("/base/base2/16/low.webp")
    assert rows[1]["image_url"].endswith("/base/base2/32/low.webp")
    # Reviewed reference art does not publish metadata, qualify a variant or
    # turn a declaration into a physical copy/known quantity.
    from pokemon_hunter.beta.effective_collection import project

    declared = next(r for r in project(b2["actor"])["cards"] if r["number"] == "32")
    assert declared["present"] and declared["declared"]
    assert declared["printing_ids"] == declared["exact_printing_owned_ids"] == []
    assert declared["identity_status"] == "card-known-variant-unresolved"
    assert declared["recorded_copy_count"] == 0 and declared["established_total_quantity"] is None
    assert art.reference_images(b2["member"]) == []
    assert inv.export_data(b2["actor"]) == before
    # Even an empty selected collection must not revive older physical imports.
    select_marks(b2, {})
    assert art.owned_cards(b2["actor"]) == []
