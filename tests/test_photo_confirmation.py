"""Photo confirmation contracts over synthetic state and controlled processes."""

import pytest
from photo_batch_helpers import BOX, cropped, photos, selected
from test_bulk_onboarding import b2, b3, b4, bulk, cx, e1, env, snapshot
from test_effective_collection import apply

from pokemon_hunter.beta import collection as inv
from pokemon_hunter.beta import collection_drafts as drafts
from pokemon_hunter.beta import photo_batches as batches

__all__ = ["b2", "b3", "b4", "bulk", "cx", "e1", "env", "snapshot", "photos"]


def photo_confirm(cx, batch):
    draft = batches.handoff(cx["actor"], batch["id"], batch["revision"], True, [])["draft"]
    preview = drafts.review(cx["actor"], draft["id"], draft["revision"])["operation"]
    assert not preview["plan"]["errors"]
    return drafts.confirm(cx["actor"], draft["id"], draft["revision"])


def test_photo_skips_existing_and_reports_edition_update_with_undo(photos):
    cx = photos
    a = cx["actor"]
    apply(a, "add", dict(printing_id=cx["by_legacy"]["c"]["id"], duplicate_policy="allow"))
    before = inv.copies(a)
    b = selected(cx)
    c = b["crops"][0]
    b = batches.select_crop(
        a,
        b["id"],
        b["revision"],
        c["id"],
        dict(printing_id=cx["by_legacy"]["c"]["id"], first_edition_selected=True),
        True,
        False,
        "different",
    )
    done = photo_confirm(cx, b)
    assert len(inv.copies(a)) == len(before)
    assert not done["plan"]["creates"]
    report = done["plan"]["photo_report"]
    assert report[0]["status"] == "edition_updated"
    assert report[0]["first_edition"] is True
    assert (
        next(c for c in inv.copies(a) if c["printing_id"] == cx["by_legacy"]["c"]["id"])[
            "first_edition_selected"
        ]
        == 1
    )
    inv.undo(a, done["id"])
    assert [c["first_edition_selected"] for c in inv.copies(a)] == [
        c["first_edition_selected"] for c in before
    ]


def test_photo_new_repeated_card_prefers_first_edition_and_adds_once(photos):
    cx = photos
    b = selected(cx, n=2)
    c = b["crops"][-1]
    b = batches.select_crop(
        cx["actor"],
        b["id"],
        b["revision"],
        c["id"],
        dict(printing_id=cx["by_legacy"]["c"]["id"], first_edition_selected=True),
        True,
        False,
        "different",
    )
    before = len(inv.copies(cx["actor"]))
    done = photo_confirm(cx, b)
    assert len(inv.copies(cx["actor"])) == before + 1
    assert sorted(r["status"] for r in done["plan"]["photo_report"]) == ["added", "duplicate"]
    assert done["plan"]["creates"][0]["row"]["first_edition_selected"] == 1


def test_photo_all_owned_noop_report_and_ambiguous_edition_not_guessed(photos):
    cx = photos
    for _ in range(2):
        apply(cx["actor"], "add", dict(printing_id=cx["by_legacy"]["c"]["id"], duplicate_policy="allow"))
    before = inv.copies(cx["actor"])
    b = selected(cx)
    c = b["crops"][0]
    b = batches.select_crop(
        cx["actor"],
        b["id"],
        b["revision"],
        c["id"],
        dict(printing_id=cx["by_legacy"]["c"]["id"], first_edition_selected=True),
        True,
        False,
        "different",
    )
    done = photo_confirm(cx, b)
    assert done["plan"]["photo_report"][0]["status"] == "needs_review"
    assert not done["plan"]["creates"] and not done["plan"]["updates"]
    assert inv.copies(cx["actor"]) == before


def test_photo_existing_first_edition_is_kept_without_adding(photos):
    cx = photos
    a = cx["actor"]
    added = apply(a, "add", dict(printing_id=cx["by_legacy"]["c"]["id"], duplicate_policy="allow"))
    copy = added["changes"][0]["after"]
    apply(a, "edition", dict(id=copy["id"], revision=copy["revision"], selection="first_edition"))
    before = inv.copies(a)
    done = photo_confirm(cx, selected(cx))
    assert done["plan"]["photo_report"][0]["status"] == "already_owned"
    assert done["plan"]["photo_report"][0]["first_edition"] is True
    assert not done["plan"]["creates"] and not done["plan"]["updates"]
    assert inv.copies(a) == before


def test_photo_duplicate_policy_rechecked_after_collection_changes(photos):
    cx = photos
    a = cx["actor"]
    b = selected(cx)
    d = batches.handoff(a, b["id"], b["revision"], True, [])["draft"]
    drafts.review(a, d["id"], d["revision"])
    apply(a, "add", dict(printing_id=cx["by_legacy"]["c"]["id"], duplicate_policy="allow"))
    with pytest.raises(inv.Conflict):
        drafts.confirm(a, d["id"], d["revision"])
    op = drafts.review(a, d["id"], d["revision"])["operation"]
    assert not op["plan"]["creates"]
    assert op["plan"]["photo_report"][0]["status"] == "already_owned"


def test_photo_match_normalizes_numbers_language_and_unknown_catalog_variants():
    from pokemon_hunter.beta.photo_matching import matches

    card = dict(
        id="jungle-5",
        name="Kangaskhan",
        collector_number="5",
        language="en",
        set_name="Jungle",
        edition=None,
        finish=None,
        variant=None,
    )
    clue = dict(
        status="readable",
        name="Kangaskhan",
        number="5/64",
        language="English",
        set_name="Jungle",
        edition="Unlimited",
        finish="Holofoil",
        variant=None,
    )
    assert matches(clue, [card]) == [card]
    assert not matches(clue, [{**card, "finish": "nonholo"}])
    assert not matches(clue, [{**card, "collector_number": "21"}])
    assert not matches({**clue, "status": "unreadable"}, [card])


def test_stored_photo_evidence_to_confirmation_and_report(photos):
    cx = photos
    a = cx["actor"]
    b = cropped(cx)
    p = cx["by_legacy"]["c"]
    clue = dict(
        status="readable",
        name=p["name"],
        number=p["collector_number"],
        set_name=p["set_name"],
        language=p["language"],
        edition=None,
        finish=None,
        variant=None,
        reason=None,
        box={**BOX, "issues": ["glare"]},
    )
    before = inv.copies(a)
    # Existing evidence remains reviewable without any model or provider adapter.
    import json

    inv.execute(
        "UPDATE scan_batch_crops SET proposal=%s WHERE id=%s", [json.dumps(clue), b["crops"][0]["id"]]
    )
    b = batches.detail(a, b["id"])
    assert inv.copies(a) == before
    c = b["crops"][0]
    assert c["proposal"]["name"] == p["name"] and c["candidates"]
    choices = [dict(id=c["id"], included=True, row=dict(printing_id=p["id"]))]
    done = batches.confirm_cards(a, b["id"], b["revision"], choices)
    assert done["state"] == "confirmed" and done["plan"]["photo_report"][0]["status"] == "added"
    assert len(inv.copies(a)) == len(before) + 1
    assert batches.confirm_cards(a, b["id"], b["revision"], choices) == done
    inv.undo(a, done["id"])
    assert len(inv.copies(a)) == len(before)


def test_direct_confirmation_rejects_missing_and_duplicate_choices(photos):
    cx = photos
    b = selected(cx, n=2)
    c = b["crops"][0]
    choice = dict(id=c["id"], included=True, row=dict(printing_id=cx["by_legacy"]["c"]["id"]))
    before = inv.copies(cx["actor"])
    for choices in ([choice], [choice, choice]):
        with pytest.raises(ValueError, match="exactly once"):
            batches.confirm_cards(cx["actor"], b["id"], b["revision"], choices)
    assert inv.copies(cx["actor"]) == before
