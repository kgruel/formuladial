"""Fold both crawls into one dataset.

Two machines, two backends, two datasets:

  advanced  settings.jsonl     -- the current API (api.py), Formula Pro Advanced
  pro       legacy_pro.jsonl   -- the retired backend (legacy_api.py), original
                                  Formula Pro (FRP0045)

The current API filters each record's `territory` array down to the territory
you asked about, so the raw crawl holds one row per (territory, brand, type,
stage).  Rows that agree on (model, brand, type, stage, setting) are merged here
into a single record with a list of territories.  Rows that *disagree* on the
setting stay separate -- that is the real regional-product case, and collapsing
it would hand someone another region's number.

Settings are kept as written.  The original machine's data says "NOT COMPATIBLE"
for formulas it cannot dispense; the Advanced's says 0, which is not a position
on a dial that runs 1-10.  Both are answers, not gaps, and neither is coerced
into a usable number.
"""
import json, os, re, sys
from collections import defaultdict
from api import BASE, IMAGE_BASE
from legacy_api import BASE as LEGACY_BASE

OUT = "formula_settings.json"


def norm_setting(v):
    """Keep numbers as ints and everything else (e.g. NOT COMPATIBLE) as text."""
    if isinstance(v, int):
        return v
    s = str(v).strip()
    return int(s) if re.fullmatch(r"\d+", s) else (s.upper() or None)


def load_advanced(path="settings.jsonl"):
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
                    "model": "advanced", "brand": rec["brand"], "type": rec["type"],
                    "stage": rec["stage"] or "", "setting": norm_setting(rec["setting"]),
                    "territory": terr, "upc": rec.get("upc") or [],
                    "image": (rec.get("image") or [None])[0],
                })
    return rows, dict(stats)


def load_pro(path="legacy_pro.jsonl"):
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
                        "model": "pro", "brand": r["brand"], "type": entry["type"],
                        "stage": "" if stage.upper() in ("N/A", "") else stage,
                        "setting": s, "territory": r["territory"], "upc": [], "image": None,
                    })
    return rows, dict(stats)


def merge(rows):
    """Collapse identical answers across territories; keep disagreements apart."""
    groups = defaultdict(lambda: {"territories": set(), "upc": set(), "image": None})
    for r in rows:
        key = (r["model"], r["brand"], r["type"], r["stage"], r["setting"])
        g = groups[key]
        g["territories"].add(r["territory"])
        g["upc"].update(r["upc"])
        g["image"] = g["image"] or r["image"]
    out = []
    for (model, brand, typ, stage, setting), g in groups.items():
        out.append({"model": model, "brand": brand, "type": typ, "stage": stage,
                    "setting": setting, "territories": sorted(g["territories"]),
                    "upc": sorted(g["upc"]), "image": g["image"]})
    out.sort(key=lambda r: (r["model"], r["brand"].lower(), r["type"].lower(), r["stage"]))
    return out


def attach_alt(records, path="alt_settings.jsonl"):
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
        if rec["model"] != "advanced" or not rec["territories"]:
            continue
        key = (rec["brand"], rec["type"], rec["stage"], rec["territories"][0])
        if key in alt:
            rec["alt_setting"] = alt[key]
            n += 1
    return n


def attach_dates(records, path="image_dates.jsonl"):
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
            rec["updated"] = d
            n += 1
    return n


def find_conflicts(records):
    """One (model, brand, type, stage, territory) answering with two settings."""
    by_query = defaultdict(set)
    for r in records:
        for t in r["territories"]:
            by_query[(r["model"], r["brand"], r["type"], r["stage"], t)].add(str(r["setting"]))
    return [{"model": m, "brand": b, "type": ty, "stage": s, "territory": t,
             "settings": sorted(v)}
            for (m, b, ty, s, t), v in by_query.items() if len(v) > 1]


def main():
    adv_rows, adv_stats = load_advanced()
    pro_rows, pro_stats = load_pro()
    if not adv_rows and not pro_rows:
        sys.exit("no crawl output found -- run the crawlers first")
    records = merge(adv_rows + pro_rows)
    n_alt = attach_alt(records)
    n_dated = attach_dates(records)
    conflicts = find_conflicts(records)

    def counts(model):
        rs = [r for r in records if r["model"] == model]
        return {
            "records": len(rs),
            "brands": len({r["brand"] for r in rs}),
            "territories": len({t for r in rs for t in r["territories"]}),
            "upcs": len({u for r in rs for u in r["upc"]}),
            "not_compatible": sum(1 for r in rs if r["setting"] == "NOT COMPATIBLE"),
            # The dial runs 1-10; a published 0 is not a position on it.
            "zero": sum(1 for r in rs if r["setting"] == 0),
            "alt": sum(1 for r in rs if "alt_setting" in r),
            "dated": sum(1 for r in rs if "updated" in r),
            "since_2026": sum(1 for r in rs if r.get("updated", "") >= "2026-01-01"),
            "newest": max((r.get("updated", "") for r in rs), default="") or None,
        }

    data = {
        "models": {
            "advanced": {
                "label": "Formula Pro Advanced",
                "note": "Covers Formula Pro Advanced, Advanced WiFi and Mini — "
                        "Baby Brezza's finder sends the identical query for all three. "
                        "Enter your lot number below if it starts with 11 — 99 formulas "
                        "have a second setting for those machines. The Mini never uses it.",
                "source": BASE,
                "counts": counts("advanced"),
            },
            "pro": {
                "label": "Formula Pro (original)",
                "note": "Kept for the record. The discontinued FRP0045, served by a "
                        "backend Baby Brezza retired — its data appears frozen since "
                        "around 2022, and 27% of the settings in its Advanced copy have "
                        "changed on the live one since. No barcodes, no lot-number "
                        "variants. Treat these numbers as a starting point.",
                "source": LEGACY_BASE,
                "counts": counts("pro"),
            },
        },
        "image_base": IMAGE_BASE,
        "crawl_stats": {"advanced": adv_stats, "pro": pro_stats},
        "conflicts": conflicts,
        "records": records,
    }
    with open(OUT, "w") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    for m, meta in data["models"].items():
        print(f"{m:9s} {json.dumps(meta['counts'])}")
    print("crawl_stats:", json.dumps(data["crawl_stats"]))
    print(f"alternate (lot 11…) settings attached: {n_alt}")
    print(f"records dated from image Last-Modified: {n_dated}")
    print(f"conflicts: {len(conflicts)}" + (f"  e.g. {conflicts[:2]}" if conflicts else ""))
    print(f"wrote {OUT} ({os.path.getsize(OUT)/1e6:.2f} MB)")


if __name__ == "__main__":
    main()
