"""Buying-order regressions with controlled offer evidence."""

from types import SimpleNamespace

from pokemon_hunter.beta import lot_recommendations


def offer(key, cost, *, score=None, name="Lapras", units=1, lane="buy_it_now"):
    return dict(
        item_id=key,
        title=name,
        lot_value=dict(
            cards=[dict(name=name)] if units else [],
            identified_quantity=units,
            benchmark_costs={lane: dict(delivered_before_tax=cost)},
        ),
        value_order=dict(
            lanes={lane: dict(group="complete" if score is not None else "unpriced", score=score)}
        ),
    )


def ordered(rows, **choices):
    lot_recommendations.rank(rows, SimpleNamespace(query="Lapras", budget="120", **choices))
    return [r["item_id"] for r in sorted(rows, key=lambda r: r["buying_order"]["combined"]["rank"])]


def test_supported_value_leads_unknown_value_and_over_reference():
    assert ordered(
        [offer("expensive", "90", score="-10"), offer("unknown", "20"), offer("supported", "70", score="30")]
    ) == ["supported", "unknown", "expensive"]


def test_request_fit_precedes_unrelated_discount():
    assert ordered([offer("unrelated", "10", score="100", name="Pikachu"), offer("match", "30")]) == [
        "match",
        "unrelated",
    ]


def test_unknown_shipping_is_not_zero_and_price_breaks_equal_evidence():
    assert ordered([offer("unknown", None), offer("high", "70"), offer("low", "30")]) == [
        "low",
        "high",
        "unknown",
    ]


def test_above_baseline_opportunity_retained_without_purchase_claim():
    rows = [offer("opportunity", "300", score="150"), offer("ordinary", "80")]
    assert ordered(rows)[0] == "opportunity"
    assert "Above your baseline" in rows[0]["buying_order"]["combined"]["reason"]
    assert "tax still to check" in rows[0]["buying_order"]["combined"]["reason"]


def test_combined_prefers_bin_observation_not_cheapest_bid():
    row = offer("dual", "100", score="10")
    row["value_order"]["lanes"]["auction"] = dict(group="complete", score="90")
    row["lot_value"]["benchmark_costs"]["auction"] = dict(delivered_before_tax="20")
    ordered([row])
    assert row["buying_order"]["combined"]["lane"] == "buy_it_now"


def test_accented_names_match_and_random_contents_do_not_lead():
    rows = [
        offer("mystery", "1", name="Lapras Mystery Box"),
        offer("accent", "20", name="Lápras"),
        offer("ordinary", "30"),
    ]
    assert ordered(rows) == ["accent", "ordinary", "mystery"]


def test_native_guide_screens_complete_lots_without_claiming_profit():
    rows = [offer("unknown", "20"), offer("better", "300"), offer("worse", "350")]
    for row in rows[1:]:
        row["lot_value"]["native_guides"] = [
            dict(cohort="same-source-date", subtotal="450", total="450", complete=True, priced_quantity=1)
        ]
    assert ordered(rows) == ["better", "worse", "unknown"]
    evidence = rows[1]["buying_order"]["combined"]
    assert evidence["guide_amount"] == "450"
    assert "Mixed-condition estimate" in evidence["reason"]
    assert "Above your baseline" in evidence["reason"]
    assert rows[1]["value_order"]["lanes"]["buy_it_now"]["score"] is None


def test_partial_native_and_unknown_shipping_never_get_whole_lot_ratio():
    for complete, cost in ((False, "20"), (True, None)):
        row = offer("partial", cost)
        row["lot_value"]["native_guides"] = [
            dict(cohort="source", subtotal="100", complete=complete, priced_quantity=1)
        ]
        ordered([row])
        assert row["buying_order"]["combined"]["price_to_guide"] is None


def test_glance_estimate_ratios_and_short_contents():
    row = offer("value", "87")
    row["lot_value"].update(
        total="100", all_pre_2000=True, cards=[dict(name=n) for n in ("Lapras", "Ditto", "Zapdos", "Moltres")]
    )
    ordered([row])
    glance = row["buying_order"]["combined"]
    assert glance["price_to_estimate"] == "0.87"
    assert glance["estimate_complete"] and glance["all_pre_2000"]
    assert glance["contents"] == "Lapras, Ditto, Zapdos +1 more"
    row["lot_value"].update(total=None, subtotal="100")
    ordered([row])
    assert row["buying_order"]["combined"]["estimate_amount"] == "100"
    assert row["buying_order"]["combined"]["price_to_estimate"] is None


def test_pre2000_requires_complete_contents_and_release_evidence():
    value = dict(
        cards=[dict(printing_id="one", quantity=2)],
        stated_quantity=2,
        contents_state="resolved",
        unidentified_quantity=0,
        quantity_issues=[],
    )
    entries = {"one": dict(set_id="fossil", language="en", edition="unlimited", finish="normal")}
    dates = {"fossil": dict(end="1999-12-31")}

    def check():
        return lot_recommendations.pre_2000_contents(value, entries, dates)

    assert check()
    value["stated_quantity"] = 3
    assert not check()
    value["stated_quantity"] = 2
    value["quantity_issues"] = ["conflicting quantity"]
    assert not check()
    value["quantity_issues"] = []
    entries["one"]["variant"] = '{"type":"normal","other":["anniversary-reprint"]}'
    assert not check()
    entries["one"]["variant"] = None
    dates["fossil"]["end"] = "2000-01-01"
    assert not check()
    dates.clear()
    assert not check()
