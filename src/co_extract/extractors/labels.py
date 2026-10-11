"""Label lexicon: recognises "Label: value" at the start of a line and column breaks.

Every label of every field (plus the ignore-list) is compiled into one alternation, longest
label first, so a single anchored match decides which field a line belongs to.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from co_extract.fields import FIELDS, IGNORED_LABELS

PRIMARY_CONFIDENCE = 0.92
WEAK_CONFIDENCE = 0.72

_LINE_DECORATION = " \t|*•·>-\u2013"
_DELIMITER = re.compile(r"^\s*(?:[:|]|\.{2,}|[-\u2013\u2014](?=\s))?\s*")


@dataclass(frozen=True, slots=True)
class LabelHit:
    field: str | None  # None for ignored labels
    confidence: float
    rest: str  # text after the label and its delimiter; empty for a bare label


def _label_key(label: str) -> str:
    return re.sub(r"[.\s]+", " ", label.lower()).strip()


def _label_regex(label: str) -> str:
    return r"\s+".join(re.escape(token) + r"\.?" for token in label.split())


def _build_label_table() -> tuple[str, dict[str, tuple[str | None, float]]]:
    """Return (regex alternation of every label, label key -> (field, confidence))."""
    table: dict[str, tuple[str | None, float]] = {}
    labels: list[str] = []

    def register(label: str, field: str | None, confidence: float) -> None:
        key = _label_key(label)
        if key in table:
            raise ValueError(f"label {label!r} is registered twice")
        table[key] = (field, confidence)
        labels.append(label)

    for spec in FIELDS:
        for label in spec.labels:
            register(label, spec.name, PRIMARY_CONFIDENCE)
        for label in spec.weak_labels:
            register(label, spec.name, WEAK_CONFIDENCE)
    for label in IGNORED_LABELS:
        register(label, None, 0.0)

    # Longest label first, so "net change by this change order" beats "net change".
    labels.sort(key=len, reverse=True)
    return "|".join(_label_regex(label) for label in labels), table


_ALTERNATIVES, _LABEL_TABLE = _build_label_table()
_LABEL_PATTERN = re.compile(rf"^(?P<label>{_ALTERNATIVES})(?![A-Za-z0-9])", re.IGNORECASE)
# A wide gap followed by "Label:" starts a new column ("CO # 07      Dated: 14 March 2026").
# Requiring the colon keeps prose such as "...request.  Owner to confirm" in one piece.
_COLUMN_BREAK = re.compile(rf"(?:\t|\s{{2,}})(?=(?:{_ALTERNATIVES})\s*[:|])", re.IGNORECASE)


def match_label(line: str) -> LabelHit | None:
    """Return the label at the start of `line`, or None if the line does not start with one."""
    cleaned = line.strip().replace("**", "").lstrip(_LINE_DECORATION)
    match = _LABEL_PATTERN.match(cleaned)
    if match is None:
        return None
    field, confidence = _LABEL_TABLE[_label_key(match["label"])]
    rest = _DELIMITER.sub("", cleaned[match.end() :], count=1)
    return LabelHit(field, confidence, rest.strip(" \t|"))


def split_columns(line: str) -> list[str]:
    """Split side-by-side 'Label: value' columns onto separate pieces."""
    return _COLUMN_BREAK.split(line.strip())
