"""Extractor contract. Extractors find raw strings; parsing and merging happen elsewhere."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from co_extract.schema import Method


@dataclass(frozen=True, slots=True)
class Candidate:
    """A raw (unparsed) value an extractor believes belongs to a field."""

    raw: str
    confidence: float  # the extractor's own trust in this being the right span, 0..1
    evidence: str  # source text the value was read from
    method: Method


class Extractor(Protocol):
    name: str

    def extract(self, text: str) -> dict[str, list[Candidate]]:
        """Return candidates per field name. Fields it found nothing for may be omitted.

        Raises ExtractorError if it cannot run at all.
        """
        ...
