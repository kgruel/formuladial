"""Emit a self-contained lookup page from the current Advanced-family snapshot.

The discontinued original Formula Pro is deliberately excluded: its frozen
dataset is retained in the repository as historical evidence, but it must not
be shipped in the current lookup page or influence its results.

Territory membership is stored as a hex bitmask over the territory list, which
is what keeps the payload small -- one record often covers dozens of markets.

The page makes the owner identify an Advanced/WiFi versus a Mini before it
shows a number. They share the current settings set, but only Advanced/WiFi
machines can use a lot-11 alternate.
"""
import json, os, re
from collections import defaultdict

from crawlers.fetch_images import thumb_path, thumb_stem
from staleness import norm

DATA = "site/data/formula_settings.json"
STALE = "data/staleness.json"
HISTORY = "data/setting_history.json"
OUT = "site/index.html"


def public_repository_url():
    """Return the public repository URL when the build environment knows it.

    GitHub Actions provides GITHUB_REPOSITORY automatically. Local preview
    builds usually do not, so they link to the bundled dataset instead of
    emitting a dead USER/REPO placeholder.
    """
    explicit = os.environ.get("REPOSITORY_URL", "").rstrip("/")
    if explicit:
        return explicit
    slug = os.environ.get("GITHUB_REPOSITORY", "")
    return f"https://github.com/{slug}" if re.fullmatch(r"[^/]+/[^/]+", slug) else ""


def thumb_of(image):
    """The committed thumbnail's stem for `image`, or None if there is not one.

    fetch_images.py owns where a thumb lands, so ask it; what is on disk --
    not what the record claims -- is the honest source, because a src pointing
    at a file the deploy does not carry would render as a broken image.
    """
    if not image or not os.path.exists(thumb_path(image)):
        return None
    stem = thumb_stem(image)
    # the stem is interpolated straight into a src="" with no escaping
    assert re.fullmatch(r"[A-Za-z0-9._-]+", stem), "unsafe thumb name: %s" % stem
    return stem


def pack(doc):
    """Compact only the current Advanced-family data for the browser payload."""
    recs = doc["records"]
    terrs = sorted({t for r in recs for t in r["territories"]})
    ti = {t: i for i, t in enumerate(terrs)}
    # ``unavailable`` is deliberately a small, separate class of source row:
    # Baby Brezza knows the formula, but has not published a setting that can be
    # used on the dial. Keep it in the browser so it is never mistaken for an
    # unknown product. Older snapshots do not have it yet.
    unavailable = doc.get("unavailable", [])
    brands = sorted({r["brand"] for r in recs} | {r["brand"] for r in unavailable})
    bi = {b: i for i, b in enumerate(brands)}
    # The unambiguous settings staleness.py caught changing between the frozen
    # ~2022 copy and the live API. Its example keys are already norm()ed.
    try:
        with open(STALE) as f:
            was = {(e["brand"], e["type"], e["stage"]): "/".join(e["was"])
                   for e in json.load(f)["examples"]}
    except FileNotFoundError:
        was = {}
    try:
        with open(HISTORY) as f:
            history_rows = json.load(f).get("events", [])
    except (FileNotFoundError, ValueError):
        history_rows = []
    history = defaultdict(list)
    for event in history_rows:
        history[(event["brand"], event["type"], event.get("stage", ""))].append(event)
    rows = []
    for r in recs:
        mask = 0
        for t in r["territories"]:
            mask |= 1 << ti[t]
        variants = []
        for variant in r.get("territory_variants", []):
            variant_mask = 0
            for t in variant["territories"]:
                variant_mask |= 1 << ti[t]
            variants.append([format(variant_mask, "x"), variant.get("upc", []),
                             variant.get("image_date"), thumb_of(variant.get("image"))])
        w = was.get((norm(r["brand"]), norm(r["type"]), norm(r["stage"])))
        events = []
        for event in history.get((r["brand"], r["type"], r["stage"]), []):
            if event["territory"] not in ti:
                continue
            events.append([event["observed"], event["field"], event.get("from"),
                           event.get("to"), format(1 << ti[event["territory"]], "x")])
        rows.append([bi[r["brand"]], r["type"], r["stage"], r["setting"],
                     format(mask, "x"), r["upc"], r.get("alt_setting"),
                     r.get("image_date"), w,
                     thumb_of(r.get("image")), variants or None, events or None])
    unavailable_rows = []
    for r in unavailable:
        mask = 0
        for t in r.get("territories", []):
            # A future source row may name a territory which has no setting
            # record; include it in the compact territory dictionary as well.
            if t not in ti:
                ti[t] = len(terrs)
                terrs.append(t)
            mask |= 1 << ti[t]
        unavailable_rows.append([bi[r["brand"]], r.get("type", ""), r.get("stage", ""),
                                 format(mask, "x"), r.get("reason", ""), r.get("upc", []),
                                 thumb_of(r.get("image"))])
    return {"T": terrs, "B": brands, "R": rows, "U": unavailable_rows,
            "M": {"label": doc["label"], "counts": doc["counts"],
                  "generated": doc["generated"], "observed": doc.get("observed")}}


TEMPLATE = r"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Formula Dial &mdash; Baby Brezza powder settings</title>
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><circle cx='50' cy='50' r='41' fill='%23f6e6cd' stroke='%23c9821a' stroke-width='9'/><line x1='50' y1='50' x2='50' y2='17' stroke='%235a3a08' stroke-width='10' stroke-linecap='round' transform='rotate(216 50 50)'/><circle cx='50' cy='50' r='7' fill='%235a3a08'/></svg>">
<script>
/* Before first paint: a stored theme choice must not flash the other one. */
try{var _t=localStorage.getItem("brezza.theme");
if(_t==="dark"||_t==="light")document.documentElement.dataset.theme=_t}catch(e){}
</script>
<style>
@font-face{font-family:"Source Sans 3";font-style:normal;font-weight:400 600;font-display:swap;src:url("fonts/source-sans-3-latin.woff2") format("woff2");unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD}
@font-face{font-family:"Source Sans 3";font-style:normal;font-weight:400 600;font-display:swap;src:url("fonts/source-sans-3-latin-ext.woff2") format("woff2");unicode-range:U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF}
@font-face{font-family:"Zilla Slab";font-style:normal;font-weight:600;font-display:swap;src:url("fonts/zilla-slab-600-latin.woff2") format("woff2")}
@font-face{font-family:"Zilla Slab";font-style:normal;font-weight:700;font-display:swap;src:url("fonts/zilla-slab-700-latin.woff2") format("woff2")}
@font-face{font-family:"Zilla Slab";font-style:normal;font-weight:600;font-display:swap;src:url("fonts/zilla-slab-600-latin-ext.woff2") format("woff2");unicode-range:U+0100-024F,U+1E00-1EFF,U+20A0-20AB,U+2C60-2C7F,U+A720-A7FF}
@font-face{font-family:"Zilla Slab";font-style:normal;font-weight:700;font-display:swap;src:url("fonts/zilla-slab-700-latin-ext.woff2") format("woff2");unicode-range:U+0100-024F,U+1E00-1EFF,U+20A0-20AB,U+2C60-2C7F,U+A720-A7FF}
@font-face{font-family:"IBM Plex Mono";font-style:normal;font-weight:400;font-display:swap;src:url("fonts/ibm-plex-mono-400-latin.woff2") format("woff2")}
@font-face{font-family:"IBM Plex Mono";font-style:normal;font-weight:500;font-display:swap;src:url("fonts/ibm-plex-mono-500-latin.woff2") format("woff2")}
@font-face{font-family:"IBM Plex Mono";font-style:normal;font-weight:600;font-display:swap;src:url("fonts/ibm-plex-mono-600-latin.woff2") format("woff2")}
@font-face{font-family:"IBM Plex Mono";font-style:normal;font-weight:400;font-display:swap;src:url("fonts/ibm-plex-mono-400-latin-ext.woff2") format("woff2");unicode-range:U+0100-02FF,U+1E00-1EFF,U+20A0-20AB,U+2C60-2C7F,U+A720-A7FF}
@font-face{font-family:"IBM Plex Mono";font-style:normal;font-weight:500;font-display:swap;src:url("fonts/ibm-plex-mono-500-latin-ext.woff2") format("woff2");unicode-range:U+0100-02FF,U+1E00-1EFF,U+20A0-20AB,U+2C60-2C7F,U+A720-A7FF}
@font-face{font-family:"IBM Plex Mono";font-style:normal;font-weight:600;font-display:swap;src:url("fonts/ibm-plex-mono-600-latin-ext.woff2") format("woff2");unicode-range:U+0100-02FF,U+1E00-1EFF,U+20A0-20AB,U+2C60-2C7F,U+A720-A7FF}
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
footer a{color:var(--ink-2)}

/* ---- controls ---- */
.controls{
  margin-top:14px; padding:20px; background:var(--surface);
  border:1px solid var(--line); border-radius:16px; box-shadow:var(--shadow);
}
.lookuphead{display:flex; justify-content:space-between; align-items:start; gap:18px; margin-bottom:17px}
.lookuphead h2{font-family:"Zilla Slab",serif;font-size:24px;line-height:1.1;margin:0 0 4px}
.lookuphead p{margin:0;color:var(--ink-2);font-size:14px}
.privacytag{font-family:"IBM Plex Mono",monospace;font-size:9.5px;letter-spacing:.09em;text-transform:uppercase;color:var(--accent-ink);background:var(--accent-soft);border-radius:999px;padding:5px 9px;white-space:nowrap}
.setupgrid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.step{position:relative;border:1px solid var(--line);border-radius:12px;padding:13px;background:var(--ground);transition:border-color .15s,box-shadow .15s,background .15s}
.step.searchstep{grid-column:1/-1}
.step.needs{border-color:var(--dial);box-shadow:0 0 0 3px var(--dial-soft);background:var(--surface)}
.step.done{border-color:color-mix(in srgb,var(--accent) 45%,var(--line));background:var(--surface)}
.stephead{display:flex;align-items:center;gap:8px;margin-bottom:9px}
.stepnum{display:grid;place-items:center;width:23px;height:23px;border-radius:50%;background:var(--raised);color:var(--ink-2);font-family:"IBM Plex Mono",monospace;font-size:11px;font-weight:600;flex:none}
.step.done .stepnum{background:var(--accent);color:var(--surface)}
.step.done .stepnum::before{content:"✓"}.step.done .stepnum{font-size:0}.step.done .stepnum::before{font-size:12px}
.steplabel{font-family:"IBM Plex Mono",monospace;font-size:10px;letter-spacing:.11em;text-transform:uppercase;color:var(--ink-2);font-weight:600}
.stepstatus{margin-left:auto;font-size:12px;color:var(--ink-3)}
.machinechoices{display:grid;grid-template-columns:1.45fr .75fr;gap:7px}
.machinechoice{font:inherit;text-align:left;color:var(--ink-2);background:var(--surface);border:1px solid var(--line-2);border-radius:9px;padding:10px 11px;cursor:pointer;line-height:1.15}
.machinechoice strong{display:block;color:var(--ink);font-size:14px;font-weight:600}
.machinechoice span{display:block;font-size:11.5px;margin-top:3px;color:var(--ink-3)}
.machinechoice:hover{border-color:var(--accent)}
.machinechoice[aria-pressed="true"]{color:var(--accent-ink);border-color:var(--accent);background:var(--accent-soft);box-shadow:inset 0 0 0 1px var(--accent)}
.field{
  display:flex; align-items:center; gap:10px;
  background:var(--surface); border:1px solid var(--line-2);
  border-radius:9px; padding:0 12px;
}
.field:focus-within,.terr:focus-within{
  border-color:var(--focus); box-shadow:0 0 0 3px var(--accent-soft);
}
.field input:focus-visible,.terr input:focus-visible{outline:none}
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
  display:flex; align-items:center; gap:8px;
  background:var(--surface); border:1px solid var(--line-2);
  border-radius:9px; padding:0 12px;
}
.terr input{padding:11px 0;cursor:text}
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
.lotrow[hidden]{display:none}
.lotfield{margin-top:10px;max-width:360px}
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
.std{
  font-family:"IBM Plex Mono",monospace; font-size:11px; letter-spacing:.06em;
  color:var(--ink-3); border:1px solid var(--line-2); padding:2px 7px; border-radius:5px;
}
.quickrow{display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin-top:11px}
.quicklabel{font-family:"IBM Plex Mono",monospace;font-size:9.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink-3)}
.chips{display:flex; gap:7px; flex-wrap:wrap}
.chip{
  font:inherit; font-size:13px; font-weight:600;color:var(--accent-ink); cursor:pointer;
  background:var(--accent-soft); border:1px solid color-mix(in srgb,var(--accent) 50%,var(--line)); border-radius:999px;
  padding:5px 12px;box-shadow:0 1px 1px rgba(28,35,41,.04);transition:transform .12s,border-color .12s,background .12s;
}
.chip:hover{color:var(--ink);border-color:var(--accent);background:var(--surface);transform:translateY(-1px)}

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
.rec.result{border:2px solid var(--dial);padding:19px 20px;background:linear-gradient(110deg,var(--surface),color-mix(in srgb,var(--dial-soft) 35%,var(--surface)))}
.resultdial{display:flex;flex-direction:column;align-items:center;gap:4px}
.resultlabel{font-family:"IBM Plex Mono",monospace;font-size:9px;letter-spacing:.11em;text-transform:uppercase;color:var(--dial-ink);font-weight:600}
.rec.result .dialsvg{width:104px;height:104px}
.rec.result .name{font-size:21px}
.rec.result .imagewrap,.rec.result .thumb{width:68px;height:68px}
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
.imagewrap{position:relative;display:block;width:52px;height:52px;z-index:1}
.imagewrap .thumb{display:block}
.imagewrap::after{content:"Enlarge";position:absolute;right:3px;bottom:3px;font-family:"IBM Plex Mono",monospace;font-size:7px;line-height:1;text-transform:uppercase;letter-spacing:.06em;color:#fff;background:rgba(15,109,114,.88);border-radius:3px;padding:3px;opacity:0;transition:opacity .12s}
.imagewrap:hover::after,.imagewrap:focus-visible::after{opacity:1}
.imagewrap .imagepreview{display:none;position:absolute;right:-10px;bottom:calc(100% + 9px);width:240px;height:240px;object-fit:contain;padding:10px;background:var(--thumb-bg);border:1px solid var(--line-2);border-radius:14px;box-shadow:0 14px 40px rgba(0,0,0,.24);z-index:30}
.imagewrap:hover .imagepreview,.imagewrap:focus-visible .imagepreview{display:block}
.imagewrap[data-preview]{cursor:zoom-in}
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
.choicehead{padding:18px 2px 10px; color:var(--ink-2)}
.choicehead h2{font-family:"Zilla Slab",serif; font-size:22px; margin:0 0 3px; color:var(--ink)}
.choicehead p{margin:0}
.choice{
  display:grid; grid-template-columns:52px 1fr auto; gap:13px; align-items:center;
  width:100%; text-align:left; font:inherit; color:var(--ink); cursor:pointer;
  background:var(--surface); border:1px solid var(--line); border-radius:12px;
  padding:12px; box-shadow:var(--shadow);
}
.choice:hover{border-color:var(--accent); background:var(--surface)}
.choice .imagewrap{grid-column:1; grid-row:1 / span 2}
.choice .choicecopy{grid-column:2; min-width:0}
.choice .choose{grid-column:3; grid-row:1 / span 2; white-space:nowrap}
.choice .meta{margin-top:4px}
.choose{font-family:"IBM Plex Mono",monospace; font-size:10px; letter-spacing:.08em; text-transform:uppercase; color:var(--accent-ink); background:var(--accent-soft); border-radius:5px; padding:5px 7px}
.warning{color:var(--stop-ink); background:var(--stop-soft); border-left:3px solid var(--stop); border-radius:5px; padding:7px 9px; margin:8px 0 0; font-size:13px}
.observed{margin:7px 0 0;color:var(--ink-3);font-size:12px}
.history{margin-top:8px;color:var(--ink-3);font-size:12px}
.history summary{cursor:pointer;font-family:"IBM Plex Mono",monospace;font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--accent-ink)}
.history ol{margin-top:6px;gap:4px}.history li{display:flex;gap:8px}.history time{font-variant-numeric:tabular-nums}
.imagebox{width:min(520px,calc(100vw - 32px));border:0;border-radius:16px;padding:0;background:var(--surface);color:var(--ink);box-shadow:0 24px 70px rgba(0,0,0,.38)}
.imagebox::backdrop{background:rgba(10,14,17,.68)}
.imageboxhead{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:12px 15px;border-bottom:1px solid var(--line)}
.imageboxhead strong{font-family:"Zilla Slab",serif;font-size:17px}.imageboxclose{font:inherit;cursor:pointer;color:var(--ink-2);background:var(--raised);border:1px solid var(--line-2);border-radius:999px;padding:4px 10px}
.imagebox img{display:block;width:100%;height:min(64vh,520px);object-fit:contain;background:var(--thumb-bg);padding:18px}

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
.editorial > summary{font-family:"Zilla Slab",serif; font-weight:600; font-size:19.5px; cursor:pointer; list-style:none}
.editorial > summary::-webkit-details-marker{display:none}
.editorial > summary::after{content:"Show"; font-family:"IBM Plex Mono",monospace; font-weight:400; font-size:10px; letter-spacing:.1em; text-transform:uppercase; color:var(--accent-ink); margin-left:8px}
.editorial[open] > summary{margin-bottom:8px}
.editorial[open] > summary::after{content:"Hide"}
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
  .controls{padding:15px}.lookuphead{display:block}.privacytag{display:inline-block;margin-top:9px}.setupgrid{grid-template-columns:1fr}.step.searchstep{grid-column:auto}.machinechoices{grid-template-columns:1fr 1fr}
  .field .tag{display:none}.field .scan{font-size:0;padding:7px}.field .scan svg{width:17px;height:17px}
  .rec{gap:13px; padding:12px 13px}
  .dialsvg{width:52px; height:52px}
  .thumb{width:44px; height:44px}
  .imagewrap{width:44px;height:44px}.imagewrap .imagepreview{display:none!important}.rec.result{grid-template-columns:1fr;text-align:center}.rec.result.hasimg{grid-template-columns:1fr}.rec.result .imagewrap,.rec.result .thumb{width:68px;height:68px}.rec.result .imagewrap{margin:4px auto 0}.rec.result .meta{justify-content:center}.rec.result .dialsvg{width:96px;height:96px}
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
    <h1>What setting does this formula need?</h1>
    <svg class="heromark" viewBox="0 0 100 100" aria-hidden="true"><circle cx="50" cy="50" r="45" fill="none" stroke="var(--dial)" stroke-width="2"></circle><g stroke="var(--dial)" stroke-width="2" stroke-linecap="round"><line x1="50" y1="10" x2="50" y2="16"></line><line x1="50" y1="10" x2="50" y2="16" transform="rotate(36 50 50)"></line><line x1="50" y1="10" x2="50" y2="16" transform="rotate(72 50 50)"></line><line x1="50" y1="10" x2="50" y2="16" transform="rotate(108 50 50)"></line><line x1="50" y1="10" x2="50" y2="16" transform="rotate(144 50 50)"></line><line x1="50" y1="10" x2="50" y2="16" transform="rotate(180 50 50)"></line><line x1="50" y1="10" x2="50" y2="16" transform="rotate(252 50 50)"></line><line x1="50" y1="10" x2="50" y2="16" transform="rotate(288 50 50)"></line><line x1="50" y1="10" x2="50" y2="16" transform="rotate(324 50 50)"></line><line x1="50" y1="10" x2="50" y2="16" transform="rotate(216 50 50)"></line></g><circle cx="50" cy="50" r="26" fill="var(--dial-soft)" stroke="var(--dial)" stroke-width="2.8"></circle><line x1="50" y1="50" x2="50" y2="29" stroke="var(--needle)" stroke-width="3.2" stroke-linecap="round" transform="rotate(216 50 50)"></line><circle cx="50" cy="50" r="4" fill="var(--needle)"></circle></svg>
  </div>
</header>

<section class="strip" id="strip"></section>

<section class="controls" id="controls" aria-labelledby="lookup-title">
  <div class="lookuphead">
    <div><h2 id="lookup-title">Find the right powder setting</h2>
      <p>Choose the machine, market, and exact formula before relying on a number.</p></div>
    <span class="privacytag">Private · on this device</span>
  </div>
  <div class="setupgrid">
    <div class="step" id="machine-step">
      <div class="stephead"><span class="stepnum">1</span><span class="steplabel">Choose your machine</span><span class="stepstatus" id="machine-status">Required</span></div>
      <input id="machine" type="hidden">
      <div class="machinechoices" role="group" aria-label="Your Formula Pro machine">
        <button class="machinechoice" type="button" data-machine="advanced" aria-pressed="false"><strong>Advanced / WiFi</strong><span>Lot 11 may differ</span></button>
        <button class="machinechoice" type="button" data-machine="mini" aria-pressed="false"><strong>Mini</strong><span>Standard setting</span></button>
      </div>
      <div class="lotrow" id="lotrow">
        <div class="terr lotfield">
          <label for="lot">Lot no.</label>
          <input id="lot" type="text" maxlength="14" autocomplete="off" spellcheck="false"
                 placeholder="optional · sticker underneath" aria-label="Machine lot number">
        </div>
        <span class="lotstate" id="lotstate"></span>
      </div>
    </div>
    <div class="step" id="market-step">
      <div class="stephead"><span class="stepnum">2</span><label class="steplabel" for="terr">Where was it sold?</label><span class="stepstatus" id="market-status">Required for a setting</span></div>
      <div class="terr">
        <svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z"></path><circle cx="12" cy="10" r="2.5"></circle></svg>
        <input id="terr" type="search" list="territories" autocomplete="off" spellcheck="false" placeholder="Search or choose a market…" aria-label="Market where the formula was bought">
        <datalist id="territories"></datalist>
      </div>
      <div class="stepstatus" style="margin-top:7px">Leave blank only to explore all markets.</div>
    </div>
    <div class="step searchstep" id="search-step">
      <div class="stephead"><span class="stepnum">3</span><label class="steplabel" for="q">Find your exact formula</label><span class="stepstatus" id="search-status">Brand, formula name, or barcode</span></div>
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
      <div class="quickrow"><span class="quicklabel">Popular brands</span><div class="chips" id="chips"></div></div>
    </div>
  </div>
</section>

<div class="count" id="count"></div>
<ol id="out"></ol>
<div class="empty" id="empty" hidden></div>

<section class="panel">
  <h2>Four checks before making a bottle</h2>
  <p>A lookup result is a starting point, not the whole safety check. Before using
  any setting &mdash; from here, Baby Brezza, or a saved screenshot &mdash; confirm
  these four things.</p>
  <ol>
    <li>
      <div>
        <h3>Match the label and the machine</h3>
        <p>The machine uses this setting to dispense the amount of powder called for
        by the formula label. The right number can depend on brand, product, stage,
        market, and your machine. Formula Pro Advanced, Advanced WiFi, and Mini share
        Baby Brezza's current settings data, but only Advanced and Advanced WiFi can
        use a lot-11 alternate. If this page, the
        <a href="https://babybrezza.com/pages/formula-pro-global-settings-finder">official
        finder</a>, and your label do not agree, stop and confirm the setting with
        Baby Brezza before using the machine. A result marked <em>no dial position</em>
        is Baby Brezza's published 0; because the dial runs 1&ndash;10, do not treat
        it as a usable setting.</p>
      </div>
    </li>
    <li>
      <div>
        <h3>Recheck when anything changes</h3>
        <p>Baby Brezza can revise settings without publishing a change log. Compared
        with a frozen copy of its data from around 2022, <strong>59 of 276
        unambiguous settings had changed</strong>; Similac Advance moved from
        4&nbsp;to&nbsp;5 and Alimentum from 6&nbsp;to&nbsp;5. That historical copy
        is not used for lookup results. It appears only as a struck-out <em>was</em>
        note where it differs from the current number. Recheck whenever you change
        formula, buy a newly labeled container, or replace the machine.</p>
      </div>
    </li>
    <li>
      <div>
        <h3>Keep it clean, then verify the output</h3>
        <p>A correct setting cannot compensate for caked powder or a clogged funnel.
        Baby Brezza says to clean the mixing funnel after every fourth bottle, keep
        powder above the MIN line, and keep powder-contact parts completely dry. To
        check what your machine actually dispenses, use its
        <a href="https://babybrezza.com/blogs/news/how-we-test-the-formula-pro-to-ensure-it-dispenses-formula-accurately">plastic-wrap
        test</a> with a kitchen scale that reads to one-hundredth of a gram, then
        compare the dispensed powder with the weight specified on the formula label.</p>
      </div>
    </li>
    <li>
      <div>
        <h3>Take extra care with higher-risk infants</h3>
        <p>Powdered formula is not sterile. The
        <a href="https://www.cdc.gov/cronobacter/prevention/index.html">CDC</a>
        identifies babies younger than 2 months, born prematurely, or with weakened
        immune systems as higher risk and recommends ready-to-feed liquid formula
        when possible. If powdered formula is used, CDC and
        <a href="https://www.who.int/publications/i/item/9789241595414">WHO</a>
        describe mixing it with very hot water; WHO specifies at least
        158&nbsp;&deg;F&thinsp;/&thinsp;70&nbsp;&deg;C. That requires separate
        preparation rather than a Formula Pro's normal dispensing cycle. Ask your
        baby's clinician which method fits your baby and formula. The
        <a href="https://www.healthychildren.org/English/ages-stages/baby/formula-feeding/Pages/how-to-safely-prepare-formula-with-water.aspx">AAP's
        preparation guide</a> also covers water, storage, and measuring exactly as
        directed on the label.</p>
      </div>
    </li>
  </ol>
</section>

<details class="panel editorial">
  <summary>About this independent, private lookup</summary>
  <p>Baby Brezza's finder will not show a setting until you enter an email address, and
  each search there is logged &mdash; email, IP address, city, ZIP, and the formula
  you looked up &mdash; whether or not you tick the consent box. The number itself
  is supplied by a public settings API that does not require an email. This page
  makes that same data searchable locally.</p>
  <p>Every number comes from Baby Brezza's own settings API, collected by an
  exhaustive crawl. __SOURCE_LINKS__</p>
  <details>
    <summary>What the official finder sends</summary>
    <p>The following behavior is visible in Baby Brezza's
    <code>formula-settings.js</code>: a lookup can send data to three destinations,
    and only one of them depends on marketing consent.</p>
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
          "I agree to receive marketing emails". This request is consent-gated.</p>
        </div>
      </li>
      <li>
        <div>
          <h3>Warranty registration<span class="gate">skippable</span></h3>
          <p>Name and email are sent to
          <code>portal.babybrezza.com/api/warranty/activate</code>. Registration is
          optional and can be skipped without affecting the setting lookup.</p>
        </div>
      </li>
    </ol>
    <p style="margin-top:16px">The location fields aren't guessed from your address &mdash;
    the page loads an IP-geolocation script that writes your city, region, ZIP and IP
    into cookies, which the logger then reads back. Meanwhile the email itself is
    checked by a regular expression in your browser; the settings API itself never
    asks for it.</p>
  </details>
  <p style="margin-top:14px"><strong>This page uses no analytics or cookies and has
  no lookup backend.</strong> Every setting is already inside the file your browser downloaded;
  searching runs locally, and your lot number stays in this tab. The barcode scanner
  is on-device too: camera frames are decoded in your browser and never uploaded.</p>
  <p><strong>Historical note:</strong> the discontinued Original Formula Pro is not
  supported by this app. Its frozen crawl is retained only as a research archive;
  none of its values are loaded, searched, or shown here.</p>
</details>

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

<dialog class="imagebox" id="imagebox">
  <div class="imageboxhead"><strong id="imageboxtitle">Product image</strong><button class="imageboxclose" id="imageboxclose" type="button">Close</button></div>
  <img id="imageboximg" alt="">
</dialog>

<script>
const D = __DATA__;
const QUICK = __QUICK__;

const fold = s => (s||"").normalize("NFKD").replace(/[\u0300-\u036f]/g,"").toLowerCase();
const HAY  = D.R.map(r => fold(D.B[r[0]] + " " + r[1] + " " + r[2]));
const MASK = D.R.map(r => BigInt("0x" + r[4]));
// U is optional so a page can still be generated from an older snapshot.
const U = D.U || [];
const UHAY = U.map(r => fold(D.B[r[0]] + " " + r[1] + " " + r[2]));
const UMASK = U.map(r => BigInt("0x" + r[3]));

const el = id => document.getElementById(id);
const $q=el("q"), $machine=el("machine"), $terr=el("terr"), $territories=el("territories"), $out=el("out"), $count=el("count"),
      $empty=el("empty"), $mode=el("mode"), $chips=el("chips"),
      $strip=el("strip"), $lot=el("lot"), $lotrow=el("lotrow"),
      $lotstate=el("lotstate"), $machineStep=el("machine-step"),
      $marketStep=el("market-step"), $searchStep=el("search-step"),
      $machineStatus=el("machine-status"), $marketStatus=el("market-status"),
      $searchStatus=el("search-status");

const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
function fmtFullDate(iso){
  if (!iso) return "";
  const [y,m,d] = iso.split("-");
  return `${MONTHS[+m - 1]} ${+d}, ${y}`;
}

// Baby Brezza reads the machine's lot number and switches to a second set of
// settings when it starts with 11. Their own field is uppercased, max 14.
const lotIsAlt = () => $lot.value.trim().toUpperCase().startsWith("11");

const store = {
  get(k,d){ try{ return localStorage.getItem(k) ?? d }catch(e){ return d } },
  set(k,v){ try{ localStorage.setItem(k,v) }catch(e){} },
  remove(k){ try{ localStorage.removeItem(k) }catch(e){} }
};
const tabStore = {
  get(k,d){ try{ return sessionStorage.getItem(k) ?? d }catch(e){ return d } },
  set(k,v){ try{ sessionStorage.setItem(k,v) }catch(e){} }
};
// Older builds persisted formula searches. Remove that legacy key once so an
// upgrade also honors the current session-only privacy boundary.
try{ localStorage.removeItem("brezza.q") }catch(e){}

let machine = store.get("brezza.machine", "");
if (!["advanced", "mini"].includes(machine)) machine = "";
let chosen = null;
let shownResult = null;

const esc = s => String(s).replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
const escAttr = s => String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const market = () => D.T.includes($terr.value.trim()) ? $terr.value.trim() : "";

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

function renderStrip(){
  const c = D.M.counts;
  const machineNote = machine === "advanced"
    ? "Advanced / WiFi selected &middot; enter a lot number only if it begins with 11."
    : machine === "mini"
      ? "Mini selected &middot; Mini always uses the standard setting; no lot number needed."
      : "Choose your machine before looking up a setting.";
  $strip.innerHTML = `<span class="striptag">Current data &middot; Advanced / WiFi / Mini</span>
    <span>${machineNote} ${c.records.toLocaleString()} settings &middot; last checked against Baby Brezza’s data
    ${fmtFullDate(D.M.observed || D.M.generated)}</span>`;
}

function applyMachine(){
  renderStrip();
  // The current data is shared, but lot-11 alternates belong only to
  // Advanced and Advanced WiFi machines; Mini never takes this branch.
  $lotrow.hidden = machine !== "advanced";
  $scan.hidden = !machine || !canScan;
  syncLot();
  $q.placeholder = "Enfamil NeuroPro, Kirkland, 070074680644…";
  const prev = store.get("brezza.terr", "");
  $territories.innerHTML = D.T.map(t => `<option value="${escAttr(t)}"></option>`).join("");
  $terr.value = D.T.includes(prev) ? prev : "";
  document.querySelectorAll("[data-machine]").forEach(button => {
    button.setAttribute("aria-pressed", String(button.dataset.machine === machine));
  });

  $chips.innerHTML = QUICK.filter(b => D.B.includes(b))
    .map(b => `<button class="chip" type="button">${esc(b)}</button>`).join("");
}

$chips.addEventListener("click", e => {
  const b = e.target.closest(".chip");
  if (!b) return;
  chosen = null; $q.value = b.textContent; run(); $q.focus();
});

const digits = s => s.replace(/[^0-9]/g,"");
const isBarcode = s => digits(s).length >= 8 && digits(s).length === s.replace(/[\s-]/g,"").length;

function search(){
  const raw = $q.value.trim();
  if (!raw) return {mode:"", hits:[], unavailable:[]};
  const ti = D.T.indexOf(market());
  const bit = ti >= 0 ? (1n << BigInt(ti)) : 0n;

  if (isBarcode(raw)){
    // Same tin, two spellings: scanners hand back 12-digit UPC-A or 13-digit
    // EAN with a leading 0, and the dataset stores a mix of both. Canonicalise
    // BOTH sides before comparing — Baby Brezza's own API is exact-string here
    // and misses its own records when the forms differ.
    const canon = d => d.length === 13 && d[0] === "0" ? d.slice(1) : d;
    const want = canon(digits(raw));
    const hits = [], unavailable = [];
    for (let i = 0; i < D.R.length; i++){
      if (ti >= 0 && (MASK[i] & bit) === 0n) continue;
      for (const u of rowUpcs(D.R[i])){
        if (canon(digits(u)) === want){ hits.push(i); break }
      }
    }
    for (let i = 0; i < U.length; i++){
      if (ti >= 0 && (UMASK[i] & bit) === 0n) continue;
      for (const u of U[i][5]){
        if (canon(digits(u)) === want){ unavailable.push(i); break }
      }
    }
    // A barcode often identifies an international product family rather than
    // one country-specific setting, so honor the selected sales territory.
    return {mode:"barcode", hits, unavailable};
  }

  const terms = fold(raw).split(/\s+/).filter(Boolean);
  const hits = [], unavailable = [];
  for (let i = 0; i < D.R.length; i++){
    if (ti >= 0 && (MASK[i] & bit) === 0n) continue;
    let ok = true;
    for (const t of terms) if (!HAY[i].includes(t)){ ok = false; break }
    if (ok) hits.push(i);
  }
  for (let i = 0; i < U.length; i++){
    if (ti >= 0 && (UMASK[i] & bit) === 0n) continue;
    if (terms.every(t => UHAY[i].includes(t))) unavailable.push(i);
  }
  hits.sort((a,b) => {
    const sa = fold(D.B[D.R[a][0]]).startsWith(terms[0]) ? 0 : 1;
    const sb = fold(D.B[D.R[b][0]]).startsWith(terms[0]) ? 0 : 1;
    return sa !== sb ? sa - sb : HAY[a].length - HAY[b].length;
  });
  return {mode:"text", hits, unavailable};
}

function selectedVariant(r){
  const ti = D.T.indexOf(market());
  if (ti < 0 || !r[10]) return null;
  const bit = 1n << BigInt(ti);
  return r[10].find(v => (BigInt("0x" + v[0]) & bit) !== 0n) || null;
}
function rowUpcs(r){
  if (!market() || !r[10]) return r[5];
  const variant = selectedVariant(r);
  return variant ? variant[1] : [];
}
function rowThumb(r){
  if (!market() || !r[10]) return r[9];
  const variant = selectedVariant(r);
  return variant ? variant[3] : null;
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
function unavailableCard(i){
  const r = U[i], label = D.B[r[0]] + " · " + r[1], thumb = productImage(r[6], label);
  const where = countryLabel(UMASK[i]);
  const detail = r[4] === "no_stage"
    ? "Baby Brezza lists the product but does not provide the stage its finder requires."
    : "Baby Brezza lists the product but returns no setting for it.";
  return `<li class="rec${thumb ? " hasimg" : ""}">
    ${stopSVG(null)}
    <div><p class="name">${esc(label)}</p>
      <div class="meta">${r[2] ? `<span class="stage">Stage ${esc(r[2])}</span>` : ""}<span class="where">${esc(where)}</span></div>
      <p class="warning"><strong>Baby Brezza lists this formula but publishes no usable setting.</strong> ${detail} Do not use it in the machine unless Baby Brezza confirms compatibility and the correct setting.</p>
    </div>${thumb}</li>`;
}

function choiceCard(i, terms){
  const r = D.R[i], label = D.B[r[0]] + " · " + r[1], thumb = productImage(rowThumb(r), label, false);
  return `<li><button class="choice" type="button" data-choice="${i}">
    ${thumb}<div class="choicecopy"><p class="name">${mark(D.B[r[0]] + " · " + r[1], terms)}</p>
      <div class="meta">${r[2] ? `<span class="stage">Stage ${esc(r[2])}</span>` : ""}<span class="where">${esc(market() || countryLabel(MASK[i]))}</span></div>
    </div><span class="choose">Choose formula</span></button></li>`;
}

function historyMarkup(r){
  const ti = D.T.indexOf(market());
  if (ti < 0 || !r[11]) return "";
  const bit = 1n << BigInt(ti);
  const events = r[11].filter(event => (BigInt("0x" + event[4]) & bit) !== 0n);
  if (!events.length) return "";
  const rows = events.map(event => {
    const label = event[1] === "alt_setting" ? "Lot 11 setting" : "Standard setting";
    const before = event[2] == null ? "not published" : event[2];
    const after = event[3] == null ? "not published" : event[3];
    return `<li><time datetime="${escAttr(event[0])}">${fmtFullDate(event[0])}</time><span>${label}: ${esc(before)} → ${esc(after)}</span></li>`;
  }).join("");
  return `<details class="history"><summary>Setting history · ${events.length} ${events.length === 1 ? "change" : "changes"}</summary><ol>${rows}</ol></details>`;
}

function resultCard(i, terms){
  const r = D.R[i], standard = r[3], altSetting = r[6];
  // A lot-11 Advanced takes the alternate number. Mini never takes this branch.
  const useAlt = machine === "advanced" && altSetting != null && lotIsAlt();
  const setting = useAlt ? altSetting : standard;
  const num = typeof setting === "number" && setting > 0;
  const where = `<span class="where">${esc(market() || countryLabel(MASK[i]))}</span>`;
  const altChip = machine !== "advanced" || altSetting == null ? ""
    : useAlt
      ? `<span class="std">Standard machine: ${standard}</span>`
      : `<span class="alt" title="Formula Pro Advanced and Advanced WiFi units whose lot number starts with 11 use this alternate. Mini never uses it.">Lot 11… → ${altSetting}</span>`;
  const was = r[8] ? `<span class="was" title="This record's setting in a frozen copy of Baby Brezza's own data from around 2022 — evidence the number moves, not an official change log.">was <s>${esc(r[8])}</s></span>` : "";
  const label = D.B[r[0]] + " · " + r[1];
  const thumb = productImage(rowThumb(r), label);
  const nope = num ? `<span class="sr">Setting ${setting}</span>`
    : setting === 0
      ? `<span class="nope" title="Baby Brezza publishes 0 for this formula. Because the dial runs 1–10, do not use it without confirming compatibility and the correct setting.">No dial position</span>`
      : `<span class="nope">${esc(setting)}</span>`;
  const observed = D.M.observed ? `<p class="observed">Last checked against Baby Brezza’s data on ${fmtFullDate(D.M.observed)}.</p>` : "";
  const history = historyMarkup(r);
  return `<li class="rec result${thumb ? " hasimg" : ""}">
    <div class="resultdial"><span class="resultlabel">Your setting</span>${num ? dialSVG(setting) : stopSVG(setting)}</div>
    <div><p class="name">${mark(label, terms)}</p>
      <div class="meta">${r[2] ? `<span class="stage">Stage ${esc(r[2])}</span>` : ""}${nope}${altChip}${was}${where}</div>${observed}${history}
    </div>${thumb}</li>`;
}

function productImage(name, label, interactive=true){
  if (!name) return "";
  const attrs = interactive
    ? ` data-preview="thumbs/${escAttr(name)}.webp" data-label="${escAttr(label)}" tabindex="0" role="button" aria-label="Enlarge image of ${escAttr(label)}"`
    : "";
  return `<span class="imagewrap"${attrs}><img class="thumb" src="thumbs/${escAttr(name)}.webp" loading="lazy" decoding="async" alt=""><img class="imagepreview" src="thumbs/${escAttr(name)}.webp" loading="lazy" decoding="async" alt=""></span>`;
}

function updateSteps(raw){
  const selectedMarket = market();
  const invalidMarket = $terr.value.trim() && !selectedMarket;
  $machineStep.classList.toggle("done", !!machine);
  $machineStep.classList.toggle("needs", !machine);
  $marketStep.classList.toggle("done", !!selectedMarket);
  $marketStep.classList.toggle("needs", !!machine && !selectedMarket);
  $searchStep.classList.toggle("done", !!raw);
  $searchStep.classList.toggle("needs", !!machine && !!selectedMarket && !raw);
  $machineStatus.textContent = machine === "advanced" ? "Advanced / WiFi" : machine === "mini" ? "Mini" : "Required";
  $marketStatus.textContent = selectedMarket ? selectedMarket : invalidMarket ? "Choose a listed market" : "Required for a setting";
  $searchStatus.textContent = raw ? "Searching formulas" : "Brand, formula name, or barcode";
}

function run(){
  const raw = $q.value.trim();
  tabStore.set("brezza.q", raw);
  if (market()) store.set("brezza.terr", market());
  else if (!$terr.value.trim()) store.remove("brezza.terr");
  updateSteps(raw);
  if (!machine){
    $mode.hidden = true; $count.textContent=""; $out.innerHTML=""; $empty.hidden=false;
    $empty.innerHTML = "<p>Start by choosing your machine. Lot numbers beginning with 11 can change settings on Advanced and Advanced WiFi machines; Mini uses the standard setting.</p>";
    return;
  }
  const {mode, hits, unavailable} = search();
  $mode.hidden = mode !== "barcode";

  if (!raw){
    $count.textContent=""; $out.innerHTML=""; $empty.hidden=false;
    $empty.innerHTML = "<p>Enter the brand or formula name on the container, or paste its barcode.</p>";
    return;
  }
  if (!hits.length && !unavailable.length){
    $count.textContent=""; $out.innerHTML=""; $empty.hidden=false;
    $empty.innerHTML = mode === "barcode"
      ? "<p>No formula with that barcode appears in the selected market. Clear the market to search everywhere, or try the brand name; barcodes can vary by package size.</p>"
      : (market()
          ? `<p>Nothing matching that in ${esc(market())}. Clear the market to explore everywhere.</p>`
          : `<p>No match in the ${esc(D.M.label)} data. Try just the brand name.</p>`);
    return;
  }
  $empty.hidden = true;

  const terms = mode === "text" ? fold(raw).split(/\s+/).filter(Boolean) : [];
  if (!hits.length){
    $count.textContent = unavailable.length === 1 ? "Known formula" : `${unavailable.length} known formulas`;
    $out.innerHTML = unavailable.slice(0, MAX).map(unavailableCard).join("");
    return;
  }
  // Anywhere is intentionally useful for browsing, but market-specific source
  // rows can disagree. Never turn it into a dial instruction: require the
  // market selector before rendering any actionable result, even for one hit.
  if (!market()){
    $count.textContent = `${hits.length} possible ${hits.length === 1 ? "match" : "matches"} — choose where the formula was sold`;
    $out.innerHTML = `<li class="choicehead"><h2>Step 2: choose where it was sold</h2><p>Search for or choose a market before using a dial setting. The same formula name or barcode can point to different products in different markets.</p></li>` +
      hits.slice(0, MAX).map(i => choiceCard(i, terms)).join("");
    return;
  }
  if (!hits.includes(chosen)) chosen = null;
  if (hits.length > 1 && chosen == null){
    $count.textContent = `${hits.length} possible matches — choose the exact formula`;
    const warning = mode === "barcode"
      ? "More than one product or setting uses this barcode. Do not use a dial setting until you choose the matching formula and market."
      : "Several products match this search. Choose the exact formula before using a dial setting.";
    $out.innerHTML = `<li class="choicehead"><h2>Step 4: which formula matches your container?</h2><p>${warning}</p></li>` +
      hits.slice(0, MAX).map(i => choiceCard(i, terms)).join("");
    return;
  }
  const i = chosen == null ? hits[0] : chosen;
  const resultChanged = shownResult !== i;
  $count.textContent = "Exact formula match" + (unavailable.length ? " — related formulas without a published setting are listed below" : "");
  $out.innerHTML = resultCard(i, terms) + unavailable.map(unavailableCard).join("");
  shownResult = i;
  if (resultChanged) requestAnimationFrame(() => $out.firstElementChild?.scrollIntoView({behavior:"smooth",block:"nearest"}));
}

el("foot").innerHTML =
  `${D.M.counts.records.toLocaleString()} current settings for Formula Pro Advanced, Advanced WiFi, and Mini across ` +
  `${D.M.counts.territories} markets/territories. Source crawl observed ${fmtFullDate(D.M.observed || D.M.generated)}. ` +
  `${D.M.counts.alt} carry a lot-11 alternate for Advanced / WiFi machines and ` +
  `${D.M.counts.zero} answer with a 0 rather than a dial position. ` +
  `<p style="margin-top:10px">Unofficial and not affiliated with Baby Brezza &mdash; ` +
  `built because a safety lookup should not require an email address. All settings ` +
  `come from Baby Brezza's public data. __FOOT_SOURCE_LINKS__</p>`;

function syncLot(){
  const raw = $lot.value.trim().toUpperCase();
  if ($lot.value !== raw) $lot.value = raw;
  tabStore.set("brezza.lot", raw);
  if (machine !== "advanced" || !raw){
    $lotstate.className = "lotstate";
    $lotstate.textContent = machine === "advanced"
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
document.querySelectorAll("[data-machine]").forEach(button => button.addEventListener("click", () => {
  $machine.value = button.dataset.machine;
  $machine.dispatchEvent(new Event("change", {bubbles:true}));
}));
$machine.addEventListener("change", () => {
  machine = $machine.value;
  chosen = null;
  store.set("brezza.machine", machine);
  applyMachine();
  run();
  if (machine) $terr.focus({preventScroll:true});
});

// ---- barcode scanner ----
// Native BarcodeDetector where it actually has a backend (Chromium); otherwise
// the library the official page uses, in its maintained fork
// (vendor/quagga2-1.12.1.min.js), loaded same-origin only when asked for.
// Frames are decoded on-device; nothing is uploaded.
const $scan=el("scan"), $scanner=el("scanner"), $viewport=el("viewport"),
      $scanstate=el("scanstate"), $scanclose=el("scanclose");
const $imagebox=el("imagebox"), $imageboximg=el("imageboximg"),
      $imageboxtitle=el("imageboxtitle"), $imageboxclose=el("imageboxclose");
const canScan = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
let scanStop = null, lastRead = "";

const scanMsg = t => { $scanstate.textContent = t };

function acceptCode(code){
  code = (code || "").trim();
  if (!code) return;
  if (code !== lastRead){ lastRead = code; return }  // same code twice, like theirs
  closeScanner();
  chosen = null;
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
$q.addEventListener("input", () => { chosen = null; clearTimeout(timer); timer = setTimeout(run, 90) });
$terr.addEventListener("input", () => { chosen = null; clearTimeout(timer); timer = setTimeout(run, 90) });
$terr.addEventListener("change", () => { chosen = null; run() });
$out.addEventListener("click", e => {
  const preview = e.target.closest("[data-preview]");
  if (preview){
    $imageboximg.src = preview.dataset.preview;
    $imageboximg.alt = preview.dataset.label;
    $imageboxtitle.textContent = preview.dataset.label;
    $imagebox.showModal();
    return;
  }
  const button = e.target.closest("[data-choice]");
  if (!button) return;
  chosen = +button.dataset.choice;
  run();
});
$out.addEventListener("keydown", e => {
  const preview = e.target.closest("[data-preview]");
  if (preview && (e.key === "Enter" || e.key === " ")){
    e.preventDefault(); preview.click();
  }
});
$imageboxclose.addEventListener("click", () => $imagebox.close());
$imagebox.addEventListener("click", e => {
  if (e.target === $imagebox) $imagebox.close();
});
$lot.value = tabStore.get("brezza.lot","");
$machine.value = machine;
applyMachine();
$q.value = tabStore.get("brezza.q","");
run();
(machine ? (market() ? $q : $terr) : document.querySelector("[data-machine]"))?.focus({preventScroll:true});
</script>
"""


def main():
    packed = pack(json.load(open(DATA)))
    wanted = ["Enfamil", "Similac", "Kirkland", "Bobbie", "Kendamil", "HiPP", "Holle",
              "ByHeart", "Parent's Choice", "Good Start", "Gerber", "Earth's Best"]
    quick = [b for b in wanted if b in packed["B"]]
    repo = public_repository_url()
    if repo:
        source_links = (
            f'<a href="{repo}">Browse the source and dataset</a> &middot; '
            f'<a href="{repo}/blob/main/docs/HOW-IT-WORKS.md">Read how it works</a>. '
            f'Found a setting that disagrees with your label? '
            f'<a href="{repo}/issues">Open an issue</a>.'
        )
        foot_source_links = (
            f'<a href="{repo}">Source and dataset</a> &middot; '
            f'<a href="{repo}/blob/main/docs/HOW-IT-WORKS.md">How it works</a>.'
        )
    else:
        source_links = (
            '<a href="data/formula_settings.json" download>Download the current dataset</a>. '
            'Found a setting that disagrees with your label? Confirm it with Baby Brezza.'
        )
        foot_source_links = '<a href="data/formula_settings.json" download>Download the current dataset</a>.'
    html = (TEMPLATE
            .replace("__DATA__", json.dumps(packed, ensure_ascii=False, separators=(",", ":")))
            .replace("__QUICK__", json.dumps(quick, ensure_ascii=False))
            .replace("__SOURCE_LINKS__", source_links)
            .replace("__FOOT_SOURCE_LINKS__", foot_source_links))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write(html)
    nwas = sum(1 for r in packed["R"] if r[8])
    nthumb = sum(1 for r in packed["R"] if r[9])
    print(f"wrote {OUT} ({os.path.getsize(OUT)/1e6:.2f} MB), "
          f"{len(packed['R'])} current Advanced-family records, {len(packed['B'])} brands, "
          f"{nwas} rows carry a 'was' chip (staleness examples: 59), "
          f"{nthumb} carry a product photo")


if __name__ == "__main__":
    main()
