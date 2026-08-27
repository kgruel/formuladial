"""Emit a single self-contained lookup page with both datasets embedded.

Territory membership is stored as a hex bitmask over the territory list, which
is what keeps the payload small -- one record often covers dozens of countries.

The page makes you name your machine before it shows a number.  The two models
mix differently and their numbers are not interchangeable, so a silent default
would be the one bug that actually matters here.
"""
import json, os

DATA = "site/data/formula_settings.json"
OUT = "site/index.html"


def pack(data):
    recs = data["records"]
    terrs = sorted({t for r in recs for t in r["territories"]})
    ti = {t: i for i, t in enumerate(terrs)}
    brands = sorted({r["brand"] for r in recs})
    bi = {b: i for i, b in enumerate(brands)}
    rows = []
    for r in recs:
        mask = 0
        for t in r["territories"]:
            mask |= 1 << ti[t]
        rows.append([1 if r["model"] == "pro" else 0, bi[r["brand"]], r["type"],
                     r["stage"], r["setting"], format(mask, "x"), r["upc"],
                     r.get("alt_setting"), r.get("updated")])
    return {"T": terrs, "B": brands, "R": rows,
            "M": {k: {"label": v["label"], "note": v["note"], "counts": v["counts"]}
                  for k, v in data["models"].items()}}


TEMPLATE = r"""<title>Brezza Setting Finder</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Familjen+Grotesk:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=Source+Sans+3:wght@400;500;600&display=swap">
<style>
:root{
  --ground:#f2f0ec; --surface:#fffefc; --raised:#e9e6e0;
  --ink:#1c2329; --ink-2:#4c565e; --ink-3:#7b858d;
  --line:#dbd7d0; --line-2:#c9c4bb;
  --accent:#0f6d72; --accent-soft:#d9e8e7; --accent-ink:#0a4a4e;
  --dial:#c9821a; --dial-ink:#5a3a08; --dial-soft:#f6e6cd;
  --stop:#9c3328; --stop-soft:#f4dedb; --stop-ink:#7c2820;
  --focus:#0f6d72;
  --shadow:0 1px 2px rgba(28,35,41,.06),0 6px 18px rgba(28,35,41,.05);
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --ground:#12171b; --surface:#1a2126; --raised:#232b31;
    --ink:#eceae6; --ink-2:#a8b1b7; --ink-3:#77828a;
    --line:#2c353b; --line-2:#3b464d;
    --accent:#5fc8c8; --accent-soft:#173436; --accent-ink:#9fe0df;
    --dial:#e8a94a; --dial-ink:#f6dcae; --dial-soft:#3a2c14;
    --stop:#e0857a; --stop-soft:#3a201d; --stop-ink:#f2bdb6;
    --focus:#5fc8c8;
    --shadow:0 1px 2px rgba(0,0,0,.3),0 6px 18px rgba(0,0,0,.25);
  }
}
:root[data-theme="dark"]{
  --ground:#12171b; --surface:#1a2126; --raised:#232b31;
  --ink:#eceae6; --ink-2:#a8b1b7; --ink-3:#77828a;
  --line:#2c353b; --line-2:#3b464d;
  --accent:#5fc8c8; --accent-soft:#173436; --accent-ink:#9fe0df;
  --dial:#e8a94a; --dial-ink:#f6dcae; --dial-soft:#3a2c14;
  --stop:#e0857a; --stop-soft:#3a201d; --stop-ink:#f2bdb6;
  --focus:#5fc8c8;
  --shadow:0 1px 2px rgba(0,0,0,.3),0 6px 18px rgba(0,0,0,.25);
}

*{box-sizing:border-box}
body{
  margin:0; background:var(--ground); color:var(--ink);
  font-family:"Source Sans 3",ui-sans-serif,system-ui,sans-serif;
  font-size:16px; line-height:1.55; -webkit-font-smoothing:antialiased;
}
.wrap{max-width:860px; margin:0 auto; padding:0 20px 72px}
:focus-visible{outline:2px solid var(--focus); outline-offset:2px; border-radius:4px}

header{padding:40px 0 20px}
.eyebrow{
  font-family:"IBM Plex Mono",ui-monospace,monospace; font-size:11px;
  letter-spacing:.16em; text-transform:uppercase; color:var(--ink-3);
  display:flex; gap:10px; align-items:center;
}
.eyebrow::after{content:""; flex:1; height:1px; background:var(--line)}
h1{
  font-family:"Familjen Grotesk",ui-sans-serif,system-ui,sans-serif;
  font-weight:700; font-size:clamp(30px,5.5vw,44px); line-height:1.05;
  letter-spacing:-.02em; margin:14px 0 8px; text-wrap:balance;
}
.lede{color:var(--ink-2); max-width:62ch; margin:0}

/* ---- machine picker: the page's one required decision ---- */
.machine{
  margin:24px 0 0; padding:18px; border-radius:12px;
  background:var(--surface); border:1px solid var(--line); box-shadow:var(--shadow);
}
.machine h2{
  font-family:"IBM Plex Mono",monospace; font-size:11px; letter-spacing:.14em;
  text-transform:uppercase; color:var(--ink-3); margin:0 0 12px; font-weight:500;
}
.pick{display:grid; grid-template-columns:1fr 1fr; gap:10px}
.pick button{
  font:inherit; text-align:left; cursor:pointer; padding:13px 15px;
  background:var(--ground); color:var(--ink); border:1.5px solid var(--line-2);
  border-radius:10px; display:flex; flex-direction:column; gap:3px;
}
.pick button:hover{border-color:var(--accent)}
.pick button[aria-pressed="true"]{
  border-color:var(--accent); background:var(--accent-soft); color:var(--accent-ink);
}
.pick .n{font-family:"Familjen Grotesk",sans-serif; font-weight:600; font-size:16px}
.pick .d{font-size:12.5px; color:var(--ink-3); line-height:1.35}
.pick button[aria-pressed="true"] .d{color:var(--accent-ink); opacity:.85}
.machine .note{margin:12px 0 0; font-size:13.5px; color:var(--ink-2)}
header .note{margin:14px 0 0; font-size:13.5px; color:var(--ink-2); max-width:60ch}
footer a{color:var(--ink-2)}

/* ---- controls ---- */
.controls{
  position:sticky; top:0; z-index:20; padding:14px 0 12px;
  background:linear-gradient(var(--ground) 78%,transparent);
  display:flex; flex-direction:column; gap:10px;
}
.searchrow{display:flex; gap:10px; flex-wrap:wrap}
.field{
  flex:1 1 320px; display:flex; align-items:center; gap:10px;
  background:var(--surface); border:1px solid var(--line-2);
  border-radius:10px; padding:0 14px; box-shadow:var(--shadow);
}
.field:focus-within{border-color:var(--focus); box-shadow:0 0 0 3px var(--accent-soft)}
.field svg{flex:none; width:17px; height:17px; color:var(--ink-3)}
input,select{
  font:inherit; color:var(--ink); background:transparent; border:0; outline:0;
  width:100%; padding:13px 0;
}
input::placeholder{color:var(--ink-3)}
.tag{
  font-family:"IBM Plex Mono",monospace; font-size:10px; letter-spacing:.12em;
  text-transform:uppercase; padding:3px 7px; border-radius:5px; flex:none;
  white-space:nowrap; color:var(--accent-ink); background:var(--accent-soft);
}
.terr{
  flex:0 1 260px; display:flex; align-items:center; gap:8px;
  background:var(--surface); border:1px solid var(--line-2);
  border-radius:10px; padding:0 12px; box-shadow:var(--shadow);
}
.terr select{padding:13px 0; cursor:pointer}
.terr label{
  font-family:"IBM Plex Mono",monospace; font-size:10px; letter-spacing:.12em;
  text-transform:uppercase; color:var(--ink-3); flex:none;
}
.lotrow{display:flex; gap:10px; align-items:center; flex-wrap:wrap}
.lotfield{flex:0 1 300px}
.lotfield input{cursor:text; text-transform:uppercase}
.lotstate{font-size:13px; color:var(--ink-3)}
.lotstate.on{
  font-family:"IBM Plex Mono",monospace; font-size:11px; letter-spacing:.08em;
  text-transform:uppercase; color:var(--dial-ink); background:var(--dial-soft);
  border:1px solid var(--dial); padding:3px 8px; border-radius:5px;
}
.hist{
  font-family:"IBM Plex Mono",monospace; font-size:9.5px; letter-spacing:.12em;
  text-transform:uppercase; color:var(--ink-3); border:1px solid var(--line-2);
  padding:1px 5px; border-radius:4px; vertical-align:middle; margin-left:6px;
}
.fresh{font-size:12px; color:var(--ink-3); font-variant-numeric:tabular-nums}
.std{
  font-family:"IBM Plex Mono",monospace; font-size:11px; letter-spacing:.06em;
  color:var(--ink-3); border:1px solid var(--line-2); padding:2px 7px; border-radius:5px;
}
.chips{display:flex; gap:7px; flex-wrap:wrap}
.chip{
  font:inherit; font-size:13px; color:var(--ink-2); cursor:pointer;
  background:var(--raised); border:1px solid transparent; border-radius:999px;
  padding:5px 12px;
}
.chip:hover{color:var(--ink); border-color:var(--line-2)}

/* ---- results ---- */
.count{
  font-family:"IBM Plex Mono",monospace; font-size:11px; letter-spacing:.1em;
  text-transform:uppercase; color:var(--ink-3); padding:16px 2px 8px;
  border-top:1px solid var(--line); margin-top:4px;
}
ol{list-style:none; margin:0; padding:0; display:flex; flex-direction:column; gap:8px}
.rec{
  display:grid; grid-template-columns:auto 1fr; gap:16px; align-items:center;
  background:var(--surface); border:1px solid var(--line);
  border-radius:12px; padding:14px 16px; box-shadow:var(--shadow);
}
/* the machine's numbered selector, borrowed as the unit of the page */
.dial{
  flex:none; width:56px; height:56px; border-radius:50%;
  display:grid; place-items:center; position:relative;
  background:var(--dial-soft); border:2px solid var(--dial);
}
.dial span{
  font-family:"IBM Plex Mono",monospace; font-variant-numeric:tabular-nums;
  font-weight:600; font-size:21px; color:var(--dial-ink); line-height:1;
}
.dial::before{
  content:""; position:absolute; top:4px; left:50%; width:2px; height:7px;
  background:var(--dial); border-radius:1px; transform:translateX(-50%);
}
.dial.stop{background:var(--stop-soft); border-color:var(--stop)}
.dial.stop span{color:var(--stop-ink); font-size:24px}
.dial.stop::before{background:var(--stop)}
.name{
  font-family:"Familjen Grotesk",sans-serif; font-weight:600; font-size:17px;
  line-height:1.25; margin:0 0 3px; text-wrap:balance;
}
.name em{font-style:normal; background:var(--accent-soft); color:var(--accent-ink); border-radius:3px}
.meta{display:flex; flex-wrap:wrap; gap:6px 12px; font-size:13px; color:var(--ink-2); align-items:center}
.stage{
  font-family:"IBM Plex Mono",monospace; font-size:11px; letter-spacing:.06em;
  color:var(--accent-ink); background:var(--accent-soft);
  padding:2px 7px; border-radius:5px;
}
.nope{
  font-family:"IBM Plex Mono",monospace; font-size:11px; letter-spacing:.06em;
  color:var(--stop-ink); background:var(--stop-soft); border:1px solid var(--stop);
  padding:2px 7px; border-radius:5px;
}
.alt{
  font-family:"IBM Plex Mono",monospace; font-size:11px; letter-spacing:.06em;
  color:var(--dial-ink); background:var(--dial-soft); border:1px solid var(--dial);
  padding:2px 7px; border-radius:5px;
}
.where{color:var(--ink-3)}
.upc{font-family:"IBM Plex Mono",monospace; font-size:12px; color:var(--ink-3);
     font-variant-numeric:tabular-nums}
.empty{padding:26px 2px; color:var(--ink-2)}
.empty p{margin:0 0 8px}

.warn{
  display:flex; gap:11px; align-items:flex-start; margin:22px 0 0; padding:12px 14px;
  border-radius:10px; background:var(--dial-soft); color:var(--dial-ink);
  border:1px solid var(--dial); font-size:14px;
}
.disclose{
  margin:26px 0 0; padding:20px; border-radius:12px;
  background:var(--surface); border:1px solid var(--line); box-shadow:var(--shadow);
}
.disclose h2{
  font-family:"Familjen Grotesk",sans-serif; font-weight:600; font-size:19px;
  margin:0 0 6px; letter-spacing:-.01em;
}
.disclose > p{margin:0 0 16px; color:var(--ink-2); max-width:62ch; font-size:14.5px}
.disclose ol{gap:14px; counter-reset:d}
.disclose li{
  display:grid; grid-template-columns:auto 1fr; gap:13px; align-items:start;
}
.disclose li::before{
  counter-increment:d; content:counter(d);
  font-family:"IBM Plex Mono",monospace; font-size:12px; font-weight:600;
  width:24px; height:24px; border-radius:50%; display:grid; place-items:center;
  background:var(--accent-soft); color:var(--accent-ink); margin-top:1px;
}
.disclose h3{
  font-size:15px; margin:0 0 3px; font-weight:600;
  font-family:"Familjen Grotesk",sans-serif;
}
.disclose p{margin:0; font-size:14px; color:var(--ink-2)}
.disclose code{
  font-family:"IBM Plex Mono",monospace; font-size:12px; color:var(--ink-2);
  background:var(--raised); padding:1px 5px; border-radius:4px;
  overflow-wrap:anywhere;
}
.fields{
  display:flex; flex-wrap:wrap; gap:5px; margin-top:8px;
}
.fields span{
  font-family:"IBM Plex Mono",monospace; font-size:11px;
  background:var(--stop-soft); color:var(--stop-ink); border:1px solid var(--stop);
  padding:2px 7px; border-radius:5px;
}
.gate{
  font-family:"IBM Plex Mono",monospace; font-size:10px; letter-spacing:.1em;
  text-transform:uppercase; padding:2px 7px; border-radius:5px; margin-left:6px;
  border:1px solid var(--line-2); color:var(--ink-3); white-space:nowrap;
}
footer{
  margin-top:22px; padding-top:18px; border-top:1px solid var(--line);
  font-size:13px; color:var(--ink-3);
}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
@media (max-width:560px){
  .pick{grid-template-columns:1fr}
  .rec{gap:13px; padding:12px 13px}
  .dial{width:48px; height:48px}
  .dial span{font-size:18px}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
</style>

<div class="wrap">
<header>
  <div class="eyebrow">Unofficial &mdash; not affiliated with Baby Brezza</div>
  <h1>What number does this tin need?</h1>
  <p class="lede">Every powder setting Baby Brezza publishes, including the alternate
    numbers your machine's lot number unlocks and the discontinued original their finder
    no longer offers. No email, no lookup limit, and nothing you type leaves this tab.</p>
  <p class="note"><strong>Check the number against your own tin before mixing a
    bottle</strong> &mdash; this is infant food prep, and manufacturers reformulate.
    Dates shown here mean "not touched since", never "verified on".</p>
</header>

<section class="machine">
  <h2>Which machine do you have?</h2>
  <div class="pick" id="pick"></div>
  <p class="note" id="machineNote"></p>
</section>

<div class="controls" id="controls" hidden>
  <div class="searchrow">
    <div class="field">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
        <circle cx="11" cy="11" r="7"></circle><path d="m20 20-3.5-3.5"></path>
      </svg>
      <input id="q" type="search" autocomplete="off" spellcheck="false"
             aria-label="Search by brand, formula name, or barcode">
      <span class="tag" id="mode" hidden>Barcode</span>
    </div>
    <div class="terr">
      <label for="terr">Sold in</label>
      <select id="terr" aria-label="Country the formula was bought in"></select>
    </div>
  </div>
  <div class="lotrow" id="lotrow">
    <div class="terr lotfield">
      <label for="lot">Lot no.</label>
      <input id="lot" type="text" maxlength="14" autocomplete="off" spellcheck="false"
             placeholder="on the sticker underneath" aria-label="Machine lot number">
    </div>
    <span class="lotstate" id="lotstate"></span>
  </div>
  <div class="chips" id="chips"></div>
</div>

<div class="count" id="count"></div>
<ol id="out"></ol>
<div class="empty" id="empty" hidden></div>

<section class="disclose">
  <h2>What the official finder does with your data</h2>
  <p>Baby Brezza's own settings finder won't hand over a number until you type an
  email address. Read out of their <code>formula-settings.js</code>, here is where
  that goes. Three destinations, only one of which asks permission.</p>
  <ol>
    <li>
      <div>
        <h3>Every lookup is logged<span class="gate">no opt-in</span></h3>
        <p>POSTed to <code>babybrezzaserver.com/index.php/without_response/getsetting</code>
        on each search. Not tied to the consent checkbox, and it fires whether or not
        you tick anything:</p>
        <div class="fields">
          <span>email</span><span>ip_address</span><span>user_agent</span>
          <span>city</span><span>state_prov</span><span>zip</span><span>country</span>
          <span>language</span><span>touch_device</span><span>lot_number</span>
          <span>brand / type / territory</span>
        </div>
      </div>
    </li>
    <li>
      <div>
        <h3>Marketing lists<span class="gate">checkbox-gated</span></h3>
        <p>Your address goes to <code>optin.babybrezza.com/api/subscribe/listrak</code>
        on the US site, or <code>/klaviyo</code> elsewhere — but only if you tick
        "I agree to receive marketing emails". This part is honest.</p>
      </div>
    </li>
    <li>
      <div>
        <h3>Warranty registration<span class="gate">skippable</span></h3>
        <p>Name and email to <code>portal.babybrezza.com/api/warranty/activate</code>,
        offered alongside the settings and safe to skip.</p>
      </div>
    </li>
  </ol>
  <p style="margin-top:16px">The location fields aren't guessed from your address —
  the page loads an IP-geolocation script that writes your city, region, ZIP and IP
  into cookies, which the logger then reads back. Meanwhile the email itself is
  checked by a regular expression in your browser and nothing else: the settings API
  never asks for one. That is the whole lock.</p>
  <p style="margin-top:10px"><strong>This page sends nothing anywhere.</strong>
  Every setting is already in the file your browser downloaded; searching runs
  locally, and your lot number stays in this tab.</p>
</section>

<div class="warn">
  <span aria-hidden="true">⚠</span>
  <div><strong>Check the number against your own tin before mixing.</strong>
  The two machines mix differently and their numbers are not interchangeable.
  Manufacturers reformulate, and the original Formula Pro's data comes from a
  backend Baby Brezza retired. That same backend also holds a frozen copy of the
  Advanced line, and <strong>27% of the settings in it have since changed</strong>
  on the live one — so treat the original's numbers as a starting point, not gospel.
  Where a result shows <em>No dial position</em>, Baby Brezza publishes a
  setting of 0 for that formula; the dial only runs 1–10, so ask them before
  using it. A <em>Lot 11…</em> chip means Baby Brezza has a second number for
  that formula, used only on Advanced and Advanced WiFi machines whose lot
  number starts with 11 — check the sticker on yours. The Mini never uses it.</div>
</div>

<footer id="foot"></footer>
</div>

<script>
const D = __DATA__;
const QUICK = __QUICK__;

const fold = s => (s||"").normalize("NFKD").replace(/[\u0300-\u036f]/g,"").toLowerCase();
const HAY  = D.R.map(r => fold(D.B[r[1]] + " " + r[2] + " " + r[3]));
const MASK = D.R.map(r => BigInt("0x" + r[5]));
const MODEL_KEY = ["advanced","pro"];

const el = id => document.getElementById(id);
const $q=el("q"), $terr=el("terr"), $out=el("out"), $count=el("count"),
      $empty=el("empty"), $mode=el("mode"), $chips=el("chips"),
      $controls=el("controls"), $pick=el("pick"), $note=el("machineNote"),
      $lot=el("lot"), $lotrow=el("lotrow"), $lotstate=el("lotstate");

const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
function fmtDate(iso){
  if (!iso) return "";
  const [y,m] = iso.split("-");
  return `${MONTHS[+m - 1]} ${y}`;
}

// Baby Brezza reads the machine's lot number and switches to a second set of
// settings when it starts with 11. Their own field is uppercased, max 14.
const lotIsAlt = () => $lot.value.trim().toUpperCase().startsWith("11");

const store = {
  get(k,d){ try{ return localStorage.getItem(k) ?? d }catch(e){ return d } },
  set(k,v){ try{ localStorage.setItem(k,v) }catch(e){} }
};

// The Advanced is the machine still being sold, so it is the default. The
// original stays one click away because its numbers are not interchangeable.
let model = store.get("brezza.model", "advanced");
if (!MODEL_KEY.includes(model)) model = "advanced";

const esc = s => String(s).replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));

// --- machine picker
$pick.innerHTML = MODEL_KEY.map(k => {
  const m = D.M[k], c = m.counts;
  return `<button type="button" data-model="${k}" aria-pressed="false">
    <span class="n">${esc(m.label)}</span>
    <span class="d">${c.records.toLocaleString()} settings · ${c.brands} brands${
      k === "advanced" ? ` · also the WiFi and Mini · updated through ${fmtDate(c.newest)}`
                       : " · discontinued FRP0045 · frozen since ~2022"}</span>
  </button>`;
}).join("");

$pick.addEventListener("click", e => {
  const b = e.target.closest("button[data-model]");
  if (!b) return;
  model = b.dataset.model;
  store.set("brezza.model", model);
  applyModel();
  run();
  $q.focus();
});

function applyModel(){
  for (const b of $pick.querySelectorAll("button[data-model]"))
    b.setAttribute("aria-pressed", String(b.dataset.model === model));
  if (!model){
    $note.textContent = "Pick one to search — the two machines take different numbers for the same tin.";
    $controls.hidden = true;
    return;
  }
  $controls.hidden = false;
  $note.textContent = D.M[model].note;
  // Only Advanced and Advanced WiFi take the lot-number branch; the Mini and
  // the original never do.
  $lotrow.hidden = model !== "advanced";
  syncLot();
  $q.placeholder = model === "pro"
    ? "Kendamil, HiPP Combiotic, Enfamil Gentlease…"
    : "Enfamil NeuroPro, Kirkland, 070074680644…";

  // Territory names differ between the two datasets; only offer this model's.
  const seen = new Set();
  for (let i = 0; i < D.R.length; i++){
    if (MODEL_KEY[D.R[i][0]] !== model) continue;
    for (let t = 0; t < D.T.length; t++)
      if ((MASK[i] >> BigInt(t)) & 1n) seen.add(D.T[t]);
  }
  const list = D.T.filter(t => seen.has(t));
  const prev = store.get("brezza.terr." + model, "");
  $terr.innerHTML = '<option value="">Anywhere</option>' +
    list.map(t => `<option>${esc(t)}</option>`).join("");
  $terr.value = list.includes(prev) ? prev : "";

  const brands = new Set();
  for (let i = 0; i < D.R.length; i++)
    if (MODEL_KEY[D.R[i][0]] === model) brands.add(D.B[D.R[i][1]]);
  $chips.innerHTML = QUICK.filter(b => brands.has(b))
    .map(b => `<button class="chip" type="button">${esc(b)}</button>`).join("");
}

$chips.addEventListener("click", e => {
  const b = e.target.closest(".chip");
  if (!b) return;
  $q.value = b.textContent; run(); $q.focus();
});

const digits = s => s.replace(/[^0-9]/g,"");
const isBarcode = s => digits(s).length >= 8 && digits(s).length === s.replace(/[\s-]/g,"").length;

function search(){
  const raw = $q.value.trim();
  if (!raw || !model) return {mode:"", hits:[]};
  const ti = D.T.indexOf($terr.value);
  const bit = ti >= 0 ? (1n << BigInt(ti)) : 0n;
  const mine = i => MODEL_KEY[D.R[i][0]] === model;

  if (isBarcode(raw)){
    const want = digits(raw);
    const alt = want.length === 13 && want[0] === "0" ? want.slice(1) : null;
    const hits = [];
    for (let i = 0; i < D.R.length; i++){
      if (!mine(i)) continue;
      for (const u of D.R[i][6]){
        const d = digits(u);
        if (d === want || (alt && d === alt)){ hits.push(i); break }
      }
    }
    // A barcode identifies the tin, so country never narrows it further.
    return {mode:"barcode", hits};
  }

  const terms = fold(raw).split(/\s+/).filter(Boolean);
  const hits = [];
  for (let i = 0; i < D.R.length; i++){
    if (!mine(i)) continue;
    if (ti >= 0 && (MASK[i] & bit) === 0n) continue;
    let ok = true;
    for (const t of terms) if (!HAY[i].includes(t)){ ok = false; break }
    if (ok) hits.push(i);
  }
  hits.sort((a,b) => {
    const sa = fold(D.B[D.R[a][1]]).startsWith(terms[0]) ? 0 : 1;
    const sb = fold(D.B[D.R[b][1]]).startsWith(terms[0]) ? 0 : 1;
    return sa !== sb ? sa - sb : HAY[a].length - HAY[b].length;
  });
  return {mode:"text", hits};
}

function mark(text, terms){
  if (!terms.length) return esc(text);
  const f = fold(text);
  // NFKD expands some characters (TM -> "tm"), which would shift every offset
  // after it. When folding changes the length, skip highlighting rather than
  // slice the original string at the wrong place.
  if (f.length !== text.length) return esc(text);
  const spans = [];
  for (const t of terms){
    let i = 0;
    while ((i = f.indexOf(t, i)) !== -1){ spans.push([i, i + t.length]); i += t.length }
  }
  if (!spans.length) return esc(text);
  spans.sort((a,b) => a[0] - b[0]);
  let out = "", at = 0;
  for (const [s,e] of spans){
    if (s < at) continue;
    out += esc(text.slice(at,s)) + "<em>" + esc(text.slice(s,e)) + "</em>";
    at = e;
  }
  return out + esc(text.slice(at));
}

function countryLabel(mask){
  const names = [];
  let total = 0;
  for (let i = 0; i < D.T.length; i++)
    if ((mask >> BigInt(i)) & 1n){ total++; if (names.length < 3) names.push(D.T[i]) }
  return total <= 3 ? names.join(", ") : names.slice(0,2).join(", ") + ` +${total-2} more`;
}

const MAX = 120;

function run(){
  const raw = $q.value.trim();
  store.set("brezza.q", raw);
  if (model) store.set("brezza.terr." + model, $terr.value);
  const {mode, hits} = search();
  $mode.hidden = mode !== "barcode";

  if (!model){ $count.textContent=""; $out.innerHTML=""; $empty.hidden=true; return }
  if (!raw){
    $count.textContent=""; $out.innerHTML=""; $empty.hidden=false;
    $empty.innerHTML = model === "pro"
      ? "<p>Type a brand name. The original Formula Pro's data carries no barcodes, so search by name.</p>"
      : "<p>Type a brand, or paste the barcode from the tin.</p>";
    return;
  }
  if (!hits.length){
    $count.textContent=""; $out.innerHTML=""; $empty.hidden=false;
    $empty.innerHTML = mode === "barcode"
      ? (model === "pro"
          ? "<p>The original Formula Pro's data has no barcodes in it — search by brand name instead.</p>"
          : "<p>No tin with that barcode. Try the brand name — barcodes vary by pack size.</p>")
      : ($terr.value
          ? `<p>Nothing matching that in ${esc($terr.value)}. Try <b>Sold in → Anywhere</b>.</p>`
          : `<p>No match in the ${esc(D.M[model].label)} data. Try just the brand name.</p>`);
    return;
  }
  $empty.hidden = true;

  const terms = mode === "text" ? fold(raw).split(/\s+/).filter(Boolean) : [];
  $count.textContent = (hits.length === 1 ? "1 match" : hits.length + " matches")
    + (hits.length > MAX ? ` — showing first ${MAX}` : "");

  $out.innerHTML = hits.slice(0, MAX).map(i => {
    const r = D.R[i], standard = r[4], altSetting = r[7];
    // A lot-11 Advanced takes the alternate number, so show that one big and
    // keep the standard one visible rather than quietly swapping it out.
    const useAlt = model === "advanced" && altSetting != null && lotIsAlt();
    const setting = useAlt ? altSetting : standard;
    // The dial runs 1-10. A published 0 is not a position on it, so it is
    // never shown as a number you could turn the machine to.
    const num = typeof setting === "number" && setting > 0;
    const where = $terr.value ? "" : `<span class="where">${esc(countryLabel(MASK[i]))}</span>`;
    const upc = mode === "barcode" && r[6].length ? `<span class="upc">${esc(r[6][0])}</span>` : "";
    const altChip = altSetting == null ? ""
      : useAlt
        ? `<span class="std">Standard machine: ${standard}</span>`
        : `<span class="alt" title="Formula Pro Advanced and Advanced WiFi units whose lot number starts with 11. The Mini and the original never use this.">Lot 11… → ${altSetting}</span>`;
    const fresh = r[8] ? `<span class="fresh">updated ${fmtDate(r[8])}</span>` : "";
    return `<li class="rec">
      <div class="dial${num ? "" : " stop"}" aria-hidden="true"><span>${
        num ? setting : (setting === 0 ? "0" : "&times;")}</span></div>
      <div>
        <p class="name">${mark(D.B[r[1]] + " · " + r[2], terms)}</p>
        <div class="meta">
          ${r[3] ? `<span class="stage">Stage ${esc(r[3])}</span>` : ""}
          ${num ? `<span class="sr">Setting ${setting}</span>`
                : `<span class="nope">${setting === 0 ? "No dial position" : esc(setting)}</span>`}
          ${altChip}${where}${upc}${fresh}
        </div>
      </div>
    </li>`;
  }).join("");
}

el("foot").innerHTML =
  `${D.M.advanced.counts.records.toLocaleString()} Formula Pro Advanced settings across ` +
  `${D.M.advanced.counts.territories} countries, dated by their product images: ` +
  `${D.M.advanced.counts.since_2026} touched this year, newest ${fmtDate(D.M.advanced.counts.newest)}. ` +
  `${D.M.advanced.counts.alt} carry a lot-11 alternate and ${D.M.advanced.counts.zero} ` +
  `answer with a 0 rather than a dial position. Kept alongside them for the record: ` +
  `${D.M.pro.counts.records.toLocaleString()} settings for the discontinued original, ` +
  `${D.M.pro.counts.not_compatible} of which that machine cannot dispense at all. ` +
  `Dates track when a record's image was last replaced, which is a "not touched since" ` +
  `signal rather than a "checked on" one.` +
  `<p style="margin-top:10px">Unofficial and not affiliated with Baby Brezza. ` +
  `All numbers come from Baby Brezza's own public data &mdash; ` +
  `<a href="https://github.com/USER/REPO">source and dataset</a> &middot; ` +
  `<a href="https://github.com/USER/REPO/blob/main/docs/HOW-IT-WORKS.md">how it works</a>.</p>`;

function syncLot(){
  const raw = $lot.value.trim().toUpperCase();
  if ($lot.value !== raw) $lot.value = raw;
  store.set("brezza.lot", raw);
  if (model !== "advanced" || !raw){
    $lotstate.className = "lotstate";
    $lotstate.textContent = model === "advanced"
      ? "Optional — only lot numbers starting 11 change any setting."
      : "";
    return;
  }
  if (lotIsAlt()){
    $lotstate.className = "lotstate on";
    $lotstate.textContent = `Lot 11 — showing the alternate settings`;
  } else {
    $lotstate.className = "lotstate";
    $lotstate.textContent = "Not a lot-11 machine — standard settings apply.";
  }
}

$lot.addEventListener("input", () => { syncLot(); run() });

let timer;
$q.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(run, 90) });
$terr.addEventListener("change", run);
$lot.value = store.get("brezza.lot","");
applyModel();
$q.value = store.get("brezza.q","");
run();
if (model) $q.focus({preventScroll:true});
</script>
"""


def main():
    data = json.load(open(DATA))
    packed = pack(data)
    wanted = ["Enfamil", "Similac", "Kirkland", "Bobbie", "Kendamil", "HiPP", "Holle",
              "ByHeart", "Parent's Choice", "Good Start", "Gerber", "Earth's Best"]
    quick = [b for b in wanted if b in packed["B"]]
    html = (TEMPLATE
            .replace("__DATA__", json.dumps(packed, ensure_ascii=False, separators=(",", ":")))
            .replace("__QUICK__", json.dumps(quick, ensure_ascii=False)))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write(html)
    print(f"wrote {OUT} ({os.path.getsize(OUT)/1e6:.2f} MB), "
          f"{len(packed['R'])} records, {len(packed['B'])} brands")


if __name__ == "__main__":
    main()
