from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from co_extract.loader import load_document
from co_extract.ocr import OcrBox, boxes_to_text
from co_extract.pipeline import OCR_REVIEW_QUALITY, ChangeOrderPipeline
from co_extract.schema import Severity


def box(text: str, left: float, top: float, width: float = 100, score: float = 0.99) -> OcrBox:
    return OcrBox(text, score, left, top, left + width, top + 20)


class FakeOcr:
    def __init__(self, boxes: list[OcrBox]) -> None:
        self.boxes = boxes

    def recognize(self, image: Image.Image) -> list[OcrBox]:
        return self.boxes


def test_boxes_become_rows_in_reading_order() -> None:
    text, _ = boxes_to_text([box("Amount:", 0, 100), box("$5.00", 110, 102), box("Title", 0, 0)])
    assert text == "Title\nAmount: $5.00"


def test_wide_gap_becomes_a_column_break() -> None:
    text, _ = boxes_to_text([box("Left", 0, 0), box("Right", 400, 0)])
    assert text == "Left    Right"


def test_larger_vertical_gap_becomes_a_blank_line() -> None:
    boxes = [box("a", 0, 0), box("b", 0, 30), box("c", 0, 60), box("d", 0, 200)]
    text, _ = boxes_to_text(boxes)
    assert text == "a\nb\nc\n\nd"


def test_quality_is_length_weighted() -> None:
    _, quality = boxes_to_text([box("aaaa", 0, 0, score=1.0), box("b", 0, 50, score=0.0)])
    assert quality == pytest.approx(0.8)


def test_empty_page_reads_as_nothing() -> None:
    assert boxes_to_text([]) == ("", 0.0)


def test_image_goes_through_the_engine_and_is_marked_as_ocr(tmp_path: Path) -> None:
    path = tmp_path / "scan.png"
    Image.new("RGB", (50, 50), "white").save(path)
    lines = ["Change Order No.: CO-9", "Net Change: $5.00"]
    engine = FakeOcr([box(line, 0, 40 * i, 600, score=0.80) for i, line in enumerate(lines)])
    document = load_document(path, engine=engine)
    assert document.ocr
    assert document.quality == pytest.approx(0.80)
    assert "CO-9" in document.text


def test_low_quality_ocr_forces_review(rules_pipeline: ChangeOrderPipeline) -> None:
    text = "Change Order No.: CO-9\nNet Change: $5.00"
    low = rules_pipeline.run_text(text, from_ocr=True, text_quality=OCR_REVIEW_QUALITY - 0.05)
    assert low.needs_review
    assert any(i.code == "ocr_text" and i.severity is Severity.ERROR for i in low.issues)
    clean = rules_pipeline.run_text(text, from_ocr=True, text_quality=0.99)
    assert any(i.code == "ocr_text" and i.severity is Severity.WARNING for i in clean.issues)


def test_ocr_quality_scales_candidate_confidence(rules_pipeline: ChangeOrderPipeline) -> None:
    text = "Change Order No.: CO-9"
    full = rules_pipeline.run_text(text).change_order.change_order_number.confidence
    half = rules_pipeline.run_text(text, text_quality=0.5).change_order.change_order_number
    assert half.confidence == pytest.approx(full * 0.5, abs=0.01)
