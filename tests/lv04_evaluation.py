"""Reproduce selection/quantity metrics on the authored LV-04 regression corpus.

Run directly with an engineering Python. This does not open an app root, acquire
anything, inspect prices or demonstrate a customer product. Not a held-out sample.
"""

import json

from lv04_cases import CASES, catalog

from pokemon_hunter.beta import hunter_lot_parser as parser


def evaluate():
    outcomes = []
    expected_rows = selected_rows = correct_rows = false_selected = false_excluded = 0
    for sample in CASES:
        value = parser.parse(sample["raw"], catalog(), detail=sample["detail"])
        selected = {}
        for row in value["proposals"]:
            if row["included_quantity"]:
                selected[row["printing_id"]] = selected.get(row["printing_id"], 0) + row["included_quantity"]
        expected = sample["expected"]
        expected_rows += len(expected)
        selected_rows += len(selected)
        correct_rows += sum(pid in expected for pid in selected)
        false_selected += sum(pid not in expected for pid in selected)
        false_excluded += sum(pid not in selected for pid in expected)
        outcomes.append(
            dict(
                case=sample["key"],
                stratum=sample["category"],
                exact_selection_and_quantity=selected == expected,
                stated_count_correct=value["seller_stated_total"] == sample["total"],
                selected_units=sum(selected.values()),
                expected_units=sum(expected.values()),
                quantities_reconciled=not value["quantity_issues"],
                unresolved=value["contents_state"] != "resolved",
            )
        )
    n = len(outcomes)
    return dict(
        scope="Authored development/regression corpus; five isolated catalog printings, no seller samples, prices, model or photo calls. Not a holdout or population estimate.",
        listings=n,
        exact_identity_precision=dict(correct=correct_rows, selected_rows=selected_rows),
        exact_identity_recall=dict(correct=correct_rows, expected_supported_rows=expected_rows),
        false_selections=dict(rows=false_selected, selected_rows=selected_rows),
        false_exclusions=dict(rows=false_excluded, expected_supported_rows=expected_rows),
        exact_selection_and_quantity=dict(
            correct=sum(r["exact_selection_and_quantity"] for r in outcomes), listings=n
        ),
        stated_count=dict(correct=sum(r["stated_count_correct"] for r in outcomes), listings=n),
        selected_physical_units=dict(
            selected=sum(r["selected_units"] for r in outcomes),
            expected=sum(r["expected_units"] for r in outcomes),
        ),
        quantities_reconciled=dict(listings=sum(r["quantities_reconciled"] for r in outcomes), evaluated=n),
        unresolved_or_optional_review=dict(listings=sum(r["unresolved"] for r in outcomes), evaluated=n),
        automatic_model_fallback=dict(calls=0, evaluated=n),
        automatic_photo_fallback=dict(calls=0, evaluated=n, necessity="unmeasured"),
        negative_or_exclusion_stratum=dict(
            listings=sum(r["stratum"] in {"adversarial", "excluded"} for r in outcomes),
            false_selection_listings=sum(
                not r["exact_selection_and_quantity"]
                for r in outcomes
                if r["stratum"] in {"adversarial", "excluded"}
            ),
        ),
        outcomes=outcomes,
    )


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2))
