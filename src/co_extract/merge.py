"""Resolve the candidates for one field into a single typed value with a confidence.

Policy, in order:
1. Parse every candidate; unparseable ones are dropped (and reported only if nothing survives).
2. The highest-confidence candidate wins.
3. An *independent* extractor (a different method) that agrees raises confidence (noisy-OR).
4. A rival value of comparable confidence lowers it and raises an issue.
5. Ambiguity found while parsing (e.g. 03/04/2026) is applied last, so agreement between
   extractors that read the same ambiguous string cannot launder the ambiguity away.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from math import prod
from typing import Any

from co_extract.extractors.base import Candidate
from co_extract.fields import FieldSpec
from co_extract.normalize import Parsed
from co_extract.schema import Extracted, Issue, Method, Severity

logger = logging.getLogger(__name__)

CONFLICT_MARGIN = 0.15  # a rival within this much of the best counts as a real conflict
CONFLICT_FACTOR = 0.60
MAX_CONFIDENCE = 0.99
_MIN_CONTAINMENT_CHARS = 12


@dataclass(frozen=True, slots=True)
class _Resolved:
    candidate: Candidate
    parsed: Parsed[Any]

    @property
    def score(self) -> float:
        return self.candidate.confidence * self.parsed.confidence_factor


def _squash(text: str) -> str:
    return re.sub(r"[\W_]+", " ", text.casefold()).strip()


def same_value(left: Any, right: Any) -> bool:
    """Equality that tolerates trivial differences in long free text ('Inc.' vs 'Inc')."""
    if isinstance(left, str) and isinstance(right, str):
        a, b = _squash(left), _squash(right)
        if a == b:
            return True
        shorter, longer = sorted((a, b), key=len)
        return len(shorter) >= _MIN_CONTAINMENT_CHARS and shorter in longer
    return bool(left == right)


def _noisy_or(*confidences: float) -> float:
    return 1.0 - prod(1.0 - c for c in confidences)


# A figure that is printed but cannot be read (typically noisy text such as "$l2,450.00") is an
# error on the money fields: the document holds a number we do not have, even when the sum
# check or a derivation hides the gap. Elsewhere ("Schedule Impact: TBD") it is only a warning.
_UNREADABLE_IS_ERROR = frozenset({"amount", "contract_sum_before", "contract_sum_after"})


def resolve_field(
    spec: FieldSpec, candidates: Sequence[Candidate]
) -> tuple[Extracted[Any], list[Issue]]:
    resolved: list[_Resolved] = []
    failures: list[Issue] = []
    for candidate in candidates:
        try:
            resolved.append(_Resolved(candidate, spec.parser(candidate.raw)))
        except ValueError as exc:
            message = f"{candidate.method} read {candidate.raw!r} but it could not be parsed: {exc}"
            failures.append(
                Issue(
                    code="unparseable_value",
                    severity=Severity.WARNING,
                    message=message,
                    field=spec.name,
                )
            )
    if not resolved:
        if spec.name in _UNREADABLE_IS_ERROR:
            failures = [f.model_copy(update={"severity": Severity.ERROR}) for f in failures]
        return Extracted[Any](), failures

    ranked = sorted(
        resolved, key=lambda item: item.score, reverse=True
    )  # stable: earlier wins ties
    best, rivals = ranked[0], ranked[1:]
    issues: list[Issue] = []

    confidence = best.candidate.confidence
    method = best.candidate.method
    agreeing = [r for r in rivals if same_value(r.parsed.value, best.parsed.value)]
    independent = [r for r in agreeing if r.candidate.method != best.candidate.method]
    if independent:
        confidence = _noisy_or(confidence, *(r.candidate.confidence for r in independent))
        method = Method.MERGED

    conflicting = [
        r
        for r in rivals
        if not same_value(r.parsed.value, best.parsed.value)
        and r.score >= best.score - CONFLICT_MARGIN
    ]
    if conflicting:
        confidence *= CONFLICT_FACTOR
        others = ", ".join(repr(r.candidate.raw) for r in conflicting)
        issues.append(
            Issue(
                code="conflicting_values",
                severity=Severity.WARNING,
                message=f"chose {best.candidate.raw!r} over {others}",
                field=spec.name,
            )
        )

    confidence *= best.parsed.confidence_factor
    if best.parsed.note:
        issues.append(
            Issue(
                code="ambiguous_value",
                severity=Severity.WARNING,
                message=best.parsed.note,
                field=spec.name,
            )
        )

    extracted = Extracted[Any](
        value=best.parsed.value,
        confidence=round(min(confidence, MAX_CONFIDENCE), 2),
        evidence=best.candidate.evidence or None,
        method=method,
    )
    return extracted, issues
