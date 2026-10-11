"""Read a document (text, PDF or image) into normalised text.

PDFs use their text layer. Pages without one, and image files, go through OCR when the
optional OCR dependencies are installed; otherwise a clear error says what to install.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from co_extract import ocr
from co_extract.errors import LoaderError, NoTextLayerError

logger = logging.getLogger(__name__)

MIN_TEXT_CHARS = 20
_TEXT_SUFFIXES = frozenset({".txt", ".md", ""})
_IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"})
SUPPORTED_SUFFIXES = frozenset({".pdf", *_TEXT_SUFFIXES - {""}, *_IMAGE_SUFFIXES})


@dataclass(frozen=True, slots=True)
class Document:
    source: str
    text: str
    ocr: bool = False  # True when any text came from OCR
    quality: float = 1.0  # 1.0 for a real text layer; the mean OCR confidence otherwise


def normalize_text(text: str) -> str:
    """Make text uniform without changing its meaning: NFKC (ligatures, NBSP, full-width
    digits), unix newlines, no trailing whitespace, no runs of blank lines."""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", text).strip("\n")


def _no_engine_error(path: Path, what: str) -> LoaderError:
    return NoTextLayerError(
        f"{path}: {what} and OCR is not installed. Install it with: {ocr.INSTALL_HINT}"
    )


def _read_pdf(path: Path, engine: ocr.OcrEngine | None) -> Document:
    """Text layer where there is one, OCR for pages without."""
    try:
        reader = PdfReader(path)
        if reader.is_encrypted and not reader.decrypt(""):
            raise LoaderError(f"{path}: PDF is password protected")
        layers = [page.extract_text() or "" for page in reader.pages]
    except PyPdfError as exc:
        raise LoaderError(f"{path}: could not read PDF ({exc})") from exc

    pages: list[str] = []
    qualities: list[float] = []
    for index, layer in enumerate(layers):
        if len(layer.strip()) >= MIN_TEXT_CHARS:
            pages.append(layer)
            continue
        if engine is None:
            if index == 0 and not any(len(x.strip()) >= MIN_TEXT_CHARS for x in layers):
                raise _no_engine_error(path, "the PDF has no text layer")
            continue  # a stray blank page in an otherwise digital PDF
        text, quality = ocr.recognize_text(ocr.render_pdf_page(path, index), engine)
        logger.debug("%s page %d read by OCR (confidence %.2f)", path, index + 1, quality)
        if text.strip():
            pages.append(text)
            qualities.append(quality)
    return Document(
        source=path.name,
        text="\n\n".join(pages),
        ocr=bool(qualities),
        quality=min(qualities, default=1.0),
    )


def _read_image(path: Path, engine: ocr.OcrEngine | None) -> Document:
    if engine is None:
        raise _no_engine_error(path, "this is an image")
    text, quality = ocr.recognize_text(ocr.open_image(path), engine)
    return Document(source=path.name, text=text, ocr=True, quality=quality)


def load_document(path: Path, *, engine: ocr.OcrEngine | None = None) -> Document:
    """Load `path`. `engine` overrides the default OCR engine (used by tests)."""
    if not path.is_file():
        raise LoaderError(f"{path}: file not found")
    suffix = path.suffix.lower()
    if suffix in _TEXT_SUFFIXES:
        document = Document(path.name, path.read_text(encoding="utf-8", errors="replace"))
    elif suffix == ".pdf":
        document = _read_pdf(path, engine or ocr.default_engine())
    elif suffix in _IMAGE_SUFFIXES:
        document = _read_image(path, engine or ocr.default_engine())
    else:
        raise LoaderError(
            f"{path}: unsupported file type {suffix!r} (expected .pdf, .txt or an image)"
        )

    text = normalize_text(document.text)
    if len(text) < MIN_TEXT_CHARS:
        raise NoTextLayerError(f"{path}: no extractable text")
    logger.debug("loaded %s (%d chars, ocr=%s)", path, len(text), document.ocr)
    return Document(document.source, text, document.ocr, document.quality)
