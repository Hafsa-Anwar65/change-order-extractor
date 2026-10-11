from __future__ import annotations

import pytest

from co_extract.extractors.labels import PRIMARY_CONFIDENCE, WEAK_CONFIDENCE
from co_extract.extractors.rules import NEXT_LINE_PENALTY, RulesExtractor
from co_extract.fields import WEAK_PATTERN_CONFIDENCE


def extract(text: str) -> dict[str, list[tuple[str, float]]]:
    found = RulesExtractor().extract(text)
    return {name: [(c.raw, c.confidence) for c in cands] for name, cands in found.items()}


def test_same_line_label() -> None:
    assert extract("Contractor: Acme Builders Inc.") == {
        "contractor": [("Acme Builders Inc.", PRIMARY_CONFIDENCE)]
    }


def test_labels_are_case_insensitive_and_tolerate_decoration() -> None:
    assert extract("**CONTRACTOR:** Acme\n| Owner | City Hall |") == {
        "contractor": [("Acme", PRIMARY_CONFIDENCE)],
        "owner": [("City Hall", PRIMARY_CONFIDENCE)],
    }


def test_value_on_next_line_costs_a_little_confidence() -> None:
    result = extract("Contractor\nAcme Builders")
    assert result == {"contractor": [("Acme Builders", PRIMARY_CONFIDENCE - NEXT_LINE_PENALTY)]}


def test_next_line_is_not_taken_when_it_is_another_label() -> None:
    assert extract("Contractor\nOwner: City Hall") == {"owner": [("City Hall", PRIMARY_CONFIDENCE)]}


def test_wide_gap_splits_side_by_side_columns() -> None:
    result = extract("CO #  07                      Dated: 14 March 2026")
    assert result["change_order_number"] == [("07", PRIMARY_CONFIDENCE)]
    assert result["date"] == [("14 March 2026", PRIMARY_CONFIDENCE)]


def test_wide_gap_inside_prose_is_not_split() -> None:
    text = "Description of Change:\nPer owner request.  Owner to confirm pricing."
    candidates = extract(text)["description"]
    assert len(candidates) == 1  # one description, and no stray "owner" field was split off
    assert " ".join(candidates[0][0].split()) == "Per owner request. Owner to confirm pricing."
    assert "owner" not in extract(text)


def test_longest_label_wins() -> None:
    assert extract("Net Change by This Change Order: $5.00") == {
        "amount": [("$5.00", PRIMARY_CONFIDENCE)]
    }


def test_ignored_label_does_not_leak_into_shorter_label() -> None:
    text = "Project No. 24-1187\nProject: Riverside Tower"
    assert extract(text) == {"project_name": [("Riverside Tower", PRIMARY_CONFIDENCE)]}


def test_label_must_end_at_a_word_boundary() -> None:
    assert extract("Projection: 5 units") == {}
    assert extract("Datelined: Tuesday") == {}


def test_negative_sign_is_preserved() -> None:
    assert extract("Net Change: -$3,200.00")["amount"][0][0] == "-$3,200.00"


def test_blank_form_field_is_not_filled_from_the_next_line() -> None:
    result = extract("Contractor: ________\nSome stray line")
    assert result["contractor"][0][0] == "________"  # rejected later by the parser
    assert "Some stray line" not in str(result)


def test_multiline_description_stops_at_blank_line_and_at_next_label() -> None:
    text = "Description of Change:\nline one\nline two\n\nunrelated\n"
    assert extract(text)["description"][0][0] == "line one line two"
    text = "Description of Change:\nline one\nAmount: $1.00"
    assert extract(text)["description"][0][0] == "line one"


def test_description_is_not_penalised_for_starting_on_the_next_line() -> None:
    assert extract("Description of Change:\nsome work")["description"][0][1] == PRIMARY_CONFIDENCE


def test_weak_label_has_lower_confidence() -> None:
    assert extract("Amount: $10.00") == {"amount": [("$10.00", WEAK_CONFIDENCE)]}


def test_fallback_pattern_finds_bare_change_order_token() -> None:
    assert extract("Please see CO-014 attached.") == {
        "change_order_number": [("CO-014", WEAK_PATTERN_CONFIDENCE)]
    }


def test_fallback_is_skipped_when_a_label_matched() -> None:
    result = extract("Change Order No.: 7\nSee also CO-99")
    assert result["change_order_number"] == [("7", PRIMARY_CONFIDENCE)]


def test_repeated_label_yields_every_candidate() -> None:
    result = extract("Net Change: $1.00\nNet Change: $2.00")
    assert [raw for raw, _ in result["amount"]] == ["$1.00", "$2.00"]


@pytest.mark.parametrize("text", ["", "\n\n", "no labels here at all", "::: ||| ---"])
def test_garbage_yields_nothing(text: str) -> None:
    assert extract(text) == {}
