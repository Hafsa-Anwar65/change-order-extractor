"""Turn awkward layouts into plain "Label: value" lines before the label lexer runs.

PDF text extraction flattens forms in a few recurring ways. Each is undone here, so the lexer
only ever sees one shape:

1. side-by-side columns        ``CO # 07      Dated: 14 March 2026``      (split in labels.py)
2. a table: header row + data row    ``CO No. | Date`` / ``CO-9 | 03/01/2026``
3. a column of labels, then a column of values (one label per line, then the values)

Every rewritten line keeps its original text as `source`, which becomes the evidence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from co_extract.extractors.labels import LabelHit, match_label, split_columns

MIN_LABEL_RUN = 3  # shorter runs are ordinary "label, then its value" pairs

_CELL_SPLIT = re.compile(r"\s*\|\s*|\t+|\s{2,}")


@dataclass(frozen=True, slots=True)
class Line:
    text: str  # what the label lexer reads
    source: str  # the document's own text, shown as evidence


def to_lines(text: str) -> list[Line]:
    """Physical lines -> logical lines the label lexer can read."""
    lines = [Line(piece, piece) for raw in text.splitlines() for piece in split_columns(raw)]
    return pair_label_runs(pair_header_rows(lines))


def _cells(text: str) -> list[str]:
    return [cell for cell in _CELL_SPLIT.split(text.strip().strip("|")) if cell.strip()]


def _bare_label(text: str) -> LabelHit | None:
    """The label if `text` is a known field label with no value after it."""
    hit = match_label(text)
    return hit if hit is not None and hit.field is not None and not hit.rest else None


def pair_header_rows(lines: list[Line]) -> list[Line]:
    """Rewrite ``A | B`` over ``1 | 2`` as ``A: 1`` and ``B: 2``."""
    out: list[Line] = []
    index = 0
    while index < len(lines):
        header = _cells(lines[index].text)
        is_header = len(header) >= 2 and all(_bare_label(cell) for cell in header)
        if is_header and index + 1 < len(lines):
            values = _cells(lines[index + 1].text)
            if len(values) == len(header) and all(match_label(v) is None for v in values):
                out.extend(
                    Line(f"{h}: {v}", f"{h} | {v}") for h, v in zip(header, values, strict=True)
                )
                index += 2
                continue
        out.append(lines[index])
        index += 1
    return out


def pair_label_runs(lines: list[Line]) -> list[Line]:
    """Rewrite a run of N bare labels followed by N value lines as N ``Label: value`` lines."""
    out: list[Line] = []
    index = 0
    while index < len(lines):
        end = index
        while end < len(lines) and _bare_label(lines[end].text):
            end += 1
        count = end - index
        if count >= MIN_LABEL_RUN:
            start = end
            while start < len(lines) and not lines[start].text.strip():
                start += 1  # tolerate blank lines between the label run and the value run
            values = lines[start : start + count]
            if len(values) == count and all(
                v.text.strip() and match_label(v.text) is None for v in values
            ):
                for label, value in zip(lines[index:end], values, strict=True):
                    text = f"{label.text.strip()}: {value.text.strip()}"
                    out.append(Line(text, f"{label.source.strip()} | {value.source.strip()}"))
                index = start + count
                continue
        out.append(lines[index])
        index += 1
    return out
