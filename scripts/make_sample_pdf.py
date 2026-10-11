"""Regenerate samples/co_006_pdf.pdf (a PDF with a clean text layer).

Usage: python scripts/make_sample_pdf.py
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

LINES = [
    ("CHANGE ORDER", 16),
    ("", 12),
    ("Change Order No.: CO-008", 11),
    ("Date: April 9, 2026", 11),
    ("Project: Oakridge Public Library - Roof Replacement", 11),
    ("Owner: Oakridge Library District", 11),
    ("Contractor: Summit Roofing & Sheet Metal", 11),
    ("", 11),
    ("Description of Change:", 11),
    ("Replace 400 sq ft of deteriorated roof decking discovered after", 11),
    ("tear-off of the existing membrane. Includes new plywood sheathing.", 11),
    ("", 11),
    ("Contract Sum Prior to This Change Order: $640,000.00", 11),
    ("Net Change by This Change Order: $9,480.00", 11),
    ("New Contract Sum Including This Change Order: $649,480.00", 11),
    ("", 11),
    ("Schedule Impact: 0 days", 11),
]


def main() -> None:
    target = Path(__file__).resolve().parent.parent / "samples" / "co_006_pdf.pdf"
    pdf = canvas.Canvas(str(target), pagesize=letter)
    y = 720
    for text, size in LINES:
        pdf.setFont("Helvetica-Bold" if size > 12 else "Helvetica", size)
        pdf.drawString(72, y, text)
        y -= size + 8
    pdf.save()
    print(f"wrote {target}")


if __name__ == "__main__":
    main()
