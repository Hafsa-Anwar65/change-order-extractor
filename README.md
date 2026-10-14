# change-order-extractor

Turns messy construction change orders (PDF or text) into **validated JSON with a confidence score
for every field**, and says plainly when a human should look at the result.

```
pdf / txt / scan ─▶ loader (+OCR*) ─▶ [split packet] ─┬─▶ RulesExtractor ─┐
                                                      └─▶ LLMExtractor** ─┴─▶ merge ─▶ validation ─▶ JSON
                                       * optional: pip install ".[ocr]"   ** optional: ANTHROPIC_API_KEY
```

Approach, design decisions and an honest list of failure modes: **[WRITEUP.md](WRITEUP.md)**.

## Quick start

Requires Python 3.12+.

```bash
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev,ocr]"        # tests + web demo + LLM client + OCR (drop ,ocr to skip scans)

co-extract samples/co_001_clean.txt                       # rules only, no API key needed
co-extract samples/ --out-dir out/ --summary out/summary.csv   # a whole folder + a CSV overview
co-extract samples/co_010_packet.txt --split              # several change orders in one file
co-extract samples/co_012_scanned.pdf                     # scanned PDF (OCR), flagged for review
co-extract --print-schema                                 # JSON Schema of the output

co-extract-web                                            # demo UI at http://127.0.0.1:8000

export ANTHROPIC_API_KEY=...
co-extract samples/ --llm-fallback                        # LLM only for documents the rules doubt
co-extract samples/co_003_ocr_noise.txt --llm             # rules + LLM on every document
```

Smaller installs: the core needs only `pip install -e .`; extras are `.[ocr]` (scans and images),
`.[web]` (demo UI and HTTP API), `.[llm]` (Anthropic client). `.[dev]` covers web, LLM and the test
tools but not OCR (its model/runtime download is large); scan tests are skipped without it.

`--model` (or `$CO_EXTRACT_MODEL`) picks the model for the LLM. `--min-confidence` (default 0.70)
sets the bar a required field must clear before the document is considered trustworthy. The LLM is
asked for its answer through a forced tool call (schema-validated), and token usage is logged with `-v`.

## Demo UI and HTTP API

`co-extract-web` serves a single page: drop a PDF, scan, image or text file (or paste text) and see
each field with its confidence, the evidence it came from, issues, and the raw JSON.

| Endpoint | |
|---|---|
| `POST /api/extract` | multipart upload, field `file` (15 MB max, extension allow-list) |
| `POST /api/extract-text` | `{"text": "..."}` |
| `GET /api/schema`, `GET /health` | JSON Schema, liveness |

Uploads are written to a temporary folder under a fixed name, never the client's file name. It has
no authentication and is meant for local use or behind your own gateway.

## What you get back

Every field is `{value, confidence, evidence, method}`. Money is a string (never a float), credits
are negative, dates are ISO. Real output for a deliberately damaged sample
(`samples/co_003_ocr_noise.txt`, shortened to three fields):

```json
{
  "source": "co_003_ocr_noise.txt",
  "extractors": ["rules"],
  "change_order": {
    "change_order_number": { "value": null, "confidence": 0.0, "evidence": null, "method": null },
    "date": {
      "value": "2026-03-04", "confidence": 0.55,
      "evidence": "Date: 03/04/2026", "method": "rules"
    },
    "amount": {
      "value": "12450.00", "confidence": 0.74,
      "evidence": "contract_sum_after - contract_sum_before", "method": "derived"
    }
  },
  "issues": [
    { "code": "ambiguous_value", "severity": "warning", "field": "date",
      "message": "'03/04/2026' is ambiguous (day/month order); read as month-first" },
    { "code": "unparseable_value", "severity": "warning", "field": "amount",
      "message": "rules read '$l2,450.00' but it could not be parsed: no amount found" },
    { "code": "derived_field", "severity": "warning", "field": "amount",
      "message": "amount was not found directly; derived from the contract sums" },
    { "code": "missing_required_field", "severity": "error", "field": "change_order_number",
      "message": "change_order_number was not found" }
  ],
  "overall_confidence": 0.0,
  "needs_review": true
}
```

The pipeline did not guess: the OCR-damaged label (`CHANGE 0RDER NO.`) and the ambiguous date are
surfaced, the unreadable amount (`$l2,450.00`) is recovered from the contract sums with a lower
confidence, and the document is routed to review.

Fields: `change_order_number`, `date`, `project_name`, `owner`, `contractor`, `description`,
`amount`, `contract_sum_before`, `contract_sum_after`, `schedule_impact_days`.

`needs_review` is true when any issue has severity `error` (missing required field, contract sums
that do not add up, a money figure that is printed but unreadable, any text read by OCR) or the weakest required field is below `--min-confidence`.

## Using it as a library

```python
from pathlib import Path
from co_extract import build_pipeline

pipeline = build_pipeline(use_llm=False)
result = pipeline.run_file(Path("samples/co_001_clean.txt"))
print(result.change_order.amount.value, result.needs_review)
```

`ChangeOrderPipeline` takes any objects that satisfy the small `Extractor` protocol, so adding an
extractor (OCR-based, layout-aware, a different model) does not touch the rest of the code.

## Layout

```
src/co_extract/
  schema.py        output contract (pydantic)
  fields.py        one FieldSpec per field: labels, parser, fallbacks, required?   <- add fields here
  normalize.py     pure parsers: money, dates, days, text
  loader.py        pdf / txt / image -> normalised text (OCR for pages without a text layer)
  ocr.py           optional RapidOCR engine, box -> reading-order text
  segment.py       split a packet into one text per change order
  extractors/      labels.py + layout.py + rules.py (layout-aware label lexer), llm.py (grounded LLM)
  merge.py         candidates -> one value + confidence per field
  validation.py    cross-field checks, derived amount, needs_review
  pipeline.py      orchestration (+ LLM fallback)     cli.py  command line     web.py  API + demo
  corpus.py        seeded synthetic corpus generator
  evaluation.py    scoring, silent errors, calibration table
samples/           hand-written change orders (text, PDF, scans, packet) + expected/*.json
scripts/           regenerate the sample PDF and the scanned samples
tests/             195 tests
.github/workflows/ci.yml   ruff, mypy, pytest, evaluation on 3.12 and 3.13
```

## Tests and evaluation

```bash
pytest                                       # 195 tests, no network or API key needed
ruff check . && ruff format --check . && mypy
python -m co_extract.evaluation --corpus 1000   # samples + 1000 generated documents
```

Hand-written samples (11 documents, including a scanned PDF and PNG read by real OCR):

```
field accuracy : 109/110 (99.1%)     wrong values: 0   missing: 1
routing correct: 11/11 (needs_review matches ground truth)
silent errors  : 0 (wrong values in documents not flagged for review)
```

Synthetic corpus (1000 generated documents, seed 7, four layouts, mixed date and money formats,
15% with an OCR-style character swap in a money figure):

```
field accuracy : 9954/10000 (99.5%)  wrong values: 2   missing: 44
routing correct: 977/1000            flagged for review: 114
silent errors  : 0
```

All of this data is synthetic and written by the same author as the extractor, so it shows that the
pipeline behaves as designed, **not** how accurate it would be on real-world change orders. The
confidence scores take only a few distinct values, so the calibration table printed by the evaluation
shows ranking, not fine-grained probabilities. The LLM path is covered by tests against a fake client
and a local stub of the Messages API, not a live model. See the writeup.
