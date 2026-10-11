from __future__ import annotations

from datetime import date
from decimal import Decimal

from co_extract.merge import CONFLICT_FACTOR, resolve_field, same_value
from co_extract.schema import Method, Severity
from tests.conftest import candidate, spec


def codes(issues: list) -> list[str]:
    return [issue.code for issue in issues]


def test_single_candidate_passes_through() -> None:
    field, issues = resolve_field(spec("amount"), [candidate("$100.00", 0.9)])
    assert field.value == Decimal("100.00")
    assert field.confidence == 0.9
    assert field.method is Method.RULES
    assert field.evidence == "$100.00"
    assert issues == []


def test_no_candidates_gives_an_empty_field() -> None:
    field, issues = resolve_field(spec("amount"), [])
    assert (field.value, field.confidence, field.method) == (None, 0.0, None)
    assert issues == []


def test_independent_agreement_raises_confidence_and_marks_merged() -> None:
    field, _ = resolve_field(
        spec("amount"),
        [candidate("$100.00", 0.7, Method.RULES), candidate("100", 0.7, Method.LLM)],
    )
    assert field.value == Decimal("100.00")
    assert field.confidence == 0.91  # 1 - 0.3 * 0.3
    assert field.method is Method.MERGED


def test_agreement_is_capped_below_certainty() -> None:
    field, _ = resolve_field(
        spec("amount"),
        [candidate("$1.00", 0.95, Method.RULES), candidate("$1.00", 0.95, Method.LLM)],
    )
    assert field.confidence == 0.99


def test_repeated_mentions_by_the_same_extractor_do_not_boost() -> None:
    field, _ = resolve_field(spec("amount"), [candidate("$5.00", 0.9), candidate("$5.00", 0.9)])
    assert field.confidence == 0.9
    assert field.method is Method.RULES


def test_comparable_disagreement_lowers_confidence_and_flags() -> None:
    field, issues = resolve_field(
        spec("amount"),
        [candidate("$100.00", 0.92, Method.RULES), candidate("$200.00", 0.85, Method.LLM)],
    )
    assert field.value == Decimal("100.00")  # higher confidence wins
    assert field.confidence == round(0.92 * CONFLICT_FACTOR, 2)
    assert codes(issues) == ["conflicting_values"]
    assert issues[0].severity is Severity.WARNING


def test_much_weaker_rival_is_ignored() -> None:
    field, issues = resolve_field(
        spec("amount"), [candidate("$100.00", 0.92), candidate("$200.00", 0.72)]
    )
    assert (field.value, field.confidence, issues) == (Decimal("100.00"), 0.92, [])


def test_ambiguity_is_applied_after_agreement() -> None:
    """Two extractors reading the same '03/04/2026' must not launder the ambiguity away."""
    field, issues = resolve_field(
        spec("date"),
        [candidate("03/04/2026", 0.92, Method.RULES), candidate("03/04/2026", 0.9, Method.LLM)],
    )
    assert field.value == date(2026, 3, 4)
    assert field.confidence < 0.7
    assert codes(issues) == ["ambiguous_value"]


def test_unparseable_candidates_are_reported_only_when_nothing_survives() -> None:
    field, issues = resolve_field(spec("amount"), [candidate("$l2,450.00")])
    assert field.value is None
    assert codes(issues) == ["unparseable_value"]

    field, issues = resolve_field(spec("amount"), [candidate("$l2,450.00"), candidate("$5.00")])
    assert field.value == Decimal("5.00")
    assert issues == []


def test_same_value_equality_rules() -> None:
    assert same_value("Halloran Construction Inc.", "Halloran Construction Inc")
    assert same_value("Riverside Medical Center", "Riverside Medical Center - East Wing")
    assert not same_value("CO-14", "CO-142")  # short identifiers never match by containment
    assert not same_value("CO-14", "CO-15")
    assert same_value(Decimal("1.00"), Decimal("1.0"))
    assert not same_value(1, 2)
