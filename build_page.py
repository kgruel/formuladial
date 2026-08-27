"""Emit a single self-contained lookup page with both datasets embedded.

The two datasets are published apart -- the live Advanced snapshot and the
frozen original Formula Pro -- and joined back together here, because the page
offers the original as a historical reference behind its own view.

Territory membership is stored as a hex bitmask over the territory list, which
is what keeps the payload small -- one record often covers dozens of countries.

The page makes you name your machine before it shows a number.  The two models
mix differently and their numbers are not interchangeable, so a silent default
would be the one bug that actually matters here.
"""
import json, os, re

from staleness import norm

DATA = "site/data/formula_settings.json"
LEGACY = "site/data/legacy_formula_pro.json"
STALE = "data/staleness.json"
THUMBS = "site/thumbs"
OUT = "site/index.html"


def thumb_stem(image):
    """The committed thumbnail for `image`, or None if there is not one.

    fetch_images.py cuts `site/thumbs/<stem>.webp` for every image it can
    fetch, so what is on disk -- not what the record claims -- is the honest
    source: a src pointing at a file the deploy does not carry would render as
    a broken image.
    """
    if not image:
        return None
    stem = os.path.splitext(image)[0]
    if not os.path.exists(os.path.join(THUMBS, stem + ".webp")):
        return None
    # the stem is interpolated straight into a src="" with no escaping
    assert re.fullmatch(r"[A-Za-z0-9._-]+", stem), "unsafe thumb name: %s" % stem
    return stem


def pack(adv, pro):
    """Fold the two published files into one payload.

    The page shows both machines, so a row still needs to say which one it came
    from (index 0) -- but that is a fact about this page's two views, not about
    the data, which now carries the distinction as a file boundary.
    """
    recs = [(0, r) for r in adv["records"]] + [(1, r) for r in pro["records"]]
    terrs = sorted({t for _, r in recs for t in r["territories"]})
    ti = {t: i for i, t in enumerate(terrs)}
    brands = sorted({r["brand"] for _, r in recs})
    bi = {b: i for i, b in enumerate(brands)}
    # The 81 settings staleness.py caught changing between the frozen ~2022
    # copy and the live API. Its example keys are already norm()ed.
    try:
        was = {(e["brand"], e["type"], e["stage"]): "/".join(e["was"])
               for e in json.load(open(STALE))["examples"]}
    except FileNotFoundError:
        was = {}
    rows = []
    for m, r in recs:
        mask = 0
        for t in r["territories"]:
            mask |= 1 << ti[t]
        w = (was.get((norm(r["brand"]), norm(r["type"]), norm(r["stage"])))
             if m == 0 else None)
        rows.append([m, bi[r["brand"]], r["type"],
                     r["stage"], r["setting"], format(mask, "x"), r["upc"],
                     r.get("alt_setting"), r.get("image_date"), w,
                     thumb_stem(r.get("image"))])
    return {"T": terrs, "B": brands, "R": rows,
            "M": {"advanced": {"label": adv["label"], "counts": adv["counts"]},
                  "pro": {"label": pro["label"], "counts": pro["counts"]}}}


TEMPLATE = r"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Formula Dial &mdash; Baby Brezza formula settings</title>
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><circle cx='50' cy='50' r='41' fill='%23f6e6cd' stroke='%23c9821a' stroke-width='9'/><line x1='50' y1='50' x2='50' y2='17' stroke='%235a3a08' stroke-width='10' stroke-linecap='round' transform='rotate(216 50 50)'/><circle cx='50' cy='50' r='7' fill='%235a3a08'/></svg>">
<script>
/* Before first paint: a stored theme choice must not flash the other one. */
try{var _t=localStorage.getItem("brezza.theme");
if(_t==="dark"||_t==="light")document.documentElement.dataset.theme=_t}catch(e){}
</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Zilla+Slab:wght@600;700&family=IBM+Plex+Mono:wght@400;500;600&family=Source+Sans+3:wght@400;500;600&display=swap">
<style>
:root{
  color-scheme:light;
  --ground:#f2f0ec; --surface:#fffefc; --raised:#e9e6e0;
  --thumb-bg:#fff;  /* deliberately the same in dark: photos keep a photo-white frame */
  --ink:#1c2329; --ink-2:#4c565e; --ink-3:#7b858d;
  --line:#dbd7d0; --line-2:#c9c4bb;
  --accent:#0f6d72; --accent-soft:#d9e8e7; --accent-ink:#0a4a4e;
  --dial:#c9821a; --dial-ink:#5a3a08; --dial-soft:#f6e6cd; --needle:#5a3a08;
  --stop:#9c3328; --stop-soft:#f4dedb; --stop-ink:#7c2820;
  --focus:#0f6d72;
  --shadow:0 1px 2px rgba(28,35,41,.06),0 6px 18px rgba(28,35,41,.05);
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    color-scheme:dark;
    --ground:#191410; --surface:#221c15; --raised:#2c241a;
    --ink:#ede6da; --ink-2:#b3a996; --ink-3:#8f877a;
    --line:#332b20; --line-2:#46392a;
    --accent:#5fc8c8; --accent-soft:#1b3531; --accent-ink:#9fe0df;
    --dial:#e8a94a; --dial-ink:#f6dcae; --dial-soft:#403012; --needle:#ede6da;
    --stop:#e0857a; --stop-soft:#3a201d; --stop-ink:#f2bdb6;
    --focus:#5fc8c8;
    --shadow:0 1px 2px rgba(0,0,0,.3),0 6px 18px rgba(0,0,0,.25);
  }
}
:root[data-theme="dark"]{
  color-scheme:dark;
  --ground:#191410; --surface:#221c15; --raised:#2c241a;
  --ink:#ede6da; --ink-2:#b3a996; --ink-3:#8f877a;
  --line:#332b20; --line-2:#46392a;
  --accent:#5fc8c8; --accent-soft:#1b3531; --accent-ink:#9fe0df;
  --dial:#e8a94a; --dial-ink:#f6dcae; --dial-soft:#403012; --needle:#ede6da;
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

header{padding:32px 0 18px}
.brandrow{display:flex; gap:12px; align-items:center}
.brand{
  font-family:"Zilla Slab",serif; font-weight:700; font-size:21px;
  letter-spacing:-.01em; color:var(--ink); display:flex; align-items:baseline;
}
.brand .ti{position:relative; display:inline-block}
.brand .ti svg{position:absolute; top:1px; left:50%; margin-left:-3.5px; width:7px; height:7px}
.rule{flex:1; height:1px; background:var(--line)}
.eyebrow{
  font-family:"IBM Plex Mono",ui-monospace,monospace; font-size:11px;
  letter-spacing:.16em; text-transform:uppercase; color:var(--ink-3);
  margin-top:12px;
}
.hgrid{display:grid; grid-template-columns:1fr auto; gap:26px; align-items:center}
.heromark{width:104px; height:104px; margin-top:6px}
.theme{
  font:inherit; font-family:"IBM Plex Mono",ui-monospace,monospace; font-size:10px;
  letter-spacing:.12em; text-transform:uppercase; color:var(--ink-2); cursor:pointer;
  background:var(--surface); border:1px solid var(--line-2); border-radius:999px;
  padding:4px 11px; flex:none;
}
.theme:hover{color:var(--ink); border-color:var(--ink-3)}
h1{
  font-family:"Zilla Slab",serif;
  font-weight:700; font-size:clamp(30px,5.5vw,42px); line-height:1.05;
  letter-spacing:-.015em; margin:14px 0 4px; text-wrap:balance;
}

/* ---- coverage strip: which data this is, in one line ---- */
.strip{
  margin:22px 0 0; display:flex; align-items:center; gap:12px; flex-wrap:wrap;
  background:var(--surface); border:1px solid var(--line); border-radius:10px;
  padding:10px 14px; box-shadow:var(--shadow); font-size:13.5px; color:var(--ink-2);
}
.striptag{
  font-family:"IBM Plex Mono",monospace; font-size:10px; letter-spacing:.1em;
  text-transform:uppercase; color:var(--accent-ink); background:var(--accent-soft);
  border-radius:5px; padding:3px 8px; flex:none;
}
.striptag.pro{color:var(--ink-2); background:var(--raised)}
.swap{
  font:inherit; color:var(--accent-ink); background:none; border:0; padding:0;
  cursor:pointer; text-decoration:underline; text-decoration-color:var(--accent);
}
.swap:hover{color:var(--accent)}
.histref{margin:18px 2px 0; font-size:13.5px; color:var(--ink-3)}
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
/* the machine's numbered selector, borrowed as the unit of the page: the
   needle fills the gap between core and ring at the setting's position */
.dialsvg{flex:none; width:64px; height:64px}
.dialsvg text{font-family:"IBM Plex Mono",ui-monospace,monospace; font-variant-numeric:tabular-nums}
.rec.hasimg{grid-template-columns:auto 1fr auto}
/* A frame around the product photo, not a crop of it: tins are tall, the odd
   few are extra-tall, and 81 arrive with a transparent background. The frame
   stays photo-white in both themes so those 81 read the same as the 3,441
   with white baked in -- one presentation, not a bright majority and a dark
   minority. */
.thumb{
  width:52px; height:52px; border-radius:10px; flex:none;
  border:1px solid var(--line-2); background:var(--thumb-bg);
  object-fit:contain; padding:3px;
}
.name{
  font-family:"Zilla Slab",serif; font-weight:600; font-size:17.5px;
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
  font-family:"Zilla Slab",serif; font-weight:600; font-size:19.5px;
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
  font-size:15.5px; margin:0 0 3px; font-weight:600;
  font-family:"Zilla Slab",serif;
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
  .rec{gap:13px; padding:12px 13px}
  .dialsvg{width:52px; height:52px}
  .thumb{width:44px; height:44px}
  .heromark{display:none}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
</style>

<div class="wrap">
<header>
  <div class="brandrow">
    <span class="brand" aria-label="Formula Dial">formula d<span class="ti">&#305;<svg viewBox="0 0 15 15" aria-hidden="true"><circle cx="7.5" cy="7.5" r="6.3" fill="var(--dial-soft)" stroke="var(--dial)" stroke-width="1.7"></circle><line x1="7.5" y1="7.5" x2="7.5" y2="2.8" stroke="var(--needle)" stroke-width="1.7" stroke-linecap="round" transform="rotate(216 7.5 7.5)"></line></svg></span>al</span>
    <span class="rule" aria-hidden="true"></span>
    <button class="theme" id="theme" type="button"
            title="Switch between automatic, dark, and light"></button>
  </div>
  <div class="eyebrow">Unofficial &mdash; not affiliated with Baby Brezza</div>
  <div class="hgrid">
    <h1>What number does this tin need?</h1>
    <svg class="heromark" viewBox="0 0 100 100" aria-hidden="true"><circle cx="50" cy="50" r="45" fill="none" stroke="var(--dial)" stroke-width="2"></circle><g stroke="var(--dial)" stroke-width="2" stroke-linecap="round"><line x1="50" y1="10" x2="50" y2="16"></line><line x1="50" y1="10" x2="50" y2="16" transform="rotate(36 50 50)"></line><line x1="50" y1="10" x2="50" y2="16" transform="rotate(72 50 50)"></line><line x1="50" y1="10" x2="50" y2="16" transform="rotate(108 50 50)"></line><line x1="50" y1="10" x2="50" y2="16" transform="rotate(144 50 50)"></line><line x1="50" y1="10" x2="50" y2="16" transform="rotate(180 50 50)"></line><line x1="50" y1="10" x2="50" y2="16" transform="rotate(252 50 50)"></line><line x1="50" y1="10" x2="50" y2="16" transform="rotate(288 50 50)"></line><line x1="50" y1="10" x2="50" y2="16" transform="rotate(324 50 50)"></line><line x1="50" y1="10" x2="50" y2="16" transform="rotate(216 50 50)"></line></g><circle cx="50" cy="50" r="26" fill="var(--dial-soft)" stroke="var(--dial)" stroke-width="2.8"></circle><line x1="50" y1="50" x2="50" y2="29" stroke="var(--needle)" stroke-width="3.2" stroke-linecap="round" transform="rotate(216 50 50)"></line><circle cx="50" cy="50" r="4" fill="var(--needle)"></circle></svg>
  </div>
</header>

<section class="strip" id="strip"></section>

<div class="controls" id="controls">
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
        Pro also mix differently &mdash; this page shows the Advanced family; the
        discontinued original lives behind the link at the bottom. If this page, the
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

<p class="histref" id="histref"></p>

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
      $strip=el("strip"), $lot=el("lot"), $lotrow=el("lotrow"),
      $lotstate=el("lotstate");

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

// --- coverage strip: which dataset is on screen. The Advanced is the line
// still being sold, so it is the default; the original is a historical
// reference reached from the line above the footer.
function renderStrip(){
  const a = D.M.advanced.counts, p = D.M.pro.counts;
  $strip.innerHTML = model === "advanced"
    ? `<span class="striptag">All Formula Pro Advanced</span>
       <span>One settings set covers the Advanced, WiFi and Mini &middot; ${
         a.records.toLocaleString()} settings &middot; live data, newest ${fmtDate(a.newest)}</span>`
    : `<span class="striptag pro">Original Formula Pro &mdash; historical</span>
       <span>${p.records.toLocaleString()} settings &middot; frozen since ~2022 &middot; a starting
       point, not gospel &middot; <button class="swap" id="backadv" type="button">back to the
       Advanced</button></span>`;
  const b = el("backadv");
  if (b) b.addEventListener("click", () => setModel("advanced"));
}

function setModel(m){
  model = m;
  store.set("brezza.model", m);
  applyModel();
  run();
  $strip.scrollIntoView({block:"nearest"});
  $q.focus({preventScroll:true});
}

function applyModel(){
  renderStrip();
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
  if (!raw) return {mode:"", hits:[]};
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

// The row dial is the featured mark with the number set into its core: outer
// ring, ten ticks, and the needle filling the core-to-ring gap at the
// setting's position — where it replaces that position's tick.
function ticksSVG(skip){
  let t = "";
  for (let a = 0; a < 360; a += 36)
    if (a !== skip) t += `<line x1="50" y1="10" x2="50" y2="16" transform="rotate(${a} 50 50)"/>`;
  return t;
}
function dialSVG(n){
  const a = (n % 10) * 36;
  return `<svg class="dialsvg" viewBox="0 0 100 100" aria-hidden="true"><circle cx="50" cy="50" r="45" fill="none" stroke="var(--dial)" stroke-width="2"/><g stroke="var(--dial)" stroke-width="2" stroke-linecap="round">${ticksSVG(a)}</g><circle cx="50" cy="50" r="26" fill="var(--dial-soft)" stroke="var(--dial)" stroke-width="2.8"/><line x1="50" y1="6.5" x2="50" y2="23" stroke="var(--needle)" stroke-width="4" stroke-linecap="round" transform="rotate(${a} 50 50)"/><text x="50" y="60" text-anchor="middle" font-size="30" font-weight="600" fill="var(--dial-ink)">${n}</text></svg>`;
}
// A published 0 (or a NOT COMPATIBLE row) is a dial face with no needle:
// there is no position to point at.
function stopSVG(setting){
  const zero = setting === 0;
  return `<svg class="dialsvg" viewBox="0 0 100 100" aria-hidden="true"><circle cx="50" cy="50" r="45" fill="none" stroke="var(--stop)" stroke-width="2"/><g stroke="var(--stop)" stroke-width="2" stroke-linecap="round">${ticksSVG(-1)}</g><circle cx="50" cy="50" r="26" fill="var(--stop-soft)" stroke="var(--stop)" stroke-width="2.8"/><text x="50" y="${zero ? 60 : 61}" text-anchor="middle" font-size="${zero ? 30 : 34}" font-weight="600" fill="var(--stop-ink)">${zero ? "0" : "&times;"}</text></svg>`;
}
function run(){
  const raw = $q.value.trim();
  store.set("brezza.q", raw);
  store.set("brezza.terr." + model, $terr.value);
  const {mode, hits} = search();
  $mode.hidden = mode !== "barcode";

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
    // The product photo, cut to 128px and served from this site. Rows without
    // one — records Baby Brezza never imaged, and every original-Pro row, whose
    // backend had no images at all — get no box rather than an empty frame,
    // which would promise a picture that is never coming. The alt is empty on
    // purpose: the row's own text names the product, so the photo is decorative.
    const thumb = r[10]
      ? `<img class="thumb" src="thumbs/${r[10]}.webp" loading="lazy" decoding="async" alt="">`
      : "";
    const nope = num ? `<span class="sr">Setting ${setting}</span>`
      : setting === 0
        ? `<span class="nope" title="Baby Brezza publishes a setting of 0 for this formula. The dial runs 1–10, so ask them before using it.">No dial position</span>`
        : `<span class="nope">${esc(setting)}</span>`;
    return `<li class="rec${thumb ? " hasimg" : ""}">
      ${num ? dialSVG(setting) : stopSVG(setting)}
      <div>
        <p class="name">${mark(D.B[r[1]] + " · " + r[2], terms)}</p>
        <div class="meta">
          ${r[3] ? `<span class="stage">Stage ${esc(r[3])}</span>` : ""}
          ${nope}
          ${altChip}${was}${where}${upc}${fresh}
        </div>
      </div>
      ${thumb}
    </li>`;
  }).join("");
}

el("histref").innerHTML =
  `Also here, as a historical reference: the discontinued ` +
  `<button class="swap" id="showpro" type="button">original Formula Pro</button> &mdash; ` +
  `${D.M.pro.counts.records.toLocaleString()} settings, frozen since ~2022, kept because ` +
  `their finder dropped it. Treat those numbers as a starting point, not gospel.`;
el("showpro").addEventListener("click", () => setModel("pro"));

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
$q.focus({preventScroll:true});
</script>
"""


def main():
    packed = pack(json.load(open(DATA)), json.load(open(LEGACY)))
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
    nadv = sum(1 for r in packed["R"] if r[0] == 0)
    nthumb = sum(1 for r in packed["R"] if r[10])
    print(f"wrote {OUT} ({os.path.getsize(OUT)/1e6:.2f} MB), "
          f"{nadv} live Advanced records + {len(packed['R']) - nadv} from the frozen "
          f"original, {len(packed['B'])} brands, "
          f"{nwas} rows carry a 'was' chip (staleness examples: 81), "
          f"{nthumb} carry a product photo")


if __name__ == "__main__":
    main()
