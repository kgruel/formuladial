"""Fold the current Formula Pro Advanced-family crawl into its dataset.

  data/raw/settings.jsonl       -- the current API (crawlers/api.py), the Formula
                                   Pro Advanced line, still maintained
                                   -> site/data/formula_settings.json

The discontinued original Formula Pro is deliberately outside the app.  Its
frozen source remains under data/legacy/ as a historical archive, but this
builder neither reads nor publishes it.

The current API filters each record's `territory` array down to the territory
you asked about, so the raw crawl holds one row per (territory, brand, type,
stage).  Rows that agree on (brand, type, stage, setting) are merged here into
a single record with a list of source-query territories.  Rows that *disagree*
on the setting stay separate -- that is the real regional-product case, and
collapsing it would hand someone another region's number.  The small
`unavailable` collection retains successful source answers which name a formula
but do not publish a usable dial setting, so they can never be mistaken for a
search miss.

Settings are kept as written. The current API sometimes says 0, which is not a
position on a dial that runs 1-10. It is an upstream answer rather than a gap,
and is never coerced into a usable number.
"""
import datetime, hashlib, json, os, re, sys
from collections import defaultdict
from crawlers.api import BASE, IMAGE_BASE

OUT = "site/data/formula_settings.json"
OBSERVATION = "data/crawl_observation.json"
HISTORY = "data/setting_history.json"
RAW_SETTINGS = "data/raw/settings.jsonl"


def file_digest(path):
    h = hashlib.sha256()
    with open(path, "rb") as source:
        for block in iter(lambda: source.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def observed_date(path=OBSERVATION, raw_path=RAW_SETTINGS):
    """The crawl date, only when its manifest matches the exact raw input."""
    try:
        with open(path) as source:
            manifest = json.load(source)
    except (FileNotFoundError, ValueError):
        return None
    if not os.path.exists(raw_path) or manifest.get("settings_sha256") != file_digest(raw_path):
        return None
    return manifest.get("observed")


def setting_map(snapshot):
    """Expand merged records into source-market values for history diffs."""
    values = {}
    for row in (snapshot or {}).get("records", []):
        for territory in row.get("territories", []):
            key = (row["brand"], row["type"], row.get("stage", ""), territory)
            values[key] = {"setting": row.get("setting"),
                           "alt_setting": row.get("alt_setting")}
    return values


def update_history(previous, current, observed, path=HISTORY):
    """Append real setting movements seen between complete current crawls."""
    try:
        with open(path) as source:
            doc = json.load(source)
    except (FileNotFoundError, ValueError):
        doc = {"events": []}
    events = doc.setdefault("events", [])
    known = {(e["observed"], e["brand"], e["type"], e.get("stage", ""),
              e["territory"], e["field"], str(e.get("from")), str(e.get("to")))
             for e in events}
    before, after = setting_map(previous), setting_map(current)
    for key in sorted(before.keys() & after.keys()):
        brand, typ, stage, territory = key
        for field in ("setting", "alt_setting"):
            old, new = before[key].get(field), after[key].get(field)
            if old == new:
                continue
            signature = (observed, brand, typ, stage, territory, field,
                         str(old), str(new))
            if signature in known:
                continue
            events.append({"observed": observed, "brand": brand, "type": typ,
                           "stage": stage, "territory": territory, "field": field,
                           "from": old, "to": new})
            known.add(signature)
    events.sort(key=lambda e: (e["observed"], e["brand"].lower(), e["type"].lower(),
                               e.get("stage", ""), e["territory"], e["field"]))
    with open(path, "w") as target:
        json.dump(doc, target, indent=2, ensure_ascii=False)
        target.write("\n")
    return len(events)


def norm_setting(v):
    """Keep numbers as ints and everything else (e.g. NOT COMPATIBLE) as text."""
    if v is None:
        return None
    if isinstance(v, int):
        return v
    s = str(v).strip()
    return int(s) if re.fullmatch(r"\d+", s) else (s.upper() or None)


def query_of(row):
    """Return a valid source query, or None for a row we must fail closed on."""
    try:
        query = row["query"]
    except (KeyError, TypeError):
        return None
    if not isinstance(query, (list, tuple)) or len(query) != 4:
        return None
    if not all(isinstance(part, str) for part in query):
        return None
    return tuple(query)


def source_row(query, rec):
    """Normalize one successful API record without losing its queried market."""
    if not isinstance(rec, dict):
        return None
    try:
        brand, typ = rec["brand"], rec["type"]
    except KeyError:
        return None
    if not isinstance(brand, str) or not isinstance(typ, str):
        return None
    stage = rec.get("stage") or ""
    if not isinstance(stage, str):
        return None
    territories = rec.get("territory") or []
    # The upstream API promises a response restricted to the market asked for.
    # Never silently re-label a response if that invariant stops holding.
    if not isinstance(territories, list) or query[0] not in territories:
        return None
    upc = rec.get("upc") or []
    image = rec.get("image") or []
    if (not isinstance(upc, list) or not all(isinstance(v, str) for v in upc)
            or not isinstance(image, list) or not all(isinstance(v, str) for v in image)):
        return None
    return {
        "brand": brand, "type": typ, "stage": stage,
        # This is the source-query territory, rather than an inferred list
        # returned by the endpoint. It makes regional provenance explicit.
        "territory": query[0], "upc": upc, "image": image[0] if image else None,
    }


def load_advanced(path="data/raw/settings.jsonl"):
    """Load successful dial answers and successful known-but-unavailable answers.

    Returns `(actionable_rows, unavailable_rows, stats)`.  Any transport or
    structural failure remains visible in `stats`, causing `main()` to refuse
    publication rather than turn a partial crawl into a confident snapshot.
    """
    rows, unavailable, stats, latest = [], [], defaultdict(int), {}
    if not os.path.exists(path):
        return rows, unavailable, dict(stats)
    with open(path) as f:
        for line in f:
            try:
                row = json.loads(line)
            except ValueError:
                stats["unparseable"] += 1
                continue
            query = query_of(row)
            if query is None:
                stats["malformed"] += 1
                continue
            latest[query] = row
    stats["queries"] = len(latest)
    for query, row in latest.items():
        if row.get("error") not in (None, "no-match"):
            stats["errors"] += 1
            continue
        if row.get("no_match") is True or row.get("error") == "no-match":
            stats["no_match"] += 1
            # Empty stages are an API limitation that the crawler identified
            # explicitly. A non-empty-stage no-match remains distinguishable
            # for any future upstream behaviour.
            reason = "no_stage" if not query[3] else "no_match"
            stats[reason] += 1
            unavailable.append({"brand": query[1], "type": query[2],
                                "stage": query[3], "territory": query[0],
                                "reason": reason, "upc": [], "image": None})
            continue
        rec = row.get("record")
        normalized = source_row(query, rec)
        if normalized is None:
            stats["malformed"] += 1
            continue
        setting = norm_setting(rec.get("setting"))
        if setting is None:
            # A successful, structured response with setting:null (or a blank
            # setting) is an upstream answer, but not a dial value we can use.
            stats["no_setting"] += 1
            normalized["reason"] = "no_setting"
            unavailable.append(normalized)
            continue
        normalized["setting"] = setting
        rows.append(normalized)
    return rows, unavailable, dict(stats)


def merge(rows):
    """Collapse identical answers across territories; keep disagreements apart.

    `territory_variants` is emitted only when UPC/image metadata differs within
    an otherwise identical setting. That keeps the normal payload compact while
    preserving the source-market association where a representative image or
    UPC would otherwise be misleading.
    """
    groups = defaultdict(lambda: {"territories": set(), "upc": set(), "image": None,
                                  "variants": defaultdict(set)})
    for r in rows:
        key = (r["brand"], r["type"], r["stage"], r["setting"])
        g = groups[key]
        g["territories"].add(r["territory"])
        g["upc"].update(r["upc"])
        g["image"] = g["image"] or r["image"]
        g["variants"][(tuple(sorted(r["upc"])), r["image"])].add(r["territory"])
    out = []
    for (brand, typ, stage, setting), g in groups.items():
        record = {"brand": brand, "type": typ, "stage": stage,
                  "setting": setting, "territories": sorted(g["territories"]),
                  "upc": sorted(g["upc"]), "image": g["image"]}
        if len(g["variants"]) > 1:
            record["territory_variants"] = [
                {"territories": sorted(territories), "upc": list(upc), "image": image}
                for (upc, image), territories in sorted(
                    g["variants"].items(), key=lambda item: (item[0][0], item[0][1] or ""))
            ]
        out.append(record)
    out.sort(key=lambda r: (r["brand"].lower(), r["type"].lower(), r["stage"]))
    return out


def merge_unavailable(rows):
    """Compact equal unavailable outcomes without erasing source territories."""
    groups = defaultdict(lambda: {"territories": set()})
    for row in rows:
        key = (row["brand"], row["type"], row["stage"], row["reason"],
               tuple(sorted(row["upc"])), row["image"])
        groups[key]["territories"].add(row["territory"])
    out = []
    for (brand, typ, stage, reason, upc, image), group in groups.items():
        out.append({"brand": brand, "type": typ, "stage": stage,
                    "territories": sorted(group["territories"]), "reason": reason,
                    "upc": list(upc), "image": image})
    out.sort(key=lambda r: (r["brand"].lower(), r["type"].lower(), r["stage"], r["reason"]))
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
        # Usually a record has one image across all of its territories. For
        # the small number that do not, keep the image date tied to that
        # source-market variant too; the top-level date remains the compact
        # representative used by older consumers.
        for variant in rec.get("territory_variants", []):
            d = when.get(variant.get("image"))
            if d:
                variant["image_date"] = d
    return n


def find_conflicts(records):
    """One (brand, type, stage, territory) answering with two settings."""
    by_query = defaultdict(set)
    for r in records:
        for t in r["territories"]:
            by_query[(r["brand"], r["type"], r["stage"], t)].add(str(r["setting"]))
    return [{"brand": b, "type": ty, "stage": s, "territory": t, "settings": sorted(v)}
            for (b, ty, s, t), v in by_query.items() if len(v) > 1]


def counts(records, unavailable, conflicts, **details):
    """Summary and integrity signals published with the current snapshot."""
    return {
        "records": len(records),
        "brands": len({r["brand"] for r in records}),
        "territories": len({t for r in records for t in r["territories"]}),
        "not_compatible": sum(1 for r in records if r["setting"] == "NOT COMPATIBLE"),
        # `records` intentionally remains the backwards-compatible count of
        # actionable dial answers. The two unavailable counts tell consumers
        # how many successful source queries produced a known non-answer.
        "unavailable_records": len(unavailable),
        "unavailable_queries": sum(len(r["territories"]) for r in unavailable),
        "conflicts": len(conflicts),
        **details,
    }


def main():
    try:
        with open(OUT) as source:
            previous = json.load(source)
    except (FileNotFoundError, ValueError):
        previous = None
    adv_rows, unavailable_rows, adv_stats = load_advanced()
    bad = {k: adv_stats.get(k, 0) for k in ("unparseable", "malformed", "errors")
           if adv_stats.get(k, 0)}
    if bad:
        sys.exit(f"refusing to build from incomplete settings crawl: {bad}")
    if not adv_rows:
        sys.exit("no crawl output found -- run the crawlers first")
    observed = observed_date()
    if not observed:
        sys.exit("crawl observation does not match settings input -- run "
                 "python3 scripts/record_observation.py after the crawl completes")
    advanced = merge(adv_rows)
    unavailable = merge_unavailable(unavailable_rows)
    n_alt = attach_alt(advanced)
    n_dated = attach_dates(advanced)
    adv_conflicts = find_conflicts(advanced)

    live = {
        # Top-level provenance so a diff of the versioned snapshot is self-describing.
        "generated": datetime.datetime.now(datetime.timezone.utc).date().isoformat(),
        "observed": observed,
        "label": "Formula Pro Advanced",
        "note": "Covers Formula Pro Advanced, Advanced WiFi and Mini — "
                "Baby Brezza's finder sends the identical query for all three. "
                "Enter your lot number below if it starts with 11 — 99 formulas "
                "have a second setting for those machines. The Mini never uses it.",
        "source": BASE,
        "counts": counts(
            advanced, unavailable, adv_conflicts,
            upcs=len({u for r in advanced for u in r["upc"]}),
            # The dial runs 1-10; a published 0 is not a position on it.
            zero=sum(1 for r in advanced if r["setting"] == 0),
            alt=n_alt,
            dated=n_dated,
            since_2026=sum(1 for r in advanced if r.get("image_date", "") >= "2026-01-01"),
            newest=max((r.get("image_date", "") for r in advanced), default="") or None,
        ),
        "image_base": IMAGE_BASE,
        "crawl_stats": dict(sorted(adv_stats.items())),
        "conflicts": adv_conflicts,
        "records": advanced,
        "unavailable": unavailable,
    }

    history_count = update_history(previous, live, observed)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(live, f, ensure_ascii=False, separators=(",", ":"))

    print("advanced", json.dumps(live["counts"]))
    print("crawl_stats:", json.dumps({"advanced": live["crawl_stats"]}))
    print(f"alternate (lot 11…) settings attached: {n_alt}")
    print(f"records dated from image Last-Modified: {n_dated}")
    print(f"conflicts (advanced): {len(adv_conflicts)}" +
          (f"  e.g. {adv_conflicts[:2]}" if adv_conflicts else ""))
    print(f"setting-history events retained: {history_count}")
    print(f"wrote {OUT} ({os.path.getsize(OUT)/1e6:.2f} MB) "
          f"— live, generated {live['generated']}")


if __name__ == "__main__":
    main()
