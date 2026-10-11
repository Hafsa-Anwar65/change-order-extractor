from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from co_extract.normalize import (
    AMBIGUOUS_DATE_FACTOR,
    parse_date,
    parse_days,
    parse_identifier,
    parse_money,
    parse_text,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("$12,450.00", "12450.00"),
        ("12450", "12450.00"),
        ("(3,200.00)", "-3200.00"),
        ("($3,200.00)", "-3200.00"),
        ("-$3,200", "-3200.00"),
        ("$ -3,200.50", "-3200.50"),
        ("\u2212$5.00", "-5.00"),  # unicode minus
        ("3,200.00 CR", "-3200.00"),
        ("USD 1,200", "1200.00"),
        ("$1,000,000.5", "1000000.50"),
    ],
)
def test_parse_money(raw: str, expected: str) -> None:
    assert parse_money(raw).value == Decimal(expected)


@pytest.mark.parametrize("raw", ["$l2,450.00", "$1,000 + $500", "abc", "", "1,2345", "$"])
def test_parse_money_refuses_to_guess(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_money(raw)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026-03-14", date(2026, 3, 14)),
        ("March 14, 2026", date(2026, 3, 14)),
        ("Mar. 14, 2026", date(2026, 3, 14)),
        ("Sept 3, 2026", date(2026, 9, 3)),
        ("14 March 2026", date(2026, 3, 14)),
        ("14th of March, 2026", date(2026, 3, 14)),
        ("14-Mar-2026", date(2026, 3, 14)),
        ("03/14/2026", date(2026, 3, 14)),  # only month-first is valid
        ("14/03/2026", date(2026, 3, 14)),  # only day-first is valid
        ("Issued on June 2, 2026 (rev 1)", date(2026, 6, 2)),
    ],
)
def test_parse_unambiguous_dates(raw: str, expected: date) -> None:
    parsed = parse_date(raw)
    assert parsed.value == expected
    assert parsed.confidence_factor == 1.0
    assert parsed.note is None


def test_equal_day_and_month_is_not_ambiguous() -> None:
    assert parse_date("05/05/2026").confidence_factor == 1.0


def test_ambiguous_numeric_date_is_flagged() -> None:
    parsed = parse_date("03/04/2026")
    assert parsed.value == date(2026, 3, 4)  # US month-first by default
    assert parsed.confidence_factor == AMBIGUOUS_DATE_FACTOR
    assert parsed.note is not None


def test_day_first_option() -> None:
    assert parse_date("03/04/2026", day_first=True).value == date(2026, 4, 3)


def test_two_digit_year() -> None:
    assert parse_date("3/14/26").value == date(2026, 3, 14)


@pytest.mark.parametrize("raw", ["13/13/2026", "Feb 30, 2026", "sometime soon", "Foo 14, 2026", ""])
def test_parse_date_rejects_invalid(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_date(raw)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("5 calendar days", 5),
        ("Add 3 working days", 3),
        ("+7 days", 7),
        ("12", 12),
        ("0 days", 0),
        ("None", 0),
        ("No change", 0),
        ("Reduction of 2 days", -2),
        ("-4 days", -4),
        ("(5) days", -5),
        ("Extend completion from 6/1/2026 by 14 days", 14),  # not the '6' in the date
    ],
)
def test_parse_days(raw: str, expected: int) -> None:
    assert parse_days(raw).value == expected


@pytest.mark.parametrize("raw", ["soon", "TBD", ""])
def test_parse_days_rejects_invalid(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_days(raw)


def test_parse_text_collapses_whitespace() -> None:
    assert parse_text("  Acme   Corp \n Ltd ").value == "Acme Corp Ltd"


@pytest.mark.parametrize("raw", ["____", "N/A", "  ", "-", "TBD"])
def test_parse_text_rejects_blank_form_fields(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_text(raw)


def test_parse_identifier() -> None:
    assert parse_identifier(" #14. ").value == "14"
    assert parse_identifier("CO-014").value == "CO-014"
    for bad in ("Date: March 1", "x" * 31, "___"):
        with pytest.raises(ValueError):
            parse_identifier(bad)
