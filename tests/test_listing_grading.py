import pytest

from pokemon_hunter.beta import discovery_comparison
from pokemon_hunter.beta.listing_grading import status


@pytest.mark.parametrize(
    ("text", "aspects", "expected"),
    [
        ("Pikachu card", [], "unknown"),
        ("Pikachu ungraded", [], "raw"),
        ("Pikachu not graded", [], "raw"),
        ("Pikachu not professionally graded", [], "raw"),
        ("Pikachu no slab", [], "unknown"),
        ("Pikachu PSA 10", [], "graded"),
        ("Pikachu slab", [], "graded"),
        ("Pikachu ungraded PSA 10", [], "unknown"),
        ("Pikachu", [{"name": "Graded", "value": "No"}], "raw"),
        ("Pikachu", [{"name": "Graded", "value": "Yes"}], "graded"),
        ("Pikachu ungraded", [{"name": "Graded", "value": "Yes"}], "unknown"),
        ("Pikachu PSA 10", [{"name": "Graded", "value": "No"}], "unknown"),
        ("Pikachu", [{"name": "Graded", "value": "Unknown"}], "unknown"),
    ],
)
def test_seller_claim_status(text, aspects, expected):
    assert status({"localizedAspects": aspects}, text) == expected


@pytest.mark.parametrize(("claimed", "reference"), [("raw", "9"), ("9", "raw")])
def test_reference_type_must_agree_with_claim(claimed, reference):
    clues = dict(language=None, edition=None, finish=None, grade=claimed, graded=claimed != "raw")
    assert "grade conflicts" in discovery_comparison._reference_claim_issue({}, clues, {"grade": reference})
