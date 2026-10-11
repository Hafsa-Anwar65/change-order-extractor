"""Pure parsers that turn raw extracted strings into typed values.

Each parser returns a `Parsed` or raises `ValueError`. Input that parses but is ambiguous
(for example ``03/04/2026``) is returned with a reduced ``confidence_factor`` and a note,
so downstream code never has to guess silently.
"""

from __future__ import annotations

import calendar
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

AMBIGUOUS_DATE_FACTOR = 0.6
_TWO_PLACES = Decimal("0.01")
_MINUS = "-\u2212\u2013"


@dataclass(frozen=True, slots=True)
class Parsed[T]:
    value: T
    confidence_factor: float = 1.0
    note: str | None = None


Parser = Callable[[str], Parsed[Any]]


def collapse_ws(text: str) -> str:
    return " ".join(text.split())


# --------------------------------------------------------------------------- text

_BLANK = re.compile(r"[\s_.\-\u2013\u2014]*|n/?a|none|tbd|tba", re.IGNORECASE)


def parse_text(raw: str) -> Parsed[str]:
    """Free text such as a name or description. Rejects blank form fields like '______'."""
    text = collapse_ws(raw)
    if _BLANK.fullmatch(text):
        raise ValueError("blank form field")
    return Parsed(text)


def parse_identifier(raw: str) -> Parsed[str]:
    """Short identifier such as 'CO-014'. Rejects values that look like prose."""
    text = collapse_ws(raw).strip(" .,;:#")
    if not text or _BLANK.fullmatch(text):
        raise ValueError("blank identifier")
    if len(text) > 30 or ":" in text:
        raise ValueError("does not look like an identifier")
    return Parsed(text)


# -------------------------------------------------------------------------- money

_MONEY = re.compile(
    rf"""
    (?P<open>\()?\s*
    (?P<neg1>[{_MINUS}])?\s*
    (?:USD|US)?\s*(?P<cur>[$€£])?\s*
    (?P<neg2>[{_MINUS}])?\s*
    (?P<num>\d{{1,3}}(?:,\d{{3}})+(?:\.\d{{1,2}})?|\d+(?:\.\d{{1,2}})?)
    \s*(?P<close>\))?\s*(?P<cr>CR\b)?
    """,
    re.VERBOSE | re.IGNORECASE,
)


def parse_money(raw: str) -> Parsed[Decimal]:
    """Parse '$12,450.00', '(3,200.00)', '-$3,200', '3,200.00 CR'. Credits are negative."""
    text = raw.strip()
    match = _MONEY.match(text)
    if match is None:
        raise ValueError("no amount found")
    if re.search(r"\d", text[match.end() :]):
        raise ValueError("more than one number in amount")
    amount = Decimal(match["num"].replace(",", "")).quantize(_TWO_PLACES)
    negative = bool(
        match["neg1"] or match["neg2"] or (match["open"] and match["close"]) or match["cr"]
    )
    return Parsed(-amount if negative else amount)


# --------------------------------------------------------------------------- dates

_MONTH_BY_PREFIX = {
    name[:3].lower(): number for number, name in enumerate(calendar.month_name) if name
}
_ISO = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
_NUMERIC = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4}|\d{2})\b")
_MONTH_FIRST = re.compile(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b")
_DAY_FIRST = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?[\s-]+(?:of\s+)?([A-Za-z]{3,9})\.?,?[\s-]+(\d{4})\b"
)


def _month_number(name: str) -> int:
    number = _MONTH_BY_PREFIX.get(name[:3].lower())
    if number is None or not calendar.month_name[number].lower().startswith(name.lower()):
        raise ValueError(f"unknown month {name!r}")
    return number


def _full_year(year: int) -> int:
    if year >= 100:
        return year
    return year + (2000 if year < 70 else 1900)


def _numeric_date(first: int, second: int, year: int, *, day_first: bool, raw: str) -> Parsed[date]:
    year = _full_year(year)
    if first > 12 and second > 12:
        raise ValueError("neither part can be a month")
    if first > 12:
        return Parsed(date(year, second, first))
    if second > 12 or first == second:
        return Parsed(date(year, first, second))
    month, day = (second, first) if day_first else (first, second)
    order = "day-first" if day_first else "month-first"
    note = f"{raw!r} is ambiguous (day/month order); read as {order}"
    return Parsed(date(year, month, day), AMBIGUOUS_DATE_FACTOR, note)


def parse_date(raw: str, *, day_first: bool = False) -> Parsed[date]:
    """Parse ISO, numeric (US month-first by default) and named-month dates."""
    text = collapse_ws(raw)
    if match := _ISO.search(text):
        year, month, day = (int(part) for part in match.groups())
        return Parsed(date(year, month, day))
    for match in _MONTH_FIRST.finditer(text):
        try:
            month = _month_number(match[1])
        except ValueError:
            continue
        return Parsed(date(int(match[3]), month, int(match[2])))
    for match in _DAY_FIRST.finditer(text):
        try:
            month = _month_number(match[2])
        except ValueError:
            continue
        return Parsed(date(int(match[3]), month, int(match[1])))
    if match := _NUMERIC.search(text):
        first, second, year = (int(part) for part in match.groups())
        return _numeric_date(first, second, year, day_first=day_first, raw=match[0])
    raise ValueError("no date found")


# --------------------------------------------------------------------------- days

_NO_CHANGE = re.compile(
    r"(?:no\s+change|no\s+impact|none|nil|zero|unchanged)\b|[-\u2013\u2014]$", re.I
)
_DAYS = re.compile(r"(\d+)\)?\s*(?:calendar\s+|working\s+|business\s+|work\s+)?days?\b", re.I)
_BARE_NUMBER = re.compile(r"[+\-\u2212\u2013(]?\s*(\d+)\s*\)?")
_DECREASE = re.compile(
    r"\b(?:reduc\w*|decreas\w*|credit\w*|earlier|accelerat\w*|shorten\w*)\b|^\s*[-\u2212\u2013(]",
    re.I,
)


def parse_days(raw: str) -> Parsed[int]:
    """Parse a schedule impact. 'Reduction of 2 days' -> -2, 'None' -> 0, 'Add 3 days' -> 3.

    The unit (calendar vs working days) is not captured; it stays visible in the evidence.
    """
    text = collapse_ws(raw)
    if _NO_CHANGE.match(text):
        return Parsed(0)
    match = _DAYS.search(text) or _BARE_NUMBER.fullmatch(text)
    if match is None:
        raise ValueError("no day count found")
    days = int(match[1])
    return Parsed(-days if _DECREASE.search(text) else days)
