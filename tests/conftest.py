from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from co_extract.extractors import Candidate, RulesExtractor
from co_extract.extractors.llm import LLMExtractor
from co_extract.fields import FIELD_BY_NAME, FieldSpec
from co_extract.pipeline import ChangeOrderPipeline
from co_extract.schema import Method

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


class FakeLLM:
    """LLMClient stand-in that returns a canned reply and records the prompt."""

    def __init__(self, reply: str | dict[str, Any]) -> None:
        self.reply = reply if isinstance(reply, str) else json.dumps(reply)
        self.prompts: list[str] = []

    def complete(self, *, system: str, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.reply


def llm_reply(**fields: tuple[str | None, str | None, float]) -> dict[str, Any]:
    """Build an LLM JSON reply: llm_reply(amount=("$5.00", "Amount: $5.00", 0.9))."""
    return {
        "fields": {
            name: {"raw": raw, "evidence": evidence, "confidence": confidence}
            for name, (raw, evidence, confidence) in fields.items()
        }
    }


@pytest.fixture
def rules_pipeline() -> ChangeOrderPipeline:
    return ChangeOrderPipeline([RulesExtractor()])


@pytest.fixture
def make_llm_pipeline() -> Callable[[dict[str, Any] | str], ChangeOrderPipeline]:
    def build(reply: dict[str, Any] | str) -> ChangeOrderPipeline:
        return ChangeOrderPipeline([RulesExtractor(), LLMExtractor(FakeLLM(reply))])

    return build


def spec(name: str) -> FieldSpec:
    return FIELD_BY_NAME[name]


def candidate(raw: str, confidence: float = 0.9, method: Method = Method.RULES) -> Candidate:
    return Candidate(raw=raw, confidence=confidence, evidence=raw, method=method)
