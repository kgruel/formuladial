#!/usr/bin/env python3
"""Offline lookup for Baby Brezza powder settings, both machines.

    ./lookup.py similac 360              # both machines, each row tagged
    ./lookup.py kendamil -m pro          # original Formula Pro only
    ./lookup.py --upc 070074680644       # barcode (Advanced data only)
    ./lookup.py --brands -m pro -t Canada
    ./lookup.py similac --alt-only       # formulas with a lot-number variant
    ./lookup.py similac 360 --lot 11X    # numbers for a lot-11 Advanced

Results are tagged ADVANCED or PRO because the two machines mix differently and
the numbers are not interchangeable. Matching is case- and accent-insensitive;
every space-separated term must appear in "brand type stage".
"""
import argparse, json, os, re, sys, unicodedata

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "formula_settings.json")
TAG = {"advanced": "ADVANCED", "pro": "PRO"}


def fold(s):
    """Casefold and strip accents so 'nestle' matches 'Nestlé'."""
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c)).casefold()


def load():
    if not os.path.exists(DATA):
        sys.exit(f"{DATA} not found — run the crawlers then build_dataset.py")
    with open(DATA) as f:
        return json.load(f)


def show(recs, territory_filter, lot=""):
    """Print results. A lot number starting 11 selects Baby Brezza's alternate
    settings for Formula Pro Advanced and Advanced WiFi machines."""
    if not recs:
        print("No match.")
        return
    alt_active = lot.strip().upper().startswith("11")
    w = max(len(f"{r['brand']} — {r['type']}") for r in recs)
    for r in recs:
        setting = r["alt_setting"] if (alt_active and "alt_setting" in r) else r["setting"]
        # The dial runs 1-10, so a published 0 is not a number to turn it to.
        if isinstance(setting, int) and setting > 0:
            cell = f"setting {setting:>2}"
        else:
            cell = f"{'NO DIAL POSITION' if setting == 0 else setting:>16}"
        stage = f"stage {r['stage']}" if r["stage"] else "no stage"
        if "alt_setting" not in r:
            alt = ""
        elif alt_active:
            alt = f"   [standard machine: {r['setting']}]"
        else:
            alt = f"   [lot 11… → {r['alt_setting']}]"
        print(f"  {TAG[r['model']]:<8} {cell}   "
              f"{r['brand'] + ' — ' + r['type']:<{w}}  {stage}{alt}")
        if not territory_filter:
            t = r["territories"]
            where = ", ".join(t) if len(t) <= 4 else f"{', '.join(t[:3])} +{len(t)-3} more"
            print(f"{'':>11}{where}")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("terms", nargs="*", help="words to match against brand/type/stage")
    p.add_argument("--upc", help="barcode on the tin (Formula Pro Advanced data only)")
    p.add_argument("-m", "--model", choices=["pro", "advanced", "all"], default="all",
                   help="which machine (default: both, each row tagged)")
    p.add_argument("-t", "--territory", help="restrict to a territory (substring)")
    p.add_argument("--brands", action="store_true", help="list brands instead of settings")
    p.add_argument("--lot", default="",
                   help="machine lot number; one starting 11 selects the alternate settings")
    p.add_argument("--alt-only", action="store_true",
                   help="only formulas with a lot-number alternate setting")
    p.add_argument("--json", action="store_true", help="raw JSON output")
    a = p.parse_args()

    data = load()
    terr = fold(a.territory) if a.territory else None
    recs = [r for r in data["records"] if a.model in ("all", r["model"])]
    if a.alt_only:
        recs = [r for r in recs if "alt_setting" in r]
    if terr:
        recs = [r for r in recs if any(terr in fold(t) for t in r["territories"])]

    if a.upc:
        want = re.sub(r"[^0-9]", "", a.upc)
        alt = want[1:] if len(want) == 13 and want.startswith("0") else None
        hits = [r for r in recs
                if any(re.sub(r"[^0-9]", "", u) in (want, alt) for u in r["upc"])]
        if not hits and a.model == "pro":
            print("The original Formula Pro dataset carries no barcodes — "
                  "search by brand name instead.")
            return
    elif a.brands:
        names = sorted({r["brand"] for r in recs}, key=fold)
        print("\n".join(names) or "No brands for that filter.")
        return
    else:
        if not a.terms:
            p.error("give search terms, --upc, or --brands")
        terms = [fold(t) for t in a.terms]
        hits = [r for r in recs
                if all(t in fold(f"{r['brand']} {r['type']} {r['stage']}") for t in terms)]

    if a.json:
        print(json.dumps(hits, indent=2, ensure_ascii=False))
        return
    show(hits, terr, a.lot)
    if hits:
        models = {r["model"] for r in hits}
        print(f"\n  {len(hits)} result(s).", end="")
        if models == {"advanced", "pro"}:
            print("  PRO and ADVANCED numbers are not interchangeable.")
        else:
            print(f"  {TAG[models.pop()]} only.")


if __name__ == "__main__":
    main()
