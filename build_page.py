"""Emit a single self-contained lookup page with both datasets embedded.

Territory membership is stored as a hex bitmask over the territory list, which
is what keeps the payload small -- one record often covers dozens of countries.

The page makes you name your machine before it shows a number.  The two models
mix differently and their numbers are not interchangeable, so a silent default
would be the one bug that actually matters here.
"""
import json, os

from staleness import norm

DATA = "site/data/formula_settings.json"
STALE = "data/staleness.json"
OUT = "site/index.html"


def pack(data):
    recs = data["records"]
    terrs = sorted({t for r in recs for t in r["territories"]})
    ti = {t: i for i, t in enumerate(terrs)}
    brands = sorted({r["brand"] for r in recs})
    bi = {b: i for i, b in enumerate(brands)}
    # The 81 settings staleness.py caught changing between the frozen ~2022
    # copy and the live API. Its example keys are already norm()ed.
    try:
        was = {(e["brand"], e["type"], e["stage"]): "/".join(e["was"])
               for e in json.load(open(STALE))["examples"]}
    except FileNotFoundError:
        was = {}
    rows = []
    for r in recs:
        mask = 0
        for t in r["territories"]:
            mask |= 1 << ti[t]
        w = (was.get((norm(r["brand"]), norm(r["type"]), norm(r["stage"])))
             if r["model"] == "advanced" else None)
        rows.append([1 if r["model"] == "pro" else 0, bi[r["brand"]], r["type"],
                     r["stage"], r["setting"], format(mask, "x"), r["upc"],
                     r.get("alt_setting"), r.get("updated"), w])
    return {"T": terrs, "B": brands, "R": rows,
            "M": {k: {"label": v["label"], "note": v["note"], "counts": v["counts"]}
                  for k, v in data["models"].items()}}


TEMPLATE = r"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Brezza Setting Finder</title>
<script>
/* Before first paint: a stored theme choice must not flash the other one. */
try{var _t=localStorage.getItem("brezza.theme");
if(_t==="dark"||_t==="light")document.documentElement.dataset.theme=_t}catch(e){}
</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Familjen+Grotesk:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&family=Source+Sans+3:wght@400;500;600&display=swap">
<style>
:root{
  color-scheme:light;
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
    color-scheme:dark;
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
  color-scheme:dark;
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
.eyebrow::after{content:none}
.eyebrow .rule{flex:1; height:1px; background:var(--line)}
.theme{
  font:inherit; font-family:"IBM Plex Mono",ui-monospace,monospace; font-size:10px;
  letter-spacing:.12em; text-transform:uppercase; color:var(--ink-2); cursor:pointer;
  background:var(--surface); border:1px solid var(--line-2); border-radius:999px;
  padding:4px 11px; flex:none;
}
.theme:hover{color:var(--ink); border-color:var(--ink-3)}
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
.scan{
  font:inherit; font-family:"IBM Plex Mono",monospace; font-size:11px;
  letter-spacing:.08em; text-transform:uppercase; color:var(--accent-ink);
  background:var(--accent-soft); border:1px solid transparent; border-radius:7px;
  padding:6px 10px; cursor:pointer; flex:none; display:flex; align-items:center; gap:6px;
}
.scan:hover{border-color:var(--accent)}
.scan svg{width:15px; height:15px}
.scanner{
  position:fixed; inset:0; z-index:50; background:rgba(10,14,17,.6);
  display:grid; place-items:center; padding:16px;
}
.scanner[hidden]{display:none}
.scanbox{
  width:min(540px,100%); background:var(--surface); border:1px solid var(--line);
  border-radius:14px; overflow:hidden; box-shadow:var(--shadow);
}
.scanhead{
  display:flex; justify-content:space-between; align-items:center; gap:10px;
  padding:11px 14px; font-size:13px; color:var(--ink-2);
}
.viewport{position:relative; background:#000; min-height:260px}
.viewport video,.viewport canvas{display:block; width:100%; height:auto}
.viewport canvas{position:absolute; inset:0; height:100%}
.scanstate{margin:0; padding:11px 14px; font-size:13.5px; color:var(--ink-2)}
.scanstate:empty{display:none}
.lotrow{display:flex; gap:10px; align-items:center; flex-wrap:wrap}
.lotfield{flex:0 1 300px}
.lotfield input{cursor:text; text-transform:uppercase}
.lotstate{font-size:13px; color:var(--ink-3)}
.lotstate.on{
  font-family:"IBM Plex Mono",monospace; font-size:11px; letter-spacing:.08em;
  text-transform:uppercase; color:var(--dial-ink); background:var(--dial-soft);
  border:1px solid var(--dial); padding:3px 8px; border-radius:5px;
}
.was{
  font-family:"IBM Plex Mono",monospace; font-size:11px; letter-spacing:.06em;
  color:var(--ink-3); border:1px dashed var(--line-2); padding:2px 7px; border-radius:5px;
}
.was s{text-decoration-color:var(--stop)}
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
/* the tick turns to the number's position, the way the wheel on the machine does */
.dial::before{
  content:""; position:absolute; inset:0; border-radius:50%;
  background:linear-gradient(var(--dial),var(--dial)) 50% 3px/2px 8px no-repeat;
  transform:rotate(var(--a,0deg));
}
.dial.stop{background:var(--stop-soft); border-color:var(--stop)}
.dial.stop span{color:var(--stop-ink); font-size:24px}
.dial.stop::before{content:none}
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

.panel{
  margin:26px 0 0; padding:20px; border-radius:12px;
  background:var(--surface); border:1px solid var(--line); box-shadow:var(--shadow);
}
.panel h2{
  font-family:"Familjen Grotesk",sans-serif; font-weight:600; font-size:19px;
  margin:0 0 6px; letter-spacing:-.01em;
}
.panel > p{margin:0 0 16px; color:var(--ink-2); max-width:62ch; font-size:14.5px}
.panel ol{gap:14px; counter-reset:d}
.panel li{
  display:grid; grid-template-columns:auto 1fr; gap:13px; align-items:start;
}
.panel li::before{
  counter-increment:d; content:counter(d);
  font-family:"IBM Plex Mono",monospace; font-size:12px; font-weight:600;
  width:24px; height:24px; border-radius:50%; display:grid; place-items:center;
  background:var(--accent-soft); color:var(--accent-ink); margin-top:1px;
}
.panel h3{
  font-size:15px; margin:0 0 3px; font-weight:600;
  font-family:"Familjen Grotesk",sans-serif;
}
.panel p{margin:0; font-size:14px; color:var(--ink-2)}
.panel code{
  font-family:"IBM Plex Mono",monospace; font-size:12px; color:var(--ink-2);
  background:var(--raised); padding:1px 5px; border-radius:4px;
  overflow-wrap:anywhere;
}
.panel a{color:var(--accent-ink); text-decoration-color:var(--accent)}
.panel details{margin-top:14px; border-top:1px solid var(--line); padding-top:12px}
.panel summary{
  font-family:"IBM Plex Mono",monospace; font-size:11px; letter-spacing:.12em;
  text-transform:uppercase; color:var(--ink-2); cursor:pointer;
}
.panel summary:hover{color:var(--ink)}
.panel details[open] summary{margin-bottom:12px}
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
  <div class="eyebrow">
    <span>Unofficial &mdash; not affiliated with Baby Brezza</span>
    <span class="rule" aria-hidden="true"></span>
    <button class="theme" id="theme" type="button"
            title="Switch between automatic, dark, and light"></button>
  </div>
  <h1>What number does this tin need?</h1>
  <p class="lede">Type the brand on the tin, get the setting &mdash; free, no email
    address, no lookup limit. Covers the whole Formula Pro Advanced family (WiFi and
    Mini included), the alternate numbers for lot-11 machines, and the discontinued
    original Formula Pro their finder dropped. Searching happens in this tab; nothing
    you type is sent anywhere.</p>
  <p class="note"><strong>Check the number against your own tin before mixing a
    bottle.</strong> These are the settings Baby Brezza publishes, findable without
    the email gate &mdash; not independently verified numbers. And they change:
    dates here mean "not touched since", never "verified on".</p>
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
      <button class="scan" id="scan" type="button" hidden
              title="Scan the barcode with your camera — decoded on your device">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <path d="M4 8V6a2 2 0 0 1 2-2h2M4 16v2a2 2 0 0 0 2 2h2m8-16h2a2 2 0 0 1 2 2v2m-4 12h2a2 2 0 0 0 2-2v-2M8 9v6m3-6v6m3-6v6"></path>
        </svg>
        Scan
      </button>
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

<section class="panel">
  <h2>Before you trust any number</h2>
  <p>From this page, the official finder, or a screenshot in a group chat &mdash;
  the same four checks apply. This is infant food prep; five careful minutes beat
  a fast wrong answer.</p>
  <ol>
    <li>
      <div>
        <h3>Check it against the tin</h3>
        <p>The setting exists to reproduce the mixing ratio printed on your formula's
        label, and it shifts with things you can see (brand, stage, country) and one
        you can't (your machine's lot number). The Advanced and the original Formula
        Pro also mix differently &mdash; the machine picker at the top is not
        decoration. If this page, the
        <a href="https://babybrezza.com/pages/formula-pro-global-settings-finder">official
        finder</a>, and the tin disagree, believe none of them: ask Baby Brezza or
        your pediatrician. A result marked <em>no dial position</em> is Baby Brezza's
        own published 0 &mdash; the dial runs 1&ndash;10, so ask them before using
        that formula.</p>
      </div>
    </li>
    <li>
      <div>
        <h3>Settings change, quietly</h3>
        <p>Baby Brezza revises these numbers with no change log and no announcement.
        Measured against a frozen copy of their own data from around 2022, <strong>81
        of 299 comparable settings had moved</strong> &mdash; Similac Advance went
        4&nbsp;&rarr;&nbsp;5, Alimentum 6&nbsp;&rarr;&nbsp;5. Where that copy
        disagrees with today's number, the result carries a struck-out
        <em>was</em> chip. Re-check the setting every time you switch formula, and
        glance again when the tin says "new look" or "improved".</p>
      </div>
    </li>
    <li>
      <div>
        <h3>A right number can still pour wrong</h3>
        <p>Powder cakes and funnels clog, so a correct setting can still pour a
        watery bottle through a dirty machine. Baby Brezza's own maintenance bar:
        clean the mixing funnel every 4 bottles, keep powder above the MIN line,
        keep every part completely dry. To check what your machine actually
        dispenses, weigh it &mdash; their
        <a href="https://babybrezza.com/blogs/news/how-we-test-the-formula-pro-to-ensure-it-dispenses-formula-accurately">plastic-wrap
        test</a> takes cling film and a kitchen scale that reads hundredths of a
        gram. The formula-feeding community treats that test as gospel, with reason.</p>
      </div>
    </li>
    <li>
      <div>
        <h3>The under-two-months caveat</h3>
        <p>Powdered formula is not sterile. For a baby under 2 months, born
        premature, or immunocompromised, the
        <a href="https://www.cdc.gov/cronobacter/prevention/index.html">CDC</a> and
        <a href="https://www.who.int/publications/i/item/9789241595414">WHO</a>
        recommend preparing powder with water at 158&nbsp;&deg;F&thinsp;/&thinsp;70&nbsp;&deg;C
        to kill Cronobacter &mdash; hotter than a Formula Pro dispenses. That's a
        conversation for your pediatrician, not a reason to panic. The
        <a href="https://www.healthychildren.org/English/ages-stages/baby/formula-feeding/Pages/how-to-safely-prepare-formula-with-water.aspx">AAP's
        preparation guide</a> covers the rest: safe water, storage times, and why
        formula is never diluted.</p>
      </div>
    </li>
  </ol>
</section>

<section class="panel">
  <h2>Why this page exists</h2>
  <p>Baby Brezza's finder won't show a number until you type an email address, and
  each search there is logged &mdash; email, IP address, city, ZIP, and the formula
  you looked up &mdash; whether or not you tick the consent box. The number itself
  was never behind anything: the settings API is public and asks for nothing. This
  page is the same public data with the ceremony removed.</p>
  <p>Every number comes from Baby Brezza's own settings API, collected by an
  exhaustive crawl whose code, dataset, and full change history are public:
  <a href="https://github.com/USER/REPO">source and dataset</a> &middot;
  <a href="https://github.com/USER/REPO/blob/main/docs/HOW-IT-WORKS.md">how it
  works</a>. Found a number that disagrees with your tin?
  <a href="https://github.com/USER/REPO/issues">Open an issue</a>.</p>
  <details>
    <summary>The receipts: where an official-finder search goes</summary>
    <p>Read out of their <code>formula-settings.js</code>. Three destinations, only
    one of which asks permission.</p>
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
          on the US site, or <code>/klaviyo</code> elsewhere &mdash; but only if you tick
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
    <p style="margin-top:16px">The location fields aren't guessed from your address &mdash;
    the page loads an IP-geolocation script that writes your city, region, ZIP and IP
    into cookies, which the logger then reads back. Meanwhile the email itself is
    checked by a regular expression in your browser and nothing else: the settings API
    never asks for one. That is the whole lock.</p>
  </details>
  <p style="margin-top:14px"><strong>This page has no analytics, no cookies, and no
  server.</strong> Every setting is already inside the file your browser downloaded;
  searching runs locally, and your lot number stays in this tab. The barcode scanner
  is on-device too: camera frames are decoded in your browser and never uploaded.</p>
</section>

<footer id="foot"></footer>
</div>

<div class="scanner" id="scanner" hidden role="dialog" aria-modal="true" aria-label="Barcode scanner">
  <div class="scanbox">
    <div class="scanhead">
      <span>Runs on your phone &mdash; camera frames never leave it.</span>
      <button class="chip" id="scanclose" type="button">Close</button>
    </div>
    <div class="viewport" id="viewport"></div>
    <p class="scanstate" id="scanstate"></p>
  </div>
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

// Theme: auto follows the phone. The override exists for the 3am feed, when
// the phone is still in day mode and the ceiling light is off.
const THEMES = ["", "dark", "light"];
const $theme = el("theme");
function applyTheme(t){
  if (t) document.documentElement.dataset.theme = t;
  else delete document.documentElement.dataset.theme;
  $theme.textContent = "◑ " + (t || "auto");
}
let theme = store.get("brezza.theme", "");
if (!THEMES.includes(theme)) theme = "";
applyTheme(theme);
$theme.addEventListener("click", () => {
  theme = THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length];
  store.set("brezza.theme", theme);
  applyTheme(theme);
});

// --- machine picker
$pick.innerHTML = MODEL_KEY.map(k => {
  const m = D.M[k], c = m.counts;
  return `<button type="button" data-model="${k}" aria-pressed="false">
    <span class="n">${esc(m.label)}</span>
    <span class="d">${c.records.toLocaleString()} settings · ${c.brands} brands${
      k === "advanced" ? ` · also the WiFi and Mini · live data, newest ${fmtDate(c.newest)}`
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
  // The original's data carries no barcodes, so no scanner there either.
  $scan.hidden = !(model === "advanced" && canScan);
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
    // Same tin, two spellings: scanners hand back 12-digit UPC-A or 13-digit
    // EAN with a leading 0, and the dataset stores a mix of both. Canonicalise
    // BOTH sides before comparing — Baby Brezza's own API is exact-string here
    // and misses its own records when the forms differ.
    const canon = d => d.length === 13 && d[0] === "0" ? d.slice(1) : d;
    const want = canon(digits(raw));
    const hits = [];
    for (let i = 0; i < D.R.length; i++){
      if (!mine(i)) continue;
      for (const u of D.R[i][6]){
        if (canon(digits(u)) === want){ hits.push(i); break }
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
      : "<p>Type the brand on the tin, or paste its barcode.</p>";
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
    const fresh = r[8] ? `<span class="fresh" title="When Baby Brezza last replaced this record's product image — a 'not touched since' signal. The setting may have been revised since without the picture changing.">image dated ${fmtDate(r[8])}</span>` : "";
    const was = r[9] ? `<span class="was" title="This record's setting in a frozen copy of Baby Brezza's own data from around 2022 — evidence the number moves, not an official change log.">was <s>${esc(r[9])}</s></span>` : "";
    const nope = num ? `<span class="sr">Setting ${setting}</span>`
      : setting === 0
        ? `<span class="nope" title="Baby Brezza publishes a setting of 0 for this formula. The dial runs 1–10, so ask them before using it.">No dial position</span>`
        : `<span class="nope">${esc(setting)}</span>`;
    return `<li class="rec">
      <div class="dial${num ? "" : " stop"}"${
        num ? ` style="--a:${(setting % 10) * 36}deg"` : ""} aria-hidden="true"><span>${
        num ? setting : (setting === 0 ? "0" : "&times;")}</span></div>
      <div>
        <p class="name">${mark(D.B[r[1]] + " · " + r[2], terms)}</p>
        <div class="meta">
          ${r[3] ? `<span class="stage">Stage ${esc(r[3])}</span>` : ""}
          ${nope}
          ${altChip}${was}${where}${upc}${fresh}
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
  `<p style="margin-top:10px">Unofficial and not affiliated with Baby Brezza &mdash; ` +
  `built out of annoyance at an email gate. All numbers come from Baby Brezza's own ` +
  `public data: <a href="https://github.com/USER/REPO">source and dataset</a> &middot; ` +
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

// ---- barcode scanner ----
// Native BarcodeDetector where it actually has a backend (Chromium); otherwise
// the library the official page uses, in its maintained fork
// (vendor/quagga2-1.12.1.min.js), loaded same-origin only when asked for.
// Frames are decoded on-device; nothing is uploaded.
const $scan=el("scan"), $scanner=el("scanner"), $viewport=el("viewport"),
      $scanstate=el("scanstate"), $scanclose=el("scanclose");
const canScan = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
let scanStop = null, lastRead = "";

const scanMsg = t => { $scanstate.textContent = t };

function acceptCode(code){
  code = (code || "").trim();
  if (!code) return;
  if (code !== lastRead){ lastRead = code; return }  // same code twice, like theirs
  closeScanner();
  $q.value = code;
  run();
}

function cameraError(e){
  const n = e && e.name;
  const fallback = "Type the digits printed under the barcode lines instead.";
  if (n === "NotAllowedError" || n === "SecurityError")
    return "Camera permission was declined. " + fallback;
  if (n === "NotFoundError" || n === "OverconstrainedError")
    return "No usable camera found. " + fallback;
  return "The camera didn't start. " + fallback;
}

async function nativeWorks(){
  if (!("BarcodeDetector" in window)) return false;
  try{
    const f = await BarcodeDetector.getSupportedFormats();
    return f.includes("ean_13") && f.includes("upc_a");
  }catch(e){ return false }
}

async function scanNative(){
  const detector = new BarcodeDetector({formats:["upc_a","ean_13"]});
  const stream = await navigator.mediaDevices.getUserMedia({video:{facingMode:"environment"}});
  const video = document.createElement("video");
  video.setAttribute("playsinline",""); video.muted = true; video.srcObject = stream;
  $viewport.replaceChildren(video);
  await video.play();
  // Some builds expose the interface with no detection backend: the first
  // detect() rejects. Fall back to Quagga rather than spinning silently.
  try{ await detector.detect(video) }
  catch(e){ stream.getTracks().forEach(t => t.stop()); $viewport.replaceChildren(); return false }
  scanMsg("Point the camera at the barcode.");
  let live = true;
  scanStop = () => { live = false; stream.getTracks().forEach(t => t.stop()) };
  const tick = async () => {
    if (!live) return;
    try{
      const found = await detector.detect(video);
      if (found.length) acceptCode(found[0].rawValue);
    }catch(e){}
    if (live) requestAnimationFrame(tick);
  };
  tick();
  return true;
}

const loadQuagga = () => window.Quagga ? Promise.resolve()
  : new Promise((ok, fail) => {
      const s = document.createElement("script");
      s.src = "vendor/quagga2-1.12.1.min.js";
      s.onload = ok; s.onerror = () => fail(new Error("scanner script failed to load"));
      document.head.appendChild(s);
    });

async function scanQuagga(){
  await loadQuagga();
  await new Promise((ok, fail) => Quagga.init({
    inputStream:{name:"Live", type:"LiveStream", target:$viewport,
                 constraints:{facingMode:"environment"}},
    decoder:{readers:["upc_reader","ean_reader"]},   // the official page's set
    locate:true, frequency:20,
    numOfWorkers: navigator.hardwareConcurrency || 1,
  }, err => err ? fail(err) : ok()));
  Quagga.start();
  scanMsg("Point the camera at the barcode.");
  const onDet = r => acceptCode(r.codeResult && r.codeResult.code);
  Quagga.onDetected(onDet);
  scanStop = () => { Quagga.offDetected(onDet); Quagga.stop() };
}

async function openScanner(){
  lastRead = "";
  $scanner.hidden = false;
  $scanclose.focus();
  scanMsg("Starting camera…");
  try{
    if (!(await nativeWorks() && await scanNative())) await scanQuagga();
  }catch(e){ scanMsg(cameraError(e)) }
}

function closeScanner(){
  if (scanStop){ try{ scanStop() }catch(e){} scanStop = null }
  $scanner.hidden = true;
  $viewport.replaceChildren();
  scanMsg("");
  $q.focus();
}

$scan.addEventListener("click", openScanner);
$scanclose.addEventListener("click", closeScanner);
$scanner.addEventListener("click", e => { if (e.target === $scanner) closeScanner() });
addEventListener("keydown", e => { if (e.key === "Escape" && !$scanner.hidden) closeScanner() });

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
    nwas = sum(1 for r in packed["R"] if r[9])
    print(f"wrote {OUT} ({os.path.getsize(OUT)/1e6:.2f} MB), "
          f"{len(packed['R'])} records, {len(packed['B'])} brands, "
          f"{nwas} rows carry a 'was' chip (staleness examples: 81)")


if __name__ == "__main__":
    main()
