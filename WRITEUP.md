# Change-order extraction: approach and failure modes

## The problem, and the stance I took

Change orders arrive as PDFs and pasted text with no consistent layout. The extraction itself is
the easy half. The harder half is that the output feeds money and schedule decisions, so a value
that is *wrong but looks confident* is worse than a value that is missing. I therefore treated
"know when not to trust the result" as the main requirement, not an add-on. Every field carries a
confidence and its evidence, and the document as a whole gets a `needs_review` verdict.

## Approach

1. **Load.** `pypdf` for PDFs, UTF-8 for text. Text is NFKC-normalised (ligatures, non-breaking
   spaces, full-width digits). Pages with no text layer, and image files, go through OCR (RapidOCR,
   optional extra). The OCR boxes are rebuilt into reading-order text (rows, wide gaps for columns,
   blank lines for paragraphs). Without OCR installed, a clear `NoTextLayerError` says what to
   install instead of returning empty fields. OCR quality scales every candidate's confidence, and
   any document read by OCR is routed to review, because OCR garbles free
   text in ways no value check can see (a real scan here produced "SchoolDistrict").
   `--split` cuts a packet into one text per change order at each new change-order number.
2. **Extract candidates with two extractors that fail differently.**
   - *Rules:* a label lexer. Every line is checked for a known label (longest match wins, so
     "Net Change by This Change Order" beats "Net Change"); the value is the rest of the line, or
     the next line when the label stands alone. A layout pass handles side-by-side columns,
     header-row/data-row tables, and a run of labels followed by a run of values. Per-pattern
     fallbacks catch a bare `CO-014` (0.60) and the AIA G701 sentences, e.g. "The Contract Sum will be
     decreased by this Change Order in the amount of $8,400.00" (0.85, sign taken from the verb).
   - *LLM (optional):* asked for the value copied verbatim plus a quote of its source. The
     answer is then checked against the document (see below).
3. **Resolve each field.** Candidates are parsed into real types (`Decimal`, `date`, `int`);
   unparseable ones are dropped. The strongest wins. If an *independent* extractor agrees, confidence
   rises (noisy-OR). If a rival of comparable strength disagrees, confidence drops and an issue is
   raised. Parse-time ambiguity is applied last, so two extractors reading the same ambiguous string
   cannot cancel the ambiguity by agreeing.
4. **Validate across fields.** Required fields present; `contract_sum_before + amount ==
   contract_sum_after` using exact decimals (a mismatch is an *error*, never silently fixed); a
   missing amount is derived from the two sums at reduced confidence; the sign of the amount is
   compared with the wording ("credit", "additional"); the date must be plausible.
5. **Output.** A Pydantic model, re-validated before it is returned, so the JSON always matches
   the published schema (`co-extract --print-schema`). `needs_review` is true if any issue is an
   error or the weakest *required* field is under 0.70.

## Decisions worth defending

- **Rules plus an LLM, not an LLM alone.** Rules are cheap, deterministic and auditable, and when
  they agree with a model they provide real corroboration because the two make different mistakes.
  The model covers what rules cannot: damaged labels and unfamiliar layouts.
- **Confidence is computed, not requested.** A model's self-reported confidence is poorly
  calibrated, so it is only an upper bound. Each LLM answer is capped by grounding: the value
  must appear in the document (otherwise ≤ 0.30) and so must its quoted evidence (otherwise ≤ 0.50);
  a fully grounded answer is capped at 0.90.
- **Refuse to guess.** `03/04/2026` is flagged, not coin-flipped. `$1,000 + $500` and `$l2,450.00`
  are rejected rather than read as 1,000 or 2,450. Blank form fields (`______`) count as missing.
- **Money is `Decimal`, serialised as a string.** Credits are negative whether written `(3,200.00)`,
  `-$3,200` or `3,200.00 CR`.
- **The document is untrusted input.** It is fenced in the prompt and the model is told not to obey
  it, but the real defence is structural: output must pass schema validation and grounding, so an
  injected instruction can at worst yield low-confidence, flagged candidates.
- **Failures degrade, they do not abort.** If the LLM call fails or returns garbage, the pipeline
  keeps the rules result and records an `extractor_failed` warning.

## What I measured, and what I did not

Two sets, both synthetic, both scored rules-only (`python -m co_extract.evaluation --corpus 1000`):

| | Hand-written samples | Generated corpus |
|---|---|---|
| Documents | 11 (layouts, a packet, a real PDF, a scanned PDF and PNG through OCR) | 1000, seed 7 |
| Fields correct | 109 / 110 (99.1%) | 9954 / 10000 (99.5%) |
| Wrong values | 0 | 2 |
| `needs_review` matches expectation | 11 / 11 | 977 / 1000 |
| Wrong values in documents *not* flagged | 0 | 0 |

The generator varies layout (labelled, alternative wording, header table, label column), date format,
money format (`$`, parentheses for credits) and injects an OCR-style character swap into a money
figure in 15% of documents. Scoring ignores spacing and case in free-text fields so layout is not
mistaken for meaning.

What the numbers did and did not show. Building the corpus exposed three label gaps (fixed) and one
real design flaw: a money figure damaged by OCR was dropped and then silently re-derived from the
other two, so the document looked fine. An unreadable money figure is now an error and routes the
document to review (routing went from 865 to 977 of 1000). When `contract_sum_after` is the
missing figure it is now also derived from `before + amount` (marked as derived, lower confidence),
which cut missing values from 83 to 44. All 2 wrong and 44 missing values sit in the 114 flagged
documents.

Caveats, stated plainly:

- I wrote all of these documents and the generator myself, alongside the extractor. This shows the
  behaviour, not accuracy on real-world change orders. A real number needs a real, independently
  labelled corpus.
- Confidences take few distinct values (0.92, 0.84, 0.72 ...), so the calibration table is "all
  returned values were right" in every bin. It cannot yet say that 0.8 means 80%.
- OCR was tested on clean, synthetic renderings. Real scans (skew, stamps, handwriting, low
  resolution) will be much worse; the review rule is deliberately conservative for that reason.
- The LLM path is tested against a fake client and a local stub of the Messages API (request shape,
  forced tool call, token counting, errors, grounding caps). I have **not** benchmarked it against
  the live model.
- The confidence constants were chosen by reasoning, not fitted. They are ordinal scores, not
  calibrated probabilities.

## Failure modes

| # | Failure | What the pipeline does | Status |
|---|---|---|---|
| 1 | Scanned PDF or image | RapidOCR reads it; confidence scaled by OCR quality; any OCR document is flagged | Built; tested on clean synthetic scans only |
| 2 | OCR-damaged label (`0RDER`) | Rules miss it; missing required field, so review. LLM can recover it (tested with a fake model) | Mitigated |
| 3 | OCR-damaged digits (`$l2,450.00`) | Rejected as unparseable (an error on money fields, so review); amount derived from the contract sums at ×0.8 | Mitigated; a human confirms |
| 4 | Ambiguous date `03/04/2026` | Read month-first, confidence ×0.6, below the bar, so review | Day-first is a parameter but not exposed per document or locale |
| 5 | Label column followed by a separate value column, header-row tables | Paired by the layout pass (label run / value run, header row / data row) | Handled for the layouts I tried; unusual grids still fall to the LLM |
| 6 | Label vocabulary the rules have not seen | Field missing, so review. A new label sharing a prefix with a known one can be mis-captured | Partly handled by an ignore-list, which is finite |
| 7 | Same field twice with different values (revision history, line items) | Confidence ×0.6 and a `conflicting_values` warning; the first is chosen, which may not be the current one | Flagged, not resolved |
| 8 | Several change orders in one PDF | `--split` cuts at each new change-order number (title line kept) | Packets without numbers, or a number repeated on every page of a different order, can mis-split |
| 9 | Sign errors | Parentheses, minus and `CR` handled; the wording check is a heuristic warning only | Heuristic |
| 10 | Prior change orders confusing the sums | Uses the distinct "prior to this change order" and "including this change order" labels; a mismatch is an error for a human | Flagged, never auto-fixed |
| 11 | Units and currency | Assumes one currency; days are parsed but calendar vs working days is dropped (visible in the evidence) | Limitation |
| 12 | LLM hallucination | Value or quote absent from the document, so the confidence cap applies | Mitigated; see next row |
| 13 | LLM quotes a real but wrong span (e.g. the architect's name for the owner) | Passes grounding, since grounding proves the text exists, not that it is the right text | Not detectable here; corroboration by rules helps only if they found it too |
| 14 | LLM non-JSON, API error, or very long input (truncated at 60k characters) | `extractor_failed` warning; falls back to rules | Handled |
| 15 | Prompt injection in the document | Fenced and ignored by instruction; output must still validate and ground | Structural defence, not tested against a live model |

## What I would do next

1. Build a labelled corpus of real change orders and calibrate confidences against it (for example
   isotonic regression), then re-fit the review threshold to a target error rate.
2. Benchmark the LLM path live, and measure how much `--llm-fallback` recovers per dollar.
3. Test OCR on genuinely bad scans; add deskew and a second engine for disagreement checks.
4. Capture reviewer corrections and use them to grow the label vocabulary and tune the weights.
