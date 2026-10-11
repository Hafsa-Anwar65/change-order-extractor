"""Split a packet (several change orders in one file) into one text per change order.

A new change order starts at the first line that carries a change-order number not seen
before, moved up to a title line ("CHANGE ORDER") directly above it when there is one. The
same number repeated on a later page does not start a new order.
"""

from __future__ import annotations

import re
from itertools import pairwise

from co_extract.extractors.labels import match_label, split_columns
from co_extract.normalize import parse_identifier

_TITLE = re.compile(r"^\W*(?:contract\s+)?change\s+order(?:\s+(?:form|request|summary))?\W*$", re.I)
_TITLE_LOOKBACK = 3


def _number_on(line: str) -> str | None:
    for piece in split_columns(line):
        hit = match_label(piece)
        if hit is None or hit.field != "change_order_number" or not hit.rest:
            continue
        try:
            return parse_identifier(hit.rest).value
        except ValueError:
            continue
    return None


def _block_start(lines: list[str], index: int) -> int:
    for above in range(index - 1, max(index - _TITLE_LOOKBACK, 0) - 1, -1):
        if _TITLE.match(lines[above].strip()):
            return above
    return index


def split_change_orders(text: str) -> list[str]:
    lines = text.splitlines()
    seen: set[str] = set()
    starts: list[int] = []
    for index, line in enumerate(lines):
        number = _number_on(line)
        if number is None or number.casefold() in seen:
            continue
        seen.add(number.casefold())
        if len(seen) > 1:
            starts.append(_block_start(lines, index))
    if not starts:
        return [text]
    bounds = [0, *starts, len(lines)]
    chunks = ("\n".join(lines[a:b]).strip("\n") for a, b in pairwise(bounds))
    return [chunk for chunk in chunks if chunk.strip()]
