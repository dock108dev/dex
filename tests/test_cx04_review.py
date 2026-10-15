"""Independent adversarial evidence, using disposable engineering roots."""

import copy
import json
import sqlite3
from unittest.mock import patch
from urllib.parse import urlsplit

import pytest
from django.core.exceptions import PermissionDenied
from test_b1 import env as env
from test_b2 import b2 as b2
from test_b3 import action, upload
from test_b3 import b3 as b3
from test_b4 import b4 as b4
from test_collection_goals import create
from test_cx03_review import find
from test_effective_collection import add, apply, select
from test_effective_collection import cx as cx
from test_migration import snapshot as snapshot
from test_sealed_catalog import e1 as e1

from pokemon_hunter.beta import card_groups as groups
from pokemon_hunter.beta import collection as inv
from pokemon_hunter.beta import effective_collection, owned_artwork, scans, store


def dump(root):
    with sqlite3.connect(root / "inventory.db") as db:
        return list(db.iterdump())


def test_review_same_account_forged_artwork_overlay_rejected(cx):
    select(cx, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}})
    forged = copy.deepcopy(effective_collection.project(cx["actor"]))
    forged["cards"][0]["present"] = not forged["cards"][0]["present"]
    before = dump(cx["root"])
    with pytest.raises((ValueError, inv.Conflict)):
        owned_artwork.owned_cards(cx["actor"], effective=forged)
    assert dump(cx["root"]) == before


def test_review_same_account_stale_artwork_overlay_rejected(cx):
    old = effective_collection.project(cx["actor"])
    add(cx)
    before = dump(cx["root"])
    with pytest.raises((ValueError, inv.Conflict)):
        owned_artwork.owned_cards(cx["actor"], effective=old)
    assert dump(cx["root"]) == before


def test_review_overlay_cannot_import_forged_catalog_or_copies(cx):
    current = effective_collection.project(cx["actor"])
    catalog = inv.catalog(cx["actor"], include_archived=True)
    active = inv.copies(cx["actor"])
    forged_catalog = copy.deepcopy(catalog)
    forged_catalog[0]["collector_number"] = "PRIVATE_SENTINEL"
    forged_copies = copy.deepcopy(active)
    forged_copies[0]["notes"] = "PRIVATE_SENTINEL"
    for kwargs in ({"catalog": forged_catalog}, {"active": forged_copies}):
        with pytest.raises((ValueError, inv.Conflict)):
            owned_artwork.owned_cards(cx["actor"], effective=current, **kwargs)


def test_review_artwork_foreign_principal_revocation_and_account_switch(cx):
    owner = effective_collection.project(cx["actor"])
    expected = owned_artwork.owned_cards(cx["actor"])
    for _ in range(3):
        assert owned_artwork.owned_cards(cx["member"]) == []
        assert owned_artwork.owned_cards(cx["actor"]) == expected
    with pytest.raises((ValueError, PermissionDenied)):
        owned_artwork.owned_cards(cx["member"], effective=owner)
    forged = store.Principal(cx["member"].subject, cx["actor"].user_id, "owner")
    with pytest.raises(PermissionDenied):
        owned_artwork.owned_cards(forged, effective=owner)
    cx["accounts"].revoke(cx["second"])
    with pytest.raises(PermissionDenied):
        owned_artwork.owned_cards(cx["member"])


def test_review_staging_and_guest_no_private_image_refs(cx, monkeypatch):
    from django.conf import settings

    monkeypatch.setattr(settings, "STAGING", True, raising=False)
    assert owned_artwork.owned_cards(cx["actor"]) == []
    guest = cx["client"]()
    data = guest.get("/api/public/card-groups/").json()
    text = json.dumps(data)
    for forbidden in ("assets.tcgdex.net", "/scan-photos/", "source_ids", "copy_id", "operation_id"):
        assert forbidden not in text
    assert guest.get("/api/card-groups/").status_code in {302, 403}


def confirmed_photo(b3):
    job = upload(b3)
    assert scans.process_one()
    response = action(b3, job, "confirm", {"printing_id": b3["catalog"][0]["id"]})
    assert response.status_code == 200, response.content
    return job, response.json()["copy_id"]


def test_review_photo_byte_access_foreign_guest_remove_undo_and_cleanup(b3):
    job, copy_id = confirmed_photo(b3)
    route = "/scan-photos/" + job["photos"][0] + "/"
    photo = b3["a"].get(route)
    assert photo.status_code == 200 and photo["Content-Type"] == "image/jpeg"
    assert "no-store" in photo["Cache-Control"]
    assert b3["b"].get(route).status_code == 404
    assert b3["client"]().get(route).status_code in {302, 403}
    current = inv.one(b3["actor"], "copy", copy_id)
    removal = apply(b3["actor"], "remove", {"id": copy_id, "revision": current["revision"]})
    assert b3["a"].get(route).status_code == 404
    inv.undo(b3["actor"], removal["id"])
    assert b3["a"].get(route).content == photo.content
    current = inv.one(b3["actor"], "copy", copy_id)
    removal = apply(b3["actor"], "remove", {"id": copy_id, "revision": current["revision"]})
    scans.cleanup()
    inv.undo(b3["actor"], removal["id"])
    assert b3["a"].get(route).status_code == 404
    assert inv.one(b3["actor"], "copy", copy_id)["state"] == "active"


def test_review_photo_undo_deletes_bytes_and_retained_history_never_restores(b3):
    job, copy_id = confirmed_photo(b3)
    route = "/scan-photos/" + job["photos"][0] + "/"
    assert action(b3, job, "undo").status_code == 200
    assert b3["a"].get(route).status_code == 404
    assert not store.rows("SELECT * FROM owned_copies WHERE id=%s", [copy_id])
    assert store.rows(
        "SELECT id FROM collection_operations WHERE id=%s",
        [scans.job(b3["actor"], job["id"])["operation_id"]],
    )
    assert not store.rows("SELECT id FROM scan_photos WHERE job_id=%s", [job["id"]])


def test_review_unconfirmed_photo_expiry_before_cleanup(b3):
    job = upload(b3)
    route = "/scan-photos/" + job["photos"][0] + "/"
    assert b3["a"].get(route).status_code == 200
    inv.execute("UPDATE scan_jobs SET created=0 WHERE id=%s", [job["id"]])
    assert b3["a"].get(route).status_code == 404
    assert store.rows("SELECT id FROM scan_photos WHERE job_id=%s", [job["id"]])
    scans.cleanup()
    assert not store.rows("SELECT id FROM scan_photos WHERE job_id=%s", [job["id"]])


def test_review_photo_revocation_immediately_blocks_bytes(b3):
    job = upload(b3, client=b3["b"])
    route = "/scan-photos/" + job["photos"][0] + "/"
    assert b3["b"].get(route).status_code == 200
    b3["accounts"].revoke(b3["second"])
    assert b3["b"].get(route).status_code in {302, 403}
    scans.cleanup()
    assert not store.rows("SELECT id FROM scan_photos WHERE job_id=%s", [job["id"]])


def test_review_artwork_reads_preserve_all_tables_and_make_no_provider_calls(cx):
    _, source = select(cx, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}})
    frozen_goal = create(cx, source)
    copy_row = inv.copies(cx["actor"])[0]
    apply(
        cx["actor"],
        "edit",
        {
            "id": copy_row["id"],
            "revision": copy_row["revision"],
            "attributes": {
                "purchase_amount": "12.34",
                "purchase_currency": "USD",
                "purchase_date": "2026-01-01",
            },
        },
    )
    before = dump(cx["root"])
    expected = owned_artwork.owned_cards(cx["actor"])
    current = find(cx)
    with (
        patch("requests.sessions.Session.request", side_effect=AssertionError("artwork network call")),
        patch("httpx.post", side_effect=AssertionError("recognition attempt")),
        patch.object(scans, "process_one", side_effect=AssertionError("recognition work")),
    ):
        for _ in range(3):
            assert owned_artwork.owned_cards(cx["actor"]) == expected
            assert cx["a"].get(current["url"]).status_code == 200
            assert cx["a"].get("/api/collection/").status_code == 200
    assert dump(cx["root"]) == before
    assert inv.goals(cx["actor"], goal_id=frozen_goal["id"])[0]["definition"] == frozen_goal["definition"]


def test_review_remote_reference_urls_have_only_public_identity(cx):
    select(cx, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}})
    for row in owned_artwork.reference_images(cx["actor"]):
        url = urlsplit(row["image_url"])
        assert url.scheme == "https" and url.netloc == "assets.tcgdex.net"
        assert not url.query and not url.fragment and not url.username and not url.password
        assert url.path == "/en/base/base4/44/low.webp"
        assert cx["actor"].user_id not in row["image_url"]


def test_review_legacy_reference_adapter_cannot_relabel_other_game_as_pokemon(cx):
    select(cx, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}})
    game_id = cx["by_legacy"]["a"]["game_id"]
    inv.execute("UPDATE games SET game_key='review-other-game' WHERE id=%s", [game_id])
    assert owned_artwork.reference_images(cx["actor"]) == []


def test_review_parity_image_assembly_never_mutates_authoritative_projection(cx):
    from pokemon_hunter.beta import parity

    select(cx, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}})
    real_project = effective_collection.project
    projections = []

    def capture(*args, **kwargs):
        projected = real_project(*args, **kwargs)
        projections.append((projected, copy.deepcopy(projected)))
        return projected

    with patch.object(effective_collection, "project", side_effect=capture):
        data = parity.projection(cx["actor"])
    assert data["pokedex"]["2"]["artwork"]["role"] == "species_artwork"
    assert projections
    for returned, initial in projections:
        assert returned == initial


def test_review_image_availability_cannot_change_ownership_totals_or_destination(cx):
    from pokemon_hunter.beta import image_mappings

    select(cx, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}})
    current = find(cx)
    before = effective_collection.project(cx["actor"])
    detail = groups.detail(cx["actor"], current["id"])
    mapped = image_mappings.card_group_reference
    for available in (None, "https://assets.tcgdex.net/en/base/base4/44/low.webp"):

        def controlled_reference(*args, **kwargs):
            descriptor = mapped(*args, **kwargs)
            return dict(
                descriptor, image_url=available, availability="reference" if available else "unavailable"
            )

        with patch.object(image_mappings, "card_group_reference", side_effect=controlled_reference):
            owned_artwork.owned_cards(cx["actor"])
            assert effective_collection.project(cx["actor"]) == before
            # Image descriptors are optional additions; collection truth remains identical.
            reloaded = groups.detail(cx["actor"], current["id"])
            for field in (
                "present",
                "established_total_quantity",
                "recorded_copy_count",
                "exact_variant_count",
                "url",
            ):
                assert reloaded["group"][field] == detail["group"][field]
            assert reloaded["selected_child"] is None


def test_review_private_photo_descriptor_uses_authoritative_association_only(b3):
    from pokemon_hunter.beta.image_bindings import private_copy_photos

    job, copy_id = confirmed_photo(b3)
    existing = next(c for c in inv.copies(b3["actor"]) if c["id"] != copy_id)
    inv.execute(
        "UPDATE owned_copies SET provisional_identity=%s WHERE id=%s",
        [
            json.dumps(
                {"scan_job": job["id"], "image_url": "https://invalid/private", "photo_path": "/tmp/private"}
            ),
            existing["id"],
        ],
    )
    before = dump(b3["root"])
    descriptors = private_copy_photos(b3["actor"], [copy_id, existing["id"]])
    assert len(descriptors[copy_id]) == 1
    assert descriptors[existing["id"]] == []
    image = descriptors[copy_id][0]
    assert image["role"] == "private_copy_photo"
    assert image["image_url"] == "/scan-photos/" + job["photos"][0] + "/"
    assert copy_id in json.dumps(image["bound_identity"])
    assert private_copy_photos(b3["member"], [copy_id]).get(copy_id, []) == []
    assert dump(b3["root"]) == before


def test_review_private_photo_descriptors_respect_removal_cleanup_and_missing_bytes(b3):
    from pokemon_hunter.beta.image_bindings import private_copy_photos

    job, copy_id = confirmed_photo(b3)
    assert private_copy_photos(b3["actor"], [copy_id])[copy_id]
    copy_row = inv.one(b3["actor"], "copy", copy_id)
    removal = apply(b3["actor"], "remove", {"id": copy_id, "revision": copy_row["revision"]})
    assert private_copy_photos(b3["actor"], [copy_id]).get(copy_id, []) == []
    inv.undo(b3["actor"], removal["id"])
    assert private_copy_photos(b3["actor"], [copy_id])[copy_id]
    inv.execute("DELETE FROM scan_photos WHERE job_id=%s", [job["id"]])
    assert private_copy_photos(b3["actor"], [copy_id])[copy_id] == []
    copy_row = inv.one(b3["actor"], "copy", copy_id)
    assert json.loads(copy_row["provisional_identity"])["scan_job"] == job["id"]


def test_review_photo_descriptor_revocation_stale_copy_and_empty_bytes(b3):
    from pokemon_hunter.beta.image_bindings import private_copy_photos

    job, copy_id = confirmed_photo(b3)
    route = "/scan-photos/" + job["photos"][0] + "/"
    assert private_copy_photos(b3["actor"], [copy_id])[copy_id]
    inv.execute("UPDATE scan_jobs SET user_id=%s WHERE id=%s", [b3["member"].user_id, job["id"]])
    assert private_copy_photos(b3["actor"], [copy_id])[copy_id] == []
    assert b3["a"].get(route).status_code == 404
    inv.execute("UPDATE scan_jobs SET user_id=%s WHERE id=%s", [b3["actor"].user_id, job["id"]])
    inv.execute("UPDATE scan_photos SET content=%s WHERE job_id=%s", [b"", job["id"]])
    assert private_copy_photos(b3["actor"], [copy_id])[copy_id] == []
    assert b3["a"].get(route).status_code == 404
    b3["accounts"].revoke(b3["second"])
    with pytest.raises(PermissionDenied):
        private_copy_photos(b3["member"], [copy_id])


def test_review_photo_render_reads_never_consume_recognition_attempts(b3):
    from pokemon_hunter.beta.image_bindings import private_copy_photos

    job, copy_id = confirmed_photo(b3)
    before = dump(b3["root"])
    with (
        patch.object(scans, "process_one", side_effect=AssertionError("provider invocation")),
        patch("httpx.post", side_effect=AssertionError("provider invocation")),
        patch("requests.sessions.Session.request", side_effect=AssertionError("remote artwork invocation")),
    ):
        for _ in range(3):
            descriptor = private_copy_photos(b3["actor"], [copy_id])[copy_id][0]
            assert b3["a"].get(descriptor["image_url"]).status_code == 200
    assert dump(b3["root"]) == before
    assert scans.job(b3["actor"], job["id"])["attempts"] == 1


def test_review_species_mapping_never_uses_card_scan_or_owned_identity(cx):
    from pokemon_hunter.beta import image_mappings
    from pokemon_hunter.beta.canonical_species import registry

    all_images = {number: image_mappings.species_artwork(number) for number in range(1, 252)}
    assert len(all_images) == 251
    for number, image in all_images.items():
        assert image["role"] == "species_artwork" and image["precision"] == "species"
        assert image["bound_identity"] == {"species_id": registry()[number]["id"], "pokemon_dex": number}
        parsed = urlsplit(image["image_url"])
        assert parsed.netloc == "raw.githubusercontent.com" and not parsed.query and not parsed.fragment
        assert parsed.path.endswith(f"/official-artwork/{number}.png")
    select(cx, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}})
    add(cx)
    assert {number: image_mappings.species_artwork(number) for number in range(1, 252)} == all_images


@pytest.mark.parametrize("number", [0, 252, None, "2", True, -1])
def test_review_species_outside_reviewed_scope_has_neutral_fallback(number):
    from pokemon_hunter.beta import image_mappings

    result = image_mappings.species_artwork(number)
    assert result["role"] == "species_artwork"
    assert result["availability"] == "unavailable" and result["image_url"] is None
    assert result["width"] == result["height"] > 0


@pytest.mark.parametrize("fault", ["missing", "wrong_species"])
def test_review_species_mapping_gap_never_falls_back_to_card_or_copy(cx, monkeypatch, fault):
    from pokemon_hunter.beta import image_mappings, parity

    mapping = copy.deepcopy(image_mappings._reviewed())
    if fault == "missing":
        mapping["species"] = [row for row in mapping["species"] if row["dex"] != 2]
    else:
        next(row for row in mapping["species"] if row["dex"] == 2)["species_id"] = "ndex:0003"
    monkeypatch.setattr(image_mappings, "_reviewed", lambda: mapping)
    projected = parity.projection(cx["actor"])
    artwork = projected["pokedex"]["2"]["artwork"]
    assert artwork["role"] == "species_artwork" and artwork["image_url"] is None
    assert artwork["availability"] == "unavailable"
    assert artwork["bound_identity"]["pokemon_dex"] == 2
    assert projected["pokedex"]["2"]["reference_images"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("name", "Dark Ivysaur"),
        ("collector_number", "044"),
        ("collector_number", "44a"),
        ("language", "ja"),
        ("pokemon_dex", 1),
        ("set_name", "Base Set"),
        ("game_id", "forged-pokemon-game"),
        ("id", "dg1-forged"),
    ],
)
def test_review_group_mapping_rejects_forged_or_literal_identity_changes(cx, field, value):
    from pokemon_hunter.beta import image_mappings

    catalog = inv.catalog(cx["actor"], include_archived=True)
    group = find(cx)
    game_ids = {row["id"] for row in store.rows("SELECT id FROM games WHERE game_key='pokemon'")}
    good = image_mappings.card_group_reference(group, catalog, pokemon_game_ids=game_ids)
    assert good["image_url"] == "https://assets.tcgdex.net/en/base/base4/44/low.webp"
    forged = dict(group, **{field: value})
    image = image_mappings.card_group_reference(forged, catalog, pokemon_game_ids=game_ids)
    assert image["image_url"] is None and image["availability"] == "unavailable"
    assert groups.detail(cx["actor"], group["id"])["selected_child"] is None


def test_review_group_ref_exact_child_and_archive_are_distinct(cx):
    group = find(cx)
    child_id = cx["by_legacy"]["a"]["id"]
    ordinary = groups.detail(cx["actor"], group["id"])
    assert ordinary["selected_child"] is None and ordinary["selected_child_image"] is None
    assert ordinary["group"]["reference_image"]["precision"] == "card_group"
    selected = groups.detail(cx["actor"], group["id"], selected_child=child_id)
    exact = selected["selected_child_image"]
    assert exact["role"] == "exact_child_artwork" and exact["precision"] == "exact_child"
    assert exact["image_url"] is None and exact["availability"] == "unavailable"
    assert exact["bound_identity"]["printing_id"] == child_id
    select(cx, {2: {"Base Set 2": "✓ Ivysaur #44 (Uncommon)"}})
    inv.execute("UPDATE printings SET publication_state='archived' WHERE id=%s", [child_id])
    archived = groups.detail(cx["actor"], group["id"], selected_child=child_id)
    assert archived["selected_child"]["id"] == child_id
    assert archived["selected_child_image"]["image_url"] is None
    assert archived["selected_child_image"]["reason"] == "archived_child"
    assert archived["group"]["reference_image"] == selected["group"]["reference_image"]


def test_review_staging_cannot_gain_remote_group_or_child_references(cx, monkeypatch):
    from django.conf import settings

    from pokemon_hunter.beta.image_bindings import catalog_images

    current = find(cx)
    # Admit controlled engineering metadata by the existing staging provider policy.
    for row in inv.catalog(cx["actor"], include_archived=True):
        provenance = json.loads(row["provenance"])
        provenance["provider"] = "dex-synthetic"
        inv.execute("UPDATE printings SET provenance=%s WHERE id=%s", [json.dumps(provenance), row["id"]])
    monkeypatch.setattr(settings, "STAGING", True, raising=False)
    assert catalog_images(cx["actor"], inv.catalog(cx["actor"])) == {}
    detail = groups.detail(cx["actor"], current["id"], selected_child=cx["by_legacy"]["a"]["id"])
    text = json.dumps(detail)
    assert "assets.tcgdex.net" not in text and "raw.githubusercontent.com" not in text
    assert detail["selected_child"]["id"] == cx["by_legacy"]["a"]["id"]


def test_review_private_image_csp_has_one_bounded_directive_and_no_store(cx):
    response = cx["a"].get("/")
    assert response.status_code == 200
    directives = [entry.strip().split() for entry in response["Content-Security-Policy"].split(";")]
    image_directives = [parts for parts in directives if parts and parts[0] == "img-src"]
    assert len(image_directives) == 1
    assert set(image_directives[0][1:]) == {
        "'self'",
        "https://assets.tcgdex.net",
        "https://raw.githubusercontent.com",
    }
    assert "no-store" in response["Cache-Control"]
    guest = cx["client"]().get("/")
    assert "assets.tcgdex.net" not in guest["Content-Security-Policy"]
    assert "raw.githubusercontent.com" not in guest["Content-Security-Policy"]
