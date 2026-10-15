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
    color-scheme: dark;
    --bg: #0d0f12; --panel: #15181d; --panel-2: #1b1f26; --line: #272c35; --text: #eceef1;
    --muted: #9099a6; --gold: #f2b53b; --gold-ink: #1a1304; --steel: #6f7a8a;
    --ok: #4ec58a; --watch: #f2b53b; --risk: #ff6b57; --mark: rgba(242,181,59,.2);
    --display: Bahnschrift, "DIN Alternate", "Arial Narrow", "Segoe UI Variable Display",
      system-ui, sans-serif;
    --body: "Segoe UI Variable Text", "Segoe UI", system-ui, -apple-system, sans-serif;
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--text); font: 15px/1.55 var(--body); }
  body::before { content: ""; position: fixed; inset: 0 0 auto 0; height: 520px; z-index: -1;
    background: radial-gradient(900px 340px at 78% -80px, rgba(242,181,59,.13), transparent 70%); }
  .wrap { max-width: 1160px; margin: 0 auto; padding: 0 20px 80px; }

  .topbar { display: flex; align-items: center; gap: 12px; padding: 18px 0; }
  .mark { width: 30px; height: 30px; border-radius: 7px; background: var(--gold);
          display: grid; place-items: center; color: var(--gold-ink); }
  .brand { font: 700 17px var(--display); letter-spacing: .6px; text-transform: uppercase; }
  .tape { height: 8px; border-radius: 2px; opacity: .9;
    background: repeating-linear-gradient(-45deg, var(--gold) 0 12px, #111418 12px 24px); }

  .hero { display: grid; grid-template-columns: minmax(0, 1.05fr) minmax(0, 1fr); gap: 40px;
          align-items: center; padding: 48px 0 40px; }
  @media (max-width: 880px) { .hero { grid-template-columns: 1fr; gap: 28px; padding-top: 32px; } }
  h1 { margin: 0; font: 700 clamp(34px, 5.4vw, 58px)/1.02 var(--display); letter-spacing: .5px;
       text-transform: uppercase; }
  h1 em { font-style: normal; color: var(--gold); display: block; }
  .lede { margin: 18px 0 0; color: var(--muted); font-size: 17px; max-width: 46ch; }
  .facts { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 22px; }
  .facts span { padding: 5px 11px; border: 1px solid var(--line); border-radius: 99px;
                color: var(--muted); font-size: 13px; background: var(--panel); }

  .card { background: var(--panel); border: 1px solid var(--line); border-radius: 12px; }
  .intake { padding: 20px; box-shadow: 0 24px 60px -30px rgba(0,0,0,.8); }
  h2 { margin: 0 0 12px; font: 700 15px var(--display); letter-spacing: .8px;
       text-transform: uppercase; color: var(--text); }
  .drop { display: block; border: 1.5px dashed #3a414d; border-radius: 10px; padding: 20px 12px;
          text-align: center; color: var(--muted); cursor: pointer; background: var(--panel-2);
          transition: border-color .15s, background .15s; }
  .drop:hover, .drop:focus-within, .drop.over { border-color: var(--gold); color: var(--text); }
  .drop strong { color: var(--gold); }
  .drop input { position: absolute; opacity: 0; width: 1px; height: 1px; }
  #picked { margin-top: 6px; font-weight: 600; color: var(--text); word-break: break-all; }
  .or { margin: 14px 0 6px; color: var(--muted); font-size: 13px; }
  textarea { width: 100%; min-height: 130px; resize: vertical; padding: 11px; color: var(--text);
             background: var(--panel-2); border: 1px solid var(--line); border-radius: 10px;
             font: 13px/1.5 ui-monospace, "Cascadia Mono", Consolas, monospace; }
  textarea:focus-visible, button:focus-visible, .drop:focus-within {
    outline: 2px solid var(--gold); outline-offset: 2px; }
  .actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; align-items: center; }
  button { font: 600 14px var(--body); padding: 10px 18px; border-radius: 8px; cursor: pointer;
           border: 1px solid #343b46; background: var(--panel-2); color: var(--text); }
  button:hover { border-color: var(--steel); }
  button.primary { background: var(--gold); border-color: var(--gold); color: var(--gold-ink);
                   font-weight: 700; }
  button.primary:hover { filter: brightness(1.08); }
  button.link { border: 0; background: none; padding: 10px 4px; color: var(--gold);
                font-weight: 500; }
  button:disabled { opacity: .55; cursor: progress; }
  #status { margin-top: 10px; font-size: 13px; color: var(--muted); min-height: 1.2em; }
  #status .err { color: var(--risk); font-weight: 600; }

  .results { display: grid; gap: 16px; scroll-margin-top: 20px; }
  .verdict { display: flex; gap: 22px; align-items: center; padding: 20px 22px; flex-wrap: wrap; }
  .stamp { font: 700 22px/1 var(--display); letter-spacing: 2px; text-transform: uppercase;
           padding: 10px 15px 9px; border: 3px solid currentColor; border-radius: 6px;
           transform: rotate(-3deg); }
  .stamp.ok { color: var(--ok); } .stamp.review { color: var(--risk); }
  .stamp.land { animation: land .32s cubic-bezier(.2,1.4,.4,1) both; }
  @keyframes land { from { transform: rotate(-9deg) scale(1.5); opacity: 0; } }
  @media (prefers-reduced-motion: reduce) { .stamp.land { animation: none; } }
  .verdict .meta { display: grid; gap: 2px; }
  .verdict .meta b { font: 700 18px var(--display); letter-spacing: .4px; }
  .verdict .meta span { color: var(--muted); font-size: 13px; word-break: break-all; }
  .why { margin-left: auto; color: var(--muted); font-size: 14px; max-width: 36ch; }
  @media (max-width: 640px) { .why { margin-left: 0; max-width: none; } }

  .ledger { padding: 6px 22px 10px; }
  .row { display: grid; grid-template-columns: 170px minmax(0, 1fr) 150px; gap: 6px 18px;
         padding: 15px 0; border-bottom: 1px solid var(--line); align-items: start; }
  .row:last-child { border-bottom: 0; }
  .name { color: var(--muted); font-weight: 600; font-size: 13.5px; padding-top: 3px; }
  .value { font: 600 17px/1.35 var(--display); letter-spacing: .2px; word-break: break-word;
           font-variant-numeric: tabular-nums; }
  .value.none { color: var(--muted); font: italic 400 14px var(--body); }
  .quote { margin-top: 6px; font-size: 12.5px; color: var(--muted); word-break: break-word; }
  mark { background: var(--mark); color: #f6d58c; padding: 1px 5px; border-radius: 3px;
         box-decoration-break: clone; -webkit-box-decoration-break: clone; }
  .conf { justify-self: end; text-align: right; display: grid; gap: 4px; justify-items: end; }
  .chip { display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px;
          border-radius: 99px; font-size: 12.5px; font-weight: 600; color: var(--tone);
          border: 1px solid color-mix(in srgb, var(--tone) 45%, transparent);
          background: color-mix(in srgb, var(--tone) 12%, transparent); }
  .chip::before { content: ""; width: 7px; height: 7px; border-radius: 50%;
                  background: var(--tone); }
  .conf small { color: var(--muted); font-size: 12px; }
  @media (max-width: 640px) {
    .row { grid-template-columns: 1fr auto; }
    .name { grid-column: 1 / -1; padding: 0; }
  }

  .issues { padding: 18px 22px; }
  .issues ul { margin: 0; padding: 0; list-style: none; display: grid; gap: 12px; }
  .issues li { padding-left: 13px; border-left: 3px solid var(--tone); }
  .issues code { font: 700 13px var(--body); color: var(--tone); }
  .sev-error { --tone: var(--risk); } .sev-warning { --tone: var(--watch); }

  details.raw { padding: 4px 22px 16px; }
  summary { cursor: pointer; font: 700 15px var(--display); letter-spacing: .8px;
            text-transform: uppercase; padding: 12px 0; }
  .rawbar { display: flex; justify-content: flex-end; margin-bottom: 8px; }
  pre { margin: 0; overflow: auto; max-height: 340px; padding: 13px; background: var(--panel-2);
        border-radius: 8px; font: 12.5px/1.5 ui-monospace, "Cascadia Mono", Consolas, monospace; }
  footer { margin-top: 40px; color: var(--muted); font-size: 13px; }
  [hidden] { display: none !important; }
</style>
</head>
<body>
<div class="wrap">
  <div class="topbar">
    <div class="mark" aria-hidden="true">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
        <path d="M14 4l6 6-3 3-6-6z"/><path d="M11 7L4 14l2 2 7-7"/><path d="M5 20l5-5"/></svg>
    </div>
    <div class="brand">Change Order Extractor</div>
  </div>
  <div class="tape" aria-hidden="true"></div>

  <section class="hero">
    <div>
      <h1>Read the change order.<em>Trust what checks out.</em></h1>
      <p class="lede">Drop in a PDF or pasted text. Every field comes back with the line it
        was read from and a status, and the contract sums are checked so a person only looks
        where it matters.</p>
      <div class="facts"><span>PDF and text</span><span>Evidence for every value</span>
        <span>Sums checked to the cent</span></div>
    </div>

    <section class="card intake" aria-label="Input">
      <h2>Upload a change order</h2>
      <label class="drop" id="drop">
        <input id="file" type="file" accept=".pdf,.txt">
        <strong>Choose a file</strong> or drop it here
        <div>PDF or text</div>
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
  </section>

  <div class="results" id="result" hidden>
    <section class="card verdict">
      <div class="stamp" id="badge"></div>
      <div class="meta"><b id="overall"></b><span id="src"></span></div>
      <div class="why" id="why"></div>
    </section>
    <section class="card ledger" id="fields" aria-label="Extracted fields"></section>
    <section class="card issues" id="issuesCard" hidden>
      <h2>Things to check</h2>
      <ul id="issues"></ul>
    </section>
    <details class="card raw">
      <summary>Raw JSON</summary>
      <div class="rawbar"><button id="copy" type="button">Copy JSON</button></div>
      <pre id="json"></pre>
    </details>
  </div>
  <footer>Confidence is a routing signal, not a probability. Always check flagged documents
    against the original.</footer>
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
  $("result").hidden = true;
});
$("copy").addEventListener("click", () => navigator.clipboard.writeText($("json").textContent));

function el(tag, text, cls) {
  const n = document.createElement(tag);
  if (text !== undefined) n.textContent = text;
  if (cls) n.className = cls;
  return n;
}
const tone = (c) => c >= 0.85 ? "var(--ok)" : c >= 0.7 ? "var(--watch)" : "var(--risk)";
const status = (c) => c >= 0.85 ? "On track" : c >= 0.7 ? "Watch" : "At risk";
const label = (name) => {
  const s = name.replaceAll("_", " ");
  return s[0].toUpperCase() + s.slice(1);
};

function render(data) {
  $("result").hidden = false;
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
      const chip = el("span", status(f.confidence), "chip");
      chip.style.setProperty("--tone", tone(f.confidence));
      conf.append(chip, el("small", f.confidence.toFixed(2) + " \u2022 " + f.method));
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
  $("result").scrollIntoView({ behavior: "smooth", block: "start" });
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
