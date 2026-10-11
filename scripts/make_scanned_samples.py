"""Regenerate the scanned samples: a PDF with no text layer and a PNG (needs the `ocr` extra).

Usage: python scripts/make_scanned_samples.py
Pages are drawn with PIL, so the PDF contains only an image, exactly like a scan.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SAMPLES = Path(__file__).resolve().parent.parent / "samples"
LINES = [
    "CHANGE ORDER",
    "",
    "Change Order No.: CO-031",
    "Date: June 12, 2026",
    "Project: Lakeview Elementary - Gym Floor Replacement",
    "Owner: Lakeview School District",
    "Contractor: Northstar Flooring Inc.",
    "",
    "Description of Change:",
    "Remove and replace damaged maple gym flooring after water intrusion.",
    "",
    "Contract Sum Prior to This Change Order: $310,000.00",
    "Net Change by This Change Order: $27,500.00",
    "New Contract Sum Including This Change Order: $337,500.00",
    "",
    "Schedule Impact: 9 days",
]


def font(size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    for name in ("DejaVuSans.ttf", "Arial.ttf", "LiberationSans-Regular.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def page() -> Image.Image:
    image = Image.new("RGB", (1700, 2200), "white")  # US Letter at 200 DPI
    draw = ImageDraw.Draw(image)
    y = 200
    for line in LINES:
        draw.text((200, y), line, fill="black", font=font(46 if line == "CHANGE ORDER" else 36))
        y += 70
    return image


def main() -> None:
    image = page()
    image.save(SAMPLES / "co_011_scanned.png")
    image.save(SAMPLES / "co_012_scanned.pdf", resolution=200)


if __name__ == "__main__":
    main()
