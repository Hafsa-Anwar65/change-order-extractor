"""Public output contract. Everything the pipeline emits validates against these models."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Method(StrEnum):
    """How a field value was obtained."""

    RULES = "rules"
    LLM = "llm"
    MERGED = "merged"  # independent extractors agreed
    DERIVED = "derived"  # computed from other fields


class Severity(StrEnum):
    WARNING = "warning"  # worth a look, does not block automation
    ERROR = "error"  # a human must review before the data is used


class Extracted[T](BaseModel):
    """One field: the typed value, how far to trust it, and the text it came from."""

    value: T | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: str | None = None
    method: Method | None = None


class Issue(BaseModel):
    code: str
    severity: Severity
    message: str
    field: str | None = None


class ChangeOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")

    change_order_number: Extracted[str]
    date: Extracted[dt.date]
    project_name: Extracted[str]
    owner: Extracted[str]
    contractor: Extracted[str]
    description: Extracted[str]
    amount: Extracted[Decimal]  # net change; negative for credits/deductions
    contract_sum_before: Extracted[Decimal]
    contract_sum_after: Extracted[Decimal]
    schedule_impact_days: Extracted[int]  # negative for reductions


class ExtractionResult(BaseModel):
    source: str
    extractors: list[str]
    change_order: ChangeOrder
    issues: list[Issue]
    overall_confidence: float = Field(ge=0.0, le=1.0)
    needs_review: bool
