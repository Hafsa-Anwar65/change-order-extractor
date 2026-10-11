"""Optional OCR for scanned PDFs and images.  Install with: pip install ".[ocr]"

The engine (RapidOCR: ONNX models bundled in the wheel, no system binaries) returns one box per
text line. `boxes_to_text` rebuilds the page's reading layout from those boxes (rows, wide
gaps for columns, blank lines between paragraphs) so the normal extractors can read it.
"""

from __future__ import annotations

import logging
import statistics
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from functools import lru_cache
from itertools import pairwise
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from co_extract.errors import LoaderError

if TYPE_CHECKING:
    from PIL.Image import Image

logger = logging.getLogger(__name__)

RENDER_DPI = 200
ROW_TOLERANCE = (
    0.6  # boxes whose vertical centres differ by less than this x line height share a row
)
COLUMN_GAP = 2.0  # a horizontal gap wider than this x line height becomes a wide gap (a column)
PARAGRAPH_GAP = 1.7  # a row pitch above this x the median pitch becomes a blank line
INSTALL_HINT = 'pip install ".[ocr]"'


class OcrUnavailableError(LoaderError):
    """OCR was needed but the optional dependencies are not installed."""


@dataclass(frozen=True, slots=True)
class OcrBox:
    text: str
    score: float  # engine confidence, 0..1
    left: float
    top: float
    right: float
    bottom: float

    @property
    def center(self) -> float:
        return (self.top + self.bottom) / 2


class OcrEngine(Protocol):
    def recognize(self, image: Image) -> list[OcrBox]: ...


class RapidOcrEngine:
    def __init__(self) -> None:
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError as exc:
            raise OcrUnavailableError(
                f"OCR support is not installed or cannot load ({exc}). {INSTALL_HINT}; on Windows "
                "a 'DLL load failed' usually needs the Microsoft Visual C++ Redistributable "
                "(or: pip install --force-reinstall opencv-python-headless)"
            ) from exc
        self._engine = RapidOCR()

    def recognize(self, image: Image) -> list[OcrBox]:
        import numpy as np

        result, _ = self._engine(np.asarray(image.convert("RGB")))
        boxes: list[OcrBox] = []
        for points, text, score in result or []:
            xs, ys = [p[0] for p in points], [p[1] for p in points]
            boxes.append(OcrBox(str(text), float(score), min(xs), min(ys), max(xs), max(ys)))
        return boxes


@lru_cache(maxsize=1)
def default_engine() -> OcrEngine | None:
    """The shared RapidOCR engine, or None when the optional dependencies are missing."""
    try:
        return RapidOcrEngine()
    except OcrUnavailableError:
        logger.debug("OCR dependencies not installed")
        return None


def boxes_to_text(boxes: Sequence[OcrBox]) -> tuple[str, float]:
    """Rebuild reading-order text from OCR boxes. Returns (text, mean confidence by length)."""
    boxes = [box for box in boxes if box.text.strip()]
    if not boxes:
        return "", 0.0
    line_height = statistics.median(box.bottom - box.top for box in boxes) or 1.0

    rows: list[list[OcrBox]] = []
    for box in sorted(boxes, key=lambda b: b.center):
        row_center = statistics.fmean(b.center for b in rows[-1]) if rows else 0.0
        if rows and abs(box.center - row_center) < ROW_TOLERANCE * line_height:
            rows[-1].append(box)
        else:
            rows.append([box])

    centers = [statistics.fmean(b.center for b in row) for row in rows]
    pitches = [b - a for a, b in pairwise(centers)]
    median_pitch = statistics.median(pitches) if pitches else 0.0

    lines: list[str] = []
    for index, row in enumerate(rows):
        if (
            index
            and median_pitch
            and centers[index] - centers[index - 1] > PARAGRAPH_GAP * median_pitch
        ):
            lines.append("")
        row.sort(key=lambda b: b.left)
        text = row[0].text.strip()
        for previous, box in pairwise(row):
            wide = box.left - previous.right > COLUMN_GAP * line_height
            text += ("    " if wide else " ") + box.text.strip()
        lines.append(text)

    total = sum(len(b.text) for b in boxes)
    quality = sum(b.score * len(b.text) for b in boxes) / total
    return "\n".join(lines), quality


def recognize_text(image: Image, engine: OcrEngine) -> tuple[str, float]:
    return boxes_to_text(engine.recognize(image))


def open_image(path: Path) -> Image:
    try:
        from PIL import Image as PilImage

        with PilImage.open(path) as image:
            return image.convert("RGB")
    except ImportError as exc:
        raise OcrUnavailableError(f"OCR support is not installed: {INSTALL_HINT}") from exc
    except OSError as exc:
        raise LoaderError(f"{path}: could not read image ({exc})") from exc


def render_pdf_page(path: Path, index: int, dpi: int = RENDER_DPI) -> Image:
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        raise OcrUnavailableError(f"OCR support is not installed: {INSTALL_HINT}") from exc
    try:
        document = pdfium.PdfDocument(str(path))
        try:
            image: Image = document[index].render(scale=dpi / 72).to_pil().convert("RGB")
            return image
        finally:
            document.close()
    except pdfium.PdfiumError as exc:
        raise LoaderError(f"{path}: could not render page {index + 1} for OCR ({exc})") from exc


def iter_pages(path: Path, count: int) -> Iterator[Image]:
    for index in range(count):
        yield render_pdf_page(path, index)
