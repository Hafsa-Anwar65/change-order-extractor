from __future__ import annotations

from pathlib import Path

from co_extract.corpus import make_corpus, write_corpus
from co_extract.evaluation import calibration, evaluate, evaluate_corpus
from co_extract.pipeline import ChangeOrderPipeline


def test_corpus_is_deterministic_for_a_seed() -> None:
    assert make_corpus(20, seed=3) == make_corpus(20, seed=3)
    assert make_corpus(20, seed=3) != make_corpus(20, seed=4)


def test_truth_is_internally_consistent() -> None:
    from decimal import Decimal

    for case in make_corpus(100):
        truth = case.truth
        before, amount = Decimal(truth["contract_sum_before"]), Decimal(truth["amount"])
        assert before + amount == Decimal(truth["contract_sum_after"])


def test_extractor_holds_up_on_the_synthetic_corpus(rules_pipeline: ChangeOrderPipeline) -> None:
    scores = evaluate_corpus(rules_pipeline, 200, seed=11)
    total = sum(s.total for s in scores)
    assert sum(s.correct for s in scores) / total >= 0.98
    assert sum(s.silent_errors for s in scores) == 0


def test_written_corpus_scores_like_the_in_memory_one(
    tmp_path: Path, rules_pipeline: ChangeOrderPipeline
) -> None:
    cases = make_corpus(30, seed=5)
    write_corpus(cases, tmp_path)
    on_disk = evaluate(rules_pipeline, tmp_path)
    in_memory = evaluate_corpus(rules_pipeline, 30, seed=5)
    assert sorted((s.source.removesuffix(".txt"), s.correct) for s in on_disk) == sorted(
        (s.source, s.correct) for s in in_memory
    )


def test_calibration_bins_count_every_returned_value(rules_pipeline: ChangeOrderPipeline) -> None:
    scores = evaluate_corpus(rules_pipeline, 20, seed=1)
    assert sum(count for _, count, _ in calibration(scores)) == sum(
        len(s.predictions) for s in scores
    )
