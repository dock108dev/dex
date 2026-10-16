"""The public paste parser stays finite on hostile text without changing its grammar."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from pokemon_hunter.beta import bulk_formats


@pytest.mark.parametrize(
    "text,expected",
    [
        ("0-2", ["0", "1", "2"]),
        ("001-003 x2", ["001", "002", "003"]),
        ("0009-11", ["0009", "0010", "0011"]),
        ("1-0003", ["1", "2", "3"]),
        ("003-003", ["003"]),
        ('"RC1-RC3"', ["RC1-RC3"]),
        ('"001-003" x2', ["001-003"]),
        ('"RC x 1"\tx 2', ["RC x 1"]),
        ("RC1; 8\n10x3", ["RC1", "8", "10"]),
        ("12X2", ["12X2"]),
        ("12\u2003x\u20032", ["12"]),
    ],
)
def test_paste_preserves_range_width_literals_and_whitespace(text, expected):
    assert [row["number"] for row in bulk_formats.parse_paste(text, {})] == expected


@pytest.mark.parametrize(
    "text",
    [
        "3-1",
        "1--2",
        "1-2-3",
        "-1",
        "1-",
        "١-٢",
        "1-２",
        "1 x２",
        "1 X2",
        "1 x2 x3",
        '""',
        '"1"extra',
        '"1""2"',
        '"1\r2"',
        '"1,2"',
        '"1\n2"',
        "1,,2",
    ],
)
def test_paste_rejects_ambiguous_or_non_ascii_range_and_quantity_syntax(text):
    with pytest.raises(ValueError):
        bulk_formats.parse_paste(text, {})


def test_paste_modes_quantities_and_row_bounds_remain_enforced():
    rows = bulk_formats.parse_paste("001-002x0002", {})
    assert [row["quantity"] for row in rows] == ["0002", "0002"]
    assert bulk_formats.parse_paste("1xunknown", {"action": "set_total"})[0]["total"] == "unknown"
    assert len(bulk_formats.parse_paste("1-2000", {})) == 2000
    assert bulk_formats.parse_paste(" \t ", {}) == []
    for text, defaults in [
        ("1x2", {"action": "mark_owned"}),
        ("1", {"action": "set_total"}),
        ("1xunknown", {}),
        ("1x0", {}),
        ("1x2001", {}),
        ("1-2001", {}),
        ("9,1-2000", {}),
        (",".join("1" for _ in range(2001)), {}),
        ("1" * (bulk_formats.MAX_BYTES + 1), {}),
    ]:
        with pytest.raises(ValueError):
            bulk_formats.parse_paste(text, defaults)


def test_paste_duplicate_occurrence_ids_remain_stable():
    rows = bulk_formats.parse_paste("1-2,1", {})
    assert rows[0]["row_id"] != rows[2]["row_id"]
    assert rows == bulk_formats.parse_paste("1-2,1", {})


def test_quantity_conversion_is_bounded_before_parsing_integers():
    assert bulk_formats.positive("0" * 100_000 + "2") == 2
    for value in ("9" * 100_000, "0" * 100_000, "٢", True):
        with pytest.raises(ValueError, match="Use a whole number"):
            bulk_formats.positive(value)


def test_range_endpoint_bound_preserves_supported_zero_padding():
    number = "0" * 4299 + "1"
    assert bulk_formats.parse_paste(f"{number}-1", {})[0]["number"] == number
    with pytest.raises(ValueError, match="Integer range endpoints are too long"):
        bulk_formats.parse_paste(f"0{number}-1", {})


def test_hostile_paste_is_rejected_within_a_bounded_process_deadline():
    # A subprocess deadline fails a hanging parser without hanging the test suite.
    # Inputs approach the public size limit and exercise failed token/range suffixes.
    script = """
import sys
from pokemon_hunter.beta.bulk_formats import parse_paste

sys.set_int_max_str_digits(0)
for text in (
    "0" * 700_000 + "-" + "0" * 700_000 + "!",
    "0" * 700_000 + "-" + "0" * 700_000,
    "1" * 700_000 + "-" + "2" * 700_000 + "!",
    "1" * 700_000 + "-" + "2" * 700_000,
    '"' + "a" * 1_400_000,
    "1 x" + " " * 1_400_000 + "!",
    "1x" + "9" * 1_400_000,
):
    try:
        parse_paste(text, {})
    except ValueError:
        continue
    raise AssertionError("Hostile paste was accepted")
"""
    subprocess.run(
        [sys.executable, "-c", script],
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
        check=True,
        capture_output=True,
        timeout=5,
    )
