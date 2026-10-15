# Change-order extraction: approach and failure modes

## What I built

A pipeline that reads a change-order PDF or pasted text and returns JSON: change-order number, date,
amount, contract sum before and after, and a few other fields. Every field has a confidence score
and the line it was read from. The whole document gets a `needs_review` flag.

The part I cared about most was not accuracy, it was knowing when not to trust the output. These
numbers feed money and schedule decisions, so a value that is wrong but looks confident is worse
than a value that is missing. I designed around that.

## How it works

1. **Load.** `pypdf` for PDFs, plain UTF-8 for text. A PDF with no text layer (a scan) raises a
   clear error instead of returning empty fields. Scanned and handwritten documents are out of scope.
   `--split` cuts a packet into one text per change order.
2. **Extract.** Two extractors that fail in different ways.
   - *Rules.* Looks for known labels and reads the value next to them, or on the next line. A layout
     pass handles side-by-side columns and header-row tables. There are also fallbacks for AIA G701
     sentences such as "The Contract Sum will be decreased by this Change Order in the amount of
     $8,400.00".
   - *LLM (optional).* Claude, forced to answer through a tool call. It must copy the value and
     quote where it found it. I check both against the document afterwards.
3. **Resolve.** Candidates are parsed into real types (`Decimal`, `date`, `int`) and the strongest
   wins. If two independent extractors agree, confidence goes up. If they disagree, it goes down and
   an issue is raised.
4. **Validate.** `contract_sum_before + amount == contract_sum_after`, with exact decimals. A mismatch
   is an error and is never fixed quietly. A missing amount, or a missing `contract_sum_after`, is
   derived from the other two at lower confidence and marked as derived. The sign is compared with the
   wording ("credit", "additional"), and the date has to be plausible.
5. **Output.** A Pydantic model, validated again before it is returned. A document needs review if
   there is any error, or if its weakest required field is under 0.70.

## Choices I would defend

- **Rules and an LLM, not an LLM alone.** Rules are cheap and easy to audit. When a rule and the model
  agree, that is real corroboration because they make different mistakes. The model covers damaged
  labels and layouts the rules have not seen.
- **Confidence is computed, not asked for.** A model's own confidence is poorly calibrated. So an LLM
  answer is capped by grounding: if the value is not in the document the cap is 0.30, if the quote is
  not in the document it is 0.50, and even a fully grounded answer stops at 0.90.
- **Refuse to guess.** `03/04/2026` is flagged, not coin-flipped. `$l2,450.00` and `$1,000 + $500` are
  rejected rather than read as a number. Blank form fields (`______`) count as missing.
- **Money is `Decimal`, written out as a string.** A credit is negative whether it is written
  `(3,200.00)`, `-$3,200` or `3,200.00 CR`.
- **The document is untrusted input.** It is fenced in the prompt and the model is told not to follow
  it, but the real protection is structural. The output still has to pass schema validation and
  grounding, so an injected instruction can only produce low-confidence candidates that get flagged.
- **Failures degrade.** If the LLM call fails, the pipeline keeps the rules result and adds an
  `extractor_failed` warning.

## What I measured, and what I did not

Everything below is synthetic and I wrote it myself, rules only
(`python -m co_extract.evaluation --corpus 1000`).

| | Hand-written samples | Generated corpus |
|---|---|---|
| Documents | 9 (layouts, a packet, a real PDF file) | 1000, seed 7 |
| Fields correct | 89 / 90 (98.9%) | 9954 / 10000 (99.5%) |
| Wrong values | 0 | 2 |
| `needs_review` as expected | 9 / 9 | 977 / 1000 |
| Wrong values in documents *not* flagged | 0 | 0 |

The generator varies layout, date format and money format, and damages one money figure
(`$l2,450.00`) in 15% of documents.

Building the corpus showed me a real flaw. A damaged money figure was being dropped and then quietly
re-derived from the other two, so the document looked fine. Now an unreadable money figure is an
error and sends the document to review. Routing went from 865 to 977 correct out of 1000. Deriving a
missing `contract_sum_after` cut missing values from 83 to 44. All 2 wrong and all 44 missing values
sit inside the 114 flagged documents.

What this does not show:

- **Real documents.** I wrote the extractor and the test documents together, so these numbers show
  the behaviour I designed, not accuracy on real change orders. I have not yet scored it on real,
  independently labelled documents.
- **Calibration.** Confidences take few distinct values (0.92, 0.84, 0.72 and so on), because most
  fields come from the same kind of match. They are ordinal scores, not probabilities. 0.92 does not
  mean 92%.
- **The LLM path.** It is tested against a fake client and a local stub of the API (request shape,
  forced tool call, errors, grounding caps). I have not benchmarked it against the live model.

## Where it breaks

| # | Failure | What happens | Status |
|---|---|---|---|
| 1 | Scanned PDF or image | Clear error, no guessing | Out of scope |
| 2 | Damaged label (`0RDER`) | Rules miss it, so a required field is missing and the document goes to review. The LLM can recover it (tested with a fake model) | Mitigated |
| 3 | Damaged digits (`$l2,450.00`) | Rejected as unparseable, so review. Amount is derived from the sums at lower confidence | A human confirms |
| 4 | Ambiguous date `03/04/2026` | Read month-first, confidence x0.6, so review | Day-first is a parameter but not exposed per document |
| 5 | Label column plus separate value column, header-row tables | Paired by the layout pass | Works for layouts I tried; unusual grids fall to the LLM |
| 6 | A label the rules have not seen | Field missing, so review | Limited by a finite label list |
| 7 | Same field twice with different values (revision history) | Confidence x0.6 and a warning; the first value is chosen, which may not be the current one | Flagged, not resolved |
| 8 | Several change orders in one PDF | `--split` cuts at each new number | Packets without numbers can mis-split |
| 9 | Sign errors | Parentheses, minus and `CR` handled; wording check is a heuristic warning | Heuristic |
| 10 | Prior change orders confusing the sums | Uses the distinct "prior to" and "including this" labels; a mismatch is an error | Flagged, never auto-fixed |
| 11 | Currency and units | One currency assumed; days are parsed but calendar vs working days is lost | Limitation |
| 12 | LLM invents a value | Value or quote not in the document, so a confidence cap applies | Mitigated |
| 13 | LLM quotes a real but wrong span | Passes grounding, since grounding proves the text exists, not that it is the right text | Not detectable here |
| 14 | LLM returns garbage, API error, or input over 60k characters | `extractor_failed` warning, falls back to rules | Handled |
| 15 | Prompt injection inside the document | Fenced and ignored by instruction; output still has to validate and ground | Structural defence, not tested on a live model |

## What I would do next

1. Collect a labelled set of real change orders, score the extractor on it, and calibrate the
   confidences and the review threshold against that.
2. Run the LLM path live and measure how much `--llm-fallback` recovers per dollar.
3. Keep reviewer corrections and use them to grow the label list and tune the weights.
4. Add OCR for scanned documents, if they turn out to matter.
