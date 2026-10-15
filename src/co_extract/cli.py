"""Command line interface: ``co-extract FILE...``."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from co_extract.errors import ChangeOrderError
from co_extract.loader import SUPPORTED_SUFFIXES
from co_extract.pipeline import build_pipeline
from co_extract.schema import ExtractionResult
from co_extract.validation import DEFAULT_MIN_CONFIDENCE


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="co-extract",
        description="Extract structured, validated fields from change-order PDFs or text files.",
    )
    parser.add_argument(
        "paths", nargs="*", type=Path, help="change-order files (pdf, txt) or folders"
    )
    parser.add_argument("--llm", action="store_true", help="also use the LLM extractor")
    parser.add_argument(
        "--llm-fallback",
        action="store_true",
        help="use the LLM only for documents the rules leave needing review",
    )
    parser.add_argument(
        "--summary", type=Path, metavar="CSV", help="also write one summary row per change order"
    )
    parser.add_argument("--model", help="model for --llm (default: $CO_EXTRACT_MODEL or built-in)")
    parser.add_argument(
        "--out-dir", type=Path, help="write <name>.json per input instead of stdout"
    )
    parser.add_argument(
        "--min-confidence",
        type=float,
        default=DEFAULT_MIN_CONFIDENCE,
        help="required fields below this confidence set needs_review (default: %(default)s)",
    )
    parser.add_argument(
        "--split",
        action="store_true",
        help="treat each file as a packet and extract every change order in it",
    )
    parser.add_argument("--print-schema", action="store_true", help="print the output JSON Schema")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def _expand(paths: Sequence[Path]) -> list[Path]:
    """Files as given; folders become their supported files, sorted."""
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(
                sorted(p for p in path.iterdir() if p.suffix.lower() in SUPPORTED_SUFFIXES)
            )
        else:
            files.append(path)
    return files


SUMMARY_COLUMNS = (
    "source",
    "needs_review",
    "overall_confidence",
    "change_order_number",
    "date",
    "amount",
    "issues",
)


def _summary_row(result: ExtractionResult) -> dict[str, object]:
    order = result.change_order
    return {
        "source": result.source,
        "needs_review": result.needs_review,
        "overall_confidence": result.overall_confidence,
        "change_order_number": order.change_order_number.value,
        "date": order.date.value,
        "amount": order.amount.value,
        "issues": "; ".join(sorted({issue.code for issue in result.issues})),
    }


def _emit(result: ExtractionResult, out_dir: Path | None, source: Path, stem: str) -> None:
    payload = result.model_dump_json(indent=2)
    if out_dir is None:
        print(payload)
        return
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{stem}.json"
    target.write_text(payload + "\n", encoding="utf-8")
    flag = "REVIEW" if result.needs_review else "ok"
    print(f"{source.name}: {flag} (confidence {result.overall_confidence:.2f}) -> {target}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING, format="%(levelname)s %(message)s"
    )

    if args.print_schema:
        print(json.dumps(ExtractionResult.model_json_schema(), indent=2))
        return 0
    if not args.paths:
        parser.error("provide at least one file (or --print-schema)")

    try:
        pipeline = build_pipeline(
            use_llm=args.llm,
            llm_fallback=args.llm_fallback,
            model=args.model,
            min_confidence=args.min_confidence,
        )
    except ChangeOrderError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    failed = False
    rows: list[dict[str, object]] = []
    for path in _expand(args.paths):
        try:
            results = pipeline.run_packet(path) if args.split else [pipeline.run_file(path)]
        except ChangeOrderError as exc:
            print(f"error: {exc}", file=sys.stderr)
            failed = True
            continue
        for number, result in enumerate(results, start=1):
            stem = f"{path.stem}_{number:02d}" if len(results) > 1 else path.stem
            _emit(result, args.out_dir, path, stem)
            rows.append(_summary_row(result))

    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        with args.summary.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=SUMMARY_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
