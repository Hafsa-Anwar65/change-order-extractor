"""Deterministic, label-driven extractor.

`layout.to_lines` first normalises awkward layouts (columns, tables, label-then-value runs),
then every line is checked for a known label at its start (longest label wins). The value is
whatever follows the label on the same line, or on the following line(s) when the label
stands alone. Sentence-style forms ("The Contract Sum will be increased by this Change Order
in the amount of $...") are handled by per-field fallback patterns.

Limitations are deliberate and documented in WRITEUP.md: labels it has never seen and
Damaged labels (e.g. "0RDER") are missed. The LLM extractor exists to cover those.
"""

from __future__ import annotations

import re
from collections import defaultdict

from co_extract.extractors.base import Candidate
from co_extract.extractors.labels import match_label
from co_extract.extractors.layout import Line, to_lines
from co_extract.fields import FIELD_BY_NAME, FIELDS, FieldSpec
from co_extract.schema import Method

NEXT_LINE_PENALTY = 0.05
MAX_EVIDENCE_CHARS = 240


def _collect_value(lines: list[Line], index: int, rest: str, *, multiline: bool) -> tuple[str, str]:
    """Return (raw value, evidence) for the label found on lines[index]."""
    parts = [rest] if rest else []
    evidence = [lines[index].source.strip()]
    if parts and not multiline:
        return parts[0], evidence[0][:MAX_EVIDENCE_CHARS]
    for line in lines[index + 1 :]:
        stripped = line.text.strip()
        if not stripped or match_label(line.text) is not None:
            break
        parts.append(stripped)
        evidence.append(line.source.strip())
        if not multiline:
            break
    return " ".join(parts), " ".join(evidence)[:MAX_EVIDENCE_CHARS]


def _parses(spec: FieldSpec, raw: str) -> bool:
    try:
        spec.parser(raw)
    except ValueError:
        return False
    return True


def _fallback(spec: FieldSpec, text: str) -> Candidate | None:
    for fallback in spec.fallbacks:
        match = re.search(fallback.pattern, text, re.IGNORECASE | re.MULTILINE)
        if match is None:
            continue
        raw = match["value"].strip()
        sign = match.groupdict().get("sign")
        if sign and sign.lower().startswith("decreas"):
            raw = f"-{raw}"
        evidence = " ".join(match.group(0).split())[:MAX_EVIDENCE_CHARS]
        return Candidate(raw, fallback.confidence, evidence, Method.RULES)
    return None


class RulesExtractor:
    name = "rules"

    def extract(self, text: str) -> dict[str, list[Candidate]]:
        lines = to_lines(text)
        found: dict[str, list[Candidate]] = defaultdict(list)

        for index, line in enumerate(lines):
            hit = match_label(line.text)
            if hit is None or hit.field is None:
                continue
            spec = FIELD_BY_NAME[hit.field]
            raw, evidence = _collect_value(lines, index, hit.rest, multiline=spec.multiline)
            if not raw:
                continue
            # A multi-line field's value normally starts on the next line, so no penalty there.
            on_next_line = not hit.rest and not spec.multiline
            confidence = hit.confidence - (NEXT_LINE_PENALTY if on_next_line else 0.0)
            found[spec.name].append(Candidate(raw, confidence, evidence, Method.RULES))

        for spec in FIELDS:
            if any(_parses(spec, c.raw) for c in found.get(spec.name, ())):
                continue  # a label already gave a usable value; .get() avoids empty entries
            if candidate := _fallback(spec, text):
                found[spec.name].append(candidate)
        return dict(found)
