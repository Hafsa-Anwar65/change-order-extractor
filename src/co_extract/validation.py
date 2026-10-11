"""Cross-field checks that no single extractor can do on its own."""

from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from co_extract.fields import FIELDS
from co_extract.schema import Extracted, Issue, Method, Severity

DEFAULT_MIN_CONFIDENCE = 0.70
DERIVED_CONFIDENCE_FACTOR = 0.80
MIN_PLAUSIBLE_YEAR = 1990
MAX_FUTURE_DAYS = 365

Fields = dict[str, Extracted[Any]]

_CREDIT_WORDS = re.compile(r"\b(?:credit\w*|deduct\w*|reduc\w*|decreas\w*|delete[ds]?)\b", re.I)
_ADDITION_WORDS = re.compile(
    r"\b(?:additional|add(?:s|ed|ing)?|increas\w*|extra|upgrad\w*)\b", re.I
)


def derive_amount(fields: Fields) -> list[Issue]:
    """Derive missing arithmetic fields from the two that are present."""
    amount, before, after = (
        fields[n] for n in ("amount", "contract_sum_before", "contract_sum_after")
    )
    issues: list[Issue] = []
    if amount.value is None and before.value is not None and after.value is not None:
        fields["amount"] = Extracted[Any](
            value=after.value - before.value,
            confidence=round(
                min(before.confidence, after.confidence) * DERIVED_CONFIDENCE_FACTOR, 2
            ),
            evidence="contract_sum_after - contract_sum_before",
            method=Method.DERIVED,
        )
        issues.append(
            Issue(
                code="derived_field",
                severity=Severity.WARNING,
                message="amount was not found directly; derived from the contract sums",
                field="amount",
            )
        )
    if after.value is None and before.value is not None and amount.value is not None:
        fields["contract_sum_after"] = Extracted[Any](
            value=before.value + amount.value,
            confidence=round(
                min(before.confidence, amount.confidence) * DERIVED_CONFIDENCE_FACTOR, 2
            ),
            evidence="contract_sum_before + amount",
            method=Method.DERIVED,
        )
        issues.append(
            Issue(
                code="derived_field",
                severity=Severity.WARNING,
                message="contract_sum_after was not found directly; derived from before + amount",
                field="contract_sum_after",
            )
        )
    return issues


def check_fields(fields: Fields, *, today: date) -> list[Issue]:
    return [
        *_missing_required(fields),
        *_check_date(fields["date"], today),
        *_check_arithmetic(fields),
        *_check_sign(fields),
    ]


def _missing_required(fields: Fields) -> list[Issue]:
    return [
        Issue(
            code="missing_required_field",
            severity=Severity.ERROR,
            message=f"{spec.name} was not found",
            field=spec.name,
        )
        for spec in FIELDS
        if spec.required and fields[spec.name].value is None
    ]


def _check_date(field: Extracted[Any], today: date) -> list[Issue]:
    value: date | None = field.value
    if value is None:
        return []
    if value.year < MIN_PLAUSIBLE_YEAR or value > today + timedelta(days=MAX_FUTURE_DAYS):
        return [
            Issue(
                code="implausible_date",
                severity=Severity.WARNING,
                message=f"{value.isoformat()} is outside the plausible range",
                field="date",
            )
        ]
    return []


def _check_arithmetic(fields: Fields) -> list[Issue]:
    before, amount, after = (
        fields[n].value for n in ("contract_sum_before", "amount", "contract_sum_after")
    )
    if before is None or amount is None or after is None:
        return []
    expected: Decimal = before + amount
    if expected == after:
        return []
    return [
        Issue(
            code="contract_sum_mismatch",
            severity=Severity.ERROR,
            message=f"{before} + {amount} = {expected}, but the document states {after}",
        )
    ]


def _check_sign(fields: Fields) -> list[Issue]:
    amount, description = fields["amount"].value, fields["description"].value
    if amount is None or description is None or amount == 0:
        return []
    credit, addition = _CREDIT_WORDS.search(description), _ADDITION_WORDS.search(description)
    if amount > 0 and credit and not addition:
        hint = f"description says {credit[0]!r} but the amount is positive"
    elif amount < 0 and addition and not credit:
        hint = f"description says {addition[0]!r} but the amount is negative"
    else:
        return []
    return [
        Issue(code="possible_sign_error", severity=Severity.WARNING, message=hint, field="amount")
    ]


def overall_confidence(fields: Fields) -> float:
    """The weakest required field. Missing required fields count as 0."""
    required = [fields[spec.name] for spec in FIELDS if spec.required]
    return min((f.confidence if f.value is not None else 0.0) for f in required)


def needs_review(fields: Fields, issues: list[Issue], min_confidence: float) -> bool:
    has_error = any(issue.severity is Severity.ERROR for issue in issues)
    has_ocr_text = any(issue.code == "ocr_text" for issue in issues)
    return has_error or has_ocr_text or overall_confidence(fields) < min_confidence
