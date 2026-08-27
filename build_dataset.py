"""Fold each crawl into its own dataset.

Two machines, two backends, two datasets -- and two files, because one is live
and the other is frozen:

  data/raw/settings.jsonl       -- the current API (crawlers/api.py), the Formula
                                   Pro Advanced line, still maintained
                                   -> site/data/formula_settings.json
  data/legacy/legacy_pro.jsonl  -- the retired backend (crawlers/legacy_api.py),
                                   the original Formula Pro (FRP0045), frozen
                                   -> site/data/legacy_formula_pro.json

They are published apart so neither file carries the other's claim to freshness:
the live snapshot is stamped `generated` and rebuilt monthly, the historical one
records when it was crawled and is never regenerated.  Which machine a record
belongs to is the file it is in, so no record carries a `model` field.

The current API filters each record's `territory` array down to the territory
you asked about, so the raw crawl holds one row per (territory, brand, type,
stage).  Rows that agree on (brand, type, stage, setting) are merged here into
a single record with a list of territories.  Rows that *disagree* on the
setting stay separate -- that is the real regional-product case, and collapsing
it would hand someone another region's number.

Settings are kept as written.  The original machine's data says "NOT COMPATIBLE"
for formulas it cannot dispense; the Advanced's says 0, which is not a position
on a dial that runs 1-10.  Both are answers, not gaps, and neither is coerced
into a usable number.
"""
import datetime, json, os, re, sys
from collections import defaultdict
from crawlers.api import BASE, IMAGE_BASE
from crawlers.legacy_api import BASE as LEGACY_BASE

OUT = "site/data/formula_settings.json"
LEGACY_OUT = "site/data/legacy_formula_pro.json"

# The retired backend was walked once and versioned under data/legacy/; this is
# the date of that crawl (`git log -- data/legacy/`), not of this build.
LEGACY_CRAWLED = "2026-08-26"


def norm_setting(v):
    """Keep numbers as ints and everything else (e.g. NOT COMPATIBLE) as text."""
    if isinstance(v, int):
        return v
    s = str(v).strip()
    return int(s) if re.fullmatch(r"\d+", s) else (s.upper() or None)


def load_advanced(path="data/raw/settings.jsonl"):
    rows, stats = [], defaultdict(int)
    if not os.path.exists(path):
        return rows, dict(stats)
    with open(path) as f:
        for line in f:
            try:
                row = json.loads(line)
            except ValueError:
                stats["unparseable"] += 1
                continue
            rec = row.get("record")
            if not rec or rec.get("setting") is None:
                stats["no_setting"] += 1
                continue
            for terr in (rec.get("territory") or [row["query"][0]]):
                rows.append({
                    "brand": rec["brand"], "type": rec["type"],
                    "stage": rec["stage"] or "", "setting": norm_setting(rec["setting"]),
                    "territory": terr, "upc": rec.get("upc") or [],
                    "image": (rec.get("image") or [None])[0],
                })
    return rows, dict(stats)


def load_pro(path="data/legacy/legacy_pro.jsonl"):
    rows, stats = [], defaultdict(int)
    if not os.path.exists(path):
        return rows, dict(stats)
    with open(path) as f:
        for line in f:
            try:
                r = json.loads(line)
            except ValueError:
                stats["unparseable"] += 1
                continue
            if r.get("error"):
                stats["errors"] += 1
            for entry in r.get("entries", []):
                if not entry["rows"]:
                    stats["empty_tables"] += 1
                for stage, setting in entry["rows"]:
                    s = norm_setting(setting)
                    if s is None:
                        stats["blank_setting"] += 1
                        continue
                    rows.append({
                        "brand": r["brand"], "type": entry["type"],
                        "stage": "" if stage.upper() in ("N/A", "") else stage,
                        "setting": s, "territory": r["territory"], "upc": [], "image": None,
                    })
    return rows, dict(stats)


def merge(rows):
    """Collapse identical answers across territories; keep disagreements apart."""
    groups = defaultdict(lambda: {"territories": set(), "upc": set(), "image": None})
    for r in rows:
        key = (r["brand"], r["type"], r["stage"], r["setting"])
        g = groups[key]
        g["territories"].add(r["territory"])
        g["upc"].update(r["upc"])
        g["image"] = g["image"] or r["image"]
    out = []
    for (brand, typ, stage, setting), g in groups.items():
        out.append({"brand": brand, "type": typ, "stage": stage,
                    "setting": setting, "territories": sorted(g["territories"]),
                    "upc": sorted(g["upc"]), "image": g["image"]})
    out.sort(key=lambda r: (r["brand"].lower(), r["type"].lower(), r["stage"]))
    return out


def attach_alt(records, path="data/raw/alt_settings.jsonl"):
    """Attach the lot-number alternate setting where it differs.

    Baby Brezza asks Formula Pro Advanced and Advanced WiFi owners for the
    machine's lot number and queries `alt_mfg_setting=true` when the prefix is
    "11".  The Mini is excluded from that branch and always uses the default.
    crawl_alt.py probed one representative query per Advanced record; the
    queries were built from `territories[0]`, so they match back 1:1.
    """
    if not os.path.exists(path):
        return 0
    alt = {}
    with open(path) as f:
        for line in f:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if isinstance(r["default"], str) or isinstance(r["alt"], str):
                continue  # transport error, not an answer
            if r["default"] != r["alt"] and r["alt"] is not None:
                t, b, ty, st = r["query"]
                alt[(b, ty, st, t)] = norm_setting(r["alt"])
    n = 0
    for rec in records:
        if not rec["territories"]:
            continue
        key = (rec["brand"], rec["type"], rec["stage"], rec["territories"][0])
        if key in alt:
            rec["alt_setting"] = alt[key]
            n += 1
    return n


def attach_dates(records, path="data/raw/image_dates.jsonl"):
    """Attach each Advanced record's image date as a freshness signal.

    Nothing in the settings API carries a timestamp.  Every Advanced record
    points at an image on babybrezzacloud.com, and those files answer HEAD with
    a Last-Modified header -- see crawl_images.py.

    This dates the *image*, not the number.  A record whose picture was uploaded
    in 2023 may have had its setting revised since without the picture changing,
    so treat it as "not touched since", never as "verified on".
    """
    if not os.path.exists(path):
        return 0
    when = {}
    with open(path) as f:
        for line in f:
            try:
                r = json.loads(line)
            except ValueError:
                continue
            if r.get("last_modified"):
                when[r["image"]] = r["last_modified"]
    n = 0
    for rec in records:
        d = when.get(rec.get("image"))
        if d:
            rec["image_date"] = d
            n += 1
    return n


def find_conflicts(records):
    """One (brand, type, stage, territory) answering with two settings."""
    by_query = defaultdict(set)
    for r in records:
        for t in r["territories"]:
            by_query[(r["brand"], r["type"], r["stage"], t)].add(str(r["setting"]))
    return [{"brand": b, "type": ty, "stage": s, "territory": t, "settings": sorted(v)}
            for (b, ty, s, t), v in by_query.items() if len(v) > 1]


def main():
    adv_rows, adv_stats = load_advanced()
    pro_rows, pro_stats = load_pro()
    if not adv_rows and not pro_rows:
        sys.exit("no crawl output found -- run the crawlers first")
    advanced, pro = merge(adv_rows), merge(pro_rows)
    n_alt = attach_alt(advanced)
    n_dated = attach_dates(advanced)
    adv_conflicts, pro_conflicts = find_conflicts(advanced), find_conflicts(pro)

    live = {
        # Top-level provenance so a diff of the versioned snapshot is self-describing.
        "generated": datetime.datetime.now(datetime.timezone.utc).date().isoformat(),
        "label": "Formula Pro Advanced",
        "note": "Covers Formula Pro Advanced, Advanced WiFi and Mini — "
                "Baby Brezza's finder sends the identical query for all three. "
                "Enter your lot number below if it starts with 11 — 99 formulas "
                "have a second setting for those machines. The Mini never uses it.",
        "source": BASE,
        "counts": {
            "records": len(advanced),
            "brands": len({r["brand"] for r in advanced}),
            "territories": len({t for r in advanced for t in r["territories"]}),
            "upcs": len({u for r in advanced for u in r["upc"]}),
            "not_compatible": sum(1 for r in advanced if r["setting"] == "NOT COMPATIBLE"),
            # The dial runs 1-10; a published 0 is not a position on it.
            "zero": sum(1 for r in advanced if r["setting"] == 0),
            "alt": n_alt,
            "dated": n_dated,
            "since_2026": sum(1 for r in advanced if r.get("image_date", "") >= "2026-01-01"),
            "newest": max((r.get("image_date", "") for r in advanced), default="") or None,
            "conflicts": len(adv_conflicts),
        },
        "image_base": IMAGE_BASE,
        "crawl_stats": dict(sorted(adv_stats.items())),
        "conflicts": adv_conflicts,
        "records": advanced,
    }

    # No `generated` stamp here on purpose: this data has not moved since the
    # backend serving it was retired, and re-dating it every monthly rebuild
    # would claim a freshness it does not have.  What it can honestly carry is
    # when we took the copy.
    historical = {
        "label": "Formula Pro (original)",
        "note": "Kept for the record. The discontinued FRP0045, served by a "
                "backend Baby Brezza retired — its data appears frozen since "
                "around 2022, and 27% of the settings in its Advanced copy have "
                "changed on the live one since. No barcodes, no lot-number "
                "variants. Treat these numbers as a starting point.",
        "source": LEGACY_BASE,
        "provenance": {
            "crawled": LEGACY_CRAWLED,
            "upstream_frozen": "~2022",
            "drift_estimate": "~27%: the same retired backend also holds a frozen copy "
                              "of the Advanced line, which disagrees with the live API "
                              "on 81 of 299 comparable entries (staleness.py -> "
                              "data/staleness.json). An estimate of how far these "
                              "numbers would have drifted, not a correction — there "
                              "is nothing to check them against.",
            "note": "Crawled once from the retired backend, versioned under "
                    "data/legacy/ and never regenerated; nothing schedules it. "
                    "See docs/HOW-IT-WORKS.md.",
        },
        "counts": {
            "records": len(pro),
            "brands": len({r["brand"] for r in pro}),
            "territories": len({t for r in pro for t in r["territories"]}),
            "not_compatible": sum(1 for r in pro if r["setting"] == "NOT COMPATIBLE"),
            "conflicts": len(pro_conflicts),
        },
        "crawl_stats": dict(sorted(pro_stats.items())),
        "conflicts": pro_conflicts,
        "records": pro,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    for path, doc in ((OUT, live), (LEGACY_OUT, historical)):
        with open(path, "w") as f:
            json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))

    print("advanced", json.dumps(live["counts"]))
    print("original", json.dumps(historical["counts"]))
    print("crawl_stats:", json.dumps({"advanced": live["crawl_stats"],
                                      "original": historical["crawl_stats"]}))
    print(f"alternate (lot 11…) settings attached: {n_alt}")
    print(f"records dated from image Last-Modified: {n_dated}")
    for name, cs in (("advanced", adv_conflicts), ("original", pro_conflicts)):
        print(f"conflicts ({name}): {len(cs)}" + (f"  e.g. {cs[:2]}" if cs else ""))
    print(f"wrote {OUT} ({os.path.getsize(OUT)/1e6:.2f} MB) "
          f"— live, generated {live['generated']}")
    print(f"wrote {LEGACY_OUT} ({os.path.getsize(LEGACY_OUT)/1e6:.2f} MB) "
          f"— frozen, crawled {LEGACY_CRAWLED}")


if __name__ == "__main__":
    main()
