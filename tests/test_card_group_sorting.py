"""Collector numbers sort naturally before pagination in every collection scope."""

import pytest
from test_card_groups import metadata

from pokemon_hunter.beta import card_groups


def catalog(numbers):
    return card_groups.build_groups([metadata(number, collector_number=number) for number in numbers])[
        "groups"
    ]


def test_group_number_order_preserves_literal_identities():
    numbers = ["TG10", "11", "2", "100", "1", "10", "9", "2a", "TG2", "02"]
    result = catalog(numbers)
    assert [row["collector_number"] for row in result if row["collector_number"] != "02"] == [
        "1",
        "2",
        "2a",
        "9",
        "10",
        "11",
        "100",
        "TG2",
        "TG10",
    ]
    assert len({row["id"] for row in result}) == len(numbers)
    assert result == catalog(list(reversed(numbers)))
    assert {row["collector_number"]: row["id"] for row in result} == {
        row["collector_number"]: row["id"] for row in catalog(list(reversed(numbers)))
    }


@pytest.mark.parametrize("public", [False, True])
@pytest.mark.parametrize("sort", [None, "set", "number", "name"])
def test_numeric_sort_across_page_boundaries_and_scopes(public, sort):
    rows = catalog(["100", "11", "10", "9", "2", "1"])
    for row in rows:
        row.update(
            variant_count=1,
            published_variant_count=1,
            catalog_available=True,
            present=True,
            established_total_quantity=None,
            recorded_copy_count=0,
            current_copy_count=0,
            exact_variant_count=0,
            _published_ids={child["id"] for child in row["_children"]},
        )
    snapshot = dict(public=public, generation=0, groups=rows, unresolved=[])
    raw = dict(page_size="3", scope="catalog" if public else "owned")
    if sort:
        raw["sort"] = sort
    pages = [card_groups._list(snapshot, dict(raw, page=str(page))) for page in (1, 2)]
    assert all(page["total"] == 6 and page["pages"] == 2 for page in pages)
    assert [row["collector_number"] for page in pages for row in page["groups"]] == [
        "1",
        "2",
        "9",
        "10",
        "11",
        "100",
    ]


def test_fractional_and_suffix_number_order():
    assert [row["collector_number"] for row in catalog(["10/102", "2b", "2a", "2/102", "1/102"])] == [
        "1/102",
        "2/102",
        "2a",
        "2b",
        "10/102",
    ]
