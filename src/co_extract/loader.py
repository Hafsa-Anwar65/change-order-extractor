"""Read a document (text or PDF) into normalised text.

PDFs must have a text layer. Scanned or image-only PDFs are not supported and raise a clear
`NoTextLayerError` rather than returning empty fields.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PyPdfError

from co_extract.errors import LoaderError, NoTextLayerError

logger = logging.getLogger(__name__)

MIN_TEXT_CHARS = 20
_TEXT_SUFFIXES = frozenset({".txt", ".md", ""})
SUPPORTED_SUFFIXES = frozenset({".pdf", *_TEXT_SUFFIXES - {""}})


@dataclass(frozen=True, slots=True)
class Document:
    source: str
    text: str


def normalize_text(text: str) -> str:
    """Make text uniform without changing its meaning: NFKC (ligatures, NBSP, full-width
    digits), unix newlines, no trailing whitespace, no runs of blank lines."""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", text).strip("\n")


def _read_pdf(path: Path) -> str:
    try:
        reader = PdfReader(path)
        if reader.is_encrypted and not reader.decrypt(""):
            raise LoaderError(f"{path}: PDF is password protected")
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    except PyPdfError as exc:
        raise LoaderError(f"{path}: could not read PDF ({exc})") from exc


def load_document(path: Path) -> Document:
    if not path.is_file():
        raise LoaderError(f"{path}: file not found")
    suffix = path.suffix.lower()
    if suffix in _TEXT_SUFFIXES:
        raw = path.read_text(encoding="utf-8", errors="replace")
    elif suffix == ".pdf":
        raw = _read_pdf(path)
    else:
        raise LoaderError(f"{path}: unsupported file type {suffix!r} (expected .pdf, .txt or .md)")

    text = normalize_text(raw)
    if len(text) < MIN_TEXT_CHARS:
        hint = " (scanned PDFs are not supported)" if suffix == ".pdf" else ""
        raise NoTextLayerError(f"{path}: no extractable text{hint}")
    logger.debug("loaded %s (%d chars)", path, len(text))
    return Document(path.name, text)
