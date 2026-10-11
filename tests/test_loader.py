from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfWriter

from co_extract.errors import LoaderError, NoTextLayerError
from co_extract.loader import load_document, normalize_text
from tests.conftest import SAMPLES


def test_loads_text_file() -> None:
    document = load_document(SAMPLES / "co_001_clean.txt")
    assert document.source == "co_001_clean.txt"
    assert "Change Order No.: CO-014" in document.text


def test_loads_pdf_text_layer() -> None:
    document = load_document(SAMPLES / "co_006_pdf.pdf")
    assert "Change Order No.: CO-008" in document.text


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(LoaderError, match="not found"):
        load_document(tmp_path / "nope.pdf")


def test_unsupported_type(tmp_path: Path) -> None:
    path = tmp_path / "scan.png"
    path.write_bytes(b"\x89PNG")
    with pytest.raises(LoaderError, match="unsupported"):
        load_document(path)


def test_scanned_pdf_without_text_layer_asks_for_ocr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("co_extract.ocr.default_engine", lambda: None)
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    path = tmp_path / "scanned.pdf"
    with path.open("wb") as handle:
        writer.write(handle)
    with pytest.raises(NoTextLayerError, match="OCR"):
        load_document(path)


def test_corrupt_pdf(tmp_path: Path) -> None:
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"this is not a pdf at all")
    with pytest.raises(LoaderError):
        load_document(path)


def test_near_empty_text_file(tmp_path: Path) -> None:
    path = tmp_path / "empty.txt"
    path.write_text("  \n", encoding="utf-8")
    with pytest.raises(NoTextLayerError):
        load_document(path)


def test_invalid_utf8_does_not_crash(tmp_path: Path) -> None:
    path = tmp_path / "latin1.txt"
    path.write_bytes(b"Contractor: Caf\xe9 Builders Inc. - change order for roof repairs")
    assert "Builders Inc." in load_document(path).text


def test_normalize_text() -> None:
    messy = (
        "Con\ufb01rm\u00a0 Net\r\nChange  \r\n\r\n\r\n\r\n"  # ligature, NBSP, CRLF, blank run
        "\uff54\uff4f\uff54\uff41\uff4c \uff11\uff12\x00"  # full-width "total 12", NUL
    )
    # Inner runs of spaces are kept on purpose: the rules extractor uses wide gaps to find columns.
    assert normalize_text(messy) == "Confirm  Net\nChange\n\ntotal 12"
