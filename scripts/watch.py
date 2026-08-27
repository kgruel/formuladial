#!/usr/bin/env python3
"""The weekly tripwire: is Baby Brezza's data still what we published?

The full walk is 69,520 requests (~10h).  This is the cheap check that decides
whether it is worth running -- roughly 10k requests, ~1.5h at the crawlers'
existing concurrency:

  * the shape of the catalogue: territories -> brands -> types (~6.5k GETs),
    diffed against `data/watch_baseline.json`;
  * every image the snapshot references, HEADed for `Last-Modified` (~3.5k),
    diffed against the `image_date` values already in the snapshot;
  * a fixed set of ~30 popular formulas across US/EU/UK/CA (SENTINELS below),
    re-queried and compared to their published settings -- including the
    lot-11 alternates, which are the values documented to drift.

The catalogue baseline cannot be derived from the snapshot: 194 live
(territory, brand, type) combinations answer with no setting at all, so they
exist upstream and are absent downstream by design.  Diffing live types against
the snapshot would therefore report "changed" every week forever.  Hence a
separate `data/watch_baseline.json`, written by `--write-baseline` from a
completed crawl and refreshed by the full-crawl workflow.

Sentinel *expectations* are not baked in -- only the queries are.  The values
are read from the committed snapshot at runtime, so a legitimate full crawl
re-arms them automatically.

All HTTP goes through crawlers/api.py (`get`, `head`) at the same bounded
concurrency the crawlers use; there is no second client here.

Usage:
    python3 scripts/watch.py                    # crawl + diff, JSON on stdout
    python3 scripts/watch.py --out watch.json   # also write the report to a file
    python3 scripts/watch.py --write-baseline   # rebuild data/watch_baseline.json
                                                #   from data/raw/types.jsonl
    python3 scripts/watch.py --offline FILE     # diff a captured observation, no network

Exit codes: 0 unchanged, 1 changed, 2 error.
"""
import argparse, datetime, json, os, sys
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "crawlers"))
from api import IMAGE_BASE, EmptyResponse, get, head  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SNAPSHOT = os.path.join(ROOT, "site/data/formula_settings.json")
BASELINE = os.path.join(ROOT, "data/watch_baseline.json")
TYPES_JSONL = os.path.join(ROOT, "data/raw/types.jsonl")
BRANDS_JSON = os.path.join(ROOT, "data/brands_by_territory.json")

# (territory, brand, type, stage, also_probe_lot_11).  Chosen from the dataset:
# mainstream lines in the four highest-traffic territories, biased towards the
# ones crawl_alt.py found a lot-11 alternate for.
SENTINELS = [
    ["United States of America", "Similac", "360 Total Care", "1", True],
    ["United States of America", "Enfamil", "A2 Premium", "1", False],
    ["United States of America", "Enfamil", "NeuroPro Gentlease", "0-12 Months", True],
    ["United States of America", "Good Start", "Good Start Gentle Pro", "0-12 Months", False],
    ["United States of America", "Parent's Choice", "Added Rice", "1", False],
    ["United States of America", "Kirkland", "ProCare 2FL HMO +DHA Lutein", "1", True],
    ["United States of America", "Bobbie", "Grass Fed Whole Milk", "0-12 Months", False],
    ["United States of America", "ByHeart", "Whole Nutrition Infant formula", "1", False],
    ["United States of America", "Member's Mark", "Advantage Non GMO 2 FL HMO", "1", True],
    ["United States of America", "Earth's Best", "Organic Gentle +DHA ARA +Iron", "0-12 Months", True],
    ["United States of America", "Happy Baby", "Organic Infant formula +Iron", "1", False],
    ["United States of America", "Kendamil", "Goat Infant Formula", "0-12 Months", True],
    ["Germany", "Aptamil", "AR", "1 (Switzerland)", False],
    ["Germany", "HiPP", "Anti Reflux", "From Birth", False],
    ["Germany", "Holle", "Bio", "2 Netherlands", False],
    ["Germany", "Nestlé NAN", "AR", "From Birth", False],
    ["Germany", "Bebivita", "Anfangsmilch", "1", False],
    ["Germany", "Milupa", "Aptamil", "1", False],
    ["France", "Gallia", "Bébé Expert AC Transit", "2", False],
    ["France", "Guigoz", "Bio +DHA", "3 Croissance", False],
    ["France", "Nestlé NAN", "AR", "From Birth", False],
    ["France", "Physiolac", "+DHA", "1", False],
    ["France", "Novalac", "1", "1", False],
    ["United Kingdom", "Aptamil", "Anti Reflux", "From Birth", False],
    ["United Kingdom", "Cow & Gate", "Anti Reflux", "From Birth", False],
    ["United Kingdom", "SMA", "Advanced", "1", False],
    ["United Kingdom", "Kendamil", "Comfort", "From Birth", False],
    ["United Kingdom", "HiPP", "Organic Anti Reflux", "1", False],
    ["Canada", "Similac", "360 Total Care", "1", True],
    ["Canada", "Enfamil", "A+ DHA-Plus", "1", False],
]


def skey(terr, brand, typ, stage):
    """Stable JSON-safe dict key for a sentinel query (names contain spaces)."""
    return json.dumps([terr, brand, typ, stage], ensure_ascii=False)


# --------------------------------------------------------------------------
# baseline
# --------------------------------------------------------------------------

def write_baseline(types_path=TYPES_JSONL, brands_path=BRANDS_JSON, out=BASELINE):
    """Compact the last completed types crawl into the committed baseline."""
    brands = json.load(open(brands_path))
    types = {}
    with open(types_path) as f:
        for line in f:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("error"):
                continue
            types.setdefault(r["territory"], {})[r["brand"]] = sorted(r["types"] or [])
    doc = {
        "generated": datetime.datetime.now(datetime.timezone.utc).date().isoformat(),
        "note": "Catalogue shape as last crawled: territory -> brand -> types. "
                "Written by scripts/watch.py --write-baseline; the weekly "
                "tripwire diffs the live API against this.",
        "territories": sorted(brands),
        "brands": {t: sorted(bs) for t, bs in sorted(brands.items())},
        "types": {t: dict(sorted(bt.items())) for t, bt in sorted(types.items())},
    }
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write("\n")
    return {"territories": len(doc["territories"]),
            "pairs": sum(len(v) for v in doc["types"].values()),
            "out": out}


# --------------------------------------------------------------------------
# what the snapshot expects
# --------------------------------------------------------------------------

def expectations(snapshot):
    """Pull the image dates and sentinel settings the snapshot committed to."""
    images, settings = {}, {}
    for r in snapshot["records"]:
        if r.get("image"):
            images[r["image"]] = r.get("image_date")
        for terr in r["territories"]:
            settings[skey(terr, r["brand"], r["type"], r["stage"])] = {
                "setting": r["setting"], "alt_setting": r.get("alt_setting"),
            }
    return images, settings


# --------------------------------------------------------------------------
# collection (network)
# --------------------------------------------------------------------------

def _pmap(fn, items, workers):
    with ThreadPoolExecutor(workers) as ex:
        return list(ex.map(fn, items))


def collect(baseline, expected_images, progress=lambda *a: None):
    """Everything the diff needs, fetched live.  ~10k requests."""
    obs = {"territories": [], "brands": {}, "types": {}, "images": {},
           "sentinels": {}, "errors": []}

    try:
        obs["territories"] = sorted(get("territories"))
    except Exception as e:
        obs["errors"].append("territories: %s" % e)

    terrs = obs["territories"] or baseline["territories"]

    def brands_of(t):
        try:
            return t, sorted(get("brands", territory=t))
        except Exception as e:
            obs["errors"].append("brands %s: %s" % (t, e))
            return t, None

    for t, bs in _pmap(brands_of, terrs, 7):
        if bs is not None:
            obs["brands"][t] = bs
    progress("brands", len(obs["brands"]))

    pairs = [(t, b) for t, bs in obs["brands"].items() for b in bs]

    def types_of(p):
        t, b = p
        try:
            return p, sorted(get("types", territory=t, brand=b))
        except Exception as e:
            obs["errors"].append("types %s/%s: %s" % (t, b, e))
            return p, None

    for (t, b), ty in _pmap(types_of, pairs, 7):
        if ty is not None:
            obs["types"].setdefault(t, {})[b] = ty
    progress("types", len(pairs))

    def image_of(img):
        try:
            h = head(IMAGE_BASE + img)
            lm = h.get("Last-Modified")
            return img, (parsedate_to_datetime(lm).date().isoformat() if lm else None)
        except Exception as e:
            return img, {"error": str(e)[:120]}

    for img, val in _pmap(image_of, sorted(expected_images), 10):
        obs["images"][img] = val
    progress("images", len(obs["images"]))

    def sentinel_of(s):
        terr, brand, typ, stage, want_alt = s
        out = {}
        for alt in (["false", "true"] if want_alt else ["false"]):
            try:
                rec = get("settings", territory=terr, brand=brand, type=typ,
                          stage=stage, alt_mfg_setting=alt)
                out[alt] = rec.get("setting")
            except EmptyResponse:
                out[alt] = "__no-match__"
            except Exception as e:
                out[alt] = {"error": str(e)[:120]}
        return skey(terr, brand, typ, stage), out

    for k, v in _pmap(sentinel_of, SENTINELS, 7):
        obs["sentinels"][k] = v
    progress("sentinels", len(obs["sentinels"]))
    return obs


# --------------------------------------------------------------------------
# diff (pure -- no network, testable offline)
# --------------------------------------------------------------------------

def _setdiff(base, live):
    b, l = set(base), set(live)
    return sorted(l - b), sorted(b - l)


def diff(baseline, expected_images, expected_settings, obs, cap=25):
    """Pure comparison of an observation against baseline + snapshot.

    Returns a delta dict whose `changed` key is the verdict.
    """
    d = {"territories": {}, "brands": {}, "types": {}, "images": {},
         "sentinels": [], "errors": list(obs.get("errors", []))[:cap]}

    if obs["territories"]:
        added, removed = _setdiff(baseline["territories"], obs["territories"])
        if added or removed:
            d["territories"] = {"added": added, "removed": removed}

    for t, live in obs["brands"].items():
        added, removed = _setdiff(baseline["brands"].get(t, []), live)
        if added or removed:
            d["brands"][t] = {"added": added, "removed": removed}

    for t, bt in obs["types"].items():
        for b, live in bt.items():
            added, removed = _setdiff(baseline["types"].get(t, {}).get(b, []), live)
            if added or removed:
                d["types"].setdefault(t, {})[b] = {"added": added, "removed": removed}

    # Images: a moved Last-Modified means the picture was re-uploaded; a newly
    # unreachable one usually means the record behind it went away.
    moved, gone = [], []
    for img, val in obs["images"].items():
        if isinstance(val, dict):
            gone.append({"image": img, "error": val.get("error")})
            continue
        was = expected_images.get(img)
        if val != was:
            moved.append({"image": img, "was": was, "now": val})
    d["images"] = {
        "moved": moved[:cap], "moved_total": len(moved),
        "unreachable": gone[:cap], "unreachable_total": len(gone),
    }

    for key, got in obs["sentinels"].items():
        terr, brand, typ, stage = json.loads(key)
        want = expected_settings.get(key)
        if want is None:
            d["sentinels"].append({"query": [terr, brand, typ, stage],
                                   "note": "not in snapshot", "now": got})
            continue
        want_std = want["setting"]
        # No alternate recorded means the lot-11 answer equals the standard one.
        want_alt = want["alt_setting"] if want.get("alt_setting") is not None else want_std
        checks = [("false", want_std)] + ([("true", want_alt)] if "true" in got else [])
        for alt, expect in checks:
            now = got.get(alt)
            if isinstance(now, dict):
                d["errors"].append("sentinel %s %s (%s) alt=%s: %s"
                                   % (brand, typ, terr, alt, now.get("error")))
                continue
            if now == "__no-match__":
                now = None
            if now != expect:
                d["sentinels"].append({"query": [terr, brand, typ, stage],
                                       "alt_mfg_setting": alt == "true",
                                       "was": expect, "now": now})

    d["changed"] = bool(d["territories"] or d["brands"] or d["types"]
                        or d["images"]["moved"] or d["images"]["unreachable"]
                        or d["sentinels"])
    return d


def summarize(d):
    """Human-readable delta, safe to paste into an issue or a commit message."""
    L = []
    if d["territories"]:
        t = d["territories"]
        line = "- Territories: +%d / -%d" % (len(t["added"]), len(t["removed"]))
        if t["added"]:
            line += " (added: %s)" % ", ".join(t["added"][:5])
        if t["removed"]:
            line += " (removed: %s)" % ", ".join(t["removed"][:5])
        L.append(line)
    if d["brands"]:
        added = sum(len(v["added"]) for v in d["brands"].values())
        removed = sum(len(v["removed"]) for v in d["brands"].values())
        L.append("- Brands: +%d / -%d across %d territories"
                 % (added, removed, len(d["brands"])))
        for t, v in list(d["brands"].items())[:8]:
            bits = ["+" + b for b in v["added"][:4]] + ["-" + b for b in v["removed"][:4]]
            L.append("    - %s: %s" % (t, ", ".join(bits)))
    if d["types"]:
        pairs = sum(len(v) for v in d["types"].values())
        added = sum(len(x["added"]) for v in d["types"].values() for x in v.values())
        removed = sum(len(x["removed"]) for v in d["types"].values() for x in v.values())
        L.append("- Types: +%d / -%d across %d (territory, brand) pairs"
                 % (added, removed, pairs))
        shown = 0
        for t, bt in d["types"].items():
            for b, v in bt.items():
                if shown >= 8:
                    break
                bits = ["+" + x for x in v["added"][:3]] + ["-" + x for x in v["removed"][:3]]
                L.append("    - %s / %s: %s" % (t, b, ", ".join(bits)))
                shown += 1
    im = d["images"]
    if im["moved_total"] or im["unreachable_total"]:
        L.append("- Images: %d re-dated, %d unreachable"
                 % (im["moved_total"], im["unreachable_total"]))
        for m in im["moved"][:8]:
            L.append("    - %s: %s -> %s" % (m["image"], m["was"], m["now"]))
    if d["sentinels"]:
        L.append("- Sentinels: %d disagree (of %d probed formulas)"
                 % (len(d["sentinels"]), len(SENTINELS)))
        for s in d["sentinels"][:12]:
            terr, brand, typ, stage = s["query"]
            lot = " (lot 11)" if s.get("alt_mfg_setting") else ""
            if "note" in s:
                L.append("    - %s %s %s [%s]: %s" % (brand, typ, stage, terr, s["note"]))
            else:
                L.append("    - %s %s %s [%s]%s: %s -> %s"
                         % (brand, typ, stage, terr, lot, s["was"], s["now"]))
    if d["errors"]:
        L.append("- Request errors: %d (first: %s)" % (len(d["errors"]), d["errors"][0]))
    if not L:
        L.append("- No differences from the committed snapshot.")
    return "\n".join(L)


def build_report(baseline, snapshot, obs):
    exp_images, exp_settings = expectations(snapshot)
    d = diff(baseline, exp_images, exp_settings, obs)
    return {
        "verdict": "changed" if d["changed"] else "unchanged",
        "checked_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "snapshot_generated": snapshot.get("generated"),
        "baseline_generated": baseline.get("generated"),
        "requests": (1 + len(obs["brands"])
                     + sum(len(v) for v in obs["types"].values())
                     + len(obs["images"])
                     + sum(len(v) for v in obs["sentinels"].values())),
        "summary": summarize(d),
        "delta": d,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--write-baseline", action="store_true",
                    help="rebuild data/watch_baseline.json from data/raw/types.jsonl")
    ap.add_argument("--offline", metavar="FILE",
                    help="diff a previously captured observation instead of crawling")
    ap.add_argument("--save-observation", metavar="FILE",
                    help="write the raw live observation for later offline diffing")
    ap.add_argument("--out", metavar="FILE", help="also write the JSON report here")
    a = ap.parse_args()

    if a.write_baseline:
        print(json.dumps(write_baseline()), flush=True)
        return 0

    if not os.path.exists(BASELINE):
        print(json.dumps({"verdict": "error",
                          "error": "missing %s; run --write-baseline" % BASELINE}))
        return 2

    baseline = json.load(open(BASELINE))
    snapshot = json.load(open(SNAPSHOT))

    if a.offline:
        obs = json.load(open(a.offline))
    else:
        exp_images, _ = expectations(snapshot)
        obs = collect(baseline, exp_images,
                      progress=lambda stage, n: print("  %s: %d" % (stage, n),
                                                      file=sys.stderr, flush=True))
        if a.save_observation:
            with open(a.save_observation, "w") as f:
                json.dump(obs, f, ensure_ascii=False)

    report = build_report(baseline, snapshot, obs)
    out = json.dumps(report, ensure_ascii=False, indent=1)
    print(out)
    if a.out:
        with open(a.out, "w") as f:
            f.write(out + "\n")
    return 1 if report["verdict"] == "changed" else 0


if __name__ == "__main__":
    sys.exit(main())
