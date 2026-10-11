from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from co_extract.fields import FIELDS
from co_extract.schema import Extracted, Issue, Method, Severity
from co_extract.validation import (
    check_fields,
    derive_amount,
    needs_review,
    overall_confidence,
)

TODAY = date(2026, 10, 11)


def make_fields(confidence: float = 0.9, **values: Any) -> dict[str, Extracted[Any]]:
    fields = {spec.name: Extracted[Any]() for spec in FIELDS}
    for name, value in values.items():
        fields[name] = Extracted[Any](value=value, confidence=confidence, method=Method.RULES)
    return fields


def complete_fields(confidence: float = 0.9, **overrides: Any) -> dict[str, Extracted[Any]]:
    base: dict[str, Any] = {
        "change_order_number": "CO-1",
        "date": date(2026, 3, 1),
        "project_name": "Tower",
        "contractor": "Acme",
        "description": "Extra footings",
        "amount": Decimal("100.00"),
    }
    return make_fields(confidence, **{**base, **overrides})


def codes(issues: list[Issue]) -> list[str]:
    return [issue.code for issue in issues]


# ------------------------------------------------------------------ derive_amount
def test_amount_is_derived_from_the_contract_sums() -> None:
    fields = make_fields(
        contract_sum_before=Decimal("1000.00"), contract_sum_after=Decimal("1250.50")
    )
    issues = derive_amount(fields)
    assert fields["amount"].value == Decimal("250.50")
    assert fields["amount"].method is Method.DERIVED
    assert fields["amount"].confidence == 0.72  # 0.9 * 0.8
    assert codes(issues) == ["derived_field"]


def test_amount_is_not_derived_when_present_or_when_inputs_are_missing() -> None:
    present = make_fields(
        amount=Decimal("1"), contract_sum_before=Decimal("1"), contract_sum_after=Decimal("9")
    )
    assert derive_amount(present) == []
    assert present["amount"].value == Decimal("1")
    assert derive_amount(make_fields(contract_sum_before=Decimal("1"))) == []


def test_contract_sum_after_is_derived_from_before_and_amount() -> None:
    fields = make_fields(contract_sum_before=Decimal("1000.00"), amount=Decimal("250.50"))
    issues = derive_amount(fields)
    assert fields["contract_sum_after"].value == Decimal("1250.50")
    assert fields["contract_sum_after"].method is Method.DERIVED
    assert fields["contract_sum_after"].confidence == 0.72  # 0.9 * 0.8
    assert codes(issues) == ["derived_field"]
    assert issues[0].field == "contract_sum_after"


# ------------------------------------------------------------------ check_fields
def test_complete_document_has_no_issues() -> None:
    assert check_fields(complete_fields(), today=TODAY) == []


def test_missing_required_fields_are_errors() -> None:
    issues = check_fields(make_fields(), today=TODAY)
    missing = {i.field for i in issues if i.code == "missing_required_field"}
    assert missing == {s.name for s in FIELDS if s.required}
    assert all(i.severity is Severity.ERROR for i in issues)


def test_optional_fields_may_be_missing() -> None:
    issues = check_fields(complete_fields(), today=TODAY)
    assert not any(i.field in {"owner", "schedule_impact_days"} for i in issues)


def test_contract_sum_arithmetic_mismatch_is_an_error() -> None:
    fields = complete_fields(
        contract_sum_before=Decimal("1000.00"), contract_sum_after=Decimal("1200.00")
    )
    issues = check_fields(fields, today=TODAY)
    assert codes(issues) == ["contract_sum_mismatch"]
    assert issues[0].severity is Severity.ERROR


def test_contract_sum_arithmetic_ok() -> None:
    fields = complete_fields(
        contract_sum_before=Decimal("1000.00"), contract_sum_after=Decimal("1100.00")
    )
    assert check_fields(fields, today=TODAY) == []


def test_implausible_dates_are_warned() -> None:
    far_future = check_fields(complete_fields(date=date(2030, 1, 1)), today=TODAY)
    ancient = check_fields(complete_fields(date=date(1985, 1, 1)), today=TODAY)
    assert codes(far_future) == codes(ancient) == ["implausible_date"]
    assert check_fields(complete_fields(date=date(2026, 12, 1)), today=TODAY) == []


def test_positive_amount_with_credit_wording_is_warned() -> None:
    fields = complete_fields(description="Credit to owner for deleted work")
    assert codes(check_fields(fields, today=TODAY)) == ["possible_sign_error"]


def test_negative_amount_with_addition_wording_is_warned() -> None:
    fields = complete_fields(amount=Decimal("-5.00"), description="Additional footings")
    assert codes(check_fields(fields, today=TODAY)) == ["possible_sign_error"]


def test_mixed_wording_is_not_second_guessed() -> None:
    fields = complete_fields(description="Delete carpet and add tile")
    assert check_fields(fields, today=TODAY) == []


# ----------------------------------------------------------- confidence and review
def test_overall_confidence_is_the_weakest_required_field() -> None:
    fields = complete_fields()
    fields["date"] = Extracted[Any](value=date(2026, 3, 1), confidence=0.55, method=Method.RULES)
    assert overall_confidence(fields) == 0.55


def test_missing_required_field_zeroes_overall_confidence() -> None:
    assert overall_confidence(make_fields()) == 0.0


def test_needs_review_rules() -> None:
    fields = complete_fields(confidence=0.8)
    assert needs_review(fields, [], min_confidence=0.7) is False
    assert needs_review(fields, [], min_confidence=0.9) is True  # below the bar
    error = Issue(code="x", severity=Severity.ERROR, message="m")
    warning = Issue(code="x", severity=Severity.WARNING, message="m")
    ocr_warning = Issue(code="ocr_text", severity=Severity.WARNING, message="m")
    assert needs_review(fields, [error], min_confidence=0.7) is True
    assert needs_review(fields, [warning], min_confidence=0.7) is False
    assert needs_review(fields, [ocr_warning], min_confidence=0.7) is True
