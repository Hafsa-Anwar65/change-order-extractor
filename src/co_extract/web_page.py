"""The demo page: one self-contained HTML document (no CDN, no build step).

Design: a reviewer's desk. Extracted values sit in a ledger beside the source, evidence is
shown as highlighter marks, and the verdict is a rubber stamp.
"""

from __future__ import annotations

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Change Order Extractor</title>
<style>
  :root {
    --desk: #e6eaf0; --sheet: #fbfcfe; --ink: #13203a; --muted: #5b6678; --rule: #cdd5e0;
    --field: #f1f4f8; --accent: #1d4ed8; --accent-ink: #ffffff;
    --mark: #ffe681; --mark-ink: #3a2f00;
    --ok: #1c7a4b; --review: #c4361f; --tick-off: #d5dbe5;
    --shadow: 0 1px 0 rgba(19,32,58,.06), 0 12px 30px -18px rgba(19,32,58,.35);
    --display: Bahnschrift, "DIN Alternate", "Segoe UI Variable Display", "Segoe UI", system-ui,
      sans-serif;
    --body: "Segoe UI Variable Text", "Segoe UI", system-ui, -apple-system, sans-serif;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --desk: #0e131c; --sheet: #161d29; --ink: #e8edf6; --muted: #98a3b6; --rule: #2a3445;
      --field: #1d2634; --accent: #7fa4ff; --accent-ink: #0b1220;
      --mark: #5a4c0c; --mark-ink: #fff1b0;
      --ok: #4cc38a; --review: #ff8068; --tick-off: #2d384a;
      --shadow: 0 1px 0 rgba(0,0,0,.4), 0 14px 34px -18px rgba(0,0,0,.8);
    }
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--desk); color: var(--ink); font: 15px/1.55 var(--body); }
  .wrap { max-width: 1180px; margin: 0 auto; padding: 28px 20px 72px; }
  header { margin-bottom: 22px; }
  h1 { margin: 0; font: 600 30px/1.1 var(--display); letter-spacing: .2px; }
  header p { margin: 6px 0 0; color: var(--muted); max-width: 62ch; }

  .layout { display: grid; grid-template-columns: 360px minmax(0, 1fr); gap: 22px;
            align-items: start; }
  @media (max-width: 900px) { .layout { grid-template-columns: 1fr; } }

  .sheet { background: var(--sheet); border: 1px solid var(--rule); border-radius: 6px;
           box-shadow: var(--shadow); }
  .intake { padding: 18px; position: sticky; top: 18px; }
  @media (max-width: 900px) { .intake { position: static; } }
  h2 { margin: 0 0 10px; font: 600 17px/1.2 var(--display); }

  .drop { display: block; border: 1.5px dashed var(--rule); border-radius: 6px; padding: 18px 12px;
          text-align: center; color: var(--muted); cursor: pointer; background: var(--field);
          transition: border-color .15s, background .15s; }
  .drop:hover, .drop:focus-within, .drop.over { border-color: var(--accent); color: var(--ink); }
  .drop strong { color: var(--ink); }
  .drop input { position: absolute; opacity: 0; width: 1px; height: 1px; }
  #picked { margin-top: 6px; font-weight: 600; color: var(--ink); word-break: break-all; }
  .or { margin: 14px 0 6px; color: var(--muted); font-size: 13px; }
  textarea { width: 100%; min-height: 170px; resize: vertical; padding: 10px; color: var(--ink);
             background: var(--field); border: 1px solid var(--rule); border-radius: 6px;
             font: 13px/1.5 ui-monospace, "Cascadia Mono", Consolas, monospace; }
  textarea:focus-visible, button:focus-visible, .drop:focus-within {
    outline: 2px solid var(--accent); outline-offset: 2px; }
  .actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; align-items: center; }
  button { font: 600 14px var(--body); padding: 9px 16px; border-radius: 6px; cursor: pointer;
           border: 1px solid var(--rule); background: var(--sheet); color: var(--ink); }
  button:hover { border-color: var(--muted); }
  button.primary { background: var(--accent); border-color: var(--accent);
                   color: var(--accent-ink); }
  button.link { border: 0; background: none; padding: 9px 4px; color: var(--accent);
                font-weight: 500; }
  button:disabled { opacity: .55; cursor: progress; }
  #status { margin-top: 10px; font-size: 13px; color: var(--muted); min-height: 1.2em; }
  #status .err { color: var(--review); font-weight: 600; }

  .empty { padding: 56px 24px; text-align: center; color: var(--muted); }
  .empty b { display: block; color: var(--ink); font: 600 18px var(--display); margin-bottom: 4px; }

  .verdict { display: flex; gap: 18px; align-items: center; padding: 18px 20px; flex-wrap: wrap; }
  .stamp { font: 700 20px/1 var(--display); letter-spacing: 1.5px; text-transform: uppercase;
           padding: 9px 14px 8px; border: 3px solid currentColor; border-radius: 6px;
           transform: rotate(-3deg); opacity: .94; }
  .stamp.ok { color: var(--ok); } .stamp.review { color: var(--review); }
  .stamp.land { animation: land .32s cubic-bezier(.2,1.4,.4,1) both; }
  @keyframes land { from { transform: rotate(-9deg) scale(1.5); opacity: 0; } }
  @media (prefers-reduced-motion: reduce) { .stamp.land { animation: none; } }
  .verdict .meta { display: grid; gap: 2px; }
  .verdict .meta b { font: 600 16px var(--display); }
  .verdict .meta span { color: var(--muted); font-size: 13px; word-break: break-all; }
  .why { margin-left: auto; color: var(--muted); font-size: 13px; max-width: 34ch; }
  @media (max-width: 640px) { .why { margin-left: 0; max-width: none; } }

  .results { display: grid; gap: 16px; }
  .ledger { padding: 4px 18px 8px; }
  .row { display: grid; grid-template-columns: 150px minmax(0, 1fr) 128px; gap: 6px 16px;
         padding: 13px 0; border-bottom: 1px solid var(--rule); align-items: start; }
  .row:last-child { border-bottom: 0; }
  .name { color: var(--muted); font-weight: 600; font-size: 13.5px; padding-top: 2px; }
  .value { font: 600 16px/1.35 var(--display); word-break: break-word;
           font-variant-numeric: tabular-nums; }
  .value.none { color: var(--muted); font: italic 400 14px var(--body); padding-top: 1px; }
  .quote { margin-top: 5px; font-size: 12.5px; color: var(--muted); word-break: break-word; }
  mark { background: var(--mark); color: var(--mark-ink); padding: 1px 4px; border-radius: 3px;
         box-decoration-break: clone; -webkit-box-decoration-break: clone; }
  .conf { text-align: right; padding-top: 3px; }
  .ticks { display: inline-flex; gap: 2px; vertical-align: middle; }
  .ticks i { width: 5px; height: 13px; border-radius: 1px; background: var(--tick-off); }
  .ticks i.on { background: var(--tone); }
  .conf small { display: block; margin-top: 3px; color: var(--muted); font-size: 12px; }
  @media (max-width: 640px) {
    .row { grid-template-columns: 1fr auto; }
    .name { grid-column: 1 / -1; padding: 0; }
    .conf { text-align: right; }
  }

  .issues { padding: 16px 18px; }
  .issues ul { margin: 0; padding: 0; list-style: none; display: grid; gap: 10px; }
  .issues li { padding-left: 12px; border-left: 3px solid var(--tone); }
  .issues code { font: 600 13px var(--body); color: var(--tone); }
  .sev-error { --tone: var(--review); } .sev-warning { --tone: #b07a00; }
  @media (prefers-color-scheme: dark) { .sev-warning { --tone: #f0b44a; } }

  details.raw { padding: 4px 18px 14px; }
  summary { cursor: pointer; font: 600 15px var(--display); padding: 10px 0; }
  .rawbar { display: flex; justify-content: flex-end; margin-bottom: 8px; }
  pre { margin: 0; overflow: auto; max-height: 340px; padding: 12px; background: var(--field);
        border-radius: 6px; font: 12.5px/1.5 ui-monospace, "Cascadia Mono", Consolas, monospace; }
  [hidden] { display: none !important; }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>Change Order Extractor</h1>
    <p>Drop in a change order and get its fields back with the evidence they were read from,
      a confidence for each, and a clear call on whether a person should check it.</p>
  </header>

  <div class="layout">
    <section class="sheet intake" aria-label="Input">
      <h2>Change order</h2>
      <label class="drop" id="drop">
        <input id="file" type="file" accept=".pdf,.txt,.png,.jpg,.jpeg,.tif,.tiff,.bmp,.webp">
        <strong>Choose a file</strong> or drop it here
        <div>PDF, scan, image or text</div>
        <div id="picked"></div>
      </label>
      <div class="or">Or paste the text</div>
      <textarea id="text" aria-label="Change order text"
        placeholder="Change Order No.: CO-014&#10;Net Change: $18,750.00"></textarea>
      <div class="actions">
        <button class="primary" id="go">Extract</button>
        <button id="clear" type="button">Clear</button>
        <button class="link" id="sample" type="button">Use sample text</button>
      </div>
      <div id="status" role="status"></div>
    </section>

    <div>
      <section class="sheet empty" id="empty">
        <b>Nothing extracted yet</b>
        Add a file or paste text, then choose Extract.
      </section>

      <div class="results" id="result" hidden>
        <section class="sheet verdict">
          <div class="stamp" id="badge"></div>
          <div class="meta"><b id="overall"></b><span id="src"></span></div>
          <div class="why" id="why"></div>
        </section>
        <section class="sheet ledger" id="fields" aria-label="Extracted fields"></section>
        <section class="sheet issues" id="issuesCard" hidden>
          <h2>Things to check</h2>
          <ul id="issues"></ul>
        </section>
        <details class="sheet raw">
          <summary>Raw JSON</summary>
          <div class="rawbar"><button id="copy" type="button">Copy JSON</button></div>
          <pre id="json"></pre>
        </details>
      </div>
    </div>
  </div>
</div>
<script>
const $ = (id) => document.getElementById(id);
const SAMPLE = [
  "CHANGE ORDER", "Change Order No.: CO-014", "Date: March 14, 2026",
  "Project: Riverside Medical Center - East Wing", "Owner: Riverside Health Partners LLC",
  "Contractor: Halloran Construction Inc.", "Description of Change:",
  "Furnish and install additional fire-rated drywall at the Level 2 corridor.",
  "Contract Sum Prior to This Change Order: $4,250,000.00",
  "Net Change by This Change Order: $18,750.00",
  "New Contract Sum Including This Change Order: $4,268,750.00", "Schedule Impact: 5 days",
].join("\n");
let chosen = null;

function setFile(f) { chosen = f; $("picked").textContent = f ? f.name : ""; }
$("file").addEventListener("change", (e) => setFile(e.target.files[0] || null));
const drop = $("drop");
["dragenter", "dragover"].forEach((t) => drop.addEventListener(t, (e) => {
  e.preventDefault(); drop.classList.add("over"); }));
["dragleave", "drop"].forEach((t) => drop.addEventListener(t, (e) => {
  e.preventDefault(); drop.classList.remove("over"); }));
drop.addEventListener("drop", (e) => setFile(e.dataTransfer.files[0] || null));
$("sample").addEventListener("click", () => { setFile(null); $("file").value = "";
  $("text").value = SAMPLE; });
$("clear").addEventListener("click", () => {
  setFile(null); $("file").value = ""; $("text").value = ""; $("status").textContent = "";
  $("result").hidden = true; $("empty").hidden = false;
});
$("copy").addEventListener("click", () => navigator.clipboard.writeText($("json").textContent));

function el(tag, text, cls) {
  const n = document.createElement(tag);
  if (text !== undefined) n.textContent = text;
  if (cls) n.className = cls;
  return n;
}
const tone = (c) => c >= 0.85 ? "var(--ok)" : c >= 0.7 ? "#b07a00" : "var(--review)";
const label = (name) => {
  const s = name.replaceAll("_", " ").replace(/^ocr/, "OCR");
  return s[0].toUpperCase() + s.slice(1);
};

function render(data) {
  $("empty").hidden = true; $("result").hidden = false;
  const stamp = $("badge");
  stamp.textContent = data.needs_review ? "Needs review" : "Looks good";
  stamp.className = "stamp " + (data.needs_review ? "review" : "ok");
  void stamp.offsetWidth; stamp.classList.add("land");
  $("overall").textContent = "Overall confidence " + data.overall_confidence.toFixed(2);
  $("src").textContent = data.source + " • read by " + data.extractors.join(" + ");
  const errors = data.issues.filter((i) => i.severity === "error").length;
  $("why").textContent = data.needs_review
    ? (errors ? errors + (errors > 1 ? " problems" : " problem") + " found. Check before use."
              : "Some values are below the confidence bar.")
    : "All required fields were found with enough confidence.";

  const box = $("fields"); box.replaceChildren();
  for (const [name, f] of Object.entries(data.change_order)) {
    const row = el("div", undefined, "row"), none = f.value === null;
    row.append(el("div", label(name), "name"));
    const mid = el("div");
    mid.append(el("div", none ? "Not found" : String(f.value), "value" + (none ? " none" : "")));
    if (!none && f.evidence) {
      const q = el("div", undefined, "quote");
      q.append(el("mark", f.evidence)); mid.append(q);
    }
    row.append(mid);
    const conf = el("div", undefined, "conf");
    if (!none) {
      const ticks = el("span", undefined, "ticks");
      ticks.style.setProperty("--tone", tone(f.confidence));
      const on = Math.round(f.confidence * 10);
      for (let i = 0; i < 10; i++) ticks.append(el("i", undefined, i < on ? "on" : ""));
      conf.append(ticks, el("small", f.confidence.toFixed(2) + " • " + f.method));
    }
    row.append(conf); box.append(row);
  }

  const list = $("issues"); list.replaceChildren();
  for (const i of data.issues) {
    const li = el("li", undefined, "sev-" + i.severity);
    li.append(el("code", label(i.code) + (i.field ? " — " + label(i.field) : "")),
              el("div", i.message));
    list.append(li);
  }
  $("issuesCard").hidden = data.issues.length === 0;
  $("json").textContent = JSON.stringify(data, null, 2);
}

$("go").addEventListener("click", async () => {
  const text = $("text").value;
  if (!chosen && !text.trim()) {
    $("status").textContent = "Add a file or paste some text first."; return;
  }
  const go = $("go"); go.disabled = true; $("status").textContent = "Extracting…";
  try {
    let resp;
    if (chosen) {
      const form = new FormData(); form.append("file", chosen);
      resp = await fetch("/api/extract", { method: "POST", body: form });
    } else {
      resp = await fetch("/api/extract-text", { method: "POST",
        headers: { "content-type": "application/json" }, body: JSON.stringify({ text }) });
    }
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || resp.statusText);
    $("status").textContent = ""; render(data);
  } catch (err) {
    $("status").replaceChildren(el("span", String(err.message || err), "err"));
  } finally { go.disabled = false; }
});
</script>
</body>
</html>
"""
