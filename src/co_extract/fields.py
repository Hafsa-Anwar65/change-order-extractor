"""Single source of truth for the fields we extract.

The rules extractor, the LLM prompt, the merge step and the validators are all driven from
`FIELDS`, so adding a field means adding one `FieldSpec` here and one attribute on
`schema.ChangeOrder`.
"""

from __future__ import annotations

from dataclasses import dataclass

from co_extract.normalize import (
    Parser,
    parse_date,
    parse_days,
    parse_identifier,
    parse_money,
    parse_text,
)

WEAK_PATTERN_CONFIDENCE = 0.60  # a bare token that merely looks right, e.g. "CO-014" anywhere
SENTENCE_CONFIDENCE = (
    0.85  # a full form sentence, e.g. "...will be increased by this Change Order..."
)


@dataclass(frozen=True, slots=True)
class Fallback:
    """Regex tried when no label gave a usable value; needs a (?P<value>) group."""

    pattern: str
    confidence: float


@dataclass(frozen=True, slots=True)
class FieldSpec:
    name: str
    description: str  # shown to the LLM
    parser: Parser
    labels: tuple[str, ...]  # unambiguous labels -> high confidence
    weak_labels: tuple[str, ...] = ()  # generic labels -> lower confidence
    fallbacks: tuple[Fallback, ...] = ()
    required: bool = False
    multiline: bool = False


# Sentence-style forms (AIA G701): "The Contract Sum will be increased by this Change Order in
# the amount of $18,750.00". `value` is the number; `sign` negates it for "decreased".
_MONEY = r"(?P<value>\(?[-\u2212]?\s*\$?\s*\d[\d,]*(?:\.\d{1,2})?\)?)"
_SIGN = r"(?P<sign>increased|decreased|unchanged)"
_AMOUNT_SENTENCE = (
    r"contract\s+sum\s+(?:will\s+be|is|shall\s+be)\s+"
    + _SIGN
    + r"\s+by\s+this\s+change\s+order\s+in\s+the\s+amount\s+of:?\s*"
    + _MONEY
)
_BEFORE_SENTENCE = r"contract\s+sum\s+prior\s+to\s+this\s+change\s+order\s+(?:was|is):?\s*" + _MONEY
_AFTER_SENTENCE = (
    r"new\s+contract\s+sum\s+including\s+this\s+change\s+order\s+"
    r"(?:will\s+be|is|shall\s+be):?\s*" + _MONEY
)
_DAYS_SENTENCE = (
    r"contract\s+time\s+(?:will\s+be|is|shall\s+be)\s+"
    + _SIGN
    + r"\s+by\s+(?:[a-z-]+\s+)?\(?(?P<value>\d+)\)?\s*(?:calendar\s+)?days?"
)

FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec(
        name="change_order_number",
        description="The change order's own number or identifier, e.g. 'CO-014' or '7'.",
        parser=parse_identifier,
        labels=(
            "change order no",
            "change order number",
            "change order #",
            "change order id",
            "co no",
            "co number",
            "co #",
            "co#",
            "c.o. no",
            "c.o. number",
            "c.o. #",
        ),
        fallbacks=(
            Fallback(r"\b(?P<value>(?:CO|PCO|COR)[-\s#]?\d{1,5}[A-Z]?)\b", WEAK_PATTERN_CONFIDENCE),
            Fallback(
                r"^\s*change\s+order\s+(?P<value>(?=[A-Z0-9-]*\d)[A-Z0-9-]{1,15})\s*$",
                WEAK_PATTERN_CONFIDENCE,
            ),
        ),
        required=True,
    ),
    FieldSpec(
        name="date",
        description="The date the change order was issued or dated.",
        parser=parse_date,
        labels=(
            "change order date",
            "date of change order",
            "date issued",
            "issue date",
            "date of issue",
            "date of issuance",
            "dated",
            "date",
        ),
        required=True,
    ),
    FieldSpec(
        name="project_name",
        description="The name of the construction project (not the project number).",
        parser=parse_text,
        labels=("project name", "project title", "project", "job name", "job"),
        required=True,
    ),
    FieldSpec(
        name="owner",
        description="The project owner or client.",
        parser=parse_text,
        labels=("owner name", "owner", "client"),
    ),
    FieldSpec(
        name="contractor",
        description="The (general) contractor performing the work.",
        parser=parse_text,
        labels=(
            "contractor name",
            "contractor's name",
            "general contractor",
            "prime contractor",
            "contractor",
            "gc",
        ),
        required=True,
    ),
    FieldSpec(
        name="description",
        description="The full description of the change in scope. Copy it completely.",
        parser=parse_text,
        labels=(
            "description of changes",
            "description of change",
            "change description",
            "work description",
            "description",
            "scope of change",
            "scope of work",
            "reason for change",
        ),
        weak_labels=("scope",),
        required=True,
        multiline=True,
    ),
    FieldSpec(
        name="amount",
        description=(
            "The net monetary change caused by THIS change order. Keep the sign as printed: "
            "a credit or deduction (parentheses or minus) is negative."
        ),
        parser=parse_money,
        labels=(
            "net change by this change order",
            "net change in contract sum",
            "net change to contract sum",
            "total change order amount",
            "change order amount",
            "this change order amount",
            "amount of this change order",
            "total of this change order",
            "change order total",
            "net change",
        ),
        fallbacks=(Fallback(_AMOUNT_SENTENCE, SENTENCE_CONFIDENCE),),
        weak_labels=("total amount", "amount", "total"),
        required=True,
    ),
    FieldSpec(
        name="contract_sum_before",
        description="The contract sum immediately BEFORE this change order is applied.",
        parser=parse_money,
        labels=(
            "contract sum prior to this change order",
            "contract sum prior to change order",
            "contract sum before this change order",
            "previous contract sum",
            "prior contract sum",
            "current contract sum",
        ),
        fallbacks=(Fallback(_BEFORE_SENTENCE, SENTENCE_CONFIDENCE),),
    ),
    FieldSpec(
        name="contract_sum_after",
        description="The contract sum AFTER this change order is applied.",
        parser=parse_money,
        labels=(
            "new contract sum including this change order",
            "contract sum including this change order",
            "contract sum after this change order",
            "new contract sum",
            "revised contract sum",
            "adjusted contract sum",
        ),
        fallbacks=(Fallback(_AFTER_SENTENCE, SENTENCE_CONFIDENCE),),
    ),
    FieldSpec(
        name="schedule_impact_days",
        description=(
            "Change to the contract time in days caused by this change order. "
            "Extensions are positive, reductions negative, 'none' is 0."
        ),
        parser=parse_days,
        labels=(
            "schedule impact",
            "time impact",
            "change in contract time",
            "contract time change",
            "change in time",
            "time extension",
            "days added",
            "calendar days added",
            "contract time adjustment",
            "time adjustment",
        ),
        fallbacks=(Fallback(_DAYS_SENTENCE, SENTENCE_CONFIDENCE),),
    ),
)

FIELD_BY_NAME: dict[str, FieldSpec] = {spec.name: spec for spec in FIELDS}

# Labels that share a prefix with a field label (e.g. "project no" vs "project"). Recognising
# them stops the shorter label from swallowing the line.
IGNORED_LABELS: tuple[str, ...] = (
    "project no",
    "project number",
    "project #",
    "project id",
    "owner's project no",
    "contract no",
    "contract number",
    "contract date",
    "date of contract",
    "date of substantial completion",
    "substantial completion",
    "completion date",
    "original contract sum",
    "original contract amount",
)
