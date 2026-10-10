"""CS-T1's independently retained expected checks plus discovered implementation risks."""

import copy
import json
from pathlib import Path

import pytest

from pokemon_hunter.beta import shopping_math as math

CASES = json.loads((Path(__file__).parents[1] / "tests/fixtures/shopping-worked-cases.json").read_text())[
    "cases"
]


def project_fixture(raw):
    """Test-only ownership projection. Never imported into production authority."""
    data = copy.deepcopy(raw)
    ownership, goal = data["ownership_context"], data.get("frozen_goal")
    ownership["availability"] = (
        "complete" if ownership["availability"] == "complete_synthetic_snapshot" else "unavailable"
    )
    if goal:
        if goal["policy"] == "species_declaration":
            owned = {
                i["item_id"] for i in goal["items"] if i.get("species_id") in goal["frozen_owned_species"]
            }
        else:
            copies = ownership["resolved_active_copies"] + (
                ownership["associated_unresolved_copies"] if goal["policy"] == "catalog" else []
            )
            owned = {
                i["item_id"]
                for i in goal["items"]
                if set(i["printing_ids"]).intersection(c["printing_id"] for c in copies)
            }
        goal["owned_item_ids"] = sorted(owned)
    return data


def path(value, key):
    for part in key.split("."):
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["case_id"])
def test_retained_independent_expected_checks(case):
    outputs = {v["variant"]: math.evaluate(project_fixture(v["input"])) for v in case["evaluations"]}
    for check in case["independent_expected_checks"]:
        assert path(outputs[check["variant"]], check["output_path"]) == check["expected"]


@pytest.mark.parametrize(
    "value",
    [
        "-1",
        "-0",
        "NaN",
        "Infinity",
        "1000000000000.000001",
        "1.0000001",
        "1e3",
        "",
        " 1",
        "01",
        "1,000",
        ".5",
        True,
        1.2,
        None,
    ],
)
def test_input_rejection(value):
    with pytest.raises(ValueError):
        math.amount(value)


@pytest.mark.parametrize("value", [0, -1, 1.5, "1", True, 100001, None])
def test_quantity_rejection(value):
    with pytest.raises(ValueError):
        math.quantity(value)


def test_missing_duplicate_references_and_conflicting_goal_mapping():
    data = project_fixture(CASES[6]["evaluations"][0]["input"])
    missing = copy.deepcopy(data)
    missing["value_references"] = []
    with pytest.raises(ValueError, match="missing_reference"):
        math.evaluate(missing)
    duplicate = copy.deepcopy(data)
    duplicate["selected_cards"].append(duplicate["selected_cards"][0])
    with pytest.raises(ValueError, match="duplicate"):
        math.evaluate(duplicate)
    data["frozen_goal"]["items"].append(dict(data["frozen_goal"]["items"][0], item_id="conflicting"))
    with pytest.raises(ValueError, match="conflicting_goal_item"):
        math.evaluate(data)


def test_overlapping_groups_rejected_and_shared_per_card_line_rounding():
    data = project_fixture(CASES[0]["evaluations"][0]["input"])
    a, b = data["selected_cards"]
    r = data["value_references"][0]
    second = dict(r, reference_id="other", applies_to_quantities={a["selection_id"]: 1, b["selection_id"]: 1})
    data["value_references"].append(second)
    b["chosen_value_reference"] = "other"
    result = math.evaluate(data)
    assert result["known_selected_subtotal"] is None
    assert set(result["reference_eligibility"].values()) == {"overlapping_active_groups"}
    data["value_references"] = [dict(r, value_scope="per_card", amount="0.005")]
    b["chosen_value_reference"] = a["chosen_value_reference"]
    result = math.evaluate(data)
    assert result["full_selected_total"] == "0.01"
    assert result["line_display_rounding_reconciliation"] == "0.01"


def test_negative_zero_and_overflow():
    data = project_fixture(CASES[0]["evaluations"][0]["input"])
    data["value_references"][0]["amount"] = "11.999999"
    assert (
        math.evaluate(data)["comparisons"]["listing_observation"]["full_selected_reference_minus_base_price"]
        == "0.00"
    )
    data["value_references"][0].update(value_scope="per_card", amount="1000000000000")
    with pytest.raises(ValueError, match="above_cap"):
        math.evaluate(data)
