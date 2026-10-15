"""Orchestration: load -> extract (many extractors) -> resolve -> validate -> result."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

from co_extract.errors import ExtractorError
from co_extract.extractors import (
    AnthropicClient,
    Candidate,
    Extractor,
    LLMExtractor,
    RulesExtractor,
)
from co_extract.fields import FIELDS
from co_extract.loader import Document, load_document, normalize_text
from co_extract.merge import resolve_field
from co_extract.schema import ChangeOrder, Extracted, ExtractionResult, Issue, Severity
from co_extract.segment import split_change_orders
from co_extract.validation import (
    DEFAULT_MIN_CONFIDENCE,
    check_fields,
    derive_amount,
    needs_review,
    overall_confidence,
)

logger = logging.getLogger(__name__)


class ChangeOrderPipeline:
    def __init__(
        self,
        extractors: Sequence[Extractor],
        *,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
        fallback_extractors: Sequence[Extractor] = (),
    ) -> None:
        """`fallback_extractors` run only when the first pass leaves the document needing
        review (cheap extractors first, an LLM only where it can help)."""
        if not extractors:
            raise ValueError("at least one extractor is required")
        self._extractors = list(extractors)
        self._fallback = list(fallback_extractors)
        self._min_confidence = min_confidence

    def run_file(self, path: Path) -> ExtractionResult:
        """Extract one change order from a file (all of its text is treated as one order)."""
        return self._run_document(load_document(path))

    def run_packet(self, path: Path) -> list[ExtractionResult]:
        """Extract every change order in a file that may contain several."""
        document = load_document(path)
        parts = split_change_orders(document.text)
        if len(parts) == 1:
            return [self._run_document(document)]
        return [
            self._run_document(replace(document, source=f"{document.source}#{n}", text=part))
            for n, part in enumerate(parts, start=1)
        ]

    def _run_document(self, document: Document) -> ExtractionResult:
        return self.run_text(document.text, source=document.source)

    def run_text(
        self,
        text: str,
        *,
        source: str = "<text>",
        today: date | None = None,
    ) -> ExtractionResult:
        def run(extractors: Sequence[Extractor]) -> ExtractionResult:
            return self._run(text, extractors, source=source, today=today)

        result = run(self._extractors)
        if self._fallback and result.needs_review:
            logger.info("%s needs review; retrying with fallback extractors", source)
            return run([*self._extractors, *self._fallback])
        return result

    def _run(
        self,
        text: str,
        extractors: Sequence[Extractor],
        *,
        source: str,
        today: date | None,
    ) -> ExtractionResult:
        text = normalize_text(text)
        issues: list[Issue] = []

        pooled: dict[str, list[Candidate]] = {spec.name: [] for spec in FIELDS}
        used: list[str] = []
        for extractor in extractors:
            try:
                found = extractor.extract(text)
            except ExtractorError as exc:
                logger.warning("%s extractor failed: %s", extractor.name, exc)
                issues.append(
                    Issue(
                        code="extractor_failed",
                        severity=Severity.WARNING,
                        message=f"{extractor.name} extractor failed: {exc}",
                    )
                )
                continue
            used.append(extractor.name)
            for name, candidates in found.items():
                pooled[name].extend(candidates)

        fields: dict[str, Extracted[Any]] = {}
        for spec in FIELDS:
            fields[spec.name], field_issues = resolve_field(spec, pooled[spec.name])
            issues.extend(field_issues)

        issues.extend(derive_amount(fields))
        issues.extend(check_fields(fields, today=today or date.today()))

        return ExtractionResult(
            source=source,
            extractors=used,
            # Re-validating through the schema is what guarantees the output is well typed.
            change_order=ChangeOrder.model_validate(
                {name: field.model_dump() for name, field in fields.items()}
            ),
            issues=issues,
            overall_confidence=round(overall_confidence(fields), 2),
            needs_review=needs_review(fields, issues, self._min_confidence),
        )


def build_pipeline(
    *,
    use_llm: bool = False,
    llm_fallback: bool = False,
    model: str | None = None,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
) -> ChangeOrderPipeline:
    """`use_llm`: rules + LLM on every document. `llm_fallback`: LLM only on flagged ones."""
    extractors: list[Extractor] = [RulesExtractor()]
    fallback: list[Extractor] = []
    if use_llm:
        extractors.append(LLMExtractor(AnthropicClient(model)))
    elif llm_fallback:
        fallback.append(LLMExtractor(AnthropicClient(model)))
    return ChangeOrderPipeline(
        extractors, min_confidence=min_confidence, fallback_extractors=fallback
    )
