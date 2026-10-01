"""Synthetic bargain comparisons; no provider calls or personal collection reads."""

from datetime import date, timedelta

import pytest

from pokemon_hunter.beta import hunt_values
from pokemon_hunter.beta.hunt_values import prepare_records, price_comparison

TODAY = date(2026, 9, 30)
DATA = {"cards": {"a": {"printing_id": "pa"}, "b": {"printing_id": "pb"}}}


def guide(key="a", value="100", **changes):
    return {
        "card_id": key,
        "edition": "standard",
        "grade": "raw",
        "grader": "Guide",
        "currency": "USD",
        "value": value,
        "source_url": "https://www.pricecharting.com/game/test/card",
        "as_of": TODAY.isoformat(),
        "variant_verified": True,
        **changes,
    }


def compare(row=None, records=None, raw=None, scope=None):
    return price_comparison(
        {
            "title": "Unlimited card",
            "cards": ["a"],
            "count": 1,
            "pool": "singles",
            "delivered": "60",
            **(row or {}),
        },
        DATA,
        records if records is not None else [guide()],
        raw or {},
        scope,
        today=TODAY,
    )


def test_single_matches_edition_and_computes_discount_without_ownership():
    result = compare(records=[guide(), guide(value="1000", edition="first_edition")])
    assert result["status"] == "matched"
    assert result["basis"] == "ungraded_guide"
    assert (result["reference_total"], result["saving"], result["discount_percent"]) == (
        "100.00",
        "40.00",
        "40.00",
    )
    assert result["priced_cards"] == result["identified_cards"] == 1
    assert result["coverage"] == 1
    assert result["evidence"][0]["edition"] == "standard"


def test_unknown_edition_is_conditional_and_does_not_use_owned_first_edition_flag():
    result = compare({"title": "card"}, [guide(), guide(value="1000", edition="first_edition")])
    assert result["status"] == "conditional"
    assert result["reference_total"] == "100.00"
    assert "conditional assumption" in result["note"]
    first = compare({"title": "1st edition card"}, [guide(), guide(value="1000", edition="first_edition")])
    assert first["status"] == "matched" and first["reference_total"] == "1000.00"
    negated = compare({"title": "not first edition card"})
    assert negated["status"] == "conditional"


@pytest.mark.parametrize(
    "changes",
    [
        {"value": "NaN"},
        {"value": "Infinity"},
        {"value": "-1"},
        {"value": "1e999999"},
        {"currency": "EUR"},
        {"variant_verified": False},
        {"source_url": "javascript:alert(1)"},
        {"source_url": "https://good.test@evil.test/guide"},
        {"source_url": "https://127.0.0.1/guide"},
        {"source_url": "https://good.test\\@evil.test/guide"},
        {"source_url": "https://good.test:444/guide"},
        {"as_of": (TODAY - timedelta(days=31)).isoformat()},
        {"as_of": (TODAY + timedelta(days=1)).isoformat()},
        {"as_of": "bad"},
    ],
)
def test_invalid_guide_evidence_is_unavailable(changes):
    result = compare(records=[guide(**changes)])
    assert result["status"] == "unavailable"
    assert result["reference_total"] is None and result["evidence"] == []


def test_newest_valid_observation_wins_and_zero_never_divides():
    result = compare(
        records=[guide(value="50", as_of=(TODAY - timedelta(days=30)).isoformat()), guide(value="0")]
    )
    assert result["reference_total"] == "0.00"
    assert result["saving"] == "-60.00" and result["discount_percent"] is None


def test_grade_grader_match_does_not_promote_generic_scenarios():
    psa10 = compare({"title": "Unlimited PSA 10 card"}, [guide(grade="10", value="500")])
    assert psa10["basis"] == "graded_guide" and psa10["reference_total"] == "500.00"
    psa9 = compare({"title": "Unlimited PSA 9 card"}, [guide(grade="9", value="300"), guide()])
    assert psa9["status"] == "unavailable"
    matched9 = compare({"title": "Unlimited PSA 9 card"}, [guide(grade="9", grader="PSA", value="300")])
    assert matched9["reference_total"] == "300.00"
    wrong_grader = compare({"title": "Unlimited BGS 10 card"}, [guide(grade="10", grader="PSA")])
    assert wrong_grader["status"] == "unavailable"
    generic = compare({"title": "Unlimited graded card"})
    assert generic["status"] == "unavailable"
    estimated = compare({"title": "Unlimited PSA 8 card"}, [guide(grade="8", grader="PSA", estimated=True)])
    assert estimated["status"] == "unavailable"


@pytest.mark.parametrize("title", ["Unlimited PSA 10.5 card", "Unlimited PSA 11 card"])
def test_unsupported_grade_is_not_truncated_or_replaced_with_raw(title):
    assert compare({"title": title}, [guide(), guide(grade="10", value="500")])["status"] == "unavailable"


def test_complete_and_partial_lots_do_not_value_unknown_cards_as_zero():
    records = [guide(), guide("b", "20")]
    complete = compare({"pool": "known_lots", "count": 2, "cards": ["a", "b"]}, records)
    assert complete["status"] == "conditional" and complete["reference_total"] == "120.00"
    partial = compare({"pool": "known_lots", "count": 30, "cards": ["a", "b"]}, records)
    assert partial["status"] == "partial" and partial["basis"] == "identified_subtotal"
    assert partial["reference_total"] == "120.00" and partial["coverage"] == 2 / 30
    missing = compare({"pool": "known_lots", "count": 2, "cards": ["a", "b"]})
    assert missing["status"] == "partial" and missing["reference_total"] == "100.00"
    assert missing["coverage"] == 0.5


def test_mixed_lot_clues_never_apply_one_cards_grade_or_edition_to_every_card():
    records = [
        guide(),
        guide("b", "20"),
        guide(value="5000", grade="10"),
        guide("b", "2000", grade="10"),
        guide(value="1000", edition="first_edition"),
        guide("b", "500", edition="first_edition"),
    ]
    graded = compare(
        {
            "title": "PSA 10 card a + raw card b lot of 2",
            "pool": "known_lots",
            "count": 2,
            "cards": ["a", "b"],
        },
        records,
    )
    assert graded["reference_total"] == "120.00" and graded["status"] == "conditional"
    assert all(e["grade"] == "raw" and e["edition"] == "standard" for e in graded["evidence"])
    editions = compare(
        {
            "title": "First edition card a + unlimited card b lot of 2",
            "pool": "known_lots",
            "count": 2,
            "cards": ["a", "b"],
        },
        records,
    )
    assert editions["reference_total"] == "120.00"
    assert "Individual lot grades and editions are not matched" in editions["note"]


def test_unknown_lot_uses_scoped_average_only_as_benchmark():
    records = [guide(), guide("b", "20")]
    result = compare({"title": "lot of 10 cards", "cards": [], "pool": "known_lots", "count": 10}, records)
    assert result["status"] == "benchmark" and result["basis"] == "catalog_average_benchmark"
    assert result["reference_total"] == "600.00" and result["average_per_card"] == "60.00"
    assert result["identified_cards"] == 0 and result["priced_cards"] == 2
    assert "actual contents" in result["note"] and "not an appraisal" in result["note"]
    scoped = compare(
        {"title": "lot of 10 cards", "cards": [], "pool": "known_lots", "count": 10},
        records,
        scope={"definition": {"items": [{"printing_ids": ["pb"]}]}},
    )
    assert scoped["reference_total"] == "200.00" and scoped["priced_cards"] == 1


@pytest.mark.parametrize(
    "title,pool",
    [
        ("mystery lot", "known_lots"),
        ("sealed lot", "known_lots"),
        ("booster packs", "known_lots"),
        ("card lot", "mystery"),
    ],
)
def test_mystery_and_sealed_unknowns_have_no_lot_valuation(title, pool):
    result = compare({"title": title, "cards": [], "pool": pool, "count": 10})
    assert result["status"] == "unavailable" and result["reference_total"] is None


def test_raw_condition_records_require_current_https_provenance():
    raw = {"a": {"LP": {"value": "80", "source": "https://prices.example/guide", "as_of": TODAY.isoformat()}}}
    result = compare({"condition": "Lightly Played"}, [guide()], raw)
    assert result["reference_total"] == "80.00"
    raw["a"]["LP"]["source"] = "source reference"
    assert compare({"condition": "Lightly Played"}, [guide()], raw)["reference_total"] == "100.00"


def test_auction_and_unavailable_delivered_cost_keep_comparison_limits_visible():
    result = compare({"type": "auction"})
    assert "current bid" in result["note"] and "settled purchase price" in result["note"]
    missing = compare({"delivered": None})
    assert missing["reference_total"] == "100.00" and missing["saving"] is None
    assert missing["discount_percent"] is None


def test_static_notes_do_not_leak_seller_names_before_evidence_is_revealed():
    result = compare({"title": "PRIVATE seller identity card"})
    assert "PRIVATE" not in result["note"]
    assert set(result["evidence"][0]) == {"card_id", "grade", "edition", "guidevalue", "source_url", "as_of"}


def test_prepared_sources_reuse_guide_and_benchmark_validation(monkeypatch):
    records = prepare_records([guide(), guide("b", "20")])
    original = hunt_values._valid
    validations = []

    def counted(*args, **kwargs):
        validations.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(hunt_values, "_valid", counted)
    unknown = {"title": "lot", "cards": [], "pool": "known_lots", "count": 10}
    first = compare(unknown, records)
    second = compare({**unknown, "count": 20}, records)
    assert first["reference_total"] == "600.00" and second["reference_total"] == "1200.00"
    assert len(validations) == 2
    assert len(records.benchmarks) == 1
    assert compare(records=records)["reference_total"] == "100.00"
    assert len(validations) == 2


def test_refreshed_source_precedence_is_retained_for_equal_dates():
    records = prepare_records([guide(value="80"), guide(value="100")])
    assert compare(records=records)["reference_total"] == "80.00"
