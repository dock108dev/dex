"""literal image roles on authentic retained metadata, without networking."""

import copy
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

import pytest

from pokemon_hunter.beta import canonical_species, card_groups
from pokemon_hunter.beta import image_mappings as images

ROOT = Path(__file__).parents[1]


def catalog_card(set_name="Base Set 2", name="Ivysaur", number="44"):
    mapped = next(
        row
        for row in images._reviewed()["cards"]
        if (row["set_name"], row["name"], row["collector_number"]) == (set_name, name, number)
    )
    return dict(
        id="retained-" + mapped["external_id"],
        game_id="reviewed-pokemon-game",
        set_id="reviewed-set-" + set_name,
        set_name=set_name,
        language="en",
        collector_number=number,
        name=name,
        unresolved_fields=[],
        attributes=dict(pokemon_dex=mapped["pokemon_dex"], supertype="Pokémon"),
    )


def grouped(rows):
    return card_groups.build_groups(rows, pokemon_game_ids={"reviewed-pokemon-game"})["groups"][0]


def reference(group, rows):
    return images.card_group_reference(group, rows, pokemon_game_ids={"reviewed-pokemon-game"})


def test_all_251_canonical_species_use_separate_pinned_artwork_without_possession():
    registry_hash = hashlib.sha256(canonical_species.REGISTRY.read_bytes()).hexdigest()
    for dex in range(1, 252):
        row = images.species_artwork(dex)
        assert row["role"] == "species_artwork"
        assert row["bound_identity"] == dict(species_id=canonical_species.require(dex), pokemon_dex=dex)
        assert row["precision"] == "species"
        assert row["availability"] == "reference"
        assert row["alt"] == canonical_species.registry()[dex]["name"]
        assert row["image_url"].endswith(f"/official-artwork/{dex}.png")
        assert row["width"] == row["height"] == 475
        assert "tcgdex" not in row["image_url"]
    assert hashlib.sha256(canonical_species.REGISTRY.read_bytes()).hexdigest() == registry_hash
    assert registry_hash == canonical_species.REGISTRY_SHA256


@pytest.mark.parametrize("dex", [0, 252, True, "2", None])
def test_unsupported_species_never_substitutes_card_artwork(dex):
    row = images.species_artwork(dex)
    assert row["availability"] == "unavailable" and row["image_url"] is None
    assert row["role"] == "species_artwork"


@pytest.mark.parametrize("damage", ["missing", "wrong-name", "wrong-identity"])
def test_missing_or_incorrect_species_mapping_has_neutral_fallback(damage):
    data = copy.deepcopy(images._reviewed())
    row = next(row for row in data["species"] if row["dex"] == 2)
    if damage == "missing":
        data["species"].remove(row)
    elif damage == "wrong-name":
        row["name"] = "Mew"
    else:
        row["species_id"] = "ndex:0151"
    with patch.object(images, "_reviewed", return_value=data):
        result = images.species_artwork(2)
    assert result["bound_identity"]["species_id"] == "ndex:0002"
    assert result["image_url"] is None and result["availability"] == "unavailable"


def test_ivysaur_set_numbers_and_mew_promo_have_independent_literal_references():
    cases = [
        ("Base Set", "Ivysaur", "30", "base1"),
        ("Base Set 2", "Ivysaur", "44", "base4"),
        ("Wizards Black Star Promos", "Mew", "8", "basep"),
    ]
    ids = []
    for set_name, name, number, key in cases:
        card = catalog_card(set_name, name, number)
        group = grouped([card])
        ids.append(group["id"])
        image = reference(group, [card])
        assert image["role"] == "card_group_reference" and image["precision"] == "card_group"
        assert image["image_url"] == f"https://assets.tcgdex.net/en/base/{key}/{number}/low.webp"
        assert image["bound_identity"]["id"] == group["id"]
        assert (image["width"], image["height"]) == (245, 337)
    assert len(set(ids)) == 3


@pytest.mark.parametrize(
    "set_name,name,number",
    [
        ("Team Rocket", "Dark Charizard", "4"),
        ("Neo Destiny", "Light Ninetales", "50"),
        ("Gym Heroes", "Brock's Rhydon", "2"),
    ],
)
def test_named_dark_light_card_names_remain_literal_species_independent(set_name, name, number):
    card = catalog_card(set_name, name, number)
    image = reference(grouped([card]), [card])
    assert image["image_url"]
    assert image["bound_identity"]["name"] == name
    species = images.species_artwork(card["attributes"]["pokemon_dex"])
    assert species["alt"] == canonical_species.registry()[card["attributes"]["pokemon_dex"]]["name"]


@pytest.mark.parametrize(
    "change",
    [
        dict(language="ja"),
        dict(collector_number="044"),
        dict(collector_number="44a"),
        dict(name="IVYSAUR"),
        dict(game_id="other-game"),
        dict(unresolved_fields=["number"]),
    ],
)
def test_unsupported_literal_language_number_game_name_and_unresolved_identity(change):
    card = catalog_card()
    group = grouped([card])
    card.update(change)
    assert reference(group, [card])["image_url"] is None


def test_contradictory_catalog_slot_and_forged_group_identity_do_not_construct_scan():
    card = catalog_card()
    group = grouped([card])
    conflict = copy.deepcopy(card)
    conflict.update(id="conflicting-card", name="Bulbasaur")
    assert reference(group, [card, conflict])["availability"] == "unavailable"
    group["name"] = "Bulbasaur"
    assert reference(group, [card])["image_url"] is None


def test_group_reference_does_not_promote_first_edition_reverse_or_archived_sibling():
    card = catalog_card()
    second = copy.deepcopy(card)
    second.update(id="independent-reverse-child", edition="first", finish="reverse")
    group = grouped([card, second])
    for child, reason in [
        (None, "no_selected_child"),
        ({"id": card["id"], "available": True}, "independent_asset_identity_missing"),
        ({"id": second["id"], "available": True}, "independent_asset_identity_missing"),
        ({"id": second["id"], "available": False}, "archived_child"),
        ({"id": "foreign-child", "available": True}, "unsupported_or_conflicting_child_identity"),
    ]:
        image = images.exact_child_artwork(group, child, [card, second], pokemon_game_ids={card["game_id"]})
        assert image["role"] == "exact_child_artwork" and image["image_url"] is None
        assert image["reason"] == reason
    assert reference(group, [card, second])["image_url"]


def test_ownership_counts_availability_and_child_order_do_not_change_mapping_or_destination():
    card = catalog_card()
    second = copy.deepcopy(card)
    second["id"] = "sibling"
    group = grouped([card, second])
    before = reference(group, [card, second])
    group.update(
        present=True,
        established_total_quantity=7,
        recorded_copy_count=2,
        exact_variant_count=1,
        catalog_available=False,
    )
    assert reference(group, [second, card]) == before
    assert grouped([second, card])["url"] == group["url"]
    assert "present" not in before and "recorded_copy_count" not in before


def test_all_required_sets_reviewed_metadata_and_outbound_references_are_bounded():
    data = images._reviewed()
    assert len(data["species"]) == 251 and len(data["cards"]) == 21516
    assert {row["set_name"] for row in data["cards"]} >= {
        "Base Set",
        "Jungle",
        "Fossil",
        "Base Set 2",
        "Team Rocket",
        "Wizards Black Star Promos",
        "Gym Heroes",
        "Gym Challenge",
        "Neo Genesis",
        "Neo Discovery",
        "Neo Revelation",
        "Neo Destiny",
        "Plasma Storm",
        "Mysterious Treasures",
        "Call of Legends",
        "Diamond & Pearl",
        "Dark Explorers",
        "EX Trainer Kit 2 — Minun",
    }
    for row in data["species"] + data["cards"]:
        url = urlsplit(row["image_url"])
        assert url.scheme == "https" and url.hostname in {"assets.tcgdex.net", "raw.githubusercontent.com"}
        assert not url.query and not url.fragment and not url.username
    assert data["exact_children"] == []


def test_mapping_file_is_fingerprinted_and_drift_fails_closed(tmp_path, monkeypatch):
    changed = tmp_path / "mapping.json"
    changed.write_text("{}")
    images._reviewed.cache_clear()
    with monkeypatch.context() as scoped:
        scoped.setattr(images, "MAPPING_FILE", changed)
        with pytest.raises(ValueError, match="mapping drift"):
            images.species_artwork(2)
    images._reviewed.cache_clear()


def test_every_reviewed_card_mapping_matches_pinned_retained_metadata():
    sources = list(sorted((ROOT / "config/catalog-imports/staging-ten").glob("*.json")))
    sources += [ROOT / f"config/catalog-pipeline/d6-20261005/gym{n}.json" for n in (1, 2)]
    expected = set()
    for path in sources:
        package = json.loads(path.read_bytes())
        for card in package.get("cards", []):
            attributes = card.get("metadata", {})
            dex = attributes.get("pokemon_dex") if attributes.get("supertype") == "Pokémon" else None
            expected.add((package["set_name"], package["language"], card["number"], card["name"], dex))
    actual = {
        (row["set_name"], row["language"], row["collector_number"], row["name"], row["pokemon_dex"])
        for row in images._reviewed()["cards"]
        if row["set_name"] not in images._reviewed()["expanded_set_names"]
    }
    assert expected <= actual
    expanded = {
        (row["set_name"], row["language"], row["collector_number"], row["name"], row["pokemon_dex"])
        for row in images._reviewed()["cards"]
        if row["set_name"] in images._reviewed()["expanded_set_names"]
    }
    for code in ("bw8", "dp2", "col1", "dp1"):
        package = json.loads((ROOT / f"tests/fixtures/retained-catalog/{code}.json").read_bytes())
        for card in package["cards"]:
            metadata = card["metadata"]
            dex = metadata.get("pokemon_dex") if metadata.get("supertype") == "Pokémon" else None
            assert (package["set_name"], package["language"], card["number"], card["name"], dex) in expanded


@pytest.mark.parametrize(
    "set_name,name,number,series,key,dex",
    [
        ("Plasma Storm", "Articuno-EX", "25", "bw", "bw8", 144),
        ("Mysterious Treasures", "Magby", "88", "dp", "dp2", 240),
        ("Call of Legends", "Vulpix", "75", "col", "col1", 37),
        ("Diamond & Pearl", "Goldeen", "84", "dp", "dp1", 118),
        ("Dark Explorers", "Eevee", "84", "bw", "bw5", 133),
        ("Legendary Collection", "Sandslash", "62", "lc", "lc", 28),
    ],
)
def test_expanded_sets_have_literal_card_references(set_name, name, number, series, key, dex):
    card = catalog_card(set_name, name, number)
    image = reference(grouped([card]), [card])
    assert image["image_url"] == f"https://assets.tcgdex.net/en/{series}/{key}/{number}/low.webp"
    assert card["attributes"]["pokemon_dex"] == dex


@pytest.mark.parametrize(
    "damage",
    [
        dict(name="EEVEE"),
        dict(number="084"),
        dict(pokemon_dex=25),
        dict(set_name="Dark explorers"),
        dict(identity_status="conflict"),
        dict(conflicts=["identity conflict"]),
    ],
)
def test_declared_reference_rejects_conflicting_or_approximate_identity(damage):
    assertion = dict(
        id="declaration",
        set_name="Dark Explorers",
        name="Eevee",
        number="84",
        pokemon_dex=133,
        identity_status="card-known-variant-unresolved",
        conflicts=[],
    )
    assert images.declared_card_reference(assertion)["image_url"]
    assertion.update(damage)
    assert images.declared_card_reference(assertion)["image_url"] is None


def test_number_aliases_are_explicit_and_do_not_normalize_other_catalog_inputs():
    cases = [
        ("Scarlet & Violet—151", "Sandslash", "028/165", "sv03.5-028"),
        ("Detective Pikachu", "Bulbasaur", "1/18", "det1-1"),
    ]
    for set_name, name, number, external_id in cases:
        card = catalog_card(set_name, name, number)
        mapped = reference(grouped([card]), [card])
        assert mapped["image_url"]
        assert (
            next(
                row
                for row in images._reviewed()["cards"]
                if row["set_name"] == set_name and row["collector_number"] == number and row["name"] == name
            )["external_id"]
            == external_id
        )
        card["collector_number"] = number.replace("/", " / ")
        assert reference(grouped([card]), [card])["image_url"] is None


def test_known_missing_trainer_kit_scan_stays_unavailable():
    assertion = dict(
        id="declared",
        name="Vulpix",
        set_name="EX Trainer Kit 2 — Minun",
        number="7",
        pokemon_dex=37,
        identity_status="card-known-variant-unresolved",
        conflicts=[],
    )
    assert images.declared_card_reference(assertion)["image_url"] is None


@pytest.mark.parametrize("duplicates", [0, 1, 2])
def test_group_and_declaration_share_checked_literal_index(tmp_path, monkeypatch, duplicates):
    card = catalog_card()
    group = grouped([card])
    assertion = dict(
        id="synthetic-declaration",
        set_name=card["set_name"],
        name=card["name"],
        number=card["collector_number"],
        pokemon_dex=card["attributes"]["pokemon_dex"],
        identity_status="card-known-variant-unresolved",
        conflicts=[],
    )
    mapped = images._card_mapping(
        card["set_name"],
        card["name"],
        card["language"],
        card["collector_number"],
        card["attributes"]["pokemon_dex"],
    )
    # Even identical duplicates are ambiguous; a third record cannot restore one.
    path = tmp_path / "synthetic-mapping.json"
    raw = json.dumps(dict(cards=[mapped] * (duplicates + 1))).encode()
    path.write_bytes(raw)
    monkeypatch.setattr(images, "MAPPING_FILE", path)
    monkeypatch.setattr(images, "MAPPING_SHA256", hashlib.sha256(raw).hexdigest())
    images._reviewed.cache_clear()
    try:
        with patch.object(images, "_card_mapping", wraps=images._card_mapping) as policy:
            indexed = reference(group, [card])
            declared = images.declared_card_reference(assertion)
            assert policy.call_count == 2
            assert policy.call_args_list[0] == policy.call_args_list[1]
        expected = None if duplicates else mapped["image_url"]
        assert indexed["image_url"] == declared["image_url"] == expected
        # No second scan of raw rows may bypass the checked index.
        images._reviewed()["cards"] = []
        assert reference(group, [card])["image_url"] == expected
        assert images.declared_card_reference(assertion)["image_url"] == expected
    finally:
        images._reviewed.cache_clear()
