"""Score extraction against hand-written ground truth.

Run: ``python -m co_extract.evaluation [samples_dir] [--llm]``

Ground truth lives in ``<samples_dir>/expected/*.json`` and describes the *document*, not what
any extractor happens to output. The metric that matters most is ``silent errors``: wrong
values in documents that were NOT flagged for review.
"""

from __future__ import annotations

import argparse
import itertools
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from co_extract.corpus import make_corpus
from co_extract.errors import ChangeOrderError
from co_extract.pipeline import ChangeOrderPipeline, build_pipeline
from co_extract.schema import ExtractionResult


@dataclass(frozen=True, slots=True)
class Score:
    source: str
    total: int
    missing: tuple[str, ...]  # truth present, extractor returned nothing
    incorrect: tuple[str, ...]  # extractor returned a different value
    needs_review: bool
    needs_review_expected: bool
    predictions: tuple[tuple[float, bool], ...] = ()  # (confidence, correct) per returned value

    @property
    def correct(self) -> int:
        return self.total - len(self.missing) - len(self.incorrect)

    @property
    def silent_errors(self) -> int:
        return 0 if self.needs_review else len(self.incorrect)


TEXT_FIELDS = frozenset({"project_name", "owner", "contractor", "description"})


def same_value(name: str, got: Any, truth: Any) -> bool:
    """Exact match; free-text fields ignore spacing and case (layout, not meaning)."""
    if got == truth:
        return True
    if name in TEXT_FIELDS and isinstance(got, str) and isinstance(truth, str):
        return "".join(got.split()).casefold() == "".join(truth.split()).casefold()
    return False


def score(result: ExtractionResult, expected: dict[str, Any]) -> Score:
    actual = result.change_order.model_dump(mode="json")
    missing: list[str] = []
    incorrect: list[str] = []
    predictions: list[tuple[float, bool]] = []
    for name, truth in expected["values"].items():
        got = actual[name]["value"]
        right = same_value(name, got, truth)
        if got is not None:
            predictions.append((actual[name]["confidence"], right))
        if right:
            continue
        (missing if got is None else incorrect).append(name)
    return Score(
        source=expected["source"],
        total=len(expected["values"]),
        missing=tuple(missing),
        incorrect=tuple(incorrect),
        needs_review=result.needs_review,
        needs_review_expected=expected["needs_review"],
        predictions=tuple(predictions),
    )


def evaluate(pipeline: ChangeOrderPipeline, samples_dir: Path) -> list[Score]:
    scores = []
    for path in sorted((samples_dir / "expected").glob("*.json")):
        expected = json.loads(path.read_text(encoding="utf-8"))
        try:
            result = pipeline.run_file(samples_dir / expected["source"])
        except ChangeOrderError as exc:  # e.g. an unreadable file
            print(f"skipped {expected['source']}: {exc}")
            continue
        scores.append(score(result, expected))
    return scores


CALIBRATION_BINS = (0.0, 0.5, 0.7, 0.85, 0.95, 1.01)


def calibration(scores: Sequence[Score]) -> list[tuple[str, int, int]]:
    """Per confidence bin: (label, values returned, values correct)."""
    rows = []
    for low, high in itertools.pairwise(CALIBRATION_BINS):
        inside = [ok for s in scores for conf, ok in s.predictions if low <= conf < high]
        label = f"{low:.2f}-{min(high, 1.0):.2f}"
        rows.append((label, len(inside), sum(inside)))
    return rows


def evaluate_corpus(pipeline: ChangeOrderPipeline, n: int, seed: int) -> list[Score]:
    scores = []
    for case in make_corpus(n, seed):
        expected = {"source": case.name, "needs_review": case.damaged, "values": case.truth}
        scores.append(score(pipeline.run_text(case.text, source=case.name), expected))
    return scores


def print_report(scores: Sequence[Score], *, per_document: bool) -> None:
    if per_document:
        print(f"{'document':28} {'fields':>7}  {'review':>6}  problems")
        for s in scores:
            problems = [f"missing:{n}" for n in s.missing] + [f"wrong:{n}" for n in s.incorrect]
            review = "yes" if s.needs_review else "no"
            line = f"{s.source:28} {s.correct:>3}/{s.total:<3}  {review:>6}  "
            print(line + (", ".join(problems) or "-"))
        print()

    total = sum(s.total for s in scores)
    correct = sum(s.correct for s in scores)
    routed = sum(s.needs_review == s.needs_review_expected for s in scores)
    silent = sum(s.silent_errors for s in scores)
    wrong = sum(len(s.incorrect) for s in scores)
    flagged = sum(s.needs_review for s in scores)
    print(f"documents      : {len(scores)} ({flagged} flagged for review)")
    print(f"field accuracy : {correct}/{total} ({correct / total:.1%})")
    print(f"wrong values   : {wrong}   missing: {sum(len(s.missing) for s in scores)}")
    print(f"routing correct: {routed}/{len(scores)} (needs_review matches ground truth)")
    print(f"silent errors  : {silent} (wrong values in documents not flagged for review)")
    print("\ncalibration (confidence of returned values vs. how often they were right)")
    for label, count, right in calibration(scores):
        rate = f"{right / count:.1%}" if count else "-"
        print(f"  {label:>9}  n={count:<6} correct={rate}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m co_extract.evaluation")
    parser.add_argument("samples_dir", nargs="?", type=Path, default=Path("samples"))
    parser.add_argument("--llm", action="store_true", help="evaluate rules + LLM")
    parser.add_argument(
        "--corpus", type=int, metavar="N", help="also score N generated synthetic documents"
    )
    parser.add_argument("--seed", type=int, default=7, help="seed for --corpus (default: 7)")
    args = parser.parse_args(argv)

    pipeline = build_pipeline(use_llm=args.llm)
    print("== hand-written samples ==")
    print_report(evaluate(pipeline, args.samples_dir), per_document=True)
    if args.corpus:
        print(f"\n== synthetic corpus (n={args.corpus}, seed={args.seed}) ==")
        print_report(evaluate_corpus(pipeline, args.corpus, args.seed), per_document=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
