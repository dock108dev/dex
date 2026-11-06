"""Server/UI integration using authored admitted projections, never market evidence."""

from datetime import datetime, timezone

import pytest
from test_hunter_lots import entries as entries
from test_hunter_lots import local as local
from test_hunter_lots import raw
from test_lv02_variant_selection import family

from pokemon_hunter.beta import discovery_comparison as dc
from pokemon_hunter.beta import discovery_listing, discovery_lot_values, hunter_lot_parser, lot_guides
from pokemon_hunter.beta import lot_calculator as lot
from pokemon_hunter.beta import price_snapshot_contract as rules
from pokemon_hunter.beta import valuation_evidence as evidence

REFERENCE_CELLS = dc._reference_cells


def native_rows(entries):
    now = datetime.now(timezone.utc)
    policy = dict(
        provider="authored-only",
        policy_version="test-1",
        fields={"market": dict(grade="raw", unit="USD_decimal")},
    )
    return [
        dict(
            printing_id=p["id"],
            observation_id="authored-" + p["id"],
            identity={k: p.get(k) for k in rules.IDENTITY},
            provider_identity=dict(
                product_id=p["id"],
                set=p["set_name"],
                number=p["collector_number"],
                language=p["language"],
                edition=p["edition"],
                finish=p["finish"],
                variant=p["variant"],
                mapping_review="authored",
            ),
            field="market",
            grade="raw",
            grader="Authored",
            original_money="10",
            value="10",
            currency="USD",
            as_of=now.date().isoformat(),
            captured_at=now.isoformat(),
            estimated=True,
            estimate_kind="provider_guide",
            source_url="https://example.test/authored",
            source_version="authored-v1",
            condition=None,
            valuation_qualification="reviewed",
            ceiling_applicable=False,
            evidence=dict(
                schema=evidence.NATIVE_SCHEMA,
                basis=evidence.NATIVE,
                condition=None,
                amount_basis=evidence.NATIVE_AMOUNT,
                native_money=dict(evidence.NATIVE_MONEY),
                sales=[],
                estimate=None,
            ),
            _snapshot_version="authored-version",
            _contract_sha256="a" * 64,
            _review_id="authored-review",
            _save_allowed=False,
            _expires_at=None,
            _native_context=policy,
        )
        for p in entries
    ]


def test_server_native_total_has_no_normalized_total_or_offer_difference(local, entries, monkeypatch):
    actor, _ = local
    for entry in entries:
        entry["catalog_version"] = "authored-v1"
    monkeypatch.setattr(dc, "_reference_cells", REFERENCE_CELLS)
    records = native_rows(entries)
    monkeypatch.setattr(lot, "retained_records", lambda: records)
    source = raw()
    rows = discovery_listing.received_rows([source])
    discovery_lot_values.project(actor, [source], rows)
    value = rows[0]["lot_value"]
    assert value["total"] is value["subtotal"] is None
    assert value["bid_difference"] is value["buy_now_difference"] is None
    assert value["native_guides"], str(value)
    assert value["native_guides"][0]["total"] == "30.00"
    assert value["native_guides"][0]["priced_quantity"] == 3
    assert all(r["basis"] == evidence.NATIVE for r in value["native_guides"][0]["references"])
    assert rows[0]["buy_now_delivered_total"] == "4.00"
    assert value["references"] == []


def test_server_mixed_native_and_normalized_is_not_a_combined_total(local, entries, monkeypatch):
    actor, _ = local
    for entry in entries:
        entry["catalog_version"] = "authored-v1"
    existing = dc._reference_cells
    monkeypatch.setattr(
        dc,
        "_reference_cells",
        lambda p, *a, **kw: existing(p, *a, **kw) if p["id"] == "charizard" else ({}, {}),
    )
    records = native_rows(entries[1:])
    monkeypatch.setattr(lot, "retained_records", lambda: records)
    source = raw()
    rows = discovery_listing.received_rows([source])
    discovery_lot_values.project(actor, [source], rows)
    value = rows[0]["lot_value"]
    assert value["subtotal"] == "20.00" and value["total"] is None
    assert value["native_guides"][0]["subtotal"] == "10.00" and value["native_guides"][0]["total"] is None
    assert value["buy_now_difference"] is None


def test_family_priced_alternative_never_selects_or_replaces_other_choices():
    entries = family()
    proposal = hunter_lot_parser.parse(
        dict(title="Pokemon lot of 2 cards", shortDescription="2x Charizard Base Set 4/102 English"), entries
    )
    original = proposal["proposals"][0]["variant_selection"].copy()
    result = lot_guides.family_alternatives(
        proposal, entries, native_rows(entries[1:2]), datetime.now(timezone.utc).date()
    )
    assert result[0]["selected_child_id"] is None
    assert len(result[0]["alternatives"]) == 2
    assert sum(a["reference"] is not None for a in result[0]["alternatives"]) == 1
    result = lot_guides.family_alternatives(proposal, entries, [], datetime.now(timezone.utc).date())
    assert result[0]["selected_child_id"] is None and len(result[0]["alternatives"]) == 2
    assert proposal["proposals"][0]["variant_selection"] == original


def test_stale_family_cannot_be_reused_for_prices():
    entries = family()
    proposal = hunter_lot_parser.parse(
        dict(title="2 cards", shortDescription="2x Charizard Base Set 4/102 English First Edition Non Holo"),
        entries,
    )
    entries[1]["catalog_version"] = "changed"
    with pytest.raises(ValueError, match="changed"):
        lot_guides.family_alternatives(
            proposal, entries, native_rows(entries[1:]), datetime.now(timezone.utc).date()
        )


@pytest.mark.parametrize(
    "text",
    [
        "2x Charizard Base Set 4/102 First Edition Non Holo",
        "2x Charizard Base Set 4/102 English",
        "2x Charizard Base Set 4/102 English Unlimited",
    ],
)
def test_only_available_printing_does_not_fill_missing_seller_traits(local, entries, monkeypatch, text):
    actor, _ = local
    for entry in entries:
        entry["catalog_version"] = "authored-v1"
    monkeypatch.setattr(dc, "_reference_cells", REFERENCE_CELLS)
    records = native_rows(entries)
    monkeypatch.setattr(lot, "retained_records", lambda: records)
    source = raw(title="Pokemon lot of 2 cards", shortDescription=text)
    rows = discovery_listing.received_rows([source])
    discovery_lot_values.project(actor, [source], rows)
    assert rows[0]["lot_value"]["native_guides"] == []


def test_native_utc_build_date_is_not_rejected_on_previous_local_calendar_day(local, entries, monkeypatch):
    from pokemon_hunter.beta import hunter_lots

    actor, _ = local
    fixed = datetime(2026, 11, 5, 1, tzinfo=timezone.utc)

    class Clock:
        @staticmethod
        def now(tz):
            return fixed.astimezone(tz)

    for entry in entries:
        entry["catalog_version"] = "authored-v1"
    records = native_rows(entries)
    for row in records:
        row.update(
            as_of=None,
            reference_as_of="2026-11-05",
            publisher_built_at=fixed.isoformat(),
            captured_at=fixed.isoformat(),
        )
    monkeypatch.setattr(hunter_lots, "datetime", Clock)
    monkeypatch.setattr(dc, "_reference_cells", REFERENCE_CELLS)
    monkeypatch.setattr(lot, "retained_records", lambda: records)
    source = raw()
    rows = discovery_listing.received_rows([source])
    discovery_lot_values.project(actor, [source], rows)
    assert rows[0]["lot_value"]["native_guides"][0]["total"] == "30.00"
