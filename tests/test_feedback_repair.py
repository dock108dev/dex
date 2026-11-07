"""The automatic Hunt with forty authored offers on its normal worker interface."""

import json
from collections import Counter
from types import SimpleNamespace

import pytest
from django.http import Http404
from test_hunter_lots import entries as entries
from test_hunter_lots import printing
from test_hunter_policy import everyday as everyday
from test_lv03_hunt import env as env
from test_lv03_hunt import offer
from test_lv05_integration import prices as prices

from pokemon_hunter.beta import discovery_lot_values
from pokemon_hunter.beta import lot_hunt as hunt


def test_forty_offers_preserve_assessments_and_expand_locally(env, prices):
    env.bin = [offer(i) for i in range(20)]
    env.auction = [offer(i, lane="auction") for i in range(20, 40)]
    for lane in (env.bin, env.auction):
        row = lane[8]
        row.update(title="37-card lot", shortDescription="Lapras Fossil mixed lot. Cards included: see list.")
        description = "Parcel information " + "a" * 1350
        row["shippingOptions"][0]["shippingCostType"] = "FIXED"
        env.details[row["itemId"]] = dict(
            row,
            description="<p>2x Charizard Base Set 4/102 English Unlimited Non Holo</p>"
            + ("<p>" + description + "</p>") * 38,
            localizedAspects=[
                dict(name="Cards Included", value="1x Blastoise Base Set 2/102 English Unlimited Non Holo")
            ],
        )
    env.details[env.auction[8]["itemId"]]["shippingOptions"] = []
    run, result = env.execute(env.start(query="Lapras"))
    counts = Counter(r["assessment_state"] for r in result["results"])
    assert counts == {"partial": 2, "unprocessed": 38}
    detailed = [r for r in result["results"] if r["assessment_state"] == "partial"]
    assert set(run.details) == {env.auction[8]["itemId"], env.bin[8]["itemId"]}
    for row in detailed:
        value = row["lot_value"]
        assert value["stated_quantity"] == 37 and value["physically_selected_quantity"] == 3
        assert value["subtotal"] == "29.00" and value["total"] is None
        assert "contents" not in value and "cards" not in value
        expanded = hunt.evidence(env.actor, "session", run.id, row["id"], row["content_revision"])
        assert expanded["evidence_version"] == row["evidence_version"]
        full = expanded["lot_value"]
        assert full["source_fields"]["title"] == "37-card lot"
        assert "Charizard" in full["source_fields"]["official_description"]
        assert "Blastoise" in full["source_fields"]["aspect_0"]
        assert {c["name"]: c["quantity"] for c in full["cards"]} == {"Charizard": 2, "Blastoise": 1}
    assert {r["value_order"]["combined"]["group"] for r in detailed} == {"partial", "unknown_cost"}
    assert len(env.calls) == 5
    assert len(json.dumps(result, separators=(",", ":")).encode()) < 120 * 1024
    row = detailed[0]

    def expand():
        return hunt.evidence(env.actor, "session", run.id, row["id"], row["content_revision"])["lot_value"]

    with pytest.raises(Http404):
        hunt.evidence(env.actor, "other-session", run.id, row["id"], row["content_revision"])
    with pytest.raises(Http404):
        hunt.evidence(SimpleNamespace(user_id="other"), "session", run.id, row["id"], row["content_revision"])
    with pytest.raises(ValueError, match="revision"):
        hunt.evidence(env.actor, "session", run.id, row["id"], row["content_revision"] - 1)
    prices.clear()
    assert expand()["subtotal"] is None
    withdrawn = hunt.status(env.actor, "session", run.id)
    assert all(r["value_order"]["combined"]["score"] is None for r in withdrawn["results"])
    hunt.stop(env.actor, "session", run.id)
    with pytest.raises(ValueError, match="stopped"):
        expand()
    assert len(env.calls) == 5


@pytest.mark.parametrize("kind", ["absent", "ambiguous", "unmatched", "identified_unpriced"])
def test_worker_distinguishes_text_and_price_gaps(env, entries, kind):
    # This authored catalog has a resolved first-edition printing as well as an
    # alternative. Neither has a reference. The customer catalog is audited separately.
    entries.extend(
        [
            dict(
                printing("lapras-first", "Lapras", number="10/62"),
                set_name="Fossil",
                edition="1st Edition",
                finish="holo",
            ),
            dict(printing("lapras-unlimited", "Lapras", number="10/62"), set_name="Fossil", finish="holo"),
        ]
    )
    source = env.bin[0]
    source.update(title="37-card mixed lot")
    line = {
        "absent": "",
        "ambiguous": "1x Lapras Fossil 10/62",
        "unmatched": "2x AuthoredUnknownCard",
        "identified_unpriced": "2x Lapras Fossil 10/62 English Unlimited Holo",
    }[kind]
    env.details[source["itemId"]] = dict(
        source, title="Seller detail title", shortDescription=line, description=""
    )
    run, result = env.execute(env.start(query="Lapras"))
    row = result["results"][0]
    full = hunt.evidence(env.actor, "session", run.id, row["id"], row["content_revision"])["lot_value"]
    assert full["stated_quantity"] == 37 and full["subtotal"] is None
    assert full["source_fields"]["title"] == "37-card mixed lot"
    assert full["source_fields"]["detail_title"] == "Seller detail title"
    if line:
        assert full["source_fields"]["detail_summary"] == line
    if kind == "identified_unpriced":
        assert full["identified_quantity"] == full["identified_unpriced_quantity"] == 2
        assert full["cards"][0]["printing_id"] == "lapras-unlimited"
    else:
        assert full["identified_quantity"] == 0
        if kind == "ambiguous":
            assert {p["id"] for p in full["contents"][0]["candidates"]} == {
                "lapras-first",
                "lapras-unlimited",
            }
        elif kind == "unmatched":
            assert full["unresolved_contents"][0]["quantity"] == 2
        else:
            assert not full["contents"] and not full["unresolved_contents"]
    assert len(env.calls) == 5
    run.created -= 1801
    with pytest.raises(ValueError, match="expired"):
        hunt.evidence(env.actor, "session", run.id, row["id"], row["content_revision"])


def test_dense_native_list_preserves_cohorts_and_ranks_under_serialization_cap():
    # Two dual-option rows, each with the parser's maximum 200 selected identities,
    # distinct native cohorts and long publisher labels. All offer rows survive.
    from hashlib import sha256

    rows = []
    for i in range(40):
        row = dict(title="🌊" * 500, seller_image="https://i.ebayimg.com/" + "a" * 491, id=str(i))
        rows.append(row)
        if i >= 2:
            continue
        groups, orders = [], []
        for index in range(200):
            cohort = sha256(f"{i}-{index}".encode()).hexdigest()
            groups.append(
                dict(
                    cohort=cohort,
                    provider="Publisher" * 200,
                    reference_date="2026-11-06",
                    date_basis="publisher_build",
                    priced_quantity=1,
                    complete=False,
                    subtotal="14.00",
                    references=[dict(source_contract="a" * 64, snapshot_version="authored-version")],
                )
            )
            orders.extend(
                dict(cohort=cohort, lane=lane, rank=index + 1) for lane in ("auction", "buy_it_now")
            )
        row.update(lot_value=dict(native_guides=groups), value_order=dict(native=orders))
    response = dict(results=rows, authority=dict(binding="authored"))
    discovery_lot_values.bound_list(response)
    assert len(json.dumps(response, ensure_ascii=False, separators=(",", ":")).encode()) <= 120 * 1024
    assert len(rows) == 40
    assert all(row["seller_image"] == "https://i.ebayimg.com/" + "a" * 491 for row in rows)
    assert len(json.dumps(response, separators=(",", ":")).encode()) <= 120 * 1024
    for row in rows[:2]:
        packed = row["lot_value"]["cohort_rows"]
        assert len(packed) == 200 and all(r[-2:] == [i + 1, i + 1] for i, r in enumerate(packed))
        assert all(r[5:8] == ["14.00", False, [0]] for r in packed)


def test_selection_reserves_dual_offer_and_uses_explicit_set_on_stable_ties(env):
    from dataclasses import replace

    run = env.start(query="Lapras")
    run.pages = tuple(replace(page, named=replace(page.named, set_name="Fossil")) for page in run.pages)
    generic = offer(1, title="Lapras mixed lot")
    other = offer(2, title="Lapras mixed lot · includes: 2x Lapras")
    selected = offer(3, title="Lapras Fossil lot · includes: 2x Lapras")
    tie = offer(4, title=selected["title"])
    risky = offer(0, title="Random mixed lot Lapras Fossil · includes: 2x Lapras")
    dual = offer(5, title=selected["title"])
    dual["buyingOptions"] = ["FIXED_PRICE", "AUCTION"]
    run.raws = [tie, dual, risky, other, selected, generic]
    assert hunt._select(run) == [selected["itemId"], dual["itemId"]]
    run.raws.reverse()
    assert hunt._select(run) == [selected["itemId"], dual["itemId"]]
    assert not env.calls


def test_indexed_assessment_identity_is_independent_of_other_lots(env, entries, monkeypatch):
    """A broad seller aspect overlaps a second lot's narrower catalog selection."""
    from pokemon_hunter.beta import discovery_listing, shopping_index

    second = printing("venusaur", "Venusaur", number="15/102")
    entries.append(second)
    indexed = SimpleNamespace(
        proposals=lambda text: entries if "Charizard" in text else [second],
        publication_checks=[],
    )
    monkeypatch.setattr(shopping_index, "current", lambda actor: indexed)
    narrow = dict(offer(0, title="Venusaur lot"), shortDescription="1x Venusaur Base Set 15/102")
    broad = offer(1, lane="auction", title="Charizard Venusaur lot")

    def project(raws):
        rows = discovery_listing.received_rows(raws)
        discovery_lot_values.project(env.actor, raws, rows)
        return {row["item_id"]: row["lot_value"] for row in rows}

    alone = project([broad])[broad["itemId"]]
    together = project([narrow, broad])[broad["itemId"]]
    assert hunt._evidence_version(alone) == hunt._evidence_version(together)
    assert alone == together


def test_explicit_all_cards_set_edition_header_is_scoped(env, entries):
    source = env.bin[0]
    source.update(title="Itemized lot")
    env.details[source["itemId"]] = dict(
        source,
        description="1x Charizard Base Set 4/102 Non Holo\nSET / EDITION: All English Base Set Unlimited.",
    )
    run, result = env.execute()
    row = result["results"][0]
    full = hunt.evidence(env.actor, "session", run.id, row["id"], row["content_revision"])["lot_value"]
    assert full["physically_selected_quantity"] == 1
    assert full["contents"][0]["clues"]["edition"] == "unlimited"
    assert any("SET / EDITION" in m["text"] for m in full["contents"][0]["scope_mentions"])


def test_metadata_compaction_preserves_listing_photos_and_normal_titles():
    title = "Original seller title with card names, set and printing details preserved in full"
    photo = "https://i.ebayimg.com/images/g/authored/s-l225.jpg"
    rows = [
        dict(id=str(i), title=title, seller_image=photo, identity_candidates=["unused" * 1000])
        for i in range(40)
    ]
    response = dict(results=rows)
    assert len(json.dumps(response).encode()) > 120 * 1024
    discovery_lot_values.bound_list(response)
    assert len(response["results"]) == 40
    assert all(row["seller_image"] == photo and row["title"] == title for row in rows)
    assert len(json.dumps(response, separators=(",", ":")).encode()) < 120 * 1024
